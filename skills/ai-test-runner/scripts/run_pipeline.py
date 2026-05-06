#!/usr/bin/env python3
"""校验并输出 AI 测试流水线调度计划。

本辅助脚本有意不实现 PRD、测试用例、DSL 或 spec 转换逻辑。
它只做计划、校验、命令输出和 pipeline-run-report.md 生成。
"""

from __future__ import annotations

import argparse
import glob
import os
from pathlib import Path
import re
import shlex
import sys


STAGES = {
    1: {"alias": "prd", "name": "PRD 转测试用例"},
    2: {"alias": "dsl", "name": "测试用例转 DSL"},
    4: {"alias": "enrich", "name": "Selector 补全"},
    3: {"alias": "spec", "name": "DSL 转 Playwright Spec"},
    5: {"alias": "run", "name": "执行 Playwright"},
    6: {"alias": "report", "name": "生成测试报告"},
}

STAGE_ALIASES = {
    "1": 1,
    "prd": 1,
    "prd转测试用例": 1,
    "prd解析": 1,
    "2": 2,
    "dsl": 2,
    "测试用例转dsl": 2,
    "生成dsl": 2,
    "3": 3,
    "spec": 3,
    "生成spec": 3,
    "dsl转playwrightspec": 3,
    "dsl转spec": 3,
    "4": 4,
    "enrich": 4,
    "selector补全": 4,
    "补全selector": 4,
    "5": 5,
    "run": 5,
    "执行playwright": 5,
    "执行测试": 5,
    "6": 6,
    "report": 6,
    "生成测试报告": 6,
    "生成报告": 6,
}

FULL_WITH_ENRICHMENT = [1, 2, 4, 3, 5, 6]
FULL_WITHOUT_ENRICHMENT = [1, 2, 3, 5, 6]
RESUME_WITH_ENRICHMENT = {
    2: [2, 4, 3, 5, 6],
    3: [3, 5, 6],
    4: [4, 3, 5, 6],
    5: [5, 6],
    6: [6],
}
RESUME_WITHOUT_ENRICHMENT = {
    2: [2, 3, 5, 6],
    3: [3, 5, 6],
    4: [4, 3, 5, 6],
    5: [5, 6],
    6: [6],
}

ARTIFACTS = [
    "testcase/xmind-testcases.md",
    "ui-dsl/ui-test.dsl.yaml",
    "ui-dsl/ui-test.enriched.dsl.yaml",
    "ui-dsl/selector-enrichment-report.md",
    "ui-dsl/unresolved-selectors.md",
    "playwright/tests/*.spec.ts",
    "playwright/results.json",
    "reports/ui-test-report.md",
]


def fail(message: str) -> None:
    print(f"[✗] {message}", file=sys.stderr)
    raise SystemExit(2)


def normalize_key(value: str) -> str:
    return re.sub(r"\s+", "", value.strip().lower())


def normalize_stage(stage_input: str) -> int:
    key = normalize_key(stage_input)
    if key in STAGE_ALIASES:
        return STAGE_ALIASES[key]
    fail(f"不支持的阶段: {stage_input}")


def stage_label(stage: int) -> str:
    meta = STAGES[stage]
    return f"{stage} [{meta['alias']} | {meta['name']}]"


def stage_header_line(stage: int, prefix: str = "") -> str:
    meta = STAGES[stage]
    return f"{prefix}{stage} [{meta['alias']}] {meta['name']}"


def parse_stage_list(value: str | None, resume_from: str | None, no_enrichment: bool) -> list[int]:
    if value:
        text = value.strip().lower()
        if text.startswith("only "):
            text = text.removeprefix("only ").strip()
        tokens = [part.strip() for part in re.split(r"[,，、]", text) if part.strip()]
        stages = [normalize_stage(token) for token in tokens]
        invalid = [stage for stage in stages if stage not in STAGES]
        if invalid:
            fail(f"不支持的阶段: {invalid}")
        return stages

    if resume_from is not None:
        table = RESUME_WITHOUT_ENRICHMENT if no_enrichment else RESUME_WITH_ENRICHMENT
        normalized = normalize_stage(str(resume_from))
        if normalized not in table:
            fail(f"resume-from 只支持 2, 3, 4, 5, 6 或对应 alias: {resume_from}")
        return table[normalized]

    return FULL_WITHOUT_ENRICHMENT if no_enrichment else FULL_WITH_ENRICHMENT


def resolve_selector_mode(args: argparse.Namespace, stages: list[int]) -> str:
    if args.selector_mode:
        return args.selector_mode
    if stages == FULL_WITH_ENRICHMENT and args.base_url:
        return "probe"
    return "dry"


def candidate_deliveries(project_root: Path, stage: int) -> list[str]:
    patterns = {
        2: "*/testcase/xmind-testcases.md",
        3: "*/ui-dsl/ui-test.dsl.yaml",
        4: "*/ui-dsl/ui-test.dsl.yaml",
        5: "*/playwright/tests/*.spec.ts",
        6: "*/playwright/results.json",
    }
    pattern = patterns.get(stage)
    if not pattern:
        return []
    names: set[str] = set()
    for match in project_root.glob(pattern):
        if ".codex" in match.parts:
            continue
        rel = match.relative_to(project_root)
        if rel.parts:
            names.add(rel.parts[0])
    return sorted(names)


def resolve_delivery(project_root: Path, delivery: str | None, stages: list[int]) -> tuple[str | None, list[str]]:
    notes: list[str] = []
    if delivery:
        return delivery, notes
    if stages and stages[0] == 1:
        notes.append("Stage 1 完成后才能确定 delivery-name 并生成 pipeline-run-report.md")
        return None, notes

    stages_needing_delivery = [stage for stage in stages if stage != 1]
    if not stages_needing_delivery:
        return None, notes
    first = stages_needing_delivery[0]
    candidates = candidate_deliveries(project_root, first)
    if len(candidates) == 1:
        notes.append(f"已从 Stage {first} 上游产物推断 delivery-name: {candidates[0]}")
        return candidates[0], notes
    if not candidates:
        notes.append(f"缺少 delivery-name，且无法从 Stage {first} 上游产物自动推断")
        return None, notes
    fail("存在多个候选 delivery 目录，请指定 --delivery: " + ", ".join(candidates))


def shell(path: Path | str) -> str:
    return shlex.quote(str(path))


def stage4_before_stage3(stages: list[int]) -> bool:
    return 4 in stages and 3 in stages and stages.index(4) < stages.index(3)


def should_use_enriched(args: argparse.Namespace, project_root: Path, delivery: str | None, stages: list[int]) -> bool:
    if args.use_enriched is True:
        return True
    if args.use_enriched is False:
        return False
    if not delivery or not stage4_before_stage3(stages):
        return False
    return (project_root / delivery / "ui-dsl" / "ui-test.enriched.dsl.yaml").is_file()


def playwright_config_has_base_url(project_root: Path) -> bool:
    for name in (
        "playwright.config.ts",
        "playwright.config.js",
        "playwright.config.mjs",
        "playwright.config.cjs",
    ):
        path = project_root / name
        if path.is_file() and "baseURL" in path.read_text(encoding="utf-8", errors="ignore"):
            return True
    return False


def stage_input_output(project_root: Path, delivery: str | None, stage: int, use_enriched: bool) -> tuple[str, str]:
    if stage == 1:
        return "<PRD Markdown>", "./<delivery-name>/testcase/xmind-testcases.md"
    if not delivery:
        return "<delivery-name pending>", "<delivery-name pending>"
    root = project_root / delivery
    if stage == 2:
        return str(root / "testcase" / "xmind-testcases.md"), str(root / "ui-dsl" / "ui-test.dsl.yaml")
    if stage == 4:
        return str(root / "ui-dsl" / "ui-test.dsl.yaml"), "\n".join(
            [
                str(root / "ui-dsl" / "ui-test.enriched.dsl.yaml"),
                str(root / "ui-dsl" / "selector-enrichment-report.md"),
                str(root / "ui-dsl" / "unresolved-selectors.md"),
            ]
        )
    if stage == 3:
        dsl_name = "ui-test.enriched.dsl.yaml" if use_enriched else "ui-test.dsl.yaml"
        return str(root / "ui-dsl" / dsl_name), str(root / "playwright" / "tests" / "*.spec.ts")
    if stage == 5:
        return str(root / "playwright" / "tests" / "*.spec.ts"), str(root / "playwright" / "results.json")
    if stage == 6:
        return str(root / "playwright" / "results.json"), str(root / "reports" / "ui-test-report.md")
    return "", ""


def stage_command(
    args: argparse.Namespace,
    project_root: Path,
    delivery: str | None,
    stage: int,
    use_enriched: bool,
) -> str:
    if stage == 1:
        source = args.prd if args.prd else "<PRD Markdown 内容>"
        return f"使用 $prd-to-xmind-testcases，输入: {source}"
    if not delivery:
        return "Stage 1 完成并确定 delivery-name 后生成命令"
    root = project_root / delivery
    if stage == 2:
        return (
            "python3 .codex/skills/testcase-to-playwright-dsl/scripts/convert_xmind_to_dsl.py"
            f" --input {shell(root / 'testcase' / 'xmind-testcases.md')}"
            f" --output {shell(root / 'ui-dsl' / 'ui-test.dsl.yaml')}"
        )
    if stage == 4:
        command = [
            "python3",
            ".codex/skills/dsl-selector-enrichment/scripts/enrich_selectors.py",
            "--input",
            str(root / "ui-dsl" / "ui-test.dsl.yaml"),
            "--output",
            str(root / "ui-dsl" / "ui-test.enriched.dsl.yaml"),
            "--report",
            str(root / "ui-dsl" / "selector-enrichment-report.md"),
            "--unresolved",
            str(root / "ui-dsl" / "unresolved-selectors.md"),
        ]
        if args.selector_mode == "probe":
            command.extend(["--mode", "probe", "--base-url", args.base_url or "<baseURL>"])
        return " ".join(shlex.quote(part) for part in command)
    if stage == 3:
        dsl_name = "ui-test.enriched.dsl.yaml" if use_enriched else "ui-test.dsl.yaml"
        return (
            "python3 .codex/skills/playwright-dsl-to-spec/scripts/convert_dsl_to_spec.py"
            f" --input {shell(root / 'ui-dsl' / dsl_name)}"
            f" --output-dir {shell(root / 'playwright' / 'tests')}"
        )
    if stage == 5:
        env_parts = ["PLAYWRIGHT_HTML_OPEN=never"]
        if args.base_url:
            env_parts.insert(0, f"BASE_URL={shlex.quote(args.base_url)}")
        env_parts.append("PLAYWRIGHT_JSON_OUTPUT_NAME=" + shell(root / "playwright" / "results.json"))
        return (
            " ".join(env_parts)
            + f" npx playwright test {shell(root / 'playwright' / 'tests')} --reporter=json"
        )
    if stage == 6:
        return (
            "使用 $playwright-result-report，输入: "
            f"{root / 'playwright' / 'results.json'}，输出: {root / 'reports' / 'ui-test-report.md'}"
        )
    return ""


def input_exists(project_root: Path, delivery: str | None, stage: int, use_enriched: bool) -> bool:
    if stage == 1:
        return True
    if not delivery:
        return False
    root = project_root / delivery
    if stage == 2:
        return (root / "testcase" / "xmind-testcases.md").is_file()
    if stage == 4:
        return (root / "ui-dsl" / "ui-test.dsl.yaml").is_file()
    if stage == 3:
        dsl_name = "ui-test.enriched.dsl.yaml" if use_enriched else "ui-test.dsl.yaml"
        return (root / "ui-dsl" / dsl_name).is_file()
    if stage == 5:
        return bool(list((root / "playwright" / "tests").glob("*.spec.ts")))
    if stage == 6:
        return (root / "playwright" / "results.json").is_file()
    return False


def existing_outputs(project_root: Path, delivery: str | None, stage: int, selector_mode: str = "dry") -> list[Path]:
    if not delivery:
        return []
    root = project_root / delivery
    if stage == 1:
        return [root / "testcase" / "xmind-testcases.md"]
    if stage == 2:
        return [root / "ui-dsl" / "ui-test.dsl.yaml"]
    if stage == 4:
        paths = [root / "ui-dsl" / "ui-test.enriched.dsl.yaml"]
        if selector_mode != "dry":
            paths.extend(
                [
                    root / "ui-dsl" / "selector-enrichment-report.md",
                    root / "ui-dsl" / "unresolved-selectors.md",
                ]
            )
        return paths
    if stage == 3:
        return [Path(p) for p in glob.glob(str(root / "playwright" / "tests" / "*.spec.ts"))]
    if stage == 5:
        return [root / "playwright" / "results.json"]
    if stage == 6:
        return [root / "reports" / "ui-test-report.md"]
    return []


def build_stage_rows(
    args: argparse.Namespace,
    project_root: Path,
    delivery: str | None,
    stages: list[int],
    use_enriched: bool,
    checks: list[str],
    blockers: list[str],
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    has_base_url_or_config = bool(args.base_url) or playwright_config_has_base_url(project_root)

    for stage in stages:
        input_text, output_text = stage_input_output(project_root, delivery, stage, use_enriched)
        command = stage_command(args, project_root, delivery, stage, use_enriched)
        stage_blockers: list[str] = []

        if stage == 1 and not args.prd and not args.prd_content:
            stage_blockers.append("Stage 1 缺少 PRD 文件路径或 PRD Markdown 内容")
        if stage != 1 and not delivery:
            stage_blockers.append("缺少 delivery-name")
        if not input_exists(project_root, delivery, stage, use_enriched):
            stage_blockers.append(f"Stage {stage} 上游产物不存在")
        if stage == 4 and args.selector_mode == "probe" and not args.base_url:
            stage_blockers.append("Stage 4 probe 缺少 baseURL")
        if stage == 5 and not has_base_url_or_config:
            stage_blockers.append("Stage 5 缺少 baseURL，且未发现现有 Playwright baseURL 配置")

        outputs = [
            path
            for path in existing_outputs(project_root, delivery, stage, args.selector_mode)
            if path.exists()
        ]
        if outputs and not args.overwrite:
            listed = ", ".join(str(path) for path in outputs)
            stage_blockers.append(f"Stage {stage} 输出已存在且未允许 overwrite: {listed}")

        status = "blocked" if stage_blockers else "ready"
        checks.extend([f"Stage {stage}: {item}" for item in stage_blockers])
        blockers.extend([f"Stage {stage}: {item}" for item in stage_blockers])
        rows.append(
            {
                "stage": str(stage),
                "alias": STAGES[stage]["alias"],
                "name": STAGES[stage]["name"],
                "status": status,
                "input": input_text,
                "output": output_text,
                "command": command,
            }
        )
    return rows


def artifact_index(project_root: Path, delivery: str | None) -> list[tuple[str, str]]:
    if not delivery:
        return [(artifact, "pending") for artifact in ARTIFACTS]
    root = project_root / delivery
    result: list[tuple[str, str]] = []
    for artifact in ARTIFACTS:
        matches = list(root.glob(artifact))
        result.append((artifact, "exists" if matches else "expected"))
    return result


def next_steps(
    args: argparse.Namespace,
    project_root: Path,
    delivery: str | None,
    stages: list[int],
    use_enriched: bool,
    blockers: list[str],
) -> list[str]:
    suggestions: list[str] = []
    if blockers:
        suggestions.extend(blockers)
    if 5 in stages and not args.base_url and not playwright_config_has_base_url(project_root):
        suggestions.append("缺少 baseURL，无法执行 Stage 5")
    if delivery:
        root = project_root / delivery
        dsl = root / "ui-dsl" / "ui-test.dsl.yaml"
        if dsl.is_file():
            text = dsl.read_text(encoding="utf-8", errors="ignore")
            if "status: \"todo\"" in text or "status: todo" in text:
                suggestions.append("存在 todo selector，建议执行 Stage 4 probe")
        if list((root / "playwright" / "tests").glob("*.spec.ts")):
            suggestions.append("已生成 spec，可执行 Stage 5")
        if (root / "playwright" / "results.json").is_file():
            suggestions.append("Playwright results.json 存在，可执行 playwright-result-report")
        if (root / "reports" / "ui-test-report.md").is_file():
            suggestions.append("测试报告已存在，可查看 reports/ui-test-report.md")
    if use_enriched:
        suggestions.append("Stage 3 将使用 enriched DSL")
    if not suggestions:
        suggestions.append("当前调度计划无阻断项，可按建议命令继续执行")
    return list(dict.fromkeys(suggestions))


def md_cell(value: str) -> str:
    return value.replace("\n", "<br>").replace("|", "\\|")


def build_report(
    args: argparse.Namespace,
    project_root: Path,
    delivery: str,
    stages: list[int],
    use_enriched: bool,
    rows: list[dict[str, str]],
    checks: list[str],
    blockers: list[str],
) -> str:
    has_codex = (project_root / ".codex").is_dir()
    output_exists = [
        f"Stage {row['stage']}: {path}"
        for row in rows
        for path in existing_outputs(project_root, delivery, int(row["stage"]), args.selector_mode)
        if path.exists()
    ]
    commands = [row["command"] for row in rows]
    suggestions = next_steps(args, project_root, delivery, stages, use_enriched, blockers)

    lines = [
        "# AI Test Pipeline Report",
        "",
        "## 基本信息",
        "",
        f"- 项目根目录: `{project_root}`",
        f"- delivery-name: `{delivery}`",
        f"- 执行阶段: `{' -> '.join(stage_label(stage) for stage in stages)}`",
        f"- selector mode: `{args.selector_mode}`",
        f"- 是否使用 enriched DSL: `{'是' if use_enriched else '否'}`",
        f"- baseURL 是否提供: `{'是' if args.base_url else '否'}`",
        f"- 是否 overwrite: `{'是' if args.overwrite else '否'}`",
        "",
        "## 阶段计划",
        "",
        "| Stage | Alias | 中文 | 状态 | 输入 | 输出 |",
        "|---|---|---|---|---|---|",
    ]
    for row in rows:
        lines.append(
            "| {stage} | {alias} | {name} | {status} | {input} | {output} |".format(
                stage=row["stage"],
                alias=md_cell(row["alias"]),
                name=md_cell(row["name"]),
                status=row["status"],
                input=md_cell(row["input"]),
                output=md_cell(row["output"]),
            )
        )
    lines.extend(
        [
            "",
            "## 前置检查结果",
            "",
            f"- 项目根目录是否包含 .codex: {'是' if has_codex else '否'}",
            f"- delivery-name 是否确定: 是",
            f"- 上游产物是否存在: {'存在阻断项，详见下方' if blockers else '是'}",
            f"- 输出产物是否已存在: {'; '.join(output_exists) if output_exists else '否'}",
            f"- 是否需要 overwrite: {'是' if output_exists and not args.overwrite else '否'}",
            f"- Stage 5 是否具备 baseURL 或依赖现有 Playwright 配置: {'是' if args.base_url or playwright_config_has_base_url(project_root) else '否'}",
        ]
    )
    if checks:
        lines.append("")
        lines.extend(f"- {check}" for check in checks)

    lines.extend(["", "## 当前阻断项", ""])
    if blockers:
        lines.extend(f"- {item}" for item in blockers)
    else:
        lines.append("- 无")

    lines.extend(["", "## 调度命令", ""])
    lines.extend(f"{index}. `{command}`" for index, command in enumerate(commands, start=1))

    lines.extend(["", "## 产物索引", ""])
    for artifact, status in artifact_index(project_root, delivery):
        lines.append(f"- `{artifact}`: {status}")

    lines.extend(["", "## 下一步建议", ""])
    lines.extend(f"- {item}" for item in suggestions)
    lines.append("")
    return "\n".join(lines)


def report_path_for(args: argparse.Namespace, project_root: Path, delivery: str) -> Path:
    if args.report_path:
        path = Path(args.report_path)
        return path if path.is_absolute() else project_root / path
    return project_root / delivery / "reports" / "pipeline-run-report.md"


def write_report(
    args: argparse.Namespace,
    project_root: Path,
    delivery: str | None,
    stages: list[int],
    use_enriched: bool,
    rows: list[dict[str, str]],
    checks: list[str],
    blockers: list[str],
) -> Path | None:
    if not args.write_report:
        return None
    if not delivery:
        print("Stage 1 完成后才能确定 delivery-name 并生成 pipeline-run-report.md")
        return None
    path = report_path_for(args, project_root, delivery)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        build_report(args, project_root, delivery, stages, use_enriched, rows, checks, blockers),
        encoding="utf-8",
    )
    return path


def print_header(project_root: Path, delivery: str | None, stages: list[int]) -> None:
    print("====== AI TEST PIPELINE ======")
    print(f"Project: {project_root}")
    print(f"Delivery: {delivery or 'pending'}")
    print("Stages:")
    for index, stage in enumerate(stages):
        print(stage_header_line(stage, "" if index == 0 else "→ "))
    print("Mode: plan")
    print("==============================")
    print()


def print_dispatch_plan(rows: list[dict[str, str]], checks: list[str]) -> None:
    for row in rows:
        print(f"Stage {row['stage']} [{row['alias']} | {row['name']}] [{row['status']}] -> {row['command']}")
        print(f"  Input: {row['input']}")
        print(f"  Output: {row['output']}")
    if checks:
        print()
        print("阻断/检查项:")
        for check in checks:
            print(f"  - {check}")


def main() -> None:
    parser = argparse.ArgumentParser(description="校验并输出 AI 测试流水线调度计划。")
    parser.add_argument("--project-root", default=os.getcwd())
    parser.add_argument("--delivery")
    parser.add_argument("--stages", help='示例: "1,2,4,3,5,6", "prd,dsl,enrich,spec,run,report", "only report"')
    parser.add_argument("--resume-from")
    parser.add_argument("--prd", help="Stage 1 使用的 PRD Markdown 文件路径")
    parser.add_argument("--prd-content", action="store_true", help="Stage 1 使用对话中的 PRD Markdown 内容")
    parser.add_argument("--no-enrichment", action="store_true", help="从默认或恢复流程中移除 Stage 4")
    parser.add_argument("--selector-mode", choices=["dry", "probe"], help="默认自动判断：完整链路且提供 baseURL 时为 probe，否则为 dry")
    enriched_group = parser.add_mutually_exclusive_group()
    enriched_group.add_argument(
        "--use-enriched",
        dest="use_enriched",
        action="store_true",
        help="Stage 3 使用 ui-test.enriched.dsl.yaml",
    )
    enriched_group.add_argument(
        "--no-use-enriched",
        dest="use_enriched",
        action="store_false",
        help="Stage 3 不使用 ui-test.enriched.dsl.yaml",
    )
    parser.set_defaults(use_enriched=None)
    parser.add_argument("--base-url")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--write-report", action="store_true", help="生成 pipeline-run-report.md")
    parser.add_argument("--report-path", help="自定义 pipeline-run-report.md 输出路径")
    args = parser.parse_args()

    project_root = Path(args.project_root).resolve()
    if not (project_root / ".codex").is_dir():
        fail(f"项目根目录必须包含 .codex: {project_root}")

    stages = parse_stage_list(args.stages, args.resume_from, args.no_enrichment)
    args.selector_mode = resolve_selector_mode(args, stages)
    delivery, resolve_notes = resolve_delivery(project_root, args.delivery, stages)
    use_enriched = should_use_enriched(args, project_root, delivery, stages)
    checks = resolve_notes[:]
    blockers: list[str] = []
    rows = build_stage_rows(args, project_root, delivery, stages, use_enriched, checks, blockers)

    print_header(project_root, delivery, stages)
    print_dispatch_plan(rows, checks)
    report_path = write_report(args, project_root, delivery, stages, use_enriched, rows, checks, blockers)

    print()
    print("[✓] Pipeline 调度计划生成完成")
    if report_path:
        print(f"[✓] Pipeline 报告已生成: {report_path}")


if __name__ == "__main__":
    main()
