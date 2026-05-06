---
name: playwright-cli
description: Drive browser sessions with the `playwright-cli` command for UI inspection, browser automation, page interaction, debugging, storage/session management, request mocking, tracing, video recording, and generating or running Playwright-oriented workflows. Use when the user asks Codex to open a page, navigate, click/type/select/upload/check elements, inspect snapshots or element attributes, manage tabs/cookies/localStorage/sessionStorage, mock network requests, capture traces/videos/screenshots/PDFs, run Playwright snippets, or debug Playwright tests via the CLI.
---

# Playwright CLI

## Scope

Use this skill to operate `playwright-cli` from the terminal.

This skill may:

- Open, attach to, inspect, and close browser sessions
- Navigate pages and interact with elements
- Use snapshots and refs to target elements
- Inspect attributes, console logs, network activity, cookies, localStorage, and sessionStorage
- Mock requests, run code against a Playwright page, capture traces, record videos, and generate test ideas

This skill does not require generating `.spec.ts` files unless the user explicitly asks for test code.

When running Playwright tests for this AI test pipeline, always use the fixed JSON reporter contract:

```bash
PLAYWRIGHT_HTML_OPEN=never PLAYWRIGHT_JSON_OUTPUT_NAME=./<delivery-name>/playwright/results.json npx playwright test ./<delivery-name>/playwright/tests --reporter=json
```

If a base URL is required, prepend `BASE_URL=<baseURL>` and keep the same `PLAYWRIGHT_JSON_OUTPUT_NAME` path.

## Command Selection

Prefer `playwright-cli` when available.
If it is not installed globally, try the local command:

```bash
npx --no-install playwright-cli --version
```

When local `npx --no-install playwright-cli` works, use `npx playwright-cli` for subsequent commands.
If neither command is available, tell the user the CLI is missing and suggest installing the project or global package.

Do not install dependencies unless the user asks or the task cannot proceed without installation.

## Basic Workflow

1. Open or attach to a browser session.
2. Navigate to the target page.
3. Take a snapshot and use element refs from it.
4. Interact with refs, CSS selectors, or Playwright locators.
5. Use assertions through snapshots, `eval`, console, network, screenshots, traces, or videos as needed.
6. Close the session when the task is complete, unless the user wants it left open.

Common commands:

```bash
playwright-cli open
playwright-cli open https://example.com/
playwright-cli goto https://example.com/
playwright-cli snapshot
playwright-cli click e3
playwright-cli fill e5 "user@example.com"
playwright-cli fill e6 "password" --submit
playwright-cli type "search query"
playwright-cli press Enter
playwright-cli select e9 "option-value"
playwright-cli check e12
playwright-cli uncheck e12
playwright-cli upload ./document.pdf
playwright-cli eval "document.title"
playwright-cli close
```

## Targeting Elements

Default to snapshot refs:

```bash
playwright-cli snapshot
playwright-cli click e15
```

Use CSS selectors or Playwright locators when refs are unstable or when the user asks for durable selectors:

```bash
playwright-cli click "#main > button.submit"
playwright-cli click "getByRole('button', { name: 'Submit' })"
playwright-cli click "getByTestId('submit-button')"
```

To inspect attributes that are not visible in the snapshot:

```bash
playwright-cli eval "el => el.id" e5
playwright-cli eval "el => el.className" e5
playwright-cli eval "el => el.getAttribute('data-testid')" e5
```

For more selector and attribute guidance, read [references/element-attributes.md](references/element-attributes.md).

## Sessions And Tabs

Use named sessions for multi-step work or when multiple browsers are needed:

```bash
playwright-cli -s=mysession open https://example.com --persistent
playwright-cli -s=mysession click e6
playwright-cli -s=mysession close
```

Useful session and tab commands:

```bash
playwright-cli list
playwright-cli close-all
playwright-cli kill-all
playwright-cli tab-list
playwright-cli tab-new https://example.com/other
playwright-cli tab-select 0
playwright-cli tab-close
```

For persistent profiles, attach modes, and cleanup rules, read [references/session-management.md](references/session-management.md).

## Storage

Use storage commands when login state, cookies, or local/session storage matter:

```bash
playwright-cli state-save auth.json
playwright-cli state-load auth.json
playwright-cli cookie-list
playwright-cli cookie-get session_id
playwright-cli cookie-set session_id abc123 --domain=example.com --httpOnly --secure
playwright-cli localstorage-list
playwright-cli localstorage-set theme dark
playwright-cli sessionstorage-list
```

For auth reuse and storage-state patterns, read [references/storage-state.md](references/storage-state.md).

## Debugging And Evidence

Use the lightest evidence that answers the question:

```bash
playwright-cli console
playwright-cli console warning
playwright-cli network
playwright-cli screenshot --filename=page.png
playwright-cli pdf --filename=page.pdf
playwright-cli tracing-start
playwright-cli tracing-stop
playwright-cli video-start video.webm
playwright-cli video-stop
```

Read only the relevant reference:

- Playwright test debugging: [references/playwright-tests.md](references/playwright-tests.md)
- Running page code: [references/running-code.md](references/running-code.md)
- Request mocking: [references/request-mocking.md](references/request-mocking.md)
- Test generation: [references/test-generation.md](references/test-generation.md)
- Tracing: [references/tracing.md](references/tracing.md)
- Video recording: [references/video-recording.md](references/video-recording.md)

## Raw Output

Use `--raw` when command output must be piped, diffed, or consumed by another command:

```bash
playwright-cli --raw eval "JSON.stringify(performance.timing)"
playwright-cli --raw snapshot > before.yml
playwright-cli click e5
playwright-cli --raw snapshot > after.yml
```

## Safety And Fit

- Do not run destructive browser actions such as deleting production data unless the user clearly requests it.
- Prefer refs from fresh snapshots over guessed selectors.
- Keep generated evidence files inside the current project or another user-approved path.
- If the task is simply to inspect a local web target in the Codex app browser and the user names the Browser Use plugin, prefer that plugin. Use this skill when the user explicitly asks for `playwright-cli` or CLI-driven Playwright work.
