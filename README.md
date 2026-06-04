# AI Test Skills

这个仓库用于沉淀测试工程相关的 Codex skills 与 MCP 服务，覆盖测试知识检索、PRD 分析、测试用例建模、UI DSL 生成、selector 补全校准、Playwright spec 转换、执行与报告的端到端测试资产生产流程。

## What Is In This Repo

```text
.
├── skills/                  # 可提交、可复用的 skill 源文件
├── mcp/                     # 测试工程 MCP 服务
│   └── test-knowledge-mcp/  # 测试知识库扫描、索引、校验与召回
├── tests/                   # 自动化测试
├── AGENTS.md                # Codex 项目约束
└── .gitignore               # 忽略本地工具状态与生成产物
```

本地 `.codex/`、`.claude/`、`scripts/` 属于工具运行或本地维护状态，不直接提交。需要提交 skill 变更时，先把 `.codex/skills/` 同步到根目录 `skills/`，只提交同步后的 `skills/` 内容。

## Skills

| Skill | Purpose |
| --- | --- |
| `ai-test-runner` | 调度完整 AI 测试流水线，按需串联 PRD、DSL、selector、spec、执行与报告阶段。 |
| `test-knowledge-retrieval` | 通过 `test-knowledge-mcp` 检索历史 PRD、测试用例、缺陷、接口和依赖资料，生成结构化上下文包。 |
| `prd-to-xmind-testcases` | 基于 PRD 和可选知识上下文，按复杂度选择分析深度并生成 XMind 风格测试用例树。 |
| `testcase-to-playwright-dsl` | 将 XMind 风格 Markdown 测试用例转换为 UI DSL YAML。 |
| `dsl-selector-enrichment` | 对 UI DSL 中的 todo selector 做候选生成与受控 probe 校准。 |
| `playwright-dsl-to-spec` | 将 UI DSL 转换为 Playwright spec。 |
| `playwright-cli` | 使用 Playwright CLI 做浏览器检查、调试和辅助自动化。 |
| `playwright-result-report` | 从 Playwright 执行产物生成 Markdown 测试报告与 artifacts 索引。 |

## Main Workflow

```text
PRD Markdown
  -> test-knowledge-retrieval (optional)
  -> analysis/context-package.json
  -> prd-to-xmind-testcases
  -> testcase/xmind-testcases.md
  -> testcase-to-playwright-dsl
  -> ui-dsl/ui-test.dsl.yaml
  -> dsl-selector-enrichment
  -> ui-dsl/ui-test.enriched.dsl.yaml
  -> playwright-dsl-to-spec
  -> Playwright spec
  -> playwright-cli
  -> playwright/results.json
  -> playwright-result-report
  -> reports/ui-test-report.md
```

`test-knowledge-mcp` 为知识检索阶段提供测试知识库扫描、分片索引、metadata 提取、规则召回、资产枚举和知识库校验能力。它只读取 Markdown 等 AI source；配套 `.xmind` 仅作为预览资产和配对信息，不读取、不解析、不修改。

`ai-test-runner` 作为流水线调度器使用，统一阶段定义如下：

| Stage | Alias | Output |
| --- | --- | --- |
| 1 | `prd` | `testcase/xmind-testcases.md` |
| 2 | `dsl` | `ui-dsl/ui-test.dsl.yaml` |
| 4 | `enrich` | `ui-dsl/ui-test.enriched.dsl.yaml`、补全报告、未解决清单 |
| 3 | `spec` | `playwright/tests/*.spec.ts` |
| 5 | `run` | `playwright/results.json` 与 Playwright 执行产物 |
| 6 | `report` | `reports/ui-test-report.md`、`reports/artifacts-index.md` |

默认完整顺序为：

```text
1 -> 2 -> 4 -> 3 -> 5 -> 6
```

`dsl-selector-enrichment` 支持两种模式：

- `dry`：默认模式，不打开浏览器、不执行步骤，只生成 selector 候选、补全报告和未解决清单。
- `probe`：受控探测模式。支持 `goto`、`wait_for` 和安全边界内的 `click` 状态推进；每个 flow 只探测本 flow steps 中用到的 todo target selector。支持 seed selector、runtime-confirmed click、reuse session、移动端 H5 参数、定位权限和 locator count 校准。

`playwright-result-report` 只读取已有 Playwright 产物，不执行测试、不生成 spec、不修改 DSL。报告会把失败映射回 DSL flow、step、`source_ts`、selector、截图、trace 和 video，并输出失败分类与自动建议。

## Sync Skills Before Commit

编辑本地 `.codex/skills/` 后，提交前把它镜像同步到 `skills/`。如果本地维护脚本存在，可以运行：

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

`scripts/` 是本地忽略目录，不随仓库提交。如果没有本地脚本，也可以用等价的 `rsync` 命令完成同步。

## Git Ignore Policy

以下内容默认不提交：

- `.codex/`
- `.claude/`
- `.playwright-cli/`
- `scripts/`
- 生成交付目录，例如 `password-login-flow/`
- 本地 PRD 草稿文件

可提交内容主要包括：

- `skills/`
- `mcp/`
- `tests/`
- `README.md`
- `AGENTS.md`

## Notes

- 不要把执行产物写入 `.codex/` 或 `.codex/skills/`。
- 生成交付物应写在项目根目录下，与 `.codex` 同级。
- 不要在 selector enrichment 阶段生成 `spec.ts`，也不要运行 `npx playwright test`。
- probe 模式用于 selector 探测，不用于验证业务结果。
- Stage 5 运行 Playwright 或 Stage 4 probe 模式需要明确 `baseURL`，不要猜测环境地址。
- Stage 6 报告阶段依赖 `playwright/results.json`；缺少 JSON 时只能生成降级报告。
