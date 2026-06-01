#!/usr/bin/env python3
"""
minimax-m3-benchmark · spatial_reasoning.py

3D 空间推理：给定 3D 坐标描述，让模型判断距离/视角/相对位置。

10 道题，输出结构化答案 + 评分。

用法：
    LLM_API_BASE=... LLM_API_KEY=... python3 scripts/spatial_reasoning.py
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "reports" / "spatial"
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


# 10 道 3D 题
QUESTIONS = [
    {
        "id": "dist_basic",
        "prompt": "点 A 在 (0, 0, 0)，点 B 在 (3, 4, 0)。A 到 B 的欧几里得距离是多少？只输出数字（保留 2 位小数）。",
        "answer": "5.00",
        "check": lambda out: "5" in out,
    },
    {
        "id": "dist_3d",
        "prompt": "点 A 在 (1, 2, 3)，点 B 在 (4, 6, 3)。A 到 B 的距离是多少？只输出数字。",
        "answer": "5.00",
        "check": lambda out: "5" in out,
    },
    {
        "id": "angle_xy",
        "prompt": "向量 v1 = (1, 0, 0)，向量 v2 = (0, 1, 0)。它们的夹角（度）是多少？",
        "answer": "90",
        "check": lambda out: "90" in out,
    },
    {
        "id": "angle_3d",
        "prompt": "向量 v1 = (1, 1, 0)，向量 v2 = (1, 0, 0)。它们的夹角（度，保留整数）是多少？",
        "answer": "45",
        "check": lambda out: "45" in out,
    },
    {
        "id": "midpoint",
        "prompt": "点 A 在 (0, 0, 0)，点 B 在 (4, 6, 8)。中点 M 的坐标？格式：(x, y, z)",
        "answer": "(2, 3, 4)",
        "check": lambda out: all(c in out for c in ["2", "3", "4"]),
    },
    {
        "id": "volume_box",
        "prompt": "一个长方体的长宽高分别是 3、4、5。体积是多少？",
        "answer": "60",
        "check": lambda out: "60" in out,
    },
    {
        "id": "surface_sphere",
        "prompt": "球的半径是 3。表面积是多少？（π 取 3.14，保留 2 位小数）",
        "answer": "113.04",
        "check": lambda out: "113" in out,
    },
    {
        "id": "above_below",
        "prompt": "点 A 在 (0, 0, 5)，点 B 在 (0, 0, -3)。A 在 B 的什么方向？A. 上方 B. 下方 C. 左方 D. 右方",
        "answer": "A",
        "check": lambda out: "A" in out and "上方" in out,
    },
    {
        "id": "left_right",
        "prompt": "从观察者 O 看：A 在 (1, 0, 0)，B 在 (-2, 0, 0)。哪个在左边？只输出字母。",
        "answer": "B",
        "check": lambda out: "B" in out,
    },
    {
        "id": "behind_ahead",
        "prompt": "观察者面朝 +Z 方向（前方）。A 在 (0, 0, 5)，B 在 (0, 0, -3)。哪个在前方？只输出字母。",
        "answer": "A",
        "check": lambda out: "A" in out,
    },
]


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    p.add_argument("--model", default=os.environ.get("MODEL", "gpt-4o-mini"))
    p.add_argument("--base", default=os.environ.get("LLM_API_BASE", ""))
    p.add_argument("--key", default=os.environ.get("LLM_API_KEY", ""))
    p.add_argument("--timeout", type=float, default=60.0)
    p.add_argument("--out", type=Path, default=OUT_DIR / "spatial_report.md")
    args = p.parse_args()

    if not (args.base and args.key):
        print("ERROR: 需 --base/--key", file=sys.stderr)
        return 2

    rows = []
    for q in QUESTIONS:
        try:
            ans = call_chat(args.base, args.key, args.model, q["prompt"], args.timeout)
        except Exception as e:
            ans = f"ERROR: {e}"
        ok = q["check"](ans)
        rows.append({"q": q, "answer": ans[:200], "passed": ok})
        print(f"  {q['id']}: {'✅' if ok else '❌'}  gt={q['answer']}")

    passed = sum(1 for r in rows if r["passed"])
    rate = passed / len(rows) * 100

    lines = [
        "# 3D 空间推理测试\n",
        f"- 目标模型：`{args.model}`",
        f"- 题目数：{len(rows)}",
        f"- **通过：{passed}/{len(rows)} = {rate:.0f}%**\n",
        "## 逐题\n",
        "| ID | 描述 | 期望 | 模型答案 | 通过 |",
        "|----|------|------|----------|------|",
    ]
    for r in rows:
        q = r["q"]
        desc = q["prompt"][:40]
        lines.append(
            f"| `{q['id']}` | {desc} | {q['answer']} | {r['answer'][:30]} | "
            f"{'✅' if r['passed'] else '❌'} |"
        )

    lines.append("\n## 失败题目\n")
    for r in rows:
        if not r["passed"]:
            lines.append(f"- **{r['q']['id']}**：期望 `{r['q']['answer']}`，模型输出 `{r['answer']}`")

    args.out.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
