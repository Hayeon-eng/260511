"""
Gemini LLM 래퍼.
환경변수 GEMINI_API_KEY 사용. (Google AI Studio에서 무료 발급)
- 텍스트 생성
- JSON 강제 출력
- 이미지 분석 (멀티모달)
"""

import os
import json
import logging
from typing import Optional, List

import google.generativeai as genai
from PIL import Image

log = logging.getLogger(__name__)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash").strip()

_configured = False


def _ensure_configured():
    global _configured
    if _configured:
        return
    if not GEMINI_API_KEY:
        raise RuntimeError(
            "GEMINI_API_KEY 환경변수가 설정되지 않았습니다. "
            "Render → Environment 메뉴에서 GEMINI_API_KEY를 추가해주세요. "
            "키는 https://aistudio.google.com/apikey 에서 무료로 발급받을 수 있습니다."
        )
    genai.configure(api_key=GEMINI_API_KEY)
    _configured = True


class GeminiLLM:
    """Gemini API 래퍼 (텍스트 + 비전)."""

    def __init__(self, system_instruction: Optional[str] = None, model: Optional[str] = None):
        _ensure_configured()
        self.model_name = model or GEMINI_MODEL
        self.system_instruction = system_instruction
        self._model = genai.GenerativeModel(
            model_name=self.model_name,
            system_instruction=system_instruction,
        )

    # ---------- 텍스트 ----------
    def generate(self, prompt: str, temperature: float = 0.8, max_tokens: int = 800) -> str:
        try:
            resp = self._model.generate_content(
                prompt,
                generation_config={
                    "temperature": temperature,
                    "max_output_tokens": max_tokens,
                },
            )
            return (resp.text or "").strip()
        except Exception as e:
            log.error(f"Gemini generate 실패: {e}")
            return f"(응답 생성 실패: {e})"

    # ---------- JSON ----------
    def generate_json(self, prompt: str, temperature: float = 0.3, max_tokens: int = 1500) -> dict:
        text = ""
        try:
            resp = self._model.generate_content(
                prompt,
                generation_config={
                    "temperature": temperature,
                    "max_output_tokens": max_tokens,
                    "response_mime_type": "application/json",
                },
            )
            text = (resp.text or "").strip()
            return json.loads(text)
        except json.JSONDecodeError:
            try:
                start = text.find("{")
                end = text.rfind("}") + 1
                if start != -1 and end > start:
                    return json.loads(text[start:end])
            except Exception:
                pass
            log.warning(f"Gemini JSON 파싱 실패: {text[:200]}")
            return {}
        except Exception as e:
            log.error(f"Gemini generate_json 실패: {e}")
            return {}

    # ---------- 멀티모달 (이미지) ----------
    def generate_with_images(self, prompt: str, images: List[Image.Image], temperature: float = 0.6, max_tokens: int = 1000) -> str:
        """이미지 + 텍스트 분석. images는 PIL Image 리스트."""
        try:
            parts = [prompt] + images
            resp = self._model.generate_content(
                parts,
                generation_config={
                    "temperature": temperature,
                    "max_output_tokens": max_tokens,
                },
            )
            return (resp.text or "").strip()
        except Exception as e:
            log.error(f"Gemini vision 실패: {e}")
            return f"(이미지 분석 실패: {e})"
