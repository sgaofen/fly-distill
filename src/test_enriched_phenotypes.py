"""Test Long's critique: re-rank each QTL with drug-mechanism-enriched phenotype
queries, diff against the original generic-survival queries, and report whether
the new top candidates make more sense biologically.

Long's exact words (5/19 19:50):
  "I am not sure it is seeing the phenotypes correctly. ... it is not so much
   the larval death that is interesting, but the death after exposure the zinc
   chloride. The best genes are the ones that are somehow protective against
   the heavy metal."

He gave us the precise mechanism descriptions for zinc and malathion. For
chemo and caffeine we use parallel mechanism phrasing constructed from
canonical pharmacology.

Run:
  python src/test_enriched_phenotypes.py
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


# Drug-mechanism-aware queries. Stays close to Long's phrasing for zinc &
# malathion; constructs parallel mechanism phrasing for chemo & caffeine.
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
        "Gemcitabine is a cytidine analog that is incorporated into DNA during "
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


def run(qtl_id: str, phenotype_override: str | None = None, topk: int = 7):
    """Run rank_qtl with an optional phenotype override."""
    if phenotype_override is None:
        return rank_qtl(DB, qtl_id, topk=topk)
    # Patch via monkey-patch of get_qtl in qtl_rank
    from flyatlas import qtl_rank as QR
    original_get_qtl = QR.get_qtl
    try:
        def patched_get_qtl(db, qid):
            q = original_get_qtl(db, qid)
            if q:
                q = dict(q)
                q["phenotype"] = phenotype_override
            return q
        QR.get_qtl = patched_get_qtl
        return rank_qtl(DB, qtl_id, topk=topk)
    finally:
        QR.get_qtl = original_get_qtl


def fmt_candidates(cands):
    return [f"{c['symbol']}({c['n_bullets']}b,ev={c['evidence']:.2f})" for c in cands]


def main():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    qtls = list(c.execute("SELECT id, study_drug, phenotype FROM qtls ORDER BY study_drug, id"))
    c.close()

    print("="*78)
    print("ENRICHED PHENOTYPE QUERIES (Long's framing)")
    print("="*78)
    for drug, text in ENRICHED.items():
        print(f"\n  {drug}:")
        print(f"    {text[:200]}{'...' if len(text) > 200 else ''}")
    print()

    print("\n" + "="*78)
    print("BEFORE/AFTER per QTL — top 7 candidates")
    print("="*78)

    drug_summary = {}

    for q in qtls:
        qtl_id = q["id"]
        drug = q["study_drug"]
        orig_phenotype = q["phenotype"]
        enriched = ENRICHED.get(drug)
        if not enriched:
            print(f"\n[skip] {qtl_id} — no enriched query for drug={drug}")
            continue

        # BEFORE
        old = run(qtl_id, phenotype_override=None, topk=7)
        # AFTER
        new = run(qtl_id, phenotype_override=enriched, topk=7)

        old_syms = set(c["symbol"] for c in (old.get("candidates") or []))
        new_syms = set(c["symbol"] for c in (new.get("candidates") or []))
        added = new_syms - old_syms
        dropped = old_syms - new_syms
        same = old_syms & new_syms

        # accumulate per-drug summary
        drug_summary.setdefault(drug, {"qtls": 0, "added": 0, "dropped": 0, "stable": 0,
                                       "examples_added": set(), "examples_dropped": set()})
        ds = drug_summary[drug]
        ds["qtls"] += 1
        ds["added"] += len(added)
        ds["dropped"] += len(dropped)
        ds["stable"] += len(same)
        ds["examples_added"].update(list(added)[:5])
        ds["examples_dropped"].update(list(dropped)[:5])

        print(f"\n── {qtl_id} ({drug}) ──")
        print(f"  orig query: {orig_phenotype}")
        print(f"  BEFORE: {', '.join(fmt_candidates(old.get('candidates') or [])[:7])}")
        print(f"  AFTER:  {', '.join(fmt_candidates(new.get('candidates') or [])[:7])}")
        if added:
            print(f"   + NEW (top-7 only after enrichment): {sorted(added)}")
        if dropped:
            print(f"   – DROPPED (top-7 only before): {sorted(dropped)}")

    print("\n" + "="*78)
    print("PER-DRUG ROLL-UP")
    print("="*78)
    for drug, ds in drug_summary.items():
        n = ds["qtls"]
        n_pos = n * 7  # total slots across all this drug's QTLs in top-7
        stability = ds["stable"] / max(1, ds["added"] + ds["dropped"] + ds["stable"])
        print(f"\n{drug} ({n} QTL(s), {n_pos} top-7 slots total):")
        print(f"  stable rank slots: {ds['stable']}")
        print(f"  newly appeared:    {ds['added']}")
        print(f"  dropped out:       {ds['dropped']}")
        if ds["examples_added"]:
            print(f"  rising candidates: {sorted(ds['examples_added'])[:10]}")
        if ds["examples_dropped"]:
            print(f"  falling candidates: {sorted(ds['examples_dropped'])[:10]}")


if __name__ == "__main__":
    main()
