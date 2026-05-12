"""
라이브 다이제스트 + 임원 요약 생성기 (5개 축 정렬).
"""

import json
import logging
from typing import List, Dict, Any

from gemini_llm import GeminiLLM

log = logging.getLogger(__name__)

DIGEST_PROMPT = """당신은 컨설팅 회의록 작성 전문가입니다. AEO 토론을 5개 축(데이터/콘텐츠/AI Commerce/UX/브랜드 메시지 적합도)으로 정리하세요.

[토론 주제]
{query}

[모든 발언 — 페르소나/축/입장과 함께]
{turns}

다음 JSON으로만 답변하세요. 5개 축 모두에 대해 정리하되, 발언이 없는 축은 빈 배열로 두세요.

{{
  "headline": "토론 전체를 한 줄로 (40자 이내)",
  "by_dimension": {{
    "데이터": {{
      "consensus": ["이 축에서 합의된 발견 (1-3개)"],
      "conflicts": ["이 축에서 충돌한 의견 (있을 경우)"],
      "actions": ["이 축의 액션 아이템 (1-3개, 우선순위 순)"]
    }},
    "콘텐츠": {{ "consensus": [], "conflicts": [], "actions": [] }},
    "AI Commerce": {{ "consensus": [], "conflicts": [], "actions": [] }},
    "UX": {{ "consensus": [], "conflicts": [], "actions": [] }},
    "브랜드 메시지 적합도": {{ "consensus": [], "conflicts": [], "actions": [] }}
  }},
  "top_insights": ["축을 가로지르는 통합 인사이트 (최대 3개)"],
  "next_questions": ["다음 라운드에서 다뤘으면 하는 질문 (최대 3개)"]
}}
"""


EXEC_PROMPT = """당신은 C-Level 임원진에게 보고하는 컨설팅 파트너입니다.
아래 AEO 토론 결과를 토대로 임원 보고용 한 페이지 결론을 작성하세요.
임원진은 30초 안에 핵심을 파악해야 합니다.

[토론 주제]
{query}

[모드]
{mode}

[크롤링·입력 데이터 기반 사전 진단 데이터]
{analysis}

[브랜드 적합도 반영 원칙]
브랜드 적합도 점수와 근거가 있으면 key_gaps/actions에 함께 반영하세요. 브랜드 적합도는 Samsung Galaxy/Apple 공식 브랜드 아이덴티티와 브랜드 페르소나 기준이며, 실제 시장 선호도·검색량·구매 의향은 데이터가 없으면 단정하지 마세요.

[전체 발언 요약]
{turns}

[기존 다이제스트]
{digest}

다음 JSON으로만 답변하세요. 각 액션의 impact와 effort는 반드시 1~5로, 정수로 매겨야 합니다.

{{
  "verdict": "최종 결론 한 줄 (60자 이내). '~다.'로 끝나는 단언형. 미사여구 금지.",
  "key_gaps": [
    {{"title": "핵심 격차/이슈 한 줄", "axis": "데이터|콘텐츠|AI Commerce|UX|브랜드 메시지 적합도", "evidence": "근거 한 줄"}}
  ],
  "actions": [
    {{
      "title": "액션 한 줄 (구체적)",
      "axis": "데이터|콘텐츠|AI Commerce|UX|브랜드 메시지 적합도",
      "impact": 1-5,
      "effort": 1-5,
      "timeline": "2주 | 1개월 | 분기 중 하나",
      "owner": "담당 (Tech | Content | Marketing | Product 중)",
      "expected_outcome": "기대 효과 한 줄"
    }}
  ],
  "expected_impact": "이 액션들을 실행하면 예상되는 비즈니스 임팩트 (2-3문장, 정량적 표현 포함)",
  "risks": [
    "리스크/가정 (예: '추정치는 동종 업계 평균 기반')"
  ]
}}

[작성 가이드]
- key_gaps는 3~5개. 가장 임팩트 큰 격차부터.
- actions는 6~10개. 다양한 축 골고루.
- impact: 1=미미함, 3=의미있음, 5=결정적
- effort: 1=즉시(반나절), 3=중간(1-2주), 5=대규모(분기)
- Quick Win = impact 4+ & effort ≤2. 이런 액션이 최소 2개는 포함되도록.
"""


def generate_digest(query: str, turns: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not turns:
        return _empty()

    try:
        lines = []
        for t in turns[-40:]:
            persona = t.get("persona", "?")
            stance = t.get("stance", "")
            target = t.get("target", "")
            synthesis = t.get("synthesis", "")
            target_tag = f"→{target} " if target else ""
            lines.append(f"\n[{persona}/{stance}] {target_tag}{synthesis}")
            for d in t.get("dimensions", []):
                ax = d.get("axis", "")
                arg = (d.get("argument", "") or "")[:200]
                act = (d.get("action", "") or "")[:120]
                lines.append(f"  · ({ax}) {arg}")
                if act:
                    lines.append(f"    → 액션: {act}")

        prompt = DIGEST_PROMPT.format(query=query, turns="".join(lines)[:9000])

        llm = GeminiLLM(
            system_instruction="당신은 회의록 작성에 능숙한 컨설턴트입니다. 항상 JSON으로만 응답합니다."
        )
        result = llm.generate_json(prompt, temperature=0.25, max_tokens=2000)

        if not isinstance(result, dict):
            return _empty()
        return _normalize(result)
    except Exception as e:
        log.error(f"digest 생성 실패: {e}")
        return _empty()


def generate_executive_summary(session: Dict[str, Any]) -> Dict[str, Any]:
    """임원 보고용 한 페이지 결론 + 액션 (Quick Win 분류 포함)."""
    try:
        query = session.get("query", "")
        mode = session.get("mode", "single")
        turns = session.get("turns") or []
        digest_row = session.get("digest") or {}
        digest = digest_row.get("digest") if isinstance(digest_row, dict) else digest_row

        # 분석 데이터 정리
        if mode == "compare":
            a = (session.get("side_a") or {}).get("analysis", {})
            b = (session.get("side_b") or {}).get("analysis", {})
            a_label = (session.get("side_a") or {}).get("label") or session.get("label_a") or "A"
            b_label = (session.get("side_b") or {}).get("label") or session.get("label_b") or "B"
            analysis_str = (
                f"[{a_label}] AEO {a.get('aeo_score',0)}/100 — {a.get('summary','')}\n"
                f"  - 축별 점수: " + ", ".join([f"{k}:{(a.get('by_dimension',{}).get(k,{}) or {}).get('score',0)}" for k in ["데이터","콘텐츠","AI Commerce","UX","브랜드 메시지 적합도"]]) + "\n"
                f"  - 부족 스키마: {a.get('schema_gaps',[])}\n\n"
                f"[{b_label}] AEO {b.get('aeo_score',0)}/100 — {b.get('summary','')}\n"
                f"  - 축별 점수: " + ", ".join([f"{k}:{(b.get('by_dimension',{}).get(k,{}) or {}).get('score',0)}" for k in ["데이터","콘텐츠","AI Commerce","UX","브랜드 메시지 적합도"]]) + "\n"
                f"  - 부족 스키마: {b.get('schema_gaps',[])}"
            )
        else:
            a = session.get("analysis", {}) or {}
            analysis_str = (
                f"AEO {a.get('aeo_score',0)}/100 — {a.get('summary','')}\n"
                f"  - 축별 점수: " + ", ".join([f"{k}:{(a.get('by_dimension',{}).get(k,{}) or {}).get('score',0)}" for k in ["데이터","콘텐츠","AI Commerce","UX","브랜드 메시지 적합도"]]) + "\n"
                f"  - 핵심 인사이트: {a.get('key_insights',[])}\n"
                f"  - 부족 스키마: {a.get('schema_gaps',[])}"
            )

        # 발언 요약
        turn_lines = []
        for t in turns:
            persona = t.get("persona", "?")
            synthesis = t.get("synthesis", "")
            turn_lines.append(f"- [{persona}] {synthesis}")
            for d in t.get("dimensions", []):
                act = (d.get("action") or "")[:140]
                if act:
                    turn_lines.append(f"  → ({d.get('axis','')}) {act}")
        turns_str = "\n".join(turn_lines)[:6000] or "(발언 없음)"

        digest_str = json.dumps(digest or {}, ensure_ascii=False)[:3000]

        prompt = EXEC_PROMPT.format(
            query=query, mode=mode, analysis=analysis_str,
            turns=turns_str, digest=digest_str
        )

        llm = GeminiLLM(
            system_instruction="당신은 C-Level 보고에 능숙한 컨설팅 파트너입니다. 간결·단언·정량 표현을 선호하며, 항상 JSON으로만 응답합니다."
        )

        # 임원 요약은 key_gaps/actions/expected_impact까지 포함되어 길어질 수 있습니다.
        # 기존 2500 토큰에서는 응답이 중간에 잘려 JSON 파싱이 실패할 수 있어 5000으로 올립니다.
        debug = llm.generate_json_debug(prompt, temperature=0.3, max_tokens=5000)
        if not debug.get("ok"):
            log.error(f"executive summary LLM 실패: {debug.get('error')}")
            return _empty_exec(debug.get("error", "임원 요약 LLM 실패"), debug)

        result = debug.get("data")
        if not isinstance(result, dict):
            return _empty_exec("Gemini 응답이 JSON 객체가 아닙니다.", debug)

        normalized = _normalize_exec(result)
        if not normalized.get("verdict"):
            return _empty_exec("Gemini 응답에 verdict 필드가 없거나 비어 있습니다.", debug)
        return normalized
    except Exception as e:
        log.exception("executive summary 실패")
        return _empty_exec(str(e))


def _normalize_exec(d: Dict[str, Any]) -> Dict[str, Any]:
    d.setdefault("verdict", "")
    d.setdefault("key_gaps", [])
    d.setdefault("actions", [])
    d.setdefault("expected_impact", "")
    d.setdefault("risks", [])

    # 액션 정규화: impact/effort 정수화, quick_win 자동 마킹
    cleaned = []
    for a in d.get("actions", []):
        if not isinstance(a, dict):
            continue
        try:
            impact = int(a.get("impact", 3))
        except Exception:
            impact = 3
        try:
            effort = int(a.get("effort", 3))
        except Exception:
            effort = 3
        impact = max(1, min(5, impact))
        effort = max(1, min(5, effort))
        a["impact"] = impact
        a["effort"] = effort
        a["quick_win"] = (impact >= 4 and effort <= 2)
        a.setdefault("title", "")
        a.setdefault("axis", "")
        a.setdefault("timeline", "")
        a.setdefault("owner", "")
        a.setdefault("expected_outcome", "")
        cleaned.append(a)

    # Quick Win 먼저, 그 다음 impact-effort 점수 순
    cleaned.sort(key=lambda x: (not x.get("quick_win", False), -x["impact"], x["effort"]))
    d["actions"] = cleaned
    return d


def _empty_exec(reason: str = "", debug: Dict[str, Any] = None) -> Dict[str, Any]:
    return {
        "_ok": False,
        "error_reason": reason or "임원 요약 생성 실패",
        "debug": debug or {},
        "verdict": "",
        "key_gaps": [],
        "actions": [],
        "expected_impact": "",
        "risks": [],
    }


def _normalize(d: Dict[str, Any]) -> Dict[str, Any]:
    d.setdefault("headline", "")
    d.setdefault("top_insights", [])
    d.setdefault("next_questions", [])
    d.setdefault("by_dimension", {})
    for ax in ["데이터", "콘텐츠", "AI Commerce", "UX", "브랜드 메시지 적합도"]:
        item = d["by_dimension"].get(ax, {})
        if not isinstance(item, dict):
            item = {}
        item.setdefault("consensus", [])
        item.setdefault("conflicts", [])
        item.setdefault("actions", [])
        d["by_dimension"][ax] = item
    return d


def _empty() -> Dict[str, Any]:
    return {
        "headline": "",
        "top_insights": [],
        "next_questions": [],
        "by_dimension": {
            "데이터": {"consensus": [], "conflicts": [], "actions": []},
            "콘텐츠": {"consensus": [], "conflicts": [], "actions": []},
            "AI Commerce": {"consensus": [], "conflicts": [], "actions": []},
            "UX": {"consensus": [], "conflicts": [], "actions": []},
            "브랜드 메시지 적합도": {"consensus": [], "conflicts": [], "actions": []},
        },
    }
