"""Fire N parallel /v1/messages calls to z.ai to find the true concurrency limit.

For each test level, all requests start within ~50ms of each other. We record per-request
HTTP status, latency, and any error code. The point isn't speed — it's to surface the
ceiling at which calls start being rejected or queued.

Tiny prompts (max_tokens=5) keep this almost free against quota.
"""
import json
import os
import statistics
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_env():
    out = {}
    p = ROOT / ".env"
    if p.exists():
        for line in p.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                out[k.strip()] = v.strip()
    return out


ENV = load_env()
API_KEY = ENV["ZAI_API_KEY"]
BASE = ENV.get("ZAI_BASE_URL", "https://api.z.ai/api/anthropic")
MODEL = ENV.get("ZAI_MODEL", "glm-5.1")


def fire_one(req_id: int, barrier: threading.Barrier) -> dict:
    """Build a curl-equivalent POST. Wait at the barrier so all threads start ~simultaneously."""
    body = json.dumps({
        "model": MODEL,
        "max_tokens": 5,
        "messages": [{"role": "user", "content": f"reply pong {req_id}"}],
    })
    barrier.wait()
    t0 = time.time()
    proc = subprocess.run(
        [
            "/usr/bin/curl", "-sS", "-o", f"/tmp/conc_resp_{req_id}.json",
            "-w", "%{http_code}",
            "--max-time", "120",
            "-H", f"x-api-key: {API_KEY}",
            "-H", "anthropic-version: 2023-06-01",
            "-H", "Content-Type: application/json",
            "-X", "POST",
            f"{BASE}/v1/messages",
            "-d", body,
        ],
        capture_output=True,
        text=True,
    )
    dt = time.time() - t0
    http_code = proc.stdout.strip()
    body_text = Path(f"/tmp/conc_resp_{req_id}.json").read_text() if Path(f"/tmp/conc_resp_{req_id}.json").exists() else ""
    err = None
    if http_code != "200":
        try:
            err = json.loads(body_text)
        except Exception:
            err = body_text[:200]
    return {
        "req_id": req_id,
        "http_code": http_code,
        "latency_s": round(dt, 3),
        "ok": http_code == "200",
        "error": err if not (http_code == "200") else None,
    }


def run_level(n: int) -> dict:
    print(f"\n=== concurrency level: {n} ===", flush=True)
    barrier = threading.Barrier(n)
    with ThreadPoolExecutor(max_workers=n) as pool:
        futures = [pool.submit(fire_one, i, barrier) for i in range(n)]
        results = [f.result() for f in futures]
    ok = [r for r in results if r["ok"]]
    bad = [r for r in results if not r["ok"]]
    summary = {
        "level": n,
        "n_ok": len(ok),
        "n_fail": len(bad),
        "latencies_ok_s": [r["latency_s"] for r in ok],
        "median_ok_s": round(statistics.median([r["latency_s"] for r in ok]), 2) if ok else None,
        "max_ok_s": max((r["latency_s"] for r in ok), default=None),
        "min_ok_s": min((r["latency_s"] for r in ok), default=None),
        "fail_codes": sorted({r["http_code"] for r in bad}),
        "fail_samples": bad[:3],
    }
    print(f"  ok: {summary['n_ok']}/{n}  fail: {summary['n_fail']}  "
          f"latency p50/min/max: {summary['median_ok_s']} / {summary['min_ok_s']} / {summary['max_ok_s']}s",
          flush=True)
    if bad:
        print(f"  fail HTTP codes: {summary['fail_codes']}", flush=True)
        for s in summary["fail_samples"]:
            print(f"    sample: {s['http_code']} → {str(s.get('error'))[:200]}", flush=True)
    return summary


def main():
    levels = [int(x) for x in sys.argv[1:]] or [2, 5, 10, 15, 20]
    all_summaries = []
    for n in levels:
        s = run_level(n)
        all_summaries.append(s)
        time.sleep(3)  # tiny cooldown between batches
    out = ROOT / "output" / "concurrency_probe.json"
    out.write_text(json.dumps(all_summaries, indent=2))
    print(f"\nwrote {out}")

    # console table
    print(f"\n{'level':>5} {'ok':>4} {'fail':>4} {'p50_s':>7} {'max_s':>7} {'fail_codes':>12}")
    for s in all_summaries:
        print(f"{s['level']:>5} {s['n_ok']:>4} {s['n_fail']:>4} "
              f"{(s['median_ok_s'] or '-'):>7} {(s['max_ok_s'] or '-'):>7}  {','.join(s['fail_codes']) or '-':>12}")


if __name__ == "__main__":
    main()
