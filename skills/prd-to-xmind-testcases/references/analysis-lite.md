# Analysis Lite

## Scope

仅用于 simple PRD。

## Goal

不执行完整 6 大建模维度，只抽取 testcase 所需最小模型。

## Must Extract

- 核心对象
- 核心流程
- 关键规则
- 关键异常
- 历史上下文影响
- workflow_hits
- reused_testcases
- regression_candidates
- risk_candidates
- upstream / downstream impact
- 待确认项

## Regression Rule

simple 也必须检查历史上下文。

如果 regression/risk/workflow 非空：

- 最终 testcase 必须生成对应回归、风险或 workflow 用例
- 未采纳时必须写 `regression_skip_reason` 或 `risk_skip_reason`
