---
name: playwright-dsl-to-spec
description: 将符合 .codex/skills/testcase-to-playwright-dsl/references/dsl-schema.md 的 ui-test.dsl.yaml 转换为 Playwright spec.ts。适用于 Codex 读取 ./<delivery-name>/ui-dsl/ui-test.dsl.yaml 并生成 ./<delivery-name>/playwright/tests/*.spec.ts；严格按 DSL schema 解析字段，不新增 DSL 字段，不修改 testcase-to-playwright-dsl skill，不执行 Playwright，不运行 npx playwright test。
---

# Playwright DSL 转 Spec

## 目标

将交付目录中的 UI DSL 转换为 Playwright 测试代码：

- 输入：`./<delivery-name>/ui-dsl/ui-test.dsl.yaml`
- 输出：`./<delivery-name>/playwright/tests/*.spec.ts`
- 唯一 DSL 规范来源：项目内 `.codex/skills/testcase-to-playwright-dsl/references/dsl-schema.md`
- `ui-test.dsl.yaml` 只能作为输入或测试样例，不能作为 schema 来源。
- 本 skill 只生成 `.spec.ts`，不执行 Playwright，不运行 `npx playwright test`。

## 执行流程

1. 确认项目根目录是包含 `.codex` 的目录。
2. 根据用户请求定位交付目录；如果未指定，查找项目根目录下的 `*/ui-dsl/ui-test.dsl.yaml`。
3. 如果找到多个 DSL 文件，立即停止执行，并要求用户指定 `delivery-name`。
4. 读取 `.codex/skills/testcase-to-playwright-dsl/references/dsl-schema.md`，确认当前 DSL schema 与任务一致。
5. 运行内置脚本生成 spec：

```bash
python3 .codex/skills/playwright-dsl-to-spec/scripts/convert_dsl_to_spec.py \
  --input ./<delivery-name>/ui-dsl/ui-test.dsl.yaml \
  --output-dir ./<delivery-name>/playwright/tests
```

如果未传入 `--input`，脚本会按 `*/ui-dsl/ui-test.dsl.yaml` 自动查找；找到多个时会失败并提示明确输入路径。

## 生成规则

- 只支持 schema 中定义的 action：`goto`、`click`、`fill`、`select`、`upload`、`wait_for`、`assert_visible`、`assert_text`、`assert_state`。
- 严格校验顶层字段、`meta`、`selectors`、`test_data`、`flows`、`steps`、`todos`、`unsupported_steps` 的字段白名单；出现 schema 外字段时停止。
- `selector.status: "todo"` 的步骤不要生成真实 Playwright 操作，只生成 TODO 注释。
- `selector.status: "confirmed"` 的步骤才生成真实 Playwright locator 操作。
- `goto` 仅在 `url` 非空时生成 `page.goto(url)`；否则生成 TODO 注释。
- `wait_for` 如果没有 target，则生成 `page.waitForTimeout(timeout_ms)`；如果有 target，遵循 selector status 规则。
- `fill`、`select`、`upload` 的 `value` 支持 `${data_key}` 引用顶层 `test_data`。
- `assert_visible` 使用 `toBeVisible`。
- `assert_text` 使用 `toContainText(expected)`；缺少 `expected` 时生成 TODO 注释。
- `assert_state` 使用 `toBeVisible` 作为保守状态断言，并保留 `expected` 为 TODO 注释，等待人工补充具体状态断言。
- `optional: true` 的步骤包裹在 `try/catch` 中，失败时记录 warning，不中断测试。

## 输出约定

- 每个 `flow` 生成一个 `<flow-id>.spec.ts`。
- 输出目录必须是 `./<delivery-name>/playwright/tests/`。
- 不要写入 `.codex/`、`.codex/skills/` 或其他执行产物目录。
- 完成后只简要说明生成的 spec 文件路径；不要在对话中粘贴完整 spec。
