#!/usr/bin/env python3
"""
minimax-m3-benchmark · meta_eval.py

裁判模型一致性（Meta-Evaluation）：让 3 个 LLM 裁判独立打分，
计算两两 Cohen's Kappa，评估 rubric 质量与裁判稳健性。

Kappa 解读：
- < 0.4：差（题目或 rubric 设计有问题）
- 0.4-0.6：中
- 0.6-0.8：良
- > 0.8：优

用法：

    # 3 个裁判
    LLM_API_BASE=...  LLM_API_KEY=sk-A \\
    LLM_API_BASE2=... LLM_API_KEY2=sk-B \\
    LLM_API_BASE3=... LLM_API_KEY3=sk-C \\
        python3 scripts/meta_eval.py \\
        --judge-model gpt-4o \\
        --judge-model2 claude-opus-4-8 \\
        --judge-model3 gemini-1.5-pro
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import urllib.request
from datetime import datetime
from itertools import combinations
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CFG = ROOT / "config" / "test_cases.json"
ANS_DIR = ROOT / "raw_answers"
OUT_DIR = ROOT / "reports" / "meta_eval"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def call_chat(base: str, key: str, model: str, prompt: str,
              timeout: float = 60.0) -> str:
    url = f"{base.rstrip('/')}/v1/chat/completions"
    body = json.dumps({
        "model": model, "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.0,
    }).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers={
        "Content-Type": "application/json", "Authorization": f"Bearer {key}",
    }, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))["choices"][0]["message"]["content"]


RUBRIC = """按 1-5 分评估下面答案的整体质量（1=极差, 5=优秀）。
仅输出一行：分数（1-5 整数），不要任何其他文字。

题目：{prompt}
答案：{answer}
分数："""


def cohen_kappa(a: list[int], b: list[int]) -> float:
    """Cohen's Kappa 计算。"""
    assert len(a) == len(b)
    n = len(a)
    if n == 0:
        return 0.0
    categories = sorted(set(a) | set(b))
    po = sum(1 for x, y in zip(a, b) if x == y) / n
    pe = 0.0
    for c in categories:
        pe += (a.count(c) / n) * (b.count(c) / n)
    if pe == 1.0:
        return 1.0
    return round((po - pe) / (1 - pe), 3)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    p.add_argument("--config", type=Path, default=DEFAULT_CFG)
    p.add_argument("--judge-model", required=True)
    p.add_argument("--base", default=os.environ.get("LLM_API_BASE", ""))
    p.add_argument("--key", default=os.environ.get("LLM_API_KEY", ""))
    p.add_argument("--judge-model2", default="")
    p.add_argument("--base2", default=os.environ.get("LLM_API_BASE2", ""))
    p.add_argument("--key2", default=os.environ.get("LLM_API_KEY2", ""))
    p.add_argument("--judge-model3", default="")
    p.add_argument("--base3", default=os.environ.get("LLM_API_BASE3", ""))
    p.add_argument("--key3", default=os.environ.get("LLM_API_KEY3", ""))
    p.add_argument("--limit", type=int, default=0)
    p.add_argument("--cases", nargs="*", default=None)
    p.add_argument("--timeout", type=float, default=60.0)
    p.add_argument("--out", type=Path,
                   default=OUT_DIR / "meta_eval_report.md")
    args = p.parse_args()

    if not (args.base and args.key):
        print("ERROR: 至少需要 --base/--key", file=sys.stderr)
        return 2

    judges = [
        (args.judge_model, args.base, args.key),
        (args.judge_model2, args.base2, args.key2),
        (args.judge_model3, args.base3, args.key3),
    ]
    judges = [(m, b, k) for m, b, k in judges if m and b and k]
    if len(judges) < 2:
        print("ERROR: 至少需要 2 个裁判", file=sys.stderr)
        return 2

    cfg = json.loads(args.config.read_text(encoding="utf-8"))
    cases = cfg.get("cases", [])
    if args.cases:
        cases = [c for c in cases if c["id"] in set(args.cases)]
    cases = cases[:args.limit] if args.limit else cases

    # 收集每个 case 的答案
    case_data = []
    for c in cases:
        ap = next(ANS_DIR.glob(f"*{c['id']}*.md"), None)
        if not ap:
            continue
        case_data.append({
            "id": c["id"], "name": c["name"],
            "prompt": c["prompt"], "answer": ap.read_text(encoding="utf-8"),
        })

    # 每个裁判打分
    print(f"用 {len(judges)} 个裁判打 {len(case_data)} 题...")
    scores_by_judge: dict[str, list[int]] = {}
    for jname, base, key in judges:
        scores: list[int] = []
        for cd in case_data:
            user = RUBRIC.format(prompt=cd["prompt"][:300],
                                 answer=cd["answer"][:600])
            try:
                resp = call_chat(base, key, jname, user, args.timeout)
                # 提取 1-5 的数字
                import re
                m = re.search(r"[1-5]", resp.strip())
                s = int(m.group(0)) if m else 3
            except Exception as e:
                print(f"  [{jname}] {cd['id']} error: {e}")
                s = 3
            scores.append(s)
        scores_by_judge[jname] = scores
        print(f"  [{jname}] mean={statistics.mean(scores):.2f}")

    # 两两 Kappa
    judge_names = list(scores_by_judge.keys())
    pairs = list(combinations(judge_names, 2))
    kappas: dict[tuple[str, str], float] = {}
    for a, b in pairs:
        kappas[(a, b)] = cohen_kappa(scores_by_judge[a], scores_by_judge[b])

    avg_kappa = round(statistics.mean(kappas.values()), 3)

    # 报告
    lines = [
        "# 裁判一致性元评估\n",
        f"- 时间：{datetime.now().isoformat(timespec='seconds')}",
        f"- 题目数：{len(case_data)}",
        f"- 裁判数：{len(judge_names)}",
        f"- **平均 Cohen's Kappa：{avg_kappa}**\n",
        "## 裁判两两一致性\n",
        "| 裁判 A | 裁判 B | Kappa | 解读 |",
        "|--------|--------|-------|------|",
    ]
    for (a, b), k in kappas.items():
        if k < 0.4:
            interp = "差"
        elif k < 0.6:
            interp = "中"
        elif k < 0.8:
            interp = "良"
        else:
            interp = "优"
        lines.append(f"| {a} | {b} | {k} | {interp} |")
    lines.append("")

    # 每题所有裁判打分
    lines.append("## 每题打分（每列 = 1 个裁判）\n")
    lines.append("| ID | " + " | ".join(judge_names) + " | 一致？ |")
    lines.append("|" + "---|" * (len(judge_names) + 2))
    for i, cd in enumerate(case_data):
        scores = [scores_by_judge[j][i] for j in judge_names]
        spread = max(scores) - min(scores)
        consistent = "✅" if spread <= 1 else "⚠️" if spread <= 2 else "❌"
        lines.append(
            f"| {cd['id']} | " + " | ".join(str(s) for s in scores) +
            f" | {consistent} (Δ={spread}) |"
        )

    lines.append("\n## 建议")
    if avg_kappa < 0.4:
        lines.append("- **Kappa 过低**：rubric 设计可能太模糊，题目可能有歧义。建议：")
        lines.append("  - 显式列出评分维度和锚点示例（exemplar）")
        lines.append("  - 缩小评分尺度（用 1-3 而非 1-5）")
        lines.append("  - 拆分多维度独立评分")
    elif avg_kappa < 0.6:
        lines.append("- Kappa 中等：rubric 仍有改进空间，建议补 exemplar。")
    else:
        lines.append("- Kappa 良好，rubric 鲁棒。")

    args.out.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nwrote {args.out}  (avg Kappa = {avg_kappa})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
