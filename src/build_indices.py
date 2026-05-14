"""Build search indices from output/genes/*.json.

Outputs in output/index/:
  catalog.jsonl              — one line per gene: fbgn, symbol, synonyms, n_bullets,
                                categories, human_disease_count, has_orthologs
  by_category.json           — category → [(fbgn, bullet_id)]
  by_human_disease.json      — disease string → [fbgn]
  by_human_ortholog.json     — entrez_id → fbgn (top-1 mapping)
  by_mouse_ortholog.json     — entrez_id → fbgn (top-1 mapping)
  bullets_flat.jsonl         — one line per bullet — fbgn, symbol, bullet — for fulltext/embedding
  lint_summary.json          — per-gene schema-drift / quality warnings
"""
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GENES_DIR = ROOT / "output" / "genes"
INDEX_DIR = ROOT / "output" / "index"


def build():
    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    catalog_lines = []
    bullets_flat_lines = []
    by_category = defaultdict(list)
    by_disease = defaultdict(list)
    by_human_ortho = {}
    by_mouse_ortho = {}
    lint_summary = {}

    gene_files = sorted(GENES_DIR.glob("FBgn*.json"))
    for f in gene_files:
        g = json.loads(f.read_text())
        fbgn = g["fbgn"]

        catalog_lines.append(json.dumps({
            "fbgn": fbgn,
            "symbol": g["symbol"],
            "synonyms": g.get("synonyms", []),
            "n_bullets": len(g["bullets"]),
            "categories": sorted({b["category"] for b in g["bullets"]}),
            "n_human_disease_links": len(g["cross_species"]["human_disease_links"]),
            "n_mouse_phenotype_links": len(g["cross_species"]["mouse_phenotype_links"]),
            "human_ortholog_symbols": [o["symbol"] for o in g["cross_species"]["human_orthologs"]],
            "mouse_ortholog_symbols": [o["symbol"] for o in g["cross_species"]["mouse_orthologs"]],
            "lint_warnings": len(g.get("_lint", [])),
            "schema_version": g["schema_version"],
        }, ensure_ascii=False))

        if g.get("_lint"):
            lint_summary[fbgn] = g["_lint"]

        # per-bullet flat
        for b in g["bullets"]:
            bullets_flat_lines.append(json.dumps({
                "fbgn": fbgn,
                "symbol": g["symbol"],
                "bullet_id": b["id"],
                "category": b["category"],
                "phenotype": b["phenotype"],
                "direction": b["direction"],
                "confidence": b["confidence"],
                "evidence": b["evidence"],
            }, ensure_ascii=False))
            by_category[b["category"]].append({"fbgn": fbgn, "bullet_id": b["id"]})

        # disease index
        for d in g["cross_species"]["human_disease_links"]:
            by_disease[d].append(fbgn)

        # ortholog → fly gene (top-1 only — assume the highest-DIOPT entry is in slot 0)
        for o in g["cross_species"]["human_orthologs"]:
            ent = o.get("entrez_id")
            if ent:
                by_human_ortho.setdefault(ent, []).append({
                    "fbgn": fbgn,
                    "fly_symbol": g["symbol"],
                    "human_symbol": o["symbol"],
                    "diopt_score": o["diopt_score"],
                    "diopt_max": o["diopt_max"],
                })
        for o in g["cross_species"]["mouse_orthologs"]:
            ent = o.get("entrez_id")
            if ent:
                by_mouse_ortho.setdefault(ent, []).append({
                    "fbgn": fbgn,
                    "fly_symbol": g["symbol"],
                    "mouse_symbol": o["symbol"],
                    "diopt_score": o["diopt_score"],
                    "diopt_max": o["diopt_max"],
                })

    (INDEX_DIR / "catalog.jsonl").write_text("\n".join(catalog_lines) + "\n")
    (INDEX_DIR / "bullets_flat.jsonl").write_text("\n".join(bullets_flat_lines) + "\n")
    (INDEX_DIR / "by_category.json").write_text(
        json.dumps({k: sorted(v, key=lambda x: x["bullet_id"]) for k, v in sorted(by_category.items())}, indent=2)
    )
    (INDEX_DIR / "by_human_disease.json").write_text(
        json.dumps({k: sorted(set(v)) for k, v in sorted(by_disease.items())}, indent=2, ensure_ascii=False)
    )
    (INDEX_DIR / "by_human_ortholog.json").write_text(
        json.dumps({k: v for k, v in sorted(by_human_ortho.items())}, indent=2)
    )
    (INDEX_DIR / "by_mouse_ortholog.json").write_text(
        json.dumps({k: v for k, v in sorted(by_mouse_ortho.items())}, indent=2)
    )
    (INDEX_DIR / "lint_summary.json").write_text(json.dumps(lint_summary, indent=2, ensure_ascii=False))

    print(f"wrote {len(gene_files)} genes, {len(bullets_flat_lines)} bullets to {INDEX_DIR}")
    print(f"  categories indexed: {len(by_category)}")
    print(f"  human diseases indexed: {len(by_disease)}")
    print(f"  human ortholog entries: {len(by_human_ortho)}")
    print(f"  mouse ortholog entries: {len(by_mouse_ortho)}")
    print(f"  genes with lint warnings: {len(lint_summary)}")


if __name__ == "__main__":
    build()
