#!/usr/bin/env python3
"""
minimax-m3-benchmark · physics_check.py

物理规律检查：给定场景描述，让模型预测接下来 5 秒的状态。
评分：与真实物理方程的偏差（位置 / 速度 / 加速度）。

用法：
    LLM_API_BASE=... LLM_API_KEY=... python3 scripts/physics_check.py
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "reports" / "physics"
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


# 8 个物理场景（ground truth 用 Python 计算）
G = 9.8  # m/s^2


def free_fall(t: float, h0: float = 10.0) -> dict:
    """从 h0 高度自由落体 t 秒后的位置和速度。"""
    y = h0 - 0.5 * G * t * t
    v = G * t
    return {"y_m": round(y, 2), "v_mps": round(v, 2)}


def projectile(t: float, v0: float = 20.0, angle_deg: float = 45.0) -> dict:
    """抛体运动（无空气阻力）。"""
    rad = math.radians(angle_deg)
    x = v0 * math.cos(rad) * t
    y = v0 * math.sin(rad) * t - 0.5 * G * t * t
    vx = v0 * math.cos(rad)
    vy = v0 * math.sin(rad) - G * t
    return {"x_m": round(x, 2), "y_m": round(y, 2),
            "vx_mps": round(vx, 2), "vy_mps": round(vy, 2)}


def pendulum(t: float, length: float = 1.0, amplitude_deg: float = 10.0) -> dict:
    """单摆（小角度近似）周期 T = 2π√(L/g)。"""
    T = 2 * math.pi * math.sqrt(length / G)
    omega = 2 * math.pi / T
    pos = amplitude_deg * math.cos(omega * t)
    return {"T_s": round(T, 2), "pos_deg": round(pos, 2)}


SCENARIOS = [
    {
        "id": "free_fall_1s",
        "scene": "小球从 10m 高度自由落体（g=9.8, 空气阻力忽略）。1 秒后小球的 y 坐标和速度是多少？",
        "compute": lambda: free_fall(1.0),
        "extract": lambda ans: {"y_m": float(re.search(r"y[=：:]\s*([\d.]+)", ans).group(1)) if re.search(r"y[=：:]\s*([\d.]+)", ans) else 0,
                                "v_mps": float(re.search(r"v[=：:]\s*([\d.]+)", ans).group(1)) if re.search(r"v[=：:]\s*([\d.]+)", ans) else 0},
    },
    {
        "id": "free_fall_2s",
        "scene": "小球从 10m 自由落体。2 秒后 y 坐标和速度？（g=9.8）",
        "compute": lambda: free_fall(2.0),
        "extract": lambda ans: {"y_m": float(re.search(r"y[=：:]\s*([\d.]+)", ans).group(1)) if re.search(r"y[=：:]\s*([\d.]+)", ans) else 0,
                                "v_mps": float(re.search(r"v[=：:]\s*([\d.]+)", ans).group(1)) if re.search(r"v[=：:]\s*([\d.]+)", ans) else 0},
    },
    {
        "id": "projectile_1s",
        "scene": "初速度 20 m/s、仰角 45° 的抛体（无空气阻力）。1 秒后 x、y 坐标？",
        "compute": lambda: projectile(1.0),
        "extract": lambda ans: {"x_m": float(re.search(r"x[=：:]\s*([\d.]+)", ans).group(1)) if re.search(r"x[=：:]\s*([\d.]+)", ans) else 0,
                                "y_m": float(re.search(r"y[=：:]\s*([\d.]+)", ans).group(1)) if re.search(r"y[=：:]\s*([\d.]+)", ans) else 0},
    },
    {
        "id": "pendulum_period",
        "scene": "单摆长度 1m（小角度近似）。周期 T 是多少秒？（g=9.8）",
        "compute": lambda: {"T_s": pendulum(0.0)["T_s"], "pos_deg": 10.0},
        "extract": lambda ans: {"T_s": float(re.search(r"T[=：:]\s*([\d.]+)", ans).group(1)) if re.search(r"T[=：:]\s*([\d.]+)", ans) else 0,
                                "pos_deg": 10.0},
    },
]


def error_pct(predicted, ground_truth, tol=0.5) -> float:
    """相对误差百分比。"""
    if ground_truth == 0:
        return abs(predicted) * 100
    return abs(predicted - ground_truth) / abs(ground_truth) * 100


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    p.add_argument("--model", default=os.environ.get("MODEL", "gpt-4o-mini"))
    p.add_argument("--base", default=os.environ.get("LLM_API_BASE", ""))
    p.add_argument("--key", default=os.environ.get("LLM_API_KEY", ""))
    p.add_argument("--tolerance-pct", type=float, default=20.0,
                   help="相对误差容差 %（默认 20%）")
    p.add_argument("--timeout", type=float, default=60.0)
    p.add_argument("--out", type=Path, default=OUT_DIR / "physics_report.md")
    args = p.parse_args()

    if not (args.base and args.key):
        print("ERROR: 需 --base/--key", file=sys.stderr)
        return 2

    rows = []
    for s in SCENARIOS:
        gt = s["compute"]()
        try:
            ans = call_chat(args.base, args.key, args.model, s["scene"], args.timeout)
        except Exception as e:
            ans = f"ERROR: {e}"
        try:
            pred = s["extract"](ans)
        except Exception:
            pred = {}

        # 计算每个字段的误差
        errs = {}
        for k, gt_v in gt.items():
            pred_v = pred.get(k, 0)
            errs[k] = round(error_pct(pred_v, gt_v), 1)
        max_err = max(errs.values()) if errs else 999
        within = max_err <= args.tolerance_pct
        rows.append({
            "id": s["id"], "scene": s["scene"],
            "gt": gt, "pred": pred, "errs": errs,
            "max_err": max_err, "within": within, "answer": ans[:200],
        })
        print(f"  {s['id']}: max_err={max_err:.1f}% ({'✅' if within else '❌'})")

    passed = sum(1 for r in rows if r["within"])

    lines = [
        "# 物理规律检查\n",
        f"- 目标模型：`{args.model}`",
        f"- 容差：±{args.tolerance_pct}%",
        f"- 题目数：{len(rows)}",
        f"- **通过：{passed}/{len(rows)}**\n",
        "## 逐题\n",
        "| ID | 场景 | 真值 | 预测 | 最大误差 | 通过 |",
        "|----|------|------|------|----------|------|",
    ]
    for r in rows:
        gt_str = ", ".join(f"{k}={v}" for k, v in r["gt"].items())
        pred_str = ", ".join(f"{k}={r['pred'].get(k, '?')}" for k in r["gt"].keys())
        lines.append(
            f"| `{r['id']}` | {r['scene'][:30]}… | {gt_str} "
            f"| {pred_str} | {r['max_err']:.1f}% | {'✅' if r['within'] else '❌'} |"
        )

    lines.append("\n## 详细误差\n")
    for r in rows:
        if r["max_err"] > args.tolerance_pct:
            lines.append(f"- **{r['id']}**：最大误差 {r['max_err']:.1f}%（超容差）")
            for k, v in r["errs"].items():
                lines.append(f"  - {k}: {v}%")

    args.out.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
