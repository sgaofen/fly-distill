"""Prompt experiment: re-distill 2 genes with two different prompts.
Compare quality on the SAME bundle to isolate prompt-vs-model effects.

Variants:
  - v1: current prompts/distill_system.md (comprehensive, ~6000 words)
  - v2: prompts/distill_system_v2.md (tightened, top-priority rules first)

For each gene:
  - run both variants
  - tier-1 check on both outputs
  - report deltas
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from distill_via_claude import call_claude_headless, build_user_prompt, strip_fences, next_key, MODEL
from distill import build_input_message
from qa import check_one as tier1_check
from canonicalize import canonicalize_one


def distill_with_prompt(fbgn: str, prompt_path: Path) -> dict:
    """Run distillation with a specific system prompt; return raw JSON."""
    bundle = json.loads((ROOT / "data" / "cache" / fbgn / "bundle.json").read_text())
    system_prompt = prompt_path.read_text()
    user_content = build_input_message(bundle)
    full_prompt = (
        f"SYSTEM INSTRUCTIONS:\n{system_prompt}\n\n"
        f"================ END INSTRUCTIONS ================\n\n"
        f"{user_content}\n\nProduce the JSON object now."
    )
    t0 = time.time()
    wrapper = call_claude_headless(full_prompt, next_key())
    dt = time.time() - t0
    text = wrapper.get("result", "")
    try:
        parsed = json.loads(strip_fences(text))
    except Exception:
        parsed = None
    return {
        "parsed": parsed,
        "elapsed_s": round(dt, 1),
        "usage": wrapper.get("usage", {}),
        "raw_text": text,
    }


def evaluate(fbgn: str, raw: dict, label: str) -> dict:
    """Write to a temp slot, canonicalize, tier-1 check. Returns metrics."""
    if not raw["parsed"]:
        return {"label": label, "parse_failed": True}
    # write to bullets.json + request_meta.json so canonicalize can read
    out_dir = ROOT / "output" / fbgn
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"bullets_{label}.json").write_text(json.dumps(raw["parsed"], indent=2, ensure_ascii=False))
    # save current bullets.json, swap in this one for canonicalize
    canon_in = out_dir / "bullets.json"
    canon_meta = out_dir / "request_meta.json"
    backup = None
    if canon_in.exists():
        backup = canon_in.read_text()
    canon_in.write_text(json.dumps(raw["parsed"], indent=2, ensure_ascii=False))
    canon_meta.write_text(json.dumps({
        "model": MODEL, "usage": raw["usage"],
        "harness": f"experiment_{label}",
    }, indent=2))
    try:
        canon = canonicalize_one(fbgn)
        tier1 = tier1_check(fbgn)
    finally:
        # restore original bullets.json
        if backup is not None:
            canon_in.write_text(backup)

    n_bullets = len(raw["parsed"].get("bullets", []))
    n_null_conf = sum(
        1 for b in raw["parsed"].get("bullets", [])
        if not b.get("confidence")
    )
    n_categories = len({b.get("category") for b in raw["parsed"].get("bullets", [])})
    return {
        "label": label,
        "elapsed_s": raw["elapsed_s"],
        "n_bullets": n_bullets,
        "n_null_confidence": n_null_conf,
        "n_categories": n_categories,
        "tier1_score": tier1["qa_score"],
        "tier1_issue_codes": sorted({i["code"] for i in tier1["issues"]}),
        "lint_codes": sorted({l["code"] for l in canon["_lint"]}),
        "in_tok": raw["usage"].get("input_tokens"),
        "out_tok": raw["usage"].get("output_tokens"),
    }


def main():
    targets = sys.argv[1:] if len(sys.argv) > 1 else ["FBgn0000527", "FBgn0004647"]
    results = []
    for fbgn in targets:
        print(f"\n===== {fbgn} =====")
        for label, prompt_path in [
            ("v1_baseline", ROOT / "prompts" / "distill_system.md"),
            ("v2_tightened", ROOT / "prompts" / "distill_system_v2.md"),
        ]:
            print(f"  running {label}...")
            raw = distill_with_prompt(fbgn, prompt_path)
            r = evaluate(fbgn, raw, label)
            r["fbgn"] = fbgn
            results.append(r)
            print(f"    bullets={r['n_bullets']}  null_conf={r.get('n_null_confidence')}  "
                  f"tier1={r.get('tier1_score')}  lint={r.get('lint_codes')}  "
                  f"t={r.get('elapsed_s')}s")

    out = ROOT / "output" / "qa" / "prompt_experiment.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, indent=2))
    print(f"\nwrote {out}")
    # tabular summary
    print(f"\n{'fbgn':14} {'prompt':14} {'bullets':>7} {'null_conf':>9} {'tier1':>5} {'cats':>4}")
    for r in results:
        if r.get("parse_failed"):
            print(f"{r['fbgn']:14} {r['label']:14} PARSE FAILED")
            continue
        print(f"{r['fbgn']:14} {r['label']:14} {r['n_bullets']:>7} "
              f"{r['n_null_confidence']:>9} {r['tier1_score']:>5} {r['n_categories']:>4}")


if __name__ == "__main__":
    main()
