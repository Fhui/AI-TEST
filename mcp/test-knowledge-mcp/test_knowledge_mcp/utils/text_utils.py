"""文本工具：提供标题提取、关键词清洗、去重和版本号识别能力。"""

from __future__ import annotations

import csv
import json
import re
from typing import Iterable
from xml.etree import ElementTree

from ..config import CHINESE_STOPWORDS


def _first_markdown_title(text: str, fallback: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            return stripped.lstrip("#").strip() or fallback
    return fallback

def _json_title(text: str, fallback: str) -> str:
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        return fallback
    if isinstance(value, dict):
        for key in ("title", "name", "summary"):
            if isinstance(value.get(key), str) and value[key].strip():
                return value[key].strip()
    return fallback

def _csv_keywords(text: str) -> list[str]:
    sample = text.splitlines()[:20]
    if not sample:
        return []
    try:
        reader = csv.reader(sample)
        rows = list(reader)
    except csv.Error:
        return []
    if not rows:
        return []
    return [cell.strip() for cell in rows[0] if cell.strip()]

def _is_noise_keyword(value: str) -> bool:
    cleaned = value.strip().strip("`'\"，,。；;：:()[]{}")
    if len(cleaned) < 2:
        return True
    if cleaned.isdigit():
        return True
    if re.fullmatch(r"[\u4e00-\u9fff]+", cleaned) and cleaned in CHINESE_STOPWORDS:
        return True
    return False

def _opml_title(text: str, fallback: str) -> str:
    try:
        root = ElementTree.fromstring(text)
    except ElementTree.ParseError:
        return fallback
    title = root.findtext(".//title")
    return title.strip() if title and title.strip() else fallback

def _unique(values: Iterable[str], limit: int = 30) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        cleaned = value.strip().strip("`'\"，,。；;：:()[]{}")
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        result.append(cleaned)
        if len(result) >= limit:
            break
    return result

def _extract_version(*values: str) -> str:
    for value in values:
        match = re.search(r"(?i)(?:v\s*)?\d+(?:\.\d+){1,3}", value or "")
        if match:
            return re.sub(r"\s+", "", match.group(0))
    return ""
