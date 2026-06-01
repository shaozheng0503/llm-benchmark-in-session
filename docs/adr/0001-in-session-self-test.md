# ADR-0001: 为什么不直接用原版 llm-benchmark-kit？

## 状态

2026-06-01 已采纳

## 背景

[shaozheng0503/llm-benchmark-kit](https://github.com/shaozheng0503/llm-benchmark-kit)
是 OpenAI 兼容 HTTP 网关的全景测试套件，结构清晰、功能完整。

但 **MiniMax-M3 当前仅在 Claude Code 内部署**，没有公网 API endpoint。

## 决策

**改为 in-session 自测**：

- 让被测模型（即当前 Claude Code 中的 assistant）直接回答测试题
- 用同样的断言（但比原版更强：17 类）
- 跳过 `discover_models` / `run_stress` / `run_authenticity` 跨厂商部分
- 自写 11 个分析脚本扩展能力

## 后果

### 正面

- 零外部依赖即可跑
- 跑通后未来 API 可用时无缝接回
- 沉淀了 11 个原创分析脚本（calibration / radar / leaderboard 等）

### 负面

- **无法测 TTFT / RPS / P99**（in-session 模式无 HTTP）
- 缺乏跨厂商反查（无法验证是哪个模型在跑）
- 单 session 内"自见"偏差（已通过伪装为用户提问降低）

## 备选方案

| 方案 | 优劣 |
|------|------|
| 等 MiniMax-M3 提供 API | 时间未知；可能 6+ 个月 |
| 用 AWS Bedrock / Azure 转一道 | 增加成本 + 跳数 |
| 用代理工具（如 LiteLLM） | 仍需 API 凭证 |

## 退出条件

当 MiniMax-M3 提供公开 API 时，**接回原版 kit 跑 `make full`**，再用本项目的
`bench.py --http` / `judge.py` / `compare.py` 补强。
