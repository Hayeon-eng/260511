"""
라이브 다이제스트 생성기 (4축 정렬).
모든 발언을 보고 합의점/충돌점/액션 아이템을 축별로 정리.
"""

import json
import logging
from typing import List, Dict, Any

from gemini_llm import GeminiLLM

log = logging.getLogger(__name__)

DIGEST_PROMPT = """당신은 컨설팅 회의록 작성 전문가입니다. AEO 토론을 4축(데이터/콘텐츠/AI Commerce/UX)으로 정리하세요.

[토론 주제]
{query}

[모든 발언 — 페르소나/축/입장과 함께]
{turns}

다음 JSON으로만 답변하세요. 4축 모두에 대해 정리하되, 발언이 없는 축은 빈 배열로 두세요.

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
    "UX": {{ "consensus": [], "conflicts": [], "actions": [] }}
  }},
  "top_insights": ["축을 가로지르는 통합 인사이트 (최대 3개)"],
  "next_questions": ["다음 라운드에서 다뤘으면 하는 질문 (최대 3개)"]
}}
"""


def generate_digest(query: str, turns: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not turns:
        return _empty()

    try:
        # 발언 정리
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


def _normalize(d: Dict[str, Any]) -> Dict[str, Any]:
    d.setdefault("headline", "")
    d.setdefault("top_insights", [])
    d.setdefault("next_questions", [])
    d.setdefault("by_dimension", {})
    for ax in ["데이터", "콘텐츠", "AI Commerce", "UX"]:
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
        },
    }
