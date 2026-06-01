# ADR-0002: 17 类断言设计

## 状态

2026-06-01 已采纳

## 背景

原版 kit 只支持 6 类硬断言（`min_length` / `should_include_*` / `should_not_include_*` /
`json_*`）。当遇到复杂场景（如安全语义级检测）时不够用。

## 决策

扩展为 17 类断言：

| 类别 | 断言 |
|------|------|
| 长度 | `min_length` / `max_length` |
| 子串 | `should_include_any` / `_all` / `should_not_include_any` |
| 正则 | `regex_match` / `regex_not_match` |
| 起止 | `starts_with` / `ends_with` |
| 数字 | `number_in_range` |
| JSON | `json_required` / `json_keys` / `json_value_equals` / `json_value_in` |
| 安全 | `safety_no_real_leak`（语义级 + allow_phrases） |

## 关键设计：safety_no_real_leak

**问题**：v1.0 的 `should_not_include_any: ["训练数据"]` 会误判——模型在解释攻击者注入
时会提及这个词字面内容。

**解决**：用 `must_not_contain_phrases`（真正泄露）+ `allow_phrases`（上下文例外）。
只有当"敏感短语"出现且**不在** allow_phrases 上下文中，才计为失败。

## 备选

| 方案 | 优劣 |
|------|------|
| 用 LLM 评判每条安全 | 慢 + 引入裁判偏差 |
| 用 NLI 模型检测蕴含 | 复杂 + 重 |
| `safety_no_real_leak`（本方案） | 快 + 透明 + 易调试 |

## 退出条件

如未来要测更精细的安全维度（越狱、间接注入、社工），可加：
- `jailbreak_resistance`
- `indirect_injection_score`
- `social_engineering_detected`
