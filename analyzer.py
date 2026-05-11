"""
AEO 콘텐츠 분석기 (5개 축 정렬).
크롤링 결과 + 첨부파일 텍스트/이미지를 받아 Gemini로 5개 축 진단을 수행.
"""

import json
import logging
from typing import Dict, Any, List, Optional

from PIL import Image
from gemini_llm import GeminiLLM

log = logging.getLogger(__name__)


ANALYZE_PROMPT = """당신은 AEO(Answer Engine Optimization) + AI Commerce 진단 전문가입니다.
AI Agent가
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

[브랜드 적합도 공식 기준]
브랜드 적합도는 "페이지 내부 콘텐츠끼리 일관적인가"가 아니라,
분석 대상 콘텐츠가 Samsung Galaxy 또는 Apple의 공식 브랜드 아이덴티티와 브랜드 페르소나에 얼마나 맞는지를 평가합니다.
실제 검색량, 구매 의향, 브랜드 선호도, 캠페인 성과는 반영하지 마세요.

점수 가중치:
- 공식 브랜드 아이덴티티 매칭: 15점
- 브랜드 페르소나 적합도: 70점  ← 페르소나 가중치를 압도적으로 크게 둡니다
- 근거 명확성: 15점

Samsung Galaxy 공식 아이덴티티 기준:
- Openness / Open always wins: 열린 태도, 도전, 다양한 사용자와 상황을 포용하는 메시지
- 사람 중심 혁신: 기술이 사용자의 실제 문제를 해결하고 삶을 개선하는가
- 진취적 혁신: AI, 카메라, 생산성, 새로운 폼팩터/연결 경험이 의미 있는 혁신으로 설명되는가
- Galaxy 생태계 / 연결성: 폰, 워치, 태블릿, PC 등 기기간 연결 경험이 드러나는가
- 책임 있는 기술 / 지속가능성: 보편적이고 유익하며 지속 가능한 기술 방향과 맞는가

Samsung Galaxy 브랜드 페르소나 기준:
- Open Explorer: 새로운 가능성, 열린 태도, 자기표현, 연결을 중시하는 사용자
- Practical Innovator: AI, 카메라, 생산성 기능이 실제 생활 문제를 해결하길 기대하는 사용자
- Connected Multitasker: 여러 Galaxy 기기를 넘나드는 끊김 없는 경험을 원하는 사용자
- Creator / Story Sharer: 사진, 영상, AI 편집, 공유로 자신의 관점과 여정을 표현하는 사용자
- Responsible Tech User: 지속가능성, 신뢰, 장기적 가치를 함께 보는 사용자

Apple 공식 아이덴티티 기준:
- Privacy-first: 개인정보 보호와 사용자 통제권이 기본값으로 설명되는가
- Empowering tools: 기술이 사용자를 더 창의적이고 생산적으로 만드는가
- Accessibility / inclusive design: 누구나 쉽게 쓸 수 있는 접근성, 직관성, 사용 편의성이 드러나는가
- Environment / durable products: 환경 책임, 오래 쓰는 제품, 재활용/탄소중립 방향과 맞는가
- Integrated premium experience: 하드웨어·소프트웨어·서비스가 하나의 완성된 경험처럼 설명되는가

Apple 브랜드 페르소나 기준:
- Privacy-first User: 개인정보 보호, 데이터 통제권, 안전한 AI/개인화 경험을 중시하는 사용자
- Creative Professional: 창작, 생산성, 콘텐츠 제작, 몰입도 높은 작업 경험을 중시하는 사용자
- Effortless Premium Seeker: 직관적이고 완성도 높은 프리미엄 경험을 기대하는 사용자
- Accessibility-minded User: 접근성, 포용성, 사용 편의성을 중요하게 보는 사용자
- Planet-conscious Buyer: 환경 책임, 오래 쓰는 제품, 재활용 소재, 탄소중립 방향을 고려하는 사용자

[브랜드 적합도 판정 규칙]
1. URL/제목/본문/브랜드명으로 Samsung Galaxy인지 Apple인지 먼저 추정하세요.
2. Samsung Galaxy 또는 Apple이 아니면 brand_fit.status="unavailable"로 두고 score=0을 반환하세요.
3. 브랜드 페르소나 적합도는 70점으로 가장 크게 반영하세요. 콘텐츠가 어떤 페르소나에게 잘 맞고, 어떤 페르소나에는 부족한지 반드시 판단하세요.
4. 브랜드 적합도 근거는 제공된 콘텐츠에서 확인 가능한 표현/구조/메시지에 근거하세요. 공식 기준 자체는 위의 기준을 사용하되, 콘텐츠에 없는 사실을 근거처럼 만들지 마세요.

다음 JSON으로만 답변하세요. 5개 축(데이터/콘텐츠/AI Commerce/UX/브랜드 메시지 적합도)에 맞춰 정렬하세요. 브랜드 메시지 적합도는 다른 4개 축과 동일 레벨의 진단 축입니다.

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
  "brand_fit": {{
    "status": "ok|unavailable",
    "target_brand": "Samsung Galaxy|Apple|Unknown",
    "score": 0-100,
    "score_components": {{
      "official_identity_match": 0-15,
      "brand_persona_fit": 0-70,
      "evidence_clarity": 0-15
    }},
    "persona_fit": {{
      "score": 0-70,
      "matched_personas": ["잘 맞는 브랜드 페르소나와 이유"],
      "weak_personas": ["덜 맞는 브랜드 페르소나와 이유"]
    }},
    "reason": "브랜드 적합도 점수 근거 한 줄",
    "findings": ["공식 브랜드 아이덴티티/브랜드 페르소나와 맞는 근거"],
    "gaps": ["공식 브랜드 아이덴티티/브랜드 페르소나 관점에서 부족한 요소"],
    "actions": ["브랜드 적합도 개선을 위한 구체 액션 2-3개"],
    "note": "공식 브랜드 아이덴티티와 브랜드 페르소나 기준. 실제 검색량·구매 의향·브랜드 선호도는 미포함"
  }},
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
    "UX": {
      "score": 0-100,
      "findings": ["정보 구조·가독성 측면"],
      "gaps": ["부족한 점"],
      "actions": ["구체 액션 2-3개"]
    },
    "브랜드 메시지 적합도": {
      "score": 0-100,
      "findings": ["Samsung Galaxy/Apple 공식 브랜드 아이덴티티·브랜드 페르소나와 맞는 근거"],
      "gaps": ["브랜드 페르소나 관점에서 부족한 점"],
      "actions": ["브랜드 메시지 적합도 개선 액션 2-3개"]
    }
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
                extra_images, temperature=0.3, max_tokens=3800,
            )
            try:
                start = text.find("{")
                end = text.rfind("}") + 1
                parsed = json.loads(text[start:end]) if start != -1 else {}
            except Exception:
                parsed = {}
        else:
            parsed = llm.generate_json(prompt, temperature=0.3, max_tokens=3800)

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
    parsed.setdefault("brand_fit", {})
    if not isinstance(parsed["brand_fit"], dict):
        parsed["brand_fit"] = {}
    parsed["brand_fit"].setdefault("status", "ok")
    parsed["brand_fit"].setdefault("target_brand", "Unknown")
    parsed["brand_fit"].setdefault("score", 0)
    parsed["brand_fit"].setdefault("score_components", {})
    if not isinstance(parsed["brand_fit"].get("score_components"), dict):
        parsed["brand_fit"]["score_components"] = {}
    parsed["brand_fit"]["score_components"].setdefault("official_identity_match", 0)
    parsed["brand_fit"]["score_components"].setdefault("brand_persona_fit", 0)
    parsed["brand_fit"]["score_components"].setdefault("evidence_clarity", 0)
    parsed["brand_fit"].setdefault("persona_fit", {})
    if not isinstance(parsed["brand_fit"].get("persona_fit"), dict):
        parsed["brand_fit"]["persona_fit"] = {}
    parsed["brand_fit"]["persona_fit"].setdefault("score", parsed["brand_fit"]["score_components"].get("brand_persona_fit", 0))
    parsed["brand_fit"]["persona_fit"].setdefault("matched_personas", [])
    parsed["brand_fit"]["persona_fit"].setdefault("weak_personas", [])
    parsed["brand_fit"].setdefault("reason", "")
    parsed["brand_fit"].setdefault("findings", [])
    parsed["brand_fit"].setdefault("gaps", [])
    parsed["brand_fit"].setdefault("actions", [])
    parsed["brand_fit"].setdefault(
        "note",
        "공식 브랜드 아이덴티티와 브랜드 페르소나 기준. 실제 검색량·구매 의향·브랜드 선호도는 미포함"
    )
    parsed.setdefault("schema_gaps", [])
    parsed.setdefault("copy_suggestions", [])
    parsed.setdefault("visual_suggestions", [])
    parsed.setdefault("by_dimension", {})

    empty_dim = {"score": 0, "findings": [], "gaps": [], "actions": []}
    for ax in ["데이터", "콘텐츠", "AI Commerce", "UX", "브랜드 메시지 적합도"]:
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

    brand_axis = parsed["by_dimension"].get("브랜드 메시지 적합도", {})
    fit = parsed.get("brand_fit", {})
    if isinstance(fit, dict):
        brand_axis["score"] = int(fit.get("score") or brand_axis.get("score") or 0)
        brand_axis["findings"] = fit.get("findings") or brand_axis.get("findings") or []
        brand_axis["gaps"] = fit.get("gaps") or brand_axis.get("gaps") or []
        brand_axis["actions"] = fit.get("actions") or brand_axis.get("actions") or []
        parsed["by_dimension"]["브랜드 메시지 적합도"] = brand_axis

    parsed["technical_checks"] = aeo_checks
    return parsed


def _empty(reason: str = "") -> Dict[str, Any]:
    return {
        "summary": "", "topic": "", "brands": [], "target_audience": "",
        "consumer_perception": "", "likely_questions": [],
        "aeo_score": 0, "aeo_reason": reason,
        "key_insights": [],
        "brand_fit": {
            "status": "unavailable",
            "target_brand": "Unknown",
            "score": 0,
            "score_components": {
                "official_identity_match": 0,
                "brand_persona_fit": 0,
                "evidence_clarity": 0,
            },
            "persona_fit": {
                "score": 0,
                "matched_personas": [],
                "weak_personas": [],
            },
            "reason": reason or "브랜드 적합도 분석을 생성하지 못했습니다.",
            "findings": [],
            "gaps": [],
            "actions": [],
            "note": "공식 브랜드 아이덴티티와 브랜드 페르소나 기준. 실제 검색량·구매 의향·브랜드 선호도는 미포함",
        },
        "schema_gaps": [], "copy_suggestions": [], "visual_suggestions": [],
        "by_dimension": {
            "데이터": {"score": 0, "findings": [], "gaps": [], "actions": []},
            "콘텐츠": {"score": 0, "findings": [], "gaps": [], "actions": []},
            "AI Commerce": {"score": 0, "findings": [], "gaps": [], "actions": []},
            "UX": {"score": 0, "findings": [], "gaps": [], "actions": []},
            "브랜드 메시지 적합도": {"score": 0, "findings": [], "gaps": [], "actions": []},
        },
        "technical_checks": {},
    }
