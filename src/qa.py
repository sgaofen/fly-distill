"""Tier-1 automated QA for distilled gene records.

Runs deterministic checks on every gene — no LLM calls. Catches:
  - phantom citations (FBrf cited that isn't in input bundle)
  - phenotypes with no lexical anchor in input (likely hallucination)
  - duplicate bullets within a gene
  - confidence/specificity distribution outliers
  - bullet-count vs gene-tier mismatches
  - OMIM ID inconsistencies between output and FlyBase bulk
  - cohort-level statistical outliers

Output:
  output/qa/tier1_report.jsonl   one row per gene with qa_score + issues[]
  output/qa/tier1_summary.md     human-readable summary

Usage:
  python3 src/qa.py tier1                  # check all genes
  python3 src/qa.py tier1 FBgn0003068      # one gene
  python3 src/qa.py sample                 # produce stratified audit sample for Tier 2
"""
import argparse
import json
import re
import statistics
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GENES_DIR = ROOT / "output" / "genes"
BUNDLES = ROOT / "data" / "cache"
QA_DIR = ROOT / "output" / "qa"

STOP = set("""
a an and are as at be been being by can for from has had have he her him his i in is it its
of on or our she so that the their them they this to was were what when where which who whom whose will with you your
abnormal increased decreased show shown demonstrate observe loss-of-function gain-of-function
flies fly mutant mutants wild-type wildtype gene allele alleles
""".split())


def content_tokens(text: str) -> set:
    """Lowercase content words >=4 chars, no punctuation, no stopwords."""
    text = re.sub(r"[^a-zA-Z0-9 ]", " ", text.lower())
    return {w for w in text.split() if len(w) >= 4 and w not in STOP}


def load_gene(fbgn: str) -> dict:
    return json.loads((GENES_DIR / f"{fbgn}.json").read_text())


def load_bundle(fbgn: str) -> dict:
    return json.loads((BUNDLES / fbgn / "bundle.json").read_text())


# ---------- per-gene checks ------------------------------------------------

def check_citations(gene: dict, bundle: dict) -> list:
    """An FBrf is a valid citation if it appears ANYWHERE in the bundle the LLM saw:
    abstracts list, refs_selected list, or as evidence-of-record inside phenotype/allele/
    disease-model section text (rendered as '<FBrf...>'). Restricting to the abstracts
    list misclassifies legitimate evidence citations from phenotype rows as phantoms."""
    issues = []
    bundle_fbrfs = set()
    bundle_fbrfs |= {a["fbrf"] for a in bundle.get("abstracts", []) if a.get("fbrf")}
    bundle_fbrfs |= {r["id"] for r in bundle.get("refs_selected", []) if r.get("id")}
    # Pull FBrf tokens out of every rendered section block (evidence-of-record)
    for sec_txt in (bundle.get("sections") or {}).values():
        bundle_fbrfs |= set(re.findall(r"FBrf\d+", sec_txt or ""))
    for b in gene["bullets"]:
        for cit in b.get("citations", []):
            if cit.get("type") == "fbrf":
                fbrf = cit.get("value") or cit.get("id")
                if fbrf and fbrf not in bundle_fbrfs:
                    issues.append({
                        "code": "citation.phantom_fbrf",
                        "severity": "error",
                        "bullet_id": b["id"],
                        "detail": f"cites {fbrf} but it's not in the input bundle",
                    })
    return issues


def check_phenotype_grounding(gene: dict, bundle: dict) -> list:
    issues = []
    # full input text
    text = bundle.get("auto_summary", "") + " " \
        + " ".join(bundle.get("sections", {}).values()) + " " \
        + " ".join(a.get("abstract", "") or "" for a in bundle.get("abstracts", [])) + " " \
        + " ".join(o.get("summary", "") or "" for o in bundle.get("human_ortholog_data", [])) + " " \
        + " ".join(o.get("summary", "") or "" for o in bundle.get("mouse_ortholog_data", []))
    bundle_tokens = content_tokens(text)
    for b in gene["bullets"]:
        phen_tokens = content_tokens(b["phenotype"])
        overlap = phen_tokens & bundle_tokens
        # Threshold 2 (not 3) because tokenizer doesn't stem — "larvae" vs "larval" both
        # count as content words but won't overlap. Hard hallucinations show 0 overlap.
        if len(overlap) < 2:
            issues.append({
                "code": "phenotype.weak_input_grounding",
                "severity": "warn",
                "bullet_id": b["id"],
                "detail": f"phenotype shares only {len(overlap)} content words with input "
                          f"(threshold 2)",
            })
    return issues


def check_bullet_uniqueness(gene: dict) -> list:
    """Flag a bullet as near-duplicate only when (a) jaccard ≥ 0.75 AND
    (b) fewer than 3 distinguishing tokens between the two AND (c) the two
    bullets share the same category + direction. Earlier 0.60 threshold
    over-flagged templated disease_model bullets that differed only in
    disease name (e.g. retinitis pigmentosa 47 vs Oguchi disease 1)."""
    issues = []
    seen = []   # (id, tokens, category, direction)
    for b in gene["bullets"]:
        tokens = content_tokens(b["phenotype"])
        cat = b.get("category")
        direction = b.get("direction")
        for prev_id, prev_toks, prev_cat, prev_dir in seen:
            if not tokens or not prev_toks:
                continue
            if cat != prev_cat or direction != prev_dir:
                continue
            j = len(tokens & prev_toks) / len(tokens | prev_toks)
            if j < 0.75:
                continue
            distinguishing = len(tokens ^ prev_toks)
            if distinguishing >= 3:
                continue
            issues.append({
                "code": "bullet.near_duplicate",
                "severity": "warn",
                "bullet_id": b["id"],
                "detail": f"jaccard {j:.2f} vs {prev_id} (only {distinguishing} distinguishing tokens)",
            })
            break
        seen.append((b["id"], tokens, cat, direction))
    return issues


def check_confidence_distribution(gene: dict) -> list:
    issues = []
    bullets = gene["bullets"]
    n = len(bullets)
    if n == 0:
        return issues
    confs = [b.get("confidence") for b in bullets]
    n_high = confs.count("high")
    n_med = confs.count("medium")
    n_low = confs.count("low")
    n_null = sum(1 for c in confs if c is None)
    if n_null == n:
        issues.append({
            "code": "confidence.all_null",
            "severity": "warn",
            "detail": f"all {n} bullets missing confidence",
        })
    elif n_high / max(n - n_null, 1) > 0.95 and (n - n_null) >= 10:
        issues.append({
            "code": "confidence.over_confident",
            "severity": "info",
            "detail": f"{n_high}/{n - n_null} bullets are 'high' confidence (over 95%)",
        })
    return issues


def check_specificity_distribution(gene: dict) -> list:
    issues = []
    bullets = gene["bullets"]
    n = len(bullets)
    if n == 0:
        return issues
    specs = [b.get("text_specificity") for b in bullets]
    n_low = specs.count("low")
    if n >= 10 and n_low / n > 0.85:
        issues.append({
            "code": "specificity.too_low",
            "severity": "info",
            "detail": f"{n_low}/{n} bullets have low text_specificity",
        })
    return issues


def check_bullet_count_vs_tier(gene: dict, bundle: dict) -> list:
    """Bullet count tiers calibrated to observed distribution across 1700+ genes.
    Stub genes (no phenotype data) legitimately return 0 bullets — allow that.
    Codex/Opus tend to produce slightly more bullets than original 28-cap for
    well-studied genes — accept up to 35."""
    issues = []
    n_pubs = bundle.get("pubs_total", 0)
    n_bullets = len(gene["bullets"])
    # Stub gene (no phenotype data, no pubs of substance) → 0 bullets is correct
    n_phen_rows = len((bundle.get("sections") or {}).get("phenotypes_sub", "").splitlines())
    if n_bullets == 0 and n_phen_rows == 0:
        return issues
    if n_pubs >= 500:
        expected = (18, 36)
        tier = "A (>500 pubs)"
    elif n_pubs >= 50:
        expected = (5, 33)
        tier = "B (50-500 pubs)"
    else:
        expected = (0, 26)
        tier = "C (<50 pubs)"
    if not (expected[0] <= n_bullets <= expected[1]):
        issues.append({
            "code": "bullet_count.out_of_range",
            "severity": "warn",
            "detail": f"tier {tier} expects {expected[0]}-{expected[1]} bullets, got {n_bullets}",
        })
    return issues


def check_omim_consistency(gene: dict) -> list:
    """OMIM IDs in output should match what FlyBase bulk has for this gene."""
    issues = []
    # We trust the canonicalizer (which used disease_links_with_ortholog) so this check
    # mostly catches manual edits. Real value: surface coverage gaps.
    try:
        import enrich
        bulk = enrich._load_dmel_human_orthologs_disease().get(gene["fbgn"], [])
    except Exception:
        return issues
    bulk_omim = {d["omim_id"] for d in bulk if d.get("omim_id")}
    out_omim = {
        d["omim_id"]
        for d in (gene.get("cross_species", {}).get("human_disease_links", []) or [])
        if d.get("omim_id")
    }
    missed = bulk_omim - out_omim
    phantom = out_omim - bulk_omim
    if phantom:
        issues.append({
            "code": "omim.phantom",
            "severity": "error",
            "detail": f"output has OMIM IDs not in FlyBase bulk: {sorted(phantom)}",
        })
    if missed and bulk_omim:
        issues.append({
            "code": "omim.missed",
            "severity": "info",
            "detail": f"FlyBase bulk has {len(missed)} OMIM ID(s) not in output: {sorted(missed)[:5]}",
        })
    return issues


# ---------- score aggregator -----------------------------------------------

SCORE_PENALTIES = {
    "citation.phantom_fbrf":          25,   # real hallucination — hard penalty
    "phenotype.weak_input_grounding": 8,    # may be stemming-artifact, but still suspect
    "bullet.near_duplicate":          8,    # dup wastes a slot, may indicate model confusion
    "confidence.all_null":            20,   # schema drift — non-trivial, send to Opus
    "confidence.over_confident":      3,    # info → soft penalty (no discrimination signal lost)
    "specificity.too_low":            0,    # truly info-only (FlyBase pipe-format artifact)
    "bullet_count.out_of_range":      12,   # bigger penalty — likely missing major coverage
    "omim.phantom":                   25,   # phantom disease ID = real hallucination
    "omim.missed":                    0,    # info-only (coverage hint, not error)
    "cohort_outlier":                 10,   # statistical anomaly
}

# Thresholds (post-rebalance):
#   ≥ 90 → ACCEPT (no audit)
#   70-89 → Tier-2 Opus audit
#   < 70  → re-distill via two-pass harness
# Logic: any single non-trivial issue should drop score below 90 → trigger audit.
TIER2_THRESHOLD = 90
REDISTILL_THRESHOLD = 70


def score(issues: list) -> int:
    s = 100
    for iss in issues:
        s -= SCORE_PENALTIES.get(iss["code"], 0)
    return max(0, s)


def check_one(fbgn: str) -> dict:
    gene = load_gene(fbgn)
    try:
        bundle = load_bundle(fbgn)
    except FileNotFoundError:
        # legacy non-sharded path may differ; try alt
        bundle = {"abstracts": [], "sections": {}, "auto_summary": "",
                  "human_ortholog_data": [], "mouse_ortholog_data": [],
                  "pubs_total": gene.get("source", {}).get("n_pubs_total", 0)}
    issues = []
    issues += check_citations(gene, bundle)
    issues += check_phenotype_grounding(gene, bundle)
    issues += check_bullet_uniqueness(gene)
    issues += check_confidence_distribution(gene)
    issues += check_specificity_distribution(gene)
    issues += check_bullet_count_vs_tier(gene, bundle)
    issues += check_omim_consistency(gene)
    return {
        "fbgn": fbgn,
        "symbol": gene["symbol"],
        "n_bullets": len(gene["bullets"]),
        "n_pubs_total": bundle.get("pubs_total", gene.get("source", {}).get("n_pubs_total", 0)),
        "qa_score": score(issues),
        "n_issues": len(issues),
        "issues": issues,
    }


# ---------- cohort outliers ------------------------------------------------

def add_cohort_outliers(reports: list) -> None:
    if len(reports) < 5:
        return
    bullet_counts = [r["n_bullets"] for r in reports]
    median_b = statistics.median(bullet_counts)
    stdev_b = statistics.stdev(bullet_counts) if len(bullet_counts) > 1 else 0
    for r in reports:
        if stdev_b > 0:
            z = abs(r["n_bullets"] - median_b) / stdev_b
            if z > 3:
                r["issues"].append({
                    "code": "cohort_outlier",
                    "severity": "warn",
                    "detail": f"bullet_count z-score {z:.1f} vs cohort median {median_b}",
                })
                r["qa_score"] = max(0, r["qa_score"] - 6)


# ---------- commands -------------------------------------------------------

def cmd_tier1(args):
    QA_DIR.mkdir(parents=True, exist_ok=True)
    if args.fbgn:
        targets = [args.fbgn]
    else:
        targets = sorted(f.stem for f in GENES_DIR.glob("FBgn*.json"))
    reports = []
    for fbgn in targets:
        try:
            r = check_one(fbgn)
            reports.append(r)
        except Exception as e:
            reports.append({"fbgn": fbgn, "error": str(e)})
    add_cohort_outliers(reports)

    out = QA_DIR / "tier1_report.jsonl"
    with out.open("w") as f:
        for r in reports:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    # console
    print(f"checked {len(reports)} genes → {out}")
    print()
    print(f"{'fbgn':14} {'sym':8} {'score':>5} {'bullets':>7} {'pubs':>5}  flags")
    for r in sorted(reports, key=lambda x: x.get("qa_score", -1)):
        if "error" in r:
            print(f"{r['fbgn']:14} {'?':8} {'ERR':>5} {'-':>7} {'-':>5}  {r['error'][:80]}")
            continue
        codes = sorted({i["code"] for i in r["issues"]})
        print(f"{r['fbgn']:14} {r['symbol']:8} {r['qa_score']:>5} "
              f"{r['n_bullets']:>7} {r['n_pubs_total']:>5}  {' '.join(codes) or 'clean'}")

    # summary md
    sm = QA_DIR / "tier1_summary.md"
    with sm.open("w") as f:
        f.write(f"# Tier-1 QA summary — {len(reports)} genes\n\n")
        f.write("## Score distribution\n\n")
        scores = [r.get("qa_score", 0) for r in reports if "qa_score" in r]
        if scores:
            f.write(f"- median: {statistics.median(scores)}\n")
            f.write(f"- mean:   {statistics.mean(scores):.1f}\n")
            f.write(f"- min:    {min(scores)}\n")
            f.write(f"- max:    {max(scores)}\n")
            f.write(f"- ≥{TIER2_THRESHOLD}:  {sum(1 for s in scores if s >= TIER2_THRESHOLD)} ACCEPT\n")
            f.write(f"- {REDISTILL_THRESHOLD}-{TIER2_THRESHOLD-1}:  {sum(1 for s in scores if REDISTILL_THRESHOLD <= s < TIER2_THRESHOLD)} → Tier-2 Opus audit\n")
            f.write(f"- <{REDISTILL_THRESHOLD}:   {sum(1 for s in scores if s < REDISTILL_THRESHOLD)} → re-distill\n")
        f.write("\n## Most-frequent issue codes\n\n")
        c = Counter()
        for r in reports:
            for i in r.get("issues", []):
                c[i["code"]] += 1
        for code, n in c.most_common():
            f.write(f"- `{code}`: {n}\n")
    print(f"\nwrote summary {sm}")


def cmd_sample(args):
    """Produce stratified sample for Tier-2 Opus audit."""
    QA_DIR.mkdir(parents=True, exist_ok=True)
    report_path = QA_DIR / "tier1_report.jsonl"
    if not report_path.exists():
        sys.exit("run tier1 first")
    rows = [json.loads(l) for l in report_path.open() if l.strip()]

    # tier the gene by pub count
    def tier_of(r):
        n = r.get("n_pubs_total", 0)
        if n >= 500: return "A"
        if n >= 50:  return "B"
        return "C"

    by_tier = {"A": [], "B": [], "C": []}
    for r in rows:
        if "error" not in r:
            by_tier[tier_of(r)].append(r)

    target = {"A": int(args.frac_a * len(by_tier["A"])),
              "B": int(args.frac_b * len(by_tier["B"])),
              "C": int(args.frac_c * len(by_tier["C"]))}

    import random
    random.seed(42)
    picks = []
    for t in ("A", "B", "C"):
        n = max(1, target[t]) if by_tier[t] else 0
        n = min(n, len(by_tier[t]))
        picks.extend(random.sample(by_tier[t], n))

    # always include low-scoring ones
    low = [r for r in rows if "qa_score" in r and r["qa_score"] < args.flag_threshold]
    seen = {r["fbgn"] for r in picks}
    picks.extend([r for r in low if r["fbgn"] not in seen])

    out = QA_DIR / "tier2_audit_sample.jsonl"
    with out.open("w") as f:
        for r in picks:
            f.write(json.dumps({
                "fbgn": r["fbgn"], "symbol": r.get("symbol"),
                "tier": tier_of(r), "qa_score": r.get("qa_score"),
                "reason": "low_score" if r in low else "stratified_sample",
            }) + "\n")
    print(f"sampled {len(picks)} genes for Tier-2 audit → {out}")
    print(f"  by tier: A={target['A']}, B={target['B']}, C={target['C']}, low={len(low)}")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("tier1", help="run automated checks on every gene")
    p.add_argument("fbgn", nargs="?", help="single gene FBgn, else all")
    p.set_defaults(fn=cmd_tier1)
    p = sub.add_parser("sample", help="produce Tier-2 audit sample from Tier-1 results")
    p.add_argument("--frac-a", type=float, default=0.03)
    p.add_argument("--frac-b", type=float, default=0.012)
    p.add_argument("--frac-c", type=float, default=0.006)
    p.add_argument("--flag-threshold", type=int, default=TIER2_THRESHOLD)
    p.set_defaults(fn=cmd_sample)
    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
