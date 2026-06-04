# PRD Structured Analysis

## Goal

将当前 PRD 与压缩历史上下文建模为可驱动 testpoint 和 testcase-expansion 的系统模型。

## Input

- 当前 PRD
- `complexity-analysis.md`
- `context-reference.md`
- `context-package.json`
- complex pipeline 的 assets / plantuml 中间产物

## Six Modeling Dimensions

### Domain Model

必须识别：

- 对象
- 类型：主体 / 资源 / 关系 / 配置 / 结果
- 生命周期
- 上下游关系
- 是否持久化

### State Machine

必须识别：

- 状态列表
- 状态迁移矩阵
- 非法迁移
- 状态幂等性
- 并发状态

### Behavior Model

每个行为必须拆成：

- 输入
- 前置条件
- 处理逻辑
- 副作用
- 输出

### Data Rules

必须拆为：

- 输入约束
- 业务规则
- 结果约束
- 跨字段约束
- 时间约束
- 幂等约束

### Permission Model

必须包含：

- 身份权限
- 操作权限
- 数据范围权限
- 时间权限

### System Behavior

必须分析：

- 同步 / 异步
- 事务边界
- 重试机制
- 幂等机制
- 失败补偿
- 外部依赖 SLA

## 强制建模问题

进入 testpoint 前必须回答：

1. 核心对象及其生命周期
2. 状态机完整性，含非法迁移
3. 行为语义，含副作用
4. 数据约束，含跨字段
5. 权限控制维度
6. 异步 / 依赖 / 事务机制
7. 失败补偿与幂等机制
8. 边界与极端情况

## Completeness Check

必须检查：

- 状态是否完整
- 行为是否完整
- 数据规则是否完整
- 权限是否完整
- 异常路径是否完整

不完整时必须补充推断或标记 `PRD未说明`。

## Context Rule

历史上下文必须参与需求点拆分、影响范围、规则复用和回归候选判断。

历史资料不得覆盖当前 PRD。冲突必须进入 conflicts / open_questions。

禁止大段复制 context package 原文。
