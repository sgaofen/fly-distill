---
name: fly-atlas
description: Query the fly-distill phenotype atlas — 14,019 Drosophila genes with structured phenotype bullets, FlyBase citations, cross-species orthologs, OMIM disease links, chromosome coordinates, and Gemini-embedded semantic search. Use when the user asks about Drosophila genes, phenotypes, disease models, fly orthologs of human/mouse genes, or QTL region fine-mapping.
---

# fly-atlas skill

The fly-distill atlas is a local, FTS5-indexed knowledge base of **14,019
Drosophila protein-coding genes** with a **Gemini-embedded semantic search
layer**. Every gene has: a 200-word summary, structured phenotype bullets
(category / direction / confidence / verbatim FlyBase evidence), human and
mouse orthologs (DIOPT-scored), OMIM disease links, chromosome coordinates,
and full reference lists with PubMed/DOI URLs.

Access it via the `flyatlas` CLI (already installed in this repo).

---

## When to invoke

Invoke the atlas whenever the user's question involves any of:

- A specific fly gene (symbol like `chico`, FBgn ID, CG annotation ID, or synonym)
- "What does <gene> do in Drosophila?" / phenotype questions
- A human gene → fly model lookup (orthology questions)
- "Which fly genes model <disease>?" (e.g., Parkinson's, T2D, muscular dystrophy)
- **A QTL region → candidate genes** ("which genes in 2L:5M-6M might affect <phenotype>?")
- "Which fly genes might affect <phenotype>?" — even if the phenotype isn't a FlyBase term
- "Which genes are cited in <paper>?" / co-cited gene questions
- Tissue-restricted phenotype browsing ("genes with eye phenotypes")
- Phenotype category queries ("lifespan", "fertility", "behavior")

Do **not** use the atlas for: vertebrate-only questions, fly questions about
non-protein-coding RNAs, or non-FlyBase-curated data.

---

## Tool — the `flyatlas` CLI

All commands print human-readable text by default. Append `--json` for
machine-readable output (use this when chaining or extracting structured fields).

### `search <query>` — semantic search (default)

Free-text phenotype / concept query, ranked by Gemini embedding cosine
similarity over summary + bullets. **This is the right tool for vague /
fuzzy / novel phenotypes** — embedding handles synonyms and concept-level
matches that keyword search would miss.

```bash
flyatlas search "pupa height pupariation behavior"   # semantic by default
flyatlas search "alcohol sensitivity ethanol"        # finds Adh as #1
flyatlas search "Z disc AND muscle" --keyword         # force FTS5 string match
flyatlas search "circadian rhythm" --region 3R:10e6-11e6
```

**Pro tip**: longer, more concept-rich queries give tighter results. The
embedding maps every word into a semantic vector — adding synonyms / related
biology nails the search direction.

### `ask <query> --region <chr:start-end>` — hybrid for QTL fine-mapping

This is **the canonical QTL workflow**: filter genes to a chromosome region,
then rank by phenotype semantic similarity.

```bash
flyatlas ask "pupa height" --region 2L:5e6-6e6 --limit 15
flyatlas ask "alcohol sensitivity" --region 3R:10000000-10500000
```

Returns: ranked list with gene symbol, FBgn, chr:start, similarity score,
summary snippet. The user can then `flyatlas gene <symbol>` on the top
candidates.

### `semantic <query>` — pure semantic over whole atlas (no region)

```bash
flyatlas semantic "circadian period sleep arousal" --limit 10
```

### `region <chr:start-end>` — list genes in a chromosome region

```bash
flyatlas region 2L:5000000-6000000           # 122 genes, sorted by start position
flyatlas region 2L:5e6-6e6 --json
```

### `regions <input.bed>` — batch region query

For multiple QTL peaks at once. Input is a BED file (or stdin). Output is
TSV with one row per (region, gene) pair.

```bash
cat qtl_peaks.bed
# 2L  5000000  5500000  QTL_pupa_height
# 3R  10000000 10500000 QTL_alcohol_response

flyatlas regions qtl_peaks.bed --out genes_per_peak.tsv
```

### `export-bed` — dump all 14k gene coordinates

For `bedtools intersect` or downstream BED-aware tools.

```bash
flyatlas export-bed --format bed --out all_genes.bed
flyatlas export-bed --format tsv | head
```

### `gene <identifier>` — single-gene detail

Auto-resolves FBgn ID, symbol, synonym, or annotation ID.

```bash
flyatlas gene chico
flyatlas gene FBgn0024248
flyatlas gene CG5686       # annotation ID
```

### `disease <OMIM_or_name>` — fly models of a disease

```bash
flyatlas disease 254100              # OMIM ID (MDRP)
flyatlas disease "Parkinson"         # name substring
```

### `ortholog <human_or_mouse_symbol>` — fly orthologs

```bash
flyatlas ortholog IRS1
flyatlas ortholog TUBGCP5
```

### `paper <FBrf_or_PMID>` — genes citing a paper

```bash
flyatlas paper FBrf0210226
flyatlas paper 20220848              # PMID also works
```

### `tissue <name>` — genes with bullets tagged with a tissue

```bash
flyatlas tissue eye
flyatlas tissue mushroom\ body
```

### `category <category>` — phenotype-category browse

Categories: `behavior`, `morphology`, `lifespan_aging`, `development`, `reproduction`,
`metabolism`, `immune`, `sensory_neural`, `stress_response`, `disease_model`,
`expression_pattern`, `other`.

```bash
flyatlas category lifespan_aging --confidence high
```

### `stats` — atlas-wide overview

```bash
flyatlas stats
```

---

## Recommended patterns

### QTL fine-mapping (the flagship workflow)

```bash
# Sarah's pupa-height QTL on 2L
flyatlas ask "pupa height pupariation behavior larval-pupal cuticle" \
         --region 2L:5e6-6e6 --limit 10 --json | jq '.ranked[] | {symbol, score, summary}'

# Top hits in this region will surface obst-E (abnormal pupal body size),
# Cpr97Ea / Edg84A (cuticle proteins), pot (epithelial-ECM adhesion).
```

### Disease → gene panel

```bash
flyatlas disease 254100 --json | jq '.[].symbol'
# Then enrich each gene with detail:
flyatlas gene <symbol>
```

### Find unknown gene affecting a new phenotype

If you have no QTL region but want gene candidates for a new phenotype:

```bash
flyatlas semantic "phenotype description with synonyms and mechanism words" --limit 30
```

### Validate cross-species ortholog claim

```bash
flyatlas ortholog AKIRIN1
```

### Inspect what a paper documented

```bash
flyatlas paper FBrf0216456    # Brooks 2011 Neuron on prt/MB function
```

---

## Output shape (when using `--json`)

`gene`:
```jsonc
{
  "fbgn": "FBgn...", "symbol": "chico",
  "summary": "...",
  "bullets": [ { "category": "...", "phenotype": "...", "direction": "...",
                 "confidence": "high|medium|low", "evidence_text": "...",
                 "citations": [{ "type":"fbrf", "value":"FBrf...", "pmid":"...", "doi":"...", "miniref":"..." }],
                 "tissues": [...], "life_stages": [...] } ],
  "references": [...],
  "orthologs": [...],
  "diseases": [...]
}
```

`search` (semantic, default) / `ask` / `semantic`:
```jsonc
[ { "fbgn": "FBgn...", "symbol": "obst-E", "chr": "2L", "start": ..., "end": ...,
    "summary": "...", "n_bullets": N, "score": 0.625 } ]
```

`region` / `regions`:
```jsonc
[ { "fbgn": "FBgn...", "symbol": "...", "chr": "2L", "start": ..., "end": ...,
    "summary": "...", "n_bullets": N } ]
```

---

## Confidence semantics

- **high** — verbatim FlyBase-curated phenotype row, or direct quote from a paper
  abstract present in the bundle.
- **medium** — derived from quote + reasoning, or cross-paper synthesis.
- **low** — orthology-based inference, or extrapolation from family members.

When answering a user's research question, **filter to high-confidence bullets**
(use `flyatlas search "..." --keyword --confidence high` for FTS5 mode) unless
they explicitly ask for speculation.

---

## Semantic vs keyword — when to use which

- **Semantic (default)** for: vague phenotypes, novel phenotypes (not yet in
  FlyBase wording), concept queries, "find me genes like X", multi-word
  free-text questions.
- **Keyword (`--keyword`)** for: exact phrase / allele name match
  (`"chico[1]"`), boolean queries with technical FlyBase terms
  (`"phenotypes_sub AND lethal"`), reproducible queries that should not
  change as embedding model evolves.

---

## What this skill does *not* replace

- FlyBase itself (use it for the canonical record; the atlas gives a structured summary)
- PubMed full-text (the atlas quotes abstract-level statements only)
- Cell-type expression atlases (Fly Cell Atlas, etc.) — beyond this scope
- Genome-coordinate aware tools like bedtools (use `flyatlas export-bed` to
  bridge: export gene coordinates as BED, then `bedtools intersect` with
  your own QTL output)
