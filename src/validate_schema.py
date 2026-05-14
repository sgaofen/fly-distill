"""Strict JSON Schema validation using the jsonschema library (Draft 2020-12).
Replaces hand-rolled validation in validate.py — pure schema-conformance check.
Domain-specific lint (e.g. citation FBrf exists in bundle) lives in qa.py.
"""
import json
import sys
from pathlib import Path

import jsonschema
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
GENES_DIR = ROOT / "output" / "genes"
SCHEMA_PATH = ROOT / "output" / "schema" / "distilled_gene_v1_2.schema.json"


def main():
    schema = json.loads(SCHEMA_PATH.read_text())
    validator = Draft202012Validator(schema)
    files = sorted(GENES_DIR.glob("FBgn*.json"))
    print(f"validating {len(files)} genes against {SCHEMA_PATH.name}")
    print()

    n_pass = n_warn = n_fail = 0
    for f in files:
        g = json.loads(f.read_text())
        errors = sorted(validator.iter_errors(g), key=lambda e: list(e.path))
        lint = g.get("_lint", [])
        if errors:
            print(f"  FAIL {g['fbgn']:13} {g['symbol']:8} — {len(errors)} schema errors")
            for e in errors[:5]:
                path = ".".join(str(p) for p in e.absolute_path)
                print(f"    × at $.{path}: {e.message[:120]}")
            if len(errors) > 5:
                print(f"    ... and {len(errors) - 5} more")
            n_fail += 1
        elif lint:
            print(f"  WARN {g['fbgn']:13} {g['symbol']:8} — {len(lint)} lint warnings")
            for w in lint:
                if isinstance(w, dict):
                    print(f"    ⚠ [{w.get('severity','?')}] {w.get('code')}: {w.get('message','')[:100]}")
                else:
                    print(f"    ⚠ {w[:120]}")
            n_warn += 1
        else:
            print(f"  PASS {g['fbgn']:13} {g['symbol']:8}")
            n_pass += 1

    print()
    print(f"summary: {n_pass} PASS, {n_warn} WARN, {n_fail} FAIL")
    sys.exit(1 if n_fail else 0)


if __name__ == "__main__":
    main()
