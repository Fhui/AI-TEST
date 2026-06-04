# Retrieval Trigger Strategy

## Responsibility

`prd-to-xmind-testcases` 只负责触发 `test-knowledge-retrieval`，不负责检索知识库。

## Trigger

如果满足以下条件，必须先触发 `test-knowledge-retrieval`：

- `./<delivery-name>/analysis/context-package.json` 不存在
- 用户未禁用知识库
- `test-knowledge-retrieval` skill 可用

触发时传递：

- 当前 PRD
- `complexity-analysis.md`
- delivery-name
- 输出目录
- retrieval query

## Retrieval Query

至少包含：

- system
- module
- business_objects
- interfaces
- states
- roles
- upstream_dependencies
- downstream_dependencies
- workflow
- journey
- keywords
- risk_keywords

## Failure Flow

顺序固定：

1. 先检查 context package 是否存在
2. 不存在时尝试触发 `test-knowledge-retrieval`
3. 成功则进入 context-consumption
4. retrieval 不可用、失败或用户禁用知识库时进入 degraded context mode
5. degraded context mode 继续后续 testcase pipeline

禁止因为 context package 不存在而直接降级。

## Forbidden

- 直接调用 `test-knowledge-mcp`
- 自行扫描知识库
- 自行读取知识库目录
- 自行伪造 context package
- 自己执行 `search_context` / `read_context_documents`
