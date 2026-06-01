#!/usr/bin/env python3
"""
minimax-m3-benchmark · data_analysis.py

数据分析能力：SQL / 数据清洗 / 可视化 3 类。

用法：
    LLM_API_BASE=... LLM_API_KEY=... python3 scripts/data_analysis.py
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
OUT_DIR = ROOT / "reports" / "data_analysis"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def call_chat(base, key, model, prompt, timeout=60.0, temperature=0.0):
    body = json.dumps({
        "model": model, "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
    }).encode("utf-8")
    req = urllib.request.Request(f"{base.rstrip('/')}/v1/chat/completions", data=body, headers={
        "Content-Type": "application/json", "Authorization": f"Bearer {key}",
    })
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))["choices"][0]["message"]["content"]


TASKS = [
    {
        "id": "sql_window",
        "name": "SQL 窗口函数",
        "prompt": "表 orders(id, user_id, amount, created_at)。写一条 SQL：找出每个用户最近 3 笔订单的 amount 总和。用 CTE + 窗口函数。",
        "must_have": ["WITH", "ROW_NUMBER", "PARTITION BY", "ORDER BY", "SUM"],
        "expected": "包含 ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY created_at DESC)",
    },
    {
        "id": "data_cleaning",
        "name": "数据清洗（pandas）",
        "prompt": "DataFrame df 有列 age, income, city。age 可能有 NaN 或负数，income 可能有 0 或负数，city 拼写不一致（'BJ'/'Beijing'/'北京'）。\n\n写一段 pandas 代码：1) 删除 age < 0 的行 2) age NaN 填中位数 3) 统一 city 字段 4) 删除 income <= 0 的行。",
        "must_have": ["df[", ".drop", ".fillna", ".median", ".replace", "income", "age"],
        "expected": "用 drop / fillna / replace 等",
    },
    {
        "id": "viz_chooser",
        "name": "可视化选型",
        "prompt": "给以下场景选最合适的图表类型：\n1) 显示某产品过去 12 个月销量趋势\n2) 比较 5 个部门的预算占比\n3) 显示用户年龄 vs 消费金额的关系\n4) 显示某地区 7 天温度变化（带区间）\n\n每题只输出图表名（如 '折线图'、'饼图' 等）。",
        "must_have": ["折线", "饼", "散点", "面积", "柱状", "line", "pie", "scatter", "bar"],
        "expected": "趋势→折线 / 占比→饼 / 关系→散点 / 区间→面积",
    },
    {
        "id": "stats_inference",
        "name": "统计推断",
        "prompt": "对照组（n=50, mean=120, sd=15）和实验组（n=50, mean=130, sd=14）。用 t 检验判断差异是否显著。给出 p-value 近似 + 结论（α=0.05）。\n\n要求：写出计算过程（不必精确算，给出公式和数量级）。",
        "must_have": ["t", "p", "0.05", "显著", "差异"],
        "expected": "t = (130-120)/sqrt(15²/50+14²/50) ≈ 3.4 → p<0.001",
    },
]


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    p.add_argument("--model", default=os.environ.get("MODEL", "gpt-4o"))
    p.add_argument("--base", default=os.environ.get("LLM_API_BASE", ""))
    p.add_argument("--key", default=os.environ.get("LLM_API_KEY", ""))
    p.add_argument("--timeout", type=float, default=60.0)
    p.add_argument("--out", type=Path, default=OUT_DIR / "data_analysis_report.md")
    args = p.parse_args()

    if not (args.base and args.key):
        print("ERROR: 需 --base/--key", file=sys.stderr)
        return 2

    rows = []
    for t in TASKS:
        try:
            ans = call_chat(args.base, args.key, args.model, t["prompt"], args.timeout)
        except Exception as e:
            ans = f"ERROR: {e}"
        hits = [k for k in t["must_have"] if k in ans]
        kw_rate = len(hits) / len(t["must_have"])
        rows.append({
            "task": t, "answer": ans[:300],
            "kw_hits": hits, "kw_rate": kw_rate,
        })
        print(f"  {t['id']}: kw={kw_rate*100:.0f}%")

    if not rows:
        return 0
    avg_kw = statistics.mean(r["kw_rate"] for r in rows)

    lines = [
        "# 数据分析能力\n",
        f"- 目标模型：`{args.model}`",
        f"- 题目数：{len(rows)}",
        f"- **平均关键词覆盖：{avg_kw*100:.0f}%**\n",
        "## 逐题\n",
        "| ID | 名称 | 期望 | 关键词覆盖 |",
        "|----|------|------|------------|",
    ]
    for r in rows:
        lines.append(
            f"| `{r['task']['id']}` | {r['task']['name']} "
            f"| {r['task']['expected'][:50]}… | {r['kw_rate']*100:.0f}% |"
        )

    lines.append("\n## 答案摘录\n")
    for r in rows:
        lines.append(f"### {r['task']['name']}")
        lines.append(f"**关键词命中**：{', '.join(r['kw_hits'])}")
        lines.append(f"**答案（前 200 字）**：{r['answer']}…")
        lines.append("")

    args.out.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
