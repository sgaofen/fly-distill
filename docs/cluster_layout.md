# Cluster data layout — fly QTL gene distillation

Production-scale (14k fly genes × cross-species data × multiple schema/model
iterations) lives on UCI HPC. This doc specifies the directory tree, file
formats, sharding, versioning, and audit/cost tracking conventions.

## Volume budget

| Layer | Size | Mutable? | Reproducible? |
|---|---|---|---|
| Raw source dumps (FlyBase TSV + Chado, PubMed XML baseline subset, MGI reports, OMIM cache, DIOPT ortholog tables) | **~80 GB** packed (≤ 300 GB unpacked) | No, immutable per release | Yes, re-downloadable |
| Per-gene bundles (fly+human+mouse fetched data) | **~3 GB** (14k × ~200 KB avg) | No, immutable after fetch | Yes, re-fetchable |
| Distilled outputs (canonical `genes/v{N}/*.json`) | **~150 MB** per schema version | No, never overwrite in-place | Costs $$ to regenerate |
| Indices (catalog, by_*, parquet, sqlite) | **~500 MB** per schema version | Yes, fully rebuildable from distilled | Yes, derived |
| Run artifacts (logs, glm_calls.jsonl, failure queues) | **~5–20 GB** over a year | Append-only | Audit data — keep |
| Project 1 BAM files (Peromyscus low-cov) | **~2–3 TB** | No | Yes, but expensive to re-sequence |
| Scratch / work | varies per SLURM job | Yes, deletable | Recreatable |

Total steady-state for **Project 2 (fly distillation)**: ~100 GB. Combined with
**Project 1 (Peromyscus BAMs)**: 2–3 TB. The user said "几个 TB" — that's
realistic if BAMs are colocated.

## Top-level layout

```
/pub/syu/fly-distill/                                      # lab partition root
├── raw/                                                   # immutable bulk source
│   ├── flybase/FB2026_01/
│   │   ├── precomputed/*.tsv.gz
│   │   ├── chado_xml_dump.gz
│   │   └── release_notes.txt
│   ├── pubmed/baseline_2026/{0001..1219}.xml.gz           # PubMed baseline
│   ├── pubmed/relevant_subset/*.xml.gz                    # only PMIDs from FlyBase pubs
│   ├── mgi/2026_01/*.rpt.gz
│   ├── omim/2026_01/api_cache/*.json                      # license-restricted
│   ├── diopt/v9.1/{fly,mouse,human}_orthologs.tsv.gz
│   └── alliance/2026_01/disease_associations.tsv.gz
│
├── bundles/                                               # per-gene fetched data, sharded
│   └── <2-char-shard>/<FBgn>/
│       ├── bundle.json                                    # the JSON we already use
│       ├── raw.html.gz                                    # FlyBase HTML snapshot, compressed
│       └── fetched_at.txt                                 # ISO timestamp
│
├── distilled/                                             # versioned output, append-only
│   ├── v1/
│   │   ├── schema.json                                    # frozen copy of distilled_gene_v1.schema.json
│   │   └── genes/<2-char-shard>/<FBgn>.json               # 14k canonical files
│   └── v2/                                                # when schema bumps
│       └── ...
│
├── indices/                                               # rebuildable, derived
│   ├── v1/
│   │   ├── catalog.jsonl                                  # 1 line / gene metadata
│   │   ├── bullets.jsonl                                  # 1 line / bullet (replaces bullets_flat.jsonl)
│   │   ├── bullets.parquet                                # columnar — duckdb/pandas analytics
│   │   ├── bullets.sqlite                                 # transactional — query API
│   │   └── inverted/
│   │       ├── by_category.json
│   │       ├── by_human_disease.json
│   │       ├── by_human_ortholog.json                     # entrez → FBgn list
│   │       ├── by_mouse_ortholog.json
│   │       └── by_phenotype_term.json                     # 'circadian' → 87 gene refs
│   └── v2/
│       └── ...
│
├── runs/                                                  # per-batch manifest + audit log
│   └── 2026-05-13_glm5-1_batch_001/
│       ├── manifest.json                                  # gene list, schema, model, harness
│       ├── glm_calls.jsonl                                # 1 line per LLM call: gene, req_id, tokens, $, status
│       ├── failures.jsonl                                 # retry queue
│       ├── slurm/                                         # SLURM stdout/stderr per array task
│       └── summary.md                                     # end-of-run human-readable report
│
├── code/                                                  # git-tracked, mirrors GitHub repo
│   └── src/, prompts/, docs/
│
└── work/                                                  # ephemeral SLURM scratch — auto-deleted
    └── ${SLURM_JOB_ID}/
```

## Sharding

Path: `bundles/<shard>/<FBgn>/`, `distilled/v1/genes/<shard>/<FBgn>.json`.

`<shard>` = first 2 hex chars of an md5 hash of the FBgn ID. 256 buckets, 14k
genes → ~55 genes per bucket. Avoids the filesystem-perf cliff that hits at
~10k files in one directory on `ext4` / `xfs`.

Sharding implementation: trivial — `shard = hashlib.md5(fbgn.encode()).hexdigest()[:2]`.

Example: `FBgn0003068 (per)` → md5 `2f1c...` → bucket `2f`.

## Schema versioning

- The schema definition lives in `distilled/v{N}/schema.json` as a **frozen
  snapshot** — never modify in place. When the bullet schema changes
  (additional field, stricter enum, etc.), bump to `v2` and write fresh
  `distilled/v2/genes/`. The old `v1` files stay readable forever.
- Each gene file embeds `"schema_version": "1.0"` so consumers can branch on it.
- Indices are also per-version: `indices/v1/` rebuilt from `distilled/v1/`,
  `indices/v2/` from `distilled/v2/`. Querying always specifies a version.

## Index store choices

| Format | When to use |
|---|---|
| **JSONL** (`catalog.jsonl`, `bullets.jsonl`) | Streaming, append-friendly, grep-able, language-neutral. The canonical wire format on cluster. |
| **Parquet** (`bullets.parquet`) | Analytics queries — "average bullets per category across the genome," embedding generation, joining with QTL hit tables. Read in seconds via duckdb/polars; no full-file load. |
| **SQLite** (`bullets.sqlite`) | Online query workflow — when Sarah's Python script asks "give me all bullets matching `phenotype LIKE '%locomotor%'` in genes within chr2L:5000000-5200000", we want a real index. SQLite + FTS5 is enough at our scale, no server needed. |
| **JSON inverted** (`by_category.json` etc.) | Cheap lookup tables for very-common queries when JSONL streaming is overkill. |

All three are **derived from `distilled/v{N}/`** and rebuildable. Never store
something in `indices/` that isn't reproducible.

## Run artifacts & cost ledger

Every batch (SLURM array job, manual run, retry sweep) writes to a fresh
`runs/<date>_<model>_<batch_id>/` directory:

### `manifest.json` (written first, before any LLM call)
```json
{
  "batch_id": "2026-05-13_glm5-1_batch_001",
  "started_at": "2026-05-13T18:42:00Z",
  "schema_version": "1.0",
  "model": "glm-5.1",
  "harness": "claude_code_headless",
  "gene_list": ["FBgn0003068", "FBgn0004647", ...],
  "code_git_sha": "a3f9e21",
  "operator": "syu"
}
```

### `glm_calls.jsonl` (append every LLM call)
```json
{"ts":"2026-05-13T18:42:14Z","fbgn":"FBgn0003068","key_idx":0,"req_id":"202605131842145e...","input_tokens":40667,"output_tokens":2250,"cache_read":19968,"elapsed_s":40.2,"http_code":200,"cost_usd":0.087}
{"ts":"2026-05-13T18:43:01Z","fbgn":"FBgn0004647","key_idx":1,"req_id":"...","input_tokens":99217,"output_tokens":3140,"elapsed_s":60.0,"http_code":200,"cost_usd":0.183}
```

- Grep failures: `jq 'select(.http_code != 200)' glm_calls.jsonl`
- Sum cost: `jq -s 'map(.cost_usd) | add' glm_calls.jsonl`
- Per-key fairness check: `jq -s 'group_by(.key_idx) | map({key: .[0].key_idx, n: length})' glm_calls.jsonl`

### `failures.jsonl` (retry queue)
Any non-200 or unparseable output gets appended here with attempt counter. A
nightly SLURM job re-tries entries with attempts < 3.

## SLURM access patterns

Worker pseudo-code (one fbgn per array index):

```python
shard = md5(fbgn)[:2]
bundle_path = f"/pub/syu/fly-distill/bundles/{shard}/{fbgn}/bundle.json"
out_path    = f"/pub/syu/fly-distill/distilled/v1/genes/{shard}/{fbgn}.json"
if out_path.exists():
    return                         # idempotent — skip if already done

bundle = load(bundle_path)
result = call_claude_headless(bundle, key=KEYS[task_id % len(KEYS)])
canonical = canonicalize(result, fbgn)
out_path.parent.mkdir(parents=True, exist_ok=True)
atomic_write(out_path, canonical)  # write to .tmp then rename
append_jsonl(run_dir/"glm_calls.jsonl", {fbgn, tokens, cost, ts, ...})
```

Idempotency = a re-run of the same SLURM array on the same gene list is a
no-op for already-completed FBgns. Critical for failure recovery.

Index rebuild is a single non-array SLURM job after the array completes:
```bash
python3 src/build_indices.py --schema-version v1 \
  --in /pub/syu/fly-distill/distilled/v1/genes/ \
  --out /pub/syu/fly-distill/indices/v1/
```

## Backup & retention

| Path | Strategy |
|---|---|
| `raw/` | Re-downloadable; no backup. Keep latest release + previous. |
| `bundles/` | Re-fetchable from FlyBase/PubMed. No backup but **don't delete during active run**. Can purge after `distilled/` is locked. |
| `distilled/v{N}/` | **Gold data**. Mirror to a 2nd cluster volume or cold storage (e.g. UCI Pure Storage), and a git LFS repo for the JSONs (small enough). |
| `indices/v{N}/` | Rebuildable. Don't back up. |
| `runs/` | Audit trail. Compress and archive to cold storage monthly. Keep raw `glm_calls.jsonl` for cost accountability. |
| `work/` | SLURM scratch — auto-purged. |

## How this scales

| Genes done | Distilled size | Indices size | LLM cost (GLM via Coding Plan) | LLM cost (direct API equivalent) |
|---|---|---|---|---|
| 6 (current pilot) | 80 KB | 100 KB | $0 marginal | ~$0.35 |
| 100 | ~1.5 MB | ~3 MB | $0 marginal | ~$6 |
| 1,000 | ~15 MB | ~30 MB | $0 marginal | ~$60 |
| 14,000 (full genome) | ~150 MB | ~500 MB | $0 marginal (within Coding Plan quota over a few weeks) | ~$800 |

The actual storage problem is **not** the LLM outputs — it's the raw caches
(PubMed XML, Chado dumps) and Project 1's Peromyscus BAMs. Distilled+indices
together stay well under 1 GB even at full genome scale.

## Migration plan (laptop prototype → cluster)

1. **Code freeze**: tag prototype `v0.1` in GitHub. No path-pattern changes after this.
2. **Bundle re-fetch on cluster**: institutional IP doesn't trip FlyBase WAF. Run `fetch_gene.py` over the full gene list, writing into sharded `bundles/`.
3. **Run distillation as SLURM array** with `--array=1-14000%20` (cap 20 concurrent — matches our 2-key quota ceiling).
4. **Build indices** as a single follow-up SLURM job.
5. **Hand off**: Sarah/Long get the SQLite + parquet for their workflow; we point Long lab's XQTL pipeline at the `query.py` interface.

## What stays on laptop

- Dev loop (modify prompt → test on 1–5 genes → iterate)
- Manual auditing
- Final paper writing
- Anything where ≤10 GB of data + interactive Claude Code feels better than SSH

## What moves to cluster

- Full-genome distillation runs
- Bulk dump caches that exceed laptop disk
- Peromyscus BAM analysis (Project 1)
- Anything that benefits from SLURM parallelism > 10
