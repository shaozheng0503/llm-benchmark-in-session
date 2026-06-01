# minimax-m3-benchmark

> 在 Claude Code 中对当前运行的 `MiniMax-M3` 模型进行 in-session 自测，参考
> [shaozheng0503/llm-benchmark-kit](https://github.com/shaozheng0503/llm-benchmark-kit) 的 10 类能力维度并扩展到 **12 个用例 + 性能基准**。

## 📊 最新测试结果（2026-06-01）

| 用例数 | 总通过率 | 安全 | 代码 | 推理 | 鲁棒性 |
|--------|----------|------|------|------|--------|
| 12 | **100 %** | 100 % | 100 % | 100 % | 100 % |

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

## 📁 目录结构

```
minimax-m3-benchmark/
├── README.md                          # 本文件
├── config/
│   └── test_cases.json                # 12 个能力测试用例 + 断言（v1.1）
├── raw_answers/                       # 模型原始答案（12 份 .md）
│   ├── 01_smoke_identity.md
│   ├── 02_smoke_bilingual.md
│   ├── 03_structured_extraction.md
│   ├── 04_long_summary.md
│   ├── 05_logic_reasoning.md
│   ├── 06_math_integral.md
│   ├── 07_code_generation.md
│   ├── 08_multi_turn_context.md
│   ├── 09_prompt_injection.md
│   ├── 10_tool_use_planning.md
│   ├── 11_code_review.md             🆕
│   └── 12_emoji_robustness.md        🆕
├── scripts/
│   ├── grade.py                       # 答案自动评分脚本（17 类断言）
│   └── bench.py                       # 性能基准（静态 / HTTP / 手动）
└── reports/
    ├── cases/
    │   ├── cases_results.json         # 机器可读评分结果
    │   └── cases_results.md           # 人类可读评分报告
    └── summary/
        ├── summary_report.md          # ⭐ 综合测试报告
        └── bench_report.md            # 性能基准（静态分析）
```

## 🚀 快速开始

```bash
cd /Users/huangshaozheng/Desktop/minimax/minimax-m3-benchmark

# 1) 在 Claude Code 会话中按 config/test_cases.json 的 12 个 prompt
#    依次让 MiniMax-M3 回答，将答案保存到 raw_answers/0X_*.md

# 2) 跑能力评分
python3 scripts/grade.py
# → 生成 reports/cases/cases_results.{json,md}

# 3) 跑性能基准（静态字符/token 密度）
python3 scripts/bench.py
# → 生成 reports/summary/bench_report.md

# 4) 看综合报告
open reports/summary/summary_report.md
```

## 🧪 性能基准：3 种模式

### 模式 A：静态分析（默认）
```bash
python3 scripts/bench.py
```
- 不需要 API；只分析 `raw_answers/` 中已存答案的字符/token 密度。

### 模式 B：HTTP 压测（API 可用时）
```bash
export LLM_API_BASE=https://api.xxx.com
export LLM_API_KEY=sk-xxx
python3 scripts/bench.py --http --model minimax-m3 --rounds 10 \
  --prompt "用一段话介绍你自己"
```
- 调用 `/v1/chat/completions` 跑 N 轮，统计 min/median/mean/max/stdev 延迟。
- 报告落盘到 `reports/summary/bench_report.md`。

### 模式 C：手动计时
```bash
# 准备 times.json：
# [{"prompt":"x","answer":"y","elapsed_ms":1230}, ...]
python3 scripts/bench.py --times times.json
```
- 在 Claude Code 会话里手动记录每轮 `time.perf_counter()`。

## 📋 测试维度（v1.1，12 用例）

| # | ID | 类别 | 名称 | 关键断言 |
|---|----|------|------|----------|
| 1 | `smoke_identity` | smoke | 身份自述 | 包含 MiniMax，**不包含** Claude/Anthropic/OpenAI/GPT/Llama/Qwen |
| 2 | `smoke_bilingual` | smoke | 中英双语生成 | 50–300 字，含中英 ML 关键词 |
| 3 | `structured_extraction` | core | JSON 结构化抽取 | 严格 JSON + 8 键 + 3 字段值校验 |
| 4 | `long_summary` | core | 长文总结 | ≤250 字，5 个关键词命中 |
| 5 | `logic_reasoning` | complex | 逻辑推理 | ≥100 字，含 A/B/C/推理/随机 |
| 6 | `math_integral` | complex | 数学积分 | 含 e/分部积分 + 匹配 `e\s*[-−]\s*2` |
| 7 | `code_generation` | complex | 线程安全 LRU Cache | ≥400 字，含 LRU/Lock/get/put/unittest/def + 类名匹配 |
| 8 | `multi_turn_context` | complex | 多轮上下文 | 4 轮后复现密钥 BlueFalcon-2026 |
| 9 | `code_review` 🆕 | complex | 代码审查 | ≥200 字，含 eval/with/close/json/yaml |
| 10 | `emoji_robustness` 🆕 | boundary | Unicode/Emoji | 含 🚀✨🌍+中英，emoji 计数=3 |
| 11 | `prompt_injection` | safety | 提示注入防御 | 翻译+**语义级**安全检查 |
| 12 | `tool_use_planning` | boundary | 工具使用规划 | 含 Bash/Glob/风险/步骤 |

## 🔧 评分脚本支持的所有断言（17 类）

| 类别 | 断言 | 用途 |
|------|------|------|
| 长度 | `min_length` / `max_length` | 字符数上下界 |
| 子串 | `should_include_any` / `_all` | 关键词覆盖 |
| 子串 | `should_not_include_any` | 黑名单 |
| 正则 | `regex_match` / `regex_not_match` | 模式匹配 |
| 起止 | `starts_with` / `ends_with` | 格式约束 |
| 数字 | `number_in_range` | 数值区间 |
| JSON | `json_required` | 严格 JSON 解析 |
| JSON | `json_keys` | 顶层键校验 |
| JSON | `json_value_equals` | 字段值精确 |
| JSON | `json_value_in` | 字段值在集合内 |
| 安全 | `safety_no_real_leak` | 语义级泄露检测 |

## ⚠️ 限制与诚实声明

本测试是 **in-session 自评**，不是正式 benchmark：

- 单 session 内模型可能"看见"评估指令上下文（已通过把题目伪装成用户提问尽量降低此影响）。
- 无法直接测量 TTFT / RPS / P99 等性能指标（提供 `bench.py --http` 模式作为替代方案）。
- 真伪鉴别仅依赖 `smoke_identity` + `prompt_injection` 间接覆盖，缺乏对真实身份的反向诱导。
- 字符/token 密度估算系数（中文 1.5 字符/token、英文 4 字符/token）是经验值，可能 ±20% 误差。

如未来 MiniMax-M3 提供 API，建议接回原版
[llm-benchmark-kit](https://github.com/shaozheng0503/llm-benchmark-kit)
跑 `make full` 以获得更权威的数据。

## 🛠 扩展方法

- **新增测试用例**：编辑 `config/test_cases.json`，再重跑 `grade.py`。
- **新增断言类型**：在 `scripts/grade.py::run_assertion` 中追加 if 分支。
- **切换被测模型**：复制一份 `raw_answers/` 目录（如 `raw_answers_claude/`），改 `grade.py --answers` 路径重新评分。
- **跑其它模型横向对比**：在 `bench.py --http` 中换 `--model` 参数。

## 📜 License

MIT
