---
name: test-knowledge-retrieval
description: 基于当前 PRD 和业务上下文，通过 test-knowledge-mcp 检索并组织测试知识库资料。适用于需要为 prd-to-xmind-testcases、UI 自动化、API 自动化、Traceability、回归分析、影响面分析提供历史 PRD、历史测试用例、历史缺陷、接口文档、上下游说明、发布说明、shared 规则等结构化上下文的场景。
---

# Test Knowledge Retrieval

## 职责边界

本 skill 只负责“检索与上下文组织”。

必须执行：

- 基于当前 PRD 和用户补充信息规划检索条件。
- 通过 `test-knowledge-mcp` 检索和读取测试知识库资料。
- 将检索结果分为强相关、中相关、弱相关。
- 识别可复用测试用例、回归候选、风险候选、上下游依赖、shared 规则、冲突和待确认问题。
- 输出 `context-retrieval.md` 和 `context-package.json`。

禁止执行：

- 生成测试用例、XMind、Playwright spec、API 自动化脚本或完整 PRD 分析。
- 修改测试知识库。
- 绕过 `test-knowledge-mcp` 直接扫描或读取知识库目录。
- 读取或解析 `.xmind` 文件。
- 臆造缺失的业务规则。

## 必需能力

知识库相关操作必须通过 `test-knowledge-mcp` 完成：

- `validate_knowledge_base`
- `search_context`
- `read_context_documents`
- `list_module_assets`

如果 `test-knowledge-mcp` 不可用，必须停止并提示用户。禁止自行扫描知识库兜底。

## Knowledge Roots

执行检索前必须确认知识库根目录来源，并在 `context-retrieval.md` 的 `Knowledge Roots` 或 `Retrieval Summary` 中记录结论。

MCP 的知识库来源包括：

- 项目默认知识库：`knowledge-base`
- 环境变量：`TEST_KNOWLEDGE_ROOTS`

必须注意：

- `search_context` 会在 MCP 允许的 knowledge roots 中检索，skill 不得自行读取 `TEST_KNOWLEDGE_ROOTS` 指向目录。
- `validate_knowledge_base`、`scan_knowledge_base`、`refresh_knowledge_index` 如果传入 `root_path`，必须传 knowledge root 本身，禁止传项目根目录。
- 如果默认 `knowledge-base` 为空，不能直接判定 `knowledge_not_found`，必须继续执行同 system 和全库关键词降级检索，让 MCP 覆盖环境变量中的 roots。
- 如果 MCP 返回所有 roots 均无结果，才允许进入空结果处理。

## 输出目录

写文件前必须确认项目根目录是包含 `.codex` 的目录。

所有产物写入：

```text
./<delivery-name>/analysis/
```

必需产物：

```text
./<delivery-name>/analysis/context-retrieval.md
./<delivery-name>/analysis/context-package.json
```

禁止把执行产物写入 `.codex/`、`.codex/skills/` 或 skill 目录。

## 执行流程

### 1. 生成检索计划

从当前 PRD 和用户补充上下文中提取或谨慎推断：

- `system`
- `module`
- `version`
- `business_objects`
- `interfaces`
- `states`
- `roles`
- `upstream_dependencies`
- `downstream_dependencies`
- `keywords`
- `risk_keywords`
- `diff` 或 release note 线索

无法推断的字段保持为空，并写入 `open_questions`。禁止臆造。

在 `context-retrieval.md` 中输出 `Retrieval Plan`，至少包含：

- System
- Module
- Business Objects
- Interfaces
- States
- Roles
- Upstream Dependencies
- Downstream Dependencies
- Keywords
- Risk Keywords
- Search Strategy
- Open Questions

### 2. 校验并检索

当知识库状态不明确时，先调用 `validate_knowledge_base`。

必须按以下降级链路调用 `search_context`，禁止跳过中间步骤后直接标记 `knowledge_not_found`。

#### 2.1 精确 Module 检索

使用最可靠的精确字段检索：

- `system`
- `module`
- `business_objects`
- `interfaces`
- `states`
- `roles`
- `upstream_dependencies`
- `downstream_dependencies`
- `keywords`

如果命中有效结果，进入相关性分级和读取阶段。

#### 2.2 同 System 降级检索

如果精确 module 无有效结果，必须将 `module` 置空或省略，保留 `system` 和业务检索条件，再次调用 `search_context`：

- `system=<当前 system>`
- `module=""`
- 保留业务对象、接口、状态、角色、依赖、关键词

命中后按实际匹配信号重新分级。不能因为不是精确 module 就全部丢弃。

#### 2.3 全库 Keywords 降级检索

如果同 system 仍无有效结果，必须执行全库关键词检索：

- `system=""`
- `module=""`
- 使用核心业务关键词、版本号、模块别名、业务对象、接口、状态、风险关键词

全库关键词命中的结果默认最多作为中相关或弱相关；只有同时命中业务对象、接口、状态、流程或历史版本关系时，才允许升级为强相关。

#### 2.4 空结果判定

只有精确 module、同 system、全库 keywords 三层检索均无有效结果，才允许设置：

```json
"knowledge_not_found": true
```

每一层检索都必须记录到 `context-package.json.retrieval_summary.search_attempts`，并写入 `context-retrieval.md` 的 `Search Attempts`。

检索覆盖范围必须包括：

- 同 system、同 module。
- 同 system 下的相关模块。
- 上游依赖和下游依赖。
- shared 规则、发布说明和上下文关键词。

优先使用多次精准检索，避免一次性全库宽泛检索。禁止读取整个知识库。

### 2.5 模块别名策略

当 PRD 中 module 可能是版本化组合名时，必须生成模块别名并纳入全库 keywords 降级检索。

示例：

- 当前 module：`V5.6.1(在线看片自助裁剪)`
- 可推断别名：`自助裁剪`、`在线看片自助裁剪`、`小程序自助裁剪`、`取片服务小程序 / 自助裁剪`、`V5.6.0(小程序自助裁剪)`

模块别名只能作为检索关键词或候选 module 说明，不能当作已确认事实写入最终业务结论。

### 3. 相关性分级

读取正文前先分级：

- `strong_related`：同 module，并命中业务对象、接口、流程、状态、角色、风险关键词或 diff。
- `medium_related`：上下游依赖、shared 规则、同 system 不同 module。
- `weak_related`：只有关键词相似，或表述相似但业务对象不同。

弱相关默认只记录摘要，不把正文写入 `context-package.json`。

### 4. 读取候选资料

必须调用 `read_context_documents`。

- 强相关：允许在 `max_chars_per_doc` 限制内读取较完整正文。
- 中相关：优先摘要读取或使用较小字符上限。
- 弱相关：默认不读取正文。

历史测试用例规则：

- `.md` 是 AI source，优先读取 `.md`。
- 如果存在关联 `.xmind`，只返回 `xmind_path` 和 `xmind_exists`。
- 禁止读取或解析 `.xmind`。

### 5. 生成 Context Package

按 `references/context-package-schema.md` 生成合法 JSON。

字段填充规则：

- `reused_testcases` 只放入与当前范围实质匹配的历史测试用例。
- `regression_candidates` 只有在命中当前模块、接口、状态流转、业务对象、风险关键词或 diff 时才能写入。
- `risk_candidates` 必须关注历史线上缺陷、高频缺陷、幂等、并发、状态错乱、通知重复、异步延迟、回滚失败、接口兼容、权限绕过。
- `upstream_dependencies` 和 `downstream_dependencies` 来源于相关资产或当前 PRD 显式描述。
- `shared_rules` 只写入与当前范围相关的 shared 规则。
- `conflicts` 记录当前 PRD 与历史 PRD、历史测试用例、缺陷、接口文档、发布说明、shared 规则之间的冲突。
- `open_questions` 记录缺失字段、归属不清、冲突待确认等问题。

选择回归候选时读取 `references/regression-selection.md`。记录冲突时读取 `references/conflict-detection.md`。

### 6. 生成人类可读摘要

写入 `context-retrieval.md`，必须包含：

```markdown
# Context Retrieval
## Knowledge Roots
## Retrieval Plan
## Search Attempts
### Exact Module Search
### System-Level Fallback Search
### Global Keyword Fallback Search
### Final Decision
## Retrieval Summary
## Strong Related Assets
## Medium Related Assets
## Weak Related Assets
## Reused Testcases
## Regression Candidates
## Risk Candidates
## Upstream Dependencies
## Downstream Dependencies
## Shared Rules
## Conflicts
## Open Questions
```

内容必须简洁、可追溯。禁止粘贴完整大文档、完整历史 PRD 或完整历史测试用例集。

## 空结果处理

如果 `search_context` 没有返回有效结果：

- 仍然输出两个产物。
- 设置 `retrieval_summary.knowledge_not_found` 为 `true`。
- 相关数组保持为空。
- 在 `open_questions` 中记录缺失知识或需要补充的元数据。
- 必须说明三层检索均失败，以及失败发生在哪些 query 条件下。

禁止臆造历史上下文。

## 参考资料

- `references/context-retrieval.md`：检索计划、查询策略和相关性分级。
- `references/regression-selection.md`：回归候选和风险候选选择规则。
- `references/conflict-detection.md`：冲突识别和记录格式。
- `references/context-package-schema.md`：`context-package.json` 结构规范。

## 示例

- `examples/context-retrieval.sample.md`
- `examples/context-package.sample.json`
- `examples/regression-candidates.sample.json`
