# Traceability Rules

## Case Source

每条 testcase 在 JSON / CSV / pipeline-output 中尽量标记：

- case_type
- context_source
- source
- source_reason
- ai_source_path
- xmind_path
- traceability

## context_source Values

允许值：

- current_prd
- historical_prd
- historical_testcase
- historical_bug
- workflow_hit
- upstream_dependency
- downstream_dependency
- shared_rule
- inferred

## Markdown Boundary

Markdown XMind 树中不要放 traceability 审计字段。

## XMind Boundary

`.xmind` 只能作为 human preview / traceability 路径，不作为 AI 输入源。
