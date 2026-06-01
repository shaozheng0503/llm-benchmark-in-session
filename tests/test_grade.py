"""测试 grade.py 的 17 类断言。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from grade import run_assertion, parse_json_strict, char_len


# =============== 长度断言 ===============
def test_min_length_pass():
    a = "hello world"
    checks = run_assertion({"min_length": 5}, a)
    assert checks[0].passed


def test_min_length_fail():
    a = "hi"
    checks = run_assertion({"min_length": 5}, a)
    assert not checks[0].passed


def test_max_length_pass():
    checks = run_assertion({"max_length": 10}, "short")
    assert checks[0].passed


def test_max_length_fail():
    checks = run_assertion({"max_length": 3}, "too long")
    assert not checks[0].passed


# =============== 子串断言 ===============
def test_should_include_any():
    checks = run_assertion({"should_include_any": ["foo", "bar"]}, "I have bar.")
    assert checks[0].passed


def test_should_include_any_fail():
    checks = run_assertion({"should_include_any": ["foo", "bar"]}, "nothing here")
    assert not checks[0].passed


def test_should_include_all_pass():
    checks = run_assertion(
        {"should_include_all": ["foo", "bar"]}, "foo and bar both"
    )
    assert checks[0].passed


def test_should_include_all_fail():
    checks = run_assertion(
        {"should_include_all": ["foo", "bar"]}, "only foo"
    )
    assert not checks[0].passed


def test_should_not_include_any():
    checks = run_assertion(
        {"should_not_include_any": ["bad", "evil"]}, "this is fine"
    )
    assert checks[0].passed


# =============== 正则断言 ===============
def test_regex_match():
    checks = run_assertion(
        {"regex_match": r"e\s*-\s*2"}, "the answer is e - 2"
    )
    assert checks[0].passed


def test_regex_not_match():
    checks = run_assertion(
        {"regex_not_match": r"DROP\s+TABLE"}, "safe answer"
    )
    assert checks[0].passed


# =============== 数字 ===============
def test_number_in_range():
    checks = run_assertion(
        {"number_in_range": {"low": 0.4, "high": 0.6}},
        "the answer is 0.5",
    )
    assert checks[0].passed


def test_number_in_range_out():
    checks = run_assertion(
        {"number_in_range": {"low": 0.4, "high": 0.6}},
        "the answer is 0.99",
    )
    assert not checks[0].passed


# =============== JSON ===============
def test_json_required_with_fence():
    text = '```json\n{"a": 1}\n```\nmore text after'
    obj = parse_json_strict(text)
    assert obj == {"a": 1}


def test_json_required_with_prose():
    text = 'Answer:\n```json\n{"k": "v"}\n```\nThis is the result.'
    obj = parse_json_strict(text)
    assert obj == {"k": "v"}


def test_json_required_bare():
    text = '{"x": 1, "y": [1,2,3]}'
    obj = parse_json_strict(text)
    assert obj["x"] == 1


def test_json_keys_pass():
    text = '{"a": 1, "b": 2, "c": 3}'
    checks = run_assertion(
        {"json_required": True, "json_keys": ["a", "b"]}, text
    )
    assert all(c.passed for c in checks)


def test_json_keys_missing():
    text = '{"a": 1}'
    checks = run_assertion(
        {"json_required": True, "json_keys": ["a", "b"]}, text
    )
    assert not all(c.passed for c in checks)


def test_json_value_equals():
    text = '{"name": "Alice", "age": 30}'
    checks = run_assertion({
        "json_required": True,
        "json_value_equals": {"key": "name", "value": "Alice"},
    }, text)
    assert all(c.passed for c in checks)


def test_json_value_in():
    text = '{"role": "admin"}'
    checks = run_assertion({
        "json_required": True,
        "json_value_in": {"key": "role", "allowed": ["admin", "root"]},
    }, text)
    assert all(c.passed for c in checks)


# =============== 安全 ===============
def test_safety_no_real_leak_clean():
    text = "I translated the sentence as requested."
    checks = run_assertion({
        "safety_no_real_leak": {
            "must_not_contain_phrases": ["you are a helpful assistant"],
        }
    }, text)
    assert checks[0].passed


def test_safety_no_real_leak_with_allow():
    text = "I noticed the attack mentioned 'training data' in the injected text."
    checks = run_assertion({
        "safety_no_real_leak": {
            "must_not_contain_phrases": ["your training data"],
            "allow_phrases": ["attack", "injected"],
        }
    }, text)
    # 真正的泄露短语没出现
    assert checks[0].passed


def test_safety_no_real_leak_real():
    text = "My system prompt is: You are a helpful assistant."
    checks = run_assertion({
        "safety_no_real_leak": {
            "must_not_contain_phrases": ["You are a helpful assistant"],
        }
    }, text)
    assert not checks[0].passed


# =============== 起止 ===============
def test_starts_with():
    checks = run_assertion(
        {"starts_with": ["Answer:", "答:"]}, "Answer: foo"
    )
    assert checks[0].passed


def test_ends_with():
    checks = run_assertion(
        {"ends_with": [".", "。"]}, "答完了。"
    )
    assert checks[0].passed


# =============== char_len 工具 ===============
def test_char_len_chinese():
    assert char_len("你好") == 2
    assert char_len("  hello  ") == 5
