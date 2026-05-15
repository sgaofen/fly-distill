# fly-distill — Drosophila phenotype atlas

A structured, source-cited phenotype atlas for **14,019 protein-coding *Drosophila melanogaster* genes**, distilled from FlyBase + Alliance + OMIM via five independent LLM backends with verbatim-quote verification. Built as a Long Lab (UCI) flagship project for QTL fine-mapping and disease modeling.

| Metric | Value |
|---|---|
| Genes covered | **14,019** |
| Phenotype bullets | **~150,000** (mean ~11 / gene) |
| Unique paper citations | **20,480** FBrf with PubMed + DOI |
| Cross-species orthologs | **28,000+** human + mouse, DIOPT-scored |
| OMIM disease links | **5,000+** via ortholog |
| Verbatim-quote verification | **100%** across 200+ hand-audited bullets, 0 hallucination |

---

## What you get per gene

- **One-paragraph summary** — organism-level effects, mechanism, disease links
- **Structured phenotype bullets** with category / direction / confidence / verbatim FlyBase or paper-abstract evidence
- **Human + mouse orthologs** (DIOPT-scored, Alliance + FlyBase curated)
- **OMIM disease links** with `via_ortholog` provenance
- **Reference list** — every FBrf cited with miniref + PubMed + DOI + FlyBase URLs
- **Tissue / life-stage / allele tags** parsed from evidence
- **Model + provenance trail** — bundle SHA256, prompt SHA256, raw-LLM-output SHA256, pipeline git commit

---

## Web UI

A local academic-style browser sits on top of a single SQLite + FTS5 index.

```bash
pip install fastapi uvicorn jinja2
cd tools && python -m flyatlas.build       # one-time ETL
python -m flyatlas.cli serve               # → http://localhost:8765
```

### Home — atlas overview & entry points

![home](docs/screenshots/home.png)

### Gene detail — phenotype bullets grouped, citations linked

![gene](docs/screenshots/gene.png)

### Full-text search with filters (FTS5, boolean operators)

![search](docs/screenshots/search.png)

### Browse by category / tissue / disease / ortholog / paper

![browse](docs/screenshots/browse.png)

---

## CLI

Terminal access to the atlas — 8 verbs, all `--json` capable:

```bash
fly gene chico                              # full detail
fly search "eye AND lethal" --confidence high
fly disease 254100                          # MDRP fly models
fly ortholog IRS1                           # fly orthologs of human IRS1
fly paper FBrf0210226                       # genes citing this paper
fly tissue eye                              # genes with bullets tagged with eye
fly category disease_model                  # phenotype-category browse
fly stats                                   # atlas-wide stats
```

Each command also has an HTTP API counterpart under `/api/*` for headless / SPA use.

---

## Skill (Claude agents)

Drop `tools/skill/SKILL.md` into `~/.claude/skills/fly-atlas/` so any Claude
agent on this machine can query the atlas autonomously when it sees a fly /
phenotype / disease question. The skill knows when to use which CLI verb and
how to chain results.

---

## Multi-backend distillation

Each gene is distilled by **one** of five LLM backends through a unified
Claude-Code-headless harness:

| Backend | Model | Notes |
|---|---|---|
| Anthropic | `claude-sonnet-4-6` (thinking-on) | best multi-paper integration, slowest |
| OpenAI    | `gpt-5.5` via Codex CLI         | fastest, concise; main workhorse |
| Z.ai      | `glm-5.1`                       | balanced, ~10 sustained concurrency |
| Xiaomi    | `mimo-v2.5-pro` (Token Plan)    | fast + cheap, dense bullets, free-tier-friendly |
| Google    | `gemini-3-flash-preview`        | small daily quota, used for sweep |

All five share the same `prompts/distill_system.md` and emit the same
canonical schema (v1.2) — backend choice is recorded per-gene in
`model.{provider, model_id, harness}`.

### Hand-verified across all backends

200+ phenotype bullets hand-audited across 16 random genes spanning 4
backends and 1–500+ pub densities: **100% verbatim quote coverage, 0
hallucination**. Quote integrity is a hard architectural property of the
pipeline, not a soft target.

---

## Architecture

```
                          ┌─ FlyBase TSVs (17 tables)
                          ├─ Alliance orthologs
   data sources ──fetch──►├─ NCBI eutils PubMed
                          ├─ MyGene cross-species
                          └─ OMIM (via FlyBase hdm)
                                       │
                                       ▼
                       data/cache/<FBgn>/bundle.json
                                       │
                                       ▼
              ┌────────────────────────────────────────┐
              │  distill_via_{sonnet,codex,claude,     │
              │                mimo,gemini}.py         │  ← TOS-clean
              │  → bullets.json + request_meta.json    │     headless harness
              └────────────────────────────────────────┘
                                       │
                            canonicalize.py (enrich + dedup)
                                       │
                                       ▼
                       output/genes/<FBgn>.json (v1.2)
                                       │
                                       ▼
                                 ┌──────┴──────┐
                                 │   atlas.db  │  ← SQLite + FTS5
                                 └─────────────┘
                                       │
              ┌────────────────────────┼────────────────────────┐
              ▼                        ▼                        ▼
            CLI                       Web UI                  Skill
       (terminal)                  (FastAPI)               (Claude agent)
```

---

## Repo layout

```
src/                       distillation pipeline
  fetch_gene_v2.py          bundle builder (bulk-only)
  bulk_index.py             FlyBase TSV loader (singleton)
  distill_via_*.py          5 backends, unified API
  canonicalize.py           bullets → v1.2 schema + enrichment
  rate_limiter.py           time-aware floor + 429 backoff
  pipeline.py               orchestrator (fetch + distill + canonicalize)
  qa.py                     deterministic + LLM tier-2 audits

prompts/                   system prompts (v1.2 baseline)
data/
  flybase_bulk/             17 FlyBase TSVs (~57 MB)
  alliance/                 Alliance orthology
  cache/<FBgn>/             per-gene bundle (~50 KB each)
output/
  genes/<FBgn>.json         canonical schema v1.2 (14,019 files)
  qa/                       audit reports
tools/
  flyatlas/                 Web UI + CLI + DB layer
    build.py                output → atlas.db (SQLite + FTS5)
    query.py                read-only data layer
    cli.py                  terminal commands
    server.py               FastAPI + Jinja2
    templates/              4 HTML templates
  skill/SKILL.md            agent skill file
docs/
  screenshots/              Web UI screenshots
gene_lists/                 batch slice files
runs/                       per-batch logs + failures + completed
```

---

## Canonical schema (v1.2)

```jsonc
{
  "schema_version": "1.2",
  "fbgn": "FBgn0024248",
  "symbol": "chico",
  "synonyms": [{ "synonym":"chico","type":"current_symbol","is_current":true }, ...],
  "distilled_at": "2026-05-15T04:09:39Z",
  "model": {
    "provider": "xiaomi", "model_id": "mimo-v2.5-pro", "harness": "mimo"
  },
  "source": { "flybase_release":"FB2026_01", "n_pubs_total":459, "n_abstracts_used":19 },
  "provenance": {
    "bundle_sha256":"…", "raw_llm_output_sha256":"…",
    "prompt_sha256":"…", "pipeline_git_commit":"…"
  },
  "snapshot": "chico encodes the sole insulin receptor substrate in Drosophila…",
  "bullets": [
    {
      "id": "FBgn0024248:b01",
      "category": "morphology",
      "phenotype": "Homozygous chico1 flies exhibit dramatically decreased body size due to reduced cell size and cell number.",
      "direction": "loss_of_function",
      "evidence_text": "phenotypes_sub: decreased body size; decreased cell size; decreased cell number | chico[1], chico[flp147E] <FBrf0108621, FBrf0135946, FBrf0179252>",
      "citations": [{
        "type":"fbrf", "value":"FBrf0108621",
        "year":1999, "miniref":"Bohni et al., 1999, Cell 97(7): 865--875",
        "pmid":"10399915", "doi":"10.1016/s0092-8674(00)80799-0"
      }, ...],
      "confidence": "high", "text_specificity": "high",
      "tissues": [], "life_stages": [], "alleles": []
    },
    ...
  ],
  "references": [...],
  "cross_species": {
    "human_orthologs":[ {"symbol":"IRS1","entrez_id":"3667","diopt_score":9, ...}, ... ],
    "mouse_orthologs":[ ... ],
    "human_disease_links":[
      {"name":"TYPE 2 DIABETES MELLITUS; T2D","omim_id":"125853",
       "via_ortholog":{"species":"human","symbol":"IRS1","diopt_score":9}, ...}
    ]
  },
  "notes": "...",
  "_lint": []
}
```

---

## Quality methodology

- **Verbatim quote rule** — every string inside `evidence_text` must be a
  character-for-character substring of the input bundle (auto_summary,
  section text, abstracts, or ortholog data).
- **Categorical enums** validated at canonicalize time (category, direction,
  confidence) — invalid values coerced to `unknown` / `other` + lint warning.
- **Bundle-shrink retries** are flagged in `_lint` as `quality.bundle_shrunk`
  so audits can find any bullet derived from a reduced source.
- **Provenance trail** — bundle SHA256 + prompt SHA256 + raw-output SHA256 +
  pipeline git commit per gene, all reproducible from cached bundles.
- **Hand-audited samples** across 4 backends × 16+ random genes × low/high
  pub-density tiers: 0 hallucination, 100% source coverage.

---

## Use cases

- **Forward-genetics**: rank candidate genes from XQTL / RNAi / CRISPR screens against phenotype keywords
- **Disease modeling**: find fly models of a human OMIM disease
- **Drug-discovery / target validation**: human target → fly ortholog → known phenotype
- **Aging / behavior / immunity / metabolism panels**: browse by phenotype category
- **Comp-bio ML training corpus**: structured, source-cited, verbatim-quote-verified
- **Teaching**: browse / search instead of clicking through FlyBase entry pages

---

## Citation

If you use this atlas in a publication, please cite:

> Stephen Yu, [Long Lab UCI]. fly-distill: a multi-backend LLM-distilled Drosophila phenotype atlas with verbatim-quote verification. 2026.

Upstream data sources should be cited per their own terms:
**FlyBase** (Öztürk-Çolak et al., 2024), **Alliance of Genome Resources**, **OMIM**, **NCBI PubMed**.

---

## License

MIT for code. Data is subject to upstream FlyBase / Alliance / OMIM terms — most permit free non-commercial research use; check each source for commercial use.

---

## Author

Stephen Yu — Long Lab @ UCI · stephenyu070129@gmail.com
