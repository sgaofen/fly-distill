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
import subprocess
import sys
import threading
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

# Tunables ---------------------------------------------------------
# As of v2 we no longer hit FlyBase API/HTML — everything is bulk-TSV in memory
# plus NCBI eutils (separate infrastructure, 10 req/s with email). PubMed fetcher
# self-throttles globally at ~3 req/s. MyGene (Scripps) tolerates burst well.
FETCH_WORKERS = int(os.environ.get("PIPELINE_FETCH_WORKERS", "6"))
GLM_WORKERS   = int(os.environ.get("PIPELINE_GLM_WORKERS", "10"))   # per-pipeline concurrency
QUEUE_CAP     = int(os.environ.get("PIPELINE_QUEUE_CAP", "30"))
RETRY_ATTEMPTS = 3
# ------------------------------------------------------------------

STOP = threading.Event()


def shard_for(fbgn: str) -> str:
    return hashlib.md5(fbgn.encode()).hexdigest()[:2]


def out_path(fbgn: str) -> Path:
    # Canonical JSON lives at the flat path (matches canonicalize.py); for sharded
    # 14k+ deployments, switch to: ROOT/"output"/"genes"/shard_for(fbgn)/f"{fbgn}.json"
    return ROOT / "output" / "genes" / f"{fbgn}.json"


def bundle_path(fbgn: str) -> Path:
    # Bundle currently flat too. Switch to sharded once 14k+ files justify it.
    return ROOT / "data" / "cache" / fbgn / "bundle.json"


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
    """Build the per-gene bundle via bulk-only fetcher (fetch_gene_v2).
    Source: in-memory BulkIndex (17 FlyBase TSVs + Alliance) + NCBI eutils
    abstracts + MyGene ortholog summaries. No FlyBase API/HTML calls."""
    from fetch_gene_v2 import build_bundle
    cache = ROOT / "data" / "cache" / fbgn
    return build_bundle(fbgn, cache)


def distill_one(fbgn: str, bundle: dict, harness: str = "claude") -> tuple[dict, dict]:
    """Returns (raw_response_obj, meta). On subprocess timeout, returns
    (None, {error_type: 'timeout', ...}) instead of raising — distill_with_retry
    inspects error_type and decides whether to shrink+retry."""
    if harness == "direct":
        from distill import call_glm, build_input_message, extract_text, strip_fences
        system = (ROOT / "prompts" / "distill_system.md").read_text()
        user = build_input_message(bundle)
        t0 = time.time()
        try:
            resp = call_glm(system, user)
        except Exception as e:
            return None, {"elapsed_s": time.time() - t0, "harness": "direct",
                          "error_type": "exception", "error": str(e)[:200]}
        dt = time.time() - t0
        text = extract_text(resp)
        try:
            parsed = json.loads(strip_fences(text))
        except Exception:
            parsed = None
        return parsed, {"elapsed_s": dt, "usage": resp.get("usage", {}), "harness": "direct"}
    else:
        # harness "claude" → GLM-5.1 via z.ai
        # harness "sonnet" → Claude Opus/Sonnet via Anthropic Max OAuth
        # harness "codex"  → OpenAI Codex CLI via ChatGPT sub
        # harness "glm5"   → GLM-5 via z.ai (different model, concurrency=2)
        # harness "mimo"   → Xiaomi MiMo-V2.5-Pro via Token Plan (no throttling)
        if harness == "sonnet":
            from distill_via_sonnet import (call_claude_headless, build_user_prompt,
                                              strip_fences, next_key)
        elif harness == "codex":
            from distill_via_codex import (call_claude_headless, build_user_prompt,
                                              strip_fences, next_key)
        elif harness == "glm5":
            from distill_via_glm5 import (call_claude_headless, build_user_prompt,
                                            strip_fences, next_key)
        elif harness == "mimo":
            from distill_via_mimo import (call_claude_headless, build_user_prompt,
                                            strip_fences, next_key)
        elif harness == "gemini":
            from distill_via_gemini import (call_claude_headless, build_user_prompt,
                                              strip_fences, next_key)
        else:
            from distill_via_claude import (call_claude_headless, build_user_prompt,
                                              strip_fences, next_key)
        prompt = build_user_prompt(bundle)
        api_key = next_key()
        t0 = time.time()
        try:
            wrapper = call_claude_headless(prompt, api_key)
        except subprocess.TimeoutExpired as e:
            return None, {"elapsed_s": time.time() - t0, "harness": "claude_code_headless",
                          "error_type": "timeout",
                          "timeout_s": getattr(e, "timeout", None),
                          "prompt_chars": len(prompt)}
        except Exception as e:
            es = str(e)
            return None, {"elapsed_s": time.time() - t0, "harness": "claude_code_headless",
                          "error_type": "exception", "error": es[:300],
                          "error_body": es[:2000], "http_code": ""}
        dt = time.time() - t0
        # claude --print wraps z.ai errors as: {is_error:true, api_error_status:NNN,
        # result:"API Error: ..."} with exit code 1. distill_via_claude now returns
        # this wrapper instead of raising — surface the signal to rate_limiter via
        # http_code + error_body so 429/quota trip the right backoff path.
        if wrapper.get("is_error"):
            http_code = str(wrapper.get("api_error_status", "") or "")
            result_text = wrapper.get("result", "") or ""
            error_text = wrapper.get("error_text", "") or ""
            # combine — codex puts quota-exhaust message in error_text, not result
            combined = (result_text + "\n" + error_text).strip()
            return None, {"elapsed_s": dt, "usage": wrapper.get("usage", {}),
                          "harness": "claude_code_headless",
                          "error_type": "api_error",
                          "error": combined[:300],
                          "error_body": combined,
                          "http_code": http_code,
                          "wrapper_cost_usd": wrapper.get("total_cost_usd")}
        text = wrapper.get("result", "")
        try:
            parsed = json.loads(strip_fences(text))
        except Exception:
            parsed = None
        return parsed, {"elapsed_s": dt, "usage": wrapper.get("usage", {}),
                        "harness": "claude_code_headless",
                        "wrapper_cost_usd": wrapper.get("total_cost_usd")}


_HARNESS_MODEL_MAP = {
    "claude":  ("z.ai",      "glm-5.1"),
    "direct":  ("z.ai",      "glm-5.1"),
    "glm5":    ("z.ai",      "glm-5"),
    "sonnet":  ("anthropic", os.environ.get("ANTHROPIC_DISTILL_MODEL") or "claude-sonnet-4-6"),
    "codex":   ("openai",    os.environ.get("CODEX_MODEL") or "gpt-5.5"),
    "mimo":    ("xiaomi",    os.environ.get("MIMO_MODEL") or "mimo-v2.5-pro"),
    "gemini":  ("google",    os.environ.get("GEMINI_MODEL") or "gemini-3-flash-preview"),
}


def canonicalize_record(fbgn: str, raw: dict, bundle: dict, meta: dict, harness: str = "claude") -> dict:
    """Convert raw bullets into canonical schema. `harness` is the pipeline-level
    backend selector (claude/sonnet/codex/glm5/direct); it drives the model_id +
    provider fields written into request_meta.json so canonicalize.py attributes
    each gene to the actual backend rather than defaulting to glm-5.1."""
    from canonicalize import canonicalize_one
    out_dir = ROOT / "output" / fbgn
    out_dir.mkdir(parents=True, exist_ok=True)
    provider, model_id = _HARNESS_MODEL_MAP.get(harness, ("z.ai", "glm-5.1"))
    (out_dir / "bullets.json").write_text(json.dumps(raw, indent=2))
    (out_dir / "request_meta.json").write_text(json.dumps({
        "provider": provider,
        "model": model_id,
        "pipeline_harness": harness,
        "thinking_tokens_env": os.environ.get("ANTHROPIC_MAX_THINKING_TOKENS"),
        "usage": meta.get("usage", {}),
        "elapsed_s": meta.get("elapsed_s"),
        "recovered_via_shrink_level": meta.get("recovered_via_shrink_level"),
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


def shrink_bundle(bundle: dict, level: int) -> dict:
    """Return a copy of `bundle` with reduced content for timeout retries.
    Aim: reduce prompt size so GLM can finish before subprocess timeout.

    level 1: halve abstracts (20→10) + halve phenotype/allele line counts
    level 2+: aggressive cap (5 abstracts, 30 phenotype/allele rows, drop low-priority sections)"""
    import copy as _copy
    out = _copy.deepcopy(bundle)
    if level <= 0:
        return out
    if level == 1:
        out["abstracts"] = out.get("abstracts", [])[:10]
        for sid in ("phenotypes_sub", "alleles_main_sub"):
            txt = (out.get("sections") or {}).get(sid, "") or ""
            lines = txt.split("\n")
            out["sections"][sid] = "\n".join(lines[:max(40, len(lines) // 2)])
    else:
        out["abstracts"] = out.get("abstracts", [])[:5]
        for sid in ("phenotypes_sub", "alleles_main_sub",
                    "summary_genetic_interactions_sub", "summary_physical_interactions_sub"):
            txt = (out.get("sections") or {}).get(sid, "") or ""
            lines = txt.split("\n")
            out["sections"][sid] = "\n".join(lines[:30])
    out["_shrink_level"] = level
    return out


def distill_with_retry(fbgn: str, bundle: dict, harness: str, run_log: Path, max_attempts: int = 3):
    """Try distill with three escalation paths:
       1. On schema_drift -> retry once with stricter prompt (same bundle).
       2. On subprocess timeout -> shrink bundle (refs+phenotypes), retry.
       3. On 'no JSON' -> retry with strict prompt + same bundle.

    Total up to max_attempts attempts; final attempt always uses shrunk bundle and
    strict prompt as a 'kitchen sink' last try. After all attempts, returns whatever
    we have (or None if every attempt threw an error)."""
    from rate_limiter import budget, is_rate_limit_response, is_quota_exhausted_response
    bd = budget()
    canonical = raw = meta = None
    cur_bundle = bundle
    shrink_level = 0
    for attempt in range(1, max_attempts + 1):
        # Pick prompt: strict on retries (drift or no-json), regular on first try
        prompt_path = (ROOT / "prompts" /
                       ("distill_system_strict.md" if attempt > 1 else "distill_system.md"))
        os.environ["DISTILL_PROMPT_FILE"] = prompt_path.name
        raw, meta = distill_one(fbgn, cur_bundle, harness)

        # Eagerly feed rate-limit signals to the global budget every attempt — otherwise
        # a successful 3rd attempt would mask 429s on attempts 1+2 and we'd never trip
        # the backoff. This is critical during peak hours.
        err_body = (meta or {}).get("error_body", "")
        http_code = (meta or {}).get("http_code", "")
        if is_quota_exhausted_response(http_code, err_body):
            bd.report_quota_exhausted()
            # Hard quota → don't burn the remaining 2 attempts. Mark deferred so
            # glm_worker can route to deferred.jsonl (not quarantine). The next
            # idempotent pipeline run picks the gene up after quota resets.
            if meta is not None:
                meta["error_type"] = "quota_deferred"
            return None, None, meta, attempt
        elif is_rate_limit_response(http_code, err_body):
            bd.report_429()

        err_type = (meta or {}).get("error_type")
        if err_type == "api_error":
            # Log structured api_error so we can see 429 rate over time
            append_jsonl(run_log / "failures.jsonl", {
                "ts": now(), "fbgn": fbgn, "stage": "api_error",
                "attempt": attempt, "http_code": http_code,
                "error": (meta or {}).get("error", ""),
                "retrying": attempt < max_attempts,
            })
            continue
        if err_type == "timeout":
            # subprocess hit timeout → shrink bundle for next try
            shrink_level += 1
            append_jsonl(run_log / "failures.jsonl", {
                "ts": now(), "fbgn": fbgn, "stage": "timeout",
                "attempt": attempt, "elapsed_s": meta.get("elapsed_s"),
                "prompt_chars": meta.get("prompt_chars"),
                "next_shrink_level": shrink_level,
                "retrying": attempt < max_attempts,
            })
            cur_bundle = shrink_bundle(bundle, shrink_level)
            continue
        if err_type == "exception":
            append_jsonl(run_log / "failures.jsonl", {
                "ts": now(), "fbgn": fbgn, "stage": "distill_exception",
                "attempt": attempt, "error": meta.get("error"),
                "retrying": attempt < max_attempts,
            })
            continue
        if not raw or "bullets" not in raw:
            append_jsonl(run_log / "failures.jsonl", {
                "ts": now(), "fbgn": fbgn, "stage": "distill",
                "attempt": attempt, "error": "no valid JSON",
                "retrying": attempt < max_attempts,
            })
            continue
        # Surface shrink-recovery BEFORE canonicalize so it lands in request_meta.json
        # and canonicalize.py can emit a quality.bundle_shrunk _lint warning
        if meta is not None and shrink_level > 0:
            meta["recovered_via_shrink_level"] = shrink_level
        canonical = canonicalize_record(fbgn, raw, cur_bundle, meta, harness=harness)
        if not has_schema_drift(canonical):
            return canonical, raw, meta, attempt
        append_jsonl(run_log / "failures.jsonl", {
            "ts": now(), "fbgn": fbgn, "stage": "schema_drift",
            "attempt": attempt, "lint": canonical.get("_lint"),
            "retrying": attempt < max_attempts,
        })
    # All attempts exhausted. Return whatever we have (may be None) — caller decides
    # whether to write a (possibly drifted) record or quarantine.
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
                    fbgn, bundle, harness, run_log, max_attempts=3
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
            # A canonical with empty bullets is a LEGITIMATE success for stub genes
            # (uncharacterized CG-prefix predicted genes with 0 phenotype data). The
            # model correctly returned `{"bullets": []}` — don't quarantine it.
            ok = canonical is not None and isinstance(canonical.get("bullets"), list)
            append_jsonl(run_log / "glm_calls.jsonl", {
                "ts": now(), "fbgn": fbgn,
                "attempts": attempts,
                "input_tokens": (meta.get("usage", {}) if meta else {}).get("input_tokens"),
                "output_tokens": (meta.get("usage", {}) if meta else {}).get("output_tokens"),
                "elapsed_s": round((meta or {}).get("elapsed_s", 0), 2),
                "harness": (meta or {}).get("harness"),
                "shrink_recovered": (meta or {}).get("recovered_via_shrink_level"),
                "weight": call_weight,
                "budget_state": bd.state,
                "drift_after_retry": has_schema_drift(canonical) if canonical else None,
                "ok": ok,
            })
            if not ok:
                err_type = (meta or {}).get("error_type")
                # Quota-deferred → don't quarantine. Gene stays unprocessed and the
                # next idempotent run picks it up after the quota resets.
                if err_type == "quota_deferred":
                    append_jsonl(run_log / "deferred.jsonl", {
                        "ts": now(), "fbgn": fbgn, "reason": "quota_exhausted",
                        "attempts": attempts,
                    })
                else:
                    append_jsonl(run_log / "quarantine.jsonl", {
                        "ts": now(), "fbgn": fbgn,
                        "reason": err_type or "no_valid_json",
                        "attempts": attempts,
                        "last_elapsed_s": (meta or {}).get("elapsed_s"),
                        "last_prompt_chars": (meta or {}).get("prompt_chars"),
                        "last_error": (meta or {}).get("error"),
                    })
                    append_jsonl(run_log / "failures.jsonl", {
                        "ts": now(), "fbgn": fbgn, "stage": "exhausted_retries",
                        "attempts": attempts,
                        "error_type": err_type,
                        "error": (meta or {}).get("error"),
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

    # Pre-warm the FlyBase bulk index BEFORE spawning fetcher threads — otherwise
    # all 6 threads race the lazy-init and spike RAM with duplicate ~500 MB instances.
    print("pre-warming bulk index...", flush=True)
    from bulk_index import get_bulk
    get_bulk()

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
    ap.add_argument("--harness", choices=["direct", "claude", "sonnet", "codex", "glm5", "mimo", "gemini"], default="claude",
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
