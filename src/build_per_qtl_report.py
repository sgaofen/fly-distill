"""Generate a per-QTL focused report — one section per QTL in Long's compilation,
with top ranked candidate genes and their FlyBase biology context. This is the
deliverable shape Long actually asked for (per-trait candidate ranking), not the
cross-QTL overlap exploration.

Run:
  python src/build_per_qtl_report.py
  python src/build_per_qtl_report.py --topk 8
"""
from __future__ import annotations
import argparse
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from flyatlas.qtl_rank import rank_qtl, list_qtls
from flyatlas.qtl_overlap import coord_overlap


DEFAULT_DB = ROOT / "tools" / "atlas.db"
REPORT_OUT = ROOT / "output" / "qtl_per_qtl_report.md"


def fmt_int(n):
    return f"{n:,}" if n is not None else "—"


def fmt_bp(n):
    if n is None: return "—"
    if n >= 1_000_000: return f"{n/1_000_000:.2f} Mb"
    if n >= 1_000: return f"{n/1_000:.1f} kb"
    return f"{n} bp"


QUADRANT_GLYPH = {
    "STRONG": "✓ STRONG",
    "NOVEL_LEAD": "⚠ NOVEL",
    "LIKELY_NOT": "✗ likely not",
    "CANT_RULE_OUT": "? can't rule",
}


def write_per_qtl(f, qtl_id: str, db_path: str, topk: int) -> None:
    result = rank_qtl(db_path, qtl_id, topk=topk)
    q = result["qtl"]

    f.write(f"### {q['id']}\n\n")

    # Header table
    f.write(f"| | |\n|---|---|\n")
    f.write(f"| **Study drug** | {q['study_drug']} ({q['drug_family']}) |\n")
    f.write(f"| **Phenotype** | _{q['phenotype']}_ |\n")
    if q.get("start_r6") and q.get("end_r6"):
        f.write(f"| **Interval (r6)** | `{q['chr']}:{fmt_int(q['start_r6'])}–{fmt_int(q['end_r6'])}` ({fmt_bp((q['end_r6'] or 0)-(q['start_r6'] or 0))}) |\n")
    if q.get("release_orig") == "r5" and q.get("start_r5"):
        f.write(f"| **Interval (r5, native)** | `{q['chr']}:{fmt_int(q['start_r5'])}–{fmt_int(q['end_r5'])}` |\n")
    if q.get("neg_log_p"):
        f.write(f"| **Significance** | −log₁₀(P) = {q['neg_log_p']} |\n")
    if q.get("h2"):
        f.write(f"| **Heritability** | {q['h2']} |\n")
    if q.get("pmc_url"):
        f.write(f"| **Source paper** | [{q['pmc_url'].rstrip('/').split('/')[-1]}]({q['pmc_url']}) |\n")
    if q.get("gene_count") is not None:
        f.write(f"| **Reported gene count** | {q['gene_count']} |\n")
    f.write("\n")

    # Handle cross-arm degenerate case
    if "warning" in result and not result.get("candidates"):
        f.write(f"*Cannot resolve: {result['warning']}. Cross-arm QTLs require manual handling of the centromere-spanning region; the published interval (`{q['chr']}`) is not a single contiguous segment in the atlas's per-arm coordinate model.*\n\n")
        return

    s = result["summary"]
    f.write(f"**Quadrant breakdown** (all {s['total_in_interval']} genes in interval): ")
    f.write(f"✓ STRONG **{s['by_quadrant']['STRONG']}** · ")
    f.write(f"⚠ NOVEL_LEAD **{s['by_quadrant']['NOVEL_LEAD']}** · ")
    f.write(f"✗ LIKELY_NOT **{s['by_quadrant']['LIKELY_NOT']}** · ")
    f.write(f"? CANT_RULE_OUT **{s['by_quadrant']['CANT_RULE_OUT']}**\n\n")

    if not result["candidates"]:
        return

    f.write(f"**Top {len(result['candidates'])} candidate genes**\n\n")
    f.write("| Rank | Gene | Quadrant | ev | q | bullets | refs | pubs |\n")
    f.write("|---:|---|---|---:|---:|---:|---:|---:|\n")
    for i, g in enumerate(result["candidates"], 1):
        f.write(f"| {i} | `{g['symbol']}` | {QUADRANT_GLYPH[g['quadrant']]} | "
                f"{g['evidence']:.2f} | {g['quality']:.2f} | "
                f"{g['n_bullets']} | {g['n_refs']} | {g['n_pubs_total'] or 0} |\n")
    f.write("\n")

    # Per-candidate biological context: pull FlyBase summary + key citation
    c = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row

    f.write(f"**Biological context for top {min(5, len(result['candidates']))} candidates**\n\n")
    for i, g in enumerate(result["candidates"][:5], 1):
        full = c.execute("SELECT summary FROM genes WHERE fbgn=?", (g["fbgn"],)).fetchone()
        summary = (full["summary"] or "") if full else ""
        # Limit summary to first 2 sentences (or ~350 chars)
        sentences = summary.split(". ")
        snippet = ". ".join(sentences[:2])
        if len(snippet) > 380:
            snippet = snippet[:380] + "..."
        elif sentences and not snippet.endswith("."):
            snippet += "."

        # Get one top citation
        cit = c.execute("""SELECT DISTINCT miniref, pmid FROM citations
                           WHERE bullet_pk IN (SELECT id FROM bullets WHERE fbgn=?)
                           AND miniref IS NOT NULL LIMIT 1""", (g["fbgn"],)).fetchone()
        cit_str = ""
        if cit:
            cit_str = f" · ref: {cit['miniref']}"
            if cit["pmid"]:
                cit_str += f" (PMID {cit['pmid']})"

        f.write(f"**{i}. `{g['symbol']}` ({g['fbgn']})** — {QUADRANT_GLYPH[g['quadrant']]}, ev={g['evidence']:.2f}, q={g['quality']:.2f}\n\n")
        f.write(f"{snippet}{cit_str}\n\n")

    c.close()
    f.write("---\n\n")


def write_intro(f, n_qtls: int) -> None:
    f.write("# Drosophila QTL Atlas — Per-QTL Candidate Rankings\n\n")
    f.write("**Author:** Stephen Yu (Long Lab, UCI) · **Atlas:** fly-distill v1.4 (14,019 *D. melanogaster* protein-coding genes)\n\n")
    f.write("---\n\n")
    f.write("## What this is\n\n")
    f.write(f"For each of the **{n_qtls} mapped QTLs** in your study compilation, this report lists the genes inside the interval, ranks them on the two independent axes you described (evidence × annotation quality), and provides the FlyBase biological context for the top candidates of each QTL.\n\n")
    f.write("Each QTL is presented as a self-contained section. No comparisons across QTLs are made in the main body. Cross-QTL coordinate overlaps (an incidental observation while running the analysis) are included as a short appendix.\n\n")

    f.write("## Method (one paragraph)\n\n")
    f.write("For each gene in the atlas a dense semantic representation has been pre-computed from (a) its FlyBase one-paragraph summary, (b) all mouse-ortholog MGI knockout phenotype terms + human-ortholog HPO clinical phenotype terms + linked OMIM disease features (verbatim, no inference), and (c) the structured phenotype bullets distilled from FlyBase pubs and paper abstracts. For each QTL, the pipeline subsets the atlas to genes in the interval (via per-FBgn r5↔r6 coordinate lookup against FB2026_01 + FB2014_01 `gene_map_table`), then ranks them by cosine similarity between the QTL's phenotype description and each gene's representation. The **evidence score** captures phenotype–gene semantic match. The **quality score** captures how well-studied the gene is (bullet count, reference count, publication count, plus binary indicators for HPO / MGI / disease coverage; stub genes get a penalty term). Per your *absence of evidence ≠ evidence of absence* principle, the two scores are reported on independent axes and never collapsed into one number.\n\n")

    f.write("## Quadrants\n\n")
    f.write("| Quadrant | Meaning | Action |\n|---|---|---|\n")
    f.write("| ✓ **STRONG** | high evidence + well-annotated | priority follow-up |\n")
    f.write("| ⚠ **NOVEL LEAD** | high evidence + sparsely annotated | functional experiment candidate; possibly under-studied |\n")
    f.write("| ✗ **LIKELY NOT** | low evidence + well-annotated | can rule out with reasonable confidence |\n")
    f.write("| ? **CANT RULE OUT** | low evidence + sparsely annotated | preserved per absence-of-evidence principle |\n\n")
    f.write("Cutoffs are evidence ≥ 0.55 and quality ≥ 0.50.\n\n")

    f.write("## Coverage sanity check\n\n")
    f.write("| | |\n|---|---|\n")
    f.write("| Atlas FBgns | 14,019 |\n")
    f.write("| Atlas ∩ r6 gene_map_table (FB2026_01) | 13,986 (99.8 %) |\n")
    f.write("| Atlas ∩ r5 gene_map_table (FB2014_01) | 13,569 (96.8 %) |\n")
    f.write("| Atlas FBgns absent from both releases | 33 (0.2 %, retired/secondary IDs) |\n\n")
    f.write("Of your 16 r6-native QTLs, the atlas-resolved gene count exactly matches your reported count for 10; the remaining 6 differ by 1–2 genes at the interval boundary.\n\n")
    f.write("---\n\n")


def write_appendix_overlaps(f, db_path: str) -> None:
    f.write("## Appendix A — incidental cross-QTL coordinate overlaps\n\n")
    f.write("While running the per-QTL analysis above, the pipeline noticed that six pairs of QTLs in your compilation share genome space after the r5→r6 lift. This is not part of the per-trait candidate-ranking task and is included only for completeness.\n\n")

    overlaps = coord_overlap(db_path)
    if not overlaps:
        f.write("*No coordinate overlaps detected.*\n\n")
        return

    f.write("| QTL A | QTL B | Chr | Shared region (r6) | Overlap | Genes in shared region | Class |\n")
    f.write("|---|---|---|---|---:|---:|---|\n")
    for o in overlaps:
        class_label = "cross-family" if o["is_cross_drug_family"] else "same-family (chemo × chemo)"
        f.write(f"| `{o['qtl_a']}` ({o['drug_a']}) | `{o['qtl_b']}` ({o['drug_b']}) | {o['chr']} | "
                f"{fmt_int(o['shared_start_r6'])}–{fmt_int(o['shared_end_r6'])} | "
                f"{fmt_bp(o['overlap_bp'])} | {o['n_genes_in_shared_region']} | {class_label} |\n")
    f.write("\n")
    f.write("Each overlap can be inspected at `/qtl-overlap/<A>/<B>` in the web UI, which lists the genes shared between the two intervals with semantic-similarity scores against both parent phenotypes.\n\n")


def write_repro(f) -> None:
    f.write("---\n\n")
    f.write("## Reproducibility\n\n")
    f.write("| Item | Location |\n|---|---|\n")
    f.write("| Source repository | https://github.com/sgaofen/fly-distill |\n")
    f.write("| v1.4 release (atlas + canonicals + embeddings) | https://github.com/sgaofen/fly-distill/releases/tag/v1.4 |\n")
    f.write("| QTL input (your file, verbatim) | `data/QTL_summary.md` |\n")
    f.write("| Web UI | `python -m flyatlas.cli serve` → http://localhost:8765/qtl |\n")
    f.write("| Per-QTL CLI | `python -m flyatlas.cli qtl-rank caffeine_D --topk 20` |\n")
    f.write("| r5 region query | `python -m flyatlas.cli ask 'DNA damage' --region X:13.25e6-14.60e6 --release r5` |\n")
    f.write("| r5↔r6 lift | `python -m flyatlas.cli lift X:13.25e6-14.60e6 --from r5` |\n")
    f.write("| Regenerate this report | `python src/build_per_qtl_report.py` |\n\n")
    f.write("**Runtime dependency:** a Gemini embedding API key (`gemini-embedding-2`) for the query-time semantic vector. All other data (atlas database, gene canonicals, pre-computed embeddings) ships in the v1.4 release tarballs.\n\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(DEFAULT_DB))
    ap.add_argument("--out", default=str(REPORT_OUT))
    ap.add_argument("--topk", type=int, default=10,
                    help="Top-K candidates shown per QTL (default 10)")
    args = ap.parse_args()

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    qtls = list_qtls(args.db)
    # Sort: r6-native first (more reliable), then by neg_log_p desc, then by drug
    qtls.sort(key=lambda q: (q["release_orig"] == "r5",
                             -(q["neg_log_p"] or 0),
                             q["study_drug"], q["id"]))

    print(f"Generating per-QTL report for {len(qtls)} QTLs (topk={args.topk})...")

    with open(out_path, "w") as f:
        write_intro(f, len(qtls))

        # Group by study (drug) for navigability
        from collections import defaultdict
        by_drug = defaultdict(list)
        for q in qtls:
            by_drug[q["study_drug"]].append(q)

        # Order drugs by release_orig (r6 first) then by strongest QTL
        drug_order = sorted(by_drug.keys(),
                             key=lambda d: (
                                 by_drug[d][0]["release_orig"] == "r5",
                                 -(max((q["neg_log_p"] or 0) for q in by_drug[d])),
                                 d,
                             ))

        f.write("## Per-QTL candidate rankings\n\n")
        for drug in drug_order:
            qs = by_drug[drug]
            family = qs[0]["drug_family"]
            release = qs[0]["release_orig"]
            n = len(qs)
            f.write(f"## {drug} ({family}, {release}; {n} QTL{'s' if n > 1 else ''})\n\n")
            for q in qs:
                write_per_qtl(f, q["id"], args.db, args.topk)
                print(f"  · {q['id']}", flush=True)

        write_appendix_overlaps(f, args.db)
        write_repro(f)

        f.write("---\n\n")
        f.write("*Per-QTL ranking framework follows your 2026-05-19 description. Comments and corrections welcome.*\n")

    n_bytes = out_path.stat().st_size
    print(f"\nWrote {out_path} ({n_bytes:,} bytes)")


if __name__ == "__main__":
    main()
