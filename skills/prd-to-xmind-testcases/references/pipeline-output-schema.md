# Pipeline Output Schema

`pipeline-output.json` 是 pipeline summary，不是 context-package 镜像。

## Required Fields

至少包含：

- system
- module
- testcase_summary
- traceability
- open_questions
- automation_candidates
- risk_points
- historical_context_missing
- degraded_mode
- context_validation
- context_reference
- context_package
- case_count_warning
- expected_min_case_count
- actual_case_count
- case_count_reason
- regression_skip_reason
- risk_skip_reason

## Context Summary

`context_package` 只保存轻量引用：

```json
{
  "retrieval_summary": {},
  "workflow_hits": [],
  "reused_testcase_refs": [],
  "regression_candidate_refs": [],
  "risk_candidate_refs": [],
  "source_files": []
}
```

禁止复制完整历史 PRD、完整历史 testcase、完整 context-package。

## Case Count Warning

低于 testcase-expansion 建议值时必须写：

```json
{
  "case_count_warning": true,
  "expected_min_case_count": 60,
  "actual_case_count": 32,
  "case_count_reason": "低于建议值的原因"
}
```

## Traceability

traceability 必须尽量保留：

- context_source
- ai_source_path
- xmind_path
- source_reason
- structured_analysis_ref
- testpoint_ref
- expansion_ref
