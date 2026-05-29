"""One-shot FlyBase bulk downloader — uses the s3ftp.flybase.org AWS S3 mirror which
is NOT behind the CloudFront WAF that blocks ftp.flybase.net from residential IPs.

Downloads only the precomputed TSV files we need for the distillation pipeline.
Skips files already present (idempotent). Verifies size after download.
"""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

S3_BASE = "https://s3ftp.flybase.org/releases/current/precomputed_files"

# subdir → list of filename stems (release suffix will be auto-discovered if not given)
WANTED = {
    "genes": [
        "automated_gene_summaries",          # 1 line/gene: auto-generated summary text
        "best_gene_summary",                  # curated short summary
        "gene_snapshots",                     # FlyBase-curator-written gene-level prose
        "gene_genetic_interactions",          # gene-gene genetic interaction edges
        "physical_interactions_mitab",        # gene-gene physical interaction (MITAB format)
        "gene_groups_HGNC",                   # fly gene group → HGNC family (cross-species)
        "fbgn_annotation_ID",                 # FBgn ↔ CG ↔ symbol mapping
        "gene_rpkm_report",                   # per-gene RNA-seq RPKM across tissues + dev stages (where/when expressed)
    ],
    "synonyms": [
        "fb_synonym",                         # full symbol/name/synonym table (robust name → FBgn resolution)
    ],
    "alleles": [
        "genotype_phenotype_data",            # MAIN: per-allele phenotype annotations (replaces phenotypes_sub scrape)
        "fbal_to_fbgn",                       # allele FBal → gene FBgn map
        "dmel_classical_and_insertion_allele_descriptions",  # allele text descriptions
    ],
    "references": [
        "representative_publications",        # FlyBase-curator-picked representative papers per gene
        "fbrf_pmid_pmcid_doi",                # FBrf ↔ PMID ↔ DOI lookup
        "entity_publication",                 # gene → all its publications (FBrf list)
    ],
    "orthologs": [
        "dmel_human_orthologs_disease",       # human ortholog + DIOPT score + OMIM disease links (replaces human_orthologs_sub + parts of hdm_sub)
    ],
    "human_disease": [
        "disease_model_annotations",          # FlyBase human-disease-model curated annotations
        "human_disease_models",               # disease models registry
        "disease_implicated_variants",        # variants implicated per disease
    ],
}


def find_latest_release(subdir: str):
    """Scrape the s3 listing to find current release suffix (e.g. 'fb_2026_01')."""
    proc = subprocess.run(
        ["/usr/bin/curl", "-s", "--max-time", "30", f"{S3_BASE}/{subdir}/"],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        return None
    import re
    m = re.search(r"_fb_(\d{4}_\d{2})\.tsv\.gz", proc.stdout)
    return f"fb_{m.group(1)}" if m else None


def download_file(url: str, dest: Path, expected_min_bytes: int = 100) -> dict:
    """Download with size check. Returns {ok, bytes, elapsed_s, message}."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size >= expected_min_bytes:
        return {"ok": True, "bytes": dest.stat().st_size, "elapsed_s": 0,
                "message": "already cached"}
    t0 = time.time()
    tmp = dest.with_suffix(dest.suffix + ".tmp")
    proc = subprocess.run(
        ["/usr/bin/curl", "-sS", "-o", str(tmp), "--max-time", "300", url],
        capture_output=True, text=True,
    )
    dt = time.time() - t0
    if proc.returncode != 0:
        if tmp.exists(): tmp.unlink()
        return {"ok": False, "bytes": 0, "elapsed_s": round(dt, 1),
                "message": f"curl exit {proc.returncode}: {proc.stderr[:200]}"}
    size = tmp.stat().st_size
    if size < expected_min_bytes:
        tmp.unlink()
        return {"ok": False, "bytes": size, "elapsed_s": round(dt, 1),
                "message": f"too small ({size} bytes)"}
    tmp.rename(dest)
    return {"ok": True, "bytes": size, "elapsed_s": round(dt, 1), "message": "downloaded"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(Path(__file__).resolve().parents[1] / "data" / "flybase_bulk"))
    ap.add_argument("--release", help="release suffix like fb_2026_01 (auto if omitted)")
    args = ap.parse_args()
    out = Path(args.out)

    # auto-detect release from first subdir
    release = args.release or find_latest_release("genes")
    if not release:
        sys.exit("could not detect FlyBase release (and none given via --release)")
    print(f"FlyBase release: {release}")
    print(f"download root:   {out}\n")

    manifest = {"release": release, "downloaded_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "source": S3_BASE, "files": []}
    fails = 0
    total_bytes = 0
    for subdir, stems in WANTED.items():
        for stem in stems:
            fname = f"{stem}_{release}.tsv.gz"
            url = f"{S3_BASE}/{subdir}/{fname}"
            dest = out / subdir / fname
            result = download_file(url, dest)
            tag = "OK  " if result["ok"] else "FAIL"
            print(f"  [{tag}] {subdir:14}/{stem:50}  {result['bytes']:>10,} B  {result['elapsed_s']:>4}s  ({result['message']})")
            manifest["files"].append({
                "subdir": subdir, "stem": stem, "filename": fname,
                "dest": str(dest.relative_to(out)),
                **result,
            })
            if result["ok"]:
                total_bytes += result["bytes"]
            else:
                fails += 1

    (out / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print(f"\nwrote {out / 'manifest.json'}")
    print(f"total: {total_bytes:,} bytes ({total_bytes / 1024 / 1024:.1f} MB), {fails} failures")


if __name__ == "__main__":
    main()
