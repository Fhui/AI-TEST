---
name: dsl-selector-enrichment
description: 对已生成的 UI DSL 做生产级 selector 补全与校准，支持 dry 候选生成和 probe 受控探测两种模式。适用于读取交付目录中的 ui-dsl/ui-test.dsl.yaml，probe v1 仅允许 goto/wait_for 进入可探测页面，再对每个 flow steps 中用到的 todo target selector 做 Playwright locator count 校准，并输出 enriched DSL、补全报告和未解决清单；不生成 spec，不运行测试，不做业务断言。
---

# DSL Selector 补全与校准

使用本 skill 对 UI DSL 进行全流程 selector 补全。它不是自动化测试执行，而是受控探测执行：probe v1 仅允许执行 `goto` 与 `wait_for`，然后对当前 flow steps 中实际用到的 todo target selector 做 locator count 探测。

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
- 按 flow 执行受控前置步骤，但 v1 只执行 `goto` 与 `wait_for`
- `click` 与 `fill` 不执行，只记录 skipped
- fill 缺失 `${test_data_key}` 或对应值为空时直接跳过并记录
- 每个 flow 只对本 flow steps 中用到的 todo target selector 候选做 Playwright locator `count()` 探测
- 只有 `count == 1` 时才写入 enriched DSL 并标记 `confirmed`

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
  --input ./<delivery-name>/ui-dsl/ui-test.dsl.yaml \
  --output ./<delivery-name>/ui-dsl/ui-test.enriched.dsl.yaml \
  --report ./<delivery-name>/ui-dsl/selector-enrichment-report.md \
  --unresolved ./<delivery-name>/ui-dsl/unresolved-selectors.md \
  --base-url <page-url>
```

如果未传 `--input`，脚本会查找 `*/ui-dsl/ui-test.dsl.yaml`。仅找到一个文件时自动使用该文件并把输出写到同级目录；找到多个文件时停止，要求用户指定 delivery-name 或输入路径。

## probe 安全边界

probe 模式只允许执行：

```text
goto
wait_for
```

以下 action 在 probe v1 中不会执行，只会记录为 skipped：

```text
click
fill
```

其中 `fill` 如果引用 `${test_data_key}` 但 test_data 缺失或值为空，必须直接跳过并在报告中记录原因。

遇到以下步骤或语义，必须中断当前 flow 探测并写入报告：

```text
captcha, 图形验证码, 验证码, 滑块, 极验, 手动验证
delete, 删除, submit, 提交, save, 保存, pay, 支付, 确认订单, publish, 发布, approve, 审批, 关闭权限
unsupported_steps
```

probe 模式不得执行删除、提交、保存、支付、确认订单、发布、审批、关闭权限或其他改变业务状态的操作。

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
