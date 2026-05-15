---
name: fly-atlas
description: Query the fly-distill phenotype atlas — 14k Drosophila genes with structured phenotype bullets, FlyBase citations, cross-species orthologs, and OMIM disease links. Use when the user asks about Drosophila genes, phenotypes, disease models, or fly orthologs of human/mouse genes.
---

# fly-atlas skill

The fly-distill atlas is a local, FTS5-indexed knowledge base of 14,019 Drosophila
protein-coding genes. Every gene has: a 200-word summary, structured phenotype
bullets (category / direction / confidence / verbatim FlyBase evidence), human and
mouse orthologs (DIOPT-scored), OMIM disease links, and full reference lists with
PubMed/DOI URLs.

Access it via the `flyatlas.cli` Python module (already installed in this repo).

---

## When to invoke

Invoke the atlas whenever the user's question involves any of:

- A specific fly gene (symbol like `chico`, FBgn ID, CG annotation ID, or synonym)
- "What does <gene> do in Drosophila?" / phenotype questions
- A human gene → fly model lookup (orthology questions)
- "Which fly genes model <disease>?" (e.g., Parkinson's, T2D, muscular dystrophy)
- "Which genes are cited in <paper>?" / co-cited gene questions
- Tissue-restricted phenotype browsing ("genes with eye phenotypes")
- Phenotype category queries ("lifespan", "fertility", "behavior")

Do **not** use the atlas for: vertebrate-only questions, fly questions about
non-protein-coding RNAs, or non-FlyBase-curated data.

---

## Tool — the `flyatlas` CLI

All commands print human-readable text by default. Append `--json` for
machine-readable output (use this when chaining or extracting structured fields).

### `gene <identifier>` — single-gene detail

Auto-resolves FBgn ID, symbol, synonym, or annotation ID.

```bash
python -m flyatlas.cli gene chico
python -m flyatlas.cli gene FBgn0024248
python -m flyatlas.cli gene CG5686       # annotation ID
```

Returns: summary, phenotype bullets grouped by category, references (with PubMed/DOI),
cross-species orthologs, OMIM disease links.

### `search "<query>"` — FTS5 full-text search

Searches summary + bullets + notes. Supports boolean operators (`AND`, `OR`, `NOT`)
and phrase queries (`"…"`).

```bash
python -m flyatlas.cli search "eye AND lethal" --confidence high
python -m flyatlas.cli search '"Z disc" AND muscle'
python -m flyatlas.cli search "tauopathy" --category disease_model
```

Filters: `--category`, `--direction`, `--confidence`, `--tissue`, `--limit`.

### `disease <OMIM_or_name>` — fly models of a disease

```bash
python -m flyatlas.cli disease 254100              # OMIM ID (MDRP)
python -m flyatlas.cli disease "Parkinson"         # name substring
```

### `ortholog <human_or_mouse_symbol>` — fly orthologs

```bash
python -m flyatlas.cli ortholog IRS1
python -m flyatlas.cli ortholog TUBGCP5
```

### `paper <FBrf_or_PMID>` — genes citing a paper

```bash
python -m flyatlas.cli paper FBrf0210226
python -m flyatlas.cli paper 20220848              # PMID also works
```

### `tissue <name>` — genes with bullets tagged with a tissue

```bash
python -m flyatlas.cli tissue eye
python -m flyatlas.cli tissue mushroom\ body
```

### `category <category>` — phenotype-category browse

Categories: `behavior`, `morphology`, `lifespan_aging`, `development`, `reproduction`,
`metabolism`, `immune`, `sensory_neural`, `stress_response`, `disease_model`,
`expression_pattern`, `other`.

```bash
python -m flyatlas.cli category lifespan_aging --confidence high
```

### `stats` — atlas-wide overview

```bash
python -m flyatlas.cli stats
```

---

## Recommended patterns

### Disease → gene panel

```bash
python -m flyatlas.cli disease 254100 --json | jq '.[].symbol'
```

Then enrich each gene with detail:

```bash
python -m flyatlas.cli gene <symbol>
```

### Find a high-confidence eye-phenotype gene

```bash
python -m flyatlas.cli search "rough eye" --category sensory_neural --confidence high
```

### Validate cross-species ortholog claim

```bash
# user asks: "Does Drosophila have an Akirin ortholog?"
python -m flyatlas.cli ortholog AKIRIN1
```

### Inspect what a paper documented

```bash
python -m flyatlas.cli paper FBrf0216456    # Brooks 2011 Neuron on prt/MB function
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

`search` / `tissue` / `category` / `disease` / `ortholog` / `paper`: list of rows
with `fbgn`, `symbol`, `summary`, and command-specific extras (`diopt_score`,
`disease_name`, `miniref`, …).

---

## Confidence semantics

- **high** — verbatim FlyBase-curated phenotype row, or direct quote from a paper
  abstract present in the bundle.
- **medium** — derived from quote + reasoning, or cross-paper synthesis.
- **low** — orthology-based inference, or extrapolation from family members.

When answering a user's research question, **filter to high-confidence bullets**
unless they explicitly ask for speculation.

---

## What this skill does *not* replace

- FlyBase itself (use it for the canonical record; the atlas gives a structured summary)
- PubMed full-text (the atlas quotes abstract-level statements only)
- Cell-type expression atlases (Fly Cell Atlas, etc.) — beyond this scope
