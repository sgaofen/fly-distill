"""Resumable producer-consumer pipeline.

Architecture:

  gene queue (FBgn list, minus already-done) →
    [Fetcher pool (FETCH_WORKERS, ~12)]      I/O bound — bulk TSV parse + abstract fetch
       │   bundles queue (cap 30)
       ▼
    [GLM pool (GLM_WORKERS, ≤10)]            LLM bound — hits 10-concurrent ceiling
       │   bullets queue (cap 30)
       ▼
    [Writer thread (1)]                      atomic write canonical JSON + append run log

Key properties:
  - Idempotent: skip any FBgn whose output already exists.
  - Append-only run log (glm_calls.jsonl) — every attempt recorded with cost / status.
  - Atomic writes: .tmp + rename. No partial files survive a crash.
  - Failure queue (failures.jsonl) for retries (separate retry script picks up attempts < 3).
  - Two API keys round-robin (you have 2). Each gets ~10 concurrent. Effectively 20 if separate plans.

Run:
  python3 src/pipeline.py path/to/gene_list.txt           # plain list, one FBgn per line
  python3 src/pipeline.py --resume                        # resume previous batch
  python3 src/pipeline.py --dry-run                       # show plan without running
"""
import argparse
import hashlib
import json
import os
import queue
import signal
import sys
import threading
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

# Tunables ---------------------------------------------------------
FETCH_WORKERS = 12          # I/O-bound, can comfortably outrun GLM
GLM_WORKERS   = 10          # GLM Coding Plan: 10-concurrent ceiling (single plan)
QUEUE_CAP     = 30          # bundles waiting for GLM; caps memory at ~1.5 MB
RETRY_ATTEMPTS = 3
# ------------------------------------------------------------------

STOP = threading.Event()


def shard_for(fbgn: str) -> str:
    return hashlib.md5(fbgn.encode()).hexdigest()[:2]


def out_path(fbgn: str) -> Path:
    return ROOT / "output" / "genes" / shard_for(fbgn) / f"{fbgn}.json"


def bundle_path(fbgn: str) -> Path:
    return ROOT / "data" / "cache" / shard_for(fbgn) / fbgn / "bundle.json"


def atomic_write(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(content)
    tmp.rename(path)


_log_lock = threading.Lock()


def append_jsonl(path: Path, record: dict):
    """Append-only log file with a lock to serialize writes from many threads."""
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, ensure_ascii=False)
    with _log_lock:
        with path.open("a") as f:
            f.write(line + "\n")


# ---- Stages -----------------------------------------------------

def fetch_one(fbgn: str) -> dict:
    """Build the per-gene bundle. Currently delegates to fetch_gene.build_bundle which uses
    APIs; in the bulk-TSV refactor this becomes a local parse + abstract sub-fetch."""
    from fetch_gene import build_bundle
    cache = ROOT / "data" / "cache" / shard_for(fbgn) / fbgn
    return build_bundle(fbgn, cache)


def distill_one(fbgn: str, bundle: dict, harness: str = "claude") -> tuple[dict, dict]:
    """Returns (raw_response_obj, meta)."""
    if harness == "direct":
        from distill import call_glm, build_input_message, extract_text, strip_fences
        system = (ROOT / "prompts" / "distill_system.md").read_text()
        user = build_input_message(bundle)
        t0 = time.time()
        resp = call_glm(system, user)
        dt = time.time() - t0
        text = extract_text(resp)
        try:
            parsed = json.loads(strip_fences(text))
        except Exception:
            parsed = None
        return parsed, {"elapsed_s": dt, "usage": resp.get("usage", {}), "harness": "direct"}
    else:
        from distill_via_claude import (call_claude_headless, build_user_prompt,
                                          strip_fences, next_key)
        prompt = build_user_prompt(bundle)
        api_key = next_key()
        t0 = time.time()
        wrapper = call_claude_headless(prompt, api_key)
        dt = time.time() - t0
        text = wrapper.get("result", "")
        try:
            parsed = json.loads(strip_fences(text))
        except Exception:
            parsed = None
        return parsed, {"elapsed_s": dt, "usage": wrapper.get("usage", {}),
                        "harness": "claude_code_headless",
                        "wrapper_cost_usd": wrapper.get("total_cost_usd")}


def canonicalize_record(fbgn: str, raw: dict, bundle: dict, meta: dict) -> dict:
    """Convert raw GLM bullets into canonical schema (lifted from canonicalize.py)."""
    from canonicalize import canonicalize_one
    # canonicalize_one re-reads files from disk; for parallel pipeline we already
    # have them in memory. Re-use the function by writing bullets.json first.
    out_dir = ROOT / "output" / fbgn       # legacy location; canonicalize reads here
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "bullets.json").write_text(json.dumps(raw, indent=2))
    (out_dir / "request_meta.json").write_text(json.dumps({
        "model": "glm-5.1", "usage": meta.get("usage", {}),
        "elapsed_s": meta.get("elapsed_s"),
    }, indent=2))
    return canonicalize_one(fbgn)


def has_schema_drift(canonical: dict) -> bool:
    for w in (canonical.get("_lint") or []):
        # support both legacy string lint and structured dict lint
        if isinstance(w, dict):
            if (w.get("code") or "").startswith("schema_drift."):
                return True
        elif isinstance(w, str) and w.startswith("schema_drift:"):
            return True
    return False


def distill_with_retry(fbgn: str, bundle: dict, harness: str, run_log: Path, max_attempts: int = 2):
    """Try distill; if canonical has schema_drift, retry once with stricter prompt."""
    for attempt in range(1, max_attempts + 1):
        prompt_path = (ROOT / "prompts" /
                       ("distill_system_strict.md" if attempt > 1 else "distill_system.md"))
        # The distill_one functions read the prompt file by name — we swap it via env
        os.environ["DISTILL_PROMPT_FILE"] = prompt_path.name
        raw, meta = distill_one(fbgn, bundle, harness)
        if not raw or "bullets" not in raw:
            append_jsonl(run_log / "failures.jsonl", {
                "ts": now(), "fbgn": fbgn, "stage": "distill",
                "attempt": attempt, "error": "no valid JSON",
            })
            continue
        canonical = canonicalize_record(fbgn, raw, bundle, meta)
        if not has_schema_drift(canonical):
            return canonical, raw, meta, attempt
        append_jsonl(run_log / "failures.jsonl", {
            "ts": now(), "fbgn": fbgn, "stage": "schema_drift",
            "attempt": attempt, "lint": canonical.get("_lint"),
            "retrying": attempt < max_attempts,
        })
    # final canonical (with drift) — still write it but flagged
    return canonical, raw, meta, max_attempts


# ---- Pipeline orchestration ------------------------------------

def fetcher_worker(in_q: queue.Queue, out_q: queue.Queue, run_log: Path):
    while not STOP.is_set():
        try:
            fbgn = in_q.get(timeout=1)
        except queue.Empty:
            return
        try:
            bundle = fetch_one(fbgn)
            out_q.put((fbgn, bundle))
        except Exception as e:
            append_jsonl(run_log / "failures.jsonl", {
                "ts": now(), "fbgn": fbgn, "stage": "fetch",
                "error": str(e)[:300], "traceback": traceback.format_exc()[:1000],
            })
        finally:
            in_q.task_done()


def glm_worker(in_q: queue.Queue, write_q: queue.Queue, run_log: Path, harness: str):
    from rate_limiter import budget, is_rate_limit_response, is_quota_exhausted_response
    bd = budget()
    # Weight per call: direct=1, claude-harness=3 (1 main + estimated 0-2 sub-agents)
    call_weight = bd.harness_weight if harness == "claude" else 1
    while not STOP.is_set():
        try:
            fbgn, bundle = in_q.get(timeout=1)
        except queue.Empty:
            if in_q.empty() and not any_fetcher_alive():
                return
            continue
        try:
            # Acquire concurrency budget before the actual LLM call; release after.
            # This is what prevents sub-agent fan-out from blowing past z.ai's hard 10-cap.
            with bd.acquire(weight=call_weight, label=fbgn):
                canonical, raw, meta, attempts = distill_with_retry(
                    fbgn, bundle, harness, run_log, max_attempts=2
                )
                # detect rate-limit / quota-exhaustion signals
                err = meta.get("error_body", "") if meta else ""
                http = meta.get("http_code", "") if meta else ""
                if is_quota_exhausted_response(http, err):
                    print(f"  ! quota-exhausted signal for {fbgn}; suspending workers", flush=True)
                    bd.report_quota_exhausted()
                elif is_rate_limit_response(http, err):
                    bd.report_429()
                else:
                    bd.report_success()
            ok = canonical is not None and canonical.get("bullets")
            append_jsonl(run_log / "glm_calls.jsonl", {
                "ts": now(), "fbgn": fbgn,
                "attempts": attempts,
                "input_tokens": meta.get("usage", {}).get("input_tokens"),
                "output_tokens": meta.get("usage", {}).get("output_tokens"),
                "elapsed_s": round(meta.get("elapsed_s", 0), 2),
                "harness": meta.get("harness"),
                "weight": call_weight,
                "budget_state": bd.state,
                "drift_after_retry": has_schema_drift(canonical) if canonical else None,
                "ok": ok,
            })
            if not ok:
                append_jsonl(run_log / "failures.jsonl", {
                    "ts": now(), "fbgn": fbgn, "stage": "distill",
                    "error": "no valid JSON parsed from GLM response after retry",
                })
                continue
            write_q.put((fbgn, raw, bundle, meta, canonical))
        except Exception as e:
            append_jsonl(run_log / "failures.jsonl", {
                "ts": now(), "fbgn": fbgn, "stage": "distill",
                "error": str(e)[:300], "traceback": traceback.format_exc()[:1000],
            })
        finally:
            in_q.task_done()


def writer_worker(in_q: queue.Queue, run_log: Path):
    while not STOP.is_set():
        try:
            fbgn, raw, bundle, meta, canonical = in_q.get(timeout=1)
        except queue.Empty:
            if in_q.empty() and not any_glm_alive():
                return
            continue
        try:
            atomic_write(out_path(fbgn), json.dumps(canonical, indent=2, ensure_ascii=False))
            append_jsonl(run_log / "completed.jsonl", {
                "ts": now(), "fbgn": fbgn, "n_bullets": len(canonical.get("bullets", [])),
                "lint": canonical.get("_lint", []),
            })
        except Exception as e:
            append_jsonl(run_log / "failures.jsonl", {
                "ts": now(), "fbgn": fbgn, "stage": "write",
                "error": str(e)[:300], "traceback": traceback.format_exc()[:1000],
            })
        finally:
            in_q.task_done()


_fetcher_threads = []
_glm_threads = []
def any_fetcher_alive(): return any(t.is_alive() for t in _fetcher_threads)
def any_glm_alive(): return any(t.is_alive() for t in _glm_threads)
def now(): return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def signal_handler(signum, frame):
    print(f"\nstop signal {signum} — finishing in-flight work, no new tasks", flush=True)
    STOP.set()


def run(gene_list: list, harness: str, batch_id: str):
    run_log = ROOT / "runs" / batch_id
    run_log.mkdir(parents=True, exist_ok=True)
    # Save manifest
    (run_log / "manifest.json").write_text(json.dumps({
        "batch_id": batch_id, "started_at": now(), "harness": harness,
        "fetch_workers": FETCH_WORKERS, "glm_workers": GLM_WORKERS,
        "n_genes_input": len(gene_list),
    }, indent=2))

    # Resume: skip already-done FBgns
    todo = [g for g in gene_list if not out_path(g).exists()]
    skipped = len(gene_list) - len(todo)
    print(f"batch {batch_id}: {len(gene_list)} input, {skipped} already done, {len(todo)} to do")
    print(f"  harness={harness}, fetch_workers={FETCH_WORKERS}, glm_workers={GLM_WORKERS}")

    if not todo:
        print("nothing to do")
        return

    in_q = queue.Queue()
    bundle_q = queue.Queue(maxsize=QUEUE_CAP)
    write_q = queue.Queue(maxsize=QUEUE_CAP)
    for g in todo:
        in_q.put(g)

    # spawn pools
    for _ in range(FETCH_WORKERS):
        t = threading.Thread(target=fetcher_worker, args=(in_q, bundle_q, run_log), daemon=True)
        t.start()
        _fetcher_threads.append(t)
    for _ in range(GLM_WORKERS):
        t = threading.Thread(target=glm_worker, args=(bundle_q, write_q, run_log, harness), daemon=True)
        t.start()
        _glm_threads.append(t)
    writer = threading.Thread(target=writer_worker, args=(write_q, run_log), daemon=True)
    writer.start()

    # progress tracker
    t0 = time.time()
    done_last = 0
    while not STOP.is_set():
        time.sleep(15)
        done = sum(1 for _ in (run_log / "completed.jsonl").open()) if (run_log / "completed.jsonl").exists() else 0
        failed = sum(1 for _ in (run_log / "failures.jsonl").open()) if (run_log / "failures.jsonl").exists() else 0
        rate = (done - done_last) / 15
        eta = (len(todo) - done) / rate if rate > 0 else float("inf")
        print(f"  [{int(time.time() - t0):5}s] done={done:5}/{len(todo)} fail={failed:3} "
              f"rate={rate:.2f}/s ETA={eta/60:.0f}min "
              f"in_q={in_q.qsize()} bundle_q={bundle_q.qsize()} write_q={write_q.qsize()}",
              flush=True)
        done_last = done
        if done + failed >= len(todo):
            break
        if not any_fetcher_alive() and not any_glm_alive():
            break

    in_q.join()
    bundle_q.join()
    write_q.join()
    print(f"\nbatch complete in {time.time() - t0:.0f}s")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("gene_list_file", nargs="?",
                    help="path to file with one FBgn per line")
    ap.add_argument("--harness", choices=["direct", "claude"], default="claude",
                    help="direct API or Claude Code headless")
    ap.add_argument("--batch-id", default=None)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if args.gene_list_file:
        genes = [l.strip() for l in open(args.gene_list_file)
                 if l.strip() and l.strip().startswith("FBgn")]
    else:
        from gene_list import GENES
        genes = [g["fbgn"] for g in GENES]

    if args.dry_run:
        todo = [g for g in genes if not out_path(g).exists()]
        print(f"would run on {len(todo)}/{len(genes)} genes (rest already done)")
        for g in todo[:10]:
            print(f"  {g}")
        if len(todo) > 10: print(f"  ... and {len(todo) - 10} more")
        return

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    batch_id = args.batch_id or f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{args.harness}"
    run(genes, args.harness, batch_id)


if __name__ == "__main__":
    main()
