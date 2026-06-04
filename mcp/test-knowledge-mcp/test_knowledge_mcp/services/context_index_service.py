"""上下文索引草稿服务：基于 module index 渲染 context-index.draft.md。"""

from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from ..security import _find_root_for_path, _resolve_path
from ..utils.atomic_io import _read_json, _write_text_atomic
from ..utils.path_utils import _display_path, _relative_to_base
from ..utils.text_utils import _extract_version, _unique
from .asset_service import _collect_testcase_assets, _find_module_path
from .index_service import _candidate_modules_from_root_index, _ensure_knowledge_index, _load_module_index, _load_root_index, _module_checksum_path


def _testcase_assets_from_index(module_path: Path, metadata_items: list[dict[str, Any]], module_checksum: dict[str, Any] | None) -> list[dict[str, Any]]:
    assets_by_stem: dict[str, dict[str, Any]] = {}
    for item in metadata_items:
        if item.get("doc_type") != "testcase":
            continue
        ai_source_path = item.get("ai_source_path")
        stem = Path(ai_source_path or item["file_path"]).stem
        assets_by_stem[stem] = {
            "ai_source_path": ai_source_path,
            "xmind_path": item.get("xmind_path"),
            "xmind_exists": item.get("xmind_exists", False),
            "version": item.get("version", ""),
            "title": item.get("title", stem),
        }

    files = (module_checksum or {}).get("files", {})
    for relative_path in files:
        path = Path(relative_path)
        if path.suffix.lower() != ".xmind" or "testcase" not in path.parts:
            continue
        stem = path.stem
        xmind_path = module_path / relative_path
        if stem in assets_by_stem:
            assets_by_stem[stem]["xmind_path"] = _display_path(xmind_path)
            assets_by_stem[stem]["xmind_exists"] = True
        else:
            assets_by_stem[stem] = {
                "ai_source_path": None,
                "xmind_path": _display_path(xmind_path),
                "xmind_exists": True,
                "version": _extract_version(module_path.name, stem),
                "title": stem,
            }
    return [assets_by_stem[stem] for stem in sorted(assets_by_stem)]

def _render_context_index(
    system: str,
    module: str,
    module_path: Path,
    metadata_items: list[dict[str, Any]],
    testcase_assets: list[dict[str, Any]] | None = None,
) -> str:
    by_type: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in metadata_items:
        by_type[item["doc_type"]].append(item)

    testcase_assets = testcase_assets if testcase_assets is not None else _collect_testcase_assets(module_path / "testcase")
    missing_lines = []
    for asset in testcase_assets:
        ai_source = asset.get("ai_source_path")
        xmind_path = asset.get("xmind_path")
        if ai_source and not xmind_path:
            missing_lines.append(f"- {ai_source} 缺少同名 XMind，预览/编辑入口缺失。")
        if xmind_path and not ai_source:
            missing_lines.append(f"- {xmind_path} 缺少同名 Markdown，AI 无法使用该历史测试用例。")
    if not metadata_items and not testcase_assets:
        missing_lines.extend(
            [
                "- 当前模块暂无可索引知识资产。",
                "- 建议补充 PRD、测试用例、接口文档、缺陷或发布说明。",
            ]
        )

    def table_for(doc_type: str) -> str:
        rows = ["| 版本 | 标题 | 文件 |", "|---|---|---|"]
        for item in by_type.get(doc_type, []):
            rows.append(f"| {item.get('version') or '-'} | {item.get('title') or '-'} | {_relative_to_base(Path(item['file_path']), module_path)} |")
        return "\n".join(rows) if len(rows) > 2 else "暂无"

    testcase_rows = ["| 版本 | 标题 | AI Source | XMind |", "|---|---|---|---|"]
    for asset in testcase_assets:
        ai_source = _relative_to_base(_resolve_path(asset["ai_source_path"]), module_path) if asset.get("ai_source_path") else "缺失"
        xmind_path = _relative_to_base(_resolve_path(asset["xmind_path"]), module_path) if asset.get("xmind_path") else "缺失"
        testcase_rows.append(f"| {asset.get('version') or '-'} | {asset.get('title') or '-'} | {ai_source} | {xmind_path} |")

    core_objects = _unique(value for item in metadata_items for value in item.get("business_objects", []))
    states = _unique(value for item in metadata_items for value in item.get("states", []))
    upstream = _unique(value for item in metadata_items for value in item.get("upstream_dependencies", []))
    downstream = _unique(value for item in metadata_items for value in item.get("downstream_dependencies", []))
    risks = _unique((value for item in metadata_items for value in item.get("risk_points", [])), limit=10)

    return "\n\n".join(
        [
            f"# {module} 模块上下文索引",
            "## 模块职责\n\n待补充",
            "## 核心对象\n\n" + ("\n".join(f"- {item}" for item in core_objects) if core_objects else "待补充"),
            "## 状态机\n\n" + ("\n".join(f"- {item}" for item in states) if states else "待补充"),
            "## 上游依赖\n\n" + ("\n".join(f"- {item}" for item in upstream) if upstream else "待补充"),
            "## 下游依赖\n\n" + ("\n".join(f"- {item}" for item in downstream) if downstream else "待补充"),
            "## 历史 PRD\n\n" + table_for("prd"),
            "## 历史测试用例\n\n" + ("\n".join(testcase_rows) if len(testcase_rows) > 2 else "暂无"),
            "## 高风险历史缺陷\n\n" + ("\n".join(f"- {item}" for item in risks) if risks else table_for("bug")),
            "## 接口文档\n\n" + table_for("api"),
            "## 发布说明\n\n" + table_for("release"),
            "## 历史测试重点\n\n待补充",
            "## 待补充信息\n\n" + ("\n".join(missing_lines) if missing_lines else "暂无"),
            "",
        ]
    )

def generate_context_index_draft(system: str, module: str) -> dict[str, Any]:
    """为指定 system/module 生成 context-index.draft.md，不覆盖正式 context-index.md。"""
    target_module_path = _find_module_path(system, module)
    root = _find_root_for_path(target_module_path)
    _ensure_knowledge_index(root, force=False)
    root_index = _load_root_index(root) or {}
    module_infos = _candidate_modules_from_root_index(root_index, system, module)
    module_info = module_infos[0] if module_infos else {"system": system, "module": module}
    module_index = _load_module_index(root, module_info) or {}
    module_checksum = _read_json(_module_checksum_path(root, system, module)) or {}
    metadata_items = module_index.get("documents", [])
    testcase_assets = _testcase_assets_from_index(target_module_path, metadata_items, module_checksum)
    content = _render_context_index(system, module, target_module_path, metadata_items, testcase_assets)
    draft_path = target_module_path / "context-index.draft.md"
    _write_text_atomic(draft_path, content)
    return {
        "context_index_path": _display_path(draft_path),
        "indexed_files": [item["file_path"] for item in metadata_items],
        "summary": {
            "system": system,
            "module": module,
            "indexed_count": len(metadata_items),
            "doc_type_summary": dict(Counter(item["doc_type"] for item in metadata_items)),
        },
    }
