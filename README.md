# minimax-m3-benchmark

> 在 Claude Code 中对当前运行的 `MiniMax-M3` 模型进行 in-session 自测，参考
> [shaozheng0503/llm-benchmark-kit](https://github.com/shaozheng0503/llm-benchmark-kit) 的 10 类能力维度，扩展为 **23 用例 + 11 个分析脚本 + 完整 CI**。

## 📊 最新测试结果（2026-06-01，v1.3）

| 用例数 | 总通过率 | ECE | 能力位次 |
|--------|----------|-----|----------|
| **23** | **100 %** | 0.104 | **L5+（超越基准）** |

👉 完整分析：[`reports/summary/summary_report.md`](reports/summary/summary_report.md)

## 🆚 为什么不用原版 kit？

原 kit 设计为对接 **OpenAI 兼容 HTTP 网关**（依赖 `LLM_API_BASE` + `LLM_API_KEY`），
通过 `discover_models → run_cases → run_stress → run_authenticity → build_summary` 跑出报告。

`MiniMax-M3` 当前**仅在 Claude Code 内部署**，没有公网 endpoint 暴露，因此：
- ❌ 跳过 `run_stress.py`（无法发起并发 HTTP 请求）
- ❌ 跳过 `discover_models.py`（无 `/v1/models`）
- ❌ 跳过 `run_authenticity.py` 的跨厂商反查
- ✅ 保留 `run_cases.py` 的 10 个能力维度，**改为 in-session 对话测试**
- ✅ 自写 11 个分析脚本，覆盖评分、性能、稳健性、可视化、元评估

## 📁 目录结构

```
minimax-m3-benchmark/
├── README.md
├── Makefile                       # 一键入口（make help 看全部）
├── pyproject.toml
├── requirements.txt
├── .github/
│   └── workflows/
│       └── benchmark.yml          # CI：grade / judge / lint
├── config/
│   └── test_cases.json            # 23 个测试用例 + 断言（v1.3）
├── raw_answers/                   # 23 份模型答案
├── scripts/
│   ├── grade.py                   # 17 类硬断言评分 + 回归检测
│   ├── bench.py                   # 性能基准（3 模式）
│   ├── judge.py                   # LLM-as-judge（单/双裁判 + 仲裁）
│   ├── compare.py                 # Pairwise A vs B
│   ├── consistency.py             # 同题 N 次一致性
│   ├── radar.py                   # 雷达图可视化
│   ├── rewrite_robustness.py      # Prompt 改写鲁棒性
│   ├── failure_analysis.py        # 失败模式聚类
│   ├── calibration.py             # 置信度校准（ECE）
│   ├── adversarial.py             # 对抗样本
│   ├── meta_eval.py               # 裁判一致性（Kappa）
│   └── difficulty.py              # 难度自适应 + 能力位次
└── reports/                       # 全部自动生成的报告
    ├── baseline.json              # 最新 baseline
    ├── history/                   # 历史快照
    ├── cases/
    ├── summary/
    ├── judge/
    ├── compare/
    ├── consistency/
    ├── radar.png                  # 雷达图
    ├── rewrite_cache/             # 改写 prompt 缓存
    ├── rewrite_robustness/
    ├── failure_analysis/
    ├── calibration/
    ├── adversarial/
    ├── meta_eval/
    └── difficulty/
```

## 🚀 快速开始

```bash
cd /Users/huangshaozheng/Desktop/minimax/minimax-m3-benchmark

# 安装依赖
make install

# 跑所有无 API 脚本（grade + bench + radar + calibration + difficulty）
make all

# 单独跑某个分析
make grade             # 硬断言评分
make grade-archive     # 评分 + 归档到 history/
make grade-baseline    # 评分 + 更新 baseline
make bench             # 性能基准（静态）
make radar             # 雷达图
make calibration       # ECE 置信度校准
make difficulty        # 难度自适应
make failure           # 失败模式聚类
make help              # 看全部
```

需要 API 的脚本：

```bash
# 设置 API
export LLM_API_BASE=https://api.openai.com
export LLM_API_KEY=sk-xxx

make judge             # LLM-as-judge
make judge-double      # 双裁判 + 仲裁
make consistency       # 同题 N 次一致性
make rewrite           # Prompt 改写鲁棒性
make adversarial       # 对抗样本
make meta              # 裁判一致性（Kappa）
make compare B_DIR=raw_answers_other/ B_LABEL=other
```

## 📋 23 个测试用例（v1.3）

| # | ID | 类别 | 名称 |
|---|----|------|------|
| 1 | `smoke_identity` | smoke | 身份自述 |
| 2 | `smoke_bilingual` | smoke | 中英双语 |
| 3 | `structured_extraction` | core | JSON 结构化抽取 |
| 4 | `long_summary` | core | 长文总结 |
| 5 | `logic_reasoning` | complex | 逻辑推理 |
| 6 | `math_integral` | complex | 数学积分 |
| 7 | `code_generation` | complex | 线程安全 LRU Cache |
| 8 | `multi_turn_context` | complex | 多轮上下文 |
| 9 | `code_review` | complex | 代码审查 |
| 10 | `prompt_injection` | safety | 提示注入（语义级） |
| 11 | `tool_use_planning` | boundary | 工具规划 |
| 12 | `emoji_robustness` | boundary | Unicode/Emoji |
| 13 | `bayesian_probability` | complex | 贝叶斯概率 |
| 14 | `unauthorized_tool` | safety | 越权工具调用 |
| 15 | `indirect_injection` | safety | 间接注入 |
| 16 | `needle_haystack` | complex | 大海捞针 |
| 17 | `style_transfer` | complex | 风格迁移 |
| 18 | `find_secrets` 🆕 | real_task | 找代码密钥 |
| 19 | `debug_incident` 🆕 | real_task | 5xx 故障排查 |
| 20 | `user_complaint` 🆕 | real_task | 模糊用户反馈 |
| 21 | `classical_chinese` 🆕 | multilingual | 古文断句 |
| 22 | `japanese_reading` 🆕 | multilingual | 日语 N1 阅读 |
| 23 | `calibration` 🆕 | complex | 置信度校准 |

## 🛠 11 个分析脚本

| 脚本 | 输入 | 输出 | API? |
|------|------|------|------|
| `grade.py` | cfg + raw_answers | cases_results.{json,md} + regression.md | ❌ |
| `bench.py` | raw_answers / HTTP | bench_report.md | 可选 |
| `judge.py` | raw_answers | judge_results.{json,md} | ✅ |
| `compare.py` | 两个答案目录 | structural_/pairwise_compare.{md,json} | 可选 |
| `consistency.py` | cfg + HTTP | consistency_report.md | ✅ |
| `radar.py` | 多个 results.json | radar.png | ❌ |
| `rewrite_robustness.py` | cfg + HTTP | rewrite_report.md | ✅ |
| `failure_analysis.py` | cases_results.json | failure_report.md | 可选 |
| `calibration.py` | 23_calibration.md | calibration_report.md | ❌ |
| `adversarial.py` | cfg + HTTP | adversarial_report.md | ✅ |
| `meta_eval.py` | raw_answers + HTTP | meta_eval_report.md | ✅ |
| `difficulty.py` | cases_results.json | difficulty_report.md | ❌ |

## 📈 评分脚本支持的所有断言（17 类）

`min_length` / `max_length` / `should_include_any` / `should_include_all` /
`should_not_include_any` / `regex_match` / `regex_not_match` /
`starts_with` / `ends_with` / `number_in_range` / `json_required` /
`json_keys` / `json_value_equals` / `json_value_in` /
`safety_no_real_leak` / `min_length` / `max_length`

## 📈 历史结果

| 版本 | 用例数 | 总通过率 | 主要变化 |
|------|--------|----------|----------|
| v1.0 | 10 | 95 % | 初版 |
| v1.1 | 12 | 100 % | 新增 `code_review` + `emoji_robustness`；修复 `math_integral` / `prompt_injection` 断言 |
| v1.2 | 17 | 100 % | 新增 5 用例（贝叶斯/越权/间接注入/大海捞针/风格迁移）+ LLM-as-judge + Pairwise |
| **v1.3** | **23** | **100 %** | 新增 6 用例（find_secrets/debug_incident/user_complaint/classical_chinese/japanese_reading/calibration）+ 6 个新分析脚本 + 回归检测 + Makefile + CI |

## ⚠️ 限制与诚实声明

- in-session 自评：模型可能"看见"评估指令上下文。
- 无法直接测量 TTFT / RPS / P99。
- 真伪鉴别仅依赖间接用例。
- 字符/token 密度估算系数是经验值，可能 ±20% 误差。

## 🛠 扩展方法

- **新增用例**：编辑 `config/test_cases.json`，再 `make grade`。
- **新增断言类型**：在 `scripts/grade.py::run_assertion` 加分支。
- **自定义 rubric**：`make judge JUDGE_MODEL=...`。
- **横向对比**：`make compare B_DIR=other/`。
- **新增分析脚本**：参考 `scripts/*.py` 的 `main()` 接口。

## 📜 License

MIT
