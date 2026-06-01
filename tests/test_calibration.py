"""测试 calibration.py 的 ECE 计算。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from calibration import ece


def test_ece_perfect():
    """全对且高置信度 → ECE 很低。"""
    probs = [99, 95, 90, 80]
    correct = [True, True, True, True]
    assert ece(probs, correct) < 0.1


def test_ece_overconfident():
    """高置信度但答错 → ECE 高。"""
    probs = [99, 95, 90, 80]
    correct = [False, False, False, False]
    assert ece(probs, correct) > 0.5


def test_ece_perfect_calibration():
    """完美校准：99% 置信度对应 99% 准确率。"""
    # 构造：20 道题 19 答对 1 答错，置信度都 95%
    probs = [95] * 20
    correct = [True] * 19 + [False]
    val = ece(probs, correct, n_bins=10)
    # 期望 ~|0.95 - 0.95| = 0 + 0.05 bin 偏移 ≈ 0.0025
    assert val < 0.05


def test_ece_empty():
    assert ece([], []) == 0.0


def test_ece_handles_normalized_input():
    """0-1 输入和 0-100 输入等价。"""
    probs_100 = [80, 60]
    probs_1 = [0.8, 0.6]
    correct = [True, False]
    assert ece(probs_100, correct) == ece(probs_1, correct)
