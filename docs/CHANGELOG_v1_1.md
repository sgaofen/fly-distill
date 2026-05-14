# Spec changelog — response to GPT review

GPT-Pro reviewed `spec_v1_1.md` and produced 26 numbered comments + 2 doc-style fixes.
This file triages each one and records what was actually changed.

---

## v1.1.1 — minimum fixes (DONE, applied 2026-05-14)

These are the items GPT classified as "minimum fixes" plus a few low-cost extras.

| # | GPT item | What changed | Where |
|---|---|---|---|
| 1 | "complete representation" overstated | Goal rewritten as "compact, evidence-linked distilled synopsis"; added a paragraph clarifying that raw FlyBase TSVs are the source-of-truth and the distilled JSON is the LLM-readable summary layer. | `docs/spec_v1_1.md` §0 |
| 2 | Citations schema not uniform | All citations now share `{type, value, [label, quote, section_enum, species]}` shape. `id`/`section`/`term`/`symbol` are GONE. JSON schema updated; `enrich.parse_citations` emits new shape; `build_sqlite.py` writes `(cite_type, cite_value)` directly with no per-type guessing. | schema + `enrich.py` + `build_sqlite.py` |
| 3 | `id` vs `bullet_id` mapping | Added explicit one-liner: "canonical JSON `bullets[].id` is the same key as SQLite `bullets.bullet_id` — copied during ingest." | `docs/spec_v1_1.md` §5 |
| 4 | SQL `d.disease_name` bug | Corrected to `d.name AS disease_name`. | `docs/spec_v1_1.md` §4 |
| 7 | `confidence` rule | Schema explicitly: confidence is REQUIRED but may be null. Missing → canonicalizer fills null + emits `schema_drift.missing_confidence` structured lint. Auto-retry already implemented in pipeline.py. | schema + `canonicalize.py` |
| 8 | `_lint` should be structured | `_lint[]` is now array of `{code, severity, message, path, stage, n_affected}` objects. Codes: `schema_drift.missing_confidence`, `category.coerced`, `direction.invalid`, `confidence.invalid`, `phenotype.too_short`, `evidence.missing`, etc. `pipeline.has_schema_drift()` updated to recognize both old-string and new-dict forms. | schema + `canonicalize.py` + `pipeline.py` |
| 9 | `specificity` misnamed | Renamed to `text_specificity` everywhere (schema, canonicalizer, SQLite, lookup CLI). Schema description explicitly: "surface textual specificity only; not evidence quality or biological confidence." | schema + `enrich.py` + `canonicalize.py` + `build_sqlite.py` + `lookup.py` |
| 16 | FTS5 NEAR syntax wrong | Corrected to `NEAR(memory consolidation, 5)` (token list before distance, not infix). Verified working on lookup CLI. | `docs/spec_v1_1.md` §4 |
| 26 | §10 self-contradiction (LLM-free vs `glm_rank` LLM call) | Added explicit "Exception: glm_rank reranker calls LLM at query-time" clarification. | `docs/spec_v1_1.md` §10 |
| Doc #1 | "Full sample" had `... 22 more bullets ...` placeholder | Retitled "Excerpt — one gene's canonical record (period)"; pointer to full file at `output/genes/FBgn0003068.json` added. | `docs/spec_v1_1.md` §5 |
| Doc #2 | "GPT-5 reviewer" audience wording | Changed to "technical / LLM reviewer + future maintainers + Prof. Long". | `docs/spec_v1_1.md` header |
| Doc #3 | `distill_via_claude.py` model confusion | Appendix A note clarifying Claude Code is just the harness, GLM-5.1 is the actual model invoked via env-routed Anthropic-compat endpoint. | `docs/spec_v1_1.md` Appendix A |

---

## v1.2 — deferred to next iteration (NOT YET DONE)

These are GPT items that require new data fields, new fetch logic, or larger
test cycles. Recording them here so they're not lost.

| # | GPT item | Why deferred | Plan |
|---|---|---|---|
| 5 | Reproducibility metadata (bundle_sha256, prompt_sha256, git commit, sub-objects for `model`) | Cheap to add but should be done in one batch alongside production run | Add to canonicalize.py before next 14k-gene batch |
| 6 | Reference selection strategy spec | Need to actually decide the strategy first | Write `docs/reference_selection.md` first, then implement |
| 10 | Split `confidence` into `evidence_strength` + `model_confidence` | Requires prompt redesign + re-distillation across all genes | Save for v2 schema |
| 11 | Tissues/stages normalized with FBbt/FBdv ontology IDs | Requires loading FBbt + FBdv obo files + lookup table | Add to enrich.py as Stage 2 of normalization |
| 12 | `category` as multi-label (`primary_category` + `categories[]`) | Requires prompt change + re-distillation | v2 schema |
| 13 | Rename `go` → `go_slim` + plan for full GO IDs | Field rename now is easy but consumers downstream haven't been built yet; defer to coordinate | v1.2 rename + add `go_full` field once `gene_ontology.tsv` is parsed |
| 14 | `mouse_phenotype_links` → richer object with MP IDs | Requires parsing MGI `MGI_PhenoGenoMP.rpt` | v1.2 with mouse enrichment |
| 15 | Disease links: add `via_ortholog` field | Easy to do — FlyBase bulk has the ortholog → disease mapping inline; just need to thread it through | v1.2 — small task |
| 17 | Tissue normalization for SQLite query (avoid leading `%X%` wildcards) | Same as #11 — depends on FBbt ID adoption | v1.2 |
| 18 | Multi-hit ortholog ranking on `gene` lookup | UX issue, not data issue | Fix in lookup.py — easy |
| 19 | `gene_synonyms` synonym type column | Need to parse synonym_type from FlyBase bulk | v1.2 with synonym table refactor |
| 20 | Production QA protocol (stratified sample 1%, thresholds) | Need production-scale data to define thresholds | Defer until after first 14k run |
| 21 | Three-layer auditor (citation exists → lexical overlap → entailment) | Larger work; current auditor is `audit.py` v0.5 | v2 audit suite |
| 22 | Use `jsonschema` library + separate domain linter | Drop-in replacement | v1.2 — small task |
| 23 | Global FBrf abstract cache `data/cache/fbrf/<FBrfID>.json` | Need to refactor fetcher to dedupe across genes | v1.2 before 14k production run — high priority for cost/quota |
| 24 | Runtime / cost budget table | Pure documentation | Add to spec §6 in v1.2 |
| 25 | Pipeline state machine docs | Pure documentation | Add to spec §1 in v1.2 |
| Doc #4 | Licensing / data-use section for OMIM/HPO/FlyBase | Pure documentation | Add to spec §11 in v1.2 |

---

## What v1.1.1 looks like in numbers

- 6 genes re-canonicalized; all 6 PASS structurally (1 WARN on ebony — same as before).
- SQLite rebuilt; 160 bullets, 136 citations, 77 tissue tags, 41 diseases.
- `_lint` for ebony is now structured (1 dict object) instead of unstructured string.
- All citations now uniform shape — `bullet_citations` table writes are now type-safe.
- `text_specificity` rename complete across spec + schema + 4 code files.
- All 12 lookup CLI subcommands re-tested PASS.

---

## How to apply this to GPT for re-review

Send GPT both files in this order:

1. `docs/CHANGELOG_v1_1.md` (this file) — so they see the response to their review
2. `docs/spec_v1_1.md` — the patched spec
3. `output/schema/distilled_gene_v1_1.schema.json` — the patched schema
4. `output/genes/FBgn0003068.json` — a working example with the new fields

If they want to verify the citations refactor end-to-end:

5. `src/enrich.py` — emits the new shape
6. `src/build_sqlite.py` — ingests the new shape
