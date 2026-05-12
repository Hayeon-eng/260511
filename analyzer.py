"""
Compact AEO / AI Commerce analyzer.
Frontend shape is unchanged. No index/style/js changes needed.
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional

from PIL import Image
from gemini_llm import GeminiLLM

log = logging.getLogger(__name__)

AXES = ["데이터", "콘텐츠", "AI Commerce", "UX", "브랜드 메시지 적합도"]

PROMPT = """당신은 AEO + AI Commerce 진단 전문가입니다. 아래 입력만 근거로 JSON만 출력하세요.

[콘텐츠]
URL: {url}
제목: {title}
메타: {meta}
H1: {h1}
H2: {h2}
본문: {body}
스키마: {schema_types}
FAQ 스키마: {has_faq}
Product 스키마: {has_product}
VideoObject 스키마: {has_video}
추가자료: {extra}

[평가 원칙]
- schema_types에 있는 스키마는 없다고 쓰지 마세요. 특히 VideoObject가 있으면 VideoObject 누락이라고 쓰면 안 됩니다.
- 이미지 alt 관련 진단은 쓰지 마세요.
- AI Commerce는 Product/Offer/Review/AggregateRating, 가격, 재고, 구매처, 리뷰, 비교 가능한 스펙을 중심으로 평가하세요.
- 브랜드 적합도는 Samsung Galaxy/Apple 공식 브랜드 메시지와 페르소나 정합성만 보며, 검색량/선호도/성과는 단정하지 마세요.

[브랜드 기준]
Samsung Galaxy: openness, 사람 중심 혁신, 진취적 혁신, Galaxy 생태계, 책임 있는 기술.
Apple: privacy-first, empowering tools, accessibility, environment, integrated premium experience.

다음 JSON만 출력하세요.
{{
  "summary":"60자 이내", "topic":"15자 이내", "brands":[],
  "target_audience":"", "consumer_perception":"", "likely_questions":[],
  "aeo_score":0, "aeo_reason":"", "key_insights":[],
  "brand_fit":{{
    "status":"ok|unavailable", "target_brand":"Samsung Galaxy|Apple|Unknown", "score":0,
    "score_components":{{"official_identity_match":0,"brand_persona_fit":0,"evidence_clarity":0}},
    "persona_fit":{{"score":0,"matched_personas":[],"weak_personas":[]}},
    "reason":"", "findings":[], "gaps":[], "actions":[],
    "note":"공식 브랜드 아이덴티티와 브랜드 페르소나 기준. 실제 검색량·구매 의향·브랜드 선호도는 미포함"
  }},
  "by_dimension":{{
    "데이터":{{"score":0,"findings":[],"gaps":[],"actions":[]}},
    "콘텐츠":{{"score":0,"findings":[],"gaps":[],"actions":[]}},
    "AI Commerce":{{"score":0,"findings":[],"gaps":[],"actions":[]}},
    "UX":{{"score":0,"findings":[],"gaps":[],"actions":[]}},
    "브랜드 메시지 적합도":{{"score":0,"findings":[],"gaps":[],"actions":[]}}
  }},
  "schema_gaps":[], "copy_suggestions":[], "visual_suggestions":[]
}}
"""


def analyze_content(
    crawl_result: Dict[str, Any],
    extra_texts: Optional[List[str]] = None,
    extra_images: Optional[List[Image.Image]] = None,
) -> Dict[str, Any]:
    try:
        if not crawl_result or not crawl_result.get("ok"):
            return _empty(crawl_result.get("error", "크롤링 실패") if crawl_result else "결과 없음")

        checks = dict(crawl_result.get("aeo_checks", {}) or {})
        schemas = crawl_result.get("schemas", []) or []
        types = _schema_types(schemas)
        checks["has_product_schema"] = _has_type(types, "Product")
        checks["has_video_schema"] = _has_type(types, "VideoObject")
        checks["has_faq_schema"] = bool(checks.get("has_faq_schema")) or _has_type(types, "FAQPage") or _has_type(types, "Question")

        scores = _score(crawl_result, types, checks)
        heads = crawl_result.get("headings", {}) or {}
        prompt = PROMPT.format(
            url=crawl_result.get("url", ""),
            title=crawl_result.get("title", ""),
            meta=crawl_result.get("meta_description", ""),
            h1=", ".join(heads.get("h1", [])[:3])[:180],
            h2=", ".join(heads.get("h2", [])[:8])[:260],
            body=(crawl_result.get("text") or "")[:2200],
            schema_types=", ".join(types[:30]) or "없음",
            has_faq="있음" if checks.get("has_faq_schema") else "없음",
            has_product="있음" if checks.get("has_product_schema") else "없음",
            has_video="있음" if checks.get("has_video_schema") else "없음",
            extra=("\n---\n".join(extra_texts or [])[:1800] or "없음"),
        )

        llm = GeminiLLM(system_instruction="JSON만 응답하는 AEO/AI Commerce 컨설턴트입니다.")
        if extra_images:
            raw = llm.generate_with_images(prompt, extra_images, temperature=0.25, max_tokens=3000)
            parsed = _parse_json(raw)
        else:
            parsed = llm.generate_json(prompt, temperature=0.25, max_tokens=3000)
        if not isinstance(parsed, dict) or not parsed:
            return _empty("LLM 응답 파싱 실패")
        return _normalize(parsed, checks, scores)
    except Exception as e:
        log.exception("analyze_content 실패")
        return _empty(str(e))


def _score(crawl: Dict[str, Any], types: List[str], checks: Dict[str, Any]) -> Dict[str, Any]:
    text = _text(crawl)
    nodes = _walk(crawl.get("schemas", []) or [])
    heads = crawl.get("headings", {}) or {}

    has_schema = bool(crawl.get("schemas"))
    has_product = _has_type(types, "Product")
    has_offer = _has_type(types, "Offer") or _has_type(types, "AggregateOffer")
    has_review = _has_type(types, "Review")
    has_rating = _has_type(types, "AggregateRating") or _has_type(types, "Rating")
    has_faq = bool(checks.get("has_faq_schema"))
    has_video = bool(checks.get("has_video_schema"))
    has_breadcrumb = _has_type(types, "BreadcrumbList")
    has_org = _has_type(types, "Organization") or _has_type(types, "Corporation")
    has_page = _has_type(types, "WebPage") or _has_type(types, "Article")

    products = _nodes(nodes, "Product")
    offers = _nodes(nodes, "Offer") + _nodes(nodes, "AggregateOffer")
    reviews = _nodes(nodes, "Review")
    ratings = _nodes(nodes, "AggregateRating") + _nodes(nodes, "Rating")
    for p in products:
        for o in _list(p.get("offers")):
            if isinstance(o, dict):
                offers.append(o); has_offer = True
        for r in _list(p.get("review")) + _list(p.get("reviews")):
            if isinstance(r, dict):
                reviews.append(r); has_review = True
        ar = p.get("aggregateRating") or p.get("rating")
        if isinstance(ar, dict):
            ratings.append(ar); has_rating = True

    product_fields = _field_count(products, "name description image brand sku mpn gtin gtin8 gtin12 gtin13 gtin14 model color category additionalProperty".split())
    offer_fields = _field_count(offers, "price priceCurrency availability url seller itemCondition priceValidUntil".split())
    review_fields = _field_count(reviews, "author reviewBody reviewRating datePublished name".split())
    rating_fields = _field_count(ratings, "ratingValue reviewCount ratingCount bestRating worstRating".split())

    price = _has_words(text, ["price", "$", "₩", "원", "가격", "출고가", "할부", "trade-in", "보상판매"])
    stock = _has_words(text, ["availability", "in stock", "pre-order", "buy now", "where to buy", "재고", "구매", "판매처", "배송"])
    review_text = _has_words(text, ["review", "rating", "리뷰", "평점", "후기", "별점"])
    specs = _word_count(text, ["display", "camera", "battery", "chip", "storage", "gb", "tb", "mp", "mah", "hz", "inch", "ip68", "디스플레이", "카메라", "배터리", "칩", "저장", "방수", "충전", "무게", "크기", "사양", "스펙"])
    compare = _word_count(text, ["compare", "comparison", "vs", "difference", "비교", "차이", "대비", "추천"])
    buy_q = _word_count(text, ["faq", "자주 묻는", "질문", "가격", "구매", "배송", "호환", "구성품", "재고", "반품", "보증"])
    trust = _word_count(text, ["warranty", "return", "support", "privacy", "보증", "반품", "지원", "공식", "개인정보", "보안"])

    data = 0
    data += 8 if checks.get("has_title") else 0
    data += 8 if checks.get("has_meta_desc") else 0
    data += 8 if checks.get("has_h1") else 0
    data += 8 if checks.get("has_og") else 0
    data += 18 if has_schema else 0
    data += 10 if has_faq else 0
    data += 10 if has_product else 0
    data += 8 if has_video else 0
    data += 8 if has_breadcrumb else 0
    data += 7 if has_org else 0
    data += 7 if has_page else 0
    data = min(100, data)

    commerce = 0
    commerce += 22 if has_product else 0
    commerce += min(20, offer_fields * 4 + (5 if price else 0) + (5 if stock else 0))
    commerce += min(15, review_fields * 3 + rating_fields * 4 + (5 if review_text else 0))
    commerce += min(15, specs * 2)
    commerce += min(10, compare * 3 + buy_q)
    commerce += min(8, product_fields * 2)
    commerce += 5 if has_video else 0
    commerce += min(5, trust)
    commerce = min(100, commerce)

    content = 35
    content += 10 if crawl.get("title") else 0
    content += 10 if crawl.get("meta_description") else 0
    content += min(20, len(heads.get("h2", []) or []) * 3)
    content += min(15, len(text) // 400)
    content += min(10, buy_q + compare)
    content = min(100, content)

    ux = 45
    ux += 10 if heads.get("h1") else 0
    ux += min(20, len(heads.get("h2", []) or []) * 3)
    ux += 10 if has_breadcrumb else 0
    ux += min(15, specs + buy_q + trust)
    ux = min(100, ux)

    metrics = {
        "schema_types": types,
        "has_product": has_product,
        "has_offer": has_offer,
        "has_review": has_review,
        "has_rating": has_rating,
        "has_faq": has_faq,
        "has_video": has_video,
        "offer_fields": offer_fields,
        "review_fields": review_fields,
        "rating_fields": rating_fields,
        "product_fields": product_fields,
        "price_signal": price,
        "stock_signal": stock,
        "spec_signal_count": specs,
        "compare_signal_count": compare,
    }
    return {"scores": {"데이터": data, "콘텐츠": content, "AI Commerce": commerce, "UX": ux}, "metrics": metrics}


def _normalize(d: Dict[str, Any], checks: Dict[str, Any], pack: Dict[str, Any]) -> Dict[str, Any]:
    d.setdefault("summary", "")
    d.setdefault("topic", "")
    d.setdefault("brands", [])
    d.setdefault("target_audience", "")
    d.setdefault("consumer_perception", "")
    d.setdefault("likely_questions", [])
    d.setdefault("key_insights", [])
    d.setdefault("copy_suggestions", [])
    d.setdefault("visual_suggestions", [])
    d.setdefault("schema_gaps", [])
    d.setdefault("by_dimension", {})
    d.setdefault("brand_fit", {})

    for ax in AXES:
        item = d["by_dimension"].get(ax, {}) if isinstance(d["by_dimension"], dict) else {}
        if not isinstance(item, dict):
            item = {}
        item.setdefault("score", 0); item.setdefault("findings", []); item.setdefault("gaps", []); item.setdefault("actions", [])
        d["by_dimension"][ax] = item

    bf = d["brand_fit"] if isinstance(d["brand_fit"], dict) else {}
    bf.setdefault("status", "ok")
    bf.setdefault("target_brand", "Unknown")
    bf.setdefault("score", 0)
    bf.setdefault("score_components", {"official_identity_match": 0, "brand_persona_fit": 0, "evidence_clarity": 0})
    bf.setdefault("persona_fit", {"score": bf.get("score_components", {}).get("brand_persona_fit", 0), "matched_personas": [], "weak_personas": []})
    bf.setdefault("reason", ""); bf.setdefault("findings", []); bf.setdefault("gaps", []); bf.setdefault("actions", [])
    bf.setdefault("note", "공식 브랜드 아이덴티티와 브랜드 페르소나 기준. 실제 검색량·구매 의향·브랜드 선호도는 미포함")
    d["brand_fit"] = bf

    scores = pack.get("scores", {})
    metrics = pack.get("metrics", {})
    for ax in ["데이터", "콘텐츠", "AI Commerce", "UX"]:
        if ax in scores:
            d["by_dimension"][ax]["score"] = int(scores[ax])
    d["by_dimension"]["브랜드 메시지 적합도"]["score"] = int(bf.get("score") or d["by_dimension"]["브랜드 메시지 적합도"].get("score") or 0)

    _merge_commerce(d, metrics)
    _merge_schema_gaps(d, metrics)
    _remove_alt_noise(d)

    brand_score = d["by_dimension"]["브랜드 메시지 적합도"].get("score", 0)
    weighted = round(scores.get("데이터", 0) * 0.22 + scores.get("콘텐츠", 0) * 0.20 + scores.get("AI Commerce", 0) * 0.32 + scores.get("UX", 0) * 0.14 + brand_score * 0.12)
    d["aeo_score"] = max(0, min(100, int(weighted)))
    d["aeo_reason"] = f"데이터/콘텐츠/AI Commerce/UX/브랜드 적합도 가중 평균. AI Commerce {scores.get('AI Commerce', 0)}점."
    d["technical_checks"] = {**checks, "commerce_metrics": metrics}
    return d


def _merge_commerce(d: Dict[str, Any], m: Dict[str, Any]) -> None:
    ai = d["by_dimension"]["AI Commerce"]
    f, g, a = ai["findings"], ai["gaps"], ai["actions"]
    if m.get("has_product"):
        f.append("Product 스키마가 감지되어 상품 엔티티 인식 기반은 있습니다.")
    else:
        g.append("Product 스키마가 없어 AI가 상품 엔티티를 확정하기 어렵습니다.")
        a.append("Product 스키마에 name, brand, image, description, sku/model을 추가하세요.")
    if not m.get("has_offer") and not (m.get("price_signal") and m.get("stock_signal")):
        g.append("가격·재고·구매처 신호가 약해 AI 추천 답변에서 구매 조건을 설명하기 어렵습니다.")
        a.append("Offer 스키마 또는 본문에 price, priceCurrency, availability, seller, 구매 URL을 명시하세요.")
    if not (m.get("has_review") or m.get("has_rating")):
        g.append("Review/AggregateRating 신호가 약해 추천 근거의 사회적 증거가 부족합니다.")
        a.append("공식 리뷰 정책에 맞춰 review 또는 aggregateRating 필드를 구조화하세요.")
    if int(m.get("spec_signal_count") or 0) < 5:
        g.append("비교 가능한 핵심 스펙 표현이 부족해 AI가 경쟁 제품과 차이를 설명하기 어렵습니다.")
        a.append("카메라, 배터리, 칩, 저장용량, 디스플레이 등 비교 가능한 스펙을 표나 문장으로 보강하세요.")
    if m.get("has_video"):
        f.append("VideoObject가 감지되어 영상형 사용 장면/리뷰 콘텐츠 신호는 확보되어 있습니다.")
    ai["findings"] = _uniq(f)[:5]
    ai["gaps"] = _uniq(g)[:5]
    ai["actions"] = _uniq(a)[:5]


def _merge_schema_gaps(d: Dict[str, Any], m: Dict[str, Any]) -> None:
    gaps = [str(x) for x in d.get("schema_gaps", []) if x]
    if not m.get("has_faq"):
        gaps.append("FAQPage")
    if not m.get("has_product"):
        gaps.append("Product")
    if not m.get("has_offer"):
        gaps.append("Offer")
    if not (m.get("has_review") or m.get("has_rating")):
        gaps.append("Review/AggregateRating")
    existing = {str(t).lower() for t in m.get("schema_types", [])}
    clean = []
    for gap in gaps:
        lg = gap.lower()
        if "videoobject" in lg and "videoobject" in existing:
            continue
        if "product" in lg and "product" in existing:
            continue
        if "faq" in lg and ("faqpage" in existing or "question" in existing):
            continue
        if "offer" in lg and ("offer" in existing or "aggregateoffer" in existing):
            continue
        if "review" in lg and ("review" in existing or "aggregaterating" in existing or "rating" in existing):
            continue
        clean.append(gap)
    d["schema_gaps"] = _uniq(clean)[:8]


def _remove_alt_noise(obj: Any) -> Any:
    bad = ("alt", "이미지 alt", "대체 텍스트", "범위가 이상")
    if isinstance(obj, dict):
        for k in list(obj.keys()):
            obj[k] = _remove_alt_noise(obj[k])
    elif isinstance(obj, list):
        obj[:] = [x for x in (_remove_alt_noise(v) for v in obj) if not (isinstance(x, str) and any(b in x.lower() for b in bad))]
    return obj


def _schema_types(schemas: Any) -> List[str]:
    found = []
    for n in _walk(schemas):
        for t in _list(n.get("@type")) if isinstance(n, dict) else []:
            if isinstance(t, str):
                found.append(t.split(":")[-1])
    return _uniq(found)


def _walk(x: Any) -> List[Dict[str, Any]]:
    out = []
    if isinstance(x, dict):
        out.append(x)
        for k in ("@graph", "itemListElement", "mainEntity", "hasPart", "video", "subjectOf"):
            if k in x:
                out += _walk(x[k])
        for v in x.values():
            if isinstance(v, (dict, list)):
                out += _walk(v)
    elif isinstance(x, list):
        for v in x:
            out += _walk(v)
    return out


def _nodes(nodes: List[Dict[str, Any]], typ: str) -> List[Dict[str, Any]]:
    return [n for n in nodes if isinstance(n, dict) and _has_type(_list(n.get("@type")), typ)]


def _has_type(types: List[Any], name: str) -> bool:
    return any(str(t).split(":")[-1].lower() == name.lower() for t in types)


def _field_count(nodes: List[Dict[str, Any]], fields: List[str]) -> int:
    return sum(1 for f in fields if any(isinstance(n, dict) and n.get(f) not in (None, "", [], {}) for n in nodes))


def _text(crawl: Dict[str, Any]) -> str:
    parts = [crawl.get("title", ""), crawl.get("meta_description", ""), crawl.get("text", "")]
    h = crawl.get("headings", {}) or {}
    parts += h.get("h1", []) + h.get("h2", []) + h.get("h3", [])
    return " ".join(str(p) for p in parts if p).lower()


def _has_words(text: str, words: List[str]) -> bool:
    return any(w.lower() in text for w in words)


def _word_count(text: str, words: List[str]) -> int:
    return sum(1 for w in words if w.lower() in text)


def _list(x: Any) -> List[Any]:
    if x is None:
        return []
    return x if isinstance(x, list) else [x]


def _uniq(items: List[Any]) -> List[Any]:
    out, seen = [], set()
    for x in items:
        key = json.dumps(x, ensure_ascii=False, sort_keys=True) if isinstance(x, (dict, list)) else str(x)
        if key not in seen:
            seen.add(key); out.append(x)
    return out


def _parse_json(text: str) -> Dict[str, Any]:
    try:
        return json.loads(text)
    except Exception:
        try:
            s, e = text.find("{"), text.rfind("}") + 1
            return json.loads(text[s:e]) if s >= 0 and e > s else {}
        except Exception:
            return {}


def _empty(reason: str = "") -> Dict[str, Any]:
    dims = {ax: {"score": 0, "findings": [], "gaps": [], "actions": []} for ax in AXES}
    return {
        "summary": "", "topic": "", "brands": [], "target_audience": "", "consumer_perception": "",
        "likely_questions": [], "aeo_score": 0, "aeo_reason": reason, "key_insights": [],
        "brand_fit": {
            "status": "unavailable", "target_brand": "Unknown", "score": 0,
            "score_components": {"official_identity_match": 0, "brand_persona_fit": 0, "evidence_clarity": 0},
            "persona_fit": {"score": 0, "matched_personas": [], "weak_personas": []},
            "reason": reason, "findings": [], "gaps": [], "actions": [],
            "note": "공식 브랜드 아이덴티티와 브랜드 페르소나 기준. 실제 검색량·구매 의향·브랜드 선호도는 미포함",
        },
        "by_dimension": dims, "schema_gaps": [], "copy_suggestions": [], "visual_suggestions": [], "technical_checks": {},
    }
