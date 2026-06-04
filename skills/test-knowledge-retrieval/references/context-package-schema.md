# Context Package 结构规范

`context-package.json` 必须是合法 JSON，并使用以下顶层结构：

```json
{
  "system": "",
  "module": "",
  "version": "",
  "retrieval_summary": {},
  "retrieval_plan": {},
  "search_attempts": [],
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

## 检索尝试条目

用于 `search_attempts`，也可以同步写入 `retrieval_summary.search_attempts`：

```json
{
  "stage": "exact_module",
  "query": {
    "system": "",
    "module": "",
    "business_objects": [],
    "interfaces": [],
    "states": [],
    "roles": [],
    "upstream_dependencies": [],
    "downstream_dependencies": [],
    "keywords": []
  },
  "strong_count": 0,
  "medium_count": 0,
  "weak_count": 0,
  "decision": "fallback_next",
  "reason": ""
}
```

`stage` 允许值：

- `exact_module`
- `system_fallback`
- `global_keywords`

`decision` 允许值：

- `used`
- `fallback_next`
- `no_result`

## 资产条目

用于 `strong_related`、`medium_related`、`weak_related`：

```json
{
  "asset_id": "",
  "title": "",
  "doc_type": "",
  "system": "",
  "module": "",
  "path": "",
  "relatedness": "strong",
  "matched_fields": [],
  "reason": "",
  "summary": "",
  "source_ts": ""
}
```

## 复用测试用例条目

```json
{
  "id": "",
  "title": "",
  "source_asset": "",
  "md_path": "",
  "xmind_path": "",
  "xmind_exists": false,
  "matched_signals": [],
  "reuse_reason": "",
  "summary": ""
}
```

## 风险候选条目

```json
{
  "id": "",
  "risk_type": "",
  "title": "",
  "source_asset": "",
  "matched_signals": [],
  "reason": "",
  "suggested_test_focus": [],
  "needs_confirmation": false
}
```

## 依赖条目

```json
{
  "name": "",
  "direction": "upstream",
  "interfaces": [],
  "source_asset": "",
  "reason": "",
  "test_impact": ""
}
```

## 待确认问题条目

```json
{
  "id": "",
  "question": "",
  "reason": "",
  "blocking": false
}
```
