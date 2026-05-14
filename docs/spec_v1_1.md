# Fly Gene-Phenotype Atlas — Spec v1.1.1

**Date:** 2026-05-14 (v1.1.1 patches applied 2026-05-14, see `docs/CHANGELOG_v1_1.md`)
**Audience:** technical / LLM reviewer + future maintainers + Prof. Long

## What this is

A **general-purpose, programmatically queryable gene-phenotype atlas** for
*Drosophila melanogaster*. Every fly protein-coding gene is represented as a
compact, evidence-linked record containing:

- a one-paragraph snapshot of what perturbing the gene does to the organism,
- 20–30 organism-level phenotype "bullets" with FBrf/paper citations,
- cross-species ortholog data linked to OMIM/HPO disease, MGI mouse phenotypes,
- structured tags (tissue, life stage, allele, GO slim, category, direction).

It is **distilled by GLM-5.1 from FlyBase + MGI + HPO + OMIM**, then enriched and
canonicalized by deterministic post-processing, and exposed through a SQLite +
FTS5 index plus a CLI with 12 forward/reverse query types.

## Why this is generally useful

The same atlas serves many workflows, not just one. Sample use cases:

| User | Workflow | Lookup pattern |
|---|---|---|
| **forward-genetics labs** (XQTL, RNAi, CRISPR, EMS screens) | Got hit list of genes; rank by phenotype relevance | `lookup gene <fbgn>` per candidate; or `query` with target trait |
| **disease modeling labs** | Want fly model for human disease X | `lookup omim <id>` or `lookup disease "<name>"` |
| **drug discovery / cross-species** | Have human drug target; want fly ortholog with well-studied phenotype | `lookup ortholog human <symbol>` |
| **aging / behavior / immune labs** | Survey known fly genes in a phenotype category | `lookup category <cat>` |
| **comparative phenotype** | Mouse gene MP phenotype X; which fly orthologs share it? | join `mouse_orthologs` ↔ `mouse_phenotype_links` |
| **textbook / review writers** | Need 200-word factual summary of a gene with paper references | `lookup gene <symbol>` returns paragraph + cited papers |
| **ML / comp bio** | Need structured natural-language phenotype dataset | read `output/genes/*.json` directly |
| **anyone manually browsing FlyBase** | Faster query for "what does this gene do" | one CLI call instead of 5 FlyBase clicks |

QTL fine-mapping is one *showcase application* (Long lab's specific use case),
not the defining scope. The artifact is general; downstream applications differ.

## Architectural commitment

- **GLM-5.1 is invoked only for the distillation step (one to two passes per gene).**
- **All other layers are deterministic** — canonicalization, enrichment with
  external databases, citation parsing, indexing, querying, and validation.
- **Raw bulk TSVs (FlyBase + MGI + HPO + OMIM + Alliance) are preserved as the
  source-of-truth.** The distilled JSON is an LLM-readable *summary layer*, not
  a replacement.
- **Schema is versioned**; all gene records carry `schema_version` and lint
  metadata so consumers can branch on it.

## Note on coverage

Each gene's output is a *synopsis* (20–30 organism-level bullets, ≤20 representative
paper abstracts, supplemented by curator annotations and cross-species data) —
not an exhaustive enumeration of every FlyBase phenotype annotation row. For
genes with hundreds-to-thousands of papers (e.g. *period* with 1680 pubs, *Notch*
with 3693), the pipeline uses the **two-pass distillation harness** (see §2.5)
which performs an initial distill followed by a critique-and-refine pass —
yielding more comprehensive coverage and self-checked citations on complex genes.

This document is the canonical reference for: schema, data flow, indices,
query patterns. It assumes you've already read the project overview in
`docs/cluster_layout.md`.

---

## 1. Pipeline architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│ INPUT — bulk databases (one-shot download, ~375 MB total)            │
│                                                                       │
│  data/flybase_bulk/    s3ftp.flybase.org    57 MB                    │
│    genes/, alleles/, references/, orthologs/, human_disease/         │
│  data/mgi/              informatics.jax.org  169 MB                  │
│  data/hpo/              github releases       126 MB                 │
│  data/omim/             omim.org              1 MB (open subset)     │
│  data/alliance/         fms.alliancegenome.org  22 MB                │
└──────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌──────────────────────────────────────────────────────────────────────┐
│ STAGE 1 — fetch per-gene bundle                                       │
│   src/fetch_gene.py                                                   │
│   • parses bulk TSVs locally (no API call) for: auto summary,         │
│     phenotype annotations, allele descriptions, disease links,        │
│     ortholog symbols + DIOPT scores, references                       │
│   • on-demand /fbrf/{id}/abstract for ~20 representative papers       │
│     (FlyBase API ~0.12s sequential, 0.012s @ 10-parallel)             │
│   • writes data/cache/<FBgn>/bundle.json (~50 KB lean / ~200 KB with HTML)│
└──────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌──────────────────────────────────────────────────────────────────────┐
│ STAGE 2 — GLM-5.1 distillation                                        │
│   src/distill_via_claude.py (Claude Code headless harness, TOS-compliant) │
│   or src/distill.py (direct API, dev-only)                            │
│   • single API call per gene, ~30-100K tokens in, ~3-4K tokens out    │
│   • ~45s wall-time per gene at 10-concurrent ceiling                  │
│   • produces raw {summary, bullets[], cross_species, notes}           │
│   • output/<FBgn>/bullets.json (raw LLM output preserved verbatim)    │
│                                                                       │
│   Auto-retry on schema drift: if canonical _lint contains             │
│   'schema_drift:', re-distill once with stricter prompt.              │
└──────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌──────────────────────────────────────────────────────────────────────┐
│ STAGE 3 — canonicalize + enrich (deterministic, no LLM)               │
│   src/canonicalize.py → uses src/enrich.py                            │
│   • parse evidence text → structured citations[]                       │
│     (FBrf IDs, FlyBase section names, GO terms, ortholog mentions)    │
│   • cross-reference disease names → OMIM IDs from FlyBase bulk        │
│   • copy GO ribbon terms verbatim from bundle                         │
│   • extract tissue / life_stage / allele tags from text               │
│   • compute specificity heuristic                                     │
│   • full synonyms from FlyBase fbgn_annotation_ID.tsv                 │
│   • record any quality issues in _lint                                │
│   • writes output/genes/<FBgn>.json (schema v1.1)                     │
└──────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌──────────────────────────────────────────────────────────────────────┐
│ STAGE 4 — build indices                                               │
│   src/build_sqlite.py                                                 │
│   • single SQLite DB with 11 tables + FTS5 virtual table              │
│   • output/index/fly_distill.sqlite                                   │
│                                                                       │
│   src/build_indices.py (optional, derivative JSON inverted indices)   │
└──────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌──────────────────────────────────────────────────────────────────────┐
│ STAGE 5 — query                                                       │
│   src/lookup.py (CLI, 12 query subcommands)                           │
│   • forward: gene <symbol|FBgn|ortholog>                              │
│   • reverse: disease, omim, paper FBrf, category, ortholog,           │
│              go, tissue, stage, allele                                │
│   • full-text: phenotype <FTS5-query> [--confidence X] [--category Y] │
│   • stats: aggregate counts                                           │
└──────────────────────────────────────────────────────────────────────┘
```

## 2. Schema v1.1 — canonical per-gene JSON

The strict definition lives at
`output/schema/distilled_gene_v1_1.schema.json`. Summarized:

| Field | Type | Required | Note |
|---|---|---|---|
| `schema_version` | string `"1.1"` | yes | constant |
| `fbgn` | string `FBgn0000000` | yes | primary key |
| `symbol` | string | yes | preferred display symbol |
| `synonyms` | string[] | no | from FlyBase `fbgn_annotation_ID.tsv` — secondary FBgns, CG IDs, historical names |
| `distilled_at` | RFC3339 | no | when canonical was written |
| `model` | string | no | e.g. `"glm-5.1"` |
| `source.flybase_release` | string | yes | e.g. `"FB2026_01"` |
| `source.n_pubs_total` | int | yes | how many FBrfs exist for this gene |
| `source.n_abstracts_used` | int | yes | how many fed to the model |
| `source.input_tokens` | int? | no | LLM token usage |
| `source.output_tokens` | int? | no | |
| `snapshot` | string | yes | one-paragraph TL;DR from the model |
| `bullets[]` | object[] | yes | 20-30 organism-level phenotype claims |
| `go.{biological_process, molecular_function, cellular_component}` | string[] | yes | GO slim categories from FlyBase ribbon, verbatim |
| `cross_species.human_orthologs[]` | object[] | yes | top-3 by DIOPT |
| `cross_species.mouse_orthologs[]` | object[] | yes | top-3 by DIOPT |
| `cross_species.human_disease_links[]` | object[] | yes | name + OMIM ID + source |
| `cross_species.mouse_phenotype_links[]` | string[] | yes | free-text from model |
| `notes` | string? | no | model-written caveat |
| `_lint` | string[] | no | non-fatal quality warnings |

### 2.1 Bullet shape

Each bullet:

```json
{
  "id": "FBgn0003068:b11",
  "category": "development",
  "phenotype": "Larvae exhibit increased genotoxic stress and double-strand DNA breaks in the central nervous system.",
  "direction": "loss_of_function",
  "evidence_text": "FBrf0261177 abstract: 'In third-instar larvae, we have observed that the absence of functional per results in increased genotoxic stress... increased double-strand DNA breaks in the central nervous system'",
  "citations": [
    { "type": "fbrf", "id": "FBrf0261177" }
  ],
  "confidence": "high",
  "specificity": "medium",
  "tissues": ["central nervous system"],
  "life_stages": ["larval"],
  "alleles": []
}
```

Allowed enums:

- `category` ∈ {behavior, morphology, lifespan_aging, development, reproduction,
  metabolism, immune, sensory_neural, stress_response, disease_model,
  expression_pattern, other}
- `direction` ∈ {loss_of_function, gain_of_function, either, unknown}
- `confidence` ∈ {high, medium, low, null}
- `specificity` ∈ {high, medium, low, null} — heuristic: text features (number content,
  named entities, quantifier presence, length)
- `citations[].type` ∈ {fbrf, flybase_section, go, ortholog}

### 2.2 Cross-species disease link shape

```json
{
  "name": "ADVANCED SLEEP PHASE SYNDROME, FAMILIAL, 1; FASPS1",
  "omim_id": "604348",
  "do_id": null,
  "source": "flybase_bulk"
}
```

`source` ∈ {`flybase_bulk` (canonical, from `dmel_human_orthologs_disease.tsv`),
`llm_inferred` (the model named a disease not in bulk), `alliance` (future)}.

---

## 3. Indices (SQLite)

Single DB file `output/index/fly_distill.sqlite`, ~280 KB at 6-gene scale,
projected ~150 MB at 14k-gene scale.

| Table | Purpose | Indexed columns |
|---|---|---|
| `genes` | top-level metadata, PK = fbgn | fbgn |
| `gene_synonyms` | every name for every gene | synonym, fbgn |
| `bullets` | one row per bullet | fbgn, category, confidence, specificity, direction |
| `bullet_citations` | many-to-many bullet ↔ {fbrf, section, go, ortholog} | (cite_type, cite_value) |
| `bullet_tissues` | many-to-many bullet ↔ tissue name | tissue |
| `bullet_life_stages` | many-to-many bullet ↔ stage | stage |
| `bullet_alleles` | many-to-many bullet ↔ allele | allele |
| `orthologs` | gene ↔ (species, symbol, entrez_id, DIOPT) | (species, symbol), entrez_id, fbgn |
| `diseases` | gene ↔ (name, omim_id, do_id, source) | fbgn, omim_id, name |
| `mouse_phenotypes` | gene ↔ free-text phenotype | fbgn |
| `go_terms` | gene ↔ (BP/MF/CC, term) | (domain, term), fbgn |
| `bullets_fts` | FTS5 virtual on phenotype + evidence_text | porter + unicode61 tokenizer |

### 3.1 Why this layout

- **Many-to-many tables** for citations / tissues / stages / alleles enable
  the "which genes affect tissue X" and "which papers cite this bullet"
  queries with a single SQL JOIN.
- **OMIM column on diseases** enables exact cross-database joining with OMIM
  bulk or HPO disease annotations later.
- **FTS5 with porter stemmer** means searching `circadian` matches
  `circadian rhythms`, `circadian rhythmicity`, `circadian-regulated`.
- **All indices derived from `output/genes/*.json`** → fully rebuildable
  via `python3 src/build_sqlite.py`. Never store anything in the SQLite
  that can't be recovered from the gene JSONs.

---

## 4. Query patterns + SQL examples

### Forward — give me everything about a gene

```bash
python3 src/lookup.py gene per
python3 src/lookup.py gene FBgn0003068
python3 src/lookup.py gene DNM1          # detected as ortholog → fly shi
```

SQL pattern (CLI does ~5 joins behind one subcommand):

```sql
-- gene base record
SELECT * FROM genes WHERE fbgn = ?;
-- bullets grouped by category
SELECT * FROM bullets WHERE fbgn = ? ORDER BY bullet_id;
-- per-bullet citations / tissues / alleles
SELECT cite_type, cite_value FROM bullet_citations WHERE bullet_id = ?;
-- orthologs sorted by DIOPT
SELECT * FROM orthologs WHERE fbgn = ? AND species = 'human' ORDER BY diopt_score DESC;
-- diseases
SELECT * FROM diseases WHERE fbgn = ?;
-- GO ribbon
SELECT domain, term FROM go_terms WHERE fbgn = ? ORDER BY domain, term;
```

### Reverse — find genes that match a query

```bash
# OMIM exact
python3 src/lookup.py omim 604348

# disease name substring
python3 src/lookup.py disease "Sleep"

# all genes citing one paper
python3 src/lookup.py paper FBrf0261177

# all bullets in a category, filtered by confidence
python3 src/lookup.py category behavior --confidence high

# cross-species reverse lookup
python3 src/lookup.py ortholog human DNM1
python3 src/lookup.py ortholog mouse Per1

# functional category
python3 src/lookup.py go BP "behavior"

# anatomy
python3 src/lookup.py tissue "Malpighian"

# life stage with category filter
python3 src/lookup.py stage larval --category development

# specific allele evidence
python3 src/lookup.py allele w1118
```

Underlying SQL examples:

```sql
-- "which fly genes have an ortholog with this OMIM phenotype ID?"
SELECT g.fbgn, g.symbol, d.name AS disease_name
FROM diseases d JOIN genes g ON g.fbgn = d.fbgn
WHERE d.omim_id = ?;

-- "find all bullets affecting tissue X with high confidence"
SELECT g.symbol, b.phenotype
FROM bullet_tissues bt
JOIN bullets b ON b.bullet_id = bt.bullet_id
JOIN genes g ON g.fbgn = b.fbgn
WHERE bt.tissue LIKE ? AND b.confidence = 'high';

-- "which bullets cite this paper?"
SELECT g.symbol, b.bullet_id, b.phenotype
FROM bullet_citations bc
JOIN bullets b ON b.bullet_id = bc.bullet_id
JOIN genes g ON g.fbgn = b.fbgn
WHERE bc.cite_type = 'fbrf' AND bc.cite_value = ?;
```

### Full-text — semantic-ish search across all bullets

```bash
python3 src/lookup.py phenotype "circadian rhythm"
python3 src/lookup.py phenotype "cocaine OR ethanol OR alcohol" --confidence high
python3 src/lookup.py phenotype "NEAR(memory consolidation, 5)" --category behavior
```

Uses FTS5 porter-stemmed tokenizer with relevance ranking. Boolean operators
(`AND` / `OR` / `NOT` / `NEAR`) supported.

---

## 5. Excerpt — one gene's canonical record (period)

Excerpted output for `period` (FBgn0003068), generated by GLM-5.1 then enriched.
Two bullets shown verbatim; the complete record contains 24 bullets and is at
`output/genes/FBgn0003068.json`.

> **Field-naming note:** the canonical JSON uses `bullets[].id`. The SQLite tables
> use `bullets.bullet_id`. These are the same key — copied directly during ingest.

```json
{
  "schema_version": "1.1",
  "fbgn": "FBgn0003068",
  "symbol": "per",
  "synonyms": ["CG2647", "FBgn0000321", "FBgn0020918", "per"],
  "distilled_at": "2026-05-14T02:00:00Z",
  "model": "glm-5.1",
  "source": {
    "flybase_release": "FB2026_01",
    "n_pubs_total": 1680,
    "n_abstracts_used": 20,
    "input_tokens": 40667,
    "output_tokens": 2250
  },
  "snapshot": "Perturbation of the period (per) gene fundamentally disrupts the circadian clock, leading to arrhythmic or abnormal locomotor activity in constant conditions. Beyond daily rest-activity cycles, per mutants exhibit altered courtship and mating behaviors (including courtship song rhythms), impaired long-term memory, abnormal sleep architecture, and a shorter adult lifespan...",
  "bullets": [
    {
      "id": "FBgn0003068:b01",
      "category": "behavior",
      "phenotype": "Loss-of-function abolishes circadian locomotor rhythms, causing flies to be arrhythmic in constant darkness.",
      "direction": "loss_of_function",
      "evidence_text": "phenotypes_sub: abnormal locomotor rhythm; abnormal circadian rhythm | per01 allele",
      "citations": [
        { "type": "flybase_section", "section": "phenotypes_sub" }
      ],
      "confidence": "high",
      "specificity": "low",
      "tissues": [],
      "life_stages": [],
      "alleles": ["per01"]
    },
    {
      "id": "FBgn0003068:b11",
      "category": "development",
      "phenotype": "Larvae exhibit increased genotoxic stress and double-strand DNA breaks in the central nervous system.",
      "direction": "loss_of_function",
      "evidence_text": "FBrf0261177 abstract: 'In third-instar larvae, we have observed that the absence of functional per results in increased genotoxic stress... increased double-strand DNA breaks in the central nervous system'",
      "citations": [
        { "type": "fbrf", "id": "FBrf0261177" }
      ],
      "confidence": "high",
      "specificity": "medium",
      "tissues": ["central nervous system"],
      "life_stages": ["larval"],
      "alleles": []
    },
    "... 22 more bullets ..."
  ],
  "go": {
    "biological_process": [
      "development", "response to stimulus", "gene expression",
      "behavior", "other biological_process", "nervous system process"
    ],
    "molecular_function": [
      "DNA binding", "other molecular_function", "transcription factor"
    ],
    "cellular_component": ["nucleus", "other cellular_component"]
  },
  "cross_species": {
    "human_orthologs": [
      { "symbol": "PER1", "entrez_id": "5187", "diopt_score": 9, "diopt_max": 14, "name": "period circadian regulator 1" },
      { "symbol": "PER3", "entrez_id": "8863", "diopt_score": 9, "diopt_max": 14, "name": "period circadian regulator 3" },
      { "symbol": "PER2", "entrez_id": "8864", "diopt_score": 8, "diopt_max": 14, "name": "period circadian regulator 2" }
    ],
    "mouse_orthologs": [
      { "symbol": "Per2", "entrez_id": "18627", "diopt_score": 8, "diopt_max": 14, "name": "period circadian clock 2" },
      { "symbol": "Per3", "entrez_id": "18628", "diopt_score": 8, "diopt_max": 14, "name": "period circadian clock 3" },
      { "symbol": "Per1", "entrez_id": "18626", "diopt_score": 7, "diopt_max": 14, "name": "period circadian clock 1" }
    ],
    "human_disease_links": [
      {
        "name": "ADVANCED SLEEP PHASE SYNDROME, FAMILIAL, 1; FASPS1",
        "omim_id": "604348",
        "do_id": null,
        "source": "flybase_bulk"
      },
      {
        "name": "ADVANCED SLEEP PHASE SYNDROME, FAMILIAL, 3; FASPS3",
        "omim_id": "616882",
        "do_id": null,
        "source": "flybase_bulk"
      }
    ],
    "mouse_phenotype_links": [
      "Circadian locomotor rhythm defects",
      "Altered sleep patterns and metabolism"
    ]
  },
  "notes": "The period gene is one of the most extensively characterized genes in Drosophila. While its primary and most noticeable organismal effect is the disruption of 24-hour behavioral and physiological rhythms, this core function cascades into a wide array of secondary phenotypes spanning sleep, reproduction, memory, stress resistance, and lifespan.",
  "_lint": []
}
```

---

## 6. Storage budget at scale

| Layer | Path | 6-gene (current) | 14k-gene (projected) |
|---|---|---|---|
| Bulk source DBs | data/{flybase_bulk,mgi,hpo,omim,alliance}/ | 375 MB | 375 MB |
| Per-gene fetched bundles | data/cache/<FBgn>/ | 800 KB | ~700 MB |
| Canonical JSONs | output/genes/<FBgn>.json | 80 KB | ~150 MB |
| SQLite (incl FTS5) | output/index/fly_distill.sqlite | 280 KB | ~150 MB |
| Derived JSON indices | output/index/{catalog,bullets_flat,by_*}* | 80 KB | ~500 MB |
| Run logs (per batch) | runs/<batch_id>/{glm_calls,failures,completed}.jsonl | ~10 KB | ~50 MB/run |
| **Total steady-state** | | **~376 MB** | **~2 GB** |

Mac Mini M4 (16 GB RAM, plenty of SSD): handles 14k-gene production easily.

---

## 7. Quality assurance

### 7.1 Schema validation

`python3 src/validate.py` runs a hand-rolled validator against
`output/schema/distilled_gene_v1_1.schema.json`. Returns PASS / WARN (lint
only) / FAIL (structural).

### 7.2 Lint warnings recorded inline

`_lint` field on each gene record. Current sample's 6 genes:
- 5 PASS
- 1 WARN: `ebony` — `schema_drift: every bullet missing 'confidence' field`.
  Pipeline.py will auto-retry this with stricter prompt on next run.

### 7.3 Manual audit (one-time, on 6-gene sample)

Stephen manually spot-checked 40+ bullets across 6 genes against the source
bundles. **0 hallucinations found.** Most flagged "issues" by the automated
auditor were citation-formatting artifacts (FlyBase's pipe-separated
phenotype annotations breaking literal substring matching). See
`output/spot_checks.json` for the per-gene verdict.

### 7.4 Specificity heuristic

`enrich.score_specificity()` rates each bullet:
- `high` — contains numbers (500x, 19hr, 80%), named entities (FBrf, allele names), or
  strong quantifiers
- `medium` — moderate specificity (≥80 char + some structure)
- `low` — vague free-text

Current distribution (160 bullets):
- high/high: 9
- high/medium: 30
- high/low: 69 (these are the ones citing FlyBase pipe-format phenotypes —
  conceptually high-confidence but low-text-specificity)
- medium tier: 26
- null confidence (ebony schema drift): 26

---

## 8. Known limitations + open questions

| # | Issue | Status |
|---|---|---|
| 1 | `do_id` is always null — DO IDs aren't in FlyBase bulk's `dmel_human_orthologs_disease.tsv`. Cross-link to Alliance disease file in future iteration. | open |
| 2 | `mouse_phenotype_links` is still free-text (no MP ID extraction). Bulk MGI files have these — needs an MGI parser similar to FlyBase disease parser. | open |
| 3 | Allele regex is conservative — misses long-form names like `per[01]` (with brackets) and complex transgene constructs. Cross-checking with FlyBase `fbal_to_fbgn.tsv` would fix this. | open |
| 4 | Specificity heuristic correlates weakly with bullet quality on FlyBase-pipe-format evidence. ML-based scoring is a v2 candidate. | open |
| 5 | One-batch tests show GLM-5.1 occasionally drops `confidence` field for some genes (~1/6 in pilot). Auto-retry with strict prompt mitigates but doesn't 100% prevent. | mitigated |
| 6 | FlyBase WAF blocks home-IP after rapid scrape bursts. Switched to `s3ftp.flybase.org` bulk + sparse per-gene API; this is workable. Cluster IPs are typically whitelisted. | mitigated |
| 7 | OMIM full clinical synopses require API key (free academic). Currently only OMIM phenotype IDs + names are captured. Adding deeper HPO disease text is a v2 target. | open |
| 8 | GO terms are slim-level (general categories), not specific GO IDs. For molecular-function fine-grained queries we'd need full GO annotations from FlyBase `gene_ontology` bulk. | open |

---

## 9. Reproducibility

Every gene record contains enough metadata to regenerate it:
- `source.flybase_release` — which FlyBase version was the input
- `model` — which LLM
- `source.input_tokens` / `output_tokens` — usage record
- `distilled_at` — timestamp
- `_lint` — any non-fatal warnings

The full pipeline is git-tracked under `src/`. To rebuild from scratch:

```bash
python3 src/download_flybase_bulk.py        # 13 sec (s3ftp)
python3 src/download_mouse_human.py          # ~45 sec
python3 src/fetch_gene.py FBgn0003068        # one gene at a time, or:
python3 src/pipeline.py gene_list.txt        # parallel batch
python3 src/canonicalize.py                  # enrich → v1.1
python3 src/build_sqlite.py                  # rebuild index
python3 src/lookup.py gene per               # query
```

---

## 10. End-state vision (FlyBase-like search engine)

The lookup CLI is the developer-facing surface. The user-facing search-engine
shell is a thin layer on top:

- **Web UI** (FastAPI + React + minimal frontend) wrapping `lookup.py` —
  gives Sarah / Long a browser-tappable interface
- **Embedding-based semantic search** — index each bullet's phenotype text
  into a vector store (e.g. sqlite-vec or chroma); enables queries like
  *"genes involved in stress response that interact with the immune system"*
  beyond what FTS5's literal matching can do
- **Cross-gene similarity** — given gene X, rank all other genes by bullet
  overlap (Jaccard on tissues + categories) or vector similarity
- **QTL fine-mapping integration** — accept a list of candidate FBgns plus
  a target phenotype description, rank by relevance — one LLM call per query
  using `src/query.py glm_rank` as the existing prototype

All of these layers operate purely on the canonical JSON + SQLite — they do not
require touching FlyBase, MGI, or the source databases after initial distillation.

**Exception:** the QTL `glm_rank` query-time reranker in `src/query.py` is an
optional layer that does call the LLM at query time (one call per user query),
since semantic gene-vs-phenotype matching benefits from the model's judgment.
All other consumer paths are LLM-free.

---

## Appendix A — File inventory

| Path | Lines | Purpose |
|---|---|---|
| `src/fetch_gene.py` | ~300 | per-gene bundle fetcher (FlyBase API + HTML + MyGene cross-species) |
| `src/download_flybase_bulk.py` | ~140 | s3ftp.flybase.org bulk downloader |
| `src/download_mouse_human.py` | ~120 | MGI + HPO + OMIM + Alliance bulk downloader |
| `src/distill.py` | ~150 | direct-API distillation (dev only) |
| `src/distill_via_claude.py` | ~150 | Claude Code headless harness (production, Z.ai TOS-compliant). Despite the filename, the actual model invoked is GLM-5.1 — Claude Code is only the harness; the env vars `ANTHROPIC_BASE_URL` + `ANTHROPIC_AUTH_TOKEN` route requests to z.ai's Anthropic-compatible endpoint. |
| `src/enrich.py` | ~280 | post-process enrichers (citations, tissues, stages, alleles, GO, disease IDs, synonyms, specificity) |
| `src/canonicalize.py` | ~180 | raw bullets.json → schema v1.1 canonical |
| `src/validate.py` | ~80 | strict schema validator |
| `src/build_sqlite.py` | ~200 | SQLite + FTS5 index builder |
| `src/build_indices.py` | ~100 | derivative JSON inverted indices (optional) |
| `src/lookup.py` | ~340 | CLI search engine (12 subcommands) |
| `src/pipeline.py` | ~280 | producer-consumer parallel batch runner with idempotency + schema-drift retry |
| `src/audit.py` | ~150 | hallucination + citation auditor |
| `src/probe_concurrency.py` | ~120 | benchmark GLM concurrent throughput |
| `prompts/distill_system.md` | ~70 | distillation system prompt (v1.0) |
| `prompts/distill_system_strict.md` | ~50 | retry prompt for schema_drift recovery |
| `output/schema/distilled_gene_v1_1.schema.json` | ~140 | JSON Schema definition |
| `docs/spec_v1_1.md` | this file | this spec |
| `docs/cluster_layout.md` | ~200 | TB-scale cluster deployment plan |
