"""Parse Long's QTL_summary.md into a structured `qtls` table in atlas.db.

Each row in Long's table becomes one record with: id, drug, chr, peak_r6,
start_r6, end_r6, peak_r5, start_r5, end_r5, neg_log_p, gene_count, phenotype,
release_orig, pmc_url.

For r5 entries, we ALSO compute r6 fields by looking up the union of genes in
the r5 interval and taking their r6 chr/min(start)/max(end). For r6 entries
we ALSO populate r5 fields the same way. This gives every QTL a dual-coordinate
record so all overlap analysis can be done in either space.

Run:
  python src/parse_qtl_summary.py
"""
from __future__ import annotations
import argparse
import re
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "tools" / "atlas.db"
MD_PATH = ROOT / "data" / "QTL_summary.md"

# Phenotype description → drug class mapping (for Long's email's "biological similarity" pairs)
DRUG_FAMILIES = {
    "Carboplatin": "chemo",
    "Gemcitabine": "chemo",
    "Methotrexate": "chemo",
    "Malathion": "pesticide",
    "Zinc oxide": "heavy_metal",
    "Caffeine": "xenobiotic",
}

# PMC URLs from the Sources section of Long's MD
PMC_MAP = {
    "Carboplatin":  "https://pmc.ncbi.nlm.nih.gov/articles/PMC4174942/",
    "Gemcitabine":  "https://pmc.ncbi.nlm.nih.gov/articles/PMC4174942/",
    "Methotrexate": "https://pmc.ncbi.nlm.nih.gov/articles/PMC3737169/",
    "Malathion":    "https://pmc.ncbi.nlm.nih.gov/articles/PMC9713458/",
    "Zinc oxide":   "https://pmc.ncbi.nlm.nih.gov/articles/PMC12606420/",
    "Caffeine":     "https://pmc.ncbi.nlm.nih.gov/articles/PMC8893256/",
}


SCHEMA = """
DROP TABLE IF EXISTS qtls;
CREATE TABLE qtls (
  id           TEXT PRIMARY KEY,        -- e.g. "caffeine_D", "methotrexate_A"
  qtl_label    TEXT,                    -- the letter Long used (A/B/C/D/CA/CB...) — may be empty
  study_drug   TEXT NOT NULL,           -- e.g. "Caffeine"
  drug_family  TEXT,                    -- chemo / pesticide / heavy_metal / xenobiotic
  chr          TEXT NOT NULL,           -- e.g. "3R", "2L-2R"
  peak_r6      INTEGER,                 -- bp; NULL if originally r5 with no peak conversion
  start_r6     INTEGER,
  end_r6       INTEGER,
  peak_r5      INTEGER,                 -- bp; populated for both r5-native and r6-native
  start_r5     INTEGER,
  end_r5       INTEGER,
  neg_log_p    REAL,                    -- significance
  h2           TEXT,                    -- heritability % (when reported)
  gene_count   INTEGER,                 -- Long's reported gene count
  release_orig TEXT NOT NULL,           -- "r5" or "r6"
  phenotype    TEXT NOT NULL,           -- e.g. "Adult female longevity on 1% caffeine"
  pmc_url      TEXT
);
CREATE INDEX idx_qtls_chr ON qtls(chr);
CREATE INDEX idx_qtls_drug ON qtls(study_drug);
"""


# Parse "Mb" or "bp" forms — Long's MD mixes them
def parse_position(s: str) -> int | None:
    """Return position in bp. Accepts 'X.X Mb' or 'X bp' or 'X,XXX,XXX bp'."""
    if s is None:
        return None
    s = s.replace(",", "").strip()
    m = re.match(r"^([\d.]+)\s*Mb$", s)
    if m:
        return int(float(m.group(1)) * 1_000_000)
    m = re.match(r"^([\d.]+)\s*bp$", s)
    if m:
        return int(float(m.group(1)))
    # Fallback: just a number
    m = re.match(r"^([\d.]+)$", s)
    if m:
        v = float(m.group(1))
        return int(v * 1_000_000) if v < 100_000 else int(v)
    return None


def parse_interval(s: str) -> tuple[int | None, int | None]:
    """Accepts:
       'X.X–Y.Y Mb', 'X.XX-Y.YY Mb', '1,234,567–7,890,123 bp', '3L:17.76–3R:5.85 Mb'
    Returns (start_bp, end_bp). Cross-arm intervals get (start, end) anyway but
    chr is ambiguous; the caller should handle that."""
    if s is None:
        return None, None
    s = s.strip()
    # cross-arm format: "3L:17.76–3R:5.85 Mb" — strip out the cross-arm tags
    cross = re.match(r"^[^:]+:([\d.]+)\s*[–-]\s*[^:]+:([\d.]+)\s*Mb$", s)
    if cross:
        return int(float(cross.group(1)) * 1_000_000), int(float(cross.group(2)) * 1_000_000)
    # standard format: number – number Mb/bp
    m = re.match(r"^([\d.,]+)\s*[–-]\s*([\d.,]+)\s*(Mb|bp)$", s)
    if not m:
        return None, None
    lo = m.group(1).replace(",", "")
    hi = m.group(2).replace(",", "")
    unit = m.group(3)
    if unit == "Mb":
        return int(float(lo) * 1_000_000), int(float(hi) * 1_000_000)
    return int(float(lo)), int(float(hi))


# Parse a single MD table row
def parse_row(line: str) -> dict | None:
    if not line.startswith("|"):
        return None
    cells = [c.strip() for c in line.split("|")[1:-1]]  # drop leading/trailing empties
    if len(cells) != 9:
        return None
    qtl_label, drug, chr_, peak, interval, neglogp, h2_or_count, release, phenotype = cells

    # Skip header & separator
    if qtl_label.lower() == "qtl" or set(qtl_label) <= set("-"):
        return None

    qtl_label = qtl_label.replace("—", "").strip()
    peak_bp = parse_position(peak)
    start_bp, end_bp = parse_interval(interval)

    # gene_count vs h²: r6 entries say "344 genes", r5 entries say "23%"
    gene_count = None
    h2 = None
    m = re.match(r"^(\d+)\s*genes?$", h2_or_count)
    if m:
        gene_count = int(m.group(1))
    elif h2_or_count.endswith("%"):
        h2 = h2_or_count
    elif h2_or_count and h2_or_count != "—":
        # Could be cross-arm gene count (rare) or unparseable
        try:
            gene_count = int(h2_or_count)
        except ValueError:
            pass

    try:
        neg_log_p_val = float(neglogp) if neglogp not in ("—", "") else None
    except ValueError:
        neg_log_p_val = None

    return {
        "qtl_label": qtl_label,
        "study_drug": drug,
        "drug_family": DRUG_FAMILIES.get(drug, "other"),
        "chr": chr_,
        "peak_bp": peak_bp,
        "start_bp": start_bp,
        "end_bp": end_bp,
        "neg_log_p": neg_log_p_val,
        "h2": h2,
        "gene_count": gene_count,
        "release_orig": "r5" if release.lower().strip() == "r5" else "r6",
        "phenotype": phenotype,
        "pmc_url": PMC_MAP.get(drug),
    }


def cross_release_interval(con: sqlite3.Connection, chr_: str, start: int, end: int,
                           src_release: str) -> tuple[str | None, int | None, int | None]:
    """Given an interval in one release space, find the corresponding genes' coords
    in the OTHER release. Returns (chr, min_start, max_end) in the target release,
    or (None, None, None) if no genes overlap."""
    tgt = "r5" if src_release == "r6" else "r6"
    if src_release == "r6":
        # search in r6 columns, return r5
        rows = con.execute(
            "SELECT chr_r5, start_r5, end_r5 FROM genes "
            "WHERE chr=? AND end>=? AND start<=? AND chr_r5 IS NOT NULL",
            (chr_, start, end),
        ).fetchall()
    else:
        rows = con.execute(
            "SELECT chr, start, end FROM genes "
            "WHERE chr_r5=? AND end_r5>=? AND start_r5<=? AND chr IS NOT NULL",
            (chr_, start, end),
        ).fetchall()
    if not rows:
        return None, None, None
    # Pick the dominant chr; if mixed (rare), pick the most-common one
    from collections import Counter
    ch_counter = Counter(r[0] for r in rows if r[0])
    if not ch_counter:
        return None, None, None
    target_chr = ch_counter.most_common(1)[0][0]
    sel = [r for r in rows if r[0] == target_chr]
    starts = [r[1] for r in sel if r[1] is not None]
    ends = [r[2] for r in sel if r[2] is not None]
    return target_chr, min(starts) if starts else None, max(ends) if ends else None


def assign_id(row: dict, n_dup: dict) -> str:
    """Make unique ID: <drug>_<label>; if label empty, use seq number."""
    drug_slug = row["study_drug"].lower().replace(" oxide", "").replace(" ", "_")
    label = row["qtl_label"]
    if not label:
        # Auto-letter for unlabeled rows
        n_dup[drug_slug] = n_dup.get(drug_slug, 0) + 1
        label = chr(64 + n_dup[drug_slug])  # 1=A, 2=B, ...
    return f"{drug_slug}_{label}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--md", default=str(MD_PATH))
    ap.add_argument("--db", default=str(DB_PATH))
    args = ap.parse_args()

    md_text = Path(args.md).read_text()
    rows = []
    in_table = False
    for line in md_text.splitlines():
        line = line.strip()
        if line.startswith("|") and "QTL" in line and "Phenotype" in line:
            in_table = True
            continue
        if in_table and line.startswith("|"):
            r = parse_row(line)
            if r:
                rows.append(r)
        elif in_table and not line.startswith("|"):
            in_table = False

    print(f"Parsed {len(rows)} QTL rows from {args.md}")

    con = sqlite3.connect(args.db)
    con.executescript(SCHEMA)
    cur = con.cursor()

    n_dup = {}
    for r in rows:
        qid = assign_id(r, n_dup)

        if r["release_orig"] == "r6":
            peak_r6 = r["peak_bp"]; start_r6 = r["start_bp"]; end_r6 = r["end_bp"]
            chr_r5, start_r5, end_r5 = cross_release_interval(
                con, r["chr"], r["start_bp"], r["end_bp"], "r6"
            )
            peak_r5 = None  # peak doesn't lift well; skip
        else:
            peak_r5 = r["peak_bp"]; start_r5 = r["start_bp"]; end_r5 = r["end_bp"]
            chr_r6_, start_r6_lifted, end_r6_lifted = cross_release_interval(
                con, r["chr"], r["start_bp"], r["end_bp"], "r5"
            )
            start_r6 = start_r6_lifted; end_r6 = end_r6_lifted
            peak_r6 = None

        cur.execute(
            "INSERT INTO qtls(id, qtl_label, study_drug, drug_family, chr,"
            " peak_r6, start_r6, end_r6, peak_r5, start_r5, end_r5,"
            " neg_log_p, h2, gene_count, release_orig, phenotype, pmc_url)"
            " VALUES (?,?,?,?,?, ?,?,?, ?,?,?, ?,?,?, ?,?,?)",
            (qid, r["qtl_label"], r["study_drug"], r["drug_family"], r["chr"],
             peak_r6, start_r6, end_r6, peak_r5, start_r5, end_r5,
             r["neg_log_p"], r["h2"], r["gene_count"], r["release_orig"],
             r["phenotype"], r["pmc_url"]),
        )

    con.commit()

    # Sanity check: verify our genes-in-region counts vs Long's reported counts
    print("\nVerification (our gene count vs Long's gene_count):")
    print(f"{'QTL_ID':22} {'Chr':4} {'Interval (r6, bp)':>30}  {'ours':>5}  {'Long':>5}")
    for r in cur.execute("SELECT id, chr, start_r6, end_r6, gene_count, release_orig FROM qtls ORDER BY id"):
        qid, chr_, s, e, expected, rel = r
        if s is None or e is None:
            print(f"{qid:22} {chr_:4} {'(no r6 mapping)':>30}  -      {expected if expected else '-'}")
            continue
        n = cur.execute(
            "SELECT COUNT(*) FROM genes WHERE chr=? AND end>=? AND start<=?",
            (chr_, s, e),
        ).fetchone()[0]
        match = "✓" if expected and n == expected else (" " if not expected else "~")
        print(f"{qid:22} {chr_:4} {s:>14,}-{e:>14,}  {n:>5}  {expected if expected else '-':>5}  {match}")

    con.close()
    print(f"\nWrote {len(rows)} rows to qtls table in {args.db}")


if __name__ == "__main__":
    main()
