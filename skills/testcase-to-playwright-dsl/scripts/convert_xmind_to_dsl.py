#!/usr/bin/env python
"""Convert XMind-style Markdown testcases to Playwright UI DSL YAML.

The parser is conservative by design: when testcase Markdown lacks real
selectors, it emits data-testid placeholders plus TODO entries.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import re
from pathlib import Path
from typing import Any


ALLOWED_ACTIONS = {
    "goto",
    "click",
    "fill",
    "select",
    "upload",
    "wait_for",
    "assert_visible",
    "assert_text",
    "assert_state",
}

ACTION_KEYWORDS: list[tuple[str, str]] = [
    ("下拉选择", "select"),
    ("点击", "click"),
    ("提交", "click"),
    ("确认", "click"),
    ("选择", "click"),
    ("勾选", "click"),
    ("选中", "click"),
    ("输入", "fill"),
    ("填写", "fill"),
    ("上传", "upload"),
    ("等待", "wait_for"),
    ("显示", "assert_text"),
    ("查看", "assert_visible"),
    ("校验可见", "assert_visible"),
    ("校验文案", "assert_text"),
    ("提示", "assert_text"),
    ("状态", "assert_state"),
    ("结果", "assert_state"),
    ("删除", "click"),
    ("移除", "click"),
    ("搜索", "fill"),
    ("查询", "fill"),
]

UI_HINTS: list[tuple[str, str]] = [
    ("按钮", "button"),
    ("输入框", "input"),
    ("文本框", "input"),
    ("列表", "list"),
    ("表格", "table"),
    ("弹窗", "modal"),
    ("页面", "page"),
    ("菜单", "menu"),
    ("下拉框", "select"),
    ("复选框", "checkbox"),
    ("单选框", "radio"),
    ("链接", "link"),
]

ACTION_CLEANUP_WORDS = ["点击", "输入", "填写", "选择", "勾选", "查看", "显示", "选中", "上传"]
ACTION_INTENT_WORDS = ["点击", "提交", "确认", "输入", "填写", "勾选", "选中", "选择", "上传", "搜索", "查询"]
FIELD_CONNECTORS = ["和", "并", "同时", "以及", "、"]
COMPOUND_CONNECTOR_PATTERN = r"(?:和|并|同时|以及|、)"
GENERIC_SEMANTIC_TERMS: list[tuple[str, str]] = [
    ("某入口", "entry"),
    ("入口", "entry"),
    ("某字段", "field"),
    ("字段", "field"),
    ("某选项", "option"),
    ("选项", "option"),
    ("协议", "agreement"),
    ("确认", "confirm"),
    ("提交", "submit"),
    ("取消", "cancel"),
    ("保存", "save"),
    ("文件", "file"),
    ("图片", "image"),
    ("文案", "text"),
    ("提示", "message"),
    ("内容", "content"),
    ("表单", "form"),
    ("页面", "page"),
    ("入口", "entry"),
    ("按钮", "button"),
    ("列表", "list"),
    ("表格", "table"),
    ("弹窗", "modal"),
    ("菜单", "menu"),
    ("链接", "link"),
]

NON_CASE_SECTIONS = {
    "待确认项",
    "歧义点与缺失点",
    "缺失点",
    "说明",
    "备注",
}


def strip_md(line: str) -> str:
    line = line.strip()
    line = re.sub(r"^#{1,6}\s*", "", line)
    line = re.sub(r"^[-*+]\s+", "", line)
    line = re.sub(r"^\d+[.)、]\s*", "", line)
    return line.strip()


def yaml_quote(value: Any) -> str:
    if value is None:
        return '""'
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    text = str(value)
    text = text.replace("\\", "\\\\").replace('"', '\\"')
    text = text.replace("\n", "\\n")
    return f'"{text}"'


def dump_yaml(data: Any, indent: int = 0) -> list[str]:
    pad = " " * indent
    lines: list[str] = []
    if isinstance(data, dict):
        if not data:
            return [pad + "{}"]
        for key, value in data.items():
            if isinstance(value, (dict, list)):
                if value:
                    lines.append(f"{pad}{key}:")
                    lines.extend(dump_yaml(value, indent + 2))
                else:
                    lines.append(f"{pad}{key}: {{}}" if isinstance(value, dict) else f"{pad}{key}: []")
            else:
                lines.append(f"{pad}{key}: {yaml_quote(value)}")
    elif isinstance(data, list):
        if not data:
            return [pad + "[]"]
        for item in data:
            if isinstance(item, dict):
                if not item:
                    lines.append(f"{pad}- {{}}")
                    continue
                first = True
                for key, value in item.items():
                    prefix = "- " if first else "  "
                    if isinstance(value, (dict, list)):
                        lines.append(f"{pad}{prefix}{key}:")
                        lines.extend(dump_yaml(value, indent + 4))
                    else:
                        lines.append(f"{pad}{prefix}{key}: {yaml_quote(value)}")
                    first = False
            elif isinstance(item, list):
                lines.append(f"{pad}-")
                lines.extend(dump_yaml(item, indent + 2))
            else:
                lines.append(f"{pad}- {yaml_quote(item)}")
    else:
        lines.append(pad + yaml_quote(data))
    return lines


def normalize_priority(text: str) -> str:
    match = re.search(r"\bP[0-3]\b", text, re.I)
    return match.group(0).upper() if match else "P1"


def parse_priority(text: str) -> str | None:
    match = re.search(r"\bP[0-3]\b", text, re.I)
    return match.group(0).upper() if match else None


def extract_value(text: str, labels: list[str]) -> str:
    label_pattern = "|".join(re.escape(label) for label in labels)
    match = re.search(rf"(?:{label_pattern})\s*[:：,，]\s*(.+)$", text)
    return match.group(1).strip() if match else ""


def extract_labeled_value(text: str, labels: list[str]) -> str | None:
    label_pattern = "|".join(re.escape(label) for label in labels)
    match = re.match(rf"^(?:{label_pattern})\s*[:：,，]\s*(.*)$", text, re.I)
    return match.group(1).strip() if match else None


def markdown_item(raw_line: str) -> tuple[int, str] | None:
    if not raw_line.strip():
        return None
    expanded = raw_line.replace("\t", "    ")
    indent = len(expanded) - len(expanded.lstrip(" "))
    text = expanded.strip()
    text = re.sub(r"^#{1,6}\s*", "", text)
    text = re.sub(r"^[-*+]\s+", "", text)
    text = re.sub(r"^\d+[.)、]\s*", "", text)
    text = text.strip()
    return (indent, text) if text else None


def is_expected_label(text: str) -> bool:
    return extract_labeled_value(text, ["预期结果", "预期", "期望", "断言", "检查点"]) is not None


def slugify(text: str, fallback: str) -> str:
    result = text
    for zh, en in GENERIC_SEMANTIC_TERMS:
        result = result.replace(zh, f" {en} ")
    result = re.sub(r"https?://\S+", " url ", result)
    result = re.sub(r"[^A-Za-z0-9]+", "_", result).strip("_").lower()
    result = re.sub(r"_+", "_", result)
    if not result:
        hash_hex = hashlib.md5(text.encode("utf-8")).hexdigest()[:8]
        result = f"cn_{hash_hex}"
    if re.match(r"^\d", result):
        result = f"{fallback}_{result}"
    return result[:64].strip("_") or fallback


def action_for(text: str) -> str | None:
    if re.search(r"(?:打开|访问)\s*https?://\S+", text):
        return "goto"
    for keyword, action in ACTION_KEYWORDS:
        if keyword in text:
            return action
    return None


def action_type_suffix(action: str, text: str) -> str:
    compact = _compact_text(text)
    if action == "fill":
        return "input"
    if action == "select":
        return "select"
    if action == "upload":
        return "upload"
    if action == "click" and re.search(r"(?:勾选|选中|复选框|checkbox)", compact, re.I):
        return "checkbox"
    if action == "click":
        return "button"
    if action == "goto":
        return "page"
    return "element"


def semantic_text_for(text: str, action: str) -> str:
    source = strip_md(text)
    source = re.sub(r"https?://\S+", " ", source)
    source = re.sub(r"^\s*(?:ts|TS|步骤|操作步骤|测试步骤)\s*[:：,，]\s*", "", source)
    for keyword in ACTION_CLEANUP_WORDS:
        source = source.replace(keyword, " ")
    source = re.sub(r"(?:按钮|输入框|文本框|复选框|下拉框|单选框)$", " ", source)
    source = re.sub(r"[\"'“”‘’\[\]【】()（）<>《》，,。.:：；;、]", " ", source)
    source = re.sub(r"\s+", " ", source).strip()
    if not source and action == "upload":
        return "file"
    return source


def selector_key_for(text: str, action: str, index: int) -> str:
    suffix = action_type_suffix(action, text)
    source = semantic_text_for(text, action)
    for hint, mapped in UI_HINTS:
        if hint in source and mapped == suffix:
            source = source.replace(hint, " ")
    base = slugify(source, f"element_{index:03d}")
    if suffix:
        if base == suffix or base.endswith(f"_{suffix}"):
            key = base
        else:
            key = f"{base}_{suffix}"
    else:
        key = base
    return re.sub(r"_+", "_", key).strip("_")


def dedupe_keep_order(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        value = value.strip()
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result


def candidate_labels(text: str, action: str) -> list[str]:
    labels: list[str] = []
    quoted = extract_quoted_text(text)
    if quoted:
        labels.append(quoted)
    semantic = semantic_text_for(text, action)
    first_atom = re.split(COMPOUND_CONNECTOR_PATTERN, semantic, maxsplit=1)[0]
    first_atom = re.sub(r"^(?:进入|打开|访问|跳转|提交|确认)", "", first_atom)
    first_atom = first_atom.strip(" \"'“”‘’[]【】()（）<>《》，,。.:：；;、")
    if first_atom and not re.fullmatch(r"cn_[0-9a-f]{8}", first_atom):
        labels.append(first_atom)
    return dedupe_keep_order(labels)


def selector_candidates_for(text: str, action: str) -> list[str]:
    candidates: list[str] = []
    labels = candidate_labels(text, action)
    combined = _compact_text(text) + "".join(labels)
    is_checkbox = bool(re.search(r"(?:勾选|选中|协议|同意|复选框|checkbox)", combined, re.I))

    for label in labels:
        if action == "click":
            if is_checkbox:
                candidates.extend([
                    f'role=checkbox[name="{label}"]',
                    f"text={label}",
                ])
            else:
                candidates.extend([
                    f'role=button[name="{label}"]',
                    f'role=link[name="{label}"]',
                    f"text={label}",
                ])
        elif action == "fill":
            candidates.extend([
                f"label={label}",
                f"placeholder={label}",
                f'role=textbox[name="{label}"]',
            ])
        elif action in {"assert_text", "assert_visible"}:
            candidates.append(f"text={label}")
        elif action == "select":
            candidates.extend([
                f"label={label}",
                f'role=combobox[name="{label}"]',
            ])
        elif action == "upload":
            candidates.append(f"label={label}")

    return dedupe_keep_order(candidates)


def _compact_text(text: str) -> str:
    return re.sub(r"\s+", "", strip_md(text))


def _clean_locator_name(text: str) -> str:
    text = _compact_text(text)
    text = re.sub(r"(按钮|输入框|文本框|复选框)$", "", text)
    return text.strip(" \"'“”‘’[]【】()（）<>《》，,。.:：；;、")


def extract_quoted_text(text: str) -> str | None:
    text = strip_md(text)
    match = re.search(r"[“\"]([^”\"]+)[”\"]", text)
    if match:
        return match.group(1).strip()
    match = re.search(r"[‘']([^’']+)[’']", text)
    if match:
        return match.group(1).strip()
    return None


def is_captcha(text: str) -> bool:
    compact = _compact_text(text).lower()
    return any(keyword in compact for keyword in ["验证码", "图形验证", "滑块", "captcha", "极验", "手动完成验证"])


def is_button_action(text: str) -> tuple[bool, str]:
    compact = _compact_text(text)
    match = re.match(r"^(?:点击|提交|确认)(.+?)(?:按钮)?$", compact)
    if not match:
        return (False, "")
    name = _clean_locator_name(match.group(1))
    return (bool(name), name)


def is_input_action(text: str) -> tuple[bool, str]:
    compact = _compact_text(text)
    match = re.match(r"^(?:输入|填写)(.+)$", compact)
    if not match:
        return (False, "")
    name = _clean_locator_name(match.group(1))
    return (bool(name), name)


def is_checkbox_action(text: str) -> tuple[bool, str]:
    compact = _compact_text(text)
    match = re.match(r"^(?:勾选|选中)(.+)$", compact)
    if not match:
        return (False, "")
    name = _clean_locator_name(match.group(1))
    return (bool(name), name)


def is_text_assertion(text: str) -> tuple[bool, str]:
    compact = _compact_text(text)
    if not re.match(r"^(?:显示|提示|看到|校验文案)", compact):
        return (False, "")
    quoted = extract_quoted_text(text)
    if quoted:
        return (True, quoted)
    match = re.match(r"^(?:显示|提示|看到|校验文案)(.+)$", compact)
    if not match:
        return (False, "")
    candidate = _clean_locator_name(match.group(1))
    if not candidate:
        return (False, "")
    if any(keyword in candidate for keyword in ["页面", "状态", "已输入", "加载完成", "PRD", "规则", "未说明"]):
        return (False, "")
    return (True, candidate)


def is_page_state(text: str) -> bool:
    compact = _compact_text(text)
    if re.search(r"(?:页面加载完成|加载完成|字段展示已输入状态|PRD未说明|规则未说明)", compact):
        return True
    if re.search(r"(?:页面|状态|流程|表单).*(?:展示|进入|变更|完成|成功|失败)", compact):
        return True
    if re.search(r"(?:展示|进入).*(?:页面|表单|流程)", compact):
        return True
    return False


def is_compound_navigation(text: str) -> bool:
    compact = _compact_text(text)
    return bool(re.match(r"^进入.+(?:页面|表单|流程)$", compact))


def compound_action_parts(text: str) -> list[tuple[str, str]]:
    compact = _compact_text(text)
    if is_compound_navigation(text):
        return []

    match = re.match(rf"^(输入|填写)(.+?){COMPOUND_CONNECTOR_PATTERN}(.+)$", compact)
    if match:
        left, right = match.group(2), match.group(3)
        right_action = action_for(right)
        if right_action in {"click", "fill", "select", "upload"}:
            right_part = right
        else:
            right_action = "fill"
            right_part = re.sub(r"^(?:输入|填写)", "", right)
        return [("fill", left), (right_action, right_part)] if left and right_part else []

    parts: list[tuple[str, str]] = []
    tokens = re.split(COMPOUND_CONNECTOR_PATTERN, compact)
    for token in tokens:
        if not token:
            continue
        action = action_for(token)
        if action in {"click", "fill", "select", "upload"}:
            for keyword, mapped_action in ACTION_KEYWORDS:
                if mapped_action == action and keyword in token:
                    label = token.replace(keyword, "", 1)
                    if label or keyword in {"提交", "确认"}:
                        parts.append((action, token if label else keyword))
                    break
    return parts if len(parts) > 1 else []


def is_compound_action(text: str) -> bool:
    if is_compound_navigation(text):
        return True
    return bool(compound_action_parts(text))


def explicit_selector_from_text(text: str) -> str:
    patterns = [
        r"\[data-testid=(?:\"[^\"]+\"|'[^']+')\]",
        r"#[A-Za-z][A-Za-z0-9_-]*",
        r"\.[A-Za-z][A-Za-z0-9_-]*",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(0)
    return ""


def infer_selector(ts_text: str) -> tuple[str, str]:
    """
    Infer a Playwright semantic selector from testcase text.

    Returns:
    (selector, status)
    """
    explicit_selector = explicit_selector_from_text(ts_text)
    if explicit_selector:
        return (explicit_selector, "confirmed")
    return ("", "todo")


def parse_markdown(text: str) -> dict[str, Any]:
    meta = {"system": "", "version": "", "module": "", "description": ""}
    cases: list[dict[str, Any]] = []
    current_case: dict[str, Any] | None = None
    current_step: dict[str, Any] | None = None
    stack: list[dict[str, Any]] = []

    def new_case(title: str, line: str) -> dict[str, Any]:
        case = {
            "tc": title,
            "tp": "",
            "module": meta["module"],
            "priority": normalize_priority(line),
            "preconditions": [],
            "steps": [],
            "expected": [],
            "unsupported": [],
        }
        cases.append(case)
        return case

    for raw_line in text.splitlines():
        item = markdown_item(raw_line)
        if item is None:
            continue
        indent, line = item

        if indent == 0 and line in NON_CASE_SECTIONS:
            current_case = None
            current_step = None
            stack.clear()
            continue

        system = extract_value(line, ["系统", "System", "system"])
        version = extract_value(line, ["版本", "Version", "version"])
        module = extract_value(line, ["模块", "Module", "module"])
        if system:
            meta["system"] = system
            continue
        if version:
            meta["version"] = version
            continue
        if module:
            meta["module"] = module
            if current_case:
                current_case["module"] = module
            continue

        while stack and indent <= stack[-1]["indent"]:
            stack.pop()
        parent = stack[-1] if stack else None

        tc_value = extract_labeled_value(line, ["tc", "TC", "用例", "测试用例"])
        if tc_value is not None:
            current_case = new_case(tc_value or line, line)
            current_step = None
            stack.append({"indent": indent, "kind": "tc", "case": current_case})
            continue

        if current_case is None:
            continue

        ts_value = extract_labeled_value(line, ["ts", "TS", "步骤", "操作步骤", "测试步骤"])
        if ts_value is not None:
            current_step = {"ts": ts_value or line, "expected": []}
            current_case["steps"].append(current_step)
            stack.append({"indent": indent, "kind": "ts", "case": current_case, "step": current_step})
            continue

        ti_value = extract_labeled_value(line, ["ti", "TI", "优先级", "Priority", "priority"])
        if ti_value is not None:
            priority = parse_priority(ti_value)
            if priority:
                current_case["priority"] = priority
            else:
                current_case["unsupported"].append({
                    "source_case": current_case["tc"],
                    "source_step": line,
                    "reason": "ti 优先级只能解析为 P0/P1/P2/P3",
                    "suggestion": "将 ti 调整为 P0、P1、P2 或 P3",
                })
            continue

        tp_value = extract_labeled_value(line, ["tp", "TP", "前置条件", "前置", "Precondition", "precondition"])
        if tp_value is not None:
            if tp_value:
                current_case["preconditions"].append(tp_value)
            stack.append({"indent": indent, "kind": "tp", "case": current_case})
            continue

        expected_value = extract_labeled_value(line, ["预期结果", "预期", "期望", "断言", "检查点"])
        if expected_value is not None:
            if expected_value:
                if parent and parent["kind"] == "ts":
                    parent["step"]["expected"].append(expected_value)
                    stack.append({"indent": indent, "kind": "expected", "case": current_case})
                elif current_step is not None:
                    current_step["expected"].append(expected_value)
                else:
                    current_case["expected"].append(expected_value)
            continue

        if parent and parent["kind"] == "ts":
            parent["step"]["expected"].append(line)
            stack.append({"indent": indent, "kind": "expected", "case": current_case})
            continue

        if parent and parent["kind"] in {"tp", "tp_line"}:
            current_case["preconditions"].append(line)
            stack.append({"indent": indent, "kind": "tp_line", "case": current_case})
            continue

        # Legacy flat format fallback.
        if any(keyword in line for keyword, _ in ACTION_KEYWORDS):
            current_step = {"ts": line, "expected": []}
            current_case["steps"].append(current_step)
            stack.append({"indent": indent, "kind": "ts", "case": current_case, "step": current_step})

    for case in cases:
        case["tp"] = "\n".join(case["preconditions"])

    return {"meta": meta, "cases": cases}


def build_dsl(parsed: dict[str, Any], source: Path, project_root: Path) -> dict[str, Any]:
    selectors: dict[str, Any] = {}
    todos: list[dict[str, str]] = []
    unsupported: list[dict[str, str]] = []
    flows: list[dict[str, Any]] = []
    source_display = "./" + str(source.relative_to(project_root)) if source.is_relative_to(project_root) else str(source)

    def todo_reason_for(source_text: str, reason_kind: str) -> str:
        if is_captcha(source_text):
            return "验证码/图形验证不适合自动化执行，需要人工处理或测试环境绕过"
        if reason_kind == "operation":
            return "无法在 DSL 阶段确认 DOM selector，需 enrichment probe 校准"
        if reason_kind == "page_state":
            return "expected 为页面/业务状态，不生成 selector"
        if reason_kind == "prd_unclear":
            return "PRD 未提供明确 UI 信息"
        if reason_kind == "compound":
            return "复合步骤需拆分为原子操作"
        return "无法在 DSL 阶段确认 DOM selector，需 enrichment probe 校准"

    def add_todo(
        todo_type: str,
        key: str,
        source_case: str,
        source_step: str,
        reason_kind: str,
    ) -> None:
        todos.append({
            "type": todo_type,
            "key": key,
            "source_case": source_case,
            "source_step": source_step,
            "reason": todo_reason_for(source_step, reason_kind),
        })

    def register_selector(
        selector_key: str,
        source_text: str,
        source_case: str,
        source_step: str,
        reason_kind: str = "operation",
        action: str = "",
    ) -> None:
        inferred_selector, status = infer_selector(source_text)
        if status == "confirmed":
            selector_value = inferred_selector
            candidates: list[str] = []
        else:
            selector_value = f'[data-testid="{selector_key}"]'
            candidates = selector_candidates_for(source_text, action)

        existing = selectors.get(selector_key)
        if existing:
            if existing.get("status") == "todo" and status == "confirmed":
                existing["selector"] = selector_value
                existing["status"] = "confirmed"
                existing["candidates"] = []
                todos[:] = [todo for todo in todos if todo.get("key") != selector_key]
            elif existing.get("status") == "todo" and candidates:
                existing["candidates"] = dedupe_keep_order(list(existing.get("candidates", [])) + candidates)
            return

        selectors[selector_key] = {
            "selector": selector_value,
            "description": source_text,
            "source": source_text,
            "status": status,
            "candidates": candidates,
        }
        if status == "todo":
            add_todo("selector", selector_key, source_case, source_step, reason_kind)

    def add_unsupported(source_case: str, source_step: str, reason: str, suggestion: str) -> None:
        unsupported.append({
            "source_case": source_case,
            "source_step": source_step,
            "reason": reason,
            "suggestion": suggestion,
        })

    def add_wait_placeholder(
        steps: list[dict[str, Any]],
        source_ts: str,
        comment: str,
        source_expected: str = "",
        expected: str = "",
    ) -> None:
        steps.append({
            "id": f"step_{len(steps) + 1:03d}",
            "source_ts": source_ts,
            "source_expected": source_expected,
            "action": "wait_for",
            "target": "",
            "value": "",
            "url": "",
            "expected": expected,
            "timeout_ms": 0,
            "optional": True,
            "comment": comment,
        })

    def add_expected_state_step(
        steps: list[dict[str, Any]],
        source_ts: str,
        expected: str,
        source_case: str,
    ) -> None:
        reason_kind = "prd_unclear" if re.search(r"(?:PRD|规则).*(?:未说明|不明确)", expected) else "page_state"
        add_todo("expected", "", source_case, expected, reason_kind)
        add_wait_placeholder(
            steps,
            source_ts,
            "expected is page/business state, selector not generated",
            source_expected=expected,
            expected=expected,
        )

    def add_action_step(
        steps: list[dict[str, Any]],
        source_ts: str,
        action: str,
        selector_key: str,
        url: str = "",
    ) -> None:
        steps.append({
            "id": f"step_{len(steps) + 1:03d}",
            "source_ts": source_ts,
            "action": action,
            "target": "" if action == "goto" else selector_key,
            "value": "",
            "url": url,
            "expected": "",
            "source_expected": "",
            "timeout_ms": 5000,
            "optional": False,
            "comment": "",
        })

    for flow_index, case in enumerate(parsed["cases"], start=1):
        steps: list[dict[str, Any]] = []
        flow_id = f"flow_{flow_index:03d}"

        for step_index, source_step in enumerate(case["steps"], start=1):
            source_ts = source_step["ts"] if isinstance(source_step, dict) else str(source_step)
            if is_compound_action(source_ts):
                parts = compound_action_parts(source_ts)
                if parts:
                    for part_action, part_text in parts:
                        selector_key = selector_key_for(part_text, part_action, len(steps) + 1)
                        register_selector(selector_key, part_text, case["tc"], source_ts, action=part_action)
                        add_action_step(steps, source_ts, part_action, selector_key)
                    expected_items = source_step.get("expected", []) if isinstance(source_step, dict) else []
                    for expected in expected_items:
                        matched, _name = is_text_assertion(expected)
                        if matched:
                            action = "assert_text"
                            selector_key = selector_key_for(expected, action, len(steps) + 1)
                            register_selector(selector_key, expected, case["tc"], source_ts, action=action)
                            steps.append({
                                "id": f"step_{len(steps) + 1:03d}",
                                "source_ts": source_ts,
                                "source_expected": expected,
                                "action": action,
                                "target": selector_key,
                                "value": "",
                                "url": "",
                                "expected": expected,
                                "timeout_ms": 5000,
                                "optional": False,
                                "comment": "由 ts 子节点预期结果转换",
                            })
                        else:
                            add_expected_state_step(steps, source_ts, expected, case["tc"])
                    continue
                add_unsupported(
                    case["tc"],
                    source_ts,
                    "复合步骤无法自动拆分",
                    "将该步骤拆分为单一的 click/fill/check 等原子 UI 步骤",
                )
                add_todo("unsupported", "", case["tc"], source_ts, "compound")
                add_wait_placeholder(steps, source_ts, "compound navigation step, requires manual decomposition")
                continue

            if is_captcha(source_ts):
                add_unsupported(
                    case["tc"],
                    source_ts,
                    "验证码/图形验证不适合自动化执行，需要人工处理或测试环境绕过",
                    "使用测试环境绕过验证码，或由人工完成该步骤",
                )
                add_wait_placeholder(steps, source_ts, "unsupported manual step, see unsupported_steps")
                continue

            action = action_for(source_ts)
            if not action:
                if re.search(r"^(?:进入|打开|访问|跳转).*(?:页面|表单|流程)$", _compact_text(source_ts)):
                    add_unsupported(
                        case["tc"],
                        source_ts,
                        "复合步骤无法自动拆分",
                        "将导航意图拆分为明确 URL goto 或可定位的 click/wait_for 原子步骤",
                    )
                    add_todo("unsupported", "", case["tc"], source_ts, "compound")
                    add_wait_placeholder(steps, source_ts, "compound navigation step, requires manual decomposition")
                    continue
                add_unsupported(
                    case["tc"],
                    source_ts,
                    "未识别可映射的 UI 动作",
                    "人工拆解为 goto/click/fill/select/upload/wait_for/assert_* 步骤",
                )
                continue

            selector_key = selector_key_for(source_ts, action, step_index)
            url_match = re.search(r"https?://\S+", source_ts)
            if action == "goto" and not url_match:
                add_unsupported(
                    case["tc"],
                    source_ts,
                    "goto 缺少 URL 或启动方式",
                    "在步骤中补充明确 URL，或在自动化执行入口配置 baseURL/启动方式",
                )
                add_wait_placeholder(steps, source_ts, "goto url is not provided, see unsupported_steps")
                continue

            if action != "goto":
                register_selector(selector_key, source_ts, case["tc"], source_ts, action=action)

            add_action_step(
                steps,
                source_ts,
                action,
                selector_key,
                url_match.group(0) if action == "goto" and url_match else "",
            )

            expected_items = source_step.get("expected", []) if isinstance(source_step, dict) else []
            for expected in expected_items:
                if is_captcha(expected):
                    add_unsupported(
                        case["tc"],
                        expected,
                        "验证码/图形验证不适合自动化执行，需要人工处理或测试环境绕过",
                        "使用测试环境绕过验证码，或由人工完成该步骤",
                    )
                    add_wait_placeholder(
                        steps,
                        source_ts,
                        "unsupported manual step, see unsupported_steps",
                        source_expected=expected,
                        expected=expected,
                    )
                    continue

                matched, _name = is_text_assertion(expected)
                if not matched:
                    add_expected_state_step(steps, source_ts, expected, case["tc"])
                    continue

                action = "assert_text"
                selector_key = selector_key_for(expected, action, len(steps) + 1)
                register_selector(selector_key, expected, case["tc"], source_ts, action=action)
                steps.append({
                    "id": f"step_{len(steps) + 1:03d}",
                    "source_ts": source_ts,
                    "source_expected": expected,
                    "action": action,
                    "target": selector_key,
                    "value": "",
                    "url": "",
                    "expected": expected,
                    "timeout_ms": 5000,
                    "optional": False,
                    "comment": "由 ts 子节点预期结果转换",
                })

        for expected in case["expected"]:
            if is_captcha(expected):
                add_unsupported(
                    case["tc"],
                    expected,
                    "验证码/图形验证不适合自动化执行，需要人工处理或测试环境绕过",
                    "使用测试环境绕过验证码，或由人工完成该步骤",
                )
                add_wait_placeholder(
                    steps,
                    expected,
                    "unsupported manual step, see unsupported_steps",
                    source_expected=expected,
                    expected=expected,
                )
                continue

            matched, _name = is_text_assertion(expected)
            if not matched:
                add_expected_state_step(steps, expected, expected, case["tc"])
                continue

            action = "assert_text"
            selector_key = selector_key_for(expected, action, len(steps) + 1)
            register_selector(selector_key, expected, case["tc"], expected, action=action)
            steps.append({
                "id": f"step_{len(steps) + 1:03d}",
                "source_ts": expected,
                "source_expected": expected,
                "action": action,
                "target": selector_key,
                "value": "",
                "url": "",
                "expected": expected,
                "timeout_ms": 5000,
                "optional": False,
                "comment": "由预期结果转换",
            })

        unsupported.extend(case.get("unsupported", []))

        flows.append({
            "id": flow_id,
            "name": case["tc"],
            "module": case["module"],
            "priority": case["priority"],
            "source_case": {
                "tc": case["tc"],
                "tp": case["tp"],
            },
            "tags": ["ui"],
            "preconditions": case["preconditions"],
            "steps": steps,
        })

    return {
        "schema_version": "1.0",
        "meta": {
            "system": parsed["meta"]["system"],
            "version": parsed["meta"]["version"],
            "module": parsed["meta"]["module"],
            "source": source_display,
            "generated_at": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
            "description": "Generated from XMind-style Markdown testcases. Review selector TODOs before execution.",
        },
        "selectors": selectors,
        "test_data": {},
        "flows": flows,
        "todos": todos,
        "unsupported_steps": unsupported,
    }


def find_input_file(project_root: Path, delivery_name: str | None) -> Path:
    if delivery_name:
        candidate = project_root / delivery_name / "testcase" / "xmind-testcases.md"
        if not candidate.is_file():
            raise SystemExit(f"Input file not found for delivery-name {delivery_name}: {candidate}")
        return candidate

    matches = sorted(project_root.glob("*/testcase/xmind-testcases.md"))
    if not matches:
        raise SystemExit("Input file not found: no */testcase/xmind-testcases.md under project root")
    if len(matches) > 1:
        choices = "\n".join(f"- {path.parent.parent.name}" for path in matches)
        raise SystemExit(
            "Found multiple xmind-testcases.md files. Please specify delivery-name.\n"
            f"Candidates:\n{choices}"
        )
    return matches[0]


def validate_dsl(dsl: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    expected_top = ["schema_version", "meta", "selectors", "test_data", "flows", "todos", "unsupported_steps"]
    for key in expected_top:
        if key not in dsl:
            errors.append(f"缺少顶层字段: {key}")

    if dsl.get("schema_version") != "1.0":
        errors.append('schema_version 必须为 "1.0"')

    if not isinstance(dsl.get("meta"), dict):
        errors.append("meta 必须是对象")
    else:
        for key in ["system", "version", "module", "source", "generated_at", "description"]:
            if key not in dsl["meta"]:
                errors.append(f"meta 缺少字段: {key}")

    if not isinstance(dsl.get("selectors"), dict):
        errors.append("selectors 必须是对象")
    else:
        for key, value in dsl["selectors"].items():
            if not re.match(r"^[a-z][a-z0-9_]*$", key):
                errors.append(f"selector key 不符合英文 snake_case: {key}")
            if not isinstance(value, dict):
                errors.append(f"selector {key} 必须是对象")
                continue
            for selector_field in ["selector", "description", "source", "status", "candidates"]:
                if selector_field not in value:
                    errors.append(f"selector {key} 缺少字段: {selector_field}")
            if value.get("status") not in {"todo", "confirmed"}:
                errors.append(f"selector {key} status 只能是 todo 或 confirmed")
            if value.get("status") == "confirmed" and not explicit_selector_from_text(str(value.get("selector", ""))):
                errors.append(f"selector {key} confirmed 必须来自显式 selector")
            candidates = value.get("candidates")
            if not isinstance(candidates, list):
                errors.append(f"selector {key} candidates 必须是数组")
            else:
                for candidate in candidates:
                    if not isinstance(candidate, str):
                        errors.append(f"selector {key} candidates 只能包含字符串")
                        continue
                    if not candidate.startswith(("role=", "label=", "placeholder=", "text=", "[data-testid=", "#", ".")):
                        errors.append(f"selector {key} candidate 前缀不合法: {candidate}")

    if not isinstance(dsl.get("test_data"), dict):
        errors.append("test_data 必须是对象")

    if not isinstance(dsl.get("flows"), list):
        errors.append("flows 必须是数组")
    elif not dsl["flows"]:
        errors.append("flows 不能为空，至少需要一个 tc")
    else:
        for flow in dsl["flows"]:
            if not isinstance(flow, dict):
                errors.append("flow 必须是对象")
                continue
            for flow_field in ["id", "name", "module", "priority", "source_case", "tags", "preconditions", "steps"]:
                if flow_field not in flow:
                    errors.append(f"flow 缺少字段: {flow_field}")
            if flow.get("priority") not in {"P0", "P1", "P2", "P3"}:
                errors.append(f"flow {flow.get('id', '')} priority 只能是 P0/P1/P2/P3")
            source_case = flow.get("source_case")
            if not isinstance(source_case, dict):
                errors.append(f"flow {flow.get('id', '')} source_case 必须是对象")
            else:
                for source_field in ["tc", "tp"]:
                    if source_field not in source_case:
                        errors.append(f"flow {flow.get('id', '')} source_case 缺少字段: {source_field}")
            if not isinstance(flow.get("steps"), list):
                errors.append(f"flow {flow.get('id', '')} steps 必须是数组")
                continue
            for step in flow["steps"]:
                if not isinstance(step, dict):
                    errors.append(f"flow {flow.get('id', '')} step 必须是对象")
                    continue
                for step_field in ["id", "source_ts", "action", "target", "timeout_ms", "optional", "comment"]:
                    if step_field not in step:
                        errors.append(f"step {step.get('id', '')} 缺少字段: {step_field}")
                if step.get("action") not in ALLOWED_ACTIONS:
                    errors.append(f"step {step.get('id', '')} action 不支持: {step.get('action')}")
                if step.get("action") in {"assert_visible", "assert_text", "assert_state"}:
                    if "source_expected" not in step:
                        errors.append(f"assert step {step.get('id', '')} 缺少字段: source_expected")

    for list_key in ["todos", "unsupported_steps"]:
        if not isinstance(dsl.get(list_key), list):
            errors.append(f"{list_key} 必须是数组")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path)
    parser.add_argument("--delivery-name")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    project_root = Path.cwd().resolve()
    if not (project_root / ".codex").is_dir():
        raise SystemExit("Project root must be the directory containing .codex")
    source = (args.input.resolve() if args.input else find_input_file(project_root, args.delivery_name).resolve())
    delivery_root = source.parent.parent
    output = (args.output.resolve() if args.output else delivery_root / "ui-dsl" / "ui-test.dsl.yaml")
    if not source.is_file():
        raise SystemExit(f"Input file not found: {source}")

    parsed = parse_markdown(source.read_text(encoding="utf-8"))
    dsl = build_dsl(parsed, source, project_root)
    validation_errors = validate_dsl(dsl)
    if validation_errors:
        dsl["unsupported_steps"].append({
            "source_case": "",
            "source_step": "",
            "reason": "生成的 YAML 不符合 references/dsl-schema.md，已停止生成最终文件",
            "suggestion": "修复以下结构问题后重试: " + "; ".join(validation_errors),
        })
        raise SystemExit("DSL schema validation failed; output was not written:\n" + "\n".join(validation_errors))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(dump_yaml(dsl)) + "\n", encoding="utf-8")
    print(f"Wrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
