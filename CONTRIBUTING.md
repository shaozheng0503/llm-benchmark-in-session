# 贡献指南

欢迎贡献！本文档说明如何给 `minimax-m3-benchmark` 加新测试用例、新断言类型、新分析脚本。

## 目录

1. [加新测试用例](#加新测试用例)
2. [加新断言类型](#加新断言类型)
3. [加新分析脚本](#加新分析脚本)
4. [代码规范](#代码规范)
5. [提交 PR](#提交-pr)

---

## 加新测试用例

1. 编辑 `config/test_cases.json`，在 `cases` 数组中追加一项：
   ```json
   {
     "id": "your_case_id",
     "category": "complex",
     "name": "你的用例名",
     "prompt": "完整的 prompt 文本",
     "assertion": {
       "min_length": 100,
       "should_include_any": ["关键词1", "关键词2"],
       "should_not_include_any": ["禁用词"]
     }
   }
   ```
   - `id` 必须 snake_case 唯一
   - `category` 必须是 schema 中的枚举值
   - `assertion` 至少包含 1 条规则

2. 从 `templates/new_test_case.json` 复制模板修改。

3. 准备答案文件：`raw_answers/your_case_id.md`（如果只想加用例不答，grade 会标为"missing"）。

4. 跑验证：
   ```bash
   python3 scripts/validate.py    # schema 校验
   python3 scripts/grade.py        # 评分
   ```

5. 在 README 的"测试维度"表中加入一行。

## 加新断言类型

在 `scripts/grade.py::run_assertion` 中追加分支：

```python
if "your_assertion" in assertion:
    spec = assertion["your_assertion"]
    # 你的检测逻辑
    passed = ...
    out.append(CheckResult(
        "your_assertion", passed, {"expected": spec, "actual": ...}
    ))
```

并在 `config/test_cases.schema.json` 的 `assertion` 定义中描述新断言（可选）。

加单元测试到 `tests/test_grade.py`。

## 加新分析脚本

模板 `scripts/your_script.py`：

```python
#!/usr/bin/env python3
"""<one-liner description>"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "reports" / "your_script"
OUT_DIR.mkdir(parents=True, exist_ok=True)

def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    # ... 你的参数
    args = p.parse_args()
    # ... 你的逻辑
    # 输出 Markdown 报告
    (OUT_DIR / "report.md").write_text(report, encoding="utf-8")
    return 0

if __name__ == "__main__":
    sys.exit(main())
```

加到 `Makefile` 和 `.github/workflows/benchmark.yml`。

## 代码规范

- Python 3.9+，type hints
- ruff check 必须通过（`make lint`）
- pytest 必须通过（`make test`）
- 每个函数 docstring
- 不引入重型依赖（除 matplotlib / streamlit / jsonschema）

## 提交 PR

1. Fork
2. `git checkout -b feat/your-feature`
3. `pre-commit run --all-files`（如果安装了 pre-commit）
4. `make test` 通过
5. `make lint` 通过
6. PR title 用 `feat:` / `fix:` / `docs:` 前缀
7. 在 PR 描述里说明：
   - 加了什么
   - 跑过哪些测试
   - 截图/报告对比（如果有）

CI 会自动跑 grade / lint / summary 三个 job。
