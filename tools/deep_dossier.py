#!/usr/bin/env python3
"""deep_dossier.py — pull the full local FlyBase bulk record for one gene.

The distilled atlas is a lossy first-pass (e.g. Svip = 19 bullets from 39 pubs,
no interaction layer). This tool reads the raw local bulk so an agent can move a
top candidate from "atlas triage" to "evidence-grounded verdict" WITHOUT going
online. Full article text still needs the PMIDs listed at the end.

Usage:
  python3 deep_dossier.py Svip
  python3 deep_dossier.py FBgn0052039
  python3 deep_dossier.py Svip --json
"""
from __future__ import annotations
import argparse, gzip, json, re, sqlite3, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BULK = ROOT / "data" / "flybase_bulk"
DB = ROOT / "tools" / "atlas.db"
GENES = ROOT / "output" / "genes"

F = {
    "geno_pheno": BULK / "alleles" / "genotype_phenotype_data_fb_2026_01.tsv.gz",
    "allele_desc": BULK / "alleles" / "dmel_classical_and_insertion_allele_descriptions_fb_2026_01.tsv.gz",
    "fbal2fbgn": BULK / "alleles" / "fbal_to_fbgn_fb_2026_01.tsv.gz",
    "gen_int": BULK / "genes" / "gene_genetic_interactions_fb_2026_01.tsv.gz",
    "phys_int": BULK / "genes" / "physical_interactions_mitab_fb_2026_01.tsv.gz",
    "entity_pub": BULK / "references" / "entity_publication_fb_2026_01.tsv.gz",
    "fbrf_map": BULK / "references" / "fbrf_pmid_pmcid_doi_fb_2026_01.tsv.gz",
    "snapshot": BULK / "genes" / "gene_snapshots_fb_2026_01.tsv.gz",
    "best_sum": BULK / "genes" / "best_gene_summary_fb_2026_01.tsv.gz",
}
FBRF = re.compile(r"FBrf\d{7}")
FBDV = re.compile(r"FBdv:\d+")
PMID = None


def rows(path):
    with gzip.open(path, "rt", errors="replace") as fh:
        for line in fh:
            if line.startswith("#") or not line.strip():
                continue
            yield line.rstrip("\n").split("\t")


def resolve_fbgn(token: str) -> tuple[str, str]:
    if token.startswith("FBgn"):
        db = sqlite3.connect(DB)
        r = db.execute("SELECT symbol FROM genes WHERE fbgn=?", (token,)).fetchone()
        return token, (r[0] if r else token)
    db = sqlite3.connect(DB)
    r = db.execute("SELECT fbgn, symbol FROM genes WHERE symbol=? COLLATE NOCASE", (token,)).fetchone()
    if r:
        return r[0], r[1]
    r = db.execute("SELECT g.fbgn, g.symbol FROM genes g JOIN synonyms s ON s.fbgn=g.fbgn WHERE s.synonym=? COLLATE NOCASE", (token,)).fetchone()
    if r:
        return r[0], r[1]
    sys.exit(f"Could not resolve '{token}' to an FBgn via atlas.db")


def collect(fbgn: str, symbol: str) -> dict:
    # 1. alleles for this gene (desc file: col1=FBal, col3=FBgn, last nonempty=description)
    alleles = []
    fbals = set()
    for c in rows(F["allele_desc"]):
        if len(c) > 3 and c[3] == fbgn:
            fbal = c[1]
            fbals.add(fbal)
            desc = next((x for x in reversed(c) if x and not x.startswith(("FB", "GO:")) and x != "0"), "")
            alleles.append({"allele": c[0], "fbal": fbal, "class": c[4] if len(c) > 4 else "", "desc": desc})
    # also map any FBal -> this gene (catches alleles only in fbal2fbgn)
    for c in rows(F["fbal2fbgn"]):
        if len(c) > 2 and c[2] == fbgn:
            fbals.add(c[0])

    # 2. genotype -> phenotype rows whose allele set intersects this gene's FBals
    gp = []
    for c in rows(F["geno_pheno"]):
        if len(c) < 3:
            continue
        line_fbals = set(c[1].split()) if len(c) > 1 else set()
        if not (line_fbals & fbals) and symbol not in c[0]:
            continue
        stage = next((x for x in c if FBDV.search(x)), "")
        rf = next((m.group() for x in c for m in [FBRF.search(x)] if m), "")
        gp.append({"genotype": c[0], "phenotype": c[2], "stage": stage.replace("FBdv:", ""), "fbrf": rf})

    # 3. genetic interactions (col1=FBgn or interactor col3 contains FBgn)
    gint = []
    for c in rows(F["gen_int"]):
        if len(c) > 5 and (c[1] == fbgn or fbgn in c[3]):
            gint.append({"gene": c[0], "interactor": c[2], "type": c[4], "fbrf": c[5]})

    # 4. snapshot + best summary
    snap = best = ""
    for c in rows(F["snapshot"]):
        if c and c[0] == fbgn:
            snap = c[-1]
            break
    for c in rows(F["best_sum"]):
        if c and c[0] == fbgn:
            best = c[-1]
            break

    # 5. publications for this gene, mapped to PMID/PMCID/DOI
    fbrfs = []
    for c in rows(F["entity_pub"]):
        if c and c[0] == fbgn and len(c) > 2 and c[2].startswith("FBrf"):
            fbrfs.append(c[2])
    fbrfs = list(dict.fromkeys(fbrfs))
    refmap = {}
    want = set(fbrfs)
    for c in rows(F["fbrf_map"]):
        if c and c[0] in want:
            refmap[c[0]] = {"pmid": c[1] if len(c) > 1 else "", "pmcid": c[2] if len(c) > 2 else "",
                            "doi": c[3] if len(c) > 3 else "", "cite": c[5] if len(c) > 5 else ""}

    # 6. atlas coverage (from bundle's own provenance: it records totals, not the exact 19 used)
    atlas_bullets = n_total = n_used = 0
    ab = GENES / f"{fbgn}.json"
    if ab.exists():
        bj = json.loads(ab.read_text())
        atlas_bullets = len(bj.get("bullets", []))
        src = bj.get("source", {})
        n_total = src.get("n_pubs_total") or 0
        n_used = src.get("n_abstracts_used") or 0
    # publications with a local PMID/PMCID (the ones full-text is reachable for), newest first
    with_id = [{"fbrf": rf, **refmap[rf]} for rf in fbrfs if refmap.get(rf) and (refmap[rf].get("pmid") or refmap[rf].get("pmcid"))]
    with_id.sort(key=lambda p: p["fbrf"], reverse=True)
    n_no_id = len(fbrfs) - len(with_id)

    return {"fbgn": fbgn, "symbol": symbol, "snapshot": snap, "best_summary": best,
            "alleles": alleles, "genotype_phenotype": gp, "genetic_interactions": gint,
            "n_pubs": len(fbrfs), "atlas_bullets": atlas_bullets, "atlas_n_total": n_total, "atlas_n_used": n_used,
            "pubs_with_id": with_id, "n_pubs_no_id": n_no_id}


def render(d: dict):
    print(f"# Deep dossier — {d['symbol']} ({d['fbgn']})  [local FlyBase bulk, no internet]\n")
    gap = (d["atlas_n_total"] or d["n_pubs"]) - (d["atlas_n_used"] or 0)
    print(f"**Atlas coverage gap:** atlas distilled **{d['atlas_bullets']} bullets** from "
          f"**{d['atlas_n_used']}/{d['atlas_n_total'] or d['n_pubs']}** publications "
          f"→ ~**{gap} publications were not distilled.** This dossier adds the raw "
          f"genotype-phenotype / allele / interaction layers below, plus PMIDs for full text.\n")
    if d["snapshot"] and d["snapshot"] not in ("-", "Contributions welcome."):
        print(f"## FlyBase gene snapshot\n{d['snapshot']}\n")
    if d["best_summary"]:
        print(f"## Best gene summary\n{d['best_summary'][:1200]}\n")
    print(f"## Alleles ({len(d['alleles'])})")
    for a in d["alleles"]:
        print(f"- **{a['allele']}** ({a['fbal']}){' — '+a['class'] if a['class'] else ''}: {a['desc'][:240]}")
    print(f"\n## Genotype → phenotype records ({len(d['genotype_phenotype'])})  *(atlas compressed these into bullets)*")
    for g in d["genotype_phenotype"]:
        st = f" [{g['stage']}]" if g["stage"] else ""
        print(f"- {g['genotype']} → **{g['phenotype']}**{st}  <{g['fbrf']}>")
    print(f"\n## Genetic interactions ({len(d['genetic_interactions'])})  *(absent from atlas)*")
    for gi in d["genetic_interactions"]:
        print(f"- {gi['gene']} — {gi['type']} — {gi['interactor']}  <{gi['fbrf']}>")
    print(f"\n## Publications with retrievable full text ({len(d['pubs_with_id'])} have PMID/PMCID; "
          f"{d['n_pubs_no_id']} older refs lack one) — newest first")
    for p in d["pubs_with_id"]:
        ids = " ".join(x for x in [f"PMID:{p['pmid']}" if p.get("pmid") else "",
                                   p.get("pmcid", ""), f"doi:{p['doi']}" if p.get("doi") else ""] if x)
        print(f"- {p.get('cite') or p['fbrf']}  [{ids}]")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("gene")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    fbgn, symbol = resolve_fbgn(a.gene)
    d = collect(fbgn, symbol)
    if a.json:
        print(json.dumps(d, ensure_ascii=False, indent=1))
    else:
        render(d)


if __name__ == "__main__":
    main()
