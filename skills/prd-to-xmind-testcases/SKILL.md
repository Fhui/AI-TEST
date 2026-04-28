---
name: prd-to-xmind-testcases
description: 将 Markdown 格式的 PRD 解析为可导入 XMind 的测试用例树。适用于需要分阶段处理 PRD、提取图片、区分流程图或时序图与原型图、借助 image-mcp 提取图片结构化结果、将明确可判定的流程图或时序图整理为 PlantUML、先做对象状态行为规则依赖抽象建模、再做结构化分析、测试点建模，最后通过 file-system-mcp 逐阶段落盘生成 XMind 风格测试用例的场景。
---

# PRD 转 XMind 测试用例

## 目标

将 Markdown PRD 按严格 pipeline 分阶段处理，避免一次性输出过大导致断流、重连或超时。

保留以下能力：

- 读取 Markdown PRD
- 提取图片
- 区分流程图 / 时序图 / 原型图 / 截图
- 将明确可判定的流程图或时序图转换为 PlantUML
- 先做抽象建模
- 再做结构化分析
- 再做测试点建模
- 最后生成 XMind 风格测试用例

执行类动作不在 skill 内直接执行。
凡是创建目录、写文件、读文件、列目录，都必须通过 `file-system-mcp` 提供的 tools 完成：

- `mkdir`
- `write_file`
- `read_file`
- `list_dir`

凡是下载图片、分类图片、OCR、提取流程图中间结构，都必须通过 `image-mcp` 提供的 tools 完成：

- `download_image`
- `classify_image`
- `ocr_image`
- `extract_flow_elements`

## 适用场景

当用户需要基于 PRD 生成测试用例，且 PRD 中可能包含流程图、时序图、原型图、截图或复杂业务规则时，使用此 skill。

不要用在以下场景：

- 执行测试
- 生成自动化脚本
- 在 PRD 未说明时补业务规则
- 一次性把所有中间产物和最终产物直接输出到对话

## 职责边界

skill 负责：

- 解析 Markdown PRD
- 抽象对象、状态、行为、规则、依赖
- 决定执行顺序
- 决定哪些图片要进入流程分析
- 结合 `PRD 文本 + 图片结构化结果 + PlantUML` 做结构化分析
- 做测试点建模
- 生成最终测试用例内容

MCP 负责：

- 创建目录
- 写文件
- 读文件
- 列目录
- 下载图片
- 图片分类
- OCR
- 提取流程图中间结构

## 路径规则

所有运行产物必须写入项目根目录下、与 `.codex` 同级的单独目录：

- `./<delivery-name>/`

目录结构固定为：

- `./<delivery-name>/assets/`
- `./<delivery-name>/plantuml/`
- `./<delivery-name>/analysis/structured-analysis.md`
- `./<delivery-name>/analysis/testpoint-model.md`
- `./<delivery-name>/testcase/xmind-testcases.md`

其中：

- `delivery-name` 优先使用系统名称
- 若系统名称不明确，再使用规范化后的 `prd-name`

强约束：

- 禁止将任何运行产物写入 `.codex/`
- 禁止将任何运行产物写入 skill 目录
- skill 目录下若存在旧的 `assets/`、`plantuml/`、`testcase/`，它们都不是运行输出目录
- 禁止直接下载图片
- 禁止直接写入文件
- 禁止直接创建目录
- 禁止直接读取目录
- 必须调用 `file-system-mcp` 的 `mkdir / write_file / read_file / list_dir`
- 必须调用 `image-mcp` 的 `download_image / classify_image / ocr_image / extract_flow_elements`
- 如果当前工作目录不是项目根目录，先停止并提示用户确认，不要落盘

## 抽象优先

在 `analysis` 和 `testpoint` 阶段，必须先抽象出：

- 对象
- 状态
- 行为
- 规则
- 依赖

然后再映射回 PRD 原始术语。
不要直接拿具体业务词充当通用分析框架。

## 强制建模问题（升级版）

在进入 `Phase 5: testcase` 之前，必须回答以下问题：

1. 核心对象及其生命周期
2. 状态机完整性（含非法迁移）
3. 行为语义（含副作用）
4. 数据约束（含跨字段）
5. 权限控制维度
6. 异步/依赖/事务机制
7. 失败补偿与幂等机制
8. 边界与极端情况

如果这 8 个问题没有回答完整，不要进入 `testcase` 阶段。

## analysis 完整性约束

在 `Phase 3: analysis` 阶段，必须执行覆盖性检查：

- 状态是否完整
- 行为是否完整
- 数据规则是否完整
- 权限是否完整
- 异常路径是否完整

如果不完整，必须补充推断或标记 `PRD未说明`。
禁止跳过不完整项。

## 执行约束

严格按阶段执行，不要跳阶段，不要合并阶段。

- 禁止一次性输出完整大文件内容到对话
- 禁止把所有阶段结果攒到最后一起输出
- 必须每阶段完成后立即落盘
- 所有阶段落盘都必须通过 `file-system-mcp`
- 所有图片处理都必须通过 `image-mcp`
- 在聊天中只输出简短状态，不输出长篇正文
- 如果用户明确要求查看某个文件内容，才允许读取并展示该文件

每个阶段完成后，只输出对应状态：

- `[✓] assets 完成`
- `[✓] plantuml 完成`
- `[✓] analysis 完成`
- `[✓] testpoint 完成`
- `[✓] testcase 完成`

## 分阶段流程

### Phase 1: assets

- 目标
  - 从 PRD 提取全部图片 URL
  - 调用 MCP 下载图片并建立图片索引
- 输入
  - Markdown PRD
  - 图片链接
- 输出目录
  - `./<delivery-name>/assets/`
- 产出文件
  - 原始图片文件
  - `./<delivery-name>/assets/image-index.md`
- MCP 动作
  - 调用 `file-system-mcp.list_dir` 检查目标目录
  - 调用 `file-system-mcp.mkdir` 创建目录
  - 调用 `image-mcp.download_image` 下载图片
  - 调用 `file-system-mcp.write_file` 写入 `image-index.md`
- 完成状态
  - `[✓] assets 完成`
- 读取资源
  - [references/diagram-assets-and-plantuml.md](references/diagram-assets-and-plantuml.md)

### Phase 2: plantuml

- 目标
  - 对每张图片做分类
  - 仅对流程图或时序图提取结构化中间结果
  - skill 决定是否生成 PlantUML 文本
- 输入
  - PRD 文本
  - `Phase 1` 下载的图片
  - `image-index.md`
- 输出目录
  - `./<delivery-name>/plantuml/`
- 产出文件
  - `.puml` 文件
  - `./<delivery-name>/plantuml/index.md`
- MCP 动作
  - 调用 `file-system-mcp.list_dir` 检查输入资产
  - 调用 `image-mcp.classify_image` 对每张图片分类
  - 对流程图或时序图调用 `image-mcp.extract_flow_elements`
  - 如分类判断或 OCR 需要补充证据，可调用 `image-mcp.ocr_image`
  - 调用 `file-system-mcp.mkdir` 创建目录
  - skill 根据 `PRD 文本 + flow elements` 生成 PlantUML 文本
  - 调用 `file-system-mcp.write_file` 写入 `.puml` 与 `index.md`
- 完成状态
  - `[✓] plantuml 完成`
- 读取资源
  - [references/diagram-assets-and-plantuml.md](references/diagram-assets-and-plantuml.md)

### Phase 3: analysis

- 目标
  - 基于 `PRD 文本 + 图片分类结果 + flow elements + PlantUML` 完成结构化分析
  - 从对象、状态、行为、规则、依赖升级为 6 大建模维度
  - 强制回答升级版 8 个强制建模问题
  - 强制执行完整性约束
- 输入
  - Markdown PRD
  - `Phase 1` 资产
  - `Phase 2` PlantUML
  - 图片分类结果
  - flow elements
- 子阶段
  - `3.1 Domain`
    - 单独建立 Domain Model
    - 识别对象、类型（主体 / 资源 / 关系 / 配置 / 结果）、生命周期、上下游关系、是否持久化
  - `3.2 State`
    - 单独建立 State Machine
    - 识别状态列表、状态迁移矩阵、非法迁移、状态幂等性、并发状态
  - `3.3 Behavior`
    - 单独建立 Behavior Model
    - 每个行为必须拆成输入、前置条件、处理逻辑、副作用、输出
  - `3.4 Data`
    - 单独建立 Data Rules
    - 拆分输入约束、业务规则、结果约束、跨字段约束、时间约束、幂等约束
  - `3.5 Permission`
    - 单独建立 Permission Model
    - 识别身份权限、操作权限、数据范围权限、时间权限
  - `3.6 System`
    - 单独建立 System Behavior
    - 强制分析同步 / 异步、事务边界、重试机制、幂等机制、失败补偿、外部依赖 SLA
  - 最后合并 3.1~3.6 为 `structured-analysis.md`
- 完整性约束
  - 必须检查状态是否完整
  - 必须检查行为是否完整
  - 必须检查数据规则是否完整
  - 必须检查权限是否完整
  - 必须检查异常路径是否完整
  - 如果不完整，必须补充推断或标记 `PRD未说明`
  - 禁止跳过不完整项
- 输出目录
  - `./<delivery-name>/analysis/`
- 产出文件
  - `./<delivery-name>/analysis/structured-analysis.md`
- MCP 动作
  - 调用 `file-system-mcp.read_file` 读取必要的中间文件
  - 调用 `file-system-mcp.mkdir` 创建目录
  - 调用 `file-system-mcp.write_file` 写入 `structured-analysis.md`
- 完成状态
  - `[✓] analysis 完成`
- 读取资源
  - [references/prd-structured-analysis.md](references/prd-structured-analysis.md)

### Phase 4: testpoint

- 目标
  - 读取 `structured-analysis.md`
  - 不复制完整结构化分析
  - 将完整分析压缩并映射为模块级测试点模型
  - 只保留可直接驱动测试用例生成的测试点
- 输入
  - `./<delivery-name>/analysis/structured-analysis.md`
  - PRD 原文
  - PlantUML
- 要求
  - `testpoint-model.md` 不是分析摘要
  - `testpoint-model.md` 不是 `structured-analysis.md` 的缩写版
  - 必须按测试类型组织：
    - 主路径测试
    - 分支路径测试
    - 异常路径测试
    - 状态测试
    - 权限测试
    - 数据约束测试
    - 通知测试
    - 场景测试
    - 失败补偿测试
  - 每个测试点必须能追溯到 `structured-analysis.md` 中的对象、状态、行为、规则或依赖
  - 不要把完整分析内容复制进 `testpoint-model.md`
- 输出目录
  - `./<delivery-name>/analysis/`
- 产出文件
  - `./<delivery-name>/analysis/testpoint-model.md`
- MCP 动作
  - 调用 `file-system-mcp.read_file` 读取 `structured-analysis.md`
  - 调用 `file-system-mcp.write_file` 写入 `testpoint-model.md`
- 完成状态
  - `[✓] testpoint 完成`
- 读取资源
  - [references/testpoint-modeling.md](references/testpoint-modeling.md)

### Phase 5: testcase

- 目标
  - 将测试点模型拆成最终 XMind 风格测试用例
  - 输出严格符合模板的树形 Markdown
- 输入
  - `structured-analysis.md`
  - `testpoint-model.md`
  - Markdown PRD
  - PlantUML
- 输出目录
  - `./<delivery-name>/testcase/`
- 产出文件
  - `./<delivery-name>/testcase/xmind-testcases.md`
- MCP 动作
  - 调用 `file-system-mcp.read_file` 读取 `structured-analysis.md` 与 `testpoint-model.md`
  - 调用 `file-system-mcp.mkdir` 创建目录
  - 调用 `file-system-mcp.write_file` 写入 `xmind-testcases.md`
- 完成状态
  - `[✓] testcase 完成`
- 读取资源
  - [references/case-rules.md](references/case-rules.md)
  - [references/output-template.md](references/output-template.md)
  - [examples/sample-output.md](examples/sample-output.md)

## 错误处理

- 如果图片下载失败，继续后续阶段，但必须在对应落盘文件中记录缺口
- 如果图片无法确认是否属于流程图或时序图，默认不转 PlantUML
- 如果正文与图片冲突，以正文为主，并在落盘文件中记为 `待确认项`
- 如果结构化分析未完成或 8 个强制问题未回答完整，停止在 `analysis` 或 `testpoint` 阶段，不进入 `testcase`
- 如果路径不在项目根目录，先停止并提示用户确认，不要创建目录
- 如果 `file-system-mcp` 不可用，先停止并提示用户， 不要改用直接写文件作为兜底
- 如果 `image-mcp` 不可用，先停止并提示用户，不要改用直接下载、直接 OCR 或直接图片分类作为兜底

## 资源引用

- 使用 `file-system-mcp` 的 `mkdir / write_file / read_file / list_dir` 执行全部文件系统操作
- 使用 `image-mcp` 的 `download_image / classify_image / ocr_image / extract_flow_elements` 执行全部图片处理操作
- 使用 [references/diagram-assets-and-plantuml.md](references/diagram-assets-and-plantuml.md) 处理图片、索引和 PlantUML
- 使用 [references/prd-structured-analysis.md](references/prd-structured-analysis.md) 生成结构化分析
- 使用 [references/testpoint-modeling.md](references/testpoint-modeling.md) 生成测试点模型
- 使用 [references/case-rules.md](references/case-rules.md) 拆分测试用例
- 使用 [references/output-template.md](references/output-template.md) 套用最终输出格式
- 仅在需要示例时读取 [examples/sample-output.md](examples/sample-output.md)
