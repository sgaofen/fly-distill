# Curated QTL candidate genes — 4 drug classes

## What's in this report

Four QTLs (one per drug class) each get one section:

1. **QTL header** — chromosome region, gene count, source paper, drug-mechanism background in plain language.
2. **Union of candidates** — for each QTL, ran four query variants against the atlas (verbatim phenotype string / keyword bag / mechanism description / mechanism + gene-family hints). Took the union of the top-7 results across all four variants. This is the algorithm's raw candidate set, typically 10–13 unique genes.
3. **Curation tag** — each candidate is then tagged by hand using FlyBase biology against the drug's mechanism of action:
    - **★ KEEP** — gene's known function is directly consistent with conferring protection against this drug.
    - **△ MAYBE** — semantic match plus plausible biology, but the link is indirect; would need wet-lab validation to triage further.
    - **✗ DISCARD** — algorithm surfaced for generic / surface-level reasons (lethality semantics, chromatin remodeling, etc.) but the gene's actual function has no specific link to the drug.
4. **One-sentence justification** for each KEEP and MAYBE; pooled justification for the DISCARDs.
5. **Curated shortlist** at the end of each section — the ★ candidates only.

Each section is color-coded in the PDF: green panels = KEEP, amber = MAYBE, grey = DISCARD.

Final summary table at the bottom reports KEEP / MAYBE / DISCARD counts across the 4 QTLs.

---

<div class="qtl-section">

## malathion_A — adult mortality under organophosphate (AChE inhibitor)

`2R:10,966,645–13,213,848` · 344 genes in interval · source PMC9713458

**Drug mechanism.** Malathion is metabolized by Cyp450s and esterases into the active metabolite malaoxon, which irreversibly inhibits acetylcholinesterase (AChE). This causes acetylcholine to accumulate at neuromuscular junctions → continuous overstimulation → paralysis → death. Protective genes are either (a) xenobiotic detoxification enzymes, (b) drug efflux pumps, or (c) modulators of cholinergic signaling.

**Union of 13 candidates across 4 prompts:**

<div class="curation-list">

<div class="gene-keep">
<div class="gene-head"><strong>Cyp6g1</strong> <code>(FBgn0025454)</code> · 19 bullets · 17 refs · 230 pubs · in 3/4 prompts</div>
<div class="gene-bio">★ KEEP — <strong>The single most studied insecticide-resistance gene in <em>Drosophila melanogaster</em></strong>. Cyp6g1 over-expression in detoxification tissues confers cross-resistance to DDT, nitenpyram, lufenuron, and other xenobiotics; constitutive over-expression is the canonical DDT-resistance mechanism in wild populations (Daborn et al., 2002). Same Cyp450 substrate-specificity class metabolizes malathion.</div>
</div>

<div class="gene-keep">
<div class="gene-head"><strong>Cyp12d1-d</strong> <code>(FBgn0053503)</code> · 19 bullets · in 3/4 prompts</div>
<div class="gene-bio">★ KEEP — Cytochrome P450 monooxygenase, major determinant of metabolic insecticide resistance. Over-expression confers DDT and dicyclanil resistance; constitutively elevated 6-fold in DDT-resistant strains.</div>
</div>

<div class="gene-keep">
<div class="gene-head"><strong>Cyp12d1-p</strong> <code>(FBgn0050489)</code> · 17 bullets · in 3/4 prompts</div>
<div class="gene-bio">★ KEEP — Tandem paralog of Cyp12d1-d on the same chromosomal segment, same substrate class. Two paralogs at the top is exactly what you'd expect for a real insecticide-detox locus under selection.</div>
</div>

<div class="gene-keep">
<div class="gene-head"><strong>Cyp6g2</strong> <code>(FBgn0033459)</code> · 17 bullets · in 3/4 prompts</div>
<div class="gene-bio">★ KEEP — Cyp450 monooxygenase in the same family as Cyp6g1. Expressed in detoxification tissues (fat body, Malpighian tubules, midgut). Functions in xenobiotic clearance.</div>
</div>

<div class="gene-keep">
<div class="gene-head"><strong>Mdr49</strong> <code>(FBgn0004513)</code> · 22 bullets · 12 refs · in 1/4 prompts</div>
<div class="gene-bio">★ KEEP — Multi-drug-resistance ABC transporter. Actively effluxes xenobiotics from cells. Mdr49 mutants are hypersensitive to a wide range of small-molecule toxins; over-expression confers cross-resistance.</div>
</div>

<div class="gene-keep">
<div class="gene-head"><strong>dare</strong> <code>(FBgn0263983)</code> · 25 bullets · in 4/4 prompts</div>
<div class="gene-bio">★ KEEP — Adrenodoxin reductase; supplies electrons to mitochondrial cytochrome P450s. Without dare, the Cyp450 detox machinery on the same chromosomal segment cannot function. A defensible auxiliary candidate even though dare itself isn't a metabolizing enzyme.</div>
</div>

<div class="gene-maybe">
<div class="gene-head"><strong>Amph</strong> <code>(FBgn0027356)</code> · 28 bullets · in 3/4 prompts</div>
<div class="gene-bio">△ MAYBE — Amphiphysin; required for synaptic-vesicle endocytosis at neuromuscular junctions. Plausibly modulates cholinergic-receptor recycling, but no direct AChE / organophosphate literature.</div>
</div>

<div class="gene-maybe">
<div class="gene-head"><strong>Taz</strong> <code>(FBgn0030182)</code> · 28 bullets · in 1/4 prompts</div>
<div class="gene-bio">△ MAYBE — Tafazzin, mitochondrial cardiolipin remodelase. Organophosphate toxicity has a mitochondrial component (cardiolipin oxidation under cholinergic excitotoxicity); plausible but indirect.</div>
</div>

<div class="gene-discard">
<div class="gene-head"><strong>Iswi</strong>, <strong>Sin3A</strong>, <strong>Psc</strong>, <strong>shn</strong>, <strong>Drep1</strong> — 5 genes</div>
<div class="gene-bio">✗ DISCARD — Generic chromatin remodelers / apoptosis effectors / TGF-β signaling. They surface for "cellular damage response" semantics but have no specific link to organophosphate detoxification. Long's <em>"hits are more like genes that could kill a larvae if mutated"</em> applies to these.</div>
</div>

</div>

**Curated shortlist:** 6 ★ candidates, all in the xenobiotic-detox / drug-efflux pathway. This is a clean malathion-resistance candidate list — the algorithm + manual filter together reduce a 344-gene interval to 6 high-confidence detox genes.

</div>


<div class="qtl-section">

## methotrexate_A — female fertility loss under DHFR inhibitor

`X:13,359,248–14,749,376` · r5-native, lifted to r6 · source PMC3737169

**Drug mechanism.** Methotrexate is a competitive inhibitor of dihydrofolate reductase (DHFR). DHFR converts dihydrofolate → tetrahydrofolate; tetrahydrofolate is needed for thymidylate synthesis. Methotrexate blocks DHFR → tetrahydrofolate pools collapse → no dTMP → DNA replication stalls in proliferating germline cells → oocyte death → ovary atrophy. Protective genes: (a) DNA damage repair (especially of stalled forks), (b) alternative thymidylate synthesis, (c) drug efflux.

**Union of 11 candidates across 4 prompts:**

<div class="curation-list">

<div class="gene-keep">
<div class="gene-head"><strong>DNAlig4</strong> <code>(FBgn0030506)</code> · 20 bullets · 15 refs · in 3/4 prompts</div>
<div class="gene-bio">★ KEEP — DNA Ligase 4, the catalytic ligase in non-homologous end-joining (NHEJ) repair of double-strand breaks. Methotrexate-stalled replication forks collapse into DSBs; DNAlig4 is required to seal them. Direct biological match.</div>
</div>

<div class="gene-keep">
<div class="gene-head"><strong>mus101</strong> <code>(FBgn0002901)</code> · 30 bullets · 13 refs · in 4/4 prompts</div>
<div class="gene-bio">★ KEEP — Mutagen-sensitive 101, the <em>Drosophila</em> TopBP1 ortholog and DNA-damage checkpoint coordinator. Activates ATR signaling at stalled replication forks (exactly what methotrexate produces). Loss-of-function mutants are hypersensitive to replication stressors. Textbook MTX-resistance candidate.</div>
</div>

<div class="gene-maybe">
<div class="gene-head"><strong>Nadsyn</strong> <code>(FBgn0030552)</code> · 12 bullets · in 4/4 prompts</div>
<div class="gene-bio">△ MAYBE — NAD synthetase. NAD is the substrate for PARP, which marks stalled forks and recruits repair machinery. Indirect support for DNA repair, but not a textbook candidate.</div>
</div>

<div class="gene-maybe">
<div class="gene-head"><strong>Bcat</strong> <code>(FBgn0030574)</code> · 30 bullets · in 3/4 prompts</div>
<div class="gene-bio">△ MAYBE — Branched-chain aminotransferase, amino-acid metabolism. Could compensate for folate-pathway disruption via methionine cycle, but speculative.</div>
</div>

<div class="gene-maybe">
<div class="gene-head"><strong>Clic</strong> <code>(FBgn0030529)</code> · 24 bullets · in 2/4 prompts</div>
<div class="gene-bio">△ MAYBE — Chloride intracellular channel, apoptosis modulator. Germline apoptosis is the proximate cause of ovary atrophy in this assay; Clic modulates that.</div>
</div>

<div class="gene-maybe">
<div class="gene-head"><strong>Yp3</strong> <code>(FBgn0004045)</code> + <strong>yl</strong> <code>(FBgn0004649)</code></div>
<div class="gene-bio">△ MAYBE — Yolk protein 3 + yolkless (vitellogenin receptor). These are oogenesis-specific; their loss directly causes ovary atrophy. <em>But</em> they're not drug-specific — the phenotype assay measures ovary atrophy and these are the most obviously-ovary genes in the interval, so they surface even without MTX context. Keep as &quot;possibly causal&quot; but flag that the algorithm's semantic match is conflating &quot;ovary atrophy gene&quot; with &quot;MTX-resistance gene.&quot;</div>
</div>

<div class="gene-discard">
<div class="gene-head"><strong>na</strong>, <strong>rdgB</strong>, <strong>NetA</strong>, <strong>g</strong> — 4 genes</div>
<div class="gene-bio">✗ DISCARD — Narrow abdomen (Ca channel, neural), retinal degeneration B (PI transfer, visual), Netrin A (axon guidance), garnet (eye pigment). All neural / visual / pigment biology with no plausible link to MTX resistance.</div>
</div>

</div>

**Curated shortlist:** 2 ★ direct DNA-repair candidates + 5 △ MAYBEs (the latter including 2 oogenesis-specific genes that are <em>real ovary genes</em> but not MTX-specific). The algorithm's strength here is finding the DNA-repair direct hits despite the verbatim phenotype string being &quot;Female fertility reduction (ovary atrophy)&quot; — no mention of MTX or DNA damage.

</div>


<div class="qtl-section">

## caffeine_D — adult-female longevity under chronic 1% caffeine

`2R:10,628,099–11,168,099` · 51 genes · −log₁₀(P)=13.10 · source PMC8893256

**Drug mechanism.** Caffeine is a methylxanthine alkaloid xenobiotic. It antagonizes adenosine receptors, inhibits cyclic-nucleotide phosphodiesterases (raising cAMP), and chronically induces oxidative stress. Genes conferring longevity under chronic caffeine exposure are either (a) xenobiotic detox enzymes that clear caffeine, (b) antioxidant defense, or (c) general stress-response regulators.

**Union of 10 candidates across 4 prompts:**

<div class="curation-list">

<div class="gene-keep">
<div class="gene-head"><strong>Cyp12d1-d</strong> <code>(FBgn0053503)</code> · 19 bullets · in 4/4 prompts</div>
<div class="gene-bio">★ KEEP — Cytochrome P450 monooxygenase, <strong>FlyBase-documented as participating in caffeine metabolism</strong>. Dietary guarana (natural caffeine source) upregulates Cyp12d1 expression in flies (FBrf0263047); silencing alters caffeine metabolite profiles (FBrf0227555). This is the cleanest direct caffeine-resistance candidate in the atlas.</div>
</div>

<div class="gene-keep">
<div class="gene-head"><strong>Cyp12d1-p</strong> <code>(FBgn0050489)</code> · 17 bullets · in 4/4 prompts</div>
<div class="gene-bio">★ KEEP — Tandem paralog of Cyp12d1-d, same substrate class. Two adjacent Cyp450 paralogs in the strongest QTL of the study (−log₁₀P=13.10) is a striking convergence.</div>
</div>

<div class="gene-keep">
<div class="gene-head"><strong>Prosβ5</strong> <code>(FBgn0029134)</code> · 25 bullets · 17 refs · in 4/4 prompts</div>
<div class="gene-bio">★ KEEP — Catalytic β5 subunit of the 26S proteasome. Adult-only over-expression directly extends fly lifespan (Nguyen et al., 2019). Chronic caffeine likely accelerates protein damage; proteasome capacity is rate-limiting for clearance. Lifespan-extension + caffeine-stress connection is direct.</div>
</div>

<div class="gene-maybe">
<div class="gene-head"><strong>CG30016</strong>, <strong>CG11883</strong> — uncharacterized · in 3-4 prompts</div>
<div class="gene-bio">△ MAYBE — High semantic match across all 4 prompt variants but the genes are uncharacterized (no published functional study). These are exactly the &quot;NOVEL LEAD&quot; quadrant per the 2D framework: under-studied genes with consistent embedding similarity to caffeine-resistance concepts. Worth functional follow-up.</div>
</div>

<div class="gene-discard">
<div class="gene-head"><strong>Daao1</strong>, <strong>LTV1</strong>, <strong>stan</strong>, <strong>alka</strong>, <strong>shn</strong> — 5 genes</div>
<div class="gene-bio">✗ DISCARD — D-amino acid oxidase (Daao1), ribosome biogenesis (LTV1), planar polarity (stan), alkaline phosphatase (alka), BMP signaling (shn). All surface for generic &quot;stress / development / metabolism&quot; semantics but have no specific link to caffeine, methylxanthine, or xenobiotic detoxification.</div>
</div>

</div>

**Curated shortlist:** 3 ★ candidates (Cyp12d1-d, Cyp12d1-p, Prosβ5) — two P450 paralogs for direct caffeine clearance + one proteasome subunit for lifespan extension. The cleanest QTL in the study, both in significance (−log₁₀P=13.10) and in candidate-list quality.

</div>


<div class="qtl-section">

## zinc_D — larval mortality under zinc chloride

`3L:8,352,067–9,512,583` · 166 genes · source PMC12606420

**Drug mechanism (your wording).** Zinc chloride toxicity in insects acts through the disruption of metal ion homeostasis, oxidative stress, and neuromuscular impairment. Protective genes: (a) metallothionein-family metal scavengers, (b) zinc transporters maintaining intracellular homeostasis, (c) antioxidant defense.

**Union of 11 candidates across 4 prompts:**

<div class="curation-list">

<div class="gene-keep">
<div class="gene-head"><strong>MTF-1</strong> <code>(FBgn0040305)</code> · 26 bullets · 6 refs · in 3/4 prompts</div>
<div class="gene-bio">★ KEEP — <strong>Metal-responsive Transcription Factor 1, the master regulator of metal homeostasis in <em>Drosophila</em></strong>. Free Zn²⁺ binds MTF-1 → MTF-1 enters nucleus → binds Metal Response Elements (MREs) → activates transcription of metallothionein genes (MtnA–MtnE). MTF-1 loss-of-function makes flies extremely zinc-sensitive (Egli et al., 2003). This is the textbook gene for &quot;protective against zinc.&quot;</div>
</div>

<div class="gene-keep">
<div class="gene-head"><strong>foi</strong> <code>(FBgn0019947)</code> · 29 bullets · 15 refs · in 1/4 prompts</div>
<div class="gene-bio">★ KEEP — &quot;Fear of intimacy.&quot; A <strong>ZIP-family zinc transporter</strong> (SLC39 ortholog) required for germ-cell migration during embryogenesis. Directly transports Zn²⁺ across membranes; its expression and activity buffer intracellular zinc concentration. Only surfaces with the family-name prompt (V_families), but is a textbook zinc-transport gene. <em>This is the algorithm catching a real candidate that V0 verbatim misses entirely.</em></div>
</div>

<div class="gene-maybe">
<div class="gene-head"><strong>Hsp22</strong> <code>(FBgn0001223)</code> · 21 bullets · in 3/4 prompts</div>
<div class="gene-bio">△ MAYBE — Mitochondrial-matrix small heat shock protein. Loss-of-function shortens lifespan and impairs oxidative-stress tolerance. Zinc toxicity has a strong mitochondrial component (cardiolipin / ETC disruption) so Hsp22 is plausibly protective, but it's a generic stress chaperone, not zinc-specific.</div>
</div>

<div class="gene-maybe">
<div class="gene-head"><strong>Hsp23</strong>, <strong>Hsp26</strong> — small HSPs</div>
<div class="gene-bio">△ MAYBE — Cytosolic small heat shock proteins, paralogous to Hsp22. Same logic: generic chaperone function, plausible protection from misfolded proteins under metal stress.</div>
</div>

<div class="gene-maybe">
<div class="gene-head"><strong>Rdl</strong> <code>(FBgn0004244)</code> · 21 bullets · 22 refs · in 4/4 prompts</div>
<div class="gene-bio">△ MAYBE — Resistant to dieldrin; GABA-A receptor subunit. Listed as &quot;protective&quot; because zinc disrupts ion channels and GABA-receptor function is implicated in neuromuscular zinc toxicity. Borderline.</div>
</div>

<div class="gene-discard">
<div class="gene-head"><strong>TrpA1</strong>, <strong>Galk</strong>, <strong>Ugp</strong>, <strong>Fhos</strong>, <strong>Arr2</strong> — 5 genes</div>
<div class="gene-bio">✗ DISCARD — TRP channel (thermal nociception), galactose/glucose metabolism (Galk, Ugp), actin remodeler (Fhos), visual arrestin (Arr2). No specific link to zinc biology. They surface for generic &quot;larval lethality&quot; / &quot;ion channel&quot; semantics.</div>
</div>

</div>

**Curated shortlist:** 2 ★ candidates (MTF-1 + foi) — the metal-response master TF + a direct zinc transporter. These are the two genes most likely to give Long a wet-lab-validatable zinc-resistance phenotype.

</div>

---

## Patterns across the 4 QTLs

| QTL | ★ KEEP | △ MAYBE | ✗ DISCARD | Algorithm's best work |
|---|:---:|:---:|:---:|---|
| malathion_A | 6 | 2 | 5 | Surfaced 4 Cyp450s + 1 ABC transporter + 1 P450 auxiliary cofactor — textbook insecticide-detox panel |
| methotrexate_A | 2 | 5 | 4 | Found DNAlig4 + mus101 (direct DNA-damage response) despite verbatim phenotype string saying nothing about DNA |
| caffeine_D | 3 | 2 | 5 | Two adjacent Cyp450 paralogs + proteasome — clean detox + lifespan story |
| zinc_D | 2 | 4 | 5 | MTF-1 (textbook gene) + foi (zinc transporter) — both real candidates worth wet-lab validation |

**Across the 4 strongest QTLs:** algorithm + manual curation yields **13 high-confidence (★) candidates** across the 4 drugs. The MAYBEs (13 total) are real follow-up territory; the DISCARDs (19) are noise the algorithm couldn't filter on its own but biology can.
