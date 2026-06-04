# Capability Abstraction

## Filesystem Capability

所有文件系统动作必须通过 filesystem capability 完成：

- `mkdir`
- `write_file`
- `read_file`
- `list_dir`

禁止直接使用 shell、Python、Node 或其他方式绕过 capability 写入运行产物。

如果 filesystem capability 不可用：

- 停止当前 skill 执行
- 提示用户 capability 不可用
- 不要自行兜底

## Image Capability

图片处理必须通过 image capability 完成：

- `download_image`
- `classify_image`
- `ocr_image`
- `extract_flow_elements`

禁止直接下载图片、直接 OCR、直接图片分类。

## Capability Boundary

skill 只负责决策和生成内容，capability provider 负责执行动作。

运行产物禁止写入 `.codex/` 或 `.codex/skills/`。
