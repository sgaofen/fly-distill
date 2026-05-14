"""Call GLM-5.1 via z.ai Anthropic-compat endpoint to distill one gene's bundle into bullets.

Usage:
  python3 src/distill.py FBgn0003068
"""
import json
import os
import sys
import time
import urllib.request
from pathlib import Path


def load_env(path: Path) -> dict:
    out = {}
    if path.exists():
        for line in path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                out[k.strip()] = v.strip()
    return out


ROOT = Path(__file__).resolve().parents[1]
ENV = load_env(ROOT / ".env")
API_KEY = ENV.get("ZAI_API_KEY", os.environ.get("ZAI_API_KEY", ""))
BASE_URL = ENV.get("ZAI_BASE_URL", "https://api.z.ai/api/anthropic")
MODEL = ENV.get("ZAI_MODEL", "glm-5.1")

if not API_KEY:
    sys.exit("Missing ZAI_API_KEY in .env")


def build_input_message(bundle: dict) -> str:
    """Compact, structured representation of the bundle for the LLM."""
    lines = []
    lines.append(f"# GENE: {bundle['fbgn']}\n")
    lines.append(f"## AUTO SUMMARY\n{bundle['auto_summary']}\n")

    lines.append("## GENE ONTOLOGY (slim categories with annotation counts)")
    for dom, ribbon in bundle["go"].items():
        if not ribbon:
            continue
        names = ribbon.get("slim_names_order", [])
        rib = ribbon.get("ribbon", {})
        cats = []
        for n in names:
            count = 0
            for gid, rec in rib.items():
                if rec.get("slim_label") == n:
                    count = rec.get("count", 0)
                    break
            if count:
                cats.append(f"{n}({count})")
        lines.append(f"  {dom}: {', '.join(cats) if cats else '(none)'}")
    lines.append("")

    section_label = {
        "function": "FUNCTION",
        "phenotypes_sub": "PHENOTYPES (FlyBase curated)",
        "alleles_main_sub": "ALLELES",
        "hdm_sub": "HUMAN DISEASE MODELS (OMIM + experimental evidence)",
        "other_comments_sub": "CURATOR NOTES",
        "summary_genetic_interactions_sub": "GENETIC INTERACTIONS",
        "summary_physical_interactions_sub": "PHYSICAL INTERACTIONS",
        "pathways_sub": "PATHWAYS",
        "gene_class_sub": "GENE CLASS",
    }
    for sid, label in section_label.items():
        txt = bundle["sections"].get(sid, "").strip()
        if txt and len(txt) > 5:
            lines.append(f"## DATABASE 1 — DROSOPHILA / FlyBase :: {label}\n{txt}\n")

    # Cross-species orthologs
    h_orthos = bundle.get("human_ortholog_data") or []
    if h_orthos:
        lines.append("## DATABASE 2 — HUMAN ORTHOLOGS (via DIOPT + NCBI Gene/MyGene)")
        for o in h_orthos:
            sym = o.get("symbol") or "?"
            sc = f"{o.get('diopt_score','?')}/{o.get('diopt_max','?')}"
            name = o.get("name", "")
            summ = o.get("summary", "") or "(no NCBI summary available)"
            ent = o.get("entrez_id", "")
            lines.append(f"\n### Human ortholog: {sym} (DIOPT {sc}, Entrez {ent}) — {name}\n{summ}\n")

    m_orthos = bundle.get("mouse_ortholog_data") or []
    if m_orthos:
        lines.append("## DATABASE 3 — MOUSE ORTHOLOGS (via DIOPT + NCBI Gene/MyGene)")
        for o in m_orthos:
            sym = o.get("symbol") or "?"
            sc = f"{o.get('diopt_score','?')}/{o.get('diopt_max','?')}"
            name = o.get("name", "")
            summ = o.get("summary", "") or "(no NCBI summary available)"
            ent = o.get("entrez_id", "")
            lines.append(f"\n### Mouse ortholog: {sym} (DIOPT {sc}, Entrez {ent}) — {name}\n{summ}\n")

    lines.append("## REFERENCED ABSTRACTS (FlyBase-curated representative papers, fly-centric)")
    for a in bundle.get("abstracts", []):
        if not a.get("abstract"):
            continue
        lines.append(
            f"\n### {a['fbrf']} ({a.get('year', '?')}) — {a['type']}\n"
            f"**Title**: {a['title']}\n"
            f"**Abstract**: {a['abstract']}\n"
        )
    return "\n".join(lines)


def call_glm(system_prompt: str, user_content: str, max_tokens: int = 8000) -> dict:
    body = {
        "model": MODEL,
        "max_tokens": max_tokens,
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_content}],
    }
    req = urllib.request.Request(
        f"{BASE_URL}/v1/messages",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "x-api-key": API_KEY,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.loads(r.read())


def extract_text(resp: dict) -> str:
    return "".join(c.get("text", "") for c in resp.get("content", []) if c.get("type") == "text")


def strip_fences(s: str) -> str:
    s = s.strip()
    if s.startswith("```"):
        # remove ```json or ```
        s = s.split("\n", 1)[1] if "\n" in s else s
        if s.endswith("```"):
            s = s.rsplit("```", 1)[0]
    return s.strip()


def distill_one(fbgn: str) -> dict:
    cache = ROOT / "data" / "cache" / fbgn
    bundle = json.loads((cache / "bundle.json").read_text())
    system_prompt = (ROOT / "prompts" / "distill_system.md").read_text()
    user_content = build_input_message(bundle)

    in_chars = len(user_content)
    print(f"  input: {in_chars} chars (~{in_chars // 4} tokens)", flush=True)

    t0 = time.time()
    resp = call_glm(system_prompt, user_content)
    dt = time.time() - t0

    text = extract_text(resp)
    usage = resp.get("usage", {})
    print(
        f"  GLM response: {len(text)} chars, {dt:.1f}s, "
        f"input_tokens={usage.get('input_tokens')}, output_tokens={usage.get('output_tokens')}",
        flush=True,
    )

    out_dir = ROOT / "output" / fbgn
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "raw_response.txt").write_text(text)
    (out_dir / "request_meta.json").write_text(
        json.dumps(
            {
                "model": MODEL,
                "elapsed_s": dt,
                "input_chars": in_chars,
                "usage": usage,
            },
            indent=2,
        )
    )

    # try to parse JSON
    parsed = None
    try:
        parsed = json.loads(strip_fences(text))
    except Exception as e:
        print(f"  ! JSON parse failed: {e}", flush=True)

    if parsed:
        (out_dir / "bullets.json").write_text(json.dumps(parsed, indent=2))
        n = len(parsed.get("bullets", []))
        cats = {b.get("category") for b in parsed.get("bullets", [])}
        print(f"  parsed OK: {n} bullets across {len(cats)} categories", flush=True)
    return {"fbgn": fbgn, "parsed_ok": parsed is not None, "elapsed_s": dt, "usage": usage}


def main():
    fbgn = sys.argv[1] if len(sys.argv) > 1 else "FBgn0003068"
    print(f"distilling {fbgn} with {MODEL}")
    distill_one(fbgn)


if __name__ == "__main__":
    main()
