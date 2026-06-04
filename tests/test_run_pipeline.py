from argparse import Namespace
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / ".codex/skills/ai-test-runner/scripts/run_pipeline.py"
spec = spec_from_file_location("run_pipeline", SPEC)
pipeline = module_from_spec(spec)
sys.modules[spec.name] = pipeline
spec.loader.exec_module(pipeline)


def args(**overrides):
    defaults = dict(prd=None, prd_content=False, selector_mode="dry", base_url=None, use_enriched=False, overwrite=True)
    return Namespace(**(defaults | overrides))


def test_stage_5_without_base_url_is_blocked(tmp_path):
    with pytest.raises(SystemExit) as error, pytest.MonkeyPatch.context() as patch:
        patch.setattr(pipeline, "fail", lambda message: (_ for _ in ()).throw(SystemExit(message)))
        pipeline.check_prerequisites(args(), tmp_path, "demo", [5])

    assert "baseURL" in str(error.value)


def test_stage_3_without_dsl_file_reports_missing_ui_dsl(tmp_path):
    with pytest.raises(SystemExit) as error, pytest.MonkeyPatch.context() as patch:
        patch.setattr(pipeline, "fail", lambda message: (_ for _ in ()).throw(SystemExit(message)))
        pipeline.check_prerequisites(args(base_url="http://localhost:3000"), tmp_path, "demo", [3])

    assert "缺少" in str(error.value)
    assert "ui-test.dsl.yaml" in str(error.value)


def test_resume_from_3_runs_only_stage_3_and_5():
    assert pipeline.parse_stage_list(None, 3, False) == [3, 5]
