# XMind Output Format

## Format

Markdown 必须对齐知识库历史测试用例格式。

结构：

```md
# <需求名称>

## <版本名称>

### <端 / 系统 / 一级业务域>

- <业务域>

  - <功能页 / 场景 / 子模块>

    - tc: <用例标题>

      - ts: <步骤>

        - <预期结果>

      - ti: P0

      - tp: <前置条件>
```

## Rules

- 用例节点只允许使用 `tc / ts / ti / tp`
- `ts` 后直接跟步骤，不写编号
- 每条 `ts` 下必须有预期结果子节点
- `ti` 只能是 `P0 / P1 / P2 / P3`
- 无前置条件时写 `tp: 无`
- 信息缺失时写 `PRD未说明`

## Historical Regression Layer

命中知识库后需要回归的用例，只允许在同一棵树中新增一个 `历史回归` 层级。

禁止：

- 额外新增第二棵系统树
- 使用 `- 系统, ... / - 版本, ... / - 模块, ...`
- 在 Markdown 中输出 `case_type / context_source / ai_source_path / xmind_path / source_reason`

这些追踪字段必须进入 JSON / CSV / pipeline-output.json。
