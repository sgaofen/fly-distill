"""Convert raw GLM bullets.json → canonical distilled_gene_v1.1 schema.

Applies enrichers from enrich.py (deterministic post-processing, no LLM call):
  - structured citations parsed from evidence_text
  - tissue / life-stage / allele tags parsed from evidence + phenotype
  - specificity heuristic
  - GO terms carried verbatim from bundle
  - disease links cross-referenced with FlyBase dmel_human_orthologs_disease.tsv for OMIM IDs
  - full synonyms from fbgn_annotation_ID.tsv
"""
import json
from datetime import datetime, timezone
from pathlib import Path

import hashlib
import subprocess

from enrich import (
    parse_citations,
    parse_tissues,
    parse_life_stages,
    parse_alleles,
    score_specificity,
    extract_go,
    disease_links_with_ortholog,
    synonyms_typed_for,
)

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "1.2"
GENES_DIR = ROOT / "output" / "genes"


def _sha256(data) -> str:
    if isinstance(data, str):
        data = data.encode("utf-8")
    elif isinstance(data, (dict, list)):
        data = json.dumps(data, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def _git_commit() -> str:
    try:
        r = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"],
                           capture_output=True, text=True, timeout=3)
        return r.stdout.strip() or "untracked"
    except Exception:
        return "untracked"


_PROMPT_HASH = None
def _prompt_hash() -> str:
    global _PROMPT_HASH
    if _PROMPT_HASH is None:
        p = ROOT / "prompts" / "distill_system.md"
        _PROMPT_HASH = _sha256(p.read_text()) if p.exists() else "missing"
    return _PROMPT_HASH

VALID_CATEGORIES = {
    "behavior", "morphology", "lifespan_aging", "development",
    "reproduction", "metabolism", "immune", "sensory_neural",
    "stress_response", "disease_model", "expression_pattern", "other",
}
VALID_DIRECTIONS = {"loss_of_function", "gain_of_function", "either", "unknown"}
VALID_CONFIDENCES = {"high", "medium", "low", None}


def canonicalize_one(fbgn: str) -> dict:
    bundle = json.loads((ROOT / "data" / "cache" / fbgn / "bundle.json").read_text())
    raw_path = ROOT / "output" / fbgn / "bullets.json"
    meta_path = ROOT / "output" / fbgn / "request_meta.json"
    if not raw_path.exists():
        raise FileNotFoundError(f"no bullets.json for {fbgn}")
    raw = json.loads(raw_path.read_text())
    meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}

    lint = []
    bullets_out = []
    n_missing_confidence = 0
    for i, b in enumerate(raw.get("bullets", []), 1):
        bullet_id = f"{fbgn}:b{i:02d}"
        cat = b.get("category") or "other"
        if cat not in VALID_CATEGORIES:
            lint.append({
                "code": "category.coerced",
                "severity": "warn",
                "message": f"unknown category '{b.get('category')}' coerced to 'other'",
                "path": f"$.bullets[{i-1}].category",
                "stage": "canonicalize",
            })
            cat = "other"
        direction = b.get("direction") or "unknown"
        if direction not in VALID_DIRECTIONS:
            lint.append({
                "code": "direction.invalid",
                "severity": "warn",
                "message": f"invalid direction '{b.get('direction')}' coerced to 'unknown'",
                "path": f"$.bullets[{i-1}].direction",
                "stage": "canonicalize",
            })
            direction = "unknown"
        conf = b.get("confidence")
        if conf == "":
            conf = None
        if conf not in VALID_CONFIDENCES:
            lint.append({
                "code": "confidence.invalid",
                "severity": "warn",
                "message": f"invalid confidence '{conf}' set to null",
                "path": f"$.bullets[{i-1}].confidence",
                "stage": "canonicalize",
            })
            conf = None
        if conf is None:
            n_missing_confidence += 1
        phen = (b.get("phenotype") or "").strip()
        ev_text = (b.get("evidence") or "").strip()
        if len(phen) < 5:
            lint.append({
                "code": "phenotype.too_short",
                "severity": "warn",
                "message": f"bullet {i}: phenotype too short, skipped",
                "path": f"$.bullets[{i-1}]",
                "stage": "canonicalize",
            })
            continue
        if not ev_text:
            lint.append({
                "code": "evidence.missing",
                "severity": "warn",
                "message": f"bullet {i}: missing evidence",
                "path": f"$.bullets[{i-1}].evidence_text",
                "stage": "canonicalize",
            })

        citations = parse_citations(ev_text)

        bullets_out.append({
            "id": bullet_id,
            "category": cat,
            "phenotype": phen,
            "direction": direction,
            "evidence_text": ev_text,
            "citations": citations,
            "confidence": conf,
            "text_specificity": score_specificity(phen, ev_text),
            "tissues": parse_tissues(phen + " " + ev_text),
            "life_stages": parse_life_stages(phen + " " + ev_text),
            "alleles": parse_alleles(phen + " " + ev_text),
        })
    # whole-gene schema drift — structured form
    if bullets_out and n_missing_confidence == len(bullets_out):
        lint.append({
            "code": "schema_drift.missing_confidence",
            "severity": "warn",
            "message": f"every bullet ({n_missing_confidence}) was missing 'confidence' field; canonicalizer filled null",
            "path": "$.bullets[*].confidence",
            "stage": "canonicalize",
            "n_affected": n_missing_confidence,
        })
    elif n_missing_confidence > 0:
        lint.append({
            "code": "schema_drift.partial_missing_confidence",
            "severity": "info",
            "message": f"{n_missing_confidence}/{len(bullets_out)} bullets missing 'confidence'; filled null",
            "path": "$.bullets[*].confidence",
            "stage": "canonicalize",
            "n_affected": n_missing_confidence,
        })

    # cross-species: orthologs from bundle, diseases enriched with OMIM IDs + via_ortholog
    cs_raw = raw.get("cross_species") or {}
    cross_species = {
        "human_orthologs": [
            {
                "symbol": o.get("symbol"),
                "entrez_id": o.get("entrez_id"),
                "diopt_score": o.get("diopt_score"),
                "diopt_max": o.get("diopt_max"),
                "name": o.get("name"),
            }
            for o in bundle.get("human_ortholog_data", [])
        ],
        "mouse_orthologs": [
            {
                "symbol": o.get("symbol"),
                "entrez_id": o.get("entrez_id"),
                "diopt_score": o.get("diopt_score"),
                "diopt_max": o.get("diopt_max"),
                "name": o.get("name"),
            }
            for o in bundle.get("mouse_ortholog_data", [])
        ],
        "human_disease_links": disease_links_with_ortholog(
            fbgn, cs_raw.get("human_disease") or []
        ),
        "mouse_phenotype_links": cs_raw.get("mouse_phenotype") or [],
    }

    # typed synonyms (v1.2)
    syns = synonyms_typed_for(fbgn, fallback_symbol=raw.get("symbol") or fbgn)

    out = {
        "schema_version": SCHEMA_VERSION,
        "fbgn": fbgn,
        "symbol": raw.get("symbol") or "?",
        "synonyms": syns,
        "distilled_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "model": {
            "provider": "z.ai",
            "model_id": meta.get("model") or "glm-5.1",
            "harness": meta.get("harness") or "direct_api",
        },
        "source": {
            "flybase_release": "FB2026_01",
            "n_pubs_total": bundle.get("pubs_total", 0),
            "n_abstracts_used": sum(1 for a in bundle.get("abstracts", []) if a.get("abstract")),
            "input_tokens": (meta.get("usage") or {}).get("input_tokens"),
            "output_tokens": (meta.get("usage") or {}).get("output_tokens"),
        },
        "provenance": {
            "bundle_sha256": _sha256(bundle),
            "raw_llm_output_sha256": _sha256(raw),
            "prompt_sha256": _prompt_hash(),
            "pipeline_git_commit": _git_commit(),
            "canonicalized_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
        "snapshot": (raw.get("summary") or "").strip(),
        "bullets": bullets_out,
        "go_slim": extract_go(bundle),
        "cross_species": cross_species,
        "notes": (raw.get("notes") or "").strip() or None,
        "_lint": lint,
    }
    return out


def write_one(fbgn: str) -> dict:
    out = canonicalize_one(fbgn)
    GENES_DIR.mkdir(parents=True, exist_ok=True)
    (GENES_DIR / f"{fbgn}.json").write_text(
        json.dumps(out, indent=2, ensure_ascii=False)
    )
    return out


def main():
    fbgns = sorted(
        d.name for d in (ROOT / "output").iterdir()
        if d.is_dir() and (d / "bullets.json").exists()
    )
    rows = []
    for fbgn in fbgns:
        try:
            out = write_one(fbgn)
            n_cit = sum(len(b["citations"]) for b in out["bullets"])
            n_tis = sum(len(b["tissues"]) for b in out["bullets"])
            n_dis = len(out["cross_species"]["human_disease_links"])
            n_omim = sum(1 for d in out["cross_species"]["human_disease_links"] if d.get("omim_id"))
            rows.append((fbgn, out["symbol"], len(out["bullets"]),
                         n_cit, n_tis, n_dis, n_omim, len(out["_lint"])))
        except Exception as e:
            rows.append((fbgn, "?", 0, 0, 0, 0, 0, f"ERR: {e}"))

    print(f"\n{'fbgn':14} {'sym':10} {'blts':>4} {'cits':>5} {'tiss':>5} "
          f"{'dis':>4} {'omim':>5} {'lint':>5}")
    for r in rows:
        print(f"{r[0]:14} {r[1]:10} {r[2]:>4} {r[3]:>5} {r[4]:>5} "
              f"{r[5]:>4} {r[6]:>5}  {r[7]}")


if __name__ == "__main__":
    main()
