#!/usr/bin/env python3
"""Generate Markdown reports from existing Playwright results and UI DSL."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


STATUS_PASS = {"passed", "expected"}
STATUS_FAIL = {"failed", "timedout", "interrupted", "unexpected"}
STATUS_SKIP = {"skipped", "pending", "disabled"}


@dataclass
class SelectorInfo:
    key: str
    selector: str = ""
    status: str = ""


@dataclass
class StepInfo:
    step_id: str = ""
    source_ts: str = ""
    action: str = ""
    selector_key: str = ""


@dataclass
class FlowInfo:
    flow_id: str
    name: str = ""
    source_tc: str = ""
    priority: str = ""
    steps: List[StepInfo] = field(default_factory=list)


@dataclass
class TestResult:
    flow_id: str
    title: str = ""
    status: str = "unknown"
    duration_ms: Optional[float] = None
    spec: str = ""
    error_message: str = ""
    stack: str = ""
    line: Optional[int] = None
    attachments: List[str] = field(default_factory=list)


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="replace")


def load_yaml(path: Path) -> Dict[str, Any]:
    try:
        import yaml  # type: ignore
    except Exception as exc:  # pragma: no cover - environment dependent
        raise SystemExit(
            "PyYAML is required to parse ui-test DSL YAML. Install pyyaml or run in the bundled Codex environment."
        ) from exc
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    return data if isinstance(data, dict) else {}


def as_rel(path: Path, base: Path) -> str:
    try:
        return str(path.resolve().relative_to(base.resolve()))
    except ValueError:
        return str(path)


def first_string(*values: Any) -> str:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
        if value is not None and not isinstance(value, (dict, list, tuple)):
            text = str(value).strip()
            if text:
                return text
    return ""


def normalize_status(status: str) -> str:
    lower = (status or "").lower()
    if lower in STATUS_PASS:
        return "passed"
    if lower in STATUS_FAIL:
        return "failed"
    if lower in STATUS_SKIP:
        return "skipped"
    return lower or "unknown"


def display_status(status: str) -> str:
    return {
        "passed": "通过",
        "failed": "失败",
        "skipped": "跳过",
        "unknown": "未知",
    }.get(normalize_status(status), status or "未知")


def parse_selectors(dsl: Dict[str, Any]) -> Dict[str, SelectorInfo]:
    raw = dsl.get("selectors") or {}
    selectors: Dict[str, SelectorInfo] = {}
    if isinstance(raw, dict):
        for key, value in raw.items():
            if isinstance(value, dict):
                selectors[str(key)] = SelectorInfo(
                    key=str(key),
                    selector=first_string(value.get("selector"), value.get("value"), value.get("locator")),
                    status=first_string(value.get("status")),
                )
            else:
                selectors[str(key)] = SelectorInfo(key=str(key), selector=first_string(value))
    elif isinstance(raw, list):
        for item in raw:
            if isinstance(item, dict):
                key = first_string(item.get("key"), item.get("id"), item.get("name"))
                if key:
                    selectors[key] = SelectorInfo(
                        key=key,
                        selector=first_string(item.get("selector"), item.get("value"), item.get("locator")),
                        status=first_string(item.get("status")),
                    )
    return selectors


def parse_step(item: Dict[str, Any], index: int) -> StepInfo:
    target = item.get("target")
    selector_key = first_string(
        item.get("selector_key"),
        item.get("selector"),
        item.get("selectorKey"),
        target.get("selector_key") if isinstance(target, dict) else "",
        target.get("selector") if isinstance(target, dict) else "",
        target if isinstance(target, str) else "",
    )
    return StepInfo(
        step_id=first_string(item.get("step_id"), item.get("id"), item.get("stepId"), f"step_{index + 1:03d}"),
        source_ts=first_string(item.get("source_ts"), item.get("sourceTs"), item.get("source"), item.get("ts")),
        action=first_string(item.get("action"), item.get("type"), item.get("name")),
        selector_key=selector_key,
    )


def parse_flows(dsl: Dict[str, Any]) -> Dict[str, FlowInfo]:
    raw = dsl.get("flows") or dsl.get("tests") or dsl.get("cases") or []
    if isinstance(raw, dict):
        items = []
        for key, value in raw.items():
            if isinstance(value, dict):
                value = {**value, "flow_id": value.get("flow_id") or value.get("id") or key}
            items.append(value)
    elif isinstance(raw, list):
        items = raw
    else:
        items = []

    flows: Dict[str, FlowInfo] = {}
    for idx, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        flow_id = first_string(item.get("flow_id"), item.get("id"), item.get("flowId"), f"flow_{idx + 1:03d}")
        source_case = item.get("source_case") if isinstance(item.get("source_case"), dict) else {}
        raw_steps = item.get("steps") or item.get("flow") or []
        steps = [parse_step(step, step_idx) for step_idx, step in enumerate(raw_steps) if isinstance(step, dict)]
        flows[flow_id] = FlowInfo(
            flow_id=flow_id,
            name=first_string(item.get("name"), item.get("title"), item.get("case_name"), source_case.get("name")),
            source_tc=first_string(source_case.get("tc"), item.get("tc"), item.get("source_tc")),
            priority=first_string(item.get("priority"), source_case.get("priority")),
            steps=steps,
        )
    return flows


def find_dsl(delivery: Path) -> Path:
    enriched = delivery / "ui-dsl" / "ui-test.enriched.dsl.yaml"
    plain = delivery / "ui-dsl" / "ui-test.dsl.yaml"
    if enriched.exists():
        return enriched
    if plain.exists():
        return plain
    raise SystemExit(f"未在目录中找到 DSL 文件：{delivery / 'ui-dsl'}")


def collect_specs(delivery: Path) -> Dict[str, Path]:
    specs: Dict[str, Path] = {}
    tests_dir = delivery / "playwright" / "tests"
    for path in sorted(tests_dir.glob("*.spec.ts")):
        flow_id = infer_flow_id_from_text(path.stem, [])
        if flow_id:
            specs[flow_id] = path
    return specs


def infer_flow_id_from_text(text: str, known: Iterable[str]) -> str:
    for flow_id in known:
        if flow_id and flow_id in text:
            return flow_id
    match = re.search(r"(flow[_-]?\d+|[A-Za-z0-9]+_flow[_-]?\d+)", text, re.I)
    if match:
        return match.group(1).replace("-", "_")
    stem = Path(text).stem
    if stem.endswith(".spec"):
        stem = stem[:-5]
    return stem if stem else ""


def extract_error(result: Dict[str, Any]) -> Tuple[str, str]:
    errors = result.get("errors")
    error = result.get("error")
    if isinstance(errors, list) and errors:
        error = errors[0]
    if isinstance(error, dict):
        return first_string(error.get("message"), error.get("value")), first_string(error.get("stack"))
    return first_string(result.get("errorMessage"), error), first_string(result.get("stack"))


def result_from_json_test(
    test: Dict[str, Any],
    result: Dict[str, Any],
    spec_file: str,
    known_flows: Iterable[str],
) -> TestResult:
    title_parts = test.get("titlePath") if isinstance(test.get("titlePath"), list) else []
    title = first_string(test.get("title"), " / ".join(str(x) for x in title_parts if x))
    status = normalize_status(first_string(result.get("status"), test.get("outcome"), test.get("status")))
    message, stack = extract_error(result)
    attachments = []
    for attachment in result.get("attachments") or []:
        if isinstance(attachment, dict):
            attachments.append(first_string(attachment.get("path"), attachment.get("name")))
    location = test.get("location") if isinstance(test.get("location"), dict) else {}
    spec = first_string(spec_file, location.get("file"), test.get("file"))
    flow_id = infer_flow_id_from_text(" ".join([title, spec]), known_flows)
    line = location.get("line")
    if not isinstance(line, int):
        line = parse_line_from_stack(stack)
    return TestResult(
        flow_id=flow_id,
        title=title,
        status=status,
        duration_ms=result.get("duration") if isinstance(result.get("duration"), (int, float)) else None,
        spec=spec,
        error_message=message,
        stack=stack,
        line=line,
        attachments=[a for a in attachments if a],
    )


def walk_suites(suite: Dict[str, Any], known_flows: Iterable[str]) -> Iterable[TestResult]:
    for spec in suite.get("specs") or []:
        if not isinstance(spec, dict):
            continue
        spec_file = first_string(spec.get("file"), spec.get("ok"))
        for test in spec.get("tests") or []:
            if not isinstance(test, dict):
                continue
            results = test.get("results") if isinstance(test.get("results"), list) else [{}]
            for result in results:
                if isinstance(result, dict):
                    yield result_from_json_test(test, result, spec_file, known_flows)
    for child in suite.get("suites") or []:
        if isinstance(child, dict):
            yield from walk_suites(child, known_flows)


def parse_json_reports(playwright_dir: Path, known_flows: Iterable[str]) -> List[TestResult]:
    results: List[TestResult] = []
    path = playwright_dir / "results.json"
    if not path.is_file():
        return results
    try:
        data = json.loads(read_text(path))
    except Exception:
        return results
    suites = data.get("suites") if isinstance(data, dict) else None
    if isinstance(suites, list):
        for suite in suites:
            if isinstance(suite, dict):
                results.extend(walk_suites(suite, known_flows))
    elif isinstance(data, dict) and isinstance(data.get("tests"), list):
        for test in data.get("tests") or []:
            if isinstance(test, dict):
                for result in test.get("results") or [{}]:
                    if isinstance(result, dict):
                        results.append(result_from_json_test(test, result, first_string(test.get("file")), known_flows))
    for item in results:
        if not item.spec:
            item.spec = as_rel(path, playwright_dir.parent)
    seen = set()
    deduped = []
    for item in results:
        key = (item.flow_id, item.title, item.status, item.spec, item.error_message)
        if key not in seen:
            seen.add(key)
            deduped.append(item)
    results = deduped
    return results


def parse_line_from_stack(stack: str) -> Optional[int]:
    match = re.search(r":(\d+):\d+\)?(?:\n|$)", stack or "")
    return int(match.group(1)) if match else None


def collect_artifacts(playwright_dir: Path, delivery: Path) -> Dict[str, List[str]]:
    artifacts = {"screenshot": [], "trace": [], "video": []}
    test_results = playwright_dir / "test-results"
    roots = [test_results] if test_results.exists() else [playwright_dir]
    patterns = {
        "screenshot": ["*.png"],
        "trace": ["trace.zip", "*.trace.zip"],
        "video": ["*.webm"],
    }
    for kind, globs in patterns.items():
        for root in roots:
            for glob in globs:
                for path in sorted(root.rglob(glob)):
                    artifacts[kind].append(as_rel(path, delivery))
    return artifacts


def artifacts_for_flow(flow_id: str, title: str, all_artifacts: Dict[str, List[str]]) -> Dict[str, List[str]]:
    tokens = [flow_id.lower(), re.sub(r"\W+", "-", title.lower()).strip("-")]
    matched: Dict[str, List[str]] = {"screenshot": [], "trace": [], "video": []}
    for kind, paths in all_artifacts.items():
        for path in paths:
            lower = path.lower()
            if any(token and token in lower for token in tokens):
                matched[kind].append(path)
        if not matched[kind] and len(paths) == 1:
            matched[kind].append(paths[0])
    return matched


def inspect_spec_for_step(spec_path: Optional[Path], line: Optional[int]) -> Dict[str, str]:
    if not spec_path or not spec_path.exists():
        return {}
    lines = read_text(spec_path).splitlines()
    if line is None or line < 1 or line > len(lines):
        line = 1
    start = max(0, line - 16)
    end = min(len(lines), line + 8)
    window = "\n".join(lines[start:end])
    keys = {
        "step_id": r"(?:step_id|stepId|step)\s*[:=]\s*['\"]?([A-Za-z0-9_.:-]+)",
        "source_ts": r"(?:source_ts|sourceTs)\s*[:=]\s*['\"]?([^'\"\n,;]+)",
        "selector_key": r"(?:selector_key|selectorKey|selector)\s*[:=]\s*['\"]?([A-Za-z0-9_.:-]+)",
    }
    found: Dict[str, str] = {}
    for name, pattern in keys.items():
        matches = re.findall(pattern, window)
        if matches:
            found[name] = str(matches[-1]).strip()
    return found


def resolve_spec_path(result: TestResult, specs: Dict[str, Path], delivery: Path) -> Optional[Path]:
    if result.flow_id in specs:
        return specs[result.flow_id]
    if result.spec:
        candidate = Path(result.spec)
        if candidate.exists():
            return candidate
        for base in [delivery, delivery / "playwright"]:
            joined = base / result.spec
            if joined.exists():
                return joined
    return None


def match_step(
    result: TestResult,
    flow: Optional[FlowInfo],
    selectors: Dict[str, SelectorInfo],
    spec_path: Optional[Path],
) -> StepInfo:
    if not flow:
        return StepInfo()
    spec_hint = inspect_spec_for_step(spec_path, result.line)
    step_id = spec_hint.get("step_id", "")
    selector_key = spec_hint.get("selector_key", "")
    if step_id:
        for step in flow.steps:
            if step.step_id == step_id:
                return StepInfo(
                    step_id=step.step_id,
                    source_ts=spec_hint.get("source_ts") or step.source_ts,
                    action=step.action,
                    selector_key=selector_key or step.selector_key,
                )
    error_text = " ".join([result.error_message, result.stack])
    for step in flow.steps:
        selector = selectors.get(step.selector_key)
        if selector and selector.selector and selector.selector in error_text:
            return step
        if step.selector_key and step.selector_key in error_text:
            return step
    if selector_key:
        for step in flow.steps:
            if step.selector_key == selector_key:
                return step
    return flow.steps[0] if flow.steps else StepInfo()


def classify_failure(result: TestResult, selector: Optional[SelectorInfo]) -> str:
    if selector and selector.status.lower() == "todo":
        return "UNRESOLVED_SELECTOR"
    text = " ".join([result.error_message, result.stack]).lower()
    if re.search(r"strict mode violation|resolved to \d+ elements|multiple elements", text):
        return "MULTIPLE_ELEMENTS"
    if re.search(r"timeout|timed out|waiting for", text):
        return "TIMEOUT"
    if re.search(r"net::|navigation|page.goto|load state|closed|target page", text):
        return "NAVIGATION_ERROR"
    if re.search(r"expect\(|assert|expected|received|to have|to be", text):
        return "ASSERTION_FAILED"
    if re.search(r"locator|selector|no element|not found|waiting for .*locator", text):
        return "SELECTOR_NOT_FOUND"
    return "UNKNOWN"


def duration_text(ms: Optional[float]) -> str:
    if ms is None:
        return "-"
    if ms >= 1000:
        return f"{ms / 1000:.2f}s"
    return f"{ms:.0f}ms"


def md_escape(text: str) -> str:
    return (text or "-").replace("|", "\\|").replace("\n", "<br>")


def trim_stack(stack: str, limit: int = 18) -> str:
    lines = (stack or "").splitlines()
    return "\n".join(lines[:limit])


def ensure_results_for_flows(results: List[TestResult], flows: Dict[str, FlowInfo], specs: Dict[str, Path], delivery: Path) -> List[TestResult]:
    by_flow = {r.flow_id for r in results if r.flow_id}
    for flow_id, flow in flows.items():
        if flow_id not in by_flow:
            spec = specs.get(flow_id)
            results.append(
                TestResult(
                    flow_id=flow_id,
                    title=flow.name or flow_id,
                    status="unknown",
                    spec=as_rel(spec, delivery) if spec else "",
                )
            )
    return results


def write_reports(delivery: Path) -> None:
    dsl_path = find_dsl(delivery)
    dsl = load_yaml(dsl_path)
    selectors = parse_selectors(dsl)
    flows = parse_flows(dsl)
    playwright_dir = delivery / "playwright"
    specs = collect_specs(delivery)
    results = parse_json_reports(playwright_dir, flows.keys()) if playwright_dir.exists() else []
    results = ensure_results_for_flows(results, flows, specs, delivery)
    artifacts = collect_artifacts(playwright_dir, delivery) if playwright_dir.exists() else {"screenshot": [], "trace": [], "video": []}

    reports_dir = delivery / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    failures = [r for r in results if normalize_status(r.status) == "failed"]
    passed = sum(1 for r in results if normalize_status(r.status) == "passed")
    skipped = sum(1 for r in results if normalize_status(r.status) == "skipped")
    failed = len(failures)
    total = len(results)
    pass_rate = (passed / total * 100) if total else 0.0

    selector_fail_counts: Dict[str, int] = {}
    failure_blocks: List[str] = []
    artifact_index_lines = ["# 产物索引", ""]

    table_lines = [
        "| flow_id | 用例名 | 状态 | 耗时 | 文件 |",
        "|---|---|---:|---:|---|",
    ]

    for result in sorted(results, key=lambda r: (r.flow_id, r.title)):
        flow = flows.get(result.flow_id)
        title = result.title or (flow.name if flow else result.flow_id)
        spec_path = resolve_spec_path(result, specs, delivery)
        spec_rel = as_rel(spec_path, delivery) if spec_path else result.spec
        table_lines.append(
            f"| {md_escape(result.flow_id)} | {md_escape(title)} | {display_status(result.status)} | {duration_text(result.duration_ms)} | {md_escape(spec_rel)} |"
        )

        flow_artifacts = artifacts_for_flow(result.flow_id, title, artifacts)
        artifact_index_lines.extend(
            [
                f"## {result.flow_id}",
                "",
                f"- spec 文件: {spec_rel or '-'}",
                f"- 失败截图: {', '.join(flow_artifacts['screenshot']) or '-'}",
                f"- trace: {', '.join(flow_artifacts['trace']) or '-'}",
                f"- video 视频: {', '.join(flow_artifacts['video']) or '-'}",
                "",
            ]
        )

        if normalize_status(result.status) != "failed":
            continue

        step = match_step(result, flow, selectors, spec_path)
        selector = selectors.get(step.selector_key)
        if step.selector_key:
            selector_fail_counts[step.selector_key] = selector_fail_counts.get(step.selector_key, 0) + 1
        category = classify_failure(result, selector)
        failure_blocks.append(
            "\n".join(
                [
                    f"### {result.flow_id} - {title}",
                    "",
                    "#### 基本信息",
                    "",
                    f"- flow_id: {result.flow_id}",
                    f"- 用例名称: {title}",
                    f"- source_case.tc: {(flow.source_tc if flow else '') or '-'}",
                    f"- priority: {(flow.priority if flow else '') or '-'}",
                    f"- spec 文件路径: {spec_rel or '-'}",
                    "",
                    "#### 失败 step",
                    "",
                    f"- step_id: {step.step_id or '-'}",
                    f"- source_ts: {step.source_ts or '-'}",
                    f"- action: {step.action or '-'}",
                    f"- selector key: {step.selector_key or '-'}",
                    f"- selector 值: {(selector.selector if selector else '') or '-'}",
                    f"- selector 状态: {(selector.status if selector else '') or '-'}",
                    "",
                    "#### 错误信息",
                    "",
                    f"- 失败分类: {category}",
                    f"- 错误消息: {result.error_message or '-'}",
                    "",
                    "```text",
                    trim_stack(result.stack) or "-",
                    "```",
                    "",
                    "#### 失败截图",
                    "",
                    "\n".join(f"- {path}" for path in flow_artifacts["screenshot"]) or "-",
                    "",
                    "#### trace / video",
                    "",
                    "\n".join(f"- trace: {path}" for path in flow_artifacts["trace"]) or "-",
                    "\n".join(f"- video: {path}" for path in flow_artifacts["video"]) or "-",
                    "",
                ]
            )
        )

    todo_selectors = [s for s in selectors.values() if s.status.lower() == "todo"]
    selector_summary = ["## 4. selector 问题汇总", ""]
    if selector_fail_counts:
        selector_summary.extend(["### 失败次数最多的 selector", "", "| selector key | 失败次数 | selector | 状态 |", "|---|---:|---|---|"])
        for key, count in sorted(selector_fail_counts.items(), key=lambda kv: (-kv[1], kv[0])):
            selector = selectors.get(key, SelectorInfo(key=key))
            selector_summary.append(f"| {md_escape(key)} | {count} | {md_escape(selector.selector)} | {md_escape(selector.status)} |")
        selector_summary.append("")
    else:
        selector_summary.extend(["失败结果中未定位到 selector。", ""])
    selector_summary.extend(["### 状态为 todo 的 selector", ""])
    if todo_selectors:
        selector_summary.extend(["| selector key | selector |", "|---|---|"])
        for selector in sorted(todo_selectors, key=lambda s: s.key):
            selector_summary.append(f"| {md_escape(selector.key)} | {md_escape(selector.selector)} |")
    else:
        selector_summary.append("无。")

    suggestions = ["## 5. 建议", ""]
    if todo_selectors:
        suggestions.append("- 建议人工补充 status=todo 的 selector。")
        suggestions.append("- 建议执行 dsl-selector-enrichment --mode probe 对 selector 做受控探测校准。")
    if any(classify_failure(r, selectors.get(match_step(r, flows.get(r.flow_id), selectors, resolve_spec_path(r, specs, delivery)).selector_key)) == "UNRESOLVED_SELECTOR" for r in failures):
        suggestions.append("- 存在未解析 selector 导致的失败，优先处理 DSL selector。")
    if any(re.search(r"captcha|验证码", " ".join([r.error_message, r.stack]), re.I) for r in failures):
        suggestions.append("- 建议跳过验证码用例或改为测试环境白名单/模拟方案。")
    if failures and not selector_fail_counts:
        suggestions.append("- 建议检查 Playwright report JSON 是否完整，必要时保留 json/html report 与 trace。")
    if not suggestions[2:]:
        suggestions.append("- 当前未发现明确的 selector 修复建议。")

    report = "\n".join(
        [
            "# UI 测试报告",
            "",
            f"DSL 文件: `{as_rel(dsl_path, delivery)}`",
            "",
            "## 1. 总览",
            "",
            f"- 总用例数: {total}",
            f"- 通过数: {passed}",
            f"- 失败数: {failed}",
            f"- 跳过数: {skipped}",
            f"- 通过率: {pass_rate:.2f}%",
            "",
            "## 2. 用例执行结果表",
            "",
            "\n".join(table_lines),
            "",
            "## 3. 失败用例详情",
            "",
            "\n".join(failure_blocks) if failure_blocks else "无失败用例。",
            "",
            "\n".join(selector_summary),
            "",
            "\n".join(suggestions),
            "",
        ]
    )

    (reports_dir / "ui-test-report.md").write_text(report, encoding="utf-8")
    (reports_dir / "artifacts-index.md").write_text("\n".join(artifact_index_lines), encoding="utf-8")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="根据 Playwright 执行结果生成 Markdown 测试报告。")
    parser.add_argument("delivery", help="交付目录，例如 ./<delivery-name>")
    args = parser.parse_args(argv)
    delivery = Path(args.delivery).resolve()
    if not delivery.exists() or not delivery.is_dir():
        parser.error(f"交付目录不存在：{delivery}")
    write_reports(delivery)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
