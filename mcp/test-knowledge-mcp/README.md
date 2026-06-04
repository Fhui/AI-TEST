# test-knowledge-mcp

`test-knowledge-mcp` 是测试知识库的扫描、索引、校验与规则召回 MCP Server。

它为 `prd-to-xmind-testcases`、UI 自动化、API 自动化和回归分析等上层 skill 提供历史上下文，但不替代这些 skill 做测试分析推理。

## 核心边界

- `.md` 是 AI 唯一测试用例读取源，对应字段为 `ai_source_path`
- `.xmind` 是配套 XMind 文件，对应字段为 `xmind_path`
- 同目录同名不同后缀视为配对，例如 `order-v1.2.md` 与 `order-v1.2.xmind`
- MCP 不读取、不解析、不修改、不生成 `.xmind`
- `.xmind` 是合法 knowledge asset，可以调用 `extract_metadata`，但只作为 preview asset 返回，不读取内容

## 目录结构

```text
mcp/test-knowledge-mcp/
├── README.md
├── requirements.txt
└── server.py
```

推荐知识库结构：

```text
knowledge-base/
├── systems/
│   └── qa-hub/
│       ├── module-map.md
│       └── order/
│           ├── context-index.md
│           ├── context-index.draft.md
│           ├── prd/
│           ├── testcase/
│           │   ├── order-v1.2.md
│           │   └── order-v1.2.xmind
│           ├── bug/
│           ├── api/
│           ├── release/
│           └── upstream-downstream.md
└── shared/
```

同时兼容最多三层的扁平业务结构：

```text
knowledge-base/
├── watchPic/
│   └── V5.6.0(小程序自助裁剪)/
│       ├── prd/
│       │   └── 自助裁剪V5.6.0.md
│       └── testcase/
│           ├── 自助裁剪V5.6.0.md
│           └── 自助裁剪V5.6.0.xmind
└── cloud/
    └── AI直出V1.0.0/
        ├── prd/
        └── testcase/
```

这种结构会被识别为：

- `system`: 第一级目录，例如 `watchPic`
- `module`: 第二级目录，例如 `V5.6.0(小程序自助裁剪)`
- `version`: 优先从第二级目录或文件名提取，例如 `V5.6.0`
- `doc_type`: `prd`、`testcase` 等类型目录

## 安装

```bash
cd mcp/test-knowledge-mcp
python3 -m pip install -r requirements.txt
```

## 代码结构

`server.py` 只负责 FastMCP 初始化、tool 注册和调用 service 层。核心业务按职责拆到合法 Python 包 `test_knowledge_mcp/`：

```text
mcp/test-knowledge-mcp/
├── server.py
├── README.md
└── test_knowledge_mcp/
    ├── config.py
    ├── security.py
    ├── models.py
    ├── utils/
    │   ├── atomic_io.py
    │   ├── path_utils.py
    │   └── text_utils.py
    └── services/
        ├── metadata_service.py
        ├── index_service.py
        ├── search_service.py
        ├── validation_service.py
        ├── asset_service.py
        └── context_index_service.py
```

- `config.py`: 常量、扩展名、索引文件名、停用词和支持的 doc_type。
- `security.py`: allowed roots、路径解析和越权防护。
- `utils/atomic_io.py`: 原子 JSON/text 写入和 AI source 文本读取。
- `utils/path_utils.py`: 路径展示、忽略规则、文档遍历和 module key。
- `utils/text_utils.py`: 标题、关键词、版本号等通用文本工具。
- `services/metadata_service.py`: metadata/frontmatter/XMind 配对信息提取。
- `services/index_service.py`: 分片索引、checksum、TTL refresh 和扫描统计。
- `services/search_service.py`: 规则召回、分桶和上下文文档读取。
- `services/asset_service.py`: 模块资产列表和测试用例配对资产。
- `services/context_index_service.py`: `context-index.draft.md` 渲染和原子写入。
- `services/validation_service.py`: 知识库和 testcase Markdown 校验。

## 启动

```bash
python3 server.py
```

server 使用 MCP stdio 通信，不向 stdout 输出日志。

## 知识库根目录

默认允许访问：

```text
../../knowledge-base
```

可通过环境变量增加白名单根目录：

```bash
export TEST_KNOWLEDGE_ROOTS="/absolute/path/to/knowledge-base"
```

多个路径使用系统路径分隔符分隔。

## 分片索引

第一版使用 root-index + module-index 分片索引，不生成单一大 `index.json`。
索引目录镜像知识库的 system/module 层级，所有索引文件统一落在 `<knowledge-root>/.knowledge-index/` 下，不会写入业务 module 目录。

```text
knowledge-base/
├── watchPic/
│   └── V5.6.0(小程序自助裁剪)/
│       ├── prd/
│       └── testcase/
└── .knowledge-index/
    ├── root-index.json
    ├── root-checksum.json
    ├── scan-report.json
    └── watchPic/
        └── V5.6.0_小程序自助裁剪/
            ├── index.json
            ├── checksum.json
            └── scan-report.json
```

- `root-index.json` 只做导航，记录 system/module、module index 路径和摘要，不保存完整 documents metadata。
- `root-checksum.json` 只做 module-level checksum 导航，记录 module、checksum_path、documents_count，不重复保存文件级 checksum。
- `.knowledge-index/<safe-system>/<safe-module>/index.json` 保存真正可检索的 searchable metadata。
- `.knowledge-index/<safe-system>/<safe-module>/checksum.json` 保存该模块下 AI source 和 preview asset 的 size/mtime，用于增量判断。
- `search_context`、`scan_knowledge_base`、`validate_knowledge_base` 和 `generate_context_index_draft` 默认使用 30 秒 TTL 刷新策略；TTL 内会直接复用现有 root-index/module-index，避免每次召回都做 checksum scan。
- `.xmind` 只参与 checksum 和配对状态，不会被读取或写入 AI content。

root-checksum 示例：

```json
{
  "generated_at": "",
  "root_path": "",
  "modules": {
    "watchPic__V5.6.0_小程序自助裁剪": {
      "system": "watchPic",
      "module": "V5.6.0(小程序自助裁剪)",
      "module_path": "watchPic/V5.6.0(小程序自助裁剪)",
      "checksum_path": ".knowledge-index/watchPic/V5.6.0_小程序自助裁剪/checksum.json",
      "documents_count": 2
    }
  }
}
```

真正的文件级 checksum 只保存在对应 module 的 `checksum.json` 中。

## Tools

### refresh_knowledge_index

刷新分片索引。默认只重建发生变化的 module，`force=true` 时重建全部 module。

```json
{
  "root_path": "knowledge-base",
  "force": false
}
```

返回：

```json
{
  "root_path": "",
  "changed": true,
  "skipped_modules": [],
  "rebuilt_modules": [],
  "modules_count": 0,
  "documents_indexed": 0,
  "root_index_path": "",
  "root_checksum_path": "",
  "scan_report_path": ""
}
```

### scan_knowledge_base

刷新分片索引后读取 root scan-report，返回系统、模块、文档数量和文档类型分布。
如果传入路径不在白名单知识库根目录内，会稳定抛出 `ValueError`；如果路径在白名单内但不存在，会稳定抛出 `FileNotFoundError`。

```json
{
  "root_path": "knowledge-base"
}
```

关键输出包含：

```json
{
  "documents_count": 0,
  "ai_source_count": 0,
  "preview_asset_count": 0
}
```

### extract_metadata

读取指定 knowledge asset 并提取 metadata。测试用例 Markdown 会附带同名 XMind 配对信息。
`.xmind` 也可以调用此 tool，但返回 `preview_only=true`、`readable=false`，不会读取 `.xmind` 内容。

```json
{
  "file_path": "knowledge-base/systems/qa-hub/order/testcase/order-v1.2.md"
}
```

关键输出：

```json
{
  "ai_source_path": "knowledge-base/systems/qa-hub/order/testcase/order-v1.2.md",
  "xmind_path": "knowledge-base/systems/qa-hub/order/testcase/order-v1.2.xmind",
  "xmind_exists": true,
  "preview_only": false,
  "readable": true
}
```

传入 `.xmind` 时：

```json
{
  "file_path": "knowledge-base/systems/qa-hub/order/testcase/order-v1.2.xmind",
  "ai_source_path": "knowledge-base/systems/qa-hub/order/testcase/order-v1.2.md",
  "xmind_path": "knowledge-base/systems/qa-hub/order/testcase/order-v1.2.xmind",
  "xmind_exists": true,
  "preview_only": true,
  "readable": false
}
```

### generate_context_index_draft

为指定模块生成 `context-index.draft.md`，避免覆盖人工维护的 `context-index.md`。
空模块目录也允许生成 draft，不会报错；当 `indexed_count=0` 时，`## 待补充信息` 会提示当前模块暂无可索引知识资产，并建议补充 PRD、测试用例、接口文档、缺陷或发布说明。
该 tool 会先刷新分片索引，再读取对应 module-index 生成 draft，不重新扫描正文。

```json
{
  "system": "qa-hub",
  "module": "order"
}
```

测试用例索引会同时记录 AI Source 与 XMind：

```markdown
| 版本 | 标题 | AI Source | XMind |
|---|---|---|---|
| v1.2 | 订单 v1.2 测试用例 | testcase/order-v1.2.md | testcase/order-v1.2.xmind |
```

### Frontmatter Metadata

推荐在 AI source 文档顶部补充 frontmatter。frontmatter 优先级高于路径推断和正文正则，缺失字段会继续 fallback 到路径、标题、正文和文件名。

```yaml
---
doc_type: testcase
system: qa-hub
module: order
version: v1.2
business_objects:
  - Order
interfaces:
  - /order/create
---
```

### search_context

基于 system、module、业务对象、接口、状态、依赖、关键词和风险点做规则召回。
搜索会优先读取分片索引，并按 TTL 判断是否需要刷新：指定 system + module 时只读取对应 module-index；只指定 system 时读取该 system 下的 module-index；未指定时读取 root-index 中的候选 module-index。默认使用 TTL refresh，调试或刚修改知识库后可传 `force_refresh=true` 强制重建索引。

```json
{
  "system": "qa-hub",
  "module": "order",
  "business_objects": ["Order", "Coupon"],
  "interfaces": ["/order/create"],
  "states": ["CREATED", "PAID"],
  "roles": ["user", "admin"],
  "upstream_dependencies": ["product"],
  "downstream_dependencies": ["payment", "inventory"],
  "keywords": ["下单", "支付", "优惠券"],
  "doc_types": ["testcase", "bug"],
  "limit": 20,
  "force_refresh": false
}
```

结果按 `strong_related`、`medium_related`、`weak_related`、`excluded` 分桶。
`doc_types` 为空时不过滤；指定后只召回对应类型，支持 `prd`、`testcase`、`bug`、`api`、`release`、`module_map`、`upstream_downstream`。

### read_context_documents

读取 `search_context` 返回的 AI source 文档。永远不会读取 `.xmind`。

```json
{
  "documents": [
    {
      "ai_source_path": "knowledge-base/systems/qa-hub/order/testcase/order-v1.2.md",
      "xmind_path": "knowledge-base/systems/qa-hub/order/testcase/order-v1.2.xmind",
      "doc_type": "testcase"
    }
  ],
  "max_chars_per_doc": 6000
}
```

### list_module_assets

列出指定模块的知识资产。`testcase` 会合并同名 `.md/.xmind`。

```json
{
  "system": "qa-hub",
  "module": "order"
}
```

### validate_knowledge_base

校验知识库结构与测试用例 Markdown/XMind 配对关系。

```json
{
  "root_path": "knowledge-base"
}
```

规则：

- `.md` 有同名 `.xmind`：正常
- `.md` 缺同名 `.xmind`：warning
- `.xmind` 缺同名 `.md`：warning
- 不读取、不解析 `.xmind` 内容

输出 summary 会包含孤儿文件列表：

```json
{
  "orphan_markdown_files": [],
  "orphan_xmind_files": []
}
```

### validate_testcase_markdown

校验单个测试用例 Markdown，并返回 XMind 配对信息。

```json
{
  "file_path": "knowledge-base/systems/qa-hub/order/testcase/order-v1.2.md"
}
```

## 安全限制

- path traversal 防护
- root_path 白名单限制
- 禁止读取知识库 root_path 之外的文件
- 禁止写知识库外文件
- 单文件读取大小限制
- 最大返回字符数限制
- `.xmind` 禁止读取内容
- `.xmind` 禁止解析
- 不执行任意 shell 命令
