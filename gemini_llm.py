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
    # 안전 필터 최저로 (BLOCK_NONE) — Gemini 2.5가 한국어/짧은 입력을 과차단하는 문제 회피
    try:
        kwargs["safety_settings"] = [
            types.SafetySetting(category=c, threshold="BLOCK_NONE")
            for c in [
                "HARM_CATEGORY_HARASSMENT",
                "HARM_CATEGORY_HATE_SPEECH",
                "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                "HARM_CATEGORY_DANGEROUS_CONTENT",
            ]
        ]
    except Exception:
        pass
    return types.GenerateContentConfig(**kwargs)


def _extract_text(resp) -> str:
    """resp.text가 비어있어도 candidates에서 텍스트 추출 시도 + finish reason 디버그."""
    try:
        txt = (resp.text or "").strip() if hasattr(resp, "text") else ""
    except Exception:
        txt = ""
    if txt:
        return txt
    # candidates 깊이 탐색
    try:
        cands = getattr(resp, "candidates", None) or []
        for c in cands:
            content = getattr(c, "content", None)
            parts = getattr(content, "parts", None) if content else None
            if parts:
                for p in parts:
                    t = getattr(p, "text", None)
                    if t:
                        return t.strip()
        # 디버그 정보 노출
        if cands:
            fr = getattr(cands[0], "finish_reason", None)
            log.warning(f"Gemini empty text — finish_reason={fr}")
            return f"(빈 응답: finish_reason={fr})"
    except Exception as e:
        log.warning(f"_extract_text 실패: {e}")
    pf = getattr(resp, "prompt_feedback", None)
    if pf:
        return f"(빈 응답: prompt_feedback={pf})"
    return ""


def _response_finish_reason(resp) -> str:
    """Gemini 응답의 finish_reason을 사람이 읽을 수 있게 추출."""
    try:
        cands = getattr(resp, "candidates", None) or []
        if cands:
            return str(getattr(cands[0], "finish_reason", "") or "")
    except Exception:
        pass
    return ""


def _response_prompt_feedback(resp) -> str:
    """프롬프트 차단/안전 필터 관련 피드백이 있으면 추출."""
    try:
        pf = getattr(resp, "prompt_feedback", None)
        return str(pf or "")
    except Exception:
        return ""


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
            text = _extract_text(resp)
            if not text:
                return "(빈 응답)"
            return text
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
            text = _extract_text(resp)
            if not text or text.startswith("(빈 응답"):
                log.warning(f"Gemini JSON 빈 응답: {text}")
                return {}
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

    def generate_json_debug(self, prompt: str, temperature: float = 0.3,
                            max_tokens: int = 1500) -> dict:
        """JSON 생성 결과와 실패 원인을 함께 반환.

        기존 generate_json은 다른 기능이 의존하므로 그대로 두고,
        임원 요약처럼 실패 원인 표시가 필요한 곳에서만 이 메서드를 사용합니다.
        """
        text = ""
        finish_reason = ""
        prompt_feedback = ""
        try:
            cfg = _build_config(self.system_instruction, temperature, max_tokens, json_mode=True)
            resp = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=cfg,
            )
            finish_reason = _response_finish_reason(resp)
            prompt_feedback = _response_prompt_feedback(resp)
            text = _extract_text(resp)
            if not text or text.startswith("(빈 응답"):
                return {
                    "ok": False,
                    "data": {},
                    "error": f"Gemini 빈 응답: {text or finish_reason or prompt_feedback or '원인 미상'}",
                    "finish_reason": finish_reason,
                    "prompt_feedback": prompt_feedback,
                    "raw_preview": text[:800],
                }
            try:
                return {
                    "ok": True,
                    "data": json.loads(text),
                    "error": "",
                    "finish_reason": finish_reason,
                    "prompt_feedback": prompt_feedback,
                    "raw_preview": text[:800],
                }
            except json.JSONDecodeError as e:
                try:
                    start = text.find("{")
                    end = text.rfind("}") + 1
                    if start != -1 and end > start:
                        return {
                            "ok": True,
                            "data": json.loads(text[start:end]),
                            "error": "",
                            "finish_reason": finish_reason,
                            "prompt_feedback": prompt_feedback,
                            "raw_preview": text[:800],
                        }
                except Exception:
                    pass
                reason = f"Gemini JSON 파싱 실패: {e}"
                if finish_reason:
                    reason += f" / finish_reason={finish_reason}"
                return {
                    "ok": False,
                    "data": {},
                    "error": reason,
                    "finish_reason": finish_reason,
                    "prompt_feedback": prompt_feedback,
                    "raw_preview": text[:800],
                }
        except Exception as e:
            return {
                "ok": False,
                "data": {},
                "error": f"Gemini API 호출 실패 ({self.model_name}): {e}",
                "finish_reason": finish_reason,
                "prompt_feedback": prompt_feedback,
                "raw_preview": text[:800],
            }

    # ---------- 멀티모달 (이미지) ----------
    def generate_with_images(self, prompt: str, images: List[Image.Image],
                             temperature: float = 0.6, max_tokens: int = 1000) -> str:
        try:
            cfg = _build_config(self.system_instruction, temperature, max_tokens, json_mode=False)
            parts = [prompt] + list(images or [])
            resp = self.client.models.generate_content(
                model=self.model_name,
                contents=parts,
                config=cfg,
            )
            text = _extract_text(resp)
            return text or "(빈 응답)"
        except Exception as e:
            log.error(f"Gemini vision 실패 ({self.model_name}): {e}")
            return f"(이미지 분석 실패: {e})"
