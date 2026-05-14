"""Strict-validate every output/genes/*.json against the v1 schema.

Reports per-gene PASS / WARN (lint only) / FAIL (structural).
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GENES_DIR = ROOT / "output" / "genes"
SCHEMA_PATH = ROOT / "output" / "schema" / "distilled_gene_v1.schema.json"


def validate(gene: dict, schema: dict) -> list:
    """Tiny hand-rolled validator — checks required fields + enums + IDs. Returns list of errors."""
    errs = []
    req = schema["required"]
    for k in req:
        if k not in gene:
            errs.append(f"missing required field: {k}")
    if gene.get("schema_version") != "1.0":
        errs.append(f"schema_version must be 1.0, got {gene.get('schema_version')}")
    if not (isinstance(gene.get("fbgn"), str) and gene["fbgn"].startswith("FBgn")):
        errs.append("fbgn must be FBgn-prefixed string")
    cs = gene.get("cross_species", {})
    for k in ("human_orthologs", "mouse_orthologs", "human_disease_links", "mouse_phenotype_links"):
        if k not in cs:
            errs.append(f"cross_species missing {k}")
    bs = gene.get("bullets", [])
    valid_cats = set(schema["properties"]["bullets"]["items"]["properties"]["category"]["enum"])
    valid_dirs = set(schema["properties"]["bullets"]["items"]["properties"]["direction"]["enum"])
    seen_ids = set()
    for i, b in enumerate(bs, 1):
        for f in ("id", "category", "phenotype", "direction", "evidence"):
            if not b.get(f):
                errs.append(f"bullet {i} missing {f}")
        if b.get("category") not in valid_cats:
            errs.append(f"bullet {i} bad category: {b.get('category')}")
        if b.get("direction") not in valid_dirs:
            errs.append(f"bullet {i} bad direction: {b.get('direction')}")
        if b["id"] in seen_ids:
            errs.append(f"bullet {i} duplicate id: {b['id']}")
        seen_ids.add(b["id"])
        if b.get("confidence") not in (None, "high", "medium", "low"):
            errs.append(f"bullet {i} bad confidence: {b.get('confidence')}")
    return errs


def main():
    schema = json.loads(SCHEMA_PATH.read_text())
    files = sorted(GENES_DIR.glob("FBgn*.json"))
    print(f"validating {len(files)} genes against schema v{schema['$id']}")
    print()
    n_pass = n_warn = n_fail = 0
    for f in files:
        g = json.loads(f.read_text())
        errs = validate(g, schema)
        lint = g.get("_lint", [])
        if errs:
            status = "FAIL"
            n_fail += 1
        elif lint:
            status = "WARN"
            n_warn += 1
        else:
            status = "PASS"
            n_pass += 1
        print(f"  {status:4} {g['fbgn']:13} {g['symbol']:8} ({len(g['bullets'])} bullets)")
        for e in errs:
            print(f"        × {e}")
        for w in lint:
            print(f"        ⚠ {w}")
    print()
    print(f"summary: {n_pass} PASS, {n_warn} WARN, {n_fail} FAIL")


if __name__ == "__main__":
    main()
