#!/usr/bin/env python3
"""
minimax-benchmark · difficulty.py

难度自适应：基于当前模型表现动态调整下一批用例难度，
输出"能力位次"评估（类似 GRE 自适应测试）。

参考基准（粗略）：
- gpt-3.5  ≈ 50%
- gpt-4o-mini ≈ 70%
- gpt-4o    ≈ 85%
- claude-opus-4-8 ≈ 90%
- 顶级推理模型 (o1) ≈ 95%

用法：

    # 查看能力位次
    python3 scripts/difficulty.py --input reports/cases/cases_results.json

    # 推荐下一批"应该会失败"的难度题
    python3 scripts/difficulty.py --recommend-hard
"""
from __future__ import annotations
import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RESULTS = ROOT / "reports" / "cases" / "cases_results.json"
DEFAULT_CFG = ROOT / "config" / "test_cases.json"
OUT_DIR = ROOT / "reports" / "difficulty"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# 难度等级（基础版；用户可扩展）
DIFFICULTY_TIERS = {
    "L0-基础": 50,    # 答对率 ≥ 50% 视为掌握
    "L1-入门": 65,
    "L2-中级": 75,
    "L3-高级": 85,
    "L4-专家": 92,
    "L5-竞赛": 97,
}

# 用例难度预标注（可扩展为 test_cases.json 中加 "difficulty" 字段）
DEFAULT_DIFFICULTY = {
    "smoke_identity": 0, "smoke_bilingual": 1,
    "structured_extraction": 1, "long_summary": 1,
    "logic_reasoning": 3, "math_integral": 3, "code_generation": 3,
    "multi_turn_context": 2, "prompt_injection": 2, "tool_use_planning": 2,
    "code_review": 2, "emoji_robustness": 1,
    "bayesian_probability": 3, "unauthorized_tool": 2, "indirect_injection": 3,
    "needle_haystack": 1, "style_transfer": 3,
    "find_secrets": 2, "debug_incident": 2, "user_complaint": 2,
    "classical_chinese": 2, "japanese_reading": 2, "calibration": 2,
}


def tier_for(pct: float) -> tuple[str, float]:
    """返回 (tier_name, tier_threshold)。"""
    current = ("L0-基础", 50)
    for name, th in DIFFICULTY_TIERS.items():
        if pct >= th:
            current = (name, th)
    return current


def model_tier(pct: float) -> str:
    """粗略对标公开模型。"""
    if pct < 40:
        return "L0（约 < gpt-3.5）"
    if pct < 55:
        return "L1（约 gpt-3.5）"
    if pct < 70:
        return "L2（约 gpt-4o-mini）"
    if pct < 80:
        return "L3（约 gpt-4o）"
    if pct < 88:
        return "L4（约 claude-opus-4-8）"
    if pct < 95:
        return "L5（顶级推理）"
    return "L5+（超越基准）"


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    p.add_argument("--input", type=Path, default=DEFAULT_RESULTS)
    p.add_argument("--config", type=Path, default=DEFAULT_CFG)
    p.add_argument("--recommend-hard", action="store_true",
                   help="推荐下一批'应该会失败'的难度题")
    p.add_argument("--out", type=Path,
                   default=OUT_DIR / "difficulty_report.md")
    args = p.parse_args()

    if not args.input.exists():
        print(f"ERROR: {args.input} not found. Run grade.py first.",
              file=sys.stderr)
        return 2

    data = json.loads(args.input.read_text(encoding="utf-8"))
    cfg = json.loads(args.config.read_text(encoding="utf-8"))
    cfg_by_id = {c["id"]: c for c in cfg.get("cases", [])}

    overall = data.get("overall_pct", 0)
    tier_name, tier_th = tier_for(overall)
    model_band = model_tier(overall)

    lines = [
        "# 难度自适应报告\n",
        f"- 时间：{datetime.now().isoformat(timespec='seconds')}",
        f"- 总平均分：**{overall}%**",
        f"- 达到难度档：**{tier_name}**（阈值 ≥ {tier_th}%）",
        f"- **能力位次评估：{model_band}**\n",
        "## 难度档位（threshold）",
    ]
    for name, th in DIFFICULTY_TIERS.items():
        mark = " ✅" if overall >= th else ""
        lines.append(f"- {name}：{th}%{mark}")

    # 逐题难度
    lines.append("\n## 逐题难度（按答对率）\n")
    lines.append("| ID | 类别 | 预标难度 | 通过率 | 差距 |")
    lines.append("|----|------|----------|--------|------|")
    for r in sorted(data.get("results", []),
                    key=lambda x: x.get("pct", 0)):
        cid = r["id"]
        d = DEFAULT_DIFFICULTY.get(cid, 2)
        pct = r.get("pct", 0)
        th = list(DIFFICULTY_TIERS.values())[d]
        diff = round(pct - th, 1)
        if diff >= 0:
            mark = f"+{diff}%"
        else:
            mark = f"{diff}%"
        lines.append(
            f"| `{cid}` | {r.get('category','')} | L{d} | {pct}% | {mark} |"
        )

    # 推荐下一批难题
    if args.recommend_hard:
        lines.append("\n## 推荐下一批'应失败'的难题（用于挖掘能力上限）\n")
        lines.append("策略：当前整体 100% 时，建议加入预标难度 ≥ L4 的题目。\n")
        lines.append("### 题目模板建议（需要人工补充完整 prompt）\n")
        harder_templates = [
            ("L4-多步因果", "5 个变量相互依赖，给定 3 个观察，推断另外 2 个。"),
            ("L4-形式化证明", "用归纳法证明：所有大于 2 的偶数都可表示为两个素数之和。"),
            ("L5-奥数几何", "在三角形 ABC 中，∠A=60°，AB=4，AC=6，求 BC 长度。"),
            ("L5-系统设计", "设计一个支持 100 万 QPS 的短链服务，给出存储 / 缓存 / 限流方案。"),
            ("L5-代码逆向", "给一段混淆后的 JS 代码，还原原始逻辑。"),
        ]
        for name, desc in harder_templates:
            lines.append(f"- **{name}**：{desc}")

    # 推荐"加难度"题（已答对但接近边缘）
    lines.append("\n## 推荐'巩固'题（答对但安全裕度 < 20%）\n")
    borderline = []
    for r in data.get("results", []):
        if r.get("pct", 0) >= 80 and r.get("pct", 0) < 100:
            borderline.append(r)
    if borderline:
        for r in borderline:
            lines.append(f"- `{r['id']}` — {r['name']}（{r['pct']}%）")
    else:
        lines.append("- 无 — 所有答对题均为 100%")

    args.out.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {args.out}")
    print(f"能力位次评估：**{model_band}**（总平均 {overall}%）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
