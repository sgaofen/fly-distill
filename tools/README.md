# flyatlas — fly-distill atlas browser, CLI, agent skill, and semantic search

Four ways to consume the 14k-gene phenotype atlas built by the fly-distill pipeline:

1. **Web UI** — local academic browser (FlyBase-style: dense, link-heavy)
2. **CLI** — terminal queries, JSON export
3. **Agent skill** — drop into `~/.claude/skills/` for autonomous Claude agents
4. **REST API** — `/api/*` for programmatic clients

All four sit on top of:
- `atlas.db` — SQLite + FTS5 + chr/start/end indexed (~250 MB, built from `output/genes/*.json`)
- `embeddings.npz` — Gemini `gemini-embedding-2` over 14019 genes (~152 MB, 3072 dim)

---

## Setup

```bash
# install once
pip install fastapi uvicorn jinja2 numpy
# 1) build SQLite index (~90s)
python -m flyatlas.build
# 2) build Gemini embeddings (~10min, $1.50 — requires GEMINI_EMBEDDING_API_KEY in .env)
python -m flyatlas.embed_build
```

---

## Web UI

```bash
python -m flyatlas.cli serve     # default 127.0.0.1:8765
```

| Route | What |
|---|---|
| `/` | Atlas overview + entry points |
| `/gene/{fbgn|symbol|synonym}` | Single gene full detail |
| `/search?q=` | **Semantic search (default)** with optional region filter; `?mode=keyword` for FTS5 |
| `/ask?q=&region=` | Hybrid: region filter ∘ semantic phenotype rank (QTL fine-mapping page) |
| `/browse/category/{cat}` | All genes with bullets in a phenotype category |
| `/browse/tissue/{name}` | All genes tagged with a tissue |
| `/browse/disease/{omim_or_name}` | All genes modeling a disease |
| `/browse/ortholog/{symbol}` | Fly genes orthologous to a human/mouse symbol |
| `/browse/paper/{FBrf_or_PMID}` | All genes citing a paper |
| `/api/*` | JSON API for all of the above + `/api/region/{chr:start-end}`, `/api/semantic?q=&region=` |

---

## CLI

```bash
flyatlas --help
```

| Command | What |
|---|---|
| **`search <query>`** | **Default: semantic (Gemini). Add `--keyword` for FTS5.** |
| **`ask <query> --region <chr:start-end>`** | **Hybrid: region ∘ semantic rank (QTL workflow)** |
| **`semantic <query>`** | Pure semantic over whole atlas |
| **`region <chr:start-end>`** | Genes in a region |
| **`regions <input.bed>`** | Batch region query from BED file |
| **`export-bed`** | Dump every gene's chr/start/end (for bedtools intersect) |
| `gene <id>` | Show one gene |
| `disease <OMIM_or_name>` | Fly models of a disease |
| `ortholog <symbol>` | Fly orthologs of human/mouse gene |
| `paper <FBrf_or_PMID>` | Genes citing a paper |
| `tissue <name>` | Genes tagged with a tissue |
| `category <cat>` | Genes with bullets in a phenotype category |
| `stats` | Atlas-wide stats |
| `serve` | Launch the Web UI |

Every command accepts `--json` for piping. Examples:

```bash
# QTL fine-mapping: rank candidates in a region by phenotype
flyatlas ask "pupa height pupariation behavior" --region 2L:5e6-6e6 --limit 10

# semantic search across whole atlas
flyatlas search "alcohol sensitivity ethanol response" --limit 5
#   #1 = Adh (Alcohol dehydrogenase) — no keyword match required

# batch QTL peaks → genes
flyatlas regions qtl_peaks.bed --out genes_per_peak.tsv

# export all 14k coordinates for bedtools
flyatlas export-bed --format bed --out all_genes.bed
bedtools intersect -a my_qtl_peaks.bed -b all_genes.bed -wa -wb

# standard lookups
flyatlas gene chico
flyatlas disease 254100
flyatlas ortholog IRS1
flyatlas paper FBrf0210226
```

### Shell alias (recommended)

```bash
# ~/.zshrc or ~/.bashrc
alias fly='python -m flyatlas.cli'
```

---

## Agent skill (Claude)

Copy `skill/SKILL.md` into `~/.claude/skills/fly-atlas/SKILL.md` so any Claude
session running on this machine can invoke the atlas autonomously:

```bash
mkdir -p ~/.claude/skills/fly-atlas
cp skill/SKILL.md ~/.claude/skills/fly-atlas/SKILL.md
```

The skill teaches the agent:
- when the atlas is the right tool (Drosophila gene questions, phenotype-to-gene lookups, QTL region fine-mapping)
- when to use **semantic** (vague/novel phenotypes) vs **keyword** (exact phrases/alleles)
- which CLI verb to choose for each query type
- how to chain commands (e.g., disease lookup → per-gene detail; region → semantic rank → gene drill-in)
- when to prefer `--json` (programmatic) vs default (human-readable) output

---

## Semantic search internals

- **Build**: `python -m flyatlas.embed_build` runs Gemini `gemini-embedding-2` over each gene's concatenated text (`symbol + summary + every bullet + notes`, capped to 7000 chars). Output: `embeddings.npz` with `(N, 3072)` float32 matrix, L2-normalized.
- **Storage**: single numpy `.npz` file, ~152 MB on disk. Loaded once into RAM at server startup (~1s).
- **Query**: user query text → Gemini API → 1 vector → cosine similarity vs all 14k → top-K. Total per query: ~50ms + 1 Gemini API call (~10–30 tokens, ≈ $0.000003).
- **Cost**: build $1.50 (one-shot). Each search $0.000003.

---

## Architecture (one slide)

```
output/genes/*.json
       │
       ├─[build.py]─►  atlas.db (SQLite + FTS5 + chr/start/end)
       │
       └─[embed_build.py]─► embeddings.npz (14019 × 3072, Gemini)
                                       │
              ┌────────────────────────┼────────────────────────┐
              ▼                        ▼                        ▼
            cli.py                server.py                 skill (agent)
        (terminal)              (Web UI + REST)          (autonomous)
                          \____query.py + embed_query.py____/
                                (shared data layer)
```

`query.py` is the structured SQLite layer; `embed_query.py` is the embedding /
region / hybrid layer. CLI, Web UI, REST API, and skill all share the same two
modules — schema is stable across consumers.
