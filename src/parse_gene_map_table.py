"""Parse FlyBase gene_map_table_fb_*.tsv.gz files and extract authoritative
per-FBgn chromosome coordinates for r5 (FB2014_01) and r6 (FB2026_01).

Long pointed us at these two files in his 2026-05-19 email — they ARE FlyBase's
own per-release coordinate tables, so we use them directly instead of
lifting r6 → r5 with a chain file.

Three-way sanity check (Long's concern about FBgn stability across releases):
  1. Our 14019 fly canonicals (output/genes/FBgn*.json)
  2. r6 gene_map_table (FB2026_01)
  3. r5 gene_map_table (FB2014_01)

Outputs:
  data/flybase_coords/coords_r6.tsv  — fbgn  chr  start  end  strand  symbol
  data/flybase_coords/coords_r5.tsv  — fbgn  chr  start  end  strand  symbol
  data/flybase_coords/fbgn_audit.tsv — fbgn  in_atlas  in_r6  in_r5

Run:
  python src/parse_gene_map_table.py
"""
from __future__ import annotations
import gzip
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COORD_DIR = ROOT / "data" / "flybase_coords"
GENES_DIR = ROOT / "output" / "genes"

R6_PATH = COORD_DIR / "gene_map_table_fb_2026_01.tsv.gz"
R5_PATH = COORD_DIR / "gene_map_table_fb_2014_01.tsv.gz"

# sequence_loc format: "chr:start..end(strand)" e.g. "2R:22136968..22172834(1)"
_LOC_RE = re.compile(r"^(\S+):(\d+)\.\.(\d+)\(([\-]?\d+)\)$")


def parse_loc(s: str):
    if not s or not s.strip():
        return None, None, None, None
    m = _LOC_RE.match(s.strip())
    if not m:
        return None, None, None, None
    chr_ = m.group(1)
    start = int(m.group(2))
    end = int(m.group(3))
    strand_int = int(m.group(4))
    strand = "+" if strand_int == 1 else ("-" if strand_int == -1 else "?")
    return chr_, start, end, strand


def parse_table(path: Path, release_label: str) -> dict[str, dict]:
    """Returns {fbgn: {symbol, chr, start, end, strand}}. Skips lines without
    parseable sequence_loc (typical for non-positional features like
    snRNA:4.5S which have only a cytogenetic location)."""
    out: dict[str, dict] = {}
    skipped_no_loc = 0
    skipped_non_dmel = 0
    seen = 0
    with gzip.open(path, "rt", encoding="utf-8", errors="replace") as f:
        # Detect r6 (has organism col) vs r5 (no organism col)
        r6_format = release_label == "r6"
        for line in f:
            line = line.rstrip("\n")
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            if r6_format:
                if len(parts) < 6:
                    continue
                organism, symbol, fbgn, recomb_loc, cyto_loc, seq_loc = parts[:6]
                if organism != "Dmel":
                    skipped_non_dmel += 1
                    continue
            else:
                if len(parts) < 5:
                    continue
                symbol, fbgn, recomb_loc, cyto_loc, seq_loc = parts[:5]
            seen += 1
            if not fbgn.startswith("FBgn"):
                continue
            chr_, start, end, strand = parse_loc(seq_loc)
            if chr_ is None:
                skipped_no_loc += 1
                continue
            out[fbgn] = {
                "symbol": symbol,
                "chr": chr_,
                "start": start,
                "end": end,
                "strand": strand,
            }
    print(f"  {release_label}: {len(out)} FBgns with seq_loc, "
          f"{skipped_no_loc} skipped (no seq_loc), "
          f"{skipped_non_dmel} non-Dmel" if r6_format else
          f"  {release_label}: {len(out)} FBgns with seq_loc, "
          f"{skipped_no_loc} skipped (no seq_loc)")
    return out


def write_coords_tsv(out_path: Path, coords: dict[str, dict]) -> None:
    with open(out_path, "w") as f:
        f.write("fbgn\tchr\tstart\tend\tstrand\tsymbol\n")
        for fbgn in sorted(coords):
            r = coords[fbgn]
            f.write(f"{fbgn}\t{r['chr']}\t{r['start']}\t{r['end']}\t{r['strand']}\t{r['symbol']}\n")


def main():
    print("Parsing r6 gene_map_table (FB2026_01)...")
    r6 = parse_table(R6_PATH, "r6")
    print("Parsing r5 gene_map_table (FB2014_01)...")
    r5 = parse_table(R5_PATH, "r5")

    # Our atlas FBgns
    atlas = sorted(p.stem for p in GENES_DIR.glob("FBgn*.json"))
    atlas_set = set(atlas)
    r6_set = set(r6)
    r5_set = set(r5)

    print(f"\nAtlas FBgns:     {len(atlas_set):>6}")
    print(f"r6 FBgns:        {len(r6_set):>6}")
    print(f"r5 FBgns:        {len(r5_set):>6}")
    print()
    print(f"Atlas ∩ r6:      {len(atlas_set & r6_set):>6}  ({len(atlas_set & r6_set)/len(atlas_set)*100:.1f}% of atlas)")
    print(f"Atlas ∩ r5:      {len(atlas_set & r5_set):>6}  ({len(atlas_set & r5_set)/len(atlas_set)*100:.1f}% of atlas)")
    print(f"Atlas ∩ r5 ∩ r6: {len(atlas_set & r5_set & r6_set):>6}  ({len(atlas_set & r5_set & r6_set)/len(atlas_set)*100:.1f}% of atlas)")
    print()
    print(f"Atlas − r6 (not in r6, our 14k has them):     {len(atlas_set - r6_set):>6}")
    print(f"Atlas − r5 (not in r5 — created after FB2014_01): {len(atlas_set - r5_set):>6}")
    print(f"Atlas − r6 ∪ r5:                               {len(atlas_set - r5_set - r6_set):>6}")

    # write coords
    COORD_DIR.mkdir(parents=True, exist_ok=True)
    write_coords_tsv(COORD_DIR / "coords_r6.tsv", r6)
    write_coords_tsv(COORD_DIR / "coords_r5.tsv", r5)
    print(f"\nWrote {COORD_DIR / 'coords_r6.tsv'}")
    print(f"Wrote {COORD_DIR / 'coords_r5.tsv'}")

    # audit table
    with open(COORD_DIR / "fbgn_audit.tsv", "w") as f:
        f.write("fbgn\tin_atlas\tin_r6\tin_r5\n")
        all_fbgns = atlas_set | r6_set | r5_set
        for fbgn in sorted(all_fbgns):
            in_a = "Y" if fbgn in atlas_set else "N"
            in_6 = "Y" if fbgn in r6_set else "N"
            in_5 = "Y" if fbgn in r5_set else "N"
            f.write(f"{fbgn}\t{in_a}\t{in_6}\t{in_5}\n")
    print(f"Wrote {COORD_DIR / 'fbgn_audit.tsv'}")

    # Sample some mismatches
    only_atlas = sorted(atlas_set - r6_set - r5_set)
    if only_atlas:
        print(f"\nFBgns only in atlas (not in either r5 or r6):")
        for fb in only_atlas[:10]:
            print(f"  {fb}")
        if len(only_atlas) > 10:
            print(f"  ... and {len(only_atlas)-10} more")

    not_in_r6 = sorted(atlas_set - r6_set)
    if not_in_r6:
        print(f"\nFBgns in atlas but not in r6 gene_map_table (sample):")
        for fb in not_in_r6[:5]:
            print(f"  {fb}")


if __name__ == "__main__":
    main()
