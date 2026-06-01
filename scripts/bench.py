#!/usr/bin/env python3
"""
minimax-m3-benchmark · bench.py

在 in-session 限制下做轻量性能基准。两种模式：

1) 默认：分析 raw_answers/ 中已有答案的字符数、估算 token 数，
   给出 throughput / char-density 报告（不依赖外部时钟）。

2) --http：当 MiniMax-M3 提供 HTTP API 时，调用 /v1/chat/completions
   跑 N 轮同一 prompt，统计首 token 时间 (TTFT) 与端到端延迟。

   用法：
     LLM_API_BASE=https://api.xxx.com LLM_API_KEY=sk-xxx \\
     python3 scripts/bench.py --http --model minimax-m3 \\
       --prompt "你好" --rounds 5

3) --times：直接吃一个 JSON 列表（如 [{"prompt":"x","answer":"y","elapsed_ms":123}, ...]）
   用来在 Claude Code 会话里手动记录每轮耗时。
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ANS_DIR = ROOT / "raw_answers"
OUT_DIR = ROOT / "reports" / "summary"
OUT_DIR.mkdir(parents=True, exist_ok=True)


# ----------------------------- 估算 -----------------------------

# 中文 ~1.5 字符/token，英文 ~4 字符/token（CJK 偏保守估值）
_ZH_RATIO = 1.5
_EN_RATIO = 4.0


def estimate_tokens(text: str) -> int:
    """粗略估算 token 数：CJK 字符按 1.5 字符/token，其它按 4 字符/token。"""
    cjk = sum(1 for c in text if "一" <= c <= "鿿")
    other = len(text) - cjk
    return max(1, int(round(cjk / _ZH_RATIO + other / _EN_RATIO)))


# ----------------------------- 静态分析模式 -----------------------------


def analyze_answers(ans_dir: Path) -> list[dict]:
    out = []
    for p in sorted(ans_dir.glob("*.md")):
        text = p.read_text(encoding="utf-8")
        cjk = sum(1 for c in text if "一" <= c <= "鿿")
        out.append({
            "file": p.name,
            "chars": len(text),
            "cjk_chars": cjk,
            "ascii_chars": len(text) - cjk,
            "est_tokens": estimate_tokens(text),
        })
    return out


def render_static_report(rows: list[dict]) -> str:
    if not rows:
        return "# 性能基准（静态分析）\n\n无答案文件。\n"
    total_chars = sum(r["chars"] for r in rows)
    total_tokens = sum(r["est_tokens"] for r in rows)
    lines = [
        "# MiniMax-M3 性能基准（静态分析）\n",
        f"- 样本数：{len(rows)}",
        f"- 总字符数：{total_chars}",
        f"- 估算总 token 数：{total_tokens}",
        f"- 平均 token/答案：{round(total_tokens/len(rows), 1)}\n",
        "| 文件 | 字符 | CJK | ASCII | 估算 token |",
        "|------|------|-----|-------|-----------|",
    ]
    for r in rows:
        lines.append(
            f"| `{r['file']}` | {r['chars']} | {r['cjk_chars']} "
            f"| {r['ascii_chars']} | {r['est_tokens']} |"
        )
    lines.append("")
    lines.append("> 注：这是**字符/token 密度分析**，不包含真实延迟。")
    lines.append("> 真实延迟请用 `--http` 模式（在 API 可用时）或 `--times` 模式手动记录。")
    return "\n".join(lines)


# ----------------------------- HTTP 压测模式 -----------------------------


def http_bench(
    base: str, key: str, model: str, prompt: str, rounds: int, timeout: float
) -> list[dict]:
    import urllib.request
    url = f"{base.rstrip('/')}/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {key}",
    }
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
    }).encode("utf-8")

    samples: list[dict] = []
    for i in range(rounds):
        req = urllib.request.Request(url, data=body, headers=headers, method="POST")
        t0 = time.perf_counter()
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            t1 = time.perf_counter()
            content = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})
            samples.append({
                "round": i + 1,
                "elapsed_ms": round((t1 - t0) * 1000, 1),
                "chars": len(content),
                "prompt_tokens": usage.get("prompt_tokens"),
                "completion_tokens": usage.get("completion_tokens"),
                "status": "ok",
            })
        except Exception as e:
            samples.append({
                "round": i + 1,
                "elapsed_ms": round((time.perf_counter() - t0) * 1000, 1),
                "status": f"error: {e}",
            })
    return samples


def render_http_report(samples: list[dict], prompt: str, model: str) -> str:
    ok = [s for s in samples if s["status"] == "ok"]
    lines = [
        "# MiniMax-M3 HTTP 压测报告\n",
        f"- 模型：`{model}`",
        f"- 轮数：{len(samples)}（成功 {len(ok)}）",
        f"- 提示：{prompt[:60]}{'...' if len(prompt) > 60 else ''}\n",
    ]
    if ok:
        lat = [s["elapsed_ms"] for s in ok]
        lines += [
            "## 延迟统计（ms）",
            f"- min    : {min(lat):.1f}",
            f"- median : {statistics.median(lat):.1f}",
            f"- mean   : {statistics.mean(lat):.1f}",
            f"- max    : {max(lat):.1f}",
            f"- stdev  : {statistics.stdev(lat) if len(lat) > 1 else 0:.1f}",
            "",
            "## 逐轮结果",
            "| # | elapsed_ms | chars | completion_tokens |",
            "|---|------------|-------|-------------------|",
        ]
        for s in ok:
            lines.append(
                f"| {s['round']} | {s['elapsed_ms']} | {s['chars']} "
                f"| {s.get('completion_tokens') or '-'} |"
            )
    bad = [s for s in samples if s["status"] != "ok"]
    if bad:
        lines.append("\n## 失败")
        for s in bad:
            lines.append(f"- 第 {s['round']} 轮：{s['status']}")
    return "\n".join(lines)


# ----------------------------- 手动 times 模式 -----------------------------


def render_times_report(samples: list[dict]) -> str:
    ok = [s for s in samples if s.get("elapsed_ms") is not None]
    lines = [
        "# MiniMax-M3 手动计时报告\n",
        f"- 样本数：{len(samples)}（有效 {len(ok)}）\n",
    ]
    if ok:
        lat = [s["elapsed_ms"] for s in ok]
        lines += [
            "## 延迟（ms）",
            f"- min    : {min(lat)}",
            f"- median : {statistics.median(lat)}",
            f"- mean   : {statistics.mean(lat):.1f}",
            f"- max    : {max(lat)}",
            "",
            "## 逐条",
            "| prompt | elapsed_ms | chars | est_tokens |",
            "|--------|------------|-------|-----------|",
        ]
        for s in ok:
            lines.append(
                f"| {s.get('prompt','')[:30]} | {s['elapsed_ms']} "
                f"| {s.get('chars','')} | {estimate_tokens(s.get('answer',''))} |"
            )
    return "\n".join(lines)


# ----------------------------- 入口 -----------------------------


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    p.add_argument("--answers", type=Path, default=ANS_DIR)
    p.add_argument("--out", type=Path, default=OUT_DIR / "bench_report.md")

    # HTTP 模式
    p.add_argument("--http", action="store_true")
    p.add_argument("--base", default=os.environ.get("LLM_API_BASE", ""))
    p.add_argument("--key", default=os.environ.get("LLM_API_KEY", ""))
    p.add_argument("--model", default=os.environ.get("BENCH_MODEL", "minimax-m3"))
    p.add_argument("--prompt", default="用一句话介绍你自己。")
    p.add_argument("--rounds", type=int, default=5)
    p.add_argument("--timeout", type=float, default=60.0)

    # 手动计时模式
    p.add_argument("--times", type=str, default=None,
                   help="JSON 文件路径，包含 [{prompt,answer,elapsed_ms}, ...]")

    args = p.parse_args()

    if args.http:
        if not args.base or not args.key:
            print("ERROR: --http 模式需要 --base 与 --key（或 env LLM_API_BASE/LLM_API_KEY）",
                  file=sys.stderr)
            return 2
        samples = http_bench(args.base, args.key, args.model, args.prompt,
                             args.rounds, args.timeout)
        md = render_http_report(samples, args.prompt, args.model)
    elif args.times:
        data = json.loads(Path(args.times).read_text(encoding="utf-8"))
        md = render_times_report(data)
    else:
        rows = analyze_answers(args.answers)
        md = render_static_report(rows)

    args.out.write_text(md, encoding="utf-8")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
