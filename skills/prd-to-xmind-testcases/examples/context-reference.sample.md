# Context Reference

## Context Package Summary

- historical_context_missing: false
- degraded_mode: false
- workflow_hits: 1
- regression_candidates: 2

## Source Files

- current_prd: /path/to/current.md
- historical_prd: /path/to/history.md
- historical_testcase_ai_source: /path/to/history-testcase.md
- historical_testcase_xmind_preview: /path/to/history.xmind

## Workflow Hits

- WF-001: 创建 -> 处理 -> 结果

## 历史测试用例复用点

- 同模块历史主流程可复用为回归候选。

## 影响范围分析

- 当前模块影响：对象处理链路。
- 下游输出影响：结果展示和通知。

## Open Questions

- workflow 回退条件 PRD未说明。
