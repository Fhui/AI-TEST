# Context Retrieval

## Knowledge Roots

- 默认知识库：`knowledge-base`
- 环境变量知识库：`TEST_KNOWLEDGE_ROOTS`
- 结论：MCP 已通过 allowed roots 检索，存在可用历史资料。

## Retrieval Plan

- System：order
- Module：refund
- Business Objects：退款单、支付单
- Interfaces：POST /refund/apply、GET /refund/status
- States：待处理、已审核、已退款、退款失败
- Roles：买家、财务管理员
- Upstream Dependencies：支付系统
- Downstream Dependencies：通知系统
- Keywords：退款申请、退款状态、支付回滚
- Risk Keywords：幂等、通知重复、异步延迟
- Search Strategy：优先检索同模块历史资料，再检索支付依赖和通知 shared 规则
- Open Questions：需确认退款回调失败后的重试超时时间

## Search Attempts

### Exact Module Search

- Query：`system=order`，`module=refund`，关键词包含退款申请、退款状态、支付回滚。
- Result：strong=3，medium=0，weak=0。
- Decision：used。
- Reason：精确模块已命中历史 PRD 和测试用例。

### System-Level Fallback Search

- 未执行。精确 module 已命中。

### Global Keyword Fallback Search

- 未执行。精确 module 已命中。

### Final Decision

- 使用精确 module 检索结果，不标记 `knowledge_not_found`。

## Retrieval Summary

检索到 3 个强相关资产、2 个中相关资产、1 个弱相关资产。历史退款回调缺陷和通知去重规则对本次回归范围有参考价值。

## Strong Related Assets

- `prd-refund-v2`：退款状态流转历史 PRD，命中模块、状态和接口。
- `tc-refund-main`：退款申请和状态查询历史测试用例 Markdown，存在关联 XMind 预览文件。

## Medium Related Assets

- `shared-notification-dedupe`：通知去重 shared 规则，影响下游通知回归。

## Weak Related Assets

- `prd-coupon-refund`：仅关键词命中，业务对象不同。

## Reused Testcases

- 复用 `tc-refund-main` 中的退款申请成功和重复提交幂等测试点。

## Regression Candidates

- 退款回调幂等：高优先级，命中当前接口和历史线上缺陷。

## Risk Candidates

- 异步回调重试后重复通知。
- 支付成功与退款失败之间出现状态错乱。

## Upstream Dependencies

- 支付回调：影响退款状态流转和重试行为。

## Downstream Dependencies

- 通知系统：接收退款成功或失败消息。

## Shared Rules

- 通知去重规则使用业务 ID 和消息类型作为去重键。

## Conflicts

- 无。

## Open Questions

- 退款回调失败后的预期重试超时时间是多少？
