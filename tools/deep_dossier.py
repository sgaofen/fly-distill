#!/usr/bin/env python3
"""deep_dossier.py — pull the full local FlyBase bulk record for one gene.

The distilled atlas is a lossy first-pass (e.g. Svip = 19 bullets from 39 pubs,
no interaction layer). This tool reads the raw local bulk so an agent can move a
top candidate from "atlas triage" to "evidence-grounded verdict" WITHOUT going
online. Full article text still needs the PMIDs listed at the end.

Usage:
  python3 deep_dossier.py Svip
  python3 deep_dossier.py ebony          # full common names resolve too
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
CACHE = ROOT / "data" / "gene_cache"   # pre-built per-gene JSON (build_gene_cache.py); fast path

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
FBAL = re.compile(r"FBal\d+")  # genotypes use space AND '/' (homozygotes) — extract by regex
FBDV = re.compile(r"FBdv:(\d+)|(?<![:\d])(\d{8})(?![\d])")  # FBdv:NNN or a bare 8-digit stage id
MITAB_SYM = re.compile(r"flybase:([^|()]+)\(gene name\)")


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
    r = db.execute(
        "SELECT g.fbgn, g.symbol FROM genes g JOIN synonyms s ON s.fbgn=g.fbgn "
        "WHERE s.synonym=? COLLATE NOCASE", (token,)).fetchone()
    if r:
        return r[0], r[1]
    # fallback: full common names (e.g. "ebony") open the best_gene_summary as "<name> (<symbol>) ..."
    pat = re.compile(r"^\s*" + re.escape(token) + r"\s*\(", re.I)
    for c in rows(F["best_sum"]):
        if len(c) > 3 and pat.match(c[3]):
            sys.stderr.write(f"[resolved '{token}' -> {c[1]} ({c[0]}) via gene-name summary]\n")
            return c[0], c[1]
    sys.exit(f"Could not resolve '{token}' to an FBgn (try the gene symbol or FBgn id).")


def _stage(cells):
    for x in cells:
        m = FBDV.search(x)
        if m:
            return m.group(1) or m.group(2)
    return ""


def _allele_desc(cells):
    """Description is a long free-text column (col ~18), NOT the last cell (stock count)."""
    cands = [x for x in cells[4:] if x and " " in x and len(x) > 15
             and not x.startswith(("FB", "GO:")) and not x.isdigit()]
    return max(cands, key=len) if cands else ""


def _mitab_partner(cell):
    m = MITAB_SYM.search(cell or "")
    return m.group(1) if m else ""


def collect(fbgn: str, symbol: str) -> dict:
    # gene's complete FBal set (precise key for everything allele-based)
    fbals = set()
    alleles = []
    for c in rows(F["allele_desc"]):
        if len(c) > 3 and c[3] == fbgn:
            fbals.add(c[1])
            alleles.append({"allele": c[0], "fbal": c[1], "class": c[4] if len(c) > 4 else "",
                            "desc": _allele_desc(c)})
    for c in rows(F["fbal2fbgn"]):
        if len(c) > 2 and c[2] == fbgn:
            fbals.add(c[0])

    # genotype -> phenotype: match ONLY by FBal-set intersection (no symbol substring — avoids
    # the 'e' explosion and driver/promoter contamination like Tk.PS / Cyp6g1.HR)
    gp = []
    for c in rows(F["geno_pheno"]):
        if len(c) < 3:
            continue
        if not (set(FBAL.findall(c[1])) & fbals):
            continue
        rf = next((m.group() for x in c for m in [FBRF.search(x)] if m), "")
        gp.append({"genotype": c[0], "phenotype": c[2], "stage": _stage(c), "fbrf": rf})

    # genetic interactions — split BOTH sides on '|' (gene clusters appear on the start side too)
    gint = []
    for c in rows(F["gen_int"]):
        if len(c) < 6:
            continue
        if fbgn in c[1].split("|") or fbgn in c[3].split("|"):
            gint.append({"gene": c[0], "interactor": c[2], "type": c[4], "fbrf": c[5]})

    # physical interactions (mitab) — previously defined but never parsed
    pint = []
    tag = "flybase:" + fbgn
    for c in rows(F["phys_int"]):
        if len(c) < 7:
            continue
        if tag in c[0] or tag in c[1]:
            partner = _mitab_partner(c[5]) if tag in c[0] else _mitab_partner(c[4])
            method = (c[6].split('(')[-1].rstrip(')') if len(c) > 6 else "")
            if partner and partner != symbol:
                pint.append({"partner": partner, "method": method})
    seen = set(); pint = [p for p in pint if not (p["partner"] in seen or seen.add(p["partner"]))]

    snap = best = ""
    for c in rows(F["snapshot"]):
        if c and c[0] == fbgn:
            snap = c[-1]; break
    for c in rows(F["best_sum"]):
        if c and c[0] == fbgn:
            best = c[-1]; break

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

    atlas_bullets = n_total = n_used = 0
    ab = GENES / f"{fbgn}.json"
    if ab.exists():
        bj = json.loads(ab.read_text())
        atlas_bullets = len(bj.get("bullets", []))
        src = bj.get("source", {})
        n_total = src.get("n_pubs_total") or 0
        n_used = src.get("n_abstracts_used") or 0
    with_id = [{"fbrf": rf, **refmap[rf]} for rf in fbrfs
               if refmap.get(rf) and (refmap[rf].get("pmid") or refmap[rf].get("pmcid"))]
    with_id.sort(key=lambda p: p["fbrf"], reverse=True)

    return {"fbgn": fbgn, "symbol": symbol, "snapshot": snap, "best_summary": best,
            "alleles": alleles, "genotype_phenotype": gp, "genetic_interactions": gint,
            "physical_interactions": pint, "n_pubs": len(fbrfs), "atlas_bullets": atlas_bullets,
            "atlas_n_total": n_total, "atlas_n_used": n_used,
            "pubs_with_id": with_id, "n_pubs_no_id": len(fbrfs) - len(with_id)}


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
        cls = f" — {a['class']}" if a["class"] else ""
        print(f"- **{a['allele']}** ({a['fbal']}){cls}: {a['desc'][:240] or '(no description)'}")
    print(f"\n## Genotype → phenotype records ({len(d['genotype_phenotype'])})  *(atlas compressed these into bullets)*")
    for g in d["genotype_phenotype"]:
        st = f" [{g['stage']}]" if g["stage"] else ""
        print(f"- {g['genotype']} → **{g['phenotype']}**{st}  <{g['fbrf']}>")
    print(f"\n## Genetic interactions ({len(d['genetic_interactions'])})  *(absent from atlas)*")
    for gi in d["genetic_interactions"]:
        print(f"- {gi['gene']} — {gi['type']} — {gi['interactor']}  <{gi['fbrf']}>")
    print(f"\n## Physical interactions ({len(d['physical_interactions'])})  *(absent from atlas)*")
    for p in d["physical_interactions"]:
        print(f"- {p['partner']}" + (f"  ({p['method']})" if p["method"] else ""))
    print(f"\n## Publications with retrievable full text ({len(d['pubs_with_id'])} have PMID/PMCID; "
          f"{d['n_pubs_no_id']} older refs lack one) — newest first")
    for p in d["pubs_with_id"]:
        ids = " ".join(x for x in [f"PMID:{p['pmid']}" if p.get("pmid") else "",
                                   p.get("pmcid", ""), f"doi:{p['doi']}" if p.get("doi") else ""] if x)
        print(f"- {p.get('cite') or p['fbrf']}  [{ids}]")


def _atlas_gap(fbgn):
    ab = GENES / f"{fbgn}.json"
    if not ab.exists():
        return None
    bj = json.loads(ab.read_text()); src = bj.get("source", {})
    return {"bullets": len(bj.get("bullets", [])),
            "n_used": src.get("n_abstracts_used") or 0, "n_total": src.get("n_pubs_total") or 0}


def render_cache(d):
    """Render from a pre-built cache doc (build_gene_cache.py) — adds name/synonyms,
    expression, GO, and cross-species layers the gzip-scan path doesn't carry."""
    print(f"# Deep dossier — {d['symbol']} ({d['fbgn']})  [cached; local FlyBase bulk, no internet]\n")
    if d.get("fullname"):
        print(f"**{d['fullname']}**" + (f"  ·  syn: {', '.join(d['synonyms'][:8])}" if d.get("synonyms") else "") + "\n")
    g = _atlas_gap(d["fbgn"])
    if g:
        gap = (g["n_total"] or d["n_pubs"]) - g["n_used"]
        print(f"**Atlas coverage gap:** distilled {g['bullets']} bullets from {g['n_used']}/{g['n_total'] or d['n_pubs']} pubs → ~{gap} not distilled.\n")
    if d.get("snapshot"):
        print(f"## FlyBase gene snapshot\n{d['snapshot']}\n")
    elif d.get("best_summary"):
        print(f"## Best gene summary\n{d['best_summary'][:1000]}\n")
    print(f"## Cross-species\n- human: " + (", ".join(f"{o['human']}(DIOPT {o['diopt']}){' — '+o['disease'] if o.get('disease') else ''}" for o in d.get("human_orthologs", [])[:6]) or "—"))
    print(f"- mouse: " + (", ".join(f"{o['mouse']}(DIOPT {o['diopt']})" for o in d.get("mouse_orthologs", [])[:6]) or "—") + "\n")
    print(f"## Alleles ({len(d['alleles'])})")
    for a in d["alleles"]:
        cls = f" — {a['class']}" if a.get("class") else ""
        print(f"- **{a['allele']}** ({a['fbal']}){cls}: {a['desc'][:240] or '(no description)'}")
    print(f"\n## Genotype → phenotype records ({len(d['genotype_phenotype'])})")
    for r in d["genotype_phenotype"]:
        st = f" [{r['stage']}]" if r.get("stage") else ""
        print(f"- {r['genotype']} → **{r['phenotype']}**{st}  <{r.get('fbrf','')}>")
    print(f"\n## Genetic interactions ({len(d['genetic_interactions'])})")
    for gi in d["genetic_interactions"]:
        print(f"- {gi['gene']} — {gi['type']} — {gi['interactor']}  <{gi['fbrf']}>")
    print(f"\n## Physical interactions ({len(d['physical_interactions'])})")
    for p in d["physical_interactions"]:
        print(f"- {p['partner']}" + (f"  ({p['method']})" if p.get("method") else ""))
    print(f"\n## GO ({len(d['go'])}) — experimental (non-IEA) first")
    for go in sorted(d["go"], key=lambda x: x["evidence"] == "IEA"):
        print(f"- [{go['aspect']}] {go['qualifier']} {go['go_id']}  ({go['evidence']}; {go['ref']})")
    print(f"\n## Top expression (RPKM, tissue/stage)")
    print("  " + ", ".join(f"{x['sample']}={x['rpkm']}" for x in d.get("expression_top", [])[:12]))
    print(f"\n## Publications with PMID ({len(d['pubs'])} of {d['n_pubs']}) — newest first")
    for p in d["pubs"]:
        ids = " ".join(x for x in [f"PMID:{p['pmid']}" if p.get("pmid") else "", p.get("pmcid", "")] if x)
        print(f"- {p.get('cite') or p['fbrf']}  [{ids}]")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("gene")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--no-cache", action="store_true", help="force live gzip scan instead of the prebuilt cache")
    a = ap.parse_args()
    fbgn, symbol = resolve_fbgn(a.gene)
    cf = CACHE / f"{fbgn}.json"
    if cf.exists() and not a.no_cache:
        d = json.loads(cf.read_text())
        if a.json:
            print(json.dumps(d, ensure_ascii=False, indent=1))
        else:
            render_cache(d)
        return
    d = collect(fbgn, symbol)
    if a.json:
        print(json.dumps(d, ensure_ascii=False, indent=1))
    else:
        render(d)


if __name__ == "__main__":
    main()
