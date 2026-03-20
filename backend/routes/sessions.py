from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from datetime import date
from backend.database import get_db
from backend.ai_provider import call_ai, parse_ai_json_list
import json
import os
import logging

router = APIRouter(prefix="/api/sessions", tags=["sessions"])
logger = logging.getLogger(__name__)


class SessionCreate(BaseModel):
    name: str
    exam_window_start: Optional[date] = None
    exam_window_end: Optional[date] = None
    regulations_cutoff: date
    fiscal_year_end: date
    tax_year: int
    description: Optional[str] = None


class SessionUpdate(BaseModel):
    name: Optional[str] = None
    exam_window_start: Optional[date] = None
    exam_window_end: Optional[date] = None
    regulations_cutoff: Optional[date] = None
    fiscal_year_end: Optional[date] = None
    tax_year: Optional[int] = None
    description: Optional[str] = None


@router.get("/")
def list_sessions():
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT s.id, s.name, s.exam_window_start, s.exam_window_end,
                   s.regulations_cutoff, s.fiscal_year_end, s.tax_year,
                   s.description, s.is_active, s.is_default, s.created_at,
                   (SELECT COUNT(*) FROM kb_syllabus WHERE session_id = s.id) as syllabus_count,
                   (SELECT COUNT(*) FROM kb_regulation WHERE session_id = s.id) as regulation_count,
                   (SELECT COUNT(*) FROM kb_sample WHERE session_id = s.id) as sample_count,
                   (SELECT COUNT(*) FROM questions WHERE session_id = s.id) as question_count
            FROM exam_sessions s ORDER BY s.exam_window_start DESC
        """)
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in rows]


@router.post("/")
def create_session(session: SessionCreate):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO exam_sessions (name, exam_window_start, exam_window_end,
                regulations_cutoff, fiscal_year_end, tax_year, description)
            VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id
        """, (session.name, session.exam_window_start, session.exam_window_end,
              session.regulations_cutoff, session.fiscal_year_end,
              session.tax_year, session.description))
        return {"id": cur.fetchone()[0]}


@router.put("/{session_id}")
def update_session(session_id: int, session: SessionUpdate):
    with get_db() as conn:
        cur = conn.cursor()
        updates = {k: v for k, v in session.dict().items() if v is not None}
        if not updates:
            return {"ok": True}
        set_clause = ", ".join(f"{k} = %s" for k in updates)
        cur.execute(f"UPDATE exam_sessions SET {set_clause} WHERE id = %s",
                    list(updates.values()) + [session_id])


@router.post("/{session_id}/set-default")
def set_default_session(session_id: int):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("UPDATE exam_sessions SET is_default = FALSE")
        cur.execute("UPDATE exam_sessions SET is_default = TRUE WHERE id = %s", (session_id,))


@router.post("/{session_id}/clone-from/{source_id}")
def clone_session(session_id: int, source_id: int):
    """Copy all KB items from source session into target session."""
    with get_db() as conn:
        cur = conn.cursor()
        for table in ['kb_syllabus', 'kb_regulation', 'kb_sample']:
            if table == 'kb_syllabus':
                cur.execute("""
                    INSERT INTO kb_syllabus (sac_thue, section_code, section_title, content, tags, source_file, is_active, session_id)
                    SELECT sac_thue, section_code, section_title, content, tags, source_file, is_active, %s
                    FROM kb_syllabus WHERE session_id = %s
                """, (session_id, source_id))
            elif table == 'kb_regulation':
                cur.execute("""
                    INSERT INTO kb_regulation (sac_thue, regulation_ref, content, tags, syllabus_ids, source_file, is_active, session_id)
                    SELECT sac_thue, regulation_ref, content, tags, '{}', source_file, is_active, %s
                    FROM kb_regulation WHERE session_id = %s
                """, (session_id, source_id))
            else:
                cur.execute("""
                    INSERT INTO kb_sample (question_type, sac_thue, title, content, exam_tricks, syllabus_ids, regulation_ids, source, session_id)
                    SELECT question_type, sac_thue, title, content, exam_tricks, '{}', '{}', source, %s
                    FROM kb_sample WHERE session_id = %s
                """, (session_id, source_id))
        return {"ok": True, "message": f"KB cloned from session {source_id}"}


@router.post("/{session_id}/parse-and-match")
def parse_and_match(session_id: int, data: dict):
    """AI-powered: parse a regulation/syllabus file into chunks, then auto-match to syllabus items."""
    file_path = f"/app/data/{data['file_path']}"
    if not os.path.exists(file_path):
        raise HTTPException(404, f"File not found: {data['file_path']}")

    from backend.context_builder import extract_text_from_file
    text = extract_text_from_file(file_path)
    text_for_ai = text[:15000]
    file_type = data.get("file_type", "regulation")
    sac_thue = data.get("sac_thue", "CIT")

    chunk_prompt = f"""Parse this Vietnamese tax {file_type} document into logical chunks for an exam question database.

Each chunk = one coherent rule or topic (one article, clause, or syllabus item).

For each chunk return:
- section_code: article/section number if present
- section_title: short title max 8 words
- content: full text of this chunk (preserve original wording)
- tags: 3-8 comma-separated English keywords

Return ONLY valid JSON array, no markdown, no extra text:
[{{"section_code":"...","section_title":"...","content":"...","tags":"..."}}]

DOCUMENT TYPE: {file_type} | TAX TYPE: {sac_thue}

DOCUMENT:
{text_for_ai}"""

    chunk_result = call_ai(chunk_prompt, model_tier="fast")
    chunks = parse_ai_json_list(chunk_result["content"])

    # If regulation, try to match to existing syllabus items for this session
    syllabus_items = []
    if file_type == "regulation":
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("SELECT id, section_code, section_title, tags FROM kb_syllabus WHERE session_id = %s AND sac_thue = %s",
                        (session_id, sac_thue))
            syllabus_items = [{"id": r[0], "section_code": r[1], "section_title": r[2], "tags": r[3]} for r in cur.fetchall()]

    match_map = {}
    if syllabus_items and len(chunks) <= 30:
        match_prompt = f"""Given these regulation chunks and syllabus items, suggest which syllabus item(s) each regulation chunk maps to.

SYLLABUS ITEMS:
{json.dumps(syllabus_items, ensure_ascii=False)}

REGULATION CHUNKS (indexed 0-based):
{json.dumps([{"index": i, "section_code": c.get("section_code"), "section_title": c.get("section_title"), "tags": c.get("tags")} for i, c in enumerate(chunks)], ensure_ascii=False)}

Return ONLY valid JSON array mapping chunk index to syllabus ids:
[{{"chunk_index": 0, "syllabus_ids": [1, 3]}}, ...]

If no match, use empty array for syllabus_ids. Cover all {len(chunks)} chunks."""

        match_result = call_ai(match_prompt, model_tier="fast")
        try:
            matches = parse_ai_json_list(match_result["content"])
            match_map = {m["chunk_index"]: m.get("syllabus_ids", []) for m in matches}
        except Exception:
            match_map = {}

    for i, chunk in enumerate(chunks):
        chunk["suggested_syllabus_ids"] = match_map.get(i, [])
        chunk["index"] = i

    return {
        "chunks": chunks,
        "total": len(chunks),
        "file_type": file_type,
        "sac_thue": sac_thue,
        "session_id": session_id,
        "has_syllabus_matches": bool(match_map),
    }


@router.post("/{session_id}/save-parsed-chunks")
def save_parsed_chunks(session_id: int, data: dict):
    """Save approved chunks from parse-and-match into KB tables."""
    chunks = data.get("chunks", [])
    file_type = data.get("file_type")
    sac_thue = data.get("sac_thue")
    source_file = data.get("source_file", "")
    saved = []

    with get_db() as conn:
        cur = conn.cursor()
        for chunk in chunks:
            if not chunk.get("content", "").strip():
                continue
            if file_type == "syllabus":
                cur.execute("""
                    INSERT INTO kb_syllabus (sac_thue, section_code, section_title, content, tags, source_file, session_id)
                    VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id
                """, (sac_thue, chunk.get("section_code"), chunk.get("section_title"),
                      chunk["content"], chunk.get("tags"), source_file, session_id))
            else:
                cur.execute("""
                    INSERT INTO kb_regulation (sac_thue, regulation_ref, content, tags, syllabus_ids, source_file, session_id)
                    VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id
                """, (sac_thue, chunk.get("section_code"), chunk["content"],
                      chunk.get("tags"), chunk.get("suggested_syllabus_ids", []),
                      source_file, session_id))
            saved.append(cur.fetchone()[0])

    return {"saved": len(saved), "ids": saved}
