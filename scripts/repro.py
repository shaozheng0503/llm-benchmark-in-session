#!/usr/bin/env python3
"""
minimax-m3-benchmark · repro.py

可复现性测试：同 prompt 跑 N 次（默认 temperature=0），看输出是否完全一致。
计算"完全一致率"和"非确定性题目"清单。

用法：
    LLM_API_BASE=... LLM_API_KEY=... python3 scripts/repro.py --rounds 3
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
DEFAULT_CFG = ROOT / "config/test_cases.json"
OUT_DIR = ROOT / "reports" / "reproducibility"
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


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    p.add_argument("--config", type=Path, default=DEFAULT_CFG)
    p.add_argument("--model", default=os.environ.get("MODEL", "gpt-4o-mini"))
    p.add_argument("--base", default=os.environ.get("LLM_API_BASE", ""))
    p.add_argument("--key", default=os.environ.get("LLM_API_KEY", ""))
    p.add_argument("--rounds", type=int, default=3)
    p.add_argument("--temperature", type=float, default=0.0)
    p.add_argument("--cases", nargs="*", default=None)
    p.add_argument("--limit", type=int, default=0)
    p.add_argument("--timeout", type=float, default=60.0)
    p.add_argument("--out", type=Path, default=OUT_DIR / "repro_report.md")
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
        print(f"running {c['id']} × {args.rounds} (T={args.temperature})...")
        answers = []
        for _ in range(args.rounds):
            try:
                ans = call_chat(args.base, args.key, args.model,
                                c["prompt"], args.timeout, args.temperature)
                answers.append(ans)
            except Exception as e:
                answers.append(f"ERROR: {e}")
        unique = len(set(answers))
        reproducible = unique == 1
        rows.append({
            "id": c["id"], "name": c["name"],
            "rounds": args.rounds, "unique_answers": unique,
            "reproducible": reproducible,
        })
        print(f"  → {unique} unique answers ({'✅' if reproducible else '❌'})")

    graded = [r for r in rows]
    repro_pct = round(100 * sum(1 for r in graded if r["reproducible"]) / max(len(graded), 1), 1)
    avg_unique = statistics.mean(r["unique_answers"] for r in graded)

    lines = [
        "# 可复现性报告\n",
        f"- 目标模型：`{args.model}`",
        f"- 每题轮数：{args.rounds}",
        f"- Temperature：{args.temperature}",
        f"- **完全可复现比例：{repro_pct}%**",
        f"- 平均 unique 答案数：{avg_unique:.2f}\n",
        "| ID | 名称 | unique 数 | 可复现 |",
        "|----|------|-----------|--------|",
    ]
    for r in rows:
        mark = "✅" if r["reproducible"] else "❌"
        lines.append(f"| `{r['id']}` | {r['name']} | {r['unique_answers']} | {mark} |")

    lines.append("\n## 解读")
    if repro_pct == 100:
        lines.append("- 完全可复现，模型在 temperature=0 下稳定。")
    elif repro_pct >= 80:
        lines.append("- 大部分可复现，少量题目有随机性。")
    else:
        lines.append("- 大量题目不可复现，可能 temperature > 0 或模型本身有非确定性。")

    if args.temperature > 0:
        lines.append("\n> temperature > 0 时，期望出现随机性。")

    args.out.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
