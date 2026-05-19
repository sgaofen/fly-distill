from __future__ import annotations
"""Minimal FastAPI Web UI for the fly-distill atlas.

Academic-style: dense data, lots of links, low-chrome.
HTML rendered server-side via Jinja2; no JS build step.

Launch:
  python -m flyatlas.cli serve
or:
  python -m flyatlas.server
"""
import json
import os
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import DB_PATH
from . import query as Q

BASE = Path(__file__).resolve().parent
TEMPLATES = Jinja2Templates(directory=str(BASE / "templates"))

app = FastAPI(title="fly-distill atlas",
              description="14k Drosophila gene phenotype atlas — local browser")
app.mount("/static", StaticFiles(directory=str(BASE / "static")), name="static")

DB = os.environ.get("FLYATLAS_DB", str(DB_PATH))


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    s = Q.stats(DB)
    return TEMPLATES.TemplateResponse("home.html", {
        "request": request, "stats": s,
    })


@app.get("/gene/{ident}", response_class=HTMLResponse)
def gene_page(request: Request, ident: str):
    fbgn = Q.resolve_gene(DB, ident)
    if not fbgn:
        raise HTTPException(404, f"Gene not found: {ident}")
    if fbgn != ident.upper() and not ident.startswith("FBgn"):
        return RedirectResponse(f"/gene/{fbgn}", status_code=302)
    g = Q.get_gene(DB, fbgn)
    # Augment with cross-species enrichment from canonical JSON (mgi/hpo phenotypes
    # are nested arrays that the SQLite schema doesn't store flatly).
    import json as _json
    canon_p = Path(__file__).resolve().parents[2] / "output" / "genes" / f"{fbgn}.json"
    if canon_p.exists():
        try:
            cj = _json.loads(canon_p.read_text())
            cs = cj.get("cross_species") or {}
            # Build {sym: phenotype_list} maps so the template can render
            human_ph = {o.get("symbol"): o.get("hpo_phenotypes") or []
                        for o in (cs.get("human_orthologs") or [])}
            mouse_ph = {o.get("symbol"): o.get("mgi_phenotypes") or []
                        for o in (cs.get("mouse_orthologs") or [])}
            disease_hpo = {d.get("omim_id"): d.get("hpo_terms") or []
                           for d in (cs.get("human_disease_links") or [])
                           if d.get("omim_id")}
            g["_human_phenotypes"] = human_ph
            g["_mouse_phenotypes"] = mouse_ph
            g["_disease_hpo"] = disease_hpo
        except Exception:
            pass
    # Group bullets by category for display
    by_cat = {}
    for b in g["bullets"]:
        by_cat.setdefault(b.get("category") or "other", []).append(b)
    return TEMPLATES.TemplateResponse("gene.html", {
        "request": request, "g": g, "by_cat": by_cat,
    })


@app.get("/search", response_class=HTMLResponse)
def search_page(request: Request, q: str = "",
                category: Optional[str] = None,
                direction: Optional[str] = None,
                confidence: Optional[str] = None,
                tissue: Optional[str] = None,
                region: Optional[str] = None,
                mode: str = "semantic",   # 'semantic' (default) | 'keyword'
                limit: int = 50):
    results = []
    if q:
        try:
            if mode == "keyword":
                results = Q.search(DB, q, category=category, direction=direction,
                                   confidence=confidence, tissue=tissue, limit=limit)
            else:
                # Semantic search (Gemini embeddings) — optional region filter
                from . import embed_query as EQ
                hybrid = EQ.hybrid_query(region, q, top_k=limit)
                results = hybrid.get("ranked", []) if "error" not in hybrid else []
                # Apply categorical + tissue filters as post-hoc on semantic results
                if results and (category or direction or confidence or tissue):
                    import sqlite3
                    c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
                    keep = []
                    for r in results:
                        ok = True
                        if category or direction or confidence:
                            cond_sql = "SELECT 1 FROM bullets WHERE fbgn=?"
                            args_sql: list = [r["fbgn"]]
                            if category:   cond_sql += " AND category=?";   args_sql.append(category)
                            if direction:  cond_sql += " AND direction=?";  args_sql.append(direction)
                            if confidence: cond_sql += " AND confidence=?"; args_sql.append(confidence)
                            cond_sql += " LIMIT 1"
                            if not c.execute(cond_sql, args_sql).fetchone():
                                ok = False
                        if ok and tissue:
                            if not c.execute(
                                "SELECT 1 FROM tissues WHERE fbgn=? AND tissue=? LIMIT 1",
                                (r["fbgn"], tissue),
                            ).fetchone():
                                ok = False
                        if ok:
                            keep.append(r)
                    results = keep
        except Exception as e:
            results = []
    return TEMPLATES.TemplateResponse("search.html", {
        "request": request, "q": q, "results": results, "mode": mode,
        "category": category, "direction": direction, "region": region,
        "confidence": confidence, "tissue": tissue,
    })


@app.get("/browse/{kind}/{term}", response_class=HTMLResponse)
def browse_page(request: Request, kind: str, term: str, limit: int = 500):
    if kind == "category":
        rows = Q.genes_by_category(DB, term, limit=limit)
        title = f"Phenotype category: {term}"
    elif kind == "tissue":
        rows = Q.genes_by_tissue(DB, term, limit=limit)
        title = f"Tissue: {term}"
    elif kind == "disease":
        rows = Q.genes_by_disease(DB, term, limit=limit)
        title = f"Disease: {term}"
    elif kind == "ortholog":
        rows = Q.genes_by_ortholog(DB, term, limit=limit)
        title = f"Ortholog: {term}"
    elif kind == "paper":
        rows = Q.genes_by_paper(DB, term, limit=limit)
        title = f"Paper: {term}"
    else:
        raise HTTPException(404, f"Unknown browse kind: {kind}")
    return TEMPLATES.TemplateResponse("browse.html", {
        "request": request, "title": title, "kind": kind,
        "term": term, "rows": rows,
    })


# ----------------------- JSON API ----------------------- #
# Same routes under /api/* return JSON, for headless clients / future SPA.

@app.get("/api/gene/{ident}")
def api_gene(ident: str):
    fbgn = Q.resolve_gene(DB, ident)
    if not fbgn:
        raise HTTPException(404, "Gene not found")
    return Q.get_gene(DB, fbgn)


@app.get("/api/search")
def api_search(q: str, category: Optional[str] = None,
               direction: Optional[str] = None,
               confidence: Optional[str] = None,
               tissue: Optional[str] = None, limit: int = 50):
    return Q.search(DB, q, category=category, direction=direction,
                    confidence=confidence, tissue=tissue, limit=limit)


@app.get("/api/disease/{term}")
def api_disease(term: str, limit: int = 200):
    return Q.genes_by_disease(DB, term, limit=limit)


@app.get("/api/ortholog/{symbol}")
def api_ortholog(symbol: str, limit: int = 200):
    return Q.genes_by_ortholog(DB, symbol, limit=limit)


@app.get("/api/paper/{ident}")
def api_paper(ident: str, limit: int = 500):
    return Q.genes_by_paper(DB, ident, limit=limit)


@app.get("/api/tissue/{term}")
def api_tissue(term: str, limit: int = 500):
    return Q.genes_by_tissue(DB, term, limit=limit)


@app.get("/api/category/{cat}")
def api_category(cat: str, confidence: Optional[str] = None, limit: int = 500):
    return Q.genes_by_category(DB, cat, confidence=confidence, limit=limit)


@app.get("/api/stats")
def api_stats():
    return Q.stats(DB)


@app.get("/api/region/{region}")
def api_region(region: str, release: str = "r6"):
    from . import embed_query as EQ
    loc = EQ.parse_region_string(region)
    if not loc:
        raise HTTPException(400, f"bad region: {region}")
    if release not in ("r5", "r6"):
        raise HTTPException(400, "release must be r5 or r6")
    return EQ.genes_in_region(*loc, release=release)


@app.get("/api/lift/{region}")
def api_lift(region: str, from_release: str = "r5"):
    """Lift a chromosome region between release 5 and release 6 coordinates."""
    from . import embed_query as EQ
    loc = EQ.parse_region_string(region)
    if not loc:
        raise HTTPException(400, f"bad region: {region}")
    if from_release not in ("r5", "r6"):
        raise HTTPException(400, "from_release must be r5 or r6")
    return EQ.lift_region(*loc, from_release=from_release)


@app.get("/api/semantic")
def api_semantic(q: str, limit: int = 20, region: Optional[str] = None,
                 release: str = "r6"):
    from . import embed_query as EQ
    return EQ.hybrid_query(region, q, top_k=limit, release=release)


@app.get("/ask", response_class=HTMLResponse)
def ask_page(request: Request, q: str = "", region: Optional[str] = None,
             release: str = "r6", limit: int = 10):
    from . import embed_query as EQ
    result = None
    if q:
        try:
            result = EQ.hybrid_query(region, q, top_k=limit, release=release)
        except Exception as e:
            result = {"error": str(e)}
    return TEMPLATES.TemplateResponse("ask.html", {
        "request": request, "q": q, "region": region, "release": release,
        "result": result,
    })


# -------------------- QTL workspace -------------------- #

@app.get("/qtl", response_class=HTMLResponse)
def qtl_list(request: Request):
    from . import qtl_rank as QR, qtl_overlap as QO
    qtls = QR.list_qtls(DB)
    overlaps = QO.coord_overlap(DB)
    # Sort QTLs by release_orig (r6 first), then by neg_log_p descending
    qtls.sort(key=lambda q: (q["release_orig"] == "r5",
                             -(q["neg_log_p"] or 0)))
    return TEMPLATES.TemplateResponse("qtl_list.html", {
        "request": request, "qtls": qtls, "overlaps": overlaps,
    })


@app.get("/qtl/{qtl_id}", response_class=HTMLResponse)
def qtl_detail(request: Request, qtl_id: str, topk: int = 25):
    from . import qtl_rank as QR, qtl_overlap as QO
    result = QR.rank_qtl(DB, qtl_id, topk=topk)
    if "error" in result:
        raise HTTPException(404, result["error"])
    # Also surface any cross-QTL overlaps involving this QTL
    overlaps = [o for o in QO.coord_overlap(DB)
                if o["qtl_a"] == qtl_id or o["qtl_b"] == qtl_id]
    return TEMPLATES.TemplateResponse("qtl_detail.html", {
        "request": request, "result": result, "overlaps": overlaps,
    })


@app.get("/qtl-overlap/{a}/{b}", response_class=HTMLResponse)
def qtl_overlap_detail(request: Request, a: str, b: str, topk: int = 50):
    from . import qtl_overlap as QO
    detail = QO.shared_genes(DB, a, b, topk=topk)
    return TEMPLATES.TemplateResponse("qtl_overlap.html", {
        "request": request, "a": a, "b": b, "detail": detail,
    })


@app.get("/api/qtl")
def api_qtl_list():
    from . import qtl_rank as QR
    return QR.list_qtls(DB)


@app.get("/api/qtl/{qtl_id}")
def api_qtl_rank(qtl_id: str, topk: int = 50):
    from . import qtl_rank as QR
    return QR.rank_qtl(DB, qtl_id, topk=topk)


@app.get("/api/qtl-overlap")
def api_qtl_overlap():
    from . import qtl_overlap as QO
    return QO.coord_overlap(DB)


@app.get("/api/qtl-overlap/{a}/{b}")
def api_qtl_overlap_detail(a: str, b: str, topk: int = 50):
    from . import qtl_overlap as QO
    return QO.shared_genes(DB, a, b, topk=topk)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8765)
