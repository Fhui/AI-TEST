"""MCP 服务入口：只负责注册工具、调用服务层并提供少量测试兼容导出。"""

from __future__ import annotations

import os
import sys
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))
try:
    from mcp.server.fastmcp import FastMCP
except ImportError:  # pragma: no cover - keeps helper functions importable in minimal test envs
    class FastMCP:  # type: ignore[no-redef]
        """真实 FastMCP 不可用时使用的最小替身，仅用于本地导入和测试。"""

        def __init__(self, name: str):
            """保存服务名称，保证未安装 MCP 依赖时测试仍可导入模块。"""
            self.name = name

        def tool(self, *args, **kwargs):
            """返回空操作装饰器，让本地测试保留原始 tool 函数。"""
            def decorator(func):
                return func

            return decorator

        def run(self, transport: str = "stdio") -> None:
            """如果误用替身启动真实 MCP 服务，则给出清晰错误。"""
            raise RuntimeError("mcp.server.fastmcp is not installed")

from test_knowledge_mcp.config import DEFAULT_MAX_CHARS_PER_DOC, DEFAULT_KNOWLEDGE_ROOT, PROJECT_ROOT
from test_knowledge_mcp.security import _allowed_roots, _assert_allowed_path, _find_root_for_path, _resolve_allowed_path, _resolve_path
from test_knowledge_mcp.services.asset_service import (
    _asset_list_for_dir,
    _collect_module_metadata,
    _collect_testcase_assets,
    _find_module_path,
    list_module_assets as _list_module_assets,
)
from test_knowledge_mcp.services.context_index_service import (
    _render_context_index,
    _testcase_assets_from_index,
    generate_context_index_draft as _generate_context_index_draft,
)
from test_knowledge_mcp.services.index_service import (
    _candidate_modules_from_root_index,
    _checksum_for_module,
    _discover_modules,
    _ensure_knowledge_index,
    _load_module_index,
    _load_root_index,
    _module_checksum_path,
    _module_index_path,
    _read_json,
    _root_checksum_path,
    _root_index_path,
    _root_scan_report_path,
    refresh_knowledge_index as _refresh_knowledge_index,
    scan_knowledge_base as _scan_knowledge_base,
)
from test_knowledge_mcp.services.metadata_service import (
    _detect_testcase_markdown_structure,
    _metadata_for_path,
    extract_metadata as _extract_metadata,
)
from test_knowledge_mcp.services.search_service import (
    _relevance_for_score,
    _score_metadata,
    read_context_documents as _read_context_documents,
    search_context as _search_context,
)
from test_knowledge_mcp.services.validation_service import (
    _iter_testcase_dirs,
    _validate_testcase_pairs,
    validate_knowledge_base as _validate_knowledge_base,
    validate_testcase_markdown as _validate_testcase_markdown,
)
from test_knowledge_mcp.utils.atomic_io import _read_text_limited, _write_json, _write_text_atomic
from test_knowledge_mcp.utils.path_utils import _display_path, _iter_documents, _make_module_key, _relative_to_base, _safe_path_segment

mcp = FastMCP("test-knowledge-mcp")


@mcp.tool()
def refresh_knowledge_index(root_path: str = "knowledge-base", force: bool = False) -> dict:
    return _refresh_knowledge_index(root_path, force)


@mcp.tool()
def scan_knowledge_base(root_path: str = "knowledge-base") -> dict:
    return _scan_knowledge_base(root_path)


@mcp.tool()
def extract_metadata(file_path: str) -> dict:
    return _extract_metadata(file_path)


@mcp.tool()
def generate_context_index_draft(system: str, module: str) -> dict:
    return _generate_context_index_draft(system, module)


@mcp.tool()
def search_context(
    system: str,
    module: str,
    business_objects: list[str] | None = None,
    interfaces: list[str] | None = None,
    states: list[str] | None = None,
    roles: list[str] | None = None,
    upstream_dependencies: list[str] | None = None,
    downstream_dependencies: list[str] | None = None,
    keywords: list[str] | None = None,
    doc_types: list[str] | None = None,
    limit: int = 20,
    force_refresh: bool = False,
) -> dict:
    return _search_context(
        system=system,
        module=module,
        business_objects=business_objects,
        interfaces=interfaces,
        states=states,
        roles=roles,
        upstream_dependencies=upstream_dependencies,
        downstream_dependencies=downstream_dependencies,
        keywords=keywords,
        doc_types=doc_types,
        limit=limit,
        force_refresh=force_refresh,
    )


@mcp.tool()
def read_context_documents(documents: list[dict], max_chars_per_doc: int = DEFAULT_MAX_CHARS_PER_DOC) -> dict:
    return _read_context_documents(documents, max_chars_per_doc)


@mcp.tool()
def list_module_assets(system: str, module: str) -> dict:
    return _list_module_assets(system, module)


@mcp.tool()
def validate_knowledge_base(root_path: str = "knowledge-base", force_rescan: bool = False) -> dict:
    return _validate_knowledge_base(root_path, force_rescan)


@mcp.tool()
def validate_testcase_markdown(file_path: str) -> dict:
    return _validate_testcase_markdown(file_path)

if __name__ == "__main__":
    mcp.run(transport="stdio")
