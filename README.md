# AI Test Skills

这个仓库用于沉淀测试工程相关的 Codex skills，覆盖从 PRD 分析、测试用例建模、UI DSL 生成、Playwright spec 转换，到 selector 补全校准的端到端测试资产生产流程。

## What Is In This Repo

```text
.
├── skills/                  # 可提交、可复用的 skill 源文件
├── scripts/                 # 仓库维护脚本
│   └── sync-skills.sh       # 将 .codex/skills 同步到 skills/
├── AGENTS.md                # Codex 项目约束
└── .gitignore               # 忽略本地工具状态与生成产物
```

本地 `.codex/` 和 `.claude/` 属于工具运行状态，不直接提交。需要提交 skill 变更时，先把 `.codex/skills/` 同步到根目录 `skills/`。

## Skills

| Skill | Purpose |
| --- | --- |
| `prd-to-xmind-testcases` | 将 Markdown PRD 解析为 XMind 风格测试用例树。 |
| `testcase-to-playwright-dsl` | 将 XMind 风格 Markdown 测试用例转换为 UI DSL YAML。 |
| `dsl-selector-enrichment` | 对 UI DSL 中的 todo selector 做候选生成与受控 probe 校准。 |
| `playwright-dsl-to-spec` | 将 UI DSL 转换为 Playwright spec。 |
| `playwright-cli` | 使用 Playwright CLI 做浏览器检查、调试和辅助自动化。 |

## Main Workflow

```text
PRD Markdown
  -> prd-to-xmind-testcases
  -> testcase/xmind-testcases.md
  -> testcase-to-playwright-dsl
  -> ui-dsl/ui-test.dsl.yaml
  -> dsl-selector-enrichment
  -> ui-dsl/ui-test.enriched.dsl.yaml
  -> playwright-dsl-to-spec
  -> Playwright spec
```

`dsl-selector-enrichment` 支持两种模式：

- `dry`：默认模式，不打开浏览器、不执行步骤，只生成 selector 候选、补全报告和未解决清单。
- `probe`：受控探测模式。probe v1 只允许执行 `goto` / `wait_for`，并且每个 flow 只探测本 flow steps 中用到的 todo target selector。

## Sync Skills Before Commit

编辑本地 `.codex/skills/` 后，提交前运行：

```bash
scripts/sync-skills.sh
```

脚本会把：

```text
.codex/skills/ -> skills/
```

做镜像同步，并排除缓存文件：

- `__pycache__/`
- `*.pyc`
- `.DS_Store`

## Git Ignore Policy

以下内容默认不提交：

- `.codex/`
- `.claude/`
- `.playwright-cli/`
- 生成交付目录，例如 `login-flow/`
- 本地 PRD 草稿文件

可提交内容主要包括：

- `skills/`
- `scripts/`
- `README.md`
- `AGENTS.md`

## Notes

- 不要把执行产物写入 `.codex/` 或 `.codex/skills/`。
- 生成交付物应写在项目根目录下，与 `.codex` 同级。
- 不要在 selector enrichment 阶段生成 `spec.ts`，也不要运行 `npx playwright test`。
- probe 模式用于 selector 探测，不用于验证业务结果。
