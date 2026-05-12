"""
FastAPI 메인 앱.

엔드포인트:
  GET    /                            메인 페이지
  GET    /health                      헬스체크
  GET    /api/config                  앱 설정 (axis 목록, 기본 페르소나)

  GET    /api/personas                페르소나 목록
  POST   /api/personas                페르소나 생성
  PATCH  /api/personas/{id}           페르소나 수정
  DELETE /api/personas/{id}           페르소나 삭제
  POST   /api/personas/seed_defaults  기본 SET 시드

  GET    /api/sessions                세션 목록
  POST   /api/sessions                세션 생성 (크롤링 + 분석 동시 수행)
  GET    /api/sessions/{id}           세션 상세 (분석 + 발언 + 다이제스트)
  DELETE /api/sessions/{id}           세션 삭제
  GET    /api/sessions/{id}/export    마크다운 내보내기

  POST   /api/sessions/{id}/turn      한 페르소나의 다음 발언 생성
  POST   /api/sessions/{id}/digest    라이브 다이제스트 갱신

  POST   /api/upload                  파일 업로드 (PDF/이미지)
"""

import os
import re
import io
import logging
import uuid
import requests
from urllib.parse import quote
from typing import List, Optional

from fastapi import FastAPI, Request, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse, PlainTextResponse, Response
from pydantic import BaseModel

import database as db
from crawler import crawl_url
from analyzer import analyze_content
from discussion import generate_digest, generate_executive_summary
from persona import Persona, ALL_DIMENSIONS, DEFAULT_PERSONAS
from file_handler import extract_pdf_text, load_image
import export as exporter

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("main")

app = FastAPI(title="AEO Discussion Platform")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


@app.get("/assets/{asset_name}")
async def flat_asset(asset_name: str):
    """Serve split frontend files kept at repository root.

    Physical folders are not required for GitHub web upload.
    Only files named js_*.js or css_*.css are exposed.
    """
    if not re.fullmatch(r"(?:js|css)_\d{2}_[A-Za-z0-9_]+\.(?:js|css)", asset_name):
        raise HTTPException(404, "asset not found")

    path = os.path.join(BASE_DIR, asset_name)
    if not os.path.isfile(path):
        raise HTTPException(404, "asset not found")

    media_type = "application/javascript" if asset_name.endswith(".js") else "text/css"
    return FileResponse(path, media_type=media_type)


# ============== Pydantic 모델 ==============
class PersonaIn(BaseModel):
    name: str
    description: str = ""
    personality: str = ""
    expertise: str = ""
    focus_dimensions: List[str] = []
    color: str = "#007AFF"
    emoji: str = "💬"


class PersonaPatch(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    personality: Optional[str] = None
    expertise: Optional[str] = None
    focus_dimensions: Optional[List[str]] = None
    color: Optional[str] = None
    emoji: Optional[str] = None


class SideIn(BaseModel):
    label: str = ""
    url: str = ""
    copy_text: str = ""
    attachment_ids: List[str] = []
    image_urls: List[str] = []


class SessionIn(BaseModel):
    query: str
    url: str = ""
    copy_text: str = ""
    personas: List[dict]
    attachment_ids: List[str] = []
    image_urls: List[str] = []
    title: str = ""
    max_rounds: int = 1
    mode: str = "single"  # 'single' | 'compare'
    side_a: Optional[SideIn] = None
    side_b: Optional[SideIn] = None


class TurnIn(BaseModel):
    persona_name: str


class AskIn(BaseModel):
    question: str
    persona_names: Optional[List[str]] = None  # None이면 모든 페르소나에게


# ============== 기본 ==============
@app.get("/")
async def home():
    index = os.path.join(BASE_DIR, "index.html")
    if os.path.exists(index):
        return FileResponse(index)
    return JSONResponse({"message": "index.html을 찾을 수 없습니다."})


@app.get("/style.css")
async def css():
    p = os.path.join(BASE_DIR, "style.css")
    return FileResponse(p, media_type="text/css") if os.path.exists(p) else JSONResponse({}, 404)


@app.get("/app.js")
async def appjs():
    p = os.path.join(BASE_DIR, "app.js")
    return FileResponse(p, media_type="application/javascript") if os.path.exists(p) else JSONResponse({}, 404)


@app.get("/health")
async def health():
    """기본 헬스 + ?probe=1 로 실제 모델 호출 테스트."""
    from fastapi import Request
    has_key = bool(os.getenv("GEMINI_API_KEY"))
    info = {
        "status": "ok",
        "gemini_key_set": has_key,
        "model": os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
    }
    return info


@app.get("/health/probe")
async def health_probe():
    """실제로 Gemini를 한 번 호출해서 모델이 살아있는지 확인 (디버그용)."""
    try:
        from gemini_llm import GeminiLLM
        llm = GeminiLLM()
        text = llm.generate("Say 'pong' in one word.", max_tokens=20, temperature=0)
        return {"ok": True, "model": llm.model_name, "response": text[:100]}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.get("/health/probe2")
async def health_probe2():
    """실제 페르소나 호출과 동일한 조건으로 진단 (한국어 JSON, 긴 컨텍스트)."""
    try:
        from gemini_llm import GeminiLLM
        llm = GeminiLLM(system_instruction="당신은 한국어로 응답하는 AI 분석가입니다. 항상 JSON으로만 응답합니다.")
        prompt = """
다음 분석을 JSON으로 응답하세요.

[데이터]
- 제목: Apple iPhone 16 Pro
- URL: https://apple.com/iphone-16-pro
- AEO 점수: 87/100

JSON 스키마:
{
  "summary": "한 줄 요약",
  "score": 0-100,
  "reason": "이유"
}
"""
        result = llm.generate_json(prompt, temperature=0.3, max_tokens=500)
        return {
            "ok": bool(result),
            "model": llm.model_name,
            "result": result,
            "note": "비어있으면 안전필터 또는 모델 응답 거부일 가능성. 로그 확인 필요."
        }
    except Exception as e:
        return {"ok": False, "error": str(e), "type": type(e).__name__}


@app.get("/api/config")
async def get_config():
    return {
        "dimensions": ALL_DIMENSIONS,
        "default_personas": DEFAULT_PERSONAS,
        "gemini_configured": bool(os.getenv("GEMINI_API_KEY")),
    }


# ============== 페르소나 ==============
@app.get("/api/personas")
async def list_personas():
    return {"personas": db.list_personas()}


@app.post("/api/personas")
async def create_persona(body: PersonaIn):
    if not body.name.strip():
        raise HTTPException(400, "이름 필수")
    return db.create_persona(body.model_dump())


@app.patch("/api/personas/{pid}")
async def update_persona(pid: str, body: PersonaPatch):
    data = {k: v for k, v in body.model_dump().items() if v is not None}
    p = db.update_persona(pid, data)
    if not p:
        raise HTTPException(404, "페르소나 없음")
    return p


@app.delete("/api/personas/{pid}")
async def delete_persona(pid: str):
    db.delete_persona(pid)
    return {"ok": True}


@app.post("/api/personas/seed_defaults")
async def seed_defaults():
    """기본 SET 시드. 이미 있는 페르소나는 유지하고, 새 기본 페르소나만 추가."""
    existing = db.list_personas()
    existing_by_name = {p.get("name"): p for p in existing}
    created = []
    updated = 0
    for p in DEFAULT_PERSONAS:
        name = p.get("name")
        if name not in existing_by_name:
            created.append(db.create_persona(p))
        elif name == "BrandStrategist":
            current = existing_by_name[name]
            if current.get("focus_dimensions") != p.get("focus_dimensions"):
                db.update_persona(current["id"], p)
                updated += 1
    personas = db.list_personas()
    return {"seeded": len(created), "updated": updated, "personas": personas}


# ============== 세션 ==============
def _fetch_remote_image(image_url: str):
    """외부 이미지 URL을 내려받아 Gemini Vision에 전달할 PIL Image로 변환."""
    try:
        r = requests.get(image_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=12)
        r.raise_for_status()
        content_type = r.headers.get("content-type", "")
        if "image" not in content_type.lower():
            log.warning(f"이미지 URL이 image content-type이 아님: {image_url} ({content_type})")
        if len(r.content) > 8 * 1024 * 1024:
            log.warning(f"이미지 URL 용량 초과로 건너뜀: {image_url}")
            return None
        img, meta = load_image(r.content)
        if not img:
            log.warning(f"원격 이미지 로드 실패: {image_url} / {meta}")
        return img
    except Exception as e:
        log.warning(f"원격 이미지 다운로드 실패: {image_url} / {e}")
        return None


def _gather_side(url: str, attachment_ids: List[str], sid: str, copy_text: str = "", image_urls: List[str] = None):
    """URL+첨부파일+직접 입력 카피+이미지 URL → (crawl, analysis) 결과 반환."""
    copy_text = (copy_text or "").strip()
    image_urls = image_urls or []
    crawl = {}
    if url:
        crawl = crawl_url(url)
    elif copy_text:
        crawl = {
            "ok": True,
            "url": "",
            "type": "copy_text",
            "title": "직접 입력 카피 문구",
            "meta_description": "",
            "meta_keywords": "",
            "og": {},
            "twitter": {},
            "headings": {"h1": ["직접 입력 카피"], "h2": [], "h3": []},
            "text": copy_text[:6000],
            "images": [],
            "images_missing_alt": 0,
            "schemas": [],
            "aeo_checks": {
                "has_title": True,
                "has_meta_desc": False,
                "has_h1": True,
                "has_og": False,
                "has_schema": False,
                "has_faq_schema": False,
                "image_alt_coverage": 0.0,
                "body_length": len(copy_text[:6000]),
                "is_direct_copy_text": True,
            },
        }
    else:
        crawl = {"ok": True, "url": "", "text": "",
                 "title": "KV 이미지 프리셋" if image_urls else "",
                 "images": [{"src": u, "alt": "KV 이미지 프리셋"} for u in image_urls],
                 "schemas": [], "aeo_checks": {"has_title": bool(image_urls), "body_length": 0}}

    extra_texts: List[str] = []
    if copy_text and url:
        extra_texts.append(f"[직접 입력 카피 문구]\n{copy_text[:6000]}")
    extra_images = []
    for aid in attachment_ids or []:
        att = db.get_attachment(aid)
        if not att:
            continue
        with db._conn() as c:
            c.execute("UPDATE attachments SET session_id = ? WHERE id = ?", (sid, aid))
        if att.get("kind") == "pdf" and att.get("text"):
            extra_texts.append(f"[PDF: {att.get('filename')}]\n{att['text']}")
        elif att.get("kind") == "image":
            img_path = att.get("meta", {}).get("path")
            if img_path and os.path.exists(img_path):
                with open(img_path, "rb") as f:
                    img, _ = load_image(f.read())
                    if img:
                        extra_images.append(img)

    if image_urls:
        safe_urls = []
        for image_url in image_urls[:4]:
            image_url = (image_url or "").strip()
            if not image_url.startswith(("http://", "https://")):
                continue
            safe_urls.append(image_url)
            img = _fetch_remote_image(image_url)
            if img:
                extra_images.append(img)
        if safe_urls:
            extra_texts.append("[KV 이미지 프리셋 URL]\n" + "\n".join(safe_urls))

    analysis = analyze_content(crawl, extra_texts=extra_texts, extra_images=extra_images)
    return crawl, analysis


@app.post("/api/sessions")
async def create_session(body: SessionIn):
    if not body.query.strip():
        raise HTTPException(400, "토론 주제(query) 필수")
    mode = body.mode if body.mode in ("single", "compare") else "single"

    if mode == "single":
        if not body.url and not body.attachment_ids and not body.copy_text.strip() and not body.image_urls:
            raise HTTPException(400, "URL, 첨부파일, 카피 문구, KV 이미지 중 최소 1개 필요")
    else:  # compare
        if not body.side_a or not body.side_b:
            raise HTTPException(400, "비교 모드는 side_a, side_b 둘 다 필요")
        a, b = body.side_a, body.side_b
        if (not a.url and not a.attachment_ids and not a.copy_text.strip() and not a.image_urls) or (not b.url and not b.attachment_ids and not b.copy_text.strip() and not b.image_urls):
            raise HTTPException(400, "양쪽 모두 URL, 첨부파일, 카피 문구, KV 이미지 중 최소 1개 필요")

    # 세션 레코드
    sid = db.create_session(
        query=body.query,
        url=body.url if mode == "single" else "",
        personas_json=body.personas,
        title=body.title,
        max_rounds=max(1, min(20, body.max_rounds or 1)),
        mode=mode,
        label_a=(body.side_a.label if body.side_a else ""),
        label_b=(body.side_b.label if body.side_b else ""),
    )

    if mode == "single":
        crawl, analysis = _gather_side(body.url, body.attachment_ids, sid, body.copy_text, body.image_urls)
        db.update_session_analysis(sid, crawl, analysis)
        return {
            "session_id": sid,
            "mode": mode,
            "analysis": analysis,
            "crawl_meta": {
                "title": crawl.get("title", ""),
                "url": crawl.get("url", ""),
                "schemas_count": len(crawl.get("schemas", [])),
                "images_count": len(crawl.get("images", [])),
            },
        }

    # compare
    a_crawl, a_analysis = _gather_side(body.side_a.url, body.side_a.attachment_ids, sid, body.side_a.copy_text, body.side_a.image_urls)
    b_crawl, b_analysis = _gather_side(body.side_b.url, body.side_b.attachment_ids, sid, body.side_b.copy_text, body.side_b.image_urls)
    side_a = {
        "label": body.side_a.label or "A",
        "url": body.side_a.url,
        "copy_text": body.side_a.copy_text,
        "image_urls": body.side_a.image_urls,
        "crawl": a_crawl,
        "analysis": a_analysis,
    }
    side_b = {
        "label": body.side_b.label or "B",
        "url": body.side_b.url,
        "copy_text": body.side_b.copy_text,
        "image_urls": body.side_b.image_urls,
        "crawl": b_crawl,
        "analysis": b_analysis,
    }
    db.update_session_sides(sid, side_a=side_a, side_b=side_b)
    return {
        "session_id": sid,
        "mode": mode,
        "side_a": {"label": side_a["label"], "url": side_a["url"], "analysis": a_analysis},
        "side_b": {"label": side_b["label"], "url": side_b["url"], "analysis": b_analysis},
    }


@app.get("/api/sessions")
async def list_sessions():
    return {"sessions": db.list_sessions()}


@app.get("/api/sessions/{sid}")
async def get_session(sid: str):
    s = db.get_session(sid)
    if not s:
        raise HTTPException(404, "세션 없음")
    s["turns"] = db.list_turns(sid)
    s["digest"] = db.latest_digest(sid)
    s["attachments"] = db.list_attachments(sid)
    return s


@app.delete("/api/sessions/{sid}")
async def delete_session(sid: str):
    db.delete_session(sid)
    return {"ok": True}


# ============== 토론 한 턴 ==============
@app.post("/api/sessions/{sid}/turn")
async def next_turn(sid: str, body: TurnIn):
    s = db.get_session(sid)
    if not s:
        raise HTTPException(404, "세션 없음")

    # 발화자 찾기
    p_data = None
    for p in s.get("personas", []):
        if p.get("name") == body.persona_name:
            p_data = p
            break
    if not p_data:
        raise HTTPException(400, f"세션에 '{body.persona_name}' 페르소나가 없음")

    # 페르소나 객체 생성
    persona = Persona(
        name=p_data["name"],
        description=p_data.get("description", ""),
        personality=p_data.get("personality", ""),
        expertise=p_data.get("expertise", ""),
        focus_dimensions=p_data.get("focus_dimensions", []),
        color=p_data.get("color", "#007AFF"),
        emoji=p_data.get("emoji", "💬"),
    )

    # 컨텍스트
    context = s.get("crawl", {}).get("text", "") or ""
    analysis = s.get("analysis", {}) or {}
    history = db.list_turns(sid)

    # 비교 모드면 양쪽 데이터 준비
    compare = None
    if s.get("mode") == "compare":
        a = s.get("side_a", {}) or {}
        b = s.get("side_b", {}) or {}
        compare = {
            "label_a": s.get("label_a") or a.get("label") or "A",
            "label_b": s.get("label_b") or b.get("label") or "B",
            "side_a": {
                "url": a.get("url", ""),
                "context": (a.get("crawl", {}) or {}).get("text", ""),
                "analysis": a.get("analysis", {}) or {},
            },
            "side_b": {
                "url": b.get("url", ""),
                "context": (b.get("crawl", {}) or {}).get("text", ""),
                "analysis": b.get("analysis", {}) or {},
            },
        }
        # 비교 모드일 때는 context/analysis가 비어있을 수 있으므로 A쪽 데이터를 기본 컨텍스트로 활용
        if not context:
            context = compare["side_a"]["context"]
        if not analysis:
            analysis = compare["side_a"]["analysis"]

    # 라운드 계산
    personas_per_round = max(1, len(s.get("personas", [])))
    round_no = db.current_round(sid, personas_per_round)

    # 응답 생성
    turn = persona.respond(s["query"], context, analysis, history, compare=compare)
    saved = db.add_turn(sid, round_no, turn)
    return {"turn": saved, "round": round_no}


# ============== 다이제스트 ==============
@app.post("/api/sessions/{sid}/digest")
async def refresh_digest(sid: str):
    s = db.get_session(sid)
    if not s:
        raise HTTPException(404, "세션 없음")
    turns = db.list_turns(sid)
    digest = generate_digest(s["query"], turns)
    personas_per_round = max(1, len(s.get("personas", [])))
    round_no = db.current_round(sid, personas_per_round)
    saved = db.add_digest(sid, round_no, digest)
    return {"digest": saved}


# ============== 꼬리질문 ==============
@app.post("/api/sessions/{sid}/ask")
async def ask_followup(sid: str, body: AskIn):
    """사용자가 추가 질문 → 지정된 페르소나(들)가 차례로 답함."""
    if not body.question.strip():
        raise HTTPException(400, "질문 내용이 비어있습니다")

    s = db.get_session(sid)
    if not s:
        raise HTTPException(404, "세션 없음")

    # 대상 페르소나 결정
    all_personas = s.get("personas", []) or []
    if body.persona_names:
        targets = [p for p in all_personas if p.get("name") in body.persona_names]
    else:
        targets = all_personas
    if not targets:
        raise HTTPException(400, "응답할 페르소나가 없습니다")

    # 컨텍스트
    context = s.get("crawl", {}).get("text", "") or ""
    analysis = s.get("analysis", {}) or {}
    compare = None
    if s.get("mode") == "compare":
        a = s.get("side_a", {}) or {}
        b = s.get("side_b", {}) or {}
        compare = {
            "label_a": s.get("label_a") or a.get("label") or "A",
            "label_b": s.get("label_b") or b.get("label") or "B",
            "side_a": {
                "url": a.get("url", ""),
                "context": (a.get("crawl", {}) or {}).get("text", ""),
                "analysis": a.get("analysis", {}) or {},
            },
            "side_b": {
                "url": b.get("url", ""),
                "context": (b.get("crawl", {}) or {}).get("text", ""),
                "analysis": b.get("analysis", {}) or {},
            },
        }
        if not context:
            context = compare["side_a"]["context"]
        if not analysis:
            analysis = compare["side_a"]["analysis"]

    personas_per_round = max(1, len(all_personas))
    round_no = db.current_round(sid, personas_per_round)

    # 사용자 질문을 시스템 발언으로 기록
    user_turn = {
        "stance": "질문",
        "target": "",
        "dimensions": [],
        "synthesis": body.question.strip()[:200],
        "persona": "👤 사용자",
        "color": "#8E8E93",
        "emoji": "👤",
        "is_user": True,
    }
    saved_user = db.add_turn(sid, round_no, user_turn)
    answers = [saved_user]

    # 각 페르소나 차례로 응답
    history = db.list_turns(sid)
    for p_data in targets:
        persona = Persona(
            name=p_data["name"],
            description=p_data.get("description", ""),
            personality=p_data.get("personality", ""),
            expertise=p_data.get("expertise", ""),
            focus_dimensions=p_data.get("focus_dimensions", []),
            color=p_data.get("color", "#007AFF"),
            emoji=p_data.get("emoji", "💬"),
        )
        try:
            turn = persona.respond(s["query"], context, analysis, history,
                                   compare=compare, user_question=body.question)
            saved = db.add_turn(sid, round_no, turn)
            answers.append(saved)
            history.append(saved)
        except Exception as e:
            log.error(f"꼬리질문 응답 실패 ({persona.name}): {e}")

    return {"answers": answers, "round": round_no}


# ============== Executive Summary ==============
@app.post("/api/sessions/{sid}/executive_summary")
async def make_executive_summary(sid: str):
    s = db.get_session(sid)
    if not s:
        raise HTTPException(404, "세션 없음")
    s["turns"] = db.list_turns(sid)
    s["digest"] = db.latest_digest(sid)
    summary = generate_executive_summary(s)
    if summary.get("_ok") is False:
        reason = summary.get("error_reason") or "임원 요약 생성 실패"
        debug = summary.get("debug") or {}
        raw = (debug.get("raw_preview") or "").replace("\n", " ")[:240]
        if raw:
            reason = f"{reason} / 응답 일부: {raw}"
        raise HTTPException(502, reason)
    return {"summary": summary}


# ============== 업로드 ==============
UPLOAD_DIR = "/tmp/aeo_uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


@app.post("/api/upload")
async def upload(file: UploadFile = File(...)):
    name = file.filename or "file"
    content = await file.read()
    if not content:
        raise HTTPException(400, "빈 파일")

    lower = name.lower()
    kind = "other"
    text = ""
    meta = {}

    if lower.endswith(".pdf"):
        kind = "pdf"
        res = extract_pdf_text(content)
        if not res.get("ok"):
            raise HTTPException(400, f"PDF 추출 실패: {res.get('error')}")
        text = res.get("text", "")
        meta = {"page_count": res.get("page_count", 0)}
    elif any(lower.endswith(ext) for ext in (".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp")):
        kind = "image"
        # 파일 시스템에 저장 (Gemini에 전달하기 위해)
        path = os.path.join(UPLOAD_DIR, f"{uuid.uuid4().hex}_{name}")
        with open(path, "wb") as f:
            f.write(content)
        meta = {"path": path, "size": len(content)}
    else:
        raise HTTPException(400, "PDF 또는 이미지 파일만 지원됩니다.")

    aid = db.add_attachment(None, name, kind, text, meta)
    return {"id": aid, "filename": name, "kind": kind, "meta": meta}


# ============== 마크다운 내보내기 ==============
@app.get("/api/sessions/{sid}/export")
async def export_md(sid: str):
    s = db.get_session(sid)
    if not s:
        raise HTTPException(404, "세션 없음")
    turns = db.list_turns(sid)
    digest_row = db.latest_digest(sid)
    analysis = s.get("analysis", {})

    lines = [f"# {s.get('title') or s.get('query')}\n",
             f"- URL: {s.get('url') or '(없음)'}",
             f"- 생성: {s.get('created_at')}",
             f"- AEO 점수: {analysis.get('aeo_score', 0)}/100\n",
             "## 분석 요약",
             f"- 요약: {analysis.get('summary','')}",
             f"- 소비자 인식: {analysis.get('consumer_perception','')}\n",
             "## 축별 진단"]
    for ax in ["데이터", "콘텐츠", "AI Commerce", "UX", "브랜드 메시지 적합도"]:
        d = analysis.get("by_dimension", {}).get(ax, {})
        lines.append(f"### {ax} (score: {d.get('score',0)})")
        lines.append("**발견**\n" + "\n".join([f"- {x}" for x in d.get('findings', [])]) or "- 없음")
        lines.append("**부족**\n" + "\n".join([f"- {x}" for x in d.get('gaps', [])]) or "- 없음")
        lines.append("**액션**\n" + "\n".join([f"- {x}" for x in d.get('actions', [])]) or "- 없음")
        lines.append("")

    lines.append("## 토론")
    for t in turns:
        lines.append(f"### {t.get('emoji','')} {t.get('persona','')} ({t.get('stance','')}{' → ' + t.get('target','') if t.get('target') else ''})")
        lines.append(f"_{t.get('synthesis','')}_\n")
        for d in t.get("dimensions", []):
            lines.append(f"**[{d.get('axis','')}]**")
            for ev in d.get("evidence", []):
                lines.append(f"- 근거 ({ev.get('source','')}): {ev.get('quote','')}")
            lines.append(f"- 주장: {d.get('argument','')}")
            lines.append(f"- 액션: {d.get('action','')}")
            lines.append("")

    if digest_row:
        digest = digest_row.get("digest", {})
        lines.append("## 라이브 다이제스트")
        lines.append(f"**헤드라인**: {digest.get('headline','')}\n")
        for ax in ["데이터", "콘텐츠", "AI Commerce", "UX", "브랜드 메시지 적합도"]:
            d = digest.get("by_dimension", {}).get(ax, {})
            lines.append(f"### {ax}")
            if d.get("consensus"):
                lines.append("**합의**: " + " / ".join(d["consensus"]))
            if d.get("conflicts"):
                lines.append("**충돌**: " + " / ".join(d["conflicts"]))
            if d.get("actions"):
                lines.append("**액션**:")
                for a in d["actions"]:
                    lines.append(f"- {a}")
            lines.append("")
        if digest.get("top_insights"):
            lines.append("### 통합 인사이트")
            for i in digest["top_insights"]:
                lines.append(f"- {i}")
        if digest.get("next_questions"):
            lines.append("### 다음 라운드 질문")
            for q in digest["next_questions"]:
                lines.append(f"- {q}")

    fname = (s.get("title") or "aeo_session").replace("/", "_")[:60] + ".md"
    return PlainTextResponse(
        "\n".join(lines),
        media_type="text/markdown; charset=utf-8",
        headers=_download_headers(fname, "aeo_session.md"),
    )




def _download_headers(filename: str, fallback: str) -> dict:
    safe = quote(filename or fallback)
    return {"Content-Disposition": f"attachment; filename=\"{fallback}\"; filename*=UTF-8''{safe}"}

# ============== Excel / PPT Export ==============
def _session_payload(sid: str) -> dict:
    """Export용 전체 페이로드 (session + turns + digest 통합)."""
    s = db.get_session(sid)
    if not s:
        return None
    s["turns"] = db.list_turns(sid)
    s["digest"] = db.latest_digest(sid)
    return s


@app.get("/api/sessions/{sid}/export/xlsx")
async def export_xlsx(sid: str):
    data = _session_payload(sid)
    if not data:
        raise HTTPException(404, "세션 없음")
    try:
        blob = exporter.generate_xlsx(data)
    except Exception as e:
        log.error(f"xlsx 생성 실패: {e}")
        raise HTTPException(500, f"Excel 생성 실패: {e}")
    fname = (data.get("title") or "aeo_session").replace("/", "_")[:60] + ".xlsx"
    return Response(
        content=blob,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=_download_headers(fname, "aeo_session.xlsx"),
    )


@app.get("/api/sessions/{sid}/export/pptx")
async def export_pptx(sid: str):
    data = _session_payload(sid)
    if not data:
        raise HTTPException(404, "세션 없음")
    try:
        blob = exporter.generate_pptx(data)
    except Exception as e:
        log.error(f"pptx 생성 실패: {e}")
        raise HTTPException(500, f"PowerPoint 생성 실패: {e}")
    fname = (data.get("title") or "aeo_session").replace("/", "_")[:60] + ".pptx"
    return Response(
        content=blob,
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        headers=_download_headers(fname, "aeo_session.pptx"),
    )
