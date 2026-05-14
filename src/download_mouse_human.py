"""Bulk download mouse (MGI) + human (HPO + OMIM mim2gene + Alliance) datasets.

All sources are open from residential IP. Total expected ~500 MB.

Layout:
  data/mgi/{file}.rpt
  data/hpo/{file}
  data/omim/mim2gene.txt
  data/alliance/{file}.tsv.gz
"""
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data"

# (subdir, filename, url, min_bytes)
SOURCES = [
    # ----- MOUSE (MGI) -----
    ("mgi", "MRK_List2.rpt",
     "https://www.informatics.jax.org/downloads/reports/MRK_List2.rpt", 1_000_000),
    ("mgi", "MGI_PhenoGenoMP.rpt",
     "https://www.informatics.jax.org/downloads/reports/MGI_PhenoGenoMP.rpt", 1_000_000),
    ("mgi", "HMD_HumanPhenotype.rpt",
     "https://www.informatics.jax.org/downloads/reports/HMD_HumanPhenotype.rpt", 100_000),
    ("mgi", "MGI_PhenotypicAllele.rpt",
     "https://www.informatics.jax.org/downloads/reports/MGI_PhenotypicAllele.rpt", 1_000_000),
    ("mgi", "MGI_Geno_DiseaseDO.rpt",
     "https://www.informatics.jax.org/downloads/reports/MGI_Geno_DiseaseDO.rpt", 100_000),
    ("mgi", "VOC_MammalianPhenotype.rpt",
     "https://www.informatics.jax.org/downloads/reports/VOC_MammalianPhenotype.rpt", 100_000),
    ("mgi", "MGI_DO.rpt",
     "https://www.informatics.jax.org/downloads/reports/MGI_DO.rpt", 100_000),

    # ----- HUMAN PHENOTYPE ONTOLOGY -----
    ("hpo", "hp.obo",
     "https://github.com/obophenotype/human-phenotype-ontology/releases/latest/download/hp.obo", 1_000_000),
    ("hpo", "phenotype.hpoa",
     "https://github.com/obophenotype/human-phenotype-ontology/releases/latest/download/phenotype.hpoa", 1_000_000),
    ("hpo", "genes_to_phenotype.txt",
     "https://github.com/obophenotype/human-phenotype-ontology/releases/latest/download/genes_to_phenotype.txt", 1_000_000),
    ("hpo", "phenotype_to_genes.txt",
     "https://github.com/obophenotype/human-phenotype-ontology/releases/latest/download/phenotype_to_genes.txt", 1_000_000),

    # ----- OMIM (open subset) -----
    ("omim", "mim2gene.txt",
     "https://omim.org/static/omim/data/mim2gene.txt", 100_000),

    # ----- ALLIANCE bulk (cross-species disease + orthology) -----
    ("alliance", "DISEASE-ALLIANCE_COMBINED.tsv.gz",
     "https://fms.alliancegenome.org/download/DISEASE-ALLIANCE_COMBINED.tsv.gz", 100_000),
    ("alliance", "ORTHOLOGY-ALLIANCE_COMBINED.tsv.gz",
     "https://fms.alliancegenome.org/download/ORTHOLOGY-ALLIANCE_COMBINED.tsv.gz", 100_000),
]


def download(url: str, dest: Path, min_bytes: int) -> dict:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size >= min_bytes:
        return {"ok": True, "bytes": dest.stat().st_size, "elapsed_s": 0, "message": "cached"}
    t0 = time.time()
    tmp = dest.with_suffix(dest.suffix + ".tmp")
    proc = subprocess.run(
        ["/usr/bin/curl", "-sSL", "-o", str(tmp), "--max-time", "300", url],
        capture_output=True, text=True,
    )
    dt = time.time() - t0
    if proc.returncode != 0 or not tmp.exists() or tmp.stat().st_size < min_bytes:
        if tmp.exists(): tmp.unlink()
        return {"ok": False, "bytes": 0, "elapsed_s": round(dt, 1),
                "message": f"curl exit {proc.returncode}, stderr={proc.stderr[:150]}"}
    tmp.rename(dest)
    return {"ok": True, "bytes": dest.stat().st_size, "elapsed_s": round(dt, 1), "message": "downloaded"}


def main():
    manifest = {"downloaded_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"), "files": []}
    fails = 0
    total = 0
    by_subdir = {}
    for subdir, fname, url, min_b in SOURCES:
        dest = OUT / subdir / fname
        r = download(url, dest, min_b)
        tag = "OK  " if r["ok"] else "FAIL"
        print(f"  [{tag}] {subdir:10}/{fname:35} {r['bytes']:>12,} B  {r['elapsed_s']:>4}s  ({r['message']})")
        manifest["files"].append({"subdir": subdir, "fname": fname, "url": url, **r})
        if r["ok"]:
            total += r["bytes"]
            by_subdir[subdir] = by_subdir.get(subdir, 0) + r["bytes"]
        else:
            fails += 1
    (OUT / "mouse_human_manifest.json").write_text(json.dumps(manifest, indent=2))
    print("\n=== per-source totals ===")
    for k, v in sorted(by_subdir.items()):
        print(f"  {k:10} {v:>12,} B  ({v / 1024 / 1024:.1f} MB)")
    print(f"\n  TOTAL: {total:,} B ({total / 1024 / 1024:.1f} MB), {fails} failures")


if __name__ == "__main__":
    main()
