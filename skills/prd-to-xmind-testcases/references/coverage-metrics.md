# Coverage Metrics

# Coverage Philosophy

coverage 的目标是判断测试覆盖是否充分。

coverage 不等于 testcase 数量。

大量 testcase 不代表高覆盖率。覆盖质量优先于数量。

case count 只能作为辅助指标，用于发现明显的展开不足，不能单独代表 coverage 是否充分。

本文件只定义可解释、可 review、可调试的 coverage validation 规则，不引入复杂数学公式，不引入百分比加权评分模型。

# Coverage Layers

coverage validation 分为四层：

```yaml
coverage_layers:
  - dimension_coverage
  - domain_coverage
  - historical_coverage
  - case_count_expectation
```

四层含义：

- `dimension_coverage`: 检查通用展开维度是否覆盖充分。
- `domain_coverage`: 检查 selected domain profiles 中定义的领域维度、风险和 workflow 是否覆盖。
- `historical_coverage`: 检查历史 testcase、历史 testpoint、历史风险是否被合理保留。
- `case_count_expectation`: 使用 testcase 数量作为辅助质量信号。

# Dimension Coverage

testcase-expansion 完成后，必须评估以下维度：

```yaml
dimensions:
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

必须判断：

- 哪些维度适用于当前 PRD / testpoint。
- 哪些维度已覆盖。
- 哪些维度缺失。
- 缺失维度是否影响最终 testcase 输出。

输出示例：

```yaml
dimension_coverage:
  field: covered
  enum: covered
  state: missing
  role: covered
  data: covered
  workflow: covered
  exception: missing
  boundary: covered
  dependency: warning
```

状态含义：

- `covered`: 适用且已覆盖。
- `missing`: 适用但未覆盖。
- `warning`: 部分覆盖或依赖 PRD 未说明。
- `not_applicable`: 当前 PRD 或 testpoint 不适用。

# Coverage Targets

Coverage Targets 用于判断 `covered / warning / missing` 状态。

Coverage Targets 不是强制生成规则，不直接决定 testcase 数量。

```yaml
coverage_targets:
  field:
    - all_relevant_rules
  enum:
    - all_relevant_values
  state:
    - all_relevant_states
  role:
    - all_relevant_roles
  workflow:
    - happy_path
    - critical_alternate_path
    - critical_exception_path
  exception:
    - critical_exceptions
  boundary:
    - critical_boundaries
  dependency:
    - critical_dependencies
```

判断原则：

- `covered`: 关键目标已覆盖。
- `warning`: 部分目标覆盖，或关键目标依赖 PRD 未说明。
- `missing`: 关键目标未覆盖。

说明：

- `all_relevant_rules`: 当前 PRD 明确或 context 命中的相关字段规则。
- `all_relevant_values`: 当前 PRD 明确或 domain profile 命中的相关枚举值。
- `all_relevant_states`: 当前状态机或生命周期中的关键状态。
- `all_relevant_roles`: 当前需求涉及的关键角色和权限边界。
- `critical_alternate_path`: 会影响核心业务结果的关键分支路径。
- `critical_exception_path`: 会影响核心业务结果或数据一致性的异常路径。
- `critical_exceptions`: 接口、三方、异步、存储等关键异常。
- `critical_boundaries`: 数量、长度、金额、时间、分页等关键边界。
- `critical_dependencies`: 上下游、三方、异步任务等关键依赖。

# Domain Coverage

domain coverage 来源于 `selected_domain_profiles`。

例如：

- `generic`
- `watchPic`
- `cloud`
- `appointment`

如果 selected domain profile 定义了以下内容，必须评估是否已经覆盖：

- Expansion Dimensions
- Risk Characteristics
- Workflow Patterns
- Domain Model
- State / Status
- Core Actions
- Key Attributes
- Integration Dependencies

输出示例：

```yaml
domain_coverage:
  profile: appointment
  covered_dimensions:
    - appointment_status
    - store_type
    - order_flow
    - payment_flow
  missing_dimensions:
    - location_failure
    - slot_exhaustion
  warning_dimensions:
    - third_party_customer_service_failure
```

规则：

- domain profile 只提供覆盖检查维度，不覆盖当前 PRD 的明确规则。
- 如果 profile 风险点与当前 PRD 命中，但 testcase-expansion 未覆盖，必须写入 `coverage_gaps.missing_domain_area`。
- 如果无法确认 profile 中的某个维度是否适用，应标记 `warning`，不要强行生成 testcase。

# Historical Coverage

如果存在以下历史上下文，必须评估历史覆盖保留情况：

- `context-package.json`
- 历史 testcase
- 历史 testpoint
- 历史缺陷
- 历史风险点
- 历史 workflow

输出：

```yaml
historical_coverage:
  matched_tc: 120
  reused_tc: 95
  skipped_tc: 25
  skip_reason:
    - 当前 PRD 未命中对应历史流程
    - 历史用例与当前 PRD 冲突
    - 历史功能已废弃
```

规则：

- 历史 coverage 只在存在历史资料时启用。
- 不允许在没有历史资料时臆造历史覆盖。
- 不允许把所有历史 testcase 无脑复制为回归 testcase。
- 历史用例未被复用时，必须说明 `skip_reason`。
- 历史缺陷和历史风险命中当前影响范围时，必须进入风险覆盖或防回归覆盖。

# Case Count Expectation

case 数量仅作为辅助指标，不能单独代表 coverage。

建议值：

```yaml
expected_case_count:
  simple:
    min: 50
  normal:
    min: 100
  complex:
    min: 300
  enterprise:
    min: 800
```

规则：

- 低于建议值时，写入 `case_count_warning`。
- `case_count_warning` 不得单独阻断 pipeline。
- case 数量达到建议值，不代表 coverage 自动通过。
- 如果 case 数量很高但关键维度缺失，coverage decision 仍可以是 `warning` 或 `fail`。

# Coverage Pressure

coverage pressure 不直接生成 testcase。

coverage pressure 用于决定是否需要返回 testcase-expansion 继续展开。

```yaml
coverage_pressure:
  insufficient_case_count:
    action:
      - continue_evaluate_dimensions
  missing_dimension:
    action:
      - continue_expand
  missing_domain_area:
    action:
      - continue_expand
  missing_risk_area:
    action:
      - continue_expand
```

规则：

- 如果 `actual_case_count` 明显低于 `expected_case_count`，不能仅依据数量判断 `fail`。
- 低数量时，必须进一步检查 `dimension_coverage`、`domain_coverage`、`historical_coverage`。
- 如果同时存在低数量和覆盖缺口，coverage decision 不得直接 `pass`。
- 如果缺失的是关键维度、关键 domain area 或关键 risk area，应返回 testcase-expansion 继续展开。
- 如果低数量但关键覆盖目标已覆盖，可以输出 `warning` 并继续 testcase。

# Coverage Gaps

必须识别以下覆盖缺口：

```yaml
coverage_gaps:
  missing_dimension: []
  missing_domain_area: []
  missing_regression_area: []
  missing_risk_area: []
```

字段说明：

- `missing_dimension`: 通用展开维度缺失，例如 state、exception、dependency。
- `missing_domain_area`: selected domain profiles 中命中的领域维度缺失。
- `missing_regression_area`: 历史 testcase / testpoint / workflow 命中但未覆盖。
- `missing_risk_area`: 风险点、历史缺陷、异常路径命中但未覆盖。

每个 gap 必须包含：

```yaml
gap_item:
  type: ""
  description: ""
  source: ""
  impact: ""
  suggested_action: ""
```

# Coverage Decision

coverage decision 定义：

```yaml
coverage_decision:
  - pass
  - warning
  - fail
```

## PASS

条件：

- 关键维度已覆盖。
- selected domain profiles 中命中的核心维度已覆盖。
- 明确命中的历史回归或风险点已覆盖，或有合理 skip reason。
- case count 没有明显低于建议值，或低于建议值但 coverage gap 不影响关键路径。

## WARNING

条件：

- 存在覆盖缺口，但 testcase 仍可输出。
- 部分维度因 PRD 未说明无法覆盖。
- 历史上下文缺失或 degraded context mode。
- case count 低于建议值，但主流程、风险路径和关键 domain dimensions 已覆盖。

## FAIL

条件：

- 关键维度严重缺失，不得进入最终 testcase 输出。
- 主 workflow 未覆盖。
- 关键异常路径未覆盖。
- Coverage Targets 中的关键目标缺失，例如 critical workflow、critical exception、critical state 未覆盖。
- selected domain profile 的核心风险维度命中但未覆盖。
- 历史高风险缺陷命中当前影响范围但未覆盖且无 skip reason。

FAIL 时必须返回 testcase-expansion 阶段继续展开，不得直接进入最终 testcase 输出。

# Output Format

coverage report 必须使用以下结构：

```yaml
coverage_report:
  dimension_coverage:
    field: ""
    enum: ""
    state: ""
    role: ""
    data: ""
    workflow: ""
    exception: ""
    boundary: ""
    dependency: ""
  domain_coverage:
    - profile: ""
      covered_dimensions: []
      missing_dimensions: []
      warning_dimensions: []
  historical_coverage:
    matched_tc: 0
    reused_tc: 0
    skipped_tc: 0
    skip_reason: []
  case_count:
    expected_min_case_count: 0
    actual_case_count: 0
    case_count_warning: false
    case_count_reason: ""
  coverage_gaps:
    missing_dimension: []
    missing_domain_area: []
    missing_regression_area: []
    missing_risk_area: []
  coverage_decision: ""
```

# Integration

`coverage-metrics` 位于 `testcase-expansion` 之后、`testcase` 之前。

流程：

```text
testpoint
↓
testcase-expansion
↓
coverage-metrics
↓
testcase
```

规则：

- coverage-metrics 不生成 testcase。
- coverage-metrics 不替代 testcase-expansion。
- coverage-metrics 只判断覆盖是否充分，并输出 coverage report。
- coverage decision 为 `fail` 时，必须返回 testcase-expansion 继续展开。
- coverage decision 为 `warning` 时，可以继续输出 testcase，但必须在 pipeline-output 中保留 warning 和 coverage gaps。

# Prohibited

禁止：

- 使用 testcase 数量替代 coverage 判断。
- 引入复杂数学公式。
- 引入百分比加权评分模型。
- 因 case count 达标就跳过 dimension / domain / historical coverage。
- 在没有历史资料时臆造 historical coverage。
- 用 domain profile 覆盖当前 PRD 的明确规则。