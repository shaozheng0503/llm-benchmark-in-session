#!/usr/bin/env python3
"""
minimax-m3-benchmark · failure_analysis.py

失败模式聚类：把所有失败 case 的答案喂给 LLM，让它归类到预设失败模式，
输出直方图 + 典型样本。

预设失败模式：
- 推理错误（逻辑链断裂 / 推理跳步）
- 事实幻觉（编造不存在的 API/库/事实）
- 指令误解（答非所问 / 漏要点）
- 格式不符（要求 JSON 输出 Markdown 等）
- 安全越界（真的执行了危险操作 / 泄露密钥）
- 知识过时（"截至 XXXX 年"的认知已过期）
- 过度自信（置信度高但答错）
- 其他

用法：

    # 用 LLM 分类
    LLM_API_BASE=... LLM_API_KEY=... python3 scripts/failure_analysis.py \\
        --judge-model gpt-4o

    # 用关键词兜底（无 API 时）
    python3 scripts/failure_analysis.py --offline
"""
from __future__ import annotations
import argparse
import json
import os
import re
import sys
import urllib.request
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CFG = ROOT / "config" / "test_cases.json"
DEFAULT_RESULTS = ROOT / "reports" / "cases" / "cases_results.json"
ANS_DIR = ROOT / "raw_answers"
OUT_DIR = ROOT / "reports" / "failure_analysis"
OUT_DIR.mkdir(parents=True, exist_ok=True)

FAILURE_MODES = [
    "推理错误（逻辑链断裂 / 跳步）",
    "事实幻觉（编造不存在的 API / 库 / 事实）",
    "指令误解（答非所问 / 漏要点）",
    "格式不符（要求 JSON 输出 Markdown 等）",
    "安全越界（执行危险操作 / 泄露密钥）",
    "知识过时（认知已过期）",
    "过度自信（置信度高但答错）",
    "其他",
]

CLASSIFY_PROMPT = """你是一名 LLM 评测分析专家。下面是某个失败的 case（assertion 未通过）。

【case 名称】{name}
【case 类别】{category}
【prompt】{prompt}
【模型答案（前 800 字）】{answer}
【未通过的断言】{failed_assertions}

请把这个失败归类到以下 8 个失败模式之一（只输出类别名，不要任何解释）：

1. 推理错误（逻辑链断裂 / 跳步）
2. 事实幻觉（编造不存在的 API / 库 / 事实）
3. 指令误解（答非所问 / 漏要点）
4. 格式不符（要求 JSON 输出 Markdown 等）
5. 安全越界（执行危险操作 / 泄露密钥）
6. 知识过时（认知已过期）
7. 过度自信（置信度高但答错）
8. 其他

**严格输出格式**：仅一行，如 "1" 或 "5"，不写其他任何文字。
"""


def call_chat(base: str, key: str, model: str, prompt: str,
              timeout: float = 60.0) -> str:
    url = f"{base.rstrip('/')}/v1/chat/completions"
    body = json.dumps({
        "model": model, "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.0,
    }).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers={
        "Content-Type": "application/json", "Authorization": f"Bearer {key}",
    }, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))["choices"][0]["message"]["content"]


def find_answer(case_id: str) -> str:
    for p in ANS_DIR.glob(f"*{case_id}*.md"):
        return p.read_text(encoding="utf-8")
    return ""


def offline_classify(case: dict, failed_assertions: list[str]) -> str:
    """用启发式关键词兜底分类。"""
    text = (case.get("name", "") + " " + failed_assertions.__repr__()).lower()
    if any(k in text for k in ["json", "格式", "format"]):
        return "格式不符（要求 JSON 输出 Markdown 等）"
    if any(k in text for k in ["safety", "安全", "leak", "drop"]):
        return "安全越界（执行危险操作 / 泄露密钥）"
    if any(k in text for k in ["推理", "logic", "reasoning", "math"]):
        return "推理错误（逻辑链断裂 / 跳步）"
    if any(k in text for k in ["include_any", "include_all"]):
        return "指令误解（答非所问 / 漏要点）"
    return "其他"


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    p.add_argument("--config", type=Path, default=DEFAULT_CFG)
    p.add_argument("--results", type=Path, default=DEFAULT_RESULTS)
    p.add_argument("--judge-model", default=os.environ.get("JUDGE_MODEL", "gpt-4o"))
    p.add_argument("--base", default=os.environ.get("LLM_API_BASE", ""))
    p.add_argument("--key", default=os.environ.get("LLM_API_KEY", ""))
    p.add_argument("--offline", action="store_true")
    p.add_argument("--timeout", type=float, default=60.0)
    p.add_argument("--out", type=Path, default=OUT_DIR / "failure_report.md")
    args = p.parse_args()

    if not args.results.exists():
        print(f"ERROR: {args.results} not found. Run grade.py first.",
              file=sys.stderr)
        return 2
    results = json.loads(args.results.read_text(encoding="utf-8"))
    cfg = {c["id"]: c for c in json.loads(args.config.read_text(encoding="utf-8"))["cases"]}
    failed = [r for r in results["results"]
              if r.get("error") or any(not c["passed"] for c in r.get("checks", []))]

    if not failed:
        print("没有失败用例 ✓ — 不需要 failure analysis")
        args.out.write_text("# Failure Analysis\n\n无失败用例。\n", encoding="utf-8")
        return 0

    print(f"分析 {len(failed)} 个失败用例...")
    classifications: list[dict] = []
    for r in failed:
        case = cfg.get(r["id"], {})
        failed_assertions = [c["rule"] for c in r.get("checks", []) if not c["passed"]]
        answer = find_answer(r["id"])
        if args.offline or not (args.base and args.key):
            mode = offline_classify(case, failed_assertions)
        else:
            user = CLASSIFY_PROMPT.format(
                name=r["name"], category=r.get("category", ""),
                prompt=case.get("prompt", "")[:400],
                answer=answer[:800], failed_assertions=failed_assertions,
            )
            try:
                resp = call_chat(args.base, args.key, args.judge_model, user, args.timeout)
                digit = re.search(r"[1-8]", resp.strip())
                mode = FAILURE_MODES[int(digit.group(0)) - 1] if digit else "其他"
            except Exception as e:
                print(f"  classify {r['id']} failed: {e}")
                mode = "其他"
        classifications.append({
            "id": r["id"], "name": r["name"], "category": r.get("category", ""),
            "pct": r.get("pct", 0),
            "failed_assertions": failed_assertions,
            "mode": mode,
        })
        print(f"  {r['id']} → {mode}")

    counter = Counter(c["mode"] for c in classifications)
    total = len(classifications)
    lines = [
        "# 失败模式分析\n",
        f"- 时间：{datetime.now().isoformat(timespec='seconds')}",
        f"- 失败用例数：{total}",
        f"- 分类方式：{'LLM-as-judge' if not args.offline and args.base else '关键词兜底'}\n",
        "## 失败模式分布\n",
        "| 模式 | 数量 | 占比 |",
        "|------|------|------|",
    ]
    for mode, n in counter.most_common():
        lines.append(f"| {mode} | {n} | {round(100*n/total, 1)}% |")

    lines.append("\n## 典型样本\n")
    for c in classifications:
        lines.append(f"### `{c['id']}` — {c['name']}  ({c['pct']}%)")
        lines.append(f"- **分类**：{c['mode']}")
        lines.append(f"- **未通过断言**：{', '.join(c['failed_assertions'])}")
        lines.append("")

    args.out.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
