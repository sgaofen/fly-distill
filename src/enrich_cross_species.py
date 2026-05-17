"""Parse MGI + HPO + OMIM controlled-vocabulary tables and attach mouse/human
phenotype descriptions to every fly gene canonical's cross_species block.

NOTE: This is pure structured-data join — NO LLM calls, NO new top-level entities.
Mouse/human genes never get their own canonical or embedding vector. They live
strictly as attached descriptions under each fly gene's cross_species.* arrays.

Sources (all local, all free):
  data/mgi/MGI_PhenoGenoMP.rpt        — mouse_allele → [MP term IDs]
  data/mgi/VOC_MammalianPhenotype.rpt — MP_id → (term, definition)
  data/mgi/HMD_HumanPhenotype.rpt     — mouse symbol ↔ human symbol bridge
  data/hpo/genes_to_phenotype.txt     — human entrez → [HP term IDs]
  data/hpo/hp.obo                     — HP_id → (term, definition)
  data/hpo/phenotype.hpoa             — OMIM disease → [HP term IDs]

Output: rewrites output/genes/<FBgn>.json in place with new fields:
  cross_species.human_orthologs[*].omim_phenotypes[*].hpo_terms (list)
  cross_species.human_orthologs[*].hpo_phenotypes (list, gene-level HPO)
  cross_species.mouse_orthologs[*].mgi_phenotypes (list)
  cross_species.human_disease_links[*].hpo_terms (list, disease-level HPO)
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GENES_DIR = ROOT / "output" / "genes"


def parse_mp_terms(path: Path) -> dict[str, dict]:
    """VOC_MammalianPhenotype.rpt has 3 tab-separated cols: MP_id, term, definition."""
    out = {}
    with open(path) as f:
        for line in f:
            cols = line.rstrip("\n").split("\t")
            if len(cols) >= 2 and cols[0].startswith("MP:"):
                out[cols[0]] = {
                    "term": cols[1],
                    "definition": cols[2] if len(cols) > 2 else "",
                }
    return out


def parse_mouse_pheno(path: Path) -> dict[str, set]:
    """MGI_PhenoGenoMP.rpt: allele-composite → MP terms.
    Column layout per MGI spec: AllelComposition  AllelSymbol  GeneticBackground  MammalianPhenotypeID  PubMedID  MGIMarkerAccession
    We aggregate by mouse SYMBOL (extracted from AllelSymbol like 'Irs1<tm1Mfw>')."""
    out: dict[str, set] = defaultdict(set)
    sym_re = re.compile(r"^([A-Za-z0-9_-]+)(?:<|/|$)")
    with open(path) as f:
        for line in f:
            cols = line.rstrip("\n").split("\t")
            if len(cols) < 4:
                continue
            allele_sym = cols[1]
            mp_id = cols[3]
            if not mp_id.startswith("MP:"):
                continue
            # Multi-allele combinations get split into individual symbols
            for tok in re.split(r"[,/\s]+", allele_sym):
                m = sym_re.match(tok)
                if m:
                    out[m.group(1)].add(mp_id)
    return out


def parse_hp_obo(path: Path) -> dict[str, dict]:
    """OBO format: blocks of [Term] with id:/name:/def: lines."""
    out: dict[str, dict] = {}
    cur_id = None
    cur_name = None
    cur_def = None
    in_term = False
    with open(path) as f:
        for line in f:
            line = line.rstrip("\n")
            if line == "[Term]":
                if cur_id and cur_name:
                    out[cur_id] = {"term": cur_name, "definition": cur_def or ""}
                cur_id = None; cur_name = None; cur_def = None
                in_term = True
            elif line.startswith("[") and line != "[Term]":
                in_term = False
            elif in_term:
                if line.startswith("id: "):
                    cur_id = line[4:]
                elif line.startswith("name: "):
                    cur_name = line[6:]
                elif line.startswith("def: "):
                    # def: "actual definition text" [refs]
                    m = re.match(r'def:\s*"([^"]*)"', line)
                    if m:
                        cur_def = m.group(1)
    if cur_id and cur_name:
        out[cur_id] = {"term": cur_name, "definition": cur_def or ""}
    return out


def parse_human_gene_hpo(path: Path) -> dict[str, set]:
    """genes_to_phenotype.txt header line then tab-separated:
    ncbi_gene_id  gene_symbol  hpo_id  hpo_name  frequency  disease_id"""
    out: dict[str, set] = defaultdict(set)
    with open(path) as f:
        next(f, None)
        for line in f:
            cols = line.rstrip("\n").split("\t")
            if len(cols) < 3:
                continue
            entrez = cols[0]
            hp_id = cols[2]
            if hp_id.startswith("HP:"):
                out[entrez].add(hp_id)
    return out


def parse_omim_hpo(path: Path) -> dict[str, set]:
    """phenotype.hpoa: disease_id  disease_name  qualifier  hpo_id  ... (header-marked, # comments)"""
    out: dict[str, set] = defaultdict(set)
    with open(path) as f:
        for line in f:
            if line.startswith("#") or line.startswith("database_id"):
                continue
            cols = line.rstrip("\n").split("\t")
            if len(cols) < 4:
                continue
            disease = cols[0]  # "OMIM:125853"
            hp = cols[3] if cols[3].startswith("HP:") else None
            if disease.startswith("OMIM:") and hp:
                out[disease[5:]].add(hp)  # strip "OMIM:" prefix
    return out


def enrich_cross_species(cs: dict, *, mp_terms, mouse_pheno, hp_terms,
                          human_gene_hpo, omim_hpo, cap_per_ortho: int = 20) -> dict:
    """Mutate cross_species block in place — add mgi_phenotypes / hpo_phenotypes
    to each ortholog, and hpo_terms to each disease link."""
    # Mouse side
    for o in cs.get("mouse_orthologs") or []:
        sym = o.get("symbol")
        if not sym:
            continue
        mp_ids = sorted(mouse_pheno.get(sym, set()))[:cap_per_ortho]
        o["mgi_phenotypes"] = [
            {"mp_id": mp, "term": mp_terms[mp]["term"],
             "definition": mp_terms[mp]["definition"][:300]}
            for mp in mp_ids if mp in mp_terms
        ]
    # Human side — gene-level HPO from genes_to_phenotype
    for o in cs.get("human_orthologs") or []:
        eid = str(o.get("entrez_id") or "")
        if not eid:
            continue
        hp_ids = sorted(human_gene_hpo.get(eid, set()))[:cap_per_ortho]
        o["hpo_phenotypes"] = [
            {"hp_id": hp, "term": hp_terms[hp]["term"],
             "definition": hp_terms[hp]["definition"][:300]}
            for hp in hp_ids if hp in hp_terms
        ]
    # Disease-level HPO from phenotype.hpoa
    for d in cs.get("human_disease_links") or []:
        omim = d.get("omim_id")
        if not omim:
            continue
        hp_ids = sorted(omim_hpo.get(omim, set()))[:12]
        d["hpo_terms"] = [
            {"hp_id": hp, "term": hp_terms[hp]["term"]}
            for hp in hp_ids if hp in hp_terms
        ]
    return cs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="Only process first N (testing)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    t0 = time.time()
    print("Loading MGI MP vocabulary...", flush=True)
    mp_terms = parse_mp_terms(ROOT / "data/mgi/VOC_MammalianPhenotype.rpt")
    print(f"  {len(mp_terms)} MP terms")

    print("Loading mouse gene → MP terms...", flush=True)
    mouse_pheno = parse_mouse_pheno(ROOT / "data/mgi/MGI_PhenoGenoMP.rpt")
    print(f"  {len(mouse_pheno)} mouse genes with phenotype data")

    print("Loading HPO ontology...", flush=True)
    hp_terms = parse_hp_obo(ROOT / "data/hpo/hp.obo")
    print(f"  {len(hp_terms)} HP terms")

    print("Loading human gene → HPO...", flush=True)
    human_gene_hpo = parse_human_gene_hpo(ROOT / "data/hpo/genes_to_phenotype.txt")
    print(f"  {len(human_gene_hpo)} human genes with HPO annotations")

    print("Loading OMIM disease → HPO...", flush=True)
    omim_hpo = parse_omim_hpo(ROOT / "data/hpo/phenotype.hpoa")
    print(f"  {len(omim_hpo)} OMIM diseases with HPO annotations")

    print(f"\nIndices ready in {time.time()-t0:.1f}s. Enriching canonicals...\n", flush=True)

    files = sorted(GENES_DIR.glob("*.json"))
    if args.limit:
        files = files[:args.limit]

    n_mouse_attached = n_human_attached = n_disease_attached = 0
    t1 = time.time()
    for i, fp in enumerate(files):
        c = json.loads(fp.read_text())
        cs = c.get("cross_species") or {}
        enrich_cross_species(cs, mp_terms=mp_terms, mouse_pheno=mouse_pheno,
                             hp_terms=hp_terms, human_gene_hpo=human_gene_hpo,
                             omim_hpo=omim_hpo)
        for o in cs.get("mouse_orthologs") or []:
            if o.get("mgi_phenotypes"): n_mouse_attached += 1
        for o in cs.get("human_orthologs") or []:
            if o.get("hpo_phenotypes"): n_human_attached += 1
        for d in cs.get("human_disease_links") or []:
            if d.get("hpo_terms"): n_disease_attached += 1
        c["cross_species"] = cs
        if not args.dry_run:
            fp.write_text(json.dumps(c, indent=2, ensure_ascii=False))
        if (i + 1) % 2000 == 0:
            print(f"  {i+1}/{len(files)} ({(time.time()-t1)/60:.1f}min)", flush=True)

    print(f"\nDone in {(time.time()-t1)/60:.1f}min")
    print(f"  Canonical files updated: {len(files)} {'(dry-run)' if args.dry_run else ''}")
    print(f"  Mouse-ortholog rows with mgi_phenotypes: {n_mouse_attached}")
    print(f"  Human-ortholog rows with hpo_phenotypes: {n_human_attached}")
    print(f"  Disease links with hpo_terms: {n_disease_attached}")


if __name__ == "__main__":
    main()
