# 回归候选选择参考

## 允许进入回归候选的条件

只有至少命中一个当前范围信号，才允许写入 `regression_candidates`：

- 当前模块命中。
- 当前接口命中。
- 当前状态流转命中。
- 当前业务对象命中。
- 当前风险关键词命中。
- 当前 diff 命中。

禁止把所有历史测试用例都标记为回归候选。

## 候选字段

每个 `regression_candidates` 条目建议包含：

- `id`
- `title`
- `source_asset`
- `reason`
- `matched_signals`
- `priority`：`high`、`medium`、`low`
- `suggested_scope`
- `xmind_path`
- `xmind_exists`

## 优先级规则

`high`：当前模块同时命中接口、状态或业务对象变更，或存在同流程历史线上缺陷。

`medium`：覆盖上下游联动、shared 规则影响，或同系统相关流程。

`low`：只有一个有依据的当前范围信号，适合作为冒烟或窄范围回归。

## 风险关键词

必须检查：

- 历史线上缺陷
- 高频缺陷
- 幂等
- 并发
- 状态错乱
- 通知重复
- 异步延迟
- 回滚失败
- 接口兼容
- 权限绕过

如果 PRD 未说明已暴露风险的预期行为，同时写入 `risk_candidates` 和 `open_questions`。
