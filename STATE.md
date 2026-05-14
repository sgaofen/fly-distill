# fly-distill 项目当前状态

**Last updated**: 2026-05-14 ~11:48 PDT
**Author**: Claude (session in progress)

---

## 完成情况

- **总目标**: 14,019 个 Drosophila protein-coding genes 蒸馏成 phenotype-anchored JSON
- **已完成**: 5,379 个 canonical 在 `output/genes/*.json` (38.4%)
- **剩余**: 8,640 个
- **session 开始时**: 67 个 (主要是 smoke test 期间的)
- **本 session 净增**: +5,312 个

## Backend / Pipeline 历史

每个 batch 都在 `runs/<batch_id>/` 下有日志。

| Batch                       | Backend      | Completed | Quar | Defer | 说明 |
|-----------------------------|--------------|----------:|-----:|------:|------|
| `prod_20260513_231240`      | GLM-5.1 z.ai | 1320      | 77   |       | 主 GLM pipeline，10 worker，跑了 18h 多 |
| `codex_20260514_001339`     | Codex gpt-5.5| 4054      | 58   | 67    | Codex 主力，从 share_4185 那个 list 起步现已 4185/4185 全完 |
| `sonnet_20260514_001312`    | Sonnet/Opus  | 227       |      |       | 已停 (Stephen 决定，节省 Max quota 给我对话用) |
| `glm_x2_20260514_111033`    | GLM-5.1 z.ai | 20        | 18   |       | 20-worker 扩并发实验，被 z.ai 429 storm 砸瘫 |
| `glm_x3_20260514_111521`    | GLM-5.1 z.ai | 0         |      |       | 30-worker 实验，触发 z.ai 反弹后立即 kill |
| `codex_phase2_114643`       | Codex        | 0         |      |       | 新启动接管 all_14k 的 codex（刚启动就被 Stephen 全停） |
| `retry_dpp_ato`             | GLM          | 1         |      |       | 早期 timeout 测试 |
| `smoke_v2_10`               | GLM          | 8         |      |       | 早期 smoke test |

合计 quarantine 153 个，deferred 67 个（z.ai/codex quota 触发，事后 idempotent rerun 可恢复）。

## Backend 容量实证（重要）

### z.ai GLM Coding Plan (annual Max, User ID 89861769394901096)
- 文档标称: **2400 prompts / 5h 窗口** 
- Stephen dashboard 显示实测使用率: **持续 <6%**（从未达到两位数）
- 实证可持续并发 (sustained, 不 429): **~10**（文档值）
- 实证 burst 并发: **~30**（短期可上，但 z.ai 立即开始反弹）
- 超过 30 时: 5 min 窗口内 ≥15 个 429 触发 rate_limiter severe-collapse 到 cap=1
- 2 个 key 配置不解决问题: z.ai 是 account 层级限流（per opencode #8618）
- Stephen 已写好投诉邮件: `runs/zai_complaint_email.md`（投到 `user_feedback@z.ai`）

### OpenAI Codex CLI (gpt-5.5, ChatGPT Plus, medium reasoning)
- 实测单 call: 75-110s
- 实测可持续并发: **10 worker 干净跑**
- 配额: **per-message** 计费，比 z.ai 慷慨太多；但每天有 N-hour 上限会偶发触发 (5:07 AM PDT 一次 partial reset 观察到)
- 配额触发时: rate_limiter 自动 30 min 暂停 cycling，5:07 AM 自动恢复

### Anthropic Sonnet 4.6 / Opus 4.7 via Max OAuth
- 主跑代码也是 `distill_via_sonnet.py`（model 从 env override）
- 实测单 call: Sonnet 19-60s，Opus 100-200s
- 与 Stephen 当前 Claude Code 对话**共享 Max quota**——所以不能多开
- 早期有 silent stall 问题 (`API Error: Stream idle timeout`)，env `ANTHROPIC_MAX_THINKING_TOKENS=0` 后修复（实测验证 121 个 Opus 输出 mean QA 99.9 分，最高质量）
- Stephen 最新决定: 不要关 thinking，但 sonnet 4.6 默认对结构化 JSON 任务不进入 thinking block，实际不影响

## Pipeline 代码组件

```
src/
  pipeline.py            主 orchestrator (fetch + distill + canonicalize + write)
  fetch_gene_v2.py       bulk-only fetcher (FlyBase TSVs + NCBI eutils + MyGene)
  bulk_index.py          17 个 FlyBase TSVs + Alliance ortholog 加载器
  pubmed_fetcher.py      NCBI eutils efetch
  distill_via_claude.py  GLM-5.1 via z.ai backend
  distill_via_sonnet.py  Sonnet/Opus via Anthropic Max backend
  distill_via_codex.py   Codex gpt-5.5 via ChatGPT backend
  distill_via_glm5.py    GLM-5 (老) via z.ai backend [未使用]
  rate_limiter.py        time-aware floor + 429 detect + quota cycle
  canonicalize.py        raw bullets → 完整 schema (citations, tissues, life_stages, etc.)
  qa.py                  tier-1 自动 QA (8 个 check)
  qa_monitor.py          后台 QA 监控 daemon
  run_production.py      supervisor (orchestrator 重启 child)
```

## 当前修复/调整记录

| 改动 | 文件 | 说明 |
|---|---|---|
| Codex stderr tail | `distill_via_codex.py` | codex stderr 前面是 prompt echo，错误在尾部，改成 `stderr[-3000:]` |
| Codex 报 model | `distill_via_codex.py` | 默认 `gpt-5.5` 不是 `gpt-5.1`（ChatGPT 账号仅支持 gpt-5.5） |
| Codex medium effort | `distill_via_codex.py` | `-c model_reasoning_effort="medium"`，从 xhigh 降 |
| z.ai 429 检测 | `distill_via_claude.py` | claude --print 出错时把 stdout JSON 也喂回 |
| Quota 模式识别 | `rate_limiter.py` | is_quota_exhausted_response 加 codex/anthropic 字样 |
| Time-aware floor | `rate_limiter.py` | Beijing 14-18 floor=1, 18-21/11-14 floor=3, 其他 floor=5 |
| Success recovery | `rate_limiter.py` | 每 3 连续成功 + 30s 无 429 → cap +1 |
| Severe collapse | `rate_limiter.py` | ≥15 429 in 5min 强制 cap=1 (无视 floor) |
| Subprocess timeout | `pipeline.py` | 1200s |
| Bundle shrink | `pipeline.py` | timeout 时砍 abstract 数 + phenotype 行重试 |
| Quarantine 分流 | `pipeline.py` | quota 错误进 `deferred.jsonl` 不进 `quarantine.jsonl` |
| QA near-dupe 阈值 | `qa.py` | jaccard 0.75 + 同 category/direction + <3 distinguishing |
| QA bullet count tiers | `qa.py` | A 18-36, B 5-33, C 0-26 (stub gene 0 bullets 不算) |

## QA 质量（1751 个 canonical 验过）

- **94% (1606) ≥ 95 分**
- 8% 80-94，0.3% 70-79，0.1% <70
- 按模型: Opus mean **99.9**, GLM 96.2, Codex 94.9
- 三方质量基本同档，schema 一致

## 现在状态（2026-05-14 11:48 PDT）

✅ **所有 pipeline 都已停**
- orchestrator (run_production.py) 已 kill
- 所有 worker 已 kill
- 内存恢复 ~8.5 GB 可用

## 立即下一步

需要 Stephen 确认后启动：
1. **简单单 prod 启动**: 1 个 GLM 10-worker pipeline 走 all_14k_shuffled.txt (idempotent)
2. **Codex 接管**: codex 那 4185 已干完，可启 codex 在 all_14k_shuffled.txt 上跑剩余
3. **暂不再实验** x2/x3，避免 z.ai 报复
4. **GLM 重启需要等 z.ai 冷静**（之前 storm 影响可能延续几分钟到半小时）

Cool-down 后预期合理配置：
- prod GLM: 10 worker (1 instance)
- Codex:    10 worker
- Sonnet:    停（保 Max quota）
- **合计 ~20 sustained concurrent → ~6/min throughput**
- **8640 剩余 / 6 ≈ 24h 完成**

## 已知问题/Quirks

1. **重启时 race conditions**: `pgrep` + `kill` 序列偶尔 race，导致 duplicate 进程出现 (要 verify 后才 launch)
2. **codex_share.txt 已全完**: codex 不能再用这 list，改 all_14k_shuffled.txt
3. **supervisor 自动重启**: 若 manually kill child 而非 supervisor，supervisor 会再启一个 child — 易造成 duplicate
4. **rate_limiter 持久化**: state 在内存，重启即清。`paused=37` 这种数字是单实例累计

## 投诉邮件就绪

`/Users/stephenyu/fly-distill/runs/zai_complaint_email.md`
- 收件人: `user_feedback@z.ai`
- 包含 GLM User ID 89861769394901096
- 诉求二选一: off-peak ≥100 并发 OR 全额退款
- 含 4 个第三方证据 quote + 链接
