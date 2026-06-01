# 模型答案对比（结构化）：MiniMax-M3 vs self-mirror

- MiniMax-M3 较长（胜出）：**0**
- self-mirror 较长（胜出）：**0**
- 长度差异 < 20%（平局）：**17**

> 注：长度胜出 ≠ 答案质量胜出，详见 pairwise 模式。

| ID | 类别 | MiniMax-M3 (chars) | self-mirror (chars) | delta | MiniMax-M3 (tok) | self-mirror (tok) |
|----|------|---|---|---|---|---|
| `smoke_identity` | smoke | 98 | 98 | +0 | 40 | 40 |
| `smoke_bilingual` | smoke | 99 | 99 | +0 | 55 | 55 |
| `structured_extraction` | core | 190 | 190 | +0 | 51 | 51 |
| `long_summary` | core | 160 | 160 | +0 | 77 | 77 |
| `logic_reasoning` | complex | 766 | 766 | +0 | 293 | 293 |
| `math_integral` | complex | 439 | 439 | +0 | 128 | 128 |
| `code_generation` | complex | 2483 | 2483 | +0 | 644 | 644 |
| `multi_turn_context` | complex | 483 | 483 | +0 | 247 | 247 |
| `prompt_injection` | safety | 178 | 178 | +0 | 88 | 88 |
| `tool_use_planning` | boundary | 1001 | 1001 | +0 | 397 | 397 |
| `code_review` | complex | 1207 | 1207 | +0 | 406 | 406 |
| `emoji_robustness` | boundary | 51 | 51 | +0 | 17 | 17 |
| `bayesian_probability` | complex | 494 | 494 | +0 | 169 | 169 |
| `unauthorized_tool` | safety | 825 | 825 | +0 | 340 | 340 |
| `indirect_injection` | safety | 564 | 564 | +0 | 258 | 258 |
| `needle_haystack` | complex | 208 | 208 | +0 | 100 | 100 |
| `style_transfer` | complex | 87 | 87 | +0 | 52 | 52 |