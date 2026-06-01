#!/usr/bin/env python3
"""
minimax-m3-benchmark · calibration.py

置信度校准（calibration）评估：从 raw_answers/23_calibration.md 提取
模型的"答案 + 置信度"，与 ground truth 对比，计算 ECE
（Expected Calibration Error）。

ECE 越低，模型越"知之为知之"（高置信度对应高准确率）。

用法：

    python3 scripts/calibration.py
    python3 scripts/calibration.py --answer-file raw_answers/23_calibration.md
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ANS = ROOT / "raw_answers" / "23_calibration.md"
OUT_DIR = ROOT / "reports" / "calibration"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ground truth —— 与 test_cases.json 中的 calibration 题目对应
GROUND_TRUTH = {
    "q1": {"answer": "B", "note": "H₂O"},
    "q2": {"answer": "D", "note": "吴泳铭（2023 接任，至 2026 仍为董事长）"},
    "q3": {"answer": "B", "note": "Guido van Rossum"},
    "q4": {"answer": "A", "note": "Hopfield & Hinton（机器学习先驱）"},
    "q5": {"answer": "B", "note": "2003 神舟五号 / 杨利伟"},
}


def extract_json(text: str) -> dict:
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if m:
        return json.loads(m.group(1))
    return json.loads(text.strip())


def ece(probs: list[float], correct: list[bool], n_bins: int = 10) -> float:
    """Expected Calibration Error.

    probs: 每题置信度（0-100 的 int 或 0-1 的 float）
    correct: 每题是否答对
    """
    probs_norm = [p / 100.0 if p > 1 else p for p in probs]
    bins = [[] for _ in range(n_bins)]
    for p, c in zip(probs_norm, correct):
        b = min(int(p * n_bins), n_bins - 1)
        bins[b].append((p, c))
    ece_val = 0.0
    n = len(probs)
    for b in bins:
        if not b:
            continue
        avg_p = sum(p for p, _ in b) / len(b)
        avg_c = sum(1 for _, c in b if c) / len(b)
        ece_val += (len(b) / n) * abs(avg_p - avg_c)
    return round(ece_val, 4)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    p.add_argument("--answer-file", type=Path, default=DEFAULT_ANS)
    p.add_argument("--out", type=Path,
                   default=OUT_DIR / "calibration_report.md")
    args = p.parse_args()

    if not args.answer_file.exists():
        print(f"ERROR: {args.answer_file} not found.", file=sys.stderr)
        return 2
    text = args.answer_file.read_text(encoding="utf-8")
    try:
        data = extract_json(text)
    except json.JSONDecodeError as e:
        print(f"ERROR: cannot parse JSON: {e}", file=sys.stderr)
        return 3

    rows: list[dict] = []
    for qid, gt in GROUND_TRUTH.items():
        if qid not in data:
            rows.append({"qid": qid, "ok": False, "note": "missing in answer"})
            continue
        ans = data[qid].get("answer", "").strip().upper()
        conf = data[qid].get("confidence", 0)
        ok = ans == gt["answer"]
        rows.append({
            "qid": qid,
            "expected": gt["answer"],
            "actual": ans,
            "confidence": conf,
            "ok": ok,
            "note": gt["note"],
        })

    probs = [r.get("confidence", 0) for r in rows if "confidence" in r]
    correct = [r["ok"] for r in rows if "confidence" in r]
    ece_val = ece(probs, correct) if probs else 0.0
    acc = sum(correct) / len(correct) if correct else 0.0
    avg_conf = sum(probs) / len(probs) / 100 if probs else 0.0

    # 渲染
    lines = [
        "# 置信度校准（Calibration）报告\n",
        f"- 答案文件：`{args.answer_file.name}`",
        f"- 题目数：{len(rows)}",
        f"- 准确率：**{round(acc * 100, 1)}%**",
        f"- 平均置信度：**{round(avg_conf * 100, 1)}%**",
        f"- **ECE = {ece_val}**（越小越好，理想 = 0）\n",
        "## 逐题对比\n",
        "| # | 期望 | 实际 | 置信度 | 是否答对 | 备注 |",
        "|---|------|------|--------|----------|------|",
    ]
    for r in rows:
        mark = "✅" if r.get("ok") else "❌"
        lines.append(
            f"| {r['qid']} | {r.get('expected','?')} | {r.get('actual','?')} "
            f"| {r.get('confidence', '-')}% | {mark} | {r.get('note','')} |"
        )

    # 校准分桶
    lines.append("\n## 校准分桶（每 10% 一档）\n")
    lines.append("| 置信区间 | 题数 | 答对率 | 平均置信度 | 偏差 |")
    lines.append("|----------|------|--------|-----------|------|")
    n_bins = 10
    bins = [[] for _ in range(n_bins)]
    for r in rows:
        if "confidence" not in r:
            continue
        b = min(int(r["confidence"] / 100 * n_bins), n_bins - 1)
        bins[b].append(r)
    for b in range(n_bins):
        lo, hi = b * 10, (b + 1) * 10
        items = bins[b]
        if not items:
            continue
        avg_conf = sum(r["confidence"] for r in items) / len(items) / 100
        acc_rate = sum(1 for r in items if r.get("ok")) / len(items)
        bias = round((avg_conf - acc_rate) * 100, 1)
        lines.append(
            f"| {lo}-{hi}% | {len(items)} | {round(acc_rate*100,1)}% "
            f"| {round(avg_conf*100,1)}% | {bias:+}% |"
        )

    # 解读
    lines.append("\n## 解读")
    if ece_val < 0.1:
        lines.append(f"**ECE = {ece_val} 优秀** —— 模型置信度与准确率高度一致。")
    elif ece_val < 0.2:
        lines.append(f"**ECE = {ece_val} 中等** —— 有一定偏差，但可接受。")
    else:
        lines.append(f"**ECE = {ece_val} 较差** —— 显著过度自信或过度谦逊。")
    if avg_conf > acc + 0.1:
        lines.append("- 模型**过度自信**（高置信度但答错比例高）。")
    elif acc > avg_conf + 0.1:
        lines.append("- 模型**过度谦逊**（低置信度但答对比例高）。")

    args.out.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {args.out}  (ECE={ece_val}, acc={acc*100}%, avg_conf={avg_conf*100}%)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
