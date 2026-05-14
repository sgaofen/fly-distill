# QA strategy — keeping GLM output quality stable at 14k-gene scale

## The problem

GLM-5.1 calls on complex genes (high publication count, large input bundle)
can produce variable output quality. We need a way to **detect quality
problems WITHOUT re-running every gene** (re-running 14k genes through Opus
would cost ~$15k and weeks of wall time).

## The strategy: three-tier sampling

### Tier 1 — automated checks on every gene (0 LLM cost)

Runs in seconds per gene. Pure deterministic Python. Catches the common
failure modes without any model. Implemented in `src/qa.py`.

| Check | What it catches |
|---|---|
| **Schema conformance** | Missing required fields, wrong types, enum violations |
| **Citation existence** | Every cited FBrf must exist in the gene's input bundle. Phantom citations = hallucination. |
| **Phenotype-input overlap** | Each bullet's phenotype must share ≥3 content words with the bundle. No overlap = pure invention. |
| **Bullet uniqueness** | No two bullets in the same gene should have ≥80% phenotype-text overlap. Duplicates = pass-1 noise. |
| **Confidence/specificity distribution** | A gene with all-low confidence OR all-low specificity is suspicious. |
| **Bullet count vs gene tier** | Well-studied gene (≥500 pubs) with <10 bullets → likely truncated. Sparse gene with 30 bullets → likely hallucinated. |
| **Cross-species citation match** | OMIM IDs in `human_disease_links` must match FlyBase bulk for that gene. |
| **Statistical outliers** | Cohort-level: any gene >3σ from cohort norm on (bullets, citations, tissues, diseases) gets flagged. |

Output: `output/qa/tier1_report.jsonl` — one line per gene with a `qa_score`
(0-100) and detailed flags.

**Cost: 0 LLM calls. ~5 seconds per 1000 genes.**

### Tier 2 — stratified Opus audit on ~5% sample

Random stratified sample for Opus 4.7 to deeply check. Token-frugal:

| Stratum | Genes in pop. | Sample size | Reason |
|---|---|---|---|
| Tier A (≥500 pubs, well-studied) | ~900 | 30 (~3%) | High-coverage genes — confirm comprehensiveness |
| Tier B (50-500 pubs, medium) | ~5,000 | 60 (~1.2%) | Modal case — confirm average quality |
| Tier C (<50 pubs, sparse) | ~8,000 | 50 (~0.6%) | Hallucination risk highest here — confirm grounding |
| Tier 1 flagged | varies | all (up to 100) | Investigate any auto-detected issues |
| **Total** | **~14,000** | **~240 genes** | |

Per-gene Opus audit:
- Show Opus the gene's distilled JSON + the original bundle
- Ask Opus to score: completeness (0-10), accuracy (0-10), citation quality (0-10), hallucinations (yes/no list)
- Returns ~500 tokens of structured feedback

**Cost: 240 genes × ~$0.20/Opus-call (Max-20x covers, or ~$50 if pay-per-token).
Wall time: ~30 min via 10-concurrent.**

### Tier 3 — cross-model consistency probe on ~30 genes

For the highest-bar QA: rerun a small subset with a DIFFERENT model entirely
and check semantic agreement with our GLM-5.1 output.

| Model | Genes | Use |
|---|---|---|
| Opus 4.7 (Max 20x) | 20 | Gold-standard alt distillation |
| Gemini 2.5 Pro (free tier) | 10 | Independent third reference |
| GLM-5.1 with different prompt | 10 | Prompt-stability check |

Compare via:
- **Bullet overlap** (Jaccard on category × phenotype-stem set)
- **OMIM ID intersection** for disease links
- **Category distribution chi-square**

A gene whose GLM-5.1 output diverges substantially from Opus's gets flagged
as low-confidence → may need re-distillation or human review.

**Cost: 40 genes × Opus + 10 × Gemini = ~$30 + free Gemini. Wall time: ~1h.**

## Decision tree — when does a gene get re-distilled?

```
                    ┌──────────────────────────┐
                    │ Tier 1 auto checks        │
                    │ (every gene, 0 cost)      │
                    └────────────┬──────────────┘
                                 │
              ┌──────────────────┼──────────────────┐
              │ qa_score >= 80  │ 60 <= score < 80 │ score < 60
              │                 │                  │
              ▼                 ▼                  ▼
         ACCEPT             TIER 2 AUDIT      RE-DISTILL
        (no action)        (Opus review)      (two-pass harness)
                                 │                  │
                                 ▼                  ▼
                          if Opus says OK     write to output/
                          → ACCEPT           run tier 1 again
                          else → RE-DISTILL
```

Plus: **all genes in stratified sample go through Tier 2 regardless of Tier 1
score** — to catch silent failures.

## What Tier 1 specifically checks (implementation in `src/qa.py`)

### Check 1: citation existence

```python
for bullet in gene["bullets"]:
    for cit in bullet["citations"]:
        if cit["type"] == "fbrf":
            assert cit["value"] in bundle's selected_fbrfs, "phantom citation"
```

### Check 2: phenotype-input lexical overlap

```python
# Tokenize phenotype to content words (strip stop words, ≥4 chars)
phen_tokens = content_tokens(bullet.phenotype)
bundle_tokens = content_tokens(bundle's auto_summary + sections + abstracts)
overlap = len(phen_tokens & bundle_tokens)
if overlap < 3:
    flag("phenotype.no_input_grounding", severity=warn)
```

### Check 3: bullet uniqueness

Compare every pair of bullets within a gene. If two bullets share ≥80%
tokens after stemming, flag duplicate.

### Check 4: confidence + specificity distribution

```python
n_high = count(bullets with confidence='high')
n_low_spec = count(bullets with text_specificity='low')
if n_high / total > 0.95:
    flag("confidence.over_confident")  # model didn't differentiate
if n_low_spec / total > 0.8:
    flag("specificity.too_low")        # phenotypes too vague
```

### Check 5: bullet count vs tier

```python
expected = {
  ">500": (18, 35),     # tier A: 18-35 bullets
  "50-500": (12, 28),   # tier B
  "<50":  (5, 20),      # tier C — sparse, fewer bullets ok
}
if not (expected_min <= n_bullets <= expected_max):
    flag("bullet_count.out_of_range")
```

### Check 6: cross-species OMIM consistency

```python
omim_in_output = {d["omim_id"] for d in gene.cross_species.human_disease_links if d["omim_id"]}
omim_in_flybase_bulk = lookup(fbgn → OMIM IDs in dmel_human_orthologs_disease.tsv)
missed = omim_in_flybase_bulk - omim_in_output
phantom = omim_in_output - omim_in_flybase_bulk
if missed:
    flag("omim.missed", n=len(missed))
if phantom:
    flag("omim.phantom", severity=error)  # never should happen post-enrichment
```

### Check 7: statistical outliers

After running tier 1 on all genes, compute cohort-level stats:

```python
median_bullets, std_bullets = compute_cohort_stats(all_genes)
for gene in genes:
    z = (gene.n_bullets - median) / std
    if abs(z) > 3:
        flag("cohort_outlier.bullet_count", z=z)
```

Same for: # citations per bullet, # diseases, % confidence=high, % specificity=high.

## Scoring formula

```
qa_score = 100
- 20 if schema_drift in _lint
- 15 if any phantom citation
- 10 per bullet with no input grounding
- 5 per duplicate bullet
- 5 if confidence over-flat
- 5 if specificity all-low
- 5 if bullet count out of range
- 10 if cohort outlier
- 0 floor
```

Genes with qa_score ≥80 are ACCEPT, 60-80 go to Tier 2 audit, <60 → re-distill.

## When this strategy works

- **Catches the typical failures**: phantom citations, schema drift, duplicate
  bullets, mode-collapsed confidence — all detected without a model.
- **Catches hallucinations**: zero-overlap phenotypes are caught lexically.
  Subtler hallucinations (wrong direction, paraphrased real claim) require
  Tier 2 Opus.
- **Spots the long-tail outliers**: cohort statistics surface the genes that
  are "weird" relative to peers.
- **Frugal with Opus**: 240 audited / 14k total = 1.7%. Manageable.

## When this strategy doesn't work

- **Subtle scientific incorrectness**: e.g., model says "loss-of-function
  causes X" but the paper actually said "overexpression causes X". Cannot
  be caught lexically; needs Tier 2 Opus or expert human.
- **Missing important phenotypes**: model didn't mention a phenotype that
  IS in the input. Detected only by Tier 2 prompts like "what's in the input
  but not in the output?".
- **Cross-gene reasoning errors**: e.g., model attributes a phenotype to
  the wrong gene in a pathway. Hard to catch without manual review.

For these, we accept the residual risk and document it in the methods section.

## Run-time integration

```bash
# After main pipeline finishes:
python3 src/qa.py tier1                    # auto-check every gene → tier1_report.jsonl
python3 src/qa.py sample --tier1-threshold 80  # produce audit sample list
python3 src/qa.py tier2 --sample-file ...  # run Opus audits (needs Anthropic API key)
python3 src/qa.py tier3 --n 30             # cross-model consistency on 30 genes
python3 src/qa.py report                   # combine all into output/qa/final_report.md
```

## Cost summary

| Stage | LLM calls | Token cost (rough) | Wall time |
|---|---|---|---|
| Distillation (one pass) | 14k × 1 | ~$1000 if pay-per-token, $0 via Coding Plan | 17.5h |
| Distillation (two-pass for complex) | 14k × 1.4 | +40% above | +40% |
| Tier 1 (auto checks) | 0 | $0 | 5 min |
| Tier 2 (240 Opus audits) | 240 | ~$50 / $0 with Max-20x | 30 min |
| Tier 3 (30 cross-model) | 40 | ~$30 / $0 with Max-20x | 1 hour |
| Re-distillation (failed genes, ~5%) | ~700 × 1 | ~$50 / $0 via Coding Plan | 1 hour |
| **Total marginal Opus cost** | | **~$130 worst case, $0 with subscriptions** | |

Production-ready, under-$200 budget, under-2x wall-time overhead vs naive run.
