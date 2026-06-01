#!/usr/bin/env python3
"""
minimax-m3-benchmark · consistency.py

同题 N 次采样一致性测试：在 temperature>0 下让模型跑同一题 N 次，
统计"主答案占比 + 熵"，揭示模型的稳定性和信心。

用法：

    # 同题 5 次（HTTP 模式，需 API）
    LLM_API_BASE=https://api.openai.com LLM_API_KEY=sk-xxx \\
        python3 scripts/consistency.py --model gpt-4o --rounds 5 --temperature 1.0

    # 复用 raw_answers 评估"答案唯一性"（无需 API）
    python3 scripts/consistency.py --answers raw_answers/ --n-variants 3

输出 reports/consistency/consistency_report.md。
"""
from __future__ import annotations
import argparse
import json
import math
import os
import re
import statistics
import sys
import time
import urllib.request
from collections import Counter
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CFG = ROOT / "config" / "test_cases.json"
ANS_DIR = ROOT / "raw_answers"
OUT_DIR = ROOT / "reports" / "consistency"
OUT_DIR.mkdir(parents=True, exist_ok=True)


# ----------------------------- HTTP 调用 -----------------------------


def call_chat(base: str, key: str, model: str, prompt: str,
              temperature: float, timeout: float = 60.0) -> str:
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
        data = json.loads(resp.read().decode("utf-8"))
    return data["choices"][0]["message"]["content"]


# ----------------------------- 答案相似度 -----------------------------


def normalize(text: str) -> str:
    """去标点/空白/大小写差异。"""
    return re.sub(r"\s+", "", text).strip().lower()


def similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, normalize(a), normalize(b)).ratio()


def cluster_answers(answers: list[str], sim_threshold: float = 0.85) -> list[list[int]]:
    """简单聚类：相似度 ≥ 阈值归为同一组。返回 [group_indices]."""
    groups: list[list[int]] = []
    for i, ans in enumerate(answers):
        placed = False
        for g in groups:
            # 跟组内任一答案相似即合并
            if any(similarity(ans, answers[j]) >= sim_threshold for j in g):
                g.append(i)
                placed = True
                break
        if not placed:
            groups.append([i])
    return groups


def entropy_from_counts(counts: list[int]) -> float:
    """计算香农熵（自然对数）。"""
    total = sum(counts)
    if total == 0:
        return 0.0
    p = [c / total for c in counts]
    return -sum(pi * math.log(pi) for pi in p if pi > 0)


# ----------------------------- 主流程 -----------------------------


def find_answer_file(case_id: str, ans_dir: Path) -> Path | None:
    for p in ans_dir.glob("*.md"):
        if case_id in p.name:
            return p
    return None


def http_consistency(
    cfg: dict, base: str, key: str, model: str,
    rounds: int, temperature: float, timeout: float,
    limit: int, cases_filter: list[str] | None,
) -> list[dict]:
    cases = cfg.get("cases", [])
    if cases_filter:
        cases = [c for c in cases if c["id"] in set(cases_filter)]
    cases = cases[:limit] if limit else cases

    out: list[dict] = []
    for c in cases:
        print(f"running {c['id']} × {rounds}...", end=" ", flush=True)
        answers: list[str] = []
        for _ in range(rounds):
            try:
                a = call_chat(base, key, model, c["prompt"],
                              temperature, timeout=timeout)
                answers.append(a)
            except Exception as e:
                answers.append(f"ERROR: {e}")
        # 聚类
        ok_answers = [a for a in answers if not a.startswith("ERROR")]
        groups = cluster_answers(ok_answers)
        group_sizes = sorted([len(g) for g in groups], reverse=True)
        majority = group_sizes[0] if group_sizes else 0
        majority_pct = round(100.0 * majority / max(len(ok_answers), 1), 1)
        ent = round(entropy_from_counts(group_sizes), 3)
        sample_majority = ok_answers[groups[0][0]] if groups else ""
        out.append({
            "id": c["id"], "name": c["name"], "category": c["category"],
            "rounds": rounds, "ok_rounds": len(ok_answers),
            "n_clusters": len(groups),
            "majority_size": majority,
            "majority_pct": majority_pct,
            "entropy": ent,
            "consistency_score": round(majority_pct / 100, 3),
            "sample_majority": sample_majority[:200],
        })
        print(f"→ {len(groups)} clusters, majority={majority_pct}%, ent={ent}")
    return out


def file_consistency(cfg: dict, ans_dir: Path, n_variants: int) -> list[dict]:
    """从 raw_answers 中读取每个用例的答案，估算"单一答案" 的一致性。
    这是一个退化版——只有 1 个样本时一致性=100%。但当 raw_answers 中存在
    多个同名文件（如 04_long_summary_v1.md, 04_long_summary_v2.md）时，
    会聚类比较。
    """
    out: list[dict] = []
    for c in cfg.get("cases", []):
        # 收集该 case_id 下的所有 .md 变体
        variants = sorted(ans_dir.glob(f"*{c['id']}*.md"))
        # 如果只有 1 个，则不评估
        if len(variants) < 2:
            out.append({
                "id": c["id"], "name": c["name"], "category": c["category"],
                "n_variants": len(variants), "consistency_score": None,
                "note": "single sample; need ≥2 variants to assess",
            })
            continue
        answers = [v.read_text(encoding="utf-8") for v in variants]
        groups = cluster_answers(answers)
        group_sizes = sorted([len(g) for g in groups], reverse=True)
        majority = group_sizes[0]
        majority_pct = round(100.0 * majority / len(answers), 1)
        ent = round(entropy_from_counts(group_sizes), 3)
        out.append({
            "id": c["id"], "name": c["name"], "category": c["category"],
            "n_variants": len(variants),
            "n_clusters": len(groups),
            "majority_size": majority,
            "majority_pct": majority_pct,
            "entropy": ent,
            "consistency_score": round(majority_pct / 100, 3),
        })
    return out


def render_report(results: list[dict], mode: str, **meta: Any) -> str:
    lines = [
        f"# MiniMax-M3 一致性测试报告（{mode}）\n",
        f"- 时间：{datetime.now().isoformat(timespec='seconds')}",
    ]
    for k, v in meta.items():
        lines.append(f"- {k}：{v}")

    graded = [r for r in results if r.get("consistency_score") is not None]
    if graded:
        avg = round(statistics.mean(r["consistency_score"] for r in graded), 3)
        lines.append(f"- **平均一致性得分：{avg}**（0=完全分散, 1=完全一致）\n")
    else:
        lines.append("")

    lines += [
        "| ID | 类别 | 样本 | 聚类 | 主答案占比 | 熵 | 一致性 | 备注 |",
        "|----|------|------|------|------------|----|--------|------|",
    ]
    for r in results:
        score = r.get("consistency_score")
        score_disp = f"{score}" if score is not None else "—"
        lines.append(
            f"| `{r['id']}` | {r['category']} | {r.get('rounds') or r.get('n_variants')} "
            f"| {r.get('n_clusters', '-')} "
            f"| {r.get('majority_pct', '-')}% "
            f"| {r.get('entropy', '-')} "
            f"| {score_disp} "
            f"| {r.get('note', '')} |"
        )
    lines.append("\n## 解读")
    lines.append("- **consistency_score** = 主答案占全部样本的比例。1.0 表示所有样本答案一致。")
    lines.append("- **entropy** 越高，答案越分散（0=所有答案相同）。")
    lines.append("- 主答案样本：")
    for r in graded:
        if r.get("sample_majority"):
            lines.append(f"  - `{r['id']}`: {r['sample_majority'][:80]}…")
    return "\n".join(lines)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    p.add_argument("--config", type=Path, default=DEFAULT_CFG)
    p.add_argument("--answers", type=Path, default=ANS_DIR)
    p.add_argument("--out", type=Path, default=OUT_DIR / "consistency_report.md")

    # HTTP 模式参数
    p.add_argument("--base", default=os.environ.get("LLM_API_BASE", ""))
    p.add_argument("--key", default=os.environ.get("LLM_API_KEY", ""))
    p.add_argument("--model", default=os.environ.get("MODEL", ""))
    p.add_argument("--rounds", type=int, default=5)
    p.add_argument("--temperature", type=float, default=1.0)
    p.add_argument("--timeout", type=float, default=60.0)
    p.add_argument("--limit", type=int, default=0)
    p.add_argument("--cases", nargs="*", default=None)
    args = p.parse_args()

    cfg = json.loads(args.config.read_text(encoding="utf-8"))

    if args.base and args.key and args.model:
        results = http_consistency(
            cfg, args.base, args.key, args.model,
            args.rounds, args.temperature, args.timeout,
            args.limit, args.cases,
        )
        md = render_report(results, "HTTP 采样",
                           model=args.model, rounds=args.rounds,
                           temperature=args.temperature)
    else:
        print("INFO: 未提供 --base/--key/--model，使用文件模式（仅统计 raw_answers 中变体）",
              file=sys.stderr)
        results = file_consistency(cfg, args.answers, n_variants=0)
        md = render_report(results, "文件分析",
                           ans_dir=str(args.answers))

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(md, encoding="utf-8")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
