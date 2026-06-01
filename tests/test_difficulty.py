"""测试 difficulty.py 的能力位次映射。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from difficulty import tier_for, model_tier


def test_tier_l5():
    """高分对应 L5+。"""
    name, th = tier_for(100)
    assert name.startswith("L5")


def test_tier_l0():
    """低分对应 L0。"""
    name, _ = tier_for(20)
    assert name == "L0-基础"


def test_tier_middle():
    """中等分对应中档。"""
    name, _ = tier_for(75)
    assert name == "L2-中级"


def test_model_tier_thresholds():
    assert model_tier(30).startswith("L0")
    assert model_tier(60).startswith("L2")
    assert model_tier(85).startswith("L4")
    assert model_tier(99).startswith("L5")
