"""Build SQLite + FTS5 index from output/genes/*.json (schema v1.1).

Tables:
  genes               — top-level metadata
  gene_synonyms       — fbgn ↔ synonym
  bullets             — one row per bullet (rich fields)
  bullet_citations    — bullet ↔ (fbrf | section | go | ortholog)
  bullet_tissues      — bullet ↔ tissue name
  bullet_life_stages  — bullet ↔ stage
  bullet_alleles      — bullet ↔ allele name
  orthologs           — gene ↔ (human|mouse, symbol, entrez_id, DIOPT)
  diseases            — gene ↔ disease (name, omim_id, do_id, source)
  mouse_phenotypes    — gene ↔ free-text phenotype
  go_terms            — gene ↔ (BP|MF|CC, term)
  bullets_fts (virtual) — full-text on phenotype + evidence_text
"""
import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GENES_DIR = ROOT / "output" / "genes"
DB_PATH = ROOT / "output" / "index" / "fly_distill.sqlite"


SCHEMA = """
DROP TABLE IF EXISTS bullets_fts;
DROP TABLE IF EXISTS go_terms;
DROP TABLE IF EXISTS mouse_phenotypes;
DROP TABLE IF EXISTS diseases;
DROP TABLE IF EXISTS orthologs;
DROP TABLE IF EXISTS bullet_alleles;
DROP TABLE IF EXISTS bullet_life_stages;
DROP TABLE IF EXISTS bullet_tissues;
DROP TABLE IF EXISTS bullet_citations;
DROP TABLE IF EXISTS bullets;
DROP TABLE IF EXISTS gene_synonyms;
DROP TABLE IF EXISTS genes;

CREATE TABLE genes (
  fbgn TEXT PRIMARY KEY,
  symbol TEXT NOT NULL,
  snapshot TEXT,
  notes TEXT,
  n_bullets INTEGER,
  lint_count INTEGER,
  schema_version TEXT,
  distilled_at TEXT,
  source_release TEXT,
  input_tokens INTEGER,
  output_tokens INTEGER
);

CREATE TABLE gene_synonyms (
  fbgn TEXT REFERENCES genes(fbgn),
  synonym TEXT,
  synonym_type TEXT,                   -- 'current_symbol' | 'annotation_id' | 'secondary_fbgn' | 'secondary_annotation_id'
  is_current INTEGER                   -- 0 or 1
);
CREATE INDEX idx_syn_synonym ON gene_synonyms(synonym COLLATE NOCASE);
CREATE INDEX idx_syn_fbgn ON gene_synonyms(fbgn);
CREATE INDEX idx_syn_type ON gene_synonyms(synonym_type);

CREATE TABLE bullets (
  bullet_id TEXT PRIMARY KEY,
  fbgn TEXT REFERENCES genes(fbgn),
  category TEXT,
  phenotype TEXT,
  direction TEXT,
  evidence_text TEXT,
  confidence TEXT,
  text_specificity TEXT
);
CREATE INDEX idx_b_fbgn ON bullets(fbgn);
CREATE INDEX idx_b_category ON bullets(category);
CREATE INDEX idx_b_confidence ON bullets(confidence);
CREATE INDEX idx_b_text_specificity ON bullets(text_specificity);
CREATE INDEX idx_b_direction ON bullets(direction);

CREATE TABLE bullet_citations (
  bullet_id TEXT REFERENCES bullets(bullet_id),
  cite_type TEXT,                       -- 'fbrf' | 'flybase_section' | 'go' | 'ortholog'
  cite_value TEXT                       -- FBrf id / section name / GO term / ortholog symbol
);
CREATE INDEX idx_cit_bullet ON bullet_citations(bullet_id);
CREATE INDEX idx_cit_value ON bullet_citations(cite_type, cite_value);

CREATE TABLE bullet_tissues (
  bullet_id TEXT REFERENCES bullets(bullet_id),
  tissue TEXT
);
CREATE INDEX idx_tis_bullet ON bullet_tissues(bullet_id);
CREATE INDEX idx_tis_tissue ON bullet_tissues(tissue);

CREATE TABLE bullet_life_stages (
  bullet_id TEXT REFERENCES bullets(bullet_id),
  stage TEXT
);
CREATE INDEX idx_stage_bullet ON bullet_life_stages(bullet_id);
CREATE INDEX idx_stage_stage ON bullet_life_stages(stage);

CREATE TABLE bullet_alleles (
  bullet_id TEXT REFERENCES bullets(bullet_id),
  allele TEXT
);
CREATE INDEX idx_alle_bullet ON bullet_alleles(bullet_id);
CREATE INDEX idx_alle_allele ON bullet_alleles(allele);

CREATE TABLE orthologs (
  fbgn TEXT REFERENCES genes(fbgn),
  species TEXT,
  symbol TEXT,
  entrez_id TEXT,
  diopt_score INTEGER,
  diopt_max INTEGER,
  name TEXT
);
CREATE INDEX idx_ortho_species_symbol ON orthologs(species, symbol);
CREATE INDEX idx_ortho_entrez ON orthologs(entrez_id);
CREATE INDEX idx_ortho_fbgn ON orthologs(fbgn);

CREATE TABLE diseases (
  fbgn TEXT REFERENCES genes(fbgn),
  disease_name TEXT,
  omim_id TEXT,
  do_id TEXT,
  source TEXT,
  via_ortholog_species TEXT,           -- v1.2: which ortholog brought this disease link
  via_ortholog_symbol TEXT,
  via_ortholog_diopt INTEGER
);
CREATE INDEX idx_dis_fbgn ON diseases(fbgn);
CREATE INDEX idx_dis_omim ON diseases(omim_id);
CREATE INDEX idx_dis_name ON diseases(disease_name);
CREATE INDEX idx_dis_via ON diseases(via_ortholog_species, via_ortholog_symbol);

CREATE TABLE mouse_phenotypes (
  fbgn TEXT REFERENCES genes(fbgn),
  phenotype_name TEXT
);
CREATE INDEX idx_mp_fbgn ON mouse_phenotypes(fbgn);

CREATE TABLE go_slim (
  fbgn TEXT REFERENCES genes(fbgn),
  domain TEXT,                          -- 'biological_process' | 'molecular_function' | 'cellular_component'
  term TEXT,
  is_slim INTEGER DEFAULT 1
);
CREATE INDEX idx_go_fbgn ON go_slim(fbgn);
CREATE INDEX idx_go_term ON go_slim(domain, term);

CREATE VIRTUAL TABLE bullets_fts USING fts5(
  phenotype, evidence_text,
  content='bullets', content_rowid='rowid',
  tokenize='porter unicode61'
);
"""


def main():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if DB_PATH.exists():
        DB_PATH.unlink()
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA)
    cur = conn.cursor()

    n_genes = n_bullets = n_cits = n_tis = n_dis = 0
    for f in sorted(GENES_DIR.glob("FBgn*.json")):
        g = json.loads(f.read_text())
        cur.execute(
            "INSERT INTO genes VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (g["fbgn"], g["symbol"], g.get("snapshot"), g.get("notes"),
             len(g.get("bullets", [])), len(g.get("_lint", [])),
             g["schema_version"], g.get("distilled_at"),
             g.get("source", {}).get("flybase_release"),
             g.get("source", {}).get("input_tokens"),
             g.get("source", {}).get("output_tokens")),
        )
        for s in g.get("synonyms", []):
            if isinstance(s, dict):
                cur.execute("INSERT INTO gene_synonyms VALUES (?,?,?,?)",
                            (g["fbgn"], s.get("synonym"), s.get("type"),
                             1 if s.get("is_current") else 0))
            else:
                cur.execute("INSERT INTO gene_synonyms VALUES (?,?,?,?)",
                            (g["fbgn"], s, "unknown", 1))
        for b in g.get("bullets", []):
            cur.execute(
                "INSERT INTO bullets VALUES (?,?,?,?,?,?,?,?)",
                (b["id"], g["fbgn"], b["category"], b["phenotype"],
                 b["direction"], b["evidence_text"], b.get("confidence"),
                 b.get("text_specificity")),
            )
            # Unified citation shape (post v1.1.1): {type, value, ...} — no per-type field guessing
            for c in b.get("citations", []):
                ctype = c.get("type")
                cval = c.get("value")
                # back-compat: older outputs used `id`/`section`/`term`/`symbol`
                if cval is None:
                    cval = (c.get("id") or c.get("section") or c.get("term")
                            or (f"{c.get('species','?')}:{c.get('symbol','?')}" if ctype == "ortholog" else None))
                if ctype and cval:
                    cur.execute("INSERT INTO bullet_citations VALUES (?,?,?)",
                                (b["id"], ctype, cval))
                    n_cits += 1
            for t in b.get("tissues", []):
                cur.execute("INSERT INTO bullet_tissues VALUES (?,?)", (b["id"], t))
                n_tis += 1
            for s in b.get("life_stages", []):
                cur.execute("INSERT INTO bullet_life_stages VALUES (?,?)", (b["id"], s))
            for a in b.get("alleles", []):
                cur.execute("INSERT INTO bullet_alleles VALUES (?,?)", (b["id"], a))
            n_bullets += 1
        for o in g.get("cross_species", {}).get("human_orthologs", []):
            cur.execute(
                "INSERT INTO orthologs VALUES (?,?,?,?,?,?,?)",
                (g["fbgn"], "human", o["symbol"], o["entrez_id"],
                 o["diopt_score"], o["diopt_max"], o.get("name")),
            )
        for o in g.get("cross_species", {}).get("mouse_orthologs", []):
            cur.execute(
                "INSERT INTO orthologs VALUES (?,?,?,?,?,?,?)",
                (g["fbgn"], "mouse", o["symbol"], o["entrez_id"],
                 o["diopt_score"], o["diopt_max"], o.get("name")),
            )
        for d in g.get("cross_species", {}).get("human_disease_links", []):
            via = d.get("via_ortholog") or {}
            cur.execute(
                "INSERT INTO diseases VALUES (?,?,?,?,?,?,?,?)",
                (g["fbgn"], d.get("name"), d.get("omim_id"),
                 d.get("do_id"), d.get("source"),
                 via.get("species"), via.get("symbol"), via.get("diopt_score")),
            )
            n_dis += 1
        for p in g.get("cross_species", {}).get("mouse_phenotype_links", []):
            cur.execute("INSERT INTO mouse_phenotypes VALUES (?,?)", (g["fbgn"], p))
        # v1.2: field renamed from 'go' to 'go_slim' to reflect that these are slim categories, not full GO IDs
        for dom, terms in (g.get("go_slim") or g.get("go") or {}).items():
            for t in terms:
                cur.execute("INSERT INTO go_slim VALUES (?,?,?,?)",
                            (g["fbgn"], dom, t, 1))
        n_genes += 1

    # Build FTS index
    cur.execute(
        "INSERT INTO bullets_fts(rowid, phenotype, evidence_text) "
        "SELECT rowid, phenotype, evidence_text FROM bullets"
    )
    conn.commit()
    cur.execute("VACUUM")
    conn.close()
    size = DB_PATH.stat().st_size
    print(f"  wrote {DB_PATH}")
    print(f"  {n_genes} genes, {n_bullets} bullets, {n_cits} citations, "
          f"{n_tis} tissue tags, {n_dis} diseases")
    print(f"  total DB: {size:,} bytes ({size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
