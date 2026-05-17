from __future__ import annotations
"""Query layer for embedding-based semantic + region search.

Loads embeddings.npz once into memory and exposes:
  - semantic_search(query, top_k, fbgn_filter=None) → ranked list of (fbgn, score)
  - genes_in_region(chr, start, end) → list of fbgns
  - hybrid(region, query, top_k) → region filter ∘ semantic rank
"""
import json
import os
import re
import sqlite3
from functools import lru_cache
from pathlib import Path
from urllib import request as urlrequest

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
EMBED_PATH = ROOT / "tools" / "embeddings.npz"
DB_PATH = ROOT / "tools" / "atlas.db"

MODEL = "gemini-embedding-2"


def _load_key() -> str:
    p = ROOT / ".env"
    if p.exists():
        for line in p.read_text().splitlines():
            if line.startswith("GEMINI_EMBEDDING_API_KEY="):
                return line.split("=", 1)[1].strip()
    raise SystemExit("GEMINI_EMBEDDING_API_KEY missing in .env")


@lru_cache(maxsize=1)
def _embeddings():
    if not EMBED_PATH.exists():
        raise SystemExit(f"Embeddings missing: {EMBED_PATH} — run `python -m flyatlas.embed_build` first")
    d = np.load(EMBED_PATH)
    fbgns = list(d["fbgns"])
    vecs = d["vecs"].astype(np.float32)
    # Already L2-normalized by Gemini, but normalize defensively
    norms = np.linalg.norm(vecs, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    vecs = vecs / norms
    fbgn_to_idx = {f: i for i, f in enumerate(fbgns)}
    return fbgns, vecs, fbgn_to_idx


def embed_query(text: str) -> np.ndarray:
    api_key = _load_key()
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:embedContent?key={api_key}"
    body = json.dumps({"content": {"parts": [{"text": text}]}}).encode()
    req = urlrequest.Request(url, data=body, method="POST",
                             headers={"Content-Type": "application/json"})
    with urlrequest.urlopen(req, timeout=30) as r:
        resp = json.loads(r.read())
    v = np.array(resp["embedding"]["values"], dtype=np.float32)
    n = np.linalg.norm(v)
    return v / n if n else v


def semantic_search(query: str, top_k: int = 20,
                    fbgn_filter: list | None = None) -> list[dict]:
    fbgns, vecs, idxs = _embeddings()
    q = embed_query(query)
    # numpy float32 SIMD matmul emits a phantom "divide by zero" RuntimeWarning
    # on macOS even when inputs are finite; suppress so CLI --json output stays
    # parseable. Result is identical.
    with np.errstate(all="ignore"):
        if fbgn_filter is not None:
            mask_idx = [idxs[f] for f in fbgn_filter if f in idxs]
            if not mask_idx:
                return []
            sub = vecs[mask_idx]
            scores = sub @ q
            order = np.argsort(-scores)[:top_k]
            return [{"fbgn": fbgns[mask_idx[i]], "score": float(scores[i])} for i in order]
        scores = vecs @ q
        order = np.argsort(-scores)[:top_k]
        return [{"fbgn": fbgns[i], "score": float(scores[i])} for i in order]


_CHR_RE = re.compile(r"Gene sequence location is\s+([0-9A-Za-z]+):(\d+)\.\.(\d+)")


def parse_region_from_bundle(bundle_text: str):
    m = _CHR_RE.search(bundle_text)
    if not m:
        return None
    return m.group(1), int(m.group(2)), int(m.group(3))


def ensure_region_columns(db_path: str = str(DB_PATH)):
    """Add chr/start/end columns to genes table if missing, then populate from
    cached bundles. Idempotent: safe to re-run after rebuild."""
    c = sqlite3.connect(db_path)
    cols = [r[1] for r in c.execute("PRAGMA table_info(genes)")]
    if "chr" not in cols:
        c.execute("ALTER TABLE genes ADD COLUMN chr TEXT")
        c.execute("ALTER TABLE genes ADD COLUMN start INTEGER")
        c.execute("ALTER TABLE genes ADD COLUMN end INTEGER")
        c.execute("CREATE INDEX IF NOT EXISTS idx_genes_chr ON genes(chr, start, end)")
    # Populate any missing
    rows = c.execute("SELECT fbgn FROM genes WHERE chr IS NULL").fetchall()
    n = 0
    for (fbgn,) in rows:
        bp = ROOT / "data" / "cache" / fbgn / "bundle.json"
        if not bp.exists():
            continue
        try:
            b = json.loads(bp.read_text())
        except Exception:
            continue
        loc = parse_region_from_bundle(b.get("auto_summary", "") or "")
        if loc:
            c.execute("UPDATE genes SET chr=?, start=?, end=? WHERE fbgn=?",
                      (loc[0], loc[1], loc[2], fbgn))
            n += 1
    c.commit()
    c.close()
    return n


@lru_cache(maxsize=1)
def _ensure_region_columns_once(db_path: str = str(DB_PATH)) -> int:
    """Self-heal: add+populate chr/start/end on first call per process. The flat
    flyatlas.build schema doesn't include these columns yet, so the first
    semantic/region query against a fresh atlas.db would otherwise 500."""
    return ensure_region_columns(db_path)


def genes_in_region(chr_: str, start: int, end: int, db_path: str = str(DB_PATH)) -> list[dict]:
    _ensure_region_columns_once(db_path)
    c = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    sql = """
      SELECT fbgn, symbol, chr, start, end, summary, n_bullets
      FROM genes WHERE chr = ? AND end >= ? AND start <= ?
      ORDER BY start
    """
    return [dict(r) for r in c.execute(sql, (chr_, start, end))]


def parse_region_string(s: str):
    """Accept '2L:5,000,000-6,000,000' or '2L:5e6-6e6' or '2L:5000000-6000000'."""
    s = s.replace(",", "").replace("_", "").strip()
    m = re.match(r"([0-9A-Za-z]+)\s*:\s*([\d.eE+]+)\s*-\s*([\d.eE+]+)$", s)
    if not m:
        return None
    return m.group(1), int(float(m.group(2))), int(float(m.group(3)))


def hybrid_query(region: str | None, query: str, top_k: int = 10) -> dict:
    """region: '2L:5e6-6e6' or None. query: free-text phenotype.
    Returns: {fbgn_in_region, fbgn_ranked} with full per-gene info."""
    _ensure_region_columns_once()
    out = {"region": region, "query": query}
    fbgn_filter = None
    if region:
        loc = parse_region_string(region)
        if not loc:
            return {"error": f"bad region: {region}"}
        chr_, start, end = loc
        in_region = genes_in_region(chr_, start, end)
        out["region_gene_count"] = len(in_region)
        out["region_genes"] = in_region
        fbgn_filter = [g["fbgn"] for g in in_region]
        if not fbgn_filter:
            return {**out, "ranked": []}
    if query:
        ranked = semantic_search(query, top_k=top_k, fbgn_filter=fbgn_filter)
        # Enrich with gene metadata
        c = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
        c.row_factory = sqlite3.Row
        enriched = []
        for r in ranked:
            g = c.execute("SELECT fbgn, symbol, summary, n_bullets, chr, start, end FROM genes WHERE fbgn=?",
                          (r["fbgn"],)).fetchone()
            if g:
                d = dict(g); d["score"] = r["score"]
                enriched.append(d)
        out["ranked"] = enriched
    return out
