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
    # Prefer process env, then .env (BOM/quotes/comments tolerant).
    v = os.environ.get("GEMINI_EMBEDDING_API_KEY")
    if v:
        return v.strip()
    p = ROOT / ".env"
    if p.exists():
        text = p.read_text(encoding="utf-8-sig")
        for raw in text.splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("export "):
                line = line[len("export "):].lstrip()
            if not line.startswith("GEMINI_EMBEDDING_API_KEY="):
                continue
            val = line.split("=", 1)[1].strip()
            if val and val[0] not in "'\"":
                val = val.split("#", 1)[0].rstrip()
            if len(val) >= 2 and val[0] == val[-1] and val[0] in "'\"":
                val = val[1:-1]
            if val:
                return val
    raise SystemExit("GEMINI_EMBEDDING_API_KEY missing in env or .env")


def build_gene_text(c: dict) -> str:
    """Compose the text we embed under one fly-gene vector. Mouse/human MGI/HPO
    text is auxiliary signal attached to the SAME fly vector — never its own
    entity. Capped to 14000 chars (Gemini limit is 8192 tokens ≈ 30k chars; we
    leave margin for the tokenizer).

    Budget strategy:
      1. Fly summary (always kept full)
      2. Cross-species ortholog context (always kept — this is the new signal
         we paid for and want guaranteed-present in every vector that has
         orthologs)
      3. Fly bullets (truncated last, in case 1+2+3 exceeds budget)
    """
    CAP = 14000
    sym = c.get("symbol", "")
    head_lines = [f"Drosophila gene: {sym}", c.get("snapshot") or ""]

    # Cross-species block — reserve guaranteed slot at top, so it always ends up in the embed
    cs = c.get("cross_species") or {}
    cs_lines: list[str] = []
    for o in (cs.get("mouse_orthologs") or []):
        terms = o.get("mgi_phenotypes") or []
        if not terms: continue
        cs_lines.append(f"Mouse ortholog {o.get('symbol','?')} (knockout/mutant phenotypes): "
                        + "; ".join(t["term"] for t in terms[:15]))
    for o in (cs.get("human_orthologs") or []):
        terms = o.get("hpo_phenotypes") or []
        if not terms: continue
        cs_lines.append(f"Human ortholog {o.get('symbol','?')} (clinical phenotypes): "
                        + "; ".join(t["term"] for t in terms[:15]))
    for d in (cs.get("human_disease_links") or []):
        hp = d.get("hpo_terms") or []
        if not hp: continue
        cs_lines.append(f"Disease via ortholog — {d.get('name','?')} (clinical features): "
                        + "; ".join(t["term"] for t in hp[:8]))
    cs_block = ("\n── Cross-species ortholog context (verbatim from MGI/HPO) ──\n"
                + "\n".join(cs_lines)) if cs_lines else ""

    # Reserve budget: head + cs_block consume first, fly bullets take the rest
    head_text = "\n".join(head_lines).strip()
    reserved = len(head_text) + len(cs_block)
    bullets_budget = max(CAP - reserved - 200, 1500)  # at least 1500 chars for bullets

    bullet_lines: list[str] = []
    for b in (c.get("bullets") or []):
        ph = b.get("phenotype") or ""
        ev = (b.get("evidence_text") or "")[:200]
        cat = b.get("category") or ""
        bullet_lines.append(f"[{cat}] {ph}  // {ev}")
    bullets_text = "\n".join(bullet_lines)[:bullets_budget]
    if c.get("notes"):
        bullets_text += f"\nNOTES: {c['notes'][:300]}"

    # Order matters: head first (always tiny), cross-species block second
    # (guaranteed-present signal we paid for), bullets last (truncation tail
    # falls on bullets, never on cross-species).
    full = head_text + "\n" + cs_block + "\n" + bullets_text
    return full[:CAP]


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
