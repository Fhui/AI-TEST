# Context Validation

## Required Validation

Phase 0.5 必须校验：

- JSON 是否可解析
- 字段类型是否正确
- `system`
- `module`
- `retrieval_summary`
- `workflow_hits`
- `strong_related`
- `medium_related`
- `reused_testcases`
- `regression_candidates`
- `risk_candidates`
- `open_questions`

## Missing Fields

如果 `system / module / retrieval_summary` 缺失：

- 写入 Open Questions
- 禁止臆造

如果 `workflow_hits / regression_candidates / risk_candidates` 为空：

- 允许继续
- 写入 warning 或 open_questions

## Invalid Package

如果 JSON 无法解析、schema 错误或字段类型错误：

- 进入 degraded context mode
- 不终止整个 pipeline

degraded 标记：

```json
{
  "historical_context_missing": true,
  "degraded_mode": true,
  "context_validation": {
    "valid": false,
    "missing_fields": [],
    "warnings": []
  }
}
```
