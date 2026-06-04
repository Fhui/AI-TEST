# Loading Strategy

## Core Principle

`SKILL.md` 是 phase orchestration contract。

`loading-strategy.md` 是 phase reference loading strategy。

`references/*.md` 是 detailed execution rules。

references 不是全局上下文。每个 phase 必须只读取当前 phase 需要的 references。

禁止一次性读取全部 references、全部 domain profiles 或全部 examples。

## Runtime Semantics

当前 phase 必须优先读取本文件中对应 phase 的 `required` references。

`optional` references 只有在当前 phase 明确命中相关语义时才允许读取。

`forbidden` references 当前 phase 禁止读取，即使文件存在，也不能加入当前 phase 上下文。

loading strategy 的目标：

- 减少无关上下文
- 避免 token 污染
- 降低跨 phase 注意力泄漏
- 保持 phase 职责边界清晰

## Loading Levels

```yaml
loading_levels:
  required:
    meaning: 当前 phase 必须读取
    behavior: 缺少 required reference 时，不要继续该 phase
  optional:
    meaning: 当前 phase 明确命中相关语义时才允许读取
    behavior: 未命中语义时禁止为了“可能有帮助”而读取
  forbidden:
    meaning: 当前 phase 禁止读取
    behavior: 即使文件存在，也不能加入当前 phase 上下文
```

## Phase-aware Loading

按 phase 加载 references。不要跨 phase 预加载。

## Phase Loading Matrix

```yaml
phases:
  complexity-analysis:
    required:
      - complexity-analysis.md
    optional:
      - workflow-modeling.md
    forbidden:
      - testcase-expansion.md
      - xmind-output-format.md
      - pipeline-output-schema.md
      - domain-expansion/*
    reason: complexity-analysis 不应该提前进入 testcase generation

  context-retrieval:
    required:
      - retrieval-trigger-strategy.md
      - workflow-modeling.md
    optional: []
    forbidden:
      - testpoint-modeling.md
      - testcase-expansion.md
      - xmind-output-format.md
      - pipeline-output-schema.md
      - domain-expansion/*
    reason: retrieval phase 不负责 testcase generation

  context-consumption:
    required:
      - context-consumption.md
      - context-validation.md
      - context-compression.md
      - traceability-rules.md
    optional:
      - workflow-modeling.md
    forbidden:
      - testcase-expansion.md
      - xmind-output-format.md
      - domain-expansion/*

  analysis-lite:
    required:
      - analysis-lite.md
      - traceability-rules.md
    optional:
      - workflow-modeling.md
    forbidden:
      - plantuml
      - testpoint-modeling.md
      - domain-expansion/*

  assets:
    required:
      - capability-abstraction.md
    optional: []
    forbidden:
      - testcase-expansion.md
      - pipeline-output-schema.md
      - domain-expansion/*

  plantuml:
    required:
      - capability-abstraction.md
    optional:
      - workflow-modeling.md
    forbidden:
      - testpoint-modeling.md
      - testcase-expansion.md
      - xmind-output-format.md
      - domain-expansion/*

  analysis:
    required:
      - prd-structured-analysis.md
      - workflow-modeling.md
      - traceability-rules.md
    optional:
      - context-consumption.md
    forbidden:
      - xmind-output-format.md
      - pipeline-output-schema.md

  testpoint:
    required:
      - testpoint-modeling.md
      - traceability-rules.md
    optional:
      - workflow-modeling.md
    forbidden:
      - xmind-output-format.md
      - pipeline-output-schema.md
      - domain-expansion/*

  testcase-expansion:
    required:
      - testcase-expansion.md
      - traceability-rules.md
      - loading-strategy.md
      - domain-expansion/generic.md
    optional:
      - selected_domain_profiles
      - workflow-modeling.md
    forbidden:
      - plantuml
      - capability-abstraction.md
      - context-validation.md

  testcase:
    required:
      - xmind-output-format.md
      - pipeline-output-schema.md
      - traceability-rules.md
    optional:
      - workflow-modeling.md
    forbidden:
      - complexity-analysis.md
      - context-validation.md
      - domain-expansion/*
```

## Domain Profile Loading

domain profiles 不是默认全量加载。

默认只读取 `references/domain-expansion/generic.md`。

只有 system、module、workflow、business objects、terminology 明确命中时，才允许读取额外 profile。

profile resolution 必须使用 `references/profile-selection-heuristic.md`，并将结果写入 `selected_domain_profiles`。

```yaml
profile_resolution:
  source:
    - profile-selection-heuristic.md
  output:
    variable: selected_domain_profiles
    fields:
      - selected_domain_profiles
      - selection_reason
      - selection_evidence
```

```yaml
domain_profile_loading:
  default:
    required:
      - generic.md
  limits:
    max_system_profiles: 1
    max_business_profiles: 2
  selection_priority:
    - exact_system_match
    - exact_module_match
    - terminology_match
    - workflow_match
    - business_object_match
    - fallback_generic
  record_in_output:
    file: testcase-expansion.md
    fields:
      - selected_domain_profiles
      - selection_reason
  forbidden:
    - load_all_profiles
    - unrelated_cross_domain_profiles
    - speculative_profile_loading
```

## Example Loading

`examples/` 不是默认上下文。

只有当前 phase 明确需要 few-shot pattern 时，才允许读取 example。

Phase 4.5 `testcase-expansion` 是 examples 的主要消费阶段。

```yaml
example_loading:
  default:
    enabled: false
  allowed_phases:
    - testcase-expansion
  max_examples: 2
  selection_priority:
    - same_system
    - same_module
    - same_workflow
    - same_business_object
  forbidden_phases_for_domain_case_expansion:
    - complexity-analysis
    - context-retrieval
    - context-consumption
    - analysis
  forbidden:
    - load_all_examples
    - cross_domain_example_mixing
    - examples_as_primary_rules
```

## Operational Notes

If a phase needs a reference that is forbidden by this file, stop and reassess the phase boundary instead of loading it.

If uncertain whether a reference is optional or forbidden, prefer not loading it and write the uncertainty to the current phase output.
