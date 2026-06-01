#!/usr/bin/env python3
"""
minimax-m3-benchmark · needle_haystack_extreme.py

1M 长上下文真实任务：在 1M token 文档中找页码/复现代码/总结章节，
画"长上下文利用率"曲线（X = 上下文位置 %，Y = 召回率）。

设计：合成一个 ~ 1M 字符的"伪长文档"，在 5 个不同位置插入
不同的"针"，让模型检索并复现。位置 0% = 文档开头，100% = 末尾。

用法：
    LLM_API_BASE=... LLM_API_KEY=... python3 scripts/needle_haystack_extreme.py
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "reports" / "needle_extreme"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def call_chat(base, key, model, prompt, timeout=120.0, temperature=0.0,
              max_tokens=512):
    body = json.dumps({
        "model": model, "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature, "max_tokens": max_tokens,
    }).encode("utf-8")
    req = urllib.request.Request(f"{base.rstrip('/')}/v1/chat/completions", data=body, headers={
        "Content-Type": "application/json", "Authorization": f"Bearer {key}",
    })
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))["choices"][0]["message"]["content"]


# 5 个"针"：放不同位置的不同事实
NEEDLES = [
    {"position_pct": 5,  "key": "PI-Vault-7281",       "type": "key"},
    {"position_pct": 25, "key": "Reginald Blackwood",  "type": "name"},
    {"position_pct": 50, "key": "Mt. K2 expedition",   "type": "event"},
    {"position_pct": 75, "key": "E = mc^2 + delta",    "type": "formula"},
    {"position_pct": 95, "key": "Sparrow-2026",        "type": "code"},
]


def build_long_doc(target_chars: int = 1_000_000) -> tuple[str, list[dict]]:
    """构造 ~ 1M 字符的合成文档，并在指定位置插入针。"""
    # 准备"自然文本"片段（lipsum 风格）
    chunk = ("这是 2026 年第二季度的内部备忘录。研发重心从通用大模型转向行业垂直模型。"
             "3 月份发布 FinBot 测试版，4 月启动 MedAssist 预研。" * 30)
    chunks_needed = (target_chars // len(chunk)) + 2
    body = (chunk * chunks_needed)[:target_chars]

    # 在 5 个位置插入针（用 sentinel 标记）
    insertion_log: list[dict] = []
    parts: list[str] = []
    last_idx = 0
    sorted_needles = sorted(NEEDLES, key=lambda n: n["position_pct"])
    for needle in sorted_needles:
        # 找到对应的字符位置
        idx = int(len(body) * needle["position_pct"] / 100)
        # 找到最近的句号边界
        while idx < len(body) and body[idx] not in "。.?!":
            idx += 1
        # 插入针
        marker = f"\n\n【{needle['type'].upper()}-{needle['key']}】\n\n"
        parts.append(body[last_idx:idx])
        parts.append(marker)
        insertion_log.append({"position": idx, "key": needle["key"], "type": needle["type"]})
        last_idx = idx
    parts.append(body[last_idx:])
    full_doc = "".join(parts)
    return full_doc, insertion_log


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    p.add_argument("--model", default=os.environ.get("MODEL", "minimax-m3"))
    p.add_argument("--base", default=os.environ.get("LLM_API_BASE", ""))
    p.add_argument("--key", default=os.environ.get("LLM_API_KEY", ""))
    p.add_argument("--target-chars", type=int, default=1_000_000)
    p.add_argument("--timeout", type=float, default=120.0)
    p.add_argument("--out", type=Path, default=OUT_DIR / "long_context_report.md")
    args = p.parse_args()

    if not (args.base and args.key):
        print("ERROR: 需 --base/--key", file=sys.stderr)
        return 2

    print(f"构造 ~{args.target_chars:,} 字符文档...")
    doc, insertions = build_long_doc(args.target_chars)
    print(f"  → 实际 {len(doc):,} 字符，5 个针已插入")

    # 对每个针，单独发问
    print(f"\n开始 5 轮长上下文检索 (model={args.model})...")
    rows = []
    for ins in insertions:
        # 让模型在长上下文中找具体事实
        if ins["type"] == "key":
            question = "请在文档中找到一个形如 'KEY-XXXX-数字' 的密钥，原样输出。"
        elif ins["type"] == "name":
            question = "请在文档中找到一个英文人名（首次出现处），原样输出。"
        elif ins["type"] == "event":
            question = "请在文档中找到一个与登山探险相关的事件名，原样输出。"
        elif ins["type"] == "formula":
            question = "请在文档中找到一个与能量/质量相关的公式（首次出现处），原样输出。"
        elif ins["type"] == "code":
            question = "请在文档中找到一个与代码常量相关的字符串（首次出现处），原样输出。"
        prompt = f"以下是 ~1M 字符的内部文档：\n\n{doc}\n\n【问题】{question}"
        try:
            ans = call_chat(args.base, args.key, args.model, prompt, args.timeout)
            hit = ins["key"] in ans
        except Exception as e:
            ans = f"ERROR: {e}"
            hit = False
        rows.append({"needle": ins, "hit": hit, "ans_preview": ans[:200]})
        print(f"  位置 {ins['position']:>7,}: 针='{ins['key']}' → {'✅ 找到' if hit else '❌ 漏'}")

    found = sum(1 for r in rows if r["hit"])
    total = len(rows)
    rate = found / total * 100

    lines = [
        "# 1M 长上下文真实任务\n",
        f"- 目标文档大小：{args.target_chars:,} 字符",
        f"- 实际文档：{len(doc):,} 字符",
        f"- 针数：{len(rows)}（分布 5% / 25% / 50% / 75% / 95%）",
        f"- 目标模型：`{args.model}`",
        f"- **召回率：{found}/{total} = {rate:.0f}%**\n",
        "## 利用率曲线（位置 vs 是否找到）\n",
        "| 位置 (%) | 针内容 | 类型 | 召回 |",
        "|---------|--------|------|------|",
    ]
    for r in rows:
        pct = r["needle"]["position"] / args.target_chars * 100
        lines.append(
            f"| {pct:.0f}% | `{r['needle']['key']}` | {r['needle']['type']} "
            f"| {'✅' if r['hit'] else '❌'} |"
        )

    lines.append("\n## 利用率图（ASCII）\n")
    for r in rows:
        pct = r["needle"]["position"] / args.target_chars * 100
        bar = "█" * int(pct / 5) + "▒" * (20 - int(pct / 5))
        mark = "✅" if r["hit"] else "❌"
        lines.append(f"  0% [{bar}] 100%  @{pct:.0f}% {mark}")

    lines.append("\n## 解读")
    if rate >= 80:
        lines.append("- 长上下文利用率优秀。")
    elif rate >= 60:
        lines.append("- 长上下文利用率中等，建议在生产中分块或检索增强。")
    else:
        lines.append("- 长上下文利用率不足，建议用 RAG / chunking 替代直接塞入。")

    lines.append("\n> 本测试用合成文档。如果你的真实工作流是 PDF/代码库，请用真实数据复测。")

    args.out.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nwrote {args.out}")
    print(f"召回率：{rate:.0f}%")
    return 0


if __name__ == "__main__":
    sys.exit(main())
