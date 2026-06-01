#!/usr/bin/env python3
"""
minimax-m3-benchmark · real_world_compare.py

真实场景 Win Rate：用户定义自己的 5 个工作场景，
跑两个模型比一比，输出 win/tie/loss 决策建议。

用法：

    # 1) 准备场景文件
    cat > my_scenarios.json << 'EOF'
    {
      "scenarios": [
        {"name": "改 bug",   "prompt": "..."},
        {"name": "写文档",   "prompt": "..."},
        {"name": "翻译",     "prompt": "..."},
        {"name": "SQL 调优", "prompt": "..."},
        {"name": "代码审查", "prompt": "..."}
      ]
    }
    EOF

    # 2) 跑对比
    LLM_API_BASE=... LLM_API_KEY=... python3 scripts/real_world_compare.py \\
      --a-model gpt-4o-mini --b-model claude-sonnet-4-5 \\
      --scenarios my_scenarios.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "reports" / "real_world"
OUT_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_SCENARIOS = {
    "scenarios": [
        {"name": "改一段 Python bug",
         "prompt": "下面这段 Python 代码报错 IndexError: list index out of range，请定位并修复：\n```python\ndef get_item(items, idx):\n    return items[idx + 1]\n\nprint(get_item([1, 2, 3], 2))\n```"},
        {"name": "写一段用户文档",
         "prompt": "为以下 Python 函数写一段 ≤ 100 字的 docstring + 用法示例：\n```python\ndef retry(times=3, delay=1.0, exceptions=(Exception,)):\n    '''带重试的装饰器'''\n    ...\n```"},
        {"name": "英中翻译",
         "prompt": "把下面这段翻译成中文（保持技术准确性）：\n'Multi-head attention allows the model to jointly attend to information from different representation subspaces at different positions.'"},
        {"name": "SQL 优化",
         "prompt": "优化下面这条慢 SQL：\n```sql\nSELECT * FROM orders o\nJOIN users u ON o.user_id = u.id\nWHERE u.country = 'US' AND o.created_at > '2026-01-01'\nORDER BY o.created_at DESC;\n```\n表结构：orders(10M 行, idx on user_id), users(1M 行, idx on country, id)"},
        {"name": "代码审查",
         "prompt": "审查下面代码，列出 3 个潜在问题 + 修复建议：\n```python\ndef read_config(path):\n    return eval(open(path).read())\n```"},
    ]
}


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


def judge_pair(base, key, judge_model, prompt, ans_a, ans_b, timeout=60.0) -> str:
    """裁判模型对比，输出 A/B/TIE/ERROR。"""
    user = f"""你是严格的 head-to-head 评测裁判。

【任务】{prompt}

【答案 A】{ans_a[:1500]}

【答案 B】{ans_b[:1500]}

哪个更好？只输出一行：A / B / TIE"""
    try:
        resp = call_chat(base, key, judge_model, user, timeout)
        ans = resp.strip()
        if ans.startswith("A") and "A" in ans[:10]:
            return "A"
        if ans.startswith("B") and "B" in ans[:10]:
            return "B"
        if "TIE" in ans.upper()[:30] or "平" in ans[:30]:
            return "TIE"
        return "TIE"
    except Exception:
        return "ERROR"


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    p.add_argument("--scenarios", type=Path, default=None)
    p.add_argument("--a-model", required=True)
    p.add_argument("--b-model", required=True)
    p.add_argument("--judge-model", default="gpt-4o")
    p.add_argument("--base", default=os.environ.get("LLM_API_BASE", ""))
    p.add_argument("--key", default=os.environ.get("LLM_API_KEY", ""))
    p.add_argument("--timeout", type=float, default=60.0)
    p.add_argument("--out", type=Path, default=OUT_DIR / "real_world_report.md")
    args = p.parse_args()

    if not (args.base and args.key):
        print("ERROR: 需 --base/--key", file=sys.stderr)
        return 2

    if args.scenarios:
        data = json.loads(args.scenarios.read_text(encoding="utf-8"))
    else:
        data = DEFAULT_SCENARIOS
        print("INFO: 用内置默认 5 场景")

    scenarios = data["scenarios"]
    print(f"对比 {args.a_model} vs {args.b_model} 在 {len(scenarios)} 个场景下")

    rows = []
    for s in scenarios:
        print(f"  跑 {s['name']}...")
        try:
            ans_a = call_chat(args.base, args.key, args.a_model, s["prompt"], args.timeout)
        except Exception as e:
            ans_a = f"ERROR: {e}"
        try:
            ans_b = call_chat(args.base, args.key, args.b_model, s["prompt"], args.timeout)
        except Exception as e:
            ans_b = f"ERROR: {e}"
        winner = judge_pair(args.base, args.key, args.judge_model, s["prompt"], ans_a, ans_b, args.timeout)
        rows.append({
            "scenario": s["name"],
            "prompt_preview": s["prompt"][:80],
            "ans_a_len": len(ans_a), "ans_b_len": len(ans_b),
            "winner": winner,
            "ans_a_excerpt": ans_a[:200], "ans_b_excerpt": ans_b[:200],
        })
        print(f"    → {winner}")

    a_wins = sum(1 for r in rows if r["winner"] == "A")
    b_wins = sum(1 for r in rows if r["winner"] == "B")
    ties = sum(1 for r in rows if r["winner"] == "TIE")
    errs = sum(1 for r in rows if r["winner"] == "ERROR")

    lines = [
        f"# 真实场景 Win Rate：{args.a_model} vs {args.b_model}\n",
        f"- 时间：{datetime.now().isoformat(timespec='seconds')}",
        f"- 场景数：{len(scenarios)}",
        f"- 裁判：`{args.judge_model}`\n",
        "## 总分\n",
        f"- **{args.a_model} 胜：{a_wins}**",
        f"- **{args.b_model} 胜：{b_wins}**",
        f"- **平局：{ties}**",
        f"- 失败：{errs}\n",
        "## 逐场景\n",
        "| 场景 | 胜者 | A 字符 | B 字符 |",
        "|------|------|--------|--------|",
    ]
    for r in rows:
        winner_disp = {"A": f"✅ {args.a_model}", "B": f"✅ {args.b_model}",
                       "TIE": "🟰 平", "ERROR": "❌"}.get(r["winner"], r["winner"])
        lines.append(
            f"| {r['scenario']} | {winner_disp} "
            f"| {r['ans_a_len']} | {r['ans_b_len']} |"
        )

    # 建议
    lines.append("\n## 决策建议\n")
    if a_wins > b_wins:
        lines.append(f"- 在你的 {len(scenarios)} 个场景中，**{args.a_model} 表现更好**({a_wins} vs {b_wins})。")
    elif b_wins > a_wins:
        lines.append(f"- 在你的 {len(scenarios)} 个场景中，**{args.b_model} 表现更好**({b_wins} vs {a_wins})。")
    else:
        lines.append(f"- 两模型在你的场景中表现相当（平局 {ties}）。建议加更多场景细化差异。")

    # 答案对比示例
    lines.append("\n## 答案示例（每场景前 200 字）\n")
    for r in rows:
        lines.append(f"### {r['scenario']}")
        lines.append(f"- **{args.a_model}**：{r['ans_a_excerpt']}…")
        lines.append(f"- **{args.b_model}**：{r['ans_b_excerpt']}…")
        lines.append("")

    args.out.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
