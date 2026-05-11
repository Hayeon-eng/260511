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
import io
import logging
import uuid
from typing import List, Optional

from fastapi import FastAPI, Request, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse, PlainTextResponse
from pydantic import BaseModel

import database as db
from crawler import crawl_url
from analyzer import analyze_content
from discussion import generate_digest
from persona import Persona, ALL_DIMENSIONS, DEFAULT_PERSONAS
from file_handler import extract_pdf_text, load_image

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


class SessionIn(BaseModel):
    query: str
    url: str = ""
    personas: List[dict]
    attachment_ids: List[str] = []
    title: str = ""
    max_rounds: int = 3


class TurnIn(BaseModel):
    persona_name: str  # 누구의 차례인가


# ============== 기본 ==============
@app.get("/")
async def home():
    index = os.path.join(BASE_DIR, "index.html")
    if os.path.exists(index):
        return FileResponse(index)
    return JSONResponse({"message": "index.html을 찾을 수 없습니다."})


@app.get("/health")
async def health():
    return {"status": "ok", "gemini": bool(os.getenv("GEMINI_API_KEY"))}


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
    """DB에 페르소나가 0개일 때 기본 SET 시드. 이미 있으면 건너뜀."""
    existing = db.list_personas()
    if existing:
        return {"seeded": 0, "personas": existing}
    created = []
    for p in DEFAULT_PERSONAS:
        created.append(db.create_persona(p))
    return {"seeded": len(created), "personas": created}


# ============== 세션 ==============
@app.post("/api/sessions")
async def create_session(body: SessionIn):
    if not body.query.strip():
        raise HTTPException(400, "토론 주제(query) 필수")
    if not body.url and not body.attachment_ids:
        raise HTTPException(400, "URL 또는 첨부파일 중 최소 1개 필요")

    # 1. 세션 레코드 생성
    sid = db.create_session(
        query=body.query,
        url=body.url,
        personas_json=body.personas,
        title=body.title,
        max_rounds=max(1, min(20, body.max_rounds or 3)),
    )

    # 2. 크롤링 (URL 있을 때만)
    crawl = {}
    if body.url:
        crawl = crawl_url(body.url)
    else:
        crawl = {"ok": True, "url": "", "text": "", "title": "", "images": [],
                 "schemas": [], "aeo_checks": {}}

    # 3. 첨부 텍스트와 이미지 수집
    extra_texts: List[str] = []
    extra_images = []
    for aid in body.attachment_ids:
        att = db.get_attachment(aid)
        if not att:
            continue
        # 세션 연결
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

    # 4. 분석
    analysis = analyze_content(crawl, extra_texts=extra_texts, extra_images=extra_images)

    # 5. DB 저장
    db.update_session_analysis(sid, crawl, analysis)
    return {"session_id": sid, "analysis": analysis, "crawl_meta": {
        "title": crawl.get("title", ""),
        "url": crawl.get("url", ""),
        "schemas_count": len(crawl.get("schemas", [])),
        "images_count": len(crawl.get("images", [])),
    }}


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

    # 라운드 계산
    personas_per_round = max(1, len(s.get("personas", [])))
    round_no = db.current_round(sid, personas_per_round)

    # 응답 생성
    turn = persona.respond(s["query"], context, analysis, history)
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
    for ax in ["데이터", "콘텐츠", "AI Commerce", "UX"]:
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
        for ax in ["데이터", "콘텐츠", "AI Commerce", "UX"]:
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

    return PlainTextResponse("\n".join(lines), media_type="text/markdown; charset=utf-8")
