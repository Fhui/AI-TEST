# file-system-mcp

这是一个最小可用的 Python MCP server，用于提供本地文件系统的基础操作能力。
它只处理文件和目录，不处理下载、OCR、PlantUML 或任何业务逻辑。

## 目录结构

```text
mcp/file-system-mcp/
├── README.md
├── requirements.txt
└── server.py
```

## 安装步骤

1. 进入目录

```bash
cd mcp/file-system-mcp
```

2. 安装依赖

```bash
python -m pip install -r requirements.txt
```

## 运行方式

使用 stdio 方式启动：

```bash
python server.py
```

说明：

- server 使用 MCP 标准 stdio 通信
- 不会向 stdout 打日志
- 如果后续需要日志，建议写 stderr

## Tools

### 1. `write_file`

输入：

- `path: string`
- `content: string`

行为：

- 自动创建父目录
- 使用 UTF-8 覆盖写入

返回：

- `success`
- `absolute_path`
- `bytes_written`

### 2. `read_file`

输入：

- `path: string`

行为：

- 使用 UTF-8 读取文本文件

返回：

- `success`
- `absolute_path`
- `content`

### 3. `mkdir`

输入：

- `path: string`

行为：

- 递归创建目录
- 已存在时不报错

返回：

- `success`
- `absolute_path`

### 4. `list_dir`

输入：

- `path: string`

行为：

- 列出目录下的直接子文件和子目录

返回：

- `success`
- `absolute_path`
- `items`

其中 `items` 至少包含：

- `name`
- `path`
- `is_dir`

## 路径规则

这个 server 支持读取和写入任意本机路径。

路径规则：

1. 所有传入路径都会先规范化
2. 相对路径会被解析到 `ai-test` 根目录下
3. 绝对路径会按原路径解析
4. `..` 会被规范化到最终绝对路径
5. 是否允许访问由操作系统文件权限决定

相对路径解析基准：

```text
/Users/fenghui/workspace/ai/ai-test
```

## 最小示例

下面是这 4 个 tools 的典型用途：

- `mkdir("tmp/demo")`
  - 创建目录 `ai-test/tmp/demo`
- `write_file("tmp/demo/hello.txt", "hello")`
  - 写入文本文件
- `read_file("tmp/demo/hello.txt")`
  - 读取文件内容
- `list_dir("tmp/demo")`
  - 列出目录下内容
