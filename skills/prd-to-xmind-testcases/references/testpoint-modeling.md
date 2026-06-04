# Testpoint Modeling

## Goal

将 structured-analysis 压缩为模块级测试点模型。testpoint 不是 testcase，不允许直接跳到用例。

## Input

- `structured-analysis.md`
- `context-reference.md`
- `context-package.json`
- 当前 PRD
- PlantUML，complex pipeline 可选

## Dynamic Categories

必须输出：

- 主路径
- 分支路径
- 异常路径
- 数据约束

有明确语义时才输出：

- 状态
- 权限
- 通知
- 异步
- 失败补偿
- 场景

禁止生成空分类，禁止硬凑测试点。

## Traceability

每个测试点必须能追溯到：

- Domain Model
- State Machine
- Behavior Model
- Data Rules
- Permission Model
- System Behavior
- context-reference 中的回归 / 风险 / workflow 命中

## Regression Mapping

历史测试用例只有在命中以下字段时，才允许转为回归测试点：

- `reused_testcases`
- `regression_candidates`
- `workflow_hits`

历史缺陷只有在命中以下字段或当前影响范围时，才允许转为风险 / 防回归测试点：

- `risk_candidates`
- `conflicts`
- current impact scope

禁止把全部历史 testcase 直接转成回归测试点。

## Output

`testpoint-model.md` 必须包含：

- 测试点分类
- 测试点 ID
- 测试点描述
- traceability
- 是否进入 testcase-expansion
- 待确认项

不要复制完整 structured-analysis。
