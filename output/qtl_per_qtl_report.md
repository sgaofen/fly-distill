# Drosophila QTL Atlas — Per-QTL Candidate Rankings

**Author:** Stephen Yu (Long Lab, UCI) · **Atlas:** fly-distill v1.4 (14,019 *D. melanogaster* protein-coding genes)

---

## What this is

For each of the **24 mapped QTLs** in your study compilation, this report lists the genes inside the interval, ranks them on the two independent axes you described (evidence × annotation quality), and provides the FlyBase biological context for the top candidates of each QTL.

Each QTL is presented as a self-contained section. No comparisons across QTLs are made in the main body. Cross-QTL coordinate overlaps (an incidental observation while running the analysis) are included as a short appendix.

## Method (one paragraph)

For each gene in the atlas a dense semantic representation has been pre-computed from (a) its FlyBase one-paragraph summary, (b) all mouse-ortholog MGI knockout phenotype terms + human-ortholog HPO clinical phenotype terms + linked OMIM disease features (verbatim, no inference), and (c) the structured phenotype bullets distilled from FlyBase pubs and paper abstracts. For each QTL, the pipeline subsets the atlas to genes in the interval (via per-FBgn r5↔r6 coordinate lookup against FB2026_01 + FB2014_01 `gene_map_table`), then ranks them by cosine similarity between the QTL's phenotype description and each gene's representation. The **evidence score** captures phenotype–gene semantic match. The **quality score** captures how well-studied the gene is (bullet count, reference count, publication count, plus binary indicators for HPO / MGI / disease coverage; stub genes get a penalty term). Per your *absence of evidence ≠ evidence of absence* principle, the two scores are reported on independent axes and never collapsed into one number.

## Quadrants

| Quadrant | Meaning | Action |
|---|---|---|
| ✓ **STRONG** | high evidence + well-annotated | priority follow-up |
| ⚠ **NOVEL LEAD** | high evidence + sparsely annotated | functional experiment candidate; possibly under-studied |
| ✗ **LIKELY NOT** | low evidence + well-annotated | can rule out with reasonable confidence |
| ? **CANT RULE OUT** | low evidence + sparsely annotated | preserved per absence-of-evidence principle |

Cutoffs are evidence ≥ 0.55 and quality ≥ 0.50.

## Coverage sanity check

| | |
|---|---|
| Atlas FBgns | 14,019 |
| Atlas ∩ r6 gene_map_table (FB2026_01) | 13,986 (99.8 %) |
| Atlas ∩ r5 gene_map_table (FB2014_01) | 13,569 (96.8 %) |
| Atlas FBgns absent from both releases | 33 (0.2 %, retired/secondary IDs) |

Of your 16 r6-native QTLs, the atlas-resolved gene count exactly matches your reported count for 10; the remaining 6 differ by 1–2 genes at the interval boundary.

---

## Per-QTL candidate rankings

## Caffeine (xenobiotic, r6; 7 QTLs)

### caffeine_D

| | |
|---|---|
| **Study drug** | Caffeine (xenobiotic) |
| **Phenotype** | _Adult female longevity on 1% caffeine_ |
| **Interval (r6)** | `2R:10,628,099–11,168,099` (540.0 kb) |
| **Significance** | −log₁₀(P) = 13.1 |
| **Source paper** | [PMC8893256](https://pmc.ncbi.nlm.nih.gov/articles/PMC8893256/) |
| **Reported gene count** | 51 |

**Quadrant breakdown** (all 51 genes in interval): ✓ STRONG **32** · ⚠ NOVEL_LEAD **19** · ✗ LIKELY_NOT **0** · ? CANT_RULE_OUT **0**

**Top 10 candidate genes**

| Rank | Gene | Quadrant | ev | q | bullets | refs | pubs |
|---:|---|---|---:|---:|---:|---:|---:|
| 1 | `Prosβ5` | ✓ STRONG | 0.66 | 0.91 | 25 | 17 | 135 |
| 2 | `Cyp12d1-d` | ✓ STRONG | 0.65 | 0.85 | 19 | 11 | 96 |
| 3 | `shn` | ✓ STRONG | 0.61 | 0.97 | 25 | 24 | 345 |
| 4 | `Cyp12d1-p` | ✓ STRONG | 0.64 | 0.83 | 17 | 9 | 100 |
| 5 | `stan` | ✓ STRONG | 0.63 | 0.85 | 28 | 3 | 434 |
| 6 | `CG30016` | ✓ STRONG | 0.63 | 0.78 | 17 | 8 | 32 |
| 7 | `LTV1` | ✓ STRONG | 0.63 | 0.77 | 20 | 5 | 41 |
| 8 | `Daao1` | ✓ STRONG | 0.64 | 0.74 | 18 | 7 | 52 |
| 9 | `CG11883` | ✓ STRONG | 0.65 | 0.68 | 8 | 4 | 40 |
| 10 | `Elp2` | ✓ STRONG | 0.63 | 0.73 | 17 | 3 | 47 |

**Biological context for top 5 candidates**

**1. `Prosβ5` (FBgn0029134)** — ✓ STRONG, ev=0.66, q=0.91

Prosβ5 encodes the catalytic β5 subunit of the 26S proteasome, and its perturbation has sweeping organism-level consequences. Ubiquitous adult-only overexpression extends lifespan, reduces ubiquitinated protein aggregates, and improves feeding and starvation resistance, while neuronal-specific augmentation slows age-related cognitive decline and preserves circadian rhythmicity. · ref: Nguyen et al., 2019, Sci. Rep. 9(1): 3170 (PMID 30816680)

**2. `Cyp12d1-d` (FBgn0053503)** — ✓ STRONG, ev=0.65, q=0.85

Cyp12d1-d encodes a cytochrome P450 monooxygenase that is a major determinant of metabolic insecticide resistance in Drosophila. Overexpression in detoxification tissues (fat body, Malpighian tubules, midgut) confers resistance to DDT and dicyclanil, and its expression is strongly induced by DDT and neonicotinoid exposure. · ref: Daborn et al., 2007, Insect Biochem. Mol. Biol. 37(5): 512--519 (PMID 17456446)

**3. `shn` (FBgn0003396)** — ✓ STRONG, ev=0.61, q=0.97

Schnurri (shn) encodes a zinc finger transcription factor that mediates Dpp/BMP signaling-dependent transcriptional repression. Loss of shn causes embryonic lethality with severe defects in dorsal closure, epidermal patterning, and midgut development. · ref: Beckwith et al., 2013, PLoS Biol. 11(12): e1001733 (PMID 24339749)

**4. `Cyp12d1-p` (FBgn0050489)** — ✓ STRONG, ev=0.64, q=0.83

Cyp12d1-p encodes a cytochrome P450 monooxygenase that functions in xenobiotic detoxification, most notably conferring resistance to DDT and dicyclanil when overexpressed in transgenic flies. Expression of Cyp12d1 is constitutively elevated in DDT-resistant Drosophila strains and is further inducible by DDT exposure, indicating both pre-adaptive and responsive roles in metaboli... · ref: Daborn et al., 2007, Insect Biochem. Mol. Biol. 37(5): 512--519 (PMID 17456446)

**5. `stan` (FBgn0024836)** — ✓ STRONG, ev=0.63, q=0.85

Perturbing starry night (stan), the Drosophila Flamingo/CELSR ortholog, disrupts planar polarity across epithelia and neural tissues, producing misoriented wing hairs, abnormal bristles, rotated ommatidia, and defective sensory-neuron dendrite and axon organization. Strong loss-of-function alleles can cause embryonic or larval lethality, abnormal larval size and developmental r... · ref: Li et al., 2016, Mol. Brain 9(1): 46 (PMID 27129721)

---

### caffeine_F

| | |
|---|---|
| **Study drug** | Caffeine (xenobiotic) |
| **Phenotype** | _Adult female longevity on 1% caffeine_ |
| **Interval (r6)** | `3R:13,447,353–14,347,353` (900.0 kb) |
| **Significance** | −log₁₀(P) = 8.81 |
| **Source paper** | [PMC8893256](https://pmc.ncbi.nlm.nih.gov/articles/PMC8893256/) |
| **Reported gene count** | 105 |

**Quadrant breakdown** (all 105 genes in interval): ✓ STRONG **57** · ⚠ NOVEL_LEAD **48** · ✗ LIKELY_NOT **0** · ? CANT_RULE_OUT **0**

**Top 10 candidate genes**

| Rank | Gene | Quadrant | ev | q | bullets | refs | pubs |
|---:|---|---|---:|---:|---:|---:|---:|
| 1 | `foxo` | ✓ STRONG | 0.65 | 1.00 | 29 | 27 | 906 |
| 2 | `Dop1R1` | ✓ STRONG | 0.62 | 0.98 | 27 | 29 | 350 |
| 3 | `trx` | ✓ STRONG | 0.60 | 0.98 | 32 | 20 | 610 |
| 4 | `Hrb87F` | ✓ STRONG | 0.65 | 0.81 | 20 | 4 | 193 |
| 5 | `spn-B` | ✓ STRONG | 0.63 | 0.83 | 23 | 6 | 124 |
| 6 | `Lkb1` | ✓ STRONG | 0.61 | 0.89 | 28 | 10 | 142 |
| 7 | `MetRS-m` | ✓ STRONG | 0.65 | 0.75 | 15 | 4 | 66 |
| 8 | `B52` | ✓ STRONG | 0.64 | 0.77 | 28 | 7 | 181 |
| 9 | `sqd` | ✓ STRONG | 0.62 | 0.84 | 24 | 4 | 288 |
| 10 | `ninaB` | ✓ STRONG | 0.63 | 0.80 | 15 | 7 | 89 |

**Biological context for top 5 candidates**

**1. `foxo` (FBgn0038197)** — ✓ STRONG, ev=0.65, q=1.00

Drosophila foxo (forkhead box O) is a conserved transcription factor that acts as a central downstream effector of insulin/PI3K signaling to control organismal growth, stress resistance, and aging. Loss-of-function mutants are smaller, short-lived, locomotor-defective, and show progressive degeneration of dopaminergic neurons and indirect flight muscles. · ref: Kwon et al., 2018, Proc. Natl. Acad. Sci. U.S.A. 115(45): E10748--EE10757 (PMID 30348793)

**2. `Dop1R1` (FBgn0011582)** — ✓ STRONG, ev=0.62, q=0.98

Dop1R1 encodes the Drosophila D1-like dopamine receptor, orthologous to human DRD1 and DRD5. Null mutants are viable and fertile but display broad behavioral deficits: disrupted locomotor activity, reduced sleep, impaired olfactory learning and memory, abnormal courtship, and altered thermotaxis. · ref: Kong et al., 2010, PLoS ONE 5(4): e9954 (PMID 20376353)

**3. `trx` (FBgn0003862)** — ✓ STRONG, ev=0.60, q=0.98

trithorax (trx) encodes a histone H3K4 methyltransferase that antagonizes Polycomb-mediated gene silencing and maintains transcriptional activation of developmental genes. Loss-of-function causes embryonic or larval lethality in most alleles, with surviving escapers showing homeotic transformations of abdominal and thoracic segments (haltere-to-wing, segment identity shifts). · ref: Zhu et al., 2017, eLife 6: e22617 (PMID 28084990)

**4. `Hrb87F` (FBgn0004237)** — ✓ STRONG, ev=0.65, q=0.81

Perturbing Hrb87F produces broad developmental and stress-sensitive phenotypes rather than a single visible body-plan defect. Loss of Hrb87F slows development, shortens adult lifespan, reduces female fecundity, sensitizes flies to starvation and thermal stress, and neural knockdown can cause larval lethality with abnormal larval neuroanatomy. · ref: Singh and Lakhotia, 2012, J. Biosci., Bangalore 37(4): 659--678 (PMID 22922191)

**5. `spn-B` (FBgn0003480)** — ✓ STRONG, ev=0.63, q=0.83

Perturbing spn-B primarily disrupts female meiosis and oogenesis: unrepaired meiotic double-strand breaks activate a checkpoint that blocks Gurken accumulation, producing abnormal oocyte nuclear morphology, defective oocyte polarity, ventralized eggshells, dorsal appendage defects, and female sterility or semi-sterility. Loss-of-function alleles are viable, indicating the stron... · ref: Ghabrial and Schupbach, 1999, Nat. Cell Biol. 1(6): 354--357 (PMID 10559962)

---

### caffeine_G

| | |
|---|---|
| **Study drug** | Caffeine (xenobiotic) |
| **Phenotype** | _Adult female longevity on 1% caffeine_ |
| **Interval (r6)** | `3R:25,707,353–27,007,353` (1.30 Mb) |
| **Significance** | −log₁₀(P) = 6.77 |
| **Source paper** | [PMC8893256](https://pmc.ncbi.nlm.nih.gov/articles/PMC8893256/) |
| **Reported gene count** | 144 |

**Quadrant breakdown** (all 144 genes in interval): ✓ STRONG **75** · ⚠ NOVEL_LEAD **69** · ✗ LIKELY_NOT **0** · ? CANT_RULE_OUT **0**

**Top 10 candidate genes**

| Rank | Gene | Quadrant | ev | q | bullets | refs | pubs |
|---:|---|---|---:|---:|---:|---:|---:|
| 1 | `Tl` | ✓ STRONG | 0.62 | 1.00 | 31 | 27 | 1090 |
| 2 | `Nf1` | ✓ STRONG | 0.62 | 0.94 | 27 | 19 | 176 |
| 3 | `Lnk` | ✓ STRONG | 0.65 | 0.82 | 21 | 6 | 95 |
| 4 | `Ets97D` | ✓ STRONG | 0.65 | 0.81 | 23 | 10 | 94 |
| 5 | `LpR1` | ✓ STRONG | 0.62 | 0.89 | 26 | 13 | 94 |
| 6 | `Aldo` | ✓ STRONG | 0.63 | 0.84 | 24 | 5 | 199 |
| 7 | `amon` | ✓ STRONG | 0.62 | 0.88 | 24 | 12 | 121 |
| 8 | `LpR2` | ✓ STRONG | 0.64 | 0.82 | 21 | 6 | 110 |
| 9 | `SPARC` | ✓ STRONG | 0.62 | 0.86 | 26 | 7 | 140 |
| 10 | `CG6295` | ✓ STRONG | 0.66 | 0.73 | 11 | 4 | 69 |

**Biological context for top 5 candidates**

**1. `Tl` (FBgn0262473)** — ✓ STRONG, ev=0.62, q=1.00

Toll perturbation affects the fly at two major organismal levels: early embryonic patterning and innate immune physiology. Maternal or recessive Toll loss causes embryonic lethality with dorsal-ventral epidermal/cuticle defects, while constitutive Toll activation drives inflammatory hemocyte expansion, melanotic masses, growth inhibition, and pupal/adult lethality. · ref: Erdelyi and Szabad, 1989, Genetics 122: 111--127 (PMID 2499514)

**2. `Nf1` (FBgn0015269)** — ✓ STRONG, ev=0.62, q=0.94

Nf1 encodes the Drosophila ortholog of human neurofibromin 1, a Ras GTPase-activating protein that also regulates cAMP/PKA signaling in the nervous system. Loss of Nf1 causes a broad syndrome of circadian and locomotor rhythm disruption, short and fragmented sleep, excessive grooming, impaired associative learning and memory, decreased body size, and reduced lifespan. · ref: Bai et al., 2018, Cell Rep. 22(13): 3416--3426 (PMID 29590612)

**3. `Lnk` (FBgn0028717)** — ✓ STRONG, ev=0.65, q=0.82

Lnk (also known as dSH2B) is a critical intracellular adaptor protein in the insulin/insulin-like growth factor signaling (IIS) pathway, acting in parallel to Chico to promote growth and metabolic homeostasis. Loss-of-function mutations result in viable but significantly smaller flies due to decreases in both cell size and cell number, while also extending lifespan and increasi... · ref: Song et al., 2010, Cell Metab. 11(5): 427--437 (PMID 20417156)

**4. `Ets97D` (FBgn0004510)** — ✓ STRONG, ev=0.65, q=0.81

Ets97D (also known as Delg/D-elg) encodes an ETS family transcription factor orthologous to human GABPα that is essential for Drosophila viability, with null and strong loss-of-function alleles causing death during the pupal-to-adult transition. It plays a critical role in abdominal segment patterning during embryogenesis, oogenesis including egg chamber axis formation and bord... · ref: Schulz et al., 1993, Oncogene 8(12): 3369--3374 (PMID 8247539)

**5. `LpR1` (FBgn0066101)** — ✓ STRONG, ev=0.62, q=0.89

Lipophorin receptor 1 (LpR1) is a brain-enriched LDLR-family receptor that mediates lipid uptake and neuron-glia lipid shuttling essential for nervous system development and maintenance. Loss-of-function causes age-dependent neurodegeneration, climbing defects, shortened lifespan, impaired olfactory memory, and disrupted sleep architecture, with anatomical defects concentrated ... · ref: Rojo-Cortés et al., 2022, BMC Biol. 20(1): 198 (PMID 36071487)

---

### caffeine_A

| | |
|---|---|
| **Study drug** | Caffeine (xenobiotic) |
| **Phenotype** | _Adult female longevity on 1% caffeine_ |
| **Interval (r6)** | `X:2,916,075–4,736,075` (1.82 Mb) |
| **Significance** | −log₁₀(P) = 5.36 |
| **Source paper** | [PMC8893256](https://pmc.ncbi.nlm.nih.gov/articles/PMC8893256/) |
| **Reported gene count** | 131 |

**Quadrant breakdown** (all 130 genes in interval): ✓ STRONG **61** · ⚠ NOVEL_LEAD **69** · ✗ LIKELY_NOT **0** · ? CANT_RULE_OUT **0**

**Top 10 candidate genes**

| Rank | Gene | Quadrant | ev | q | bullets | refs | pubs |
|---:|---|---|---:|---:|---:|---:|---:|
| 1 | `Pde4` | ✓ STRONG | 0.62 | 1.00 | 29 | 43 | 608 |
| 2 | `mei-9` | ✓ STRONG | 0.66 | 0.86 | 29 | 5 | 222 |
| 3 | `bi` | ✓ STRONG | 0.62 | 0.98 | 28 | 23 | 445 |
| 4 | `Myc` | ✓ STRONG | 0.61 | 1.00 | 29 | 32 | 842 |
| 5 | `Torsin` | ✓ STRONG | 0.66 | 0.83 | 22 | 8 | 74 |
| 6 | `fzr` | ✓ STRONG | 0.62 | 0.91 | 20 | 17 | 236 |
| 7 | `Pdha1` | ✓ STRONG | 0.65 | 0.81 | 26 | 4 | 109 |
| 8 | `norpA` | ✓ STRONG | 0.61 | 0.91 | 33 | 7 | 705 |
| 9 | `CG3527` | ✓ STRONG | 0.66 | 0.75 | 10 | 8 | 43 |
| 10 | `Xpac` | ✓ STRONG | 0.65 | 0.76 | 12 | 7 | 50 |

**Biological context for top 5 candidates**

**1. `Pde4` (FBgn0000479)** — ✓ STRONG, ev=0.62, q=1.00

Pde4 (dunce) encodes a cAMP-specific phosphodiesterase that serves as the primary regulator of cAMP degradation in the Drosophila nervous system. Loss of Pde4 profoundly impairs learning and memory across olfactory, operant, and courtship conditioning paradigms, disrupts circadian locomotor rhythms and sleep architecture, and causes recessive female sterility with oogenesis def... · ref: Kanellopoulos et al., 2012, J. Neurosci. 32(38): 13111--13124 (PMID 22993428)

**2. `mei-9` (FBgn0002707)** — ✓ STRONG, ev=0.66, q=0.86

Perturbing mei-9 primarily compromises genome maintenance in whole flies, making animals hypersensitive to radiation, DNA-damaging chemicals, oxidative/genotoxic stress, and causing abnormal DNA repair in adult tissues. In the germline, mei-9 loss disrupts meiotic crossover formation and meiotic cell-cycle progression, producing female sterility or semi-sterility, abnormal oocy... · ref: Mishra et al., 2014, Mutat. Res. 766: 35--41 (PMID 24614193)

**3. `bi` (FBgn0000179)** — ✓ STRONG, ev=0.62, q=0.98

bifid (bi), also known as optomotor-blind (omb), encodes a T-box transcription factor activated downstream of Dpp and Wg signaling that controls cell proliferation, survival, and migration across multiple imaginal disc-derived tissues including wings, eyes, and legs. Loss-of-function alleles produce characteristic wing vein defects, ectopic wing sensilla, and reduced eye struct... · ref: Adachi-Yamada et al., 1999, Mol. Cell. Biol. 19(3): 2322--2329 (PMID 10022918)

**4. `Myc` (FBgn0262656)** — ✓ STRONG, ev=0.61, q=1.00

Myc encodes the Drosophila ortholog of the vertebrate c-Myc proto-oncogene, a bHLH transcription factor that drives cell growth, ribosome biogenesis, and cell competition. Loss of Myc reduces body and cell size, slows developmental rate, and causes larval or pupal lethality in strong alleles; hypomorphic alleles produce small but viable adults that are long-lived. · ref: Pierce et al., 2004, Development 131(10): 2317--2327 (PMID 15128666)

**5. `Torsin` (FBgn0025615)** — ✓ STRONG, ev=0.66, q=0.83

Perturbation of Torsin, the sole Drosophila member of the AAA-ATPase torsin family, causes progressive locomotor impairment, semi-lethality, male sterility, shortened lifespan, and reduced body size. Loss of Torsin disrupts nuclear envelope budding of megaRNP granules—preventing synaptic mRNA delivery and causing neuromuscular junction overgrowth—and severely reduces dopamine l... · ref: Nguyen et al., 2016, Neural Plast. 2016: 6762086 (PMID 27313903)

---

### caffeine_E

| | |
|---|---|
| **Study drug** | Caffeine (xenobiotic) |
| **Phenotype** | _Adult female longevity on 1% caffeine_ |
| **Interval (r6)** | `3L:12,328,478–16,368,478` (4.04 Mb) |
| **Significance** | −log₁₀(P) = 4.99 |
| **Source paper** | [PMC8893256](https://pmc.ncbi.nlm.nih.gov/articles/PMC8893256/) |
| **Reported gene count** | 463 |

**Quadrant breakdown** (all 463 genes in interval): ✓ STRONG **221** · ⚠ NOVEL_LEAD **242** · ✗ LIKELY_NOT **0** · ? CANT_RULE_OUT **0**

**Top 10 candidate genes**

| Rank | Gene | Quadrant | ev | q | bullets | refs | pubs |
|---:|---|---|---:|---:|---:|---:|---:|
| 1 | `DCTN1-p150` | ✓ STRONG | 0.64 | 0.98 | 38 | 25 | 309 |
| 2 | `dlp` | ✓ STRONG | 0.62 | 0.99 | 30 | 24 | 359 |
| 3 | `Adk2` | ✓ STRONG | 0.68 | 0.75 | 13 | 5 | 65 |
| 4 | `bmm` | ✓ STRONG | 0.62 | 0.96 | 36 | 20 | 278 |
| 5 | `CrebA` | ✓ STRONG | 0.63 | 0.93 | 25 | 15 | 267 |
| 6 | `Pdi` | ✓ STRONG | 0.64 | 0.85 | 13 | 14 | 147 |
| 7 | `Prosβ2` | ✓ STRONG | 0.63 | 0.88 | 24 | 10 | 152 |
| 8 | `Diap1` | ✓ STRONG | 0.63 | 0.90 | 35 | 6 | 1205 |
| 9 | `D` | ✓ STRONG | 0.61 | 0.96 | 24 | 22 | 312 |
| 10 | `Plp` | ✓ STRONG | 0.63 | 0.86 | 26 | 6 | 225 |

**Biological context for top 5 candidates**

**1. `DCTN1-p150` (FBgn0001108)** — ✓ STRONG, ev=0.64, q=0.98

DCTN1-p150 encodes the p150 subunit of the dynactin complex, which mediates retrograde dynein-based transport along microtubules. Loss-of-function alleles cause progressive locomotor and flight defects, neuromuscular junction degeneration, and reduced adult lifespan. · ref: Borg et al., 2023, Front. Neurosci. 17: 1164251 (PMID 37360176)

**2. `dlp` (FBgn0041604)** — ✓ STRONG, ev=0.62, q=0.99

Perturbing dally-like disrupts multiple morphogen-dependent developmental programs, producing embryonic segment polarity and cuticle defects, wing margin and wing-size abnormalities, eye/neural patterning defects, and substantial developmental lethality. In the nervous system, altered dlp changes larval neuromuscular junction bouton architecture, dendritic arbor anatomy, neurop... · ref: Han et al., 2004, Development 131(3): 601--611 (PMID 14729575)

**3. `Adk2` (FBgn0036337)** — ✓ STRONG, ev=0.68, q=0.75

Adk2 is a Drosophila adenosine kinase whose curated fly phenotypes are sparse but point to viability, fertility, and adult lifespan effects when the locus is perturbed. A dominant Adk2 allele is annotated as long lived, consistent with published evidence that heterozygous mutations in AMP biosynthetic enzymes extend adult fly lifespan through adenine nucleotide and AMPK-depende... · ref: Stenesen et al., 2013, Cell Metab. 17(1): 101--112 (PMID 23312286)

**4. `bmm` (FBgn0036449)** — ✓ STRONG, ev=0.62, q=0.96

brummer (bmm) is the fly ATGL-like triglyceride lipase that controls how stored fat is mobilized across fat body, gonad, neurons, glia, kidney-like nephrocytes and reproductive tissues. Loss or knockdown generally causes excess lipid storage, enlarged or more numerous lipid droplets, altered starvation physiology, reduced lifespan in several contexts, impaired male fertility, d... · ref: Gronke et al., 2005, Cell Metab. 1(5): 323--330 (PMID 16054079)

**5. `CrebA` (FBgn0004396)** — ✓ STRONG, ev=0.63, q=0.93

CrebA encodes a bZIP transcription factor that drives expression of the core secretory machinery (SRP, ER translocators, COPII vesicles) and is essential for salivary gland and epidermis development. Loss-of-function alleles are lethal during embryonic or larval stages with severe cuticle patterning defects, while overexpression in the eye causes rough-eye phenotypes. · ref: Andrew et al., 1997, Development 124(1): 181--193 (PMID 9006079)

---

### caffeine_B

| | |
|---|---|
| **Study drug** | Caffeine (xenobiotic) |
| **Phenotype** | _Adult female longevity on 1% caffeine_ |
| **Interval (r6)** | `2L:3,030,610–4,290,610` (1.26 Mb) |
| **Significance** | −log₁₀(P) = 4.72 |
| **Source paper** | [PMC8893256](https://pmc.ncbi.nlm.nih.gov/articles/PMC8893256/) |
| **Reported gene count** | 137 |

**Quadrant breakdown** (all 137 genes in interval): ✓ STRONG **70** · ⚠ NOVEL_LEAD **67** · ✗ LIKELY_NOT **0** · ? CANT_RULE_OUT **0**

**Top 10 candidate genes**

| Rank | Gene | Quadrant | ev | q | bullets | refs | pubs |
|---:|---|---|---:|---:|---:|---:|---:|
| 1 | `for` | ✓ STRONG | 0.63 | 0.97 | 26 | 25 | 327 |
| 2 | `ft` | ✓ STRONG | 0.62 | 0.98 | 26 | 23 | 517 |
| 3 | `capu` | ✓ STRONG | 0.64 | 0.87 | 25 | 7 | 265 |
| 4 | `tim` | ✓ STRONG | 0.66 | 0.80 | 29 | 6 | 986 |
| 5 | `Thor` | ✓ STRONG | 0.65 | 0.80 | 39 | 12 | 670 |
| 6 | `Mad` | ✓ STRONG | 0.62 | 0.91 | 30 | 7 | 1207 |
| 7 | `Sec5` | ✓ STRONG | 0.63 | 0.86 | 20 | 10 | 152 |
| 8 | `Cog3` | ✓ STRONG | 0.65 | 0.78 | 14 | 8 | 47 |
| 9 | `ed` | ✓ STRONG | 0.62 | 0.86 | 32 | 19 | 251 |
| 10 | `Tdp1` | ✓ STRONG | 0.64 | 0.80 | 20 | 6 | 56 |

**Biological context for top 5 candidates**

**1. `for` (FBgn0000721)** — ✓ STRONG, ev=0.63, q=0.97

The foraging (for) gene encodes a cGMP-dependent protein kinase (PKG) with extensive pleiotropy spanning behavior, development, metabolism, synaptic function, and immunity in Drosophila melanogaster. Two naturally occurring alleles — rover (for[R], higher PKG activity) and sitter (for[s], lower PKG activity) — produce distinct phenotypes in larval food-search locomotion, adult ... · ref: Pereira and Sokolowski, 1993, Proc. Natl. Acad. Sci. U.S.A. 90(11): 5044--5046 (PMID 8506349)

**2. `ft` (FBgn0001075)** — ✓ STRONG, ev=0.62, q=0.98

Fat is a giant atypical cadherin and tumor suppressor that serves as a receptor in the Hippo growth-control pathway and a transmembrane component of the Dachsous-Fat planar cell polarity pathway. Loss-of-function mutations cause massive tissue overgrowth (hyperplasia) in imaginal discs, disrupt planar polarity across wings, eyes, thorax, and embryonic cuticle, and are lethal at... · ref: Bryant et al., 1988, Dev. Biol. 129: 541--554 (PMID 3417051)

**3. `capu` (FBgn0000256)** — ✓ STRONG, ev=0.64, q=0.87

Perturbing cappuccino primarily disrupts female germline cytoskeletal organization, causing defective oocyte polarity, abnormal egg chamber and chorion structures, maternal-effect embryonic patterning defects, and female sterility. Loss of capu removes the mid-oogenesis oocyte actin mesh, unleashing premature cytoplasmic streaming and disturbing microtubule organization and loc... · ref: Yoo et al., 2015, Mol. Biol. Cell 26(10): 1875--1886 (PMID 25788286)

**4. `tim` (FBgn0014396)** — ✓ STRONG, ev=0.66, q=0.80

Perturbing timeless primarily disrupts the fly's circadian system, producing abnormal locomotor, eclosion, sleep, feeding, mating, and photoperiod-dependent behaviors. Loss-of-function alleles also affect reproductive output, seasonal reproductive dormancy, oogenesis-associated size phenotypes, larval stress response, adult heart function, and clock-neuron-associated neuroanato... · ref: Singh et al., 2019, Front. Physiol. 10: 1442 (PMID 31849700)

**5. `Thor` (FBgn0261560)** — ✓ STRONG, ev=0.65, q=0.80

Thor perturbation changes how flies allocate growth, stress resistance, immunity, neuromuscular function, reproduction and aging. Loss-of-function alleles are viable or recessive lethal depending on allele context, but show short lifespan, chemical sensitivity, abnormal stress and immune responses, reduced female germline stem cells, and altered dopaminergic neurons. · ref: Vasudevan et al., 2017, Cell Rep. 21(8): 2039--2047 (PMID 29166596)

---

### caffeine_C

| | |
|---|---|
| **Study drug** | Caffeine (xenobiotic) |
| **Phenotype** | _Adult female longevity on 1% caffeine_ |
| **Interval (r6)** | `2L:10,710,610–12,170,610` (1.46 Mb) |
| **Significance** | −log₁₀(P) = 4.59 |
| **Source paper** | [PMC8893256](https://pmc.ncbi.nlm.nih.gov/articles/PMC8893256/) |
| **Reported gene count** | 187 |

**Quadrant breakdown** (all 187 genes in interval): ✓ STRONG **103** · ⚠ NOVEL_LEAD **84** · ✗ LIKELY_NOT **0** · ? CANT_RULE_OUT **0**

**Top 10 candidate genes**

| Rank | Gene | Quadrant | ev | q | bullets | refs | pubs |
|---:|---|---|---:|---:|---:|---:|---:|
| 1 | `Ca-beta` | ✓ STRONG | 0.65 | 0.89 | 25 | 13 | 100 |
| 2 | `mre11` | ✓ STRONG | 0.64 | 0.86 | 24 | 9 | 124 |
| 3 | `Pex19` | ✓ STRONG | 0.64 | 0.86 | 29 | 9 | 65 |
| 4 | `Hgd` | ✓ STRONG | 0.68 | 0.71 | 11 | 3 | 64 |
| 5 | `Nup154` | ✓ STRONG | 0.63 | 0.86 | 21 | 11 | 114 |
| 6 | `Nup107` | ✓ STRONG | 0.65 | 0.81 | 24 | 4 | 122 |
| 7 | `esc` | ✓ STRONG | 0.63 | 0.84 | 28 | 3 | 386 |
| 8 | `cmet` | ✓ STRONG | 0.63 | 0.85 | 22 | 8 | 121 |
| 9 | `Nup160` | ✓ STRONG | 0.63 | 0.86 | 26 | 9 | 86 |
| 10 | `Nos` | ✓ STRONG | 0.59 | 0.96 | 32 | 21 | 204 |

**Biological context for top 5 candidates**

**1. `Ca-beta` (FBgn0287724)** — ✓ STRONG, ev=0.65, q=0.89

Ca-beta encodes the voltage-gated calcium channel beta subunit in Drosophila. Complete loss of function is lethal at multiple developmental stages (embryonic through larval), reflecting an essential role in calcium-dependent signaling. · ref: Schnorrer et al., 2010, Nature 464(7286): 287--291 (PMID 20220848)

**2. `mre11` (FBgn0020270)** — ✓ STRONG, ev=0.64, q=0.86

Perturbing Drosophila mre11 primarily compromises genome maintenance in dividing tissues, causing telomere fusion, chromosome breakage, abnormal mitotic cycles, radiation sensitivity, developmental death, and maternal-effect embryonic lethality. The strongest organism-level effects are seen during development and reproduction: null or hypomorphic alleles can cause pupal lethali... · ref: Yuan et al., 2018, G3 (Bethesda) 8(6): 2099--2106 (PMID 29695495)

**3. `Pex19` (FBgn0032407)** — ✓ STRONG, ev=0.64, q=0.86

Pex19 encodes a peroxisomal membrane protein import receptor essential for peroxisome biogenesis. Loss-of-function abolishes peroxisomes entirely, triggering a cascade of lipotoxicity: hyperactive Hnf4 signaling drives excessive lipolysis via Lipase 3, flooding cells with free fatty acids that damage mitochondria and cause neurodegeneration. · ref: Bülow et al., 2018, Mol. Biol. Cell 29(4): 396--407 (PMID 29282281)

**4. `Hgd` (FBgn0040211)** — ✓ STRONG, ev=0.68, q=0.71

Hgd encodes homogentisate 1,2-dioxygenase, catalyzing the third step of L-tyrosine catabolism. Complete loss of Hgd via CRIMIC gene trap is larval lethal with abnormal developmental rate, while fat-body-specific knockdown disrupts mitochondrial morphology and reduces larval size. · ref: Martelli et al., 2024, Cell Rep. 43(3): 113861 (PMID 38416643)

**5. `Nup154` (FBgn0021761)** — ✓ STRONG, ev=0.63, q=0.86

Nup154 encodes a core nucleoporin component of the nuclear pore complex essential for viability. Strong loss-of-function alleles are recessive lethal, with larvae showing severely reduced body size and undersized imaginal discs, brains, and testes. · ref: Kiger et al., 1999, Genetics 153(2): 799--812 (PMID 10511559)

---

## Malathion (pesticide, r6; 2 QTLs)

### malathion_A

| | |
|---|---|
| **Study drug** | Malathion (pesticide) |
| **Phenotype** | _Adult survival (~95% baseline mortality)_ |
| **Interval (r6)** | `2R:10,966,645–13,213,848` (2.25 Mb) |
| **Source paper** | [PMC9713458](https://pmc.ncbi.nlm.nih.gov/articles/PMC9713458/) |
| **Reported gene count** | 344 |

**Quadrant breakdown** (all 343 genes in interval): ✓ STRONG **184** · ⚠ NOVEL_LEAD **153** · ✗ LIKELY_NOT **5** · ? CANT_RULE_OUT **1**

**Top 10 candidate genes**

| Rank | Gene | Quadrant | ev | q | bullets | refs | pubs |
|---:|---|---|---:|---:|---:|---:|---:|
| 1 | `Iswi` | ✓ STRONG | 0.57 | 0.98 | 28 | 22 | 387 |
| 2 | `shn` | ✓ STRONG | 0.57 | 0.97 | 25 | 24 | 345 |
| 3 | `Amph` | ✓ STRONG | 0.57 | 0.95 | 28 | 22 | 164 |
| 4 | `Taz` | ✓ STRONG | 0.59 | 0.88 | 28 | 11 | 84 |
| 5 | `Psc` | ✓ STRONG | 0.57 | 0.95 | 18 | 22 | 470 |
| 6 | `Drep1` | ✓ STRONG | 0.60 | 0.82 | 20 | 8 | 70 |
| 7 | `dare` | ✓ STRONG | 0.60 | 0.84 | 25 | 8 | 70 |
| 8 | `Buffy` | ✓ STRONG | 0.62 | 0.76 | 29 | 13 | 139 |
| 9 | `en` | ✓ STRONG | 0.57 | 0.92 | 30 | 8 | 2070 |
| 10 | `Sin3A` | ✓ STRONG | 0.55 | 0.98 | 34 | 26 | 241 |

**Biological context for top 5 candidates**

**1. `Iswi` (FBgn0011604)** — ✓ STRONG, ev=0.57, q=0.98

Iswi encodes the catalytic ATPase of multiple ISWI-family nucleosome remodeling complexes (NURF, CHRAC, ACF, RSF) and is essential for organism viability — null alleles cause recessive lethality and disrupt polytene chromosome morphology, especially on the male X. Pan-neuronal loss of Iswi shrinks adult brain and mushroom bodies and produces a syndrome of decreased sleep, disru... · ref: Onorati et al., 2011, PLoS Genet. 7(5): e1002096 (PMID 21637796)

**2. `shn` (FBgn0003396)** — ✓ STRONG, ev=0.57, q=0.97

Schnurri (shn) encodes a zinc finger transcription factor that mediates Dpp/BMP signaling-dependent transcriptional repression. Loss of shn causes embryonic lethality with severe defects in dorsal closure, epidermal patterning, and midgut development. · ref: Beckwith et al., 2013, PLoS Biol. 11(12): e1001733 (PMID 24339749)

**3. `Amph` (FBgn0027356)** — ✓ STRONG, ev=0.57, q=0.95

Amphiphysin (Amph) encodes a BAR/SH3 domain protein that is the primary regulator of transverse (T)-tubule biogenesis in Drosophila muscle; loss-of-function alleles produce flies that are viable but severely locomotion-impaired at both larval and adult stages and completely flightless owing to disorganized T-tubules in indirect flight muscle. Amph is also required post-synaptic... · ref: Zelhof et al., 2001, Development 128(24): 5005--5015 (PMID 11748137)

**4. `Taz` (FBgn0026619)** — ✓ STRONG, ev=0.59, q=0.88

Perturbing Drosophila Tafazzin produces a Barth syndrome-like mitochondrial myopathy: adults are viable but show weak locomotion, impaired flight and climbing, reduced exercise endurance, and abnormal flight-muscle mitochondria. Loss of Taz also disrupts male reproduction by blocking spermatid individualization and causing male sterility. · ref: Xu et al., 2006, Proc. Natl. Acad. Sci. U.S.A. 103(31): 11584--11588 (PMID 16855048)

**5. `Psc` (FBgn0005624)** — ✓ STRONG, ev=0.57, q=0.95

Posterior sex combs (Psc) encodes a core component of Polycomb repressive complex 1 (PRC1) that compacts chromatin and silences developmental regulators. Loss-of-function causes homeotic transformations — most notably ectopic sex combs on anterior leg segments — and embryonic/lethal lethality in strong alleles, with dominant visible effects on eye pigmentation and wing morpholo... · ref: Schaaf et al., 2013, PLoS Genet. 9(6): e1003560 (PMID 23818863)

---

### malathion_B

| | |
|---|---|
| **Study drug** | Malathion (pesticide) |
| **Phenotype** | _Adult survival (~95% baseline mortality)_ |
| **Interval (r6)** | `3L:5,515,636–6,735,645` (1.22 Mb) |
| **Source paper** | [PMC9713458](https://pmc.ncbi.nlm.nih.gov/articles/PMC9713458/) |
| **Reported gene count** | 145 |

**Quadrant breakdown** (all 144 genes in interval): ✓ STRONG **73** · ⚠ NOVEL_LEAD **69** · ✗ LIKELY_NOT **2** · ? CANT_RULE_OUT **0**

**Top 10 candidate genes**

| Rank | Gene | Quadrant | ev | q | bullets | refs | pubs |
|---:|---|---|---:|---:|---:|---:|---:|
| 1 | `ple` | ✓ STRONG | 0.59 | 0.92 | 31 | 8 | 559 |
| 2 | `Ldh` | ✓ STRONG | 0.59 | 0.91 | 31 | 10 | 267 |
| 3 | `ScsβG` | ✓ STRONG | 0.62 | 0.78 | 13 | 7 | 76 |
| 4 | `spo` | ✓ STRONG | 0.58 | 0.89 | 27 | 13 | 101 |
| 5 | `Alp9` | ✓ STRONG | 0.63 | 0.70 | 9 | 4 | 53 |
| 6 | `PXo` | ✓ STRONG | 0.61 | 0.76 | 14 | 6 | 40 |
| 7 | `sfl` | ✓ STRONG | 0.56 | 0.91 | 33 | 11 | 202 |
| 8 | `Usp47` | ✓ STRONG | 0.58 | 0.86 | 23 | 10 | 108 |
| 9 | `DnaJ-1` | ✓ STRONG | 0.55 | 0.94 | 23 | 24 | 180 |
| 10 | `S6k` | ✓ STRONG | 0.56 | 0.89 | 28 | 41 | 654 |

**Biological context for top 5 candidates**

**1. `ple` (FBgn0005626)** — ✓ STRONG, ev=0.59, q=0.92

Perturbing pale disrupts dopamine and melanin-dependent fly phenotypes, producing embryonic lethality with cuticle and cephalopharyngeal defects, abnormal pigmentation, and broad adult behavioral deficits. Loss or tissue-specific knockdown affects locomotion, flight, sleep, feeding initiation, proboscis extension, courtship, memory, phototaxis, smell perception, and thermotaxis... · ref: Amin et al., 2025, J. Neurosci. 45(11): e1498242024 (PMID 39753299)

**2. `Ldh` (FBgn0001258)** — ✓ STRONG, ev=0.59, q=0.91

Perturbing Drosophila Ldh primarily disrupts organismal energy allocation, with consequences for larval viability, adult lifespan, locomotion, neurodegeneration, memory, immune defense, wound responses, and hypoxia adaptation. Loss of Ldh can be tolerated in some tissues but causes partial larval/pupal lethality when broadly reduced, while neuronal or glial dosage changes produ... · ref: Li et al., 2019, Development 146(17): dev175315 (PMID 31399469)

**3. `ScsβG` (FBgn0029118)** — ✓ STRONG, ev=0.62, q=0.78

ScsβG is a mitochondrial succinate-CoA ligase beta-subunit gene with sparse but coherent fly phenotype evidence centered on viability, adult survival, reproduction, and abdominal pigmentation. Broad RNAi knockdown is lethal, while heart-directed knockdown is viable but short-lived, indicating that reduced ScsβG function can compromise organismal survival depending on tissue con... · ref: François et al., 2023, Nat. Commun. 14(1): 6737 (PMID 37872135)

**4. `spo` (FBgn0003486)** — ✓ STRONG, ev=0.58, q=0.89

spook (spo) encodes a cytochrome P450 enzyme (CYP307A1) essential for ecdysteroid biosynthesis during Drosophila embryogenesis. Loss-of-function mutations abolish embryonic ecdysone production, causing lethality with failures in head involution, dorsal closure, and cuticle secretion. · ref: Chavez et al., 2000, Development 127(19): 4115--4126 (PMID 10976044)

**5. `Alp9` (FBgn0035620)** — ✓ STRONG, ev=0.63, q=0.70

Alp9 is a poorly characterized Drosophila alkaline phosphatase gene with sparse direct phenotype annotation. A piggyBac insertion allele is viable and fertile, whereas pnr-GAL4-driven RNAi causes substantial pupal-stage lethality, suggesting that reduced Alp9 function can compromise development in specific tissues or expression contexts. · ref: Neely et al., 2010, Cell 143(4): 628--638 (PMID 21074052)

---

## Zinc (other, r6; 7 QTLs)

### zinc_A

| | |
|---|---|
| **Study drug** | Zinc (other) |
| **Phenotype** | _Larval survival (~90% baseline mortality)_ |
| **Interval (r6)** | `X:13,796,451–14,093,253` (296.8 kb) |
| **Reported gene count** | 21 |

**Quadrant breakdown** (all 23 genes in interval): ✓ STRONG **11** · ⚠ NOVEL_LEAD **12** · ✗ LIKELY_NOT **0** · ? CANT_RULE_OUT **0**

**Top 10 candidate genes**

| Rank | Gene | Quadrant | ev | q | bullets | refs | pubs |
|---:|---|---|---:|---:|---:|---:|---:|
| 1 | `Clic` | ✓ STRONG | 0.61 | 0.88 | 24 | 14 | 82 |
| 2 | `Nup93-1` | ✓ STRONG | 0.67 | 0.68 | 14 | 1 | 72 |
| 3 | `inaE` | ✓ STRONG | 0.63 | 0.72 | 23 | 7 | 68 |
| 4 | `AMPdeam` | ✓ STRONG | 0.63 | 0.73 | 10 | 5 | 68 |
| 5 | `ben` | ✓ STRONG | 0.59 | 0.79 | 26 | 21 | 171 |
| 6 | `jub` | ✓ STRONG | 0.61 | 0.71 | 22 | 10 | 115 |
| 7 | `mamo` | ✓ STRONG | 0.62 | 0.63 | 27 | 10 | 121 |
| 8 | `Galml2` | ✓ STRONG | 0.63 | 0.58 | 7 | 5 | 32 |
| 9 | `Dmel\Ste12DOR` | ✓ STRONG | 0.61 | 0.57 | 9 | 3 | 30 |
| 10 | `Ste:CG33247` | ✓ STRONG | 0.62 | 0.52 | 8 | 2 | 19 |

**Biological context for top 5 candidates**

**1. `Clic` (FBgn0030529)** — ✓ STRONG, ev=0.61, q=0.88

Clic encodes the sole Drosophila ortholog of the vertebrate Chloride Intracellular Channel (CLIC) family, a metamorphic protein with chloride channel, glutathione peroxidase, and oxidoreductase activities. Loss-of-function perturbation produces pleiotropic organism-level effects: lethality or partial lethality, abnormal adult locomotor behavior, blunted sensitivity to acute eth... · ref: Bhandari et al., 2012, Genes Brain Behav. 11(4): 387--397 (PMID 22239914)

**2. `Nup93-1` (FBgn0027537)** — ✓ STRONG, ev=0.67, q=0.68

Perturbing Nup93-1 primarily compromises development and nuclear organization in tissues that rely on nucleoporin function. Tissue-specific RNAi can cause pupal lethality and visible dorsal thorax defects, while germline knockdown alters oocyte and nurse-cell nuclear structures including karyosome and chromatin organization. · ref: Bierzynska et al., 2022, Pediatr. Nephrol. 37(11): 2643--2656 (PMID 35211795)

**3. `inaE` (FBgn0261244)** — ✓ STRONG, ev=0.63, q=0.72

inaE encodes a diacylglycerol lipase (dDAGL) that produces the endocannabinoid-like signal lipid 2-linoleoyl glycerol (2-LG) and is essential for Drosophila phototransduction. Loss-of-function mutations cause abnormal photoreceptor neurophysiology, rhabdomere degeneration, and visual behavior defects, while also impairing oxidative stress responses. · ref: Leung et al., 2008, Neuron 58(6): 884--896 (PMID 18579079)

**4. `AMPdeam` (FBgn0052626)** — ✓ STRONG, ev=0.63, q=0.73

FlyBase has sparse organism-level annotation for AMPdeam, but available RNAi phenotype records indicate that knockdown is often viable in muscle, neuronal, and tin-expressing tissues, while pnr-driven knockdown with one RNAi line causes substantial lethality with some deaths during pupal development. The gene is most interpretable as a purine/AMP metabolism gene whose developme... · ref: Schnorrer et al., 2010, Nature 464(7286): 287--291 (PMID 20220848)

**5. `ben` (FBgn0000173)** — ✓ STRONG, ev=0.59, q=0.79

Bendless (ben) encodes a K63-linked E2 ubiquitin-conjugating enzyme essential for synaptic connectivity, innate immune signaling, DNA damage tolerance, and mitochondrial quality control in Drosophila. Loss of ben disrupts the giant fiber circuit between the giant fiber neuron and the tergotrochanteral motor neuron, producing uncoordinated locomotion, abnormal jumping, and groom... · ref: Oh et al., 1994, J. Neurosci. 14(5 Pt. 2): 3166--3179 (PMID 8182464)

---

### zinc_B

| | |
|---|---|
| **Study drug** | Zinc (other) |
| **Phenotype** | _Larval survival (~90% baseline mortality)_ |
| **Interval (r6)** | `2L:6,829,342–7,325,061` (495.7 kb) |
| **Reported gene count** | 58 |

**Quadrant breakdown** (all 56 genes in interval): ✓ STRONG **40** · ⚠ NOVEL_LEAD **16** · ✗ LIKELY_NOT **0** · ? CANT_RULE_OUT **0**

**Top 10 candidate genes**

| Rank | Gene | Quadrant | ev | q | bullets | refs | pubs |
|---:|---|---|---:|---:|---:|---:|---:|
| 1 | `Hmgcl` | ✓ STRONG | 0.65 | 0.78 | 16 | 6 | 55 |
| 2 | `Wee1` | ✓ STRONG | 0.62 | 0.90 | 30 | 10 | 157 |
| 3 | `milt` | ✓ STRONG | 0.59 | 0.94 | 30 | 20 | 149 |
| 4 | `wg` | ✓ STRONG | 0.59 | 0.94 | 35 | 11 | 3617 |
| 5 | `MICU1` | ✓ STRONG | 0.63 | 0.79 | 20 | 6 | 51 |
| 6 | `ihog` | ✓ STRONG | 0.63 | 0.80 | 18 | 5 | 118 |
| 7 | `nop5` | ✓ STRONG | 0.66 | 0.69 | 11 | 2 | 83 |
| 8 | `MME1` | ✓ STRONG | 0.67 | 0.65 | 7 | 2 | 56 |
| 9 | `Gas41` | ✓ STRONG | 0.62 | 0.77 | 25 | 3 | 52 |
| 10 | `Nlg2` | ✓ STRONG | 0.60 | 0.84 | 26 | 7 | 85 |

**Biological context for top 5 candidates**

**1. `Hmgcl` (FBgn0031877)** — ✓ STRONG, ev=0.65, q=0.78

Perturbing Hmgcl primarily compromises metabolic resilience: flies show developmental lethality, abnormal developmental rate, increased adult mortality, and impaired adult immune-response phenotypes when Hmgcl is reduced in relevant tissues. Fat-body knockdown is linked to reduced adult locomotor activity and increased mortality, consistent with a role for ketogenesis in sustai... · ref: Krejčová et al., 2025, Brain Behav. Immun. 125: 280--291 (PMID 39824470)

**2. `Wee1` (FBgn0011737)** — ✓ STRONG, ev=0.62, q=0.90

Wee1 is a maternal cell-cycle regulator whose loss disrupts the rapid nuclear divisions of early embryogenesis, producing premature mitotic entry, spindle and centrosome defects, chromosome condensation problems, developmental arrest, and embryonic lethality. In reproductive contexts, loss or germline knockdown causes female sterility or semi-sterility, consistent with a strong... · ref: Stumpff et al., 2004, Curr. Biol. 14(23): 2143--2148 (PMID 15589158)

**3. `milt` (FBgn0262872)** — ✓ STRONG, ev=0.59, q=0.94

Perturbing milton primarily disrupts mitochondrial transport and positioning in neurons, producing larval lethality, abnormal locomotion, altered pain responses, defective neurophysiology, and degeneration-sensitive axons and brain tissue. Tissue-specific knockdown affects visual, olfactory, gustatory, wing-nerve, muscle, bristle, fat-body, and mushroom-body phenotypes, consist... · ref: Stowers et al., 2002, Neuron 36(6): 1063--1077 (PMID 12495622)

**4. `wg` (FBgn0284084)** — ✓ STRONG, ev=0.59, q=0.94

Perturbing wingless profoundly disrupts Drosophila body patterning, wing formation, epithelial growth, neural wiring, adult behavior, metabolism, and tissue survival after damage. Loss-of-function and RNAi phenotypes include embryonic denticle and epidermal pattern defects, absent or reduced wing margins, reduced adult wing size, abnormal neuromuscular and brain anatomy, memory... · ref: Gracia-Latorre et al., 2022, Nat. Commun. 13(1): 4794 (PMID 35995781)

**5. `MICU1` (FBgn0031893)** — ✓ STRONG, ev=0.63, q=0.79

MICU1 encodes the gatekeeper subunit of the mitochondrial calcium uniporter, essential for preventing unregulated Ca2+ influx into mitochondria. Complete loss of MICU1 is developmentally lethal at the larval stage due to uncontrolled mitochondrial Ca2+ overload, while tissue-specific knockdown reveals critical roles in locomotor behavior, memory formation, eye morphogenesis, an... · ref: Tufi et al., 2019, Cell Rep. 27(5): 1541--1550.e5 (PMID 31042479)

---

### zinc_C

| | |
|---|---|
| **Study drug** | Zinc (other) |
| **Phenotype** | _Larval survival (~90% baseline mortality)_ |
| **Interval (r6)** | `2R:15,116,465–15,886,141` (769.7 kb) |
| **Reported gene count** | 88 |

**Quadrant breakdown** (all 86 genes in interval): ✓ STRONG **48** · ⚠ NOVEL_LEAD **38** · ✗ LIKELY_NOT **0** · ? CANT_RULE_OUT **0**

**Top 10 candidate genes**

| Rank | Gene | Quadrant | ev | q | bullets | refs | pubs |
|---:|---|---|---:|---:|---:|---:|---:|
| 1 | `Xpc` | ✓ STRONG | 0.66 | 0.73 | 10 | 4 | 93 |
| 2 | `dup` | ✓ STRONG | 0.61 | 0.87 | 26 | 8 | 168 |
| 3 | `Zasp52` | ✓ STRONG | 0.61 | 0.87 | 28 | 7 | 170 |
| 4 | `Arf6` | ✓ STRONG | 0.61 | 0.87 | 21 | 12 | 134 |
| 5 | `SRPK` | ✓ STRONG | 0.63 | 0.82 | 26 | 5 | 97 |
| 6 | `Stacl` | ✓ STRONG | 0.64 | 0.76 | 21 | 3 | 70 |
| 7 | `fus` | ✓ STRONG | 0.64 | 0.75 | 18 | 3 | 78 |
| 8 | `Hr51` | ✓ STRONG | 0.60 | 0.89 | 31 | 12 | 82 |
| 9 | `Gpo1` | ✓ STRONG | 0.62 | 0.80 | 15 | 7 | 96 |
| 10 | `Poxn` | ✓ STRONG | 0.60 | 0.86 | 29 | 21 | 230 |

**Biological context for top 5 candidates**

**1. `Xpc` (FBgn0004698)** — ✓ STRONG, ev=0.66, q=0.73

Perturbing Drosophila Xpc primarily compromises the fly's ability to survive and repair DNA after genotoxic exposure, especially during larval development. Nonsense alleles are viable and fertile under standard conditions, but homozygous mutants become hypersensitive to MMS, UV light, analgesics, and other chemical mutagens, indicating a stress-conditional phenotype rather than... · ref: Luchkina et al., 1982, Genetika, Moscow 18(4): 625--633 (PMID 7200926)

**2. `dup` (FBgn0000996)** — ✓ STRONG, ev=0.61, q=0.87

double parked (dup), the fly ortholog of human CDT1, is an essential replication-licensing gene whose loss causes failed S phase, mitotic-cycle failure, and embryonic lethality. Perturbing dup disrupts proliferating and endocycling tissues, including embryonic epidermis, larval brain and glia, salivary gland, imaginal discs, retina, follicle cells, and nurse cells. · ref: Whittaker et al., 2000, Genes Dev. 14(14): 1765--1776 (PMID 10898791)

**3. `Zasp52` (FBgn0265991)** — ✓ STRONG, ev=0.61, q=0.87

Perturbing Zasp52 primarily compromises muscle integrity: embryos and larvae can die, adult flight muscles lose normal Z-disc, H-zone, sarcomere and myofibril organization, and adults become flightless or show abnormal locomotion. Zasp52 is also required outside mature muscle, where loss disrupts embryonic supracellular actomyosin cables and epithelial organization during morph... · ref: Katzemich et al., 2013, PLoS Genet. 9(3): e1003342 (PMID 23505387)

**4. `Arf6` (FBgn0013750)** — ✓ STRONG, ev=0.61, q=0.87

Arf6 encodes a small GTPase of the Ras superfamily that regulates vesicular trafficking, cell adhesion, and cytoskeletal remodeling. Loss of Arf6 causes male sterility via cytokinesis failure in spermatocytes, hypersensitivity to ethanol-induced sedation with loss of rapid tolerance, and dominant loss of wing margin bristles through disrupted Wingless signaling. · ref: Peru Y Colón de Portugal et al., 2012, J. Neurosci. 32(49): 17706--17713 (PMID 23223291)

**5. `SRPK` (FBgn0286813)** — ✓ STRONG, ev=0.63, q=0.82

Perturbing Drosophila SRPK primarily compromises reproduction and early development: viable mutant adults can be female-sterile or male-sterile, and maternal loss disrupts oocyte karyosome formation, acentrosomal meiotic spindle assembly, and embryonic nuclear divisions. Strong maternal-effect alleles produce abnormal early embryos with large, erratically distributed nuclei, sp... · ref: Loh et al., 2012, J. Cell Sci. 125(19): 4457--4462 (PMID 22854045)

---

### zinc_D

| | |
|---|---|
| **Study drug** | Zinc (other) |
| **Phenotype** | _Larval survival (~90% baseline mortality)_ |
| **Interval (r6)** | `3L:8,352,067–9,512,583` (1.16 Mb) |
| **Reported gene count** | 166 |

**Quadrant breakdown** (all 166 genes in interval): ✓ STRONG **99** · ⚠ NOVEL_LEAD **67** · ✗ LIKELY_NOT **0** · ? CANT_RULE_OUT **0**

**Top 10 candidate genes**

| Rank | Gene | Quadrant | ev | q | bullets | refs | pubs |
|---:|---|---|---:|---:|---:|---:|---:|
| 1 | `Rdl` | ✓ STRONG | 0.63 | 0.96 | 21 | 22 | 420 |
| 2 | `TrpA1` | ✓ STRONG | 0.60 | 1.00 | 29 | 47 | 739 |
| 3 | `Hsp23` | ✓ STRONG | 0.63 | 0.87 | 26 | 6 | 328 |
| 4 | `Arr2` | ✓ STRONG | 0.62 | 0.86 | 15 | 12 | 206 |
| 5 | `Galk` | ✓ STRONG | 0.63 | 0.82 | 18 | 9 | 66 |
| 6 | `Ugp` | ✓ STRONG | 0.65 | 0.75 | 20 | 2 | 101 |
| 7 | `Fhos` | ✓ STRONG | 0.63 | 0.82 | 24 | 5 | 124 |
| 8 | `PGRP-LC` | ✓ STRONG | 0.65 | 0.76 | 23 | 10 | 490 |
| 9 | `path` | ✓ STRONG | 0.63 | 0.82 | 21 | 6 | 114 |
| 10 | `CG4080` | ✓ STRONG | 0.63 | 0.80 | 20 | 7 | 48 |

**Biological context for top 5 candidates**

**1. `Rdl` (FBgn0004244)** — ✓ STRONG, ev=0.63, q=0.96

Rdl encodes the primary GABA-A receptor subunit in Drosophila, mediating fast inhibitory neurotransmission throughout the nervous system. Complete loss of Rdl is embryonic lethal, while targeted point mutations in the channel pore confer resistance to multiple insecticide classes (cyclodienes, phenylpyrazoles, isoxazolines) at significant fitness costs including sterility, redu... · ref: Stilwell and ffrench-Constant, 1998, J. Neurobiol. 36(4): 468--484 (PMID 9740020)

**2. `TrpA1` (FBgn0035934)** — ✓ STRONG, ev=0.60, q=1.00

TrpA1 encodes a polymodal cation channel activated by warmth and reactive chemicals, functioning as the primary thermosensor and chemosensor for nociception, thermotaxis, and chemosensory avoidance in Drosophila. Loss of TrpA1 eliminates thermal and mechanical nociception in larvae and adults, abolishes innocuous temperature preference behavior, and disrupts circadian activity ... · ref: Luo et al., 2017, Nat. Neurosci. 20(1): 34--41 (PMID 27749829)

**3. `Hsp23` (FBgn0001224)** — ✓ STRONG, ev=0.63, q=0.87

Perturbing Hsp23 mainly changes how flies cope with environmental stress: knockout reduces cold tolerance but can increase heat tolerance, while also altering developmental rate, fecundity, lifespan, and pupal heat hardening. Hsp23 knockdown impairs adult recovery from chill coma, and overexpression can protect pupal hearts from tachypacing-induced contractile and structural re... · ref: Gu et al., 2021, Insect Biochem. Mol. Biol. 139: 103652 (PMID 34562590)

**4. `Arr2` (FBgn0000121)** — ✓ STRONG, ev=0.62, q=0.86

Arrestin 2 (Arr2) is the major visual arrestin in Drosophila, essential for rhodopsin inactivation, photoreceptor maintenance, and auditory perception. Loss-of-function mutations cause abnormal photoreceptor neurophysiology and light-dependent retinal degeneration due to stable Arr2-rhodopsin complexes. · ref: Acharya et al., 2003, Science 299(5613): 1740--1743 (PMID 12637747)

**5. `Galk` (FBgn0263199)** — ✓ STRONG, ev=0.63, q=0.82

Drosophila Galk has sparse direct single-gene phenotype annotation: a reported mutant allele is viable and fertile, and several tissue-directed RNAi combinations are annotated as viable. Its strongest organism-level evidence comes from disease-model modifier studies, where reducing or disrupting Galk modifies galactosemia and calcineurin-induced cardiomyopathy phenotypes. · ref: Schnorrer et al., 2010, Nature 464(7286): 287--291 (PMID 20220848)

---

### zinc_E

| | |
|---|---|
| **Study drug** | Zinc (other) |
| **Phenotype** | _Larval survival (~90% baseline mortality)_ |
| **Interval (r6)** | `3R:18,717,419–18,987,824` (270.4 kb) |
| **Reported gene count** | 30 |

**Quadrant breakdown** (all 30 genes in interval): ✓ STRONG **15** · ⚠ NOVEL_LEAD **15** · ✗ LIKELY_NOT **0** · ? CANT_RULE_OUT **0**

**Top 10 candidate genes**

| Rank | Gene | Quadrant | ev | q | bullets | refs | pubs |
|---:|---|---|---:|---:|---:|---:|---:|
| 1 | `EndoA` | ✓ STRONG | 0.63 | 0.90 | 28 | 12 | 134 |
| 2 | `ChAT` | ✓ STRONG | 0.62 | 0.93 | 17 | 19 | 401 |
| 3 | `Mpc1` | ✓ STRONG | 0.63 | 0.87 | 25 | 12 | 67 |
| 4 | `VAChT` | ✓ STRONG | 0.62 | 0.86 | 27 | 8 | 121 |
| 5 | `Mekk1` | ✓ STRONG | 0.63 | 0.73 | 28 | 9 | 147 |
| 6 | `Octalpha2R` | ✓ STRONG | 0.62 | 0.76 | 15 | 4 | 77 |
| 7 | `Epg5` | ✓ STRONG | 0.63 | 0.72 | 17 | 3 | 35 |
| 8 | `Sgsh` | ✓ STRONG | 0.62 | 0.74 | 15 | 4 | 53 |
| 9 | `Xrp1` | ✓ STRONG | 0.63 | 0.66 | 31 | 13 | 132 |
| 10 | `gwl` | ✓ STRONG | 0.63 | 0.66 | 26 | 4 | 90 |

**Biological context for top 5 candidates**

**1. `EndoA` (FBgn0038659)** — ✓ STRONG, ev=0.63, q=0.90

Endophilin A is essential for fly nervous-system function: loss-of-function animals are larval paralytics with severe developmental lethality, slowed movement, abnormal synaptic physiology, and malformed neuromuscular junctions. In adult neural tissues, EndoA perturbation disrupts photoreceptor and lamina function, causes progressive dopaminergic neuron loss, uncoordination, sh... · ref: Guichet et al., 2002, EMBO J. 21(7): 1661--1672 (PMID 11927550)

**2. `ChAT` (FBgn0000303)** — ✓ STRONG, ev=0.62, q=0.93

Choline acetyltransferase (ChAT) catalyzes the biosynthesis of the neurotransmitter acetylcholine and is the defining marker of cholinergic neurons. Loss-of-function alleles are recessive lethal, with strong alleles causing embryonic death from failed neuromuscular transmission and temperature-sensitive alleles producing adult paralysis. · ref: Kitamoto and Salvaterra, 1995, J. Neurosci. 15(5 Pt. 1): 3509--3518 (PMID 7751926)

**3. `Mpc1` (FBgn0038662)** — ✓ STRONG, ev=0.63, q=0.87

Perturbing Drosophila Mpc1 disrupts mitochondrial pyruvate use and produces broad organism-level consequences in survival, memory, locomotion, intestinal growth control, glucose homeostasis, and injury responses. Loss of Mpc1 can be lethal in transheterozygous mutants, while tissue-specific knockdown impairs adult medium- and long-term memory, reduces climbing ability, alters m... · ref: Bricker et al., 2012, Science 337(6090): 96--100 (PMID 22628558)

**4. `VAChT` (FBgn0270928)** — ✓ STRONG, ev=0.62, q=0.86

Perturbing VAChT primarily disrupts cholinergic neurotransmission, producing severe developmental lethality when function is lost and broad adult nervous-system phenotypes when dosage or activity is altered. Loss-of-function or hypomorphic alleles impair larval movement, neurophysiology, flight-related muscle function, and sleep, while cholinergic overexpression causes shortene... · ref: Vernon et al., 2019, eNeuro 6(1): ENEURO.0477--ENEURO.18.2019 (PMID 30847389)

**5. `Mekk1` (FBgn0024329)** — ✓ STRONG, ev=0.63, q=0.73

Mekk1 is a stress-response MAP kinase kinase kinase whose loss makes flies poorly able to survive environmental insults, especially osmotic shock, heat stress, oxidative stress, and some chemical challenges. Perturbing Mekk1 also affects immune and gut homeostasis through Duox regulation, alters larval and ovarian tissue phenotypes, and modifies wing morphology when the pathway... · ref: Inoue et al., 2001, EMBO J. 20(19): 5421--5430 (PMID 11574474)

---

### zinc_F

| | |
|---|---|
| **Study drug** | Zinc (other) |
| **Phenotype** | _Larval survival (~90% baseline mortality)_ |
| **Interval (r6)** | `3R:23,458,263–24,716,284` (1.26 Mb) |
| **Reported gene count** | 190 |

**Quadrant breakdown** (all 190 genes in interval): ✓ STRONG **120** · ⚠ NOVEL_LEAD **70** · ✗ LIKELY_NOT **0** · ? CANT_RULE_OUT **0**

**Top 10 candidate genes**

| Rank | Gene | Quadrant | ev | q | bullets | refs | pubs |
|---:|---|---|---:|---:|---:|---:|---:|
| 1 | `Hmgcr` | ✓ STRONG | 0.64 | 0.89 | 32 | 8 | 177 |
| 2 | `Gdh` | ✓ STRONG | 0.64 | 0.88 | 20 | 12 | 156 |
| 3 | `nAChRα1` | ✓ STRONG | 0.62 | 0.92 | 25 | 15 | 204 |
| 4 | `mbc` | ✓ STRONG | 0.62 | 0.94 | 21 | 21 | 252 |
| 5 | `slo` | ✓ STRONG | 0.60 | 0.99 | 36 | 30 | 348 |
| 6 | `spas` | ✓ STRONG | 0.61 | 0.94 | 25 | 22 | 147 |
| 7 | `Rpt2` | ✓ STRONG | 0.64 | 0.85 | 23 | 8 | 124 |
| 8 | `Dis3` | ✓ STRONG | 0.63 | 0.85 | 19 | 11 | 87 |
| 9 | `Syx1A` | ✓ STRONG | 0.60 | 0.92 | 34 | 9 | 349 |
| 10 | `jar` | ✓ STRONG | 0.61 | 0.89 | 28 | 8 | 238 |

**Biological context for top 5 candidates**

**1. `Hmgcr` (FBgn0263782)** — ✓ STRONG, ev=0.64, q=0.89

Hmgcr perturbation causes broad organismal defects in Drosophila, with strongest effects on embryonic viability, heart tube formation, larval molting, body size, locomotion, feeding, muscle performance, and germ cell migration. Loss of Hmgcr disrupts mevalonate/isoprenoid-dependent developmental signals, producing embryonic lethality, abnormal cuticle and segment polarity pheno... · ref: Jones et al., 2010, Gen. Comp. Endocrinol. 165(2): 244--254 (PMID 19595690)

**2. `Gdh` (FBgn0001098)** — ✓ STRONG, ev=0.64, q=0.88

Perturbation of Drosophila Gdh is linked to adult starvation-stress defects, shortened lifespan, and abnormal larval locomotor behavior, consistent with a role for glutamate metabolism in organismal energy balance and neuromuscular function. Available FlyBase phenotypes indicate that some Gdh alleles or RNAi conditions remain viable and fertile, so the strongest organism-level ... · ref: Maguire et al., 2015, J. Biol. Chem. 290(33): 20407--20416 (PMID 26124278)

**3. `nAChRα1` (FBgn0000036)** — ✓ STRONG, ev=0.62, q=0.92

nAChRα1 (Dα1) encodes an alpha subunit of the nicotinic acetylcholine receptor, a pentameric ligand-gated cation channel mediating fast cholinergic synaptic transmission throughout the Drosophila CNS. Null knockout flies are viable but display a striking behavioral syndrome: locomotor hyperactivity, decreased sleep, impaired courtship and copulation in both sexes, and memory de... · ref: Somers et al., 2017, Genetics 205(1): 263--271 (PMID 28049707)

**4. `mbc` (FBgn0015513)** — ✓ STRONG, ev=0.62, q=0.94

Perturbing myoblast city (mbc) blocks myoblast fusion in the Drosophila embryo, producing larvae with missing or severely reduced somatic, visceral, and pharyngeal musculature. Null alleles cause complete embryonic lethality, while partial loss-of-function disrupts dorsal closure, midgut constriction, Malpighian tubule morphogenesis, and CNS axon tract organization. · ref: Rushton et al., 1995, Development 121(7): 1979--1988 (PMID 7635046)

**5. `slo` (FBgn0003429)** — ✓ STRONG, ev=0.60, q=0.99

slowpoke encodes the fly BK calcium-activated potassium channel alpha subunit, and perturbing it broadly disrupts electrical excitability in neurons, muscles, heart, and circadian output circuits. Loss-of-function mutants show abnormal flight, locomotion, courtship, circadian rhythms, chemosensation, neuromuscular-junction structure, mitochondrial integrity, oxidative-stress re... · ref: Atkinson et al., 2000, J. Neurosci. 20(8): 2988--2993 (PMID 10751451)

---

### zinc_G

| | |
|---|---|
| **Study drug** | Zinc (other) |
| **Phenotype** | _Larval survival (~90% baseline mortality)_ |
| **Interval (r6)** | `3R:30,368,845–31,020,051` (651.2 kb) |
| **Reported gene count** | 78 |

**Quadrant breakdown** (all 78 genes in interval): ✓ STRONG **54** · ⚠ NOVEL_LEAD **24** · ✗ LIKELY_NOT **0** · ? CANT_RULE_OUT **0**

**Top 10 candidate genes**

| Rank | Gene | Quadrant | ev | q | bullets | refs | pubs |
|---:|---|---|---:|---:|---:|---:|---:|
| 1 | `dj-1beta` | ✓ STRONG | 0.60 | 0.93 | 27 | 21 | 122 |
| 2 | `cindr` | ✓ STRONG | 0.61 | 0.92 | 30 | 14 | 134 |
| 3 | `zfh1` | ✓ STRONG | 0.59 | 0.93 | 35 | 10 | 437 |
| 4 | `Fer1HCH` | ✓ STRONG | 0.61 | 0.88 | 31 | 7 | 207 |
| 5 | `5-HT7` | ✓ STRONG | 0.59 | 0.92 | 25 | 17 | 143 |
| 6 | `Jon99Fi` | ✓ STRONG | 0.65 | 0.71 | 8 | 5 | 58 |
| 7 | `Fer2LCH` | ✓ STRONG | 0.63 | 0.78 | 20 | 12 | 157 |
| 8 | `Aralar` | ✓ STRONG | 0.64 | 0.75 | 11 | 5 | 84 |
| 9 | `CG9698` | ✓ STRONG | 0.65 | 0.72 | 10 | 6 | 34 |
| 10 | `Rpt6R` | ✓ STRONG | 0.61 | 0.83 | 19 | 11 | 59 |

**Biological context for top 5 candidates**

**1. `dj-1beta` (FBgn0039802)** — ✓ STRONG, ev=0.60, q=0.93

dj-1beta is the Drosophila ortholog of human PARK7 (DJ-1), a gene mutated in autosomal recessive early-onset Parkinson's disease 7. Loss-of-function causes progressive locomotor deficits, dopaminergic neuron degeneration, and hypersensitivity to oxidative stress, paraquat, rotenone, radiation, and anoxia. · ref: Lavara-Culebras and Paricio, 2007, Gene 400(1-2): 158--165 (PMID 17651920)

**2. `cindr` (FBgn0027598)** — ✓ STRONG, ev=0.61, q=0.92

Perturbing cindr disrupts epithelial junction remodeling, eye patterning, nephrocyte filtration structures, germline cytokinesis, and larval synaptic function. Loss of cindr can cause embryonic or first-instar lethality, partial lethality, shortened adult survival, rough or mis-patterned eyes, abnormal bristle number, defective intercellular bridges, and impaired neuromuscular ... · ref: Johnson et al., 2008, J. Cell Biol. 180(6): 1191--1204 (PMID 18362180)

**3. `zfh1` (FBgn0004606)** — ✓ STRONG, ev=0.59, q=0.93

Perturbing zfh1 causes broad developmental failure, with recessive loss-of-function alleles producing embryonic lethality and defects in mesodermal derivatives including somatic muscle, dorsal vessel, pericardial cells, tracheal dorsal trunk, gonad/fat body primordia, hemocytes, and larval nerves. Tissue-specific knockdown or misexpression affects adult traits including wing mo... · ref: Xu et al., 2024, eLife 12: RP90133 (PMID 38180023)

**4. `Fer1HCH` (FBgn0015222)** — ✓ STRONG, ev=0.61, q=0.88

Fer1HCH is an essential ferritin heavy-chain gene whose disruption causes early lethality, slow larval development, reduced body size, impaired cell division, and tissue damage from failed iron handling. In the nervous system, ferritin supplied by glia supports neuroblast self-renewal, brain growth, axonal integrity, circadian output, and adult locomotor performance. · ref: Mumbauer et al., 2019, PLoS Genet. 15(9): e1008396 (PMID 31568497)

**5. `5-HT7` (FBgn0004573)** — ✓ STRONG, ev=0.59, q=0.92

Perturbing 5-HT7 primarily affects serotonin-dependent neural control of behavior, including courtship, female receptivity, sleep, feeding microstructure, olfactory learning, sensory plasticity, swallowing, and restrained immobility. FlyBase curated phenotypes also link altered 5-HT7 activity to shortened lifespan and abnormal starvation stress response when manipulated in insu... · ref: Becnel et al., 2011, PLoS ONE 6(6): e20800 (PMID 21674056)

---

## Gemcitabine (chemo, r5; 2 QTLs)

### gemcitabine_GB

| | |
|---|---|
| **Study drug** | Gemcitabine (chemo) |
| **Phenotype** | _Female fertility reduction (ovary atrophy)_ |
| **Interval (r6)** | `3L:3,224,838–3,616,682` (391.8 kb) |
| **Interval (r5, native)** | `3L:3,230,000–3,620,000` |
| **Significance** | −log₁₀(P) = 4.97 |
| **Heritability** | 18% |
| **Source paper** | [PMC4174942](https://pmc.ncbi.nlm.nih.gov/articles/PMC4174942/) |

**Quadrant breakdown** (all 43 genes in interval): ✓ STRONG **21** · ⚠ NOVEL_LEAD **22** · ✗ LIKELY_NOT **0** · ? CANT_RULE_OUT **0**

**Top 10 candidate genes**

| Rank | Gene | Quadrant | ev | q | bullets | refs | pubs |
|---:|---|---|---:|---:|---:|---:|---:|
| 1 | `armi` | ✓ STRONG | 0.65 | 0.82 | 21 | 4 | 232 |
| 2 | `sty` | ✓ STRONG | 0.59 | 0.96 | 29 | 20 | 232 |
| 3 | `Gtpx` | ✓ STRONG | 0.63 | 0.73 | 11 | 3 | 134 |
| 4 | `ZnT63C` | ✓ STRONG | 0.60 | 0.83 | 23 | 6 | 104 |
| 5 | `Ostm1` | ✓ STRONG | 0.63 | 0.71 | 9 | 6 | 32 |
| 6 | `kst` | ✓ STRONG | 0.57 | 0.93 | 22 | 19 | 256 |
| 7 | `CycJ` | ✓ STRONG | 0.65 | 0.66 | 20 | 7 | 67 |
| 8 | `Strip` | ✓ STRONG | 0.62 | 0.70 | 31 | 8 | 66 |
| 9 | `CG17746` | ✓ STRONG | 0.63 | 0.64 | 9 | 7 | 63 |
| 10 | `Eip63E` | ✓ STRONG | 0.61 | 0.68 | 29 | 4 | 139 |

**Biological context for top 5 candidates**

**1. `armi` (FBgn0041164)** — ✓ STRONG, ev=0.65, q=0.82

Perturbing armitage primarily damages the germline: females become sterile or semi-sterile, egg chambers and dorsal appendages are abnormal, and maternal loss can cause embryonic death. The gene is repeatedly linked to piRNA pathway failure, transposon derepression, defective germ cell development, and compromised oogenesis, making its organism-level signature a fertility and e... · ref: Atikukke et al., 2014, Mech. Dev. 133: 64--76 (PMID 24946235)

**2. `sty` (FBgn0014388)** — ✓ STRONG, ev=0.59, q=0.96

Sprouty (sty) encodes a conserved negative feedback inhibitor of receptor tyrosine kinase (RTK) signaling, including EGFR, FGFR, and Ras/MAPK pathways. Loss-of-function mutations cause dramatic tracheal branching defects due to unchecked FGFR signaling, leading to excessive terminal tracheal cell outgrowth and pupal lethality. · ref: Hacohen et al., 1998, Cell 92(2): 253--263 (PMID 9458049)

**3. `Gtpx` (FBgn0035438)** — ✓ STRONG, ev=0.63, q=0.73

Perturbing Drosophila Gtpx primarily affects the fly's ability to handle oxidative stress, with both mutant and overexpression alleles annotated for abnormal oxidative-stress responses. Increased Gtpx activity can protect flies in oxidative-stress-sensitive disease contexts, ameliorating Pink1/Parkinsonian and human tau neurodegeneration models. · ref: Missirlis et al., 2003, Biol. Chem. 384(3): 463--472 (PMID 12715897)

**4. `ZnT63C` (FBgn0035432)** — ✓ STRONG, ev=0.60, q=0.83

ZnT63C/dZnT1 is an essential zinc exporter whose perturbation primarily disrupts organismal zinc acquisition and homeostasis. Loss of ZnT63C causes developmental arrest or lethality, especially under zinc-limiting conditions and when intestinal function is compromised, with zinc accumulating in gut regions rather than being properly exported to circulation. · ref: Wang et al., 2020, Biochem. Biophys. Res. Commun. 533(4): 1004--1011 (PMID 33012507)

**5. `Ostm1` (FBgn0035440)** — ✓ STRONG, ev=0.63, q=0.71

Perturbing Drosophila Ostm1 produces adult immune defects and increased mortality, with the clearest fly phenotype being failure of extracellular dsRNA-directed RNAi and associated antiviral immunity. The available mutant alleles are coding-region deletions, and curated FlyBase phenotypes link the Ostm1[24]/Ostm1[74] genotype to abnormal adult immune response. · ref: Tanaka et al., 2024, Nat. Commun. 15(1): 6993 (PMID 39143098)

---

### gemcitabine_GA

| | |
|---|---|
| **Study drug** | Gemcitabine (chemo) |
| **Phenotype** | _Female fertility reduction (ovary atrophy)_ |
| **Interval (r6)** | `2R:10,673,345–12,899,385` (2.23 Mb) |
| **Interval (r5, native)** | `2R:6,600,000–8,790,000` |
| **Significance** | −log₁₀(P) = 2.13 |
| **Heritability** | 9% |
| **Source paper** | [PMC4174942](https://pmc.ncbi.nlm.nih.gov/articles/PMC4174942/) |

**Quadrant breakdown** (all 338 genes in interval): ✓ STRONG **191** · ⚠ NOVEL_LEAD **145** · ✗ LIKELY_NOT **2** · ? CANT_RULE_OUT **0**

**Top 10 candidate genes**

| Rank | Gene | Quadrant | ev | q | bullets | refs | pubs |
|---:|---|---|---:|---:|---:|---:|---:|
| 1 | `Mos` | ✓ STRONG | 0.69 | 0.71 | 13 | 3 | 47 |
| 2 | `Taz` | ✓ STRONG | 0.63 | 0.88 | 28 | 11 | 84 |
| 3 | `alphaTry` | ✓ STRONG | 0.67 | 0.74 | 12 | 4 | 71 |
| 4 | `Iswi` | ✓ STRONG | 0.59 | 0.98 | 28 | 22 | 387 |
| 5 | `en` | ✓ STRONG | 0.61 | 0.92 | 30 | 8 | 2070 |
| 6 | `Amph` | ✓ STRONG | 0.60 | 0.95 | 28 | 22 | 164 |
| 7 | `Drep1` | ✓ STRONG | 0.63 | 0.82 | 20 | 8 | 70 |
| 8 | `Drip` | ✓ STRONG | 0.63 | 0.81 | 20 | 6 | 100 |
| 9 | `shn` | ✓ STRONG | 0.59 | 0.97 | 25 | 24 | 345 |
| 10 | `dare` | ✓ STRONG | 0.62 | 0.84 | 25 | 8 | 70 |

**Biological context for top 5 candidates**

**1. `Mos` (FBgn0033773)** — ✓ STRONG, ev=0.69, q=0.71

Mos encodes a serine/threonine kinase that activates the MAPK cascade during Drosophila oogenesis. Loss-of-function mutations reduce female fertility and trigger oocyte apoptosis, but — unlike its vertebrate ortholog — Drosophila Mos is not essential for meiotic completion, suggesting redundant meiotic regulatory pathways exist in the fly. · ref: Ivanovska et al., 2004, Curr. Biol. 14(1): 75--80 (PMID 14711418)

**2. `Taz` (FBgn0026619)** — ✓ STRONG, ev=0.63, q=0.88

Perturbing Drosophila Tafazzin produces a Barth syndrome-like mitochondrial myopathy: adults are viable but show weak locomotion, impaired flight and climbing, reduced exercise endurance, and abnormal flight-muscle mitochondria. Loss of Taz also disrupts male reproduction by blocking spermatid individualization and causing male sterility. · ref: Xu et al., 2006, Proc. Natl. Acad. Sci. U.S.A. 103(31): 11584--11588 (PMID 16855048)

**3. `alphaTry` (FBgn0003863)** — ✓ STRONG, ev=0.67, q=0.74

alphaTry is a sparsely characterized Drosophila trypsin-like serine protease gene with the clearest fly phenotype in oogenesis: RNAi perturbation is curated to affect egg chambers and nurse cells. The available oogenesis study places alphaTry among candidates whose perturbation changes nurse-cell death or clearance programs, linking the gene to reproductive tissue integrity rat... · ref: Bandyadka et al., 2025, PLoS Genet. 21(1): e1011220 (PMID 39752622)

**4. `Iswi` (FBgn0011604)** — ✓ STRONG, ev=0.59, q=0.98

Iswi encodes the catalytic ATPase of multiple ISWI-family nucleosome remodeling complexes (NURF, CHRAC, ACF, RSF) and is essential for organism viability — null alleles cause recessive lethality and disrupt polytene chromosome morphology, especially on the male X. Pan-neuronal loss of Iswi shrinks adult brain and mushroom bodies and produces a syndrome of decreased sleep, disru... · ref: Onorati et al., 2011, PLoS Genet. 7(5): e1002096 (PMID 21637796)

**5. `en` (FBgn0000577)** — ✓ STRONG, ev=0.61, q=0.92

Perturbing engrailed disrupts anterior-posterior compartment identity, causing embryonic lethality, abnormal segmental cuticle patterning, and adult appendage defects in wings, legs, antennae, genitalia, and sensory organs. In imaginal and niche tissues, altered en activity changes wing veins and crossveins, air sac primordium size, ovarian germline stem cell numbers, spermathe... · ref: Ali-Murthy et al., 2013, PLoS Genet. 9(4): e1003428 (PMID 23593026)

---

## Methotrexate (chemo, r5; 4 QTLs)

### methotrexate_C

| | |
|---|---|
| **Study drug** | Methotrexate (chemo) |
| **Phenotype** | _Female fertility reduction (ovary atrophy)_ |
| **Interval (r6)** | `3L:2,786,207–3,842,326` (1.06 Mb) |
| **Interval (r5, native)** | `3L:2,790,000–3,840,000` |
| **Significance** | −log₁₀(P) = 3.5 |
| **Heritability** | 19% |
| **Source paper** | [PMC3737169](https://pmc.ncbi.nlm.nih.gov/articles/PMC3737169/) |

**Quadrant breakdown** (all 120 genes in interval): ✓ STRONG **59** · ⚠ NOVEL_LEAD **60** · ✗ LIKELY_NOT **1** · ? CANT_RULE_OUT **0**

**Top 10 candidate genes**

| Rank | Gene | Quadrant | ev | q | bullets | refs | pubs |
|---:|---|---|---:|---:|---:|---:|---:|
| 1 | `armi` | ✓ STRONG | 0.65 | 0.82 | 21 | 4 | 232 |
| 2 | `sty` | ✓ STRONG | 0.59 | 0.96 | 29 | 20 | 232 |
| 3 | `enc` | ✓ STRONG | 0.67 | 0.64 | 21 | 4 | 96 |
| 4 | `Tet` | ✓ STRONG | 0.60 | 0.85 | 27 | 7 | 105 |
| 5 | `CG32281` | ✓ STRONG | 0.64 | 0.71 | 8 | 6 | 35 |
| 6 | `rasp` | ✓ STRONG | 0.60 | 0.83 | 24 | 7 | 84 |
| 7 | `Hsp83` | ✓ STRONG | 0.62 | 0.78 | 31 | 10 | 750 |
| 8 | `Gtpx` | ✓ STRONG | 0.63 | 0.73 | 11 | 3 | 134 |
| 9 | `ZnT63C` | ✓ STRONG | 0.60 | 0.83 | 23 | 6 | 104 |
| 10 | `aly` | ✓ STRONG | 0.64 | 0.69 | 18 | 8 | 142 |

**Biological context for top 5 candidates**

**1. `armi` (FBgn0041164)** — ✓ STRONG, ev=0.65, q=0.82

Perturbing armitage primarily damages the germline: females become sterile or semi-sterile, egg chambers and dorsal appendages are abnormal, and maternal loss can cause embryonic death. The gene is repeatedly linked to piRNA pathway failure, transposon derepression, defective germ cell development, and compromised oogenesis, making its organism-level signature a fertility and e... · ref: Atikukke et al., 2014, Mech. Dev. 133: 64--76 (PMID 24946235)

**2. `sty` (FBgn0014388)** — ✓ STRONG, ev=0.59, q=0.96

Sprouty (sty) encodes a conserved negative feedback inhibitor of receptor tyrosine kinase (RTK) signaling, including EGFR, FGFR, and Ras/MAPK pathways. Loss-of-function mutations cause dramatic tracheal branching defects due to unchecked FGFR signaling, leading to excessive terminal tracheal cell outgrowth and pupal lethality. · ref: Hacohen et al., 1998, Cell 92(2): 253--263 (PMID 9458049)

**3. `enc` (FBgn0004875)** — ✓ STRONG, ev=0.67, q=0.64

Perturbing encore primarily disrupts oogenesis: germline cysts fail to stop after the normal four mitotic divisions, egg chambers form with extra nurse cells, and oocyte differentiation is abnormal. Maternal encore function is also required for egg and embryo axis patterning, with mutant females producing ventralized eggs, abnormal dorsal appendages, and embryos with cuticle an... · ref: Hawkins et al., 1996, Development 122(1): 281--290 (PMID 8565840)

**4. `Tet` (FBgn0263392)** — ✓ STRONG, ev=0.60, q=0.85

Perturbing Drosophila Tet primarily disrupts nervous-system development and function: larvae show abnormal locomotion, axon-patterning defects, altered glial organization, and impaired brain development, while adults can become immobile, short-lived, and behaviorally abnormal. Strong loss-of-function alleles are lethal before or during pupal development, and muscle-specific dep... · ref: Frey et al., 2022, eNeuro 9(2): ENEURO.0418--ENEURO.21.2022 (PMID 35396259)

**5. `CG32281` (FBgn0052281)** — ✓ STRONG, ev=0.64, q=0.71

CG32281 is a sparsely characterized, conserved fly ortholog of human TRMT5, with FlyBase phenotypes mainly from RNAi screens rather than detailed allele studies. Perturbation has been curated as viable in several tissue-specific RNAi contexts, suggesting no broad lethality was detected under those screened conditions. · ref: Breznak et al., 2023, Sci. Adv. 9(25): eade5492 (PMID 37343092)

---

### methotrexate_A

| | |
|---|---|
| **Study drug** | Methotrexate (chemo) |
| **Phenotype** | _Female fertility reduction (ovary atrophy)_ |
| **Interval (r6)** | `X:13,359,248–14,749,376` (1.39 Mb) |
| **Interval (r5, native)** | `X:13,250,000–14,600,000` |
| **Significance** | −log₁₀(P) = 3.19 |
| **Heritability** | 15% |
| **Source paper** | [PMC3737169](https://pmc.ncbi.nlm.nih.gov/articles/PMC3737169/) |

**Quadrant breakdown** (all 120 genes in interval): ✓ STRONG **59** · ⚠ NOVEL_LEAD **61** · ✗ LIKELY_NOT **0** · ? CANT_RULE_OUT **0**

**Top 10 candidate genes**

| Rank | Gene | Quadrant | ev | q | bullets | refs | pubs |
|---:|---|---|---:|---:|---:|---:|---:|
| 1 | `Yp3` | ✓ STRONG | 0.65 | 0.85 | 20 | 7 | 237 |
| 2 | `g` | ✓ STRONG | 0.61 | 0.89 | 23 | 10 | 225 |
| 3 | `yl` | ✓ STRONG | 0.64 | 0.74 | 20 | 9 | 108 |
| 4 | `na` | ✓ STRONG | 0.58 | 0.93 | 30 | 17 | 122 |
| 5 | `rdgB` | ✓ STRONG | 0.59 | 0.87 | 24 | 8 | 221 |
| 6 | `Nadsyn` | ✓ STRONG | 0.62 | 0.77 | 12 | 8 | 54 |
| 7 | `mus101` | ✓ STRONG | 0.63 | 0.75 | 30 | 13 | 113 |
| 8 | `Bcat` | ✓ STRONG | 0.59 | 0.89 | 30 | 12 | 82 |
| 9 | `NetA` | ✓ STRONG | 0.59 | 0.89 | 28 | 8 | 219 |
| 10 | `DNAlig4` | ✓ STRONG | 0.59 | 0.88 | 20 | 15 | 103 |

**Biological context for top 5 candidates**

**1. `Yp3` (FBgn0004047)** — ✓ STRONG, ev=0.65, q=0.85

Yp3 encodes one of the three major yolk proteins whose dosage contributes quantitatively to egg production and fertility, rather than supplying a unique indispensable embryonic function. Perturbation or depletion of yolk proteins affects oocyte organization, including oskar mRNA localization and germ plasm anchoring, while FlyBase RNAi phenotypes also link Yp3 to adult immune r... · ref: Bownes et al., 1991, Mol. Gen. Genet. 228: 324--327 (PMID 1909423)

**2. `g` (FBgn0001087)** — ✓ STRONG, ev=0.61, q=0.89

The garnet gene encodes the delta subunit of the AP-3 adaptor complex, which sorts cargo into vesicles destined for lysosome-related organelles including pigment granules. Loss-of-function mutations cause striking reductions in eye and body pigmentation across nearly all characterized alleles, with pigment granules being fewer and abnormally sized in retinal and surrounding cel... · ref: Lloyd et al., 1999, Genome 42(6): 1183--1193 (PMID 10659786)

**3. `yl` (FBgn0004649)** — ✓ STRONG, ev=0.64, q=0.74

Yolkless encodes the Drosophila vitellogenin receptor, an LDL receptor superfamily member essential for clathrin-mediated yolk protein endocytosis during oogenesis. Loss-of-function mutations abolish coated pit formation in oocytes, blocking vitellogenin uptake and causing recessive female sterility across all characterized alleles. · ref: DiMario and Mahowald, 1987, J. Cell Biol. 105: 199--206 (PMID 2886508)

**4. `na` (FBgn0002917)** — ✓ STRONG, ev=0.58, q=0.93

Perturbing narrow abdomen disrupts neural excitability outputs that control adult circadian locomotor rhythms, light-dependent activity, touch responses, anesthetic responsiveness, social clustering, walking, and flight. FlyBase alleles and RNAi phenotypes also show lethality or partial lethality in several tissue-specific contexts, abnormal adult abdomen/head/thorax morphology... · ref: Nash et al., 2002, Curr. Biol. 12(24): 2152--2158 (PMID 12498692)

**5. `rdgB` (FBgn0003218)** — ✓ STRONG, ev=0.59, q=0.87

Perturbing rdgB primarily damages sensory physiology: loss of function disrupts phototransduction, weakens electrophysiological light responses, and causes progressive, light-enhanced degeneration of photoreceptors and rhabdomeres. The gene is also required outside vision, with mutant alleles causing abnormal olfactory behavior in both adults and larvae and altered peripheral a... · ref: Mishra et al., 2024, Life Sci Alliance 7(6): e202302525 (PMID 38499328)

---

### methotrexate_B

| | |
|---|---|
| **Study drug** | Methotrexate (chemo) |
| **Phenotype** | _Female fertility reduction (ovary atrophy)_ |
| **Interval (r6)** | `2R:17,955,396–18,498,026` (542.6 kb) |
| **Interval (r5, native)** | `2R:13,820,000–14,380,000` |
| **Significance** | −log₁₀(P) = 2.13 |
| **Heritability** | 12% |
| **Source paper** | [PMC3737169](https://pmc.ncbi.nlm.nih.gov/articles/PMC3737169/) |

**Quadrant breakdown** (all 87 genes in interval): ✓ STRONG **37** · ⚠ NOVEL_LEAD **50** · ✗ LIKELY_NOT **0** · ? CANT_RULE_OUT **0**

**Top 10 candidate genes**

| Rank | Gene | Quadrant | ev | q | bullets | refs | pubs |
|---:|---|---|---:|---:|---:|---:|---:|
| 1 | `Hsf` | ✓ STRONG | 0.61 | 0.90 | 31 | 8 | 282 |
| 2 | `Ote` | ✓ STRONG | 0.68 | 0.62 | 24 | 10 | 129 |
| 3 | `pAbp` | ✓ STRONG | 0.60 | 0.86 | 25 | 23 | 287 |
| 4 | `Dnaaf3` | ✓ STRONG | 0.64 | 0.73 | 18 | 3 | 34 |
| 5 | `Nup75` | ✓ STRONG | 0.63 | 0.74 | 10 | 6 | 55 |
| 6 | `Spn55B` | ✓ STRONG | 0.61 | 0.78 | 14 | 7 | 66 |
| 7 | `rswl` | ✓ STRONG | 0.62 | 0.74 | 21 | 3 | 38 |
| 8 | `nopo` | ✓ STRONG | 0.61 | 0.77 | 18 | 5 | 52 |
| 9 | `Gtpbp1` | ✓ STRONG | 0.60 | 0.79 | 14 | 8 | 60 |
| 10 | `PIG-O` | ✓ STRONG | 0.60 | 0.79 | 14 | 9 | 46 |

**Biological context for top 5 candidates**

**1. `Hsf` (FBgn0001222)** — ✓ STRONG, ev=0.61, q=0.90

Perturbing Drosophila Hsf primarily compromises organismal stress resilience, with recessive alleles causing larval lethality, defective heat-shock survival, abnormal neurophysiology under heat, and increased adult mortality or shortened lifespan. Hsf is also required in the female germline for normal egg-chamber/nurse-cell function and female fertility, and RNAi or aptamer-med... · ref: Funikov et al., 2014, Molek. Biol., Moscow 48(2): 306--313 (PMID 25850300)

**2. `Ote` (FBgn0266420)** — ✓ STRONG, ev=0.68, q=0.62

Otefin perturbation primarily compromises germline stem-cell maintenance and fertility rather than general viability. Loss-of-function alleles cause female sterility, ovarian germ cell loss, disrupted germarium architecture, blocked germ cell differentiation, and age-progressive male sterility with loss of male germline stem cells and niche defects. · ref: Barton et al., 2016, Dev. Biol. 415(1): 75--86 (PMID 27174470)

**3. `pAbp` (FBgn0265297)** — ✓ STRONG, ev=0.60, q=0.86

pAbp encodes the cytoplasmic poly(A)-binding protein, a conserved RNA-binding protein essential for mRNA translation, stability, and poly(A) tail regulation. Loss-of-function alleles cause male sterility due to meiotic cell cycle arrest and spermatid differentiation failure, and female sterility through oocyte development defects. · ref: Sigrist et al., 2003, J. Neurosci. 23(16): 6546--6556 (PMID 12878696)

**4. `Dnaaf3` (FBgn0034352)** — ✓ STRONG, ev=0.64, q=0.73

Perturbing Dnaaf3 primarily disrupts the two Drosophila cell types that depend on motile cilia or flagella: chordotonal mechanosensory neurons and sperm. Loss of Dnaaf3 causes larval deafness, adult uncoordination, absent vibration-evoked chordotonal responses, and male infertility with immotile, structurally abnormal sperm. · ref: Zur Lage et al., 2021, Biol. Open 10(10): bio058812 (PMID 34553759)

**5. `Nup75` (FBgn0034310)** — ✓ STRONG, ev=0.63, q=0.74

Nup75 is a conserved nuclear pore component with sparse direct fly phenotype annotation, but available perturbation data indicate that it is required for viability in some developmental tissues and for normal male germline homeostasis. RNAi driven with pnr causes pupal-stage lethality, while neuronal and tin-driven knockdown are reported as viable, suggesting context-dependent ... · ref: Neely et al., 2010, Cell 143(4): 628--638 (PMID 21074052)

---

### methotrexate_D

| | |
|---|---|
| **Study drug** | Methotrexate (chemo) |
| **Phenotype** | _Female fertility reduction (ovary atrophy)_ |
| **Interval (r5, native)** | `3L–3R:17,760,000–5,850,000` |
| **Significance** | −log₁₀(P) = 1.92 |
| **Heritability** | 10% |
| **Source paper** | [PMC3737169](https://pmc.ncbi.nlm.nih.gov/articles/PMC3737169/) |

*Cannot resolve: no genes in interval. Cross-arm QTLs require manual handling of the centromere-spanning region; the published interval (`3L–3R`) is not a single contiguous segment in the atlas's per-arm coordinate model.*

## Carboplatin (chemo, r5; 2 QTLs)

### carboplatin_CA

| | |
|---|---|
| **Study drug** | Carboplatin (chemo) |
| **Phenotype** | _Female fertility reduction (ovary atrophy)_ |
| **Interval (r6)** | `X:14,169,592–14,653,928` (484.3 kb) |
| **Interval (r5, native)** | `X:14,050,000–14,550,000` |
| **Significance** | −log₁₀(P) = 3.32 |
| **Heritability** | 23% |
| **Source paper** | [PMC4174942](https://pmc.ncbi.nlm.nih.gov/articles/PMC4174942/) |

**Quadrant breakdown** (all 39 genes in interval): ✓ STRONG **16** · ⚠ NOVEL_LEAD **23** · ✗ LIKELY_NOT **0** · ? CANT_RULE_OUT **0**

**Top 10 candidate genes**

| Rank | Gene | Quadrant | ev | q | bullets | refs | pubs |
|---:|---|---|---:|---:|---:|---:|---:|
| 1 | `yl` | ✓ STRONG | 0.64 | 0.74 | 20 | 9 | 108 |
| 2 | `na` | ✓ STRONG | 0.58 | 0.93 | 30 | 17 | 122 |
| 3 | `NetA` | ✓ STRONG | 0.59 | 0.89 | 28 | 8 | 219 |
| 4 | `CG42271` | ✓ STRONG | 0.61 | 0.74 | 10 | 7 | 46 |
| 5 | `Prp16` | ✓ STRONG | 0.60 | 0.78 | 24 | 3 | 75 |
| 6 | `Muc12Ea` | ✓ STRONG | 0.65 | 0.57 | 13 | 4 | 37 |
| 7 | `mRpS25` | ✓ STRONG | 0.61 | 0.71 | 9 | 5 | 46 |
| 8 | `sbm` | ✓ STRONG | 0.59 | 0.75 | 16 | 4 | 61 |
| 9 | `nmdyn-D6` | ✓ STRONG | 0.61 | 0.67 | 7 | 4 | 37 |
| 10 | `Tat` | ✓ STRONG | 0.60 | 0.68 | 12 | 2 | 44 |

**Biological context for top 5 candidates**

**1. `yl` (FBgn0004649)** — ✓ STRONG, ev=0.64, q=0.74

Yolkless encodes the Drosophila vitellogenin receptor, an LDL receptor superfamily member essential for clathrin-mediated yolk protein endocytosis during oogenesis. Loss-of-function mutations abolish coated pit formation in oocytes, blocking vitellogenin uptake and causing recessive female sterility across all characterized alleles. · ref: DiMario and Mahowald, 1987, J. Cell Biol. 105: 199--206 (PMID 2886508)

**2. `na` (FBgn0002917)** — ✓ STRONG, ev=0.58, q=0.93

Perturbing narrow abdomen disrupts neural excitability outputs that control adult circadian locomotor rhythms, light-dependent activity, touch responses, anesthetic responsiveness, social clustering, walking, and flight. FlyBase alleles and RNAi phenotypes also show lethality or partial lethality in several tissue-specific contexts, abnormal adult abdomen/head/thorax morphology... · ref: Nash et al., 2002, Curr. Biol. 12(24): 2152--2158 (PMID 12498692)

**3. `NetA` (FBgn0015773)** — ✓ STRONG, ev=0.59, q=0.89

Perturbing NetA primarily disrupts neural wiring and cell positioning, with curated phenotypes in larval chordotonal neurons, embryonic glia, commissural axons, optic lobe structures, photoreceptor projections, and clock-neuron axons. NetA/NetB double loss causes broader organismal consequences including reduced viability, inability to fly, female and male fertility defects, an... · ref: Liu et al., 2024, eLife 13: RP96041 (PMID 39052321)

**4. `CG42271` (FBgn0259166)** — ✓ STRONG, ev=0.61, q=0.74

CG42271 is a conserved phosphoinositide phosphatase gene with very limited direct fly phenotype annotation. Available FlyBase-curated alleles and RNAi combinations are reported as viable, and the e02366 allele is also fertile, suggesting no obvious organismal lethality or sterility has been captured under those tested conditions. · ref: Schnorrer et al., 2010, Nature 464(7286): 287--291 (PMID 20220848)

**5. `Prp16` (FBgn0026713)** — ✓ STRONG, ev=0.60, q=0.78

Prp16 perturbation produces broad organism-level consequences consistent with an essential splicing factor whose dosage is limiting in multiple tissues. Strong loss-of-function alleles are lethal from embryonic through larval, prepupal, pupal, or pharate adult stages, while tissue-directed knockdown affects flight muscle structure, larval neuroanatomy, adult pain response, dors... · ref: Magwire et al., 2010, PLoS Genet. 6(7): e1001037 (PMID 20686706)

---

### carboplatin_CB

| | |
|---|---|
| **Study drug** | Carboplatin (chemo) |
| **Phenotype** | _Female fertility reduction (ovary atrophy)_ |
| **Interval (r6)** | `2L:12,455,540–14,689,340` (2.23 Mb) |
| **Interval (r5, native)** | `2L:12,480,000–14,640,000` |
| **Significance** | −log₁₀(P) = 3.23 |
| **Heritability** | 17% |
| **Source paper** | [PMC4174942](https://pmc.ncbi.nlm.nih.gov/articles/PMC4174942/) |

**Quadrant breakdown** (all 217 genes in interval): ✓ STRONG **122** · ⚠ NOVEL_LEAD **95** · ✗ LIKELY_NOT **0** · ? CANT_RULE_OUT **0**

**Top 10 candidate genes**

| Rank | Gene | Quadrant | ev | q | bullets | refs | pubs |
|---:|---|---|---:|---:|---:|---:|---:|
| 1 | `loqs` | ✓ STRONG | 0.62 | 0.91 | 23 | 14 | 197 |
| 2 | `rk` | ✓ STRONG | 0.61 | 0.93 | 26 | 18 | 172 |
| 3 | `mTor` | ✓ STRONG | 0.62 | 0.92 | 31 | 8 | 820 |
| 4 | `PolG1` | ✓ STRONG | 0.61 | 0.88 | 33 | 8 | 154 |
| 5 | `PolG2` | ✓ STRONG | 0.62 | 0.84 | 22 | 8 | 102 |
| 6 | `Arpc1` | ✓ STRONG | 0.61 | 0.86 | 24 | 7 | 167 |
| 7 | `Pect` | ✓ STRONG | 0.61 | 0.83 | 25 | 7 | 77 |
| 8 | `Ance` | ✓ STRONG | 0.62 | 0.82 | 22 | 4 | 217 |
| 9 | `spel1` | ✓ STRONG | 0.63 | 0.77 | 14 | 5 | 89 |
| 10 | `Vha68-2` | ✓ STRONG | 0.58 | 0.93 | 25 | 21 | 145 |

**Biological context for top 5 candidates**

**1. `loqs` (FBgn0032515)** — ✓ STRONG, ev=0.62, q=0.91

Loquacious (loqs) encodes a double-stranded RNA binding protein that serves as an essential cofactor for both Dicer-1 (miRNA processing) and Dicer-2 (siRNA processing) through distinct splice isoforms. Loss-of-function mutations cause embryonic lethality with a rescuable maternal effect, female sterility due to germline stem cell loss, neuroanatomical defects, locomotor dysfunc... · ref: Fukunaga et al., 2012, Cell 151(3): 533--546 (PMID 23063653)

**2. `rk` (FBgn0003255)** — ✓ STRONG, ev=0.61, q=0.93

Rickets (rk) encodes a G-protein coupled receptor for the heterodimeric hormone bursicon, signaling via cAMP. Loss of rk disrupts post-eclosion cuticle hardening and melanization, wing expansion, and proper formation of legs, tarsal segments, and other adult structures. · ref: Baker and Truman, 2002, J. Exp. Biol. 205(17): 2555--2565 (PMID 12151362)

**3. `mTor` (FBgn0021796)** — ✓ STRONG, ev=0.62, q=0.92

Perturbing mTor broadly disrupts growth, developmental timing, survival, fertility, neural structure, and stress tolerance in Drosophila. Loss-of-function or RNAi reduces cell and body size, decreases cell number, impairs larval and pupal development, compromises oogenesis and germline stem cell maintenance, and alters neuromuscular and dendritic anatomy. · ref: Spitz et al., 2022, Cells 11(13): 2103 (PMID 35805186)

**4. `PolG1` (FBgn0004406)** — ✓ STRONG, ev=0.61, q=0.88

PolG1 encodes the catalytic subunit of mitochondrial DNA polymerase gamma, so perturbing it primarily damages mitochondrial genome maintenance and produces organism-level failure in larval growth, pupal development, adult movement, lifespan, muscle integrity, neuronal survival, and male germline mitochondrial genome handling. Strong loss-of-function alleles are larval or pupal ... · ref: Ozaki et al., 2022, Biomolecules 12(8): 1105 (PMID 36008999)

**5. `PolG2` (FBgn0004407)** — ✓ STRONG, ev=0.62, q=0.84

PolG2 encodes the accessory subunit of mitochondrial DNA polymerase gamma, essential for mtDNA replication and maintenance in Drosophila. Loss-of-function mutations cause complete lethality during the pupal stage, with loss of mtDNA and mitochondrial mass, reduced cell proliferation in the central nervous system, and abnormal neuroanatomy. · ref: Iyengar et al., 2002, Proc. Natl. Acad. Sci. U.S.A. 99(7): 4483--4488 (PMID 11917141)

---

## Appendix A — incidental cross-QTL coordinate overlaps

While running the per-QTL analysis above, the pipeline noticed that six pairs of QTLs in your compilation share genome space after the r5→r6 lift. This is not part of the per-trait candidate-ranking task and is included only for completeness.

| QTL A | QTL B | Chr | Shared region (r6) | Overlap | Genes in shared region | Class |
|---|---|---|---|---:|---:|---|
| `gemcitabine_GA` (Gemcitabine) | `malathion_A` (Malathion) | 2R | 10,966,645–12,899,385 | 1.93 Mb | 301 | cross-family |
| `gemcitabine_GA` (Gemcitabine) | `caffeine_D` (Caffeine) | 2R | 10,673,345–11,168,099 | 494.8 kb | 47 | cross-family |
| `carboplatin_CA` (Carboplatin) | `methotrexate_A` (Methotrexate) | X | 14,169,592–14,653,928 | 484.3 kb | 39 | same-family (chemo × chemo) |
| `gemcitabine_GB` (Gemcitabine) | `methotrexate_C` (Methotrexate) | 3L | 3,224,838–3,616,682 | 391.8 kb | 43 | same-family (chemo × chemo) |
| `methotrexate_A` (Methotrexate) | `zinc_A` (Zinc) | X | 13,796,451–14,093,253 | 296.8 kb | 23 | cross-family |
| `malathion_A` (Malathion) | `caffeine_D` (Caffeine) | 2R | 10,966,645–11,168,099 | 201.5 kb | 10 | cross-family |

Each overlap can be inspected at `/qtl-overlap/<A>/<B>` in the web UI, which lists the genes shared between the two intervals with semantic-similarity scores against both parent phenotypes.

---

## Reproducibility

| Item | Location |
|---|---|
| Source repository | https://github.com/sgaofen/fly-distill |
| v1.4 release (atlas + canonicals + embeddings) | https://github.com/sgaofen/fly-distill/releases/tag/v1.4 |
| QTL input (your file, verbatim) | `data/QTL_summary.md` |
| Web UI | `python -m flyatlas.cli serve` → http://localhost:8765/qtl |
| Per-QTL CLI | `python -m flyatlas.cli qtl-rank caffeine_D --topk 20` |
| r5 region query | `python -m flyatlas.cli ask 'DNA damage' --region X:13.25e6-14.60e6 --release r5` |
| r5↔r6 lift | `python -m flyatlas.cli lift X:13.25e6-14.60e6 --from r5` |
| Regenerate this report | `python src/build_per_qtl_report.py` |

**Runtime dependency:** a Gemini embedding API key (`gemini-embedding-2`) for the query-time semantic vector. All other data (atlas database, gene canonicals, pre-computed embeddings) ships in the v1.4 release tarballs.

---

*Per-QTL ranking framework follows your 2026-05-19 description. Comments and corrections welcome.*
