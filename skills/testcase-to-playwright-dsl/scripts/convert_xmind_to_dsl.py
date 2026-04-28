#!/usr/bin/env python
"""Convert XMind-style Markdown testcases to Playwright UI DSL YAML.

The parser is conservative by design: when testcase Markdown lacks real
selectors, it emits data-testid placeholders plus TODO entries.
"""

from __future__ import annotations

import argparse
import datetime as dt
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
    ("打开", "goto"),
    ("进入", "goto"),
    ("访问", "goto"),
    ("跳转", "goto"),
    ("点击", "click"),
    ("选择", "click"),
    ("勾选", "click"),
    ("输入", "fill"),
    ("填写", "fill"),
    ("上传", "upload"),
    ("等待", "wait_for"),
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

ACTION_INTENT_WORDS = ["点击", "提交", "确认", "输入", "填写", "勾选", "选中", "选择", "上传", "搜索", "查询"]
FIELD_CONNECTORS = ["和", "并", "同时", "以及", "、"]

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
    replacements = {
        "登录": "login",
        "权限": "permission",
        "课程": "course",
        "导入": "import",
        "删除": "delete",
        "确认": "confirm",
        "搜索": "search",
        "查询": "query",
        "保存": "save",
        "提交": "submit",
        "取消": "cancel",
        "列表": "list",
        "表格": "table",
        "弹窗": "modal",
        "按钮": "button",
        "输入框": "input",
        "名称": "name",
        "账号": "account",
        "密码": "password",
        "首页": "home",
        "页面": "page",
    }
    result = text
    for zh, en in replacements.items():
        result = result.replace(zh, f" {en} ")
    result = re.sub(r"https?://\S+", " url ", result)
    result = re.sub(r"[^A-Za-z0-9]+", "_", result).strip("_").lower()
    result = re.sub(r"_+", "_", result)
    if not result:
        result = fallback
    if re.match(r"^\d", result):
        result = f"{fallback}_{result}"
    return result[:64].strip("_") or fallback


def action_for(text: str) -> str | None:
    for keyword, action in ACTION_KEYWORDS:
        if keyword in text:
            return action
    return None


def selector_key_for(text: str, action: str, index: int) -> str:
    source = text
    for keyword, _action in ACTION_KEYWORDS:
        source = source.replace(keyword, " ")
    suffix = ""
    for hint, mapped in UI_HINTS:
        if hint in text:
            suffix = mapped
            source = source.replace(hint, " ")
            break
    base = slugify(source, f"element_{index:03d}")
    if action == "goto":
        suffix = suffix or "page"
    elif action in {"click", "assert_visible"}:
        suffix = suffix or "element"
    elif action == "fill":
        suffix = suffix or "input"
    elif action == "select":
        suffix = suffix or "select"
    elif action == "upload":
        suffix = suffix or "upload"
    key = f"{base}_{suffix}" if suffix and not base.endswith(f"_{suffix}") else base
    return re.sub(r"_+", "_", key).strip("_")


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
    return (bool(quoted), quoted or "")


def is_page_state(text: str) -> bool:
    compact = _compact_text(text)
    if re.match(r"^(?:打开|启动|进入)应用$", compact):
        return True
    if re.match(r"^(?:进入|展示).*(?:页面)$", compact):
        return True
    if any(keyword in compact for keyword in ["状态已", "登录成功", "查看数据", "检查结果", "显示结果", "看到列表", "展示页面"]):
        return True
    return False


def is_compound_action(text: str) -> bool:
    compact = _compact_text(text)
    action_count = sum(len(re.findall(re.escape(word), compact)) for word in ACTION_INTENT_WORDS)
    has_connector = any(connector in compact for connector in FIELD_CONNECTORS)
    if action_count >= 2 and has_connector:
        return True
    if action_count != 1:
        return False
    if not has_connector:
        return False
    return bool(re.match(r"^(?:输入|填写|选择).+(?:和|并|同时|以及|、).+", compact))


def infer_selector(ts_text: str) -> tuple[str, str]:
    """
    Infer a Playwright semantic selector from testcase text.

    Returns:
    (selector, status)
    """
    if is_captcha(ts_text) or is_compound_action(ts_text):
        return ("", "todo")

    matched, name = is_text_assertion(ts_text)
    if matched:
        return (f"text={name}", "confirmed")

    if is_page_state(ts_text):
        return ("", "todo")

    matched, name = is_button_action(ts_text)
    if matched:
        return (f'role=button[name="{name}"]', "confirmed")

    matched, name = is_input_action(ts_text)
    if matched:
        return (f"label={name}", "confirmed")

    matched, name = is_checkbox_action(ts_text)
    if matched:
        return (f'role=checkbox[name="{name}"]', "confirmed")

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
        if reason_kind == "expected" or is_page_state(source_text):
            return "预期结果是页面或业务状态描述，缺少明确 UI 文案，需要人工补充 selector 或断言方式"
        return "无法从源步骤推断稳定 Playwright locator，需要人工补充"

    def register_selector(
        selector_key: str,
        source_text: str,
        source_case: str,
        source_step: str,
        reason_kind: str = "selector",
    ) -> None:
        inferred_selector, status = infer_selector(source_text)
        if status == "confirmed":
            selector_value = inferred_selector
        else:
            selector_value = f'[data-testid="{selector_key}"]'

        existing = selectors.get(selector_key)
        if existing:
            if existing.get("status") == "todo" and status == "confirmed":
                existing["selector"] = selector_value
                existing["status"] = "confirmed"
                todos[:] = [todo for todo in todos if todo.get("key") != selector_key]
            return

        selectors[selector_key] = {
            "selector": selector_value,
            "description": source_text,
            "source": source_text,
            "status": status,
        }
        if status == "todo":
            todos.append({
                "type": "selector",
                "key": selector_key,
                "source_case": source_case,
                "source_step": source_step,
                "reason": todo_reason_for(source_text, reason_kind),
            })

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

    def add_todo_expected_step(
        steps: list[dict[str, Any]],
        source_ts: str,
        expected: str,
        source_case: str,
    ) -> None:
        selector_key = selector_key_for(expected, "assert_visible", len(steps) + 1)
        register_selector(selector_key, expected, source_case, source_ts, reason_kind="expected")
        steps.append({
            "id": f"step_{len(steps) + 1:03d}",
            "source_ts": source_ts,
            "source_expected": expected,
            "action": "assert_visible",
            "target": selector_key,
            "value": "",
            "url": "",
            "expected": expected,
            "timeout_ms": 5000,
            "optional": True,
            "comment": "expected is not confirmed; selector requires review",
        })

    for flow_index, case in enumerate(parsed["cases"], start=1):
        steps: list[dict[str, Any]] = []
        flow_id = f"flow_{flow_index:03d}"

        for step_index, source_step in enumerate(case["steps"], start=1):
            source_ts = source_step["ts"] if isinstance(source_step, dict) else str(source_step)
            if is_compound_action(source_ts):
                add_unsupported(
                    case["tc"],
                    source_ts,
                    "组合动作需要拆分为多个 UI 步骤",
                    "将该步骤拆分为单一的 click/fill/check 等原子 UI 步骤",
                )
                add_wait_placeholder(steps, source_ts, "unsupported manual step, see unsupported_steps")
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
                register_selector(selector_key, source_ts, case["tc"], source_ts)

            step: dict[str, Any] = {
                "id": f"step_{len(steps) + 1:03d}",
                "source_ts": source_ts,
                "action": action,
                "target": "" if action == "goto" else selector_key,
                "value": "",
                "url": "",
                "expected": "",
                "source_expected": "",
                "timeout_ms": 5000,
                "optional": False,
                "comment": "",
            }
            if action == "goto":
                step["url"] = url_match.group(0) if url_match else ""
            steps.append(step)

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
                    add_todo_expected_step(steps, source_ts, expected, case["tc"])
                    continue

                action = "assert_text"
                selector_key = selector_key_for(expected, action, len(steps) + 1)
                register_selector(selector_key, expected, case["tc"], source_ts, reason_kind="expected")
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
                add_todo_expected_step(steps, expected, expected, case["tc"])
                continue

            action = "assert_text"
            selector_key = selector_key_for(expected, action, len(steps) + 1)
            register_selector(selector_key, expected, case["tc"], expected, reason_kind="expected")
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
            for selector_field in ["selector", "description", "source", "status"]:
                if selector_field not in value:
                    errors.append(f"selector {key} 缺少字段: {selector_field}")
            if value.get("status") not in {"todo", "confirmed"}:
                errors.append(f"selector {key} status 只能是 todo 或 confirmed")

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
