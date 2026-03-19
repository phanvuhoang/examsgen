import json
from fastapi import APIRouter, HTTPException, Query
from typing import Optional

from backend.database import get_db

router = APIRouter(prefix="/api/questions", tags=["questions"])


@router.get("")
def list_questions(
    question_type: Optional[str] = None,
    sac_thue: Optional[str] = None,
    starred: Optional[bool] = None,
    limit: int = Query(50, le=200),
    offset: int = 0,
):
    conditions = []
    params = []
    if question_type:
        conditions.append("question_type = %s")
        params.append(question_type)
    if sac_thue:
        conditions.append("sac_thue = %s")
        params.append(sac_thue)
    if starred is not None:
        conditions.append("is_starred = %s")
        params.append(starred)

    where = "WHERE " + " AND ".join(conditions) if conditions else ""

    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            f"SELECT id, question_type, sac_thue, question_part, question_number, "
            f"content_json, model_used, provider_used, exam_session, created_at, is_starred "
            f"FROM questions {where} ORDER BY created_at DESC LIMIT %s OFFSET %s",
            params + [limit, offset],
        )
        rows = cur.fetchall()

        cur.execute(f"SELECT COUNT(*) FROM questions {where}", params)
        total = cur.fetchone()[0]

    return {
        "total": total,
        "questions": [
            {
                "id": r[0],
                "question_type": r[1],
                "sac_thue": r[2],
                "question_part": r[3],
                "question_number": r[4],
                "content_json": r[5],
                "model_used": r[6],
                "provider_used": r[7],
                "exam_session": r[8],
                "created_at": r[9].isoformat() if r[9] else None,
                "is_starred": r[10],
            }
            for r in rows
        ],
    }


@router.get("/{question_id}")
def get_question(question_id: int):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, question_type, sac_thue, question_part, question_number, "
            "content_json, content_html, model_used, provider_used, exam_session, "
            "created_at, is_starred, notes "
            "FROM questions WHERE id = %s",
            (question_id,),
        )
        r = cur.fetchone()
    if not r:
        raise HTTPException(status_code=404, detail="Question not found")
    return {
        "id": r[0], "question_type": r[1], "sac_thue": r[2],
        "question_part": r[3], "question_number": r[4],
        "content_json": r[5], "content_html": r[6],
        "model_used": r[7], "provider_used": r[8],
        "exam_session": r[9],
        "created_at": r[10].isoformat() if r[10] else None,
        "is_starred": r[11], "notes": r[12],
    }


@router.patch("/{question_id}/star")
def toggle_star(question_id: int):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "UPDATE questions SET is_starred = NOT is_starred WHERE id = %s RETURNING is_starred",
            (question_id,),
        )
        row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Question not found")
    return {"id": question_id, "is_starred": row[0]}


@router.delete("/{question_id}")
def delete_question(question_id: int):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM generation_log WHERE question_id = %s", (question_id,))
        cur.execute("DELETE FROM questions WHERE id = %s RETURNING id", (question_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Question not found")
    return {"message": "Question deleted"}
