---
name: testcase-to-playwright-dsl
description: 将 XMind 风格 Markdown 测试用例转换为面向 Playwright UI 自动化流程的可执行 DSL YAML。适用于 Codex 读取交付目录中的 testcase/xmind-testcases.md，并生成 ui-dsl/ui-test.dsl.yaml；要求 selector 与 flow 分离、生成 TODO selector 占位、保留 source_case 可追溯信息，且只生成 UI DSL，不执行 Playwright、不生成 .spec.ts、不运行 npx playwright test。
---

# 测试用例转 Playwright UI DSL

## 目标

将 XMind 风格测试用例 Markdown 转换为稳定、可维护、可二次编辑的 UI 自动化 DSL 文件：

- 输入：`./<delivery-name>/testcase/xmind-testcases.md`
- 输出：`./<delivery-name>/ui-dsl/ui-test.dsl.yaml`
- 本 skill 只生成 UI DSL。
- 不执行 Playwright。
- 不生成 `.spec.ts`。
- 不运行 `npx playwright test`。
- 不要在对话中输出完整 DSL，只落盘文件。
- 完成后只输出：`[✓] UI DSL 生成完成`

## 执行流程

1. 确认项目根目录是包含 `.codex` 的目录。
2. 根据用户请求定位交付目录；如果未指定，查找项目根目录下的 `*/testcase/xmind-testcases.md`。
3. 如果找到多个 `xmind-testcases.md`，立即停止执行，并要求用户指定 `delivery-name`。
4. 读取输入 Markdown，识别系统、版本、模块、用例标题、步骤、预期结果、优先级、前置条件。
   - 必须保留 Markdown 缩进层级，通过缩进判断 `tc`、`ts`、`ti`、`tp` 与 expected 的父子关系。
   - `ts` 的直接子节点都是该步骤的 expected，不要求带有“预期结果”前缀。
   - 不要把 `ts` 子节点误判为新的步骤，也不要把 `ti`、`tp` 当成 expected。
5. 运行 `scripts/convert_xmind_to_dsl.py` 生成初始 DSL。
6. 对照 `references/dsl-schema.md` 校验 YAML。若不符合，必须先修复再落盘；无法修复时，把原因写入 `unsupported_steps`，停止生成最终文件。
7. 只写入 `./<delivery-name>/ui-dsl/` 目录。
8. 最终回复只输出 `[✓] UI DSL 生成完成`。

## 转换脚本

优先使用内置转换脚本：

```bash
python .codex/skills/testcase-to-playwright-dsl/scripts/convert_xmind_to_dsl.py \
  --input ./<delivery-name>/testcase/xmind-testcases.md \
  --output ./<delivery-name>/ui-dsl/ui-test.dsl.yaml
```

脚本采用保守策略：没有真实 DOM 时不把语义推断标记为 confirmed。当测试用例中无法确定真实 selector 时，生成 `[data-testid="<selector_key>"]` 占位、`candidates` 候选列表，并记录 selector TODO；`点击 XXX`、`输入 XXX`、`看到 XXX` 等语义线索只作为后续 selector enrichment 的候选来源。只有源测试用例明确给出 `[data-testid="xxx"]`、`#id`、`.class` 时，selector 才能标记为 `confirmed`。
如果未传入 `--input`，脚本会查找 `*/testcase/xmind-testcases.md`；找到多个时会停止，并要求明确 `delivery-name`。

## DSL 规则

- 使用 `schema_version: "1.0"`。
- 一个 `tc` 转换为一个 `flow`。
- 一个 `ts` 转换为一个 action step。
- `ts` 的直接子节点转换为该步骤的 expected；一个 `ts` 可以有多个 expected 子节点。
- expected 子节点只在包含明确 UI 文案时转换为 assert 类 step，并写入 `source_expected`。
- 页面加载、页面展示、字段状态、业务状态、PRD/规则未说明等 expected 不生成 selector，转换为 `optional: true` 的 `wait_for`，并写入 TODO reason。
- 兼容旧格式 `预期结果: xxx` 和 `预期结果, xxx`。
- `ti` 只解析为 `P0`、`P1`、`P2`、`P3`。
- `tp` 解析为前置条件，保留多行内容。
- 每个 flow 必须包含 `source_case.tc` 和 `source_case.tp`。
- 可复用 selector 必须放在顶层 `selectors` 中。
- selector entry 必须包含 `candidates`；候选只用于 enrichment 校准，不代表 confirmed。
- 不确定的 selector 必须写入 `todos`。
- 无法转换的行为必须写入 `unsupported_steps`。
- 不允许凭空补充源测试用例中没有的业务规则。
- YAML 必须符合 `references/dsl-schema.md` 后才允许落盘。
- 本 skill 不负责执行自动化，不生成 Playwright 测试代码，不运行测试命令。

手动调整生成 YAML 前，先阅读 `references/dsl-schema.md`。

## 动作映射

- `打开 https://...`、`访问 https://...` -> `goto`
- `点击`、`选择`、`勾选` -> `click`
- `输入`、`填写` -> `fill`
- `下拉选择` -> `select`
- `上传` -> `upload`
- `等待` -> `wait_for`
- `查看`、`校验可见` -> `assert_visible`
- `校验文案`、`提示`、`状态`、`结果` -> `assert_text` 或 `assert_state`
- `删除`、`移除` -> `click`；如果存在预期结果，再补充 assert
- `搜索`、`查询` -> `fill` + `click`；如果源文本足够明确，再补充 assert
- `进入页面`、`进入流程`、`点击后进入页面` 等不允许自动转为 `goto`；若没有明确 URL 或可拆分原子动作，生成可选 `wait_for` 并记录 unsupported。

## Selector 规则

- 使用英文 `snake_case`。
- 基于 `description + source + action` 提取通用 UI 语义词，不使用具体业务 PRD 或业务词表。
- 清理动作词：`点击`、`输入`、`填写`、`选择`、`勾选`、`查看`、`显示`。
- 按动作推断类型后缀：`click -> button`、`fill -> input`、`select -> select`、`upload -> upload`、勾选类 click -> `checkbox`。
- key 结构为 `<semantic>_<type>`；只有无法提取语义时才 fallback 到 `element_<index>`。
- 示例：`点击某入口 -> entry_button`、`输入某字段 -> field_input`、`勾选某选项 -> option_checkbox`、`点击确认 -> confirm_button`、`上传文件 -> file_upload`。
- 如果无法确定真实 selector，使用 `[data-testid="<selector_key>"]`，并保持 `status: "todo"`。
- `status: "todo"` 的 selector 应尽量生成 `candidates`，例如 role、label、placeholder、text、data-testid、id、class 候选。
- `candidates` 不能写入 `selector` 字段，也不能让 selector 变为 confirmed；`dsl-selector-enrichment` 负责验证 candidates 并在唯一命中后写回 confirmed selector。
- `playwright-dsl-to-spec` 只执行 `status: "confirmed"` 的 selector，忽略 `candidates`。
- 不要仅凭 `点击 XXX` 推断为 `role=button[name="XXX"]` confirmed；真实 DOM 中可能是 button、link 或普通文本，交给 `dsl-selector-enrichment` probe 校准。
- 每个 selector 占位都必须在 `todos` 中记录 `selector_key`、来源用例、来源步骤和原因。

## Expected 规则

- 只有 expected 包含明确 UI 文案时才生成 selector/assert，例如 `显示“xxx”`、`提示“xxx”`、`看到“xxx”`。
- `页面加载完成`、`页面展示xxx`、`字段展示已输入状态`、`PRD未说明`、`规则未说明` 等状态类 expected 禁止生成 selector。
- 状态类 expected 转换为 `action: wait_for`、`optional: true`，comment 使用 `expected is page/business state, selector not generated`。

## 复合步骤规则

- 支持拆分通用原子动作：`输入 A 和 B` -> 两个 `fill`；`点击 A 并点击 B` -> 两个 `click`；`勾选 A 并提交` -> `checkbox` click + button click。
- 不可拆分的导航语义，例如 `进入某页面`、`进入某表单`，转换为 `optional: true` 的 `wait_for`，comment 使用 `compound navigation step, requires manual decomposition`，并写入 `unsupported_steps`。

## TODO reason 规则

- 操作类 selector：`无法在 DSL 阶段确认 DOM selector，需 enrichment probe 校准`。
- 页面/业务状态类 expected：`expected 为页面/业务状态，不生成 selector`。
- PRD 不明确：`PRD 未提供明确 UI 信息`。
- 复合步骤：`复合步骤需拆分为原子操作`。

## 输出约定

最终 YAML 必须符合以下顶层结构：

```yaml
schema_version: "1.0"
meta: {}
selectors: {}
test_data: {}
flows: []
todos: []
unsupported_steps: []
```
