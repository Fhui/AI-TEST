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
    candidates: []

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
    reason: "无法在 DSL 阶段确认 DOM selector，需 enrichment probe 校准"

unsupported_steps:
  - source_case: ""
    source_step: ""
    reason: ""
    suggestion: ""
```

## 约束

- selector key 必须在文件内唯一。
- 自动生成的占位 selector 使用 `status: "todo"`。

- 只有源材料明确提供真实 selector（如 `[data-testid="xxx"]`、`#id`、`.class`）时，才可以使用 `status: "confirmed"`。
- 没有真实 DOM 时，不要仅凭语义文案确认 selector。例如 `点击确认` 不应在 DSL 生成阶段直接 confirmed 为 `role=button[name="确认"]`，因为真实 DOM 可能是 button、link 或普通文本。

- `status: "confirmed"` 的 selector 必须能够直接转换为 Playwright locator 并稳定执行。

- 当无法确认真实 selector 时，必须使用 `status: "todo"`，由 `dsl-selector-enrichment` 在 probe 阶段通过真实 DOM 的唯一匹配结果校准。

- 每个 selector entry 必须包含 `candidates`。
- `candidates` 必须是 `list[str]`。
- `status: "confirmed"` 时 `candidates` 可以为空。
- `status: "todo"` 时 `candidates` 应尽量非空。
- `candidates` 只是候选，不代表 confirmed，不允许改变 `selector` 或 `status`。
- 允许的 candidate 前缀：`role=`、`label=`、`placeholder=`、`text=`、`[data-testid=`、`#`、`.`。

- 除非源测试用例包含明确的数据值，否则保持 `test_data` 为空。
- 遇到不确定内容时，优先生成 TODO，不要猜测业务行为。

- selector key 使用 `<semantic>_<type>` 结构，动作词不进入 key；只有无法提取语义时才 fallback 到 `element_<index>`。
- expected 只有包含明确 UI 文案时才生成 selector/assert；页面加载、页面展示、字段状态、业务状态、PRD/规则未说明等 expected 不生成 selector，使用可选 `wait_for` 承接。
- `goto` 只用于源步骤明确包含 URL 的 `打开 https://...` 或 `访问 https://...`；普通 `进入页面/流程/表单` 不自动映射为 `goto`。
