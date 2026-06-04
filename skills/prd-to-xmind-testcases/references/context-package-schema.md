# Context Package Schema

`context-package.json` 至少包含：

```json
{
  "system": "",
  "module": "",
  "retrieval_summary": {},
  "workflow_hits": [],
  "strong_related": [],
  "medium_related": [],
  "weak_related": [],
  "reused_testcases": [],
  "regression_candidates": [],
  "risk_candidates": [],
  "upstream_dependencies": [],
  "downstream_dependencies": [],
  "shared_rules": [],
  "conflicts": [],
  "open_questions": []
}
```

## Source Rules

- `.md` 是 AI source，可以被读取和压缩
- `.xmind` 只能作为 human preview / traceability path
- 历史 testcase Markdown 路径写入 `ai_source_path`
- XMind 路径写入 `xmind_path`

## Consumption Rules

只消费结构化上下文，不把完整 context package 镜像复制到 pipeline-output。
