from __future__ import annotations
"""flyatlas CLI — terminal access to the fly phenotype atlas.

Quick start:
  python -m flyatlas.build              # one-time: build atlas.db
  python -m flyatlas.cli gene chico     # show one gene
  python -m flyatlas.cli search 'lethal AND eye' --confidence high
  python -m flyatlas.cli disease 254100
  python -m flyatlas.cli ortholog IRS1
  python -m flyatlas.cli paper FBrf0210226
  python -m flyatlas.cli tissue eye
  python -m flyatlas.cli category disease_model
  python -m flyatlas.cli stats
  python -m flyatlas.cli serve          # launch Web UI

All commands accept --json for piping.
"""
import argparse
import json
import sys
import textwrap
from pathlib import Path

from . import DB_PATH
from . import query as Q


# ----------------------- TTY renderers ----------------------- #

C = {
    "reset": "\033[0m", "bold": "\033[1m", "dim": "\033[2m",
    "blue": "\033[34m", "cyan": "\033[36m", "green": "\033[32m",
    "yellow": "\033[33m", "red": "\033[31m", "mag": "\033[35m",
}


def use_color() -> bool:
    return sys.stdout.isatty()


def cfmt(s: str, *codes: str) -> str:
    if not use_color():
        return s
    return "".join(C[c] for c in codes) + s + C["reset"]


def hr(ch: str = "─", width: int = 72) -> str:
    return cfmt(ch * width, "dim")


def wrap(text: str, indent: str = "  ", width: int = 78) -> str:
    return textwrap.fill(text or "", width=width, initial_indent=indent,
                         subsequent_indent=indent)


# ----------------------- formatters ----------------------- #

def render_gene(g: dict, *, max_bullets: int = 999):
    print(cfmt(f"{g['symbol']}", "bold", "cyan"), cfmt(f"({g['fbgn']})", "dim"))
    if g.get("synonyms"):
        aliases = [s["synonym"] for s in g["synonyms"]
                   if s["synonym"] != g["symbol"] and s.get("type") != "secondary_fbgn"][:6]
        if aliases:
            print(cfmt("  aliases: ", "dim") + ", ".join(aliases))
    model = f"{g.get('provider','?')}/{g.get('model_id','?')}"
    print(cfmt(f"  distilled by: ", "dim") + model
          + cfmt(f" · pubs={g.get('n_pubs_total','?')}"
                 f" · bullets={g.get('n_bullets')} · refs={g.get('n_refs')}", "dim"))
    print(hr())
    print(cfmt("SUMMARY", "bold"))
    print(wrap(g.get("summary") or "(no summary)"))
    print()

    if g.get("bullets"):
        print(cfmt("PHENOTYPES", "bold"))
        # Group by category
        by_cat: dict[str, list] = {}
        for b in g["bullets"]:
            by_cat.setdefault(b.get("category") or "other", []).append(b)
        for cat, bs in by_cat.items():
            print(cfmt(f"\n  ▸ {cat}", "yellow", "bold"))
            for b in bs[:max_bullets]:
                conf = b.get("confidence") or "?"
                conf_color = {"high":"green","medium":"yellow","low":"red"}.get(conf,"dim")
                marker = cfmt(f"[{conf}]", conf_color)
                dir_ = b.get("direction") or ""
                dir_str = cfmt(f"({dir_})", "dim") if dir_ else ""
                print(f"    {marker} {b['phenotype']} {dir_str}")
                ev = b.get("evidence_text") or ""
                if ev:
                    print(cfmt(f"        ↳ {ev[:160]}", "dim"))
                cites = b.get("citations") or []
                # show paper minirefs only
                paper_cites = [c["miniref"] for c in cites if c.get("type") == "fbrf" and c.get("miniref")]
                if paper_cites:
                    print(cfmt(f"        cited: {'; '.join(paper_cites[:3])}", "dim"))

    if g.get("references"):
        print()
        print(cfmt("REFERENCES", "bold"))
        for r in g["references"][:15]:
            mr = r.get("miniref") or r["fbrf"]
            url = r.get("pubmed_url") or r.get("doi_url") or r.get("flybase_url")
            print(f"  • {mr}")
            if url:
                print(cfmt(f"    {url}", "dim", "blue"))
        if len(g["references"]) > 15:
            print(cfmt(f"  …and {len(g['references']) - 15} more", "dim"))

    if g.get("orthologs"):
        print()
        print(cfmt("CROSS-SPECIES", "bold"))
        humans = [o for o in g["orthologs"] if o["species"] == "human"]
        mice = [o for o in g["orthologs"] if o["species"] == "mouse"]
        if humans:
            hs = sorted(humans, key=lambda x: -(x.get("diopt_score") or 0))
            print("  human: " + ", ".join(
                f"{o['symbol']}({o.get('diopt_score','?')})" for o in hs[:6]))
        if mice:
            ms = sorted(mice, key=lambda x: -(x.get("diopt_score") or 0))
            print("  mouse: " + ", ".join(
                f"{o['symbol']}({o.get('diopt_score','?')})" for o in ms[:6]))

    if g.get("diseases"):
        with_omim = [d for d in g["diseases"] if d.get("omim_id")]
        if with_omim:
            print()
            print(cfmt("DISEASE LINKS", "bold"))
            for d in with_omim[:8]:
                via = f" (via {d['via_species']} {d['via_symbol']})" if d.get("via_symbol") else ""
                print(f"  • OMIM {d['omim_id']}: {d['name']}{via}")


def render_table(rows: list[dict], cols: list[tuple[str, str, int]]):
    if not rows:
        print(cfmt("(no results)", "dim"))
        return
    head = "  ".join(cfmt(label.ljust(w), "bold") for _, label, w in cols)
    print(head)
    print(hr())
    for r in rows:
        line = "  ".join(
            (str(r.get(key) or "")[:w]).ljust(w)
            for key, _, w in cols
        )
        print(line)


# ----------------------- commands ----------------------- #

def cmd_gene(args):
    fbgn = Q.resolve_gene(args.db, args.query)
    if not fbgn:
        print(cfmt(f"No match for '{args.query}'", "red"), file=sys.stderr)
        sys.exit(1)
    g = Q.get_gene(args.db, fbgn)
    if args.json:
        print(json.dumps(g, indent=2, ensure_ascii=False))
    else:
        render_gene(g, max_bullets=args.max_bullets)


def cmd_search(args):
    """Default = semantic (Gemini); use --keyword for FTS5 string match."""
    if args.keyword:
        rows = Q.search(args.db, args.query,
                        category=args.category, direction=args.direction,
                        confidence=args.confidence, tissue=args.tissue,
                        limit=args.limit)
        mode_label = "keyword (FTS5)"
    else:
        from . import embed_query as EQ
        hybrid = EQ.hybrid_query(args.region, args.query, top_k=args.limit)
        rows = hybrid.get("ranked", [])
        mode_label = "semantic (Gemini)"
    if args.json:
        print(json.dumps(rows, indent=2, ensure_ascii=False)); return
    region_str = f" in region {args.region}" if args.region else ""
    print(cfmt(f"Found {len(rows)} genes for: ", "bold") + cfmt(args.query, "cyan")
          + cfmt(f"  [{mode_label}{region_str}]", "dim"))
    print(hr())
    for r in rows:
        score_str = cfmt(f" score={r['score']:.3f}", "green") if r.get("score") is not None else ""
        chr_str = cfmt(f" {r.get('chr','')}:{r.get('start','')}", "dim") if r.get('chr') else ""
        print(f"{cfmt(r['symbol'], 'cyan', 'bold')} {cfmt('('+r['fbgn']+')', 'dim')}"
              + chr_str + score_str
              + cfmt(f' · bullets={r.get("n_bullets","?")}', "dim"))
        snip = r.get("snip") or ""
        if snip:
            snip = snip.replace("<b>", "\033[1m").replace("</b>", "\033[22m") if use_color() else snip.replace("<b>","").replace("</b>","")
            print(wrap(snip, indent="  "))
        elif r.get("summary"):
            print(wrap(r["summary"][:280], indent="  "))
        print()


def cmd_disease(args):
    rows = Q.genes_by_disease(args.db, args.term, limit=args.limit)
    if args.json: print(json.dumps(rows, indent=2)); return
    print(cfmt(f"{len(rows)} genes link to ", "bold") + cfmt(args.term, "cyan"))
    render_table(rows, [("fbgn","FBgn",13),("symbol","Symbol",16),
                        ("via_symbol","via",10),("disease_name","Disease",40)])


def cmd_ortholog(args):
    rows = Q.genes_by_ortholog(args.db, args.symbol, limit=args.limit)
    if args.json: print(json.dumps(rows, indent=2)); return
    print(cfmt(f"{len(rows)} fly genes ortholog to ", "bold") + cfmt(args.symbol, "cyan"))
    render_table(rows, [("fbgn","FBgn",13),("symbol","Symbol",16),
                        ("diopt_score","DIOPT",6),("species","Species",6)])


def cmd_paper(args):
    rows = Q.genes_by_paper(args.db, args.id, limit=args.limit)
    if args.json: print(json.dumps(rows, indent=2)); return
    print(cfmt(f"{len(rows)} genes cite ", "bold") + cfmt(args.id, "cyan"))
    render_table(rows, [("fbgn","FBgn",13),("symbol","Symbol",16),
                        ("miniref","Reference",55)])


def cmd_tissue(args):
    rows = Q.genes_by_tissue(args.db, args.term, limit=args.limit)
    if args.json: print(json.dumps(rows, indent=2)); return
    print(cfmt(f"{len(rows)} genes with bullets tagged ", "bold") + cfmt(args.term, "cyan"))
    render_table(rows, [("fbgn","FBgn",13),("symbol","Symbol",16),
                        ("n_bullets","Bullets",8),("summary","Summary",45)])


def cmd_category(args):
    rows = Q.genes_by_category(args.db, args.cat, confidence=args.confidence,
                                limit=args.limit)
    if args.json: print(json.dumps(rows, indent=2)); return
    print(cfmt(f"{len(rows)} genes have ", "bold") + cfmt(args.cat, "cyan")
          + cfmt(" phenotype bullets", "bold"))
    render_table(rows, [("fbgn","FBgn",13),("symbol","Symbol",16),
                        ("n_in_cat","#bullets",10),("summary","Summary",45)])


def cmd_region(args):
    from . import embed_query as EQ
    loc = EQ.parse_region_string(args.region)
    if not loc:
        print(cfmt(f"bad region: {args.region}", "red"), file=sys.stderr); sys.exit(1)
    chr_, start, end = loc
    rows = EQ.genes_in_region(chr_, start, end)
    if args.json: print(json.dumps(rows, indent=2)); return
    print(cfmt(f"{len(rows)} genes in {chr_}:{start:,}-{end:,}", "bold"))
    render_table(rows, [("fbgn","FBgn",13),("symbol","Symbol",16),
                        ("start","Start",12),("n_bullets","Bullets",8),
                        ("summary","Summary",40)])


def cmd_export_bed(args):
    """Dump every gene's chr/start/end/fbgn/symbol as a BED-like TSV.
    Sorted by chromosome + start. Suitable for `bedtools intersect`."""
    import sqlite3
    c = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    sql = ("SELECT chr, start, end, fbgn, symbol, n_bullets FROM genes "
           "WHERE chr IS NOT NULL ORDER BY chr, start")
    rows = list(c.execute(sql))
    out = sys.stdout if args.out == "-" else open(args.out, "w")
    if args.format == "bed":
        # BED6: chrom start end name score strand   (we use n_bullets as score, '+' placeholder)
        for r in rows:
            out.write(f"{r['chr']}\t{r['start']}\t{r['end']}\t{r['fbgn']}|{r['symbol']}\t{r['n_bullets']}\t+\n")
    elif args.format == "tsv":
        out.write("chr\tstart\tend\tfbgn\tsymbol\tn_bullets\n")
        for r in rows:
            out.write(f"{r['chr']}\t{r['start']}\t{r['end']}\t{r['fbgn']}\t{r['symbol']}\t{r['n_bullets']}\n")
    else:  # json
        out.write(json.dumps([dict(r) for r in rows], indent=2))
    if out is not sys.stdout: out.close()
    print(f"  → {len(rows)} genes written to {args.out} ({args.format})", file=sys.stderr)


def cmd_regions(args):
    """Batch region query: input a BED file (or tab-separated chr/start/end on
    stdin), output for each region the genes in it."""
    from . import embed_query as EQ
    import csv
    src = sys.stdin if args.input == "-" else open(args.input)
    out_rows = []
    region_count = 0
    for line in src:
        line = line.strip()
        if not line or line.startswith("#") or line.lower().startswith("chr\t"):
            continue
        parts = line.split("\t") if "\t" in line else line.split()
        if len(parts) < 3: continue
        chr_, start, end = parts[0], int(parts[1]), int(parts[2])
        label = parts[3] if len(parts) > 3 else f"{chr_}:{start}-{end}"
        genes = EQ.genes_in_region(chr_, start, end)
        region_count += 1
        for g in genes:
            out_rows.append({"region": label, **g})
    if src is not sys.stdin: src.close()

    if args.json: print(json.dumps(out_rows, indent=2)); return
    out = sys.stdout if args.out == "-" else open(args.out, "w")
    out.write("region\tchr\tstart\tend\tfbgn\tsymbol\tn_bullets\n")
    for r in out_rows:
        out.write(f"{r['region']}\t{r['chr']}\t{r['start']}\t{r['end']}\t{r['fbgn']}\t{r['symbol']}\t{r['n_bullets']}\n")
    if out is not sys.stdout: out.close()
    print(f"  → {region_count} regions, {len(out_rows)} gene rows", file=sys.stderr)


def cmd_semantic(args):
    from . import embed_query as EQ
    results = EQ.semantic_search(args.query, top_k=args.limit)
    if args.json: print(json.dumps(results, indent=2)); return
    print(cfmt(f"Top {len(results)} semantic matches for: ", "bold") + cfmt(args.query, "cyan"))
    print(hr())
    c = __import__("sqlite3").connect(f"file:{args.db}?mode=ro", uri=True)
    c.row_factory = __import__("sqlite3").Row
    for r in results:
        g = c.execute("SELECT symbol, summary, n_bullets FROM genes WHERE fbgn=?", (r["fbgn"],)).fetchone()
        sym = g["symbol"] if g else "?"
        print(f"  {cfmt(sym, 'cyan', 'bold')} {cfmt('('+r['fbgn']+')', 'dim')} "
              + cfmt(f"score={r['score']:.3f}", "green"))
        if g and g["summary"]:
            print(wrap(g["summary"][:240], indent="    "))
        print()


def cmd_ask(args):
    """Hybrid: region (optional) + phenotype semantic search."""
    from . import embed_query as EQ
    out = EQ.hybrid_query(args.region, args.query, top_k=args.limit)
    if args.json: print(json.dumps(out, indent=2)); return
    if "error" in out:
        print(cfmt(out["error"], "red"), file=sys.stderr); sys.exit(1)
    if out.get("region"):
        print(cfmt(f"Region {out['region']}: ", "bold") + f"{out['region_gene_count']} genes")
    if out.get("query"):
        print(cfmt(f"Phenotype query: ", "bold") + cfmt(out["query"], "cyan"))
    print(hr())
    for g in out.get("ranked", []):
        print(f"  {cfmt(g['symbol'], 'cyan', 'bold')} {cfmt('('+g['fbgn']+')', 'dim')} "
              f"{cfmt(g.get('chr') or '', 'dim')}  "
              + cfmt(f"score={g['score']:.3f}", "green"))
        print(wrap((g.get("summary") or "")[:240], indent="    "))
        print()


def cmd_stats(args):
    s = Q.stats(args.db)
    if args.json: print(json.dumps(s, indent=2)); return
    print(cfmt("FLY-DISTILL ATLAS", "bold", "cyan"))
    print(hr())
    print(f"  genes:    {s['n_genes']:>6}")
    print(f"  bullets:  {s['n_bullets']:>6}")
    print(f"  refs:     {s['n_refs']:>6}")
    print(f"  diseases: {s['n_diseases']:>6}")
    print()
    print(cfmt("by backend:", "bold"))
    for k,v in s["by_provider"].items(): print(f"  {k or '?':12s} {v}")
    print()
    print(cfmt("phenotype categories:", "bold"))
    for k,v in s["by_category"].items(): print(f"  {k or '?':18s} {v}")
    print()
    print(cfmt("confidence:", "bold"))
    for k,v in s["by_confidence"].items(): print(f"  {k or '?':8s} {v}")
    print()
    print(cfmt("top tissues:", "bold"))
    for tissue, n in s["top_tissues"]: print(f"  {tissue:20s} {n}")


def cmd_serve(args):
    import uvicorn
    from .server import app
    uvicorn.run(app, host=args.host, port=args.port)


# ----------------------- main ----------------------- #

def build_parser():
    p = argparse.ArgumentParser(prog="flyatlas",
                                description="fly-distill phenotype atlas — local index + Web UI")
    p.add_argument("--db", default=str(DB_PATH),
                   help=f"Path to atlas.db (default {DB_PATH})")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("gene", help="Show one gene by fbgn/symbol/synonym")
    sp.add_argument("query")
    sp.add_argument("--json", action="store_true")
    sp.add_argument("--max-bullets", type=int, default=999)
    sp.set_defaults(func=cmd_gene)

    sp = sub.add_parser("search", help="Default semantic (Gemini); --keyword for FTS5")
    sp.add_argument("query")
    sp.add_argument("--region", help="Optional region filter, e.g. 2L:5e6-6e6")
    sp.add_argument("--keyword", action="store_true", help="Use FTS5 keyword match instead of semantic")
    sp.add_argument("--category")
    sp.add_argument("--direction", choices=["loss_of_function","gain_of_function","either","unknown"])
    sp.add_argument("--confidence", choices=["high","medium","low"])
    sp.add_argument("--tissue")
    sp.add_argument("--limit", type=int, default=20)
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_search)

    sp = sub.add_parser("disease", help="Genes linked to a disease (OMIM ID or name)")
    sp.add_argument("term")
    sp.add_argument("--limit", type=int, default=200)
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_disease)

    sp = sub.add_parser("ortholog", help="Fly genes orthologous to a human/mouse gene")
    sp.add_argument("symbol")
    sp.add_argument("--limit", type=int, default=200)
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_ortholog)

    sp = sub.add_parser("paper", help="Genes citing an FBrf or PMID")
    sp.add_argument("id")
    sp.add_argument("--limit", type=int, default=500)
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_paper)

    sp = sub.add_parser("tissue", help="Genes with bullets tagged with a tissue")
    sp.add_argument("term")
    sp.add_argument("--limit", type=int, default=500)
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_tissue)

    sp = sub.add_parser("category", help="Genes with bullets in a category")
    sp.add_argument("cat", choices=[
        "behavior","morphology","lifespan_aging","development","reproduction",
        "metabolism","immune","sensory_neural","stress_response","disease_model",
        "expression_pattern","other"])
    sp.add_argument("--confidence", choices=["high","medium","low"])
    sp.add_argument("--limit", type=int, default=500)
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_category)

    sp = sub.add_parser("region", help="Genes in a chromosome region (e.g. 2L:5e6-6e6)")
    sp.add_argument("region", help="chr:start-end, e.g. 2L:5000000-6000000 or 2L:5e6-6e6")
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_region)

    sp = sub.add_parser("export-bed", help="Dump every gene's chr/start/end as BED/TSV/JSON (for bedtools intersect)")
    sp.add_argument("--out", default="-", help="output file or '-' for stdout")
    sp.add_argument("--format", choices=["bed","tsv","json"], default="bed")
    sp.set_defaults(func=cmd_export_bed)

    sp = sub.add_parser("regions", help="Batch region query from a BED file (stdin or file)")
    sp.add_argument("input", help="BED file path or '-' for stdin")
    sp.add_argument("--out", default="-")
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_regions)

    sp = sub.add_parser("semantic", help="Semantic phenotype search via Gemini embeddings")
    sp.add_argument("query", help="Free-text phenotype, e.g. 'pupa height' or 'alcohol sensitivity'")
    sp.add_argument("--limit", type=int, default=20)
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_semantic)

    sp = sub.add_parser("ask", help="Hybrid: region (optional) + semantic phenotype rank")
    sp.add_argument("query", help="Phenotype, e.g. 'pupa height'")
    sp.add_argument("--region", help="Chr:start-end filter (optional)")
    sp.add_argument("--limit", type=int, default=10)
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_ask)

    sp = sub.add_parser("stats", help="Atlas-wide statistics")
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_stats)

    sp = sub.add_parser("serve", help="Launch the Web UI")
    sp.add_argument("--host", default="127.0.0.1")
    sp.add_argument("--port", type=int, default=8765)
    sp.set_defaults(func=cmd_serve)

    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
