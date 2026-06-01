#!/usr/bin/env python3
"""
minimax-m3-benchmark · agent_workflow.py

Agent 长链路测试：5 步多轮任务，评估每步决策合理性。

场景：分析一个 PR（Pull Request），决定是否合并。

用法：
    LLM_API_BASE=... LLM_API_KEY=... python3 scripts/agent_workflow.py
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "reports" / "agent_workflow"
OUT_DIR.mkdir(parents=True, exist_ok=True)

WORKFLOW = [
    {
        "step": 1,
        "name": "检查 diff",
        "task": "阅读下面这个 PR 的 diff 描述，列出 3 个最值得关注的改动点。",
        "expected_keywords": ["修改", "新增", "删除", "功能", "bug"],
        "rubric": "是否准确识别了主要改动（而非次要格式变更）",
    },
    {
        "step": 2,
        "name": "运行测试",
        "task": "现在你运行了 CI，结果：4 个测试套件，3 通过，1 失败（test_payment.py::test_refund）。你的下一步行动是什么？",
        "expected_keywords": ["定位", "复现", "log", "debug", "测试", "test_refund"],
        "rubric": "是否优先排查失败测试而非合并",
    },
    {
        "step": 3,
        "name": "评估影响",
        "task": "test_payment.py 的退款逻辑改动了：把 `process_refund(amount, currency='USD')` 改为 `process_refund(amount, currency=None)` 并自动从 amount 推断币种。这种 breaking change 的影响范围？",
        "expected_keywords": ["API", "调用方", "兼容", "下游", "客户端", "SDK", "文档"],
        "rubric": "是否识别出对外部 API 用户的破坏性影响",
    },
    {
        "step": 4,
        "name": "安全审计",
        "task": "在退款逻辑里，amount 现在会被直接传给外部支付网关。`amount` 是否需要做类型/范围校验？",
        "expected_keywords": ["校验", "验证", "validate", "负数", "类型", "金额", "sanitize"],
        "rubric": "是否识别出安全/数据完整性风险",
    },
    {
        "step": 5,
        "name": "最终决策",
        "task": "综合以上 4 步，你是否建议合并此 PR？为什么？请给出 ≤ 80 字决策。",
        "expected_keywords": ["不合并", "拒绝", "需要修改", "block", "待修改", "建议", "reject", "需修复"],
        "rubric": "是否给出明确的'不合并'决定 + 原因",
    },
]


def call_chat(base, key, model, messages, timeout=60.0, temperature=0.0):
    body = json.dumps({
        "model": model, "messages": messages, "temperature": temperature,
    }).encode("utf-8")
    req = urllib.request.Request(f"{base.rstrip('/')}/v1/chat/completions", data=body, headers={
        "Content-Type": "application/json", "Authorization": f"Bearer {key}",
    })
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))["choices"][0]["message"]["content"]


def evaluate_step(step: dict, answer: str) -> dict:
    """评估单步：关键词命中 + rubric 1-5。"""
    hits = [k for k in step["expected_keywords"] if k.lower() in answer.lower()]
    return {
        "step": step["step"],
        "name": step["name"],
        "keyword_hits": hits,
        "keyword_coverage": round(len(hits) / len(step["expected_keywords"]), 2),
        "rubric": step["rubric"],
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    p.add_argument("--model", default=os.environ.get("MODEL", "gpt-4o-mini"))
    p.add_argument("--base", default=os.environ.get("LLM_API_BASE", ""))
    p.add_argument("--key", default=os.environ.get("LLM_API_KEY", ""))
    p.add_argument("--timeout", type=float, default=60.0)
    p.add_argument("--out", type=Path, default=OUT_DIR / "workflow_report.md")
    args = p.parse_args()

    if not (args.base and args.key):
        print("ERROR: 需 --base/--key", file=sys.stderr)
        return 2

    print(f"target={args.model}, steps={len(WORKFLOW)}")
    messages: list[dict] = []
    rows = []
    for step in WORKFLOW:
        messages.append({"role": "user", "content": step["task"]})
        try:
            ans = call_chat(args.base, args.key, args.model, messages, args.timeout)
            messages.append({"role": "assistant", "content": ans})
        except Exception as e:
            ans = f"ERROR: {e}"
        eval_result = evaluate_step(step, ans)
        eval_result["answer"] = ans[:200]
        rows.append(eval_result)
        print(f"  step {step['step']} {step['name']}: "
              f"coverage={eval_result['keyword_coverage']*100:.0f}%")

    avg = statistics.mean(r["keyword_coverage"] for r in rows)

    lines = [
        "# Agent 长链路工作流报告\n",
        f"- 目标模型：`{args.model}`",
        f"- 步数：{len(WORKFLOW)}",
        f"- **平均关键词覆盖率：{avg*100:.1f}%**\n",
        "## 工作流概览\n",
        "**场景**：分析一个 PR（Pull Request），决定是否合并。\n",
    ]
    for step in WORKFLOW:
        lines.append(f"- **Step {step['step']} {step['name']}**：{step['task'][:50]}...")

    lines.append("\n## 逐步评估\n")
    for r in rows:
        lines.append(f"### Step {r['step']}: {r['name']}")
        lines.append(f"- **任务**：{WORKFLOW[r['step']-1]['task'][:100]}...")
        lines.append(f"- **关键词命中**：{', '.join(r['keyword_hits']) or '（无）'}")
        lines.append(f"- **覆盖率**：{r['keyword_coverage']*100:.0f}%")
        lines.append(f"- **Rubric**：{r['rubric']}")
        lines.append(f"- **模型答案**：{r['answer']}…")
        lines.append("")

    args.out.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
