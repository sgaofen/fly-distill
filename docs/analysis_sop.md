# Candidate-gene analysis SOP

How to take a QTL interval (or a phenotype with no interval yet) and arrive at a
short list of *truly causal* candidate genes — not a list of genes that merely
share vocabulary with the phenotype. The method is three layers, used in order,
each narrowing the field and each trusted only for what it is good at.

The guiding rule: **the atlas triages; the raw record decides.** Semantic search
and the distilled bullets are fast and wide but lossy; a verdict that will go in
a paper or drive an allele swap must rest on the raw FlyBase record and the
primary literature.

---

## The three layers

### Layer 1 — Candidate net (embedding / region)
Cheap, wide, low-precision. Use it to avoid missing anything, never to rank.

```bash
# interval → every gene in the peak (method-independent; no prompt bias)
flyatlas region 3L:9.0e6-9.5e6 --json

# or phenotype-first, restricted to a region (ranking is vocabulary-driven — treat as a net)
flyatlas ask "<12–15 token keyword bag>" --region 3L:9.0e6-9.5e6 --limit 15
```

For query wording see [query_prompt_guide.md](query_prompt_guide.md). Two cautions
that the calibration below made concrete:

- **The embedding ranks on text similarity, so it produces vocabulary artifacts.**
  Genes score high for sharing a token (a *zinc*-finger gene under a zinc trait, a
  `Cyp6`-named P450 with no measured activity, an octopamine *receptor* when the
  query contains "octopamine"). High rank ≠ mechanism.
- **`qtl-rank` scores against the stored phenotype string, which is generic**
  ("Larval survival ~90% mortality"). Within-interval ranking therefore rewards
  generic survival/stress vocabulary. Use it to enumerate, not to choose.

### Layer 2 — Triage (distilled atlas)
Fast, structured, lossy. Read the bullets to bin candidates into tiers and decide
which few are worth deep verification.

```bash
flyatlas gene MTF-1        # categorized bullets, confidence + direction, cross-species
```

What the atlas is good at: it pre-categorizes, tags confidence and effect
direction, and **preferentially distills the high-value papers** (it kept the one
*Nat Aging* paper among 39 for `Svip`). What it loses: the interaction layer
entirely, allele-level molecular detail, raw genotype→phenotype records, and most
of the literature (e.g. `Svip` 19/39 papers distilled, `Tbh` 20/255). Good enough
to triage; not enough to conclude.

### Layer 3 — Verdict (raw record + primary papers)
Slow, complete, decisive. Run **only on the handful of survivors** from Layer 2.

```bash
python3 tools/deep_dossier.py Svip      # local FlyBase bulk, no internet
```

`deep_dossier` pulls, from the local bulk, what the atlas does not carry:

- every **allele** with its molecular lesion — flagging **point mutations and
  human-disease-equivalent variants** (the natural-variation signature a QTL needs)
- all **raw genotype→phenotype records** (the atlas compressed these into a few bullets)
- **genetic + physical interactions** (absent from the atlas)
- the gene snapshot + best summary
- the full **publication list with PMID / PMCID / DOI**, newest first

Then read the 1–3 most relevant **primary-paper abstracts** by PMID for the
measured result (effect size, condition, direction). Full article text is not
local — the PMIDs make that lookup targeted.

A verdict weighs **directly-measured evidence** (transgenic resistance, an
allele-resolved lifespan effect, a measured aggression assay) over shared
vocabulary or genomic proximity. Default to *artifact* when the only link is
vocabulary-deep.

---

## Why three layers, and why deep verification is not optional

A 39-gene deep pass over four QTLs with paper-validated causal genes ("anchors")
calibrated the method:

- **All anchors recovered and confirmed** with primary evidence (transgenic
  overexpression, survival GWAS, interaction networks). For biochemical traits the
  causal gene is the obvious detox machinery, and Layer 3 supplies the proof the
  atlas only summarized.
- **Layer 3 changed verdicts Layer 2 got wrong — in both directions.** Genes the
  atlas ranked as leads collapsed on inspection (a positional `Cyp9h1` with zero
  alleles and only "viable" RNAi; a "longevity" gene whose short-lived record was
  actually a bacterial-infection phenotype). One gene the atlas-only pass had
  dismissed as an artifact was *upgraded* once its measured ROS-buffering
  phenotype was read. Deep verification is therefore not a rubber stamp.

The cost asymmetry is the whole argument: the atlas covers 14k genes in one pass,
but any given question turns on a handful. Pay the deep cost only there. Do **not**
re-distill the corpus to recover the lost detail — `deep_dossier` recovers it on
demand, per gene, from the same local source.

---

## Checklist

1. **Net** — `flyatlas region <interval>` (or `ask --region`); take all genes, ignore the ranking's tail.
2. **Triage** — `flyatlas gene <sym>` on the candidates; bin into tiers; pick the survivors worth deciding.
3. **Verify** — `deep_dossier <sym>` on each survivor; read the interaction layer, the allele molecular detail, the raw genotype→phenotype records; fetch the top PMIDs.
4. **Decide** — prefer measured evidence over vocabulary. For a QTL, favor an
   allele-resolved / point-mutation effect (natural-variation signature) and a
   mechanism consistent with the trait's conditions (e.g. constitutive and
   diet-independent for a both-diets lifespan peak; metabolic/transport/repair for
   a biochemical drug trait).
5. **Stay honest about blind spots** — an uncharacterized gene under the peak with
   no record cannot be ruled out by a low embedding score. If the causal gene is
   novel-function, no annotation-based layer will surface it; say so.
