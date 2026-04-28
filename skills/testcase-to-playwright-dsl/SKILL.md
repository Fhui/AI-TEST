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

脚本采用保守策略：当测试用例中无法确定真实 selector 时，生成 `[data-testid="<selector_key>"]` 占位，并记录 selector TODO。
如果未传入 `--input`，脚本会查找 `*/testcase/xmind-testcases.md`；找到多个时会停止，并要求明确 `delivery-name`。

## DSL 规则

- 使用 `schema_version: "1.0"`。
- 一个 `tc` 转换为一个 `flow`。
- 一个 `ts` 转换为一个 action step。
- `ts` 的直接子节点转换为该步骤的 expected；一个 `ts` 可以有多个 expected 子节点。
- 每个 expected 子节点转换为一个 assert 类 step，并写入 `source_expected`。
- 兼容旧格式 `预期结果: xxx` 和 `预期结果, xxx`。
- `ti` 只解析为 `P0`、`P1`、`P2`、`P3`。
- `tp` 解析为前置条件，保留多行内容。
- 每个 flow 必须包含 `source_case.tc` 和 `source_case.tp`。
- 可复用 selector 必须放在顶层 `selectors` 中。
- 不确定的 selector 必须写入 `todos`。
- 无法转换的行为必须写入 `unsupported_steps`。
- 不允许凭空补充源测试用例中没有的业务规则。
- YAML 必须符合 `references/dsl-schema.md` 后才允许落盘。
- 本 skill 不负责执行自动化，不生成 Playwright 测试代码，不运行测试命令。

手动调整生成 YAML 前，先阅读 `references/dsl-schema.md`。

## 动作映射

- `打开`、`进入`、`访问`、`跳转` -> `goto`
- `点击`、`选择`、`勾选` -> `click`
- `输入`、`填写` -> `fill`
- `下拉选择` -> `select`
- `上传` -> `upload`
- `等待` -> `wait_for`
- `查看`、`校验可见` -> `assert_visible`
- `校验文案`、`提示`、`状态`、`结果` -> `assert_text` 或 `assert_state`
- `删除`、`移除` -> `click`；如果存在预期结果，再补充 assert
- `搜索`、`查询` -> `fill` + `click`；如果源文本足够明确，再补充 assert

## Selector 规则

- 使用英文 `snake_case`。
- 优先表达业务含义，不使用纯位置描述。
- 示例：`login_button`、`permission_name_input`、`import_course_button`、`product_table`、`confirm_delete_modal`。
- 如果无法确定真实 selector，使用 `[data-testid="<selector_key>"]`。
- 每个 selector 占位都必须在 `todos` 中记录 `selector_key`、来源用例、来源步骤和原因。

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
