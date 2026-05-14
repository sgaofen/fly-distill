# Search Engine UI Design

## Design principle: layered disclosure

A user comes to look up a gene. They want **5-second understanding**, then progressively
more depth on demand. Three layers:

```
┌──────────────────────────────────────────────────────────────────┐
│   LAYER 1 — SNAPSHOT (always visible, 5-second read)             │
│                                                                   │
│   per     period circadian clock                  Tier A (1680   │
│   ────    FBgn0003068 · CG2647 · X:2685580        pubs)          │
│                                                                   │
│   Perturbation of the period gene fundamentally disrupts the     │
│   circadian clock... [200-char snapshot]                          │
│                                                                   │
│   Human disease via ortholog:  FASPS1 · FASPS3   (OMIM:604348, ..)│
│   Top human orthologs:         PER1 (9/14) PER3 (9/14) PER2 (8/14)│
│   Top mouse orthologs:         Per2 Per3 Per1                     │
│                                                                   │
│   Phenotype categories at a glance:                              │
│     ●●●●●●●●●● behavior (9)         ●●●● development (3)         │
│     ●● sensory_neural (3)            ●● stress_response (3)      │
│     ● lifespan_aging (1)             ● disease_model (2)         │
│     ● reproduction (1)               ● expression_pattern (1)    │
│     ● morphology (1)                                              │
└──────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│   LAYER 2 — BULLETS BY CATEGORY (click any category bar to expand)│
│                                                                   │
│   ▾ behavior  (9 bullets)                                         │
│     [high] Loss-of-function abolishes circadian locomotor         │
│            rhythms, causing flies arrhythmic in constant dark.    │
│            → phenotypes_sub (FlyBase curated)        [LoF]        │
│                                                                   │
│     [high] Mutations alter free-running period of locomotor       │
│            activity: short (~19hr) or long (~29hr) days.          │
│            → CURATOR NOTES                          [either]      │
│            ⓘ alleles: perL, perS                                 │
│                                                                   │
│     [high] Cocaine sensitization is eliminated.                   │
│            → CURATOR NOTES                          [LoF]        │
│     ...                                                            │
│   ▸ development (3)                                               │
│   ▸ sensory_neural (3)                                           │
│   ...                                                              │
└──────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│   LAYER 3 — EVIDENCE DRILL-DOWN (click any bullet to expand)      │
│                                                                   │
│   Bullet ID: FBgn0003068:b11                                      │
│   "Larvae exhibit increased genotoxic stress and double-strand    │
│    DNA breaks in the central nervous system."                     │
│                                                                   │
│   ◆ Confidence: high     · Text specificity: medium               │
│   ◆ Direction:  loss_of_function                                  │
│   ◆ Tissues:    central nervous system                            │
│   ◆ Life stage: larval                                            │
│   ◆ Alleles:    per0                                              │
│                                                                   │
│   Evidence:                                                       │
│   ─ Paper: FBrf0261177 (2024)                                    │
│     "Neuronal Progenitors Suffer Genotoxic Stress in the         │
│      Drosophila Clock Mutant per[0]."                            │
│     Verbatim quote: "In third-instar larvae, we have observed    │
│     that the absence of functional per results in increased      │
│     genotoxic stress... increased double-strand DNA breaks in    │
│     the central nervous system."                                  │
│     [▸ open on PubMed] [▸ FlyBase reference page]                │
└──────────────────────────────────────────────────────────────────┘
```

## Information density tradeoff

The 5-second read needs to answer:
- **What is this gene?** (symbol + name + 1 sentence)
- **Where does it live?** (tier, # papers, location)
- **What does it do organism-level?** (snapshot paragraph)
- **What human disease does it model?** (cross-species link)
- **Which phenotype categories?** (visual density bars)

This is achievable in 6 visual lines. Anything beyond requires click-to-expand.

## Layout / mockup

### Top-of-page: search bar + filters

```
┌────────────────────────────────────────────────────────────────┐
│ 🔍  fly gene phenotype atlas                                    │
│ ┌──────────────────────────────────────────────────────────┐  │
│ │ search: gene symbol, FBgn, human/mouse ortholog, phenotype│  │
│ └──────────────────────────────────────────────────────────┘  │
│ filters: [tier ▾] [category ▾] [confidence: ≥high] [tissue ▾]  │
│         [disease ▾] [life stage ▾] [allele ▾]                  │
└────────────────────────────────────────────────────────────────┘
```

### Result page: gene profile

The three layers from above, stacked vertically. Behaviors:
- Snapshot card always visible at top
- Bullets-by-category section: collapsed by default except first 1-2 categories
- Evidence drill-down: shown inline on bullet click (no modal)

### Reverse-search page

```
"Show me genes affecting circadian rhythm in central nervous system"
                            ↓ (FTS5 + bullet_tissues join)

  ranked by relevance + confidence:

  ▸ per  [9 bullets match]   tier A · FASPS1, FASPS3 disease
    ▸ "Loss-of-function abolishes circadian locomotor rhythms..."
    ▸ "Larvae exhibit increased genotoxic stress and DSBs in CNS..."
    ▸ ...
  ▸ N    [2 bullets match]   tier A · Adams-Oliver, CADASIL
    ▸ ...
  ▸ shi  [1 bullet matches]   tier B · DNM1 → epileptic encephalopathy
```

## Specific interactions for a lab member's daily workflow

| Task | UI path |
|---|---|
| "I have a hit list of 12 candidate genes from a screen — quickly rank them by relevance to circadian phenotype" | Paste FBgn list → search "circadian" → ranked match. |
| "I'm reading a paper that cites FBrf0261177 — what other bullets cite this paper?" | Click paper ID in any bullet → reverse cite view. |
| "My XQTL hits chromosome 2L 5M-5.2M — which genes there are interesting for memory?" | Filter by genomic location (future), then search "memory". |
| "Is there a fly model of OMIM 604348?" | Direct OMIM search → goes to per. |
| "What does CG13725 do?" (sparse CG-only gene) | Search → see synonyms → cross-species rescue kicks in (mouse Per1 has Y phenotype). |
| "Compare per and tim phenotype overlap" | Multi-gene view (future) — show bullets side-by-side, highlight shared categories. |

## Implementation tech stack

For a lab-internal version (Stephen + Sarah + Long's grad students):

### Minimum viable: FastAPI + jinja2 + sqlite

```
# 1 file, ~200 lines:
src/web.py
  GET /                     → search page
  GET /gene/<fbgn>          → gene profile (Layer 1 + collapsible Layer 2)
  GET /api/gene/<fbgn>      → JSON for layer 3 expansion
  GET /search?q=...&filters... → search results
  GET /omim/<id>            → reverse OMIM lookup
  GET /paper/<fbrf>         → bullets citing this paper
```

Static HTML + minimal JS for collapse/expand. **No build pipeline.** Runs as:

```bash
python3 src/web.py    # http://localhost:8000
```

### Production version: full web app

If we want to make it public (after FlyBase grant termination potentially makes
us relevant to broader community):

- **Backend**: FastAPI on a small VPS, SQLite in-memory + read-only mode (handles 100s of req/sec)
- **Frontend**: Vanilla JS or htmx (no React build needed for this complexity)
- **Hosting**: Cloudflare Pages + a tiny VPS for the API ($5/month)
- **Updates**: re-run `build_sqlite.py` weekly; deploy via rsync

### Stretch goals

- **Embedding-based search**: index every bullet phenotype with `sentence-transformers`,
  vector store via sqlite-vec. Lets users search by *concept* not just keyword.
- **Cross-gene similarity**: for any gene, list "most similar genes" by Jaccard
  of (categories × tissues × disease links).
- **Author profiles**: show "which papers from author X are cited across our genes."
- **Diff view**: when v1.2 → v1.3 schema upgrade, show per-gene before/after.

## Key principle: it's a research tool, not a consumer app

- **Density over white space**: scientists want information per pixel, not big margins.
- **Provenance ALWAYS visible**: every claim has a citation link. No floating facts.
- **Confidence labels prominent**: "[high]" / "[medium]" badges by every claim.
- **Lint warnings shown**: if the gene record has _lint warnings, show a small ⚠ in the snapshot.
- **Compare-with-FlyBase always one click away**: "Open this gene on flybase.org" link
  in every profile — we augment FlyBase, we don't replace it.

## What this WOULDN'T have (deliberate scope cuts)

- ❌ User accounts / login — every user is anonymous
- ❌ Bookmark / favorite — use browser bookmark instead
- ❌ Comments / annotations from users — research tool, not Wikipedia
- ❌ "Cite this page" widget — research paper or DOI is the citable thing
- ❌ Beautiful animations / progressive web app polish — research tool, not portfolio piece

## Phasing

| Phase | Deliverable | Effort |
|---|---|---|
| 0 (current) | CLI: `lookup.py` 12 query types | done |
| 1 | Single-page lab-internal webapp (FastAPI + sqlite, static-y) | ~1 day |
| 2 | Reverse-search index pages (by disease, by tissue, by paper) | ~half day |
| 3 | Embedding-based semantic search | ~1 day |
| 4 | Public-facing deploy + DOI registration | ~1 day |
