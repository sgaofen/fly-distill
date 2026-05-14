"""End-to-end production orchestrator.

Goal: start it, walk away, come back to ~14k canonical JSONs.

Behavior:
  - Spawns pipeline.py (distill) and qa_monitor.py (audit) as supervised
    subprocesses
  - If either crashes (uncaught exception, OOM, etc.), supervisor restarts it
    after a backoff (idempotency in those scripts means re-runs are safe)
  - Both scripts already handle quota-exhaustion internally — supervisor only
    handles process-level crashes
  - Append-only progress log to runs/<batch_id>/orchestrator.log
  - Graceful Ctrl-C: signals children, waits for in-flight work to drain,
    saves a final summary

Usage:
  python3 src/run_production.py gene_list.txt
  python3 src/run_production.py --resume                  # continue prior batch
  python3 src/run_production.py --check                   # status without starting
"""
import argparse
import json
import os
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "runs"

STOP_REQUESTED = False
CHILDREN = {}     # name → subprocess.Popen


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def handle_sigint(signum, frame):
    global STOP_REQUESTED
    print(f"\n[orchestrator] caught signal {signum} — initiating graceful shutdown", flush=True)
    STOP_REQUESTED = True
    for name, p in CHILDREN.items():
        if p.poll() is None:
            print(f"[orchestrator]   sending SIGTERM to {name} (pid {p.pid})", flush=True)
            try:
                p.terminate()
            except Exception:
                pass


signal.signal(signal.SIGINT, handle_sigint)
signal.signal(signal.SIGTERM, handle_sigint)


def count_progress() -> dict:
    out_dir = ROOT / "output" / "genes"
    qa_dir = ROOT / "output" / "qa"
    canonical = len(list(out_dir.glob("FBgn*.json"))) if out_dir.exists() else 0
    tier1 = 0
    if (qa_dir / "tier1_report.jsonl").exists():
        tier1 = sum(1 for _ in (qa_dir / "tier1_report.jsonl").open())
    tier2 = 0
    if (qa_dir / "tier2_audit_results.jsonl").exists():
        tier2 = sum(1 for _ in (qa_dir / "tier2_audit_results.jsonl").open())
    return {"canonical_count": canonical, "tier1_count": tier1, "tier2_count": tier2}


def supervise(name: str, cmd: list, max_restarts: int = 50, log_path: Path = None) -> dict:
    """Launch subprocess; if it crashes (non-zero exit, non-signal), restart with backoff.
    Returns total run stats."""
    restarts = 0
    backoff = 5
    while not STOP_REQUESTED and restarts < max_restarts:
        log_f = log_path.open("ab") if log_path else None
        print(f"[supervisor:{name}] launching: {' '.join(cmd)}", flush=True)
        try:
            p = subprocess.Popen(cmd, stdout=log_f, stderr=subprocess.STDOUT,
                                 cwd=str(ROOT))
            CHILDREN[name] = p
            rc = p.wait()
        finally:
            if log_f:
                log_f.close()
        del CHILDREN[name]
        if STOP_REQUESTED:
            print(f"[supervisor:{name}] shutting down (stop requested)", flush=True)
            break
        if rc == 0:
            print(f"[supervisor:{name}] exited cleanly", flush=True)
            break
        restarts += 1
        if rc < 0:    # killed by signal
            print(f"[supervisor:{name}] killed by signal {-rc} — restart {restarts} after {backoff}s", flush=True)
        else:
            print(f"[supervisor:{name}] non-zero exit {rc} — restart {restarts} after {backoff}s", flush=True)
        for _ in range(backoff):
            if STOP_REQUESTED:
                return {"name": name, "restarts": restarts, "final_rc": rc, "stopped": True}
            time.sleep(1)
        backoff = min(60, backoff * 2)   # exponential backoff capped at 60s
    return {"name": name, "restarts": restarts}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("gene_list_file", nargs="?")
    ap.add_argument("--harness", choices=["direct", "claude", "sonnet"], default="claude")
    ap.add_argument("--batch-id", default=None)
    ap.add_argument("--check", action="store_true", help="show status only")
    ap.add_argument("--monitor-only", action="store_true",
                    help="run the QA monitor only — assume pipeline already running elsewhere")
    args = ap.parse_args()

    batch_id = args.batch_id or f"prod_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    run_dir = RUNS / batch_id
    run_dir.mkdir(parents=True, exist_ok=True)

    if args.check:
        p = count_progress()
        print(f"# Production status — {now()}")
        print(f"  canonical JSONs:  {p['canonical_count']}")
        print(f"  tier-1 reports:   {p['tier1_count']}")
        print(f"  tier-2 audits:    {p['tier2_count']}")
        return

    print(f"[orchestrator] batch {batch_id} starting at {now()}")
    print(f"[orchestrator] logs in: {run_dir}")
    print(f"[orchestrator] Ctrl-C to stop gracefully (children will drain in-flight)")

    # ----- supervised threads ----------------------------------------
    import threading
    threads = []

    if not args.monitor_only and args.gene_list_file:
        pipeline_cmd = [sys.executable, "src/pipeline.py", args.gene_list_file,
                        "--harness", args.harness, "--batch-id", batch_id]
        pipeline_log = run_dir / "pipeline.log"
        t = threading.Thread(
            target=supervise, args=("pipeline", pipeline_cmd),
            kwargs={"log_path": pipeline_log},
            daemon=True,
        )
        t.start()
        threads.append(t)
        print(f"[orchestrator] pipeline log → {pipeline_log}")

    monitor_cmd = [sys.executable, "src/qa_monitor.py",
                   "--poll-interval-s", "60", "--max-idle-minutes", "30"]
    monitor_log = run_dir / "monitor.log"
    t = threading.Thread(
        target=supervise, args=("monitor", monitor_cmd),
        kwargs={"log_path": monitor_log},
        daemon=True,
    )
    t.start()
    threads.append(t)
    print(f"[orchestrator] monitor log  → {monitor_log}")

    # ----- progress heartbeat ---------------------------------------
    t0 = time.time()
    last_canon = 0
    while not STOP_REQUESTED and any(t.is_alive() for t in threads):
        time.sleep(60)
        p = count_progress()
        delta = p["canonical_count"] - last_canon
        last_canon = p["canonical_count"]
        elapsed_m = (time.time() - t0) / 60
        rate = delta   # per-minute since last heartbeat
        print(f"[orchestrator] +{int(elapsed_m):3}m  canonical={p['canonical_count']:5}  "
              f"tier1={p['tier1_count']:5}  tier2={p['tier2_count']:4}  "
              f"rate={rate}/min", flush=True)

    # ----- wait for clean shutdown ----------------------------------
    print(f"[orchestrator] waiting for supervisor threads to drain...")
    for t in threads:
        t.join(timeout=300)

    p = count_progress()
    print(f"\n[orchestrator] batch {batch_id} ended at {now()}")
    print(f"  canonical: {p['canonical_count']}")
    print(f"  tier-1:    {p['tier1_count']}")
    print(f"  tier-2:    {p['tier2_count']}")


if __name__ == "__main__":
    main()
