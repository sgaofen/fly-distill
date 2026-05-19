"""After embed_build.py finishes, any zero-vector rows in tools/embeddings.npz
indicate rate-limited / network-failed embeds. This script identifies them
and retries just those, then writes the merged result back.

Run after embed_build.py completes:
  python src/retry_embed_failures.py
"""
from __future__ import annotations
import json
import os
import sys
import time
from pathlib import Path
from urllib import request as urlrequest, error as urlerror

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from flyatlas.embed_build import load_key, embed_one, build_gene_text  # noqa: E402

EMBED_PATH = ROOT / "tools" / "embeddings.npz"
GENES_DIR = ROOT / "output" / "genes"


def main():
    d = np.load(EMBED_PATH)
    fbgns = list(d["fbgns"])
    vecs = d["vecs"].copy()

    norms = np.linalg.norm(vecs, axis=1)
    zero_idxs = np.where(norms == 0)[0]
    print(f"Total rows: {len(fbgns)}; zero-vector rows: {len(zero_idxs)}")
    if len(zero_idxs) == 0:
        print("Nothing to retry.")
        return

    api_key = load_key()
    n_ok = 0
    n_fail = 0
    for j, i in enumerate(zero_idxs):
        fbgn = str(fbgns[i])
        p = GENES_DIR / f"{fbgn}.json"
        if not p.exists():
            print(f"  {fbgn}: no canonical, skip")
            n_fail += 1
            continue
        try:
            c = json.loads(p.read_text())
            text = build_gene_text(c)
            v = embed_one(api_key, text)
            vecs[i] = np.array(v, dtype=np.float32)
            n_ok += 1
            if (j + 1) % 20 == 0:
                print(f"  retried {j+1}/{len(zero_idxs)}  ok={n_ok}  fail={n_fail}", flush=True)
        except Exception as e:
            print(f"  {fbgn}: {e}")
            n_fail += 1
            time.sleep(2)

    # Save merged result
    np.savez_compressed(EMBED_PATH, fbgns=np.array(fbgns), vecs=vecs)
    print(f"\nFinal: {n_ok} retried + saved; {n_fail} still failed")
    print(f"Saved: {EMBED_PATH}")


if __name__ == "__main__":
    main()
