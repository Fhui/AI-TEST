"""分片索引服务：发现模块、维护 root/module 索引、checksum 和 TTL 刷新。"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..config import (
    ALL_KNOWLEDGE_EXTENSIONS,
    DOC_TYPE_DIRS,
    INDEX_DIR_NAME,
    INDEX_REFRESH_TTL_SECONDS,
    MODULE_CHECKSUM_FILE_NAME,
    MODULE_INDEX_FILE_NAME,
    MODULE_MARKER_FILES,
    PREVIEW_ONLY_EXTENSIONS,
    ROOT_CHECKSUM_FILE_NAME,
    ROOT_INDEX_FILE_NAME,
    SCAN_REPORT_FILE_NAME,
    IGNORED_NAMES,
)
from ..security import _assert_allowed_path, _resolve_allowed_path
from ..utils.atomic_io import _read_json, _write_json
from ..utils.path_utils import _display_path, _is_ignored_path, _iter_documents, _make_module_key, _relative_to_base, _safe_path_segment
from .metadata_service import _detect_doc_type, _metadata_for_path, _path_context


def _scan_root(root: Path) -> dict[str, Any]:
    _assert_allowed_path(root)
    if not root.exists():
        raise FileNotFoundError(f"knowledge root not found: {root}")
    if not root.is_dir():
        raise ValueError(f"knowledge root is not a directory: {root}")

    systems: set[str] = set()
    modules: set[str] = set()
    doc_type_summary: Counter[str] = Counter()
    documents_count = 0
    ai_source_count = 0
    preview_asset_count = 0

    for path in _iter_documents(root):
        doc_type = _detect_doc_type(path)
        system, module = _path_context(path)
        if system:
            systems.add(system)
        if module:
            modules.add(f"{system}/{module}" if system else module)
        doc_type_summary[doc_type] += 1
        documents_count += 1
        if path.suffix.lower() in AI_SOURCE_EXTENSIONS:
            ai_source_count += 1
        elif path.suffix.lower() in PREVIEW_ONLY_EXTENSIONS:
            preview_asset_count += 1

    return {
        "systems": sorted(systems),
        "modules": sorted(modules),
        "documents_count": documents_count,
        "ai_source_count": ai_source_count,
        "preview_asset_count": preview_asset_count,
        "doc_type_summary": dict(sorted(doc_type_summary.items())),
    }

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def _index_dir(root: Path) -> Path:
    return root / INDEX_DIR_NAME

def _root_index_path(root: Path) -> Path:
    return _index_dir(root) / ROOT_INDEX_FILE_NAME

def _root_checksum_path(root: Path) -> Path:
    return _index_dir(root) / ROOT_CHECKSUM_FILE_NAME

def _root_scan_report_path(root: Path) -> Path:
    return _index_dir(root) / SCAN_REPORT_FILE_NAME

def _module_index_dir(root: Path, system: str, module: str) -> Path:
    return _index_dir(root) / _safe_path_segment(system) / _safe_path_segment(module)

def _module_index_path(root: Path, system: str, module: str) -> Path:
    return _module_index_dir(root, system, module) / MODULE_INDEX_FILE_NAME

def _module_checksum_path(root: Path, system: str, module: str) -> Path:
    return _module_index_dir(root, system, module) / MODULE_CHECKSUM_FILE_NAME

def _module_scan_report_path(root: Path, system: str, module: str) -> Path:
    return _module_index_dir(root, system, module) / SCAN_REPORT_FILE_NAME

def _parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed

def _root_index_is_fresh(root: Path) -> bool:
    root_index = _load_root_index(root)
    if not root_index:
        return False
    generated_at = _parse_iso_datetime(root_index.get("generated_at"))
    if generated_at is None:
        return False
    age = (datetime.now(timezone.utc) - generated_at).total_seconds()
    return age < INDEX_REFRESH_TTL_SECONDS

def _ensure_knowledge_index(root: Path, force: bool = False) -> None:
    if force or not _root_index_is_fresh(root):
        refresh_knowledge_index(str(root), force=force)

def _is_module_dir(path: Path) -> bool:
    if not path.is_dir() or path.name in IGNORED_NAMES:
        return False
    for doc_type in DOC_TYPE_DIRS:
        if (path / doc_type).is_dir():
            return True
    for marker in MODULE_MARKER_FILES:
        if (path / marker).exists():
            return True
    return False

def _discover_modules(root: Path) -> list[dict[str, Any]]:
    _assert_allowed_path(root)
    if not root.exists():
        raise FileNotFoundError(f"knowledge root not found: {root}")
    if not root.is_dir():
        raise ValueError(f"knowledge root is not a directory: {root}")

    discovered: dict[Path, dict[str, Any]] = {}

    def add(system: str, module: str, module_path: Path) -> None:
        if not _is_module_dir(module_path):
            return
        normalized = module_path.resolve(strict=False)
        module_key = _make_module_key(system, module)
        discovered[normalized] = {
            "module_key": module_key,
            "safe_system": _safe_path_segment(system),
            "safe_module": _safe_path_segment(module),
            "system": system,
            "module": module,
            "module_path": module_path,
            "module_path_text": _relative_to_base(module_path, root),
        }

    systems_dir = root / "systems"
    if systems_dir.exists():
        for system_dir in sorted(systems_dir.iterdir()):
            if not system_dir.is_dir() or system_dir.name in IGNORED_NAMES:
                continue
            for module_dir in sorted(system_dir.iterdir()):
                add(system_dir.name, module_dir.name, module_dir)

    shared_dir = root / "shared"
    if shared_dir.exists():
        for module_dir in sorted(shared_dir.iterdir()):
            add("shared", module_dir.name, module_dir)

    for system_dir in sorted(root.iterdir()):
        if not system_dir.is_dir() or system_dir.name in IGNORED_NAMES or system_dir.name in {"systems", "shared"}:
            continue
        for module_dir in sorted(system_dir.iterdir()):
            add(system_dir.name, module_dir.name, module_dir)

    return sorted(discovered.values(), key=lambda item: (item["system"], item["module"]))

def _checksum_for_module(module_path: Path) -> dict[str, dict[str, int]]:
    files: dict[str, dict[str, int]] = {}
    if not module_path.exists():
        return files
    for path in sorted(module_path.rglob("*")):
        rel = path.relative_to(module_path)
        try:
            is_file = path.is_file()
        except FileNotFoundError:
            continue
        if _is_ignored_path(rel) or not is_file:
            continue
        if path.name == "context-index.draft.md":
            continue
        if path.suffix.lower() not in ALL_KNOWLEDGE_EXTENSIONS:
            continue
        try:
            stat = path.stat()
        except FileNotFoundError:
            continue
        files[rel.as_posix()] = {
            "size": stat.st_size,
            "mtime": int(stat.st_mtime),
        }
    return files

def _build_module_index(root: Path, module_info: dict[str, Any], generated_at: str) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    module_path = module_info["module_path"]
    documents = []
    for path in _iter_documents(module_path, include_preview_assets=False):
        if path.name == "context-index.draft.md":
            continue
        documents.append(_metadata_for_path(path))

    doc_type_summary = dict(Counter(document["doc_type"] for document in documents))
    checksum_files = _checksum_for_module(module_path)
    preview_asset_count = sum(1 for path in checksum_files if Path(path).suffix.lower() in PREVIEW_ONLY_EXTENSIONS)
    index = {
        "generated_at": generated_at,
        "root_path": _display_path(root),
        "index_scope": "module",
        "system": module_info["system"],
        "module": module_info["module"],
        "module_path": module_info["module_path_text"],
        "documents": documents,
    }
    checksum = {
        "generated_at": generated_at,
        "root_path": _display_path(root),
        "system": module_info["system"],
        "module": module_info["module"],
        "module_path": module_info["module_path_text"],
        "files": checksum_files,
    }
    report = {
        "generated_at": generated_at,
        "root_path": _display_path(root),
        "index_scope": "module",
        "system": module_info["system"],
        "module": module_info["module"],
        "module_path": module_info["module_path_text"],
        "documents_count": len(documents),
        "ai_source_count": len(documents),
        "preview_asset_count": preview_asset_count,
        "doc_type_summary": doc_type_summary,
    }
    return index, checksum, report

def _root_checksum_from_modules(root: Path, root_modules: list[dict[str, Any]], generated_at: str) -> dict[str, Any]:
    return {
        "generated_at": generated_at,
        "root_path": _display_path(root),
        "modules": {
            module["module_key"]: {
                "system": module["system"],
                "module": module["module"],
                "module_path": module["module_path"],
                "checksum_path": module["checksum_path"],
                "documents_count": module["documents_count"],
            }
            for module in root_modules
        },
    }

def refresh_knowledge_index(root_path: str = "knowledge-base", force: bool = False) -> dict[str, Any]:
    """刷新知识库分片索引：root-index 负责导航，module-index 保存可检索 metadata。"""
    root = _resolve_allowed_path(root_path)
    modules = _discover_modules(root)
    generated_at = _now_iso()
    rebuilt_modules = []
    skipped_modules = []
    root_modules = []
    documents_indexed = 0
    preview_assets_indexed = 0

    for module_info in modules:
        module_key = module_info["module_key"]
        current_files = _checksum_for_module(module_info["module_path"])
        old_checksum = _read_json(_module_checksum_path(root, module_info["system"], module_info["module"]))
        old_files = old_checksum.get("files") if old_checksum else None
        module_index_path = _module_index_path(root, module_info["system"], module_info["module"])
        changed = force or old_files != current_files or not module_index_path.exists()

        if changed:
            module_index, module_checksum, module_report = _build_module_index(root, module_info, generated_at)
            _write_json(module_index_path, module_index)
            _write_json(_module_checksum_path(root, module_info["system"], module_info["module"]), module_checksum)
            _write_json(_module_scan_report_path(root, module_info["system"], module_info["module"]), module_report)
            rebuilt_modules.append(module_key)
        else:
            module_index = _read_json(module_index_path) or {}
            module_report = _read_json(_module_scan_report_path(root, module_info["system"], module_info["module"])) or {}
            skipped_modules.append(module_key)

        documents = module_index.get("documents", [])
        documents_count = len(documents)
        documents_indexed += documents_count
        preview_assets_indexed += int(module_report.get("preview_asset_count", 0))
        doc_type_summary = module_report.get("doc_type_summary") or dict(Counter(document.get("doc_type", "unknown") for document in documents))
        root_modules.append(
            {
                "module_key": module_key,
                "system": module_info["system"],
                "safe_system": module_info["safe_system"],
                "module": module_info["module"],
                "safe_module": module_info["safe_module"],
                "module_path": module_info["module_path_text"],
                "index_path": _relative_to_base(_module_index_path(root, module_info["system"], module_info["module"]), root),
                "checksum_path": _relative_to_base(_module_checksum_path(root, module_info["system"], module_info["module"]), root),
                "documents_count": documents_count,
                "doc_type_summary": doc_type_summary,
                "changed": changed,
            }
        )

    systems: dict[str, dict[str, Any]] = {}
    for module in root_modules:
        systems.setdefault(module["system"], {"modules": []})["modules"].append(
            {
                "module_key": module["module_key"],
                "module": module["module"],
                "safe_module": module["safe_module"],
                "module_path": module["module_path"],
                "index_path": module["index_path"],
                "checksum_path": module["checksum_path"],
                "documents_count": module["documents_count"],
                "doc_type_summary": module["doc_type_summary"],
                "changed": module["changed"],
            }
        )

    root_index = {
        "generated_at": generated_at,
        "root_path": _display_path(root),
        "index_scope": "root",
        "systems": systems,
    }
    root_checksum = _root_checksum_from_modules(root, root_modules, generated_at)
    doc_type_summary = dict(
        sum((Counter(module.get("doc_type_summary", {})) for module in root_modules), Counter())
    )
    scan_report = {
        "generated_at": generated_at,
        "root_path": _display_path(root),
        "systems": sorted({module["system"] for module in root_modules}),
        "modules": [f"{module['system']}/{module['module']}" for module in root_modules],
        "modules_count": len(root_modules),
        "documents_count": documents_indexed,
        "ai_source_count": documents_indexed,
        "preview_asset_count": preview_assets_indexed,
        "doc_type_summary": doc_type_summary,
        "rebuilt_modules": rebuilt_modules,
        "skipped_modules": skipped_modules,
    }

    _write_json(_root_index_path(root), root_index)
    _write_json(_root_checksum_path(root), root_checksum)
    _write_json(_root_scan_report_path(root), scan_report)

    return {
        "root_path": _display_path(root),
        "changed": bool(rebuilt_modules),
        "skipped_modules": skipped_modules,
        "rebuilt_modules": rebuilt_modules,
        "modules_count": len(root_modules),
        "documents_indexed": documents_indexed,
        "root_index_path": _display_path(_root_index_path(root)),
        "root_checksum_path": _display_path(_root_checksum_path(root)),
        "scan_report_path": _display_path(_root_scan_report_path(root)),
    }

def _load_root_index(root: Path) -> dict[str, Any] | None:
    return _read_json(_root_index_path(root))

def _load_module_index(root: Path, module_info: dict[str, Any]) -> dict[str, Any] | None:
    return _read_json(_module_index_path(root, module_info["system"], module_info["module"]))

def _candidate_modules_from_root_index(root_index: dict[str, Any], system: str, module: str) -> list[dict[str, Any]]:
    modules = []
    for system_name, system_info in root_index.get("systems", {}).items():
        for item in system_info.get("modules", []):
            modules.append({"system": system_name, **item})
    if system and module:
        return [item for item in modules if item.get("system") == system and item.get("module") == module]
    if system:
        return [item for item in modules if item.get("system") == system]
    return modules

def scan_knowledge_base(root_path: str = "knowledge-base") -> dict[str, Any]:
    """扫描知识库目录，优先使用分片索引 scan-report 返回统计。"""
    root = _resolve_allowed_path(root_path)
    _ensure_knowledge_index(root, force=False)
    report = _read_json(_root_scan_report_path(root))
    if report is None:
        raise FileNotFoundError(f"scan report not found: {_root_scan_report_path(root)}")
    return {
        "systems": report.get("systems", []),
        "modules": report.get("modules", []),
        "documents_count": report.get("documents_count", 0),
        "ai_source_count": report.get("ai_source_count", 0),
        "preview_asset_count": report.get("preview_asset_count", 0),
        "doc_type_summary": report.get("doc_type_summary", {}),
        "modules_count": report.get("modules_count", 0),
        "root_index_path": _display_path(_root_index_path(root)),
        "root_checksum_path": _display_path(_root_checksum_path(root)),
        "scan_report_path": _display_path(_root_scan_report_path(root)),
    }
