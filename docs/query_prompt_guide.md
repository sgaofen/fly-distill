# Query-prompt guide for QTL fine-mapping

How to write semantic-search query strings that surface the right candidate
genes from a QTL interval, **without needing to read the paper that maps the
QTL**. Tested across 4 QTLs against paper-validated anchor genes; achieves
~87 % recall on in-interval anchors.

---

## Why this matters

If you run `flyatlas ask` with a phenotype string copied verbatim from a QTL
mapping paper (e.g. `"Larval survival (~90 % baseline mortality)"`), the
embedding will return whatever genes are semantically close to *generic
lethality* — chromatin remodelers, apoptosis effectors, anything that kills
a larva when knocked out. **You will not get the genes specifically protective
against the chemical being tested.**

The fix is to write the query at the level the embedding can match: **specific
chemical / pathway / enzyme-family tokens**. The trick is that you do *not*
need the QTL paper to write these. Drug pharmacology is taught in undergrad
biochem; the relevant token set comes straight from the textbook.

---

## The template

A good QTL query is a flat keyword bag of **12–15 tokens**, laid out along
the causal chain from compound to protection:

```
1. Compound name (exact, e.g. "zinc chloride", "malathion")
2. Chemical class                 ("heavy metal", "organophosphate", "methylxanthine")
3. Primary molecular target       (the enzyme / receptor the drug binds)
4. Top-level concept              ("xenobiotic detoxification", "DNA damage")
5. Specific protective gene families
                                   (Cyp450 / GST / UGT / ABC transporter
                                    / metallothionein / DNA-repair / etc.)
6. Downstream damage type         ("oxidative stress", "stalled fork",
                                    "neuromuscular excitotoxicity")
7. Protective response mechanism  ("repair", "chaperone", "efflux",
                                    "antioxidant", "buffering")
```

Skip anything you don't know — embedding rewards specific tokens, doesn't
penalise gaps. **Never use full sentences or narrative wrapping** (`"Best
candidate genes confer protection against..."`); the connective tissue
dilutes the specific-term signal.

---

## Worked examples

Each prompt below was written from the drug name + chemical pharmacology
alone, **without reading the QTL paper**. The recall percentage compares
the prompt's top-7 candidates against the paper's experimentally validated
gene list.

### Zinc — `zinc_D`

```
zinc chloride heavy metal homeostasis metallothionein ZIP ZnT
transporter oxidative stress mitochondrial
```

| Token | Causal-chain slot |
|---|---|
| `zinc chloride` | compound |
| `heavy metal` | chemical class |
| `homeostasis` | what Zn toxicity disrupts |
| `metallothionein` | canonical Zn-scavenging protein family |
| `ZIP` | SLC39 zinc importers |
| `ZnT` | SLC30 zinc efflux transporters |
| `transporter` | umbrella for both |
| `oxidative stress` | downstream damage |
| `mitochondrial` | primary damage site |

Recovery: **3 of 4 anchors** (`foi`, `MTF-1`, `Hsp22`; missed `GluRIB`).

### Caffeine — `caffeine_D`

```
caffeine methylxanthine adenosine receptor phosphodiesterase
cytochrome P450 xenobiotic ABC transporter UGT glucuronidation
oxidative stress
```

| Token | Causal-chain slot |
|---|---|
| `caffeine` | compound |
| `methylxanthine` | chemical class |
| `adenosine receptor` | primary pharmacological target (antagonist) |
| `phosphodiesterase` | secondary target (PDE inhibition) |
| `cytochrome P450` | Phase I detoxification |
| `xenobiotic` | umbrella concept |
| `ABC transporter` | drug efflux |
| `UGT` | Phase II conjugation enzyme family |
| `glucuronidation` | the reaction Phase II performs |
| `oxidative stress` | chronic-exposure damage type |

Recovery: **3 of 3 anchors** (`Cyp12d1-d`, `Cyp12d1-p`, `Prosβ5`).

### Malathion — `malathion_A`

```
malathion organophosphate acetylcholinesterase AChE inhibitor
xenobiotic detoxification cytochrome P450 carboxylesterase
ABC transporter efflux
```

| Token | Causal-chain slot |
|---|---|
| `malathion` | compound |
| `organophosphate` | chemical class |
| `acetylcholinesterase` / `AChE` | the enzyme malathion inhibits |
| `inhibitor` | toxicity mechanism |
| `xenobiotic detoxification` | umbrella |
| `cytochrome P450` | Phase I metabolism of OPs |
| `carboxylesterase` | OP-specific hydrolase |
| `ABC transporter` | drug efflux |
| `efflux` | the action itself |

Recovery: **5 of 6 anchors** (`Cyp12d1-d`, `Cyp12d1-p`, `Cyp6g1`, `Cyp6g2`,
`Mdr49`; missed `Mdr65`).

### Methotrexate — `methotrexate_A`

```
methotrexate dihydrofolate reductase DHFR inhibitor folate antagonist
thymidylate synthesis DNA replication stalled fork DNA damage repair
```

| Token | Causal-chain slot |
|---|---|
| `methotrexate` | compound |
| `dihydrofolate reductase` / `DHFR` | direct target enzyme |
| `inhibitor` | mechanism |
| `folate antagonist` | drug class |
| `thymidylate synthesis` | downstream block (no dTMP) |
| `DNA replication` | what stalls |
| `stalled fork` | specific lesion |
| `DNA damage` | fork collapse → DSB |
| `repair` | protective response |

Recovery: **2 of 2 anchors** (`DNAlig4`, `mus101`).

---

## Empirical baseline

The four prompts above, evaluated against paper-validated anchor genes for
each QTL:

| QTL              | keyword | multi-axis | possible |
|------------------|--------:|-----------:|---------:|
| `zinc_D`         |    3    |     3      |    4     |
| `caffeine_D`     |    3    |     3      |    3     |
| `malathion_A`    |    5    |     5      |    6     |
| `methotrexate_A` |    2    |     2      |    2     |
| **total**        | **13/15** | **13/15** | (87 %) |

The keyword-bag approach matches Long's multi-axis decomposition (15 separate
axis queries derived from reading the paper) **exactly**. The extra
information from the paper does not add recall beyond what textbook-level
chemical pharmacology tokens already produce.

---

## What the keyword approach cannot do

The remaining ~13 % gap (e.g. `GluRIB` on `zinc_D`, `Mdr65` on `malathion_A`)
is composed of genes the paper validated through **novel, paper-specific
mechanisms**. `GluRIB` is a glutamate receptor; the zinc paper's contribution
was the discovery that NMJ-glutamate signaling matters for chronic zinc
tolerance — that connection is not in any textbook and is not in the gene's
FlyBase annotation (which has only the canonical NMJ / circadian / disease-
model description). No pre-experiment query can surface what the paper itself
discovered.

For those, the only path is to read the paper after publication and inject its
findings back into the atlas (see `src/inject_qtl_paper.py` if implemented).

---

## Quick checklist for writing a new QTL prompt

When given a new compound + phenotype:

1. Compound name as one token
2. Chemical class as one token
3. Wikipedia-or-textbook level pharmacology: what enzyme / receptor does the
   drug target?
4. List canonical detox routes for that compound class: Phase I (Cyp450),
   Phase II (GST / UGT), Phase III (ABC transporters)
5. Downstream damage type: oxidative / DNA / proteotoxic / mitochondrial /
   neuromuscular
6. Protective gene-family names you know the embedding will recognise

Aim for 12–15 tokens. No commas needed, no narrative.

Then `flyatlas ask "<prompt>" --region <qtl-interval>` and inspect top 7.
