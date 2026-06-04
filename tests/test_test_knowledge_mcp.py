from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "mcp/test-knowledge-mcp/server.py"
spec = spec_from_file_location("test_knowledge_mcp_server", SPEC)
server = module_from_spec(spec)
sys.modules[spec.name] = server
spec.loader.exec_module(server)

from test_knowledge_mcp.services import index_service, search_service


def test_server_import_smoke_and_tool_wrappers_are_callable():
    assert server.mcp.name == "test-knowledge-mcp"
    for tool_name in [
        "refresh_knowledge_index",
        "scan_knowledge_base",
        "extract_metadata",
        "generate_context_index_draft",
        "search_context",
        "read_context_documents",
        "list_module_assets",
        "validate_knowledge_base",
        "validate_testcase_markdown",
    ]:
        assert callable(getattr(server, tool_name))


@pytest.fixture()
def knowledge_base(tmp_path, monkeypatch):
    root = tmp_path / "knowledge-base"
    module = root / "systems" / "qa-hub" / "order"
    for directory in ["prd", "testcase", "bug", "api", "release"]:
        (module / directory).mkdir(parents=True, exist_ok=True)
    shared = root / "shared" / "payment"
    for directory in ["api", "testcase"]:
        (shared / directory).mkdir(parents=True, exist_ok=True)
    flat_module = root / "watchPic" / "V5.6.0(小程序自助裁剪)"
    for directory in ["prd", "testcase"]:
        (flat_module / directory).mkdir(parents=True, exist_ok=True)

    (root / "systems" / "qa-hub" / "module-map.md").write_text(
        "# qa-hub 模块地图\n\n- order: 订单模块\n",
        encoding="utf-8",
    )
    (module / "upstream-downstream.md").write_text(
        "# order 上下游\n\n上游依赖: product\n下游依赖: payment, inventory\n",
        encoding="utf-8",
    )
    (module / "prd" / "order-v1.2.md").write_text(
        "# 订单 v1.2 PRD\n\n业务对象: Order, Coupon\n接口: POST /order/create\n状态: CREATED, PAID\n角色: user, admin\n关键词: 下单 支付 优惠券\n",
        encoding="utf-8",
    )
    (module / "testcase" / "order-v1.2.md").write_text(
        "# 订单 v1.2 测试用例\n\n业务对象: Order, Coupon\n接口: /order/create\n状态: CREATED, PAID\n\n## 下单流程\n### TC001 正常下单\n- steps:\n  - step: 提交订单\n    expected: CREATED\n",
        encoding="utf-8",
    )
    (module / "testcase" / "order-v1.2.xmind").write_bytes(b"preview only")
    (module / "testcase" / "order-v1.3.md").write_text(
        "# 订单 v1.3 测试用例\n\n### TC001 仅 Markdown\n",
        encoding="utf-8",
    )
    (module / "testcase" / "order-v1.4.xmind").write_bytes(b"orphan xmind")
    (module / "bug" / "coupon-payment-duplicate-bug.md").write_text(
        "# 优惠券支付重复扣减缺陷\n\n风险: 支付重复、库存回滚失败\n业务对象: Coupon, Order\n",
        encoding="utf-8",
    )
    (module / "api" / "order-api.md").write_text(
        "# 订单 API\n\nPOST /order/create\nGET /order/detail\n",
        encoding="utf-8",
    )
    (module / "release" / "release-v1.2.md").write_text(
        "# v1.2 发布说明\n\n包含下单、支付、优惠券能力。\n",
        encoding="utf-8",
    )
    (shared / "api" / "payment-common-rules.md").write_text(
        "# 支付共享规则\n\n关键词: 支付 优惠券\n风险: 重复支付、幂等失败\n",
        encoding="utf-8",
    )
    (shared / "testcase" / "payment-shared.md").write_text(
        "# 支付共享测试用例\n\n### TC001 共享规则仅 Markdown\n",
        encoding="utf-8",
    )
    (shared / "testcase" / "payment-orphan.xmind").write_bytes(b"shared orphan xmind")
    (flat_module / "prd" / "自助裁剪V5.6.0.md").write_text(
        "# 自助裁剪 V5.6.0 PRD\n\n业务对象: PhotoCrop\n接口: /crop/create\n关键词: 自助裁剪\n",
        encoding="utf-8",
    )
    (flat_module / "testcase" / "自助裁剪V5.6.0.md").write_text(
        "# 自助裁剪 V5.6.0 测试用例\n\n### TC001 正常裁剪\n- steps:\n  - step: 选择尺寸\n    expected: 裁剪成功\n",
        encoding="utf-8",
    )
    (flat_module / "testcase" / "自助裁剪V5.6.0.xmind").write_bytes(b"preview only")

    monkeypatch.setenv("TEST_KNOWLEDGE_ROOTS", str(root))
    monkeypatch.setattr(server, "DEFAULT_KNOWLEDGE_ROOT", root)
    return root


def test_scan_knowledge_base_counts_documents_and_types(knowledge_base):
    result = server.scan_knowledge_base(str(knowledge_base))

    assert result["systems"] == ["qa-hub", "shared", "watchPic"]
    assert result["modules"] == ["qa-hub/order", "shared/payment", "watchPic/V5.6.0(小程序自助裁剪)"]
    assert result["doc_type_summary"]["testcase"] == 4
    assert result["doc_type_summary"]["prd"] == 2
    assert result["documents_count"] >= 11
    assert result["ai_source_count"] >= 11
    assert result["preview_asset_count"] == 4


def test_make_module_key_preserves_chinese_and_normalizes_symbols():
    assert server._make_module_key("watchPic", "V5.6.0(小程序自助裁剪)") == "watchPic__V5.6.0_小程序自助裁剪"
    assert server._safe_path_segment("V5.6.0(小程序自助裁剪)") == "V5.6.0_小程序自助裁剪"


def test_discover_modules_supports_flat_and_standard_layouts_and_ignores_index(knowledge_base):
    ignored = knowledge_base / ".knowledge-index" / "modules" / "fake"
    ignored.mkdir(parents=True)
    (ignored / "prd").mkdir()

    modules = server._discover_modules(knowledge_base)
    module_pairs = {(item["system"], item["module"]) for item in modules}

    assert ("qa-hub", "order") in module_pairs
    assert ("watchPic", "V5.6.0(小程序自助裁剪)") in module_pairs
    assert not any(item["system"] == ".knowledge-index" for item in modules)


def test_refresh_knowledge_index_writes_sharded_indexes_and_skips_unchanged_modules(knowledge_base):
    first = server.refresh_knowledge_index(str(knowledge_base), force=False)

    root_index = knowledge_base / ".knowledge-index/root-index.json"
    root_checksum = knowledge_base / ".knowledge-index/root-checksum.json"
    root_report = knowledge_base / ".knowledge-index/scan-report.json"
    module_key = server._make_module_key("watchPic", "V5.6.0(小程序自助裁剪)")
    module_index = knowledge_base / ".knowledge-index/watchPic/V5.6.0_小程序自助裁剪/index.json"
    module_checksum = knowledge_base / ".knowledge-index/watchPic/V5.6.0_小程序自助裁剪/checksum.json"

    assert root_index.exists()
    assert root_checksum.exists()
    assert root_report.exists()
    assert module_index.exists()
    assert module_checksum.exists()
    assert not (knowledge_base / ".knowledge-index/modules" / module_key).exists()
    assert module_key in first["rebuilt_modules"]

    second = server.refresh_knowledge_index(str(knowledge_base), force=False)
    assert second["rebuilt_modules"] == []
    assert module_key in second["skipped_modules"]


def test_root_index_is_navigation_only_and_points_to_mirrored_module_indexes(knowledge_base):
    server.refresh_knowledge_index(str(knowledge_base), force=True)

    root_index = server._read_json(knowledge_base / ".knowledge-index/root-index.json")

    assert "documents" not in root_index
    assert "systems" in root_index
    module_entry = root_index["systems"]["watchPic"]["modules"][0]
    assert module_entry["safe_module"] == "V5.6.0_小程序自助裁剪"
    assert module_entry["index_path"] == ".knowledge-index/watchPic/V5.6.0_小程序自助裁剪/index.json"
    assert module_entry["checksum_path"] == ".knowledge-index/watchPic/V5.6.0_小程序自助裁剪/checksum.json"


def test_refresh_knowledge_index_rebuilds_only_changed_module_and_force_rebuilds_all(knowledge_base):
    server.refresh_knowledge_index(str(knowledge_base), force=False)
    changed_file = knowledge_base / "watchPic/V5.6.0(小程序自助裁剪)/prd/自助裁剪V5.6.0.md"
    changed_file.write_text(changed_file.read_text(encoding="utf-8") + "\n新增内容\n", encoding="utf-8")

    changed = server.refresh_knowledge_index(str(knowledge_base), force=False)
    changed_key = server._make_module_key("watchPic", "V5.6.0(小程序自助裁剪)")
    unchanged_key = server._make_module_key("qa-hub", "order")

    assert changed["rebuilt_modules"] == [changed_key]
    assert unchanged_key in changed["skipped_modules"]

    forced = server.refresh_knowledge_index(str(knowledge_base), force=True)
    assert changed_key in forced["rebuilt_modules"]
    assert unchanged_key in forced["rebuilt_modules"]


def test_refresh_scan_report_preview_count_comes_from_module_reports(knowledge_base, monkeypatch):
    result = server.refresh_knowledge_index(str(knowledge_base), force=True)
    report = server._read_json(knowledge_base / ".knowledge-index/scan-report.json")

    def fail_rglob(*args, **kwargs):
        raise AssertionError("root preview count must not rescan filesystem")

    monkeypatch.setattr(Path, "rglob", fail_rglob)

    scan = server.scan_knowledge_base(str(knowledge_base))

    assert result["documents_indexed"] == report["documents_count"]
    assert scan["preview_asset_count"] == report["preview_asset_count"] == 4


def test_index_refresh_ttl_skips_refresh_when_root_index_is_fresh(knowledge_base, monkeypatch):
    server.refresh_knowledge_index(str(knowledge_base), force=True)

    def fail_refresh(*args, **kwargs):
        raise AssertionError("fresh root-index should be reused within TTL")

    monkeypatch.setattr(server, "refresh_knowledge_index", fail_refresh)

    result = server.search_context(
        system="watchPic",
        module="V5.6.0(小程序自助裁剪)",
        keywords=["自助裁剪"],
        limit=10,
    )

    assert result["strong_related"] or result["medium_related"] or result["weak_related"]


def test_search_context_force_refresh_triggers_forced_refresh(knowledge_base, monkeypatch):
    server.refresh_knowledge_index(str(knowledge_base), force=True)
    calls = []
    original_refresh = index_service.refresh_knowledge_index

    def record_refresh(root_path="knowledge-base", force=False):
        calls.append(force)
        return original_refresh(root_path, force=force)

    monkeypatch.setattr(index_service, "refresh_knowledge_index", record_refresh)

    server.search_context(
        system="watchPic",
        module="V5.6.0(小程序自助裁剪)",
        keywords=["自助裁剪"],
        limit=10,
        force_refresh=True,
    )

    assert True in calls


def test_write_json_uses_tmp_file_and_replaces_target(knowledge_base):
    path = knowledge_base / ".knowledge-index/atomic.json"

    server._write_json(path, {"value": 1})
    server._write_json(path, {"value": 2})

    assert server._read_json(path) == {"value": 2}
    assert not path.with_name("atomic.json.tmp").exists()


def test_write_text_atomic_writes_target_and_cleans_tmp(knowledge_base):
    path = knowledge_base / "systems/qa-hub/order/context-index.draft.md"

    server._write_text_atomic(path, "# draft\n")
    server._write_text_atomic(path, "# updated draft\n")

    assert path.read_text(encoding="utf-8") == "# updated draft\n"
    assert not path.with_name("context-index.draft.md.tmp").exists()


def test_root_checksum_is_module_level_navigation_without_file_checksums(knowledge_base):
    server.refresh_knowledge_index(str(knowledge_base), force=True)

    root_checksum = server._read_json(knowledge_base / ".knowledge-index/root-checksum.json")
    module_key = server._make_module_key("watchPic", "V5.6.0(小程序自助裁剪)")
    module_entry = root_checksum["modules"][module_key]

    assert "files" not in module_entry
    assert module_entry["checksum_path"] == ".knowledge-index/watchPic/V5.6.0_小程序自助裁剪/checksum.json"
    assert module_entry["documents_count"] == 2

    module_checksum = server._read_json(knowledge_base / module_entry["checksum_path"])
    assert "files" in module_checksum
    assert "testcase/自助裁剪V5.6.0.xmind" in module_checksum["files"]


def test_checksum_for_module_ignores_files_deleted_during_scan(knowledge_base, monkeypatch):
    module_path = knowledge_base / "systems/qa-hub/order"
    original_stat = Path.stat

    def flaky_stat(path, *args, **kwargs):
        if path.name == "order-v1.2.md":
            raise FileNotFoundError(str(path))
        return original_stat(path, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", flaky_stat)

    checksum = server._checksum_for_module(module_path)

    assert "testcase/order-v1.2.md" not in checksum
    assert "testcase/order-v1.2.xmind" in checksum


def test_find_root_for_path_resolves_allowed_root_and_rejects_outside(knowledge_base, tmp_path):
    module_path = knowledge_base / "watchPic/V5.6.0(小程序自助裁剪)"

    assert server._find_root_for_path(module_path) == knowledge_base.resolve(strict=False)

    with pytest.raises(ValueError, match="outside allowed knowledge roots"):
        server._find_root_for_path(tmp_path / "outside")


def test_extract_metadata_pairs_testcase_markdown_with_xmind(knowledge_base):
    path = knowledge_base / "systems/qa-hub/order/testcase/order-v1.2.md"

    result = server.extract_metadata(str(path))

    assert result["doc_type"] == "testcase"
    assert result["system"] == "qa-hub"
    assert result["module"] == "order"
    assert result["ai_source_path"].endswith("order-v1.2.md")
    assert result["xmind_path"].endswith("order-v1.2.xmind")
    assert result["xmind_exists"] is True
    assert "Order" in result["business_objects"]
    assert "/order/create" in result["interfaces"]
    assert result["readable"] is True
    assert result["preview_only"] is False


def test_extract_metadata_supports_flat_system_iteration_layout(knowledge_base):
    path = knowledge_base / "watchPic/V5.6.0(小程序自助裁剪)/testcase/自助裁剪V5.6.0.md"

    result = server.extract_metadata(str(path))

    assert result["doc_type"] == "testcase"
    assert result["system"] == "watchPic"
    assert result["module"] == "V5.6.0(小程序自助裁剪)"
    assert result["version"] == "V5.6.0"
    assert result["xmind_exists"] is True
    assert result["xmind_path"].endswith("自助裁剪V5.6.0.xmind")


def test_extract_metadata_accepts_xmind_as_preview_asset_without_reading(knowledge_base, monkeypatch):
    path = knowledge_base / "systems/qa-hub/order/testcase/order-v1.2.xmind"
    original_read_text_limited = server._read_text_limited

    def fail_if_xmind_is_read(target, *args, **kwargs):
        if Path(target).suffix == ".xmind":
            raise AssertionError("xmind content must not be read")
        return original_read_text_limited(target, *args, **kwargs)

    monkeypatch.setattr(server, "_read_text_limited", fail_if_xmind_is_read)

    result = server.extract_metadata(str(path))

    assert result["doc_type"] == "testcase"
    assert result["file_path"].endswith("order-v1.2.xmind")
    assert result["ai_source_path"].endswith("order-v1.2.md")
    assert result["xmind_path"].endswith("order-v1.2.xmind")
    assert result["xmind_exists"] is True
    assert result["preview_only"] is True
    assert result["readable"] is False


def test_extract_metadata_frontmatter_overrides_path_inference(knowledge_base):
    path = knowledge_base / "systems/wrong/path/prd/frontmatter.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "---\n"
        "doc_type: testcase\n"
        "system: qa-hub\n"
        "module: order\n"
        "version: v9.9\n"
        "business_objects:\n"
        "  - Order\n"
        "interfaces:\n"
        "  - /order/create\n"
        "states:\n"
        "  - CREATED\n"
        "roles:\n"
        "  - user\n"
        "---\n"
        "# Frontmatter Wins\n\nCreateOrderService should not become a business object.\n",
        encoding="utf-8",
    )

    result = server.extract_metadata(str(path))

    assert result["doc_type"] == "testcase"
    assert result["system"] == "qa-hub"
    assert result["module"] == "order"
    assert result["version"] == "v9.9"
    assert result["business_objects"] == ["Order"]
    assert result["interfaces"] == ["/order/create"]
    assert result["states"] == ["CREATED"]
    assert result["roles"] == ["user"]


def test_extract_metadata_frontmatter_missing_fields_fall_back_to_path_and_text(knowledge_base):
    path = knowledge_base / "systems/qa-hub/order/prd/partial-frontmatter-v2.0.md"
    path.write_text(
        "---\n"
        "version: v2.0\n"
        "---\n"
        "# 部分 Frontmatter PRD\n\n业务对象: Order\n接口: /order/update\n",
        encoding="utf-8",
    )

    result = server.extract_metadata(str(path))

    assert result["doc_type"] == "prd"
    assert result["system"] == "qa-hub"
    assert result["module"] == "order"
    assert result["version"] == "v2.0"
    assert result["title"] == "部分 Frontmatter PRD"
    assert "Order" in result["business_objects"]
    assert "/order/update" in result["interfaces"]


def test_extract_metadata_invalid_frontmatter_does_not_crash(knowledge_base):
    path = knowledge_base / "systems/qa-hub/order/prd/bad-frontmatter.md"
    path.write_text(
        "---\n"
        "doc_type testcase\n"
        "# Bad Frontmatter PRD\n\n业务对象: Order\n",
        encoding="utf-8",
    )

    result = server.extract_metadata(str(path))

    assert result["doc_type"] == "prd"
    assert result["system"] == "qa-hub"
    assert result["module"] == "order"
    assert result["warnings"]


def test_list_module_assets_merges_markdown_and_xmind_pairs(knowledge_base):
    result = server.list_module_assets("qa-hub", "order")

    testcase = {Path(item.get("ai_source_path") or item["xmind_path"]).stem: item for item in result["testcase"]}
    assert testcase["order-v1.2"]["xmind_exists"] is True
    assert testcase["order-v1.2"]["ai_source_path"].endswith("order-v1.2.md")
    assert testcase["order-v1.3"]["xmind_path"] is None
    assert testcase["order-v1.4"]["ai_source_path"] is None
    assert testcase["order-v1.4"]["xmind_path"].endswith("order-v1.4.xmind")


def test_list_module_assets_finds_module_in_extra_allowed_root(knowledge_base, tmp_path, monkeypatch):
    extra_root = tmp_path / "extra-knowledge-base"
    extra_module = extra_root / "systems" / "crm" / "coupon"
    (extra_module / "testcase").mkdir(parents=True)
    (extra_module / "testcase" / "coupon-v1.md").write_text(
        "# 优惠券测试用例\n\n### TC001 核销\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("TEST_KNOWLEDGE_ROOTS", f"{knowledge_base}{server.os.pathsep}{extra_root}")

    result = server.list_module_assets("crm", "coupon")

    assert result["testcase"][0]["ai_source_path"].endswith("coupon-v1.md")


def test_list_module_assets_supports_flat_system_iteration_layout(knowledge_base):
    result = server.list_module_assets("watchPic", "V5.6.0(小程序自助裁剪)")

    assert result["prd"][0]["ai_source_path"].endswith("自助裁剪V5.6.0.md")
    assert result["testcase"][0]["ai_source_path"].endswith("自助裁剪V5.6.0.md")
    assert result["testcase"][0]["xmind_path"].endswith("自助裁剪V5.6.0.xmind")
    assert result["testcase"][0]["version"] == "V5.6.0"


def test_validate_knowledge_base_reports_orphan_markdown_and_xmind_as_warnings(knowledge_base):
    result = server.validate_knowledge_base(str(knowledge_base))

    assert result["valid"] is True
    assert result["errors"] == []
    assert result["summary"]["paired_testcase_count"] == 2
    assert result["summary"]["orphan_markdown_count"] == 2
    assert result["summary"]["orphan_xmind_count"] == 2
    assert any(path.endswith("shared/payment/testcase/payment-shared.md") for path in result["summary"]["orphan_markdown_files"])
    assert any(path.endswith("shared/payment/testcase/payment-orphan.xmind") for path in result["summary"]["orphan_xmind_files"])
    assert any("缺少同名 XMind" in warning for warning in result["warnings"])
    assert any("缺少同名 Markdown" in warning for warning in result["warnings"])


def test_read_context_documents_reads_ai_source_and_rejects_xmind(knowledge_base):
    md_path = knowledge_base / "systems/qa-hub/order/testcase/order-v1.2.md"
    xmind_path = knowledge_base / "systems/qa-hub/order/testcase/order-v1.2.xmind"

    result = server.read_context_documents(
        [
            {"ai_source_path": str(md_path), "doc_type": "testcase"},
            {"ai_source_path": str(xmind_path), "doc_type": "testcase"},
        ],
        max_chars_per_doc=80,
    )

    assert len(result["documents"]) == 1
    assert "订单 v1.2 测试用例" in result["documents"][0]["content"]
    assert result["documents"][0]["xmind_path"].endswith("order-v1.2.xmind")
    assert result["errors"]
    assert ".xmind is a preview asset only" in result["errors"][0]["error"]


def test_search_context_returns_paired_paths_for_strong_results(knowledge_base):
    result = server.search_context(
        system="qa-hub",
        module="order",
        business_objects=["Order", "Coupon"],
        interfaces=["/order/create"],
        states=["CREATED", "PAID"],
        roles=["user", "admin"],
        upstream_dependencies=["product"],
        downstream_dependencies=["payment", "inventory"],
        keywords=["下单", "支付", "优惠券"],
        limit=10,
    )

    assert result["strong_related"]
    testcase_hits = [item for item in result["strong_related"] if item["doc_type"] == "testcase"]
    assert testcase_hits
    assert testcase_hits[0]["ai_source_path"].endswith(".md")
    assert testcase_hits[0]["xmind_path"].endswith(".xmind")
    assert testcase_hits[0]["xmind_exists"] is True


def test_search_context_with_system_module_reads_only_matching_module_index(knowledge_base, monkeypatch):
    server.refresh_knowledge_index(str(knowledge_base), force=True)
    loaded = []
    original = search_service._load_module_index

    def record_load(root, module_info):
        loaded.append(module_info["module_key"])
        return original(root, module_info)

    monkeypatch.setattr(search_service, "_load_module_index", record_load)

    server.search_context(
        system="watchPic",
        module="V5.6.0(小程序自助裁剪)",
        keywords=["自助裁剪"],
        limit=10,
    )

    assert loaded == [server._make_module_key("watchPic", "V5.6.0(小程序自助裁剪)")]


def test_search_context_with_system_reads_that_system_module_indexes(knowledge_base, monkeypatch):
    server.refresh_knowledge_index(str(knowledge_base), force=True)
    loaded = []
    original = search_service._load_module_index

    def record_load(root, module_info):
        loaded.append(module_info["module_key"])
        return original(root, module_info)

    monkeypatch.setattr(search_service, "_load_module_index", record_load)

    server.search_context(system="watchPic", module="", keywords=["自助裁剪"], limit=10)

    assert loaded == [server._make_module_key("watchPic", "V5.6.0(小程序自助裁剪)")]


def test_search_context_searches_multiple_allowed_roots_and_skips_missing_roots(knowledge_base, tmp_path, monkeypatch):
    extra_root = tmp_path / "extra-knowledge-base"
    extra_module = extra_root / "systems" / "crm" / "coupon"
    (extra_module / "prd").mkdir(parents=True)
    (extra_module / "prd" / "coupon-v2.md").write_text(
        "# 优惠券 v2 PRD\n\n业务对象: Coupon\n接口: /coupon/apply\n关键词: 优惠券 核销\n",
        encoding="utf-8",
    )
    missing_root = tmp_path / "missing-knowledge-base"
    monkeypatch.setenv("TEST_KNOWLEDGE_ROOTS", f"{knowledge_base}{server.os.pathsep}{extra_root}{server.os.pathsep}{missing_root}")

    result = server.search_context(
        system="crm",
        module="coupon",
        business_objects=["Coupon"],
        interfaces=["/coupon/apply"],
        keywords=["优惠券"],
        limit=20,
    )

    paths = [item["file_path"] for item in result["strong_related"] + result["medium_related"] + result["weak_related"]]
    assert any(path.endswith("extra-knowledge-base/systems/crm/coupon/prd/coupon-v2.md") for path in paths)


def test_search_context_doc_types_filter_limits_results(knowledge_base):
    result = server.search_context(
        system="qa-hub",
        module="order",
        business_objects=["Order", "Coupon"],
        interfaces=["/order/create"],
        keywords=["支付"],
        doc_types=["bug"],
        limit=20,
    )

    returned = result["strong_related"] + result["medium_related"] + result["weak_related"] + result["excluded"]
    assert returned
    assert {item["doc_type"] for item in returned} == {"bug"}


def test_search_context_can_recall_shared_rules(knowledge_base):
    result = server.search_context(
        system="",
        module="",
        keywords=["支付", "优惠券"],
        doc_types=["api"],
        limit=20,
    )

    returned = result["strong_related"] + result["medium_related"] + result["weak_related"]
    assert any(item["file_path"].endswith("shared/payment/api/payment-common-rules.md") for item in returned)


def test_search_context_returns_empty_buckets_when_nothing_matches(knowledge_base):
    result = server.search_context(
        system="unknown",
        module="unknown",
        keywords=["never-hit-keyword"],
        limit=20,
    )

    assert result["strong_related"] == []
    assert result["medium_related"] == []
    assert result["weak_related"] == []
    assert result["excluded"] == []
    assert result["reasoning_summary"] == "未命中有效上下文，建议检查 system/module/keywords 是否正确。"


def test_generate_context_index_draft_writes_draft_with_ai_source_and_xmind_columns(knowledge_base):
    module_path = knowledge_base / "systems/qa-hub/order"

    result = server.generate_context_index_draft("qa-hub", "order")

    draft_path = module_path / "context-index.draft.md"
    content = draft_path.read_text(encoding="utf-8")
    assert result["context_index_path"].endswith("context-index.draft.md")
    assert "| 版本 | 标题 | AI Source | XMind |" in content
    assert "testcase/order-v1.2.md" in content
    assert "testcase/order-v1.2.xmind" in content
    assert "order-v1.4.xmind 缺少同名 Markdown" in content


def test_generate_context_index_draft_handles_empty_module_directory(knowledge_base):
    module_path = knowledge_base / "systems/qa-hub/empty"
    for directory in ["prd", "testcase", "bug", "api", "release"]:
        (module_path / directory).mkdir(parents=True, exist_ok=True)

    result = server.generate_context_index_draft("qa-hub", "empty")

    draft_path = module_path / "context-index.draft.md"
    content = draft_path.read_text(encoding="utf-8")
    assert result["summary"]["indexed_count"] == 0
    assert "## 历史 PRD\n\n暂无" in content
    assert "## 历史测试用例\n\n暂无" in content
    assert "- 当前模块暂无可索引知识资产。" in content
    assert "- 建议补充 PRD、测试用例、接口文档、缺陷或发布说明。" in content


def test_generate_context_index_draft_finds_module_in_extra_allowed_root(knowledge_base, tmp_path, monkeypatch):
    extra_root = tmp_path / "extra-knowledge-base"
    extra_module = extra_root / "systems" / "crm" / "coupon"
    (extra_module / "prd").mkdir(parents=True)
    (extra_module / "prd" / "coupon-v1.md").write_text(
        "# 优惠券 PRD\n\n业务对象: Coupon\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("TEST_KNOWLEDGE_ROOTS", f"{knowledge_base}{server.os.pathsep}{extra_root}")

    result = server.generate_context_index_draft("crm", "coupon")

    draft_path = extra_module / "context-index.draft.md"
    assert result["context_index_path"].endswith("context-index.draft.md")
    assert draft_path.exists()
    assert "优惠券 PRD" in draft_path.read_text(encoding="utf-8")


def test_generate_context_index_draft_supports_flat_system_iteration_layout(knowledge_base):
    result = server.generate_context_index_draft("watchPic", "V5.6.0(小程序自助裁剪)")

    draft_path = knowledge_base / "watchPic/V5.6.0(小程序自助裁剪)/context-index.draft.md"
    content = draft_path.read_text(encoding="utf-8")
    assert result["context_index_path"].endswith("context-index.draft.md")
    assert "自助裁剪 V5.6.0 PRD" in content
    assert "testcase/自助裁剪V5.6.0.md" in content
    assert "testcase/自助裁剪V5.6.0.xmind" in content


def test_generate_context_index_draft_uses_existing_module_index(knowledge_base, monkeypatch):
    server.refresh_knowledge_index(str(knowledge_base), force=True)

    def fail_realtime_module_scan(*args, **kwargs):
        raise AssertionError("generate_context_index_draft should use module index")

    monkeypatch.setattr(server, "_collect_module_metadata", fail_realtime_module_scan)

    result = server.generate_context_index_draft("watchPic", "V5.6.0(小程序自助裁剪)")

    assert result["summary"]["indexed_count"] >= 2


def test_validate_testcase_markdown_warns_when_xmind_is_missing(knowledge_base):
    path = knowledge_base / "systems/qa-hub/order/testcase/order-v1.3.md"

    result = server.validate_testcase_markdown(str(path))

    assert result["valid"] is True
    assert result["ai_source_path"].endswith("order-v1.3.md")
    assert result["xmind_path"] is None
    assert result["xmind_exists"] is False
    assert any("缺少同目录同名 XMind" in warning for warning in result["warnings"])


def test_validate_testcase_markdown_rejects_xmind_without_crashing(knowledge_base):
    path = knowledge_base / "systems/qa-hub/order/testcase/order-v1.2.xmind"

    result = server.validate_testcase_markdown(str(path))

    assert result["valid"] is False
    assert "testcase AI source must be a Markdown .md file" in result["errors"]
    assert result["ai_source_path"].endswith("order-v1.2.md")
    assert result["xmind_path"].endswith("order-v1.2.xmind")
    assert result["xmind_exists"] is True


def test_validate_testcase_markdown_without_case_id_but_steps_expected_is_valid(knowledge_base):
    path = knowledge_base / "systems/qa-hub/order/testcase/steps-expected.md"
    path.write_text(
        "# 无编号测试用例\n\n"
        "- steps:\n"
        "  - step: 提交订单\n"
        "    expected: 创建成功\n",
        encoding="utf-8",
    )

    result = server.validate_testcase_markdown(str(path))

    assert result["valid"] is True
    assert result["structure"]["has_steps"] is True
    assert result["structure"]["has_expected"] is True


def test_validate_testcase_markdown_tree_structure_is_valid(knowledge_base):
    path = knowledge_base / "systems/qa-hub/order/testcase/tree.md"
    path.write_text(
        "# 订单测试\n\n"
        "## 下单流程\n"
        "### 正常下单\n"
        "- 输入订单信息\n"
        "  - 校验优惠券\n"
        "  - 提交订单\n",
        encoding="utf-8",
    )

    result = server.validate_testcase_markdown(str(path))

    assert result["valid"] is True
    assert result["structure"]["has_tree_structure"] is True


def test_validate_testcase_markdown_empty_markdown_is_invalid(knowledge_base):
    path = knowledge_base / "systems/qa-hub/order/testcase/empty.md"
    path.write_text("", encoding="utf-8")

    result = server.validate_testcase_markdown(str(path))

    assert result["valid"] is False
    assert "testcase Markdown is empty" in result["errors"]


def test_path_traversal_outside_allowed_roots_is_rejected(knowledge_base):
    with pytest.raises(ValueError):
        server.extract_metadata(str(knowledge_base / "../outside.md"))


def test_knowledge_root_outside_allowed_roots_is_rejected(knowledge_base, tmp_path):
    outside = tmp_path / "outside.md"
    outside.write_text("# outside\n", encoding="utf-8")

    with pytest.raises(ValueError):
        server.extract_metadata(str(outside))


def test_scan_knowledge_base_missing_path_has_stable_error(knowledge_base):
    with pytest.raises(ValueError, match="outside allowed knowledge roots"):
        server.scan_knowledge_base("not-exists")


def test_scan_knowledge_base_missing_path_inside_allowed_root_has_stable_error(knowledge_base):
    with pytest.raises(FileNotFoundError, match="knowledge root not found"):
        server.scan_knowledge_base(str(knowledge_base / "not-exists"))


def test_read_context_documents_enforces_max_total_return_chars(knowledge_base, monkeypatch):
    doc1 = knowledge_base / "systems/qa-hub/order/prd/long-1.md"
    doc2 = knowledge_base / "systems/qa-hub/order/prd/long-2.md"
    doc1.write_text("# long 1\n" + "a" * 200, encoding="utf-8")
    doc2.write_text("# long 2\n" + "b" * 200, encoding="utf-8")
    monkeypatch.setattr(search_service, "MAX_TOTAL_RETURN_CHARS", 100)

    result = server.read_context_documents(
        [
            {"ai_source_path": str(doc1), "doc_type": "prd"},
            {"ai_source_path": str(doc2), "doc_type": "prd"},
        ],
        max_chars_per_doc=80,
    )

    assert len(result["documents"]) == 2
    assert sum(len(document["content"]) for document in result["documents"]) == 100
    assert len(result["documents"][0]["content"]) == 80
    assert len(result["documents"][1]["content"]) == 20
    assert result["documents"][1]["truncated"] is True


def test_read_context_documents_does_not_append_empty_document_after_total_limit(knowledge_base, monkeypatch):
    doc1 = knowledge_base / "systems/qa-hub/order/prd/limit-1.md"
    doc2 = knowledge_base / "systems/qa-hub/order/prd/limit-2.md"
    doc1.write_text("# limit 1\n" + "a" * 200, encoding="utf-8")
    doc2.write_text("# limit 2\n" + "b" * 200, encoding="utf-8")
    monkeypatch.setattr(search_service, "MAX_TOTAL_RETURN_CHARS", 50)

    result = server.read_context_documents(
        [
            {"ai_source_path": str(doc1), "doc_type": "prd"},
            {"ai_source_path": str(doc2), "doc_type": "prd"},
        ],
        max_chars_per_doc=50,
    )

    assert len(result["documents"]) == 1
    assert result["documents"][0]["content"]


def test_extract_keywords_filters_chinese_stopwords_and_camelcase_body_noise(knowledge_base):
    path = knowledge_base / "systems/qa-hub/order/prd/noisy.md"
    path.write_text(
        "# OrderCouponFeature\n\n"
        "需求 系统 页面 功能 支持 进行 展示 输入 输出 点击 用户 数据 处理 操作 信息 相关 内容 模块 接口 状态 规则 创建 更新 删除 查询 列表 详情 提交 返回\n\n"
        "CreateOrderService 调用 PaymentController 返回 OrderDTO。\n",
        encoding="utf-8",
    )

    metadata = server.extract_metadata(str(path))

    assert "需求" not in metadata["keywords"]
    assert "页面" not in metadata["keywords"]
    assert "CreateOrderService" not in metadata["business_objects"]
    assert "PaymentController" not in metadata["business_objects"]
    assert "OrderDTO" not in metadata["business_objects"]
    assert "OrderCouponFeature" in metadata["business_objects"]
