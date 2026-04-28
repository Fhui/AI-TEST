# image-mcp

这是一个最小可用的 Python MCP server，用于提供通用图片处理能力。
它只负责下载图片、分类图片、OCR 图片、提取流程元素的结构化中间结果。
它不负责生成 PlantUML，不负责理解完整业务流程，也不负责生成测试用例。

## 目录结构

```text
mcp/image-mcp/
├── README.md
├── requirements.txt
└── server.py
```

## 安装步骤

1. 进入目录

```bash
cd mcp/image-mcp
```

2. 安装 Python 依赖

```bash
python3 -m pip install -r requirements.txt
```

3. 如需使用 OCR，请额外安装系统依赖 `tesseract`

macOS 示例：

```bash
brew install tesseract
brew install tesseract-lang
```

如果没有中文语言包，`chi_sim` 识别可能不可用。

## 运行方式

使用 stdio 方式启动：

```bash
python3 server.py
```

说明：

- server 使用 MCP 标准 stdio 通信
- 不会向 stdout 打日志
- 如果后续需要日志，建议写 stderr

## Tools

### 1. `download_image`

输入：

- `url: string`
- `save_path: string`

行为：

- 下载远程图片到本地
- 自动创建父目录
- 支持 `png / jpg / jpeg / webp`

返回：

- `success`
- `absolute_path`
- `bytes_written`
- `content_type`

### 2. `classify_image`

输入：

- `path: string`

行为：

- 对本地图片做基础分类
- 基于 OCR 文本和简单启发式规则输出结果

返回：

- `success`
- `absolute_path`
- `image_type`
- `reason`

支持的类型：

- `flowchart`
- `sequence_diagram`
- `wireframe`
- `screenshot`
- `modal_or_popup`
- `unknown`

### 3. `ocr_image`

输入：

- `path: string`

行为：

- 对本地图片做 OCR

返回：

- `success`
- `absolute_path`
- `extracted_text`

如果环境缺少 `pytesseract` 或 `tesseract`，会返回清晰错误。

### 4. `extract_flow_elements`

输入：

- `path: string`
- `nearby_text: string`

行为：

- 基于图片 OCR 结果和附近文本，输出可用于后续生成 PlantUML 的结构化中间结果
- 不直接生成 PlantUML

返回至少包含：

- `success`
- `absolute_path`
- `image_type`
- `nodes`
- `edges`
- `annotations`
- `confidence`
- `limitations`

说明：

- 如果图片不是流程图或时序图，会返回空结构和原因
- 不会臆造节点关系
- 当前版本的 `edges` 主要基于 OCR 阅读顺序推断，不是真实箭头检测

## 安全限制

这个 server 默认只允许操作当前项目根目录 `ai-test` 下的文件和目录。

安全规则：

1. 所有传入路径都会先规范化
2. 相对路径会被解析到 `ai-test` 根目录下
3. 绝对路径只有在位于 `ai-test` 根目录内时才允许
4. 不允许通过 `..` 逃逸到项目根目录之外
5. 如果目标路径超出允许根目录，server 会直接返回错误

默认允许操作的根目录：

```text
/Users/fenghui/workspace/ai/ai-test
```

## OCR 依赖要求

OCR 默认依赖：

- Python 包 `pytesseract`
- 系统命令 `tesseract`

如果没有安装 `tesseract`：

- `ocr_image` 会返回错误
- `classify_image` 会退化为较弱的无 OCR 启发式分类
- `extract_flow_elements` 会返回错误

## 最小调用示例

下面是几个典型用途：

- `download_image("https://example.com/demo.png", "tmp/demo.png")`
  - 下载图片到项目目录内
- `classify_image("tmp/demo.png")`
  - 获取图片基础类型
- `ocr_image("tmp/demo.png")`
  - 提取 OCR 文本
- `extract_flow_elements("tmp/demo.png", "这是一张流程图")`
  - 提取流程节点和边的中间结果
