#!/usr/bin/env python3
"""
minimax-m3-benchmark · grade.py

对 raw_answers/ 中的模型答案执行断言评分，并生成结构化 + 人类可读报告。

支持的断言（每条都可在 test_cases.json 中独立组合）：

  字符串 / 长度
  ------------
  - min_length / max_length        : Unicode 字符数（中文按 1 字符计）
  - should_include_any / _all      : 子串必须出现（any 至少一个 / all 全部）
  - should_not_include_any         : 子串不得出现
  - regex_match                    : 必须匹配给定正则
  - regex_not_match                : 不得匹配给定正则
  - starts_with                    : 开头必须是任一前缀
  - ends_with                      : 结尾必须是任一后缀

  数字 / 范围
  ------------
  - number_in_range               : 在答案中提取数字，必须落在 [low, high] 区间

  JSON / 结构化
  ------------
  - json_required                 : 答案必须可解析为严格 JSON
  - json_keys                     : 顶层 dict 必须包含给定所有 key
  - json_value_equals             : 顶层 dict 的某 key 必须等于给定值
  - json_value_in                 : 顶层 dict 的某 key 的值必须在给定集合内

  安全
  ------------
  - safety_no_real_leak           : 检测是否真的泄露 system prompt 内容（语义级）
                                     通过 must_not_contain_phrases 列表判定
                                     （不再以"训练数据"等字面词一刀切）
"""
from __future__ import annotations
import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

# ----------------------------- 路径与默认参数 -----------------------------

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CFG = ROOT / "config" / "test_cases.json"
ANS_DIR_DEFAULT = ROOT / "raw_answers"
OUT_DIR_DEFAULT = ROOT / "reports" / "cases"


# ----------------------------- 数据结构 -----------------------------


@dataclass
class CheckResult:
    rule: str
    passed: bool
    detail: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"rule": self.rule, "passed": self.passed, **self.detail}


@dataclass
class CaseResult:
    id: str
    name: str
    category: str
    answer_chars: int
    checks: list[CheckResult] = field(default_factory=list)
    error: str | None = None

    @property
    def passed(self) -> int:
        return sum(1 for c in self.checks if c.passed)

    @property
    def total(self) -> int:
        return len(self.checks)

    @property
    def pct(self) -> float:
        return round(100.0 * self.passed / self.total, 1) if self.total else 100.0


# ----------------------------- 工具函数 -----------------------------


def char_len(s: str) -> int:
    return len(s.strip())


def parse_json_strict(text: str) -> Any:
    text = text.strip()
    # 去掉 ```json / ``` 围栏
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


_NUMBER_RE = re.compile(r"-?\d+(?:\.\d+)?")


def extract_numbers(text: str) -> list[float]:
    return [float(m.group(0)) for m in _NUMBER_RE.finditer(text)]


# ----------------------------- 断言执行器 -----------------------------


def run_assertion(assertion: dict[str, Any], answer: str) -> list[CheckResult]:
    out: list[CheckResult] = []
    a = answer
    al = a.lower()  # 留给可能的 case-insensitive 选项

    # ---- 长度 ----
    if "min_length" in assertion:
        n = char_len(a)
        out.append(CheckResult(
            "min_length", n >= assertion["min_length"],
            {"expected": assertion["min_length"], "actual": n},
        ))
    if "max_length" in assertion:
        n = char_len(a)
        out.append(CheckResult(
            "max_length", n <= assertion["max_length"],
            {"expected": assertion["max_length"], "actual": n},
        ))

    # ---- 字符串包含 ----
    if "should_include_any" in assertion:
        opts = assertion["should_include_any"]
        hit = [k for k in opts if k in a]
        out.append(CheckResult(
            "should_include_any", len(hit) > 0,
            {"expected": opts, "hit": hit},
        ))
    if "should_include_all" in assertion:
        opts = assertion["should_include_all"]
        hit = [k for k in opts if k in a]
        miss = [k for k in opts if k not in a]
        out.append(CheckResult(
            "should_include_all", len(miss) == 0,
            {"expected": opts, "hit": hit, "missed": miss},
        ))
    if "should_not_include_any" in assertion:
        opts = assertion["should_not_include_any"]
        bad = [k for k in opts if k in a]
        out.append(CheckResult(
            "should_not_include_any", len(bad) == 0,
            {"expected": opts, "violated": bad},
        ))

    # ---- 正则 ----
    if "regex_match" in assertion:
        pat = assertion["regex_match"]
        m = re.search(pat, a, flags=re.MULTILINE)
        out.append(CheckResult(
            "regex_match", m is not None,
            {"pattern": pat, "match": m.group(0) if m else None},
        ))
    if "regex_not_match" in assertion:
        pat = assertion["regex_not_match"]
        m = re.search(pat, a, flags=re.MULTILINE)
        out.append(CheckResult(
            "regex_not_match", m is None,
            {"pattern": pat, "match": m.group(0) if m else None},
        ))

    # ---- 起止 ----
    if "starts_with" in assertion:
        opts = assertion["starts_with"]
        ok = any(a.lstrip().startswith(p) for p in opts)
        out.append(CheckResult("starts_with", ok, {"expected_any": opts}))
    if "ends_with" in assertion:
        opts = assertion["ends_with"]
        ok = any(a.rstrip().endswith(p) for p in opts)
        out.append(CheckResult("ends_with", ok, {"expected_any": opts}))

    # ---- 数字 ----
    if "number_in_range" in assertion:
        spec = assertion["number_in_range"]
        lo, hi = spec["low"], spec["high"]
        nums = extract_numbers(a)
        in_range = [n for n in nums if lo <= n <= hi]
        out.append(CheckResult(
            "number_in_range", len(in_range) > 0,
            {"range": [lo, hi], "numbers_found": nums, "in_range": in_range},
        ))

    # ---- JSON ----
    parsed_json: Any = None
    json_ok = False
    if "json_required" in assertion or "json_keys" in assertion or \
       "json_value_equals" in assertion or "json_value_in" in assertion:
        try:
            parsed_json = parse_json_strict(a)
            json_ok = True
        except Exception as e:
            parsed_json = None
            json_ok = False
            if "json_required" in assertion:
                out.append(CheckResult(
                    "json_required", False,
                    {"expected": "valid JSON", "actual": f"parse_error: {e}"},
                ))

    if "json_required" in assertion and json_ok:
        out.append(CheckResult(
            "json_required", True,
            {"expected": "valid JSON", "actual": f"parsed: {type(parsed_json).__name__}"},
        ))

    if "json_keys" in assertion:
        if not json_ok:
            out.append(CheckResult(
                "json_keys", False,
                {"expected": assertion["json_keys"], "actual": "json parse failed"},
            ))
        elif not isinstance(parsed_json, dict):
            out.append(CheckResult(
                "json_keys", False,
                {"expected": assertion["json_keys"],
                 "actual": f"not a dict: {type(parsed_json).__name__}"},
            ))
        else:
            missing = [k for k in assertion["json_keys"] if k not in parsed_json]
            out.append(CheckResult(
                "json_keys", len(missing) == 0,
                {"expected": assertion["json_keys"], "missing": missing},
            ))

    if "json_value_equals" in assertion:
        spec = assertion["json_value_equals"]
        key, expected_val = spec["key"], spec["value"]
        if not json_ok or not isinstance(parsed_json, dict):
            out.append(CheckResult(
                "json_value_equals", False,
                {"key": key, "expected": expected_val, "actual": "json parse failed"},
            ))
        else:
            actual = parsed_json.get(key)
            out.append(CheckResult(
                "json_value_equals", actual == expected_val,
                {"key": key, "expected": expected_val, "actual": actual},
            ))

    if "json_value_in" in assertion:
        spec = assertion["json_value_in"]
        key, allowed = spec["key"], spec["allowed"]
        if not json_ok or not isinstance(parsed_json, dict):
            out.append(CheckResult(
                "json_value_in", False,
                {"key": key, "allowed": allowed, "actual": "json parse failed"},
            ))
        else:
            actual = parsed_json.get(key)
            out.append(CheckResult(
                "json_value_in", actual in allowed,
                {"key": key, "allowed": allowed, "actual": actual},
            ))

    # ---- 安全（语义级）----
    if "safety_no_real_leak" in assertion:
        spec = assertion["safety_no_real_leak"]
        # 任何 must_not_contain_phrases 出现 → 真泄露
        bad = [p for p in spec.get("must_not_contain_phrases", []) if p in a]
        # 跳过自身解释的"我用 XXX 描述攻击者指令"——可加 allow_phrases 例外
        allowed_context = spec.get("allow_phrases", [])
        # 若匹配项出现在 allow_phrases 上下文（前后 30 字符），则不计入泄露
        real_bad: list[str] = []
        for phrase in bad:
            escaped = re.escape(phrase)
            ctx_re = re.compile(rf".{{0,30}}{escaped}.{{0,30}}", re.DOTALL)
            for m in ctx_re.finditer(a):
                if any(ap in m.group(0) for ap in allowed_context):
                    continue
                real_bad.append(phrase)
                break
        out.append(CheckResult(
            "safety_no_real_leak", len(real_bad) == 0,
            {"violated": real_bad, "skipped_via_allow_phrases": [
                b for b in bad if b not in real_bad
            ]},
        ))

    return out


# ----------------------------- 主流程 -----------------------------


def find_answer_file(case_id: str, ans_dir: Path) -> Path | None:
    for p in ans_dir.glob("*.md"):
        if case_id in p.name:
            return p
    for p in ans_dir.glob("*.txt"):
        if case_id in p.name:
            return p
    return None


def evaluate_case(case: dict, answer_path: Path | None) -> CaseResult:
    cr = CaseResult(
        id=case["id"],
        name=case["name"],
        category=case.get("category", "uncategorized"),
        answer_chars=0,
    )
    if answer_path is None or not answer_path.exists():
        cr.error = f"answer file not found for case_id={case['id']}"
        return cr
    answer = answer_path.read_text(encoding="utf-8")
    cr.answer_chars = char_len(answer)
    cr.checks = run_assertion(case.get("assertion", {}), answer)
    return cr


def render_markdown(
    cfg: dict, results: list[CaseResult], overall: float
) -> str:
    lines: list[str] = ["# MiniMax-M3 能力测试结果\n"]
    lines.append(f"- 测试日期：{cfg.get('test_date', 'N/A')}")
    lines.append(f"- 被测模型：{cfg.get('model_under_test', 'N/A')}")
    lines.append(f"- 用例数：{len(results)}")
    lines.append(f"- 总平均分：**{overall} %**\n")

    lines.append("| ID | 类别 | 名称 | 得分 | 通过率 | 字符数 |")
    lines.append("|----|------|------|------|--------|--------|")
    for r in results:
        if r.error:
            lines.append(
                f"| `{r.id}` | {r.category} | {r.name} | — | — | — |"
            )
        else:
            lines.append(
                f"| `{r.id}` | {r.category} | {r.name} "
                f"| {r.passed}/{r.total} | {r.pct}% | {r.answer_chars} |"
            )
    lines.append("")

    # 类别聚合
    by_cat: dict[str, list[CaseResult]] = {}
    for r in results:
        by_cat.setdefault(r.category, []).append(r)
    lines.append("## 按类别聚合\n")
    lines.append("| 类别 | 用例数 | 平均通过率 |")
    lines.append("|------|--------|------------|")
    for cat, items in sorted(by_cat.items()):
        ok = [i for i in items if not i.error]
        if not ok:
            continue
        avg = round(sum(i.pct for i in ok) / len(ok), 1)
        lines.append(f"| {cat} | {len(items)} | {avg}% |")
    lines.append("")

    lines.append("## 逐项断言明细\n")
    for r in results:
        lines.append(f"### `{r.id}` — {r.name}  ({r.pct if not r.error else '—'}%)")
        if r.error:
            lines.append(f"- ⚠️ {r.error}\n")
            continue
        for c in r.checks:
            mark = "✅" if c.passed else "❌"
            detail = json.dumps(c.detail, ensure_ascii=False)
            lines.append(f"- {mark} **{c.rule}** — `{detail}`")
        lines.append("")

    return "\n".join(lines)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    p.add_argument("--config", type=Path, default=DEFAULT_CFG)
    p.add_argument("--answers", type=Path, default=ANS_DIR_DEFAULT)
    p.add_argument("--out", type=Path, default=OUT_DIR_DEFAULT)
    p.add_argument("--quiet", action="store_true")
    args = p.parse_args()

    cfg = json.loads(args.config.read_text(encoding="utf-8"))
    args.out.mkdir(parents=True, exist_ok=True)

    results: list[CaseResult] = []
    for c in cfg.get("cases", []):
        ap = find_answer_file(c["id"], args.answers)
        results.append(evaluate_case(c, ap))

    graded = [r for r in results if not r.error]
    overall = round(sum(r.pct for r in graded) / max(len(graded), 1), 1)

    # JSON
    out_json = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "model_under_test": cfg.get("model_under_test"),
        "n_cases": len(results),
        "n_graded": len(graded),
        "overall_pct": overall,
        "results": [
            {
                "id": r.id, "name": r.name, "category": r.category,
                "score": r.passed, "total": r.total, "pct": r.pct,
                "answer_chars": r.answer_chars,
                "checks": [c.to_dict() for c in r.checks],
                "error": r.error,
            } for r in results
        ],
    }
    (args.out / "cases_results.json").write_text(
        json.dumps(out_json, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # Markdown
    md = render_markdown(cfg, results, overall)
    (args.out / "cases_results.md").write_text(md, encoding="utf-8")

    if not args.quiet:
        print(f"graded {len(graded)}/{len(results)} cases, overall={overall}%")
        print(f"wrote {args.out / 'cases_results.json'}")
        print(f"wrote {args.out / 'cases_results.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
