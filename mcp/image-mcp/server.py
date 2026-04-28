from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

import requests
from PIL import Image
from mcp.server.fastmcp import FastMCP

try:
    import pytesseract
except ImportError:  # pragma: no cover - optional dependency at runtime
    pytesseract = None


# 允许操作的根目录固定为当前项目根目录 ai-test。
PROJECT_ROOT = Path(__file__).resolve().parents[2]
ALLOWED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}

mcp = FastMCP("image-mcp")


def _resolve_path(path: str) -> Path:
    """将输入路径规范化，并确保路径始终落在项目根目录内。"""
    raw_path = Path(path)
    candidate = raw_path if raw_path.is_absolute() else PROJECT_ROOT / raw_path
    normalized = candidate.resolve(strict=False)

    try:
        normalized.relative_to(PROJECT_ROOT)
    except ValueError as exc:
        raise ValueError(f"path is outside allowed root: {path}") from exc

    return normalized


def _error_result(message: str, path: str | None = None) -> dict[str, Any]:
    """统一的错误返回格式。"""
    result: dict[str, Any] = {"success": False, "error": message}
    if path is not None:
        try:
            result["absolute_path"] = str(_resolve_path(path))
        except Exception:
            pass
    return result


def _ensure_ocr_ready() -> None:
    """确保 OCR 依赖可用。"""
    if pytesseract is None:
        raise RuntimeError("pytesseract is not installed")
    if shutil.which("tesseract") is None:
        raise RuntimeError("tesseract binary is not installed or not in PATH")


def _ocr_text(path: Path) -> str:
    """读取图片并提取 OCR 文本。"""
    _ensure_ocr_ready()
    with Image.open(path) as image:
        return pytesseract.image_to_string(image, lang="chi_sim+eng").strip()


def _ocr_data(path: Path) -> list[dict[str, Any]]:
    """提取带位置信息的 OCR 数据，用于流程元素抽取。"""
    _ensure_ocr_ready()
    with Image.open(path) as image:
        data = pytesseract.image_to_data(
            image,
            lang="chi_sim+eng",
            output_type=pytesseract.Output.DICT,
        )

    rows: list[dict[str, Any]] = []
    total = len(data["text"])
    for index in range(total):
        text = (data["text"][index] or "").strip()
        confidence_raw = data["conf"][index]
        try:
            confidence = float(confidence_raw)
        except (TypeError, ValueError):
            confidence = -1.0

        if not text or confidence < 0:
            continue

        rows.append(
            {
                "text": text,
                "left": int(data["left"][index]),
                "top": int(data["top"][index]),
                "width": int(data["width"][index]),
                "height": int(data["height"][index]),
                "conf": confidence,
            }
        )

    return rows


def _classify_image_internal(path: Path) -> tuple[str, str]:
    """基于 OCR 文本和简单启发式规则做基础图片分类。"""
    suffix = path.suffix.lower()
    if suffix not in ALLOWED_IMAGE_EXTENSIONS:
        return "unknown", f"unsupported image extension: {suffix}"

    with Image.open(path) as image:
        width, height = image.size

    text = ""
    try:
        text = _ocr_text(path).lower()
    except Exception:
        text = ""

    keywords = {
        "sequence_diagram": ["participant", "actor", "->", "-->", "alt", "opt", "loop", "lifeline"],
        "flowchart": ["开始", "结束", "流程", "判断", "是否", "处理", "节点", "提交", "审批"],
        "modal_or_popup": ["提示", "确认", "取消", "关闭", "知道了", "弹窗"],
        "wireframe": ["原型", "输入", "提交", "备注", "选择", "按钮", "页面"],
        "screenshot": ["首页", "详情", "列表", "设置", "管理", "中心"],
    }

    if any(keyword in text for keyword in keywords["sequence_diagram"]):
        return "sequence_diagram", "ocr text contains sequence-diagram style keywords"

    if any(keyword in text for keyword in keywords["flowchart"]):
        return "flowchart", "ocr text contains flowchart keywords"

    if any(keyword in text for keyword in keywords["modal_or_popup"]):
        return "modal_or_popup", "ocr text contains popup or confirmation keywords"

    if width < 600 and height > width * 2:
        return "wireframe", "image is tall and narrow, similar to a mobile wireframe"

    if width > 1200 and height > 700:
        return "screenshot", "image size is similar to a desktop screenshot"

    if any(keyword in text for keyword in keywords["wireframe"]):
        return "wireframe", "ocr text looks like page fields or form labels"

    if any(keyword in text for keyword in keywords["screenshot"]):
        return "screenshot", "ocr text looks like UI navigation or page labels"

    return "unknown", "no clear heuristic matched"


@mcp.tool()
def download_image(url: str, save_path: str) -> dict[str, Any]:
    """下载远程图片到本地。"""
    try:
        target = _resolve_path(save_path)
        if target.suffix.lower() not in ALLOWED_IMAGE_EXTENSIONS:
            return _error_result("save_path must use png/jpg/jpeg/webp", save_path)

        target.parent.mkdir(parents=True, exist_ok=True)

        response = requests.get(url, timeout=30)
        response.raise_for_status()

        content_type = response.headers.get("Content-Type", "")
        if content_type and not content_type.startswith("image/"):
            return _error_result(f"url did not return an image content-type: {content_type}", save_path)

        data = response.content
        target.write_bytes(data)
        return {
            "success": True,
            "absolute_path": str(target),
            "bytes_written": len(data),
            "content_type": content_type or None,
        }
    except Exception as exc:
        return _error_result(str(exc), save_path)


@mcp.tool()
def ocr_image(path: str) -> dict[str, Any]:
    """对本地图片做 OCR。"""
    try:
        target = _resolve_path(path)
        if not target.exists():
            return _error_result(f"file not found: {path}", path)
        if not target.is_file():
            return _error_result(f"path is not a file: {path}", path)

        text = _ocr_text(target)
        return {
            "success": True,
            "absolute_path": str(target),
            "extracted_text": text,
        }
    except Exception as exc:
        return _error_result(str(exc), path)


@mcp.tool()
def classify_image(path: str) -> dict[str, Any]:
    """对本地图片做基础分类。"""
    try:
        target = _resolve_path(path)
        if not target.exists():
            return _error_result(f"file not found: {path}", path)
        if not target.is_file():
            return _error_result(f"path is not a file: {path}", path)

        image_type, reason = _classify_image_internal(target)
        return {
            "success": True,
            "absolute_path": str(target),
            "image_type": image_type,
            "reason": reason,
        }
    except Exception as exc:
        return _error_result(str(exc), path)


@mcp.tool()
def extract_flow_elements(path: str, nearby_text: str = "") -> dict[str, Any]:
    """提取流程图或时序图的结构化中间结果，不直接生成 PlantUML。"""
    try:
        target = _resolve_path(path)
        if not target.exists():
            return _error_result(f"file not found: {path}", path)
        if not target.is_file():
            return _error_result(f"path is not a file: {path}", path)

        image_type, reason = _classify_image_internal(target)
        if image_type not in {"flowchart", "sequence_diagram"}:
            return {
                "success": True,
                "absolute_path": str(target),
                "image_type": image_type,
                "nodes": [],
                "edges": [],
                "annotations": [],
                "confidence": 0.0,
                "limitations": [f"image is not a flowchart or sequence diagram: {reason}"],
            }

        rows = _ocr_data(target)
        nodes = [
            {"id": f"node_{index + 1}", "text": row["text"]}
            for index, row in enumerate(rows)
        ]

        edges = []
        sorted_rows = sorted(rows, key=lambda row: (row["top"], row["left"]))
        for index in range(len(sorted_rows) - 1):
            current_id = f"node_{rows.index(sorted_rows[index]) + 1}"
            next_id = f"node_{rows.index(sorted_rows[index + 1]) + 1}"
            edges.append({"from": current_id, "to": next_id})

        annotations = []
        if nearby_text.strip():
            annotations.append("nearby_text was provided as auxiliary context")

        limitations = [
            "edges are inferred from OCR reading order, not from actual arrow detection",
            "node grouping is based on OCR text boxes and may split one visual node into multiple text items",
        ]

        if not rows:
            limitations.append("no OCR text was extracted from the image")

        confidence = 0.3
        if rows:
            avg_conf = sum(row["conf"] for row in rows) / len(rows)
            confidence = min(1.0, max(0.1, avg_conf / 100))

        return {
            "success": True,
            "absolute_path": str(target),
            "image_type": image_type,
            "nodes": nodes,
            "edges": edges,
            "annotations": annotations,
            "confidence": round(confidence, 2),
            "limitations": limitations,
        }
    except Exception as exc:
        return _error_result(str(exc), path)


if __name__ == "__main__":
    mcp.run(transport="stdio")
