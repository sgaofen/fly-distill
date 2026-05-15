from __future__ import annotations
"""Build SQLite index from output/genes/*.json — single one-shot ETL.

Tables:
  genes        — one row per fbgn (symbol, summary, model, etc.)
  bullets      — phenotype bullets, one row each (fk → genes)
  citations    — bullet citations expanded (fk → bullets)
  tissues      — bullet × tissue tag join
  life_stages  — bullet × life_stage join
  refs         — references[] entries
  orthologs    — human/mouse orthologs
  diseases     — human_disease_links
  synonyms     — gene aliases for symbol lookup
  fts_genes    — FTS5 virtual table over summary + bullets (symbol-aware)

Usage:
  python -m flyatlas.build [--out path/to/atlas.db]
"""
import argparse
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB = ROOT / "tools" / "atlas.db"
GENES_DIR = ROOT / "output" / "genes"

SCHEMA = """
DROP TABLE IF EXISTS genes;
DROP TABLE IF EXISTS bullets;
DROP TABLE IF EXISTS citations;
DROP TABLE IF EXISTS tissues;
DROP TABLE IF EXISTS life_stages;
DROP TABLE IF EXISTS refs;
DROP TABLE IF EXISTS orthologs;
DROP TABLE IF EXISTS diseases;
DROP TABLE IF EXISTS synonyms;
DROP TABLE IF EXISTS fts_genes;

CREATE TABLE genes (
  fbgn          TEXT PRIMARY KEY,
  symbol        TEXT NOT NULL,
  summary       TEXT,
  notes         TEXT,
  provider      TEXT,
  model_id      TEXT,
  harness       TEXT,
  n_pubs_total  INTEGER,
  n_bullets     INTEGER,
  n_refs        INTEGER,
  schema_version TEXT,
  distilled_at  TEXT
);
CREATE INDEX idx_genes_symbol ON genes(symbol);

CREATE TABLE bullets (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  fbgn            TEXT NOT NULL,
  bullet_id       TEXT NOT NULL,
  category        TEXT,
  phenotype       TEXT,
  direction       TEXT,
  evidence_text   TEXT,
  confidence      TEXT,
  text_specificity TEXT,
  FOREIGN KEY(fbgn) REFERENCES genes(fbgn)
);
CREATE INDEX idx_bullets_fbgn ON bullets(fbgn);
CREATE INDEX idx_bullets_cat ON bullets(category);
CREATE INDEX idx_bullets_conf ON bullets(confidence);
CREATE INDEX idx_bullets_dir ON bullets(direction);

CREATE TABLE citations (
  bullet_pk   INTEGER NOT NULL,
  type        TEXT,
  value       TEXT,
  miniref     TEXT,
  year        INTEGER,
  pmid        TEXT,
  doi         TEXT,
  title       TEXT,
  FOREIGN KEY(bullet_pk) REFERENCES bullets(id)
);
CREATE INDEX idx_citations_value ON citations(value);
CREATE INDEX idx_citations_pmid ON citations(pmid);

CREATE TABLE tissues (
  fbgn   TEXT NOT NULL,
  tissue TEXT NOT NULL
);
CREATE INDEX idx_tissues_tissue ON tissues(tissue);
CREATE INDEX idx_tissues_fbgn ON tissues(fbgn);

CREATE TABLE life_stages (
  fbgn   TEXT NOT NULL,
  stage  TEXT NOT NULL
);
CREATE INDEX idx_life_stages_stage ON life_stages(stage);

CREATE TABLE refs (
  fbgn        TEXT NOT NULL,
  fbrf        TEXT NOT NULL,
  miniref     TEXT,
  title       TEXT,
  year        INTEGER,
  pmid        TEXT,
  doi         TEXT,
  pubmed_url  TEXT,
  doi_url     TEXT,
  flybase_url TEXT
);
CREATE INDEX idx_refs_fbgn ON refs(fbgn);
CREATE INDEX idx_refs_fbrf ON refs(fbrf);

CREATE TABLE orthologs (
  fbgn         TEXT NOT NULL,
  species      TEXT NOT NULL,
  symbol       TEXT NOT NULL,
  entrez_id    TEXT,
  diopt_score  INTEGER,
  name         TEXT
);
CREATE INDEX idx_orthologs_symbol ON orthologs(symbol);
CREATE INDEX idx_orthologs_fbgn ON orthologs(fbgn);

CREATE TABLE diseases (
  fbgn       TEXT NOT NULL,
  name       TEXT NOT NULL,
  omim_id    TEXT,
  via_symbol TEXT,
  via_species TEXT,
  source     TEXT
);
CREATE INDEX idx_diseases_omim ON diseases(omim_id);
CREATE INDEX idx_diseases_name ON diseases(name);

CREATE TABLE synonyms (
  fbgn         TEXT NOT NULL,
  synonym      TEXT NOT NULL,
  type         TEXT,
  is_current   INTEGER
);
CREATE INDEX idx_synonyms_value ON synonyms(synonym);

CREATE VIRTUAL TABLE fts_genes USING fts5(
  fbgn UNINDEXED,
  symbol,
  summary,
  bullets_text,
  notes,
  tokenize='porter unicode61'
);
"""


def load_gene(p: Path) -> dict | None:
    try:
        return json.loads(p.read_text())
    except Exception as e:
        print(f"  WARN {p.name}: {e}", file=sys.stderr)
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(DEFAULT_DB))
    ap.add_argument("--genes-dir", default=str(GENES_DIR))
    args = ap.parse_args()

    out_p = Path(args.out)
    out_p.parent.mkdir(parents=True, exist_ok=True)
    if out_p.exists():
        out_p.unlink()

    con = sqlite3.connect(out_p)
    con.executescript(SCHEMA)
    cur = con.cursor()

    genes_dir = Path(args.genes_dir)
    files = sorted(genes_dir.glob("*.json"))
    print(f"Loading {len(files)} canonicals from {genes_dir}...")

    n_genes = n_bullets = n_refs = n_orth = n_dis = n_syn = 0
    for i, p in enumerate(files):
        c = load_gene(p)
        if not c:
            continue
        fbgn = c["fbgn"]
        symbol = c.get("symbol") or fbgn
        model = c.get("model") or {}
        bullets = c.get("bullets") or []
        refs = c.get("references") or []

        cur.execute(
            "INSERT INTO genes(fbgn, symbol, summary, notes, provider, model_id, harness,"
            " n_pubs_total, n_bullets, n_refs, schema_version, distilled_at)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                fbgn, symbol, c.get("snapshot"), c.get("notes"),
                model.get("provider"), model.get("model_id"), model.get("harness"),
                (c.get("source") or {}).get("n_pubs_total"),
                len(bullets), len(refs),
                c.get("schema_version"), c.get("distilled_at"),
            ),
        )
        n_genes += 1

        for syn in c.get("synonyms") or []:
            cur.execute(
                "INSERT INTO synonyms(fbgn, synonym, type, is_current) VALUES (?,?,?,?)",
                (fbgn, syn.get("synonym"), syn.get("type"),
                 int(bool(syn.get("is_current")))),
            )
            n_syn += 1

        # bullets, citations, tissues, life_stages
        bullets_blob = []
        for b in bullets:
            cur.execute(
                "INSERT INTO bullets(fbgn, bullet_id, category, phenotype, direction,"
                " evidence_text, confidence, text_specificity)"
                " VALUES (?,?,?,?,?,?,?,?)",
                (
                    fbgn, b.get("id"), b.get("category"), b.get("phenotype"),
                    b.get("direction"), b.get("evidence_text"),
                    b.get("confidence"), b.get("text_specificity"),
                ),
            )
            bullet_pk = cur.lastrowid
            n_bullets += 1
            bullets_blob.append(b.get("phenotype") or "")
            bullets_blob.append(b.get("evidence_text") or "")
            for cit in b.get("citations") or []:
                cur.execute(
                    "INSERT INTO citations(bullet_pk, type, value, miniref, year, pmid, doi, title)"
                    " VALUES (?,?,?,?,?,?,?,?)",
                    (bullet_pk, cit.get("type"), cit.get("value"),
                     cit.get("miniref"), cit.get("year"),
                     cit.get("pmid"), cit.get("doi"), cit.get("title")),
                )
            for t in b.get("tissues") or []:
                cur.execute("INSERT INTO tissues(fbgn, tissue) VALUES (?,?)", (fbgn, t))
            for s in b.get("life_stages") or []:
                cur.execute("INSERT INTO life_stages(fbgn, stage) VALUES (?,?)", (fbgn, s))

        for r in refs:
            cur.execute(
                "INSERT INTO refs(fbgn, fbrf, miniref, title, year, pmid, doi,"
                " pubmed_url, doi_url, flybase_url)"
                " VALUES (?,?,?,?,?,?,?,?,?,?)",
                (fbgn, r.get("fbrf"), r.get("miniref"), r.get("title"),
                 r.get("year"), r.get("pmid"), r.get("doi"),
                 r.get("pubmed_url"), r.get("doi_url"), r.get("flybase_url")),
            )
            n_refs += 1

        cs = c.get("cross_species") or {}
        for o in (cs.get("human_orthologs") or []):
            cur.execute(
                "INSERT INTO orthologs(fbgn, species, symbol, entrez_id, diopt_score, name)"
                " VALUES (?, 'human', ?, ?, ?, ?)",
                (fbgn, o.get("symbol"), o.get("entrez_id"),
                 o.get("diopt_score"), o.get("name")),
            )
            n_orth += 1
        for o in (cs.get("mouse_orthologs") or []):
            cur.execute(
                "INSERT INTO orthologs(fbgn, species, symbol, entrez_id, diopt_score, name)"
                " VALUES (?, 'mouse', ?, ?, ?, ?)",
                (fbgn, o.get("symbol"), o.get("entrez_id"),
                 o.get("diopt_score"), o.get("name")),
            )
            n_orth += 1
        for d in (cs.get("human_disease_links") or []):
            via = d.get("via_ortholog") or {}
            cur.execute(
                "INSERT INTO diseases(fbgn, name, omim_id, via_symbol, via_species, source)"
                " VALUES (?,?,?,?,?,?)",
                (fbgn, d.get("name"), d.get("omim_id"),
                 via.get("symbol"), via.get("species"), d.get("source")),
            )
            n_dis += 1

        cur.execute(
            "INSERT INTO fts_genes(fbgn, symbol, summary, bullets_text, notes) VALUES (?,?,?,?,?)",
            (fbgn, symbol, c.get("snapshot") or "",
             "\n".join(bullets_blob), c.get("notes") or ""),
        )

        if (i + 1) % 1000 == 0:
            con.commit()
            print(f"  {i+1}/{len(files)}", flush=True)

    con.commit()
    con.close()
    print(f"\nDone. {out_p}")
    print(f"  genes={n_genes}  bullets={n_bullets}  refs={n_refs}")
    print(f"  orthologs={n_orth}  diseases={n_dis}  synonyms={n_syn}")


if __name__ == "__main__":
    main()
