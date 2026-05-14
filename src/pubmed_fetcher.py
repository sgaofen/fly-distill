"""Batched PubMed abstract fetcher via NCBI E-utilities.

This is NOT FlyBase — it's NCBI's public eutils endpoint. Completely different
infrastructure from FlyBase's CloudFront WAF. No 405/CAPTCHA risk.

- Up to 200 PMIDs per efetch call
- Rate: 3/s without email, 10/s with email (we have email)
- Global on-disk cache: data/cache/pubmed/<pmid>.json
- Returns {pmid: {title, abstract, year, authors_short}}
"""
import gzip
import json
import os
import re
import subprocess
import threading
import time
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE_DIR = ROOT / "data" / "cache" / "pubmed"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

NCBI_EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
NCBI_EMAIL = os.environ.get("NCBI_EMAIL", "")
TOOL_NAME = "fly-distill-atlas"

# Conservative rate: ~3 calls/sec global, thread-safe.
# NCBI allows 3/s without email and 10/s with — we stay well under either.
_rate_lock = threading.Lock()
_last_call_t = 0.0
RATE_DELAY_S = 0.34


def _curl(url: str, timeout: int = 30) -> str:
    """Shell out to curl for HTTPS get."""
    r = subprocess.run(
        ["/usr/bin/curl", "-sL", "--max-time", str(timeout), url],
        capture_output=True, check=False,
    )
    return r.stdout.decode("utf-8", errors="replace")


def _rate_limit():
    global _last_call_t
    with _rate_lock:
        now = time.time()
        delay = RATE_DELAY_S - (now - _last_call_t)
        if delay > 0:
            time.sleep(delay)
        _last_call_t = time.time()


def _parse_pubmed_xml(xml: str) -> dict:
    """Light regex extraction: returns {pmid: {title, abstract, year, journal}}."""
    out = {}
    for art in re.finditer(r"<PubmedArticle>(.*?)</PubmedArticle>", xml, flags=re.S):
        body = art.group(1)
        pmid_m = re.search(r"<PMID[^>]*>(\d+)</PMID>", body)
        title_m = re.search(r"<ArticleTitle[^>]*>(.*?)</ArticleTitle>", body, flags=re.S)
        year_m = re.search(r"<PubDate>.*?<Year>(\d{4})</Year>", body, flags=re.S)
        journal_m = re.search(r"<Journal>.*?<Title>([^<]+)</Title>", body, flags=re.S)
        abs_chunks = re.findall(r"<AbstractText[^>]*>(.*?)</AbstractText>", body, flags=re.S)
        abstract = " ".join(re.sub(r"<[^>]+>", "", c) for c in abs_chunks).strip()
        if not pmid_m:
            continue
        pmid = pmid_m.group(1)
        out[pmid] = {
            "pmid": pmid,
            "title": re.sub(r"<[^>]+>", "", title_m.group(1)).strip() if title_m else "",
            "abstract": abstract,
            "year": int(year_m.group(1)) if year_m else None,
            "journal": journal_m.group(1).strip() if journal_m else "",
        }
    return out


def _cached(pmid: str):
    p = CACHE_DIR / f"{pmid}.json"
    if p.exists():
        try:
            return json.loads(p.read_text())
        except Exception:
            return None
    return None


def _cache_put(pmid: str, record: dict):
    (CACHE_DIR / f"{pmid}.json").write_text(json.dumps(record, ensure_ascii=False))


def fetch_abstracts(pmids: list, batch_size: int = 100) -> dict:
    """Fetch abstracts for given PMIDs. Hits cache first; only fetches missing.
    Returns {pmid: record}. Failures yield None or omit the pmid."""
    pmids = [p for p in pmids if p and p.isdigit()]
    if not pmids:
        return {}
    result = {}
    missing = []
    for p in pmids:
        c = _cached(p)
        if c is not None:
            result[p] = c
        else:
            missing.append(p)
    # batch-fetch missing
    for i in range(0, len(missing), batch_size):
        batch = missing[i:i + batch_size]
        params = {
            "db": "pubmed",
            "id": ",".join(batch),
            "rettype": "abstract",
            "retmode": "xml",
            "tool": TOOL_NAME,
        }
        if NCBI_EMAIL:
            params["email"] = NCBI_EMAIL
        url = f"{NCBI_EUTILS}/efetch.fcgi?{urllib.parse.urlencode(params)}"
        _rate_limit()
        xml = _curl(url, timeout=60)
        parsed = _parse_pubmed_xml(xml)
        for pmid, rec in parsed.items():
            _cache_put(pmid, rec)
            result[pmid] = rec
        # write empty cache for any PMID we asked about but didn't get back
        for p in batch:
            if p not in result:
                _cache_put(p, {"pmid": p, "title": "", "abstract": "", "year": None, "journal": ""})
                result[p] = _cached(p)
    return result


def main():
    test_pmids = ["20023653", "12345678", "27466818"]   # known + bad + real
    print(f"fetching {len(test_pmids)} abstracts...")
    t0 = time.time()
    out = fetch_abstracts(test_pmids)
    print(f"  done in {time.time()-t0:.1f}s")
    for pmid, rec in out.items():
        print(f"  {pmid} ({rec.get('year')}): {rec.get('title','')[:80]}")
        print(f"    abstract: {(rec.get('abstract','') or '(empty)')[:120]}")


if __name__ == "__main__":
    main()
