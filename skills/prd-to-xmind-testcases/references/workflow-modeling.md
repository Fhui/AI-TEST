# Workflow Modeling

## Concepts

workflow / journey 表示跨步骤、跨对象、跨状态或跨系统的业务路径。

示例抽象：

- 创建 -> 审核 -> 发布
- 下单 -> 支付 -> 履约 -> 售后
- 上传 -> 处理 -> 预览 -> 归档

## Retrieval

retrieval query 必须提取 workflow / journey。

workflow hit 必须写入 `workflow_hits`。

## Regression

workflow 命中历史资料时，优先进入 regression_candidates。

## Expansion

workflow 必须展开：

- 主流程
- 分支流程
- 回退流程
- 失败流程
- 重试流程
- 跨系统流程
- 异步流程
- 补偿流程

## Open Questions

workflow 无法确认时，必须标记 `workflow 未明确`。
