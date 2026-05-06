# Selector 补全策略

## 候选顺序

必须按以下顺序生成并验证候选：

1. 原始 selector
2. role locator
3. label locator
4. placeholder locator
5. text locator

原始 selector 优先验证，但只有在 probe 模式下 `count == 1` 时才能确认。

## Playwright 探测规则

使用 Playwright locator 的 `count()` 做只读探测：

- `count == 1`：可 confirmed
- `count == 0`：未找到
- `count > 1`：不唯一

候选 locator 默认只用于统计匹配数量。probe 模式允许在安全边界内推进页面状态，但 click 必须受控：

- seed selector 已 confirmed，可执行 click
- 当前页面 probe 已经 `count == 1` 并写回 confirmed 的 selector，可执行 click
- 第一个 click 步骤允许 limited fallback：若 `role=button`、`role=link` 或 `text=` 候选中存在唯一匹配，可临时 click，并记录 `runtime-confirmed`，但不写回 DSL

禁止对 todo selector、模糊 locator 或危险动作执行 click。

## Flow 执行策略

默认建议使用 `--reuse-session` 复用同一个页面状态执行多个 flow。如果不使用 `--reuse-session`，每个 flow 会独立打开 baseURL，页面状态不会跨 flow 延续。

flow 执行前置步骤：

1. 执行 `goto` 与 `wait_for`
2. 对 confirmed selector 执行安全 click
3. 对第一个 click 步骤支持 limited fallback click，不写回 DSL
4. `fill` 不执行，只记录 skipped；如果引用 `${test_data_key}` 但 test_data 缺失或值为空，直接跳过并记录
5. unsupported action 或危险语义出现时，中断当前 flow 探测
6. 前置步骤执行过程中和结束后，只对本 flow steps 中用到的 todo target selector 候选做 locator count 探测

confirmed selector 执行 click 前必须重新 `count()`。如果 `count != 1`，说明 selector 在当前页面不稳定，必须跳过当前 step 并记录原因，不能 abort 当前 flow；后续 step 和 flow 结束后的 selector count 探测继续执行。

不得为了通过而伪造测试数据。probe v1 不真实执行 `fill`，只检查并记录 test_data 缺失情况。

## 点击稳定性

所有成功 click 后必须等待页面稳定，保证下一步 selector count 使用稳定 DOM：

1. 优先等待 `page.wait_for_load_state("networkidle", timeout=3000)`
2. 如果失败，fallback 到 `page.wait_for_timeout(1000)`

每条 click 日志必须包含：

- `before_url`
- `after_url`
- `stable`

`first_click_seen` 只能在 click 真正成功后置为 true。skipped、abort、无 target、非唯一匹配都不能消耗 first click。

## Assert 步骤

`assert_visible` 不执行断言，也不终止 flow。记录：

```text
assert step skipped but flow continues
```

其他 unsupported action 仍按安全策略中断当前 flow。

## Seed Selector

可通过 `--seed-selectors ./seed.yaml` 提供人工锚点：

```yaml
selectors:
  cn_07b18118_button:
    selector: 'role=tab[name="我的"]'
    status: 'confirmed'
```

seed selector 优先级最高，会覆盖 enriched DSL 中同 key selector，并允许 probe 使用该 selector 执行安全 click。

seed 文件中的 `status` 会被强制视为 `confirmed`，因为 seed 的含义就是人工锚点；不要把 seed 当普通候选。

## Runtime Confirmed

第一个 click 步骤支持 limited fallback：

- 仅限 `role=button`、`role=link`、`text=` 候选
- 候选必须 `count == 1`
- 默认只用于本次运行中的临时 click，不写回 DSL

开启 `--persist-runtime` 后，runtime-confirmed selector 会写回 enriched DSL，并标记 `status: confirmed`。第一轮 probe 不建议同时开启 `--persist-runtime`；应先通过报告观察 selector 是否稳定，再在后续轮次开启。

## 共享 Session

可通过 `--reuse-session` 复用同一个浏览器页面状态执行多个 flow。此模式不会在 flow 之间重启浏览器页面，上一个 flow 的页面状态会继续保留；如果 flow 自身包含 `goto`，仍按步骤执行导航。

## 分类提示词

当 selector 的 key、description 或 source 包含以下内容时，视为按钮类：

```text
button, 按钮, 点击, 提交, 确认
```

生成：

```text
role=button[name="xxx"]
role=link[name="xxx"]
text=xxx
```

不要硬判 `点击 xxx` 一定是 button。必须生成候选集，并由 probe 使用真实 DOM 的 `count == 1` 决定最终 confirmed selector。

当 selector 的 key、description 或 source 包含以下内容时，视为输入类：

```text
input, 输入, 填写, 手机号, 密码, 名称
```

生成：

```text
role=textbox[name="xxx"]
label=xxx
placeholder=xxx
```

当 selector 的 key、description 或 source 包含以下内容时，视为 checkbox 类：

```text
checkbox, 勾选, 选中, 协议, 同意
```

生成：

```text
role=checkbox[name="xxx"]
```

当 description 或 source 明确表示显示文案、提示文案或断言文案时，视为文本类：

```text
显示, 提示, 看到, 校验文案
```

生成：

```text
text=xxx
```

## 文本提取

优先来源：

1. `description`
2. `source`

清理动作词：

```text
点击, 输入, 按钮, 提交, 确认, 勾选, 未勾选, 保持
```

只有清理后仍有非空文本时才使用。selector key 只作为兜底来源，使用时将 `_` 和 `-` 替换为空格。

过滤噪声候选：

- `cn_xxxxxxxx` / `cn xxxxxxxx`
- 包含 `并` 的复合句
- 长度大于 12 的文本
- `form element`
- `page element`

## 永远保持 todo

以下目标不得自动 confirmed：

```text
captcha
验证码
滑块
极验
手动验证
```


相关 selector 即使候选有唯一匹配，也必须保持 todo，并写入 unresolved-selectors.md。
