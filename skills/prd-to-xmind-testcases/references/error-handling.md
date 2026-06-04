# Error Handling

## Retrieval

- context package 不存在时，先尝试 retrieval
- retrieval 不可用或失败时进入 degraded context mode
- 不允许直接调用 `test-knowledge-mcp` 兜底
- 不允许自行扫描知识库

## Context

- context package 非法时继续 pipeline，但标记 degraded mode
- context 与当前 PRD 冲突时写 conflicts 和 open_questions
- 历史 source 截断时写 warning

## Analysis

- normal / complex 的 6 大建模维度和 8 个强制问题不完整时，不进入 testpoint
- simple 的核心对象、核心流程、关键规则、关键异常不完整时，不进入 testcase

## Testcase Expansion

- normal / complex 禁止跳过 testcase-expansion
- case 数量低于建议值时必须写 case_count_warning
- 跳过历史回归候选必须写 skip_reason

## Assets

- 图片下载失败时记录缺口并继续
- 无法确认流程图 / 时序图时不转 PlantUML
