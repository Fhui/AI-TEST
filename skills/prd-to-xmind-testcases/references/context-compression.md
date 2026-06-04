# Context Compression

## Goal

将历史上下文压缩为对当前 PRD 有用的分析输入，避免 token 爆炸和无脑复制历史资料。

## Must Extract

- reusable rules
- reusable testcase patterns
- regression focus
- workflow impact
- risk patterns
- upstream / downstream impact
- conflicts
- open questions

## Forbidden

- 复制完整历史 PRD
- 复制大量历史 testcase 原文
- 复制完整缺陷记录
- 把弱相关资料直接转成回归要求

## Truncation Handling

如果历史 AI source 过大或读取被截断：

- 在 `context_validation.warnings` 中记录
- 只使用已读取且证据明确的内容
- 不假装完整消费
