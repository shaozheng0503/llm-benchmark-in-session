#!/usr/bin/env python3
"""
minimax-m3-benchmark · validate.py

JSON Schema 校验 test_cases.json。

用法：
    python3 scripts/validate.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = ROOT / "config" / "test_cases.schema.json"
TARGET = ROOT / "config" / "test_cases.json"


def main() -> int:
    if not SCHEMA.exists():
        print(f"ERROR: schema not found: {SCHEMA}", file=sys.stderr)
        return 2
    if not TARGET.exists():
        print(f"ERROR: target not found: {TARGET}", file=sys.stderr)
        return 2

    try:
        import jsonschema
    except ImportError:
        print("ERROR: 需要安装 jsonschema：pip install jsonschema",
              file=sys.stderr)
        return 3

    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    data = json.loads(TARGET.read_text(encoding="utf-8"))

    validator = jsonschema.Draft7Validator(schema)
    errors = list(validator.iter_errors(data))

    if not errors:
        print(f"✅ {TARGET.name} 通过 schema 校验")
        return 0

    print(f"❌ 发现 {len(errors)} 个 schema 错误：\n")
    for err in errors:
        path = "/".join(str(p) for p in err.absolute_path) or "(root)"
        print(f"  - {path}: {err.message}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
