# Drosophila QTL Atlas — First-Pass Cross-Reference Findings

**Author:** Stephen Yu (Long Lab, UCI) · **Date:** 19 May 2026
**Source data:** 24 mapped QTLs from 5 published studies (Carboplatin, Gemcitabine, Methotrexate, Malathion, Zinc, Caffeine)
**Atlas version:** fly-distill v1.4 (14,019 *D. melanogaster* protein-coding genes; both r5 and r6 chromosome coordinates)

---

## Summary

After cross-referencing all 24 QTL intervals against the atlas, the all-pairs coordinate-overlap analysis surfaces **six pairs** of independent studies whose mapped intervals share genome space. Four of these are **cross-class** — different drug families converging on the same physical region — and constitute the strongest evidence that some genome regions encode broadly-acting stress-response machinery rather than drug-specific resistance.

**Three findings worth your attention:**

1. **Malathion × Caffeine on 2R (201 kb).** Top two shared candidates are **Cyp12d1-d** and **Cyp12d1-p** — paralogous cytochrome-P450 monooxygenases that the FlyBase literature documents in both insecticide detoxification *and* caffeine metabolism. Neither original paper appears to have flagged this. Section 4.1.

2. **Methotrexate × Zinc on X (297 kb).** Confirms the overlap you noted between the chemotherapy and zinc studies. Top shared candidates: **mamo** (Zn-finger maternal-effect TF), **inaE**, **jub**, **Nup93-1** — all consistent with nuclear-envelope and Zn-coordination biology. Section 4.5.

3. **The same-class controls behave as expected**: the two chemo × chemo overlaps recover oogenesis-specific genes (*yolkless*, *armi*, *CycJ*) and ROS-detoxification (*Gtpx*). This is the sanity check that the cross-class signals are not artifacts. Sections 4.3, 4.4.

The full per-QTL candidate ranking (all 24 QTLs × top-K candidates with 2D scores) is in the companion file `qtl_report.md` available in the repository.

---

## How the analysis works (brief)

For each gene in the atlas we pre-compute a dense semantic embedding of its FlyBase summary, structured phenotype bullets, and **verbatim cross-species ortholog phenotype context** (mouse MGI knockout phenotypes; human HPO clinical phenotypes; linked OMIM disease features). All cross-species terms come straight from FlyBase, MGI, and HPO — no inference layer is involved in producing them.

For each QTL the pipeline does two steps:

- **Coordinate filter:** SQL subsets the atlas to genes whose r6 chr/start/end intersect the QTL interval. For the 8 chemo QTLs originally reported in r5, the lift is done by per-FBgn join between FB2026_01 and FB2014_01 `gene_map_table` (not chain-file interpolation), which preserves authoritative coordinates for the 96.8 % of atlas FBgns present in both releases.
- **Semantic ranking:** the QTL's phenotype description (verbatim from your table, e.g. *"Adult female longevity on 1% caffeine"*) is compared by cosine similarity to each candidate gene's pre-computed embedding. The result is an **evidence score** in [0, 1].

Each gene also gets an **annotation-quality score** computed from FlyBase aggregates (bullet count, reference count, total publication count, plus binary indicators for HPO / MGI / disease coverage; stub genes get a penalty term). The two scores are reported on **independent axes**, deliberately not collapsed into one number — a poorly-annotated gene with strong evidence ("novel lead") and a heavily-studied gene with no evidence ("likely not") are very different prior states.

Per your "absence of evidence is not evidence of absence" principle, sparsely-annotated genes in the QTL interval are kept in a separate quadrant (CANT-RULE-OUT) rather than excluded.

---

## Coverage check

| Quantity | Value |
|---|---|
| Atlas FBgns | 14,019 |
| Atlas ∩ r6 gene_map_table (FB2026_01) | 13,986 (99.8 %) |
| Atlas ∩ r5 gene_map_table (FB2014_01) | 13,569 (96.8 %) |
| Atlas FBgns absent from both releases | 33 (0.2 %, retired/secondary IDs) |
| Atlas FBgns absent from r5 only | 450 (post-2014 IDs) |

**Gene-count verification against your reported counts** (16 r6-native QTLs): 10 of 16 are exact matches; the other 6 differ by 1–2 genes at the interval boundary. The 8 r5-native chemo QTLs are not directly comparable (you reported H², not gene count) but lifted r6 intervals produce sensible gene-count distributions.

---

## 4. The findings

For each overlap below: the shared genome region, the two parent phenotypes, and the top shared candidates ranked by `min(ev_A, ev_B)` so genes relevant to **both** parent phenotypes float to the top. Near-ties are broken by annotation depth (n_bullets, then n_refs) to demote heterochromatic tandem-repeat clusters whose embeddings collide.

`ev_A` and `ev_B` refer to evidence scores against phenotype A and phenotype B respectively.

---

### 4.1 Malathion × Caffeine_D — 201 kb on 2R *(cross-class)*

| | |
|---|---|
| **Region (r6)** | 2R: 10,966,645 – 11,168,099 |
| **Overlap size** | 201,455 bp |
| **Phenotype A** | Adult survival under malathion (organophosphate, ~95 % lethal dose) |
| **Phenotype B** | Adult-female longevity on 1 % caffeine |
| **Source studies** | PMC9713458 (Malathion) · PMC8893256 (Caffeine) |
| **Total genes in shared region** | 10 |

The cleanest of the four cross-class findings. Both stresses challenge xenobiotic metabolism; both top candidates are characterized P450 detox enzymes.

**Top shared candidates**

| Rank | Gene | ev malathion | ev caffeine | n_bullets | function |
|---:|---|---:|---:|---:|---|
| 1 | **Cyp12d1-d** (FBgn0053503) | 0.58 | 0.65 | 19 | Cytochrome P450 — insecticide + caffeine detox |
| 2 | **Cyp12d1-p** (FBgn0050489) | 0.59 | 0.64 | 17 | Paralog of #1, same function class |
| 3 | CG12391 (FBgn0030411) | 0.59 | 0.63 | 10 | Uncharacterized |
| 4 | BBS4 (FBgn0033052) | 0.59 | 0.64 | 9 | Bardet-Biedl Syndrome 4 ortholog, ciliary basal body |
| 5 | CG13229 (FBgn0030412) | 0.58 | 0.65 | 6 | Uncharacterized adjacent gene |
| 6 | CG13231 (FBgn0030413) | 0.59 | 0.64 | 5 | Uncharacterized adjacent gene |
| 7 | shn (FBgn0003396) | 0.57 | 0.61 | 25 | Schnurri Zn-finger TF; BMP signaling |

**Cyp12d1-d.** Cytochrome P450 monooxygenase. Overexpression in detoxification tissues (fat body, Malpighian tubules, midgut) confers resistance to DDT and dicyclanil; mRNA is constitutively elevated 6-fold in DDT-resistant strains and further induced by DDT exposure. The gene **also participates in caffeine metabolism** — dietary guarana upregulates Cyp12d1 expression in flies (FBrf0263047), and gene silencing alters caffeine metabolite profiles (FBrf0227555). Human orthologs are CYP24A1/CYP27A1/CYP27B1 (vitamin D metabolism, cerebrotendinous xanthomatosis, vitamin-D-dependent rickets).

**Cyp12d1-p.** Paralog of Cyp12d1-d on the same chromosomal segment. Same DDT/dicyclanil resistance profile; same Cyp450 substrate-specificity class.

**Interpretation.** The shared region contains a small Cyp450 cluster whose products perform broad-substrate xenobiotic detoxification. Independent QTL studies for two unrelated chemical stresses (organophosphate pesticide; methylxanthine alkaloid) converged on this region. The Malathion paper analyzed 344 genes in its interval; the Caffeine paper analyzed 51; neither paper's discussion names Cyp12d1.

**Suggested experiment.** RNAi knockdown of Cyp12d1-d or Cyp12d1-p (e.g. VDRC GD lines) followed by both the published malathion-survival and 1%-caffeine-longevity assays should shorten both, providing causal validation.

---

### 4.2 Gemcitabine_GA × Malathion — 1.93 Mb on 2R *(cross-class)*

| | |
|---|---|
| **Region (r6)** | 2R: 10,966,645 – 12,899,385 |
| **Overlap size** | 1,932,741 bp |
| **Phenotype A** | Chemotherapy-induced ovary atrophy / fertility reduction |
| **Phenotype B** | Adult survival under malathion |
| **Source studies** | PMC4174942 (Gemcitabine) · PMC9713458 (Malathion) |
| **Total genes in shared region** | 301 |

**Caveat.** Both contributing QTLs have wide confidence intervals (≈2.2 Mb each), so this overlap region contains 301 genes — treat as a 2-Mb region of interest, not a candidate gene list. Top candidates concentrate on mitochondrial-apoptosis machinery.

**Top shared candidates**

| Rank | Gene | ev Gem | ev Mal | n_bullets | function |
|---:|---|---:|---:|---:|---|
| 1 | **Buffy** (FBgn0029131) | 0.60 | 0.62 | 29 | Bcl-2 family anti-apoptotic; mitochondrial outer-membrane permeabilization |
| 2 | **Taz** (FBgn0030182) | 0.63 | 0.59 | 28 | Tafazzin; cardiolipin remodelase; Barth syndrome model |
| 3 | qvr (FBgn0263395) | 0.60 | 0.60 | 28 | quiver; Shaker K+ channel modulator; sleep |
| 4 | Prp8 (FBgn0033688) | 0.60 | 0.58 | 28 | Spliceosome core |
| 5 | pyr (FBgn0033649) | 0.60 | 0.60 | 26 | FGF ligand thisbe; embryonic patterning |
| 6 | **dare** (FBgn0263983) | 0.62 | 0.60 | 25 | Adrenodoxin reductase; electron donor for mitochondrial P450s |
| 7 | E(Pc) (FBgn0000581) | 0.61 | 0.59 | 24 | Enhancer of polycomb; chromatin |

**Buffy.** Bcl-2 family member acting at the mitochondrial outer membrane to regulate apoptosis. Loss of buffy sensitizes cells to many forms of damage; overexpression suppresses apoptosis in stress models.

**Taz.** Tafazzin, a cardiolipin acyltransferase required for the structural integrity of mitochondrial cristae and respiratory chain super-complex assembly. Loss-of-function is the fly model for Barth syndrome.

**dare.** Adrenodoxin reductase — supplies electrons to mitochondrial cytochrome P450s. Loss causes general mitochondrial dysfunction; provides metabolic linkage to the steroid and xenobiotic detoxification machinery on the same chromosomal segment.

**Interpretation.** Both stresses converge on mitochondrial-driven apoptosis. Chemo via DNA damage signaling through Bcl-2 family regulators; organophosphate via neuronal excitotoxicity → mitochondrial calcium overload → cytochrome-c release. The shared region encodes several mitochondrial-apoptosis decision-makers.

---

### 4.3 Carboplatin × Methotrexate_A — 484 kb on X *(same-class control)*

| | |
|---|---|
| **Region (r6)** | X: 14,169,592 – 14,653,928 |
| **Overlap size** | 484,337 bp |
| **Phenotype A** | Chemotherapy-induced ovary atrophy (Carboplatin) |
| **Phenotype B** | Chemotherapy-induced ovary atrophy (Methotrexate) |
| **Source studies** | PMC4174942 (Carboplatin) · PMC3737169 (Methotrexate) |
| **Total genes in shared region** | 39 |

Same-class control. Both phenotype strings are identical, so `ev_A` equals `ev_B`. This is the sanity check: same-phenotype overlaps should recover obvious oogenesis-specific genes.

**Top shared candidates**

| Rank | Gene | evidence | n_bullets | function |
|---:|---|---:|---:|---|
| 1 | **yl** (FBgn0004649) | 0.64 | 20 | yolkless — vitellogenin receptor; ovary-specific; loss → sterility |
| 2 | Muc12Ea (FBgn0034205) | 0.65 | 13 | Mucin 12 Ea; female-reproductive-tract glycoprotein |
| 3 | mRNA-cap (FBgn0030582) | 0.64 | 12 | mRNA-capping enzyme |
| 4 | βNACtes3 (FBgn0259098) | 0.63 | 11 | Nascent-polypeptide complex β subunit, testis-expressed (X-cluster) |
| 5 | βNACtes6 (FBgn0259095) | 0.64 | 9 | Same family |
| 6 | βNACtes1 (FBgn0259093) | 0.63 | 8 | Same family |
| 7 | CG9400 (FBgn0035608) | 0.64 | 8 | Uncharacterized |

**yl.** Yolkless, the membrane vitellogenin receptor on developing oocytes. Loss-of-function alleles produce small, agametic ovaries — the textbook genetic phenotype for the ovary-atrophy observable measured in the source studies.

**Interpretation.** Same-class overlap recovers a textbook oogenesis gene at #1. This validates the algorithm's ability to find the right biology where biology is known, supporting the cross-class findings above.

---

### 4.4 Gemcitabine_GB × Methotrexate_C — 392 kb on 3L *(same-class control)*

| | |
|---|---|
| **Region (r6)** | 3L: 3,224,838 – 3,616,682 |
| **Overlap size** | 391,845 bp |
| **Phenotype A** | Chemotherapy-induced ovary atrophy (Gemcitabine) |
| **Phenotype B** | Chemotherapy-induced ovary atrophy (Methotrexate) |
| **Source studies** | PMC4174942 (Gemcitabine) · PMC3737169 (Methotrexate) |
| **Total genes in shared region** | 43 |

**Top shared candidates**

| Rank | Gene | evidence | n_bullets | function |
|---:|---|---:|---:|---|
| 1 | **armi** (FBgn0041164) | 0.65 | 21 | Armitage; piRNA pathway; germline transposon silencing; oocyte axis specification |
| 2 | **CycJ** (FBgn0010317) | 0.65 | 20 | Cyclin J; oocyte meiosis |
| 3 | eIF5B (FBgn0034532) | 0.63 | 12 | Translation initiation factor |
| 4 | **Gtpx** (FBgn0035438) | 0.63 | 11 | Glutathione peroxidase; ROS detoxification |
| 5 | CG17746 (FBgn0035529) | 0.63 | 9 | Uncharacterized |
| 6 | Ostm1 (FBgn0034486) | 0.63 | 9 | Osteopetrosis-associated transmembrane protein |
| 7 | Drsl4 (FBgn0044819) | 0.65 | 9 | Drosomycin-like 4; immune AMP |

**armi.** ATP-dependent helicase central to the piRNA pathway. Required for transposon silencing in the female germline; loss causes oocyte axis-specification defects and arrested oogenesis — a developmentally early disruption to the same cell population the chemo agents target.

**Gtpx.** Glutathione peroxidase. Both gemcitabine (cytidine analog → DNA damage → ROS) and methotrexate (folate blockade → DNA damage → ROS) elevate cellular oxidative load. Gtpx is the canonical ROS-scavenging enzyme; its presence at the top of this overlap is biologically appropriate.

**Interpretation.** Second same-class control. Top candidates land in germline-development (armi, CycJ) and oxidative-stress (Gtpx) — exactly where they should for a chemo × chemo overlap targeting the female germline.

---

### 4.5 Methotrexate_A × Zinc_A — 297 kb on X *(cross-class, confirms your hint)*

| | |
|---|---|
| **Region (r6)** | X: 13,796,451 – 14,093,253 |
| **Overlap size** | 296,803 bp |
| **Phenotype A** | Chemotherapy-induced ovary atrophy (Methotrexate, lifted from r5) |
| **Phenotype B** | Larval survival under zinc oxide (~90 % lethal dose) |
| **Source studies** | PMC3737169 (Methotrexate) · PMC12606420 (Zinc) |
| **Total genes in shared region** | 23 |

Your 2026-05-19 note flagged this as a possible overlap (Methotrexate-X around 13.85 Mb r5; Zinc-A around 13.9 Mb r6). The lift confirms it: r5 → r6 mapping puts the Methotrexate interval at X:13,359,248–14,749,376 and the Zinc interval at X:13,796,451–14,093,253, sharing 297 kb.

**Top shared candidates** (Stellate paralogs Ste:CG33237–33247 dominate the raw similarity score because that segment is the heterochromatic Stellate cluster with near-identical embeddings; for interpretive ranking they're demoted by the annotation-depth tiebreak)

| Rank | Gene | ev MTX | ev Zinc | n_bullets | function |
|---:|---|---:|---:|---:|---|
| 1 | **mamo** (FBgn0267033) | 0.63 | 0.62 | 27 | BTB / Zn-finger TF; maternal-effect oocyte gene; Zn-coordinated |
| 2 | **inaE** (FBgn0261244) | 0.58 | 0.63 | 23 | Diacylglycerol lipase α; PIP2/IP3 signaling |
| 3 | **jub** (FBgn0030530) | 0.59 | 0.61 | 22 | Ajuba LIM protein; Hippo + DNA-damage response |
| 4 | **Nup93-1** (FBgn0027537) | 0.62 | 0.67 | 14 | Nuclear-pore component; nuclear-envelope integrity |
| 5 | AMPdeam (FBgn0052626) | 0.60 | 0.63 | 10 | AMP deaminase; purine cycle |
| 6 | Galml2 (FBgn0030525) | 0.61 | 0.63 | 7 | Galmin-like 2 |

**mamo.** BTB/POZ-domain Zn-finger transcription factor. Maternal-effect: required in oocyte for normal embryogenesis. The zinc-coordination at the DNA-binding domain is biochemically essential, and excess cytoplasmic Zn²⁺ disrupts Zn-finger TF function broadly.

**inaE.** Membrane-tethered diacylglycerol lipase α, generates 2-AG signaling lipid; sub-cellular role in light/touch transduction and photoreceptor lifespan. Less obvious direct connection to either stress but consistent with general membrane-stress response.

**jub.** Ajuba LIM family. Direct binding partner of Lats kinase (Hippo pathway) and of nuclear factors involved in DNA-damage response. Genes coupling mechanical/proliferative cues to apoptotic decisions cluster here.

**Nup93-1.** Component of the Nup93–Nup205 sub-complex of the nuclear-pore basket. Nuclear-pore integrity is sensitive to both DNA-damage (chemo) and heavy-metal stress (zinc displaces structurally-bound metals from pore-associated proteins).

**Interpretation.** The shared region encodes nuclear-envelope and Zn-coordinated transcription machinery — both methotrexate (folate-blocked DNA synthesis → genome stress) and zinc toxicity (free Zn²⁺ → disrupted Zn-coordinated proteins) converge on these pathways. The presence of *mamo* — a Zn-finger TF *and* an oogenesis gene — is a falsifiable hypothesis: knockdown should sensitize both the methotrexate ovary-atrophy and the zinc larval-survival phenotypes.

---

### 4.6 Gemcitabine_GA × Caffeine_D — 495 kb on 2R *(cross-class)*

| | |
|---|---|
| **Region (r6)** | 2R: 10,673,345 – 11,168,099 |
| **Overlap size** | 494,755 bp |
| **Phenotype A** | Chemotherapy-induced ovary atrophy (Gemcitabine, lifted from r5) |
| **Phenotype B** | Adult-female longevity on 1 % caffeine |
| **Source studies** | PMC4174942 (Gemcitabine) · PMC8893256 (Caffeine) |
| **Total genes in shared region** | 47 |

**Top shared candidates**

| Rank | Gene | ev Gem | ev Caf | n_bullets | function |
|---:|---|---:|---:|---:|---|
| 1 | **nclb** (FBgn0033474) | 0.64 | 0.65 | 23 | "no child left behind"; H3K4me chromatin reader |
| 2 | **wde** (FBgn0034876) | 0.65 | 0.66 | 20 | windei; SetDB1 partner; H3K9me deposition |
| 3 | **Mat1** (FBgn0040341) | 0.63 | 0.64 | 10 | CDK7 assembly factor; TFIIH complex |
| 4 | CG12343 (FBgn0033472) | 0.64 | 0.66 | 10 | Uncharacterized |
| 5 | CG30020 (FBgn0050020) | 0.63 | 0.63 | 9 | Uncharacterized |
| 6 | CG7220 (FBgn0030915) | 0.63 | 0.66 | 7 | Uncharacterized |
| 7 | stan (FBgn0024836) | 0.59 | 0.63 | 28 | starry night; planar polarity |

**Mat1.** Subunit of TFIIH transcription / nucleotide-excision-repair complex; activates CDK7. Couples transcription initiation to DNA-damage repair. The human ortholog (MNAT1) appears in chemo-resistance pharmacogenomics.

**nclb, wde.** Chromatin-modifier complex components. Stress responses (acute DNA damage from chemo; chronic xenobiotic load from caffeine) both require coordinated rewiring of transcription programs — chromatin-modifying machinery is a logical shared dependency.

**Interpretation.** Both stresses force the cell to rewrite which genes are transcribed. The shared region contains components of the basal transcription machinery (Mat1/TFIIH) and chromatin-modification platform (nclb, wde) that this rewiring depends on.

---

## Limitations

- The pipeline produces ranked candidates, not causal identifications. Validation (RNAi, CRISPR, targeted assay re-runs in the published phenotypes) is required to convert any candidate into a verified causal gene.
- The "CANT-RULE-OUT" quadrant (sparsely-annotated genes with no positive signal) is preserved by design — these are not eliminated but also not actively flagged.
- The r5 → r6 coordinate lift is per-FBgn (covers 96.8 % of atlas); ~3 % of atlas FBgns are absent from FB2014_01 and cannot be queried in r5 space.
- Heterochromatic tandem-repeat clusters (Stellate, βNACtes) produce near-identical embedding vectors; these are demoted by an annotation-depth tiebreak but still appear in candidate lists.
- Linkage disequilibrium is not modeled — published QTL intervals are used as-is. Tighter intervals from your downstream analyses can be plugged in trivially.

---

## Reproducibility

| Item | Location |
|---|---|
| Source repository | https://github.com/sgaofen/fly-distill |
| v1.4 release (atlas.db + canonicals + embeddings) | https://github.com/sgaofen/fly-distill/releases/tag/v1.4 |
| QTL summary input file | `data/QTL_summary.md` |
| Full per-QTL ranking (auto-generated companion) | `output/qtl_report.md` |
| Web UI entry point | `python -m flyatlas.cli serve` → http://localhost:8765/qtl |
| Single-QTL CLI | `python -m flyatlas.cli qtl-rank caffeine_D` |
| Overlap matrix CLI | `python -m flyatlas.cli qtl-overlap` |
| Regenerate this analysis | `python src/build_qtl_report.py` |

**Only runtime dependency:** a Gemini embedding API key (`gemini-embedding-2`) for the query-time semantic vector. All pre-computed gene embeddings, atlas SQL database, and canonical JSON are ship-as-is in the v1.4 release tarballs — no other inference layer is invoked at query time.

---

*Comments, corrections, and counter-evidence welcome.*
