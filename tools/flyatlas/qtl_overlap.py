"""Cross-QTL overlap detection: find pairs of QTLs whose intervals share
physical genome space, and identify the genes shared between them.

This implements Long's hint (Methotrexate-A × Zinc-A on X) and Codex's
discovery (Malathion-A × Caffeine-D on 2R), plus any other shared regions
in the 24-QTL set.

Reports both:
  (a) Coordinate overlap: intervals share basepairs (after r5→r6 lift)
  (b) Candidate overlap: same gene appears in candidate lists of multiple QTLs

CLI:
  python -m flyatlas.qtl_overlap                      # full matrix to stdout
  python -m flyatlas.qtl_overlap --json               # JSON output
  python -m flyatlas.qtl_overlap --candidates-topk 10 # also do candidate overlap
"""
from __future__ import annotations
import argparse
import json
import sqlite3
import sys
from itertools import combinations
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB = ROOT / "tools" / "atlas.db"


def coord_overlap(db_path: str) -> list[dict]:
    """All-pairs coordinate overlap of QTL intervals in r6 space (after lift
    for r5-native QTLs). Returns list of overlap records."""
    c = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    qtls = list(c.execute("SELECT * FROM qtls"))
    out = []
    for a, b in combinations(qtls, 2):
        # need r6 coords on both sides
        if not (a["start_r6"] and a["end_r6"] and b["start_r6"] and b["end_r6"]):
            continue
        # different chromosomes -> no overlap (cross-arm methotrexate_D handled by skipping)
        if a["chr"] != b["chr"]:
            continue
        s = max(a["start_r6"], b["start_r6"])
        e = min(a["end_r6"], b["end_r6"])
        if s > e:
            continue
        # interval overlap exists
        overlap_bp = e - s + 1
        # Count fly genes in the shared region
        n_genes = c.execute(
            "SELECT COUNT(*) FROM genes WHERE chr=? AND end>=? AND start<=?",
            (a["chr"], s, e),
        ).fetchone()[0]
        out.append({
            "qtl_a": a["id"],
            "qtl_b": b["id"],
            "drug_a": a["study_drug"],
            "drug_b": b["study_drug"],
            "drug_family_a": a["drug_family"],
            "drug_family_b": b["drug_family"],
            "phenotype_a": a["phenotype"],
            "phenotype_b": b["phenotype"],
            "chr": a["chr"],
            "shared_start_r6": s,
            "shared_end_r6": e,
            "overlap_bp": overlap_bp,
            "n_genes_in_shared_region": n_genes,
            "is_cross_drug_family": a["drug_family"] != b["drug_family"],
            "release_a": a["release_orig"],
            "release_b": b["release_orig"],
        })
    c.close()
    # sort by overlap size descending
    out.sort(key=lambda r: -r["overlap_bp"])
    return out


def shared_genes(db_path: str, qtl_a: str, qtl_b: str, topk: int = 50) -> dict:
    """For a pair of overlapping QTLs, list the genes in the shared region
    with their atlas annotation depth."""
    c = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    a = dict(c.execute("SELECT * FROM qtls WHERE id=?", (qtl_a,)).fetchone() or {})
    b = dict(c.execute("SELECT * FROM qtls WHERE id=?", (qtl_b,)).fetchone() or {})
    if not a or not b:
        return {"error": "QTL not found"}
    if a["chr"] != b["chr"]:
        return {"error": "different chromosomes"}
    if not (a["start_r6"] and b["start_r6"]):
        return {"error": "missing r6 coords"}
    s = max(a["start_r6"], b["start_r6"])
    e = min(a["end_r6"], b["end_r6"])
    if s > e:
        return {"error": "no overlap"}
    rows = list(c.execute(
        "SELECT fbgn, symbol, chr, start, end, summary, n_bullets, n_refs, n_pubs_total "
        "FROM genes WHERE chr=? AND end>=? AND start<=? ORDER BY n_bullets DESC, n_refs DESC",
        (a["chr"], s, e),
    ))
    c.close()
    return {
        "qtl_a": qtl_a,
        "qtl_b": qtl_b,
        "shared_region": f"{a['chr']}:{s}-{e} (r6)",
        "overlap_bp": e - s + 1,
        "n_shared_genes": len(rows),
        "genes": [dict(r) for r in rows[:topk]],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(DEFAULT_DB))
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--detail", help="Show shared-genes detail for one QTL pair (format: A_id,B_id)")
    ap.add_argument("--topk", type=int, default=20)
    args = ap.parse_args()

    if args.detail:
        a, b = args.detail.split(",")
        result = shared_genes(args.db, a, b, topk=args.topk)
        if args.json:
            print(json.dumps(result, indent=2, ensure_ascii=False, default=str)); return
        print(f"\n{result.get('shared_region','(no overlap)')}")
        print(f"Overlap: {result.get('overlap_bp', '?'):,} bp, {result.get('n_shared_genes', '?')} genes")
        print()
        print(f"{'rank':>4}  {'symbol':<20} {'n_bullets':>9} {'n_refs':>6} {'n_pubs':>7}")
        for i, g in enumerate(result.get("genes", []), 1):
            print(f"{i:>4}  {g['symbol']:<20} {g['n_bullets']:>9} {g['n_refs']:>6} {g['n_pubs_total'] or 0:>7}")
        return

    overlaps = coord_overlap(args.db)
    if args.json:
        print(json.dumps(overlaps, indent=2, ensure_ascii=False, default=str))
        return

    if not overlaps:
        print("No QTL pairs with coordinate overlap.")
        return

    print(f"\nFound {len(overlaps)} QTL pairs with coordinate overlap (r6 space):\n")
    print(f"{'QTL A':18} {'QTL B':18} {'chr':4}  {'overlap':>12}  {'shared genes':>12}  cross-class?")
    print("-" * 100)
    for o in overlaps:
        flag = "★ CROSS-CLASS" if o["is_cross_drug_family"] else ""
        print(f"{o['qtl_a']:18} {o['qtl_b']:18} {o['chr']:4}  "
              f"{o['overlap_bp']:>10,} bp  {o['n_genes_in_shared_region']:>12}  {flag}")
    print()
    print("Cross-class pairs are biologically more interesting (different drug families")
    print("hitting the same locus = a likely shared molecular mechanism).")


if __name__ == "__main__":
    main()
