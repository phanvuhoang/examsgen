from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
import json
import logging

from backend.database import get_db
from backend.ai_provider import call_ai, parse_ai_json_list

router = APIRouter(prefix="/api/kb", tags=["kb"])
logger = logging.getLogger(__name__)


# --- Models ---

class SyllabusItem(BaseModel):
    sac_thue: str
    section_code: Optional[str] = None
    section_title: Optional[str] = None
    content: str
    tags: Optional[str] = None
    source_file: Optional[str] = None
    session_id: Optional[int] = None


class RegulationItem(BaseModel):
    sac_thue: str
    regulation_ref: Optional[str] = None
    content: str
    tags: Optional[str] = None
    syllabus_ids: Optional[List[int]] = []
    source_file: Optional[str] = None
    session_id: Optional[int] = None


class SampleItem(BaseModel):
    question_type: str
    sac_thue: str
    title: Optional[str] = None
    content: str
    exam_tricks: Optional[str] = None
    syllabus_ids: Optional[List[int]] = []
    regulation_ids: Optional[List[int]] = []
    source: str = "manual"
    session_id: Optional[int] = None


class ParseRequest(BaseModel):
    file_type: str        # "syllabus" | "regulation"
    sac_thue: str
    file_path: str        # relative to /app/data/


# --- Syllabus CRUD ---

@router.get("/syllabus")
def list_syllabus(session_id: Optional[int] = None, sac_thue: Optional[str] = None, search: Optional[str] = None):
    with get_db() as conn:
        cur = conn.cursor()
        query = "SELECT id, sac_thue, section_code, section_title, content, tags, is_active, created_at, session_id FROM kb_syllabus WHERE 1=1"
        params = []
        if session_id:
            query += " AND session_id = %s"
            params.append(session_id)
        if sac_thue:
            query += " AND sac_thue = %s"
            params.append(sac_thue)
        if search:
            query += " AND (section_title ILIKE %s OR tags ILIKE %s OR content ILIKE %s)"
            params += [f"%{search}%", f"%{search}%", f"%{search}%"]
        query += " ORDER BY sac_thue, section_code, id"
        cur.execute(query, params)
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in rows]


@router.post("/syllabus")
def create_syllabus(item: SyllabusItem):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO kb_syllabus (sac_thue, section_code, section_title, content, tags, source_file, session_id) VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id",
            (item.sac_thue, item.section_code, item.section_title, item.content, item.tags, item.source_file, item.session_id)
        )
        return {"id": cur.fetchone()[0]}


@router.put("/syllabus/{item_id}")
def update_syllabus(item_id: int, item: SyllabusItem):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "UPDATE kb_syllabus SET sac_thue=%s, section_code=%s, section_title=%s, content=%s, tags=%s WHERE id=%s",
            (item.sac_thue, item.section_code, item.section_title, item.content, item.tags, item_id)
        )


@router.delete("/syllabus/{item_id}")
def delete_syllabus(item_id: int):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM kb_syllabus WHERE id=%s", (item_id,))


# --- Regulation CRUD ---

@router.get("/regulations")
def list_regulations(session_id: Optional[int] = None, sac_thue: Optional[str] = None, search: Optional[str] = None):
    with get_db() as conn:
        cur = conn.cursor()
        query = "SELECT id, sac_thue, regulation_ref, content, tags, syllabus_ids, is_active, created_at, session_id FROM kb_regulation WHERE 1=1"
        params = []
        if session_id:
            query += " AND session_id = %s"
            params.append(session_id)
        if sac_thue:
            query += " AND sac_thue = %s"
            params.append(sac_thue)
        if search:
            query += " AND (regulation_ref ILIKE %s OR tags ILIKE %s OR content ILIKE %s)"
            params += [f"%{search}%", f"%{search}%", f"%{search}%"]
        query += " ORDER BY sac_thue, regulation_ref, id"
        cur.execute(query, params)
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in rows]


@router.post("/regulations")
def create_regulation(item: RegulationItem):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO kb_regulation (sac_thue, regulation_ref, content, tags, syllabus_ids, source_file, session_id) VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id",
            (item.sac_thue, item.regulation_ref, item.content, item.tags, item.syllabus_ids or [], item.source_file, item.session_id)
        )
        return {"id": cur.fetchone()[0]}


@router.put("/regulations/{item_id}")
def update_regulation(item_id: int, item: RegulationItem):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "UPDATE kb_regulation SET sac_thue=%s, regulation_ref=%s, content=%s, tags=%s, syllabus_ids=%s WHERE id=%s",
            (item.sac_thue, item.regulation_ref, item.content, item.tags, item.syllabus_ids or [], item_id)
        )


@router.delete("/regulations/{item_id}")
def delete_regulation(item_id: int):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM kb_regulation WHERE id=%s", (item_id,))


# --- Sample CRUD ---

@router.get("/samples")
def list_samples(session_id: Optional[int] = None, sac_thue: Optional[str] = None, question_type: Optional[str] = None, search: Optional[str] = None):
    with get_db() as conn:
        cur = conn.cursor()
        query = "SELECT id, question_type, sac_thue, title, content, exam_tricks, syllabus_ids, regulation_ids, source, created_at, session_id FROM kb_sample WHERE 1=1"
        params = []
        if session_id:
            query += " AND session_id = %s"
            params.append(session_id)
        if sac_thue:
            query += " AND sac_thue = %s"
            params.append(sac_thue)
        if question_type:
            query += " AND question_type = %s"
            params.append(question_type)
        if search:
            query += " AND (title ILIKE %s OR exam_tricks ILIKE %s OR content ILIKE %s)"
            params += [f"%{search}%", f"%{search}%", f"%{search}%"]
        query += " ORDER BY sac_thue, question_type, id"
        cur.execute(query, params)
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in rows]


@router.post("/samples")
def create_sample(item: SampleItem):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO kb_sample (question_type, sac_thue, title, content, exam_tricks, syllabus_ids, regulation_ids, source, session_id) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
            (item.question_type, item.sac_thue, item.title, item.content, item.exam_tricks, item.syllabus_ids or [], item.regulation_ids or [], item.source, item.session_id)
        )
        return {"id": cur.fetchone()[0]}


@router.post("/samples/import-from-bank")
def import_from_bank(data: dict):
    """Import a question from the question bank into kb_sample."""
    question_id = data.get("question_id")
    title = data.get("title", "")
    exam_tricks = data.get("exam_tricks", "")
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT question_type, sac_thue, content_json FROM questions WHERE id=%s", (question_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, "Question not found")
        cur.execute(
            "INSERT INTO kb_sample (question_type, sac_thue, title, content, exam_tricks, source) VALUES (%s,%s,%s,%s,%s,%s) RETURNING id",
            (row[0], row[1], title, json.dumps(row[2]) if not isinstance(row[2], str) else row[2], exam_tricks, f"question_bank:{question_id}")
        )
        return {"id": cur.fetchone()[0]}


@router.put("/samples/{item_id}")
def update_sample(item_id: int, item: SampleItem):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "UPDATE kb_sample SET title=%s, exam_tricks=%s, syllabus_ids=%s, regulation_ids=%s WHERE id=%s",
            (item.title, item.exam_tricks, item.syllabus_ids or [], item.regulation_ids or [], item_id)
        )


@router.delete("/samples/{item_id}")
def delete_sample(item_id: int):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM kb_sample WHERE id=%s", (item_id,))


# --- Auto-parse file into chunks ---

@router.post("/parse-file")
def parse_file(req: ParseRequest):
    """Use AI to chunk a regulation or syllabus file into KB items."""
    import os
    from backend.context_builder import extract_text_from_file

    file_path = f"/app/data/{req.file_path}"
    if not os.path.exists(file_path):
        raise HTTPException(404, f"File not found: {req.file_path}")

    text = extract_text_from_file(file_path)
    if not text or len(text) < 100:
        raise HTTPException(400, "Could not extract text from file")

    # Truncate if too long (keep first 15000 chars for parsing)
    text_for_ai = text[:15000]

    prompt = f"""You are parsing a Vietnamese tax document for an exam question knowledge base.

Split this document into logical chunks. Each chunk should be:
- One coherent rule or topic (roughly one article, clause, or syllabus item)
- Self-contained enough to be exam context

For each chunk return:
- section_code: article/section number if present (e.g. "Article 9.2" or "Section B3")
- section_title: short title max 8 words
- content: full text of this chunk (keep original wording)
- tags: 3-8 comma-separated English keywords

Return ONLY valid JSON array, no markdown:
[
  {{
    "section_code": "Article 9",
    "section_title": "Deductible expenses general conditions",
    "content": "...",
    "tags": "deductible,expenses,conditions,genuine,invoice"
  }}
]

DOCUMENT TYPE: {req.file_type} | TAX TYPE: {req.sac_thue}

DOCUMENT:
{text_for_ai}"""

    result = call_ai(prompt, model_tier="fast")
    chunks = parse_ai_json_list(result["content"])

    # Save to appropriate table
    saved_ids = []
    with get_db() as conn:
        cur = conn.cursor()
        for chunk in chunks:
            if req.file_type == "syllabus":
                cur.execute(
                    "INSERT INTO kb_syllabus (sac_thue, section_code, section_title, content, tags, source_file) VALUES (%s,%s,%s,%s,%s,%s) RETURNING id",
                    (req.sac_thue, chunk.get("section_code"), chunk.get("section_title"), chunk.get("content", ""), chunk.get("tags"), req.file_path)
                )
            else:
                cur.execute(
                    "INSERT INTO kb_regulation (sac_thue, regulation_ref, content, tags, source_file) VALUES (%s,%s,%s,%s,%s) RETURNING id",
                    (req.sac_thue, chunk.get("section_code"), chunk.get("content", ""), chunk.get("tags"), req.file_path)
                )
            saved_ids.append(cur.fetchone()[0])

    return {"created": len(saved_ids), "ids": saved_ids, "chunks": chunks}
