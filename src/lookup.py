"""FlyBase-style search CLI for the distilled gene index (schema v1.1).

Forward (give me everything about X):
  lookup.py gene per                # by fly symbol, FBgn, or ortholog symbol
  lookup.py gene FBgn0003068
  lookup.py gene DNM1

Reverse (which genes do X):
  lookup.py disease "Sleep"                       # substring on disease name
  lookup.py omim 604348                           # exact OMIM phenotype ID
  lookup.py category behavior --confidence high
  lookup.py ortholog human DNM1
  lookup.py ortholog mouse Per1
  lookup.py paper FBrf0261177                     # which genes cite this paper?
  lookup.py go BP "behavior"                      # genes with this GO slim category
  lookup.py tissue "Malpighian"                   # bullets affecting this tissue
  lookup.py stage adult --category behavior
  lookup.py allele per01                          # bullets mentioning this allele

Full-text:
  lookup.py phenotype "circadian rhythm"
  lookup.py phenotype "cocaine OR ethanol" --confidence high

Stats / explore:
  lookup.py stats
"""
import argparse
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "output" / "index" / "fly_distill.sqlite"


def conn():
    if not DB.exists():
        sys.exit(f"index not found: {DB}\nrun: python3 src/build_sqlite.py")
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c


def _conf_filter(args):
    return f" AND b.confidence = '{args.confidence}'" if args.confidence else ""


def _cat_filter(args):
    return f" AND b.category = '{args.category}'" if args.category else ""


# ---------- forward ----------

def cmd_gene(args):
    """Resolve query to a gene, with explicit ranking:
       1) exact FBgn
       2) current fly symbol
       3) any fly synonym (current → historical)
       4) ortholog symbol (with disambiguation if multiple fly genes share an ortholog)
    """
    c = conn()
    q = args.query
    # 1. exact FBgn
    row = c.execute("SELECT * FROM genes WHERE fbgn=?", (q,)).fetchone()
    if row:
        match_via = "exact FBgn"
    if not row:
        # 2. current symbol
        row = c.execute(
            "SELECT g.* FROM genes g WHERE g.symbol=? COLLATE NOCASE LIMIT 1", (q,)
        ).fetchone()
        if row:
            match_via = f"current symbol '{q}'"
    if not row:
        # 3. synonym (prefer current synonym_type)
        row = c.execute(
            "SELECT g.* FROM genes g JOIN gene_synonyms s ON s.fbgn=g.fbgn "
            "WHERE s.synonym=? COLLATE NOCASE ORDER BY s.is_current DESC LIMIT 1", (q,)
        ).fetchone()
        if row:
            match_via = f"synonym '{q}'"
    if not row:
        # 4. ortholog — handle multi-hit
        orthos = c.execute(
            "SELECT o.species, o.fbgn, o.diopt_score, o.diopt_max, g.symbol AS fly_symbol "
            "FROM orthologs o JOIN genes g ON g.fbgn=o.fbgn "
            "WHERE o.symbol=? COLLATE NOCASE ORDER BY o.diopt_score DESC",
            (q,),
        ).fetchall()
        if len(orthos) == 1:
            row = c.execute("SELECT * FROM genes WHERE fbgn=?",
                            (orthos[0]["fbgn"],)).fetchone()
            match_via = f"{orthos[0]['species']} ortholog → fly {orthos[0]['fly_symbol']}"
        elif len(orthos) > 1:
            print(f"'{q}' matches {len(orthos)} fly genes via ortholog. Ranked by DIOPT:")
            for o in orthos:
                print(f"  fly {o['fly_symbol']:8} ({o['fbgn']})  "
                      f"via {o['species']} ortholog  DIOPT={o['diopt_score']}/{o['diopt_max']}")
            print(f"\nPick one and rerun with that FBgn or fly symbol.")
            return
    if not row:
        sys.exit(f"no gene found for '{q}'")
    print(f"(matched via {match_via})\n")

    print(f"## {row['symbol']}  ({row['fbgn']})")
    syns = c.execute("SELECT synonym FROM gene_synonyms WHERE fbgn=?",
                     (row["fbgn"],)).fetchall()
    if syns:
        print(f"   synonyms: {', '.join(s['synonym'] for s in syns)}")
    print(f"   distilled {row['distilled_at']} via {row['source_release']}")
    print()
    print(f"**Snapshot.** {row['snapshot']}")
    print()

    # GO slim categories
    go = c.execute(
        "SELECT domain, term FROM go_slim WHERE fbgn=? ORDER BY domain, term",
        (row["fbgn"],)).fetchall()
    if go:
        by_dom = {}
        for x in go:
            by_dom.setdefault(x["domain"], []).append(x["term"])
        print("### GO categories")
        for dom, ts in by_dom.items():
            print(f"  {dom}: {', '.join(ts)}")
        print()

    # bullets grouped by category
    bullets = c.execute(
        "SELECT * FROM bullets WHERE fbgn=? ORDER BY bullet_id", (row["fbgn"],)
    ).fetchall()
    by_cat = {}
    for b in bullets:
        by_cat.setdefault(b["category"], []).append(b)
    for cat in sorted(by_cat):
        print(f"### {cat}")
        for b in by_cat[cat]:
            conf = b["confidence"] or "-"
            spec = b["text_specificity"] or "-"
            cits = [r["cite_value"] for r in c.execute(
                "SELECT cite_value FROM bullet_citations WHERE bullet_id=?",
                (b["bullet_id"],)).fetchall()]
            tis = [r["tissue"] for r in c.execute(
                "SELECT tissue FROM bullet_tissues WHERE bullet_id=?",
                (b["bullet_id"],)).fetchall()]
            print(f"  [{conf}/{spec}] {b['phenotype']}")
            if cits or tis:
                tag = []
                if cits: tag.append("cites: " + ", ".join(cits))
                if tis: tag.append("tissue: " + ", ".join(tis))
                print(f"        {' | '.join(tag)}")
        print()

    h_orth = c.execute(
        "SELECT * FROM orthologs WHERE fbgn=? AND species='human' "
        "ORDER BY diopt_score DESC", (row["fbgn"],)).fetchall()
    m_orth = c.execute(
        "SELECT * FROM orthologs WHERE fbgn=? AND species='mouse' "
        "ORDER BY diopt_score DESC", (row["fbgn"],)).fetchall()
    print("### cross-species")
    if h_orth:
        print("  Human orthologs (DIOPT):")
        for o in h_orth:
            print(f"    {o['symbol']:8} {o['diopt_score']}/{o['diopt_max']}  Entrez {o['entrez_id']}  — {o['name']}")
    diseases = c.execute(
        "SELECT disease_name, omim_id, source, via_ortholog_species, via_ortholog_symbol, via_ortholog_diopt "
        "FROM diseases WHERE fbgn=?",
        (row["fbgn"],)).fetchall()
    if diseases:
        print("  Human disease links:")
        for d in diseases:
            tag = f"OMIM:{d['omim_id']}" if d["omim_id"] else f"({d['source']})"
            via = ""
            if d["via_ortholog_symbol"]:
                via = f"  via {d['via_ortholog_species']} ortholog {d['via_ortholog_symbol']} ({d['via_ortholog_diopt']}/14)"
            print(f"    • [{tag}] {d['disease_name']}{via}")
    if m_orth:
        print("  Mouse orthologs (DIOPT):")
        for o in m_orth:
            print(f"    {o['symbol']:8} {o['diopt_score']}/{o['diopt_max']}  Entrez {o['entrez_id']}  — {o['name']}")
    mp = c.execute(
        "SELECT phenotype_name FROM mouse_phenotypes WHERE fbgn=?",
        (row["fbgn"],)).fetchall()
    if mp:
        print("  Mouse phenotype links:")
        for p in mp:
            print(f"    • {p['phenotype_name']}")
    if row["notes"]:
        print()
        print("### caveat from model")
        print(f"  {row['notes']}")


# ---------- reverse ----------

def cmd_disease(args):
    c = conn()
    rows = c.execute(
        "SELECT DISTINCT g.fbgn, g.symbol, d.disease_name, d.omim_id, d.source "
        "FROM diseases d JOIN genes g ON g.fbgn=d.fbgn "
        "WHERE d.disease_name LIKE ? ORDER BY g.symbol",
        (f"%{args.query}%",),
    ).fetchall()
    if not rows:
        print(f"no disease entries matching '{args.query}'")
        return
    for r in rows:
        omim = f"OMIM:{r['omim_id']}" if r["omim_id"] else f"({r['source']})"
        print(f"  {r['symbol']:8}  {r['fbgn']}    {omim:20}  {r['disease_name']}")


def cmd_omim(args):
    c = conn()
    rows = c.execute(
        "SELECT g.fbgn, g.symbol, d.disease_name "
        "FROM diseases d JOIN genes g ON g.fbgn=d.fbgn "
        "WHERE d.omim_id=?",
        (args.query,),
    ).fetchall()
    if not rows:
        print(f"no genes linked to OMIM {args.query}")
        return
    for r in rows:
        print(f"  {r['symbol']:8}  {r['fbgn']}    → {r['disease_name']}")


def cmd_paper(args):
    c = conn()
    rows = c.execute(
        "SELECT DISTINCT g.fbgn, g.symbol, b.bullet_id, b.category, b.phenotype "
        "FROM bullet_citations bc "
        "JOIN bullets b ON b.bullet_id=bc.bullet_id "
        "JOIN genes g ON g.fbgn=b.fbgn "
        "WHERE bc.cite_type='fbrf' AND bc.cite_value=? "
        "ORDER BY g.symbol, b.bullet_id",
        (args.query,),
    ).fetchall()
    if not rows:
        print(f"no bullets cite paper {args.query}")
        return
    print(f"paper {args.query} cited by {len(rows)} bullet(s):")
    for r in rows:
        print(f"  {r['symbol']:8}  [{r['category']:18}]  {r['phenotype']}")


def cmd_category(args):
    c = conn()
    rows = c.execute(
        f"SELECT b.bullet_id, b.phenotype, b.confidence, b.text_specificity, g.symbol "
        f"FROM bullets b JOIN genes g ON g.fbgn=b.fbgn "
        f"WHERE b.category=? {_conf_filter(args)} "
        f"ORDER BY g.symbol, b.bullet_id LIMIT ?",
        (args.query, args.limit),
    ).fetchall()
    if not rows:
        print(f"no bullets in category '{args.query}'")
        return
    print(f"{len(rows)} bullets in [{args.query}]"
          + (f" (confidence={args.confidence})" if args.confidence else "")
          + ":")
    for r in rows:
        c_ = r['confidence'] or '-'
        s_ = r['text_specificity'] or '-'
        print(f"  [{c_}/{s_}] {r['symbol']:8}  {r['phenotype']}")


def cmd_ortholog(args):
    c = conn()
    rows = c.execute(
        "SELECT o.symbol AS ortho, o.diopt_score, o.diopt_max, o.entrez_id, "
        "       g.fbgn, g.symbol AS fly_symbol "
        "FROM orthologs o JOIN genes g ON g.fbgn=o.fbgn "
        "WHERE o.species=? AND (o.symbol=? COLLATE NOCASE OR o.entrez_id=?) "
        "ORDER BY o.diopt_score DESC",
        (args.species, args.query, args.query),
    ).fetchall()
    if not rows:
        print(f"no {args.species} ortholog matching '{args.query}'")
        return
    for r in rows:
        print(f"  {args.species:5} {r['ortho']:8} (Entrez {r['entrez_id']}, "
              f"DIOPT {r['diopt_score']}/{r['diopt_max']}) "
              f"→ fly {r['fly_symbol']} ({r['fbgn']})")


def cmd_go(args):
    c = conn()
    domain_map = {"BP": "biological_process", "MF": "molecular_function",
                  "CC": "cellular_component",
                  "biological_process": "biological_process",
                  "molecular_function": "molecular_function",
                  "cellular_component": "cellular_component"}
    domain = domain_map.get(args.domain, args.domain)
    rows = c.execute(
        "SELECT g.fbgn, g.symbol, t.term FROM go_slim t "
        "JOIN genes g ON g.fbgn=t.fbgn "
        "WHERE t.domain=? AND t.term LIKE ? "
        "ORDER BY g.symbol",
        (domain, f"%{args.query}%"),
    ).fetchall()
    if not rows:
        print(f"no genes with GO {domain} matching '{args.query}'")
        return
    for r in rows:
        print(f"  {r['symbol']:8}  {r['fbgn']}    → {domain}: {r['term']}")


def cmd_tissue(args):
    c = conn()
    rows = c.execute(
        f"SELECT g.symbol, b.bullet_id, b.category, b.phenotype, b.confidence, "
        f"       bt.tissue "
        f"FROM bullet_tissues bt JOIN bullets b ON b.bullet_id=bt.bullet_id "
        f"JOIN genes g ON g.fbgn=b.fbgn "
        f"WHERE bt.tissue LIKE ? {_conf_filter(args)} {_cat_filter(args)} "
        f"ORDER BY g.symbol, b.bullet_id LIMIT ?",
        (f"%{args.query}%", args.limit),
    ).fetchall()
    if not rows:
        print(f"no bullets affecting tissue '{args.query}'")
        return
    for r in rows:
        c_ = r['confidence'] or '-'
        print(f"  [{c_}] {r['symbol']:8} [{r['category']:18}] ({r['tissue']}) {r['phenotype']}")


def cmd_stage(args):
    c = conn()
    rows = c.execute(
        f"SELECT g.symbol, b.category, b.phenotype, b.confidence, bs.stage "
        f"FROM bullet_life_stages bs JOIN bullets b ON b.bullet_id=bs.bullet_id "
        f"JOIN genes g ON g.fbgn=b.fbgn "
        f"WHERE bs.stage=? {_conf_filter(args)} {_cat_filter(args)} "
        f"ORDER BY g.symbol LIMIT ?",
        (args.query, args.limit),
    ).fetchall()
    if not rows:
        print(f"no bullets in life stage '{args.query}'")
        return
    for r in rows:
        c_ = r['confidence'] or '-'
        print(f"  [{c_}] {r['symbol']:8} [{r['category']:18}] {r['phenotype']}")


def cmd_allele(args):
    c = conn()
    rows = c.execute(
        "SELECT g.symbol, b.category, b.phenotype, ba.allele "
        "FROM bullet_alleles ba JOIN bullets b ON b.bullet_id=ba.bullet_id "
        "JOIN genes g ON g.fbgn=b.fbgn "
        "WHERE ba.allele=? COLLATE NOCASE ORDER BY g.symbol",
        (args.query,),
    ).fetchall()
    if not rows:
        print(f"no bullets mention allele '{args.query}'")
        return
    for r in rows:
        print(f"  {r['symbol']:8} [{r['category']:18}] ({r['allele']}) {r['phenotype']}")


def cmd_phenotype(args):
    c = conn()
    rows = c.execute(
        f"SELECT g.symbol, b.bullet_id, b.category, b.phenotype, b.confidence, b.text_specificity, "
        f"       snippet(bullets_fts, 0, '«', '»', '…', 16) AS hit "
        f"FROM bullets_fts JOIN bullets b ON b.rowid=bullets_fts.rowid "
        f"JOIN genes g ON g.fbgn=b.fbgn "
        f"WHERE bullets_fts MATCH ? {_conf_filter(args)} {_cat_filter(args)} "
        f"ORDER BY rank LIMIT ?",
        (args.query, args.limit),
    ).fetchall()
    if not rows:
        print(f"no bullets matching '{args.query}'")
        return
    print(f"{len(rows)} bullets matching FTS '{args.query}':")
    for r in rows:
        c_ = r['confidence'] or '-'
        s_ = r['text_specificity'] or '-'
        print(f"  [{c_}/{s_}] [{r['category']:18}] {r['symbol']:8}  {r['hit']}")


def cmd_stats(args):
    c = conn()
    print("Index summary:")
    for sql, label in [
        ("SELECT COUNT(*) FROM genes", "genes"),
        ("SELECT COUNT(*) FROM bullets", "bullets"),
        ("SELECT COUNT(*) FROM bullet_citations", "citations"),
        ("SELECT COUNT(DISTINCT cite_value) FROM bullet_citations WHERE cite_type='fbrf'", "unique FBrfs cited"),
        ("SELECT COUNT(*) FROM bullet_tissues", "tissue tags"),
        ("SELECT COUNT(DISTINCT tissue) FROM bullet_tissues", "unique tissues"),
        ("SELECT COUNT(*) FROM orthologs", "ortholog rows"),
        ("SELECT COUNT(*) FROM diseases", "disease entries"),
        ("SELECT COUNT(*) FROM diseases WHERE omim_id IS NOT NULL", "with OMIM ID"),
        ("SELECT COUNT(*) FROM go_terms", "GO term annotations"),
    ]:
        n = c.execute(sql).fetchone()[0]
        print(f"  {label:25} {n:>6}")
    print()
    print("Bullets by category:")
    for r in c.execute(
        "SELECT category, COUNT(*) n FROM bullets GROUP BY category ORDER BY n DESC"
    ):
        print(f"  {r['category']:20} {r['n']:5}")
    print()
    print("Bullets by confidence × specificity:")
    for r in c.execute(
        "SELECT confidence, specificity, COUNT(*) n FROM bullets "
        "GROUP BY confidence, specificity ORDER BY confidence, specificity"
    ):
        c_ = r['confidence'] or '∅'
        s_ = r['text_specificity'] or '∅'
        print(f"  conf={c_:6} × spec={s_:6}  {r['n']:5}")
    print()
    print("Top 10 tissues by # bullets:")
    for r in c.execute(
        "SELECT tissue, COUNT(*) n FROM bullet_tissues GROUP BY tissue ORDER BY n DESC LIMIT 10"
    ):
        print(f"  {r['tissue']:30} {r['n']:5}")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    def add_filter_args(p):
        p.add_argument("--confidence", choices=["high", "medium", "low"], default=None)
        p.add_argument("--category", choices=list({
            "behavior", "morphology", "lifespan_aging", "development",
            "reproduction", "metabolism", "immune", "sensory_neural",
            "stress_response", "disease_model", "expression_pattern", "other",
        }), default=None)
        p.add_argument("--limit", type=int, default=50)

    p = sub.add_parser("gene")
    p.add_argument("query"); p.set_defaults(fn=cmd_gene)

    p = sub.add_parser("disease")
    p.add_argument("query"); p.set_defaults(fn=cmd_disease)

    p = sub.add_parser("omim")
    p.add_argument("query"); p.set_defaults(fn=cmd_omim)

    p = sub.add_parser("paper", help="find bullets citing a FBrf")
    p.add_argument("query"); p.set_defaults(fn=cmd_paper)

    p = sub.add_parser("category")
    p.add_argument("query"); add_filter_args(p); p.set_defaults(fn=cmd_category)

    p = sub.add_parser("ortholog")
    p.add_argument("species", choices=["human", "mouse"])
    p.add_argument("query"); p.set_defaults(fn=cmd_ortholog)

    p = sub.add_parser("go")
    p.add_argument("domain", help="BP / MF / CC")
    p.add_argument("query"); p.set_defaults(fn=cmd_go)

    p = sub.add_parser("tissue")
    p.add_argument("query"); add_filter_args(p); p.set_defaults(fn=cmd_tissue)

    p = sub.add_parser("stage")
    p.add_argument("query", help="embryonic / larval / pupal / adult")
    add_filter_args(p); p.set_defaults(fn=cmd_stage)

    p = sub.add_parser("allele")
    p.add_argument("query"); p.set_defaults(fn=cmd_allele)

    p = sub.add_parser("phenotype")
    p.add_argument("query"); add_filter_args(p); p.set_defaults(fn=cmd_phenotype)

    p = sub.add_parser("stats")
    p.set_defaults(fn=cmd_stats)

    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
