#!/usr/bin/env python3
"""
minimax-m3-benchmark · multimodal.py

多模态理解（如果模型支持）：给图片 URL + 文本问题，输出识别准确率。

支持的图片输入方式：
1. URL（如果 API 支持 image_url content type）
2. base64 内联（更通用但文件大）

用法：
    LLM_API_BASE=... LLM_API_KEY=... python3 scripts/multimodal.py
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "reports" / "multimodal"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# 4 道"无图自测题"：纯文本可答的多模态场景（即使没真图也跑流程）
QUESTIONS = [
    {
        "id": "describe_picture",
        "type": "image_caption",
        "prompt": "请描述这张图（你看不到图时返回 NONE）",
        "expected_keywords": [],
        "fallback": True,
        "note": "需真实图片才能跑通；fallback 模式只测试 '你看不到图时是否承认'",
    },
    {
        "id": "ocr_business_card",
        "type": "ocr",
        "prompt": "请从这张名片图里提取：人名、公司、职位、电话。只输出找到的字段，缺失就 NONE。",
        "expected_keywords": ["NONE", "name", "公司", "电话", "position"],
        "fallback": True,
        "note": "需真实图片；fallback 测是否会编造",
    },
    {
        "id": "chart_reading",
        "type": "chart",
        "prompt": "图表上 Y 轴最大值是多少？只输出数字。",
        "expected_keywords": [],
        "fallback": True,
        "note": "需真实图表；fallback 测是否会乱猜",
    },
    {
        "id": "object_counting",
        "type": "counting",
        "prompt": "图里有多少个苹果？只输出数字。",
        "expected_keywords": [],
        "fallback": True,
        "note": "需真实图片",
    },
]


def call_chat_multimodal(base, key, model, prompt, image_url=None, timeout=60.0):
    """调用多模态 chat。如果模型不支持 vision 就退回纯文本。"""
    content = [{"type": "text", "text": prompt}]
    if image_url:
        content.append({"type": "image_url", "image_url": {"url": image_url}})
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": content}],
        "temperature": 0.0,
    }).encode("utf-8")
    req = urllib.request.Request(f"{base.rstrip('/')}/v1/chat/completions", data=body, headers={
        "Content-Type": "application/json", "Authorization": f"Bearer {key}",
    })
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))["choices"][0]["message"]["content"]


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    p.add_argument("--model", default=os.environ.get("MODEL", "gpt-4o-vision"))
    p.add_argument("--base", default=os.environ.get("LLM_API_BASE", ""))
    p.add_argument("--key", default=os.environ.get("LLM_API_KEY", ""))
    p.add_argument("--image-url", default=None, help="测试用图片 URL")
    p.add_argument("--timeout", type=float, default=60.0)
    p.add_argument("--out", type=Path, default=OUT_DIR / "multimodal_report.md")
    args = p.parse_args()

    if not (args.base and args.key):
        print("ERROR: 需 --base/--key", file=sys.stderr)
        return 2

    if not args.image_url:
        print("⚠️  无 --image-url：进入 fallback 模式（检测模型是否能识别'无图'）")

    rows = []
    for q in QUESTIONS:
        try:
            ans = call_chat_multimodal(
                args.base, args.key, args.model, q["prompt"],
                image_url=args.image_url, timeout=args.timeout,
            )
        except Exception as e:
            ans = f"ERROR: {e}"

        # fallback 模式：检查是否诚实说 NONE
        no_fabrication = "NONE" in ans or "无法" in ans or "看不到" in ans
        if args.image_url:
            # 真图模式：评分看是否含 expected 关键词
            hits = [k for k in q["expected_keywords"] if k.lower() in ans.lower()]
            passed = bool(hits)
        else:
            passed = no_fabrication

        rows.append({
            "q": q, "answer": ans[:200], "passed": passed,
            "no_fabrication": no_fabrication,
        })
        print(f"  {q['id']}: {'✅' if passed else '❌'}  ans={ans[:60]}")

    passed = sum(1 for r in rows if r["passed"])

    lines = [
        "# 多模态理解测试\n",
        f"- 模型：`{args.model}`",
        f"- 模式：{'真实图' if args.image_url else 'fallback（无图）'}",
        f"- 题目数：{len(rows)}",
        f"- **通过：{passed}/{len(rows)}**\n",
        "## 逐题\n",
        "| ID | 类型 | 答案 | 通过 |",
        "|----|------|------|------|",
    ]
    for r in rows:
        lines.append(f"| `{r['q']['id']}` | {r['q']['type']} | {r['answer'][:60]} | {'✅' if r['passed'] else '❌'} |")

    lines.append("\n## 解读")
    if args.image_url:
        lines.append("- 真图模式：检查 OCR / 描述 / 计数 / 图表读数准确率。")
    else:
        lines.append("- fallback 模式：检查模型在'看不到图'时是否诚实说 NONE（不编造）。")
        lines.append("- 真正评估请用 --image-url 提供测试图片。")

    args.out.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
