"""模块资产服务：列出 PRD、测试用例、缺陷、接口和发布说明等知识资产。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..config import READABLE_AI_EXTENSIONS
from ..security import _allowed_roots, _assert_allowed_path
from ..utils.path_utils import _display_path
from ..utils.text_utils import _extract_version
from .metadata_service import _metadata_for_path


def _find_module_path(system: str, module: str) -> Path:
    seen_roots: set[Path] = set()
    for root in _allowed_roots():
        normalized_root = root.resolve(strict=False)
        if normalized_root in seen_roots:
            continue
        seen_roots.add(normalized_root)
        _assert_allowed_path(normalized_root)
        candidates = [normalized_root / "systems" / system / module]
        if system == "shared":
            candidates.append(normalized_root / "shared" / module)
        else:
            candidates.append(normalized_root / system / module)
        for candidate in candidates:
            if candidate.exists() and candidate.is_dir():
                return candidate
    raise FileNotFoundError(f"module not found in allowed knowledge roots: {system}/{module}")

def _collect_module_metadata(module_path: Path) -> list[dict[str, Any]]:
    result = []
    for path in _iter_documents(module_path, include_preview_assets=False):
        result.append(_metadata_for_path(path))
    module_map = module_path.parent / "module-map.md"
    if result and module_map.exists():
        result.append(_metadata_for_path(module_map))
    return result

def _collect_testcase_assets(testcase_dir: Path) -> list[dict[str, Any]]:
    if not testcase_dir.exists():
        return []
    stems: set[str] = set()
    for path in testcase_dir.iterdir():
        if path.is_file() and path.suffix.lower() in {".md", ".xmind"}:
            stems.add(path.stem)

    assets = []
    for stem in sorted(stems):
        md_path = testcase_dir / f"{stem}.md"
        xmind_path = testcase_dir / f"{stem}.xmind"
        if md_path.exists():
            metadata = _metadata_for_path(md_path)
            assets.append(
                {
                    "ai_source_path": metadata["ai_source_path"],
                    "xmind_path": metadata["xmind_path"],
                    "xmind_exists": metadata["xmind_exists"],
                    "version": metadata["version"],
                    "title": metadata["title"],
                }
            )
        else:
            assets.append(
                {
                    "ai_source_path": None,
                    "xmind_path": _display_path(xmind_path),
                    "xmind_exists": xmind_path.exists(),
                    "version": _extract_version(testcase_dir.parent.name, stem),
                    "title": stem,
                    "warnings": ["存在 XMind 但缺少同名 Markdown，AI 无法读取该历史测试用例"],
                }
            )
    return assets

def _asset_list_for_dir(directory: Path) -> list[dict[str, Any]]:
    if not directory.exists():
        return []
    assets = []
    for path in sorted(directory.iterdir()):
        if not path.is_file() or path.suffix.lower() not in READABLE_AI_EXTENSIONS:
            continue
        metadata = _metadata_for_path(path)
        assets.append(
            {
                "file_path": metadata["file_path"],
                "ai_source_path": metadata["ai_source_path"],
                "doc_type": metadata["doc_type"],
                "version": metadata["version"],
                "title": metadata["title"],
            }
        )
    return assets

def list_module_assets(system: str, module: str) -> dict[str, Any]:
    """列出指定模块的知识资产，testcase 会合并同名 Markdown/XMind 配对。"""
    module_dir = _find_module_path(system, module)

    module_map = module_dir.parent / "module-map.md"
    upstream_downstream = module_dir / "upstream-downstream.md"
    return {
        "prd": _asset_list_for_dir(module_dir / "prd"),
        "testcase": _collect_testcase_assets(module_dir / "testcase"),
        "bug": _asset_list_for_dir(module_dir / "bug"),
        "api": _asset_list_for_dir(module_dir / "api"),
        "release": _asset_list_for_dir(module_dir / "release"),
        "module_map": [_metadata_for_path(module_map)] if module_map.exists() else [],
        "upstream_downstream": [_metadata_for_path(upstream_downstream)] if upstream_downstream.exists() else [],
    }
