凌晨 2 点告警排查，5 步计划（从快→慢、从最可能→最不可能）：

- **步骤 1：看 5xx 错误的最近 15 分钟日志**（Grafana → Logs / Kibana）
  - 工具：`Bash kubectl logs -n prod -l app=orders --since=15m | grep -E "5[0-9]{2}|ERROR|Exception"`
  - 看什么：是某一类异常（DB timeout / OOM / 第三方 API 503）还是随机分布。
  - 预期耗时：1-2 分钟。

- **步骤 2：检查依赖项健康**（最快定位"是不是被上游拖垮"）
  - 工具：`curl -m 3 <db_host>:5432`、`curl -m 3 <redis>:6379/ping`、看 APM（Datadog/SkyWalking）的上游调用链。
  - 看什么：DB 连接数、Redis 命中率、第三方 API 错误率。
  - 如果 DB 连接池打满 → 立刻按"扩连接池 + 重启服务"二选一。

- **步骤 3：检查资源水位**（CPU / 内存 / 连接池 / 队列）
  - 工具：Prometheus 指标（`container_cpu_usage_seconds_total`, `jvm_memory_used_bytes`, `pg_stat_activity_count`）。
  - 看什么：是不是某个实例 OOM 被重启、是不是连接池耗尽、是不是磁盘写满。
  - 如果是 OOM → 抓 heap dump；如果是连接池 → 改 max_pool_size + 看是否有连接泄漏。

- **步骤 4：检查最近 30 分钟的发布/配置变更**
  - 工具：`kubectl rollout history` / ArgoCD / GitHub Actions 部署历史。
  - 看什么：是不是有发版？是不是改了 configmap？是不是改了数据库迁移？
  - 如果有变更 → **触发回滚预案**：回滚到上一个稳定版本。

- **步骤 5：进入回滚预案**（当 1-4 在 10 分钟内没定位时）
  - 工具：`kubectl rollout undo deployment/orders --to-revision=<last_good>`。
  - 同步：在 #incident 频道同步状态，每 5 分钟更新一次进展。
  - 回滚后 5xx 应在 2 分钟内回到基线；若不回滚无效 → 升级到事件经理 + 拉架构师会诊。

**同时做的事**（不阻塞排查）：
- 在 Confluence / incident.io 写实时时间线（5xx 起点、调查动作、缓解动作）。
- 5 分钟内同步到管理层（用预设的告警模板）。
- 排查完后 24 小时内出 RCA 报告。

**经验法则**：3-5-2 原则——3 分钟看错误、5 分钟看依赖、2 分钟看资源，剩下时间看变更。
