# minimax-m3-benchmark · Makefile
# 一键入口

SHELL := /bin/bash
PY    := python3
CFG   := config/test_cases.json
ANS   := raw_answers
OUT   := reports

# 默认目标
.PHONY: help
help: ## 显示所有可用命令
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# === 核心评分 ===
.PHONY: grade
grade: ## 硬断言评分（17 类断言）
	$(PY) scripts/grade.py

.PHONY: grade-archive
grade-archive: ## 跑评分并归档到 history/
	$(PY) scripts/grade.py --archive

.PHONY: grade-baseline
grade-baseline: ## 跑评分并更新 baseline
	$(PY) scripts/grade.py --set-baseline $(OUT)/baseline.json --archive

# === 性能 ===
.PHONY: bench
bench: ## 性能基准（静态字符/token 密度）
	$(PY) scripts/bench.py

.PHONY: bench-http
bench-http: ## HTTP 压测（需 LLM_API_BASE/KEY）
	@test -n "$$LLM_API_BASE" || (echo "需要 LLM_API_BASE"; exit 1)
	@test -n "$$LLM_API_KEY" || (echo "需要 LLM_API_KEY"; exit 1)
	$(PY) scripts/bench.py --http --model $${BENCH_MODEL:-gpt-4o} --rounds 5

# === LLM 裁判 ===
.PHONY: judge
judge: ## LLM-as-judge 评分（单裁判）
	@test -n "$$LLM_API_BASE" || (echo "需要 LLM_API_BASE"; exit 1)
	$(PY) scripts/judge.py --judge-model $${JUDGE_MODEL:-gpt-4o}

.PHONY: judge-double
judge-double: ## 双裁判 + 仲裁
	@test -n "$$LLM_API_BASE" || (echo "需要 LLM_API_BASE"; exit 1)
	@test -n "$$LLM_API_BASE2" || (echo "需要 LLM_API_BASE2"; exit 1)
	$(PY) scripts/judge.py \
		--judge-model $${JUDGE_MODEL:-gpt-4o} \
		--judge-model2 $${JUDGE_MODEL2:-claude-opus-4-8} \
		--arbitrator-model $${ARBITRATOR_MODEL:-gpt-4o}

.PHONY: judge-dry
judge-dry: ## 调试：只生成 prompt 草稿
	$(PY) scripts/judge.py --dry-run

# === 对比 ===
.PHONY: compare
compare: ## Pairwise A vs B 对比（结构化 + 裁判）
	@if [ -z "$(B_DIR)" ]; then \
		echo "用法: make compare B_DIR=raw_answers_other/ B_LABEL=other"; \
		exit 1; \
	fi
	$(PY) scripts/compare.py \
		--a-dir $(ANS) --label-a "MiniMax-M3" \
		--b-dir $(B_DIR) --label-b "$${B_LABEL:-B}"

# === 高级分析 ===
.PHONY: radar
radar: ## 雷达图（多版本叠加）
	@ls $(OUT)/history/ 2>/dev/null || (echo "无 history"; exit 1)
	$(PY) scripts/radar.py

.PHONY: consistency
consistency: ## 一致性测试（需 API）
	@test -n "$$LLM_API_BASE" || (echo "需要 LLM_API_BASE"; exit 1)
	$(PY) scripts/consistency.py --model $${MODEL:-gpt-4o} --rounds 5

.PHONY: rewrite
rewrite: ## Prompt 改写鲁棒性（需 API）
	@test -n "$$LLM_API_BASE" || (echo "需要 LLM_API_BASE"; exit 1)
	$(PY) scripts/rewrite_robustness.py \
		--rewriter-model $${REWRITER_MODEL:-gpt-4o} \
		--target-model $${TARGET_MODEL:-gpt-4o-mini}

.PHONY: failure
failure: ## 失败模式聚类（无 API 时用 --offline）
	@if [ -n "$$LLM_API_BASE" ]; then \
		$(PY) scripts/failure_analysis.py --judge-model $${JUDGE_MODEL:-gpt-4o}; \
	else \
		$(PY) scripts/failure_analysis.py --offline; \
	fi

.PHONY: calibration
calibration: ## 置信度校准
	$(PY) scripts/calibration.py

.PHONY: adversarial
adversarial: ## 对抗样本测试
	@test -n "$$LLM_API_BASE" || (echo "需要 LLM_API_BASE"; exit 1)
	$(PY) scripts/adversarial.py --model $${MODEL:-gpt-4o-mini}

.PHONY: meta
meta: ## 裁判一致性元评估（需 2-3 个裁判）
	@test -n "$$LLM_API_BASE" || (echo "需要 LLM_API_BASE"; exit 1)
	@test -n "$$LLM_API_BASE2" || (echo "需要 LLM_API_BASE2"; exit 1)
	$(PY) scripts/meta_eval.py \
		--judge-model $${JUDGE_MODEL:-gpt-4o} \
		--judge-model2 $${JUDGE_MODEL2:-claude-opus-4-8}

.PHONY: difficulty
difficulty: ## 难度自适应 + 能力位次
	$(PY) scripts/difficulty.py

# === 一键全跑（无 API 部分）===
.PHONY: all
all: grade bench radar calibration difficulty ## 跑所有无 API 依赖的脚本
	@echo "✅ all done"

# === 清理 ===
.PHONY: clean
clean: ## 清理 reports/（保留 history/）
	rm -rf $(OUT)/cases/*.json $(OUT)/cases/*.md
	rm -rf $(OUT)/summary/*.md $(OUT)/judge/prompts/
	rm -rf $(OUT)/consistency/ $(OUT)/failure_analysis/ $(OUT)/calibration/
	rm -rf $(OUT)/rewrite_robustness/ $(OUT)/adversarial/ $(OUT)/meta_eval/
	rm -rf $(OUT)/difficulty/ $(OUT)/compare/structural_*
	rm -f $(OUT)/radar.png $(OUT)/baseline.json
	@echo "cleaned"

# === 开发 ===
.PHONY: install
install: ## 安装依赖
	pip install -r requirements.txt
	pip install -e ".[dev]"

.PHONY: lint
lint: ## ruff check
	ruff check scripts/

.PHONY: test
test: ## 跑 pytest
	pytest tests/ -v
