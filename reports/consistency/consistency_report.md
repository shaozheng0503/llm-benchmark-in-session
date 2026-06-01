# MiniMax-M3 一致性测试报告（文件分析）

- 时间：2026-06-01T15:02:49
- ans_dir：/Users/huangshaozheng/Desktop/minimax/minimax-m3-benchmark/raw_answers

| ID | 类别 | 样本 | 聚类 | 主答案占比 | 熵 | 一致性 | 备注 |
|----|------|------|------|------------|----|--------|------|
| `smoke_identity` | smoke | 1 | - | -% | - | — | single sample; need ≥2 variants to assess |
| `smoke_bilingual` | smoke | 1 | - | -% | - | — | single sample; need ≥2 variants to assess |
| `structured_extraction` | core | 1 | - | -% | - | — | single sample; need ≥2 variants to assess |
| `long_summary` | core | 1 | - | -% | - | — | single sample; need ≥2 variants to assess |
| `logic_reasoning` | complex | 1 | - | -% | - | — | single sample; need ≥2 variants to assess |
| `math_integral` | complex | 1 | - | -% | - | — | single sample; need ≥2 variants to assess |
| `code_generation` | complex | 1 | - | -% | - | — | single sample; need ≥2 variants to assess |
| `multi_turn_context` | complex | 1 | - | -% | - | — | single sample; need ≥2 variants to assess |
| `prompt_injection` | safety | 1 | - | -% | - | — | single sample; need ≥2 variants to assess |
| `tool_use_planning` | boundary | 1 | - | -% | - | — | single sample; need ≥2 variants to assess |
| `code_review` | complex | 1 | - | -% | - | — | single sample; need ≥2 variants to assess |
| `emoji_robustness` | boundary | 1 | - | -% | - | — | single sample; need ≥2 variants to assess |
| `bayesian_probability` | complex | 1 | - | -% | - | — | single sample; need ≥2 variants to assess |
| `unauthorized_tool` | safety | 1 | - | -% | - | — | single sample; need ≥2 variants to assess |
| `indirect_injection` | safety | 1 | - | -% | - | — | single sample; need ≥2 variants to assess |
| `needle_haystack` | complex | 1 | - | -% | - | — | single sample; need ≥2 variants to assess |
| `style_transfer` | complex | 1 | - | -% | - | — | single sample; need ≥2 variants to assess |
| `find_secrets` | real_task | 1 | - | -% | - | — | single sample; need ≥2 variants to assess |
| `debug_incident` | real_task | 1 | - | -% | - | — | single sample; need ≥2 variants to assess |
| `user_complaint` | real_task | 1 | - | -% | - | — | single sample; need ≥2 variants to assess |
| `classical_chinese` | multilingual | 1 | - | -% | - | — | single sample; need ≥2 variants to assess |
| `japanese_reading` | multilingual | 1 | - | -% | - | — | single sample; need ≥2 variants to assess |
| `calibration` | complex | 1 | - | -% | - | — | single sample; need ≥2 variants to assess |

## 解读
- **consistency_score** = 主答案占全部样本的比例。1.0 表示所有样本答案一致。
- **entropy** 越高，答案越分散（0=所有答案相同）。
- 主答案样本：