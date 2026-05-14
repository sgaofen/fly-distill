"""Batch fetch + distill across the curated gene list."""
import json
import sys
import time
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gene_list import GENES
from fetch_gene import build_bundle
from distill import distill_one

ROOT = Path(__file__).resolve().parents[1]
CACHE_ROOT = ROOT / "data" / "cache"
OUT_ROOT = ROOT / "output"


def run_one(g: dict, skip_fetch_if_cached: bool = True, skip_distill_if_cached: bool = True):
    fbgn = g["fbgn"]
    cache = CACHE_ROOT / fbgn
    out = OUT_ROOT / fbgn
    log = {"fbgn": fbgn, "symbol": g["symbol"], "tier": g["tier"], "note": g["note"]}

    print(f"\n========== {fbgn} {g['symbol']} (tier {g['tier']}) ==========", flush=True)

    # ---- fetch ----
    bundle_path = cache / "bundle.json"
    if skip_fetch_if_cached and bundle_path.exists():
        print(f"  bundle already cached, skip fetch", flush=True)
        log["fetch_skipped"] = True
    else:
        t0 = time.time()
        try:
            build_bundle(fbgn, cache)
            log["fetch_time_s"] = round(time.time() - t0, 1)
        except Exception as e:
            log["fetch_error"] = str(e)
            log["traceback"] = traceback.format_exc()
            print(f"  FETCH FAILED: {e}", flush=True)
            return log

    # measure bundle
    b = json.loads(bundle_path.read_text())
    log["pubs_total"] = b.get("pubs_total", 0)
    log["abstracts_with_text"] = sum(1 for a in b.get("abstracts", []) if a.get("abstract"))
    log["human_orthologs"] = len(b.get("human_ortholog_data", []))
    log["mouse_orthologs"] = len(b.get("mouse_ortholog_data", []))

    # ---- distill ----
    bullets_path = out / "bullets.json"
    if skip_distill_if_cached and bullets_path.exists():
        print(f"  bullets already cached, skip distill", flush=True)
        log["distill_skipped"] = True
    else:
        t0 = time.time()
        try:
            r = distill_one(fbgn)
            log["distill_time_s"] = round(time.time() - t0, 1)
            log["parsed_ok"] = r["parsed_ok"]
            log["usage"] = r["usage"]
        except Exception as e:
            log["distill_error"] = str(e)
            log["traceback"] = traceback.format_exc()
            print(f"  DISTILL FAILED: {e}", flush=True)
            return log

    # bullets summary
    if bullets_path.exists():
        d = json.loads(bullets_path.read_text())
        log["n_bullets"] = len(d.get("bullets", []))
        log["categories"] = sorted({b.get("category") for b in d.get("bullets", [])})

    return log


def main():
    only = sys.argv[1].split(",") if len(sys.argv) > 1 else None
    genes = [g for g in GENES if (not only or g["fbgn"] in only or g["symbol"] in only)]
    print(f"Running {len(genes)} genes\n", flush=True)
    results = []
    for i, g in enumerate(genes):
        if i > 0:
            time.sleep(5)  # inter-gene cooldown to keep WAF happy
        results.append(run_one(g))
    # write summary
    summary_path = OUT_ROOT / "batch_summary.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(results, indent=2))
    print(f"\n=== batch done; summary in {summary_path}")
    # console table
    print(f"\n{'fbgn':14} {'sym':10} {'T':1}  {'fetch':6} {'distill':7} {'bullets':7} {'pubs':5} {'h_ort':5} {'m_ort':5}")
    for r in results:
        print(f"{r['fbgn']:14} {r['symbol']:10} {r['tier']:1}  "
              f"{r.get('fetch_time_s','-' ):>6} {r.get('distill_time_s','-'):>7} "
              f"{r.get('n_bullets','-'):>7} {r.get('pubs_total','-'):>5} "
              f"{r.get('human_orthologs','-'):>5} {r.get('mouse_orthologs','-'):>5}")


if __name__ == "__main__":
    main()
