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
    rows = Q.search(args.db, args.query,
                    category=args.category, direction=args.direction,
                    confidence=args.confidence, tissue=args.tissue,
                    limit=args.limit)
    if args.json:
        print(json.dumps(rows, indent=2, ensure_ascii=False)); return
    print(cfmt(f"Found {len(rows)} genes for: ", "bold") + cfmt(args.query, "cyan"))
    print(hr())
    for r in rows:
        print(f"{cfmt(r['symbol'], 'cyan', 'bold')} {cfmt('('+r['fbgn']+')', 'dim')} "
              f"{cfmt('· bullets='+str(r['n_bullets']), 'dim')}")
        snip = r.get("snip") or ""
        if snip:
            # Replace bold markers
            snip = snip.replace("<b>", "\033[1m").replace("</b>", "\033[22m") if use_color() else snip.replace("<b>","").replace("</b>","")
            print(wrap(snip, indent="  "))
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

    sp = sub.add_parser("search", help="FTS5 full-text search across summary+bullets")
    sp.add_argument("query")
    sp.add_argument("--category")
    sp.add_argument("--direction", choices=["loss_of_function","gain_of_function","either","unknown"])
    sp.add_argument("--confidence", choices=["high","medium","low"])
    sp.add_argument("--tissue")
    sp.add_argument("--limit", type=int, default=50)
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
