# 上下文检索参考

## 输入范围

允许输入当前 PRD 内容和用户补充上下文：

- `system`、`module`、`version`
- `business_objects`
- `interfaces`
- `states`
- `roles`
- `upstream_dependencies`
- `downstream_dependencies`
- `keywords`
- `diff`
- `release_notes`
- 用户手工指定的历史资料路径

推断信息时只能基于 PRD 标题、术语表、接口名、状态机、角色权限表、依赖说明、发布说明和 diff 文本。缺少依据的内容必须写入 `open_questions`。

## 查询计划

必须按“精确 module → 同 system → 全库 keywords”的顺序组织降级检索，禁止第一层失败后直接判定 `knowledge_not_found`。

### 1. 精确 Module 检索

使用：

- `system=<当前 system>`
- `module=<当前 module>`
- 业务对象、接口、状态、角色、依赖、关键词、风险关键词

适合命中同模块历史 PRD、历史测试用例、历史缺陷、接口文档和发布说明。

### 2. 同 System 降级检索

当精确 module 无结果时，使用：

- `system=<当前 system>`
- `module=""`
- 保留业务对象、接口、状态、角色、依赖、关键词、风险关键词

适合发现同系统不同模块、上下游联动、shared 规则、历史版本模块名不一致的资料。

### 3. 全库 Keywords 降级检索

当同 system 仍无结果时，使用：

- `system=""`
- `module=""`
- 核心业务关键词
- 版本号
- 模块别名
- 业务对象、接口、状态、风险关键词

适合发现 system/module 元数据不一致、历史资料迁移到其他目录、版本名变化导致的漏召回。

全库结果默认谨慎分级，不能仅凭关键词命中标记为强相关。

当已知 system/module 但不清楚可用资产类型时，先调用 `list_module_assets`。

## Knowledge Roots 记录

`context-retrieval.md` 必须记录：

- 默认知识库：`knowledge-base`
- 环境变量知识库：`TEST_KNOWLEDGE_ROOTS`
- MCP 是否返回有效知识资产

skill 不能自行扫描环境变量路径。只能通过 MCP 的 `search_context`、`validate_knowledge_base`、`list_module_assets` 等工具确认结果。

如果默认 `knowledge-base` 为空，仍必须继续同 system 和全库 keywords 检索，因为 MCP 可能还能从 `TEST_KNOWLEDGE_ROOTS` 中召回资料。

## Search Attempts 记录格式

每次检索至少记录：

- `stage`：`exact_module`、`system_fallback`、`global_keywords`
- `query`：实际传给 `search_context` 的关键字段
- `strong_count`
- `medium_count`
- `weak_count`
- `decision`：`used`、`fallback_next`、`no_result`
- `reason`

示例：

```json
{
  "stage": "system_fallback",
  "query": {
    "system": "watchPic",
    "module": "",
    "keywords": ["自助裁剪", "V5.6.0", "尺寸库"]
  },
  "strong_count": 0,
  "medium_count": 2,
  "weak_count": 1,
  "decision": "used",
  "reason": "精确模块未命中，但同 system 命中历史版本资料"
}
```

## 模块别名

从 PRD 标题、功能列表、模块列、版本号和历史版本关键词中生成别名。

示例：

- `V5.6.1(在线看片自助裁剪)`
- `自助裁剪`
- `在线看片自助裁剪`
- `小程序自助裁剪`
- `取片服务小程序 / 自助裁剪`
- `V5.6.0(小程序自助裁剪)`

别名只用于扩大召回，不代表业务规则已确认。

## 相关性分级

强相关通常同时满足：

- 同模块。
- 命中至少一个当前业务对象。
- 命中至少一个当前接口、流程、状态或角色。
- 能为当前测试提供历史 PRD、测试用例、缺陷、发布或接口证据。

中相关通常满足：

- 上游或下游依赖。
- 同系统不同模块。
- shared 权限、通知、状态流转、异步、回滚或兼容规则。

弱相关通常只满足：

- 关键词相似。
- 表述相似但业务对象或流程不同。

全库 keywords 降级检索的命中结果，如果只有关键词或版本号命中，默认归为弱相关；如果同时命中业务对象、接口、状态或流程，可升级为中相关；只有具备明确同模块/历史版本关系且命中业务信号时，才允许归为强相关。

## 读取限制

强相关资产可以使用较高 `max_chars_per_doc`，以保留规则和测试意图。中相关资产使用较低字符上限或摘要读取。弱相关资产默认不读取正文，除非后续出现强/中相关信号。

## 可追溯字段

每个入选资产尽量保留 MCP 返回的标识：

- `asset_id`
- `title`
- `doc_type`
- `system`
- `module`
- `path`
- `matched_fields`
- `reason`
- `source_ts` 或版本信息

禁止只写自然语言摘要而丢失来源标识。
