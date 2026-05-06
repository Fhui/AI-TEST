---
name: playwright-result-report
description: 从已有 Playwright 执行产物生成生产级 Markdown 测试报告。用于解析交付目录中的 playwright/results.json、test-results、spec 和 ui-dsl YAML，并把 Playwright 失败关联回 DSL flow、step、source_ts、selector、截图、trace 和 video；不执行测试，不生成 spec，不修改 DSL/spec 文件。
---

# Playwright 结果报告

## 范围

仅在以下场景使用本 skill：

- 读取 `./<delivery-name>/playwright/` 下已有的 Playwright 执行结果。
- 固定读取 `./<delivery-name>/playwright/results.json`，该文件应由 Playwright JSON reporter 生成。
- 优先读取 `./<delivery-name>/ui-dsl/ui-test.enriched.dsl.yaml`，不存在时读取 `./<delivery-name>/ui-dsl/ui-test.dsl.yaml`。
- 生成 `./<delivery-name>/reports/ui-test-report.md`。
- 生成 `./<delivery-name>/reports/artifacts-index.md`。

不要执行 `npx playwright test`，不要生成 spec，不要修改 DSL，不要新增 DSL 字段，不要调用其他 skill。

## 工作流

1. 确认项目根目录是包含 `.codex` 的目录。
2. 确认交付目录。该目录应包含 `playwright/` 或 `ui-dsl/`。
3. 执行：

```bash
python3 .codex/skills/playwright-result-report/scripts/generate_report.py ./<delivery-name>
```

4. 不要在对话中粘贴完整报告。最终只回复：

```text
[✓] Playwright 测试报告生成完成
```

## 报告契约

脚本必须创建：

- `reports/ui-test-report.md`
- `reports/artifacts-index.md`

`ui-test-report.md` 必须包含：

- 总览：总用例数、通过数、失败数、跳过数、通过率。
- 用例执行结果表：每个 DSL flow 一行，包含 `flow_id`、用例名、状态、耗时、文件。
- 失败用例详情：包含 flow 元信息、映射后的失败 step、selector key/value/status、错误信息、裁剪后的 stack、截图、trace、video 和失败原因分类。
- selector 问题汇总：失败次数最多的 selector，以及仍为 `todo` 的 selector。
- 自动生成的建议。

`artifacts-index.md` 必须按 flow 列出：

- spec
- screenshot
- trace
- video

## 映射规则

- 优先使用 `ui-test.enriched.dsl.yaml`；不存在时回退到 `ui-test.dsl.yaml`。
- 从 `selectors[key].selector` 和 `selectors[key].status` 解析 selector。
- 固定从 `./<delivery-name>/playwright/results.json` 读取 Playwright JSON reporter 结果。
- 通过 spec 文件名、测试标题、文件路径或附近注释中的 `flow_id` 将 spec 映射回 DSL。
- `playwright-dsl-to-spec` 生成的 spec 必须在每个 step 前固定输出 `flow_id`、`step_id`、`source_ts`、`selector_key` 注释；本 skill 优先使用这些注释做失败 step 映射。
- 如果 `results.json` 不存在，仍可基于 DSL、`test-results/` 产物和 `playwright/tests/*.spec.ts` 生成降级报告，但不会读取其他 JSON 文件。

## 失败分类

每个失败用例必须分类为以下之一：

- `SELECTOR_NOT_FOUND`
- `MULTIPLE_ELEMENTS`
- `TIMEOUT`
- `NAVIGATION_ERROR`
- `ASSERTION_FAILED`
- `UNRESOLVED_SELECTOR`：映射到的 selector status 为 `todo`
- `UNKNOWN`
