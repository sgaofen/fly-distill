# flyatlas — fly-distill atlas browser, CLI, and skill

Three ways to consume the 14k-gene phenotype atlas built by the fly-distill pipeline:

1. **Web UI** — local academic browser (FlyBase-style: dense, link-heavy, low-chrome)
2. **CLI** — terminal queries, JSON export
3. **Skill** — drop into `~/.claude/skills/` so Claude agents can search the atlas autonomously

All three sit on top of one read-only SQLite (`atlas.db`) built once from `output/genes/*.json`.

---

## Setup (one-time, ~30s)

```bash
# from repo root
pip install fastapi uvicorn jinja2
python -m flyatlas.build         # ETL: output/genes/*.json → tools/atlas.db
```

This produces `tools/atlas.db` (~80 MB for 14k genes, FTS5 indexed).

---

## Web UI

```bash
python -m flyatlas.cli serve     # default 127.0.0.1:8765
```

Open <http://localhost:8765>. Pages:

| Route | What |
|---|---|
| `/` | Atlas overview + entry points |
| `/gene/{fbgn|symbol|synonym}` | Single gene full detail |
| `/search?q=` | FTS5 full-text search with filters |
| `/browse/category/{cat}` | All genes with bullets in a phenotype category |
| `/browse/tissue/{name}` | All genes tagged with a tissue |
| `/browse/disease/{omim_or_name}` | All genes modeling a disease |
| `/browse/ortholog/{symbol}` | Fly genes orthologous to a human/mouse symbol |
| `/browse/paper/{FBrf_or_PMID}` | All genes citing a paper |
| `/api/*` | Same routes as JSON for headless clients |

---

## CLI

```bash
python -m flyatlas.cli --help
```

| Command | What |
|---|---|
| `gene <id>` | Show one gene (FBgn / symbol / synonym auto-resolve) |
| `search "<query>"` | FTS5 search across summary + bullets |
| `disease <OMIM_or_name>` | List genes linked to a disease |
| `ortholog <symbol>` | List fly genes ortholog to a human/mouse gene |
| `paper <FBrf_or_PMID>` | List genes citing a paper |
| `tissue <name>` | Genes with bullets tagged with a tissue |
| `category <cat>` | Genes with bullets in a phenotype category |
| `stats` | Atlas-wide stats (genes, bullets, refs, backend split) |
| `serve` | Launch the Web UI |

Every command accepts `--json` for piping. Examples:

```bash
# quick lookup
python -m flyatlas.cli gene chico

# boolean search
python -m flyatlas.cli search "lethal AND eye" --confidence high

# disease panel as JSON
python -m flyatlas.cli disease 254100 --json > MDRP_fly_models.json

# everything orthologous to IRS1
python -m flyatlas.cli ortholog IRS1

# all genes citing the same paper
python -m flyatlas.cli paper FBrf0210226

# atlas-wide stats
python -m flyatlas.cli stats
```

### Shell alias (recommended)

```bash
# ~/.zshrc or ~/.bashrc
alias fly='python -m flyatlas.cli'
```

Then:

```bash
fly gene Notch
fly search "Z disc AND muscle" --json | jq '.[].symbol'
```

---

## Skill (for Claude agents)

Copy `skill/SKILL.md` into `~/.claude/skills/fly-atlas/SKILL.md` so any Claude
session running on this machine can invoke the atlas autonomously:

```
cp skill/SKILL.md ~/.claude/skills/fly-atlas/SKILL.md
```

The skill teaches the agent:
- when the atlas is the right tool (Drosophila gene questions, phenotype-to-gene lookups, fly disease models),
- which CLI command to choose for each query type,
- how to chain commands (e.g., disease lookup → per-gene detail),
- when to prefer `--json` (programmatic) vs default (human-readable) output.

---

## Architecture (one slide)

```
output/genes/*.json  ─[build.py]─►  atlas.db (SQLite + FTS5)
                                        │
              ┌─────────────┬───────────┼───────────────┐
              ▼             ▼           ▼               ▼
        cli.py         server.py     query.py       skill (agent)
        (terminal)     (Web UI)      (shared)       (autonomous)
```

`query.py` is the single read-only data layer. Everything else (CLI, Web,
Skill) calls into it — schema is stable across consumers.
