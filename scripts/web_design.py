#!/usr/bin/env python3
"""
minimax-m3-benchmark · web_design.py

网页设计：给定需求 → HTML+CSS 单文件，LLM-as-judge 评分
（布局 / 可用性 / 视觉 / 响应式）。

用法：
    LLM_API_BASE=... LLM_API_KEY=... python3 scripts/web_design.py
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
OUT_DIR = ROOT / "reports" / "web_design"
OUT_DIR.mkdir(parents=True, exist_ok=True)

TASKS = [
    {
        "id": "login_page",
        "title": "Todo App 登录页",
        "requirement": "做一个简洁的 Todo App 登录页：含 logo、邮箱/密码输入框、登录按钮、忘记密码链接。要求：现代简约风格、响应式（移动端可用）、无障碍 label。",
        "must_have": ["<!DOCTYPE", "<form", "input", "type=\"submit\"", "<style", "media query"],
    },
    {
        "id": "dashboard",
        "title": "数据仪表盘",
        "requirement": "做一个数据仪表盘：左侧 sidebar 导航，顶部 header 含搜索框，主区域放 4 个 KPI 卡片 + 1 个折线图占位（用 SVG 简单画）。要求：Tailwind 风格类名、响应式。",
        "must_have": ["<nav", "<svg", "card", "grid", "sidebar", "kpi"],
    },
    {
        "id": "pricing",
        "title": "定价页",
        "requirement": "做一个 3 栏定价页：免费 / 专业 / 企业，标注推荐项。要求：清晰对比表格、CTA 按钮、hover 效果。",
        "must_have": ["pricing", "<table", "推荐", "btn", "hover", "free", "pro", "enterprise"],
    },
]


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


JUDGE_PROMPT = """你是 web 设计评审。给下面这个 HTML+CSS 单文件打分（每项 1-5）：

【任务需求】{req}

【代码】{code}

评分维度：
- layout（布局合理、信息层次清晰）
- usability（按钮 / 表单 / 导航是否符合用户预期）
- visual（配色 / 间距 / 字体）
- responsive（是否支持移动端）

**严格 JSON**：
{{"layout": <1-5>, "usability": <1-5>, "visual": <1-5>, "responsive": <1-5>, "rationale": "≤60字"}}
"""


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    p.add_argument("--target-model", default=os.environ.get("MODEL", "gpt-4o-mini"))
    p.add_argument("--judge-model", default=os.environ.get("JUDGE_MODEL", "gpt-4o"))
    p.add_argument("--base", default=os.environ.get("LLM_API_BASE", ""))
    p.add_argument("--key", default=os.environ.get("LLM_API_KEY", ""))
    p.add_argument("--timeout", type=float, default=60.0)
    p.add_argument("--out", type=Path, default=OUT_DIR / "web_design_report.md")
    args = p.parse_args()

    if not (args.base and args.key):
        print("ERROR: 需 --base/--key", file=sys.stderr)
        return 2

    rows = []
    for task in TASKS:
        print(f"生成 {task['title']}...")
        prompt = f"""请按以下需求生成一个完整的 HTML+CSS 单文件页面（所有 CSS 在 <style> 标签内）：

【需求】{task['requirement']}

要求：
1. 必须是单文件（HTML+CSS 都在同一文件）
2. 现代简洁风格
3. 响应式（移动端可用）
4. 输出**仅** HTML 代码，不要任何额外解释
"""
        try:
            code = call_chat(args.base, args.key, args.target_model, prompt, args.timeout)
        except Exception as e:
            code = f"ERROR: {e}"
        # 提取 <html>...</html> 或 <!DOCTYPE>...
        m = re.search(r"(<!DOCTYPE.*?</html>)", code, re.DOTALL | re.IGNORECASE)
        if m:
            code = m.group(1)
        # 关键词命中
        hits = [k for k in task["must_have"] if k in code]
        kw_rate = len(hits) / len(task["must_have"])
        # LLM-as-judge
        try:
            judge_user = JUDGE_PROMPT.format(req=task["requirement"], code=code[:3000])
            judge_resp = call_chat(args.base, args.key, args.judge_model, judge_user, args.timeout)
            m2 = re.search(r"\{.*\}", judge_resp, re.DOTALL)
            scores = json.loads(m2.group(0)) if m2 else {"layout": 3, "usability": 3, "visual": 3, "responsive": 3}
        except Exception as e:
            scores = {"layout": 0, "usability": 0, "visual": 0, "responsive": 0, "rationale": f"judge error: {e}"}
        rows.append({
            "task": task, "code_len": len(code),
            "kw_hits": hits, "kw_rate": kw_rate, "scores": scores,
        })
        avg = statistics.mean([scores.get(k, 0) for k in ("layout", "usability", "visual", "responsive")])
        print(f"  → kw {kw_rate*100:.0f}%, judge avg {avg:.1f}/5")

    if not rows:
        return 0
    avg_kw = statistics.mean(r["kw_rate"] for r in rows)
    avg_layout = statistics.mean(r["scores"].get("layout", 0) for r in rows)
    avg_usab = statistics.mean(r["scores"].get("usability", 0) for r in rows)
    avg_visual = statistics.mean(r["scores"].get("visual", 0) for r in rows)
    avg_resp = statistics.mean(r["scores"].get("responsive", 0) for r in rows)

    lines = [
        "# 网页设计测试\n",
        f"- 目标模型：`{args.target_model}`",
        f"- 裁判：`{args.judge_model}`\n",
        "## 总分\n",
        f"- 平均关键词覆盖：**{avg_kw*100:.0f}%**",
        f"- layout：{avg_layout:.1f}/5",
        f"- usability：{avg_usab:.1f}/5",
        f"- visual：{avg_visual:.1f}/5",
        f"- responsive：{avg_resp:.1f}/5\n",
        "## 逐题\n",
        "| 任务 | 关键词覆盖 | layout | usability | visual | responsive |",
        "|------|-----------|--------|-----------|--------|------------|",
    ]
    for r in rows:
        s = r["scores"]
        lines.append(
            f"| {r['task']['id']} | {r['kw_rate']*100:.0f}% "
            f"| {s.get('layout','-')} | {s.get('usability','-')} "
            f"| {s.get('visual','-')} | {s.get('responsive','-')} |"
        )

    lines.append("\n## 评语\n")
    for r in rows:
        lines.append(f"### {r['task']['title']}")
        lines.append(f"- 关键词命中：{', '.join(r['kw_hits'])}")
        lines.append(f"- 评语：{r['scores'].get('rationale', '—')}")
        lines.append("")

    args.out.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
