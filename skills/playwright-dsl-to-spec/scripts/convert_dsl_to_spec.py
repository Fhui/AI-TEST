#!/usr/bin/env python
"""Convert Playwright UI DSL YAML to Playwright spec.ts.

The DSL source of truth is:
.codex/skills/testcase-to-playwright-dsl/references/dsl-schema.md

This script intentionally avoids third-party YAML dependencies to stay aligned
with the existing Python-only skill scripts in this project.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from pathlib import Path
from typing import Any


ALLOWED_TOP = {"schema_version", "meta", "selectors", "test_data", "flows", "todos", "unsupported_steps"}
ALLOWED_META = {"system", "version", "module", "source", "generated_at", "description"}
ALLOWED_SELECTOR = {"selector", "description", "source", "status"}
ALLOWED_TEST_DATA = {"value", "description"}
ALLOWED_FLOW = {"id", "name", "module", "priority", "source_case", "tags", "preconditions", "steps"}
ALLOWED_SOURCE_CASE = {"tc", "tp"}
ALLOWED_STEP = {
    "id",
    "source_ts",
    "action",
    "target",
    "value",
    "url",
    "source_expected",
    "expected",
    "timeout_ms",
    "optional",
    "comment",
}
ALLOWED_TODO = {"type", "key", "source_case", "source_step", "reason"}
ALLOWED_UNSUPPORTED = {"source_case", "source_step", "reason", "suggestion"}
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
ALLOWED_STATUS = {"todo", "confirmed"}
ALLOWED_PRIORITY = {"P0", "P1", "P2", "P3"}


def die(message: str) -> None:
    raise SystemExit(f"[ERROR] {message}")


def split_key_value(text: str) -> tuple[str, str]:
    in_single = False
    in_double = False
    escaped = False
    for index, char in enumerate(text):
        if escaped:
            escaped = False
            continue
        if char == "\\" and in_double:
            escaped = True
            continue
        if char == "'" and not in_double:
            in_single = not in_single
            continue
        if char == '"' and not in_single:
            in_double = not in_double
            continue
        if char == ":" and not in_single and not in_double:
            return text[:index].strip(), text[index + 1 :].strip()
    die(f"Invalid YAML line, expected key: value: {text}")


def parse_scalar(value: str) -> Any:
    value = value.strip()
    if value == "{}":
        return {}
    if value == "[]":
        return []
    if value == "":
        return None
    if value == "true":
        return True
    if value == "false":
        return False
    if value in {"null", "~"}:
        return None
    if re.fullmatch(r"-?\d+", value):
        return int(value)
    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        try:
            return ast.literal_eval(value)
        except (SyntaxError, ValueError):
            return value[1:-1]
    return value


def preprocess_yaml(text: str) -> list[tuple[int, str]]:
    rows: list[tuple[int, str]] = []
    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        expanded = raw.replace("\t", "    ")
        indent = len(expanded) - len(expanded.lstrip(" "))
        rows.append((indent, expanded.strip()))
    return rows


def parse_yaml_subset(text: str) -> Any:
    rows = preprocess_yaml(text)
    if not rows:
        return {}

    def parse_block(index: int, indent: int) -> tuple[Any, int]:
        if index >= len(rows):
            return {}, index
        current_indent, current_text = rows[index]
        if current_indent < indent:
            return {}, index
        if current_indent != indent:
            die(f"Unexpected indentation at line: {current_text}")
        if current_text.startswith("- "):
            return parse_list(index, indent)
        return parse_map(index, indent)

    def parse_map(index: int, indent: int) -> tuple[dict[str, Any], int]:
        result: dict[str, Any] = {}
        while index < len(rows):
            row_indent, text = rows[index]
            if row_indent < indent:
                break
            if row_indent != indent:
                die(f"Unexpected indentation at line: {text}")
            if text.startswith("- "):
                break
            key, raw_value = split_key_value(text)
            if not key:
                die(f"Empty YAML key at line: {text}")
            index += 1
            if raw_value == "":
                if index < len(rows) and rows[index][0] > row_indent:
                    value, index = parse_block(index, rows[index][0])
                else:
                    value = {}
            else:
                value = parse_scalar(raw_value)
            result[key] = value
        return result, index

    def parse_list(index: int, indent: int) -> tuple[list[Any], int]:
        result: list[Any] = []
        while index < len(rows):
            row_indent, text = rows[index]
            if row_indent < indent:
                break
            if row_indent != indent:
                die(f"Unexpected indentation at line: {text}")
            if not text.startswith("- "):
                break
            body = text[2:].strip()
            index += 1
            if body == "":
                if index < len(rows) and rows[index][0] > row_indent:
                    item, index = parse_block(index, rows[index][0])
                else:
                    item = None
                result.append(item)
                continue
            if ":" in body and not body.startswith(("'", '"')):
                key, raw_value = split_key_value(body)
                item: dict[str, Any] = {}
                item[key] = parse_scalar(raw_value) if raw_value else {}
                if raw_value == "" and index < len(rows) and rows[index][0] > row_indent:
                    item[key], index = parse_block(index, rows[index][0])
                while index < len(rows) and rows[index][0] > row_indent:
                    child_indent, child_text = rows[index]
                    child_key, child_value = split_key_value(child_text)
                    index += 1
                    if child_value == "":
                        if index < len(rows) and rows[index][0] > child_indent:
                            item[child_key], index = parse_block(index, rows[index][0])
                        else:
                            item[child_key] = {}
                    else:
                        item[child_key] = parse_scalar(child_value)
                result.append(item)
            else:
                result.append(parse_scalar(body))
        return result, index

    parsed, final_index = parse_block(0, rows[0][0])
    if final_index != len(rows):
        die("YAML parsing stopped before end of file")
    return parsed


def assert_mapping(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        die(f"{path} must be a mapping")
    return value


def assert_list(value: Any, path: str) -> list[Any]:
    if not isinstance(value, list):
        die(f"{path} must be a list")
    return value


def assert_allowed_keys(value: dict[str, Any], allowed: set[str], path: str) -> None:
    extra = set(value) - allowed
    if extra:
        die(f"{path} contains unsupported field(s): {', '.join(sorted(extra))}")


def validate_schema_reference(project_root: Path) -> None:
    schema_path = project_root / ".codex" / "skills" / "testcase-to-playwright-dsl" / "references" / "dsl-schema.md"
    if not schema_path.is_file():
        die(f"DSL schema reference not found: {schema_path}")
    schema_text = schema_path.read_text(encoding="utf-8")
    for action in sorted(ALLOWED_ACTIONS):
        if action not in schema_text:
            die(f"DSL schema reference does not mention action {action!r}")


def validate_dsl(dsl: Any) -> dict[str, Any]:
    root = assert_mapping(dsl, "root")
    assert_allowed_keys(root, ALLOWED_TOP, "root")
    if root.get("schema_version") != "1.0":
        die('schema_version must be "1.0"')

    meta = assert_mapping(root.get("meta", {}), "meta")
    assert_allowed_keys(meta, ALLOWED_META, "meta")

    selectors = assert_mapping(root.get("selectors", {}), "selectors")
    for key, value in selectors.items():
        selector = assert_mapping(value, f"selectors.{key}")
        assert_allowed_keys(selector, ALLOWED_SELECTOR, f"selectors.{key}")
        if selector.get("status") not in ALLOWED_STATUS:
            die(f"selectors.{key}.status must be todo or confirmed")

    test_data = assert_mapping(root.get("test_data", {}), "test_data")
    for key, value in test_data.items():
        data = assert_mapping(value, f"test_data.{key}")
        assert_allowed_keys(data, ALLOWED_TEST_DATA, f"test_data.{key}")

    flows = assert_list(root.get("flows", []), "flows")
    for flow_index, flow_value in enumerate(flows):
        flow_path = f"flows[{flow_index}]"
        flow = assert_mapping(flow_value, flow_path)
        assert_allowed_keys(flow, ALLOWED_FLOW, flow_path)
        priority = str(flow.get("priority", ""))
        if priority and priority not in ALLOWED_PRIORITY:
            die(f"{flow_path}.priority must be P0, P1, P2, or P3")
        source_case = assert_mapping(flow.get("source_case", {}), f"{flow_path}.source_case")
        assert_allowed_keys(source_case, ALLOWED_SOURCE_CASE, f"{flow_path}.source_case")
        assert_list(flow.get("tags", []), f"{flow_path}.tags")
        assert_list(flow.get("preconditions", []), f"{flow_path}.preconditions")
        steps = assert_list(flow.get("steps", []), f"{flow_path}.steps")
        for step_index, step_value in enumerate(steps):
            step_path = f"{flow_path}.steps[{step_index}]"
            step = assert_mapping(step_value, step_path)
            assert_allowed_keys(step, ALLOWED_STEP, step_path)
            action = str(step.get("action", ""))
            if action not in ALLOWED_ACTIONS:
                die(f"{step_path}.action is unsupported: {action!r}")
            target = str(step.get("target", ""))
            if target and target not in selectors:
                die(f"{step_path}.target references unknown selector: {target}")

    todos = assert_list(root.get("todos", []), "todos")
    for index, value in enumerate(todos):
        todo = assert_mapping(value, f"todos[{index}]")
        assert_allowed_keys(todo, ALLOWED_TODO, f"todos[{index}]")

    unsupported = assert_list(root.get("unsupported_steps", []), "unsupported_steps")
    for index, value in enumerate(unsupported):
        item = assert_mapping(value, f"unsupported_steps[{index}]")
        assert_allowed_keys(item, ALLOWED_UNSUPPORTED, f"unsupported_steps[{index}]")

    return root


def find_project_root(start: Path) -> Path:
    current = start.resolve()
    for candidate in [current, *current.parents]:
        if (candidate / ".codex").is_dir():
            return candidate
    die("Run from inside the project containing .codex")


def find_single_input(project_root: Path) -> Path:
    matches = sorted(project_root.glob("*/ui-dsl/ui-test.dsl.yaml"))
    if not matches:
        die(f"No */ui-dsl/ui-test.dsl.yaml found under {project_root}")
    if len(matches) > 1:
        rels = "\n".join(f"- ./{path.relative_to(project_root)}" for path in matches)
        die(f"Multiple DSL files found; pass --input explicitly:\n{rels}")
    return matches[0]


def js_string(value: Any) -> str:
    return json.dumps("" if value is None else str(value), ensure_ascii=False)


def ts_comment(text: str) -> str:
    return "\n".join(f"// {line}" for line in str(text).splitlines())


def safe_file_name(value: Any, fallback: str) -> str:
    name = re.sub(r"[^a-z0-9_-]+", "-", str(value or "").strip().lower()).strip("-")
    return name or fallback


def int_value(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def bool_value(value: Any) -> bool:
    return value is True


def step_label(step: dict[str, Any]) -> str:
    parts = [str(step.get(key, "") or "") for key in ["id", "source_ts", "comment"]]
    parts = [part for part in parts if part]
    return " | ".join(parts) if parts else "unnamed step"


def todo_line(step: dict[str, Any], message: str) -> str:
    return f"  {ts_comment(f'TODO {step_label(step)}: {message}')}"


def test_data_expression(value: Any, test_data: dict[str, Any]) -> str:
    raw = "" if value is None else str(value)
    match = re.fullmatch(r"\$\{([A-Za-z0-9_-]+)\}", raw)
    if not match:
        return js_string(raw)
    key = match.group(1)
    if key not in test_data:
        die(f"value references unknown test_data key: {key}")
    return f"testData[{js_string(key)}]"


def operation_lines(step: dict[str, Any], selectors: dict[str, Any], test_data: dict[str, Any]) -> list[str]:
    action = str(step.get("action", ""))
    target = str(step.get("target", "") or "")
    timeout = int_value(step.get("timeout_ms"), 5000)
    expected = str(step.get("expected", "") or "")

    if action == "goto":
        url = str(step.get("url", "") or "")
        if not url:
            return [todo_line(step, "补充 url 后再执行 page.goto")]
        return [f"  await page.goto({js_string(url)});"]

    if action == "wait_for" and not target:
        return [f"  await page.waitForTimeout({timeout});"]

    if not target:
        return [todo_line(step, "补充 target 后再生成 Playwright 操作")]

    selector = selectors[target]
    if selector.get("status") == "todo":
        return [todo_line(step, f"selector {target!r} 仍为 todo，确认真实 selector 后再执行")]

    locator = f"page.locator({js_string(selector.get('selector', ''))})"
    if action == "click":
        return [f"  await {locator}.click({{ timeout: {timeout} }});"]
    if action == "fill":
        if not str(step.get("value", "") or ""):
            return [todo_line(step, "补充 value 后再执行 fill")]
        return [f"  await {locator}.fill({test_data_expression(step.get('value'), test_data)}, {{ timeout: {timeout} }});"]
    if action == "select":
        if not str(step.get("value", "") or ""):
            return [todo_line(step, "补充 value 后再执行 selectOption")]
        return [f"  await {locator}.selectOption({test_data_expression(step.get('value'), test_data)}, {{ timeout: {timeout} }});"]
    if action == "upload":
        if not str(step.get("value", "") or ""):
            return [todo_line(step, "补充 value 文件路径后再执行 setInputFiles")]
        return [f"  await {locator}.setInputFiles({test_data_expression(step.get('value'), test_data)}, {{ timeout: {timeout} }});"]
    if action == "wait_for":
        return [f"  await {locator}.waitFor({{ state: 'visible', timeout: {timeout} }});"]
    if action == "assert_visible":
        return [f"  await expect({locator}).toBeVisible({{ timeout: {timeout} }});"]
    if action == "assert_text":
        if not expected:
            return [todo_line(step, "补充 expected 后再执行文本断言")]
        return [f"  await expect({locator}).toContainText({js_string(expected)}, {{ timeout: {timeout} }});"]
    if action == "assert_state":
        lines = [f"  await expect({locator}).toBeVisible({{ timeout: {timeout} }});"]
        if expected:
            lines.append(f"  {ts_comment(f'TODO {step_label(step)}: 根据 expected 补充具体状态断言：{expected}')}")
        return lines
    die(f"Unsupported action after validation: {action}")


def wrap_optional(lines: list[str], step: dict[str, Any]) -> list[str]:
    if not bool_value(step.get("optional")):
        return lines
    wrapped = ["  try {"]
    wrapped.extend(f"  {line}" if line.startswith("  ") else f"    {line}" for line in lines)
    wrapped.append("  } catch (error) {")
    wrapped.append(f"    console.warn({js_string('Optional step failed: ' + step_label(step))}, error);")
    wrapped.append("  }")
    return wrapped


def render_spec(flow: dict[str, Any], selectors: dict[str, Any], test_data: dict[str, Any]) -> str:
    flow_name = str(flow.get("name") or flow.get("id") or "flow")
    test_data_literal = {key: str(value.get("value", "") or "") for key, value in test_data.items()}
    lines = [
        "import { test, expect } from '@playwright/test';",
        "",
        f"const testData: Record<string, string> = {json.dumps(test_data_literal, ensure_ascii=False)};",
        "",
        f"test.describe({js_string(flow.get('module', ''))}, () => {{",
        f"  test({js_string(flow_name)}, async ({{ page }}) => {{",
    ]
    source_case = flow.get("source_case", {})
    if source_case.get("tc"):
        lines.append(f"    {ts_comment('source_case.tc: ' + str(source_case['tc']))}")
    if source_case.get("tp"):
        lines.append(f"    {ts_comment('source_case.tp: ' + str(source_case['tp']))}")
    lines.append("")

    for step in flow.get("steps", []):
        for line in wrap_optional(operation_lines(step, selectors, test_data), step):
            lines.append(f"  {line}")
        lines.append("")

    lines.extend(["  });", "});", ""])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, help="Path to ./<delivery-name>/ui-dsl/ui-test.dsl.yaml")
    parser.add_argument("--output-dir", type=Path, help="Path to ./<delivery-name>/playwright/tests")
    args = parser.parse_args()

    project_root = find_project_root(Path.cwd())
    validate_schema_reference(project_root)

    input_path = (args.input.resolve() if args.input else find_single_input(project_root).resolve())
    if not input_path.is_file():
        die(f"Input file not found: {input_path}")

    delivery_root = input_path.parent.parent
    if delivery_root.parent != project_root:
        die("Input delivery directory must be a direct child of the project root")
    expected_input = delivery_root / "ui-dsl" / "ui-test.dsl.yaml"
    if input_path != expected_input:
        die("Input must match ./<delivery-name>/ui-dsl/ui-test.dsl.yaml")

    output_dir = (args.output_dir.resolve() if args.output_dir else delivery_root / "playwright" / "tests")
    if output_dir != delivery_root / "playwright" / "tests":
        die("Output dir must match ./<delivery-name>/playwright/tests")

    dsl = validate_dsl(parse_yaml_subset(input_path.read_text(encoding="utf-8")))
    output_dir.mkdir(parents=True, exist_ok=True)

    for index, flow in enumerate(dsl.get("flows", []), start=1):
        file_name = f"{safe_file_name(flow.get('id'), f'flow-{index:03d}')}.spec.ts"
        output_path = output_dir / file_name
        output_path.write_text(render_spec(flow, dsl["selectors"], dsl["test_data"]), encoding="utf-8")
        print(f"./{output_path.relative_to(project_root)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
