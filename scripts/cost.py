#!/usr/bin/env python3
"""
minimax-m3-benchmark · cost.py

成本跟踪：每次跑完分析 judge / bench / leaderboard 等 API 调用的
prompt + completion token 数，按模型价格计算美元成本。

输出 reports/cost/cost_report.md，CI 配月度上限告警。
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "reports" / "cost"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# 美元 / 1M tokens
PRICING = {
    "gpt-4o":         {"input": 2.50, "output": 10.00},
    "gpt-4o-mini":    {"input": 0.15, "output": 0.60},
    "o1":             {"input": 15.00, "output": 60.00},
    "o1-mini":        {"input": 3.00, "output": 12.00},
    "claude-opus-4-8":  {"input": 15.00, "output": 75.00},
    "claude-sonnet-4-5": {"input": 3.00, "output": 15.00},
    "claude-haiku-4-5":  {"input": 0.80, "output": 4.00},
    "gemini-1.5-pro": {"input": 1.25, "output": 5.00},
    "gemini-1.5-flash": {"input": 0.075, "output": 0.30},
    "deepseek-chat":  {"input": 0.14, "output": 0.28},
    "qwen-2.5-72b":   {"input": 0.40, "output": 0.40},
    "minimax-m3":     {"input": 0.50, "output": 2.00},
}


def calc_cost(model: str, prompt_t: int, completion_t: int) -> float:
    p = PRICING.get(model)
    if not p:
        return 0.0
    return (prompt_t * p["input"] + completion_t * p["output"]) / 1_000_000


def collect_usage() -> list[dict]:
    """从所有 reports/ 子目录的 _meta.usage 收集 token 用量。"""
    usages = []
    for json_file in (ROOT / "reports").rglob("*.json"):
        try:
            data = json.loads(json_file.read_text(encoding="utf-8"))
        except Exception:
            continue
        # 递归找 _meta.usage
        def walk(obj, path=""):
            if isinstance(obj, dict):
                if "_meta" in obj and isinstance(obj["_meta"], dict) and "usage" in obj["_meta"]:
                    usages.append({
                        "file": json_file.relative_to(ROOT),
                        **obj["_meta"]["usage"],
                        "model": obj["_meta"].get("judge_model", "?"),
                    })
                for k, v in obj.items():
                    walk(v, f"{path}.{k}")
            elif isinstance(obj, list):
                for i, v in enumerate(obj):
                    walk(v, f"{path}[{i}]")
        walk(data)
    return usages


def workflow_cost(workflow: dict) -> dict:
    """根据工作流描述算月成本。
    workflow 格式: {
        "model": "gpt-4o-mini",
        "monthly_calls": 1000,
        "avg_input_tokens": 500,
        "avg_output_tokens": 500,
    }
    """
    model = workflow["model"]
    calls = workflow["monthly_calls"]
    pt = workflow["avg_input_tokens"]
    ct = workflow["avg_output_tokens"]
    per_call = calc_cost(model, pt, ct)
    return {
        "model": model, "monthly_calls": calls,
        "per_call_usd": round(per_call, 6),
        "monthly_usd": round(per_call * calls, 2),
        "yearly_usd": round(per_call * calls * 12, 2),
    }


def render_workflow_report(workflow: dict) -> str:
    r = workflow_cost(workflow)
    lines = [
        "# 真实工作流成本估算\n",
        f"- 模型：`{r['model']}`",
        f"- 每月调用：{r['monthly_calls']:,} 次",
        f"- 平均输入：{workflow['avg_input_tokens']} tokens",
        f"- 平均输出：{workflow['avg_output_tokens']} tokens",
        f"- **单次成本：${r['per_call_usd']:.6f}**",
        f"- **月度成本：${r['monthly_usd']:.2f}**",
        f"- **年度成本：${r['yearly_usd']:.2f}**\n",
    ]
    # 横向对比（其他同档位模型）
    same_tier = {
        "gpt-4o-mini":  ["gpt-4o-mini", "gemini-1.5-flash", "deepseek-chat", "qwen-2.5-72b"],
        "gpt-4o":       ["gpt-4o", "claude-sonnet-4-5", "gemini-1.5-pro", "minimax-m3"],
        "claude-opus-4-8": ["claude-opus-4-8", "o1", "gpt-4o"],
    }.get(r["model"], [r["model"]])
    lines.append("## 同档位模型对比\n")
    lines.append("| 模型 | 月成本 | 年成本 | 倍数 |")
    lines.append("|------|--------|--------|------|")
    for m in same_tier:
        if m not in PRICING:
            continue
        w = {"model": m, "monthly_calls": workflow["monthly_calls"],
             "avg_input_tokens": workflow["avg_input_tokens"],
             "avg_output_tokens": workflow["avg_output_tokens"]}
        wr = workflow_cost(w)
        ratio = wr["monthly_usd"] / r["monthly_usd"] if r["monthly_usd"] > 0 else 0
        marker = " ← 当前" if m == r["model"] else ""
        lines.append(
            f"| {m} | ${wr['monthly_usd']:.2f} | ${wr['yearly_usd']:.2f} "
            f"| {ratio:.2f}x{marker} |"
        )

    lines.append("\n## 建议")
    lines.append(f"- 当前模型 `{r['model']}` 月成本 ${r['monthly_usd']:.2f}，可接受。")
    if r["monthly_usd"] > 100:
        lines.append("- 月成本 > $100，建议评估同档位更便宜的模型。")
    return "\n".join(lines)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    p.add_argument("--monthly-cap-usd", type=float, default=50.0)
    p.add_argument("--workflow", type=str, default=None,
                   help="工作流 JSON：'{\"model\":\"gpt-4o-mini\",\"monthly_calls\":1000,"
                        "\"avg_input_tokens\":500,\"avg_output_tokens\":500}'")
    p.add_argument("--out", type=Path, default=OUT_DIR / "cost_report.md")
    args = p.parse_args()

    # 工作流模式
    if args.workflow:
        wf = json.loads(args.workflow)
        args.out.write_text(render_workflow_report(wf), encoding="utf-8")
        r = workflow_cost(wf)
        print(f"wrote {args.out}")
        print(f"{r['model']}: 月 ${r['monthly_usd']:.2f} / 年 ${r['yearly_usd']:.2f}")
        return 0

    usages = collect_usage()
    by_model: dict[str, dict] = defaultdict(
        lambda: {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0, "cost": 0.0}
    )
    for u in usages:
        model = u.get("model", "?")
        pt = u.get("prompt_tokens", 0) or 0
        ct = u.get("completion_tokens", 0) or 0
        cost = calc_cost(model, pt, ct)
        by_model[model]["calls"] += 1
        by_model[model]["prompt_tokens"] += pt
        by_model[model]["completion_tokens"] += ct
        by_model[model]["cost"] += cost

    total_cost = sum(m["cost"] for m in by_model.values())
    over_cap = total_cost > args.monthly_cap_usd

    lines = [
        "# 成本跟踪报告\n",
        f"- 时间：{datetime.now().isoformat(timespec='seconds')}",
        f"- 用量记录条数：{len(usages)}",
        f"- **总成本：${total_cost:.4f}**",
        f"- 月度上限：${args.monthly_cap_usd}",
        f"- 状态：{'⚠️ 超限' if over_cap else '✅ 正常'}\n",
        "## 按模型分项\n",
        "| 模型 | 调用数 | Prompt tokens | Completion tokens | 成本 (USD) |",
        "|------|--------|---------------|-------------------|-----------|",
    ]
    for m, s in sorted(by_model.items(), key=lambda x: -x[1]["cost"]):
        lines.append(
            f"| {m} | {s['calls']} | {s['prompt_tokens']:,} "
            f"| {s['completion_tokens']:,} | ${s['cost']:.4f} |"
        )

    lines.append("\n## 价格表（美元/1M tokens）\n")
    lines.append("| 模型 | Input | Output |")
    lines.append("|------|-------|--------|")
    for m, p in PRICING.items():
        lines.append(f"| {m} | ${p['input']} | ${p['output']} |")

    if over_cap:
        lines.append("\n## ⚠️ 成本告警\n")
        lines.append(f"总成本 ${total_cost:.4f} 已超过月度上限 ${args.monthly_cap_usd}。")
        lines.append("建议：")
        lines.append("- 用更便宜的模型（如 gpt-4o-mini 代替 gpt-4o）")
        lines.append("- 减少 --rounds / --limit")
        lines.append("- 启用 --dry-run 调试")

    args.out.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {args.out}")
    print(f"总成本 ${total_cost:.4f} / 上限 ${args.monthly_cap_usd}")
    return 1 if over_cap else 0


if __name__ == "__main__":
    sys.exit(main())
