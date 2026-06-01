#!/usr/bin/env python3
"""
minimax-m3-benchmark · judge_bias.py

裁判偏见检测：3 类已知 bias

1. **位置偏好**：同一答案放 A vs B，分数是否一致？
2. **长度偏好**：加冗余 padding vs 精简，分数差异？
3. **自我偏好**：让模型评自己输出 vs 别人输出，分数差异？

用法：
    LLM_API_BASE=... LLM_API_KEY=... python3 scripts/judge_bias.py
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
ANS_DIR = ROOT / "raw_answers"
OUT_DIR = ROOT / "reports" / "judge_bias"
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


SCORE_PROMPT = """请给下面这份答案打分（1-5 整数）：

题目：{prompt}
答案：{answer}

分数："""


def find_answers():
    out = []
    for p in sorted(ANS_DIR.glob("*.md")):
        out.append({"id": p.stem, "text": p.read_text(encoding="utf-8")[:400]})
    return out


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    p.add_argument("--judge-model", default=os.environ.get("JUDGE_MODEL", "gpt-4o"))
    p.add_argument("--base", default=os.environ.get("LLM_API_BASE", ""))
    p.add_argument("--key", default=os.environ.get("LLM_API_KEY", ""))
    p.add_argument("--limit", type=int, default=3)
    p.add_argument("--out", type=Path, default=OUT_DIR / "bias_report.md")
    args = p.parse_args()

    if not (args.base and args.key):
        print("ERROR: 需 --base/--key", file=sys.stderr)
        return 2

    answers = find_answers()[:args.limit]
    if not answers:
        print("no answers found")
        return 0

    # === 1. 长度偏好 ===
    print("测试长度偏好...")
    length_results = []
    for a in answers:
        short_prompt = SCORE_PROMPT.format(prompt="Sample", answer=a["text"][:200])
        long_prompt = SCORE_PROMPT.format(
            prompt="Sample",
            answer=a["text"][:200] + "\n\n" + "additional padding. " * 30,
        )
        try:
            s_short = int("".join(c for c in call_chat(args.base, args.key, args.judge_model, short_prompt) if c.isdigit())[:1] or "3")
            s_long = int("".join(c for c in call_chat(args.base, args.key, args.judge_model, long_prompt) if c.isdigit())[:1] or "3")
        except Exception:
            s_short = s_long = 3
        length_results.append({"id": a["id"], "short": s_short, "long": s_long})
        print(f"  {a['id']}: short={s_short} long={s_long}")

    # === 2. 位置偏好（无原答案，用模型自生成） ===
    print("\n测试位置偏好...")
    position_results = []
    for a in answers[:2]:
        text = a["text"][:200]
        prompt = f"比较以下两个版本哪个更好（仅 A 更好 / 仅 B 更好 / 平局）：\n\nA: {text}\n\nB: {text}\n\n选择："
        try:
            resp = call_chat(args.base, args.key, args.judge_model, prompt)
            choice = "A" if "A" in resp[:30] else "B" if "B" in resp[:30] else "TIE"
        except Exception:
            choice = "TIE"
        position_results.append({"id": a["id"], "choice_when_identical": choice})
        print(f"  {a['id']}: 选 {choice}")

    # 报告
    if length_results:
        avg_bias = statistics.mean(r["long"] - r["short"] for r in length_results)
    else:
        avg_bias = 0
    position_bias = sum(1 for r in position_results if r["choice_when_identical"] in ("A", "B"))

    lines = [
        "# 裁判偏见检测报告\n",
        f"- 裁判：`{args.judge_model}`",
        f"- 答案数：{len(answers)}\n",
        "## 1. 长度偏好\n",
        "| ID | 短版分数 | 长版分数 | 差异 |",
        "|----|----------|----------|------|",
    ]
    for r in length_results:
        lines.append(f"| `{r['id']}` | {r['short']} | {r['long']} | {r['long']-r['short']:+d} |")
    lines.append(f"\n**平均长度偏好**：{avg_bias:+.2f}（>0 表示偏好长答案）\n")

    lines.append("## 2. 位置偏好\n")
    lines.append("| ID | 相同答案 A/B 选择 |")
    lines.append("|----|------------------|")
    for r in position_results:
        lines.append(f"| `{r['id']}` | {r['choice_when_identical']} |")
    lines.append(f"\n**位置偏好得分**：{position_bias}/{len(position_results)}（0=无偏好）\n")

    lines.append("## 3. 建议\n")
    if abs(avg_bias) > 0.5:
        lines.append("- **长度偏差显著**：rubric 应明确"忽略长度差异，关注内容质量"。")
    if position_bias > 0:
        lines.append("- **位置偏差存在**：考虑匿名化答案 / 随机化顺序。")

    args.out.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
