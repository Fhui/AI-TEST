from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "skills/playwright-dsl-to-spec/scripts/convert_dsl_to_spec.py"
spec = spec_from_file_location("convert_dsl_to_spec", SPEC)
convert = module_from_spec(spec)
sys.modules[spec.name] = convert
spec.loader.exec_module(convert)


def squote(code):
    return code.replace('"', "'")


def test_role_label_and_placeholder_selectors_render_playwright_apis():
    assert squote(convert.locator_expression('role=button[name="登录"]')) == "page.getByRole('button', { name: '登录' })"
    assert squote(convert.locator_expression("label=手机号")) == "page.getByLabel('手机号')"
    assert squote(convert.locator_expression("placeholder=请输入密码")) == "page.getByPlaceholder('请输入密码')"


def test_text_and_fallback_selectors_render_playwright_apis():
    assert squote(convert.locator_expression("text=登录成功")) == "page.getByText('登录成功', { exact: true })"
    assert "page.locator(" in convert.locator_expression('[data-testid="login"]')


def test_todo_selector_generates_throwing_step():
    selectors = {"login": {"selector": 'role=button[name="登录"]', "status": "todo"}}
    step = {"id": "s1", "action": "click", "target": "login", "source_ts": "点击登录按钮"}

    code = "\n".join(convert.operation_lines(step, selectors, {}))

    assert "throw new Error" in code
