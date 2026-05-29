#!/usr/bin/env python3
"""build_gene_cache.py — assemble ALL local FlyBase bulk files into one JSON per gene.

The per-gene agent / deep_dossier was re-scanning 7+ gzipped TSVs on every call.
This pre-builds data/gene_cache/<FBgn>.json once (one streaming pass per file, not
14k passes), so per-gene lookup becomes a single file read. Adds three layers the
atlas never had: full name + synonyms (fb_synonym), tissue/stage expression
(gene_rpkm_report), and GO with evidence codes + PMIDs (gene_association.fb).

Deterministic — no LLM. Run after download_flybase_bulk.py.
"""
from __future__ import annotations
import gzip, json, re, sqlite3, sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BULK = ROOT / "data" / "flybase_bulk"
DB = ROOT / "tools" / "atlas.db"
OUT = ROOT / "data" / "gene_cache"
RPKM_TOP = 15
FBRF = re.compile(r"FBrf\d{7}")
FBAL = re.compile(r"FBal\d+")
FBDV = re.compile(r"FBdv:(\d+)|(?<![:\d])(\d{8})(?![\d])")
MITAB_SYM = re.compile(r"flybase:([^|()]+)\(gene name\)")


def rows(name, sub=None):
    p = (BULK / sub / name) if sub else BULK / name
    matches = list(p.parent.glob(p.name))
    if not matches:
        return
    with gzip.open(matches[0], "rt", errors="replace") as fh:
        for line in fh:
            if line.startswith(("#", "!")) or not line.strip():
                continue
            yield line.rstrip("\n").split("\t")


def f(stem, sub):
    g = list((BULK / sub).glob(f"{stem}_*.tsv.gz"))
    return g[0].name if g else None


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB); db.row_factory = sqlite3.Row
    genes = {r["fbgn"]: r["symbol"] for r in db.execute("SELECT fbgn, symbol FROM genes")}
    print(f"{len(genes)} genes in atlas")

    acc = defaultdict(lambda: defaultdict(list))   # fbgn -> field -> [rows]
    scalar = defaultdict(dict)                       # fbgn -> {name, snapshot, ...}

    # FBal -> FBgn (for genotype_phenotype keying)
    fbal2fbgn = {}
    for c in rows(f("fbal_to_fbgn", "alleles"), "alleles"):
        if len(c) > 2:
            fbal2fbgn[c[0]] = c[2]
    print(f"{len(fbal2fbgn)} allele->gene maps")

    # fb_synonym: name + synonyms
    for c in rows(f("fb_synonym", "synonyms"), "synonyms"):
        if len(c) > 3 and c[0] in genes:
            syn = []
            if len(c) > 4 and c[4]: syn += c[4].split("|")
            if len(c) > 5 and c[5]: syn += c[5].split("|")
            scalar[c[0]]["fullname"] = c[3]
            scalar[c[0]]["synonyms"] = [s for s in syn if s][:25]

    for c in rows(f("gene_snapshots", "genes"), "genes"):
        if c[0] in genes and len(c) > 4 and c[-1] not in ("-", "Contributions welcome."):
            scalar[c[0]]["snapshot"] = c[-1]
    for c in rows(f("best_gene_summary", "genes"), "genes"):
        if c[0] in genes and len(c) > 3:
            scalar[c[0]]["best_summary"] = c[-1]
    for c in rows(f("automated_gene_summaries", "genes"), "genes"):
        if c[0] in genes and len(c) > 1:
            scalar[c[0]]["auto_summary"] = c[-1]

    # alleles
    for c in rows(f("dmel_classical_and_insertion_allele_descriptions", "alleles"), "alleles"):
        if len(c) > 3 and c[3] in genes:
            cand = [x for x in c[4:] if x and " " in x and len(x) > 15
                    and not x.startswith(("FB", "GO:")) and not x.isdigit()]
            acc[c[3]]["alleles"].append({"allele": c[0], "fbal": c[1],
                "class": c[4] if len(c) > 4 else "", "desc": max(cand, key=len) if cand else ""})

    # genotype -> phenotype (key by FBal -> FBgn)
    for c in rows(f("genotype_phenotype_data", "alleles"), "alleles"):
        if len(c) < 3:
            continue
        hit = {fbal2fbgn[x] for x in FBAL.findall(c[1]) if x in fbal2fbgn}
        if not hit:
            continue
        st = ""
        for x in c:
            m = FBDV.search(x)
            if m: st = m.group(1) or m.group(2); break
        rf = next((m.group() for x in c for m in [FBRF.search(x)] if m), "")
        rec = {"genotype": c[0], "phenotype": c[2], "stage": st, "fbrf": rf}
        for g in hit:
            if g in genes:
                acc[g]["genotype_phenotype"].append(rec)

    for c in rows(f("gene_genetic_interactions", "genes"), "genes"):
        if len(c) < 6:
            continue
        for g in set(c[1].split("|")) | set(c[3].split("|")):
            if g in genes:
                acc[g]["genetic_interactions"].append(
                    {"gene": c[0], "interactor": c[2], "type": c[4], "fbrf": c[5]})

    for c in rows(f("physical_interactions_mitab", "genes"), "genes"):
        if len(c) < 7:
            continue
        a = c[0].replace("flybase:", "") if c[0].startswith("flybase:") else ""
        b = c[1].replace("flybase:", "") if c[1].startswith("flybase:") else ""
        for g, partner_cell in ((a, c[5]), (b, c[4])):
            if g in genes:
                m = MITAB_SYM.search(partner_cell or "")
                if m and m.group(1) != genes[g]:
                    acc[g]["physical_interactions"].append(
                        {"partner": m.group(1), "method": c[6].split('(')[-1].rstrip(')')})

    # GO with evidence + PMID
    for c in rows("gene_association.fb.gz", "go"):
        if len(c) > 8 and c[1] in genes:
            acc[c[1]]["go"].append({"aspect": c[8], "qualifier": c[3], "go_id": c[4],
                                    "evidence": c[6], "ref": c[5]})

    # expression: keep top RPKM samples
    for c in rows(f("gene_rpkm_report", "genes"), "genes"):
        if len(c) > 7 and c[1] in genes:
            try:
                acc[c[1]]["rpkm"].append({"sample": c[6], "rpkm": int(c[7])})
            except ValueError:
                pass

    # human orthologs + disease
    # cols: 0 FBgn | 1 sym | 2 HGNC | 3 OMIM-gene | 4 human symbol | 5 DIOPT | 6 OMIM-pheno-IDs | 7 pheno names
    for c in rows(f("dmel_human_orthologs_disease", "orthologs"), "orthologs"):
        if c and c[0] in genes and len(c) > 5:
            acc[c[0]]["human_orthologs"].append({"human": c[4], "diopt": c[5],
                "disease": c[7] if len(c) > 7 else ""})

    # publications + PMID map
    for c in rows(f("entity_publication", "references"), "references"):
        if c and c[0] in genes and len(c) > 2 and c[2].startswith("FBrf"):
            acc[c[0]]["fbrfs"].append(c[2])
    fbrfmap = {}
    for c in rows(f("fbrf_pmid_pmcid_doi", "references"), "references"):
        if c and len(c) > 1 and c[1]:
            fbrfmap[c[0]] = {"pmid": c[1], "pmcid": c[2] if len(c) > 2 else "",
                             "cite": c[5] if len(c) > 5 else ""}

    # mouse orthologs from atlas.db (not in FlyBase bulk)
    mouse = defaultdict(list)
    for r in db.execute("SELECT fbgn, symbol, diopt_score FROM orthologs WHERE species='mouse'"):
        mouse[r["fbgn"]].append({"mouse": r["symbol"], "diopt": r["diopt_score"]})

    n = 0
    for fbgn, sym in genes.items():
        a = acc.get(fbgn, {})
        rpkm = sorted(a.get("rpkm", []), key=lambda x: -x["rpkm"])[:RPKM_TOP]
        fbrfs = list(dict.fromkeys(a.get("fbrfs", [])))
        pubs = [{"fbrf": rf, **fbrfmap[rf]} for rf in fbrfs if rf in fbrfmap]
        pubs.sort(key=lambda p: p["fbrf"], reverse=True)
        doc = {
            "fbgn": fbgn, "symbol": sym,
            "fullname": scalar[fbgn].get("fullname", ""),
            "synonyms": scalar[fbgn].get("synonyms", []),
            "snapshot": scalar[fbgn].get("snapshot", ""),
            "best_summary": scalar[fbgn].get("best_summary", ""),
            "auto_summary": scalar[fbgn].get("auto_summary", ""),
            "alleles": a.get("alleles", []),
            "genotype_phenotype": a.get("genotype_phenotype", []),
            "genetic_interactions": a.get("genetic_interactions", []),
            "physical_interactions": list({p["partner"]: p for p in a.get("physical_interactions", [])}.values()),
            "go": a.get("go", []),
            "expression_top": rpkm,
            "human_orthologs": a.get("human_orthologs", []),
            "mouse_orthologs": mouse.get(fbgn, []),
            "n_pubs": len(fbrfs), "pubs": pubs,
        }
        (OUT / f"{fbgn}.json").write_text(json.dumps(doc, ensure_ascii=False))
        n += 1
        if n % 2000 == 0:
            print(f"  {n}/{len(genes)} written")
    print(f"wrote {n} per-gene cache files -> {OUT}")


if __name__ == "__main__":
    main()
