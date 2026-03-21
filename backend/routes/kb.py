import re
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
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
def list_syllabus(session_id: Optional[int] = None, sac_thue: Optional[str] = None,
                  tax_type: Optional[str] = None, search: Optional[str] = None):
    with get_db() as conn:
        cur = conn.cursor()
        query = """SELECT id, sac_thue, section_code, section_title, content, tags, is_active,
                          created_at, session_id,
                          COALESCE(tax_type, sac_thue) as tax_type,
                          COALESCE(syllabus_code, section_code) as syllabus_code,
                          COALESCE(topic, section_title) as topic,
                          COALESCE(detailed_syllabus, content) as detailed_syllabus
                   FROM kb_syllabus WHERE 1=1"""
        params = []
        if session_id:
            query += " AND session_id = %s"
            params.append(session_id)
        # Accept both tax_type (new) and sac_thue (legacy)
        filter_tax = tax_type or sac_thue
        if filter_tax:
            query += " AND (COALESCE(tax_type, sac_thue) = %s)"
            params.append(filter_tax)
        if search:
            query += " AND (section_title ILIKE %s OR tags ILIKE %s OR content ILIKE %s OR detailed_syllabus ILIKE %s)"
            params += [f"%{search}%", f"%{search}%", f"%{search}%", f"%{search}%"]
        query += " ORDER BY COALESCE(syllabus_code, section_code), id"
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


# ============================================================
# v2: SYLLABUS — Upload CSV/Excel + Bulk Insert + Search
# ============================================================

@router.post("/syllabus/upload")
async def upload_syllabus(
    session_id: int = Form(...),
    tax_type: str = Form(...),
    file: UploadFile = File(...)
):
    """Parse CSV or Excel syllabus file, return preview rows."""
    try:
        import pandas as pd
    except ImportError:
        raise HTTPException(500, "pandas not installed")

    if file.filename.endswith('.csv'):
        df = pd.read_csv(file.file)
    elif file.filename.endswith(('.xlsx', '.xls')):
        df = pd.read_excel(file.file)
    else:
        raise HTTPException(400, "Only CSV or Excel files accepted")

    df.columns = [c.strip().lower().replace(' ', '_') for c in df.columns]
    required = {'code', 'topics', 'detailed_syllabus'}
    missing = required - set(df.columns)
    if missing:
        raise HTTPException(400, f"Missing required columns: {missing}")

    rows = df[['code', 'topics', 'detailed_syllabus']].fillna('').to_dict('records')
    return {"preview": rows[:5], "total": len(rows), "rows": rows}


@router.post("/syllabus/bulk-insert")
def bulk_insert_syllabus(data: dict):
    """Confirm and insert parsed syllabus rows. Upserts on (session_id, tax_type, syllabus_code)."""
    session_id = data['session_id']
    tax_type = data['tax_type']
    rows = data['rows']

    with get_db() as conn:
        cur = conn.cursor()
        for row in rows:
            code = row.get('code') or row.get('syllabus_code', '')
            topic = row.get('topics') or row.get('topic', '')
            detail = row.get('detailed_syllabus', '')
            # Upsert manually: update if exists, insert if not
            cur.execute("""
                UPDATE kb_syllabus
                SET topic = %s, detailed_syllabus = %s, section_title = %s, content = %s
                WHERE session_id = %s AND tax_type = %s AND syllabus_code = %s
            """, (topic, detail, topic, detail, session_id, tax_type, code))
            if cur.rowcount == 0:
                cur.execute("""
                    INSERT INTO kb_syllabus (session_id, tax_type, syllabus_code, topic, detailed_syllabus,
                                            sac_thue, section_code, section_title, content)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (session_id, tax_type, code, topic, detail,
                      tax_type, code, topic, detail))
    return {"inserted": len(rows)}


@router.get("/syllabus/search")
def search_syllabus(session_id: Optional[int] = None, tax_type: Optional[str] = None, q: Optional[str] = None, limit: int = 20):
    with get_db() as conn:
        cur = conn.cursor()
        query = """SELECT id, syllabus_code, topic, detailed_syllabus
                   FROM kb_syllabus WHERE syllabus_code IS NOT NULL"""
        params = []
        if session_id:
            query += " AND session_id = %s"
            params.append(session_id)
        if tax_type:
            query += " AND (tax_type = %s OR sac_thue = %s)"
            params += [tax_type, tax_type]
        if q:
            query += " AND (syllabus_code ILIKE %s OR topic ILIKE %s OR detailed_syllabus ILIKE %s)"
            params += [f"%{q}%", f"%{q}%", f"%{q}%"]
        query += " ORDER BY syllabus_code LIMIT %s"
        params.append(limit)
        cur.execute(query, params)
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in rows]


# ============================================================
# v2: REGULATIONS PARSED — AI Parse + CRUD + Search
# ============================================================

@router.post("/regulations/parse-doc")
def parse_regulation_doc(data: dict):
    """AI-parse a regulation document into kb_regulation_parsed rows."""
    import os
    from backend.context_builder import extract_text_from_file
    from backend.config import DATA_DIR

    session_id = data['session_id']
    tax_type = data['tax_type']
    file_path = data['file_path']
    doc_ref = data.get('doc_ref', '')

    full_path = os.path.join(DATA_DIR, file_path) if not file_path.startswith('/') else file_path
    if not os.path.exists(full_path):
        raise HTTPException(404, f"File not found: {file_path}")

    text = extract_text_from_file(full_path)[:20000]

    prompt = f"""Parse this Vietnamese tax regulation document into individual paragraphs.

For each paragraph, extract:
- article_no: article number (e.g. "Article 12" or "Điều 12")
- paragraph_no: sequential number within that article (1, 2, 3...)
- paragraph_text: the complete text of this paragraph
- tags: 3-6 English keywords describing this paragraph's topic

Return ONLY a valid JSON array:
[
  {{
    "article_no": "Article 12",
    "paragraph_no": 1,
    "paragraph_text": "...",
    "tags": "deductible,salary,expenses"
  }}
]

DOCUMENT ({tax_type} — {doc_ref}):
{text}"""

    result = call_ai(prompt, model_tier="fast")
    chunks = parse_ai_json_list(result['content'])

    doc_slug = re.sub(r'[^A-Za-z0-9]', '', doc_ref.replace('/', '-').replace(' ', ''))[:20]
    rows = []
    with get_db() as conn:
        cur = conn.cursor()
        for chunk in chunks:
            art = re.sub(r'[^0-9]', '', chunk.get('article_no', '0'))
            p = chunk.get('paragraph_no', 0)
            reg_code = f"{tax_type}-{doc_slug}-Art{art}-P{p}"
            cur.execute("""
                INSERT INTO kb_regulation_parsed
                  (session_id, tax_type, reg_code, doc_ref, article_no, paragraph_no, paragraph_text, tags, source_file)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                RETURNING id, reg_code
            """, (session_id, tax_type, reg_code, doc_ref,
                  chunk.get('article_no'), chunk.get('paragraph_no'),
                  chunk.get('paragraph_text', ''), chunk.get('tags', ''), file_path))
            row = cur.fetchone()
            rows.append({"id": row[0], "reg_code": row[1], **chunk})

    return {"parsed": len(rows), "rows": rows}


@router.get("/regulations/parsed")
def list_parsed_regulations(session_id: Optional[int] = None, tax_type: Optional[str] = None,
                             source_file: Optional[str] = None, limit: int = 200):
    with get_db() as conn:
        cur = conn.cursor()
        query = """SELECT id, session_id, tax_type, reg_code, doc_ref, article_no, paragraph_no,
                          paragraph_text, syllabus_codes, tags, source_file, is_active, created_at
                   FROM kb_regulation_parsed WHERE is_active = TRUE"""
        params = []
        if session_id:
            query += " AND session_id = %s"
            params.append(session_id)
        if tax_type:
            query += " AND tax_type = %s"
            params.append(tax_type)
        if source_file:
            query += " AND source_file = %s"
            params.append(source_file)
        query += " ORDER BY tax_type, article_no, paragraph_no LIMIT %s"
        params.append(limit)
        cur.execute(query, params)
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in rows]


@router.get("/regulations/search")
def search_parsed_regulations(session_id: Optional[int] = None, tax_type: Optional[str] = None,
                               q: Optional[str] = None, syllabus_codes: Optional[str] = None, limit: int = 20):
    with get_db() as conn:
        cur = conn.cursor()
        query = "SELECT id, reg_code, doc_ref, paragraph_text FROM kb_regulation_parsed WHERE is_active = TRUE"
        params = []
        if session_id:
            query += " AND session_id = %s"
            params.append(session_id)
        if tax_type:
            query += " AND tax_type = %s"
            params.append(tax_type)
        if q:
            query += " AND (reg_code ILIKE %s OR paragraph_text ILIKE %s OR tags ILIKE %s)"
            params += [f"%{q}%", f"%{q}%", f"%{q}%"]
        if syllabus_codes:
            codes = [c.strip() for c in syllabus_codes.split(',') if c.strip()]
            if codes:
                query += " AND syllabus_codes && %s"
                params.append(codes)
        query += " ORDER BY reg_code LIMIT %s"
        params.append(limit)
        cur.execute(query, params)
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in rows]


@router.put("/regulation-parsed/{item_id}")
def update_parsed_regulation(item_id: int, data: dict):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            UPDATE kb_regulation_parsed SET
                paragraph_text = COALESCE(%s, paragraph_text),
                syllabus_codes = COALESCE(%s, syllabus_codes),
                tags = COALESCE(%s, tags)
            WHERE id = %s
        """, (data.get('paragraph_text'), data.get('syllabus_codes'), data.get('tags'), item_id))
    return {"ok": True}


@router.delete("/regulation-parsed/{item_id}")
def delete_parsed_regulation(item_id: int):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM kb_regulation_parsed WHERE id = %s", (item_id,))
    return {"ok": True}


# ============================================================
# v2: TAX RATES — Upload + CRUD
# ============================================================

@router.get("/tax-rates")
def list_tax_rates(session_id: Optional[int] = None, tax_type: Optional[str] = None):
    with get_db() as conn:
        cur = conn.cursor()
        query = """SELECT id, session_id, tax_type, table_name, content, source_file, display_order, is_active, created_at
                   FROM kb_tax_rates WHERE is_active = TRUE"""
        params = []
        if session_id:
            query += " AND session_id = %s"
            params.append(session_id)
        if tax_type:
            query += " AND tax_type = %s"
            params.append(tax_type)
        query += " ORDER BY tax_type, display_order, id"
        cur.execute(query, params)
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in rows]


@router.post("/tax-rates/upload")
async def upload_tax_rates(
    session_id: int = Form(...),
    tax_type: str = Form(...),
    table_name: str = Form(...),
    file: UploadFile = File(...)
):
    """Read CSV/Excel and convert to HTML table, save to kb_tax_rates."""
    try:
        import pandas as pd
    except ImportError:
        raise HTTPException(500, "pandas not installed")

    if file.filename.endswith('.csv'):
        df = pd.read_csv(file.file)
    else:
        df = pd.read_excel(file.file)

    html = df.to_html(index=False, classes='tax-rate-table', border=0)

    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO kb_tax_rates (session_id, tax_type, table_name, content, source_file) VALUES (%s,%s,%s,%s,%s) RETURNING id",
            (session_id, tax_type, table_name, html, file.filename)
        )
        return {"id": cur.fetchone()[0]}


@router.post("/tax-rates")
def create_tax_rate(data: dict):
    """Create a tax rate entry manually (rich text content)."""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO kb_tax_rates (session_id, tax_type, table_name, content, display_order) VALUES (%s,%s,%s,%s,%s) RETURNING id",
            (data['session_id'], data['tax_type'], data['table_name'], data['content'], data.get('display_order', 0))
        )
        return {"id": cur.fetchone()[0]}


@router.put("/tax-rates/{item_id}")
def update_tax_rate(item_id: int, data: dict):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            UPDATE kb_tax_rates SET
                table_name = COALESCE(%s, table_name),
                content = COALESCE(%s, content),
                display_order = COALESCE(%s, display_order)
            WHERE id = %s
        """, (data.get('table_name'), data.get('content'), data.get('display_order'), item_id))
    return {"ok": True}


@router.delete("/tax-rates/{item_id}")
def delete_tax_rate(item_id: int):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM kb_tax_rates WHERE id = %s", (item_id,))
    return {"ok": True}
