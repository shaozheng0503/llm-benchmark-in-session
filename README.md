# minimax-m3-benchmark

> 在 Claude Code 中对当前运行的 `MiniMax-M3` 模型进行 in-session 自测，参考
> [shaozheng0503/llm-benchmark-kit](https://github.com/shaozheng0503/llm-benchmark-kit) 的 10 类能力维度并扩展到 **17 个用例 + 性能基准 + LLM-as-judge + Pairwise 对比**。

## 📊 最新测试结果（2026-06-01，v1.2）

| 用例数 | 总通过率 | 推理 | 代码 | 安全 | 鲁棒性 |
|--------|----------|------|------|------|--------|
| **17** | **100 %** | 100 % | 100 % | 100 % | 100 % |

👉 完整分析：[`reports/summary/summary_report.md`](reports/summary/summary_report.md)

## 🆚 为什么不用原版 kit？

原 kit 设计为对接 **OpenAI 兼容 HTTP 网关**（依赖 `LLM_API_BASE` + `LLM_API_KEY`），
通过 `discover_models → run_cases → run_stress → run_authenticity → build_summary` 跑出报告。

`MiniMax-M3` 当前**仅在 Claude Code 内部署**，没有公网 endpoint 暴露，因此：
- ❌ 跳过 `run_stress.py`（无法发起并发 HTTP 请求）
- ❌ 跳过 `discover_models.py`（无 `/v1/models`）
- ❌ 跳过 `run_authenticity.py` 的跨厂商反查
- ✅ 保留 `run_cases.py` 的 10 个能力维度，**改为 in-session 对话测试**
- ✅ 自写 `scripts/grade.py` 完成 17 类断言的评分与报告
- ✅ 自写 `scripts/bench.py` 支持 3 种性能基准模式（静态 / HTTP / 手动）
- ✅ 自写 `scripts/judge.py` 支持 LLM-as-judge（双裁判 + 仲裁）
- ✅ 自写 `scripts/compare.py` 支持 Pairwise A vs B 对比

## 📁 目录结构

```
minimax-m3-benchmark/
├── README.md                          # 本文件
├── config/
│   └── test_cases.json                # 17 个能力测试用例 + 断言（v1.2）
├── raw_answers/                       # 模型原始答案（17 份 .md）
├── scripts/
│   ├── grade.py                       # 答案自动评分脚本（17 类断言）
│   ├── bench.py                       # 性能基准（3 种模式）
│   ├── judge.py                       # LLM-as-judge 评分（单/双裁判 + 仲裁）
│   └── compare.py                     # Pairwise A vs B 对比
└── reports/
    ├── cases/
    │   ├── cases_results.json         # 结构化评分结果
    │   └── cases_results.md           # 人类可读评分报告
    ├── judge/                         # LLM-as-judge 输出
    │   ├── prompts/                   # dry-run 时生成的 prompt 草稿
    │   ├── judge_results.json
    │   └── judge_results.md
    ├── compare/                       # Pairwise 对比输出
    │   ├── structural_compare.{md,json}
    │   └── pairwise_compare.{md,json}
    └── summary/
        ├── summary_report.md          # ⭐ 综合测试报告
        └── bench_report.md            # 性能基准
```

## 🚀 快速开始

```bash
cd /Users/huangshaozheng/Desktop/minimax/minimax-m3-benchmark

# 1) 在 Claude Code 会话中按 config/test_cases.json 的 17 个 prompt
#    依次让 MiniMax-M3 回答，将答案保存到 raw_answers/0X_*.md

# 2) 跑能力评分（17 类硬断言）
python3 scripts/grade.py
# → reports/cases/cases_results.{json,md}

# 3) 跑性能基准（字符/token 密度）
python3 scripts/bench.py
# → reports/summary/bench_report.md

# 4) 跑 LLM-as-judge（需要 OpenAI 兼容 API）
export LLM_API_BASE=https://api.openai.com
export LLM_API_KEY=sk-xxx
python3 scripts/judge.py --judge-model gpt-4o
# → reports/judge/judge_results.{json,md}

# 5) 跑 Pairwise 对比（结构化 + 裁判）
python3 scripts/compare.py \
  --a-dir raw_answers/ --label-a "MiniMax-M3" \
  --b-dir raw_answers_claude/ --label-b "claude-sonnet-4-5"
# → reports/compare/structural_compare.{md,json}
```

## 🧪 4 个核心脚本

### `grade.py` —— 17 类硬断言评分

| 类别 | 断言 |
|------|------|
| 长度 | `min_length` / `max_length` |
| 子串 | `should_include_any` / `_all` / `should_not_include_any` |
| 正则 | `regex_match` / `regex_not_match` |
| 起止 | `starts_with` / `ends_with` |
| 数字 | `number_in_range` |
| JSON | `json_required` / `json_keys` / `json_value_equals` / `json_value_in` |
| 安全 | `safety_no_real_leak`（语义级，带 `allow_phrases` 例外） |

### `bench.py` —— 3 种性能模式

- **静态分析**：默认；分析 raw_answers/ 的字符/token 密度
- **HTTP 压测**：`--http`；调 `/v1/chat/completions` 跑 N 轮统计 min/median/mean/max/stdev 延迟
- **手动计时**：`--times`；吃 JSON 列表，会话内手动记录

### `judge.py` —— LLM-as-Judge 评分

```bash
# 单裁判
LLM_API_BASE=... LLM_API_KEY=... python3 scripts/judge.py --judge-model gpt-4o

# 双裁判 + 仲裁（推荐）
LLM_API_BASE=... LLM_API_KEY=... \
LLM_API_BASE2=... LLM_API_KEY2=... \
  python3 scripts/judge.py \
  --judge-model gpt-4o \
  --judge-model2 claude-opus-4-8 \
  --arbitrator-model gpt-4o

# dry-run（调试用，只生成 prompt 草稿）
python3 scripts/judge.py --dry-run
```

### `compare.py` —— Pairwise A vs B 对比

```bash
# 结构化对比（无 API）
python3 scripts/compare.py --a-dir raw_answers/ --label-a "MiniMax-M3" \
  --b-dir raw_answers_claude/ --label-b "claude-sonnet-4-5"

# Pairwise 裁判对比（需 API）
LLM_API_BASE=... LLM_API_KEY=... JUDGE_MODEL=gpt-4o \
python3 scripts/compare.py --a-dir raw_answers/ --label-a "MiniMax-M3" \
  --b-dir raw_answers_gpt/ --label-b "gpt-4o-mini" --judge-model gpt-4o
```

## 📋 测试维度（v1.2，17 用例）

| # | ID | 类别 | 名称 |
|---|----|------|------|
| 1 | `smoke_identity` | smoke | 身份自述 |
| 2 | `smoke_bilingual` | smoke | 中英双语生成 |
| 3 | `structured_extraction` | core | JSON 结构化抽取 |
| 4 | `long_summary` | core | 长文总结 |
| 5 | `logic_reasoning` | complex | 逻辑推理 |
| 6 | `math_integral` | complex | 数学积分 |
| 7 | `code_generation` | complex | 线程安全 LRU Cache |
| 8 | `multi_turn_context` | complex | 多轮上下文 |
| 9 | `prompt_injection` | safety | 提示注入（语义级） |
| 10 | `tool_use_planning` | boundary | 工具规划 |
| 11 | `code_review` | complex | 代码审查 |
| 12 | `emoji_robustness` | boundary | Unicode/Emoji 鲁棒性 |
| 13 | `bayesian_probability` 🆕 | complex | 贝叶斯概率（经典陷阱） |
| 14 | `unauthorized_tool` 🆕 | safety | 越权工具调用（拒绝口头授权） |
| 15 | `indirect_injection` 🆕 | safety | 间接注入（来自工具结果） |
| 16 | `needle_haystack` 🆕 | complex | 大海捞针（长上下文检索） |
| 17 | `style_transfer` 🆕 | complex | 风格迁移（鲁迅 × 程序员） |

## 📈 历史结果

| 版本 | 用例数 | 总通过率 | 主要变化 |
|------|--------|----------|----------|
| v1.0 | 10 | 95 % | 初版 |
| v1.1 | 12 | 100 % | 新增 `code_review` + `emoji_robustness`；修复 `math_integral` / `prompt_injection` 断言 |
| v1.2 | **17** | **100 %** | 新增 5 个高价值用例 + LLM-as-judge + Pairwise 对比 |

## ⚠️ 限制与诚实声明

本测试是 **in-session 自评**，不是正式 benchmark：

- 单 session 内模型可能"看见"评估指令上下文（已通过把题目伪装成用户提问尽量降低此影响）。
- 无法直接测量 TTFT / RPS / P99 等性能指标（提供 `bench.py --http` 模式作为替代方案）。
- 真伪鉴别仅依赖 2 个间接用例，缺乏对真实身份的反向诱导。
- 字符/token 密度估算系数（中文 1.5 字符/token、英文 4 字符/token）是经验值，可能 ±20% 误差。
- 间接注入 / 越权用例依赖**字面语义级**判断，可能存在"过度提及攻击域名"被误判的情况——已用 `safety_no_real_leak.allow_phrases` 缓解。

如未来 MiniMax-M3 提供 API，建议接回原版
[llm-benchmark-kit](https://github.com/shaozheng0503/llm-benchmark-kit)
跑 `make full` 以获得更权威的数据。

## 🛠 扩展方法

- **新增测试用例**：编辑 `config/test_cases.json`，再重跑 `grade.py`。
- **新增断言类型**：在 `scripts/grade.py::run_assertion` 中追加 if 分支。
- **自定义 rubric**：`judge.py --rubric "$(cat my_rubric.md)"`。
- **横向对比模型**：`compare.py --a-dir A --b-dir B`。
- **跑其它模型**：复制 `raw_answers/` 目录命名 `raw_answers_<model>/`，再用 `compare.py` 或 `grade.py --answers`。

## 📜 License

MIT
