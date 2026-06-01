#!/usr/bin/env python3
"""
minimax-m3-benchmark · dashboard.py

Streamlit 一页可视化仪表板。

用法：
    streamlit run scripts/dashboard.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

st.set_page_config(
    page_title="MiniMax-M3 Benchmark",
    page_icon="🧪",
    layout="wide",
)


def load_json(path: Path):
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return None


def list_versions() -> list[Path]:
    hist = ROOT / "reports" / "history"
    if not hist.exists():
        return []
    return sorted(hist.glob("v*.json"))


# ============== Sidebar ==============
st.sidebar.title("🧪 MiniMax-M3 Benchmark")
st.sidebar.markdown("参考 [llm-benchmark-kit](https://github.com/shaozheng0503/llm-benchmark-kit)")

versions = list_versions()
all_data: dict[str, dict] = {"current": load_json(ROOT / "reports/cases/cases_results.json")}
for v in versions:
    all_data[v.stem] = load_json(v)

sel = st.sidebar.selectbox("选择版本", list(all_data.keys()),
                            index=len(all_data) - 1)
data = all_data.get(sel) or {}

# ============== Header ==============
st.title("📊 MiniMax-M3 综合测试仪表板")
if data:
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("总分", f"{data.get('overall_pct', 0)}%")
    col2.metric("用例数", data.get("n_cases", 0))
    n_graded = data.get("n_graded", data.get("n_cases", 0))
    col3.metric("已评分", n_graded)

    cal = load_json(ROOT / "reports/calibration/calibration_report.md")
    # 简单正则提取 ECE
    if cal:
        import re
        m = re.search(r"ECE = ([\d.]+)", cal if isinstance(cal, str) else "")
    else:
        m = None
    col4.metric("ECE", m.group(1) if m else "—")

    diff = load_json(ROOT / "reports/difficulty/difficulty_report.md")
    if diff:
        m2 = re.search(r"能力位次评估：(.+)", diff if isinstance(diff, str) else "")
    else:
        m2 = None
    col5.metric("能力位次", m2.group(1)[:8] if m2 else "—")

st.markdown("---")

# ============== Main panels ==============
if data and data.get("results"):
    # === 用例得分表 ===
    st.subheader("📋 各用例得分")
    rows = []
    for r in data["results"]:
        rows.append({
            "ID": r.get("id"),
            "类别": r.get("category"),
            "名称": r.get("name"),
            "得分": f"{r.get('pct', 0)}%",
            "字符数": r.get("answer_chars", 0),
        })
    st.dataframe(rows, use_container_width=True, height=400)

    # === 类别分布（matplotlib） ===
    st.subheader("📈 类别分布")
    import matplotlib.pyplot as plt
    by_cat: dict[str, list[float]] = {}
    for r in data["results"]:
        if r.get("error"):
            continue
        by_cat.setdefault(r["category"], []).append(r.get("pct", 0))

    fig, ax = plt.subplots(figsize=(8, 4))
    cats = sorted(by_cat.keys())
    avgs = [sum(by_cat[c]) / len(by_cat[c]) for c in cats]
    ax.barh(cats, avgs, color="steelblue", alpha=0.8)
    ax.set_xlim(0, 105)
    ax.set_xlabel("通过率 (%)")
    ax.set_title("各能力类别平均通过率")
    for i, v in enumerate(avgs):
        ax.text(v + 1, i, f"{v:.1f}%", va="center", fontsize=9)
    st.pyplot(fig)
    plt.close(fig)

# ============== 历史趋势 ==============
st.markdown("---")
st.subheader("📉 历史趋势（多版本）")
trend = []
for vname, vdata in all_data.items():
    if vdata and vdata.get("overall_pct") is not None:
        trend.append({
            "版本": vname,
            "总分": vdata["overall_pct"],
            "用例数": vdata.get("n_cases", 0),
        })
if len(trend) >= 2:
    import pandas as pd
    df = pd.DataFrame(trend)
    st.line_chart(df.set_index("版本")["总分"])
    st.dataframe(df, use_container_width=True)
else:
    st.info("需要至少 2 个历史快照才能显示趋势")

# ============== 报告索引 ==============
st.markdown("---")
st.subheader("📁 报告索引")
reports_dir = ROOT / "reports"
if reports_dir.exists():
    for sub in sorted(reports_dir.iterdir()):
        if sub.is_dir():
            files = sorted(sub.glob("*"))
            with st.expander(f"📂 reports/{sub.name}  ({len(files)} files)"):
                for f in files[:10]:
                    st.markdown(f"- `{f.relative_to(ROOT)}` ({f.stat().st_size} B)")
                if len(files) > 10:
                    st.markdown(f"- ... 还有 {len(files) - 10} 个文件")
