# MiniMax-M3 性能基准（静态分析）

- 样本数：12
- 总字符数：7155
- 估算总 token 数：2443
- 平均 token/答案：203.6

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

> 注：这是**字符/token 密度分析**，不包含真实延迟。
> 真实延迟请用 `--http` 模式（在 API 可用时）或 `--times` 模式手动记录。