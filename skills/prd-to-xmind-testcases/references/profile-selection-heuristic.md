# Profile Selection Heuristic

## Core Principle

profile selection 的目标是根据当前 PRD、`complexity-analysis.md`、`context-reference.md` 与 `context-package.json` 中的系统、模块、workflow、业务对象和术语，选择最相关的 domain profiles。

选择结果用于 Phase 4.5 `testcase-expansion` 的 `selected_domain_profiles`，驱动 testcase expansion matrix 的领域维度补充。

本 heuristic 是 rule-based，不使用 embedding、vector search、TF-IDF 或外部 RAG。

禁止：

- 加载全部 domain profiles
- 在无法判断领域时加载多个 profile
- 用历史示例反推 profile 选择
- 把 profile 选择结果当作业务事实覆盖当前 PRD

## Selection Priority

```yaml
selection_priority:
  - exact_system_match
  - exact_module_match
  - workflow_match
  - business_object_match
  - terminology_match
  - keyword_density_match
  - related_profile_match
  - fallback_generic
```

## Scoring Rules

```yaml
scores:
  exact_system_match: 100
  exact_module_match: 60
  workflow_match: 30
  business_object_match: 20
  terminology_match: 10
  keyword_density_match: 5
  related_profile_match: 15
```

说明：

- score 只用于 heuristic ranking，不代表精确数学计算。
- score 用于表达优先级关系，帮助 Codex 稳定排序。
- 当前 PRD 明确语义优先于历史上下文语义。
- `complexity-analysis.md` 中的 system/module 优先级高于正文散落关键词。

## Selection Rules

### Rule 1: System First

如果 `complexity-analysis.md` 明确识别出 `system`，必须优先匹配 profile frontmatter 中的 `match_systems`。

命中 `match_systems` 的 system profile 优先于 business / workflow profile。

### Rule 2: Module Match

如果 PRD 标题、模块名称、需求列表或 `complexity-analysis.md` 中的 module 命中 profile frontmatter 的 `match_modules`，增加优先级。

模块命中不能覆盖 system 命中，但可以在同 system 下提升 profile 排序。

### Rule 3: Workflow Match

如果当前 PRD、`workflow_hits`、`context-reference.md` 或 `testpoint-model.md` 中的 workflow / journey 命中 `match_workflows`，增加优先级。

workflow 命中常用于选择 business profile 或 system profile 的 `related_profiles`。

### Rule 4: Business Object Match

如果领域对象、业务对象、数据对象命中 `match_business_objects`，增加优先级。

业务对象示例：

- 订单
- 支付
- 库存
- 照片
- 裁剪结果
- 审核单
- 单据

### Rule 5: Terminology and Keyword Match

如果 PRD 中反复出现 profile frontmatter 的 `match_keywords`，可以作为 terminology / keyword density 信号。

`keyword_density_match` 表示：PRD 中 profile 关键词的出现频率和覆盖度信号。

关键词只提供弱信号，不能单独导致多个 profile 同时加载。

### Rule 6: Score Ordering

如果多个 profile 命中，必须按 score 从高到低排序。

### Rule 7: Priority Tie-breaker

如果多个 profile score 相同，使用 profile frontmatter 中的 `priority` 排序。

priority 更高的 profile 排在前面。

### Rule 8: Profile Combination

允许组合：

- `generic`
- 最多 1 个 system profile
- 最多 1-2 个 business / workflow profiles

system profile 命中后，可以读取其 `related_profiles`，但仍必须受 profile limits 约束。

### Rule 9: Single System Profile

禁止多个 system profiles 同时加载。

如果多个 system profiles 命中：

1. 优先选择 exact system match。
2. 如果都是弱命中，按 score 排序。
3. score 相同时按 `priority` 排序。
4. 未被选择的 system profile 只能写入 open questions 或 selection notes，不能加载。

## Profile Limits

```yaml
limits:
  max_system_profiles: 1
  max_business_profiles: 2
  always_include:
    - generic
```

说明：

- `generic` 必须始终包含。
- `generic` 是 fallback / baseline profile，不代表加载所有领域规则。
- system profile 数量最多 1 个。
- business / workflow profile 总数最多 2 个。

## Fallback Strategy

如果 system、module、workflow、business object 均未命中任何 profile：

```yaml
selected_domain_profiles:
  - generic
```

禁止：

- 无法判断时加载多个 profile
- 为了“可能有帮助”加载跨领域 profile
- 仅凭单个弱关键词加载 system profile

如果只有弱关键词命中，但 system/module/workflow/business object 均无法确认，仍使用 `generic`，并把不确定性写入 `selection_reason` 或 open questions。

## Selection Output

Phase 4.5 `testcase-expansion.md` 必须输出：

```yaml
selected_domain_profiles:
  - generic
  - watchPic
selection_reason:
  - exact_system_match: watchPic
  - exact_module_match: 自助裁剪
  - workflow_match: AI裁剪
selection_evidence:
  systems:
    - watchPic
  modules:
    - 自助裁剪
  workflows:
    - AI裁剪
  business_objects:
    - 照片
    - 裁剪结果
```

字段说明：

- `selected_domain_profiles`: 最终允许加载的 profile id 列表，必须包含 `generic`。
- `selection_reason`: 可读解释，用于 review。
- `selection_evidence`: 从当前 PRD、complexity-analysis、context package 提取的证据。

## Review Rules

如果选择结果存在不确定性，必须在 `testcase-expansion.md` 记录：

- ambiguous_profiles
- skipped_profiles
- skip_reason

禁止通过加载更多 profile 来掩盖不确定性。
