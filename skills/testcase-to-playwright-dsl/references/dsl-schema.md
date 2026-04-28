# UI DSL Schema

`ui-test.dsl.yaml` 必须使用以下 schema。

```yaml
schema_version: "1.0"

meta:
  system: ""
  version: ""
  module: ""
  source: "./<delivery-name>/testcase/xmind-testcases.md"
  generated_at: ""
  description: ""

selectors:
  selector_key:
    selector: '[data-testid="selector_key"]'
    description: ""
    source: ""
    status: "todo" # todo | confirmed

test_data:
  data_key:
    value: ""
    description: ""

flows:
  - id: "flow_001"
    name: ""
    module: ""
    priority: "P1" # P0 | P1 | P2 | P3
    source_case:
      tc: ""
      tp: ""
    tags:
      - "ui"
    preconditions:
      - ""
    steps:
      - id: "step_001"
        source_ts: ""
        action: "goto" # goto | click | fill | select | upload | wait_for | assert_visible | assert_text | assert_state
        target: ""
        value: ""
        url: ""
        source_expected: ""
        timeout_ms: 5000
        optional: false
        comment: ""
      - id: "step_002"
        source_ts: ""
        source_expected: ""
        action: "assert_visible"
        target: ""
        expected: ""
        timeout_ms: 5000
        optional: false
        comment: ""

todos:
  - type: "selector"
    key: ""
    source_case: ""
    source_step: ""
    reason: "真实 selector 未在测试用例中提供，需要人工补充"

unsupported_steps:
  - source_case: ""
    source_step: ""
    reason: ""
    suggestion: ""
```

## 约束

- selector key 必须在文件内唯一。
- 自动生成的占位 selector 使用 `status: "todo"`。

- 当源材料满足以下任一条件时，可以使用 `status: "confirmed"`：
  1. 明确提供真实 selector（如 data-testid、id 等）
  2. 提供明确 UI 文案，可推断为稳定的 Playwright 语义 locator，包括但不限于：
     - 按钮文案（role=button[name="xxx"]）
     - 输入字段（label=xxx / placeholder=xxx）
     - 勾选项（role=checkbox[name="xxx"]）
     - 页面或提示文案（text=xxx）

- `status: "confirmed"` 的 selector 必须能够直接转换为 Playwright locator 并稳定执行。

- 当无法推断稳定 selector 时，必须使用 `status: "todo"`。

- 除非源测试用例包含明确的数据值，否则保持 `test_data` 为空。
- 遇到不确定内容时，优先生成 TODO，不要猜测业务行为。
