"""路径安全层：负责 allowed roots、路径解析和越权访问防护。"""

from __future__ import annotations

import os
from pathlib import Path

from .config import DEFAULT_KNOWLEDGE_ROOT, PROJECT_ROOT


def _allowed_roots() -> list[Path]:
    roots = [DEFAULT_KNOWLEDGE_ROOT]
    env_value = os.environ.get("TEST_KNOWLEDGE_ROOTS", "")
    for raw in env_value.split(os.pathsep):
        if raw.strip():
            roots.append(Path(raw).expanduser())
    return [root.resolve(strict=False) for root in roots]

def _resolve_path(path: str) -> Path:
    raw_path = Path(path).expanduser()
    candidate = raw_path if raw_path.is_absolute() else PROJECT_ROOT / raw_path
    return candidate.resolve(strict=False)

def _assert_allowed_path(path: Path) -> None:
    normalized = path.resolve(strict=False)
    for root in _allowed_roots():
        try:
            normalized.relative_to(root)
            return
        except ValueError:
            continue
    roots = ", ".join(str(root) for root in _allowed_roots())
    raise ValueError(f"path is outside allowed knowledge roots: {path}; allowed roots: {roots}")

def _resolve_allowed_path(path: str) -> Path:
    target = _resolve_path(path)
    _assert_allowed_path(target)
    return target

def _find_root_for_path(path: Path) -> Path:
    normalized = path.resolve(strict=False)
    roots = sorted(_allowed_roots(), key=lambda root: len(root.parts), reverse=True)
    for root in roots:
        try:
            normalized.relative_to(root)
            return root
        except ValueError:
            continue
    roots_text = ", ".join(str(root) for root in roots)
    raise ValueError(f"path is outside allowed knowledge roots: {path}; allowed roots: {roots_text}")
