from __future__ import annotations

from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP


# 相对路径的解析基准为当前项目根目录 ai-test；绝对路径按原路径解析。
PROJECT_ROOT = Path(__file__).resolve().parents[2]

mcp = FastMCP("file-system-mcp")


def _resolve_path(path: str) -> Path:
    """将输入路径规范化。"""
    raw_path = Path(path)
    candidate = raw_path if raw_path.is_absolute() else PROJECT_ROOT / raw_path
    return candidate.resolve(strict=False)


@mcp.tool()
def mkdir(path: str) -> dict[str, Any]:
    """递归创建目录，目录已存在时不报错。"""
    target = _resolve_path(path)
    target.mkdir(parents=True, exist_ok=True)
    return {
        "success": True,
        "absolute_path": str(target),
    }


@mcp.tool()
def write_file(path: str, content: str) -> dict[str, Any]:
    """使用 UTF-8 覆盖写入文件，必要时自动创建父目录。"""
    target = _resolve_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    data = content.encode("utf-8")
    target.write_text(content, encoding="utf-8")
    return {
        "success": True,
        "absolute_path": str(target),
        "bytes_written": len(data),
    }


@mcp.tool()
def read_file(path: str) -> dict[str, Any]:
    """使用 UTF-8 读取文本文件。"""
    target = _resolve_path(path)
    if not target.exists():
        raise FileNotFoundError(f"file not found: {path}")
    if not target.is_file():
        raise ValueError(f"path is not a file: {path}")

    return {
        "success": True,
        "absolute_path": str(target),
        "content": target.read_text(encoding="utf-8"),
    }


@mcp.tool()
def list_dir(path: str) -> dict[str, Any]:
    """列出目录下的直接子文件和子目录。"""
    target = _resolve_path(path)
    if not target.exists():
        raise FileNotFoundError(f"directory not found: {path}")
    if not target.is_dir():
        raise ValueError(f"path is not a directory: {path}")

    items = [
        {
            "name": child.name,
            "path": str(child.resolve(strict=False)),
            "is_dir": child.is_dir(),
        }
        for child in sorted(target.iterdir(), key=lambda item: (not item.is_dir(), item.name))
    ]

    return {
        "success": True,
        "absolute_path": str(target),
        "items": items,
    }


if __name__ == "__main__":
    mcp.run(transport="stdio")
