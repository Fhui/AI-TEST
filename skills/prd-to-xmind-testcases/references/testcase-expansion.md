# Testcase Expansion

## Expansion Philosophy

`testpoint` 不等于 `testcase`。

`testpoint` 是测试对象或测试意图，通常描述“需要测什么”。

`testcase-expansion` 的职责是把测试对象展开为测试矩阵，再由测试矩阵生成多条可执行 testcase。

禁止：

```text
一个 testpoint -> 一个 testcase
```

鼓励：

```text
一个 testpoint -> 多维矩阵 -> 多个 testcase
```

复杂 testpoint 必须先识别可展开维度，再决定 testcase 数量。不要把多个独立规则压缩进一条 testcase。

## Expansion Principle

禁止：

```text
功能点 -> 单条代表性 case
```

必须：

```text
功能点 -> 业务维度识别 -> 组合矩阵 -> 多条可执行 case
```

测试点不是最终 case。每个测试点必须先进入 expansion matrix，再生成 testcase groups。

## Expansion Dimensions

每个 testpoint 必须逐项评估以下通用维度。

适用则展开；不适用可以跳过，但必须能说明 skipped reason。

```yaml
expansion_dimensions:
  - field
  - enum
  - state
  - role
  - data
  - workflow
  - exception
  - boundary
  - dependency
```

维度含义：

- `field`: 输入框、下拉框、开关、单选、多选、上传组件等字段级规则。
- `enum`: 状态、类型、分类、模式、渠道等枚举值。
- `state`: 状态机、流程状态、生命周期状态。
- `role`: 用户角色、后台角色、系统角色、数据范围权限。
- `data`: 业务数据、关系数据、配置数据、结果数据。
- `workflow`: 业务流程、操作链路、跨页面链路。
- `exception`: 接口、数据库、缓存、消息、三方系统异常。
- `boundary`: 数量、长度、金额、时间、分页等边界。
- `dependency`: 上游、下游、外部依赖、异步任务。

## General Expansion Dimensions

不要硬编码具体业务。必须从 PRD 与 context 中抽取以下维度：

- 业务对象维度
- 操作维度
- 状态维度
- 角色维度
- 数据维度
- 规则命中维度
- 配置维度
- 权限维度
- 异常维度
- 异步维度
- workflow 维度
- 上下游维度
- 历史回归维度
- 历史缺陷维度
- 结果形态维度
- 版本形态维度
- 环境维度

## Field Expansion Rule

适用于：

- 输入框
- 下拉框
- 开关
- 单选
- 多选
- 上传组件
- 日期 / 时间选择器
- 搜索框

建议展开：

```yaml
field_expansion:
  - required
  - optional
  - empty
  - duplicate
  - invalid_format
  - max_length
  - min_length
  - special_characters
```

规则：

- 每个字段约束应单独评估。
- 必填、格式、长度、重复、默认值不能合并为一条 testcase。
- 字段之间存在依赖时，必须补充跨字段组合。

## Enum Expansion Rule

适用于：

- 状态
- 类型
- 分类
- 模式
- 渠道
- 配置方案

要求：

- 每个枚举值必须单独评估。
- 禁止用一条 testcase 概括“所有枚举值展示正确”。
- 枚举值影响行为、权限、状态或结果时，必须进入组合矩阵。

## State Expansion Rule

适用于：

- 状态机
- 流程状态
- 生命周期状态

建议展开：

```yaml
state_expansion:
  - valid_transition
  - invalid_transition
  - rollback
  - duplicate_operation
  - terminal_state
```

规则：

- 合法迁移和非法迁移必须分开。
- 终态后的操作必须单独覆盖。
- 重复操作、回退、取消、关闭、刷新等幂等路径必须评估。

## Workflow Expansion Rule

适用于：

- 业务流程
- 操作链路
- 跨页面链路
- 跨系统链路

建议展开：

```yaml
workflow_expansion:
  - happy_path
  - alternate_path
  - exception_path
  - recovery_path
```

规则：

- 主流程只覆盖 happy path，不代表 workflow 完整。
- 分支、异常、恢复路径必须独立生成 testcase。
- workflow 中每个关键节点都应能追溯到 testpoint 或 structured-analysis。

## Exception Expansion Rule

适用于：

- 接口
- 数据库
- 缓存
- 消息
- 三方系统
- 文件上传 / 下载
- 异步任务

建议展开：

```yaml
exception_expansion:
  - timeout
  - empty_result
  - invalid_result
  - partial_failure
  - duplicate_request
```

规则：

- 异常不能只写“异常处理正确”。
- 超时、空结果、非法结果、部分失败、重复请求必须按适用性拆开。
- 如果 PRD 未说明异常处理，必须生成待确认项或风险 testcase。

## Boundary Expansion Rule

适用于：

- 数量
- 长度
- 金额
- 时间
- 分页
- 上传数量
- 选择数量

建议展开：

```yaml
boundary_expansion:
  - minimum
  - maximum
  - below_minimum
  - above_maximum
  - default_value
```

规则：

- 最小值、最大值、低于最小值、高于最大值、默认值必须分开评估。
- 边界影响保存、查询、展示或状态时，必须生成独立 testcase。
- 分页、批量选择、批量导入导出必须覆盖边界页和空数据页。

## Combination Matrix Rules

每个测试点至少回答：

- 该测试点涉及哪些对象
- 有哪些操作方式
- 涉及哪些状态
- 涉及哪些配置
- 涉及哪些数据边界
- 涉及哪些角色 / 权限
- 涉及哪些异常和失败路径
- 涉及哪些上下游和 workflow
- 是否命中历史回归或历史缺陷

组合示例必须保持抽象：

```text
对象类型 x 操作方式 x 状态 x 配置 x 结果形态
角色 x 权限 x 数据范围 x 操作
workflow 节点 x 分支条件 x 失败模式 x 补偿方式
```

不要在主规则中写具体业务组合。

## Domain Profile Integration

`testcase-expansion` 不负责定义业务维度。

业务维度必须来源于：

- 当前 PRD
- `structured-analysis.md`
- `testpoint-model.md`
- `context-reference.md`
- `selected_domain_profiles` 对应的 `references/domain-expansion/*.md`

职责边界：

```text
testcase-expansion 定义：如何展开
domain-expansion 定义：按什么业务维度展开
```

规则：

- 禁止在本文件写入具体业务规则。
- 禁止把某个系统、某个产品、某个模块的枚举硬编码到本文件。
- domain profile 只提供领域扩展维度，不能覆盖当前 PRD 的明确规则。

## Historical Regression Expansion

如果命中历史 testcase：

- 禁止只抽几条代表性回归
- 必须按命中范围生成覆盖型回归集合
- 同 module 历史 testcase 命中时，最终相关回归 case 数量通常不得低于历史相关 tc 数量的 70%
- 如果低于 70%，必须写明 `skip_reason`

可跳过的合理原因：

- 历史用例与当前 PRD 冲突
- 历史用例对应功能被废弃
- 历史 AI source 截断，无法确认细节
- 当前影响范围未命中该历史流程

## Workflow Expansion

workflow 必须展开：

- 主流程
- 分支流程
- 回退流程
- 失败流程
- 重试流程
- 跨系统流程
- 异步流程
- 补偿流程

## Coverage Expectation

case 数量不是唯一目标，但复杂 testpoint 不应被摘要成少数 testcase。

通常期望：

- 普通 testpoint：产生 2~5 个 testcase。
- 复杂 testpoint：产生 5~20 个 testcase。
- 极复杂 testpoint：可能产生 20~50 个 testcase。

如果复杂 testpoint 最终只生成 1~2 条 testcase，必须在 `testcase-expansion.md` 写明原因。

合理原因包括：

- PRD 明确只有单一行为。
- 该 testpoint 已被其他矩阵覆盖。
- 缺少数据或规则，已进入 open questions。
- 当前变更范围不包含该维度。

## Minimum Case Count Guidance

不要强行凑数量，但必须检查数量偏低风险：

- simple：通常不少于 30 条
- normal：通常不少于 60 条
- complex：通常不少于 100 条

低于建议值时，必须在 `pipeline-output.json` 写入：

```json
{
  "case_count_warning": true,
  "expected_min_case_count": 60,
  "actual_case_count": 32,
  "case_count_reason": ""
}
```

## Prohibited Patterns

禁止使用以下抽象描述作为 testcase 标题或唯一验证目标：

- 符合规则
- 功能正常
- 校验正确
- 状态正确
- 数据正确
- 展示正确
- 跳转正常
- 操作成功
- 异常处理正确

禁止：

- 一个 testcase 验证多个独立规则。
- 一个复杂 testpoint 仅生成 1~2 个 testcase 且无说明。
- 把多个字段校验合并为“字段校验正确”。
- 把多个枚举值合并为“枚举展示正确”。
- 把多个状态迁移合并为“状态流转正确”。
- 把多个异常合并为“异常提示正确”。

每条 testcase 必须有明确的单一验证目标，且能追溯到一个或一组不可再拆的规则。

## Expansion Self Check

每个 testpoint 完成 expansion 后，必须执行自检。

```yaml
self_check:
  evaluated_dimensions: []
  expanded_dimensions: []
  skipped_dimensions: []
  expected_case_count: 0
  expansion_reason: ""
```

字段说明：

- `evaluated_dimensions`: 已评估的维度，必须覆盖 `expansion_dimensions`。
- `expanded_dimensions`: 实际展开的维度。
- `skipped_dimensions`: 跳过的维度及原因。
- `expected_case_count`: 根据矩阵推导出的建议 case 数。
- `expansion_reason`: 说明为什么生成这些 testcase，以及为什么没有继续展开。

自检规则：

- `evaluated_dimensions` 不能为空。
- `expanded_dimensions` 不能为空，除非 testpoint 被明确跳过。
- `skipped_dimensions` 必须写明 reason。
- `expected_case_count` 明显高于实际 case 数时，必须写入 `case_count_warning` 或 `case_count_reason`。

## Output Template

`testcase-expansion.md` 至少包含：

- Expansion Summary
- Domain Expansion Profile Used
- Testpoint to Matrix Mapping
- Case Groups
- Historical Regression Expansion
- Workflow Expansion
- Skipped Combinations
- Minimum Case Count Check
- Expansion Self Check
- Open Questions
