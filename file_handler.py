"""
첨부파일 처리.
- PDF → 텍스트 추출
- 이미지 → PIL Image 로드 (Gemini Vision 전달용)
"""

import io
import logging
from typing import Dict, Any, List, Tuple

from PIL import Image
from pypdf import PdfReader

log = logging.getLogger(__name__)

MAX_PDF_PAGES = 30
MAX_TEXT_LEN = 8000


def extract_pdf_text(file_bytes: bytes) -> Dict[str, Any]:
    """PDF에서 텍스트 추출."""
    try:
        reader = PdfReader(io.BytesIO(file_bytes))
        pages_text: List[str] = []
        for i, page in enumerate(reader.pages):
            if i >= MAX_PDF_PAGES:
                break
            try:
                pages_text.append(page.extract_text() or "")
            except Exception as e:
                log.warning(f"PDF page {i} 추출 실패: {e}")

        text = "\n\n".join(pages_text).strip()
        return {
            "ok": True,
            "type": "pdf",
            "page_count": len(reader.pages),
            "text": text[:MAX_TEXT_LEN],
        }
    except Exception as e:
        log.error(f"PDF 추출 실패: {e}")
        return {"ok": False, "type": "pdf", "error": str(e), "text": ""}


def load_image(file_bytes: bytes) -> Tuple[Image.Image, Dict[str, Any]]:
    """이미지 바이트 → PIL Image + 메타정보."""
    try:
        img = Image.open(io.BytesIO(file_bytes))
        img.load()
        if img.mode not in ("RGB", "RGBA"):
            img = img.convert("RGB")
        # 너무 큰 이미지는 축소
        max_side = 1600
        if max(img.size) > max_side:
            ratio = max_side / max(img.size)
            new_size = (int(img.size[0] * ratio), int(img.size[1] * ratio))
            img = img.resize(new_size, Image.LANCZOS)
        meta = {
            "ok": True,
            "type": "image",
            "size": img.size,
            "format": img.format or "unknown",
        }
        return img, meta
    except Exception as e:
        log.error(f"이미지 로드 실패: {e}")
        return None, {"ok": False, "type": "image", "error": str(e)}
