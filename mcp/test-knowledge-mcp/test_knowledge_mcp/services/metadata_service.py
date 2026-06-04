"""Metadata 提取服务：解析 AI source 文档并维护 Markdown/XMind 配对信息。"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from ..config import (
    AI_SOURCE_EXTENSIONS,
    DOC_TYPE_DIRS,
    FRONTMATTER_FIELDS,
    FRONTMATTER_LIST_FIELDS,
    PREVIEW_ONLY_EXTENSIONS,
    READABLE_AI_EXTENSIONS,
    RISK_KEYWORDS,
    ROLE_KEYWORDS,
    SUPPORTED_DOC_TYPES,
    TECHNICAL_CAMEL_SUFFIXES,
)
from ..security import _assert_allowed_path, _resolve_allowed_path
from ..utils.atomic_io import _read_text_limited
from ..utils.path_utils import _display_path, _relative_to_allowed_root
from ..utils.text_utils import (
    _csv_keywords,
    _extract_version,
    _first_markdown_title,
    _is_noise_keyword,
    _json_title,
    _opml_title,
    _unique,
)


def _detect_doc_type(path: Path) -> str:
    lower_name = path.name.lower()
    lower_parts = [part.lower() for part in path.parts]
    if lower_name == "module-map.md":
        return "module_map"
    if lower_name == "upstream-downstream.md":
        return "upstream_downstream"
    for doc_type in DOC_TYPE_DIRS:
        if doc_type in lower_parts:
            return doc_type
    return "unknown"

def _path_context(path: Path) -> tuple[str, str]:
    parts = path.resolve(strict=False).parts
    system = ""
    module = ""
    if "systems" in parts:
        index = parts.index("systems")
        if len(parts) > index + 1:
            system = parts[index + 1]
        if len(parts) > index + 2 and parts[index + 2] not in {"module-map.md"}:
            module = parts[index + 2]
    elif "shared" in parts:
        index = parts.index("shared")
        system = "shared"
        if len(parts) > index + 1:
            module = parts[index + 1]
    else:
        relative = _relative_to_allowed_root(path)
        if relative is not None:
            relative_parts = relative.parts
            if (
                len(relative_parts) >= 4
                and relative_parts[0] not in {"systems", "shared"}
                and relative_parts[2].lower() in DOC_TYPE_DIRS
            ):
                system = relative_parts[0]
                module = relative_parts[1]
    return system, module

def _same_stem_xmind_path(path: Path) -> Path:
    return path.with_suffix(".xmind")

def _same_stem_markdown_path(path: Path) -> Path:
    return path.with_suffix(".md")

def _pairing_info(path: Path, doc_type: str) -> dict[str, Any]:
    suffix = path.suffix.lower()
    if doc_type != "testcase":
        return {
            "ai_source_path": _display_path(path) if suffix in READABLE_AI_EXTENSIONS else None,
            "xmind_path": None,
            "xmind_exists": False,
        }

    if suffix == ".md":
        xmind_path = _same_stem_xmind_path(path)
        exists = xmind_path.exists()
        return {
            "ai_source_path": _display_path(path),
            "xmind_path": _display_path(xmind_path) if exists else None,
            "xmind_exists": exists,
        }

    if suffix == ".xmind":
        ai_path = _same_stem_markdown_path(path)
        return {
            "ai_source_path": _display_path(ai_path) if ai_path.exists() else None,
            "xmind_path": _display_path(path),
            "xmind_exists": True,
        }

    return {
        "ai_source_path": _display_path(path) if suffix in READABLE_AI_EXTENSIONS else None,
        "xmind_path": None,
        "xmind_exists": False,
    }

def _extract_labeled_values(text: str, labels: list[str]) -> list[str]:
    values: list[str] = []
    label_pattern = "|".join(re.escape(label) for label in labels)
    pattern = re.compile(rf"(?:{label_pattern})\s*[:：]\s*([^\n\r]+)", re.IGNORECASE)
    for match in pattern.finditer(text):
        raw = match.group(1)
        values.extend(re.split(r"[,，、;/\s]+", raw))
    return _unique(values)

def _extract_keywords(text: str, path: Path, doc_type: str) -> list[str]:
    words: list[str] = []
    words.extend(re.split(r"[-_.\s/]+", path.stem))
    words.append(doc_type)
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            words.extend(re.split(r"[\s#：:,，/、()（）]+", stripped))
    words.extend(re.findall(r"[\u4e00-\u9fff]{2,8}", text[:10000]))
    words.extend(re.findall(r"\b[A-Za-z][A-Za-z0-9_]{2,30}\b", text[:10000]))
    return _unique((word for word in words if not _is_noise_keyword(word)), limit=60)

def _frontmatter_lines(text: str) -> list[str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return []
    result = []
    for line in lines[1:]:
        if line.strip() == "---":
            break
        result.append(line)
    return result

def _split_frontmatter_scalar(value: str) -> list[str]:
    stripped = value.strip().strip("[]")
    if not stripped:
        return []
    return _unique(re.split(r"[,，、;/]+", stripped), limit=60)

def _parse_frontmatter(text: str) -> tuple[dict[str, Any], list[str]]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, []

    metadata: dict[str, Any] = {}
    warnings: list[str] = []
    current_list_key: str | None = None
    closed = False

    for line_number, line in enumerate(lines[1:], start=2):
        stripped = line.strip()
        if stripped == "---":
            closed = True
            break
        if not stripped or stripped.startswith("#"):
            continue

        list_match = re.match(r"^\s*-\s*(.+?)\s*$", line)
        if list_match:
            if current_list_key is None:
                warnings.append(f"frontmatter line {line_number}: list item without a key")
                continue
            metadata.setdefault(current_list_key, []).append(list_match.group(1).strip().strip("'\""))
            continue

        key_match = re.match(r"^([A-Za-z_][A-Za-z0-9_-]*)\s*:\s*(.*)$", stripped)
        if not key_match:
            warnings.append(f"frontmatter line {line_number}: cannot parse line")
            current_list_key = None
            continue

        key = key_match.group(1).strip().replace("-", "_")
        raw_value = key_match.group(2).strip()
        current_list_key = key if key in FRONTMATTER_LIST_FIELDS else None
        if key not in FRONTMATTER_FIELDS:
            continue

        if key in FRONTMATTER_LIST_FIELDS:
            metadata[key] = _split_frontmatter_scalar(raw_value) if raw_value else []
        else:
            metadata[key] = raw_value.strip("'\"") if raw_value else ""

    if not closed:
        return {}, ["frontmatter is not closed"]

    return metadata, warnings

def _business_object_candidate_lines(text: str) -> list[str]:
    label_pattern = re.compile(r"(业务对象|核心对象|business_objects|business object)\s*[:：]", re.IGNORECASE)
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#") or label_pattern.search(stripped):
            lines.append(stripped)
    lines.extend(_frontmatter_lines(text))
    return lines

def _extract_camelcase_business_objects(text: str) -> list[str]:
    values = []
    for line in _business_object_candidate_lines(text):
        values.extend(re.findall(r"\b[A-Z][a-z]+(?:[A-Z][a-z0-9]+)+\b", line))
    return [
        value
        for value in values
        if not any(value.endswith(suffix) for suffix in TECHNICAL_CAMEL_SUFFIXES)
    ]

def _detect_testcase_markdown_structure(text: str) -> dict[str, Any]:
    stripped = text.strip()
    frontmatter, _warnings = _parse_frontmatter(text)
    has_case_id = bool(re.search(r"\b(?:TC|CASE)[-_ ]?\d+\b", text, re.IGNORECASE))
    has_steps = bool(re.search(r"\bsteps?\b|步骤", text, re.IGNORECASE))
    has_expected = bool(re.search(r"\bexpected\b|预期", text, re.IGNORECASE))
    has_priority = bool(re.search(r"\bpriority\b|\bP[0-3]\b|优先级", text, re.IGNORECASE))
    heading_count = len(re.findall(r"(?m)^#{2,6}\s+\S+", text))
    nested_bullet_count = len(re.findall(r"(?m)^\s{2,}[-*]\s+\S+", text))
    has_tree_structure = heading_count >= 2 or nested_bullet_count >= 2
    frontmatter_testcase = frontmatter.get("doc_type") == "testcase"

    signals = [
        has_case_id,
        has_steps and has_expected,
        has_priority,
        has_tree_structure,
        frontmatter_testcase,
    ]
    if not stripped:
        confidence = 0.0
    else:
        confidence = min(1.0, sum(1 for signal in signals if signal) / 3)

    return {
        "has_case_id": has_case_id,
        "has_steps": has_steps,
        "has_expected": has_expected,
        "has_priority": has_priority,
        "has_tree_structure": has_tree_structure,
        "confidence": confidence,
    }

def _extract_from_text(path: Path, doc_type: str, text: str) -> dict[str, Any]:
    fallback_title = path.stem
    suffix = path.suffix.lower()
    if suffix == ".json":
        title = _json_title(text, fallback_title)
    elif suffix == ".opml":
        title = _opml_title(text, fallback_title)
    else:
        title = _first_markdown_title(text, fallback_title)

    version = _extract_version(path.stem, text[:4000])

    route_matches = re.findall(
        r"(?:\b(?:GET|POST|PUT|DELETE|PATCH)\s+)?(/[A-Za-z0-9_./{}:-]+)",
        text,
    )
    interfaces = [
        item.rstrip(".,;，。；")
        for item in route_matches
        if not item.startswith("//") and "." not in item.rsplit("/", 1)[-1]
    ]

    states = re.findall(r"\b[A-Z][A-Z0-9_]{2,}\b", text)
    roles = [role for role in ROLE_KEYWORDS if re.search(re.escape(role), text, re.IGNORECASE)]
    risk_points = []
    for line in text.splitlines():
        if any(keyword.lower() in line.lower() for keyword in RISK_KEYWORDS):
            risk_points.append(line.strip("- *\t "))

    business_objects = _extract_labeled_values(text, ["业务对象", "核心对象", "对象", "business_objects", "business object"])
    business_objects.extend(_extract_camelcase_business_objects(text))

    upstream = _extract_labeled_values(text, ["上游依赖", "upstream", "upstream_dependencies"])
    downstream = _extract_labeled_values(text, ["下游依赖", "downstream", "downstream_dependencies"])

    keywords = _extract_keywords(text, path, doc_type)
    if suffix == ".csv":
        keywords.extend(_csv_keywords(text))

    return {
        "version": version,
        "title": title,
        "business_objects": _unique(business_objects),
        "interfaces": _unique(interfaces),
        "states": _unique(states),
        "roles": _unique(roles),
        "upstream_dependencies": _unique(upstream),
        "downstream_dependencies": _unique(downstream),
        "keywords": _unique(keywords, limit=60),
        "risk_points": _unique(risk_points, limit=20),
    }

def _frontmatter_list_value(frontmatter: dict[str, Any], key: str) -> list[str] | None:
    if key not in frontmatter:
        return None
    value = frontmatter.get(key)
    if isinstance(value, list):
        return _unique(str(item) for item in value)
    if isinstance(value, str):
        return _split_frontmatter_scalar(value)
    return []

def _metadata_for_path(path: Path) -> dict[str, Any]:
    _assert_allowed_path(path)
    path_doc_type = _detect_doc_type(path)
    path_system, path_module = _path_context(path)
    suffix = path.suffix.lower()
    readable = suffix in AI_SOURCE_EXTENSIONS
    preview_only = suffix in PREVIEW_ONLY_EXTENSIONS
    warnings: list[str] = []
    frontmatter: dict[str, Any] = {}
    text = ""
    if readable and path.exists():
        text = _read_text_limited(path)
        frontmatter, warnings = _parse_frontmatter(text)

    doc_type = str(frontmatter.get("doc_type") or path_doc_type)
    if doc_type not in SUPPORTED_DOC_TYPES:
        warnings.append(f"unsupported frontmatter doc_type: {doc_type}")
        doc_type = path_doc_type
    system = str(frontmatter.get("system") or path_system)
    module = str(frontmatter.get("module") or path_module)
    pairing = _pairing_info(path, doc_type)

    extracted = {
        "version": "",
        "title": path.stem,
        "business_objects": [],
        "interfaces": [],
        "states": [],
        "roles": [],
        "upstream_dependencies": [],
        "downstream_dependencies": [],
        "keywords": _unique(re.split(r"[-_.\s]+", path.stem)),
        "risk_points": [],
    }
    if readable and path.exists():
        extracted = _extract_from_text(path, doc_type, text)
    path_version = _extract_version(path_module, path.stem)

    merged = {
        "version": frontmatter.get("version") or path_version or extracted["version"],
        "title": frontmatter.get("title") or extracted["title"] or path.stem,
        "business_objects": _frontmatter_list_value(frontmatter, "business_objects") if "business_objects" in frontmatter else extracted["business_objects"],
        "interfaces": _frontmatter_list_value(frontmatter, "interfaces") if "interfaces" in frontmatter else extracted["interfaces"],
        "states": _frontmatter_list_value(frontmatter, "states") if "states" in frontmatter else extracted["states"],
        "roles": _frontmatter_list_value(frontmatter, "roles") if "roles" in frontmatter else extracted["roles"],
        "upstream_dependencies": _frontmatter_list_value(frontmatter, "upstream_dependencies") if "upstream_dependencies" in frontmatter else extracted["upstream_dependencies"],
        "downstream_dependencies": _frontmatter_list_value(frontmatter, "downstream_dependencies") if "downstream_dependencies" in frontmatter else extracted["downstream_dependencies"],
        "keywords": _frontmatter_list_value(frontmatter, "keywords") if "keywords" in frontmatter else extracted["keywords"],
        "risk_points": _frontmatter_list_value(frontmatter, "risk_points") if "risk_points" in frontmatter else extracted["risk_points"],
    }

    return {
        "file_path": _display_path(path),
        **pairing,
        "preview_only": preview_only,
        "readable": readable,
        "doc_type": doc_type,
        "system": system,
        "module": module,
        "warnings": warnings,
        **merged,
    }

def extract_metadata(file_path: str) -> dict[str, Any]:
    """提取知识资产 metadata；.xmind 仅返回 preview metadata，不读取内容。"""
    path = _resolve_allowed_path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"file not found: {file_path}")
    if not path.is_file():
        raise ValueError(f"path is not a file: {file_path}")
    return _metadata_for_path(path)
