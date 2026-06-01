#!/usr/bin/env python3
"""
minimax-m3-benchmark · radar.py

把 benchmark 结果画成雷达图，支持多版本曲线叠加。

用法：

    # 单版本（当前 latest）
    python3 scripts/radar.py

    # 多版本叠加
    python3 scripts/radar.py --versions v1.1 v1.2 v1.3

    # 自定义输入
    python3 scripts/radar.py --inputs reports/cases/cases_results.json \\
        --inputs reports/history/v1.2.json --labels current v1.2
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUTS = [ROOT / "reports" / "cases" / "cases_results.json"]
DEFAULT_OUT = ROOT / "reports" / "radar.png"


def load_results(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def aggregate_by_category(data: dict) -> dict[str, float]:
    """把 results 按 category 聚合：取平均 pct。"""
    by_cat: dict[str, list[float]] = {}
    for r in data.get("results", []):
        cat = r.get("category", "uncategorized")
        if "error" in r and r["error"]:
            continue
        by_cat.setdefault(cat, []).append(r.get("pct", 0))
    return {k: round(sum(v) / len(v), 1) for k, v in by_cat.items()}


def plot_radar(datasets: list[tuple[str, dict[str, float]]], out: Path) -> None:
    if not datasets:
        print("no data to plot", file=sys.stderr)
        return
    categories = sorted({c for _, d in datasets for c in d.keys()})
    if not categories:
        print("no categories found", file=sys.stderr)
        return

    n = len(categories)
    angles = np.linspace(0, 2 * np.pi, n, endpoint=False).tolist()
    angles += angles[:1]  # 闭合

    fig, ax = plt.subplots(
        figsize=(10, 10), subplot_kw=dict(polar=True)
    )
    ax.set_theta_offset(np.pi / 2)
    ax.set_theta_direction(-1)
    ax.set_rlabel_position(0)
    ax.set_ylim(0, 100)
    ax.set_yticks([20, 40, 60, 80, 100])
    ax.set_yticklabels(["20", "40", "60", "80", "100"], color="gray", size=8)
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(categories, size=10)
    ax.grid(True, alpha=0.3)

    colors = plt.cm.tab10(np.linspace(0, 1, max(len(datasets), 3)))
    for i, (label, data) in enumerate(datasets):
        vals = [data.get(c, 0) for c in categories]
        vals += vals[:1]
        ax.plot(angles, vals, color=colors[i % len(colors)],
                linewidth=2, label=label)
        ax.fill(angles, vals, color=colors[i % len(colors)], alpha=0.10)

    ax.legend(loc="upper right", bbox_to_anchor=(1.30, 1.10), fontsize=10)
    plt.title("LLM Benchmark Radar — by Category", size=14, pad=20)
    plt.tight_layout()
    out.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out, dpi=120, bbox_inches="tight")
    plt.close(fig)
    print(f"wrote {out}")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    p.add_argument("--inputs", nargs="+", type=Path, default=None,
                   help="JSON 结果文件路径列表")
    p.add_argument("--labels", nargs="+", default=None,
                   help="每个 input 对应的标签")
    p.add_argument("--versions", nargs="+", default=None,
                   help="reports/history/ 下的版本号（自动拼路径）")
    p.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = p.parse_args()

    inputs: list[Path] = []
    labels: list[str] = []
    if args.inputs:
        inputs.extend(args.inputs)
        if args.labels:
            labels.extend(args.labels)
        else:
            labels.extend(p.stem for p in args.inputs)
    if args.versions:
        for v in args.versions:
            tag = v if v.startswith("v") else f"v{v}"
            inputs.append(ROOT / "reports" / "history" / f"{tag}.json")
            labels.append(tag)
    if not inputs:
        # 默认用 latest cases_results.json
        inputs = list(DEFAULT_INPUTS)
        labels = [p.stem for p in inputs]

    if not labels:
        labels = [p.stem for p in inputs]
    if len(labels) != len(inputs):
        print("ERROR: --labels 数量必须等于 --inputs", file=sys.stderr)
        return 2

    datasets: list[tuple[str, dict[str, float]]] = []
    for path, label in zip(inputs, labels):
        if not path.exists():
            print(f"  skip {path} (not found)")
            continue
        data = load_results(path)
        by_cat = aggregate_by_category(data)
        datasets.append((label, by_cat))
        print(f"  loaded {label} from {path.name}: {by_cat}")

    plot_radar(datasets, args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
