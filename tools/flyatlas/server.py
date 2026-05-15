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
                limit: int = 50):
    results = []
    if q:
        try:
            results = Q.search(DB, q, category=category, direction=direction,
                              confidence=confidence, tissue=tissue, limit=limit)
        except Exception as e:
            results = []
    return TEMPLATES.TemplateResponse("search.html", {
        "request": request, "q": q, "results": results,
        "category": category, "direction": direction,
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8765)
