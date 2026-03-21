import json
import os
import re
import shutil
import logging
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from typing import Optional
from datetime import date
from backend.database import get_db
from backend.ai_provider import call_ai, parse_ai_json_list
from backend.config import DATA_DIR

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


class SessionSettingsPatch(BaseModel):
    parameters: Optional[list] = None
    tax_types: Optional[list] = None
    question_types: Optional[list] = None


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


def _make_folder_name(name: str) -> str:
    """Convert session name to folder-safe name."""
    return re.sub(r'[^a-z0-9_]', '', name.lower().replace(' ', '_'))


@router.post("/")
def create_session(session: SessionCreate):
    folder_name = _make_folder_name(session.name)
    folder_path = f"sessions/{folder_name}"
    # Create session folder structure
    for sub in ['regulations', 'syllabus', 'samples']:
        os.makedirs(os.path.join(DATA_DIR, folder_path, sub), exist_ok=True)
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO exam_sessions (name, exam_window_start, exam_window_end,
                regulations_cutoff, fiscal_year_end, tax_year, description, folder_path)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id
        """, (session.name, session.exam_window_start, session.exam_window_end,
              session.regulations_cutoff, session.fiscal_year_end,
              session.tax_year, session.description, folder_path))
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


@router.patch("/{session_id}")
def patch_session_settings(session_id: int, data: SessionSettingsPatch):
    """Update session settings: parameters, tax_types, question_types."""
    updates = {}
    if data.parameters is not None:
        updates['parameters'] = json.dumps(data.parameters)
    if data.tax_types is not None:
        updates['tax_types'] = json.dumps(data.tax_types)
    if data.question_types is not None:
        updates['question_types'] = json.dumps(data.question_types)
    if not updates:
        return {"ok": True}
    with get_db() as conn:
        cur = conn.cursor()
        set_clause = ", ".join(f"{k} = %s" for k in updates)
        cur.execute(f"UPDATE exam_sessions SET {set_clause} WHERE id = %s",
                    list(updates.values()) + [session_id])
    return {"ok": True}


@router.get("/{session_id}/settings")
def get_session_settings(session_id: int):
    """Get session settings: parameters, tax_types, question_types."""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT parameters, tax_types, question_types FROM exam_sessions WHERE id = %s", (session_id,))
        row = cur.fetchone()
    if not row:
        raise HTTPException(404, "Session not found")
    return {
        "parameters": row[0] or [],
        "tax_types": row[1] or [],
        "question_types": row[2] or [],
    }


@router.post("/{session_id}/set-default")
def set_default_session(session_id: int):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("UPDATE exam_sessions SET is_default = FALSE")
        cur.execute("UPDATE exam_sessions SET is_default = TRUE WHERE id = %s", (session_id,))


@router.post("/{session_id}/clone-from/{source_id}")
def clone_session(session_id: int, source_id: int):
    """Copy all KB items and settings from source session into target session."""
    with get_db() as conn:
        cur = conn.cursor()

        # Copy session settings (parameters, tax_types, question_types)
        cur.execute("""
            UPDATE exam_sessions t SET
                parameters = s.parameters,
                tax_types = s.tax_types,
                question_types = s.question_types
            FROM exam_sessions s
            WHERE s.id = %s AND t.id = %s
        """, (source_id, session_id))

        # Copy kb_syllabus
        cur.execute("""
            INSERT INTO kb_syllabus (sac_thue, section_code, section_title, content, tags, source_file, is_active, session_id,
                                     tax_type, syllabus_code, topic, detailed_syllabus)
            SELECT sac_thue, section_code, section_title, content, tags, source_file, is_active, %s,
                   tax_type, syllabus_code, topic, detailed_syllabus
            FROM kb_syllabus WHERE session_id = %s
        """, (session_id, source_id))

        # Copy kb_regulation
        cur.execute("""
            INSERT INTO kb_regulation (sac_thue, regulation_ref, content, tags, syllabus_ids, source_file, is_active, session_id)
            SELECT sac_thue, regulation_ref, content, tags, '{}', source_file, is_active, %s
            FROM kb_regulation WHERE session_id = %s
        """, (session_id, source_id))

        # Copy kb_regulation_parsed
        cur.execute("""
            INSERT INTO kb_regulation_parsed (session_id, tax_type, reg_code, doc_ref, article_no, paragraph_no,
                                              paragraph_text, syllabus_codes, tags, source_file, is_active)
            SELECT %s, tax_type, reg_code, doc_ref, article_no, paragraph_no,
                   paragraph_text, syllabus_codes, tags, source_file, is_active
            FROM kb_regulation_parsed WHERE session_id = %s
        """, (session_id, source_id))

        # Copy kb_tax_rates
        cur.execute("""
            INSERT INTO kb_tax_rates (session_id, tax_type, table_name, content, source_file, display_order, is_active)
            SELECT %s, tax_type, table_name, content, source_file, display_order, is_active
            FROM kb_tax_rates WHERE session_id = %s
        """, (session_id, source_id))

        # Copy kb_sample
        cur.execute("""
            INSERT INTO kb_sample (question_type, sac_thue, title, content, exam_tricks, syllabus_ids, regulation_ids, source, session_id)
            SELECT question_type, sac_thue, title, content, exam_tricks, '{}', '{}', source, %s
            FROM kb_sample WHERE session_id = %s
        """, (session_id, source_id))

    # Copy uploaded files via shutil
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT folder_path FROM exam_sessions WHERE id = %s", (source_id,))
        row = cur.fetchone()
        src_folder = row[0] if row else None
        cur.execute("SELECT folder_path FROM exam_sessions WHERE id = %s", (session_id,))
        row = cur.fetchone()
        dst_folder = row[0] if row else None

    if src_folder and dst_folder:
        for sub in ['regulations', 'syllabus', 'samples']:
            src_path = os.path.join(DATA_DIR, src_folder, sub)
            dst_path = os.path.join(DATA_DIR, dst_folder, sub)
            if os.path.isdir(src_path):
                if os.path.isdir(dst_path):
                    shutil.rmtree(dst_path)
                shutil.copytree(src_path, dst_path)

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
            elif file_type == "sample_questions":
                cur.execute("""
                    INSERT INTO kb_sample (question_type, sac_thue, title, content, exam_tricks, source, session_id)
                    VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id
                """, (chunk.get("question_type", "MCQ"), sac_thue, chunk.get("section_title", chunk.get("title", "")),
                      chunk["content"], chunk.get("tags", ""), f"parsed:{source_file}", session_id))
            else:
                cur.execute("""
                    INSERT INTO kb_regulation (sac_thue, regulation_ref, content, tags, syllabus_ids, source_file, session_id)
                    VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id
                """, (sac_thue, chunk.get("section_code"), chunk["content"],
                      chunk.get("tags"), chunk.get("suggested_syllabus_ids", []),
                      source_file, session_id))
            saved.append(cur.fetchone()[0])

    return {"saved": len(saved), "ids": saved}


@router.delete("/{session_id}")
def delete_session(session_id: int):
    """Delete a session and all its related data."""
    with get_db() as conn:
        cur = conn.cursor()
        # Ensure not deleting the last session
        cur.execute("SELECT COUNT(*) FROM exam_sessions")
        if cur.fetchone()[0] <= 1:
            raise HTTPException(400, "Cannot delete the last session")
        # Get session folder
        cur.execute("SELECT folder_path FROM exam_sessions WHERE id = %s", (session_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, "Session not found")
        folder_path = row[0]
        # Delete related records
        cur.execute("DELETE FROM kb_syllabus WHERE session_id = %s", (session_id,))
        cur.execute("DELETE FROM kb_regulation WHERE session_id = %s", (session_id,))
        cur.execute("DELETE FROM kb_sample WHERE session_id = %s", (session_id,))
        cur.execute("DELETE FROM generation_log WHERE question_id IN (SELECT id FROM questions WHERE session_id = %s)", (session_id,))
        cur.execute("DELETE FROM questions WHERE session_id = %s", (session_id,))
        cur.execute("DELETE FROM regulations WHERE session_id = %s", (session_id,))
        cur.execute("DELETE FROM exam_sessions WHERE id = %s", (session_id,))
    # Remove folder
    if folder_path:
        full_path = os.path.join(DATA_DIR, folder_path)
        if os.path.isdir(full_path):
            shutil.rmtree(full_path, ignore_errors=True)
    return {"ok": True}


@router.get("/{session_id}/stats")
def session_stats(session_id: int):
    """Get counts for delete confirmation."""
    with get_db() as conn:
        cur = conn.cursor()
        counts = {}
        for table, col in [('kb_syllabus', 'syllabus'), ('kb_regulation', 'regulations'),
                           ('kb_sample', 'samples'), ('questions', 'questions'), ('regulations', 'files')]:
            cur.execute(f"SELECT COUNT(*) FROM {table} WHERE session_id = %s", (session_id,))
            counts[col] = cur.fetchone()[0]
    return counts


DOC_TYPE_SUBFOLDER = {
    "regulation": "regulations",
    "syllabus": "syllabus",
    "sample_questions": "samples",
}


@router.post("/{session_id}/upload-doc")
async def upload_doc(session_id: int, doc_type: str = Form(...), sac_thue: str = Form("CIT"), file: UploadFile = File(...)):
    """Upload a document file into the session's folder."""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT folder_path FROM exam_sessions WHERE id = %s", (session_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, "Session not found")
        folder_path = row[0]

    subfolder = DOC_TYPE_SUBFOLDER.get(doc_type, "regulations")
    dest_dir = os.path.join(DATA_DIR, folder_path, subfolder)
    os.makedirs(dest_dir, exist_ok=True)
    dest_path = os.path.join(dest_dir, file.filename)

    content = await file.read()
    with open(dest_path, "wb") as f:
        f.write(content)

    rel_path = f"{folder_path}/{subfolder}/{file.filename}"

    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO regulations (sac_thue, file_path, file_name, doc_type, session_id, is_active) "
            "VALUES (%s, %s, %s, %s, %s, TRUE) RETURNING id",
            (sac_thue, rel_path, file.filename, doc_type, session_id)
        )
        reg_id = cur.fetchone()[0]

    return {"id": reg_id, "file_name": file.filename, "file_path": rel_path, "doc_type": doc_type}


@router.get("/{session_id}/files")
def list_session_files(session_id: int, doc_type: Optional[str] = None):
    """List uploaded files for a session, optionally filtered by doc_type."""
    with get_db() as conn:
        cur = conn.cursor()
        query = "SELECT id, sac_thue, file_name, file_path, doc_type, is_active, uploaded_at FROM regulations WHERE session_id = %s"
        params = [session_id]
        if doc_type:
            query += " AND doc_type = %s"
            params.append(doc_type)
        query += " ORDER BY uploaded_at DESC"
        cur.execute(query, params)
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in rows]


@router.delete("/{session_id}/files/{file_id}")
def delete_session_file(session_id: int, file_id: int):
    """Delete an uploaded file."""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT file_path FROM regulations WHERE id = %s AND session_id = %s", (file_id, session_id))
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, "File not found")
        file_path = row[0]
        cur.execute("DELETE FROM regulations WHERE id = %s", (file_id,))
    # Remove physical file
    full_path = os.path.join(DATA_DIR, file_path)
    if os.path.isfile(full_path):
        os.remove(full_path)
    return {"ok": True}
