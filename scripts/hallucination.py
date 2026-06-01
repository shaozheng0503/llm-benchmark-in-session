#!/usr/bin/env python3
"""
minimax-m3-benchmark · hallucination.py

Hallucination 专项检测：从 raw_answers 提取"事实断言"，用 LLM 裁判判定每条
断言是否被外部事实支撑。输出 hallucination rate（每 100 字含多少条
无支撑断言）。

用法：
    LLM_API_BASE=... LLM_API_KEY=... python3 scripts/hallucination.py \\
        --judge-model gpt-4o
"""
from __future__ import annotations

import argparse
import json
import os
import re
import statistics
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CFG = ROOT / "config/test_cases.json"
ANS_DIR = ROOT / "raw_answers"
OUT_DIR = ROOT / "reports/hallucination"
OUT_DIR.mkdir(parents=True, exist_ok=True)

PROMPT = """你是一名事实核查员。从下面这段答案里抽取所有"事实断言"（具体数字、日期、人名、地点、事件等），然后对每条评估 0-1：

- 1.0 = 有充分事实支撑（公认常识 / 题目给定）
- 0.5 = 部分支撑 / 模糊
- 0.0 = 无支撑 / 疑似幻觉

题目：{prompt}
答案：{answer}

**严格 JSON 输出**（不要其他文字）：
{{
  "claims": [
    {{"text": "<断言原文>", "score": <0-1>, "note": "≤30字理由"}},
    ...
  ],
  "overall_hallucination_rate": <0-1>  // 平均 1-score
}}
"""


def call_chat(base, key, model, prompt, timeout=60.0):
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.0,
    }).encode("utf-8")
    req = urllib.request.Request(f"{base.rstrip('/')}/v1/chat/completions", data=body, headers={
        "Content-Type": "application/json", "Authorization": f"Bearer {key}",
    })
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))["choices"][0]["message"]["content"]


def find_answer(case_id):
    for p in ANS_DIR.glob(f"*{case_id}*.md"):
        return p.read_text(encoding="utf-8")
    return ""


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    p.add_argument("--config", type=Path, default=DEFAULT_CFG)
    p.add_argument("--judge-model", default=os.environ.get("JUDGE_MODEL", "gpt-4o"))
    p.add_argument("--base", default=os.environ.get("LLM_API_BASE", ""))
    p.add_argument("--key", default=os.environ.get("LLM_API_KEY", ""))
    p.add_argument("--cases", nargs="*", default=None)
    p.add_argument("--limit", type=int, default=0)
    p.add_argument("--timeout", type=float, default=60.0)
    p.add_argument("--out", type=Path, default=OUT_DIR / "hallucination_report.md")
    args = p.parse_args()

    if not (args.base and args.key):
        print("ERROR: 需 --base/--key", file=sys.stderr)
        return 2

    cfg = json.loads(args.config.read_text(encoding="utf-8"))
    cases = cfg.get("cases", [])
    if args.cases:
        cases = [c for c in cases if c["id"] in set(args.cases)]
    cases = cases[:args.limit] if args.limit else cases

    rows = []
    for c in cases:
        ans = find_answer(c["id"])
        if not ans:
            continue
        user = PROMPT.format(prompt=c["prompt"][:300], answer=ans[:800])
        try:
            resp = call_chat(args.base, args.key, args.judge_model, user, args.timeout)
            m = re.search(r"\{.*\}", resp, re.DOTALL)
            data = json.loads(m.group(0))
            rate = data.get("overall_hallucination_rate", 0)
            claims = data.get("claims", [])
            rows.append({"id": c["id"], "name": c["name"], "category": c["category"],
                         "rate": rate, "n_claims": len(claims),
                         "claims": claims[:5]})
            print(f"  {c['id']}: {len(claims)} claims, hallucination={rate*100:.1f}%")
        except Exception as e:
            rows.append({"id": c["id"], "name": c["name"], "category": c["category"],
                         "rate": -1, "n_claims": 0, "claims": [], "error": str(e)})
            print(f"  {c['id']}: ERROR {e}")

    if not rows:
        print("no data")
        return 0

    valid = [r for r in rows if r["rate"] >= 0]
    avg_rate = statistics.mean(r["rate"] for r in valid) if valid else 0
    total_claims = sum(r["n_claims"] for r in valid)

    lines = [
        "# Hallucination 专项报告\n",
        f"- 裁判模型：`{args.judge_model}`",
        f"- 评估用例数：{len(valid)}/{len(rows)}",
        f"- 提取事实断言总数：{total_claims}",
        f"- **平均 hallucination rate：{avg_rate*100:.2f}%**\n",
        "## 逐题\n",
        "| ID | 类别 | 断言数 | Hallucination Rate |",
        "|----|------|--------|--------------------|",
    ]
    for r in valid:
        rate_pct = f"{r['rate']*100:.1f}%"
        lines.append(f"| `{r['id']}` | {r['category']} | {r['n_claims']} | {rate_pct} |")
    for r in rows:
        if r.get("error"):
            lines.append(f"| `{r['id']}` | — | — | ⚠️ {r.get('error','')} |")

    lines.append("\n## 典型可疑断言（hallucination 最高）\n")
    for r in sorted(valid, key=lambda x: -x["rate"])[:3]:
        for c in r["claims"]:
            if c.get("score", 1) < 0.5:
                lines.append(f"- `{r['id']}`: {c.get('text','')} (score={c.get('score','?')})")
                lines.append(f"  - {c.get('note','')}")

    args.out.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
