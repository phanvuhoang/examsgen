from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, List

from backend.database import get_db

router = APIRouter(prefix="/api/sample-questions", tags=["sample-questions"])


class SampleQuestionCreate(BaseModel):
    question_type: str
    question_subtype: Optional[str] = None
    tax_type: str
    title: Optional[str] = None
    content: str
    answer: Optional[str] = None
    marks: Optional[int] = None
    exam_ref: Optional[str] = None
    syllabus_codes: Optional[List[str]] = None
    reg_codes: Optional[List[str]] = None
    tags: Optional[str] = None


class SampleQuestionUpdate(SampleQuestionCreate):
    pass


@router.get("")
def list_sample_questions(
    question_type: Optional[str] = None,
    tax_type: Optional[str] = None,
    subtype: Optional[str] = None,
    search: Optional[str] = None,
    syllabus_code: Optional[str] = None,
    limit: int = Query(50, le=200),
    offset: int = 0,
):
    with get_db() as conn:
        cur = conn.cursor()
        query = """SELECT id, question_type, question_subtype, tax_type, title, content, answer,
                          marks, exam_ref, syllabus_codes, reg_codes, tags, is_active, created_at
                   FROM sample_questions WHERE is_active = TRUE"""
        params = []
        if question_type:
            query += " AND question_type = %s"
            params.append(question_type)
        if tax_type:
            query += " AND tax_type = %s"
            params.append(tax_type)
        if subtype:
            query += " AND question_subtype = %s"
            params.append(subtype)
        if search:
            query += " AND (title ILIKE %s OR content ILIKE %s)"
            params += [f"%{search}%", f"%{search}%"]
        if syllabus_code:
            query += " AND syllabus_codes @> %s"
            params.append([syllabus_code])
        count_query = query.replace(
            "SELECT id, question_type, question_subtype, tax_type, title, content, answer,\n                          marks, exam_ref, syllabus_codes, reg_codes, tags, is_active, created_at",
            "SELECT COUNT(*)"
        )
        cur.execute(count_query, params)
        total = cur.fetchone()[0]
        query += " ORDER BY created_at DESC LIMIT %s OFFSET %s"
        cur.execute(query, params + [limit, offset])
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description]
    return {"total": total, "items": [dict(zip(cols, r)) for r in rows]}


@router.get("/search")
def search_sample_questions(
    question_type: Optional[str] = None,
    tax_type: Optional[str] = None,
    q: Optional[str] = None,
    limit: int = 20,
):
    with get_db() as conn:
        cur = conn.cursor()
        query = "SELECT id, question_type, question_subtype, tax_type, title FROM sample_questions WHERE is_active = TRUE"
        params = []
        if question_type:
            query += " AND question_type = %s"
            params.append(question_type)
        if tax_type:
            query += " AND tax_type = %s"
            params.append(tax_type)
        if q:
            query += " AND (title ILIKE %s OR content ILIKE %s OR tags ILIKE %s)"
            params += [f"%{q}%", f"%{q}%", f"%{q}%"]
        query += " ORDER BY created_at DESC LIMIT %s"
        params.append(limit)
        cur.execute(query, params)
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in rows]


@router.get("/{item_id}")
def get_sample_question(item_id: int):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""SELECT id, question_type, question_subtype, tax_type, title, content, answer,
                              marks, exam_ref, syllabus_codes, reg_codes, tags, is_active, created_at
                       FROM sample_questions WHERE id = %s""", (item_id,))
        row = cur.fetchone()
    if not row:
        raise HTTPException(404, "Sample question not found")
    cols = ['id', 'question_type', 'question_subtype', 'tax_type', 'title', 'content', 'answer',
            'marks', 'exam_ref', 'syllabus_codes', 'reg_codes', 'tags', 'is_active', 'created_at']
    return dict(zip(cols, row))


@router.post("")
def create_sample_question(item: SampleQuestionCreate):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO sample_questions
              (question_type, question_subtype, tax_type, title, content, answer, marks, exam_ref,
               syllabus_codes, reg_codes, tags)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id
        """, (item.question_type, item.question_subtype, item.tax_type, item.title,
              item.content, item.answer, item.marks, item.exam_ref,
              item.syllabus_codes or [], item.reg_codes or [], item.tags))
        return {"id": cur.fetchone()[0]}


@router.put("/{item_id}")
def update_sample_question(item_id: int, item: SampleQuestionUpdate):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            UPDATE sample_questions SET
                question_type = %s, question_subtype = %s, tax_type = %s, title = %s,
                content = %s, answer = %s, marks = %s, exam_ref = %s,
                syllabus_codes = %s, reg_codes = %s, tags = %s
            WHERE id = %s
        """, (item.question_type, item.question_subtype, item.tax_type, item.title,
              item.content, item.answer, item.marks, item.exam_ref,
              item.syllabus_codes or [], item.reg_codes or [], item.tags, item_id))
    return {"ok": True}


@router.delete("/{item_id}")
def delete_sample_question(item_id: int):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("UPDATE sample_questions SET is_active = FALSE WHERE id = %s RETURNING id", (item_id,))
        if not cur.fetchone():
            raise HTTPException(404, "Sample question not found")
    return {"ok": True}
