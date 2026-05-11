"""
Gemini LLM 래퍼 — 신규 google-genai SDK 사용.
Gemini 2.5+ 모델은 새 SDK로만 정상 호출됩니다.
환경변수 GEMINI_API_KEY 필수.
"""

import os
import json
import logging
from typing import Optional, List

from google import genai
from google.genai import types
from PIL import Image

log = logging.getLogger(__name__)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()

_client = None


def _get_client():
    global _client
    if _client is None:
        if not GEMINI_API_KEY:
            raise RuntimeError(
                "GEMINI_API_KEY 환경변수가 설정되지 않았습니다. "
                "Render → Environment 메뉴에서 GEMINI_API_KEY를 추가해주세요. "
                "키는 https://aistudio.google.com/apikey 에서 무료로 발급받을 수 있습니다."
            )
        _client = genai.Client(api_key=GEMINI_API_KEY)
    return _client


def _build_config(system_instruction: Optional[str], temperature: float,
                  max_tokens: int, json_mode: bool = False) -> types.GenerateContentConfig:
    kwargs = {
        "temperature": temperature,
        "max_output_tokens": max_tokens,
    }
    if system_instruction:
        kwargs["system_instruction"] = system_instruction
    if json_mode:
        kwargs["response_mime_type"] = "application/json"
    return types.GenerateContentConfig(**kwargs)


class GeminiLLM:
    """Gemini API 래퍼 (텍스트 + JSON + 비전)."""

    def __init__(self, system_instruction: Optional[str] = None, model: Optional[str] = None):
        self.client = _get_client()
        self.model_name = model or GEMINI_MODEL
        self.system_instruction = system_instruction

    # ---------- 텍스트 ----------
    def generate(self, prompt: str, temperature: float = 0.8, max_tokens: int = 800) -> str:
        try:
            cfg = _build_config(self.system_instruction, temperature, max_tokens, json_mode=False)
            resp = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=cfg,
            )
            return (resp.text or "").strip()
        except Exception as e:
            log.error(f"Gemini generate 실패 ({self.model_name}): {e}")
            return f"(응답 생성 실패: {e})"

    # ---------- JSON ----------
    def generate_json(self, prompt: str, temperature: float = 0.3, max_tokens: int = 1500) -> dict:
        text = ""
        try:
            cfg = _build_config(self.system_instruction, temperature, max_tokens, json_mode=True)
            resp = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=cfg,
            )
            text = (resp.text or "").strip()
            return json.loads(text)
        except json.JSONDecodeError:
            # JSON 부분만 추출 재시도
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
            log.error(f"Gemini generate_json 실패 ({self.model_name}): {e}")
            return {}

    # ---------- 멀티모달 (이미지) ----------
    def generate_with_images(self, prompt: str, images: List[Image.Image],
                             temperature: float = 0.6, max_tokens: int = 1000) -> str:
        try:
            cfg = _build_config(self.system_instruction, temperature, max_tokens, json_mode=False)
            # 새 SDK는 PIL Image를 contents 리스트에 그대로 넣을 수 있음
            parts = [prompt] + list(images or [])
            resp = self.client.models.generate_content(
                model=self.model_name,
                contents=parts,
                config=cfg,
            )
            return (resp.text or "").strip()
        except Exception as e:
            log.error(f"Gemini vision 실패 ({self.model_name}): {e}")
            return f"(이미지 분석 실패: {e})"
