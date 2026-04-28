<!--
 * @Author: fenghui ezs1028@dingtalk.com
 * @Date: 2026-04-08 11:21:13
 * @LastEditors: fenghui ezs1028@dingtalk.com
 * @LastEditTime: 2026-04-08 17:43:33
 * @FilePath: /ai-test/.codex/skills/prd-to-xmind-testcases/references/output-template.md
 * @Description: 这是默认设置,请设置`customMade`, 打开koroFileHeader查看配置 进行设置: https://github.com/OBKoro1/koro1FileHeader/wiki/%E9%85%8D%E7%BD%AE
-->
# 输出模板

请严格使用以下 Markdown 结构。层级固定为 `系统 -> 版本 -> 模块 -> 用例`。
不要修改字段名 `tc`、`ts`、`ti`、`tp`。
最终输出文件建议通过 `file-system-mcp` 的 `write_file` 落盘到项目根目录下、与 `.codex` 同级的 `./<delivery-name>/testcase/xmind-testcases.md`。

```md
- 系统, <系统名称或系统名称（待确认）>
  - 版本, <版本号、迭代名或版本名称；不明确时写版本待确认或附加（待确认）>
    - 模块, <模块名称或模块名称（待确认）>
      - tc: <只描述一个核心验证点的用例标题>
        - ts: <步骤1>
          - <步骤1对应的预期结果>
        - ts: <步骤2>
          - <步骤2对应的预期结果>
        - ts: <步骤3>
          - <步骤3对应的预期结果>
        - ti: P0
        - tp: <前置条件；无则写无；需要但无法从PRD确认则写PRD未说明>
      - tc: <另一条用例标题>
        - ts: <步骤1>
          - <步骤1对应的预期结果>
        - ts: <步骤2>
          - <步骤2对应的预期结果>
        - ti: P1
        - tp: 无
    - 模块, <另一个模块名称>
      - tc: <用例标题>
        - ts: <步骤1>
          - <步骤1对应的预期结果>
        - ts: <步骤2>
          - <步骤2对应的预期结果>
        - ti: P2
        - tp: <前置条件>

## 待确认项

- <系统/版本/模块为推断结果时，在这里说明依据与待确认点>
- <需求存在歧义时，在这里列出问题>
- <PRD未说明但可能影响测试设计的内容，在这里明确标注>
```

## 必须遵守的规范

- 每条用例只能归属一个模块。
- `ts` 表示单条步骤，同一用例下每一步都要单独写一条 `ts`。
- `ts` 后直接跟步骤内容，不要写编号。
- 每条 `ts` 下必须紧跟一个子节点 `xxx`。
- 除 `tc:`、`ts:`、`ti:`、`tp:` 外，其他位置不要使用冒号，建议使用逗号。
- `ti` 只能使用 `P0 / P1 / P2 / P3`。
- 仅在确实没有前置条件时写 `tp: 无`。
- 对于缺失事实，必须写 `PRD未说明`，不要自行补全。
- `analysis` 阶段与 `testpoint` 阶段的产物应分别通过 `write_file` 落盘到 `./<delivery-name>/analysis/structured-analysis.md` 与 `./<delivery-name>/analysis/testpoint-model.md`。
- 最终 Markdown 测试用例应通过 `write_file` 存放在项目根目录下、与 `.codex` 同级的 `./<delivery-name>/testcase/` 目录下。
