"""Autonomous QA monitor — runs while pipeline produces canonical JSONs.

Behavior:
  - Every POLL_INTERVAL_S seconds, scan output/genes/ for new canonical files.
  - For each new gene:
      1. Tier-1 deterministic check → qa_score
      2. If score >= TIER2_THRESHOLD → ACCEPT, no audit needed
      3. Else → fire a sub-agent (tier-2 audit call via z.ai GLM)
      4. If verdict = redistill OR critical bugs found → trigger two-pass re-distill
      5. Re-canonicalize → re-check tier-1
  - Append-only log: output/qa/monitor.jsonl
  - Self-terminating: after MAX_IDLE_MINUTES with no new genes, exits cleanly.

Sub-agent design:
  Each tier-2 audit is one fresh GLM call via call_auditor() in qa_tier2.py.
  Each re-distill is one fresh GLM/Claude Code call via distill_two_pass.
  NO accumulated context across genes — every call has its own fresh prompt.
  This is the "context auto-cleaning" the user asked for: each agent invocation
  is stateless per gene.

Usage:
  python3 src/qa_monitor.py                # auto-detect new canonical files, loop
  python3 src/qa_monitor.py --once         # one-pass, then exit
  python3 src/qa_monitor.py --max-fixes 5  # cap re-distill attempts per cycle
"""
import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from qa import check_one as tier1_check, TIER2_THRESHOLD, REDISTILL_THRESHOLD
from qa_tier2 import audit_one as tier2_audit

GENES_DIR = ROOT / "output" / "genes"
QA_DIR = ROOT / "output" / "qa"
MONITOR_LOG = QA_DIR / "monitor.jsonl"
PROCESSED_FILE = QA_DIR / "monitor_processed.jsonl"


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def append_log(record: dict, path: Path = None):
    path = path or MONITOR_LOG
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def already_processed() -> set:
    """Set of FBgn IDs we've already handled this run-or-past-runs."""
    if not PROCESSED_FILE.exists():
        return set()
    return {json.loads(l)["fbgn"] for l in PROCESSED_FILE.open() if l.strip()}


def discover_pending() -> list:
    """Genes with canonical JSON but not yet processed."""
    done = already_processed()
    return sorted(f.stem for f in GENES_DIR.glob("FBgn*.json") if f.stem not in done)


def trigger_redistill(fbgn: str) -> dict:
    """Spawn two-pass re-distillation as a subprocess.
    Returns {ok, elapsed_s, error_or_summary}."""
    t0 = time.time()
    proc = subprocess.run(
        [sys.executable, str(ROOT / "src" / "distill_two_pass.py"), fbgn, "--force"],
        capture_output=True, text=True, timeout=900,
    )
    dt = time.time() - t0
    if proc.returncode != 0:
        return {"ok": False, "elapsed_s": round(dt, 1), "error": proc.stderr[:500]}

    # re-canonicalize
    rc = subprocess.run(
        [sys.executable, "-c",
         f"import sys; sys.path.insert(0, '{ROOT / 'src'}'); "
         f"from canonicalize import write_one; write_one('{fbgn}')"],
        capture_output=True, text=True, timeout=60,
    )
    return {"ok": rc.returncode == 0, "elapsed_s": round(dt, 1),
            "stdout_tail": proc.stdout[-300:], "canon_ok": rc.returncode == 0}


def handle_one(fbgn: str, max_attempts: int = 2) -> dict:
    """Process one gene end-to-end. Returns a structured log record."""
    record = {"fbgn": fbgn, "ts_start": now()}

    # Tier 1
    try:
        t1 = tier1_check(fbgn)
    except Exception as e:
        record["error"] = f"tier1: {e}"
        return record
    record["tier1_score"] = t1["qa_score"]
    record["tier1_issue_codes"] = sorted({i["code"] for i in t1["issues"]})

    if t1["qa_score"] >= TIER2_THRESHOLD:
        record["action"] = "accept_via_tier1"
        record["verdict"] = "accept"
        return record

    # Tier 2 audit
    record["action"] = "tier2_audit"
    record["attempts"] = []
    for attempt in range(1, max_attempts + 1):
        try:
            t2 = tier2_audit(fbgn, model="glm-5.1")
        except Exception as e:
            record["attempts"].append({"attempt": attempt, "error": f"tier2: {e}"})
            break
        a = t2.get("audit", {})
        record["attempts"].append({
            "attempt": attempt,
            "tier2_verdict": a.get("verdict"),
            "tier2_scores": {k: a.get(k) for k in ("completeness_score", "accuracy_score", "citation_score")},
            "tier2_n_halluc": len(a.get("hallucinations", [])),
            "tier2_n_missed": len(a.get("missed_phenotypes", [])),
            "elapsed_s": t2.get("elapsed_s"),
        })
        record["verdict"] = a.get("verdict")
        if a.get("verdict") in ("accept", "minor_fixes"):
            break
        # verdict = "redistill" → try fixing
        if t1["qa_score"] < REDISTILL_THRESHOLD or a.get("verdict") == "redistill":
            redo = trigger_redistill(fbgn)
            record["attempts"][-1]["redistill"] = redo
            if not redo.get("ok"):
                break
            # re-evaluate
            try:
                t1 = tier1_check(fbgn)
                record["tier1_score_after_redistill"] = t1["qa_score"]
            except Exception as e:
                record["attempts"][-1]["post_redistill_error"] = str(e)
                break

    record["ts_end"] = now()
    return record


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true", help="single pass, then exit")
    ap.add_argument("--max-fixes", type=int, default=5,
                    help="cap re-distill attempts per cycle (cost guard)")
    ap.add_argument("--poll-interval-s", type=int, default=60)
    ap.add_argument("--max-idle-minutes", type=int, default=30)
    args = ap.parse_args()

    QA_DIR.mkdir(parents=True, exist_ok=True)
    print(f"[monitor] starting at {now()}", flush=True)
    print(f"[monitor] poll every {args.poll_interval_s}s, "
          f"exit after {args.max_idle_minutes}min idle", flush=True)

    cycles = 0
    last_activity = time.time()
    fixes_this_cycle = 0
    while True:
        cycles += 1
        pending = discover_pending()
        if pending:
            last_activity = time.time()
            print(f"[monitor] cycle {cycles}: {len(pending)} pending → handling", flush=True)
            for fbgn in pending:
                # cost guard
                if fixes_this_cycle >= args.max_fixes:
                    print(f"[monitor]   reached --max-fixes={args.max_fixes}, "
                          f"pausing re-distills until next cycle", flush=True)
                rec = handle_one(fbgn)
                if rec.get("action") == "tier2_audit":
                    fixes_this_cycle += 1
                append_log(rec)
                append_log({"fbgn": fbgn, "ts": now()}, PROCESSED_FILE)
                print(f"[monitor]   {fbgn} → t1={rec.get('tier1_score','?')} "
                      f"verdict={rec.get('verdict','?')} action={rec.get('action','?')}", flush=True)
        else:
            idle_min = (time.time() - last_activity) / 60
            print(f"[monitor] cycle {cycles}: nothing pending (idle {idle_min:.0f}m)", flush=True)
            if idle_min >= args.max_idle_minutes:
                print(f"[monitor] idle exceeded {args.max_idle_minutes}min, exiting cleanly", flush=True)
                break

        if args.once:
            break
        fixes_this_cycle = 0  # reset per cycle
        time.sleep(args.poll_interval_s)

    print(f"[monitor] done. processed log: {PROCESSED_FILE}", flush=True)
    print(f"[monitor] full activity:    {MONITOR_LOG}", flush=True)


if __name__ == "__main__":
    main()
