#!/usr/bin/env python3
"""
minimax-m3-benchmark · leaderboard.py

多模型基线：批量跑多个模型的同一组测试，输出排行榜。

用法：
    LLM_API_BASE=... LLM_API_KEY=... python3 scripts/leaderboard.py \\
        --models gpt-4o gpt-4o-mini claude-sonnet-4-5 claude-opus-4-8
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CFG = ROOT / "config/test_cases.json"
OUT_DIR = ROOT / "reports" / "leaderboard"
OUT_DIR.mkdir(parents=True, exist_ok=True)
ANSWERS_DIR = OUT_DIR / "answers"
ANSWERS_DIR.mkdir(exist_ok=True)

sys.path.insert(0, str(ROOT / "scripts"))
from grade import run_assertion  # type: ignore  # noqa: E402


def call_chat(base, key, model, prompt, timeout=60.0, temperature=0.0):
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
    }).encode("utf-8")
    req = urllib.request.Request(f"{base.rstrip('/')}/v1/chat/completions", data=body, headers={
        "Content-Type": "application/json", "Authorization": f"Bearer {key}",
    })
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))["choices"][0]["message"]["content"]


def evaluate_assertion(assertion, answer):
    checks = run_assertion(assertion, answer)
    return sum(1 for c in checks if c.passed) / max(len(checks), 1)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    p.add_argument("--config", type=Path, default=DEFAULT_CFG)
    p.add_argument("--models", nargs="+", required=True)
    p.add_argument("--base", default=os.environ.get("LLM_API_BASE", ""))
    p.add_argument("--key", default=os.environ.get("LLM_API_KEY", ""))
    p.add_argument("--cases", nargs="*", default=None)
    p.add_argument("--limit", type=int, default=0)
    p.add_argument("--timeout", type=float, default=60.0)
    p.add_argument("--out", type=Path, default=OUT_DIR / "leaderboard.md")
    p.add_argument("--out-json", type=Path, default=OUT_DIR / "leaderboard.json")
    args = p.parse_args()

    if not (args.base and args.key):
        print("ERROR: 需 --base/--key", file=sys.stderr)
        return 2

    cfg = json.loads(args.config.read_text(encoding="utf-8"))
    cases = cfg.get("cases", [])
    if args.cases:
        cases = [c for c in cases if c["id"] in set(args.cases)]
    cases = cases[:args.limit] if args.limit else cases

    # 跑每个模型
    leaderboard = []
    for model in args.models:
        print(f"\n=== {model} ===")
        model_ans_dir = ANSWERS_DIR / model
        model_ans_dir.mkdir(exist_ok=True)
        scores = []
        for c in cases:
            ans_path = model_ans_dir / f"{c['id']}.md"
            if ans_path.exists():
                ans = ans_path.read_text(encoding="utf-8")
            else:
                try:
                    ans = call_chat(args.base, args.key, model,
                                    c["prompt"], args.timeout)
                    ans_path.write_text(ans, encoding="utf-8")
                except Exception as e:
                    print(f"  [{c['id']}] ERROR: {e}")
                    ans = ""
            score = evaluate_assertion(c.get("assertion", {}), ans)
            scores.append({"id": c["id"], "score": score})
            print(f"  {c['id']}: {score*100:.0f}%")
        avg = statistics.mean(s["score"] for s in scores)
        leaderboard.append({
            "model": model, "avg_quality": round(avg * 100, 2),
            "n_cases": len(scores), "scores": scores,
        })
        print(f"  → 平均：{avg*100:.1f}%")

    # 排序
    leaderboard.sort(key=lambda x: -x["avg_quality"])

    # 报告
    lines = [
        "# 多模型 Leaderboard\n",
        f"- 时间：{datetime.now().isoformat(timespec='seconds')}",
        f"- 题目数：{len(cases)}",
        f"- 模型数：{len(args.models)}\n",
        "## 排名\n",
        "| 排名 | 模型 | 平均分 |",
        "|------|------|--------|",
    ]
    for i, m in enumerate(leaderboard, 1):
        lines.append(f"| {i} | `{m['model']}` | {m['avg_quality']}% |")

    # 各模型逐题对比
    lines.append("\n## 逐题对比\n")
    lines.append("| ID | " + " | ".join(m["model"] for m in leaderboard) + " |")
    lines.append("|" + "---|" * (len(leaderboard) + 1))
    by_id_scores: dict[str, list[tuple[str, float]]] = {}
    for m in leaderboard:
        for s in m["scores"]:
            by_id_scores.setdefault(s["id"], []).append((m["model"], s["score"]))
    for cid in sorted(by_id_scores.keys()):
        cells = []
        for m in leaderboard:
            score = next((s["score"] for s in m["scores"] if s["id"] == cid), 0)
            cells.append(f"{score*100:.0f}%")
        lines.append(f"| `{cid}` | " + " | ".join(cells) + " |")

    args.out.write_text("\n".join(lines), encoding="utf-8")
    args.out_json.write_text(
        json.dumps({"generated_at": datetime.now().isoformat(),
                    "models": [{"model": m["model"], "quality": m["avg_quality"]}
                                for m in leaderboard]},
                    ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nwrote {args.out}")
    print(f"wrote {args.out_json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
