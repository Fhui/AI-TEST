from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "skills/dsl-selector-enrichment/scripts/enrich_selectors.py"
spec = spec_from_file_location("enrich_selectors", SPEC)
enrich = module_from_spec(spec)
sys.modules[spec.name] = enrich
spec.loader.exec_module(enrich)


def candidates_for(source_ts, key):
    entry = {"selector": f'[data-testid="{key}"]', "status": "todo", "source": source_ts}
    _, _, candidates, _ = enrich.generate_candidates(key, entry, {"selectors": {key: entry}})
    return {candidate.selector for candidate in candidates}


def test_login_button_source_generates_role_and_text_candidates():
    candidates = candidates_for("点击登录按钮", "登录")

    assert 'role=button[name="登录"]' in candidates
    assert "text=登录" in candidates


def test_phone_input_source_generates_label_and_placeholder_candidates():
    candidates = candidates_for("输入手机号", "手机号")

    assert "label=手机号" in candidates
    assert "placeholder=手机号" in candidates


def test_agreement_checkbox_source_generates_checkbox_candidate():
    candidates = candidates_for("勾选同意协议", "同意")

    assert 'role=checkbox[name="同意"]' in candidates
