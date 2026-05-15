from __future__ import annotations
"""Build dense embedding vectors for every gene in the atlas, using Gemini
`gemini-embedding-2` (3072-dim).

  python -m flyatlas.embed_build [--out path/to/embeddings.npz]

Output: a single .npz with two arrays
  - fbgns: (N,) array of FBgn strings (canonical order)
  - vecs : (N, 3072) float32 array
N = 14019 typically. File ≈ 175 MB on disk; loads to RAM in ~1s.

Concurrency: 16 workers (Gemini paid tier handles this easily). Rate-limit
back-off on 429 / 5xx.
"""
import argparse
import json
import os
import sys
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib import request as urlrequest, error as urlerror

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT = ROOT / "tools" / "embeddings.npz"
GENES_DIR = ROOT / "output" / "genes"

MODEL = "gemini-embedding-2"
ENDPOINT = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:embedContent"


def load_key() -> str:
    p = ROOT / ".env"
    if p.exists():
        for line in p.read_text().splitlines():
            if line.startswith("GEMINI_EMBEDDING_API_KEY="):
                return line.split("=", 1)[1].strip()
    raise SystemExit("GEMINI_EMBEDDING_API_KEY not found in .env")


def build_gene_text(c: dict) -> str:
    """Compose the text we embed: symbol + summary + concatenated bullet
    phenotypes + evidence + notes. Capped to ~7000 chars to stay well under
    Gemini's 8192-token input limit."""
    parts = [c.get("symbol", "")]
    parts.append(c.get("snapshot") or "")
    for b in (c.get("bullets") or []):
        ph = b.get("phenotype") or ""
        ev = (b.get("evidence_text") or "")[:200]
        cat = b.get("category") or ""
        parts.append(f"[{cat}] {ph}  // {ev}")
    notes = c.get("notes")
    if notes:
        parts.append(f"NOTES: {notes}")
    txt = "\n".join(p for p in parts if p).strip()
    return txt[:7000]


def embed_one(api_key: str, text: str, retries: int = 4) -> list:
    body = json.dumps({"content": {"parts": [{"text": text}]}}).encode()
    url = f"{ENDPOINT}?key={api_key}"
    backoff = 1.5
    for attempt in range(retries):
        try:
            req = urlrequest.Request(url, data=body, method="POST",
                                     headers={"Content-Type": "application/json"})
            with urlrequest.urlopen(req, timeout=60) as r:
                resp = json.loads(r.read())
            return resp["embedding"]["values"]
        except urlerror.HTTPError as e:
            code = e.code
            if code == 429 or 500 <= code < 600:
                time.sleep(backoff)
                backoff *= 2
                continue
            raise
        except Exception:
            time.sleep(backoff); backoff *= 2
            if attempt == retries - 1:
                raise
    raise RuntimeError("all retries failed")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--limit", type=int, default=0, help="0 = all")
    args = ap.parse_args()

    api_key = load_key()
    files = sorted(GENES_DIR.glob("*.json"))
    if args.limit:
        files = files[:args.limit]
    fbgns = [p.stem for p in files]
    N = len(files)
    print(f"Embedding {N} genes via Gemini {MODEL} ({args.workers} workers)...")

    vecs = [None] * N
    lock = threading.Lock()
    done = [0]
    failed = []
    t0 = time.time()

    def task(idx: int):
        try:
            c = json.loads(files[idx].read_text())
            text = build_gene_text(c)
            v = embed_one(api_key, text)
            vecs[idx] = v
        except Exception as e:
            with lock:
                failed.append((fbgns[idx], str(e)[:200]))
        with lock:
            done[0] += 1
            if done[0] % 200 == 0:
                el = time.time() - t0
                rate = done[0] / el
                eta_min = (N - done[0]) / rate / 60
                print(f"  {done[0]}/{N}  rate={rate:.1f}/s  ETA={eta_min:.1f}min  fail={len(failed)}", flush=True)

    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        list(as_completed(ex.submit(task, i) for i in range(N)))

    # Fill failed slots with zero vectors (we'll mark them in a sidecar)
    dim = next((len(v) for v in vecs if v is not None), 3072)
    arr = np.zeros((N, dim), dtype=np.float32)
    for i, v in enumerate(vecs):
        if v is not None:
            arr[i] = v

    out_p = Path(args.out)
    out_p.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(out_p, fbgns=np.array(fbgns), vecs=arr)
    print(f"\nDone in {(time.time()-t0)/60:.1f}min")
    print(f"  Saved: {out_p}")
    print(f"  Shape: {arr.shape}, dtype={arr.dtype}, size on disk: {out_p.stat().st_size//1024//1024} MB")
    print(f"  Failed: {len(failed)}")
    if failed:
        for fb, e in failed[:5]:
            print(f"    {fb}: {e}")


if __name__ == "__main__":
    main()
