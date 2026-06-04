---
name: prd-to-xmind-testcases
description: 将 Markdown PRD 按复杂度自适应解析为可导入 XMind 的测试用例树，并输出 Markdown、JSON、CSV 与 pipeline-output.json。适用于读取当前 PRD，按需触发 test-knowledge-retrieval，消费 context package，执行 analysis-lite 或完整系统建模，经过 testpoint 与 testcase-expansion 矩阵展开后生成测试用例。
---

# PRD 转 XMind 测试用例

## 目标

将当前 PRD 转换为可导入 XMind 的测试用例树，并同步输出 JSON、CSV、pipeline-output.json，供 UI DSL、Playwright、API 自动化和 Traceability 后续链路使用。
本 skill 采用复杂度自适应 pipeline：

- simple：`analysis-lite -> testcase`
- normal：`analysis -> testpoint -> testcase-expansion -> testcase`
- complex：`assets -> plantuml -> analysis -> testpoint -> testcase-expansion -> testcase`

所有 pipeline 前置执行：

- `Phase 0: complexity-analysis`
- `Phase 0.3: context-retrieval`
- `Phase 0.5: context-consumption`

## 职责边界

负责：

- 读取当前 Markdown PRD
- 判断复杂度并选择 pipeline
- 在需要历史上下文时触发 `test-knowledge-retrieval`
- 消费 `context-retrieval.md` 与 `context-package.json`
- 生成 `context-reference.md`
- 执行轻量分析或完整结构化分析
- 将测试点展开为 testcase expansion matrix
- 生成 Markdown / JSON / CSV / pipeline-output.json

不负责：

- 扫描知识库
- 直接调用 `test-knowledge-mcp`
- 直接读取知识库根目录
- 自己做 metadata 提取、召回、rerank
- 解析 `.xmind`
- 生成自动化脚本
- 执行测试

## Capability 强约束

必须读取 [references/capability-abstraction.md](references/capability-abstraction.md)。
文件系统操作必须通过 filesystem capability：

- `mkdir`
- `write_file`
- `read_file`
- `list_dir`

图片处理必须通过 image capability：

- `download_image`
- `classify_image`
- `ocr_image`
- `extract_flow_elements`

禁止：

- 直接写文件、创建目录、读取目录
- 直接下载图片、直接 OCR、直接图片分类
- 在 capability 不可用时自行兜底

## Knowledge Retrieval 依赖

必须读取：

- [references/retrieval-trigger-strategy.md](references/retrieval-trigger-strategy.md)
- [references/context-package-schema.md](references/context-package-schema.md)
- [references/context-validation.md](references/context-validation.md)
- [references/context-consumption.md](references/context-consumption.md)
- [references/context-compression.md](references/context-compression.md)

调用链路只能是：

```text
prd-to-xmind-testcases
-> test-knowledge-retrieval
-> test-knowledge-mcp
-> context-package.json
-> context-consumption / analysis / testpoint / testcase
```

禁止：

```text
prd-to-xmind-testcases -> test-knowledge-mcp
```

`.md` 是 AI source。`.xmind` 只能作为 human preview / traceability 路径。

## 输出路径规则

所有运行产物必须写入项目根目录下、与 `.codex` 同级的 `./<delivery-name>/`，禁止写入 `.codex/` 或 skill 目录。

- `./<delivery-name>/assets/`
- `./<delivery-name>/plantuml/`
- `./<delivery-name>/analysis/complexity-analysis.md`
- `./<delivery-name>/analysis/context-retrieval.md`
- `./<delivery-name>/analysis/context-package.json`
- `./<delivery-name>/analysis/context-reference.md`
- `./<delivery-name>/analysis/analysis-lite.md`
- `./<delivery-name>/analysis/structured-analysis.md`
- `./<delivery-name>/analysis/testpoint-model.md`
- `./<delivery-name>/analysis/testcase-expansion.md`
- `./<delivery-name>/testcase/xmind-testcases.md`
- `./<delivery-name>/testcase/xmind-testcases.json`
- `./<delivery-name>/testcase/xmind-import.csv`
- `./<delivery-name>/pipeline-output.json`

## Pipeline Overview

所有 phase 必须遵守 [references/loading-strategy.md](references/loading-strategy.md)，只读取当前 phase 允许的 references。

必须先执行 `Phase 0 -> Phase 0.3 -> Phase 0.5`，再按复杂度执行核心阶段：

- simple：2 phase
  - `analysis-lite`
  - `testcase`
- normal：4 phase
  - `analysis`
  - `testpoint`
  - `testcase-expansion`
  - `testcase`
- complex：6 phase
  - `assets`
  - `plantuml`
  - `analysis`
  - `testpoint`
  - `testcase-expansion`
  - `testcase`

`testpoint` 不是最终 testcase。normal / complex 禁止跳过 `testcase-expansion`。

## Phase 0: complexity-analysis

当前 phase 必须遵守 `references/loading-strategy.md` 中 `complexity-analysis` 的 loading strategy。

读取 [references/complexity-analysis.md](references/complexity-analysis.md)。

目标：

- 读取 PRD
- 判断复杂度：`simple / normal / complex`
- 选择 pipeline
- 记录跳过阶段和原因

输出：

- `./<delivery-name>/analysis/complexity-analysis.md`

必须包含：

- PRD 名称
- system / module 推断
- 图片数量
- 流程图 / 时序图可能性
- 状态、角色、依赖、异步、事务、补偿、复杂规则判断
- complexity
- selected_pipeline
- skipped_phases
- skip_reason

## Phase 0.3: context-retrieval

当前 phase 必须遵守 `references/loading-strategy.md` 中 `context-retrieval` 的 loading strategy。

读取 [references/retrieval-trigger-strategy.md](references/retrieval-trigger-strategy.md) 与 [references/workflow-modeling.md](references/workflow-modeling.md)。

目标：

- 基于当前 PRD 和 `complexity-analysis.md` 构建 retrieval query
- 调用/切换 `test-knowledge-retrieval`
- 校验 `context-retrieval.md` 与 `context-package.json` 是否存在

retrieval query 至少包含：system、module、business_objects、interfaces、states、roles、upstream/downstream_dependencies、workflow / journey、keywords、risk_keywords。

如果 `context-package.json` 不存在、非法、过期，或当前 PRD 与 context package 不匹配，必须重新执行 `test-knowledge-retrieval`。

执行 retrieval 时至少传递：当前 PRD、`complexity-analysis.md`、delivery-name、输出目录、retrieval query。

输出：

- `./<delivery-name>/analysis/context-retrieval.md`
- `./<delivery-name>/analysis/context-package.json`

Phase 0.3 只负责构建 query、调用 retrieval skill、校验 retrieval 输出。

Phase 0.3 不负责 `search_context`、`read_context_documents`、metadata extraction、rerank、knowledge indexing；这些必须由 `test-knowledge-retrieval` 和 `test-knowledge-mcp` 负责。

禁止 `prd-to-xmind-testcases` 自行伪造 retrieval 结果。

## Phase 0.5: context-consumption

当前 phase 必须遵守 `references/loading-strategy.md` 中 `context-consumption` 的 loading strategy。

读取：

- [references/context-consumption.md](references/context-consumption.md)
- [references/context-validation.md](references/context-validation.md)
- [references/context-compression.md](references/context-compression.md)
- [references/traceability-rules.md](references/traceability-rules.md)

目标：

- 校验 context package
- 压缩历史上下文
- 识别影响范围、冲突、回归候选、风险候选、上下游影响
- 生成当前 skill 使用的压缩上下文

输出：

- `./<delivery-name>/analysis/context-reference.md`

context package 缺失、非法、retrieval 不可用时，进入 degraded context mode，但继续后续 pipeline。

## Phase analysis-lite

当前 phase 必须遵守 `references/loading-strategy.md` 中 `analysis-lite` 的 loading strategy。

读取 [references/analysis-lite.md](references/analysis-lite.md)。

适用：simple。

目标：

- 不做完整 6 大建模
- 抽取 testcase 所需最小 expansion model
- 检查 context 中的 regression / risk / workflow / upstream / downstream impact

输出：

- `./<delivery-name>/analysis/analysis-lite.md`

simple 不生成 `testcase-expansion.md`，但 `analysis-lite.md` 必须内置 lightweight expansion matrix。

`analysis-lite` 不是功能点摘要，而是 simple testcase generation 的最小 expansion model。

即使是 simple，也必须展开：主流程、分支流程、异常流程、regression hits、workflow hits、risk hits。

simple expansion 优先覆盖：主流程、高频 workflow、regression candidates、历史风险、边界值。

禁止 simple pipeline 一个功能点只生成一条 case。

如果存在 regression/risk/workflow 命中，最终 testcase 必须落地对应用例或写入 skip reason。

## Phase 1: assets

当前 phase 必须遵守 `references/loading-strategy.md` 中 `assets` 的 loading strategy。

适用：complex。

目标：

- 提取 PRD 图片
- 下载图片
- 建立图片索引

输出：

- `./<delivery-name>/assets/`
- `./<delivery-name>/assets/image-index.md`

只处理当前 PRD 中的图片。simple / normal 禁止强制走图片 pipeline。

## Phase 2: plantuml

当前 phase 必须遵守 `references/loading-strategy.md` 中 `plantuml` 的 loading strategy。

适用：complex。
目标：

- 分类图片
- 对流程图 / 时序图提取结构化元素
- 生成 PlantUML 中间产物

输出：

- `./<delivery-name>/plantuml/*.puml`
- `./<delivery-name>/plantuml/index.md`

原型图、截图、页面图默认不转 PlantUML。

## Phase 3: analysis

当前 phase 必须遵守 `references/loading-strategy.md` 中 `analysis` 的 loading strategy。

读取 [references/prd-structured-analysis.md](references/prd-structured-analysis.md)。

适用：normal / complex。

目标：

- 基于当前 PRD、context-reference、context-package 和必要中间产物进行完整建模
- 完成 6 大建模维度
- 回答 8 个强制建模问题
- 做完整性检查

输出：

- `./<delivery-name>/analysis/structured-analysis.md`

历史上下文必须参与需求点拆分、影响范围、规则复用、冲突识别和回归候选判断，但不能覆盖当前 PRD。

## Phase 4: testpoint

当前 phase 必须遵守 `references/loading-strategy.md` 中 `testpoint` 的 loading strategy。

读取 [references/testpoint-modeling.md](references/testpoint-modeling.md)。
适用：normal / complex。
目标：

- 将 structured-analysis 压缩为测试点模型
- 动态输出测试点分类
- 将历史命中的 reused/regression/risk/workflow 转成测试点或待确认项

输出：

- `./<delivery-name>/analysis/testpoint-model.md`

禁止把完整分析复制进 testpoint。禁止把全部历史用例无脑转为回归测试点。

## Phase 4.5: testcase-expansion

当前 phase 必须遵守 `references/loading-strategy.md` 中 `testcase-expansion` 的 loading strategy。

在加载 domain profiles 前，必须执行 [references/profile-selection-heuristic.md](references/profile-selection-heuristic.md)。

`selected_domain_profiles` 必须来源于 `references/profile-selection-heuristic.md` 的 rule-based selection output。

读取：

- [references/testcase-expansion.md](references/testcase-expansion.md)
- [references/domain-expansion/generic.md](references/domain-expansion/generic.md)
- 按 domain profile 选择规则读取额外 profile

适用：normal / complex。
目标：

- 将 testpoint 展开为 expansion matrix
- 将测试点按业务维度、状态、数据、角色、配置、异常、workflow、历史回归等维度组合
- 生成可执行 testcase groups
- 生成 `expected_case_count`

domain profile 必须按 system、module、workflow、business objects、terminology 推断。

domain profiles 必须包含结构化 Markdown frontmatter metadata，用于后续 profile routing 与 heuristic selection。

如果无法明确判断领域，只允许读取 `references/domain-expansion/generic.md`。

禁止无法判断领域时同时加载多个无关 profile。

`testcase-expansion.md` 必须记录 `selected_domain_profiles` 与 `selection_reason`。

domain profiles 与 examples 必须遵守 `references/loading-strategy.md`。

输出：

- `./<delivery-name>/analysis/testcase-expansion.md`

禁止：

- `testpoint -> testcase` 直接生成
- 一个测试点只生成一条代表性 case
- 把具体业务组合硬编码进主流程

## Phase 5: testcase

当前 phase 必须遵守 `references/loading-strategy.md` 中 `testcase` 的 loading strategy。

读取：

- [references/xmind-output-format.md](references/xmind-output-format.md)
- [references/pipeline-output-schema.md](references/pipeline-output-schema.md)
- [references/traceability-rules.md](references/traceability-rules.md)

输入：

- simple：`analysis-lite.md`
- normal / complex：`testpoint-model.md` + `testcase-expansion.md`
- 所有复杂度：当前 PRD、`context-reference.md`、`context-package.json`（如存在）

输出：

- `./<delivery-name>/testcase/xmind-testcases.md`
- `./<delivery-name>/testcase/xmind-testcases.json`
- `./<delivery-name>/testcase/xmind-import.csv`
- `./<delivery-name>/pipeline-output.json`

Markdown 必须对齐知识库历史用例格式，只承载 XMind 树。traceability、context_source、source_reason、ai_source_path、xmind_path 必须进入 JSON / CSV / pipeline-output.json。

必须统计 `actual_case_count`。

如果 `actual_case_count` 明显低于 `expected_case_count`，必须输出 `case_count_warning`，写入 `pipeline-output.json`，并给出 `case_count_reason`：

```json
{
  "case_count_warning": true,
  "expected_case_count": 80,
  "actual_case_count": 32,
  "case_count_reason": "workflow branches not fully expanded"
}
```

case 数量不是唯一目标，但 expansion coverage 必须满足 workflow / regression / risk 覆盖。

## 关键禁止项

禁止：

- 删除 degraded context mode
- 删除 workflow awareness
- 删除 context validation
- 删除 filesystem / image capability 强约束
- 删除 `.md` / `.xmind` 边界
- 删除 pipeline-output.json
- 删除 traceability
- 删除 retrieval dependency
- 删除 context package
- 跳过 testcase-expansion
- 在主流程硬编码具体业务规则
- 将 references 内容重新塞回 `SKILL.md`
- 因历史上下文缺失而终止整个 testcase pipeline

## 资源引用

必须遵守 [references/loading-strategy.md](references/loading-strategy.md)。

`SKILL.md` 只定义 phase orchestration contract；详细 required / optional / forbidden reference rules 由 `references/loading-strategy.md` 统一定义。

必须按阶段读取对应 reference。不要一次性加载全部 references。

domain profiles 按需读取。默认只读取 `references/domain-expansion/generic.md`；只有明确命中领域语义时，才允许加载额外 profile。

domain profiles 必须包含 `profile_id / profile_type / display_name / description / match_systems / match_modules / match_keywords / match_workflows / match_business_objects / priority / related_profiles / fallback_priority` frontmatter。

- [references/loading-strategy.md](references/loading-strategy.md)
- [references/capability-abstraction.md](references/capability-abstraction.md)
- [references/complexity-analysis.md](references/complexity-analysis.md)
- [references/retrieval-trigger-strategy.md](references/retrieval-trigger-strategy.md)
- [references/context-consumption.md](references/context-consumption.md)
- [references/prd-structured-analysis.md](references/prd-structured-analysis.md)
- [references/testpoint-modeling.md](references/testpoint-modeling.md)
- [references/testcase-expansion.md](references/testcase-expansion.md)
- [references/profile-selection-heuristic.md](references/profile-selection-heuristic.md)
- [references/xmind-output-format.md](references/xmind-output-format.md)
- [references/pipeline-output-schema.md](references/pipeline-output-schema.md)
- [references/error-handling.md](references/error-handling.md)
- [references/domain-expansion/generic.md](references/domain-expansion/generic.md)
- 领域明确命中时再按需读取 `references/domain-expansion/*.md`

examples 仅用于 few-shot，不得当作主规则。

## 完成状态

每个阶段完成后只输出简短状态：

- `[✓] complexity-analysis 完成`
- `[✓] context-retrieval 完成`
- `[✓] context-consumption 完成`
- `[✓] assets 完成`
- `[✓] plantuml 完成`
- `[✓] analysis-lite 完成`
- `[✓] analysis 完成`
- `[✓] testpoint 完成`
- `[✓] testcase-expansion 完成`
- `[✓] testcase 完成`
