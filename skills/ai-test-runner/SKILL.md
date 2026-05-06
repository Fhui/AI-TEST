---
name: ai-test-runner
description: 调度 AI 测试流水线，从 PRD Markdown 文件、PRD Markdown 内容或已有 delivery-name 开始，按需串联 prd-to-xmind-testcases、testcase-to-playwright-dsl、dsl-selector-enrichment、playwright-dsl-to-spec 和 playwright-cli。适用于完整执行 PRD 到 Playwright 测试、指定 only/resume 阶段、从已有测试用例/DSL/spec 继续、执行 selector enrichment 或运行 Playwright 的场景。
---

# AI 测试流水线调度器

## 职责范围

仅把本 skill 作为调度器使用。不要重复实现 PRD 分析、测试用例生成、DSL 生成、Selector 补全、Spec 生成或 Playwright 执行逻辑。

各阶段必须委托给已有 skill：

- Stage 1: `prd-to-xmind-testcases`
- Stage 2: `testcase-to-playwright-dsl`
- Stage 4: `dsl-selector-enrichment`
- Stage 3: `playwright-dsl-to-spec`
- Stage 5: `playwright-cli`
- Stage 6: `playwright-result-report`

统一阶段定义：

| Stage | Alias | 中文名称 |
|------|------|----------|
| 1 | prd | PRD 转测试用例 |
| 2 | dsl | 测试用例转 DSL |
| 4 | enrich | Selector 补全 |
| 3 | spec | DSL 转 Playwright Spec |
| 5 | run | 执行 Playwright |
| 6 | report | 生成测试报告 |

默认完整执行顺序：

```text
1 -> 2 -> 4 -> 3 -> 5 -> 6
```

如果用户明确不需要 Selector 补全：

```text
1 -> 2 -> 3 -> 5 -> 6
```

## 前置检查

1. 确认项目根目录是当前包含 `.codex` 的目录。
2. 执行任何工作前，先解析用户要求的阶段列表。
3. 如果从 Stage 2 或更后阶段开始，先解析 `delivery-name`。
4. 每个阶段执行前检查必要的上游产物。
5. 缺少必要输入时必须停止并询问用户。不要猜测。

需要稳定检查时，优先使用辅助脚本：

```bash
python3 .codex/skills/ai-test-runner/scripts/run_pipeline.py \
  --stages 1,2,4,3,5,6 \
  --delivery <delivery-name> \
  --base-url <url>
```

脚本负责校验阶段顺序、项目根目录、`delivery-name`、baseURL 要求、上游产物和覆盖风险，并输出调度计划；它不实现已有 skill 的转换逻辑。

如果需要生成流水线调度报告，传入 `--write-report`：

```bash
python3 .codex/skills/ai-test-runner/scripts/run_pipeline.py \
  --delivery <delivery-name> \
  --stages 2,4,3,5 \
  --selector-mode dry \
  --write-report
```

## 输入

支持以下任一输入：

- PRD Markdown 文件路径，例如 `./prd/login-flow.md`
- 用户直接提供的 PRD Markdown 内容
- 已存在的 `delivery-name`，用于恢复执行或从中间阶段开始

当 Stage 1 从 PRD 开始执行时，由 `prd-to-xmind-testcases` 决定 `delivery-name`。Stage 1 完成后，再根据生成的 `testcase/xmind-testcases.md` 识别交付目录。

当从 Stage 2 或更后阶段开始时，必须要求用户提供 `delivery-name`，除非能从所需上游产物自动推断出唯一候选交付目录。如果存在多个候选目录，必须停止并要求用户指定 `delivery-name`。

## 阶段选择

支持精确阶段表达：

```text
only 1
only 2
only 3
only 4
only 5
only 6
only prd
only dsl
only enrich
only spec
only run
only report
1
1,2
1,2,3
1,2,4,3
1,2,4,3,5
1,2,4,3,5,6
prd,dsl,enrich,spec,run,report
PRD转测试用例,测试用例转DSL,Selector补全,生成Spec,执行Playwright,生成测试报告
1,dsl,enrich,5,report
resume from 2
resume from 3
resume from 4
resume from 5
resume from 6
resume from spec
resume from enrich
resume from report
```

支持自然语言映射：

- `只生成测试用例` -> `only 1`
- `生成测试用例和 DSL` -> `1,2`
- `只把 DSL 转 spec` -> `only 3`
- `只执行 Playwright` -> `only 5`
- `只生成报告` -> `only report`
- `从已有 DSL 开始执行` -> `resume from 3`
- `从已有 spec 开始执行` -> `resume from 5`
- `生成报告` -> `report`
- `执行测试` -> `run`
- `补全selector` -> `enrich`
- `生成dsl` -> `dsl`
- `生成spec` -> `spec`
- `PRD解析` -> `prd`

对于 `resume from N`，使用从 `N` 开始的默认完整顺序：

- `resume from 2` 或 `resume from dsl` -> `2,4,3,5,6`
- `resume from 4` 或 `resume from enrich` -> `4,3,5,6`
- `resume from 3` 或 `resume from spec` -> `3,5,6`
- `resume from 5` 或 `resume from run` -> `5,6`
- `resume from 6` 或 `resume from report` -> `6`

如果用户禁用 Selector 补全，则从完整流程或恢复流程中移除 Stage 4。

## baseURL 规则

如果 Stage 4 以 `probe` 模式运行，或需要执行 Stage 5，但用户没有提供 `baseURL`，必须停止并询问 `baseURL`。

不要猜测 `baseURL`。没有 `baseURL` 时，不要继续执行 Playwright。生成调度计划或 pipeline-run-report 时，可以把 Stage 5 标记为 `blocked`，但不能运行 Playwright。

Stage 1、Stage 2、Stage 3，以及 Stage 4 的 `dry` 模式不需要 `baseURL`。

`--selector-mode` 未显式指定时，只在阶段正好为完整链路 `1 -> 2 -> 4 -> 3 -> 5 -> 6` 且提供 `baseURL` 时，自动使用 `probe`。其他阶段组合一律默认 `dry`。

## 中间产物检查

每个阶段执行前，检查必要输入是否存在：

- Stage 2 需要 `./<delivery-name>/testcase/xmind-testcases.md`
- Stage 3 需要 `./<delivery-name>/ui-dsl/ui-test.dsl.yaml`
- 只有当 `./<delivery-name>/ui-dsl/ui-test.enriched.dsl.yaml` 存在，且用户明确要求使用 enriched DSL 时，Stage 3 才能使用 enriched DSL
- Stage 4 需要 `./<delivery-name>/ui-dsl/ui-test.dsl.yaml`
- Stage 5 至少需要一个 `./<delivery-name>/playwright/tests/*.spec.ts`
- Stage 6 需要 `./<delivery-name>/playwright/results.json`

如果产物缺失，必须停止，并说明应该先执行哪个阶段。

不要覆盖已有产物，除非用户明确允许覆盖。已有产物包括：

- Stage 1: `./<delivery-name>/testcase/xmind-testcases.md`
- Stage 2: `./<delivery-name>/ui-dsl/ui-test.dsl.yaml`
- Stage 4: `./<delivery-name>/ui-dsl/ui-test.enriched.dsl.yaml`, `selector-enrichment-report.md`, `unresolved-selectors.md`
- Stage 3: `./<delivery-name>/playwright/tests/*.spec.ts`
- Stage 5: `./<delivery-name>/playwright/results.json`
- Stage 6: `./<delivery-name>/reports/ui-test-report.md`

Stage 4 为 `dry` 模式时，允许覆盖 `selector-enrichment-report.md` 和 `unresolved-selectors.md`，不要因为这两个报告已存在而阻断。`ui-test.enriched.dsl.yaml` 仍按普通输出产物处理。

## Pipeline 报告

`ai-test-runner` 负责生成 `pipeline-run-report.md`，用于记录流水线阶段、前置检查、调度命令和产物索引。

默认报告路径：

```text
./<delivery-name>/reports/pipeline-run-report.md
```

如果用户通过 `--report-path` 指定路径，使用用户指定路径。

如果当前从 Stage 1 开始，且 `delivery-name` 尚未生成，不要强行写报告；只在控制台提示：

```text
Stage 1 完成后才能确定 delivery-name 并生成 pipeline-run-report.md
```

报告必须包含：

- 基本信息：项目根目录、delivery-name、执行阶段、selector mode、是否使用 enriched DSL、baseURL 是否提供、是否 overwrite
- 阶段计划：Stage、Alias、中文、状态、输入、输出
- 前置检查结果：`.codex`、delivery-name、上游产物、输出产物、overwrite、Stage 5 baseURL 或 Playwright 配置
- 调度命令
- 产物索引
- 下一步建议

状态只使用：

```text
pending
ready
skipped
blocked
failed
```

注意区分报告职责：

- `ai-test-runner` 只生成 `pipeline-run-report.md`，记录流水线调度计划、检查结果、命令和产物路径。
- `playwright-result-report` 负责生成 `ui-test-report.md`，用于分析 Playwright 执行结果、失败用例、截图、trace 和 selector 问题。

两者不能混淆。不要生成 `ui-test-report.md`，不要解析 `playwright/results.json`，不要分析失败用例。

## 阶段调度

### Stage 1：PRD 转测试用例

使用 `prd-to-xmind-testcases`。

输入：

- PRD Markdown 文件路径，或
- PRD Markdown 内容

输出：

```text
./<delivery-name>/testcase/xmind-testcases.md
```

完成后输出：

```text
[✓] Stage 1 PRD 转测试用例完成
```

### Stage 2：测试用例转 UI DSL

使用 `testcase-to-playwright-dsl`。

输入：

```text
./<delivery-name>/testcase/xmind-testcases.md
```

输出：

```text
./<delivery-name>/ui-dsl/ui-test.dsl.yaml
```

完成后输出：

```text
[✓] Stage 2 测试用例转 DSL 完成
```

### Stage 4：Selector 补全

使用 `dsl-selector-enrichment`。

默认模式为 `dry`。只有当用户显式要求 probe，或调度完整链路 `1 -> 2 -> 4 -> 3 -> 5 -> 6` 且提供 `baseURL` 时，才使用 `probe` 模式，并且必须要求 `baseURL`。

输入：

```text
./<delivery-name>/ui-dsl/ui-test.dsl.yaml
```

输出：

```text
./<delivery-name>/ui-dsl/ui-test.enriched.dsl.yaml
./<delivery-name>/ui-dsl/selector-enrichment-report.md
./<delivery-name>/ui-dsl/unresolved-selectors.md
```

完成后输出：

```text
[✓] Stage 4 Selector 补全完成
```

### Stage 3：UI DSL 转 Playwright Spec

使用 `playwright-dsl-to-spec`。

输入：

```text
./<delivery-name>/ui-dsl/ui-test.dsl.yaml
```

如果 `ui-test.enriched.dsl.yaml` 存在，且用户明确要求使用 enriched，则将它作为 Stage 3 输入。

如果阶段列表包含 Stage 4，且 Stage 4 位于 Stage 3 之前，并且 `ui-test.enriched.dsl.yaml` 已存在，Stage 3 默认使用 enriched DSL。只有当用户显式禁用 enriched DSL 时，才使用原始 `ui-test.dsl.yaml`。

输出：

```text
./<delivery-name>/playwright/tests/*.spec.ts
```

完成后输出：

```text
[✓] Stage 3 DSL 转 Playwright Spec 完成
```

### Stage 5：执行 Playwright

使用 `playwright-cli` 的指导，并执行：

```bash
PLAYWRIGHT_HTML_OPEN=never PLAYWRIGHT_JSON_OUTPUT_NAME=./<delivery-name>/playwright/results.json npx playwright test ./<delivery-name>/playwright/tests --reporter=json
```

执行本阶段前必须要求 `baseURL`。如果项目通过环境变量读取 baseURL，应保持一致传入，例如：

```bash
BASE_URL=<baseURL> PLAYWRIGHT_HTML_OPEN=never PLAYWRIGHT_JSON_OUTPUT_NAME=./<delivery-name>/playwright/results.json npx playwright test ./<delivery-name>/playwright/tests --reporter=json
```

Stage 5 必须固定启用 Playwright JSON reporter，并固定输出到 `./<delivery-name>/playwright/results.json`，供 `playwright-result-report` 读取。

完成后输出：

```text
[✓] Stage 5 Playwright 执行完成
```

### Stage 6：生成测试报告

使用 `playwright-result-report`。

输入：

```text
./<delivery-name>/playwright/results.json
```

输出：

```text
./<delivery-name>/reports/ui-test-report.md
```

`ai-test-runner` 只负责在调度计划和 pipeline-run-report 中记录 Stage 6 的建议命令与产物路径，不直接生成 `ui-test-report.md`，不解析 Playwright `results.json`。

完成后输出：

```text
[✓] Stage 6 测试报告生成完成
```

## 状态输出

每个阶段完成后，输出对应状态：

```text
[✓] Stage 1 PRD 转测试用例完成
[✓] Stage 2 测试用例转 DSL 完成
[✓] Stage 4 Selector 补全完成
[✓] Stage 3 DSL 转 Playwright Spec 完成
[✓] Stage 5 Playwright 执行完成
[✓] Stage 6 测试报告生成完成
```

跳过某阶段时，输出：

```text
[-] Stage X 已跳过，原因 <reason>
```

某阶段失败时，输出：

```text
[✗] Stage X 失败，原因 <reason>
```

对话输出保持简短。除非用户明确要求查看内容，否则不要在对话中粘贴生成的测试用例、DSL 或 spec 全文。

禁止事项：

- `ai-test-runner` 自身不要生成 `ui-test-report.md`
- 不要解析 Playwright `results.json`
- 不要分析失败用例
- 不要修改其他 skill
- 不要执行 `npx playwright test`
- 不要把 `ai-test-runner` 变成业务转换器
