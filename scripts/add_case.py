#!/usr/bin/env python3
"""
minimax-m3-benchmark · add_case.py

交互式加题向导：让用户输入 prompt + 期望关键词，
自动建议断言 + 写入 test_cases.json + 跑分验证。

用法：
    # 交互式
    python3 scripts/add_case.py

    # 批处理
    python3 scripts/add_case.py --prompt "你的 prompt" --must "关键词1" --must "关键词2"
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CFG = ROOT / "config" / "test_cases.json"


def suggest_assertion(prompt: str, must_keywords: list[str],
                       forbid_keywords: list[str] | None = None) -> dict:
    """根据 prompt 和必含词建议断言。"""
    assertion: dict = {"should_include_all": must_keywords}
    if forbid_keywords:
        assertion["should_not_include_any"] = forbid_keywords
    # 估算最小长度：必含词总字符 + 50% 缓冲
    min_len = sum(len(k) for k in must_keywords) * 3
    if min_len > 50:
        assertion["min_length"] = min_len
    # 如果 prompt 含 JSON 关键词，加 json_required
    if any(kw in prompt.lower() for kw in ["json", "json 格式", "严格 json"]):
        assertion["json_required"] = True
    return assertion


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    p.add_argument("--id", help="用例 ID (snake_case)")
    p.add_argument("--name", help="用例名")
    p.add_argument("--category", default="complex",
                   choices=["smoke", "core", "complex", "safety", "boundary",
                            "real_task", "multilingual"])
    p.add_argument("--prompt", help="完整 prompt")
    p.add_argument("--must", nargs="*", default=[], help="必须包含的关键词")
    p.add_argument("--forbid", nargs="*", default=[], help="禁止出现的词")
    p.add_argument("--auto", action="store_true",
                   help="非交互模式：所有参数都从 CLI 取")
    p.add_argument("--no-validate", action="store_true", help="跳过跑分验证")
    p.add_argument("--no-save", action="store_true", help="不写入 test_cases.json")
    args = p.parse_args()

    # 交互模式
    if not args.auto:
        print("=== 交互式加题向导 ===\n")
        if not args.id:
            args.id = input("用例 ID（snake_case）: ").strip()
        if not args.name:
            args.name = input("用例名: ").strip()
        if not args.prompt:
            print("prompt（多行输入，空行结束）:")
            lines = []
            while True:
                line = input()
                if not line:
                    break
                lines.append(line)
            args.prompt = "\n".join(lines)
        if not args.must:
            kw = input("必含关键词（逗号分隔）: ").strip()
            args.must = [k.strip() for k in kw.split(",") if k.strip()]
        if not args.forbid:
            kw = input("禁用关键词（逗号分隔，可空）: ").strip()
            args.forbid = [k.strip() for k in kw.split(",") if k.strip()]

    if not (args.id and args.name and args.prompt and args.must):
        print("ERROR: 缺少必要参数", file=sys.stderr)
        return 2

    # 建议断言
    assertion = suggest_assertion(args.prompt, args.must, args.forbid)
    print(f"\n建议断言：{json.dumps(assertion, ensure_ascii=False, indent=2)}")

    if not args.auto:
        accept = input("\n接受？(y/n) ").strip().lower()
        if accept != "y":
            print("已取消")
            return 0

    # 写入
    new_case = {
        "id": args.id, "category": args.category, "name": args.name,
        "prompt": args.prompt, "assertion": assertion,
    }
    if not args.no_save:
        cfg = json.loads(CFG.read_text(encoding="utf-8"))
        existing_ids = {c["id"] for c in cfg.get("cases", [])}
        if args.id in existing_ids:
            print(f"ERROR: ID '{args.id}' 已存在", file=sys.stderr)
            return 3
        cfg["cases"].append(new_case)
        CFG.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"✓ 写入 {CFG}")

    # 跑分（无 raw_answer 跳过）
    if not args.no_validate:
        print("\n跑分验证...")
        result = subprocess.run(
            ["python3", "scripts/grade.py"],
            capture_output=True, text=True, cwd=ROOT,
        )
        # 找该 case 的结果
        out = result.stdout
        print(out.splitlines()[-1] if out else "")
        if "missing" in out.lower():
            print(f"⚠️  请用 Claude Code 答完 '{args.id}' 后存到 raw_answers/{args.id}.md")

    return 0


if __name__ == "__main__":
    sys.exit(main())
