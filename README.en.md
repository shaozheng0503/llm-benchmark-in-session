# minimax-m3-benchmark (English)

> In-session benchmark for the `MiniMax-M3` model running inside Claude Code, inspired by
> [shaozheng0503/llm-benchmark-kit](https://github.com/shaozheng0503/llm-benchmark-kit)
> and extended with **23 test cases + 19 analysis scripts + statistical tests + CI + dashboard**.

## Latest Results (2026-06-01, v1.3)

| Cases | Pass Rate | ECE | Capability Tier |
|--------|-----------|-----|-----------------|
| **23** | **100 %** | 0.104 | **L5+ (Beyond Reference)** |

Full analysis: [`reports/summary/summary_report.md`](reports/summary/summary_report.md)
([Chinese version](README.md))

## Why not use the original kit?

The original kit targets an **OpenAI-compatible HTTP gateway** (requires `LLM_API_BASE`
+ `LLM_API_KEY`). It runs `discover_models → run_cases → run_stress → run_authenticity →
build_summary`.

`MiniMax-M3` is currently only deployed **inside Claude Code**, with no public API
endpoint. Therefore:
- ❌ Skip `run_stress.py` (can't issue concurrent HTTP)
- ❌ Skip `discover_models.py` (no `/v1/models`)
- ❌ Skip the cross-vendor part of `run_authenticity.py`
- ✅ Keep `run_cases.py` semantics — **convert to in-session dialogue tests**
- ✅ Self-write 19 analysis scripts covering scoring, performance, robustness, visualization,
  meta-evaluation

## Quick Start

```bash
cd minimax-m3-benchmark

# Install deps
make install

# Run all offline scripts (grade + bench + radar + calibration + difficulty)
make all

# Run with API
export LLM_API_BASE=https://api.openai.com
export LLM_API_KEY=sk-xxx
make judge            # LLM-as-judge
make judge-double     # dual judges + arbitration
make consistency      # N-run consistency
make adversarial      # adversarial samples
make meta             # judge consistency (Kappa)
```

## Directory Layout

```
minimax-m3-benchmark/
├── README.md / README.en.md      # This file (bilingual)
├── Makefile                       # 25+ targets
├── pyproject.toml
├── requirements.txt
├── .github/workflows/benchmark.yml
├── .pre-commit-config.yaml
├── CONTRIBUTING.md                # Contribution guide
├── config/
│   ├── test_cases.json            # 23 test cases
│   └── test_cases.schema.json     # JSON Schema for CI validation
├── templates/
│   └── new_test_case.json         # Template for new cases
├── docs/
│   ├── adr/                       # Architecture Decision Records
│   │   ├── 0001-in-session-self-test.md
│   │   ├── 0002-17-assertion-types.md
│   │   └── 0003-hard-assertion-vs-llm-judge.md
│   └── index.md                   # Documentation index
├── raw_answers/                   # 23 model answers
├── scripts/                       # 19 analysis scripts
│   ├── grade.py                   # 17 hard assertions
│   ├── bench.py                   # 3 performance modes
│   ├── judge.py                   # LLM-as-judge
│   ├── compare.py                 # Pairwise A vs B
│   ├── consistency.py             # N-run consistency
│   ├── radar.py                   # Radar visualization
│   ├── rewrite_robustness.py      # Prompt paraphrase
│   ├── failure_analysis.py        # Failure clustering
│   ├── calibration.py             # ECE
│   ├── adversarial.py             # Adversarial
│   ├── meta_eval.py               # Judge Kappa
│   ├── difficulty.py              # Adaptive difficulty
│   ├── injection_gradient.py      # 5-level injection
│   ├── leaderboard.py             # Multi-model leaderboard
│   ├── cost_quality.py            # Pareto
│   ├── judge_bias.py              # Judge bias
│   ├── cost.py                    # Cost tracking
│   ├── repro.py                   # Reproducibility
│   ├── auto_generate.py           # Auto-generate cases
│   ├── dashboard.py               # Streamlit
│   ├── significance.py            # Bootstrap CI + p-value
│   ├── validate.py                # JSON Schema
│   └── agent_workflow.py          # 5-step agent task
└── reports/                       # Auto-generated
    ├── cases/
    ├── judge/
    ├── compare/
    ├── leaderboard/
    ├── ...
    └── baseline.json              # Latest baseline
```

## 19 Analysis Scripts

| Script | Input | Output | API? |
|--------|-------|--------|------|
| `grade.py` | cfg + raw_answers | cases_results.{json,md} + regression.md | ❌ |
| `bench.py` | raw_answers / HTTP | bench_report.md | optional |
| `judge.py` | raw_answers | judge_results.{json,md} | ✅ |
| `compare.py` | two answer dirs | structural_/pairwise_compare.{md,json} | optional |
| `consistency.py` | cfg + HTTP | consistency_report.md | ✅ |
| `radar.py` | multiple results.json | radar.png | ❌ |
| `rewrite_robustness.py` | cfg + HTTP | rewrite_report.md | ✅ |
| `failure_analysis.py` | cases_results.json | failure_report.md | optional |
| `calibration.py` | 23_calibration.md | calibration_report.md | ❌ |
| `adversarial.py` | cfg + HTTP | adversarial_report.md | ✅ |
| `meta_eval.py` | raw_answers + HTTP | meta_eval_report.md | ✅ |
| `difficulty.py` | cases_results.json | difficulty_report.md | ❌ |
| `injection_gradient.py` | cfg + HTTP | gradient_report.md | ✅ |
| `leaderboard.py` | cfg + HTTP | leaderboard.{md,json} | ✅ |
| `cost_quality.py` | leaderboard.json | pareto_report.md | ❌ |
| `judge_bias.py` | raw_answers + HTTP | bias_report.md | ✅ |
| `cost.py` | reports/*/json | cost_report.md | ❌ |
| `repro.py` | cfg + HTTP | repro_report.md | ✅ |
| `auto_generate.py` | cfg + HTTP | generated_cases.json | ✅ |
| `dashboard.py` | history | Streamlit UI | ❌ |
| `significance.py` | current + baseline | significance_report.md | ❌ |
| `validate.py` | test_cases.json | pass/fail | ❌ |
| `agent_workflow.py` | 5-step PR | workflow_report.md | ✅ |

## 23 Test Cases (v1.3)

[Same as Chinese README - 7 categories, full table]

## License

MIT
