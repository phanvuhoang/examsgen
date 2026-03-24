import os
import shutil
import logging
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from typing import Optional
from backend.database import get_db
from backend.config import DATA_DIR

router = APIRouter(prefix="/api/sessions", tags=["sessions"])
logger = logging.getLogger(__name__)

TAX_TYPES = ["CIT", "VAT", "PIT", "FCT", "TP", "TaxAdmin"]
FILE_TYPES = ["regulation", "syllabus", "rates", "sample"]


class SessionCreate(BaseModel):
    name: str
    exam_date: Optional[str] = None      # e.g. "Jun2026"
    assumed_date: Optional[str] = None   # e.g. "1 June 2026"


class SessionUpdate(BaseModel):
    name: Optional[str] = None
    exam_date: Optional[str] = None
    assumed_date: Optional[str] = None


@router.get("/")
def list_sessions():
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT s.id, s.name, s.exam_date, s.assumed_date, s.is_default, s.created_at,
                   (SELECT COUNT(*) FROM session_files WHERE session_id = s.id AND is_active = TRUE) as file_count,
                   (SELECT COUNT(*) FROM questions WHERE session_id = s.id) as question_count
            FROM exam_sessions s ORDER BY s.created_at DESC
        """)
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in rows]


@router.post("/")
def create_session(session: SessionCreate):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO exam_sessions (name, exam_date, assumed_date)
            VALUES (%s, %s, %s) RETURNING id
        """, (session.name, session.exam_date, session.assumed_date))
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
    return {"ok": True}


@router.post("/{session_id}/set-default")
def set_default_session(session_id: int):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("UPDATE exam_sessions SET is_default = FALSE")
        cur.execute("UPDATE exam_sessions SET is_default = TRUE WHERE id = %s", (session_id,))
    return {"ok": True}


@router.delete("/{session_id}")
def delete_session(session_id: int):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM exam_sessions")
        if cur.fetchone()[0] <= 1:
            raise HTTPException(400, "Cannot delete the last session")
        cur.execute("SELECT id, file_path FROM session_files WHERE session_id = %s", (session_id,))
        files = cur.fetchall()
        cur.execute("DELETE FROM generation_log WHERE question_id IN (SELECT id FROM questions WHERE session_id = %s)", (session_id,))
        cur.execute("DELETE FROM questions WHERE session_id = %s", (session_id,))
        cur.execute("DELETE FROM session_files WHERE session_id = %s", (session_id,))
        cur.execute("DELETE FROM exam_sessions WHERE id = %s", (session_id,))
    # Remove physical files
    for _, file_path in files:
        if file_path:
            full = os.path.join(DATA_DIR, file_path) if not os.path.isabs(file_path) else file_path
            if os.path.isfile(full):
                os.remove(full)
    return {"ok": True}


@router.get("/{session_id}/files")
def list_session_files(session_id: int, file_type: Optional[str] = None):
    with get_db() as conn:
        cur = conn.cursor()
        query = """
            SELECT id, file_type, tax_type, exam_type, display_name, file_name,
                   file_path, file_size, is_active, uploaded_at
            FROM session_files WHERE session_id = %s
        """
        params = [session_id]
        if file_type:
            query += " AND file_type = %s"
            params.append(file_type)
        query += " ORDER BY file_type, tax_type, uploaded_at ASC"
        cur.execute(query, params)
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in rows]


@router.post("/{session_id}/files")
async def upload_file(
    session_id: int,
    file_type: str = Form(...),       # regulation | syllabus | rates | sample
    tax_type: str = Form("ALL"),      # CIT | VAT | PIT | FCT | TP | TaxAdmin | ALL
    exam_type: str = Form("ALL"),     # MCQ | Scenario | Longform | ALL (for sample files)
    display_name: str = Form(""),
    file: UploadFile = File(...),
):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id FROM exam_sessions WHERE id = %s", (session_id,))
        if not cur.fetchone():
            raise HTTPException(404, "Session not found")

    # Build path: sessions/{session_id}/{file_type}/{tax_type}/filename
    rel_dir = os.path.join("sessions", str(session_id), file_type, tax_type)
    dest_dir = os.path.join(DATA_DIR, rel_dir)
    os.makedirs(dest_dir, exist_ok=True)
    dest_path = os.path.join(dest_dir, file.filename)

    content = await file.read()
    with open(dest_path, "wb") as f:
        f.write(content)

    rel_path = os.path.join(rel_dir, file.filename)
    name = display_name or file.filename

    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO session_files
              (session_id, file_type, tax_type, exam_type, display_name, file_name, file_path, file_size)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id
        """, (session_id, file_type, tax_type, exam_type, name, file.filename, rel_path, len(content)))
        file_id = cur.fetchone()[0]

    return {"id": file_id, "file_name": file.filename, "file_path": rel_path}


@router.delete("/{session_id}/files/{file_id}")
def delete_file(session_id: int, file_id: int):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT file_path FROM session_files WHERE id = %s AND session_id = %s", (file_id, session_id))
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, "File not found")
        file_path = row[0]
        cur.execute("DELETE FROM session_files WHERE id = %s", (file_id,))
    if file_path:
        full = os.path.join(DATA_DIR, file_path) if not os.path.isabs(file_path) else file_path
        if os.path.isfile(full):
            os.remove(full)
    return {"ok": True}


@router.put("/{session_id}/files/{file_id}/toggle")
def toggle_file(session_id: int, file_id: int):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "UPDATE session_files SET is_active = NOT is_active WHERE id = %s AND session_id = %s RETURNING is_active",
            (file_id, session_id)
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, "File not found")
        return {"is_active": row[0]}


@router.post("/{session_id}/carry-forward")
def carry_forward(session_id: int, data: dict):
    """Copy all file records (and physical files) from another session into this session."""
    from_session_id = data.get("from_session_id")
    if not from_session_id:
        raise HTTPException(400, "from_session_id required")

    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, file_type, tax_type, exam_type, display_name, file_name, file_path, file_size FROM session_files WHERE session_id = %s AND is_active = TRUE", (from_session_id,))
        src_files = cur.fetchall()

    copied = 0
    for row in src_files:
        _, file_type, tax_type, exam_type, display_name, file_name, src_rel_path, file_size = row
        # Build new path for target session
        rel_dir = os.path.join("sessions", str(session_id), file_type, tax_type or "ALL")
        dest_dir = os.path.join(DATA_DIR, rel_dir)
        os.makedirs(dest_dir, exist_ok=True)
        dest_rel_path = os.path.join(rel_dir, file_name)

        # Copy physical file if it exists
        src_full = os.path.join(DATA_DIR, src_rel_path) if src_rel_path and not os.path.isabs(src_rel_path) else src_rel_path
        dest_full = os.path.join(DATA_DIR, dest_rel_path)
        if src_full and os.path.isfile(src_full) and not os.path.isfile(dest_full):
            shutil.copy2(src_full, dest_full)

        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO session_files
                  (session_id, file_type, tax_type, exam_type, display_name, file_name, file_path, file_size)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT DO NOTHING
            """, (session_id, file_type, tax_type, exam_type, display_name, file_name, dest_rel_path, file_size))
        copied += 1

    return {"ok": True, "copied": copied}


@router.get("/{session_id}/samples/preview")
def get_sample_previews(session_id: int, sac_thue: str, exam_type: str = "MCQ"):
    """Return list of sample files with first 400 chars of text content as preview."""
    from backend.context_builder import _load_files
    from backend.document_extractor import extract_text

    files = _load_files(session_id, "sample", tax_type=sac_thue, exam_type=exam_type)
    result = []
    for f in files:
        file_path = f["path"]
        if not os.path.isabs(file_path):
            file_path = os.path.join(DATA_DIR, file_path)
        try:
            text = extract_text(file_path)
            preview = text[:400].strip()
        except Exception:
            preview = ""
        result.append({
            "name": f["name"] or f["path"],
            "tax_type": f["tax_type"],
            "exam_type": f["exam_type"],
            "preview": preview,
        })
    return result


@router.get("/{session_id}/stats")
def session_stats(session_id: int):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM session_files WHERE session_id = %s", (session_id,))
        files = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM questions WHERE session_id = %s", (session_id,))
        questions = cur.fetchone()[0]
    return {"files": files, "questions": questions}
