"""
SQLite 데이터베이스 (분석 축 dimensions 포함).
테이블:
- personas: 사용자 정의 페르소나 라이브러리 (focus_dimensions 추가)
- sessions: 토론 세션
- turns: 페르소나 발언 (dimensions_json 추가)
- attachments: 업로드된 파일 메타
- digests: 라이브 요약 스냅샷
"""

import os
import json
import sqlite3
import uuid
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional

log = logging.getLogger(__name__)

DB_PATH = os.getenv("DB_PATH", "discussion.db")

# 분석 표준 축
DIMENSIONS = ["데이터", "콘텐츠", "커머스", "기술", "UX", "브랜드"]


def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    with _conn() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS personas (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT DEFAULT '',
            personality TEXT DEFAULT '',
            expertise TEXT DEFAULT '',
            focus_dimensions TEXT DEFAULT '[]',
            color TEXT DEFAULT '#007AFF',
            emoji TEXT DEFAULT '💬',
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,
            title TEXT DEFAULT '',
            query TEXT NOT NULL,
            url TEXT DEFAULT '',
            crawl_json TEXT DEFAULT '',
            analysis_json TEXT DEFAULT '',
            personas_json TEXT DEFAULT '[]',
            max_rounds INTEGER DEFAULT 3,
            mode TEXT DEFAULT 'single',
            side_a_json TEXT DEFAULT '',
            side_b_json TEXT DEFAULT '',
            label_a TEXT DEFAULT '',
            label_b TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS turns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            round INTEGER DEFAULT 1,
            persona TEXT NOT NULL,
            color TEXT DEFAULT '#007AFF',
            emoji TEXT DEFAULT '💬',
            stance TEXT DEFAULT '',
            target TEXT DEFAULT '',
            dimensions_json TEXT DEFAULT '[]',
            synthesis TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS attachments (
            id TEXT PRIMARY KEY,
            session_id TEXT,
            filename TEXT,
            kind TEXT,
            text TEXT,
            meta_json TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS digests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            round INTEGER DEFAULT 1,
            digest_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_turns_session ON turns(session_id, id);
        CREATE INDEX IF NOT EXISTS idx_digests_session ON digests(session_id, id);
        """)
        # 안전 마이그레이션 (기존 DB에 컬럼이 없을 때만 추가)
        for col, ddl in [
            ("max_rounds", "INTEGER DEFAULT 3"),
            ("mode", "TEXT DEFAULT 'single'"),
            ("side_a_json", "TEXT DEFAULT ''"),
            ("side_b_json", "TEXT DEFAULT ''"),
            ("label_a", "TEXT DEFAULT ''"),
            ("label_b", "TEXT DEFAULT ''"),
        ]:
            try:
                c.execute(f"ALTER TABLE sessions ADD COLUMN {col} {ddl}")
            except sqlite3.OperationalError:
                pass


# ============= PERSONAS =============
def list_personas() -> List[Dict[str, Any]]:
    with _conn() as c:
        rows = c.execute("SELECT * FROM personas ORDER BY created_at DESC").fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["focus_dimensions"] = json.loads(d.get("focus_dimensions") or "[]")
            result.append(d)
        return result


def create_persona(data: Dict[str, Any]) -> Dict[str, Any]:
    pid = str(uuid.uuid4())
    with _conn() as c:
        c.execute("""
            INSERT INTO personas (id, name, description, personality, expertise,
                                  focus_dimensions, color, emoji, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            pid,
            data["name"],
            data.get("description", ""),
            data.get("personality", ""),
            data.get("expertise", ""),
            json.dumps(data.get("focus_dimensions", []), ensure_ascii=False),
            data.get("color", "#007AFF"),
            data.get("emoji", "💬"),
            datetime.now().isoformat(),
        ))
    return get_persona(pid)


def get_persona(pid: str) -> Optional[Dict[str, Any]]:
    with _conn() as c:
        row = c.execute("SELECT * FROM personas WHERE id = ?", (pid,)).fetchone()
        if not row:
            return None
        d = dict(row)
        d["focus_dimensions"] = json.loads(d.get("focus_dimensions") or "[]")
        return d


def update_persona(pid: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    fields = {
        "name": data.get("name"),
        "description": data.get("description"),
        "personality": data.get("personality"),
        "expertise": data.get("expertise"),
        "color": data.get("color"),
        "emoji": data.get("emoji"),
    }
    sets = []
    params = []
    for k, v in fields.items():
        if v is not None:
            sets.append(f"{k} = ?")
            params.append(v)
    if "focus_dimensions" in data:
        sets.append("focus_dimensions = ?")
        params.append(json.dumps(data["focus_dimensions"], ensure_ascii=False))
    if not sets:
        return get_persona(pid)
    params.append(pid)
    with _conn() as c:
        c.execute(f"UPDATE personas SET {', '.join(sets)} WHERE id = ?", params)
    return get_persona(pid)


def delete_persona(pid: str) -> bool:
    with _conn() as c:
        c.execute("DELETE FROM personas WHERE id = ?", (pid,))
    return True


# ============= SESSIONS =============
def create_session(query: str, url: str, personas_json: List[Dict[str, Any]],
                   title: str = "", max_rounds: int = 3,
                   mode: str = "single",
                   label_a: str = "", label_b: str = "") -> str:
    sid = str(uuid.uuid4())
    now = datetime.now().isoformat()
    with _conn() as c:
        c.execute("""
            INSERT INTO sessions (id, title, query, url, personas_json, max_rounds,
                                  mode, label_a, label_b, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (sid, title or query[:50], query, url,
              json.dumps(personas_json, ensure_ascii=False), max_rounds,
              mode, label_a, label_b, now, now))
    return sid


def update_session_sides(sid: str,
                         side_a: Dict[str, Any] = None,
                         side_b: Dict[str, Any] = None):
    """비교 모드의 좌/우 분석 결과 저장."""
    fields, params = [], []
    if side_a is not None:
        fields.append("side_a_json = ?")
        params.append(json.dumps(side_a, ensure_ascii=False, default=str))
    if side_b is not None:
        fields.append("side_b_json = ?")
        params.append(json.dumps(side_b, ensure_ascii=False, default=str))
    if not fields:
        return
    fields.append("updated_at = ?")
    params.append(datetime.now().isoformat())
    params.append(sid)
    with _conn() as c:
        c.execute(f"UPDATE sessions SET {', '.join(fields)} WHERE id = ?", params)


def update_session_analysis(sid: str, crawl: Dict[str, Any], analysis: Dict[str, Any]):
    with _conn() as c:
        c.execute("""
            UPDATE sessions SET crawl_json = ?, analysis_json = ?, updated_at = ?
            WHERE id = ?
        """, (
            json.dumps(crawl, ensure_ascii=False, default=str),
            json.dumps(analysis, ensure_ascii=False),
            datetime.now().isoformat(),
            sid,
        ))


def get_session(sid: str) -> Optional[Dict[str, Any]]:
    with _conn() as c:
        row = c.execute("SELECT * FROM sessions WHERE id = ?", (sid,)).fetchone()
        if not row:
            return None
        d = dict(row)
        d["personas"] = json.loads(d.get("personas_json") or "[]")
        d["crawl"] = json.loads(d.get("crawl_json") or "{}") if d.get("crawl_json") else {}
        d["analysis"] = json.loads(d.get("analysis_json") or "{}") if d.get("analysis_json") else {}
        d["side_a"] = json.loads(d.get("side_a_json") or "{}") if d.get("side_a_json") else {}
        d["side_b"] = json.loads(d.get("side_b_json") or "{}") if d.get("side_b_json") else {}
        return d


def list_sessions(limit: int = 100) -> List[Dict[str, Any]]:
    with _conn() as c:
        rows = c.execute("""
            SELECT id, title, query, url, created_at, updated_at
            FROM sessions ORDER BY updated_at DESC LIMIT ?
        """, (limit,)).fetchall()
        return [dict(r) for r in rows]


def delete_session(sid: str) -> bool:
    with _conn() as c:
        c.execute("DELETE FROM sessions WHERE id = ?", (sid,))
    return True


def touch_session(sid: str):
    with _conn() as c:
        c.execute("UPDATE sessions SET updated_at = ? WHERE id = ?",
                  (datetime.now().isoformat(), sid))


# ============= TURNS =============
def add_turn(sid: str, round_no: int, turn: Dict[str, Any]) -> Dict[str, Any]:
    now = datetime.now().isoformat()
    with _conn() as c:
        cur = c.execute("""
            INSERT INTO turns (session_id, round, persona, color, emoji, stance, target,
                               dimensions_json, synthesis, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            sid, round_no,
            turn.get("persona", ""),
            turn.get("color", "#007AFF"),
            turn.get("emoji", "💬"),
            turn.get("stance", ""),
            turn.get("target", ""),
            json.dumps(turn.get("dimensions", []), ensure_ascii=False),
            turn.get("synthesis", ""),
            now,
        ))
        turn_id = cur.lastrowid
    touch_session(sid)
    return {**turn, "id": turn_id, "session_id": sid, "round": round_no, "created_at": now}


def list_turns(sid: str) -> List[Dict[str, Any]]:
    with _conn() as c:
        rows = c.execute("""
            SELECT * FROM turns WHERE session_id = ? ORDER BY id ASC
        """, (sid,)).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["dimensions"] = json.loads(d.get("dimensions_json") or "[]")
            result.append(d)
        return result


def count_turns(sid: str) -> int:
    with _conn() as c:
        row = c.execute("SELECT COUNT(*) AS n FROM turns WHERE session_id = ?", (sid,)).fetchone()
        return row["n"] if row else 0


def current_round(sid: str, personas_per_round: int) -> int:
    """현재 라운드 번호 (1-based)."""
    n = count_turns(sid)
    if personas_per_round <= 0:
        return 1
    return (n // personas_per_round) + 1


# ============= ATTACHMENTS =============
def add_attachment(sid: Optional[str], filename: str, kind: str,
                   text: str, meta: Dict[str, Any]) -> str:
    aid = str(uuid.uuid4())
    with _conn() as c:
        c.execute("""
            INSERT INTO attachments (id, session_id, filename, kind, text, meta_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (aid, sid, filename, kind, text or "",
              json.dumps(meta, ensure_ascii=False, default=str),
              datetime.now().isoformat()))
    return aid


def list_attachments(sid: str) -> List[Dict[str, Any]]:
    with _conn() as c:
        rows = c.execute("""
            SELECT id, filename, kind, created_at FROM attachments
            WHERE session_id = ? ORDER BY id ASC
        """, (sid,)).fetchall()
        return [dict(r) for r in rows]


def get_attachment(aid: str) -> Optional[Dict[str, Any]]:
    with _conn() as c:
        row = c.execute("SELECT * FROM attachments WHERE id = ?", (aid,)).fetchone()
        if not row:
            return None
        d = dict(row)
        d["meta"] = json.loads(d.get("meta_json") or "{}")
        return d


# ============= DIGESTS =============
def add_digest(sid: str, round_no: int, digest: Dict[str, Any]) -> Dict[str, Any]:
    now = datetime.now().isoformat()
    with _conn() as c:
        cur = c.execute("""
            INSERT INTO digests (session_id, round, digest_json, created_at)
            VALUES (?, ?, ?, ?)
        """, (sid, round_no, json.dumps(digest, ensure_ascii=False), now))
    return {**digest, "id": cur.lastrowid, "round": round_no, "created_at": now}


def latest_digest(sid: str) -> Optional[Dict[str, Any]]:
    with _conn() as c:
        row = c.execute("""
            SELECT * FROM digests WHERE session_id = ? ORDER BY id DESC LIMIT 1
        """, (sid,)).fetchone()
        if not row:
            return None
        d = dict(row)
        d["digest"] = json.loads(d.get("digest_json") or "{}")
        return d


# 초기화
init_db()
