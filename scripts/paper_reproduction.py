#!/usr/bin/env python3
"""
minimax-m3-benchmark · paper_reproduction.py

论文复现测试：5 篇经典 ML 论文摘要 → 写核心算法 + 关键公式。
LLM-as-judge 评分：与原论文对比结构准确度。

用法：
    LLM_API_BASE=... LLM_API_KEY=... python3 scripts/paper_reproduction.py \\
        --judge-model gpt-4o
"""
from __future__ import annotations

import argparse
import json
import os
import re
import statistics
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "reports" / "paper_repro"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# 5 篇经典论文（摘要 + ground truth 关键元素）
PAPERS = [
    {
        "id": "attention_is_all_you_need",
        "title": "Attention Is All You Need (Transformer, 2017)",
        "abstract": "The dominant sequence transduction models are based on complex recurrent or "
                    "convolutional neural networks. We propose a new simple network architecture, "
                    "the Transformer, based solely on attention mechanisms, dispensing with recurrence "
                    "and convolutions entirely.",
        "must_have": ["self-attention", "Q", "K", "V", "scaled dot-product",
                       "multi-head", "softmax", "残差", "LayerNorm", "位置编码"],
        "ground_truth_pseudocode": """
def transformer(x):
    x = embedding(x) + positional_encoding(x.shape[1])
    for layer in layers:
        x = x + self_attention(layer_norm(x))
        x = x + ffn(layer_norm(x))
    return softmax(x)
""",
    },
    {
        "id": "deep_residual",
        "title": "Deep Residual Learning (ResNet, 2015)",
        "abstract": "Deeper neural networks are more difficult to train. We present a residual "
                    "learning framework to ease the training of networks that are substantially "
                    "deeper than those used previously.",
        "must_have": ["残差", "shortcut", "identity", "y = F(x) + x", "梯度",
                       "网络深度", "ImageNet", "skip connection"],
        "ground_truth_pseudocode": """
def res_block(x):
    residual = x
    x = conv(x); x = bn(x); x = relu(x)
    x = conv(x); x = bn(x)
    return relu(x + residual)
""",
    },
    {
        "id": "gan",
        "title": "Generative Adversarial Networks (GAN, 2014)",
        "abstract": "We propose a new framework for estimating generative models via an "
                    "adversarial process, in which we simultaneously train two models: a "
                    "generative model G and a discriminative model D.",
        "must_have": ["生成器", "判别器", "G", "D", "minimax", "对抗",
                       "真假样本", "min max log", "零和博弈"],
        "ground_truth_pseudocode": """
# min_G max_D V(D, G) = E[log D(x)] + E[log(1 - D(G(z)))]
""",
    },
    {
        "id": "bert",
        "title": "BERT: Pre-training of Deep Bidirectional Transformers (2018)",
        "abstract": "We introduce a new language representation model called BERT, which stands "
                    "for Bidirectional Encoder Representations from Transformers. BERT is designed "
                    "to pre-train deep bidirectional representations from unlabeled text.",
        "must_have": ["双向", "MLM", "masked language model", "NSP", "next sentence",
                       "encoder", "Transformer", "[CLS]", "[SEP]"],
        "ground_truth_pseudocode": """
def bert_pretrain(text):
    tokens = tokenize_with_mask(text)  # 15% masked
    return mlm_head(encoder(tokens)), nsp_head(pool(encoder(tokens)))
""",
    },
    {
        "id": "rmsnorm",
        "title": "RMSNorm (2019, LLaMA 关键组件)",
        "abstract": "We present Root Mean Square Layer Normalization (RMSNorm), a simple and "
                    "efficient alternative to Layer Normalization. RMSNorm regularizes the summed "
                    "inputs to a neuron according to the root mean square (RMS).",
        "must_have": ["RMS", "均方根", "无均值中心化", "可学习缩放", "gamma",
                       "LayerNorm", "效率", "LLaMA"],
        "ground_truth_pseudocode": """
def rms_norm(x, gamma):
    return x / sqrt(mean(x**2) + eps) * gamma
""",
    },
]


def call_chat(base, key, model, prompt, timeout=60.0, temperature=0.0):
    body = json.dumps({
        "model": model, "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
    }).encode("utf-8")
    req = urllib.request.Request(f"{base.rstrip('/')}/v1/chat/completions", data=body, headers={
        "Content-Type": "application/json", "Authorization": f"Bearer {key}",
    })
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))["choices"][0]["message"]["content"]


JUDGE_PROMPT = """你是一名 ML 学术评审。比较模型复现与原论文的差距：

【原论文摘要】{abstract}
【原论文关键伪代码】
{ground_truth}

【模型复现】
{reproduction}

请从 3 维独立评分（各 1-5）：
- accuracy（核心算法是否正确）
- completeness（关键元素是否覆盖）
- clarity（表达是否清晰）

**严格 JSON**：
{{"accuracy": <1-5>, "completeness": <1-5>, "clarity": <1-5>, "rationale": "≤60字"}}
"""


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    p.add_argument("--target-model", default=os.environ.get("MODEL", "gpt-4o-mini"))
    p.add_argument("--judge-model", default=os.environ.get("JUDGE_MODEL", "gpt-4o"))
    p.add_argument("--base", default=os.environ.get("LLM_API_BASE", ""))
    p.add_argument("--key", default=os.environ.get("LLM_API_KEY", ""))
    p.add_argument("--timeout", type=float, default=60.0)
    p.add_argument("--out", type=Path, default=OUT_DIR / "paper_repro_report.md")
    args = p.parse_args()

    if not (args.base and args.key):
        print("ERROR: 需 --base/--key", file=sys.stderr)
        return 2

    rows = []
    for paper in PAPERS:
        print(f"复现 {paper['title']}...")
        prompt = f"""请基于以下论文摘要，复现其核心算法：写出关键公式 + 简短伪代码（≤ 30 行）+ 关键概念列表（不超过 8 项）。

【论文标题】{paper['title']}
【论文摘要】{paper['abstract']}

要求：聚焦算法本质，不要展开背景介绍。"""
        try:
            repro = call_chat(args.base, args.key, args.target_model, prompt, args.timeout)
        except Exception as e:
            repro = f"ERROR: {e}"

        # 关键词命中
        hits = [k for k in paper["must_have"] if k in repro]
        kw_coverage = len(hits) / len(paper["must_have"])

        # LLM-as-judge 评分
        try:
            judge_user = JUDGE_PROMPT.format(
                abstract=paper["abstract"],
                ground_truth=paper["ground_truth_pseudocode"],
                reproduction=repro,
            )
            judge_resp = call_chat(args.base, args.key, args.judge_model, judge_user, args.timeout)
            m = re.search(r"\{.*\}", judge_resp, re.DOTALL)
            scores = json.loads(m.group(0)) if m else {"accuracy": 3, "completeness": 3, "clarity": 3}
        except Exception as e:
            scores = {"accuracy": 0, "completeness": 0, "clarity": 0, "rationale": f"judge error: {e}"}

        rows.append({
            "paper": paper, "reproduction": repro[:300],
            "kw_hits": hits, "kw_coverage": kw_coverage,
            "scores": scores,
        })
        avg = statistics.mean([scores.get(k, 0) for k in ("accuracy", "completeness", "clarity")])
        print(f"  → kw {kw_coverage*100:.0f}%, judge avg {avg:.1f}/5")

    if not rows:
        return 0

    avg_kw = statistics.mean(r["kw_coverage"] for r in rows)
    avg_acc = statistics.mean(r["scores"].get("accuracy", 0) for r in rows)
    avg_comp = statistics.mean(r["scores"].get("completeness", 0) for r in rows)
    avg_clar = statistics.mean(r["scores"].get("clarity", 0) for r in rows)

    lines = [
        "# 论文复现测试\n",
        f"- 目标模型：`{args.target_model}`",
        f"- 裁判：`{args.judge_model}`",
        f"- 论文数：{len(rows)}\n",
        "## 总分\n",
        f"- 平均关键词覆盖：**{avg_kw*100:.0f}%**",
        f"- 平均 accuracy：{avg_acc:.1f}/5",
        f"- 平均 completeness：{avg_comp:.1f}/5",
        f"- 平均 clarity：{avg_clar:.1f}/5\n",
        "## 逐篇\n",
        "| 论文 | 关键词覆盖 | accuracy | completeness | clarity |",
        "|------|------------|----------|--------------|---------|",
    ]
    for r in rows:
        s = r["scores"]
        lines.append(
            f"| {r['paper']['id']} | {r['kw_coverage']*100:.0f}% "
            f"| {s.get('accuracy','-')} | {s.get('completeness','-')} "
            f"| {s.get('clarity','-')} |"
        )

    # 详情
    lines.append("\n## 复现摘要\n")
    for r in rows:
        lines.append(f"### {r['paper']['title']}")
        lines.append(f"**关键词命中**：{', '.join(r['kw_hits'])}")
        lines.append(f"**复现**：{r['reproduction']}…")
        lines.append("")

    args.out.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
