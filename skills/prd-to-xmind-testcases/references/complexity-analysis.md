# Complexity Analysis

## Goal

在正式 pipeline 前判断 PRD 复杂度，并选择 simple / normal / complex 路径。

## Dimensions

必须综合判断：

- PRD 长度
- 图片数量
- 是否存在流程图 / 时序图
- 状态数量
- 角色数量
- 系统依赖数量
- 是否存在异步 / 事务 / 补偿 / 重试 / 幂等机制
- 是否存在复杂规则、跨字段规则、批量、导入导出、分页、搜索、权限、通知、审批、支付、风控等语义

## Classification

simple：

- 核心流程单一
- 状态、角色、依赖少
- 无复杂异步 / 事务 / 补偿
- 图片不是测试路径建模必需输入

normal：

- 多模块或多分支
- 存在状态、权限、数据规则、异常路径或上下游影响
- 不需要完整图片 / PlantUML 链路即可建模

complex：

- 存在影响测试路径的流程图 / 时序图
- 状态机复杂
- 多角色、多系统、多依赖
- 存在异步、事务、补偿、重试、幂等或外部 SLA
- 规则多且存在组合爆炸风险

## Output

`complexity-analysis.md` 至少包含：

- PRD 名称
- system / module 推断
- complexity
- selected_pipeline
- skipped_phases
- skip_reason
- 关键判断依据
