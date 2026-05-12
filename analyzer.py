"""AEO / AI Commerce analyzer.
- Frontend JSON shape is kept.
- LLM is used for wording only; core scores are corrected by deterministic signals.
- If LLM JSON parsing fails, returns a rule-based analysis instead of failing.
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional

from PIL import Image
from gemini_llm import GeminiLLM

log = logging.getLogger(__name__)

AXES = ["데이터", "콘텐츠", "AI Commerce", "UX", "브랜드 메시지 적합도"]


def analyze_content(
    crawl_result: Dict[str, Any],
    extra_texts: Optional[List[str]] = None,
    extra_images: Optional[List[Image.Image]] = None,
) -> Dict[str, Any]:
    try:
        if not crawl_result or not crawl_result.get("ok"):
            reason = crawl_result.get("error", "크롤링 실패") if crawl_result else "결과 없음"
            return _empty(reason)

        schema_types = _schema_types(crawl_result.get("schemas", []))
        aeo_checks = dict(crawl_result.get("aeo_checks", {}) or {})
        aeo_checks["schema_types"] = schema_types
        aeo_checks["has_product_schema"] = _has_type(schema_types, "Product")
        aeo_checks["has_video_schema"] = _has_type(schema_types, "VideoObject")
        aeo_checks["has_article_schema"] = any(_has_type(schema_types, t) for t in ["Article", "NewsArticle", "BlogPosting"])
        aeo_checks["has_howto_schema"] = _has_type(schema_types, "HowTo")
        aeo_checks["has_faq_schema"] = bool(aeo_checks.get("has_faq_schema") or _has_type(schema_types, "FAQPage") or _has_type(schema_types, "Question"))
        aeo_checks["has_schema"] = bool(aeo_checks.get("has_schema") or schema_types)

        scores, commerce = _score_from_crawl(crawl_result, aeo_checks)
        prompt = _build_prompt(crawl_result, aeo_checks, scores, commerce, extra_texts)
        parsed = _call_llm(prompt, extra_images)
        if not parsed:
            parsed = _rule_based_result(crawl_result, aeo_checks, scores, commerce)
        return _normalize(parsed, crawl_result, aeo_checks, scores, commerce)
    except Exception as e:
        log.exception("analyze_content failed")
        return _empty(str(e))


def _call_llm(prompt: str, images: Optional[List[Image.Image]]) -> Dict[str, Any]:
    try:
        llm = GeminiLLM(
            system_instruction="AEO/AI Commerce consultant. Return valid JSON only. No markdown."
        )
        if images:
            text = llm.generate_with_images(prompt, images, temperature=0.2, max_tokens=2600)
            return _parse_json_text(text)
        if hasattr(llm, "generate_json_debug"):
            debug = llm.generate_json_debug(prompt, temperature=0.2, max_tokens=2600)
            if debug.get("ok") and isinstance(debug.get("data"), dict):
                return debug["data"]
            log.warning("LLM JSON failed: %s", debug.get("error"))
            return _parse_json_text(debug.get("raw_preview", ""))
        result = llm.generate_json(prompt, temperature=0.2, max_tokens=2600)
        return result if isinstance(result, dict) else {}
    except Exception as e:
        log.warning("LLM call failed: %s", e)
        return {}


def _build_prompt(crawl: Dict[str, Any], checks: Dict[str, Any], scores: Dict[str, int], commerce: Dict[str, Any], extra_texts: Optional[List[str]]) -> str:
    headings = crawl.get("headings", {}) or {}
    payload = {
        "url": crawl.get("url", ""),
        "title": crawl.get("title", ""),
        "meta_description": crawl.get("meta_description", ""),
        "h1": (headings.get("h1") or [])[:5],
        "h2": (headings.get("h2") or [])[:8],
        "body": (crawl.get("text") or "")[:2200],
        "schema_types": checks.get("schema_types", []),
        "checks": {
            "has_schema": checks.get("has_schema", False),
            "has_faq_schema": checks.get("has_faq_schema", False),
            "has_product_schema": checks.get("has_product_schema", False),
            "has_video_schema": checks.get("has_video_schema", False),
            "has_article_schema": checks.get("has_article_schema", False),
            "has_howto_schema": checks.get("has_howto_schema", False),
            "body_length": checks.get("body_length", len(crawl.get("text") or "")),
        },
        "deterministic_scores": scores,
        "commerce_metrics": commerce,
        "extra_content": "\n---\n".join(extra_texts or [])[:1800] if extra_texts else "",
    }
    return (
        "Analyze the content for AEO and AI Commerce in Korean. "
        "Use the deterministic scores as the source of truth for numeric scores. "
        "Do not say a schema is missing when it appears in schema_types. "
        "Do not mention image alt. Return JSON only with these keys: "
        "summary, topic, brands, target_audience, consumer_perception, likely_questions, "
        "aeo_score, aeo_reason, key_insights, brand_fit, by_dimension, schema_gaps, copy_suggestions, visual_suggestions. "
        "by_dimension must contain 데이터, 콘텐츠, AI Commerce, UX, 브랜드 메시지 적합도. "
        "Each dimension needs score, findings, gaps, actions. "
        "brand_fit needs status, target_brand, score, score_components, persona_fit, reason, findings, gaps, actions, note.\n\n"
        "INPUT:\n" + json.dumps(payload, ensure_ascii=False)
    )


def _parse_json_text(text: str) -> Dict[str, Any]:
    if not text:
        return {}
    text = text.strip()
    text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.I | re.M).strip()
    try:
        obj = json.loads(text)
        return obj if isinstance(obj, dict) else {}
    except Exception:
        pass
    start, end = text.find("{"), text.rfind("}")
    if start >= 0 and end > start:
        try:
            obj = json.loads(text[start : end + 1])
            return obj if isinstance(obj, dict) else {}
        except Exception:
            return {}
    return {}


def _schema_types(items: Any) -> List[str]:
    found: List[str] = []

    def walk(x: Any):
        if isinstance(x, list):
            for v in x:
                walk(v)
        elif isinstance(x, dict):
            t = x.get("@type") or x.get("type")
            if isinstance(t, list):
                found.extend(str(v) for v in t if v)
            elif t:
                found.append(str(t))
            for key in ("@graph", "mainEntity", "itemListElement", "hasPart", "isPartOf", "offers", "aggregateRating", "review", "subjectOf"):
                if key in x:
                    walk(x[key])

    walk(items)
    clean: List[str] = []
    for t in found:
        name = t.split("/")[-1].split("#")[-1]
        if name and name not in clean:
            clean.append(name)
    return clean


def _has_type(types: List[str], name: str) -> bool:
    return any(name.lower() == str(t).lower() or name.lower() in str(t).lower() for t in types)


def _schema_has_key(items: Any, names: List[str]) -> bool:
    names_l = {n.lower() for n in names}

    def walk(x: Any) -> bool:
        if isinstance(x, list):
            return any(walk(v) for v in x)
        if isinstance(x, dict):
            for k, v in x.items():
                if str(k).lower() in names_l:
                    return True
                if walk(v):
                    return True
        return False

    return walk(items)


def _count_schema_keys(items: Any, names: List[str]) -> int:
    names_l = {n.lower() for n in names}
    count = 0

    def walk(x: Any):
        nonlocal count
        if isinstance(x, list):
            for v in x:
                walk(v)
        elif isinstance(x, dict):
            for k, v in x.items():
                if str(k).lower() in names_l and v not in (None, "", []):
                    count += 1
                walk(v)

    walk(items)
    return count


def _score_from_crawl(crawl: Dict[str, Any], checks: Dict[str, Any]) -> (Dict[str, int], Dict[str, Any]):
    schemas = crawl.get("schemas", []) or []
    types = checks.get("schema_types", []) or []
    text = " ".join([
        crawl.get("title", ""),
        crawl.get("meta_description", ""),
        crawl.get("text", ""),
    ]).lower()
    headings = crawl.get("headings", {}) or {}
    h_count = len(headings.get("h1") or []) + len(headings.get("h2") or [])
    body_len = int(checks.get("body_length") or len(crawl.get("text") or ""))

    offer_keys = _count_schema_keys(schemas, ["offers", "price", "priceCurrency", "availability", "url", "seller", "priceValidUntil"])
    review_keys = _count_schema_keys(schemas, ["aggregateRating", "review", "ratingValue", "reviewCount", "bestRating"])
    id_keys = _count_schema_keys(schemas, ["sku", "gtin", "gtin13", "gtin14", "mpn", "model", "brand", "color"])
    spec_hits = len(re.findall(r"ai|camera|display|battery|storage|processor|chip|spec|compare|price|리뷰|가격|비교|스펙|배터리|카메라|구매|재고", text))
    buy_hits = len(re.findall(r"buy|shop|trade.?in|where to buy|price|availability|구매|가격|보상판매|재고|리뷰|평점", text))
    has_product = _has_type(types, "Product")
    has_offer = offer_keys > 0 or _schema_has_key(schemas, ["Offer", "offers"])
    has_review = review_keys > 0

    commerce = {
        "has_product_schema": has_product,
        "has_offer_or_price": has_offer,
        "has_review_or_rating": has_review,
        "offer_field_count": offer_keys,
        "review_field_count": review_keys,
        "identifier_field_count": id_keys,
        "spec_signal_count": min(spec_hits, 30),
        "buying_signal_count": min(buy_hits, 30),
    }

    data = 0
    data += 10 if crawl.get("title") else 0
    data += 10 if crawl.get("meta_description") else 0
    data += 10 if headings.get("h1") else 0
    data += 10 if crawl.get("og") else 0
    data += 25 if checks.get("has_schema") else 0
    data += 10 if checks.get("has_faq_schema") else 0
    data += 15 if any(checks.get(k) for k in ["has_product_schema", "has_video_schema", "has_article_schema", "has_howto_schema"]) else 0
    data += 10 if body_len >= 800 else 5 if body_len >= 250 else 0

    content = 35
    content += 15 if body_len >= 1200 else 8 if body_len >= 500 else 0
    content += min(15, h_count * 3)
    content += 15 if spec_hits >= 8 else 8 if spec_hits >= 3 else 0
    content += 10 if re.search(r"how|why|what|which|방법|왜|무엇|비교|추천", text) else 0
    content += 10 if crawl.get("meta_description") else 0

    ai = 10
    ai += 25 if has_product else 0
    ai += min(20, offer_keys * 5)
    ai += min(15, review_keys * 5)
    ai += min(10, id_keys * 3)
    ai += 10 if spec_hits >= 8 else 5 if spec_hits >= 3 else 0
    ai += 5 if checks.get("has_faq_schema") else 0
    ai += 5 if buy_hits >= 5 else 0
    if not has_product and not has_offer and not has_review:
        ai = min(ai, 58)

    ux = 35
    ux += min(20, h_count * 4)
    ux += 15 if body_len >= 1000 else 8 if body_len >= 400 else 0
    ux += 10 if checks.get("has_faq_schema") else 0
    ux += 10 if crawl.get("og") else 0
    ux += 10 if re.search(r"compare|spec|faq|learn more|비교|스펙|자주 묻는|구매", text) else 0

    return {
        "데이터": _clamp(data),
        "콘텐츠": _clamp(content),
        "AI Commerce": _clamp(ai),
        "UX": _clamp(ux),
    }, commerce


def _normalize(parsed: Dict[str, Any], crawl: Dict[str, Any], checks: Dict[str, Any], scores: Dict[str, int], commerce: Dict[str, Any]) -> Dict[str, Any]:
    rb = _rule_based_result(crawl, checks, scores, commerce)
    for k, v in rb.items():
        parsed.setdefault(k, v)

    parsed["brands"] = _as_list(parsed.get("brands"))
    parsed["likely_questions"] = _as_list(parsed.get("likely_questions"))[:5]
    parsed["key_insights"] = _filter_texts(_as_list(parsed.get("key_insights")))[:5]
    parsed["schema_gaps"] = _filter_schema_gaps(_as_list(parsed.get("schema_gaps")) + rb.get("schema_gaps", []), checks)
    parsed["copy_suggestions"] = _filter_texts(_as_list(parsed.get("copy_suggestions")))[:3]
    parsed["visual_suggestions"] = _filter_texts(_as_list(parsed.get("visual_suggestions")))[:3]

    if not isinstance(parsed.get("brand_fit"), dict):
        parsed["brand_fit"] = rb["brand_fit"]
    parsed["brand_fit"] = _normalize_brand_fit(parsed["brand_fit"], crawl)

    if not isinstance(parsed.get("by_dimension"), dict):
        parsed["by_dimension"] = {}
    for ax in AXES:
        d = parsed["by_dimension"].get(ax, {})
        if not isinstance(d, dict):
            d = {}
        base = rb["by_dimension"][ax]
        d["score"] = _clamp(scores.get(ax, d.get("score", base["score"]))) if ax != "브랜드 메시지 적합도" else _clamp(parsed["brand_fit"].get("score", base["score"]))
        d["findings"] = _filter_texts(_as_list(d.get("findings")) or base["findings"])[:4]
        d["gaps"] = _filter_texts(_as_list(d.get("gaps")) or base["gaps"])[:4]
        d["actions"] = _filter_texts(_as_list(d.get("actions")) or base["actions"])[:4]
        parsed["by_dimension"][ax] = d

    # Recalculate total so same-looking official pages can still differ by commerce completeness.
    weights = {"데이터": 0.23, "콘텐츠": 0.22, "AI Commerce": 0.30, "UX": 0.15, "브랜드 메시지 적합도": 0.10}
    total = sum(parsed["by_dimension"][ax]["score"] * w for ax, w in weights.items())
    parsed["aeo_score"] = _clamp(total)
    parsed["aeo_reason"] = parsed.get("aeo_reason") or "기술 신호와 AI Commerce 필드 완성도를 기준으로 산정했습니다."
    parsed["technical_checks"] = checks
    parsed["technical_checks"]["commerce_metrics"] = commerce
    return parsed


def _rule_based_result(crawl: Dict[str, Any], checks: Dict[str, Any], scores: Dict[str, int], commerce: Dict[str, Any]) -> Dict[str, Any]:
    title = crawl.get("title") or "분석 대상 콘텐츠"
    brand = _infer_brand(crawl)
    brand_score = 78 if brand != "Unknown" else 0
    schema_gaps = _schema_gaps(checks, commerce)
    ai_gaps = _commerce_gaps(commerce)
    ai_actions = _commerce_actions(commerce)
    data_findings = ["구조화 데이터 감지: " + ", ".join(checks.get("schema_types", [])[:8])] if checks.get("schema_types") else ["감지된 구조화 데이터가 없습니다."]
    if checks.get("has_video_schema"):
        data_findings.append("VideoObject 스키마가 감지되어 영상 콘텐츠 신호는 존재합니다.")

    result = {
        "summary": str(title)[:60],
        "topic": str(title)[:15],
        "brands": [brand] if brand != "Unknown" else [],
        "target_audience": "제품 정보를 비교하고 구매 판단을 하려는 사용자",
        "consumer_perception": "핵심 메시지는 파악할 수 있으나, AI 추천 답변에 필요한 가격·리뷰·비교 데이터는 별도로 확인해야 합니다.",
        "likely_questions": ["이 제품의 핵심 장점은?", "가격과 구매 옵션은?", "경쟁 제품과 차이는?", "리뷰 평점은?", "어떤 사용자에게 맞나?"],
        "aeo_score": 0,
        "aeo_reason": "기술 신호와 AI Commerce 필드 완성도를 기준으로 산정했습니다.",
        "key_insights": [
            f"AI Commerce 점수는 Product/Offer/Review 신호 기준 {scores.get('AI Commerce', 0)}점입니다.",
            "브랜드 메시지와 AI 추천 가능 데이터는 분리해서 봐야 합니다.",
        ],
        "brand_fit": {
            "status": "ok" if brand != "Unknown" else "unavailable",
            "target_brand": brand,
            "score": brand_score,
            "score_components": {"official_identity_match": min(15, brand_score // 7), "brand_persona_fit": min(70, brand_score), "evidence_clarity": 10 if brand != "Unknown" else 0},
            "persona_fit": {"score": min(70, brand_score), "matched_personas": [], "weak_personas": []},
            "reason": "콘텐츠 내 브랜드명과 제품 메시지를 기준으로 추정했습니다.",
            "findings": [],
            "gaps": [],
            "actions": ["브랜드 메시지와 구매 판단 데이터를 같은 페이지 흐름 안에서 연결하세요."],
            "note": "공식 브랜드 아이덴티티와 브랜드 페르소나 기준. 실제 검색량·구매 의향·브랜드 선호도는 미포함",
        },
        "by_dimension": {
            "데이터": {"score": scores.get("데이터", 0), "findings": data_findings, "gaps": schema_gaps[:4], "actions": ["누락된 Schema.org 타입과 필수 속성을 JSON-LD로 보강하세요."]},
            "콘텐츠": {"score": scores.get("콘텐츠", 0), "findings": ["본문 길이와 헤딩 구조를 기준으로 답변 후보성을 평가했습니다."], "gaps": ["구매 질문에 바로 답하는 문장과 비교형 문장이 부족할 수 있습니다."], "actions": ["가격·비교·추천 질문에 답하는 H2/H3와 짧은 답변 문단을 추가하세요."]},
            "AI Commerce": {"score": scores.get("AI Commerce", 0), "findings": _commerce_findings(commerce), "gaps": ai_gaps, "actions": ai_actions},
            "UX": {"score": scores.get("UX", 0), "findings": ["헤딩·본문·FAQ 신호로 정보 발견성을 평가했습니다."], "gaps": ["구매 판단 정보가 한 화면 안에서 구조적으로 묶이지 않으면 AI와 사용자가 모두 찾기 어렵습니다."], "actions": ["스펙·가격·구매 옵션·FAQ를 같은 의사결정 흐름으로 재배치하세요."]},
            "브랜드 메시지 적합도": {"score": brand_score, "findings": [], "gaps": [], "actions": ["브랜드 페르소나별 혜택 문장을 명확히 분리하세요."]},
        },
        "schema_gaps": schema_gaps,
        "copy_suggestions": ["AI가 그대로 인용할 수 있도록 혜택-근거-대상 사용자를 한 문장에 묶으세요."],
        "visual_suggestions": [],
    }
    return result


def _schema_gaps(checks: Dict[str, Any], commerce: Dict[str, Any]) -> List[str]:
    gaps: List[str] = []
    if not checks.get("has_schema"):
        gaps += ["Organization", "WebPage", "BreadcrumbList"]
    if not checks.get("has_faq_schema"):
        gaps.append("FAQPage")
    commerce_like = commerce.get("buying_signal_count", 0) >= 2 or commerce.get("spec_signal_count", 0) >= 4
    if commerce_like and not commerce.get("has_product_schema"):
        gaps.append("Product")
    if commerce.get("has_product_schema") and not commerce.get("has_offer_or_price"):
        gaps.append("Offer")
    if commerce.get("has_product_schema") and not commerce.get("has_review_or_rating"):
        gaps.append("Review/AggregateRating")
    return gaps


def _filter_schema_gaps(items: List[Any], checks: Dict[str, Any]) -> List[str]:
    types = checks.get("schema_types", []) or []
    out: List[str] = []
    for item in items:
        s = str(item).strip()
        if not s or "alt" in s.lower():
            continue
        if checks.get("has_video_schema") and "videoobject" in s.lower():
            continue
        if checks.get("has_product_schema") and s.lower() == "product":
            continue
        if checks.get("has_faq_schema") and "faq" in s.lower():
            continue
        if any(str(t).lower() == s.lower() for t in types):
            continue
        if s not in out:
            out.append(s)
    return out[:8]


def _commerce_findings(c: Dict[str, Any]) -> List[str]:
    out = []
    out.append("Product 스키마가 감지되었습니다." if c.get("has_product_schema") else "Product 스키마가 감지되지 않았습니다.")
    out.append("Offer/가격/재고 계열 필드가 감지되었습니다." if c.get("has_offer_or_price") else "Offer/가격/재고 계열 필드가 약합니다.")
    out.append("Review/AggregateRating 계열 필드가 감지되었습니다." if c.get("has_review_or_rating") else "Review/AggregateRating 계열 필드가 약합니다.")
    return out


def _commerce_gaps(c: Dict[str, Any]) -> List[str]:
    gaps = []
    if not c.get("has_product_schema"):
        gaps.append("AI 상품 추천 후보로 쓰일 Product 구조화 데이터가 부족합니다.")
    if not c.get("has_offer_or_price"):
        gaps.append("가격·재고·구매 가능 여부를 판단할 Offer 필드가 부족합니다.")
    if not c.get("has_review_or_rating"):
        gaps.append("리뷰·평점 신뢰 신호가 구조화되어 있지 않습니다.")
    if c.get("identifier_field_count", 0) < 2:
        gaps.append("SKU·모델명·GTIN 등 상품 식별 필드가 부족합니다.")
    if c.get("spec_signal_count", 0) < 4:
        gaps.append("AI가 비교 답변에 쓸 수 있는 스펙 신호가 부족합니다.")
    return gaps[:4] or ["핵심 커머스 구조는 감지되며, 세부 필드 완성도 점검이 필요합니다."]


def _commerce_actions(c: Dict[str, Any]) -> List[str]:
    actions = []
    if not c.get("has_product_schema"):
        actions.append("Product JSON-LD를 추가하고 brand, model, sku, description을 채우세요.")
    if not c.get("has_offer_or_price"):
        actions.append("Offer에 price, priceCurrency, availability, seller, url을 넣으세요.")
    if not c.get("has_review_or_rating"):
        actions.append("가능하면 Review 또는 AggregateRating을 연결해 추천 신뢰 신호를 만드세요.")
    if c.get("spec_signal_count", 0) < 4:
        actions.append("카메라·배터리·디스플레이·AI 기능을 비교 가능한 표와 문장으로 추가하세요.")
    return actions[:4] or ["Product/Offer/Review 필드의 최신성과 정확성을 정기 점검하세요."]


def _normalize_brand_fit(fit: Dict[str, Any], crawl: Dict[str, Any]) -> Dict[str, Any]:
    brand = fit.get("target_brand") or _infer_brand(crawl)
    if brand not in ["Samsung Galaxy", "Apple"]:
        brand = _infer_brand(crawl)
    fit.setdefault("status", "ok" if brand != "Unknown" else "unavailable")
    fit["target_brand"] = brand
    fit["score"] = _clamp(fit.get("score", 78 if brand != "Unknown" else 0))
    fit.setdefault("score_components", {"official_identity_match": 10, "brand_persona_fit": min(70, fit["score"]), "evidence_clarity": 10})
    fit.setdefault("persona_fit", {"score": min(70, fit["score"]), "matched_personas": [], "weak_personas": []})
    fit.setdefault("reason", "콘텐츠 내 브랜드 신호 기준")
    fit.setdefault("findings", [])
    fit.setdefault("gaps", [])
    fit.setdefault("actions", [])
    fit.setdefault("note", "공식 브랜드 아이덴티티와 브랜드 페르소나 기준. 실제 검색량·구매 의향·브랜드 선호도는 미포함")
    return fit


def _infer_brand(crawl: Dict[str, Any]) -> str:
    text = " ".join([crawl.get("url", ""), crawl.get("title", ""), crawl.get("meta_description", ""), crawl.get("text", "")[:1000]]).lower()
    if "samsung" in text or "galaxy" in text:
        return "Samsung Galaxy"
    if "apple" in text or "iphone" in text or "ipad" in text or "macbook" in text:
        return "Apple"
    return "Unknown"


def _filter_texts(items: List[Any]) -> List[str]:
    bad = ["image alt", "이미지 alt", "alt 커버리지", "alt 범위", "alt"]
    out: List[str] = []
    for x in items:
        s = str(x).strip()
        if not s:
            continue
        low = s.lower()
        if any(b in low for b in bad):
            continue
        if s not in out:
            out.append(s)
    return out


def _as_list(v: Any) -> List[Any]:
    if v is None:
        return []
    return v if isinstance(v, list) else [v]


def _clamp(v: Any) -> int:
    try:
        return max(0, min(100, int(round(float(v)))))
    except Exception:
        return 0


def _empty(reason: str = "") -> Dict[str, Any]:
    dims = {ax: {"score": 0, "findings": [], "gaps": [], "actions": []} for ax in AXES}
    return {
        "summary": "",
        "topic": "",
        "brands": [],
        "target_audience": "",
        "consumer_perception": "",
        "likely_questions": [],
        "aeo_score": 0,
        "aeo_reason": reason,
        "key_insights": [],
        "brand_fit": {
            "status": "unavailable",
            "target_brand": "Unknown",
            "score": 0,
            "score_components": {"official_identity_match": 0, "brand_persona_fit": 0, "evidence_clarity": 0},
            "persona_fit": {"score": 0, "matched_personas": [], "weak_personas": []},
            "reason": reason,
            "findings": [],
            "gaps": [],
            "actions": [],
            "note": "공식 브랜드 아이덴티티와 브랜드 페르소나 기준. 실제 검색량·구매 의향·브랜드 선호도는 미포함",
        },
        "by_dimension": dims,
        "schema_gaps": [],
        "copy_suggestions": [],
        "visual_suggestions": [],
        "technical_checks": {},
    }
