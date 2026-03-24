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
    session_id: Optional[int] = None,
    user_id: Optional[int] = None,
    syllabus_code: Optional[str] = None,
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
    if session_id:
        conditions.append("session_id = %s")
        params.append(session_id)
    if user_id:
        conditions.append("user_id = %s")
        params.append(user_id)
    if syllabus_code:
        conditions.append("syllabus_codes @> %s")
        params.append([syllabus_code])

    where = "WHERE " + " AND ".join(conditions) if conditions else ""

    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            f"SELECT id, question_type, sac_thue, question_part, question_number, "
            f"content_json, model_used, provider_used, exam_session, created_at, is_starred, "
            f"syllabus_codes, reg_codes, session_id "
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
                "syllabus_codes": r[11] or [],
                "reg_codes": r[12] or [],
                "exam_session_id": r[13],
            }
            for r in rows
        ],
    }


@router.get("/search")
def search_questions(
    question_type: Optional[str] = None,
    sac_thue: Optional[str] = None,
    q: Optional[str] = None,
    limit: int = 20,
):
    """Search questions — used in Generate page reference picker."""
    conditions = []
    params = []
    if question_type:
        type_map = {"mcq": "MCQ", "scenario": "SCENARIO_10", "longform": "LONGFORM_15"}
        db_type = type_map.get(question_type.lower(), question_type)
        conditions.append("question_type = %s")
        params.append(db_type)
    if sac_thue:
        conditions.append("sac_thue = %s")
        params.append(sac_thue)
    if q:
        conditions.append("(content_json::text ILIKE %s)")
        params.append(f"%{q}%")

    where = "WHERE " + " AND ".join(conditions) if conditions else ""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            f"SELECT id, question_type, sac_thue, question_number, created_at "
            f"FROM questions {where} ORDER BY created_at DESC LIMIT %s",
            params + [limit],
        )
        rows = cur.fetchall()
    return [{"id": r[0], "question_type": r[1], "sac_thue": r[2],
             "question_number": r[3], "created_at": r[4].isoformat() if r[4] else None}
            for r in rows]


@router.get("/for-reference")
def get_questions_for_reference(
    type: Optional[str] = None,
    sac_thue: Optional[str] = None,
):
    """Lightweight list for the reference question dropdown."""
    conditions = []
    params = []
    if type:
        # Map frontend type names to DB question_type
        type_map = {"mcq": "MCQ", "scenario": "SCENARIO_10", "longform": "LONGFORM_15",
                     "MCQ": "MCQ", "SCENARIO_10": "SCENARIO_10", "LONGFORM_15": "LONGFORM_15"}
        db_type = type_map.get(type, type)
        conditions.append("question_type = %s")
        params.append(db_type)
    if sac_thue:
        conditions.append("sac_thue = %s")
        params.append(sac_thue)

    where = "WHERE " + " AND ".join(conditions) if conditions else ""

    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            f"SELECT id, question_type, sac_thue, question_number, created_at, content_json "
            f"FROM questions {where} ORDER BY created_at DESC LIMIT 50",
            params,
        )
        rows = cur.fetchall()

    results = []
    for r in rows:
        q_id, q_type, q_sac, q_num, created, content = r
        # Build a short label
        date_str = created.strftime("%Y-%m-%d") if created else ""
        # Try to get a snippet from content
        snippet = ""
        try:
            cj = json.loads(content) if isinstance(content, str) else content
            if q_type == "MCQ":
                qs = cj.get("questions", [])
                first_scenario = qs[0].get("scenario", "") if qs else ""
                snippet = first_scenario[:100] if first_scenario else f"{len(qs)} questions"
            else:
                scenario = cj.get("scenario", "")
                snippet = scenario[:100] + "..." if len(scenario) > 100 else scenario
        except Exception:
            pass

        label = f"{q_num or q_type} {q_sac}"
        if snippet:
            label += f" — {snippet[:60]}{'...' if len(snippet) > 60 else ''}"
        label += f" ({date_str})"

        results.append({
            "id": q_id,
            "label": label,
            "question_type": q_type,
            "sac_thue": q_sac,
            "snippet": snippet,
            "created_at": date_str,
        })

    return results


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


@router.patch("/{question_id}/codes")
def update_question_codes(question_id: int, data: dict):
    """Update syllabus_codes and reg_codes for a question."""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "UPDATE questions SET syllabus_codes = %s, reg_codes = %s WHERE id = %s RETURNING id",
            (data.get('syllabus_codes', []), data.get('reg_codes', []), question_id)
        )
        if not cur.fetchone():
            raise HTTPException(404, "Question not found")
    return {"ok": True}


@router.delete("/{question_id}")
def delete_question(question_id: int):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM generation_log WHERE question_id = %s", (question_id,))
        cur.execute("DELETE FROM questions WHERE id = %s RETURNING id", (question_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Question not found")
    return {"message": "Question deleted"}
