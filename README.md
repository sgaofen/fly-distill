# Fly Gene-Phenotype Atlas

A general-purpose, programmatically queryable gene-phenotype atlas for
*Drosophila melanogaster* (~14,000 protein-coding genes), distilled from
FlyBase + MGI + HPO + OMIM via GLM-5.1 and enriched by deterministic
post-processing.

## What you get per gene

- One-paragraph snapshot of organism-level effects
- 20–30 phenotype "bullets" with category, direction, confidence, source citations
- Human + mouse ortholog data with DIOPT scores and Entrez IDs
- OMIM disease links with `via_ortholog` provenance
- GO slim categories, tissue/life-stage/allele tags
- Full provenance (SHA256 hashes of input bundle and raw LLM output)

## Use cases

- forward-genetics labs ranking candidate genes from XQTL / RNAi / CRISPR screens
- disease modeling labs searching for fly models of human diseases
- drug discovery (human target → fly ortholog → phenotype)
- aging / behavior / immune labs surveying genes by category
- comp bio / ML training corpus
- educators / paper writers
- anyone tired of clicking through FlyBase 5x per query

## Quick start

```bash
# install (depends on Python 3.9+, curl, sqlite3, optional: jsonschema)
pip3 install jsonschema

# download bulk databases (~375 MB, runs once)
python3 src/download_flybase_bulk.py
python3 src/download_mouse_human.py

# distill one gene
python3 src/fetch_gene.py FBgn0003068        # build the bundle
python3 src/distill_via_claude.py FBgn0003068 # GLM-5.1 distillation
python3 src/canonicalize.py                   # post-process → canonical JSON

# build searchable index
python3 src/build_sqlite.py
python3 src/build_indices.py

# query
python3 src/lookup.py gene per
python3 src/lookup.py disease "Sleep"
python3 src/lookup.py omim 604348
python3 src/lookup.py paper FBrf0261177
python3 src/lookup.py phenotype "circadian rhythm" --confidence high

# QA
python3 src/qa.py tier1                      # deterministic checks
python3 src/qa.py sample                     # produce audit sample
python3 src/qa_tier2.py run                  # GLM tier-2 audit
```

## Architecture

See `docs/spec_v1_1.md` for the full spec, `docs/cluster_layout.md` for
production deployment, `docs/qa_strategy.md` for the QA tier design,
`docs/concurrency_strategy.md` for rate-limit handling.

```
data/flybase_bulk/        FlyBase TSV dumps (~57 MB)
data/mgi/, hpo/, omim/    MGI + HPO + OMIM open subset (~318 MB)
data/cache/<FBgn>/        per-gene fetched bundle (lean: ~50 KB)
output/genes/<FBgn>.json  canonical schema v1.2 record
output/index/             SQLite FTS5 + inverted JSON indices
output/qa/                tier-1 deterministic + tier-2 LLM audit reports
src/*.py                  pipeline + canonicalize + index + lookup + QA
docs/*.md                 design documents + spec
prompts/*.md              distillation system prompts (v1 baseline + v2 tightened)
```

## Project status

Active development. Tested on 10 genes spanning sparse CG-only (4 bullets, 14 pubs)
to highly pleiotropic (Notch — 29 bullets, 3693 pubs). Schema v1.2 stable. Ready
for production batch at 14k-gene scale on cluster.

## License

MIT (code) / data subject to upstream FlyBase, MGI, HPO, OMIM terms.

## Author

Stephen Yu (sgaofen on GitHub), in collaboration with Long lab @ UCI.
