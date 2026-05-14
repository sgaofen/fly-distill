"""Per-gene audit of GLM distillation output against source bundle.

Checks each bullet's evidence pointer can be resolved back to the input.
Flags possible hallucinations, missing-citation issues, and coverage gaps.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(fbgn: str):
    bundle = json.loads((ROOT / "data" / "cache" / fbgn / "bundle.json").read_text())
    bullets = json.loads((ROOT / "output" / fbgn / "bullets.json").read_text())
    return bundle, bullets


def full_input_text(bundle: dict) -> str:
    """Concatenate everything the LLM saw, for substring lookups."""
    parts = [bundle.get("auto_summary", "")]
    parts.extend(bundle.get("sections", {}).values())
    for a in bundle.get("abstracts", []):
        parts.append(a.get("title", ""))
        parts.append(a.get("abstract", ""))
    for o in bundle.get("human_ortholog_data", []) + bundle.get("mouse_ortholog_data", []):
        parts.append(o.get("summary", "") or "")
        parts.append(o.get("name", "") or "")
    return "\n".join(parts).lower()


def fbrfs_in_bundle(bundle: dict) -> set:
    return {a["fbrf"] for a in bundle.get("abstracts", []) if a.get("fbrf")}


def section_ids_in_bundle(bundle: dict) -> set:
    return {sid for sid, t in bundle.get("sections", {}).items() if t.strip()}


def audit_one(fbgn: str) -> dict:
    bundle, b = load(fbgn)
    text = full_input_text(bundle)
    fbrfs = fbrfs_in_bundle(bundle)
    sections = section_ids_in_bundle(bundle)

    bullets = b.get("bullets", [])
    report = {
        "fbgn": fbgn,
        "symbol": b.get("symbol"),
        "n_bullets": len(bullets),
        "categories": sorted({x.get("category") for x in bullets}),
        "confidence_counts": {},
        "direction_counts": {},
        "issues": [],
    }

    for x in bullets:
        c = x.get("confidence") or "missing"
        report["confidence_counts"][c] = report["confidence_counts"].get(c, 0) + 1
        d = x.get("direction") or "missing"
        report["direction_counts"][d] = report["direction_counts"].get(d, 0) + 1
    # Flag entire-gene schema drift (all bullets missing same key)
    n = len(bullets)
    for key in ("confidence", "direction", "evidence", "phenotype"):
        missing = sum(1 for x in bullets if not x.get(key))
        if missing == n and n > 0:
            report["issues"].append({
                "bullet": "all",
                "kind": "schema_drift",
                "detail": f"every bullet missing '{key}' field",
            })

    # Per-bullet evidence check
    for i, x in enumerate(bullets, 1):
        ev = x.get("evidence", "") or ""
        phen = x.get("phenotype", "") or ""

        # 1. Each FBrf cited in evidence must actually be in the bundle's abstract set
        for fbrf_cited in re.findall(r"FBrf\d{7}", ev):
            if fbrf_cited not in fbrfs:
                report["issues"].append({
                    "bullet": i,
                    "kind": "phantom_fbrf",
                    "detail": f"cited {fbrf_cited} not in input abstracts",
                    "phenotype": phen[:120],
                })

        # 2. Each section name cited must exist (have content) in the bundle
        for sid_cited in re.findall(r"\b([a-z_]+_sub|CURATOR NOTES|phenotypes_sub|hdm_sub)\b", ev):
            # normalize CURATOR NOTES → other_comments_sub
            mapped = "other_comments_sub" if sid_cited == "CURATOR NOTES" else sid_cited
            if mapped.endswith("_sub") and mapped not in sections:
                report["issues"].append({
                    "bullet": i,
                    "kind": "phantom_section",
                    "detail": f"cited section {sid_cited} not in input",
                    "phenotype": phen[:120],
                })

        # 3. Verbatim support — multiple fallback checks because the FlyBase HTML text
        # has lots of pipe-separated curator tags (e.g. 'paralytic | adult stage | heat
        # sensitive') and the model often quotes them in that exact pipe-separated form.
        norm_text = re.sub(r"[^a-z0-9 ]", " ", text)
        norm_text = re.sub(r"\s+", " ", norm_text)
        nospace_text = re.sub(r"[^a-z0-9]", "", text)
        for q in re.findall(r"'([^']{15,300})'|\"([^\"]{15,300})\"", ev):
            quoted = (q[0] or q[1]).strip().lower()
            # First split on ellipses; within each chunk also split on FlyBase-style
            # separators ( |, /, ;, , and ' and ') so we check each token independently.
            top_chunks = re.split(r"\.{2,}|…", quoted)
            tokens = []
            for c in top_chunks:
                for t in re.split(r"\s*(?:\||/|;|\sand\s)\s*", c):
                    t = re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", t)).strip()
                    if len(t) >= 8:
                        tokens.append(t)
            if not tokens:
                continue
            missing = []
            for tok in tokens:
                tok_nospace = re.sub(r"[^a-z0-9]", "", tok)
                if tok in norm_text or tok_nospace in nospace_text:
                    continue
                # last resort: at least 80% of word tokens present in input
                words = [w for w in tok.split() if len(w) >= 3]
                if words and sum(1 for w in words if w in norm_text) / len(words) >= 0.8:
                    continue
                missing.append(tok)
            if missing:
                report["issues"].append({
                    "bullet": i,
                    "kind": "quote_not_found",
                    "detail": f"token(s) not grounded in input: {missing[:3]}",
                    "phenotype": phen[:120],
                })

    # Cross-species sanity
    cs = b.get("cross_species") or {}
    for disease in cs.get("human_disease") or []:
        # Disease name should appear somewhere in hdm_sub or human ortholog data
        hdm = (bundle.get("sections", {}).get("hdm_sub", "") or "").lower()
        h_ortho_text = " ".join(o.get("summary", "") or "" for o in bundle.get("human_ortholog_data", [])).lower()
        # split disease name into significant tokens (skip stopwords)
        toks = [t for t in re.findall(r"[A-Za-z]{4,}", disease.lower())
                if t not in {"phase", "syndrome", "advanced", "type", "familial", "early", "late"}]
        if toks and not any(t in hdm or t in h_ortho_text for t in toks):
            report["issues"].append({
                "bullet": "cross_species",
                "kind": "disease_unsourced",
                "detail": f"human_disease '{disease}' has no token match in hdm_sub or human ortholog summaries",
            })

    report["n_issues"] = len(report["issues"])
    return report


def main():
    fbgns = sys.argv[1:] if len(sys.argv) > 1 else None
    if not fbgns:
        # all genes with output
        fbgns = sorted(d.name for d in (ROOT / "output").iterdir()
                       if d.is_dir() and (d / "bullets.json").exists())
    reports = [audit_one(f) for f in fbgns]
    out = ROOT / "output" / "audit_summary.json"
    out.write_text(json.dumps(reports, indent=2))
    print(f"audited {len(reports)} genes")
    for r in reports:
        flag = "OK" if r["n_issues"] == 0 else f"{r['n_issues']} ISSUES"
        print(f"  {r['fbgn']} {r['symbol']:10}  {r['n_bullets']:3} bullets  "
              f"{len(r['categories']):2} cats  {flag}")
        for iss in r["issues"][:5]:
            print(f"     ! {iss['kind']:18} bullet {iss['bullet']}: {iss['detail'][:120]}")


if __name__ == "__main__":
    main()
