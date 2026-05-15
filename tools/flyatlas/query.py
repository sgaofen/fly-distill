from __future__ import annotations
"""Read-only query layer over atlas.db. Shared by CLI + server."""
import json
import re
import sqlite3
from pathlib import Path
from typing import Any


def _conn(db) -> sqlite3.Connection:
    c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    return c


def stats(db) -> dict:
    c = _conn(db)
    out = {}
    out["n_genes"] = c.execute("SELECT COUNT(*) FROM genes").fetchone()[0]
    out["n_bullets"] = c.execute("SELECT COUNT(*) FROM bullets").fetchone()[0]
    out["n_refs"] = c.execute("SELECT COUNT(DISTINCT fbrf) FROM refs").fetchone()[0]
    out["n_diseases"] = c.execute("SELECT COUNT(DISTINCT omim_id) FROM diseases WHERE omim_id IS NOT NULL").fetchone()[0]
    out["by_provider"] = dict(c.execute(
        "SELECT provider, COUNT(*) FROM genes GROUP BY provider ORDER BY 2 DESC"
    ).fetchall())
    out["by_category"] = dict(c.execute(
        "SELECT category, COUNT(*) FROM bullets WHERE category IS NOT NULL GROUP BY category ORDER BY 2 DESC"
    ).fetchall())
    out["by_confidence"] = dict(c.execute(
        "SELECT confidence, COUNT(*) FROM bullets GROUP BY confidence"
    ).fetchall())
    out["top_tissues"] = c.execute(
        "SELECT tissue, COUNT(DISTINCT fbgn) FROM tissues GROUP BY tissue ORDER BY 2 DESC LIMIT 15"
    ).fetchall()
    return out


def resolve_gene(db, query: str) -> str | None:
    """Resolve fbgn|symbol|annotation_id|secondary_fbgn → canonical fbgn."""
    c = _conn(db)
    q = query.strip()
    # Direct fbgn
    if q.upper().startswith("FBGN"):
        r = c.execute("SELECT fbgn FROM genes WHERE fbgn = ?", (q,)).fetchone()
        if r: return r["fbgn"]
    # Symbol exact
    r = c.execute("SELECT fbgn FROM genes WHERE symbol = ? COLLATE NOCASE", (q,)).fetchone()
    if r: return r["fbgn"]
    # Synonym
    r = c.execute(
        "SELECT fbgn FROM synonyms WHERE synonym = ? COLLATE NOCASE ORDER BY is_current DESC LIMIT 1",
        (q,),
    ).fetchone()
    if r: return r["fbgn"]
    return None


def get_gene(db, fbgn: str) -> dict | None:
    """Return full canonical (denormalized) for a single gene."""
    c = _conn(db)
    g = c.execute("SELECT * FROM genes WHERE fbgn = ?", (fbgn,)).fetchone()
    if not g: return None
    out: dict[str, Any] = dict(g)
    out["synonyms"] = [dict(r) for r in c.execute(
        "SELECT synonym, type, is_current FROM synonyms WHERE fbgn = ? ORDER BY is_current DESC", (fbgn,))]
    out["bullets"] = []
    for b in c.execute(
        "SELECT * FROM bullets WHERE fbgn = ? ORDER BY id", (fbgn,)):
        bd = dict(b)
        bd["citations"] = [dict(r) for r in c.execute(
            "SELECT * FROM citations WHERE bullet_pk = ?", (b["id"],))]
        out["bullets"].append(bd)
    out["references"] = [dict(r) for r in c.execute(
        "SELECT * FROM refs WHERE fbgn = ? ORDER BY year DESC NULLS LAST", (fbgn,))]
    out["orthologs"] = [dict(r) for r in c.execute(
        "SELECT * FROM orthologs WHERE fbgn = ?", (fbgn,))]
    out["diseases"] = [dict(r) for r in c.execute(
        "SELECT * FROM diseases WHERE fbgn = ?", (fbgn,))]
    out["tissues"] = [r[0] for r in c.execute(
        "SELECT DISTINCT tissue FROM tissues WHERE fbgn = ?", (fbgn,))]
    out["life_stages"] = [r[0] for r in c.execute(
        "SELECT DISTINCT stage FROM life_stages WHERE fbgn = ?", (fbgn,))]
    return out


def _fts_safe(q: str) -> str:
    """Escape FTS5 query — wrap each token to allow AND/OR/NOT semantics."""
    # If user uses MATCH operators (AND/OR/NEAR/quotes), pass through after light cleanup
    if re.search(r'\b(AND|OR|NEAR|NOT)\b', q):
        return q
    # Else split by spaces, quote each token (handles symbols with hyphens etc)
    tokens = [t for t in re.split(r"\s+", q.strip()) if t]
    return " ".join(f'"{t}"' for t in tokens)


def search(db, query: str, *,
           category: str | None = None,
           direction: str | None = None,
           confidence: str | None = None,
           tissue: str | None = None,
           limit: int = 50) -> list[dict]:
    c = _conn(db)
    fts_q = _fts_safe(query)
    sql = """
      SELECT g.fbgn, g.symbol, g.summary, g.n_bullets, g.provider,
             snippet(fts_genes, 3, '<b>', '</b>', '…', 32) AS snip
      FROM fts_genes
      JOIN genes g ON g.fbgn = fts_genes.fbgn
      WHERE fts_genes MATCH ?
    """
    params: list[Any] = [fts_q]
    if category:
        sql += " AND g.fbgn IN (SELECT DISTINCT fbgn FROM bullets WHERE category = ?)"
        params.append(category)
    if direction:
        sql += " AND g.fbgn IN (SELECT DISTINCT fbgn FROM bullets WHERE direction = ?)"
        params.append(direction)
    if confidence:
        sql += " AND g.fbgn IN (SELECT DISTINCT fbgn FROM bullets WHERE confidence = ?)"
        params.append(confidence)
    if tissue:
        sql += " AND g.fbgn IN (SELECT DISTINCT fbgn FROM tissues WHERE tissue = ?)"
        params.append(tissue)
    sql += " ORDER BY bm25(fts_genes) LIMIT ?"
    params.append(limit)
    return [dict(r) for r in c.execute(sql, params)]


def genes_by_disease(db, omim_or_name: str, limit: int = 200) -> list[dict]:
    c = _conn(db)
    sql = """
      SELECT g.fbgn, g.symbol, g.summary, d.name AS disease_name, d.omim_id,
             d.via_symbol, d.via_species
      FROM diseases d JOIN genes g ON g.fbgn = d.fbgn
      WHERE d.omim_id = ? OR d.name LIKE ?
      ORDER BY g.symbol LIMIT ?
    """
    return [dict(r) for r in c.execute(sql, (omim_or_name, f"%{omim_or_name}%", limit))]


def genes_by_ortholog(db, symbol: str, limit: int = 200) -> list[dict]:
    c = _conn(db)
    sql = """
      SELECT g.fbgn, g.symbol, g.summary, o.symbol AS ortho_symbol,
             o.species, o.diopt_score
      FROM orthologs o JOIN genes g ON g.fbgn = o.fbgn
      WHERE o.symbol = ? COLLATE NOCASE
      ORDER BY o.diopt_score DESC NULLS LAST LIMIT ?
    """
    return [dict(r) for r in c.execute(sql, (symbol, limit))]


def genes_by_paper(db, fbrf_or_pmid: str, limit: int = 500) -> list[dict]:
    c = _conn(db)
    sql = """
      SELECT g.fbgn, g.symbol, g.summary, r.fbrf, r.pmid, r.title, r.miniref
      FROM refs r JOIN genes g ON g.fbgn = r.fbgn
      WHERE r.fbrf = ? OR r.pmid = ?
      ORDER BY g.symbol LIMIT ?
    """
    return [dict(r) for r in c.execute(sql, (fbrf_or_pmid, fbrf_or_pmid, limit))]


def genes_by_tissue(db, tissue: str, limit: int = 500) -> list[dict]:
    c = _conn(db)
    sql = """
      SELECT DISTINCT g.fbgn, g.symbol, g.summary, g.n_bullets
      FROM tissues t JOIN genes g ON g.fbgn = t.fbgn
      WHERE t.tissue = ? COLLATE NOCASE
      ORDER BY g.n_bullets DESC LIMIT ?
    """
    return [dict(r) for r in c.execute(sql, (tissue, limit))]


def genes_by_category(db, category: str, *, confidence: str | None = None,
                       limit: int = 500) -> list[dict]:
    c = _conn(db)
    sql = """
      SELECT DISTINCT g.fbgn, g.symbol, g.summary,
             (SELECT COUNT(*) FROM bullets b2 WHERE b2.fbgn = g.fbgn AND b2.category = ?) AS n_in_cat
      FROM bullets b JOIN genes g ON g.fbgn = b.fbgn
      WHERE b.category = ?
    """
    params: list = [category, category]
    if confidence:
        sql += " AND b.confidence = ?"
        params.append(confidence)
    sql += " ORDER BY n_in_cat DESC LIMIT ?"
    params.append(limit)
    return [dict(r) for r in c.execute(sql, params)]
