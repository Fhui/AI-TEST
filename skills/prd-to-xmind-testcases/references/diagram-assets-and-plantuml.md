# 图片资源与 PlantUML 规范

## 目标

当 PRD 中包含流程图、时序图、原型图、页面截图、弹窗示意图或泳道图时，先通过 MCP 完成图片下载与图片分类；仅将明确可判定为流程图、时序图或泳道图的图片整理为 PlantUML，最后用 `PRD 文本 + 图片结构化结果 + PlantUML` 的组合上下文生成测试用例。

## 目录约定

对每一份 PRD，在项目根目录创建一个单独目录，目录必须与 `.codex` 同级。
该目录名记为 `delivery-name`，优先使用系统名称；若系统名称不明确，则使用规范化后的 `prd-name`。
运行产物只能写到该目录下，不得写入 `.codex/` 或 skill 目录。
所有目录创建、目录检查、文件读取、文件写入，都应通过 `file-system-mcp` 的 `mkdir / list_dir / read_file / write_file` 完成。
所有图片下载、图片分类、OCR、流程元素提取，都应通过 `image-mcp` 的 `download_image / classify_image / ocr_image / extract_flow_elements` 完成。
然后在该目录下创建以下子目录：

```text
./<delivery-name>/assets/
./<delivery-name>/plantuml/
./<delivery-name>/analysis/
./<delivery-name>/testcase/
```

其中：

- `./<delivery-name>/assets/` 用于存放从 Markdown 中下载的原始图片
- `./<delivery-name>/plantuml/` 用于存放根据正文与图片整理出的 `.puml` 文件
- `./<delivery-name>/analysis/` 用于存放结构化分析与测试点模型
- `./<delivery-name>/testcase/` 用于存放最终输出的 Markdown 测试用例

`prd-name` 建议使用规范化名称，例如：

- `partner-capability-auth-center-training-auto-permission`
- `order-center-refund-v2`

## 图片提取规则

必须同时扫描以下两类图片语法：

- Markdown 图片：`![alt](url)`
- HTML 图片：`<img src="url" ...>`

执行要求：

1. 提取全部图片链接。
2. 去重。
3. 通过 `image-mcp.download_image` 下载到 `./<delivery-name>/assets/`。
4. 通过 `file-system-mcp.write_file` 记录图片索引文件 `./<delivery-name>/assets/image-index.md`。

索引建议至少包含：

- 本地文件名
- 原始 URL
- 来源章节
- 预估图片类型
- 是否进入 PlantUML

## PlantUML 生成规则

仅对以下类型的图片，尝试整理为 PlantUML：

- 流程图
- 时序图
- 泳道图
- 角色交互链路图
- 状态流转图
- 消息通知流程图

对以下类型的图片，不生成 PlantUML，也不参与流程推导，仅保留原始资源：

- 页面原型图
- 列表页截图
- 表单页截图
- 弹窗示意图
- 普通页面 UI 截图
- 仅展示样式的设计图

生成 PlantUML 时：

- 结合图片相邻段落与表格描述，不要只凭图像推断
- 优先使用 `image-mcp.classify_image` 与 `image-mcp.extract_flow_elements` 的结果作为图片侧输入
- 文件名使用 `序号-主题名.puml`
- 图中无法确认的分支条件、接口字段、状态名称要显式标 `待确认`
- 图中无法判断的细节不要编造

## 建议的 PlantUML 表达方式

根据场景选择合适图种：

- 业务步骤流转：活动图
- 多角色消息交互：时序图
- 状态变化：状态图
- 页面或系统组件关系：组件图或简单方框图

如果不确定一张图片是否属于流程图或时序图，则默认不转换，直接保留资源并标记为 `待确认`。
在可确定属于流程型图片的前提下，如果仍不确定图种，优先使用活动图，因为它最适合表达测试用例所需的流程与分支。

## 图文冲突处理

如果正文、图片、PlantUML 三者存在差异：

- 正文优先级最高
- 已确认的流程图或时序图次之
- PlantUML 只是整理结果，不得凌驾于原始资料之上

冲突必须写入 `待确认项`，例如：

- 图片中显示某个特定对象在失效前一天收到通知，但正文未说明触发时点
- 页面图中存在某个操作入口，但功能说明中未提到该操作能力

## 失败兜底

如果出现以下情况，仍要继续完成测试分析：

- 图片链接失效
- 图片下载失败
- 图片内容模糊不可辨识
- 图片只有界面样式，没有业务规则

此时应：

- 保留已下载成功的资源
- 在 `待确认项` 中说明缺口
- 继续基于正文输出测试用例

## 文件系统约束

本文件中的所有“落盘”“创建目录”“读取中间文件”等动作，均不应直接操作本地文件系统。
统一改为调用：

- `mkdir`
- `write_file`
- `read_file`
- `list_dir`

本文件中的所有“下载图片”“分类图片”“OCR”“提取流程元素”等动作，也不应由 skill 直接执行。
统一改为调用：

- `download_image`
- `classify_image`
- `ocr_image`
- `extract_flow_elements`

不要把执行细节写回 skill 主流程。

## 最终分析要求

完成图片与 PlantUML 处理后，再回到测试用例输出主流程：

1. 识别系统、版本、模块
2. 提取可测试信息
3. 生成 XMind 友好的测试用例树
4. 输出 `待确认项`
5. 将结果交给后续 `analysis` 与 `testcase` 阶段使用，不要在当前阶段输出完整测试用例正文

最终交付的核心仍然是测试用例树，而不是图片目录或 PlantUML 本身。
原型图、页面截图、弹窗示意图等非流程型图片不应进入 PlantUML 链路，也不应单独作为测试规则来源。
