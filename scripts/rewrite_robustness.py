#!/usr/bin/env python3
"""
minimax-m3-benchmark · rewrite_robustness.py

Prompt 改写鲁棒性测试：用 LLM 把每个用例改写 3 种措辞，
再让同一模型答 + 跑断言，看一致率。

一致率高 = 模型对该能力鲁棒（不靠特定措辞"背题"）
一致率低 = 模型对该能力敏感（不同问法得到不同答案）

用法：

    LLM_API_BASE=https://api.openai.com LLM_API_KEY=sk-xxx \\
    python3 scripts/rewrite_robustness.py --rewriter-model gpt-4o \\
        --target-model gpt-4o-mini --n-variants 3

    # 不调 LLM（用预生成变体）—— 通常用 HTTP 模式跑一次后缓存
    python3 scripts/rewrite_robustness.py --use-cached
"""
from __future__ import annotations
import argparse
import json
import os
import re
import statistics
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CFG = ROOT / "config" / "test_cases.json"
CACHE_DIR = ROOT / "reports" / "rewrite_cache"
OUT_DIR = ROOT / "reports" / "rewrite_robustness"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
OUT_DIR.mkdir(parents=True, exist_ok=True)

REWRITER_PROMPT = """你是一名 prompt 工程师。请把下面这道题改写成 {n} 种不同措辞的等价版本。
要求：
- 保留核心考察点不变
- 措辞、句式、风格显著不同
- 不引入新的干扰信息
- 不改变答案应该匹配的关键模式

题目：
{prompt}

输出**严格 JSON**（不要任何额外文字）：
{{"variants": ["...", "...", "..."]}}
"""


def call_chat(base: str, key: str, model: str,
              prompt: str, timeout: float = 60.0,
              temperature: float = 0.7) -> str:
    url = f"{base.rstrip('/')}/v1/chat/completions"
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
    }).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers={
        "Content-Type": "application/json", "Authorization": f"Bearer {key}",
    }, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))["choices"][0]["message"]["content"]


def extract_json(text: str) -> dict:
    m = re.search(r"\{.*\}", text, re.DOTALL)
    return json.loads(m.group(0)) if m else json.loads(text)


# 复用 grade.py 的断言执行
sys.path.insert(0, str(ROOT / "scripts"))
from grade import run_assertion  # type: ignore  # noqa: E402


def evaluate_assertion(assertion: dict, answer: str) -> tuple[int, int]:
    """返回 (passed, total)。"""
    checks = run_assertion(assertion, answer)
    return sum(1 for c in checks if c.passed), len(checks)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    p.add_argument("--config", type=Path, default=DEFAULT_CFG)
    p.add_argument("--n-variants", type=int, default=3)
    p.add_argument("--limit", type=int, default=0)
    p.add_argument("--cases", nargs="*", default=None)
    p.add_argument("--rewriter-model", default=os.environ.get("REWRITER_MODEL", "gpt-4o"))
    p.add_argument("--target-model", default=os.environ.get("TARGET_MODEL", "gpt-4o-mini"))
    p.add_argument("--base", default=os.environ.get("LLM_API_BASE", ""))
    p.add_argument("--key", default=os.environ.get("LLM_API_KEY", ""))
    p.add_argument("--timeout", type=float, default=60.0)
    p.add_argument("--use-cached", action="store_true",
                   help="只读缓存（不复跑）")
    p.add_argument("--out", type=Path, default=OUT_DIR / "rewrite_report.md")
    args = p.parse_args()

    cfg = json.loads(args.config.read_text(encoding="utf-8"))
    cases = cfg.get("cases", [])
    if args.cases:
        cases = [c for c in cases if c["id"] in set(args.cases)]
    if args.limit:
        cases = cases[:args.limit]

    if args.use_cached or not (args.base and args.key):
        # 缓存模式
        variants_map = {}
        for c in cases:
            cache_path = CACHE_DIR / f"{c['id']}.json"
            if cache_path.exists():
                variants_map[c["id"]] = json.loads(cache_path.read_text(encoding="utf-8"))
        if not variants_map:
            print("ERROR: 缓存为空且未提供 API。请先跑一次非 --use-cached 模式生成缓存。",
                  file=sys.stderr)
            return 2
    else:
        # 1) 改写
        variants_map = {}
        for c in cases:
            print(f"rewriting {c['id']}...", end=" ", flush=True)
            user_prompt = REWRITER_PROMPT.format(n=args.n_variants, prompt=c["prompt"])
            try:
                resp = call_chat(args.base, args.key, args.rewriter_model,
                                 user_prompt, timeout=args.timeout, temperature=0.7)
                vs = extract_json(resp).get("variants", [])
            except Exception as e:
                print(f"ERROR: {e}")
                vs = []
            variants_map[c["id"]] = vs
            (CACHE_DIR / f"{c['id']}.json").write_text(
                json.dumps(vs, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"→ {len(vs)} variants")
        # 2) 答题 + 评分
    results = []
    offline_fallback_answer = None
    if not (args.base and args.key):
        # 无 API：使用 raw_answers 中的现有答案作为所有变体的"答案"（退化但能跑通流程）
        ans_dir = ROOT / "raw_answers"
        for c in cases:
            ap = next(ans_dir.glob(f"*{c['id']}*.md"), None)
            if ap:
                offline_fallback_answer = ap.read_text(encoding="utf-8")
                break

    for c in cases:
        vs = variants_map.get(c["id"], [])
        if not vs:
            results.append({"id": c["id"], "name": c["name"],
                            "consistency": None, "note": "no variants"})
            continue
        scores = []
        for v in vs:
            try:
                if args.base and args.key:
                    ans = call_chat(args.base, args.key, args.target_model,
                                    v, timeout=args.timeout, temperature=0.0)
                else:
                    # 离线：复用 raw_answer
                    ans = offline_fallback_answer or ""
                ok, total = evaluate_assertion(c.get("assertion", {}), ans)
                scores.append(ok / total if total else 1.0)
            except Exception as e:
                scores.append(0.0)
        avg = round(statistics.mean(scores), 3) if scores else 0
        std = round(statistics.pstdev(scores), 3) if len(scores) > 1 else 0
        results.append({
            "id": c["id"], "name": c["name"], "category": c["category"],
            "n_variants": len(vs),
            "scores": scores,
            "avg": avg,
            "stdev": std,
            "consistency": avg,  # alias
        })

    # 报告
    graded = [r for r in results if r.get("consistency") is not None]
    overall = round(statistics.mean(r["consistency"] for r in graded), 3) if graded else 0
    lines = [
        "# Prompt 改写鲁棒性报告\n",
        f"- 改写模型：`{args.rewriter_model}`",
        f"- 目标模型：`{args.target_model}`",
        f"- 变体数：{args.n_variants}",
        f"- **平均鲁棒性得分：{overall}**（= 各变体下断言通过率的均值，1.0=所有措辞都通过）\n",
        "| ID | 类别 | 变体得分 | 均值 | 标准差 |",
        "|----|------|----------|------|--------|",
    ]
    for r in results:
        if r.get("consistency") is None:
            lines.append(f"| `{r['id']}` | — | — | — | — | ⚠️ {r.get('note','')} |")
            continue
        scores_str = ", ".join(f"{s:.2f}" for s in r["scores"])
        lines.append(
            f"| `{r['id']}` | {r['category']} | {scores_str} "
            f"| {r['avg']} | {r['stdev']} |"
        )
    lines.append("\n## 解读")
    lines.append("- **均值高 / 标准差低** = 鲁棒：不依赖特定措辞。")
    lines.append("- **均值高 / 标准差高** = 大部分变体通过，少数措辞导致失败。")
    lines.append("- **均值低** = 该能力本身不稳，与措辞无关。")
    args.out.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
