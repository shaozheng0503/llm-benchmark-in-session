"""测试 injection_gradient 的扰动函数。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from injection_gradient import (
    add_prefix, add_suffix, add_multilang, add_typos, add_indirect, encode_base64,
    GRADIENT_LEVELS,
)


SAMPLE = "What is 2+2?"


def test_add_prefix_appends():
    out = add_prefix(SAMPLE)
    assert out != SAMPLE
    assert "What is 2+2?" in out


def test_add_suffix_appends():
    out = add_suffix(SAMPLE)
    assert out != SAMPLE
    assert "What is 2+2?" in out


def test_add_multilang_contains_marker():
    out = add_multilang(SAMPLE)
    # 检查中英日混排特征
    assert "Aside in English" in out
    assert "Aside en japonais" in out
    assert "Aside" in out


def test_add_indirect_contains_url():
    out = add_indirect(SAMPLE)
    assert "http" in out


def test_encode_base64_decodable():
    out = encode_base64(SAMPLE)
    import base64, re
    m = re.search(r"^[A-Za-z0-9+/=\s]+$", out, re.MULTILINE)
    assert m is not None
    decoded = base64.b64decode(m.group(0).strip()).decode("utf-8")
    assert decoded == SAMPLE


def test_add_typos_rate_zero():
    """rate=0 时不应改任何字符。"""
    out = add_typos(SAMPLE, rate=0.0)
    assert out == SAMPLE


def test_gradient_levels_complete():
    """5 档必须都有。"""
    assert set(GRADIENT_LEVELS.keys()) == {
        "L0_baseline", "L1_simple", "L2_obfuscated", "L3_multilang", "L4_indirect"
    }
