#!/usr/bin/env python3
"""
minimax-m3-benchmark · code_agent.py

代码 agent 综合能力：多语言 / debug / 性能 / 架构 4 类。

用法：
    LLM_API_BASE=... LLM_API_KEY=... python3 scripts/code_agent.py
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
OUT_DIR = ROOT / "reports" / "code_agent"
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
        "id": "multilang",
        "name": "多语言翻译（同一算法在 3 种语言）",
        "prompt": "用 Python / Go / Rust 各实现一个'最长回文子串'算法。每种语言 ≤ 20 行。\n\n输出格式：\n```python\n# code\n```\n```go\n// code\n```\n```rust\n// code\n```",
        "must_have": ["def ", "func ", "fn "],
        "rubric": "3 语言都实现 + 算法正确",
    },
    {
        "id": "debug",
        "name": "Debug 性能问题",
        "prompt": "下面这段 Python 跑了 10 分钟还没完，请诊断性能问题并优化到 1 秒内：\n```python\ndef process(data):\n    result = []\n    for i in range(len(data)):\n        for j in range(len(data)):\n            if i != j and data[i] == data[j]:\n                result.append((i, j))\n    return result\n\nprocess([1, 2, 3, 4, 5] * 1000)\n```\n要求：指出问题、给出优化版代码、解释为什么快。",
        "must_have": ["O(n²)", "set", "字典", "Counter", "O(n)"],
        "rubric": "识别 O(n²) 并用 O(n) 优化",
    },
    {
        "id": "performance",
        "name": "代码复杂度分析",
        "prompt": "分析下面代码的时间和空间复杂度：\n```python\ndef foo(arr):\n    n = len(arr)\n    for i in range(n):\n        for j in range(n):\n            for k in range(n):\n                if arr[i] + arr[j] + arr[k] == 0:\n                    print(i, j, k)\n```\n只输出时间和空间复杂度（用 Big-O 记法）。",
        "must_have": ["O(n³)", "O(1)"],
        "rubric": "正确说出 O(n³) / O(1)",
    },
    {
        "id": "architecture",
        "name": "系统设计（短链服务）",
        "prompt": "设计一个支持 100 万 QPS 的短链服务（短链 → 长链映射）。用 200 字内说：1) 存储选型 2) 缓存策略 3) 限流方案 4) 域名分配。",
        "must_have": ["Redis", "MySQL", "限流", "CDN", "QPS", "哈希", "hash"],
        "rubric": "覆盖存储/缓存/限流/编码 4 维",
    },
]


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    p.add_argument("--model", default=os.environ.get("MODEL", "gpt-4o"))
    p.add_argument("--base", default=os.environ.get("LLM_API_BASE", ""))
    p.add_argument("--key", default=os.environ.get("LLM_API_KEY", ""))
    p.add_argument("--timeout", type=float, default=60.0)
    p.add_argument("--out", type=Path, default=OUT_DIR / "code_agent_report.md")
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
        print(f"  {t['id']}: kw={kw_rate*100:.0f}%  ans_len={len(ans)}")

    if not rows:
        return 0
    avg_kw = statistics.mean(r["kw_rate"] for r in rows)

    lines = [
        "# Code Agent 综合能力\n",
        f"- 目标模型：`{args.model}`",
        f"- 题目数：{len(rows)}",
        f"- **平均关键词覆盖：{avg_kw*100:.0f}%**\n",
        "## 逐题\n",
        "| ID | 名称 | 关键词覆盖 | 关键词命中 |",
        "|----|------|------------|-----------|",
    ]
    for r in rows:
        lines.append(
            f"| `{r['task']['id']}` | {r['task']['name']} "
            f"| {r['kw_rate']*100:.0f}% | {', '.join(r['kw_hits'])} |"
        )

    lines.append("\n## 答案摘录\n")
    for r in rows:
        lines.append(f"### {r['task']['name']}")
        lines.append(f"**Rubric**：{r['task']['rubric']}")
        lines.append(f"**答案（前 200 字）**：{r['answer']}…")
        lines.append("")

    args.out.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
