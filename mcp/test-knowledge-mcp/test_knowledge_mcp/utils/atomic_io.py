"""原子 IO 工具：统一处理安全读取、JSON 写入和文本写入。"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from ..config import MAX_FILE_BYTES, READABLE_AI_EXTENSIONS
from ..security import _assert_allowed_path


def _read_text_limited(path: Path, max_bytes: int = MAX_FILE_BYTES) -> str:
    _assert_allowed_path(path)
    suffix = path.suffix.lower()
    if suffix == ".xmind":
        raise ValueError(".xmind is a preview asset only and must not be read")
    if suffix not in READABLE_AI_EXTENSIONS:
        raise ValueError(f"unsupported AI source extension: {suffix}")
    if not path.exists():
        raise FileNotFoundError(f"file not found: {path}")
    if not path.is_file():
        raise ValueError(f"path is not a file: {path}")
    size = path.stat().st_size
    if size > max_bytes:
        raise ValueError(f"file is too large: {size} bytes > {max_bytes} bytes")
    return path.read_text(encoding="utf-8", errors="replace")

def _write_json(path: Path, data: dict[str, Any]) -> None:
    _assert_allowed_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f"{path.name}.tmp")
    content = json.dumps(data, ensure_ascii=False, indent=2)
    with tmp_path.open("w", encoding="utf-8") as file:
        file.write(content)
        file.flush()
        os.fsync(file.fileno())
    tmp_path.replace(path)

def _write_text_atomic(path: Path, content: str) -> None:
    _assert_allowed_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f"{path.name}.tmp")
    with tmp_path.open("w", encoding="utf-8") as file:
        file.write(content)
        file.flush()
        os.fsync(file.fileno())
    tmp_path.replace(path)

def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))
