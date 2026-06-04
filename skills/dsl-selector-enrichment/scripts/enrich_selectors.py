#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""对 UI DSL 做 dry/probe 两种模式的 selector 补全。"""

from __future__ import annotations

import argparse
import asyncio
import copy
import os
import re
from difflib import SequenceMatcher
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
UNSAFE_SELECTOR_HINTS = ("captcha", "图形验证码", "图形验证", "验证码", "滑块", "极验", "手动验证", "手动完成验证")
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
    "下单",
    "确认订单",
    "发布",
    "审批",
    "关闭权限",
)
ALLOWED_PROBE_ACTIONS = {"goto", "wait_for"}
ACTION_WORDS = ("未勾选", "勾选", "保持", "点击", "输入", "填写", "按钮", "提交", "确认")
NOISE_LABELS = {"form element", "page element"}
RUNTIME_CLICK_STRATEGIES = {"dsl candidate", "role locator", "text locator"}


@dataclass
class Candidate:
    selector: str
    strategy: str
    count: int | None = None
    visible_count: int | None = None
    visible_index: int | None = None
    score: float | None = None
    threshold: float | None = None
    fuzzy_allowed: bool | None = None
    note: str = ""


@dataclass
class ProbeEvent:
    flow_id: str
    step_id: str
    action: str
    result: str
    reason: str
    screenshot: str = ""


@dataclass
class ProbeState:
    first_click_seen: bool = False


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
    parser.add_argument("--seed-selectors", help="seed selector YAML 文件路径，用于人工锚点覆盖")
    parser.add_argument("--reuse-session", action="store_true", help="probe 模式复用同一个浏览器页面状态执行多个 flow")
    parser.add_argument("--persist-runtime", action="store_true", help="将 runtime-confirmed selector 写回 enriched DSL")
    parser.add_argument("--allow-fuzzy-click", action="store_true", help="允许 runtime click 使用 fuzzy score 门控做探索式安全点击")
    parser.add_argument(
        "--fuzzy-click-threshold",
        type=float,
        default=0.90,
        help="Minimum score required for fuzzy runtime click (default: 0.90)",
    )
    parser.add_argument("--screenshot", action="store_true", help="是否在 probe 模式记录每个 step 执行后的页面截图")
    parser.add_argument("--screenshot-dir", help="截图输出目录（默认：<delivery>/playwright/probe-screenshots）")
    parser.add_argument(
        "--screenshot-mode",
        choices=("viewport", "full-page"),
        default="viewport",
        help="截图模式，viewport：只截当前视口；full-page：截完整页面",
    )
    parser.add_argument("--mobile", action="store_true", help="启用移动端浏览器上下文")
    parser.add_argument("--device", default="iPhone 13", help="移动端设备名称，仅在 --mobile 时生效，默认：iPhone 13")
    parser.add_argument("--viewport", help="覆盖浏览器 viewport，格式：390x844")
    parser.add_argument("--geolocation", help="设置地理位置，格式：30.2741,120.1551")
    parser.add_argument("--permissions", help="授权权限列表，格式：geolocation,camera")
    parser.add_argument("--debug", action="store_true", help="输出候选生成和 locator 探测调试日志")
    parser.add_argument(
        "--mode",
        choices=("dry", "probe"),
        default="dry",
        help="dry：只生成候选；probe：受控执行 flow 前置步骤后做 locator count 探测",
    )
    args = parser.parse_args()
    if not 0.0 <= args.fuzzy_click_threshold <= 1.0:
        parser.error("--fuzzy-click-threshold 必须在 0.0 到 1.0 之间。")
    return args


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


def parse_viewport(value: str | None) -> dict[str, int] | None:
    if not value:
        return None
    match = re.fullmatch(r"\s*(\d+)x(\d+)\s*", value)
    if not match:
        raise ValueError("--viewport 格式必须是 WIDTHxHEIGHT，例如：390x844")
    return {"width": int(match.group(1)), "height": int(match.group(2))}


def parse_geolocation(value: str | None) -> dict[str, float] | None:
    if not value:
        return None
    parts = [part.strip() for part in value.split(",")]
    if len(parts) != 2:
        raise ValueError("--geolocation 格式必须是 latitude,longitude，例如：30.2741,120.1551")
    return {"latitude": float(parts[0]), "longitude": float(parts[1])}


def parse_permissions(value: str | None) -> list[str]:
    if not value:
        return []
    return [part.strip() for part in value.split(",") if part.strip()]


def build_context_options(playwright: Any, args: argparse.Namespace) -> dict[str, Any]:
    if not args.mobile:
        return {}

    if args.device not in playwright.devices:
        available = ", ".join(sorted(playwright.devices.keys()))
        raise ValueError(f"未知 Playwright device：{args.device}。可用 device 包括：{available}")

    context_options = dict(playwright.devices[args.device])
    viewport = parse_viewport(args.viewport)
    geolocation = parse_geolocation(args.geolocation)
    permissions = parse_permissions(args.permissions)
    if viewport:
        context_options["viewport"] = viewport
    if geolocation:
        context_options["geolocation"] = geolocation
    if permissions:
        context_options["permissions"] = permissions
    context_options["locale"] = "zh-CN"
    context_options["timezone_id"] = "Asia/Shanghai"
    return context_options


def probe_environment_lines(args: argparse.Namespace) -> list[str]:
    return [
        "",
        "## Probe 环境",
        "",
        f"- mobile: {str(bool(getattr(args, 'mobile', False))).lower()}",
        f"- device: {as_text(getattr(args, 'device', '')) if getattr(args, 'mobile', False) else ''}",
        f"- viewport: {as_text(getattr(args, 'viewport', ''))}",
        f"- geolocation: {as_text(getattr(args, 'geolocation', ''))}",
        f"- permissions: {as_text(getattr(args, 'permissions', ''))}",
        f"- screenshot-mode: {as_text(getattr(args, 'screenshot_mode', 'viewport'))}",
        f"- allow-fuzzy-click: {str(bool(getattr(args, 'allow_fuzzy_click', False))).lower()}",
        f"- fuzzy-click-threshold: {getattr(args, 'fuzzy_click_threshold', 0.90):.2f}",
    ]


def read_optional_yaml(path_text: str | None) -> dict[str, Any]:
    if not path_text:
        return {}
    path = Path(path_text)
    if not path.exists():
        raise SystemExit(f"seed selector 文件不存在：{path}")
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise SystemExit("seed selector 文件根节点必须是 mapping。")
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
    for phrase in ("以已登录状态", "以未登录状态", "连续多次", "清空或不", "不输入", "保持", "直接", "再次", "重新"):
        cleaned = cleaned.replace(phrase, "")
    for word in ACTION_WORDS:
        cleaned = cleaned.replace(word, "")
    cleaned = cleaned.replace("button", "").replace("input", "")
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" :：,，.。")
    cleaned = re.split(r"[并和且,，]", cleaned)[0].strip()
    return cleaned


def is_noisy_label(label: str) -> bool:
    normalized = label.strip()
    lowered = normalized.lower()
    if re.match(r"^cn[_ ]", lowered):
        return True
    if "并" in normalized or len(normalized) > 24:
        return True
    if lowered in NOISE_LABELS:
        return True
    return False


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


def is_placeholder_selector(selector: str, key: str) -> bool:
    return selector == f'[data-testid="{key}"]' or selector == f"[data-testid='{key}']"


def dsl_candidate_values(entry: dict[str, Any]) -> list[str]:
    raw_candidates = entry.get("candidates", [])
    if not isinstance(raw_candidates, list):
        return []
    values: list[str] = []
    seen: set[str] = set()
    for raw_candidate in raw_candidates:
        if not isinstance(raw_candidate, str):
            continue
        candidate = raw_candidate.strip()
        if candidate and candidate not in seen:
            seen.add(candidate)
            values.append(candidate)
    return values


def generate_candidates(key: str, entry: dict[str, Any], data: dict[str, Any]) -> tuple[str, str, list[Candidate], bool]:
    description = as_text(entry.get("description"))
    source = as_text(entry.get("source")) or key_usage_context(data, key)
    current_selector = as_text(entry.get("selector")).strip()
    combined = " ".join((key, description, source, current_selector))
    labels = label_values(key, description, source)
    candidates: list[Candidate] = []

    def add(selector: str, strategy: str, label: str = "") -> None:
        if selector and all(candidate.selector != selector for candidate in candidates):
            note = "noisy label" if label and is_noisy_label(label) else ""
            candidates.append(Candidate(selector=selector, strategy=strategy, note=note))

    for selector in dsl_candidate_values(entry):
        add(selector, "dsl candidate")

    if current_selector and not is_placeholder_selector(current_selector, key):
        add(current_selector, "原始 selector")

    if contains_any(combined, CHECKBOX_HINTS):
        for label in labels:
            add(f'role=checkbox[name="{label}"]', "role locator", label)
    if contains_any(combined, BUTTON_HINTS):
        for label in labels:
            add(f'role=button[name="{label}"]', "role locator", label)
        for label in labels:
            add(f'role=link[name="{label}"]', "role locator", label)
    if contains_any(combined, INPUT_HINTS):
        for label in labels:
            add(f'role=textbox[name="{label}"]', "role locator", label)
        for label in labels:
            add(f"label={label}", "label locator", label)
        for label in labels:
            add(f"placeholder={label}", "placeholder locator", label)
    if contains_any(" ".join((description, source)), TEXT_HINTS) or contains_any(combined, BUTTON_HINTS):
        for label in labels:
            add(f"text={label}", "text locator", label)

    if not candidates and labels:
        add(f"text={labels[0]}", "text locator (fallback)", labels[0])

    is_unsafe = contains_any(combined, UNSAFE_SELECTOR_HINTS)
    return description, source, candidates, is_unsafe


async def locator_count(page: Any, selector: str) -> int:
    role_match = re.fullmatch(r'role=([A-Za-z0-9_-]+)\[name="(.*)"\]', selector)
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
    role_match = re.fullmatch(r'role=([A-Za-z0-9_-]+)\[name="(.*)"\]', selector)
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


def selector_label(selector: str) -> str:
    role_match = re.fullmatch(r'role=([A-Za-z0-9_-]+)\[name="(.*)"\]', selector)
    if role_match:
        return role_match.group(2)
    for prefix in ("label=", "placeholder=", "text="):
        if selector.startswith(prefix):
            return selector[len(prefix) :]
    return ""


async def visible_locator_text(locator: Any) -> str:
    text_parts: list[str] = []
    for getter in (
        lambda: locator.inner_text(timeout=1000),
        lambda: locator.text_content(timeout=1000),
        lambda: locator.get_attribute("aria-label", timeout=1000),
        lambda: locator.get_attribute("placeholder", timeout=1000),
        lambda: locator.input_value(timeout=1000),
    ):
        try:
            value = await getter()
        except Exception:
            continue
        value_text = as_text(value).strip()
        if value_text:
            text_parts.append(value_text)
    return " ".join(dict.fromkeys(text_parts))


def text_similarity(expected: str, actual: str) -> float | None:
    expected = re.sub(r"\s+", "", expected.strip())
    actual = re.sub(r"\s+", "", actual.strip())
    if not expected or not actual:
        return None
    if expected == actual:
        return 1.0
    if expected in actual or actual in expected:
        shorter = min(len(expected), len(actual))
        longer = max(len(expected), len(actual))
        return shorter / longer if longer else 0.0
    return SequenceMatcher(None, expected, actual).ratio()


async def update_fuzzy_score(candidate: Candidate, locator: Any, threshold: float, allow_fuzzy_click: bool) -> None:
    candidate.threshold = threshold
    candidate.fuzzy_allowed = False
    if candidate.visible_count != 1 or candidate.visible_index is None or not is_runtime_click_candidate(candidate):
        return
    expected = selector_label(candidate.selector)
    actual = await visible_locator_text(locator.nth(candidate.visible_index))
    candidate.score = text_similarity(expected, actual)
    candidate.fuzzy_allowed = bool(allow_fuzzy_click and candidate.score is not None and candidate.score >= threshold)


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


def apply_seed_selectors(enriched: dict[str, Any], seed_data: dict[str, Any]) -> list[ProbeEvent]:
    if not seed_data:
        return []
    raw_selectors = seed_data.get("selectors", {})
    if not isinstance(raw_selectors, dict):
        raise SystemExit("seed selector 文件中的 selectors 必须是 mapping。")

    if "selectors" not in enriched or not isinstance(enriched.get("selectors"), dict):
        enriched["selectors"] = {}
    selectors = enriched["selectors"]
    events: list[ProbeEvent] = []
    for key, seed in raw_selectors.items():
        if not isinstance(seed, dict):
            continue
        selector = as_text(seed.get("selector")).strip()
        status = "confirmed"
        if not selector:
            continue
        if key not in selectors:
            selectors[str(key)] = {
                "selector": selector,
                "description": as_text(seed.get("description")),
                "source": "seed selector",
                "status": status,
                "candidates": [],
            }
        else:
            selectors[str(key)]["selector"] = selector
            selectors[str(key)]["status"] = status
            selectors[str(key)].setdefault("candidates", [])
            if seed.get("description"):
                selectors[str(key)]["description"] = as_text(seed.get("description"))
            source = as_text(selectors[str(key)].get("source"))
            selectors[str(key)]["source"] = f"{source}; seed selector".strip("; ")
        events.append(ProbeEvent("_seed_", str(key), "seed", "applied", f"使用 seed selector 覆盖：{selector}"))
    return events


def update_enriched_selector(enriched: dict[str, Any], result: SelectorResult, selector: str, status: str = "confirmed") -> None:
    entry = selector_entries(enriched)[result.key]
    entry["selector"] = selector
    entry["status"] = status
    result.final_selector = selector
    result.final_status = status


def is_runtime_click_candidate(candidate: Candidate) -> bool:
    selector = candidate.selector
    return (
        candidate.strategy in RUNTIME_CLICK_STRATEGIES
        and (
            selector.startswith("role=button[")
            or selector.startswith("role=link[")
            or selector.startswith("text=")
        )
    )


def is_role_selector(selector: str, role: str | None = None) -> bool:
    match = re.fullmatch(r'role=([A-Za-z0-9_-]+)\[name=".*"\]', selector)
    if not match:
        return False
    return role is None or match.group(1) == role


def candidate_locator_rank(candidate: Candidate) -> int:
    selector = candidate.selector
    strategy = candidate.strategy
    if strategy == "dsl candidate" and any(is_role_selector(selector, role) for role in ("button", "link", "checkbox", "textbox")):
        return 1
    if strategy == "role locator":
        return 2
    if strategy == "label locator":
        return 3
    if strategy == "placeholder locator":
        return 4
    if strategy == "dsl candidate" and selector.startswith("text="):
        return 5
    if strategy == "text locator":
        return 6
    if strategy == "text locator (fallback)":
        return 7
    if strategy == "dsl candidate":
        return 8
    if strategy == "原始 selector":
        return 9
    return 10


def candidate_priority(candidate: Candidate) -> tuple[float, int, str]:
    score = candidate.score if candidate.score is not None else 0.0
    return (candidate_locator_rank(candidate), -score, candidate.selector)


async def wait_after_click(page: Any) -> str:
    try:
        await page.wait_for_load_state("networkidle", timeout=3000)
        return "networkidle"
    except Exception:
        await page.wait_for_timeout(1000)
        return "timeout fallback 1000ms"


async def perform_stable_click(page: Any, locator: Any, timeout_ms: int) -> tuple[str, str, str]:
    before_url = page.url
    await locator.click(timeout=timeout_ms)
    stable_state = await wait_after_click(page)
    after_url = page.url
    return before_url, after_url, stable_state


async def visible_locator_info(locator: Any) -> tuple[int, int | None]:
    count = await locator.count()
    visible_count = 0
    first_visible_index: int | None = None
    for index in range(count):
        if await locator.nth(index).is_visible():
            visible_count += 1
            if first_visible_index is None:
                first_visible_index = index
    return visible_count, first_visible_index


async def unique_visible_locator(locator: Any) -> tuple[bool, Any | None, str]:
    count = await locator.count()
    visible_count, first_visible_index = await visible_locator_info(locator)
    reason = f"count={count}, visible_count={visible_count}, visible_index={first_visible_index}"
    if visible_count == 1 and first_visible_index is not None:
        return True, locator.nth(first_visible_index), reason
    return False, None, reason


def safe_filename_part(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip())
    return cleaned.strip("_") or "unknown"


async def maybe_screenshot(page: Any, flow_id: str, step_id: str, action: str, args: argparse.Namespace) -> str:
    if not getattr(args, "screenshot", False):
        return ""
    base_dir = Path(args.screenshot_dir) if getattr(args, "screenshot_dir", None) else Path("./playwright/probe-screenshots")
    flow_dir = base_dir / safe_filename_part(flow_id)
    flow_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{safe_filename_part(step_id)}_{safe_filename_part(action)}.png"
    path = flow_dir / filename
    try:
        await page.screenshot(path=str(path), full_page=args.screenshot_mode == "full-page")
        return str(path)
    except Exception as exc:  # noqa: BLE001 - 截图失败不能影响 probe 行为
        return f"screenshot failed: {exc}"


async def make_probe_event(
    page: Any,
    flow_id: str,
    step_id: str,
    action: str,
    result: str,
    reason: str,
    args: argparse.Namespace,
) -> ProbeEvent:
    screenshot = await maybe_screenshot(page, flow_id, step_id, action, args)
    return ProbeEvent(flow_id, step_id, action, result, reason, screenshot=screenshot)


async def probe_result_on_page(
    page: Any,
    result: SelectorResult,
    enriched: dict[str, Any],
    flow_id: str,
    *,
    write_back: bool,
    runtime_only: bool = False,
    allow_fuzzy_click: bool = False,
    fuzzy_click_threshold: float = 0.90,
    debug: bool = False,
) -> Candidate | None:
    if result.reason.startswith("安全策略"):
        return None
    result.probed = True
    for candidate in result.candidates:
        if runtime_only and not is_runtime_click_candidate(candidate):
            continue
        try:
            locator = locator_for_action(page, candidate.selector)
            candidate.count = await locator.count()
            candidate.visible_count, candidate.visible_index = await visible_locator_info(locator)
            await update_fuzzy_score(candidate, locator, fuzzy_click_threshold, allow_fuzzy_click)
            if debug:
                print(
                    f"[VISIBLE] selector={candidate.selector} "
                    f"count={candidate.count} "
                    f"visible={candidate.visible_count} "
                    f"score={candidate.score} "
                    f"threshold={candidate.threshold} "
                    f"fuzzy_allowed={candidate.fuzzy_allowed}"
                )
            visibility_note = (
                f"flow={flow_id} count={candidate.count} "
                f"visible_count={candidate.visible_count} "
                f"visible_index={candidate.visible_index} "
                f"score={candidate.score} "
                f"threshold={candidate.threshold} "
                f"fuzzy_allowed={candidate.fuzzy_allowed}"
            )
            candidate.note = f"{candidate.note}; {visibility_note}".strip("; ")
        except Exception as exc:  # noqa: BLE001 - 单个 locator 失败不影响其他候选
            candidate.count = -1
            candidate.visible_count = None
            candidate.visible_index = None
            candidate.score = None
            candidate.fuzzy_allowed = False
            candidate.note = f"locator 探测失败：{exc}"

    unique = [
        candidate
        for candidate in result.candidates
        if candidate.visible_count == 1
        and (
            not runtime_only
            or (
                is_runtime_click_candidate(candidate)
                and (not allow_fuzzy_click or candidate.fuzzy_allowed is True)
            )
        )
    ]
    if not unique:
        return None

    unique = sorted(unique, key=candidate_priority)
    selected = unique[0]
    if write_back:
        update_enriched_selector(enriched, result, selected.selector)
        result.result = "confirmed"
        result.reason = f"在 flow={flow_id} 中唯一匹配，选择候选：{selected.selector}"
        result.strategy = selected.strategy
        result.flow_id = flow_id
    return selected


async def execute_probe_step(
    page: Any,
    step: dict[str, Any],
    enriched: dict[str, Any],
    results: dict[str, SelectorResult],
    base_url: str,
    data_values: dict[str, str],
    state: ProbeState,
    flow_id: str,
    persist_runtime: bool,
    args: argparse.Namespace,
) -> ProbeEvent:
    selectors = selector_entries(enriched)
    action = as_text(step.get("action")).lower()
    step_id = as_text(step.get("id")) or "_unknown_step_"
    target = as_text(step.get("target"))
    timeout_ms = int(step.get("timeout_ms") or 5000)

    if action == "assert_visible":
        return await make_probe_event(page, flow_id, step_id, action, "skipped", "assert step skipped but flow continues", args)

    if contains_any(step_text(step, selectors), UNSAFE_SELECTOR_HINTS):
        return await make_probe_event(page, flow_id, step_id, action, "abort", "遇到验证码、滑块、极验或手动验证步骤，中断当前 flow 探测。", args)
    if contains_any(step_text(step, selectors), UNSAFE_STEP_HINTS):
        return await make_probe_event(page, flow_id, step_id, action, "abort", "遇到可能改变业务状态的危险步骤，中断当前 flow 探测。", args)

    if action == "click":
        is_first_click = not state.first_click_seen
        if not target:
            return await make_probe_event(page, flow_id, step_id, action, "skipped", "click 步骤没有 target，已跳过。", args)
        if selector_status(selectors, target) == "confirmed":
            locator = locator_for_action(page, selector_string(selectors, target))
            ok, visible_locator, visibility_reason = await unique_visible_locator(locator)
            if not ok or visible_locator is None:
                return await make_probe_event(
                    page,
                    flow_id,
                    step_id,
                    action,
                    "skipped",
                    f"unstable confirmed selector：{visibility_reason}，可见元素不是唯一匹配，已跳过当前 step，继续后续探测。",
                    args,
                )
            before_url, after_url, stable_state = await perform_stable_click(page, visible_locator, timeout_ms)
            state.first_click_seen = True
            return await make_probe_event(
                page,
                flow_id,
                step_id,
                action,
                "executed",
                f"safe click using confirmed selector: {selector_string(selectors, target)}; {visibility_reason}; before_url={before_url}; after_url={after_url}; stable={stable_state}",
                args,
            )

        result = results.get(target)
        if result and is_first_click:
            runtime_candidate = await probe_result_on_page(
                page,
                result,
                enriched,
                flow_id,
                write_back=False,
                runtime_only=True,
                allow_fuzzy_click=bool(getattr(args, "allow_fuzzy_click", False)),
                fuzzy_click_threshold=float(getattr(args, "fuzzy_click_threshold", 0.90)),
                debug=bool(getattr(args, "debug", False)),
            )
            if runtime_candidate:
                if persist_runtime:
                    update_enriched_selector(enriched, result, runtime_candidate.selector)
                    result.result = "confirmed"
                    result.reason = f"runtime-confirmed 持久化：{runtime_candidate.selector}"
                    result.strategy = runtime_candidate.strategy
                    result.flow_id = flow_id
                before_url, after_url, stable_state = await perform_stable_click(
                    page,
                    locator_for_action(page, runtime_candidate.selector).nth(runtime_candidate.visible_index or 0),
                    timeout_ms,
                )
                state.first_click_seen = True
                persist_note = " persisted" if persist_runtime else ""
                return await make_probe_event(
                    page,
                    flow_id,
                    step_id,
                    action,
                    "runtime-confirmed",
                    f"runtime-confirmed{persist_note} click using {runtime_candidate.selector}; count={runtime_candidate.count}; visible_count={runtime_candidate.visible_count}; visible_index={runtime_candidate.visible_index}; score={runtime_candidate.score}; threshold={runtime_candidate.threshold}; fuzzy_allowed={runtime_candidate.fuzzy_allowed}; before_url={before_url}; after_url={after_url}; stable={stable_state}",
                    args,
                )

        if result:
            selected = await probe_result_on_page(
                page,
                result,
                enriched,
                flow_id,
                write_back=False,
                allow_fuzzy_click=bool(getattr(args, "allow_fuzzy_click", False)),
                fuzzy_click_threshold=float(getattr(args, "fuzzy_click_threshold", 0.90)),
                debug=bool(getattr(args, "debug", False)),
            )
            if selected:
                locator = locator_for_action(page, selected.selector)
                ok, visible_locator, visibility_reason = await unique_visible_locator(locator)
                if not ok or visible_locator is None:
                    return await make_probe_event(
                        page,
                        flow_id,
                        step_id,
                        action,
                        "skipped",
                        f"unstable probe confirmed selector：{visibility_reason}，可见元素不是唯一匹配，已跳过当前 step，继续后续探测。",
                        args,
                    )
                before_url, after_url, stable_state = await perform_stable_click(page, visible_locator, timeout_ms)
                update_enriched_selector(enriched, result, selected.selector)
                result.result = "confirmed"
                result.reason = f"click 成功后确认候选：{selected.selector}"
                result.strategy = selected.strategy
                result.flow_id = flow_id
                state.first_click_seen = True
                return await make_probe_event(
                    page,
                    flow_id,
                    step_id,
                    action,
                    "executed",
                    f"safe click using probe confirmed selector: {selected.selector}; {visibility_reason}; before_url={before_url}; after_url={after_url}; stable={stable_state}",
                    args,
                )

        return await make_probe_event(page, flow_id, step_id, action, "skipped", "target selector 未 confirmed，禁止模糊 click。", args)
    if action == "fill":
        value = as_text(step.get("value"))
        ref = test_data_reference(value)
        if ref and (ref not in data_values or data_values.get(ref) == ""):
            return await make_probe_event(page, flow_id, step_id, action, "skipped", f"fill 依赖的 test_data 缺失或为空：{ref}，已跳过。", args)
        return await make_probe_event(page, flow_id, step_id, action, "skipped", "probe v1 不执行 fill，仅记录跳过。", args)

    if action not in ALLOWED_PROBE_ACTIONS:
        return await make_probe_event(page, flow_id, step_id, action, "abort", f"不支持的 probe action：{action}", args)

    if action == "goto":
        await page.goto(resolve_url(base_url, as_text(step.get("url"))), wait_until="domcontentloaded", timeout=timeout_ms)
        return await make_probe_event(page, flow_id, step_id, action, "executed", "已打开页面。", args)

    if action == "wait_for":
        if target and selector_status(selectors, target) == "confirmed":
            await locator_for_action(page, selector_string(selectors, target)).wait_for(timeout=timeout_ms)
            return await make_probe_event(page, flow_id, step_id, action, "executed", "已等待 confirmed selector 出现。", args)
        await page.wait_for_timeout(min(timeout_ms, 5000))
        return await make_probe_event(page, flow_id, step_id, action, "executed", "未提供 confirmed selector，按 timeout 做受控等待。", args)

    return await make_probe_event(page, flow_id, step_id, action, "skipped", "步骤未执行。", args)


async def probe_selector_results(
    data: dict[str, Any],
    enriched: dict[str, Any],
    results: dict[str, SelectorResult],
    base_url: str,
    reuse_session: bool,
    seed_events: list[ProbeEvent],
    persist_runtime: bool,
    args: argparse.Namespace,
) -> tuple[str, list[ProbeEvent]]:
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return "未安装 Playwright Python 包。", []

    events: list[ProbeEvent] = list(seed_events)
    data_values = test_data_values(data)

    try:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True)
            context_options = build_context_options(playwright, args)
            context = await browser.new_context(**context_options)
            source_flows = flows(data) or [{"id": "_default_", "steps": [{"id": "goto_base", "action": "goto", "url": ""}]}]
            shared_page = await context.new_page() if reuse_session else None
            for flow in source_flows:
                flow_id = as_text(flow.get("id")) or "_unknown_flow_"
                page = shared_page or await context.new_page()
                state = ProbeState()
                try:
                    flow_steps = [step for step in flow.get("steps", []) if isinstance(step, dict)]
                    first_action = as_text(flow_steps[0].get("action")).lower() if flow_steps else ""
                    if first_action != "goto":
                        if not reuse_session or page.url == "about:blank":
                            await page.goto(base_url, wait_until="domcontentloaded", timeout=30000)
                    target_keys = flow_target_selector_keys(flow_steps, results)
                    if not target_keys:
                        events.append(ProbeEvent(flow_id, "_flow_", "probe", "skipped", "本 flow steps 未使用 todo target selector，跳过 selector 探测。"))
                    aborted = False
                    for step in flow_steps:
                        event = await execute_probe_step(
                            page,
                            step,
                            enriched,
                            results,
                            base_url,
                            data_values,
                            state,
                            flow_id,
                            persist_runtime,
                            args,
                        )
                        event.flow_id = flow_id
                        events.append(event)
                        if event.result == "abort":
                            aborted = True
                            break
                    if aborted:
                        continue
                    await probe_counts_on_page(page, results, enriched, flow_id, target_keys, args)
                finally:
                    if not reuse_session:
                        await page.close()
            if shared_page:
                await shared_page.close()
            await context.close()
            await browser.close()
    except Exception as exc:  # noqa: BLE001 - 记录探测失败，不覆盖原始 DSL
        return f"probe 探测失败：{exc}", events
    return "", events


async def probe_counts_on_page(
    page: Any,
    results: dict[str, SelectorResult],
    enriched: dict[str, Any],
    flow_id: str,
    target_keys: set[str],
    args: argparse.Namespace,
) -> None:
    try:
        await page.wait_for_load_state("networkidle", timeout=5000)
    except Exception:
        pass
    for key, result in results.items():
        if key not in target_keys:
            continue
        if result.final_status.lower() == "confirmed" or result.reason.startswith("安全策略"):
            continue
        await probe_result_on_page(
            page,
            result,
            enriched,
            flow_id,
            write_back=True,
            fuzzy_click_threshold=float(getattr(args, "fuzzy_click_threshold", 0.90)),
            debug=bool(getattr(args, "debug", False)),
        )


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
        elif any(candidate.visible_count and candidate.visible_count > 1 for candidate in result.candidates):
            result.reason = "候选 locator 存在可见匹配但不唯一。"
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


def screenshot_markdown(screenshot: str, report_path: Path) -> str:
    if not screenshot:
        return ""
    if screenshot.startswith("screenshot failed:"):
        return markdown_escape(screenshot)
    try:
        relative_path = os.path.relpath(screenshot, report_path.parent)
    except ValueError:
        relative_path = screenshot
    return f"![screenshot]({relative_path})"


def write_report(
    path: Path,
    original_selectors: dict[str, dict[str, Any]],
    final_selectors: dict[str, dict[str, Any]],
    results: dict[str, SelectorResult],
    events: list[ProbeEvent],
    mode: str,
    probe_error: str,
    args: argparse.Namespace,
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
    lines.extend(probe_environment_lines(args))
    lines.extend(["", "## 受控探测执行记录", ""])
    if events:
        lines.extend(["| flow | step | action | 结果 | 原因 | 截图 |", "| --- | --- | --- | --- | --- | --- |"])
        for event in events:
            lines.append(
                f"| {markdown_escape(event.flow_id)} | {markdown_escape(event.step_id)} | {markdown_escape(event.action)} | {markdown_escape(event.result)} | {markdown_escape(event.reason)} | {screenshot_markdown(event.screenshot, path)} |"
            )
    else:
        lines.append("无受控探测执行记录。")

    runtime_events = [
        event
        for event in events
        if event.action in {"seed", "goto", "click"} or event.result in {"runtime-confirmed", "executed"}
    ]
    lines.extend(["", "## runtime 行为", ""])
    if runtime_events:
        lines.extend(["| flow | step | 行为 | 结果 | 路径/selector | 截图 |", "| --- | --- | --- | --- | --- | --- |"])
        for event in runtime_events:
            lines.append(
                f"| {markdown_escape(event.flow_id)} | {markdown_escape(event.step_id)} | {markdown_escape(event.action)} | {markdown_escape(event.result)} | {markdown_escape(event.reason)} | {screenshot_markdown(event.screenshot, path)} |"
            )
    else:
        lines.append("无 runtime click、seed selector 或进入路径记录。")

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
                "| 候选 locator | 策略 | count | visible_count | visible_index | score | threshold | fuzzy_allowed | 备注 |",
                "| --- | --- | ---: | ---: | ---: | ---: | ---: | --- | --- |",
            ]
        )
        for candidate in result.candidates:
            count = "" if candidate.count is None else str(candidate.count)
            visible_count = "" if candidate.visible_count is None else str(candidate.visible_count)
            visible_index = "" if candidate.visible_index is None else str(candidate.visible_index)
            score = "" if candidate.score is None else f"{candidate.score:.2f}"
            threshold = "" if candidate.threshold is None else f"{candidate.threshold:.2f}"
            fuzzy_allowed = "" if candidate.fuzzy_allowed is None else str(candidate.fuzzy_allowed).lower()
            lines.append(
                f"| `{markdown_escape(candidate.selector)}` | {markdown_escape(candidate.strategy)} | {count} | {visible_count} | {visible_index} | {score} | {threshold} | {fuzzy_allowed} | {markdown_escape(candidate.note)} |"
            )
        if not result.candidates:
            lines.append("| _无_ |  |  |  |  |  |  |  |  |")
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
    if args.screenshot and not args.screenshot_dir:
        args.screenshot_dir = str(input_path.parent.parent / "playwright" / "probe-screenshots")
    data = read_yaml(input_path)
    enriched = copy.deepcopy(data)
    seed_events = apply_seed_selectors(enriched, read_optional_yaml(args.seed_selectors))
    results = build_selector_results(enriched)
    events: list[ProbeEvent] = []
    probe_error = ""

    if args.mode == "probe" and results:
        probe_error, events = await probe_selector_results(
            data,
            enriched,
            results,
            args.base_url,
            args.reuse_session,
            seed_events,
            args.persist_runtime,
            args,
        )
    elif seed_events:
        events = seed_events

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
        args,
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
