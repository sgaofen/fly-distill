"""Generate a focused before/after demo for 4 representative QTLs.
Minimal narrative. Email body carries the context; PDF carries the data.
"""
from __future__ import annotations
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from flyatlas.qtl_rank import rank_qtl


DB = str(ROOT / "tools" / "atlas.db")
OUT = ROOT / "output" / "qtl_enriched_demo.md"


ENRICHED = {
    "Carboplatin": (
        "Female fly fertility loss after carboplatin chemotherapy exposure. "
        "Carboplatin is a platinum-based chemotherapy agent that forms DNA "
        "crosslinks in proliferating cells, causing germline stem-cell death "
        "and ovary atrophy. The best candidate genes are protective against "
        "platinum DNA damage: DNA crosslink repair, apoptosis suppression in "
        "the germline, or pharmacokinetic resistance (efflux, glutathione conjugation)."
    ),
    "Gemcitabine": (
        "Female fly fertility loss after gemcitabine chemotherapy exposure. "
        "Gemcitabine is a cytidine analog incorporated into DNA during "
        "replication, stalling synthesis and killing fast-dividing germline "
        "cells, causing ovary atrophy. Best candidates protect against "
        "nucleoside-analog incorporation, repair stalled forks, or reduce "
        "germline apoptosis."
    ),
    "Methotrexate": (
        "Female fly fertility loss after methotrexate chemotherapy exposure. "
        "Methotrexate is a dihydrofolate reductase inhibitor that depletes "
        "tetrahydrofolate pools, blocking thymidylate synthesis and stalling "
        "DNA replication in proliferating germline cells. Best candidates "
        "are protective against folate-pathway depletion, DNA damage from "
        "thymine starvation, or pharmacokinetic resistance."
    ),
    "Malathion": (
        "Adult fly mortality after malathion exposure. Malathion is an "
        "organophosphate insecticide that irreversibly inhibits "
        "acetylcholinesterase (AChE), causing toxic acetylcholine buildup and "
        "neuromuscular overstimulation. Best candidates protect against "
        "organophosphate toxicity: cytochrome P450 / esterase xenobiotic "
        "detoxification, glutathione conjugation, ABC-transporter efflux, "
        "or modulation of cholinergic signaling."
    ),
    "Zinc": (
        "Larval fly mortality after zinc chloride (ZnCl2) exposure. Zinc "
        "toxicity disrupts metal ion homeostasis, induces oxidative stress, "
        "and impairs neuromuscular function. Best candidates protect against "
        "heavy-metal toxicity: metallothionein (Mtn) family metal scavenging, "
        "zinc transporter regulation, antioxidant defense, ferritin storage."
    ),
    "Caffeine": (
        "Adult-female fly longevity under chronic 1% caffeine exposure. "
        "Caffeine is a methylxanthine alkaloid xenobiotic; it antagonizes "
        "adenosine receptors, inhibits phosphodiesterase, elevates cAMP, "
        "and induces oxidative stress. Best candidates protect against "
        "chronic caffeine toxicity: cytochrome P450 xenobiotic detoxification, "
        "antioxidant defense, regulation of adenosine/cAMP signaling, "
        "stress-response transcription factors."
    ),
}


DEMO_QTLS = ["zinc_D", "methotrexate_A", "malathion_A", "caffeine_D"]


def run(qtl_id: str, phenotype_override: str | None = None, topk: int = 7):
    if phenotype_override is None:
        return rank_qtl(DB, qtl_id, topk=topk)
    from flyatlas import qtl_rank as QR
    original_get_qtl = QR.get_qtl
    try:
        def patched(db, qid):
            q = original_get_qtl(db, qid)
            if q:
                q = dict(q)
                q["phenotype"] = phenotype_override
            return q
        QR.get_qtl = patched
        return rank_qtl(DB, qtl_id, topk=topk)
    finally:
        QR.get_qtl = original_get_qtl


def get_summary(fbgn: str) -> str:
    c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    r = c.execute("SELECT summary FROM genes WHERE fbgn=?", (fbgn,)).fetchone()
    c.close()
    s = (r["summary"] or "") if r else ""
    sentences = s.split(". ")
    short = ". ".join(sentences[:1])
    if len(short) > 220:
        short = short[:220] + "..."
    elif sentences and not short.endswith("."):
        short += "."
    return short


def write_qtl_section(f, qtl_id: str) -> None:
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    qrow_raw = c.execute("SELECT * FROM qtls WHERE id=?", (qtl_id,)).fetchone()
    if not qrow_raw:
        return
    qrow = dict(qrow_raw)
    c.close()

    drug = qrow["study_drug"]
    enriched_query = ENRICHED.get(drug)
    if not enriched_query: return

    before = run(qtl_id, phenotype_override=None, topk=7)
    after = run(qtl_id, phenotype_override=enriched_query, topk=7)

    # Header
    f.write(f'<div class="qtl-section">\n\n')
    f.write(f"## {qtl_id} — {drug}\n\n")
    f.write(f"`{qrow['chr']}:{qrow['start_r6']:,}–{qrow['end_r6']:,}`")
    if qrow.get("neg_log_p"):
        f.write(f" · −log₁₀(P) = {qrow['neg_log_p']}")
    if qrow.get("gene_count"):
        f.write(f" · {qrow['gene_count']} genes")
    f.write("\n\n")

    # Query comparison block
    f.write('<div class="query-block">\n\n')
    f.write(f'**Original query** ({len(qrow["phenotype"].split())} words):\n\n')
    f.write(f'> _{qrow["phenotype"]}_\n\n')
    f.write(f'**Enriched query** ({len(enriched_query.split())} words):\n\n')
    f.write(f'> _{enriched_query}_\n\n')
    f.write('</div>\n\n')

    # Top 7 side-by-side
    before_syms = [g["symbol"] for g in before["candidates"]]
    after_syms = [g["symbol"] for g in after["candidates"]]
    before_set = set(before_syms)
    after_set = set(after_syms)

    f.write("**Top 7 candidates** (★ = newly appearing after enrichment)\n\n")
    f.write("| Rank | Before | After |\n|---:|---|---|\n")
    for i in range(7):
        b = before_syms[i] if i < len(before_syms) else ""
        a = after_syms[i] if i < len(after_syms) else ""
        a_star = f"**{a}** ★" if a and a not in before_set else f"`{a}`"
        b_str = f"`{b}`"
        f.write(f"| {i+1} | {b_str} | {a_star} |\n")
    f.write("\n")

    # Risers — each as its own block
    rose = [c for c in after["candidates"] if c["symbol"] not in before_set]
    if rose:
        f.write("**Newly entering top 7**\n\n")
        f.write('<div class="rise-list">\n\n')
        for g in rose:
            summary = get_summary(g["fbgn"])
            f.write(f'<div class="gene-entry">\n')
            f.write(f'<div class="gene-head"><strong>{g["symbol"]}</strong> '
                    f'<code>({g["fbgn"]})</code> — ev = {g["evidence"]:.2f}, '
                    f'{g["n_bullets"]} bullets</div>\n')
            f.write(f'<div class="gene-bio">{summary}</div>\n')
            f.write(f'</div>\n\n')
        f.write('</div>\n\n')

    # Fallers — just a list of names + bullet count, no bio
    fell = [c for c in before["candidates"] if c["symbol"] not in after_set]
    if fell:
        names = ", ".join(f"`{g['symbol']}`" for g in fell)
        f.write(f"**Dropping out**: {names}\n\n")

    f.write('</div>\n\n')


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w") as f:
        f.write("# QTL Candidate Ranking — Before/After Enriched Query\n\n")
        f.write("Demo on 4 representative QTLs. Atlas, embeddings, and ranking algorithm are unchanged — only the query text is enriched with the drug mechanism.\n\n")
        f.write("---\n\n")
        for qtl_id in DEMO_QTLS:
            print(f"  ranking {qtl_id}...", flush=True)
            write_qtl_section(f, qtl_id)
    n = OUT.stat().st_size
    print(f"\nWrote {OUT} ({n:,} bytes)")


if __name__ == "__main__":
    main()
