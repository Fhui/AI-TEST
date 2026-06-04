# Testcase Expansion

## Expansion Summary

- complexity: normal
- selected profiles: generic
- testpoints: 8
- generated case groups: 12
- expected_min_case_count: 60
- actual_case_count_planned: 64

## Testpoint to Matrix Mapping

### TP-MAIN-001

Matrix:

```text
对象类型 x 操作方式 x 状态 x 结果形态
```

Generated groups:

- CG-001 正常对象在初始状态下执行主操作成功
- CG-002 正常对象在处理中状态下重复执行主操作幂等
- CG-003 异常对象在受限状态下执行主操作被阻止

## Historical Regression Expansion

- 命中历史同模块 testcase 10 条
- 采纳 8 条
- coverage: 80%

## Skipped Combinations

- 历史用例 H-009 被废弃，skip_reason: 当前 PRD 删除对应功能
