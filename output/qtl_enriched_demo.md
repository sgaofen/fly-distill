# QTL Candidate Ranking — Before/After Enriched Query

Demo on 4 representative QTLs. Atlas, embeddings, and ranking algorithm are unchanged — only the query text is enriched with the drug mechanism.

---

<div class="qtl-section">

## zinc_D — Zinc

`3L:8,352,067–9,512,583` · 166 genes

<div class="query-block">

**Original query** (5 words):

> _Larval survival (~90% baseline mortality)_

**Enriched query** (39 words):

> _Larval fly mortality after zinc chloride (ZnCl2) exposure. Zinc toxicity disrupts metal ion homeostasis, induces oxidative stress, and impairs neuromuscular function. Best candidates protect against heavy-metal toxicity: metallothionein (Mtn) family metal scavenging, zinc transporter regulation, antioxidant defense, ferritin storage._

</div>

**Top 7 candidates** (★ = newly appearing after enrichment)

| Rank | Before | After |
|---:|---|---|
| 1 | `Rdl` | `Rdl` |
| 2 | `TrpA1` | **MTF-1** ★ |
| 3 | `Hsp23` | `Hsp23` |
| 4 | `Arr2` | `TrpA1` |
| 5 | `Galk` | `Galk` |
| 6 | `Ugp` | **Hsp26** ★ |
| 7 | `Fhos` | **Hsp22** ★ |

**Newly entering top 7**

<div class="rise-list">

<div class="gene-entry">
<div class="gene-head"><strong>MTF-1</strong> <code>(FBgn0040305)</code> — ev = 0.76, 26 bullets</div>
<div class="gene-bio">MTF-1 is a major organismal protector against disrupted metal homeostasis in Drosophila.</div>
</div>

<div class="gene-entry">
<div class="gene-head"><strong>Hsp26</strong> <code>(FBgn0001225)</code> — ev = 0.68, 17 bullets</div>
<div class="gene-bio">Hsp26 encodes a small heat shock protein chaperone critical for protein homeostasis during environmental stress and neuronal development.</div>
</div>

<div class="gene-entry">
<div class="gene-head"><strong>Hsp22</strong> <code>(FBgn0001223)</code> — ev = 0.68, 21 bullets</div>
<div class="gene-bio">Hsp22 encodes a mitochondrial matrix small heat shock protein whose expression increases dramatically during aging.</div>
</div>

</div>

**Dropping out**: `Arr2`, `Ugp`, `Fhos`

</div>

<div class="qtl-section">

## methotrexate_A — Methotrexate

`X:13,359,248–14,749,376` · −log₁₀(P) = 3.19

<div class="query-block">

**Original query** (5 words):

> _Female fertility reduction (ovary atrophy)_

**Enriched query** (44 words):

> _Female fly fertility loss after methotrexate chemotherapy exposure. Methotrexate is a dihydrofolate reductase inhibitor that depletes tetrahydrofolate pools, blocking thymidylate synthesis and stalling DNA replication in proliferating germline cells. Best candidates are protective against folate-pathway depletion, DNA damage from thymine starvation, or pharmacokinetic resistance._

</div>

**Top 7 candidates** (★ = newly appearing after enrichment)

| Rank | Before | After |
|---:|---|---|
| 1 | `Yp3` | **DNAlig4** ★ |
| 2 | `g` | `mus101` |
| 3 | `yl` | `Nadsyn` |
| 4 | `na` | **Clic** ★ |
| 5 | `rdgB` | `Yp3` |
| 6 | `Nadsyn` | **NetA** ★ |
| 7 | `mus101` | `na` |

**Newly entering top 7**

<div class="rise-list">

<div class="gene-entry">
<div class="gene-head"><strong>DNAlig4</strong> <code>(FBgn0030506)</code> — ev = 0.71, 20 bullets</div>
<div class="gene-bio">DNA ligase 4 (DNAlig4) encodes the ATP-dependent ligase that seals double-strand breaks during canonical non-homologous end joining (NHEJ).</div>
</div>

<div class="gene-entry">
<div class="gene-head"><strong>Clic</strong> <code>(FBgn0030529)</code> — ev = 0.69, 24 bullets</div>
<div class="gene-bio">Clic encodes the sole Drosophila ortholog of the vertebrate Chloride Intracellular Channel (CLIC) family, a metamorphic protein with chloride channel, glutathione peroxidase, and oxidoreductase activities.</div>
</div>

<div class="gene-entry">
<div class="gene-head"><strong>NetA</strong> <code>(FBgn0015773)</code> — ev = 0.68, 28 bullets</div>
<div class="gene-bio">Perturbing NetA primarily disrupts neural wiring and cell positioning, with curated phenotypes in larval chordotonal neurons, embryonic glia, commissural axons, optic lobe structures, photoreceptor projections, and clock...</div>
</div>

</div>

**Dropping out**: `g`, `yl`, `rdgB`

</div>

<div class="qtl-section">

## malathion_A — Malathion

`2R:10,966,645–13,213,848` · 344 genes

<div class="query-block">

**Original query** (5 words):

> _Adult survival (~95% baseline mortality)_

**Enriched query** (44 words):

> _Adult fly mortality after malathion exposure. Malathion is an organophosphate insecticide that irreversibly inhibits acetylcholinesterase (AChE), causing toxic acetylcholine buildup and neuromuscular overstimulation. Best candidates protect against organophosphate toxicity: cytochrome P450 / esterase xenobiotic detoxification, glutathione conjugation, ABC-transporter efflux, or modulation of cholinergic signaling._

</div>

**Top 7 candidates** (★ = newly appearing after enrichment)

| Rank | Before | After |
|---:|---|---|
| 1 | `Iswi` | **Cyp12d1-p** ★ |
| 2 | `shn` | **Cyp6g1** ★ |
| 3 | `Amph` | `Amph` |
| 4 | `Taz` | **Cyp12d1-d** ★ |
| 5 | `Psc` | `Iswi` |
| 6 | `Drep1` | **Mdr49** ★ |
| 7 | `dare` | **Cyp6g2** ★ |

**Newly entering top 7**

<div class="rise-list">

<div class="gene-entry">
<div class="gene-head"><strong>Cyp12d1-p</strong> <code>(FBgn0050489)</code> — ev = 0.73, 17 bullets</div>
<div class="gene-bio">Cyp12d1-p encodes a cytochrome P450 monooxygenase that functions in xenobiotic detoxification, most notably conferring resistance to DDT and dicyclanil when overexpressed in transgenic flies.</div>
</div>

<div class="gene-entry">
<div class="gene-head"><strong>Cyp6g1</strong> <code>(FBgn0025454)</code> — ev = 0.73, 19 bullets</div>
<div class="gene-bio">Cyp6g1 encodes a cytochrome P450 monooxygenase that is the paradigm for metabolic insecticide resistance in Drosophila melanogaster.</div>
</div>

<div class="gene-entry">
<div class="gene-head"><strong>Cyp12d1-d</strong> <code>(FBgn0053503)</code> — ev = 0.71, 19 bullets</div>
<div class="gene-bio">Cyp12d1-d encodes a cytochrome P450 monooxygenase that is a major determinant of metabolic insecticide resistance in Drosophila.</div>
</div>

<div class="gene-entry">
<div class="gene-head"><strong>Mdr49</strong> <code>(FBgn0004512)</code> — ev = 0.70, 22 bullets</div>
<div class="gene-bio">Mdr49 encodes an ABCB subfamily drug efflux transporter that plays critical roles in primordial germ cell migration, insecticide detoxification, and stress tolerance.</div>
</div>

<div class="gene-entry">
<div class="gene-head"><strong>Cyp6g2</strong> <code>(FBgn0033696)</code> — ev = 0.74, 17 bullets</div>
<div class="gene-bio">Cyp6g2 encodes the major cytochrome P450 epoxidase responsible for juvenile hormone (JHB3 and JH III) biosynthesis in Drosophila, expressed predominantly in the corpus allatum of the ring gland.</div>
</div>

</div>

**Dropping out**: `shn`, `Taz`, `Psc`, `Drep1`, `dare`

</div>

<div class="qtl-section">

## caffeine_D — Caffeine

`2R:10,628,099–11,168,099` · −log₁₀(P) = 13.1 · 51 genes

<div class="query-block">

**Original query** (6 words):

> _Adult female longevity on 1% caffeine_

**Enriched query** (46 words):

> _Adult-female fly longevity under chronic 1% caffeine exposure. Caffeine is a methylxanthine alkaloid xenobiotic; it antagonizes adenosine receptors, inhibits phosphodiesterase, elevates cAMP, and induces oxidative stress. Best candidates protect against chronic caffeine toxicity: cytochrome P450 xenobiotic detoxification, antioxidant defense, regulation of adenosine/cAMP signaling, stress-response transcription factors._

</div>

**Top 7 candidates** (★ = newly appearing after enrichment)

| Rank | Before | After |
|---:|---|---|
| 1 | `Prosβ5` | `Prosβ5` |
| 2 | `Cyp12d1-d` | `Cyp12d1-d` |
| 3 | `shn` | `Cyp12d1-p` |
| 4 | `Cyp12d1-p` | `shn` |
| 5 | `stan` | **CG11883** ★ |
| 6 | `CG30016` | `CG30016` |
| 7 | `LTV1` | `stan` |

**Newly entering top 7**

<div class="rise-list">

<div class="gene-entry">
<div class="gene-head"><strong>CG11883</strong> <code>(FBgn0033538)</code> — ev = 0.71, 8 bullets</div>
<div class="gene-bio">CG11883 is a sparsely characterized Drosophila protein-coding gene annotated with 5'-nucleotidase/hydrolase activity, but the available fly phenotype record is mainly RNAi-screen based.</div>
</div>

</div>

**Dropping out**: `LTV1`

</div>

