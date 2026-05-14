"""End-to-end query demo: 'given these candidate FBgns and a target phenotype, rank them'.

This is the consumer side of the pipeline — the QTL-fine-mapping workflow. Two query modes:

  1. --keyword KEYWORD       quick string match over bullets (no LLM)
  2. --phenotype "..." --candidates FBgn1,FBgn2,...    GLM-semantic ranking (one API call)

Both work off the canonical /output/genes/*.json + /output/index/*.
"""
import argparse
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GENES_DIR = ROOT / "output" / "genes"
INDEX_DIR = ROOT / "output" / "index"


def load_env():
    out = {}
    p = ROOT / ".env"
    if p.exists():
        for line in p.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                out[k.strip()] = v.strip()
    return out


def load_gene(fbgn: str) -> dict:
    return json.loads((GENES_DIR / f"{fbgn}.json").read_text())


def keyword_search(kw: str, top: int = 20) -> list:
    """Naive substring match over bullets_flat.jsonl. Fast, no LLM."""
    kw_low = kw.lower()
    hits = []
    for line in (INDEX_DIR / "bullets_flat.jsonl").read_text().splitlines():
        rec = json.loads(line)
        text = f"{rec['phenotype']} {rec['evidence']}".lower()
        if kw_low in text:
            hits.append(rec)
    return hits[:top]


def glm_rank(phenotype: str, candidates: list[str]) -> dict:
    """One API call to GLM-5.1 — show it the candidate profiles, ask for ranked match."""
    env = load_env()
    api_key = env["ZAI_API_KEY"]
    base = env.get("ZAI_BASE_URL", "https://api.z.ai/api/anthropic")
    model = env.get("ZAI_MODEL", "glm-5.1")

    profiles = []
    for fbgn in candidates:
        try:
            g = load_gene(fbgn)
        except FileNotFoundError:
            profiles.append({"fbgn": fbgn, "error": "not distilled yet"})
            continue
        compact = {
            "fbgn": g["fbgn"],
            "symbol": g["symbol"],
            "snapshot": g["snapshot"],
            "cross_species": g["cross_species"],
            "bullets": [
                {"category": b["category"], "phenotype": b["phenotype"], "confidence": b["confidence"]}
                for b in g["bullets"]
            ],
        }
        profiles.append(compact)

    system = (
        "You are helping rank Drosophila candidate genes against a target QTL phenotype. "
        "For each candidate, give a relatedness verdict: 'strong', 'plausible', 'weak', 'unrelated'. "
        "Cite the specific bullet(s) that support your verdict. Output strict JSON: "
        '{"ranking":[{"fbgn":"...","verdict":"...","reasoning":"...","supporting_bullets":["..."]}]}. '
        "Order by likelihood of being the QTL's causal gene."
    )
    user = f"## Target phenotype\n{phenotype}\n\n## Candidate gene profiles\n{json.dumps(profiles, ensure_ascii=False)}"

    body = json.dumps({
        "model": model, "max_tokens": 4000, "system": system,
        "messages": [{"role": "user", "content": user}],
    })
    proc = subprocess.run(
        ["/usr/bin/curl", "-sS", "--max-time", "180",
         "-H", f"x-api-key: {api_key}",
         "-H", "anthropic-version: 2023-06-01",
         "-H", "Content-Type: application/json",
         "-X", "POST", f"{base}/v1/messages", "-d", body],
        capture_output=True, text=True,
    )
    resp = json.loads(proc.stdout)
    text = "".join(c.get("text", "") for c in resp.get("content", []) if c.get("type") == "text")
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0]
    try:
        parsed = json.loads(text)
    except Exception:
        parsed = {"raw": text}
    return {
        "phenotype": phenotype,
        "candidates": candidates,
        "result": parsed,
        "usage": resp.get("usage"),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--keyword", help="substring search over bullets")
    ap.add_argument("--phenotype", help="target phenotype for GLM-semantic ranking")
    ap.add_argument("--candidates", help="comma-separated FBgn IDs for ranking")
    ap.add_argument("--top", type=int, default=20)
    args = ap.parse_args()

    if args.keyword:
        hits = keyword_search(args.keyword, args.top)
        print(f"# keyword '{args.keyword}' — {len(hits)} matching bullets")
        for h in hits:
            print(f"  [{h['symbol']:6}] [{h['category']:18}] {h['phenotype']}")
            print(f"          source: {h['evidence'][:120]}")
        return

    if args.phenotype and args.candidates:
        cands = [c.strip() for c in args.candidates.split(",") if c.strip()]
        out = glm_rank(args.phenotype, cands)
        print(json.dumps(out, indent=2, ensure_ascii=False))
        return

    ap.error("either --keyword OR (--phenotype + --candidates)")


if __name__ == "__main__":
    main()
