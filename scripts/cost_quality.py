#!/usr/bin/env python3
"""
minimax-m3-benchmark · cost_quality.py

性价比 Pareto：模型 × 质量 × 单次推理成本，画 Pareto 前沿。

输入：reports/leaderboard.json（leaderboard.py 输出）或自己指定的 JSON。

用法：
    python3 scripts/cost_quality.py --input reports/leaderboard.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "reports" / "cost_quality"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# 公开模型价格（美元 / 1M tokens，2026 Q1 数据，仅供参考）
KNOWN_PRICING = {
    "gpt-4o":          {"input": 2.50,  "output": 10.00},
    "gpt-4o-mini":     {"input": 0.15,  "output": 0.60},
    "o1":              {"input": 15.00, "output": 60.00},
    "o1-mini":         {"input": 3.00,  "output": 12.00},
    "claude-opus-4-8":  {"input": 15.00, "output": 75.00},
    "claude-sonnet-4-5": {"input": 3.00, "output": 15.00},
    "claude-haiku-4-5":  {"input": 0.80, "output": 4.00},
    "gemini-1.5-pro":  {"input": 1.25,  "output": 5.00},
    "gemini-1.5-flash":{"input": 0.075, "output": 0.30},
    "deepseek-chat":   {"input": 0.14,  "output": 0.28},
    "qwen-2.5-72b":    {"input": 0.40,  "output": 0.40},
    "minimax-m3":      {"input": 0.50,  "output": 2.00},
}

# 假设平均 500 input + 500 output tokens / 1 次推理
ASSUMED_INPUT_TOKENS = 500
ASSUMED_OUTPUT_TOKENS = 500


def cost_per_req(model: str) -> float:
    p = KNOWN_PRICING.get(model)
    if not p:
        return float("nan")
    return (p["input"] * ASSUMED_INPUT_TOKENS + p["output"] * ASSUMED_OUTPUT_TOKENS) / 1_000_000


def is_pareto_frontier(points: list[tuple[float, float]]) -> set[int]:
    """返回 Pareto 最优点的索引集合。
    横轴：cost（越小越好），纵轴：quality（越大越好）。
    """
    on_frontier = set()
    for i, (c1, q1) in enumerate(points):
        dominated = False
        for j, (c2, q2) in enumerate(points):
            if i == j:
                continue
            if c2 <= c1 and q2 >= q1 and (c2 < c1 or q2 > q1):
                dominated = True
                break
        if not dominated:
            on_frontier.add(i)
    return on_frontier


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    p.add_argument("--input", type=Path, default=None,
                   help="leaderboard.json；如未指定用 default 示例数据")
    p.add_argument("--out", type=Path, default=OUT_DIR / "pareto_report.md")
    args = p.parse_args()

    # 加载数据
    if args.input and args.input.exists():
        data = json.loads(args.input.read_text(encoding="utf-8"))
        rows = data.get("models", [])
    else:
        # 用内置示例
        rows = [
            {"model": m, "quality": q, "cost_per_million_input": KNOWN_PRICING.get(m, {}).get("input", 0),
             "cost_per_million_output": KNOWN_PRICING.get(m, {}).get("output", 0)}
            for m, q in [
                ("gpt-4o-mini", 78), ("claude-haiku-4-5", 76), ("gemini-1.5-flash", 75),
                ("gpt-4o", 92), ("claude-sonnet-4-5", 88), ("claude-opus-4-8", 90),
                ("gemini-1.5-pro", 85), ("deepseek-chat", 82), ("qwen-2.5-72b", 80),
                ("o1", 94), ("o1-mini", 86), ("minimax-m3", 100),
            ]
        ]

    # 算 cost/req
    for r in rows:
        r["cost_per_req"] = (
            (r.get("cost_per_million_input", 0) * ASSUMED_INPUT_TOKENS +
             r.get("cost_per_million_output", 0) * ASSUMED_OUTPUT_TOKENS) / 1_000_000
        )
        if r["cost_per_req"] == 0 and r["model"] in KNOWN_PRICING:
            r["cost_per_req"] = cost_per_req(r["model"])
        r["quality_per_dollar"] = (
            r["quality"] / (r["cost_per_req"] * 1_000_000)
            if r["cost_per_req"] > 0 else float("inf")
        )

    # Pareto
    points = [(r["cost_per_req"], r["quality"]) for r in rows]
    frontier_idx = is_pareto_frontier(points)

    # 报告
    lines = [
        "# 模型性价比 Pareto 报告\n",
        f"- 假设：每次推理 = {ASSUMED_INPUT_TOKENS} input + {ASSUMED_OUTPUT_TOKENS} output tokens",
        f"- 模型数：{len(rows)}",
        f"- Pareto 前沿模型：{len(frontier_idx)}\n",
        "## 详细表（按性价比排序）\n",
        "| 模型 | 质量 | 成本/请求 | 质量/百万美元 | Pareto |",
        "|------|------|----------|--------------|--------|",
    ]
    for i, r in enumerate(sorted(rows, key=lambda x: -x["quality_per_dollar"])):
        c = f"${r['cost_per_req']:.4f}" if r["cost_per_req"] > 0 else "—"
        qpd = f"{r['quality_per_dollar']:.0f}" if r["quality_per_dollar"] != float("inf") else "—"
        on = "✅" if i in frontier_idx else ""
        lines.append(
            f"| {r['model']} | {r['quality']}% | {c} | {qpd} | {on} |"
        )

    lines.append("\n## Pareto 前沿\n")
    lines.append("性价比前沿上的模型（无法被任何其它模型在「更便宜+同等质量」或「同价+更高质量」上同时超越）：\n")
    for i in sorted(frontier_idx, key=lambda x: rows[x]["cost_per_req"]):
        r = rows[i]
        c = f"${r['cost_per_req']:.4f}"
        lines.append(f"- **{r['model']}**：质量 {r['quality']}%，成本 {c}/请求")

    # 推荐
    lines.append("\n## 推荐\n")
    cheapest = min(rows, key=lambda r: r["cost_per_req"])
    highest_q = max(rows, key=lambda r: r["quality"])
    best_qpd = max(rows, key=lambda r: r["quality_per_dollar"] if r["quality_per_dollar"] != float("inf") else 0)
    lines.append(f"- **最便宜**：{cheapest['model']}（${cheapest['cost_per_req']:.4f}/请求）")
    lines.append(f"- **最高质量**：{highest_q['model']}（{highest_q['quality']}%）")
    lines.append(f"- **最佳性价比**：{best_qpd['model']}（质量/美元最高）")

    args.out.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {args.out}")
    print(f"Pareto 前沿：{[rows[i]['model'] for i in frontier_idx]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
