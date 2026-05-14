"""Tier-2 Opus audit — uses Max 20x subscription via Claude Code headless (OAuth-routed,
NOT z.ai-routed).

For each gene in the audit sample, we hand Opus 4.7:
  - the canonical distilled JSON output
  - the input bundle that was distilled from
  - an audit prompt asking for hallucinations, missed phenotypes, calibration issues

Opus returns a structured audit JSON. We aggregate into a final report.

Cost: 0 marginal (Max 20x quota); ~2-5 calls per gene budget; ~30 min wall-clock for
~50 genes at 10-concurrent.
"""
import argparse
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GENES_DIR = ROOT / "output" / "genes"
BUNDLES = ROOT / "data" / "cache"
QA_DIR = ROOT / "output" / "qa"
PROMPT_PATH = ROOT / "prompts" / "tier2_audit.md"


def load_gene_and_bundle(fbgn: str) -> tuple[dict, dict]:
    gene = json.loads((GENES_DIR / f"{fbgn}.json").read_text())
    bundle = json.loads((BUNDLES / fbgn / "bundle.json").read_text())
    return gene, bundle


def compact_bundle(bundle: dict, max_abstract_chars: int = 1500) -> dict:
    """Trim bundle for audit prompt — keep key signal, drop long-tail to control input size."""
    return {
        "auto_summary": bundle.get("auto_summary", ""),
        "sections": {
            k: v for k, v in bundle.get("sections", {}).items()
            if v.strip() and k in {
                "phenotypes_sub", "alleles_main_sub", "hdm_sub",
                "other_comments_sub", "function", "gene_class_sub",
                "summary_genetic_interactions_sub", "pathways_sub",
                "human_orthologs_sub", "mod_orthologs_sub",
            }
        },
        "abstracts": [
            {
                "fbrf": a["fbrf"],
                "title": a.get("title", ""),
                "abstract": (a.get("abstract", "") or "")[:max_abstract_chars],
            }
            for a in bundle.get("abstracts", []) if a.get("abstract")
        ],
        "human_orthologs": [
            {"symbol": o["symbol"], "diopt_score": o["diopt_score"], "summary": (o.get("summary", "") or "")[:600]}
            for o in bundle.get("human_ortholog_data", [])
        ],
        "mouse_orthologs": [
            {"symbol": o["symbol"], "diopt_score": o["diopt_score"], "summary": (o.get("summary", "") or "")[:600]}
            for o in bundle.get("mouse_ortholog_data", [])
        ],
    }


def build_audit_prompt(gene: dict, bundle: dict) -> str:
    """Combine system prompt + gene + bundle into one user message."""
    system = PROMPT_PATH.read_text()
    bundle_compact = compact_bundle(bundle)
    return (
        "SYSTEM INSTRUCTIONS — read first, do NOT echo back:\n"
        f"{system}\n\n"
        "================ END INSTRUCTIONS ================\n\n"
        f"## GENE PROFILE TO AUDIT ({gene['fbgn']} / {gene['symbol']})\n\n"
        f"```json\n{json.dumps(gene, ensure_ascii=False, indent=2)}\n```\n\n"
        "## INPUT BUNDLE (what the distiller saw)\n\n"
        f"```json\n{json.dumps(bundle_compact, ensure_ascii=False, indent=2)}\n```\n\n"
        "Produce the audit JSON now."
    )


def _load_env_file():
    out = {}
    p = ROOT / ".env"
    if p.exists():
        for line in p.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                out[k.strip()] = v.strip()
    return out


def call_auditor(prompt: str, model: str = "glm-5.1", timeout_s: int = 600,
                 audit_key_idx: int = 1) -> dict:
    """Call Claude Code headless. Routes via z.ai if model starts with 'glm-' (uses
    your second API key by default for independence from distillation pass).
    For Opus / Sonnet, set ANTHROPIC_API_KEY env var with an api.anthropic.com key.

    The 'glm-5.1 audits glm-5.1' pattern is acceptable because:
      - Different prompt (criticism vs creation)
      - We can use a different API key → independent session context
      - The auditor sees both gene OUTPUT and INPUT bundle, giving it strict checking material
    For maximum cross-model independence, upgrade to Opus/Sonnet by setting an
    Anthropic API key.
    """
    env_file = _load_env_file()
    env = {k: v for k, v in os.environ.items()
           if k not in {"ANTHROPIC_BASE_URL", "ANTHROPIC_AUTH_TOKEN",
                        "ANTHROPIC_DEFAULT_OPUS_MODEL",
                        "ANTHROPIC_DEFAULT_SONNET_MODEL",
                        "ANTHROPIC_DEFAULT_HAIKU_MODEL",
                        "CLAUDE_CONFIG_DIR"}}
    env["CLAUDE_CONFIG_DIR"] = str(Path.home() / ".glm-fly-distill-audit")

    if model.startswith("glm-"):
        # route to z.ai with the second key (different from distill pass key #0)
        all_keys = [k.strip() for k in env_file.get(
            "ZAI_API_KEYS", env_file.get("ZAI_API_KEY", "")
        ).split(",") if k.strip()]
        if not all_keys:
            return {"error": "no ZAI keys in .env"}
        key = all_keys[audit_key_idx % len(all_keys)]
        env["ANTHROPIC_BASE_URL"] = env_file.get("ZAI_BASE_URL", "https://api.z.ai/api/anthropic")
        env["ANTHROPIC_AUTH_TOKEN"] = key
        env["ANTHROPIC_DEFAULT_OPUS_MODEL"] = model
        env["ANTHROPIC_DEFAULT_SONNET_MODEL"] = model
        env["ANTHROPIC_DEFAULT_HAIKU_MODEL"] = model
    else:
        # claude-opus-* / claude-sonnet-* etc — needs Anthropic API key
        api_key = os.environ.get("ANTHROPIC_API_KEY") or env_file.get("ANTHROPIC_API_KEY")
        if not api_key:
            return {"error": "ANTHROPIC_API_KEY not set; cannot use Opus/Sonnet. "
                             "Either set the env var, or use --model glm-5.1 for now."}
        env["ANTHROPIC_AUTH_TOKEN"] = api_key

    proc = subprocess.run(
        ["claude", "--print", "--model", model, "--output-format", "json",
         "--permission-mode", "bypassPermissions"],
        input=prompt, env=env, capture_output=True, text=True, timeout=timeout_s,
    )
    if proc.returncode != 0:
        return {"error": f"claude exit {proc.returncode}: {proc.stderr[:500]}"}
    return json.loads(proc.stdout)


def strip_fences(s: str) -> str:
    s = s.strip()
    if s.startswith("```"):
        s = s.split("\n", 1)[1] if "\n" in s else s
        if s.endswith("```"):
            s = s.rsplit("```", 1)[0]
    return s.strip()


def audit_one(fbgn: str, model: str = "glm-5.1") -> dict:
    try:
        gene, bundle = load_gene_and_bundle(fbgn)
    except FileNotFoundError as e:
        return {"fbgn": fbgn, "error": f"missing: {e}"}
    prompt = build_audit_prompt(gene, bundle)
    in_chars = len(prompt)
    t0 = time.time()
    wrapper = call_auditor(prompt, model=model)
    dt = time.time() - t0
    if "error" in wrapper:
        return {"fbgn": fbgn, "error": wrapper["error"], "elapsed_s": dt}
    text = wrapper.get("result", "")
    try:
        audit = json.loads(strip_fences(text))
    except Exception as e:
        audit = {"parse_error": str(e), "raw": text[:1000]}
    return {
        "fbgn": fbgn,
        "symbol": gene["symbol"],
        "elapsed_s": round(dt, 1),
        "input_chars": in_chars,
        "model": model,
        "usage": wrapper.get("usage", {}),
        "audit": audit,
    }


def cmd_run(args):
    QA_DIR.mkdir(parents=True, exist_ok=True)
    if args.fbgn:
        targets = [args.fbgn]
    else:
        sample_path = QA_DIR / "tier2_audit_sample.jsonl"
        if not sample_path.exists():
            sys.exit("run `python3 src/qa.py sample` first")
        targets = [json.loads(l)["fbgn"] for l in sample_path.open() if l.strip()]

    print(f"auditing {len(targets)} gene(s) with {args.model}")
    out_path = QA_DIR / "tier2_audit_results.jsonl"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # serial or parallel
    if args.workers == 1:
        for fbgn in targets:
            print(f"  auditing {fbgn}...", flush=True)
            r = audit_one(fbgn, model=args.model)
            print(f"    done {fbgn}: verdict={r.get('audit', {}).get('verdict', '?')} "
                  f"t={r.get('elapsed_s', 0)}s", flush=True)
            with out_path.open("a") as f:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
    else:
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = {pool.submit(audit_one, fbgn, args.model): fbgn for fbgn in targets}
            for fut in as_completed(futures):
                r = fut.result()
                print(f"  done {r['fbgn']}: verdict={r.get('audit', {}).get('verdict', '?')} "
                      f"t={r.get('elapsed_s', 0)}s", flush=True)
                with out_path.open("a") as f:
                    f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"\nwrote {out_path}")


def cmd_report(args):
    path = QA_DIR / "tier2_audit_results.jsonl"
    if not path.exists():
        sys.exit("no audit results yet")
    rows = [json.loads(l) for l in path.open() if l.strip()]
    print(f"# Tier-2 Opus audit summary — {len(rows)} genes\n")
    verdicts = {}
    for r in rows:
        v = r.get("audit", {}).get("verdict", "error")
        verdicts[v] = verdicts.get(v, 0) + 1
    print("## Verdict distribution\n")
    for v, n in sorted(verdicts.items()):
        print(f"  - {v}: {n}")
    print()
    print(f"{'fbgn':14} {'sym':8} {'verdict':12} {'comp':>4} {'acc':>4} {'cit':>4} {'halluc':>6} {'miss':>4}")
    for r in rows:
        a = r.get("audit", {})
        print(f"{r['fbgn']:14} {r.get('symbol','?'):8} "
              f"{a.get('verdict','?'):12} "
              f"{a.get('completeness_score','-'):>4} {a.get('accuracy_score','-'):>4} "
              f"{a.get('citation_score','-'):>4} "
              f"{len(a.get('hallucinations',[])):>6} {len(a.get('missed_phenotypes',[])):>4}")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("run")
    p.add_argument("--model", default="glm-5.1",
                   help="glm-5.1 (default, via z.ai) | claude-opus-4-7 (requires ANTHROPIC_API_KEY)")
    p.add_argument("--workers", type=int, default=1)
    p.add_argument("fbgn", nargs="?", help="single gene to audit (else uses sample file)")
    p.set_defaults(fn=cmd_run)
    p = sub.add_parser("report")
    p.set_defaults(fn=cmd_report)
    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
