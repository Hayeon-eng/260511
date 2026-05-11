"""
AEO 콘텐츠 분석기 (4축 정렬).
크롤링 결과 + 첨부파일 텍스트/이미지를 받아 Gemini로 4축 진단을 수행.
"""

import json
import logging
from typing import Dict, Any, List, Optional

from PIL import Image
from gemini_llm import GeminiLLM

log = logging.getLogger(__name__)


ANALYZE_PROMPT = """당신은 AEO(Answer Engine Optimization) + AI Commerce 진단 전문가입니다.
LLM·AI 검색엔진(ChatGPT, Perplexity, Gemini, Google AI Overview)·AI Shopping(Google Shopping, ChatGPT Shopping)이
이 콘텐츠를 얼마나 잘 인용·추천할지를 진단합니다.

[크롤링된 콘텐츠]
URL: {url}
제목: {title}
메타 설명: {meta_desc}
H1: {h1}
H2 일부: {h2}
본문(요약): {body}
구조화 데이터 타입: {schema_types}
JSON-LD/Schema 존재: {has_schema}
FAQPage 스키마: {has_faq}
Product 스키마: {has_product}
이미지 alt 커버리지: {alt_coverage}%
OG 태그: {og}

[추가 콘텐츠 - 첨부파일에서 추출]
{extra_content}

다음 JSON으로만 답변하세요. 4개 축(데이터/콘텐츠/AI Commerce/UX)에 맞춰 정렬하세요.

{{
  "summary": "콘텐츠 한 줄 요약 (60자 이내)",
  "topic": "핵심 주제 (15자 이내)",
  "brands": ["언급된 브랜드"],
  "target_audience": "타겟 고객 묘사 한 줄",
  "consumer_perception": "이 콘텐츠를 본 일반 소비자의 첫인상·감정 (2-3문장)",
  "likely_questions": ["AI에 사용자가 물어볼 만한 질문 5개 (이 콘텐츠가 답변 후보가 될 수 있는 질문)"],
  "aeo_score": 0-100,
  "aeo_reason": "점수 근거 한 줄",
  "key_insights": ["핵심 인사이트 3-5개 (축 구분 없이)"],
  "by_dimension": {{
    "데이터": {{
      "score": 0-100,
      "findings": ["발견된 사실 (데이터/스키마 측면)"],
      "gaps": ["부족한 점"],
      "actions": ["구체 액션 2-3개"]
    }},
    "콘텐츠": {{
      "score": 0-100,
      "findings": ["카피·메시지 측면 발견"],
      "gaps": ["부족한 점"],
      "actions": ["구체 액션 2-3개"]
    }},
    "AI Commerce": {{
      "score": 0-100,
      "findings": ["AI Agent의 제품 추천 답변에 인용될 가능성 측면"],
      "gaps": ["부족한 점 (Product/Offer/Review 스키마 등)"],
      "actions": ["구체 액션 2-3개"]
    }},
    "UX": {{
      "score": 0-100,
      "findings": ["정보 구조·가독성 측면"],
      "gaps": ["부족한 점"],
      "actions": ["구체 액션 2-3개"]
    }}
  }},
  "schema_gaps": ["전반적으로 부족한 스키마 종류"],
  "copy_suggestions": ["카피 개선안 2-3개"],
  "visual_suggestions": ["비주얼/이미지 제언 2-3개"]
}}
"""


def analyze_content(crawl_result: Dict[str, Any],
                    extra_texts: Optional[List[str]] = None,
                    extra_images: Optional[List[Image.Image]] = None) -> Dict[str, Any]:
    try:
        if not crawl_result or not crawl_result.get("ok"):
            return _empty(crawl_result.get("error", "크롤링 실패") if crawl_result else "결과 없음")

        schemas = crawl_result.get("schemas", [])
        schema_types = [s.get("@type", "Unknown") for s in schemas if isinstance(s, dict)]
        has_product = any("Product" in str(t) for t in schema_types)
        aeo_checks = crawl_result.get("aeo_checks", {})

        headings = crawl_result.get("headings", {})
        h1 = ", ".join(headings.get("h1", []))[:200]
        h2 = ", ".join(headings.get("h2", [])[:8])[:300]

        extra_content = ""
        if extra_texts:
            extra_content = "\n\n---\n\n".join(extra_texts)[:3000]

        prompt = ANALYZE_PROMPT.format(
            url=crawl_result.get("url", ""),
            title=crawl_result.get("title", ""),
            meta_desc=crawl_result.get("meta_description", ""),
            h1=h1,
            h2=h2,
            body=(crawl_result.get("text") or "")[:2500],
            schema_types=", ".join(set(map(str, schema_types[:10]))) or "없음",
            has_schema="있음" if aeo_checks.get("has_schema") else "없음",
            has_faq="있음" if aeo_checks.get("has_faq_schema") else "없음",
            has_product="있음" if has_product else "없음",
            alt_coverage=aeo_checks.get("image_alt_coverage", 0),
            og=json.dumps(crawl_result.get("og", {}), ensure_ascii=False)[:300],
            extra_content=extra_content or "(없음)",
        )

        llm = GeminiLLM(
            system_instruction="당신은 AEO·AI Commerce 진단에 능숙한 컨설턴트입니다. 항상 JSON으로만 응답합니다."
        )

        if extra_images:
            text = llm.generate_with_images(
                prompt + "\n\n첨부된 이미지도 함께 분석하여 visual_suggestions에 반영하세요.",
                extra_images, temperature=0.3, max_tokens=2500,
            )
            try:
                start = text.find("{")
                end = text.rfind("}") + 1
                parsed = json.loads(text[start:end]) if start != -1 else {}
            except Exception:
                parsed = {}
        else:
            parsed = llm.generate_json(prompt, temperature=0.3, max_tokens=2500)

        if not parsed:
            return _empty("LLM 응답 파싱 실패")

        return _normalize(parsed, aeo_checks)
    except Exception as e:
        log.error(f"analyze_content 실패: {e}")
        return _empty(str(e))


def _normalize(parsed: Dict[str, Any], aeo_checks: Dict[str, Any]) -> Dict[str, Any]:
    parsed.setdefault("summary", "")
    parsed.setdefault("topic", "")
    parsed.setdefault("brands", [])
    parsed.setdefault("target_audience", "")
    parsed.setdefault("consumer_perception", "")
    parsed.setdefault("likely_questions", [])
    parsed.setdefault("aeo_score", 0)
    parsed.setdefault("aeo_reason", "")
    parsed.setdefault("key_insights", [])
    parsed.setdefault("schema_gaps", [])
    parsed.setdefault("copy_suggestions", [])
    parsed.setdefault("visual_suggestions", [])
    parsed.setdefault("by_dimension", {})

    empty_dim = {"score": 0, "findings": [], "gaps": [], "actions": []}
    for ax in ["데이터", "콘텐츠", "AI Commerce", "UX"]:
        d = parsed["by_dimension"].get(ax, {})
        if not isinstance(d, dict):
            d = empty_dim.copy()
        for k in ("score", "findings", "gaps", "actions"):
            d.setdefault(k, empty_dim[k])
        parsed["by_dimension"][ax] = d

    if not aeo_checks.get("has_schema"):
        existing_gaps = set(parsed["schema_gaps"])
        for g in ("Organization", "WebPage", "BreadcrumbList"):
            existing_gaps.add(g)
        parsed["schema_gaps"] = list(existing_gaps)
    if not aeo_checks.get("has_faq_schema") and "FAQPage" not in parsed["schema_gaps"]:
        parsed["schema_gaps"].append("FAQPage")

    parsed["technical_checks"] = aeo_checks
    return parsed


def _empty(reason: str = "") -> Dict[str, Any]:
    return {
        "summary": "", "topic": "", "brands": [], "target_audience": "",
        "consumer_perception": "", "likely_questions": [],
        "aeo_score": 0, "aeo_reason": reason,
        "key_insights": [], "schema_gaps": [], "copy_suggestions": [], "visual_suggestions": [],
        "by_dimension": {
            "데이터": {"score": 0, "findings": [], "gaps": [], "actions": []},
            "콘텐츠": {"score": 0, "findings": [], "gaps": [], "actions": []},
            "AI Commerce": {"score": 0, "findings": [], "gaps": [], "actions": []},
            "UX": {"score": 0, "findings": [], "gaps": [], "actions": []},
        },
        "technical_checks": {},
    }
