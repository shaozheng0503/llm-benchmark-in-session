#!/usr/bin/env python3
"""
minimax-m3-benchmark · auto_generate.py

自动生成新测试用例：让强模型按能力维度生成新题 + 建议断言。

用法：
    LLM_API_BASE=... LLM_API_KEY=... python3 scripts/auto_generate.py \\
        --target-category complex --difficulty L4 --count 5
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "reports" / "auto_generated"
OUT_DIR.mkdir(parents=True, exist_ok=True)

PROMPT = """你是一名 LLM benchmark 设计专家。请生成 1 道全新的测试题 + 推荐断言。

【目标能力维度】{category}
【目标难度】{difficulty}（L0-基础 50% / L1-入门 65% / L2-中级 75% / L3-高级 85% / L4-专家 92% / L5-竞赛 97%）
【考察重点】{focus}

要求：
1. 题目不能与已有题目重复
2. 输出**严格 JSON**（不要任何额外文字）：
{{
  "id": "<snake_case 唯一 ID>",
  "category": "{category}",
  "name": "<中文名称>",
  "prompt": "<完整 prompt，可含多行 / 代码块 / 中文>",
  "assertion": {{
    "min_length": <int>,
    "should_include_any": ["<关键词1>", "..."],
    "should_not_include_any": ["<词>"],
    "regex_match": "<可选>",
    "json_required": true/false,
    "json_keys": ["<可选>"]
  }},
  "rationale": "≤80 字设计意图"
}}
"""


def call_chat(base, key, model, prompt, timeout=60.0, temperature=0.8):
    body = json.dumps({
        "model": model, "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
    }).encode("utf-8")
    req = urllib.request.Request(f"{base.rstrip('/')}/v1/chat/completions", data=body, headers={
        "Content-Type": "application/json", "Authorization": f"Bearer {key}",
    })
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))["choices"][0]["message"]["content"]


CATEGORIES = {
    "smoke":       "基础身份/双语测试",
    "core":        "核心能力（JSON 抽取、长文总结）",
    "complex":     "复杂推理（数学、逻辑、代码）",
    "safety":      "安全（提示注入、越权、隐私）",
    "boundary":    "边界（工具调用、Unicode、格式）",
    "real_task":   "真实任务（debug、on-call、代码审查）",
    "multilingual": "多语言（日/英/古文）",
}

DIFFICULTY_FOCUS = {
    "L0": "基础常识：单步即可答对",
    "L1": "入门：1-2 步推理",
    "L2": "中级：需 3-5 步推理或简单工具",
    "L3": "高级：需长链推理或跨领域知识",
    "L4": "专家：奥数/系统设计/形式化证明级",
    "L5": "竞赛：超出公开模型平均水平",
}


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    p.add_argument("--generator-model", default=os.environ.get("GENERATOR_MODEL", "gpt-4o"))
    p.add_argument("--base", default=os.environ.get("LLM_API_BASE", ""))
    p.add_argument("--key", default=os.environ.get("LLM_API_KEY", ""))
    p.add_argument("--target-category", default="complex", choices=list(CATEGORIES.keys()))
    p.add_argument("--difficulty", default="L4", choices=list(DIFFICULTY_FOCUS.keys()))
    p.add_argument("--count", type=int, default=3)
    p.add_argument("--focus", default="", help="额外考察点")
    p.add_argument("--timeout", type=float, default=60.0)
    p.add_argument("--out", type=Path, default=OUT_DIR / "generated_cases.json")
    args = p.parse_args()

    if not (args.base and args.key):
        print("ERROR: 需 --base/--key", file=sys.stderr)
        return 2

    generated = []
    for i in range(args.count):
        user = PROMPT.format(
            category=args.target_category,
            difficulty=args.difficulty,
            focus=args.focus or DIFFICULTY_FOCUS[args.difficulty],
        )
        try:
            resp = call_chat(args.base, args.key, args.generator_model, user, args.timeout)
            m = re.search(r"\{.*\}", resp, re.DOTALL)
            data = json.loads(m.group(0))
            data["_generated_at"] = datetime.now().isoformat()
            data["_generator_model"] = args.generator_model
            generated.append(data)
            print(f"  [{i+1}/{args.count}] generated: {data.get('id')}")
        except Exception as e:
            print(f"  [{i+1}/{args.count}] ERROR: {e}")

    args.out.write_text(
        json.dumps(generated, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\nwrote {args.out} ({len(generated)} cases)")
    print("\n用法：把这些用例人工 review 后合并到 config/test_cases.json：")
    for g in generated:
        print(f"  - {g.get('id')}: {g.get('name')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
