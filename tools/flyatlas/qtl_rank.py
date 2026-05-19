"""QTL fine-mapping: 2D scoring for candidate genes in a QTL interval.

Implements Long's framework from the 2026-05-19 email:
  - Dimension 1: Evidence score (Gemini cosine similarity between phenotype
    description and gene embedding)
  - Dimension 2: Annotation quality score (composite: how well-studied is this
    gene? — n_bullets, n_refs, n_pubs, cross-species data, etc.)

Each candidate gets assigned to a quadrant:
  - STRONG       — high evidence  + high quality (top priority follow-up)
  - NOVEL_LEAD   — high evidence  + low quality  (worth functional experiment)
  - LIKELY_NOT   — low evidence   + high quality (can rule out with confidence)
  - CANT_RULE_OUT — low evidence  + low quality  (absence of evidence is not
                                                   evidence of absence — keep)

CLI:
  python -m flyatlas.qtl_rank caffeine_D --topk 20
  python -m flyatlas.qtl_rank-all --out output/qtl_candidates.tsv
"""
from __future__ import annotations
import argparse
import json
import math
import sqlite3
import sys
from pathlib import Path

from . import DB_PATH

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB = ROOT / "tools" / "atlas.db"

EVIDENCE_THRESHOLD = 0.55  # cosine similarity above this = "high evidence"
QUALITY_THRESHOLD = 0.50   # quality score above this = "well-annotated"


def annotation_quality(gene: dict, has_HPO: bool, has_MGI: bool,
                       has_disease: bool) -> float:
    """Codex-suggested weights. Each component normalized to [0,1] via log-scale,
    then weighted, then penalized if the gene is a stub (≤3 bullets).

    Final score is clamped to [0,1].
    """
    n_bullets = gene.get("n_bullets") or 0
    n_refs    = gene.get("n_refs")    or 0
    n_pubs    = gene.get("n_pubs_total") or 0

    # log-scale normalizations (saturate at typical "well-studied" levels)
    s_bullets = min(1.0, math.log1p(n_bullets) / math.log1p(30))   # 30 bullets = saturated
    s_refs    = min(1.0, math.log1p(n_refs)    / math.log1p(25))   # 25 refs = saturated
    s_pubs    = min(1.0, math.log1p(n_pubs)    / math.log1p(500))  # 500 papers = saturated

    score = (0.30 * s_bullets
             + 0.25 * s_refs
             + 0.20 * s_pubs
             + 0.10 * (1.0 if has_HPO else 0.0)
             + 0.10 * (1.0 if has_MGI else 0.0)
             + 0.05 * (1.0 if has_disease else 0.0))

    if n_bullets <= 3:
        score -= 0.15

    return max(0.0, min(1.0, score))


def quadrant(evidence: float, quality: float) -> str:
    e_hi = evidence >= EVIDENCE_THRESHOLD
    q_hi = quality  >= QUALITY_THRESHOLD
    if e_hi and q_hi:     return "STRONG"
    if e_hi and not q_hi: return "NOVEL_LEAD"
    if not e_hi and q_hi: return "LIKELY_NOT"
    return "CANT_RULE_OUT"


def get_qtl(db_path: str, qtl_id: str) -> dict | None:
    c = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    r = c.execute("SELECT * FROM qtls WHERE id = ?", (qtl_id,)).fetchone()
    c.close()
    return dict(r) if r else None


def list_qtls(db_path: str) -> list[dict]:
    c = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    rows = list(c.execute("SELECT * FROM qtls ORDER BY id"))
    c.close()
    return [dict(r) for r in rows]


def genes_in_qtl(db_path: str, qtl: dict, use_release: str = "r6") -> list[dict]:
    """Pull genes in the QTL interval. If r6 mapping not available
    (e.g. r5-only QTL with no r6 cross-lift), fall back to r5 columns."""
    c = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row

    chr_ = qtl["chr"]
    if use_release == "r6" and qtl.get("start_r6") and qtl.get("end_r6"):
        s, e = qtl["start_r6"], qtl["end_r6"]
        sql = ("SELECT fbgn, symbol, chr, start, end, summary, n_bullets, n_refs, n_pubs_total "
               "FROM genes WHERE chr = ? AND end >= ? AND start <= ? ORDER BY start")
    elif qtl.get("start_r5") and qtl.get("end_r5"):
        s, e = qtl["start_r5"], qtl["end_r5"]
        sql = ("SELECT fbgn, symbol, chr_r5 as chr, start_r5 as start, end_r5 as end, "
               "summary, n_bullets, n_refs, n_pubs_total "
               "FROM genes WHERE chr_r5 = ? AND end_r5 >= ? AND start_r5 <= ? ORDER BY start_r5")
    else:
        c.close()
        return []
    rows = [dict(r) for r in c.execute(sql, (chr_, s, e))]
    c.close()
    return rows


def annotate_cross_species(db_path: str, fbgns: list[str]) -> dict[str, dict]:
    """Returns {fbgn: {has_HPO, has_MGI, has_disease}}."""
    c = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    out = {}
    # Have human ortholog records?  (use canonical JSON for hpo/mgi phenotype rows
    # which the orthologs SQL table doesn't carry — but we can proxy: any human
    # ortholog row = potential HPO; any mouse ortholog row = potential MGI.)
    for fbgn in fbgns:
        has_human = c.execute(
            "SELECT 1 FROM orthologs WHERE fbgn=? AND species='human' LIMIT 1", (fbgn,)
        ).fetchone() is not None
        has_mouse = c.execute(
            "SELECT 1 FROM orthologs WHERE fbgn=? AND species='mouse' LIMIT 1", (fbgn,)
        ).fetchone() is not None
        has_disease = c.execute(
            "SELECT 1 FROM diseases WHERE fbgn=? AND omim_id IS NOT NULL LIMIT 1", (fbgn,)
        ).fetchone() is not None
        # For HPO/MGI phenotype-term presence, we'd need to read canonicals.
        # As a starting heuristic: has_human ⇒ has_HPO candidate, has_mouse ⇒ has_MGI candidate.
        out[fbgn] = {"has_HPO": has_human, "has_MGI": has_mouse, "has_disease": has_disease}
    c.close()
    return out


def annotate_cross_species_from_canonical(fbgns: list[str]) -> dict[str, dict]:
    """Stricter version: actually read canonical JSON for each FBgn and check
    whether the phenotype TERMS are present (not just ortholog symbols).
    Falls back to has=False if canonical missing."""
    out = {}
    canon_dir = ROOT / "output" / "genes"
    for fbgn in fbgns:
        p = canon_dir / f"{fbgn}.json"
        if not p.exists():
            out[fbgn] = {"has_HPO": False, "has_MGI": False, "has_disease": False}
            continue
        try:
            j = json.loads(p.read_text())
        except Exception:
            out[fbgn] = {"has_HPO": False, "has_MGI": False, "has_disease": False}
            continue
        cs = j.get("cross_species") or {}
        has_HPO = any(o.get("hpo_phenotypes") for o in (cs.get("human_orthologs") or []))
        has_MGI = any(o.get("mgi_phenotypes") for o in (cs.get("mouse_orthologs") or []))
        has_disease = any(d.get("omim_id") for d in (cs.get("human_disease_links") or []))
        out[fbgn] = {"has_HPO": has_HPO, "has_MGI": has_MGI, "has_disease": has_disease}
    return out


def rank_qtl(db_path: str, qtl_id: str, topk: int = 20,
             use_canonical_cs: bool = True) -> dict:
    """Returns full 2D ranking for one QTL."""
    qtl = get_qtl(db_path, qtl_id)
    if not qtl:
        return {"error": f"unknown QTL: {qtl_id}"}

    genes = genes_in_qtl(db_path, qtl)
    if not genes:
        return {"qtl": qtl, "candidates": [], "warning": "no genes in interval"}

    # Cross-species annotations
    fbgns = [g["fbgn"] for g in genes]
    cs_map = (annotate_cross_species_from_canonical(fbgns) if use_canonical_cs
              else annotate_cross_species(db_path, fbgns))

    # Quality score for every gene in interval
    for g in genes:
        cs = cs_map.get(g["fbgn"], {})
        g["has_HPO"] = cs.get("has_HPO", False)
        g["has_MGI"] = cs.get("has_MGI", False)
        g["has_disease"] = cs.get("has_disease", False)
        g["quality"] = annotation_quality(g, g["has_HPO"], g["has_MGI"], g["has_disease"])

    # Evidence score: ask Gemini semantic ranker for these specific genes only
    from . import embed_query as EQ
    try:
        sem = EQ.semantic_search(qtl["phenotype"], top_k=len(fbgns), fbgn_filter=fbgns)
        score_by_fbgn = {r["fbgn"]: r["score"] for r in sem}
    except Exception as e:
        return {"qtl": qtl, "candidates": [], "error": f"semantic ranking failed: {e}"}

    for g in genes:
        g["evidence"] = score_by_fbgn.get(g["fbgn"], 0.0)
        g["quadrant"] = quadrant(g["evidence"], g["quality"])

    # Sort: STRONG first, then NOVEL_LEAD, then LIKELY_NOT, then CANT_RULE_OUT;
    # within each, by evidence × quality (Stephen-Long composite)
    quadrant_order = {"STRONG": 0, "NOVEL_LEAD": 1, "LIKELY_NOT": 2, "CANT_RULE_OUT": 3}
    genes.sort(key=lambda g: (quadrant_order[g["quadrant"]], -g["evidence"] - 0.3 * g["quality"]))

    return {
        "qtl": qtl,
        "candidates": genes[:topk] if topk else genes,
        "summary": {
            "total_in_interval": len(genes),
            "by_quadrant": {q: sum(1 for g in genes if g["quadrant"] == q)
                            for q in ["STRONG", "NOVEL_LEAD", "LIKELY_NOT", "CANT_RULE_OUT"]},
        },
    }


def render_human(result: dict) -> str:
    if "error" in result:
        return f"ERROR: {result['error']}"
    q = result["qtl"]
    lines = []
    lines.append(f"\nQTL: {q['id']}  ({q['study_drug']}, {q['drug_family']}, original={q['release_orig']})")
    lines.append(f"  Phenotype:  {q['phenotype']}")
    lines.append(f"  Interval r6: {q['chr']}:{q.get('start_r6')}-{q.get('end_r6')}")
    if q.get("start_r5"):
        lines.append(f"  Interval r5: {q['chr']}:{q.get('start_r5')}-{q.get('end_r5')}")
    if q.get("neg_log_p"):
        lines.append(f"  Significance: -log10(P) = {q['neg_log_p']}")
    if q.get("pmc_url"):
        lines.append(f"  Source: {q['pmc_url']}")
    lines.append(f"  Gene count: {result['summary']['total_in_interval']} (Long reported: {q.get('gene_count')})")
    lines.append("")
    s = result["summary"]["by_quadrant"]
    lines.append(f"  Quadrants:  STRONG={s['STRONG']}  NOVEL_LEAD={s['NOVEL_LEAD']}"
                 f"  LIKELY_NOT={s['LIKELY_NOT']}  CANT_RULE_OUT={s['CANT_RULE_OUT']}")
    lines.append("")
    lines.append(f"  {'rank':>4}  {'symbol':<18} {'quadrant':<14} {'ev':>5}  {'q':>5}  {'b':>3} {'r':>4} {'p':>5}")
    lines.append("  " + "-" * 70)
    for i, g in enumerate(result["candidates"], 1):
        lines.append(f"  {i:>4}  {g['symbol']:<18} {g['quadrant']:<14}  "
                     f"{g['evidence']:.2f}  {g['quality']:.2f}  "
                     f"{g['n_bullets']:>3} {g['n_refs']:>4} {g['n_pubs_total'] or 0:>5}")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("qtl_id", nargs="?", help="QTL id (e.g. caffeine_D); omit to list all")
    ap.add_argument("--topk", type=int, default=20)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--db", default=str(DEFAULT_DB))
    args = ap.parse_args()

    if not args.qtl_id:
        # list mode
        rows = list_qtls(args.db)
        if args.json:
            print(json.dumps(rows, indent=2, ensure_ascii=False))
            return
        print(f"{'id':22} {'drug':14} {'chr':6} {'release':>7}  {'genes':>6}  phenotype")
        print("-" * 110)
        for r in rows:
            print(f"{r['id']:22} {r['study_drug']:14} {r['chr']:6} {r['release_orig']:>7}  "
                  f"{(r['gene_count'] or 0):>6}  {r['phenotype'][:60]}")
        return

    result = rank_qtl(args.db, args.qtl_id, topk=args.topk)
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
    else:
        print(render_human(result))


if __name__ == "__main__":
    main()
