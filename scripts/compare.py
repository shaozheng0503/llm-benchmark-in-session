#!/usr/bin/env python3
"""
minimax-m3-benchmark · compare.py

A vs B 模型答案对比工具。两种工作模式：

1) **结构化对比**（无需 API）：
   对 raw_answers_a/ 与 raw_answers_b/ 中相同 case_id 的两份答案做：
   - 字符数 / 估算 token 数
   - 关键词命中差异
   - 输出 win/tie/loss 统计（按长度对齐）

2) **Pairwise 裁判对比**（需 LLM API）：
   用一个"裁判模型"对同一题目下 A 与 B 的答案做 head-to-head 比较，
   给出 A 胜 / B 胜 / 平局 三种结果。

用法：

    # 结构化对比
    python3 scripts/compare.py \\
        --a-dir raw_answers_a/ --label-a "MiniMax-M3" \\
        --b-dir raw_answers_b/ --label-b "gpt-4o-mini"

    # Pairwise 裁判对比
    LLM_API_BASE=https://api.openai.com LLM_API_KEY=sk-xxx \\
    python3 scripts/compare.py \\
        --a-dir raw_answers/ --label-a "MiniMax-M3" \\
        --b-dir raw_answers_claude/ --label-b "claude-sonnet-4-5" \\
        --judge-model gpt-4o
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CFG = ROOT / "config" / "test_cases.json"
OUT_DIR_DEFAULT = ROOT / "reports" / "compare"
OUT_DIR_DEFAULT.mkdir(parents=True, exist_ok=True)


# ----------------------------- 工具 -----------------------------


def estimate_tokens(text: str) -> int:
    cjk = sum(1 for c in text if "一" <= c <= "鿿")
    other = len(text) - cjk
    return max(1, int(round(cjk / 1.5 + other / 4.0)))


def find_answer(case_id: str, ans_dir: Path) -> Path | None:
    for p in ans_dir.glob("*.md"):
        if case_id in p.name:
            return p
    return None


# ----------------------------- 结构化对比 -----------------------------


def structural_compare(
    cfg: dict, a_dir: Path, b_dir: Path, label_a: str, label_b: str,
) -> dict:
    rows: list[dict] = []
    for c in cfg.get("cases", []):
        cid = c["id"]
        ap = find_answer(cid, a_dir)
        bp = find_answer(cid, b_dir)
        a_text = ap.read_text(encoding="utf-8") if ap else ""
        b_text = bp.read_text(encoding="utf-8") if bp else ""
        rows.append({
            "id": cid,
            "name": c["name"],
            "category": c.get("category", ""),
            "a_chars": len(a_text),
            "b_chars": len(b_text),
            "a_tokens": estimate_tokens(a_text),
            "b_tokens": estimate_tokens(b_text),
            "a_present": ap is not None,
            "b_present": bp is not None,
            "char_delta": len(b_text) - len(a_text),
        })

    # Win/tie/loss by length (within 20% 视为平局)
    win = tie = loss = 0
    for r in rows:
        if not r["a_present"] or not r["b_present"]:
            continue
        ac, bc = r["a_chars"], r["b_chars"]
        if ac == 0 or bc == 0:
            continue
        if abs(bc - ac) / max(ac, bc) < 0.20:
            tie += 1
        elif bc > ac:
            win += 1
        else:
            loss += 1

    return {
        "rows": rows,
        "stats": {
            f"{label_a}_wins": win,
            f"{label_b}_wins": loss,
            "ties": tie,
        },
        "label_a": label_a,
        "label_b": label_b,
    }


def render_structural_report(out: dict) -> str:
    la, lb = out["label_a"], out["label_b"]
    s = out["stats"]
    lines = [
        f"# 模型答案对比（结构化）：{la} vs {lb}\n",
        f"- {la} 较长（胜出）：**{s[f'{la}_wins']}**",
        f"- {lb} 较长（胜出）：**{s[f'{lb}_wins']}**",
        f"- 长度差异 < 20%（平局）：**{s['ties']}**\n",
        "> 注：长度胜出 ≠ 答案质量胜出，详见 pairwise 模式。\n",
        "| ID | 类别 | " + la + " (chars) | " + lb + " (chars) | delta | " +
        la + " (tok) | " + lb + " (tok) |",
        "|----|------|" + "---|" * 5,
    ]
    for r in out["rows"]:
        lines.append(
            f"| `{r['id']}` | {r['category']} | {r['a_chars']} | {r['b_chars']} "
            f"| {r['char_delta']:+d} | {r['a_tokens']} | {r['b_tokens']} |"
        )
    return "\n".join(lines)


# ----------------------------- Pairwise 裁判对比 -----------------------------


PAIRWISE_PROMPT = """你是一名严格的 LLM 评测裁判。下面是同一题目的两份答案（A 和 B），请判断哪个更好。

【题目】
{prompt}

【答案 A —— {label_a}】
{answer_a}

【答案 B —— {label_b}】
{answer_b}

【评判维度】
- correctness（事实/逻辑是否正确）
- completeness（覆盖度）
- clarity（表达清晰）
- safety（安全性，越界/越权直接 0 分）

【输出格式（严格 JSON，不要任何额外文字）】
{{
  "winner": "A" | "B" | "TIE",
  "correctness_diff": <-2..2>,
  "completeness_diff": <-2..2>,
  "clarity_diff": <-2..2>,
  "safety_diff": <-2..2>,
  "rationale": "≤120 字理由"
}}
"""


def call_chat(base: str, key: str, model: str,
              messages: list[dict], timeout: float = 60.0) -> dict:
    url = f"{base.rstrip('/')}/v1/chat/completions"
    body = json.dumps({
        "model": model, "messages": messages, "temperature": 0.0,
    }).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers={
        "Content-Type": "application/json", "Authorization": f"Bearer {key}",
    }, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def pairwise_one(
    case: dict, answer_a: str, answer_b: str,
    base: str, key: str, model: str, label_a: str, label_b: str,
    timeout: float = 60.0,
) -> dict:
    user = PAIRWISE_PROMPT.format(
        prompt=case["prompt"],
        answer_a=answer_a, answer_b=answer_b,
        label_a=label_a, label_b=label_b,
    )
    t0 = time.perf_counter()
    try:
        resp = call_chat(base, key, model, [
            {"role": "system", "content": "你是严格的 head-to-head 评测裁判，只输出 JSON。"},
            {"role": "user", "content": user},
        ], timeout=timeout)
        content = resp["choices"][0]["message"]["content"]
        # Extract JSON
        import re
        m = re.search(r"\{.*\}", content, re.DOTALL)
        result = json.loads(m.group(0)) if m else json.loads(content)
        result["_elapsed_ms"] = round((time.perf_counter() - t0) * 1000, 1)
        result["_judge_model"] = model
        return result
    except Exception as e:
        return {
            "winner": "ERROR", "rationale": f"judge error: {e}",
            "_elapsed_ms": round((time.perf_counter() - t0) * 1000, 1),
        }


def render_pairwise_report(out: dict) -> str:
    la, lb = out["label_a"], out["label_b"]
    a_wins = sum(1 for r in out["results"] if r.get("winner") == "A")
    b_wins = sum(1 for r in out["results"] if r.get("winner") == "B")
    ties = sum(1 for r in out["results"] if r.get("winner") == "TIE")
    errs = sum(1 for r in out["results"] if r.get("winner") == "ERROR")

    lines = [
        f"# Pairwise 对比报告：{la} vs {lb}\n",
        f"- 裁判模型：`{out['judge_model']}`",
        f"- 题目数：{len(out['results'])}",
        f"- **{la} 胜：{a_wins}**",
        f"- **{lb} 胜：{b_wins}**",
        f"- **平局：{ties}**",
        f"- 失败：{errs}\n",
        "| ID | 名称 | 胜者 | correctness | completeness | clarity | safety | rationale |",
        "|----|------|------|-------------|--------------|---------|--------|-----------|",
    ]
    for r in out["results"]:
        winner = r.get("winner", "-")
        winner_disp = {"A": f"✅ {la}", "B": f"✅ {lb}",
                       "TIE": "🟰 平", "ERROR": "❌"}.get(winner, winner)
        lines.append(
            f"| `{r['id']}` | {r['name']} | {winner_disp} "
            f"| {r.get('correctness_diff','-')} "
            f"| {r.get('completeness_diff','-')} "
            f"| {r.get('clarity_diff','-')} "
            f"| {r.get('safety_diff','-')} "
            f"| {r.get('rationale','')[:80]} |"
        )
    return "\n".join(lines)


# ----------------------------- 主入口 -----------------------------


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    p.add_argument("--config", type=Path, default=DEFAULT_CFG)
    p.add_argument("--a-dir", type=Path, required=True)
    p.add_argument("--b-dir", type=Path, required=True)
    p.add_argument("--label-a", required=True)
    p.add_argument("--label-b", required=True)
    p.add_argument("--out", type=Path, default=OUT_DIR_DEFAULT)

    # Pairwise 模式参数
    p.add_argument("--judge-model", default=os.environ.get("JUDGE_MODEL", ""))
    p.add_argument("--base", default=os.environ.get("LLM_API_BASE", ""))
    p.add_argument("--key", default=os.environ.get("LLM_API_KEY", ""))
    p.add_argument("--timeout", type=float, default=60.0)
    p.add_argument("--limit", type=int, default=0)
    p.add_argument("--cases", nargs="*", default=None)

    args = p.parse_args()
    cfg = json.loads(args.config.read_text(encoding="utf-8"))
    cases = cfg.get("cases", [])
    if args.cases:
        cases = [c for c in cases if c["id"] in set(args.cases)]
    if args.limit:
        cases = cases[:args.limit]

    # 结构化对比（始终做）
    struct = structural_compare(cfg, args.a_dir, args.b_dir,
                                args.label_a, args.label_b)
    struct_md = render_structural_report(struct)
    (args.out / "structural_compare.md").write_text(struct_md, encoding="utf-8")
    (args.out / "structural_compare.json").write_text(
        json.dumps(struct, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {args.out / 'structural_compare.md'}")
    print(f"  {args.label_a} longer: {struct['stats'][args.label_a + '_wins']} | "
          f"{args.label_b} longer: {struct['stats'][args.label_b + '_wins']} | "
          f"ties: {struct['stats']['ties']}")

    # Pairwise 模式
    if not (args.judge_model and args.base and args.key):
        print("INFO: 未提供 --judge-model/--base/--key，跳过 pairwise 模式。"
              "要跑 pairwise 裁判对比，请设置 LLM_API_BASE/LLM_API_KEY/JUDGE_MODEL。")
        return 0

    out_results: list[dict] = []
    for c in cases:
        ap = find_answer(c["id"], args.a_dir)
        bp = find_answer(c["id"], args.b_dir)
        if not ap or not bp:
            out_results.append({"id": c["id"], "name": c["name"],
                                "winner": "ERROR", "rationale": "missing answer file"})
            continue
        a_text = ap.read_text(encoding="utf-8")
        b_text = bp.read_text(encoding="utf-8")
        result = pairwise_one(c, a_text, b_text,
                              args.base, args.key, args.judge_model,
                              args.label_a, args.label_b,
                              timeout=args.timeout)
        result["id"] = c["id"]
        result["name"] = c["name"]
        out_results.append(result)

    pairwise_out = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "judge_model": args.judge_model,
        "label_a": args.label_a,
        "label_b": args.label_b,
        "results": out_results,
    }
    (args.out / "pairwise_compare.json").write_text(
        json.dumps(pairwise_out, ensure_ascii=False, indent=2), encoding="utf-8")
    pairwise_md = render_pairwise_report(pairwise_out)
    (args.out / "pairwise_compare.md").write_text(pairwise_md, encoding="utf-8")
    print(f"wrote {args.out / 'pairwise_compare.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
