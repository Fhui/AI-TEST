# Running Playwright Tests

To run Playwright tests for the AI test pipeline, always enable the JSON reporter and write the fixed result file used by `playwright-result-report`: `./<delivery-name>/playwright/results.json`. To avoid opening the interactive html report, use `PLAYWRIGHT_HTML_OPEN=never`.

```bash
# Run all tests
PLAYWRIGHT_HTML_OPEN=never PLAYWRIGHT_JSON_OUTPUT_NAME=./<delivery-name>/playwright/results.json npx playwright test ./<delivery-name>/playwright/tests --reporter=json

# Run all tests through a custom npm script
PLAYWRIGHT_HTML_OPEN=never PLAYWRIGHT_JSON_OUTPUT_NAME=./<delivery-name>/playwright/results.json npm run special-test-command -- --reporter=json
```

When a base URL is required, keep the same fixed JSON reporter contract:

```bash
BASE_URL=<baseURL> PLAYWRIGHT_HTML_OPEN=never PLAYWRIGHT_JSON_OUTPUT_NAME=./<delivery-name>/playwright/results.json npx playwright test ./<delivery-name>/playwright/tests --reporter=json
```

# Debugging Playwright Tests

To debug a failing Playwright test, run it with `--debug=cli` option. This command will pause the test at the start and print the debugging instructions.

**IMPORTANT**: run the command in the background and check the output until "Debugging Instructions" is printed.

Once instructions containing a session name are printed, use `playwright-cli` to attach the session and explore the page.

```bash
# Run the test
PLAYWRIGHT_HTML_OPEN=never npx playwright test --debug=cli
# ...
# ... debugging instructions for "tw-abcdef" session ...
# ...

# Attach to the test
playwright-cli attach tw-abcdef
```

Keep the test running in the background while you explore and look for a fix.
The test is paused at the start, so you should step over or pause at a particular location
where the problem is most likely to be.

Every action you perform with `playwright-cli` generates corresponding Playwright TypeScript code.
This code appears in the output and can be copied directly into the test. Most of the time, a specific locator or an expectation should be updated, but it could also be a bug in the app. Use your judgement.

After fixing the test, stop the background test run. Rerun to check that test passes.
