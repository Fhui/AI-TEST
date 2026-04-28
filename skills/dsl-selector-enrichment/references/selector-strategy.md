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

不得点击候选 locator，不得通过候选 locator 改变页面状态。候选 locator 只用于统计匹配数量。

## Flow 执行策略

每个 flow 独立打开页面并执行前置步骤：

1. probe v1 只执行 `goto` 与 `wait_for`
2. `click` 与 `fill` 不执行，只记录 skipped
3. `fill` 引用 `${test_data_key}` 但 test_data 缺失或值为空时，直接跳过并记录
4. unsupported action 或危险语义出现时，中断当前 flow 探测
5. 前置步骤结束后，只对本 flow steps 中用到的 todo target selector 候选做 locator count 探测

不得为了通过而伪造测试数据。probe v1 不真实执行 `fill`，只检查并记录 test_data 缺失情况。

## 分类提示词

当 selector 的 key、description 或 source 包含以下内容时，视为按钮类：

```text
button, 按钮, 点击, 提交, 确认
```

生成：

```text
role=button[name="xxx"]
text=xxx
```

当 selector 的 key、description 或 source 包含以下内容时，视为输入类：

```text
input, 输入, 填写, 手机号, 密码, 名称
```

生成：

```text
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
点击, 输入, 按钮, 提交, 确认
```

只有清理后仍有非空文本时才使用。selector key 只作为兜底来源，使用时将 `_` 和 `-` 替换为空格。

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
