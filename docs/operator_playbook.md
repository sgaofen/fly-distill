# Operator playbook — running the 14k production batch

## TL;DR — one command

```bash
cd /Users/stephenyu/fly-distill
python3 src/run_production.py gene_lists/all_14k.txt
```

Walk away. Come back ~30 hours later to a complete atlas.

## What happens

1. **Supervisor process** (`run_production.py`) starts and stays running.
2. It spawns two long-running children:
   - **`pipeline.py`** — fetches each gene's bundle, distills via GLM-5.1, canonicalizes, writes `output/genes/<FBgn>.json`. 10-concurrent z.ai quota.
   - **`qa_monitor.py`** — polls for new canonical files, runs tier-1 deterministic checks + tier-2 GLM self-audit on flagged genes.
3. Heartbeat every 60s prints progress to stdout.
4. **Crash recovery is automatic** at every level:
   - Per-gene idempotency: if `output/genes/<FBgn>.json` exists, both scripts skip it
   - Per-process supervisor: if pipeline or monitor crashes, supervisor restarts with exponential backoff (5s → 60s)
   - Per-call quota wait: if z.ai returns 429/1302, rate_limiter pauses all workers for 5min, polls back
5. Graceful Ctrl-C: SIGTERM → children drain in-flight work → supervisor saves state → exit.

## Files produced

```
output/genes/<FBgn>.json          14000 canonical records
output/index/fly_distill.sqlite   ~150 MB SQLite with FTS5
output/qa/tier1_report.jsonl      14000 deterministic QA records
output/qa/tier2_audit_results.jsonl  ~700 GLM-audited records
runs/prod_<timestamp>/             per-batch logs (pipeline.log, monitor.log, glm_calls.jsonl, failures.jsonl)
```

## Pre-flight checks (5 min before running)

```bash
# 1. Bulk databases present
ls -lh data/flybase_bulk/genes/ data/mgi/ data/hpo/

# 2. API keys configured
grep ZAI_API .env | head -2

# 3. Quota currently available (single ping)
python3 -c "
import subprocess, json
r = subprocess.run(['/usr/bin/curl', '-s', '-X', 'POST',
  'https://api.z.ai/api/anthropic/v1/messages',
  '-H', 'x-api-key: $(grep ZAI_API_KEY .env | head -1 | cut -d= -f2)',
  '-H', 'anthropic-version: 2023-06-01',
  '-H', 'Content-Type: application/json',
  '-d', '{\"model\":\"glm-5.1\",\"max_tokens\":5,\"messages\":[{\"role\":\"user\",\"content\":\"ping\"}]}'],
  capture_output=True, text=True)
print(r.stdout[:200])
"

# 4. Gene list prepared
wc -l gene_lists/all_14k.txt    # should be ~14000 lines, FBgn per line

# 5. Disk space (need ~3 GB free)
df -h .
```

## Monitoring during the run

In a second terminal:

```bash
# real-time progress
python3 src/run_production.py --check

# tail pipeline activity
tail -f runs/prod_*/pipeline.log

# tail monitor activity
tail -f runs/prod_*/monitor.log

# detailed per-gene LLM calls
tail -f runs/prod_*/glm_calls.jsonl | jq -r 'select(.ok==false) | "\(.fbgn) \(.error // .http_code)"'

# failures only
tail -f runs/prod_*/failures.jsonl
```

## Known failure modes & responses

| Symptom | Cause | Auto-handled? | Manual action |
|---|---|---|---|
| Worker logs "got 0 bytes, retry N/5" | FlyBase WAF transient | ✓ retries with backoff up to 5x | wait |
| Worker logs "quota-exhausted signal — pausing" | z.ai 5h window full | ✓ pauses all, polls every 5min | wait — auto resumes |
| `pipeline.log` shows traceback | Python uncaught exception | ✓ supervisor restarts | check stack trace if recurring |
| `monitor.log` shows "no new files" | Pipeline ahead of monitor backlog | ✓ monitor sleeps + polls | wait |
| qa_score < 70 for >5% of genes | Distill prompt may need tightening | ✗ manual | inspect samples, consider re-running with v2 prompt |
| Disk filling | Per-gene cache + run logs accumulate | ✗ manual | rotate logs, prune `data/cache/` if confident |

## If something looks really wrong

1. **Check process state**: `ps aux | grep -E "pipeline|monitor|run_production"`
2. **Sample a canonical file**: `cat output/genes/$(ls output/genes/ | tail -1) | jq .symbol,.bullets[0]`
3. **Read recent failures**: `tail runs/prod_*/failures.jsonl | jq`
4. **Kill cleanly**: `kill -TERM $(pgrep -f run_production.py)` — supervisor handles draining
5. **Re-run is safe**: same command picks up where it left off (idempotency)

## What to do AFTER batch finishes

```bash
# Build SQLite + indices
python3 src/build_sqlite.py
python3 src/build_indices.py

# Verify schema across all genes
python3 src/validate_schema.py

# Browse stats
python3 src/lookup.py stats

# Spot-check 10 random genes manually
for g in $(ls output/genes/ | sort -R | head -10); do
  python3 src/lookup.py gene "${g%.json}"
done

# Examine the Tier-2 audits that flagged anything
jq -r 'select(.audit.verdict != "accept") | "\(.fbgn) \(.audit.verdict)"' output/qa/tier2_audit_results.jsonl | head -20
```

## Opus deep-audit for problem genes (using my Max 20x via Agent tool)

If tier-2 GLM flags a gene as `redistill` or you spot something suspicious, the
flow is:

1. You bring the gene to my attention in chat (e.g. "audit FBgn0003068")
2. I spawn an `Agent tool` subagent with the audit prompt
3. The subagent runs as a fresh Opus 4.7 session under your Max 20x quota
4. Returns structured audit JSON in ~70-200 seconds

Cost: ~80K tokens per audit × ~50-100 audits = well within Max 20x weekly quota.
**You never need to manage this manually** — it's just me using the Agent tool
when you flag something or when monitor flags a redistill verdict.

## Sanity test before going full 14k

Recommended one-time dry run on 50 genes (~2 hours):

```bash
# pick 50 genes spanning tiers
shuf -n 50 gene_lists/all_14k.txt > gene_lists/dry_run_50.txt

python3 src/run_production.py gene_lists/dry_run_50.txt --batch-id dry_run

# after ~2 hours
python3 src/run_production.py --check
python3 src/lookup.py stats
python3 src/qa.py tier1
```

If 50-gene dry run is clean → confident to launch full 14k.
