#!/usr/bin/env python3
"""
minimax-m3-benchmark · significance.py

统计显著性检验：用 bootstrap 重采样算 95% CI 和 p-value，
让"100% vs 90%" 不再是绝对值，而是"p=0.07 不显著"。

用法：
    python3 scripts/significance.py
    python3 scripts/significance.py --compare reports/history/v1.2.json current
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RESULTS = ROOT / "reports/cases/cases_results.json"
DEFAULT_HISTORY_DIR = ROOT / "reports/history"
OUT_DIR = ROOT / "reports/significance"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def bootstrap_ci(pcts: list[float], n_boot: int = 1000,
                 ci: float = 0.95) -> tuple[float, float, float]:
    """返回 (mean, low, high) 的百分位 bootstrap CI。"""
    if not pcts:
        return 0.0, 0.0, 0.0
    means = []
    for _ in range(n_boot):
        sample = [random.choice(pcts) for _ in pcts]
        means.append(sum(sample) / len(sample))
    means.sort()
    lo_idx = int((1 - ci) / 2 * n_boot)
    hi_idx = int((1 + ci) / 2 * n_boot)
    return sum(pcts) / len(pcts), means[lo_idx], means[hi_idx]


def permutation_pvalue(pcts_a: list[float], pcts_b: list[float],
                       n_perm: int = 1000) -> float:
    """Permutation test: H0 两组无差异。"""
    if not pcts_a or not pcts_b:
        return 1.0
    observed_diff = abs(sum(pcts_a) / len(pcts_a) - sum(pcts_b) / len(pcts_b))
    combined = pcts_a + pcts_b
    n_a = len(pcts_a)
    count = 0
    for _ in range(n_perm):
        random.shuffle(combined)
        a = combined[:n_a]
        b = combined[n_a:]
        diff = abs(sum(a) / len(a) - sum(b) / len(b))
        if diff >= observed_diff:
            count += 1
    return count / n_perm


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    p.add_argument("--current", type=Path, default=DEFAULT_RESULTS)
    p.add_argument("--baseline", type=Path, default=None)
    p.add_argument("--n-boot", type=int, default=1000)
    p.add_argument("--out", type=Path, default=OUT_DIR / "significance_report.md")
    args = p.parse_args()

    if not args.current.exists():
        print(f"ERROR: {args.current} not found", file=sys.stderr)
        return 2

    cur = json.loads(args.current.read_text(encoding="utf-8"))
    cur_pcts = [r["pct"] for r in cur.get("results", []) if not r.get("error")]

    # 找 baseline（用户指定 or 最新历史快照）
    if args.baseline:
        base = json.loads(args.baseline.read_text(encoding="utf-8"))
    else:
        history = sorted(DEFAULT_HISTORY_DIR.glob("v*.json"))
        if len(history) < 1:
            print("ERROR: 无历史 baseline", file=sys.stderr)
            return 2
        # 取除当前之外最新
        if str(cur.get("version", "")) and history[-1].stem == f"v{cur['version']}":
            history = history[:-1]
        if not history:
            print("ERROR: 无更早历史", file=sys.stderr)
            return 2
        base = json.loads(history[-1].read_text(encoding="utf-8"))

    base_pcts = [r["pct"] for r in base.get("results", []) if not r.get("error")]

    # 当前
    cur_mean, cur_lo, cur_hi = bootstrap_ci(cur_pcts, args.n_boot)
    # baseline
    base_mean, base_lo, base_hi = bootstrap_ci(base_pcts, args.n_boot)
    # p-value
    p_val = permutation_pvalue(cur_pcts, base_pcts, args.n_boot)
    delta = cur_mean - base_mean
    significant = "✅ 显著" if p_val < 0.05 else "❌ 不显著"

    # 逐题对比
    cur_by_id = {r["id"]: r["pct"] for r in cur["results"]}
    base_by_id = {r["id"]: r["pct"] for r in base["results"]}
    common_ids = set(cur_by_id) & set(base_by_id)
    rows = []
    for cid in sorted(common_ids):
        c, b = cur_by_id[cid], base_by_id[cid]
        d = c - b
        rows.append((cid, b, c, d))

    # 报告
    lines = [
        "# 统计显著性报告\n",
        f"- 当前：`{args.current.name}` (v{cur.get('version','?')})",
        f"- baseline：`{args.baseline.name if args.baseline else 'latest history'}`",
        f"- 重采样次数：{args.n_boot}\n",
        "## 总体\n",
        "| 指标 | 当前 | baseline | 95% CI |",
        "|------|------|----------|--------|",
        f"| 平均 | {cur_mean:.2f}% | {base_mean:.2f}% | ±{(cur_hi-cur_lo)/2:.2f} |",
        f"| 下界 | {cur_lo:.2f}% | {base_lo:.2f}% | — |",
        f"| 上界 | {cur_hi:.2f}% | {base_hi:.2f}% | — |",
        "",
        f"**Δ = {delta:+.2f}%, p-value = {p_val:.3f} → {significant}**\n",
        "## 逐题对比\n",
        "| ID | baseline | current | Δ |",
        "|----|----------|---------|---|",
    ]
    for cid, b, c, d in rows:
        lines.append(f"| `{cid}` | {b:.1f}% | {c:.1f}% | {d:+.1f}% |")

    # 解读
    lines.append("\n## 解读")
    if abs(delta) < 1:
        lines.append("- Δ < 1%，基本无变化。")
    elif delta > 0:
        lines.append(f"- 提升 {delta:.1f}%，{'统计显著' if p_val < 0.05 else '**但未达统计显著**'}。")
    else:
        lines.append(f"- 退步 {abs(delta):.1f}%，{'统计显著' if p_val < 0.05 else '**但未达统计显著**'}。")
    lines.append(f"- p-value = {p_val:.3f}（< 0.05 为显著，< 0.01 为强显著）")

    args.out.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {args.out}")
    print(f"Δ = {delta:+.2f}%, p = {p_val:.3f} ({significant})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
