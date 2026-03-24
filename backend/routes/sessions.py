import os
import shutil
import logging
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, BackgroundTasks
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

    if file_type == "sample":
        from backend.document_extractor import parse_sample_examples
        full_path = os.path.join(DATA_DIR, rel_path)
        # Small delay to ensure file is fully flushed to disk
        import time; time.sleep(0.1)
        examples = parse_sample_examples(full_path)
        if examples:
            with get_db() as conn:
                cur = conn.cursor()
                cur.execute("DELETE FROM sample_examples WHERE file_id = %s", (file_id,))
                for ex in examples:
                    cur.execute("""
                        INSERT INTO sample_examples (session_id, file_id, example_number, title, content, tax_type, exam_type)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """, (session_id, file_id, ex["example_number"], ex["title"], ex["content"], tax_type, exam_type))
            logger.info(f"Parsed {len(examples)} examples from {file.filename}")
        else:
            logger.warning(f"No examples found in {file.filename} — check 'Example N:' headings")

    return {"id": file_id, "file_name": file.filename, "file_path": rel_path, "examples_parsed": len(examples) if file_type == "sample" else 0}


@router.delete("/{session_id}/files/{file_id}")
def delete_file(session_id: int, file_id: int):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT file_path FROM session_files WHERE id = %s AND session_id = %s", (file_id, session_id))
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, "File not found")
        file_path = row[0]
        # Delete parsed examples first (FK cascade may not be set)
        cur.execute("DELETE FROM sample_examples WHERE file_id = %s", (file_id,))
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


@router.get("/{session_id}/examples")
def list_sample_examples(session_id: int, sac_thue: str = None, exam_type: str = None):
    """List parsed sample examples for a session, optionally filtered."""
    with get_db() as conn:
        cur = conn.cursor()
        query = """
            SELECT se.id, se.file_id, se.example_number, se.title,
                   LEFT(se.content, 200) as preview,
                   se.syllabus_codes, se.tax_type, se.exam_type,
                   sf.display_name as file_name
            FROM sample_examples se
            JOIN session_files sf ON se.file_id = sf.id
            WHERE se.session_id = %s
        """
        params = [session_id]
        if sac_thue:
            query += " AND se.tax_type = %s"
            params.append(sac_thue)
        if exam_type:
            query += " AND se.exam_type = %s"
            params.append(exam_type)
        query += " ORDER BY se.tax_type, se.exam_type, se.example_number"
        cur.execute(query, params)
        rows = cur.fetchall()
    return [
        {
            "id": r[0], "file_id": r[1], "example_number": r[2],
            "title": r[3], "preview": r[4], "syllabus_codes": r[5] or [],
            "tax_type": r[6], "exam_type": r[7], "file_name": r[8],
        }
        for r in rows
    ]


@router.post("/{session_id}/files/{file_id}/reparse")
def reparse_sample_file(session_id: int, file_id: int):
    """Re-parse a sample file into examples. Useful when file was uploaded before fix or after editing."""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT file_path, tax_type, exam_type FROM session_files WHERE id = %s AND session_id = %s AND file_type = 'sample'",
            (file_id, session_id)
        )
        row = cur.fetchone()
    if not row:
        raise HTTPException(404, "Sample file not found")

    rel_path, tax_type, exam_type = row
    full_path = os.path.join(DATA_DIR, rel_path) if not os.path.isabs(rel_path) else rel_path

    from backend.document_extractor import parse_sample_examples
    examples = parse_sample_examples(full_path)

    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM sample_examples WHERE file_id = %s", (file_id,))
        for ex in examples:
            cur.execute("""
                INSERT INTO sample_examples (session_id, file_id, example_number, title, content, tax_type, exam_type)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (session_id, file_id, ex["example_number"], ex["title"], ex["content"], tax_type, exam_type))

    return {"ok": True, "examples_parsed": len(examples)}


@router.get("/{session_id}/examples/{example_id}/full")
def get_example_full(session_id: int, example_id: int):
    """Get full content of a specific example."""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT content, title, syllabus_codes FROM sample_examples WHERE id = %s AND session_id = %s",
                    (example_id, session_id))
        row = cur.fetchone()
    if not row:
        raise HTTPException(404, "Example not found")
    return {"content": row[0], "title": row[1], "syllabus_codes": row[2] or []}


@router.post("/{session_id}/examples/{example_id}/tag")
def tag_example_with_ai(session_id: int, example_id: int):
    """Use AI to tag this example with syllabus codes."""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT content, tax_type FROM sample_examples WHERE id = %s AND session_id = %s",
                    (example_id, session_id))
        row = cur.fetchone()
    if not row:
        raise HTTPException(404, "Example not found")

    content, tax_type = row
    from backend.ai_provider import call_ai
    import json as _json
    prompt = f"""Read this ACCA TX(VNM) exam question and identify which ACCA syllabus codes it tests.

TAX TYPE: {tax_type}

QUESTION:
{content[:2000]}

Return ONLY a JSON array of syllabus code strings, e.g.: ["C2d", "C2n", "C3a"]
Use the short code format (e.g. C2d, P4a, V2b) — not verbose descriptions.
Return [] if you cannot determine the codes."""

    result = call_ai(prompt, model_tier="fast")
    try:
        text = result["content"].strip()
        import re as _re
        match = _re.search(r'\[.*?\]', text, _re.DOTALL)
        codes = _json.loads(match.group()) if match else []
    except Exception:
        codes = []

    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("UPDATE sample_examples SET syllabus_codes = %s WHERE id = %s",
                    (codes, example_id))
    return {"syllabus_codes": codes}


@router.post("/{session_id}/examples/tag-all")
def tag_all_examples(session_id: int, background_tasks: BackgroundTasks):
    """Queue AI tagging for all untagged examples in this session."""
    def _tag_all():
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("SELECT id FROM sample_examples WHERE session_id = %s AND (syllabus_codes IS NULL OR syllabus_codes = '{}')",
                        (session_id,))
            ids = [r[0] for r in cur.fetchall()]
        for eid in ids:
            try:
                tag_example_with_ai(session_id, eid)
            except Exception as e:
                logger.warning(f"Tag failed for example {eid}: {e}")
    background_tasks.add_task(_tag_all)
    return {"message": f"Tagging queued for session {session_id}"}


@router.get("/{session_id}/variables")
def list_variables(session_id: int):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, var_key, var_label, var_value, var_unit, description
            FROM session_variables WHERE session_id = %s ORDER BY id
        """, (session_id,))
        rows = cur.fetchall()
    return [{"id": r[0], "key": r[1], "label": r[2], "value": r[3], "unit": r[4], "description": r[5]} for r in rows]


@router.post("/{session_id}/variables")
def create_variable(session_id: int, data: dict):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO session_variables (session_id, var_key, var_label, var_value, var_unit, description)
            VALUES (%s, %s, %s, %s, %s, %s) RETURNING id
        """, (session_id, data["key"], data["label"], data["value"], data.get("unit", ""), data.get("description", "")))
        new_id = cur.fetchone()[0]
    return {"id": new_id}


@router.put("/{session_id}/variables/{var_id}")
def update_variable(session_id: int, var_id: int, data: dict):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            UPDATE session_variables SET var_label=%s, var_value=%s, var_unit=%s, description=%s
            WHERE id=%s AND session_id=%s
        """, (data["label"], data["value"], data.get("unit", ""), data.get("description", ""), var_id, session_id))
    return {"ok": True}


@router.delete("/{session_id}/variables/{var_id}")
def delete_variable(session_id: int, var_id: int):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM session_variables WHERE id=%s AND session_id=%s", (var_id, session_id))
    return {"ok": True}


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
