"""Use MiMo to write LOW-CONFIDENCE inference bullets for stub genes — fly genes
with ≤3 verbatim FlyBase bullets BUT with rich mouse/human ortholog phenotype
context (MGI MP terms + HPO terms) attached in v1.2.

Rules enforced architecturally:
  - Each new bullet must have confidence="low"
  - Each new bullet's evidence_text MUST start with "INFERENCE from mouse|human ortholog"
    and quote a verbatim MGI/HPO term from the bundle
  - Each new bullet gets a new field `source: "ortholog_inference"` so it's
    distinguishable from verbatim FlyBase bullets
  - Each new bullet's id prefix is "inf:" not "FBgn:b"
  - The model is told the fly side has no direct evidence for these claims and
    must NOT invent fly experiments

Usage:
  GEMINI_EMBEDDING_API_KEY=... python -m flyatlas.enrich_stub_inference \
    --in /tmp/stub_genes_to_enrich.txt
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import re
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


INFERENCE_PROMPT = """You are predicting *likely* Drosophila phenotypes for a gene with limited fly literature, based STRICTLY on its mouse and human ortholog phenotype data. This is INFERENCE, not verbatim curation.

HARD RULES:
1. Output JSON only: {"bullets": [...]}. No other text.
2. Each bullet's "confidence" MUST be "low" (these are inferences, not curated facts).
3. Each bullet's "direction" should be "loss_of_function" when the inference is from knockout/mutant data, or "unknown" otherwise.
4. Each bullet's "evidence_text" MUST start with "INFERENCE from mouse|human ortholog <symbol>: " followed by a VERBATIM quote of the MP/HPO term and its definition (if available) from the ortholog data provided. Do NOT invent fly experiments. Do NOT cite FlyBase phenotypes_sub or fly papers in evidence — those are zero for this gene.
5. Aim for 3-5 bullets max. Skip if ortholog data is too thin to infer cleanly.
6. Each bullet's "category" must be one of: behavior, morphology, lifespan_aging, development, reproduction, metabolism, immune, sensory_neural, stress_response, disease_model, expression_pattern, other.
7. Each bullet must have a new field "source": "ortholog_inference".
8. phenotype field: write a brief organism-level prediction for fly, framed as "predicted" or "may". Examples: "Predicted to affect bone-like cuticle structure based on mouse Irs1 KO". Never assert as fact.

CONTEXT (fly gene info + ortholog phenotype data):
"""


def load_key() -> str:
    p = ROOT / ".env"
    if p.exists():
        for line in p.read_text().splitlines():
            if line.startswith("GEMINI_EMBEDDING_API_KEY="):
                return line.split("=", 1)[1].strip()
            if line.startswith("MIMO_API_KEY="):
                return line.split("=", 1)[1].strip()
    raise SystemExit("MIMO_API_KEY missing from .env")


def build_inference_prompt(canon: dict) -> str:
    """Compose the user-side prompt: existing fly info + cross-species data."""
    sym = canon.get("symbol", "?")
    fbgn = canon.get("fbgn", "?")

    lines = [INFERENCE_PROMPT]
    lines.append(f"FLY GENE: {sym} ({fbgn})")
    if canon.get("snapshot"):
        lines.append(f"FLY SUMMARY (existing): {canon['snapshot']}")
    fly_bullets = canon.get("bullets") or []
    if fly_bullets:
        lines.append(f"FLY VERBATIM BULLETS (existing, do NOT duplicate):")
        for b in fly_bullets:
            lines.append(f"  - [{b.get('category')}] {b.get('phenotype')}")
    cs = canon.get("cross_species") or {}

    lines.append("\nMOUSE ORTHOLOG KNOCKOUT PHENOTYPES (MGI):")
    for o in (cs.get("mouse_orthologs") or []):
        mp = o.get("mgi_phenotypes") or []
        if mp:
            lines.append(f"  Mouse {o.get('symbol')} (DIOPT {o.get('diopt_score')}):")
            for p in mp[:15]:
                term = p.get("term", "")
                defn = (p.get("definition") or "")[:150]
                lines.append(f"    - {term} [{p.get('mp_id')}] {defn}")

    lines.append("\nHUMAN ORTHOLOG CLINICAL PHENOTYPES (HPO):")
    for o in (cs.get("human_orthologs") or []):
        hp = o.get("hpo_phenotypes") or []
        if hp:
            lines.append(f"  Human {o.get('symbol')} (DIOPT {o.get('diopt_score')}):")
            for p in hp[:15]:
                term = p.get("term", "")
                defn = (p.get("definition") or "")[:150]
                lines.append(f"    - {term} [{p.get('hp_id')}] {defn}")

    diseases = cs.get("human_disease_links") or []
    if diseases:
        lines.append("\nHUMAN ORTHOLOG DISEASE LINKS:")
        for d in diseases[:5]:
            if d.get("omim_id"):
                lines.append(f"  - {d['name']} (OMIM {d['omim_id']}, via {d.get('via_symbol')})")
                hp = d.get("hpo_terms") or []
                for t in hp[:5]:
                    lines.append(f"      → {t['term']}")

    lines.append("\nOutput JSON now (bullets array only):")
    return "\n".join(lines)


def call_mimo(prompt: str, retries: int = 4) -> dict | None:
    """Call MiMo Token Plan SG endpoint with strict-mode prompt."""
    from urllib import request as urlreq, error as urlerr
    key = (ROOT / ".env").read_text()
    api_key = None
    for line in key.splitlines():
        if line.startswith("MIMO_API_KEY="):
            api_key = line.split("=", 1)[1].strip()
            break
    if not api_key:
        raise SystemExit("MIMO_API_KEY missing")
    base = os.environ.get("MIMO_BASE_URL") or "https://token-plan-sgp.xiaomimimo.com/anthropic"
    model = "mimo-v2.5-pro"
    url = f"{base}/v1/messages"
    body = json.dumps({
        "model": model,
        "max_tokens": 4000,
        "messages": [{"role": "user", "content": prompt}],
    }).encode()
    backoff = 2
    for attempt in range(retries):
        try:
            req = urlreq.Request(url, data=body, method="POST",
                                 headers={"x-api-key": api_key,
                                          "anthropic-version": "2023-06-01",
                                          "content-type": "application/json"})
            with urlreq.urlopen(req, timeout=120) as r:
                resp = json.loads(r.read())
            # extract text from content blocks
            parts = resp.get("content") or []
            text = "".join(p.get("text", "") for p in parts if p.get("type") == "text")
            return parse_json(text)
        except urlerr.HTTPError as e:
            if e.code in (429, 500, 502, 503, 529):
                time.sleep(backoff); backoff *= 2; continue
            raise
        except Exception:
            time.sleep(backoff); backoff *= 2
            if attempt == retries - 1: raise
    return None


def parse_json(text: str) -> dict | None:
    text = text.strip()
    # Strip markdown fences
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text
        if text.endswith("```"):
            text = text.rsplit("```", 1)[0]
    text = text.strip()
    try:
        return json.loads(text)
    except Exception:
        # Try to extract bullets via brace match
        m = re.search(r"\{[\s\S]*\}", text)
        if m:
            try: return json.loads(m.group(0))
            except: pass
    return None


def validate_inference_bullets(bullets: list, fbgn: str, mouse_terms: set, hpo_terms: set) -> list:
    """Drop any bullet that violates the inference contract: must be low conf,
    must cite a real ortholog term verbatim."""
    out = []
    for i, b in enumerate(bullets, 1):
        if b.get("confidence") != "low":
            continue
        ev = (b.get("evidence_text") or "").lower()
        if "inference from" not in ev:
            continue
        # Check the evidence text mentions at least one verbatim ortholog phenotype term
        has_real = any(t.lower() in ev for t in mouse_terms | hpo_terms if t)
        if not has_real:
            continue
        # Mark as inference + assign new id
        b["id"] = f"inf:{fbgn}:b{i:02d}"
        b["source"] = "ortholog_inference"
        b["text_specificity"] = b.get("text_specificity") or "low"
        b["tissues"] = b.get("tissues") or []
        b["life_stages"] = b.get("life_stages") or []
        b["alleles"] = b.get("alleles") or []
        b["citations"] = b.get("citations") or []
        out.append(b)
    return out


def collect_terms(canon: dict) -> tuple[set, set]:
    cs = canon.get("cross_species") or {}
    mp = set()
    for o in (cs.get("mouse_orthologs") or []):
        for p in (o.get("mgi_phenotypes") or []):
            if p.get("term"): mp.add(p["term"])
    hp = set()
    for o in (cs.get("human_orthologs") or []):
        for p in (o.get("hpo_phenotypes") or []):
            if p.get("term"): hp.add(p["term"])
    for d in (cs.get("human_disease_links") or []):
        for t in (d.get("hpo_terms") or []):
            if t.get("term"): hp.add(t["term"])
    return mp, hp


def process_one(fbgn: str) -> tuple[str, int, str]:
    """Returns (fbgn, n_added, status_msg)."""
    canon_p = ROOT / "output" / "genes" / f"{fbgn}.json"
    if not canon_p.exists():
        return fbgn, 0, "no canonical"
    canon = json.loads(canon_p.read_text())
    if any(b.get("source") == "ortholog_inference" for b in (canon.get("bullets") or [])):
        return fbgn, 0, "already enriched"

    mouse_terms, hpo_terms = collect_terms(canon)
    if not (mouse_terms or hpo_terms):
        return fbgn, 0, "no ortholog material"

    prompt = build_inference_prompt(canon)
    try:
        resp = call_mimo(prompt)
    except Exception as e:
        return fbgn, 0, f"api fail: {str(e)[:60]}"
    if not resp:
        return fbgn, 0, "parse fail"
    raw_bullets = resp.get("bullets") or []
    valid = validate_inference_bullets(raw_bullets, fbgn, mouse_terms, hpo_terms)
    if not valid:
        return fbgn, 0, "no valid inference bullets after filter"
    canon["bullets"] = (canon.get("bullets") or []) + valid
    if not canon.get("_lint"):
        canon["_lint"] = []
    canon["_lint"].append({
        "code": "inference.ortholog_bullets_added",
        "severity": "info",
        "message": f"Added {len(valid)} inference bullets from mouse/human ortholog phenotype context. confidence=low.",
        "stage": "stub_inference",
        "n_added": len(valid),
    })
    canon_p.write_text(json.dumps(canon, indent=2, ensure_ascii=False))
    return fbgn, len(valid), "ok"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="input", default="/tmp/stub_genes_to_enrich.txt")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    fbgns = [l.strip() for l in open(args.input) if l.strip()]
    if args.limit:
        fbgns = fbgns[:args.limit]
    print(f"Processing {len(fbgns)} stub genes with MiMo inference (workers={args.workers})...")

    t0 = time.time()
    ok = skipped = failed = 0
    total_bullets = 0
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futures = {ex.submit(process_one, f): f for f in fbgns}
        for i, fut in enumerate(as_completed(futures), 1):
            fbgn, n, msg = fut.result()
            if msg == "ok":
                ok += 1; total_bullets += n
            elif "fail" in msg:
                failed += 1
            else:
                skipped += 1
            if i % 10 == 0:
                el = time.time() - t0
                print(f"  {i}/{len(fbgns)} ok={ok} skip={skipped} fail={failed} bullets+={total_bullets} ({el:.0f}s)", flush=True)
            if msg not in ("ok",):
                print(f"    [{fbgn}] {msg}")

    print(f"\nDone in {(time.time()-t0)/60:.1f}min")
    print(f"  ok={ok}  skipped={skipped}  failed={failed}")
    print(f"  total inference bullets added: {total_bullets}")


if __name__ == "__main__":
    main()
