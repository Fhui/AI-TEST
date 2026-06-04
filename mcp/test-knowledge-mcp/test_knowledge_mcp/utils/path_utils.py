"""路径工具：负责展示路径、相对路径、忽略规则和知识资产遍历。"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable

from ..config import AI_SOURCE_EXTENSIONS, ALL_KNOWLEDGE_EXTENSIONS, IGNORED_NAMES, PROJECT_ROOT
from ..security import _allowed_roots


def _display_path(path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        return path.resolve(strict=False).relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return str(path.resolve(strict=False))

def _relative_to_base(path: Path, base: Path) -> str:
    try:
        return path.resolve(strict=False).relative_to(base.resolve(strict=False)).as_posix()
    except ValueError:
        return _display_path(path) or str(path)

def _relative_to_allowed_root(path: Path) -> Path | None:
    normalized = path.resolve(strict=False)
    roots = sorted(_allowed_roots(), key=lambda root: len(root.parts), reverse=True)
    for root in roots:
        try:
            return normalized.relative_to(root)
        except ValueError:
            continue
    return None

def _is_ignored_path(path: Path) -> bool:
    return any(part in IGNORED_NAMES for part in path.parts)

def _iter_documents(root: Path, include_preview_assets: bool = True) -> Iterable[Path]:
    extensions = ALL_KNOWLEDGE_EXTENSIONS if include_preview_assets else AI_SOURCE_EXTENSIONS
    for path in sorted(root.rglob("*")):
        if _is_ignored_path(path.relative_to(root) if path.is_absolute() else path):
            continue
        if path.is_file() and path.suffix.lower() in extensions:
            yield path

def _safe_path_segment(name: str) -> str:
    cleaned = re.sub(r"[^\w.]+", "_", name, flags=re.UNICODE)
    cleaned = re.sub(r"_+", "_", cleaned)
    return cleaned.strip("_")

def _make_module_key(system: str, module: str) -> str:
    return f"{_safe_path_segment(system)}__{_safe_path_segment(module)}"
