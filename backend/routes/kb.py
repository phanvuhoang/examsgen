import re
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, BackgroundTasks, Query
from pydantic import BaseModel
from typing import Optional, List
import json
import logging

from backend.database import get_db
from backend.ai_provider import call_ai, parse_ai_json_list, parse_ai_json

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
    """Confirm and insert parsed syllabus rows. Optionally clears existing before insert."""
    session_id = data['session_id']
    tax_type = data['tax_type']
    rows = data['rows']
    replace = data.get('replace', True)  # default: replace existing for this session+tax_type

    with get_db() as conn:
        cur = conn.cursor()
        cleared = 0
        if replace:
            cur.execute(
                "DELETE FROM kb_syllabus WHERE session_id = %s AND COALESCE(tax_type, sac_thue) = %s",
                (session_id, tax_type)
            )
            cleared = cur.rowcount
        for row in rows:
            code = row.get('code') or row.get('syllabus_code', '')
            topic = row.get('topics') or row.get('topic', '')
            detail = row.get('detailed_syllabus', '')
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
    return {"inserted": len(rows), "cleared": cleared}


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

def _split_into_article_chunks(text: str, max_chars: int = 8000) -> list:
    """Split regulation text into chunks at article boundaries."""
    import re as _re
    article_pattern = _re.compile(
        r'(?:^|\n)\s*(?:Article|Điều|ARTICLE|ĐIỀU)\s+\d+',
        _re.MULTILINE | _re.IGNORECASE
    )
    matches = list(article_pattern.finditer(text))

    if not matches:
        chunks = []
        step = max_chars - 500
        for i in range(0, len(text), step):
            chunks.append(text[i:i + max_chars])
            if i + max_chars >= len(text):
                break
        return chunks

    chunks = []
    current_chunk_start = 0
    current_chunk_articles = []

    for i, match in enumerate(matches):
        article_start = match.start()
        article_end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        article_text = text[article_start:article_end]

        if len(article_text) > max_chars:
            if current_chunk_articles:
                chunks.append(text[current_chunk_start:article_start])
                current_chunk_articles = []
                current_chunk_start = article_start
            for j in range(0, len(article_text), max_chars - 200):
                chunks.append(article_text[j:j + max_chars])
            current_chunk_start = article_end
            continue

        current_size = article_start - current_chunk_start
        if current_chunk_articles and current_size + len(article_text) > max_chars:
            chunks.append(text[current_chunk_start:article_start])
            current_chunk_start = article_start
            current_chunk_articles = []

        current_chunk_articles.append(match.group())

    if current_chunk_start < len(text):
        chunks.append(text[current_chunk_start:])

    return [c for c in chunks if c.strip()]


# In-memory job store for async parse jobs
_parse_jobs: dict = {}


def _run_parse_job(job_id: str, data: dict):
    """Background task — runs the chunked parse and updates job status."""
    import os
    from backend.context_builder import extract_text_from_file
    from backend.config import DATA_DIR
    try:
        session_id = data['session_id']
        tax_type = data['tax_type']
        file_path = data['file_path']
        doc_ref = data.get('doc_ref', '')

        full_path = os.path.join(DATA_DIR, file_path) if not file_path.startswith('/') else file_path
        if not os.path.exists(full_path):
            _parse_jobs[job_id]['status'] = 'failed'
            _parse_jobs[job_id]['error'] = f'File not found: {file_path}'
            return

        text = extract_text_from_file(full_path)

        # Load syllabus context
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT COALESCE(syllabus_code, section_code) as code,
                       COALESCE(topic, section_title) as topic,
                       COALESCE(detailed_syllabus, content) as detail
                FROM kb_syllabus
                WHERE session_id = %s AND COALESCE(tax_type, sac_thue) = %s
                  AND COALESCE(syllabus_code, section_code) IS NOT NULL
                ORDER BY COALESCE(syllabus_code, section_code)
            """, (session_id, tax_type))
            syllabus_rows = cur.fetchall()

        syllabus_context = ''
        if syllabus_rows:
            syllabus_list = '\n'.join(f'- [{r[0]}] {r[1]}: {r[2][:80]}' for r in syllabus_rows[:80])
            syllabus_context = f'\n\nAVAILABLE SYLLABUS CODES (match paragraphs to these if relevant):\n{syllabus_list}'

        text_chunks = _split_into_article_chunks(text, max_chars=8000)
        _parse_jobs[job_id]['total_chunks'] = len(text_chunks)
        doc_slug = re.sub(r'[^A-Za-z0-9]', '', doc_ref.replace('/', '-').replace(' ', ''))[:20]
        all_rows = []

        for chunk_idx, chunk_text in enumerate(text_chunks):
            _parse_jobs[job_id]['chunk'] = chunk_idx + 1
            prompt = f"""Parse this Vietnamese tax regulation document chunk into individual paragraphs.

For each paragraph extract:
- article_no: article number if present (e.g. "Article 12" or "Điều 12")
- paragraph_no: sequential number within that article (1, 2, 3...)
- paragraph_text: the complete text of this paragraph (keep original wording)
- tags: 3-6 English keywords
- syllabus_codes: array of matching syllabus codes from the list below (empty array [] if none match){syllabus_context}

Return ONLY valid JSON array, no markdown:
[
  {{
    "article_no": "Article 9",
    "paragraph_no": 1,
    "paragraph_text": "...",
    "tags": "deductible,expenses,conditions",
    "syllabus_codes": ["B2a", "B2b"]
  }}
]

DOCUMENT TYPE: regulation | TAX TYPE: {tax_type} | SOURCE: {doc_ref} | CHUNK {chunk_idx + 1}/{len(text_chunks)}

DOCUMENT CHUNK:
{chunk_text}"""

            result = call_ai(prompt, model_tier='fast')
            chunks_parsed = parse_ai_json_list(result['content'])

            with get_db() as conn:
                cur = conn.cursor()
                for item in chunks_parsed:
                    art = re.sub(r'[^0-9]', '', str(item.get('article_no', '0')))
                    p = item.get('paragraph_no', 0)
                    reg_code = f'{tax_type}-{doc_slug}-Art{art}-P{p}'
                    syllabus_codes = item.get('syllabus_codes', [])
                    if isinstance(syllabus_codes, str):
                        syllabus_codes = [s.strip() for s in syllabus_codes.split(',') if s.strip()]
                    cur.execute("""
                        INSERT INTO kb_regulation_parsed
                          (session_id, tax_type, reg_code, doc_ref, article_no, paragraph_no,
                           paragraph_text, syllabus_codes, tags, source_file)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                        ON CONFLICT DO NOTHING
                    """, (session_id, tax_type, reg_code, doc_ref,
                          item.get('article_no'), p,
                          item.get('paragraph_text', ''),
                          syllabus_codes,
                          item.get('tags', ''),
                          file_path))
                    all_rows.append({'reg_code': reg_code, 'syllabus_codes': syllabus_codes})

            _parse_jobs[job_id]['parsed'] = len(all_rows)

        _parse_jobs[job_id]['status'] = 'done'
        _parse_jobs[job_id]['rows'] = all_rows
    except Exception as e:
        _parse_jobs[job_id]['status'] = 'failed'
        _parse_jobs[job_id]['error'] = str(e)


@router.post("/regulations/parse-doc")
def parse_regulation_doc(data: dict):
    """AI-parse a regulation document into kb_regulation_parsed rows (chunked, clears first)."""
    import os
    from backend.context_builder import extract_text_from_file
    from backend.config import DATA_DIR

    session_id = data['session_id']
    tax_type = data['tax_type']
    file_path = data['file_path']
    doc_ref = data.get('doc_ref', '')

    # Clear existing rows for this file (smart re-parse)
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "DELETE FROM kb_regulation_parsed WHERE session_id = %s AND source_file = %s",
            (session_id, file_path)
        )
        cleared = cur.rowcount

    full_path = os.path.join(DATA_DIR, file_path) if not file_path.startswith('/') else file_path
    if not os.path.exists(full_path):
        raise HTTPException(404, f"File not found: {file_path}")

    text = extract_text_from_file(full_path)
    if not text or len(text) < 100:
        raise HTTPException(400, "Could not extract text from file")

    # Load syllabus context
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT COALESCE(syllabus_code, section_code) as code,
                   COALESCE(topic, section_title) as topic,
                   COALESCE(detailed_syllabus, content) as detail
            FROM kb_syllabus
            WHERE session_id = %s AND COALESCE(tax_type, sac_thue) = %s
              AND COALESCE(syllabus_code, section_code) IS NOT NULL
            ORDER BY COALESCE(syllabus_code, section_code)
        """, (session_id, tax_type))
        syllabus_rows = cur.fetchall()

    syllabus_context = ''
    if syllabus_rows:
        syllabus_list = '\n'.join(f'- [{r[0]}] {r[1]}: {r[2][:80]}' for r in syllabus_rows[:80])
        syllabus_context = f'\n\nAVAILABLE SYLLABUS CODES (match paragraphs to these if relevant):\n{syllabus_list}'

    text_chunks = _split_into_article_chunks(text, max_chars=8000)
    doc_slug = re.sub(r'[^A-Za-z0-9]', '', doc_ref.replace('/', '-').replace(' ', ''))[:20]
    all_rows = []

    for chunk_idx, chunk_text in enumerate(text_chunks):
        prompt = f"""Parse this Vietnamese tax regulation document chunk into individual paragraphs.

For each paragraph extract:
- article_no: article number if present (e.g. "Article 12" or "Điều 12")
- paragraph_no: sequential number within that article (1, 2, 3...)
- paragraph_text: the complete text of this paragraph (keep original wording)
- tags: 3-6 English keywords
- syllabus_codes: array of matching syllabus codes from the list below (empty array [] if none match){syllabus_context}

Return ONLY valid JSON array, no markdown:
[
  {{
    "article_no": "Article 9",
    "paragraph_no": 1,
    "paragraph_text": "...",
    "tags": "deductible,expenses,conditions",
    "syllabus_codes": ["B2a", "B2b"]
  }}
]

DOCUMENT TYPE: regulation | TAX TYPE: {tax_type} | SOURCE: {doc_ref} | CHUNK {chunk_idx + 1}/{len(text_chunks)}

DOCUMENT CHUNK:
{chunk_text}"""

        result = call_ai(prompt, model_tier='fast')
        chunks_parsed = parse_ai_json_list(result['content'])

        with get_db() as conn:
            cur = conn.cursor()
            for item in chunks_parsed:
                art = re.sub(r'[^0-9]', '', str(item.get('article_no', '0')))
                p = item.get('paragraph_no', 0)
                reg_code = f'{tax_type}-{doc_slug}-Art{art}-P{p}'
                syllabus_codes = item.get('syllabus_codes', [])
                if isinstance(syllabus_codes, str):
                    syllabus_codes = [s.strip() for s in syllabus_codes.split(',') if s.strip()]
                cur.execute("""
                    INSERT INTO kb_regulation_parsed
                      (session_id, tax_type, reg_code, doc_ref, article_no, paragraph_no,
                       paragraph_text, syllabus_codes, tags, source_file)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT DO NOTHING
                """, (session_id, tax_type, reg_code, doc_ref,
                      item.get('article_no'), p,
                      item.get('paragraph_text', ''),
                      syllabus_codes,
                      item.get('tags', ''),
                      file_path))
                all_rows.append({
                    'reg_code': reg_code,
                    'article_no': item.get('article_no'),
                    'paragraph_no': p,
                    'paragraph_text': item.get('paragraph_text', '')[:200],
                    'syllabus_codes': syllabus_codes,
                    'tags': item.get('tags', '')
                })

    if cleared > 0:
        logger.info(f"Re-parse: cleared {cleared} existing rows for {file_path}")

    return {
        "parsed": len(all_rows),
        "chunks_processed": len(text_chunks),
        "re_parsed": cleared > 0,
        "cleared": cleared,
        "rows": all_rows
    }


@router.post("/regulations/parse-doc-async")
def parse_regulation_doc_async(data: dict, background_tasks: BackgroundTasks):
    """Start async chunked parse job. Returns job_id to poll."""
    import uuid
    job_id = str(uuid.uuid4())[:8]

    # Clear existing rows first
    session_id = data.get('session_id')
    file_path = data.get('file_path', '')
    if session_id and file_path:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute(
                "DELETE FROM kb_regulation_parsed WHERE session_id = %s AND source_file = %s",
                (session_id, file_path)
            )
            cleared = cur.rowcount
    else:
        cleared = 0

    _parse_jobs[job_id] = {
        "status": "running", "parsed": 0, "total_chunks": 0,
        "chunk": 0, "rows": [], "cleared": cleared
    }
    background_tasks.add_task(_run_parse_job, job_id, data)
    return {"job_id": job_id}


@router.get("/regulations/parse-job/{job_id}")
def get_parse_job(job_id: str):
    job = _parse_jobs.get(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return job


@router.get("/regulations/parsed")
def list_parsed_regulations(
    session_id: Optional[int] = None,
    tax_type: Optional[str] = None,
    source_file: Optional[str] = None,
    syllabus_code: Optional[str] = None,
    article_no: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = Query(100, le=500),
    offset: int = 0,
):
    with get_db() as conn:
        cur = conn.cursor()
        query = """SELECT id, session_id, tax_type, reg_code, doc_ref, article_no,
                          paragraph_no, paragraph_text, syllabus_codes, tags, source_file
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
        if syllabus_code:
            query += " AND syllabus_codes @> %s"
            params.append([syllabus_code])
        if article_no:
            query += " AND article_no ILIKE %s"
            params.append(f"%{article_no}%")
        if search:
            query += " AND (reg_code ILIKE %s OR paragraph_text ILIKE %s OR tags ILIKE %s)"
            params += [f"%{search}%", f"%{search}%", f"%{search}%"]

        count_q = query.replace(
            "SELECT id, session_id, tax_type, reg_code, doc_ref, article_no,\n                          paragraph_no, paragraph_text, syllabus_codes, tags, source_file",
            "SELECT COUNT(*)"
        )
        cur.execute(count_q, params)
        total = cur.fetchone()[0]

        query += " ORDER BY doc_ref, article_no, paragraph_no LIMIT %s OFFSET %s"
        cur.execute(query, params + [limit, offset])
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description]
    return {"total": total, "items": [dict(zip(cols, r)) for r in rows]}


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


# ============================================================
# v2: BULK DELETE endpoints
# ============================================================

@router.delete("/syllabus/bulk")
def bulk_delete_syllabus(data: dict):
    """Delete multiple syllabus items by id list."""
    ids = data.get('ids', [])
    if not ids:
        return {"deleted": 0}
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM kb_syllabus WHERE id = ANY(%s) RETURNING id", (ids,))
        deleted = len(cur.fetchall())
    return {"deleted": deleted}


@router.delete("/regulation-parsed/bulk")
def bulk_delete_reg_parsed(data: dict):
    """Delete multiple parsed regulation items by id list."""
    ids = data.get('ids', [])
    if not ids:
        return {"deleted": 0}
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM kb_regulation_parsed WHERE id = ANY(%s) RETURNING id", (ids,))
        deleted = len(cur.fetchall())
    return {"deleted": deleted}


# ============================================================
# v2: REGULATION FILES list
# ============================================================

@router.get("/regulations/files")
def list_regulation_files(session_id: int, tax_type: Optional[str] = None):
    """Return distinct source files with their paragraph counts."""
    with get_db() as conn:
        cur = conn.cursor()
        query = """
            SELECT source_file, doc_ref, tax_type, COUNT(*) as paragraph_count
            FROM kb_regulation_parsed
            WHERE session_id = %s AND is_active = TRUE
        """
        params = [session_id]
        if tax_type:
            query += " AND tax_type = %s"
            params.append(tax_type)
        query += " GROUP BY source_file, doc_ref, tax_type ORDER BY doc_ref"
        cur.execute(query, params)
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in rows]


# ============================================================
# v2: AUTO-SUGGEST CODES
# ============================================================

@router.post("/suggest-codes")
def suggest_codes(data: dict):
    """Given question content, session_id, tax_type — use AI to suggest syllabus + reg codes."""
    import re as _re

    content = data.get('content', '')
    tax_type = data.get('tax_type', '')
    session_id = data.get('session_id')
    question_type = data.get('question_type', '')

    clean_content = _re.sub(r'<[^>]+>', ' ', content).strip()
    if len(clean_content) < 30:
        return {"syllabus_codes": [], "reg_codes": []}

    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT COALESCE(syllabus_code, section_code) as code,
                   COALESCE(topic, section_title) as topic,
                   COALESCE(detailed_syllabus, content) as detail
            FROM kb_syllabus
            WHERE session_id = %s AND COALESCE(tax_type, sac_thue) = %s
              AND COALESCE(syllabus_code, section_code) IS NOT NULL
            ORDER BY COALESCE(syllabus_code, section_code)
        """, (session_id, tax_type))
        syllabus_rows = cur.fetchall()

        cur.execute("""
            SELECT reg_code, doc_ref, LEFT(paragraph_text, 200) as text
            FROM kb_regulation_parsed
            WHERE session_id = %s AND tax_type = %s AND is_active = TRUE
            ORDER BY reg_code
        """, (session_id, tax_type))
        reg_rows = cur.fetchall()

    if not syllabus_rows and not reg_rows:
        return {"syllabus_codes": [], "reg_codes": []}

    syllabus_list = "\n".join(f"- [{r[0]}] {r[1]}: {r[2][:100]}" for r in syllabus_rows[:60])
    reg_list = "\n".join(f"- [{r[0]}] ({r[1]}): {r[2]}" for r in reg_rows[:60])

    prompt = f"""You are an ACCA TX(VNM) exam analyst. Given a question, identify which syllabus items and regulation paragraphs it tests or references.

QUESTION ({question_type} — {tax_type}):
{clean_content[:2000]}

AVAILABLE SYLLABUS ITEMS:
{syllabus_list if syllabus_list else "(none loaded yet)"}

AVAILABLE REGULATION PARAGRAPHS:
{reg_list if reg_list else "(none loaded yet)"}

Return ONLY valid JSON (no markdown):
{{
    "syllabus_codes": [
        {{"code": "B2a", "reason": "Question directly tests deductibility of salary expenses"}}
    ],
    "reg_codes": [
        {{"reg_code": "CIT-ND320-Art9-P1", "reason": "The 5x salary cap rule is central to this question"}}
    ]
}}

Rules:
- Only suggest codes that ACTUALLY appear in the lists above
- Suggest 1-5 syllabus codes max, 0-3 reg codes max
- If nothing matches well, return empty arrays
"""

    result = call_ai(prompt, model_tier="fast")
    try:
        parsed = parse_ai_json(result['content'])
        suggested_codes = parsed.get('syllabus_codes', [])
        suggested_regs = parsed.get('reg_codes', [])

        syllabus_map = {r[0]: {'topic': r[1], 'detail': r[2]} for r in syllabus_rows}
        reg_map = {r[0]: {'doc_ref': r[1], 'text': r[2]} for r in reg_rows}

        enriched_syllabus = []
        for s in suggested_codes:
            code = s.get('code', '')
            if code in syllabus_map:
                enriched_syllabus.append({
                    'code': code,
                    'topic': syllabus_map[code]['topic'],
                    'detail': syllabus_map[code]['detail'][:120],
                    'reason': s.get('reason', '')
                })

        enriched_regs = []
        for r in suggested_regs:
            rc = r.get('reg_code', '')
            if rc in reg_map:
                enriched_regs.append({
                    'reg_code': rc,
                    'doc_ref': reg_map[rc]['doc_ref'],
                    'text': reg_map[rc]['text'],
                    'reason': r.get('reason', '')
                })

        return {"syllabus_codes": enriched_syllabus, "reg_codes": enriched_regs}
    except Exception:
        return {"syllabus_codes": [], "reg_codes": []}
