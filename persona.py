"""
페르소나 (5개 축 분석 + 중복 방지 + 닉네임 기반 SET).

축: 데이터 / 콘텐츠 / AI Commerce / UX / 브랜드 메시지 적합도
응답 구조:
- stance, target
- dimensions[]: 1~2개 축. 각 축마다 evidence(근거+출처), argument(150자+), action(50자+)
- synthesis: 종합 한 줄
"""

import json
import logging
from typing import List, Dict, Any, Optional

from gemini_llm import GeminiLLM

log = logging.getLogger(__name__)

STANCES = ["지지", "반박", "보완", "신규관점", "질문"]
ALL_DIMENSIONS = ["데이터", "콘텐츠", "AI Commerce", "UX", "브랜드 메시지 적합도"]

MIN_ARGUMENT_LEN = 150
MIN_ACTION_LEN = 50


DIMENSION_GUIDE = """[분석 축 정의 — 반드시 이 정의 안에서만 발언]

📊 데이터
  - JSON-LD / Schema.org / Open Graph / 메타 태그 / 정량 정보
  - AI가 인용할 수 있는 구조화된 데이터의 유무·정확성·완성도
  - 예: "FAQPage 스키마 부재", "Product 스키마에 price 없음", "alt 커버리지 23%"

✍️ 콘텐츠
  - 카피, 메시지, 내러티브, 톤앤매너, 정보 위계, 어휘 선택
  - 키워드 자연 노출, 답변형 문장 구조, 헤딩의 정보성
  - 예: "H1이 슬로건형이라 질의 매칭 어려움", "본문에 가격 비교 서술 없음"

🛍️ AI Commerce
  - AI Agent가 상품을 추천할 때 우리 데이터를 인용·추천하게 만드는 측면
  - 상품 데이터 피드/커머스 플랫폼 친화성, Product/Offer/Review/AggregateRating 스키마
  - 가격·재고·리뷰·비교 데이터의 AI 발견 가능성
  - 주의: 기존 마케팅의 CTA/전환률/광고는 이 축이 아님. 어디까지나 "AI Agent의 답변에 들어가는가"의 관점.
  - 예: "Product 스키마에 aggregateRating 없어 AI 추천 답변 후보 제외", "비교 가능한 사양표가 본문에 없음"

🎨 UX
  - 정보 구조, 탐색 경로, 스캐닝/가독성, 의사결정 흐름
  - 사람과 AI 모두에게 정보 발견·소화가 쉬운가
  - 예: "핵심 정보가 4스크롤 아래", "FAQ 섹션이 아코디언으로 숨겨져 본문 텍스트에 없음"

🎯 브랜드 메시지 적합도
  - Samsung Galaxy / Apple 공식 브랜드 아이덴티티와 브랜드 페르소나에 맞는가
  - 검색량·구매 의향이 아니라 공식 브랜드 기준과 콘텐츠 메시지의 정합성
  - 예: "Galaxy의 Open Explorer 페르소나에는 맞지만 Responsible Tech User 근거가 부족함"
"""


def _build_system_instruction(name: str, description: str, personality: str,
                              expertise: str, focus_dimensions: List[str]) -> str:
    focus_str = ", ".join(focus_dimensions) if focus_dimensions else "(전체 축 가능)"
    return f"""당신은 "{name}"이라는 AEO·AI Commerce 토론 참여자입니다.

[페르소나 정체성]
- 설명: {description or '(없음)'}
- 성격·말투: {personality or '균형 잡힌 톤'}
- 전문 분야: {expertise or '일반'}
- 주력 분석 축: {focus_str}

{DIMENSION_GUIDE}

[핵심 원칙 — 어기면 발언이 폐기됩니다]
1. 한국어로 응답.
2. 5개 축(데이터/콘텐츠/AI Commerce/UX/브랜드 메시지 적합도) 중 **1~2개를 선택**해서 발언. 한 발언에 모든 축 다루지 않음.
3. 각 축의 evidence는 **반드시 제공된 콘텐츠/분석 데이터에서 직접 인용**. 데이터에 없는 내용 창작 금지.
4. argument는 **150자 이상**의 분석. "느낌상", "보통", "일반적으로", "~인 것 같다" 표현 금지.
5. action은 **50자 이상**의 구체적 실행안. "개선이 필요하다" 같은 막연한 제안 금지.
6. 이미 다른 페르소나가 인용한 evidence나 주장한 argument는 **재사용 금지**. 같은 콘텐츠를 보더라도 다른 관점·다른 데이터 포인트를 찾아야 함.
7. 페르소나의 성격과 말투를 일관되게 유지. 닉네임에 담긴 정체성(예: "감성젠지"라면 Z세대 어법, "SkepticalShopper"라면 의심 많은 소비자 톤)을 반드시 반영.
8. stance와 target은 직전 발언자에 대한 입장. 첫 발언이면 stance=신규관점, target="".
9. 반드시 JSON으로만 응답. 부가 텍스트 일체 금지.
"""


RESPONSE_SCHEMA_HINT = """
다음 JSON 스키마로만 출력. 키 누락/추가 금지.

{
  "stance": "지지|반박|보완|신규관점|질문 중 하나",
  "target": "직전 발화자의 닉네임 (없으면 빈 문자열)",
  "dimensions": [
    {
      "axis": "데이터|콘텐츠|AI Commerce|UX|브랜드 메시지 적합도 중 하나",
      "evidence": [
        {"source": "데이터 출처 (예: H1 태그, JSON-LD, AEO 점수, alt 커버리지)",
         "quote": "실제 인용 값"}
      ],
      "argument": "이 축에 대한 분석 (반드시 150자 이상). 데이터를 인용하며 왜 그것이 AEO/AI Commerce 관점에서 문제/기회인지 페르소나의 톤으로 설명.",
      "action": "구체 실행안 (반드시 50자 이상). 누가 무엇을 어떻게 할지 명시."
    }
  ],
  "synthesis": "이 발언을 페르소나 톤으로 한 줄 요약 (40자 이내). 다이제스트에 들어감."
}
"""


class Persona:
    def __init__(self, name: str, description: str = "", personality: str = "",
                 expertise: str = "", focus_dimensions: Optional[List[str]] = None,
                 color: str = "#007AFF", emoji: str = "💬"):
        self.name = name
        self.description = description
        self.personality = personality
        self.expertise = expertise
        self.focus_dimensions = focus_dimensions or []
        self.color = color
        self.emoji = emoji

        self.llm = GeminiLLM(
            system_instruction=_build_system_instruction(
                name, description, personality, expertise, self.focus_dimensions
            )
        )

    def respond(self, query: str, context: str, analysis: Dict[str, Any],
                history: List[Dict[str, Any]],
                compare: Optional[Dict[str, Any]] = None,
                user_question: Optional[str] = None) -> Dict[str, Any]:
        recent = history[-10:] if history else []

        used_evidence = []
        used_arguments = []
        used_axes_recently = []
        for t in recent:
            for dim in t.get("dimensions", []):
                for ev in dim.get("evidence", []):
                    src = ev.get("source", "")
                    q = ev.get("quote", "")
                    if src or q:
                        used_evidence.append(f"[{t.get('persona','')}/{dim.get('axis','')}] {src}: {q}")
                arg = dim.get("argument", "")
                if arg:
                    used_arguments.append(f"[{t.get('persona','')}/{dim.get('axis','')}] {arg[:80]}...")
                ax = dim.get("axis", "")
                if ax:
                    used_axes_recently.append(ax)

        last_speaker = recent[-1].get("persona", "") if recent else ""

        history_lines = []
        for t in recent:
            speaker = t.get("persona", "?")
            stance = t.get("stance", "")
            syn = t.get("synthesis", "")
            axes = "·".join([d.get("axis", "") for d in t.get("dimensions", [])])
            history_lines.append(f"- [{speaker}/{stance}/{axes}] {syn}")
        history_text = "\n".join(history_lines) or "(아직 발언 없음 — 당신이 첫 발화자입니다)"

        technical = analysis.get("technical_checks", {})

        # 비교 모드 컨텍스트
        compare_block = ""
        compare_instruction = ""
        if compare:
            a = compare.get("side_a", {}) or {}
            b = compare.get("side_b", {}) or {}
            label_a = compare.get("label_a") or "A"
            label_b = compare.get("label_b") or "B"
            a_ctx = (a.get("context") or "")[:1200]
            b_ctx = (b.get("context") or "")[:1200]
            a_an = a.get("analysis", {}) or {}
            b_an = b.get("analysis", {}) or {}
            compare_block = f"""

============================================
🆚 비교 모드 — 좌측({label_a}) vs 우측({label_b})
============================================

[좌측 - {label_a}]
- URL/제목: {a.get('url','')} / {a_an.get('summary','')}
- AEO 점수: {a_an.get('aeo_score', 0)}/100
- 본문 발췌: {a_ctx}
- 부족한 스키마: {a_an.get('schema_gaps', [])}
- 카피 개선안: {a_an.get('copy_suggestions', [])}
- 기술 체크: {json.dumps(a_an.get('technical_checks', {}), ensure_ascii=False)}

[우측 - {label_b}]
- URL/제목: {b.get('url','')} / {b_an.get('summary','')}
- AEO 점수: {b_an.get('aeo_score', 0)}/100
- 본문 발췌: {b_ctx}
- 부족한 스키마: {b_an.get('schema_gaps', [])}
- 카피 개선안: {b_an.get('copy_suggestions', [])}
- 기술 체크: {json.dumps(b_an.get('technical_checks', {}), ensure_ascii=False)}
"""
            compare_instruction = (
                f"\n- 비교 모드입니다. 모든 evidence의 source 앞에 반드시 [{label_a}] 또는 [{label_b}] 접두어를 붙이세요. "
                f"  예: \"[{label_a}] H1 태그\", \"[{label_b}] JSON-LD\".\n"
                f"- argument에서 좌·우 차이를 명확히 짚어야 합니다 (어느 쪽이 무엇이 더 좋은지/부족한지).\n"
                f"- action은 약한 쪽({label_a}/{label_b} 중)을 어떻게 강한 쪽 수준으로 끌어올릴지 구체 제시.\n"
            )

        # 사용자 꼬리질문 컨텍스트
        user_q_block = ""
        if user_question:
            user_q_block = f"""

============================================
❓ 사용자(임원진/PM)가 추가로 던진 질문
============================================
"{user_question}"

위 질문에 직접 답하세요. 다음 원칙을 지키세요:
- 일반 토론과 동일한 4파트 구조(stance/dimensions/synthesis) 유지
- stance는 보통 "신규관점" 또는 "보완", target은 ""
- 질문이 특정 페르소나를 지목했어도 "{self.name}" 페르소나로서 자기 관점으로 답변
- argument에서 **질문에 직접적으로 답한 뒤** 근거와 논리를 제시
- action에서 질문자가 바로 가져갈 수 있는 구체적 다음 단계 제시
"""

        prompt = f"""[토론 주제]
{query}

[콘텐츠 요약]
{analysis.get('summary', '(요약 없음)')}

[콘텐츠 본문 발췌 — 여기서 evidence 직접 인용]
{(context or '(본문 없음)')[:2000]}

[AEO 진단 데이터 — 여기서도 evidence 인용 가능]
- AEO 점수: {analysis.get('aeo_score', 0)}/100 ({analysis.get('aeo_reason','')})
- 기술 체크: {json.dumps(technical, ensure_ascii=False)}
- 핵심 인사이트: {analysis.get('key_insights', [])}
- 부족한 스키마: {analysis.get('schema_gaps', [])}
- 카피 개선안: {analysis.get('copy_suggestions', [])}
- 비주얼 제언: {analysis.get('visual_suggestions', [])}
- 소비자 인식: {analysis.get('consumer_perception','')}
- 예상 질의: {analysis.get('likely_questions', [])}
{compare_block}
[지금까지의 발언 ({len(recent)}건)]
{history_text}

[이미 다른 페르소나가 인용한 evidence — 동일 인용 금지]
{chr(10).join(used_evidence[-15:]) if used_evidence else "(없음)"}

[이미 나온 argument 요지 — 동일 주장 금지]
{chr(10).join(used_arguments[-10:]) if used_arguments else "(없음)"}

[직전 라운드에서 많이 다뤄진 축 — 가능하면 다른 축 선택]
{', '.join(set(used_axes_recently[-4:])) if used_axes_recently else "(없음)"}

직전 발화자: "{last_speaker}"

위 데이터만 사용해 "{self.name}" 페르소나로서 응답하세요.
- 다른 페르소나와 중복되지 않는 새로운 evidence·관점을 가져오세요.
- 본인의 주력 축({', '.join(self.focus_dimensions) if self.focus_dimensions else '자유'})을 우선 고려하되, 이미 다뤄진 축이면 다른 축을 선택해도 됩니다.
- 닉네임 정체성에 맞는 말투·태도를 반드시 드러내세요.
- argument는 반드시 150자 이상, action은 50자 이상.{compare_instruction}{user_q_block}
{RESPONSE_SCHEMA_HINT}
"""

        result = self.llm.generate_json(prompt, temperature=0.85, max_tokens=1400)

        if not self._validate(result):
            log.info(f"{self.name} 응답 검증 실패, 재시도")
            result = self.llm.generate_json(
                prompt + "\n\n[중요] 직전 응답이 검증을 통과하지 못했습니다. argument 150자 이상, action 50자 이상, evidence 1개 이상 필수.",
                temperature=0.9, max_tokens=1500
            )

        if not isinstance(result, dict) or not result.get("dimensions"):
            result = self._fallback()

        result.setdefault("stance", "신규관점")
        if result["stance"] not in STANCES:
            result["stance"] = "신규관점"
        result.setdefault("target", "")
        result.setdefault("dimensions", [])
        result.setdefault("synthesis", "")

        cleaned_dims = []
        for d in result.get("dimensions", []):
            if not isinstance(d, dict):
                continue
            axis = d.get("axis", "")
            if axis not in ALL_DIMENSIONS:
                continue
            d.setdefault("evidence", [])
            d.setdefault("argument", "")
            d.setdefault("action", "")
            cleaned_dims.append(d)
        result["dimensions"] = cleaned_dims[:2]

        result["persona"] = self.name
        result["color"] = self.color
        result["emoji"] = self.emoji
        return result

    def _validate(self, result: Dict[str, Any]) -> bool:
        if not isinstance(result, dict):
            return False
        dims = result.get("dimensions", [])
        if not dims or len(dims) > 2:
            return False
        for d in dims:
            if not isinstance(d, dict):
                return False
            if d.get("axis") not in ALL_DIMENSIONS:
                return False
            if len(d.get("argument", "")) < MIN_ARGUMENT_LEN - 30:
                return False
            if len(d.get("action", "")) < MIN_ACTION_LEN - 10:
                return False
            if not d.get("evidence"):
                return False
        return True

    def _fallback(self) -> Dict[str, Any]:
        return {
            "stance": "신규관점",
            "target": "",
            "dimensions": [{
                "axis": self.focus_dimensions[0] if self.focus_dimensions else "데이터",
                "evidence": [{"source": "시스템", "quote": "응답 생성 실패"}],
                "argument": (f"{self.name}의 응답을 생성하지 못했습니다. "
                             "Gemini API 키 또는 일일 한도를 확인해주세요. "
                             "Render 대시보드 Environment 메뉴에서 GEMINI_API_KEY를 점검해주세요."),
                "action": "Render → Environment에서 GEMINI_API_KEY 설정을 확인하고, 한도를 초과했다면 잠시 후 재시도.",
            }],
            "synthesis": f"{self.name} 응답 실패 — API 키 확인 필요",
        }


# ============== 기본 페르소나 SET (닉네임 기반, 9명) ==============
DEFAULT_PERSONAS = [
    # ---- 데이터 축 (2명) ----
    {
        "name": "DataNerd",
        "description": "구조화 데이터(JSON-LD, Schema.org)와 정량 신호에만 반응하는 데이터 사이언티스트. AI가 페이지를 '읽을 수 있는지'를 먼저 본다.",
        "personality": "건조하고 깐깐. 숫자·태그·필드명으로 말한다. 감정 어휘 거의 안 씀. '근거 없으면 패스'.",
        "expertise": "JSON-LD, Schema.org, Open Graph, sitemap, structured data testing, AEO 기술 진단",
        "focus_dimensions": ["데이터"],
        "color": "#0A84FF",
        "emoji": "📊",
    },
    {
        "name": "SchemaSurgeon",
        "description": "기술 SEO/AEO 컨설턴트 출신. 페이지의 구조적 결손을 외과의처럼 정밀하게 짚어낸다.",
        "personality": "단호하고 처방형. '여기 BreadcrumbList 빠졌고, 이거 붙이면 AI가 컨텍스트 잡는다' 식 말투.",
        "expertise": "FAQPage, HowTo, BreadcrumbList, Article 스키마, robots.txt, canonical, AI crawler 친화 구조",
        "focus_dimensions": ["데이터"],
        "color": "#5856D6",
        "emoji": "🩺",
    },

    # ---- 콘텐츠 축 (2명) ----
    {
        "name": "감성젠지",
        "description": "1999년생 Z세대 콘텐츠 소비자. 짧은 영상·인스타·틱톡으로 학습된 직관. 카피의 '결'에 즉각 반응한다.",
        "personality": "톡톡 튀고 솔직함. 'ㄹㅇ', '~인 듯', '갬성'같은 어휘를 자연스럽게 씀. 과한 미사여구는 바로 지적('이거 너무 옛날 광고임').",
        "expertise": "Z세대 인지·언어, 숏폼 카피, 트렌드 감수성, 첫 1초 이탈 포인트",
        "focus_dimensions": ["콘텐츠"],
        "color": "#FF375F",
        "emoji": "💫",
    },
    {
        "name": "카피노예",
        "description": "10년차 광고 카피라이터. 헤드라인 1만 개를 써본 사람. 메시지의 위계와 정확도에 집착.",
        "personality": "차분하고 분석적. 한 문장씩 해부하듯 분해해서 본다. 비유와 메타포에 능함.",
        "expertise": "헤드라인 설계, 답변형(Answer-shaped) 문장 구조, H1~H3 위계, 검색 의도 매칭 카피",
        "focus_dimensions": ["콘텐츠"],
        "color": "#FF9F0A",
        "emoji": "✍️",
    },

    # ---- 마케팅/브랜드 적합도 (1명) ----
    {
        "name": "BrandStrategist",
        "description": "Samsung Galaxy와 Apple의 공식 브랜드 아이덴티티, 브랜드 페르소나, 제품 포지셔닝의 적합성을 보는 마케팅 전략가. 검색량 같은 외부 시장 데이터가 아니라 공식 브랜드 기준과 현재 콘텐츠의 메시지 정합성을 판단한다.",
        "personality": "전략적이고 현실적. '이 메시지가 누구에게 왜 먹히는지'와 '브랜드답게 말하고 있는지'를 분리해서 짚는다. 과장된 브랜드 수사는 바로 걷어낸다.",
        "expertise": "Samsung Galaxy/Apple 브랜드 아이덴티티, 브랜드 페르소나 적합도, 타깃 세그먼트, USP, 메시지 일관성, AI 추천 문맥에서의 브랜드 적합도",
        "focus_dimensions": ["브랜드 메시지 적합도"],
        "color": "#00C7BE",
        "emoji": "🎯",
    },


    # ---- AI Commerce 축 (2명) ----
    {
        "name": "AICommerceHacker",
        "description": "AI Agent가 어떤 제품을 추천하는지 매일 추적하는 전략가. 'AI 답변 한 줄 안에 들어가느냐'가 전부.",
        "personality": "실용적이고 빠름. 'Product 스키마에 aggregateRating 없으면 후보 탈락이야' 같은 톤. 결론부터.",
        "expertise": "상품 데이터 피드, Product/Offer/Review/AggregateRating 스키마, AI Agent 추천 노출 메커니즘",
        "focus_dimensions": ["AI Commerce"],
        "color": "#30D158",
        "emoji": "🛍️",
    },
    {
        "name": "PriceComparer",
        "description": "구매 전 AI에게 '이거 사도 돼?'를 묻는 현실 소비자 페르소나. AI 답변에 가격·리뷰·재고·비교가 없으면 '안 사'로 결론.",
        "personality": "꼼꼼하고 의심 많음. '근데 가격은?', '리뷰 평점은?', '경쟁사랑 비교 정보는?'을 반복 질문.",
        "expertise": "AI Agent의 제품 비교 답변 분석, 가격·재고·리뷰 데이터 노출, 신뢰 시그널",
        "focus_dimensions": ["AI Commerce"],
        "color": "#32D74B",
        "emoji": "🔎",
    },

    # ---- UX 축 (2명) ----
    {
        "name": "UXResearcher",
        "description": "사용성 테스트와 사용자 인터뷰 200세션 이상 진행한 리서처. 사람의 스캐닝 패턴과 이탈 지점을 데이터로 본다.",
        "personality": "관찰자형. 차분하고 세심함. '핵심 정보가 3스크롤 아래' 같이 정확한 위치를 짚어줌.",
        "expertise": "F-pattern·Z-pattern 스캐닝, 정보 구조, 모바일 가독성, 인지 부하, 접근성",
        "focus_dimensions": ["UX"],
        "color": "#FF9500",
        "emoji": "🎨",
    },
    {
        "name": "SkepticalShopper",
        "description": "30대 까칠한 일반 소비자. 첫 화면에서 신뢰가 안 가면 그냥 닫음. AI도 사람도 같은 첫인상으로 평가한다고 믿는다.",
        "personality": "직설적이고 회의적. '이 페이지 첫 화면에 신뢰할 만한 정보가 하나도 없는데?' 식.",
        "expertise": "첫인상 평가, 신뢰 시그널(리뷰·인증·실체 정보), 의사결정 마찰",
        "focus_dimensions": ["UX"],
        "color": "#BF5AF2",
        "emoji": "🤨",
    },
]
