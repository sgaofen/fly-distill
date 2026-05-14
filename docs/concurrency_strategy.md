# Concurrency strategy — handling sub-agent fan-out + external contention

## The four real problems

1. **Hard ceiling 10**: z.ai rejects calls 11+ with HTTP 429 + error code `1302`.
2. **Sub-agent fan-out**: a Claude Code headless session may internally spawn
   1–2 sub-agents (Task tool). Each sub-agent is another LLM call against the
   same quota. So one "session" can cost up to 3 concurrent slots.
3. **External contention**: the user is running their own Claude Code session
   in parallel (talking to Claude) and also hits the same Coding Plan quota.
   We can't see those calls directly.
4. **Recovery from 429**: when contention spikes, we must back off — not retry
   immediately — and slowly recover.

## How the limiter handles each

### Sub-agent fan-out → per-call weight

| Caller | Weight | Reason |
|---|---|---|
| Direct API call (`distill.py`) | 1 | One LLM call, no sub-agents possible |
| Claude Code harness (`distill_via_claude.py`) | 3 | 1 main + estimated up to 2 sub-agents |
| Two-pass distillation (`distill_two_pass.py`) | 3 per pass (serial) | Each pass is one Claude Code session |

A worker doing Claude-Code distill takes 3 slots from the budget. The pipeline
will only start 8/3 ≈ 2-3 such workers concurrently when running in harness mode.

### External contention → ZAI_RESERVE_SLOTS

Default: reserve 2 slots for the user. Pipeline only uses 8 of the 10.

If the user wants more headroom (e.g. they're doing heavy interactive work
in another Claude Code session):

```bash
ZAI_RESERVE_SLOTS=4 python3 src/pipeline.py gene_list.txt
```

→ pipeline uses 6 slots, leaves 4 for user.

If running unattended overnight with no other usage:

```bash
ZAI_RESERVE_SLOTS=0 python3 src/pipeline.py gene_list.txt
```

→ pipeline uses 10.

### Adaptive 429 backoff

When any worker sees HTTP 429 or error code `1302`:

```python
budget.report_429()
```

The limiter:
1. Drops `effective_cap` by 1 (down to 1 minimum)
2. Refuses to start new work until existing work drains below new cap
3. Records timestamp for the recovery timer

Recovery is timer-based, not success-based (avoids oscillation):
- Every `ZAI_RECOVERY_INTERVAL_S` (default 60s)
- If no 429s in the last 60s → bump `effective_cap` by 1
- Stops at `initial_cap` (max - reserve)

This means a contention spike causes a graceful drop then slow recovery,
never a stuck-throttled state.

## Concrete scenarios

### Scenario A: pure pipeline run (no user interaction)

```
ZAI_RESERVE_SLOTS=0
harness=direct (weight=1)
14,000 genes
```

- 10 workers concurrent
- ~45s per gene at full saturation
- ~17.5h wall-clock total

### Scenario B: pipeline + user using Claude Code in another window

```
ZAI_RESERVE_SLOTS=2  (default)
harness=claude (weight=3)
14,000 genes
```

- 8/3 ≈ 2-3 pipeline workers concurrent (each consuming 3 slots)
- User has 2 slots free for their own Claude Code session
- Pipeline is slower: ~50-60s per gene, ~3 concurrent → ~78h wall-clock
- BUT user can keep working

### Scenario C: pipeline + accidental external one-off `claude` invocation

The external `claude` call doesn't go through our budget — but z.ai will return
429 for our worker when contention hits 10. We catch it:

```python
# inside worker
with budget.acquire(weight=3, label=fbgn):
    resp = call(...)
    if is_rate_limit_response(resp):
        budget.report_429()       # cap drops by 1
        # next iteration retries — by then the external call should have completed
```

After the external call finishes, our cap auto-recovers in ~60s.

### Scenario D: night-time bulk run, peak-hour caution

z.ai docs mention 14:00–18:00 Beijing time (= 22:00–02:00 California) is peak;
quota is debited at 3× rate during peak. Don't have separate concurrency
constraint, but be conservative:

```bash
# during peak hours
ZAI_INITIAL_CONCURRENCY=5 python3 src/pipeline.py
```

The 60s recovery interval will gradually expand if 429s stay quiet.

## Knobs (environment variables)

| Var | Default | Effect |
|---|---|---|
| `ZAI_MAX_CONCURRENT` | 10 | Hard ceiling. Don't raise — z.ai's documented limit. |
| `ZAI_RESERVE_SLOTS` | 2 | Slots not used by pipeline (left for user) |
| `ZAI_INITIAL_CONCURRENCY` | max-reserve | Starting effective cap |
| `ZAI_HARNESS_WEIGHT` | 3 | Slot cost per Claude Code session call |
| `ZAI_RECOVERY_INTERVAL_S` | 60 | Min seconds between cap-recovery bumps |

## What the limiter does NOT do

- **Cross-process coordination**: if you launch two `pipeline.py` processes
  on the same Mac, they each have their own budget — they'll collide. Use
  one pipeline process at a time.
- **Predict z.ai's actual cap**: 429s are the ground truth. The limiter
  *reacts* — it doesn't psychic-predict.
- **Help if z.ai bans your key**: if the account hits a multi-day suspension,
  no client-side limiter can rescue. Only solution is to wait.

## Observability

Every entry in `runs/<batch_id>/glm_calls.jsonl` records `budget_state`:

```json
{
  "ts": "...", "fbgn": "FBgn0003068",
  "weight": 3,
  "budget_state": {"max": 10, "reserve": 2, "effective_cap": 7, "in_use": 6, "available": 1, "recent_429s_60s": 1}
}
```

Use this to debug "why is the pipeline running slower than expected":

```bash
# how often did we hit 429 in the run?
jq -s 'map(.budget_state.recent_429s_60s) | add' glm_calls.jsonl

# what was the effective cap distribution?
jq -r '.budget_state.effective_cap' glm_calls.jsonl | sort | uniq -c
```
