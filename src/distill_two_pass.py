"""Two-pass distillation for complex genes (GPT review #32; user requested for high-pub genes).

Pass 1: standard distill → initial bullets
Pass 2: critique-and-refine using `prompts/distill_critique.md` — sees pass-1 output + same input
        bundle, fixes coverage gaps, citation errors, hallucinations, field completeness.

When to use: any gene with >50 representative refs or >50 KB input bundle. Single-pass works
fine for sparse genes; two-pass overhead (~2x cost, ~2x latency) isn't worth it.

Decision (configurable):
  - complex if n_pubs_total >= 50 OR n_abstracts_used >= 15 OR section_chars_total >= 50_000
  - else: single pass

Output: same bullets.json schema. Marked with model.harness='claude_two_pass'.
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from distill_via_claude import call_claude_headless, build_user_prompt, strip_fences, next_key, KEYS, MODEL
from distill import build_input_message


def _load_env():
    out = {}
    p = ROOT / ".env"
    if p.exists():
        for line in p.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                out[k.strip()] = v.strip()
    return out


def is_complex(bundle: dict) -> bool:
    n_pubs = bundle.get("pubs_total", 0)
    n_abs = sum(1 for a in bundle.get("abstracts", []) if a.get("abstract"))
    sections = bundle.get("sections", {})
    section_chars = sum(len(v) for v in sections.values())
    return n_pubs >= 50 or n_abs >= 15 or section_chars >= 50_000


def pass1(fbgn: str, bundle: dict) -> tuple[dict, dict]:
    """Use the existing distill_via_claude.build_user_prompt → call_claude_headless."""
    prompt = build_user_prompt(bundle)
    key = next_key()
    t0 = time.time()
    wrapper = call_claude_headless(prompt, key)
    text = wrapper.get("result", "")
    try:
        parsed = json.loads(strip_fences(text))
    except Exception:
        parsed = None
    return parsed, {
        "elapsed_s": time.time() - t0,
        "usage": wrapper.get("usage", {}),
        "key_idx": (KEYS.index(key) if key in KEYS else -1),
    }


def pass2(fbgn: str, bundle: dict, pass1_output: dict) -> tuple[dict, dict]:
    """Critique-and-refine: feed pass1 output back along with the bundle."""
    system_prompt = (ROOT / "prompts" / "distill_critique.md").read_text()
    user_content = build_input_message(bundle)  # same bundle as pass 1
    full_prompt = (
        "SYSTEM INSTRUCTIONS — read first, do NOT echo back:\n"
        f"{system_prompt}\n\n"
        "================ END INSTRUCTIONS ================\n\n"
        "## INPUT BUNDLE (same as Pass 1)\n\n"
        f"{user_content}\n\n"
        "## PRIOR PASS JSON OUTPUT\n\n"
        f"```json\n{json.dumps(pass1_output, ensure_ascii=False, indent=2)}\n```\n\n"
        "Now produce the REFINED JSON. JSON only, no surrounding text."
    )
    key = next_key()
    t0 = time.time()
    wrapper = call_claude_headless(full_prompt, key)
    text = wrapper.get("result", "")
    try:
        parsed = json.loads(strip_fences(text))
    except Exception:
        parsed = None
    return parsed, {
        "elapsed_s": time.time() - t0,
        "usage": wrapper.get("usage", {}),
        "key_idx": (KEYS.index(key) if key in KEYS else -1),
    }


def distill_two_pass(fbgn: str, force: bool = False) -> dict:
    """Returns {parsed_ok, complex, pass1_meta, pass2_meta?}.  Writes bullets_twopass.json."""
    bundle = json.loads((ROOT / "data" / "cache" / fbgn / "bundle.json").read_text())
    complex_flag = force or is_complex(bundle)
    out_dir = ROOT / "output" / fbgn
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"  is_complex: {complex_flag} (pubs={bundle.get('pubs_total',0)}, "
          f"abstracts={sum(1 for a in bundle.get('abstracts',[]) if a.get('abstract'))}, "
          f"section_chars={sum(len(v) for v in bundle.get('sections',{}).values())})", flush=True)

    p1, m1 = pass1(fbgn, bundle)
    print(f"  pass 1: {m1['elapsed_s']:.1f}s  in={m1['usage'].get('input_tokens')} "
          f"out={m1['usage'].get('output_tokens')}  bullets={len(p1.get('bullets',[]) if p1 else [])}",
          flush=True)
    (out_dir / "pass1_raw.json").write_text(json.dumps(p1, indent=2, ensure_ascii=False))

    if not complex_flag:
        # single pass is enough
        (out_dir / "bullets_twopass.json").write_text(json.dumps(p1, indent=2, ensure_ascii=False))
        (out_dir / "request_meta_twopass.json").write_text(json.dumps({
            "model": MODEL, "harness": "claude_two_pass_skipped",
            "pass1": m1, "pass2_skipped_reason": "not complex enough",
        }, indent=2))
        return {"parsed_ok": p1 is not None, "complex": False, "pass1_meta": m1}

    p2, m2 = pass2(fbgn, bundle, p1 or {})
    print(f"  pass 2: {m2['elapsed_s']:.1f}s  in={m2['usage'].get('input_tokens')} "
          f"out={m2['usage'].get('output_tokens')}  bullets={len(p2.get('bullets',[]) if p2 else [])}",
          flush=True)
    (out_dir / "pass2_raw.json").write_text(json.dumps(p2, indent=2, ensure_ascii=False))

    final = p2 if p2 and p2.get("bullets") else p1
    (out_dir / "bullets_twopass.json").write_text(json.dumps(final, indent=2, ensure_ascii=False))
    (out_dir / "request_meta_twopass.json").write_text(json.dumps({
        "model": MODEL, "harness": "claude_two_pass",
        "pass1": m1, "pass2": m2,
    }, indent=2))
    return {"parsed_ok": final is not None, "complex": True,
            "pass1_meta": m1, "pass2_meta": m2,
            "pass1_n_bullets": len(p1.get("bullets",[]) if p1 else []),
            "pass2_n_bullets": len(p2.get("bullets",[]) if p2 else [])}


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("fbgn")
    ap.add_argument("--force", action="store_true", help="run pass-2 even if not deemed complex")
    args = ap.parse_args()
    print(f"two-pass distill: {args.fbgn}  model={MODEL}")
    r = distill_two_pass(args.fbgn, force=args.force)
    print(f"  done: {r}")


if __name__ == "__main__":
    main()
