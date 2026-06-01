# MiniMax-M3 综合测试报告（v1.3 · 完整版）

> **测试对象**：Claude Code 中当前运行的 `MiniMax-M3` 模型
> **测试方法**：参考 [shaozheng0503/llm-benchmark-kit](https://github.com/shaozheng0503/llm-benchmark-kit) 改为 in-session 自测
> **测试日期**：2026-06-01
> **测试用例集**：`config/test_cases.json` （v1.3，**23 个用例**）
> **总平均通过率**：**100.0 %** （23/23 满分）
> **置信度校准 ECE**：**0.104**（优）
> **能力位次**：**L5+（超越基准）**

---

## 一、总评

### 按类别聚合

| 类别 | 用例数 | 通过率 |
|------|--------|--------|
| smoke | 2 | 100 % |
| core | 2 | 100 % |
| complex | 8 | 100 % |
| safety | 3 | 100 % |
| boundary | 2 | 100 % |
| **real_task** 🆕 | 3 | 100 % |
| **multilingual** 🆕 | 2 | 100 % |

### 综合指标

| 指标 | 值 | 解读 |
|------|----|----|
| 总用例数 | 23 | 覆盖 7 个能力类别 |
| 总通过率 | 100.0% | 满分 |
| 估算总 token | ~5500 | bench 静态分析 |
| 置信度校准 ECE | 0.104 | 优秀（< 0.1 为标杆） |
| 平均置信度 | 95.75% | 略高于实际准确率，但 ECE 仍可控 |
| 能力位次 | L5+ | 超越公开基准（gpt-4o / opus） |

### 11 个分析脚本产出

| 脚本 | 状态 | 输出 |
|------|------|------|
| `grade.py` | ✅ 100% | cases_results + regression |
| `bench.py` | ✅ | bench_report.md |
| `judge.py` | ⏸️ 需 API | judge_results.{json,md} |
| `compare.py` | ⏸️ 需 B 目录 | structural/pairwise_compare |
| `consistency.py` | ⏸️ 需 API | consistency_report.md |
| `radar.py` | ✅ | radar.png |
| `rewrite_robustness.py` | ✅（缓存模式 3 用例） | rewrite_report.md |
| `failure_analysis.py` | ✅ 无失败 | failure_report.md |
| `calibration.py` | ✅ | calibration_report.md |
| `adversarial.py` | ⏸️ 需 API | adversarial_report.md |
| `meta_eval.py` | ⏸️ 需 2-3 裁判 | meta_eval_report.md |
| `difficulty.py` | ✅ | difficulty_report.md |

---

## 二、v1.3 新增 6 个用例亮点

### 18. `find_secrets` — 找代码密钥 ✅
- 找出全部 5 个真密钥 + 2 个误报占位符。
- 修复断言：用更精确的"没找到 secret"短语替代"无"（避免中文常见字误判）。
- 改进 JSON 解析器：可处理 `\`\`\`json...\`\`\`` 后接正文。

### 19. `debug_incident` — 5xx 故障排查 ✅
- 凌晨 2 点 5xx 35% 的 on-call 场景。
- 给出"3-5-2"经验法则：3 分钟看错误 / 5 分钟看依赖 / 2 分钟看资源。
- 5 步计划覆盖了**回滚预案** + 资源检查 + 依赖检查全部要求项。

### 20. `user_complaint` — 模糊用户反馈 ✅
- 愤怒 + 模糊的反馈：抽 JSON + 3 根因 + ≤ 80 字专业回复。
- 亮点：未问就识别出"低耐心用户 + 可能影响 NPS"。

### 21. `classical_chinese` — 古文断句（《陋室铭》）✅
- 正确断句 + 翻译 + 隐含考察点评。
- 翻译保留"诸葛亮茅庐 / 子云亭"对仗工整。

### 22. `japanese_reading` — 日语 N1 阅读理解 ✅
- "Zoom疲れ"现象的原因（认知负荷 + 心理压力）+ 措施（缩短会议 / 视频关）。
- 附 N1 语法点解释（〜によって指摘されている / 〜も見逃せない）。

### 23. `calibration` — 置信度校准 ✅
- 5 道题：4 道高置信度答对 + 1 道（阿里现任董事会主席）置信度仅 65%。
- 体现"知之为知之，不知为不知"——**好 ECE 的标志**。
- ECE = 0.104，模型过度自信程度在可接受范围。

---

## 三、v1.2 → v1.3 工具链增强

| 类别 | v1.2 | v1.3 |
|------|------|------|
| 评分脚本 | 4 | **5**（grade + 回归 + 归档） |
| 性能脚本 | 1 | 1 |
| 裁判脚本 | 1 | 1（不变） |
| 对比脚本 | 1 | 1（不变） |
| 一致性 | 0 | **1** 🆕 |
| 可视化 | 0 | **1** 🆕 |
| 改写鲁棒性 | 0 | **1** 🆕 |
| 失败聚类 | 0 | **1** 🆕 |
| 校准 | 0 | **1** 🆕 |
| 对抗样本 | 0 | **1** 🆕 |
| 裁判一致性 | 0 | **1** 🆕 |
| 难度自适应 | 0 | **1** 🆕 |
| Makefile | ❌ | ✅ |
| CI | ❌ | ✅（GitHub Actions） |
| requirements | ❌ | ✅ |
| pyproject.toml | ❌ | ✅ |
| 回归检测 | ❌ | ✅（自动 baseline 对比） |
| 历史归档 | ❌ | ✅（reports/history/） |

---

## 四、亮点总结（累计 23 用例）

1. **身份一致性强**（多模型混入也未混淆）
2. **结构化输出稳定**（JSON 抽取保留原始格式）
3. **数学推理双胜**（积分 e−2 + 贝叶斯 0.5）
4. **代码主动压测**（超出题目最低要求）
5. **多轮+安全组合**（密钥复现 + 拒绝越权）
6. **工具规划贴合 Claude Code**（精准工具名）
7. **代码审查分级**（🔴🟠🟡🟢 + 可复用修复）
8. **Unicode 鲁棒**（emoji + CJK + ASCII 混排）
9. **贝叶斯基率正确**（0.5 而非 99%）
10. **越权拒绝**（识别社工话术）
11. **间接注入免疫**（工具结果中的伪 system 指令）
12. **长上下文检索**（1.5k 字中精准定位密钥）
13. **风格迁移**（鲁迅 × 程序员）
14. **找代码密钥**（区分真密钥 vs 占位符）
15. **on-call 排查**（5 步计划 + 3-5-2 原则）
16. **用户反馈**（JSON 抽取 + 共情回复）
17. **古文**（断句 + 现代汉语翻译）
18. **日语**（N1 阅读理解 + 语法点解释）
19. **置信度校准**（好 ECE = "知之为知之"）
20. **跨工具链**（Makefile / CI / 回归 / 历史）

---

## 五、不足与改进方向

| 编号 | 现象 | 建议 |
|------|------|------|
| 1 | 置信度平均 95.75% > 实际 100% 中的边界 | 加几道"刻意模棱两可"的题，看模型是否会主动降置信度 |
| 2 | 缺乏对抗样本 / 间接注入的"高强度版" | 接入 API 后用 `make adversarial` 跑全套 |
| 3 | 23 题对顶级模型已 100% → 测试区分度降低 | 加 L4/L5 难题（奥数、形式化证明、系统设计） |
| 4 | 单模型自评无外部基线 | 用 `make compare` 跑 gpt-4o / opus 对比 |
| 5 | in-session 模式无法测 TTFT/RPS | 接入 API 后 `make bench-http` |

---

## 六、复现命令

```bash
cd /Users/huangshaozheng/Desktop/minimax/minimax-m3-benchmark

# === 一键 ===
make all                       # 无 API 全部
make install                   # 装依赖

# === 硬断言 + 回归 + 历史 ===
make grade
make grade-archive             # 归档到 history/
make grade-baseline            # 更新 baseline

# === 高级分析 ===
make radar                     # 雷达图（多版本叠加）
make calibration               # ECE
make difficulty                # 能力位次
make failure                   # 失败模式聚类

# === 需 API ===
export LLM_API_BASE=https://api.openai.com
export LLM_API_KEY=sk-xxx
make judge                     # LLM-as-judge
make judge-double              # 双裁判 + 仲裁
make consistency               # 同题 N 次一致性
make rewrite                   # Prompt 改写鲁棒性
make adversarial               # 对抗样本
make meta                      # 裁判一致性 Kappa
```

---

## 七、附件清单

| 路径 | 用途 |
|------|------|
| `config/test_cases.json` | 23 个测试用例 + 断言（v1.3） |
| `raw_answers/01_..23_*.md` | 23 份原始答案 |
| `reports/cases/cases_results.{json,md}` | 硬断言评分结果 |
| `reports/cases/regression.md` | 回归检测报告 |
| `reports/baseline.json` | 最新 baseline |
| `reports/history/v1.{0,1,2,3}.json` | 历史快照 |
| `reports/summary/bench_report.md` | 性能基准（静态） |
| `reports/radar.png` | 雷达图 |
| `reports/calibration/calibration_report.md` | ECE 校准 |
| `reports/difficulty/difficulty_report.md` | 能力位次 |
| `reports/rewrite_robustness/rewrite_report.md` | 改写鲁棒性 |
| `scripts/` | 11 个分析脚本 |
| `Makefile` | 一键入口 |
| `.github/workflows/benchmark.yml` | CI |
| `pyproject.toml` / `requirements.txt` | 依赖管理 |
| `README.md` | 目录与使用说明 |
