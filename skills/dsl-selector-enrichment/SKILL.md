---
name: dsl-selector-enrichment
description: 对已生成的 UI DSL 做生产级 selector 补全与校准，支持 dry 候选生成和 probe 受控状态推进两种模式。适用于读取交付目录中的 ui-dsl/ui-test.dsl.yaml，通过 seed selector、安全 click、runtime-confirmed click、reuse-session 和 Playwright locator count 校准 todo selector，并输出 enriched DSL、补全报告和未解决清单；不生成 spec，不运行测试，不做业务断言。
---

# DSL Selector 补全与校准

使用本 skill 对 UI DSL 进行全流程 selector 补全。它不是自动化测试执行，而是受控探测执行：probe 模式允许在严格安全边界内推进页面状态，然后对当前 flow steps 中实际用到的 todo target selector 做 locator count 探测。

禁止生成 Playwright spec，禁止运行 `npx playwright test`，禁止修改 DSL schema，禁止修改 `testcase-to-playwright-dsl` 或 `playwright-dsl-to-spec`，禁止做业务断言。

## 输入与输出

输入：

```bash
./<delivery-name>/ui-dsl/ui-test.dsl.yaml
```

输出：

```bash
./<delivery-name>/ui-dsl/ui-test.enriched.dsl.yaml
./<delivery-name>/ui-dsl/selector-enrichment-report.md
./<delivery-name>/ui-dsl/unresolved-selectors.md
```

禁止覆盖原始 `ui-test.dsl.yaml`。

## 模式

dry 模式是默认模式：

- 不打开浏览器
- 不执行 flow 步骤
- 只生成 selector 候选和报告
- 不把 todo selector 自动改成 confirmed

probe 模式：

- 打开浏览器
- 按 flow 执行受控前置步骤，支持 `goto`、`wait_for` 和受控 `click`
- confirmed selector 可执行安全 click
- probe 已唯一命中并写回 confirmed 的 selector 可执行安全 click
- 第一个 click 支持 limited fallback：`role=button`、`role=link` 或 `text=` 候选唯一命中时可 runtime-confirmed click
- click 成功后等待页面稳定：优先 `networkidle` 3000ms，失败后 fallback 等待 1000ms
- `assert_visible` 不执行断言、不终止 flow，只记录 skipped 并继续
- `fill` 不执行，只记录 skipped
- fill 缺失 `${test_data_key}` 或对应值为空时直接跳过并记录
- 每个 flow 只对本 flow steps 中用到的 todo target selector 候选做 Playwright locator `count()` 探测
- `点击 XXX` 不硬判为 button；候选集至少包含 `role=button[name="XXX"]`、`role=link[name="XXX"]`、`text=XXX`
- 只有 `visible_count == 1` 时才允许 runtime click 或写入 enriched DSL 并标记 `confirmed`
- 可选 `--allow-fuzzy-click` 对第一个 runtime click 增加文本相似度阈值门控，默认阈值为 `0.90`

## 使用方式

先确认项目根目录是包含 `.codex` 的目录。

dry 模式：

```bash
python .codex/skills/dsl-selector-enrichment/scripts/enrich_selectors.py \
  --input ./<delivery-name>/ui-dsl/ui-test.dsl.yaml \
  --output ./<delivery-name>/ui-dsl/ui-test.enriched.dsl.yaml \
  --report ./<delivery-name>/ui-dsl/selector-enrichment-report.md \
  --unresolved ./<delivery-name>/ui-dsl/unresolved-selectors.md
```

probe 模式：

```bash
python .codex/skills/dsl-selector-enrichment/scripts/enrich_selectors.py \
  --mode probe \
  --base-url <page-url> \
  --reuse-session \
  --input ./<delivery-name>/ui-dsl/ui-test.dsl.yaml \
  --output ./<delivery-name>/ui-dsl/ui-test.enriched.dsl.yaml \
  --report ./<delivery-name>/ui-dsl/selector-enrichment-report.md \
  --unresolved ./<delivery-name>/ui-dsl/unresolved-selectors.md
```

probe 全流程探测建议使用 `--reuse-session`。不使用 `--reuse-session` 时，每个 flow 会独立打开 `baseURL`，页面状态不会跨 flow 延续。

移动端 H5 probe 模式：

```bash
python .codex/skills/dsl-selector-enrichment/scripts/enrich_selectors.py \
  --mode probe \
  --base-url <page-url> \
  --reuse-session \
  --mobile \
  --device "iPhone 13" \
  --geolocation "30.2741,120.1551" \
  --permissions geolocation \
  --input ./<delivery-name>/ui-dsl/ui-test.dsl.yaml \
  --output ./<delivery-name>/ui-dsl/ui-test.enriched.dsl.yaml \
  --report ./<delivery-name>/ui-dsl/selector-enrichment-report.md \
  --unresolved ./<delivery-name>/ui-dsl/unresolved-selectors.md
```

默认是 PC context，不会启用移动端模拟。移动端 H5 页面需要显式传 `--mobile`；定位相关页面需要同时传 `--geolocation` 和 `--permissions geolocation`。`--device` 默认是 `iPhone 13`，`--viewport 390x844` 可覆盖 device viewport。

probe 可选增强：

```bash
python .codex/skills/dsl-selector-enrichment/scripts/enrich_selectors.py \
  --mode probe \
  --base-url <page-url> \
  --reuse-session \
  --input ./<delivery-name>/ui-dsl/ui-test.dsl.yaml \
  --output ./<delivery-name>/ui-dsl/ui-test.enriched.dsl.yaml \
  --report ./<delivery-name>/ui-dsl/selector-enrichment-report.md \
  --unresolved ./<delivery-name>/ui-dsl/unresolved-selectors.md \
  --seed-selectors ./seed.yaml \
  --persist-runtime
```

`--seed-selectors` 用于人工锚点，优先级最高。`--reuse-session` 复用同一页面状态执行多个 flow。`--persist-runtime` 会把 runtime-confirmed selector 写回 enriched DSL；默认不写回。第一轮 probe 不建议同时使用 `--persist-runtime`，应在 selector 稳定后再开启。

fuzzy runtime click 推荐参数（安全）：

```bash
python .codex/skills/dsl-selector-enrichment/scripts/enrich_selectors.py \
  --mode probe \
  --base-url <page-url> \
  --reuse-session \
  --allow-fuzzy-click \
  --input ./<delivery-name>/ui-dsl/ui-test.dsl.yaml \
  --output ./<delivery-name>/ui-dsl/ui-test.enriched.dsl.yaml \
  --report ./<delivery-name>/ui-dsl/selector-enrichment-report.md \
  --unresolved ./<delivery-name>/ui-dsl/unresolved-selectors.md
```

`--allow-fuzzy-click` 默认使用 `--fuzzy-click-threshold 0.90`，适合稳定自动化前的保守探测。

fuzzy runtime click 调试参数（探索模式）：

```bash
python .codex/skills/dsl-selector-enrichment/scripts/enrich_selectors.py \
  --mode probe \
  --base-url <page-url> \
  --reuse-session \
  --allow-fuzzy-click \
  --fuzzy-click-threshold 0.80 \
  --input ./<delivery-name>/ui-dsl/ui-test.dsl.yaml \
  --output ./<delivery-name>/ui-dsl/ui-test.enriched.dsl.yaml \
  --report ./<delivery-name>/ui-dsl/selector-enrichment-report.md \
  --unresolved ./<delivery-name>/ui-dsl/unresolved-selectors.md
```

`--fuzzy-click-threshold 0.80` 更适合页面探索、selector 冷启动和移动端导航，但风险更高，不建议与 `--persist-runtime` 同时用于第一轮补全。阈值必须在 `0.0` 到 `1.0` 之间。

如果未传 `--input`，脚本会查找 `*/ui-dsl/ui-test.dsl.yaml`。仅找到一个文件时自动使用该文件并把输出写到同级目录；找到多个文件时停止，要求用户指定 delivery-name 或输入路径。

## probe 安全边界

probe 模式允许执行：

```text
goto
wait_for
受控 click
```

受控 click 必须满足以下条件之一：

- target selector 已经是 confirmed，例如 seed selector
- 当前页面 probe 唯一命中并写回 confirmed
- 当前 flow 的第一个 click 通过 limited fallback 唯一命中 `role=button`、`role=link` 或 `text=` 候选

启用 `--allow-fuzzy-click` 时，第一个 click 仍必须满足唯一可见元素：`visible_count == 1`。只有 fuzzy `score >= --fuzzy-click-threshold` 才允许 runtime click；报告会记录 `score`、`threshold` 和 `fuzzy_allowed`。即使 fuzzy runtime click 成功，也默认不会写回 confirmed，除非显式传入 `--persist-runtime`。

如果 confirmed selector 在执行前匹配数量不是 1，当前 click 必须跳过并记录 unstable confirmed selector，不能中断整个 flow；后续 step 和 flow 结束后的 selector count 探测仍需继续执行。

以下 action 不会真实执行，只会记录为 skipped：

```text
fill
assert_visible
```

其中 `fill` 如果引用 `${test_data_key}` 但 test_data 缺失或值为空，必须直接跳过并在报告中记录原因。

遇到以下步骤或语义，必须中断当前 flow 探测并写入报告：

```text
captcha, 图形验证码, 验证码, 滑块, 极验, 手动验证
delete, 删除, submit, 提交, save, 保存, pay, 支付, 确认订单, publish, 发布, approve, 审批, 关闭权限
unsupported_steps
```

probe 模式不得执行删除、提交、保存、支付、确认订单、发布、审批、关闭权限或其他改变业务状态的操作。

每次 click 报告必须记录：

- click 前 URL
- click 后 URL
- 页面稳定等待方式

## 更新规则

成功：

```yaml
selector: 'role=button[name="登录"]'
status: "confirmed"
```

失败时保持原值：

```yaml
selector: '[data-testid="login_button"]'
status: "todo"
```

以下 selector 必须永远保持 todo：

```text
captcha
验证码
滑块
极验
手动验证
```

详细候选策略见 `references/selector-strategy.md`。
