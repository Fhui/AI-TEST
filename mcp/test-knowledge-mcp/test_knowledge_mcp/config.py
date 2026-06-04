"""集中维护 test-knowledge-mcp 的路径、索引、扩展名和文本识别常量。"""

from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_KNOWLEDGE_ROOT = PROJECT_ROOT / "knowledge-base"
MAX_FILE_BYTES = 2 * 1024 * 1024
DEFAULT_MAX_CHARS_PER_DOC = 6000
MAX_TOTAL_RETURN_CHARS = 60000
INDEX_DIR_NAME = ".knowledge-index"
ROOT_INDEX_FILE_NAME = "root-index.json"
ROOT_CHECKSUM_FILE_NAME = "root-checksum.json"
MODULE_INDEX_FILE_NAME = "index.json"
MODULE_CHECKSUM_FILE_NAME = "checksum.json"
SCAN_REPORT_FILE_NAME = "scan-report.json"
INDEX_REFRESH_TTL_SECONDS = 30
AI_SOURCE_EXTENSIONS = {".md", ".json", ".csv", ".opml", ".txt"}
PREVIEW_ONLY_EXTENSIONS = {".xmind"}
ALL_KNOWLEDGE_EXTENSIONS = AI_SOURCE_EXTENSIONS | PREVIEW_ONLY_EXTENSIONS
READABLE_AI_EXTENSIONS = AI_SOURCE_EXTENSIONS
DOC_TYPE_DIRS = {"prd", "testcase", "bug", "api", "release"}
MODULE_MARKER_FILES = {"upstream-downstream.md", "context-index.md", "context-index.draft.md"}
IGNORED_NAMES = {".DS_Store", ".gitkeep", INDEX_DIR_NAME, "__MACOSX", ".git"}
ROLE_KEYWORDS = {
    "user",
    "admin",
    "buyer",
    "seller",
    "operator",
    "用户",
    "管理员",
    "运营",
    "商家",
    "买家",
    "审核员",
}
RISK_KEYWORDS = {"风险", "缺陷", "bug", "阻塞", "兼容", "回滚", "线上问题", "异常", "失败", "超时", "重复", "幂等"}
CHINESE_STOPWORDS = {
    "需求",
    "系统",
    "页面",
    "功能",
    "支持",
    "进行",
    "展示",
    "输入",
    "输出",
    "点击",
    "用户",
    "数据",
    "处理",
    "操作",
    "信息",
    "相关",
    "内容",
    "模块",
    "接口",
    "状态",
    "规则",
    "创建",
    "更新",
    "删除",
    "查询",
    "列表",
    "详情",
    "提交",
    "返回",
}
TECHNICAL_CAMEL_SUFFIXES = (
    "Service",
    "Controller",
    "DTO",
    "DAO",
    "Mapper",
    "Repository",
    "Client",
    "Config",
    "Request",
    "Response",
    "VO",
    "PO",
)
SUPPORTED_DOC_TYPES = {"prd", "testcase", "bug", "api", "release", "module_map", "upstream_downstream", "unknown"}
FRONTMATTER_LIST_FIELDS = {
    "business_objects",
    "interfaces",
    "states",
    "roles",
    "upstream_dependencies",
    "downstream_dependencies",
    "keywords",
    "risk_points",
}
FRONTMATTER_SCALAR_FIELDS = {"doc_type", "system", "module", "version", "title"}
FRONTMATTER_FIELDS = FRONTMATTER_LIST_FIELDS | FRONTMATTER_SCALAR_FIELDS
