#!/usr/bin/env python3
"""对 UI DSL 做 dry/probe 两种模式的 selector 补全。"""

from __future__ import annotations

import argparse
import asyncio
import copy
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

try:
    import yaml
except ImportError as exc:
    raise SystemExit("缺少 PyYAML。运行脚本前请先安装 pyyaml。") from exc


BUTTON_HINTS = ("button", "按钮", "点击", "提交", "确认")
INPUT_HINTS = ("input", "输入", "填写", "手机号", "密码", "名称")
CHECKBOX_HINTS = ("checkbox", "勾选", "选中", "协议", "同意")
TEXT_HINTS = ("显示", "提示", "看到", "校验文案")
UNSAFE_SELECTOR_HINTS = ("captcha", "图形验证码", "验证码", "滑块", "极验", "手动验证", "手动完成验证")
UNSAFE_STEP_HINTS = (
    "delete",
    "remove",
    "submit",
    "save",
    "pay",
    "publish",
    "approve",
    "permission",
    "删除",
    "提交",
    "保存",
    "支付",
    "确认订单",
    "发布",
    "审批",
    "关闭权限",
)
ALLOWED_PROBE_ACTIONS = {"goto", "wait_for"}
ACTION_WORDS = ("点击", "输入", "填写", "按钮", "提交", "确认")


@dataclass
class Candidate:
    selector: str
    strategy: str
    count: int | None = None
    note: str = ""


@dataclass
class ProbeEvent:
    flow_id: str
    step_id: str
    action: str
    result: str
    reason: str


@dataclass
class SelectorResult:
    key: str
    description: str = ""
    source: str = ""
    current_selector: str = ""
    original_status: str = ""
    final_selector: str = ""
    final_status: str = ""
    result: str = "unchanged"
    reason: str = ""
    strategy: str = ""
    candidates: list[Candidate] = field(default_factory=list)
    flow_id: str = ""
    probed: bool = False


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", dest="input_path", help="ui-test.dsl.yaml 输入路径")
    parser.add_argument("--output", help="ui-test.enriched.dsl.yaml 输出路径")
    parser.add_argument("--report", help="selector-enrichment-report.md 输出路径")
    parser.add_argument("--unresolved", help="unresolved-selectors.md 输出路径")
    parser.add_argument("--base-url", help="probe 模式页面入口 URL")
    parser.add_argument(
        "--mode",
        choices=("dry", "probe"),
        default="dry",
        help="dry：只生成候选；probe：受控执行 flow 前置步骤后做 locator count 探测",
    )
    return parser.parse_args()


def resolve_paths(args: argparse.Namespace) -> tuple[Path, Path, Path, Path]:
    if args.input_path:
        input_path = Path(args.input_path)
    else:
        matches = sorted(Path(".").glob("*/ui-dsl/ui-test.dsl.yaml"))
        if not matches:
            raise SystemExit("未找到 */ui-dsl/ui-test.dsl.yaml，请传入 --input。")
        if len(matches) > 1:
            listed = "\n".join(f"- {path}" for path in matches)
            raise SystemExit("找到多个 UI DSL 文件，请指定 --input 或 delivery-name：\n" + listed)
        input_path = matches[0]

    if not input_path.exists():
        raise SystemExit(f"输入文件不存在：{input_path}")

    ui_dsl_dir = input_path.parent
    output = Path(args.output) if args.output else ui_dsl_dir / "ui-test.enriched.dsl.yaml"
    report = Path(args.report) if args.report else ui_dsl_dir / "selector-enrichment-report.md"
    unresolved = Path(args.unresolved) if args.unresolved else ui_dsl_dir / "unresolved-selectors.md"
    return input_path, output, report, unresolved


def read_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise SystemExit("DSL 根节点必须是 mapping。")
    return data


def write_yaml(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(data, handle, allow_unicode=True, sort_keys=False)


def as_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (str, int, float, bool)):
        return str(value)
    if isinstance(value, list):
        return " ".join(as_text(item) for item in value if item is not None)
    if isinstance(value, dict):
        parts: list[str] = []
        for key in ("id", "description", "source", "source_ts", "expected", "comment", "name", "title", "target"):
            if key in value:
                parts.append(as_text(value[key]))
        return " ".join(part for part in parts if part)
    return str(value)


def selector_entries(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    selectors = data.get("selectors", {})
    if not isinstance(selectors, dict):
        raise SystemExit("DSL 字段 selectors 必须是 mapping。")
    return {str(key): value for key, value in selectors.items() if isinstance(value, dict)}


def flows(data: dict[str, Any]) -> list[dict[str, Any]]:
    value = data.get("flows", [])
    return value if isinstance(value, list) else []


def test_data_values(data: dict[str, Any]) -> dict[str, str]:
    values: dict[str, str] = {}
    raw = data.get("test_data", {})
    if not isinstance(raw, dict):
        return values
    for key, item in raw.items():
        if isinstance(item, dict):
            values[str(key)] = as_text(item.get("value"))
        else:
            values[str(key)] = as_text(item)
    return values


def key_usage_context(data: Any, selector_key: str) -> str:
    contexts: list[str] = []

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            if node.get("target") == selector_key or node.get("selector") == selector_key or node.get("selector_key") == selector_key:
                contexts.append(as_text(node))
            for child in node.values():
                walk(child)
        elif isinstance(node, list):
            for child in node:
                walk(child)

    walk(data)
    return " ".join(contexts)


def contains_any(text: str, hints: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(hint.lower() in lowered for hint in hints)


def clean_label(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", text.strip())
    cleaned = re.sub(r"^[：:，,。.\s]+|[：:，,。.\s]+$", "", cleaned)
    for word in ACTION_WORDS:
        cleaned = cleaned.replace(word, "")
    cleaned = cleaned.replace("button", "").replace("input", "")
    return re.sub(r"\s+", " ", cleaned).strip(" :：,，.。")


def quoted_fragments(text: str) -> list[str]:
    return [value.strip() for value in re.findall(r"[\"'“”‘’](.*?)[\"'“”‘’]", text) if value.strip()]


def label_values(key: str, description: str, source: str) -> list[str]:
    values: list[str] = []
    values.extend(quoted_fragments(" ".join((description, source))))
    for raw in (description, source):
        cleaned = clean_label(raw)
        if cleaned and len(cleaned) <= 40:
            values.append(cleaned)
    key_label = clean_label(key.replace("_", " ").replace("-", " "))
    if key_label:
        values.append(key_label)

    deduped: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value not in seen:
            seen.add(value)
            deduped.append(value)
    return deduped[:5]


def generate_candidates(key: str, entry: dict[str, Any], data: dict[str, Any]) -> tuple[str, str, list[Candidate], bool]:
    description = as_text(entry.get("description"))
    source = as_text(entry.get("source")) or key_usage_context(data, key)
    current_selector = as_text(entry.get("selector")).strip()
    combined = " ".join((key, description, source, current_selector))
    labels = label_values(key, description, source)
    candidates: list[Candidate] = []

    def add(selector: str, strategy: str) -> None:
        if selector and all(candidate.selector != selector for candidate in candidates):
            candidates.append(Candidate(selector=selector, strategy=strategy))

    add(current_selector, "原始 selector")

    if contains_any(combined, CHECKBOX_HINTS):
        for label in labels:
            add(f'role=checkbox[name="{label}"]', "role locator")
    if contains_any(combined, BUTTON_HINTS):
        for label in labels:
            add(f'role=button[name="{label}"]', "role locator")
    if contains_any(combined, INPUT_HINTS):
        for label in labels:
            add(f"label={label}", "label locator")
        for label in labels:
            add(f"placeholder={label}", "placeholder locator")
    if contains_any(" ".join((description, source)), TEXT_HINTS) or contains_any(combined, BUTTON_HINTS):
        for label in labels:
            add(f"text={label}", "text locator")

    is_unsafe = contains_any(combined, UNSAFE_SELECTOR_HINTS)
    return description, source, candidates, is_unsafe


async def locator_count(page: Any, selector: str) -> int:
    role_match = re.fullmatch(r'role=(button|checkbox)\[name="(.*)"\]', selector)
    if role_match:
        role, name = role_match.groups()
        return await page.get_by_role(role, name=name).count()
    if selector.startswith("label="):
        return await page.get_by_label(selector[len("label=") :]).count()
    if selector.startswith("placeholder="):
        return await page.get_by_placeholder(selector[len("placeholder=") :]).count()
    if selector.startswith("text="):
        return await page.get_by_text(selector[len("text=") :], exact=True).count()
    return await page.locator(selector).count()


def locator_for_action(page: Any, selector: str) -> Any:
    role_match = re.fullmatch(r'role=(button|checkbox)\[name="(.*)"\]', selector)
    if role_match:
        role, name = role_match.groups()
        return page.get_by_role(role, name=name)
    if selector.startswith("label="):
        return page.get_by_label(selector[len("label=") :])
    if selector.startswith("placeholder="):
        return page.get_by_placeholder(selector[len("placeholder=") :])
    if selector.startswith("text="):
        return page.get_by_text(selector[len("text=") :], exact=True)
    return page.locator(selector)


def resolve_url(base_url: str, step_url: str) -> str:
    if step_url.startswith(("http://", "https://")):
        return step_url
    if step_url:
        return urljoin(base_url.rstrip("/") + "/", step_url.lstrip("/"))
    return base_url


def test_data_reference(value: str) -> str:
    match = re.fullmatch(r"\$\{([^}]+)\}", value.strip())
    return match.group(1) if match else ""


def step_text(step: dict[str, Any], selectors: dict[str, dict[str, Any]]) -> str:
    target = as_text(step.get("target"))
    target_meta = selectors.get(target, {})
    return " ".join((as_text(step), as_text(target_meta)))


def selector_status(selectors: dict[str, dict[str, Any]], key: str) -> str:
    return as_text(selectors.get(key, {}).get("status")).lower()


def selector_string(selectors: dict[str, dict[str, Any]], key: str) -> str:
    return as_text(selectors.get(key, {}).get("selector")).strip()


def flow_target_selector_keys(flow_steps: list[dict[str, Any]], results: dict[str, SelectorResult]) -> set[str]:
    keys: set[str] = set()
    for step in flow_steps:
        target = as_text(step.get("target"))
        if target in results:
            keys.add(target)
    return keys


async def execute_probe_step(
    page: Any,
    step: dict[str, Any],
    selectors: dict[str, dict[str, Any]],
    base_url: str,
    data_values: dict[str, str],
) -> ProbeEvent:
    action = as_text(step.get("action")).lower()
    step_id = as_text(step.get("id")) or "_unknown_step_"
    target = as_text(step.get("target"))
    timeout_ms = int(step.get("timeout_ms") or 5000)

    if contains_any(step_text(step, selectors), UNSAFE_SELECTOR_HINTS):
        return ProbeEvent("", step_id, action, "abort", "遇到验证码、滑块、极验或手动验证步骤，中断当前 flow 探测。")
    if contains_any(step_text(step, selectors), UNSAFE_STEP_HINTS):
        return ProbeEvent("", step_id, action, "abort", "遇到可能改变业务状态的危险步骤，中断当前 flow 探测。")

    if action == "click":
        return ProbeEvent("", step_id, action, "skipped", "probe v1 不执行 click，仅允许 goto / wait_for。")
    if action == "fill":
        value = as_text(step.get("value"))
        ref = test_data_reference(value)
        if ref and (ref not in data_values or data_values.get(ref) == ""):
            return ProbeEvent("", step_id, action, "skipped", f"fill 依赖的 test_data 缺失或为空：{ref}，已跳过。")
        return ProbeEvent("", step_id, action, "skipped", "probe v1 不执行 fill，仅记录跳过。")

    if action not in ALLOWED_PROBE_ACTIONS:
        return ProbeEvent("", step_id, action, "abort", f"不支持的 probe action：{action}")

    if action == "goto":
        await page.goto(resolve_url(base_url, as_text(step.get("url"))), wait_until="domcontentloaded", timeout=timeout_ms)
        return ProbeEvent("", step_id, action, "executed", "已打开页面。")

    if action == "wait_for":
        if target and selector_status(selectors, target) == "confirmed":
            await locator_for_action(page, selector_string(selectors, target)).wait_for(timeout=timeout_ms)
            return ProbeEvent("", step_id, action, "executed", "已等待 confirmed selector 出现。")
        await page.wait_for_timeout(min(timeout_ms, 5000))
        return ProbeEvent("", step_id, action, "executed", "未提供 confirmed selector，按 timeout 做受控等待。")

    return ProbeEvent("", step_id, action, "skipped", "步骤未执行。")


async def probe_selector_results(
    data: dict[str, Any],
    enriched: dict[str, Any],
    results: dict[str, SelectorResult],
    base_url: str,
) -> tuple[str, list[ProbeEvent]]:
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return "未安装 Playwright Python 包。", []

    events: list[ProbeEvent] = []
    data_values = test_data_values(data)

    try:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True)
            source_flows = flows(data) or [{"id": "_default_", "steps": [{"id": "goto_base", "action": "goto", "url": ""}]}]
            for flow in source_flows:
                flow_id = as_text(flow.get("id")) or "_unknown_flow_"
                page = await browser.new_page()
                try:
                    flow_steps = [step for step in flow.get("steps", []) if isinstance(step, dict)]
                    first_action = as_text(flow_steps[0].get("action")).lower() if flow_steps else ""
                    if not flow_steps or first_action != "goto":
                        await page.goto(base_url, wait_until="domcontentloaded", timeout=30000)
                    target_keys = flow_target_selector_keys(flow_steps, results)
                    if not target_keys:
                        events.append(ProbeEvent(flow_id, "_flow_", "probe", "skipped", "本 flow steps 未使用 todo target selector，跳过 selector 探测。"))
                    aborted = False
                    for step in flow_steps:
                        event = await execute_probe_step(
                            page,
                            step,
                            selector_entries(enriched),
                            base_url,
                            data_values,
                        )
                        event.flow_id = flow_id
                        events.append(event)
                        if event.result == "abort":
                            aborted = True
                            break
                    if aborted:
                        continue
                    await probe_counts_on_page(page, results, flow_id, target_keys)
                finally:
                    await page.close()
            await browser.close()
    except Exception as exc:  # noqa: BLE001 - 记录探测失败，不覆盖原始 DSL
        return f"probe 探测失败：{exc}", events
    return "", events


async def probe_counts_on_page(page: Any, results: dict[str, SelectorResult], flow_id: str, target_keys: set[str]) -> None:
    try:
        await page.wait_for_load_state("networkidle", timeout=5000)
    except Exception:
        pass
    for key, result in results.items():
        if key not in target_keys:
            continue
        if result.final_status.lower() == "confirmed" or result.reason.startswith("安全策略"):
            continue
        result.probed = True
        for candidate in result.candidates:
            if candidate.count == 1:
                continue
            try:
                count = await locator_count(page, candidate.selector)
                if candidate.count is None or count == 1:
                    candidate.count = count
                    candidate.note = f"flow={flow_id}"
                elif count > 0:
                    candidate.note = f"{candidate.note}; flow={flow_id} count={count}".strip("; ")
            except Exception as exc:  # noqa: BLE001 - 单个 locator 失败不影响其他候选
                candidate.count = -1
                candidate.note = f"locator 探测失败：{exc}"

        unique = [candidate for candidate in result.candidates if candidate.count == 1]
        if unique:
            selected = unique[0]
            result.final_selector = selected.selector
            result.final_status = "confirmed"
            result.result = "confirmed"
            result.reason = f"在 flow={flow_id} 中唯一匹配，选择候选：{selected.selector}"
            result.strategy = selected.strategy
            result.flow_id = flow_id


def apply_results(enriched: dict[str, Any], results: dict[str, SelectorResult], mode: str, probe_error: str) -> None:
    selectors = selector_entries(enriched)
    for key, result in results.items():
        entry = selectors[key]
        if probe_error and not result.reason:
            result.reason = probe_error
        if mode == "dry" and not result.reason:
            result.reason = "dry 模式只生成候选，不打开浏览器，不自动确认。"
        if result.result == "confirmed":
            entry["selector"] = result.final_selector
            entry["status"] = "confirmed"
            continue
        if result.reason:
            continue
        if not result.candidates:
            result.reason = "未生成候选 locator。"
        elif mode == "probe" and not result.probed:
            result.reason = "probe 模式仅探测每个 flow steps 中使用到的 target selector；该 selector 未被可完成前置探测的 flow 覆盖。"
        elif any(candidate.count and candidate.count > 1 for candidate in result.candidates):
            result.reason = "候选 locator 存在匹配但不唯一。"
        else:
            result.reason = "候选 locator 未匹配到页面元素。"


def build_selector_results(data: dict[str, Any]) -> dict[str, SelectorResult]:
    results: dict[str, SelectorResult] = {}
    for key, entry in selector_entries(data).items():
        status = as_text(entry.get("status")).lower()
        if status != "todo":
            continue
        description, source, candidates, is_unsafe = generate_candidates(key, entry, data)
        result = SelectorResult(
            key=key,
            description=description,
            source=source,
            current_selector=as_text(entry.get("selector")).strip(),
            original_status=as_text(entry.get("status")),
            final_selector=as_text(entry.get("selector")).strip(),
            final_status=as_text(entry.get("status")),
            candidates=candidates,
        )
        if is_unsafe:
            result.reason = "安全策略：captcha、验证码、滑块、极验或手动验证相关 selector 永远保持 todo。"
        results[key] = result
    return results


def markdown_escape(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ").strip()


def display_result(value: str) -> str:
    return {"unchanged": "保持 todo", "confirmed": "已补全"}.get(value, value)


def write_report(
    path: Path,
    original_selectors: dict[str, dict[str, Any]],
    final_selectors: dict[str, dict[str, Any]],
    results: dict[str, SelectorResult],
    events: list[ProbeEvent],
    mode: str,
    probe_error: str,
) -> None:
    total = len(original_selectors)
    todo_total = sum(1 for entry in original_selectors.values() if as_text(entry.get("status")).lower() == "todo")
    confirmed_total = sum(1 for entry in original_selectors.values() if as_text(entry.get("status")).lower() == "confirmed")
    success_total = sum(1 for result in results.values() if result.result == "confirmed")
    failure_total = sum(1 for result in results.values() if result.final_status.lower() == "todo")
    final_todo_total = sum(1 for entry in final_selectors.values() if as_text(entry.get("status")).lower() == "todo")
    final_confirmed_total = sum(1 for entry in final_selectors.values() if as_text(entry.get("status")).lower() == "confirmed")

    lines = [
        "# Selector 补全报告",
        "",
        f"- 模式：{mode}",
        f"- selector 总数：{total}",
        f"- 补全前 todo 数：{todo_total}",
        f"- 补全前 confirmed 数：{confirmed_total}",
        f"- 补全后 todo 数：{final_todo_total}",
        f"- 补全后 confirmed 数：{final_confirmed_total}",
        f"- 本次补全成功数：{success_total}",
        f"- 失败数：{failure_total}",
    ]
    if probe_error:
        lines.append(f"- probe 全局错误：{probe_error}")
    lines.extend(["", "## 受控探测执行记录", ""])
    if events:
        lines.extend(["| flow | step | action | 结果 | 原因 |", "| --- | --- | --- | --- | --- |"])
        for event in events:
            lines.append(
                f"| {markdown_escape(event.flow_id)} | {markdown_escape(event.step_id)} | {markdown_escape(event.action)} | {markdown_escape(event.result)} | {markdown_escape(event.reason)} |"
            )
    else:
        lines.append("无受控探测执行记录。")

    lines.extend(["", "## selector 处理明细", ""])
    for result in results.values():
        lines.extend(
            [
                f"### {result.key}",
                "",
                f"- 是否成功：{display_result(result.result)}",
                f"- 当前 selector：`{result.current_selector}`",
                f"- 最终 selector：`{result.final_selector}`",
                f"- 原因：{result.reason}",
                f"- 使用策略：{result.strategy or '_未确认_'}",
                f"- 命中 flow：{result.flow_id or '_无_'}",
                "",
                "| 候选 locator | 策略 | count | 备注 |",
                "| --- | --- | ---: | --- |",
            ]
        )
        for candidate in result.candidates:
            count = "" if candidate.count is None else str(candidate.count)
            lines.append(
                f"| `{markdown_escape(candidate.selector)}` | {markdown_escape(candidate.strategy)} | {count} | {markdown_escape(candidate.note)} |"
            )
        if not result.candidates:
            lines.append("| _无_ |  |  |  |")
        lines.append("")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_unresolved(path: Path, results: dict[str, SelectorResult]) -> None:
    unresolved = [result for result in results.values() if result.final_status.lower() == "todo"]
    lines = ["# 未解决 Selectors", ""]
    if not unresolved:
        lines.append("没有未解决的 todo selectors。")
    for result in unresolved:
        lines.extend(
            [
                f"## {result.key}",
                "",
                f"- key：{result.key}",
                f"- description：{result.description or '_空_'}",
                f"- source：{result.source or '_空_'}",
                f"- 当前 selector：`{result.current_selector}`",
                f"- 失败原因：{result.reason}",
                "- 建议人工处理方式：人工检查页面 DOM 和可访问性树，填写稳定且唯一的 role、label、placeholder、text、data-testid、id 或 class selector；确认唯一匹配后再将 status 改为 confirmed。",
                "",
            ]
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


async def async_main() -> int:
    args = parse_args()
    if args.mode == "probe" and not args.base_url:
        raise SystemExit("probe 模式必须传入 --base-url。")

    input_path, output_path, report_path, unresolved_path = resolve_paths(args)
    data = read_yaml(input_path)
    enriched = copy.deepcopy(data)
    results = build_selector_results(data)
    events: list[ProbeEvent] = []
    probe_error = ""

    if args.mode == "probe" and results:
        probe_error, events = await probe_selector_results(data, enriched, results, args.base_url)

    apply_results(enriched, results, args.mode, probe_error)
    write_yaml(output_path, enriched)
    write_report(
        report_path,
        selector_entries(data),
        selector_entries(enriched),
        results,
        events,
        args.mode,
        probe_error,
    )
    write_unresolved(unresolved_path, results)

    print(f"已写入 enriched DSL：{output_path}")
    print(f"已写入补全报告：{report_path}")
    print(f"已写入未解决 selector 清单：{unresolved_path}")
    return 0


def main() -> int:
    return asyncio.run(async_main())


if __name__ == "__main__":
    raise SystemExit(main())
