# MiniMax-M3 性能基准（静态分析）

- 样本数：23
- 总字符数：14044
- 估算总 token 数：5241
- 平均 token/答案：227.9

| 文件 | 字符 | CJK | ASCII | 估算 token |
|------|------|-----|-------|-----------|
| `01_smoke_identity.md` | 98 | 38 | 60 | 40 |
| `02_smoke_bilingual.md` | 99 | 72 | 27 | 55 |
| `03_structured_extraction.md` | 190 | 8 | 182 | 51 |
| `04_long_summary.md` | 160 | 89 | 71 | 77 |
| `05_logic_reasoning.md` | 766 | 244 | 522 | 293 |
| `06_math_integral.md` | 439 | 43 | 396 | 128 |
| `07_code_generation.md` | 2483 | 55 | 2428 | 644 |
| `08_multi_turn_context.md` | 483 | 304 | 179 | 247 |
| `09_prompt_injection.md` | 178 | 104 | 74 | 88 |
| `10_tool_use_planning.md` | 1001 | 353 | 648 | 397 |
| `11_code_review.md` | 1207 | 251 | 956 | 406 |
| `12_emoji_robustness.md` | 51 | 11 | 40 | 17 |
| `13_bayesian_probability.md` | 494 | 110 | 384 | 169 |
| `14_unauthorized_tool.md` | 825 | 320 | 505 | 340 |
| `15_indirect_injection.md` | 564 | 280 | 284 | 258 |
| `16_needle_haystack.md` | 208 | 114 | 94 | 100 |
| `17_style_transfer.md` | 87 | 73 | 14 | 52 |
| `18_find_secrets.md` | 1089 | 243 | 846 | 374 |
| `19_debug_incident.md` | 1281 | 407 | 874 | 490 |
| `20_user_complaint.md` | 533 | 232 | 301 | 230 |
| `21_classical_chinese.md` | 436 | 339 | 97 | 250 |
| `22_japanese_reading.md` | 475 | 173 | 302 | 191 |
| `23_calibration.md` | 897 | 287 | 610 | 344 |

> 注：这是**字符/token 密度分析**，不包含真实延迟。
> 真实延迟请用 `--http` 模式（在 API 可用时）或 `--times` 模式手动记录。