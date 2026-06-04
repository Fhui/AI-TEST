"""校验服务：检查知识库结构、Markdown/XMind 配对和 testcase Markdown 质量。"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from ..utils.atomic_io import _read_text_limited
from ..utils.path_utils import _display_path
from .index_service import _discover_modules, _ensure_knowledge_index, _read_json, _root_scan_report_path
from .metadata_service import _detect_testcase_markdown_structure, _metadata_for_path
from ..security import _resolve_allowed_path


def _validate_testcase_pairs(testcase_dir: Path) -> dict[str, Any]:
    warnings = []
    md_files = {path.stem: path for path in testcase_dir.glob("*.md")} if testcase_dir.exists() else {}
    xmind_files = {path.stem: path for path in testcase_dir.glob("*.xmind")} if testcase_dir.exists() else {}
    paired = sorted(set(md_files) & set(xmind_files))
    orphan_md = sorted(set(md_files) - set(xmind_files))
    orphan_xmind = sorted(set(xmind_files) - set(md_files))

    for stem in orphan_md:
        warnings.append(f"{_display_path(md_files[stem])} 缺少同名 XMind，预览/编辑入口缺失。")
    for stem in orphan_xmind:
        warnings.append(f"{_display_path(xmind_files[stem])} 缺少同名 Markdown，AI 无法使用该历史测试用例。")

    return {
        "warnings": warnings,
        "orphan_markdown_files": [_display_path(md_files[stem]) for stem in orphan_md],
        "orphan_xmind_files": [_display_path(xmind_files[stem]) for stem in orphan_xmind],
        "summary": {
            "testcase_markdown_count": len(md_files),
            "testcase_xmind_count": len(xmind_files),
            "paired_testcase_count": len(paired),
            "orphan_markdown_count": len(orphan_md),
            "orphan_xmind_count": len(orphan_xmind),
        },
    }

def _iter_testcase_dirs(root: Path) -> Iterable[Path]:
    seen: set[Path] = set()
    patterns = ["systems/*/*/testcase", "shared/*/testcase", "*/*/testcase"]
    for pattern in patterns:
        for path in sorted(root.glob(pattern)):
            normalized = path.resolve(strict=False)
            if path.is_dir() and normalized not in seen:
                seen.add(normalized)
                yield path

def validate_knowledge_base(root_path: str = "knowledge-base", force_rescan: bool = False) -> dict[str, Any]:
    """校验知识库结构与 testcase Markdown/XMind 配对关系。"""
    errors = []
    warnings = []
    summary = {
        "systems_count": 0,
        "modules_count": 0,
        "testcase_markdown_count": 0,
        "testcase_xmind_count": 0,
        "paired_testcase_count": 0,
        "orphan_markdown_count": 0,
        "orphan_xmind_count": 0,
        "orphan_markdown_files": [],
        "orphan_xmind_files": [],
    }
    try:
        root = _resolve_allowed_path(root_path)
        _ensure_knowledge_index(root, force=force_rescan)
        report = _read_json(_root_scan_report_path(root)) or {}
        summary["systems_count"] = len(report.get("systems", []))
        summary["modules_count"] = report.get("modules_count", len(report.get("modules", [])))
        for module_info in _discover_modules(root):
            testcase_dir = module_info["module_path"] / "testcase"
            if not testcase_dir.exists():
                continue
            pair_result = _validate_testcase_pairs(testcase_dir)
            warnings.extend(pair_result["warnings"])
            summary["orphan_markdown_files"].extend(pair_result["orphan_markdown_files"])
            summary["orphan_xmind_files"].extend(pair_result["orphan_xmind_files"])
            for key, value in pair_result["summary"].items():
                summary[key] += value
    except Exception as exc:
        errors.append(str(exc))
    return {"valid": not errors, "errors": errors, "warnings": warnings, "summary": summary}

def validate_testcase_markdown(file_path: str) -> dict[str, Any]:
    """校验单个 testcase Markdown，并返回同名 XMind 配对信息。"""
    errors = []
    warnings = []
    ai_source_path = None
    xmind_path = None
    xmind_exists = False
    structure = {
        "has_case_id": False,
        "has_steps": False,
        "has_expected": False,
        "has_priority": False,
        "has_tree_structure": False,
        "confidence": 0.0,
    }
    try:
        path = _resolve_allowed_path(file_path)
        if path.suffix.lower() != ".md":
            errors.append("testcase AI source must be a Markdown .md file")
        if not path.exists():
            errors.append(f"file not found: {file_path}")
        elif not path.is_file():
            errors.append(f"path is not a file: {file_path}")
        elif path.suffix.lower() != ".md":
            metadata = _metadata_for_path(path)
            ai_source_path = metadata["ai_source_path"]
            xmind_path = metadata["xmind_path"]
            xmind_exists = metadata["xmind_exists"]
        else:
            if "testcase" not in [part.lower() for part in path.parts]:
                warnings.append("file is not under a testcase directory")
            text = _read_text_limited(path)
            structure = _detect_testcase_markdown_structure(text)
            if not text.strip():
                errors.append("testcase Markdown is empty")
            elif structure["confidence"] <= 0:
                errors.append("Markdown does not look like a testcase document")
            metadata = _metadata_for_path(path)
            ai_source_path = metadata["ai_source_path"]
            xmind_path = metadata["xmind_path"]
            xmind_exists = metadata["xmind_exists"]
            if not xmind_exists:
                warnings.append("缺少同目录同名 XMind，预览/编辑入口缺失。")
    except Exception as exc:
        errors.append(str(exc))

    return {
        "valid": not errors,
        "ai_source_path": ai_source_path,
        "xmind_path": xmind_path,
        "xmind_exists": xmind_exists,
        "structure": structure,
        "warnings": warnings,
        "errors": errors,
    }
