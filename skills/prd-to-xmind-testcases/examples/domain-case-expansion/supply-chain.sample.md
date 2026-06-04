# Supply Chain Expansion Sample

示例只用于 few-shot，不是主规则。

## Matrix

```text
SKU x 仓库 x 库存状态 x 单据状态 x 入出库方式
```

## Case Groups

- CG-001 正常 SKU 入库成功并增加可用库存
- CG-002 批次 SKU 入库成功并记录批次信息
- CG-003 库存锁定状态下出库占用成功
- CG-004 库存不足时出库失败
- CG-005 调拨单审核通过后源仓扣减、目标仓增加
- CG-006 异常收货时进入异常处理流程
