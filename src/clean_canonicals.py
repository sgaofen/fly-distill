"""In-place cleanup of all output/genes/FBgn*.json files.

Fixes 4 data-quality issues identified by Codex re-audit:

  P1-1: Ortholog dedup that handles NULL/missing entrez_id properly.
        Old logic keyed on (symbol, str(entrez_id)) — so "Egfbp2 entrez=13647"
        and "Egfbp2 entrez=None" were treated as different. New logic:
        dedup by symbol alone, preferring the record with the richer fields
        (non-empty entrez_id, higher diopt_score, longer name).

  P1-2: Disease dedup. Same pattern as orthologs.

  P1-4: Bullet dedup. Some genes (e.g. FBgn0036274) had exact-duplicate
        (phenotype, evidence_text) pairs from a single LLM run that looped.
        Dedup by exact pair.

  P1-5: Repair 14 ortholog_inference bullets where prefix is literally
        "INFERENCE from mouse|human ortholog X:" — should be "mouse ortholog"
        or "human ortholog" based on whether the cited term is MP: (mouse)
        or HP: (human).

Run:
  python src/clean_canonicals.py
  python src/clean_canonicals.py --dry-run        # print stats, no writes
"""
from __future__ import annotations
import argparse
import json
import re
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parents[1]
GENES_DIR = ROOT / "output" / "genes"


# ---------- ortholog dedup ----------------

def _ortholog_completeness(o: dict) -> tuple:
    """Sort key for picking the 'best' record among same-symbol dupes.
    Higher = better. Tie-break: prefer entrez_id, higher diopt, longer name."""
    return (
        1 if o.get("entrez_id") else 0,
        int(o.get("diopt_score") or 0),
        len(o.get("name") or ""),
    )


def dedup_orthologs(arr: list[dict]) -> list[dict]:
    """Dedup by symbol (case-sensitive — human is UPPER, mouse Capitalized,
    so collision means same gene), keep the most-complete record."""
    by_symbol: dict[str, dict] = {}
    for o in arr or []:
        sym = (o.get("symbol") or "").strip()
        if not sym:
            continue
        cur = by_symbol.get(sym)
        if cur is None or _ortholog_completeness(o) > _ortholog_completeness(cur):
            by_symbol[sym] = o
    return list(by_symbol.values())


# ---------- disease dedup ----------------

def _disease_key(d: dict) -> tuple:
    """Dedup key: (omim_id, normalized_name). Normalize case + whitespace."""
    name_norm = re.sub(r"\s+", " ", (d.get("name") or "")).strip().lower()
    omim = d.get("omim_id") or ""
    return (omim, name_norm)


def _disease_completeness(d: dict) -> tuple:
    """Prefer records with omim_id + via_symbol + via_species."""
    return (
        1 if d.get("omim_id") else 0,
        1 if d.get("via_symbol") else 0,
        1 if d.get("via_species") else 0,
        len(d.get("source") or ""),
    )


def dedup_diseases(arr: list[dict]) -> list[dict]:
    """Dedup by (omim_id, normalized name)."""
    by_key: dict[tuple, dict] = {}
    for d in arr or []:
        k = _disease_key(d)
        cur = by_key.get(k)
        if cur is None or _disease_completeness(d) > _disease_completeness(cur):
            by_key[k] = d
    return list(by_key.values())


# ---------- bullet dedup ----------------

def dedup_bullets(arr: list[dict]) -> list[dict]:
    """Dedup by exact (phenotype, evidence_text) pair."""
    seen: set[tuple] = set()
    out: list[dict] = []
    for b in arr or []:
        key = (
            (b.get("phenotype") or "").strip(),
            (b.get("evidence_text") or "").strip(),
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(b)
    return out


# ---------- inference-prefix repair ----------------

_INFERENCE_PREFIX_RE = re.compile(
    r"^INFERENCE from mouse\|human ortholog ([^:]+):", re.I
)


def repair_inference_prefix(b: dict) -> bool:
    """If evidence starts with 'INFERENCE from mouse|human ortholog <X>:',
    detect species from the cited term ID (MP: = mouse, HP: = human) and
    rewrite. Returns True if a repair was applied."""
    if b.get("source") != "ortholog_inference":
        return False
    ev = (b.get("evidence_text") or "").strip()
    m = _INFERENCE_PREFIX_RE.match(ev)
    if not m:
        return False
    body = ev[m.end():]
    # Look ahead in body for MP: or HP: ID
    species = None
    if "[MP:" in body:
        species = "mouse"
    elif "[HP:" in body:
        species = "human"
    elif "MP:" in body:
        species = "mouse"
    elif "HP:" in body:
        species = "human"
    if species is None:
        return False  # leave alone if we can't tell
    new_ev = f"INFERENCE from {species} ortholog {m.group(1).strip()}:{body}"
    b["evidence_text"] = new_ev
    return True


# ---------- main ----------------

def clean_one(canonical_path: Path) -> dict:
    """Returns counts: {ortho_before, ortho_after, disease_before, ..., bullets_before, bullets_after,
                       inference_repaired}."""
    c = json.loads(canonical_path.read_text())
    cs = c.get("cross_species") or {}
    counts = {"ortho_before": 0, "ortho_after": 0,
              "disease_before": 0, "disease_after": 0,
              "bullets_before": 0, "bullets_after": 0,
              "inference_repaired": 0}

    # Orthologs (mouse + human)
    for key in ("mouse_orthologs", "human_orthologs"):
        before = cs.get(key) or []
        after = dedup_orthologs(before)
        counts["ortho_before"] += len(before)
        counts["ortho_after"] += len(after)
        cs[key] = after

    # Diseases
    before = cs.get("human_disease_links") or []
    after = dedup_diseases(before)
    counts["disease_before"] += len(before)
    counts["disease_after"] += len(after)
    cs["human_disease_links"] = after

    c["cross_species"] = cs

    # Bullets
    bullets = c.get("bullets") or []
    counts["bullets_before"] = len(bullets)
    for b in bullets:
        if repair_inference_prefix(b):
            counts["inference_repaired"] += 1
    bullets = dedup_bullets(bullets)
    counts["bullets_after"] = len(bullets)
    c["bullets"] = bullets

    # Keep n_bullets in sync (we'll re-derive in build.py anyway, but write here)
    c["n_bullets"] = len(bullets)

    return c, counts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    files = sorted(GENES_DIR.glob("FBgn*.json"))
    total = {"ortho_before": 0, "ortho_after": 0,
             "disease_before": 0, "disease_after": 0,
             "bullets_before": 0, "bullets_after": 0,
             "inference_repaired": 0}
    n_changed = 0
    for p in files:
        new_c, counts = clean_one(p)
        for k in total:
            total[k] += counts[k]
        # any change?
        changed = (counts["ortho_before"] != counts["ortho_after"]
                   or counts["disease_before"] != counts["disease_after"]
                   or counts["bullets_before"] != counts["bullets_after"]
                   or counts["inference_repaired"] > 0)
        if changed:
            n_changed += 1
            if not args.dry_run:
                p.write_text(json.dumps(new_c, indent=2, ensure_ascii=False))

    print(f"Scanned {len(files)} canonicals, changes in {n_changed}\n")
    print(f"Orthologs:  {total['ortho_before']} → {total['ortho_after']}  (removed {total['ortho_before']-total['ortho_after']} dupes)")
    print(f"Diseases:   {total['disease_before']} → {total['disease_after']}  (removed {total['disease_before']-total['disease_after']} dupes)")
    print(f"Bullets:    {total['bullets_before']} → {total['bullets_after']}  (removed {total['bullets_before']-total['bullets_after']} dupes)")
    print(f"Inference prefix repaired: {total['inference_repaired']} bullets")
    if args.dry_run:
        print("\n(dry-run: no files written)")


if __name__ == "__main__":
    main()
