"""Bulk-only fetcher: builds a bundle.json for one gene using ONLY:
  - in-memory BulkIndex (all 17 FlyBase TSVs + Alliance ortholog file)
  - NCBI E-utilities efetch (PubMed abstracts — completely separate infra from FlyBase WAF)
  - MyGene.info (optional NCBI gene summaries for orthologs — also separate infra)

Replaces fetch_gene.py which hit FlyBase HTML + API per-gene and got WAF'd.

Output schema is the same as fetch_gene.py's bundle.json — distill.py + pipeline.py
need no changes.

Usage:
  python3 src/fetch_gene_v2.py FBgn0003068
"""
import json
import os
import subprocess
import sys
import time
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from bulk_index import get_bulk
from pubmed_fetcher import fetch_abstracts

ROOT = Path(__file__).resolve().parents[1]

MAX_REFS = 20
MAX_ORTHO_PER_SPECIES = 3
MYGENE_API = "https://mygene.info/v3"
MAX_PHENOTYPE_ROWS = 200
MAX_ALLELE_DESCS = 60
MAX_DISEASE_MODELS = 40
MAX_INTERACTIONS = 60


def _curl(url: str, timeout: int = 30) -> bytes:
    r = subprocess.run(
        ["/usr/bin/curl", "-sL", "--max-time", str(timeout), url],
        capture_output=True, check=False,
    )
    return r.stdout


# ---------- Section synthesis from bulk rows ----------

def render_phenotypes(rows: list) -> str:
    if not rows:
        return ""
    seen = set()
    lines = []
    for r in rows[:MAX_PHENOTYPE_ROWS * 2]:
        key = (r.get("phenotype"), r.get("qualifier"), r.get("genotype"))
        if key in seen:
            continue
        seen.add(key)
        phen = r.get("phenotype") or ""
        qual = r.get("qualifier") or ""
        gen = r.get("genotype") or ""
        ref = r.get("ref") or ""
        bits = [phen]
        if qual:
            bits.append(f"({qual})")
        if gen:
            bits.append(f"[{gen}]")
        if ref:
            bits.append(f"<{ref}>")
        lines.append("  • " + " ".join(bits))
        if len(lines) >= MAX_PHENOTYPE_ROWS:
            break
    return "\n".join(lines)


def render_alleles(rows: list) -> str:
    if not rows:
        return ""
    lines = []
    for r in rows[:MAX_ALLELE_DESCS]:
        a = r.get("allele", "")
        d = r.get("description", "")
        ref = r.get("ref", "")
        if not d:
            continue
        line = f"  • {a}: {d}"
        if ref:
            line += f" <{ref}>"
        lines.append(line)
    return "\n".join(lines)


def render_disease_models(rows: list, ortho_disease: list) -> str:
    parts = []
    if ortho_disease:
        parts.append("HUMAN ORTHOLOG OMIM LINKS (FlyBase curated):")
        for o in ortho_disease[:10]:
            sym = o.get("human_symbol", "?")
            hgnc = o.get("hgnc", "")
            mim = o.get("mim", "")
            diopt = o.get("diopt_score") or "?"
            head = f"  • {sym} (HGNC:{hgnc}, MIM {mim}, DIOPT {diopt})"
            phens = o.get("omim_phenotypes") or []
            if phens:
                phen_strs = [f"OMIM {p['omim_id']}={p['name']}" for p in phens[:5]]
                head += " — " + "; ".join(phen_strs)
            parts.append(head)
    if rows:
        parts.append("\nDISEASE MODEL ANNOTATIONS (DO):")
        seen = set()
        for r in rows[:MAX_DISEASE_MODELS]:
            do_term = r.get("do_term", "")
            qual = r.get("do_qualifier", "")
            allele = r.get("allele", "")
            orth = r.get("ortholog_symbol", "")
            evidence = r.get("evidence", "")
            ref = r.get("ref", "")
            key = (do_term, qual, allele, orth, evidence)
            if key in seen:
                continue
            seen.add(key)
            line = f"  • {do_term} ({qual or 'model of'})"
            if allele:
                line += f" via allele {allele}"
            if orth:
                line += f" [ortholog: {orth}]"
            if evidence:
                line += f" — {evidence}"
            if ref:
                line += f" <{ref}>"
            parts.append(line)
    return "\n".join(parts)


def render_genetic_interactions(rows: list, bulk) -> str:
    if not rows:
        return ""
    # Group by partner + type
    grouped = {}
    for r in rows:
        partner = r.get("partner_symbol", "")
        ix_type = r.get("type", "")
        key = (partner, ix_type)
        grouped.setdefault(key, []).append(r.get("ref", ""))
    lines = []
    for (partner, ix_type), refs in sorted(grouped.items(), key=lambda kv: -len(kv[1]))[:MAX_INTERACTIONS]:
        n = len(refs)
        sample = refs[0] if refs else ""
        line = f"  • {partner} — {ix_type}"
        if n > 1:
            line += f" ({n}×)"
        if sample:
            line += f" <{sample}>"
        lines.append(line)
    return "\n".join(lines)


def render_physical_interactions(rows: list, bulk) -> str:
    if not rows:
        return ""
    grouped = {}
    for r in rows:
        partner = r.get("partner_fbgn", "")
        assay = r.get("assay", "")
        ref = r.get("ref", "")
        grouped.setdefault(partner, []).append((assay, ref))
    lines = []
    for partner, evidence in sorted(grouped.items(), key=lambda kv: -len(kv[1]))[:MAX_INTERACTIONS]:
        sym = bulk.symbols.get(partner, partner)
        assays = sorted({e[0] for e in evidence if e[0]})
        assay_str = "; ".join(assays[:3])
        n = len(evidence)
        line = f"  • {sym} ({partner})"
        if assay_str:
            line += f" — {assay_str}"
        if n > 1:
            line += f" ({n} evidence rows)"
        lines.append(line)
    return "\n".join(lines)


# ---------- Ortholog enrichment ----------

def mygene_summary(symbol: str, species: str) -> dict:
    """Look up NCBI gene summary by symbol → entrez_id → fields."""
    try:
        q = urllib.parse.quote(f"symbol:{symbol}")
        url = f"{MYGENE_API}/query?q={q}&species={species}&fields=entrezgene&size=1"
        d = json.loads(_curl(url, timeout=15))
        hits = d.get("hits", [])
        if not hits:
            return {}
        ent = hits[0].get("entrezgene")
        if not ent:
            return {}
        url2 = f"{MYGENE_API}/gene/{ent}?fields=symbol,name,summary,alias"
        d2 = json.loads(_curl(url2, timeout=15))
        return {
            "entrez_id": str(ent),
            "name": d2.get("name") or "",
            "summary": d2.get("summary") or "",
            "alias": d2.get("alias") or [],
        }
    except Exception as e:
        return {"_error": str(e)}


def select_human_orthologs(fbgn: str, bulk) -> list:
    """Merge orthologs_disease (DIOPT + OMIM) + Alliance human_orthologs by symbol."""
    by_sym = {}
    # Primary: orthologs_disease — has DIOPT + HGNC + OMIM
    for o in bulk.orthologs_disease.get(fbgn, []):
        sym = o.get("human_symbol")
        if not sym:
            continue
        by_sym[sym] = {
            "symbol": sym,
            "hgnc": o.get("hgnc", ""),
            "mim": o.get("mim", ""),
            "diopt_score": o.get("diopt_score"),
            "diopt_max": None,
            "omim_phenotypes": o.get("omim_phenotypes", []),
            "source": "flybase_orthologs_disease",
        }
    # Augment: Alliance human_orthologs (may have diopt_max where flybase doesn't)
    for o in bulk.human_orthologs.get(fbgn, []):
        sym = o.get("symbol")
        if not sym:
            continue
        existing = by_sym.get(sym)
        alliance_entry = {
            "symbol": sym,
            "hgnc": (o.get("external_id") or "").replace("HGNC:", "") if o.get("external_id", "").startswith("HGNC:") else "",
            "mim": "",
            "diopt_score": o.get("diopt_score"),
            "diopt_max": o.get("diopt_max"),
            "omim_phenotypes": [],
            "source": "alliance",
        }
        if existing:
            existing["diopt_max"] = alliance_entry["diopt_max"] or existing.get("diopt_max")
            existing["source"] = "flybase+alliance"
        else:
            by_sym[sym] = alliance_entry
    ranked = sorted(
        by_sym.values(),
        key=lambda r: (-(r.get("diopt_score") or 0), r["symbol"]),
    )
    return ranked


def select_mouse_orthologs(fbgn: str, bulk) -> list:
    """Mouse — only Alliance (FlyBase orthologs_disease is human-only)."""
    out = []
    for o in bulk.mouse_orthologs.get(fbgn, []):
        sym = o.get("symbol")
        if not sym:
            continue
        out.append({
            "symbol": sym,
            "mgi": (o.get("external_id") or "").replace("MGI:", "") if o.get("external_id", "").startswith("MGI:") else "",
            "diopt_score": o.get("diopt_score"),
            "diopt_max": o.get("diopt_max"),
            "source": "alliance",
        })
    out.sort(key=lambda r: (-(r.get("diopt_score") or 0), r["symbol"]))
    return out


# ---------- Reference selection ----------

def select_refs(fbgn: str, bulk, limit: int = MAX_REFS) -> list:
    """Use FlyBase rep_pubs (curator-picked) first; fall back to all gene_pubs sorted by year."""
    rep = bulk.rep_pubs.get(fbgn, [])
    all_pubs = bulk.gene_pubs.get(fbgn, [])  # list of (fbrf, pmid)
    fbrf_to_pmid_local = {fbrf: pmid for fbrf, pmid in all_pubs}

    def meta(fbrf):
        m = bulk.fbrf_meta.get(fbrf, {})
        return {
            "id": fbrf,
            "year": m.get("year"),
            "type": m.get("pub_type", ""),
            "miniref": m.get("miniref", ""),
            "pmid": fbrf_to_pmid_local.get(fbrf) or bulk.fbrf_to_pmid.get(fbrf, "") or "",
            "doi": m.get("doi", ""),
        }

    rep_meta = [meta(r) for r in rep]
    # Sort rep_meta by year desc, but keep the curator-ordered as tiebreak
    rep_meta.sort(key=lambda r: -(r["year"] or 0))

    if len(rep_meta) >= limit:
        return rep_meta[:limit]

    # Need more: pull recent paper-type pubs not already in rep
    have = {r["id"] for r in rep_meta}
    extra = [meta(fbrf) for fbrf, _ in all_pubs if fbrf not in have]
    extra = [e for e in extra if e["year"]]
    extra.sort(key=lambda e: -e["year"])
    return (rep_meta + extra)[:limit]


# ---------- Main bundle build ----------

def build_bundle(fbgn: str, cache_dir: Path, enable_mygene: bool = True) -> dict:
    cache_dir.mkdir(parents=True, exist_ok=True)
    bulk = get_bulk()

    bundle = {
        "fbgn": fbgn,
        "symbol": bulk.symbols.get(fbgn, ""),
        "synonyms": bulk.synonyms.get(fbgn, []),
        "fetched_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "bulk_source": {
            "flybase_release": "fb_2026_01",
            "alliance": "ORTHOLOGY-ALLIANCE_COMBINED",
            "harvest_method": "bulk_tsv_in_memory_v2",
        },
    }

    print(f"  [1/5] bulk lookup ({bundle['symbol']})", flush=True)
    bundle["auto_summary"] = bulk.summaries.get(fbgn, "")
    bundle["go"] = {}  # not loaded from bulk; intentional empty for distill prompt

    # Synthesize the sections dict (matches fetch_gene.py keys so distill.py is unchanged)
    phen_rows = bulk.phenotypes_by_gene.get(fbgn, [])
    allele_rows = bulk.allele_descriptions_by_gene.get(fbgn, [])
    disease_rows = bulk.disease_models.get(fbgn, [])
    ortho_disease = bulk.orthologs_disease.get(fbgn, [])
    gx_rows = bulk.genetic_interactions.get(fbgn, [])
    px_rows = bulk.physical_interactions.get(fbgn, [])
    snapshot = bulk.snapshots.get(fbgn, "")

    bundle["sections"] = {
        "function": "",  # covered by auto_summary
        "phenotypes_sub": render_phenotypes(phen_rows),
        "alleles_main_sub": render_alleles(allele_rows),
        "hdm_sub": render_disease_models(disease_rows, ortho_disease),
        "other_comments_sub": snapshot,
        "summary_genetic_interactions_sub": render_genetic_interactions(gx_rows, bulk),
        "summary_physical_interactions_sub": render_physical_interactions(px_rows, bulk),
        "pathways_sub": "",
        "gene_class_sub": "",
    }

    print(f"  [2/5] ortholog selection", flush=True)
    h_orthos = select_human_orthologs(fbgn, bulk)[:MAX_ORTHO_PER_SPECIES]
    m_orthos = select_mouse_orthologs(fbgn, bulk)[:MAX_ORTHO_PER_SPECIES]
    bundle["top_human_orthologs"] = h_orthos
    bundle["top_mouse_orthologs"] = m_orthos

    print(f"  [3/5] reference selection", flush=True)
    refs = select_refs(fbgn, bulk)
    bundle["refs_selected"] = refs
    bundle["pubs_total"] = len(bulk.gene_pubs.get(fbgn, []))

    print(f"  [4/5] PubMed abstracts ({sum(1 for r in refs if r['pmid'])} of {len(refs)} refs have PMID)", flush=True)
    pmids = [r["pmid"] for r in refs if r.get("pmid")]
    pmid_to_abs = fetch_abstracts(pmids) if pmids else {}
    abstracts = []
    for r in refs:
        rec = pmid_to_abs.get(r["pmid"], {}) if r.get("pmid") else {}
        abstracts.append({
            "fbrf": r["id"],
            "pmid": r.get("pmid", ""),
            "year": r.get("year") or rec.get("year"),
            "type": r.get("type", ""),
            "title": rec.get("title", "") or r.get("miniref", ""),
            "miniref": r.get("miniref", ""),
            "abstract": rec.get("abstract", ""),
        })
    bundle["abstracts"] = abstracts

    print(f"  [5/5] mygene ortholog enrichment ({'on' if enable_mygene else 'off'})", flush=True)
    bundle["human_ortholog_data"] = []
    for o in h_orthos:
        merged = dict(o)
        if enable_mygene:
            info = mygene_summary(o["symbol"], "human")
            merged.update({k: v for k, v in info.items() if k != "_error"})
        bundle["human_ortholog_data"].append(merged)
    bundle["mouse_ortholog_data"] = []
    for o in m_orthos:
        merged = dict(o)
        if enable_mygene:
            info = mygene_summary(o["symbol"], "mouse")
            merged.update({k: v for k, v in info.items() if k != "_error"})
        bundle["mouse_ortholog_data"].append(merged)

    out_path = cache_dir / "bundle.json"
    tmp = out_path.with_suffix(".tmp")
    tmp.write_text(json.dumps(bundle, indent=2, ensure_ascii=False))
    tmp.rename(out_path)
    return bundle


def summarize_bundle(b: dict) -> None:
    print(f"\n=== bundle summary: {b['fbgn']} ({b.get('symbol','')}) ===")
    print(f"auto_summary: {len(b['auto_summary'])} chars")
    for sid, txt in b["sections"].items():
        if txt:
            print(f"section {sid}: {len(txt)} chars")
    print(f"pubs_total: {b['pubs_total']}, refs selected: {len(b['refs_selected'])}")
    abs_with = sum(1 for a in b["abstracts"] if a["abstract"])
    abs_chars = sum(len(a["abstract"]) for a in b["abstracts"])
    print(f"abstracts with text: {abs_with}/{len(b['abstracts'])}, total {abs_chars} chars")
    print(f"human orthologs: {len(b.get('human_ortholog_data', []))}")
    print(f"mouse orthologs: {len(b.get('mouse_ortholog_data', []))}")
    body = (
        len(b["auto_summary"])
        + sum(len(s) for s in b["sections"].values())
        + abs_chars
        + sum(len(o.get("summary", "") or "") for o in b.get("human_ortholog_data", []))
        + sum(len(o.get("summary", "") or "") for o in b.get("mouse_ortholog_data", []))
    )
    print(f"~total text payload: {body} chars (~{body//4} tokens)")


def main():
    fbgn = sys.argv[1] if len(sys.argv) > 1 else "FBgn0003068"
    enable_mygene = os.environ.get("DISABLE_MYGENE") != "1"
    cache = ROOT / "data" / "cache" / fbgn
    print(f"Fetching {fbgn} (bulk-only) → {cache}")
    t0 = time.time()
    b = build_bundle(fbgn, cache, enable_mygene=enable_mygene)
    print(f"\nbuilt in {time.time()-t0:.1f}s")
    summarize_bundle(b)


if __name__ == "__main__":
    main()
