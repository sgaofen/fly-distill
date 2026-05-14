"""Fetch a single fly gene's full data bundle from FlyBase.

Per-gene sources:
  - API /gene/summaries/auto/{fbgn}                  — auto summary
  - API /ribbon/go/{biological_process,molecular_function,cellular_component}/{fbgn}
  - HTML /reports/{fbgn}                             — phenotypes / alleles / orthologs / disease sections,
                                                       and full pubs list (1000s) via embedded data-pubs JSON
  - API /fbrf/{id}/abstract                          — abstract per FlyBase reference
                                                       (no need to round-trip through PubMed)

Output: data/cache/{fbgn}/bundle.json packed for downstream LLM distillation.
"""
import html
import json
import os
import re
import subprocess
import sys
import time
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

FLYBASE_API = "https://api.flybase.org/api/v1.0"
FLYBASE_HTML = "https://flybase.org/reports"
MYGENE_API = "https://mygene.info/v3"
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"

# Caps for prototype scale — keeps payload bounded & polite to FlyBase
MAX_REFS = 20             # pull abstracts for top-N most-recent representative refs
MAX_ORTHO_PER_SPECIES = 3 # fetch deep data for top N orthologs per species (human, mouse)
RATE_DELAY_S = 0.4        # FlyBase asks ≤3 req/s; we stay well below


def get(url: str, timeout: int = 30, retries: int = 5, min_bytes: int = 1) -> bytes:
    """Shell out to curl — FlyBase's AWS WAF blocks Python urllib but lets curl through.
    Retries with exponential backoff if response is empty / shorter than min_bytes."""
    last = b""
    backoffs = [1, 4, 10, 25, 60]
    for i in range(retries):
        try:
            r = subprocess.run(
                ["/usr/bin/curl", "-sL", "--max-time", str(timeout), url],
                capture_output=True, check=True,
            )
            data = r.stdout
            if len(data) >= min_bytes and data.strip():
                return data
            last = data
        except subprocess.CalledProcessError as e:
            if i == retries - 1:
                raise RuntimeError(f"curl failed for {url}: {e.stderr.decode()[:300]}")
        wait = backoffs[min(i, len(backoffs) - 1)]
        print(f"    (got {len(last)} bytes, retry {i+1}/{retries} after {wait}s)", flush=True)
        time.sleep(wait)
    return last


def fetch_auto_summary(fbgn: str) -> str:
    raw = get(f"{FLYBASE_API}/gene/summaries/auto/{fbgn}")
    if not raw.strip():
        return ""
    res = json.loads(raw).get("resultset", {}).get("result", [])
    return res[0]["summary"] if res else ""


def fetch_go_ribbon(fbgn: str, domain: str) -> dict:
    raw = get(f"{FLYBASE_API}/ribbon/go/{domain}/{fbgn}")
    if not raw.strip():
        return {}
    res = json.loads(raw).get("resultset", {}).get("result", [])
    return res[0] if res else {}


def fetch_gene_html(fbgn: str) -> str:
    # Gene report pages are typically >500KB; demand at least 50KB to ensure not a WAF stub
    return get(f"{FLYBASE_HTML}/{fbgn}", min_bytes=50_000).decode("utf-8", errors="replace")


_FBRF_CACHE_DIR = Path(__file__).resolve().parents[1] / "data" / "cache" / "fbrf"


def fetch_abstract(fbrf: str) -> str:
    """Many FBrf records legitimately have no abstract — don't aggressively retry on empty.

    v1.2 (GPT review #23): shared per-FBrf cache at data/cache/fbrf/<FBrfID>.json so that
    abstracts are fetched at most once per FBrf across the entire 14k-gene run. At
    14k genes × 20 abstracts/gene = 280k requests, ~50% will be deduplicated.
    """
    _FBRF_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = _FBRF_CACHE_DIR / f"{fbrf}.json"
    if cache_path.exists():
        try:
            cached = json.loads(cache_path.read_text())
            return cached.get("abstract", "")
        except Exception:
            pass  # corrupted, refetch

    raw = get(f"{FLYBASE_API}/fbrf/{fbrf}/abstract", retries=2)
    abstract = ""
    if raw.strip():
        try:
            res = json.loads(raw).get("resultset", {}).get("result", [])
            if res:
                abstract = res[0].get("abstract", "")
        except json.JSONDecodeError:
            pass

    cache_path.write_text(json.dumps({
        "fbrf": fbrf,
        "abstract": abstract,
        "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }))
    return abstract


def fetch_mygene_by_entrez(entrez_id: str) -> dict:
    """Fetch gene info by Entrez ID — fastest path."""
    fields = "symbol,name,summary,alias,clinvar,pathway.reactome,go,phenotypes"
    try:
        raw = get(f"{MYGENE_API}/gene/{entrez_id}?fields={fields}")
        d = json.loads(raw)
        return {
            "symbol": d.get("symbol"),
            "name": d.get("name"),
            "summary": d.get("summary", ""),
            "alias": d.get("alias"),
        }
    except Exception as e:
        return {"_error": str(e)}


class SectionExtractor(HTMLParser):
    """Pulls text out of selected divs by id attr."""

    def __init__(self, target_ids: set):
        super().__init__(convert_charrefs=True)
        self.targets = target_ids
        self.depth = 0
        self.stack = []
        self.bufs = {tid: [] for tid in target_ids}

    def handle_starttag(self, tag, attrs):
        self.depth += 1
        tid = dict(attrs).get("id")
        if tid in self.targets:
            self.stack.append((tid, self.depth))

    def handle_endtag(self, tag):
        if self.stack and self.depth == self.stack[-1][1]:
            self.stack.pop()
        self.depth -= 1

    def handle_data(self, data):
        if self.stack:
            self.bufs[self.stack[-1][0]].append(data)

    def text(self, tid: str) -> str:
        return re.sub(r"\s+", " ", "".join(self.bufs.get(tid, []))).strip()


SECTION_IDS = {
    "function",
    "phenotypes_sub",
    "alleles_main_sub",
    "human_orthologs_sub",
    "mod_orthologs_sub",
    "hdm_sub",                          # human disease model summary
    "other_comments_sub",               # curator notes — often rich
    "summary_genetic_interactions_sub",
    "summary_physical_interactions_sub",
    "pathways_sub",
    "gene_class_sub",
}


def extract_sections(html_text: str) -> dict:
    ex = SectionExtractor(SECTION_IDS)
    ex.feed(html_text)
    return {tid: ex.text(tid) for tid in SECTION_IDS}


def parse_top_orthologs(html_text: str, species_prefix: str, limit: int) -> list:
    """Pull top-N orthologs for a species code (Hsap / Mmus / Rnor) directly from raw HTML.
    Captures symbol + NCBI Entrez ID (from term=X) + DIOPT score."""
    pat = re.compile(
        species_prefix + r"\\([A-Za-z][A-Za-z0-9\-]*)</a>.{0,3000}?term=(\d+)",
        flags=re.S,
    )
    rows = []
    for m in pat.finditer(html_text):
        sym, entrez = m.group(1), m.group(2)
        nxt = html_text[m.end():m.end() + 3000]
        sm = re.search(r">\s*(\d+)\s*of\s*(\d+)\s*<", nxt)
        if not sm:
            continue
        rows.append({
            "symbol": sym,
            "entrez_id": entrez,
            "diopt_score": int(sm.group(1)),
            "diopt_max": int(sm.group(2)),
        })
    # de-dup keep highest score per symbol
    best = {}
    for r in rows:
        if r["symbol"] not in best or best[r["symbol"]]["diopt_score"] < r["diopt_score"]:
            best[r["symbol"]] = r
    ranked = sorted(best.values(), key=lambda r: r["diopt_score"], reverse=True)
    return ranked[:limit]


def extract_pubs(html_text: str) -> list:
    """Decode the data-pubs JSON blob embedded in the gene report."""
    m = re.search(r'id="pubs_json"[^>]*?data-pubs="(\[.*?\])"', html_text, flags=re.S)
    if not m:
        return []
    decoded = html.unescape(m.group(1))
    # find balanced array end (data-pubs is followed by other attrs in same tag)
    depth = 0
    in_str = False
    esc = False
    end = None
    for i, c in enumerate(decoded):
        if esc:
            esc = False
            continue
        if c == "\\":
            esc = True
            continue
        if c == '"':
            in_str = not in_str
            continue
        if in_str:
            continue
        if c == "[":
            depth += 1
        elif c == "]":
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    if end is None:
        return []
    return json.loads(decoded[:end])


def pick_refs(pubs: list, limit: int = MAX_REFS) -> list:
    """Prefer FlyBase 'representative' refs (curator-picked); fall back to reviews then papers,
    sorted most-recent-first."""
    rank = {"representative": 0, "review": 1, "paper": 2, "abstract": 3}
    ranked = sorted(
        pubs,
        key=lambda r: (rank.get(r.get("type", ""), 99), -int(r.get("year") or 0)),
    )
    return ranked[:limit]


def build_bundle(fbgn: str, cache_dir: Path) -> dict:
    cache_dir.mkdir(parents=True, exist_ok=True)
    bundle = {"fbgn": fbgn, "fetched_at": time.strftime("%Y-%m-%d %H:%M:%S")}

    print("  [1/5] auto summary", flush=True)
    bundle["auto_summary"] = fetch_auto_summary(fbgn)

    print("  [2/5] GO ribbons", flush=True)
    bundle["go"] = {}
    for dom in ("biological_process", "molecular_function", "cellular_component"):
        time.sleep(RATE_DELAY_S)
        bundle["go"][dom] = fetch_go_ribbon(fbgn, dom)

    print("  [3/6] HTML report", flush=True)
    html_text = fetch_gene_html(fbgn)
    if len(html_text) < 50_000:
        raise RuntimeError(
            f"FlyBase HTML for {fbgn} too small ({len(html_text)} chars) — likely WAF blocked"
        )
    (cache_dir / "raw.html").write_text(html_text)

    print("  [4/6] section extraction + pubs list + ortholog symbols", flush=True)
    bundle["sections"] = extract_sections(html_text)
    pubs = extract_pubs(html_text)
    bundle["pubs_total"] = len(pubs)
    selected = pick_refs(pubs)
    bundle["refs_selected"] = selected
    bundle["top_human_orthologs"] = parse_top_orthologs(html_text, "Hsap", MAX_ORTHO_PER_SPECIES)
    bundle["top_mouse_orthologs"] = parse_top_orthologs(html_text, "Mmus", MAX_ORTHO_PER_SPECIES)

    print(f"  [5/6] abstracts ({len(selected)} of {len(pubs)} refs)", flush=True)
    abstracts = []
    for ref in selected:
        time.sleep(RATE_DELAY_S)
        try:
            a = fetch_abstract(ref["id"])
        except Exception as e:
            a = ""
            print(f"    ! abstract fetch failed for {ref['id']}: {e}", flush=True)
        abstracts.append({
            "fbrf": ref["id"],
            "year": ref.get("year"),
            "type": ref.get("type"),
            "title": ref.get("title", ""),
            "miniref": ref.get("miniref", ""),
            "abstract": a,
        })
    bundle["abstracts"] = abstracts

    print(f"  [6/6] mygene cross-species "
          f"({len(bundle['top_human_orthologs'])} human, {len(bundle['top_mouse_orthologs'])} mouse)", flush=True)
    bundle["human_ortholog_data"] = []
    for o in bundle["top_human_orthologs"]:
        time.sleep(RATE_DELAY_S)
        info = fetch_mygene_by_entrez(o["entrez_id"])
        merged = {**o, **info}
        # 'symbol' from MyGene may overwrite FlyBase symbol; keep FlyBase's for consistency
        merged["symbol"] = o["symbol"]
        bundle["human_ortholog_data"].append(merged)
    bundle["mouse_ortholog_data"] = []
    for o in bundle["top_mouse_orthologs"]:
        time.sleep(RATE_DELAY_S)
        info = fetch_mygene_by_entrez(o["entrez_id"])
        merged = {**o, **info}
        merged["symbol"] = o["symbol"]
        bundle["mouse_ortholog_data"].append(merged)

    (cache_dir / "bundle.json").write_text(json.dumps(bundle, indent=2))
    return bundle


def summarize_bundle(b: dict) -> None:
    print(f"\n=== bundle summary: {b['fbgn']} ===")
    print(f"auto_summary: {len(b['auto_summary'])} chars")
    for dom, ribbon in b["go"].items():
        n = len(ribbon.get("slim_names_order", [])) if ribbon else 0
        print(f"GO {dom}: {n} slim categories")
    for sid, txt in b["sections"].items():
        print(f"section {sid}: {len(txt)} chars")
    print(f"pubs_total: {b['pubs_total']}, refs selected: {len(b['refs_selected'])}")
    abs_with = sum(1 for a in b["abstracts"] if a["abstract"])
    abs_chars = sum(len(a["abstract"]) for a in b["abstracts"])
    print(f"abstracts with text: {abs_with}/{len(b['abstracts'])}, total {abs_chars} chars")
    h_chars = sum(len(o.get("summary", "") or "") for o in b.get("human_ortholog_data", []))
    m_chars = sum(len(o.get("summary", "") or "") for o in b.get("mouse_ortholog_data", []))
    print(f"human orthologs: {len(b.get('human_ortholog_data', []))} ({h_chars} chars summary)")
    print(f"mouse orthologs: {len(b.get('mouse_ortholog_data', []))} ({m_chars} chars summary)")
    body_chars = (
        len(b["auto_summary"])
        + sum(len(s) for s in b["sections"].values())
        + abs_chars
        + h_chars
        + m_chars
    )
    print(f"~total text payload: {body_chars} chars (~{body_chars // 4} tokens)")


def main():
    fbgn = sys.argv[1] if len(sys.argv) > 1 else "FBgn0003068"
    root = Path(__file__).resolve().parents[1]
    cache = root / "data" / "cache" / fbgn
    print(f"Fetching {fbgn} → {cache}")
    b = build_bundle(fbgn, cache)
    summarize_bundle(b)
    print(f"\nbundle written: {cache / 'bundle.json'}")


if __name__ == "__main__":
    main()
