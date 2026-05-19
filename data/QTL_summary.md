# Drosophila QTL Mapping Studies: Summary

## QTL Table

**Coordinate systems: Release 5 (r5) = Mb; Release 6 (r6) = bp. Direct comparison between r5 and r6 coordinates requires liftOver (see note below).**

| QTL | Study Drug | Chr | Peak | Interval | −log₁₀(P) | H² / Gene Count | Genome Release | Phenotype |
|-----|-----------|-----|------|----------|-----------|-----------------|---------------|-----------|
| CA | Carboplatin | X | 14.29 Mb | 14.05–14.55 Mb | 3.32 | 23% | r5 | Female fertility reduction (ovary atrophy) |
| CB | Carboplatin | 2L | 12.67 Mb | 12.48–14.64 Mb | 3.23 | 17% | r5 | Female fertility reduction (ovary atrophy) |
| GA | Gemcitabine | 2R | 8.22 Mb | 6.60–8.79 Mb | 2.13 | 9% | r5 | Female fertility reduction (ovary atrophy) |
| GB | Gemcitabine | 3L | 3.40 Mb | 3.23–3.62 Mb | 4.97 | 18% | r5 | Female fertility reduction (ovary atrophy) |
| A | Methotrexate | X | 13.85 Mb | 13.25–14.60 Mb | 3.19 | 15% | r5 | Female fertility reduction (ovary atrophy) |
| B | Methotrexate | 2R | 14.00 Mb | 13.82–14.38 Mb | 2.13 | 12% | r5 | Female fertility reduction (ovary atrophy) |
| C | Methotrexate | 3L | 3.42 Mb | 2.79–3.84 Mb | 3.50 | 19% | r5 | Female fertility reduction (ovary atrophy) |
| D | Methotrexate | 3L–3R | 22.24 Mb (3L) | 3L:17.76–3R:5.85 Mb | 1.92 | 10% | r5 | Female fertility reduction (ovary atrophy) |
| — | Malathion | 2R | 12,294,089 bp | 10,966,645–13,213,848 bp | — | 344 genes | r6 | Adult survival (~95% baseline mortality) |
| — | Malathion | 3L | 6,162,469 bp | 5,515,636–6,735,645 bp | — | 145 genes | r6 | Adult survival (~95% baseline mortality) |
| A | Zinc | X | 13,945,053 bp | 13,796,451–14,093,253 bp | — | 21 genes | r6 | Larval survival (~90% baseline mortality) |
| B | Zinc | 2L | 7,135,043 bp | 6,829,342–7,325,061 bp | — | 58 genes | r6 | Larval survival (~90% baseline mortality) |
| C | Zinc | 2R | 15,413,541 bp | 15,116,465–15,886,141 bp | — | 88 genes | r6 | Larval survival (~90% baseline mortality) |
| D | Zinc | 3L | 8,925,893 bp | 8,352,067–9,512,583 bp | — | 166 genes | r6 | Larval survival (~90% baseline mortality) |
| E | Zinc | 3R | 18,864,745 bp | 18,717,419–18,987,824 bp | — | 30 genes | r6 | Larval survival (~90% baseline mortality) |
| F | Zinc | 3R | 23,906,956 bp | 23,458,263–24,716,284 bp | — | 190 genes | r6 | Larval survival (~90% baseline mortality) |
| G | Zinc | 3R | 30,848,984 bp | 30,368,845–31,020,051 bp | — | 78 genes | r6 | Larval survival (~90% baseline mortality) |
| A | Caffeine | X | 3,716,075 bp | 2,916,075–4,736,075 bp | 5.36 | 131 genes | r6 | Adult female longevity on 1% caffeine |
| B | Caffeine | 2L | 3,370,610 bp | 3,030,610–4,290,610 bp | 4.72 | 137 genes | r6 | Adult female longevity on 1% caffeine |
| C | Caffeine | 2L | 11,730,610 bp | 10,710,610–12,170,610 bp | 4.59 | 187 genes | r6 | Adult female longevity on 1% caffeine |
| D | Caffeine | 2R | 10,848,099 bp | 10,628,099–11,168,099 bp | 13.10 | 51 genes | r6 | Adult female longevity on 1% caffeine |
| E | Caffeine | 3L | 13,108,478 bp | 12,328,478–16,368,478 bp | 4.99 | 463 genes | r6 | Adult female longevity on 1% caffeine |
| F | Caffeine | 3R | 14,067,353 bp | 13,447,353–14,347,353 bp | 8.81 | 105 genes | r6 | Adult female longevity on 1% caffeine |
| G | Caffeine | 3R | 26,287,353 bp | 25,707,353–27,007,353 bp | 6.77 | 144 genes | r6 | Adult female longevity on 1% caffeine |

**Total QTLs: 24** across 5 studies / 6 drug treatments.

---

## Phenotype Summary

| Study | Drug | Life Stage | Exposure | Phenotype Measured | QTL Count |
|-------|------|-----------|----------|-------------------|-----------|
| Chemotherapy (PMC4174942) | Gemcitabine & Carboplatin | Adult female | Dietary | Female fertility loss; degree of ovary atrophy and/or recovery after drug-induced mitotic arrest in ovaries | 4 (2 per drug) |
| Chemotherapy (PMC3737169) | Methotrexate | Adult female | Dietary | Female fertility loss; degree of ovary atrophy and/or recovery after drug-induced mitotic arrest | 4 |
| Malathion (PMC9713458) | Malathion (organophosphate) | Adult | Contact/dietary | Survival at ~95%-lethal dose | 2 |
| Zinc (PMC12606420) | Zinc oxide | Larval | Dietary | Survival at ~90%-lethal dose in larvae | 7 |
| Caffeine (PMC8893256) | Caffeine | Adult female | Dietary (activity monitors) | Longevity on 1% caffeine; recovered longest-surviving 10% | 7 |

---

## Note on Coordinate Conversion

Release 5 and release 6 of the *D. melanogaster* genome are not simply offset from each other — there are structural rearrangements, remapped contigs, and coordinate shifts that differ by chromosome arm and region. Tools to convert between them:

- **FlyBase Coordinate Converter**: https://flybase.org/convert/coordinates — can convert individual positions or BED-format intervals from r5 to r6
- **UCSC liftOver**: chain files for dm3→dm6 are available (dm3 ≈ r5, dm6 = r6)

The r5 QTL intervals in the chemotherapy papers are fairly wide (hundreds of kb to Mb), so liftOver conversion is feasible and the intervals would remain interpretable after conversion. Of potential interest: the Methotrexate QTL A on X (~13.85 Mb r5) may overlap with the Zinc QTL A on X (~13.9 Mb r6).

---

## Sources

| Study | Drug(s) | PMC Link |
|-------|---------|----------|
| PMC4174942 | Gemcitabine, Carboplatin | https://pmc.ncbi.nlm.nih.gov/articles/PMC4174942/ |
| PMC3737169 | Methotrexate | https://pmc.ncbi.nlm.nih.gov/articles/PMC3737169/ |
| PMC9713458 | Malathion | https://pmc.ncbi.nlm.nih.gov/articles/PMC9713458/ |
| PMC12606420 | Zinc oxide | https://pmc.ncbi.nlm.nih.gov/articles/PMC12606420/ |
| PMC8893256 | Caffeine | https://pmc.ncbi.nlm.nih.gov/articles/PMC8893256/ |
