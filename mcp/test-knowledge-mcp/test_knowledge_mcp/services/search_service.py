"""上下文召回服务：基于分片索引 metadata 做规则打分、分桶和文档读取。"""

from __future__ import annotations

from typing import Any

from ..config import DEFAULT_MAX_CHARS_PER_DOC, MAX_TOTAL_RETURN_CHARS, SUPPORTED_DOC_TYPES
from ..security import _allowed_roots, _resolve_allowed_path, _resolve_path
from ..utils.atomic_io import _read_text_limited
from ..utils.text_utils import _unique
from .index_service import _candidate_modules_from_root_index, _ensure_knowledge_index, _load_module_index, _load_root_index
from .metadata_service import _metadata_for_path


def _score_metadata(query: dict[str, Any], metadata: dict[str, Any]) -> tuple[int, list[str], list[str], str]:
    score = 0
    matched_fields: list[str] = []
    matched_terms: list[str] = []

    def add(field: str, term: str, points: int) -> None:
        nonlocal score
        score += points
        matched_fields.append(field)
        matched_terms.append(term)

    if query.get("system") and metadata.get("system") == query.get("system"):
        add("system", query["system"], 15)
    if query.get("module") and metadata.get("module") == query.get("module"):
        add("module", query["module"], 25)

    weighted_fields = [
        ("business_objects", 15),
        ("interfaces", 20),
        ("states", 10),
        ("roles", 5),
        ("upstream_dependencies", 12),
        ("downstream_dependencies", 12),
        ("keywords", 5),
    ]
    for field, points in weighted_fields:
        query_values = {str(value).lower() for value in query.get(field, [])}
        metadata_values = {str(value).lower() for value in metadata.get(field, [])}
        for value in sorted(query_values & metadata_values):
            add(field, value, points)

    risk_values = " ".join(metadata.get("risk_points", [])).lower()
    for keyword in query.get("keywords", []):
        if str(keyword).lower() in risk_values:
            add("risk_points", str(keyword), 10)

    if metadata.get("system") == "shared" and matched_terms:
        add("shared", "shared", 8)

    reason = "命中字段: " + ", ".join(_unique(matched_fields, limit=12)) if matched_fields else "未命中有效召回条件"
    return score, _unique(matched_fields, limit=20), _unique(matched_terms, limit=30), reason

def _relevance_for_score(score: int) -> str:
    if score >= 60:
        return "strong"
    if score >= 30:
        return "medium"
    if score >= 10:
        return "weak"
    return "excluded"

def _all_searchable_metadata(root: Path) -> list[dict[str, Any]]:
    if not root.exists():
        return []
    items = []
    for path in _iter_documents(root, include_preview_assets=False):
        items.append(_metadata_for_path(path))
    return items

def _all_searchable_metadata_from_allowed_roots(doc_types: set[str] | None = None) -> list[dict[str, Any]]:
    items = []
    seen_paths: set[Path] = set()
    seen_roots: set[Path] = set()
    for root in _allowed_roots():
        normalized_root = root.resolve(strict=False)
        if normalized_root in seen_roots:
            continue
        seen_roots.add(normalized_root)
        _assert_allowed_path(normalized_root)
        if not normalized_root.exists() or not normalized_root.is_dir():
            continue
        for metadata in _all_searchable_metadata(normalized_root):
            ai_source_path = metadata.get("ai_source_path") or metadata.get("file_path")
            if not ai_source_path:
                continue
            resolved = _resolve_path(str(ai_source_path))
            if resolved in seen_paths:
                continue
            if doc_types is not None and metadata.get("doc_type") not in doc_types:
                continue
            seen_paths.add(resolved)
            items.append(metadata)
    return items

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
) -> dict[str, Any]:
    """基于 metadata、关键词和路径结构做历史上下文召回。"""
    normalized_doc_types = {doc_type.strip() for doc_type in doc_types or [] if doc_type and doc_type.strip()}
    unsupported_doc_types = sorted(normalized_doc_types - SUPPORTED_DOC_TYPES)
    if unsupported_doc_types:
        raise ValueError(f"unsupported doc_types: {', '.join(unsupported_doc_types)}")

    query = {
        "system": system,
        "module": module,
        "business_objects": business_objects or [],
        "interfaces": interfaces or [],
        "states": states or [],
        "roles": roles or [],
        "upstream_dependencies": upstream_dependencies or [],
        "downstream_dependencies": downstream_dependencies or [],
        "keywords": keywords or [],
        "doc_types": sorted(normalized_doc_types),
        "force_refresh": force_refresh,
    }
    candidates = []
    seen_paths: set[str] = set()
    seen_roots: set[Path] = set()
    for root in _allowed_roots():
        root = root.resolve(strict=False)
        if root in seen_roots:
            continue
        seen_roots.add(root)
        if not root.exists() or not root.is_dir():
            continue
        _ensure_knowledge_index(root, force=force_refresh)
        root_index = _load_root_index(root)
        if not root_index:
            continue
        for module_info in _candidate_modules_from_root_index(root_index, system, module):
            module_index = _load_module_index(root, module_info)
            if not module_index:
                continue
            for metadata in module_index.get("documents", []):
                if normalized_doc_types and metadata.get("doc_type") not in normalized_doc_types:
                    continue
                key = metadata.get("ai_source_path") or metadata.get("file_path")
                if not key or key in seen_paths:
                    continue
                seen_paths.add(key)
                candidates.append(metadata)

    buckets: dict[str, list[dict[str, Any]]] = {"strong": [], "medium": [], "weak": [], "excluded": []}
    for metadata in candidates:
        score, matched_fields, matched_terms, reason = _score_metadata(query, metadata)
        relevance = _relevance_for_score(score)
        item = {
            "file_path": metadata["file_path"],
            "ai_source_path": metadata["ai_source_path"],
            "xmind_path": metadata["xmind_path"],
            "xmind_exists": metadata["xmind_exists"],
            "doc_type": metadata["doc_type"],
            "relevance": relevance,
            "score": score,
            "matched_fields": matched_fields,
            "matched_terms": matched_terms,
            "reason": reason,
        }
        buckets[relevance].append(item)

    for key in buckets:
        buckets[key].sort(key=lambda item: item["score"], reverse=True)

    selected_total = 0
    response = {}
    for output_key, bucket_key in [
        ("strong_related", "strong"),
        ("medium_related", "medium"),
        ("weak_related", "weak"),
        ("excluded", "excluded"),
    ]:
        remaining = max(0, limit - selected_total) if bucket_key != "excluded" else limit
        response[output_key] = buckets[bucket_key][:remaining]
        if bucket_key != "excluded":
            selected_total += len(response[output_key])

    response["retrieval_keywords"] = query
    if selected_total == 0:
        response["excluded"] = []
        response["reasoning_summary"] = "未命中有效上下文，建议检查 system/module/keywords 是否正确。"
    else:
        response["reasoning_summary"] = "基于 system/module、业务对象、接口、状态、依赖、关键词和风险点的规则召回。"
    return response

def read_context_documents(documents: list[dict[str, Any]], max_chars_per_doc: int = DEFAULT_MAX_CHARS_PER_DOC) -> dict[str, Any]:
    """读取 search_context 返回的 AI source 文档；不会读取 .xmind。"""
    max_chars = max(1, min(max_chars_per_doc, DEFAULT_MAX_CHARS_PER_DOC))
    total_chars = 0
    results = []
    errors = []
    for document in documents:
        raw_path = document.get("ai_source_path") or document.get("file_path")
        if not raw_path:
            errors.append({"document": document, "error": "missing ai_source_path"})
            continue
        try:
            path = _resolve_allowed_path(str(raw_path))
            text = _read_text_limited(path)
            remaining = max(0, MAX_TOTAL_RETURN_CHARS - total_chars)
            if remaining <= 0:
                break
            allowed = min(max_chars, remaining)
            content = text[:allowed]
            total_chars += len(content)
            truncated = len(text) > allowed
            metadata = _metadata_for_path(path)
            results.append(
                {
                    "file_path": metadata["file_path"],
                    "ai_source_path": metadata["ai_source_path"],
                    "xmind_path": metadata["xmind_path"],
                    "xmind_exists": metadata["xmind_exists"],
                    "doc_type": document.get("doc_type") or metadata["doc_type"],
                    "content": content,
                    "truncated": truncated,
                }
            )
        except Exception as exc:
            errors.append({"document": document, "error": str(exc)})
    return {"documents": results, "errors": errors}
