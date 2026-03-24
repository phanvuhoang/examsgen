import time
import json
import logging
from fastapi import APIRouter, HTTPException

from backend.models import MCQGenerateRequest, ScenarioGenerateRequest, LongformGenerateRequest, RefineRequest
from backend.ai_provider import call_ai, parse_ai_json
from backend.context_builder import build_context, get_reference_content, format_question_as_text
from backend.prompts import (
    MCQ_SYSTEM, MCQ_PROMPT,
    SCENARIO_SYSTEM, SCENARIO_PROMPT,
    LONGFORM_SYSTEM, LONGFORM_PROMPT,
    build_syllabus_instruction, build_difficulty_instruction,
)
from backend.database import get_db
from backend.html_renderer import render_question_html

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/generate", tags=["generate"])


def _resolve_session_id(session_id: int = None) -> int:
    """Resolve session_id: use provided, then default with files, then any session with files."""
    with get_db() as conn:
        cur = conn.cursor()
        if session_id:
            cur.execute("SELECT id FROM exam_sessions WHERE id = %s", (session_id,))
            row = cur.fetchone()
            if row:
                return row[0]

        # Try default session — but only if it has files
        cur.execute("SELECT id FROM exam_sessions WHERE is_default = TRUE ORDER BY id DESC LIMIT 1")
        row = cur.fetchone()
        if row:
            default_id = row[0]
            cur.execute("SELECT COUNT(*) FROM session_files WHERE session_id = %s AND is_active = TRUE", (default_id,))
            if cur.fetchone()[0] > 0:
                return default_id

        # Default session has no files — use most recent session WITH files
        cur.execute("""
            SELECT DISTINCT sf.session_id
            FROM session_files sf
            WHERE sf.is_active = TRUE
            ORDER BY sf.session_id DESC
            LIMIT 1
        """)
        row = cur.fetchone()
        if row:
            return row[0]

        # Absolute last resort: most recently created session
        cur.execute("SELECT id FROM exam_sessions ORDER BY id DESC LIMIT 1")
        row = cur.fetchone()
        return row[0] if row else None


def _save_question(question_type, sac_thue, question_part, question_number,
                   content_json, content_html, model_used, provider_used,
                   exam_session, duration_ms, prompt_tokens, completion_tokens,
                   session_id=None, user_id=1, syllabus_codes=None):
    """Save question and generation log to DB. Returns question id."""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO questions (question_type, sac_thue, question_part, question_number, "
            "content_json, content_html, model_used, provider_used, exam_session, session_id, user_id, syllabus_codes) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id",
            (question_type, sac_thue, question_part, question_number,
             json.dumps(content_json), content_html, model_used, provider_used, exam_session,
             session_id, user_id, syllabus_codes),
        )
        q_id = cur.fetchone()[0]
        cur.execute(
            "INSERT INTO generation_log (question_id, question_type, sac_thue, model_used, "
            "provider_used, prompt_tokens, completion_tokens, duration_ms, status) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'success')",
            (q_id, question_type, sac_thue, model_used, provider_used,
             prompt_tokens, completion_tokens, duration_ms),
        )
    return q_id


def _log_failure(question_type, sac_thue, error, duration_ms):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO generation_log (question_type, sac_thue, status, error, duration_ms) "
                "VALUES (%s, %s, 'failed', %s, %s)",
                (question_type, sac_thue, str(error)[:500], duration_ms),
            )
    except Exception:
        pass


@router.post("/mcq")
def generate_mcq(req: MCQGenerateRequest):
    start = time.time()
    try:
        session_id = _resolve_session_id(req.session_id)
        if not session_id:
            raise HTTPException(400, "No exam session configured. Please create a session first.")

        ctx = build_context(session_id, req.sac_thue, "MCQ")
        syllabus_instr = build_syllabus_instruction(req.syllabus_codes or [])
        diff_instr = build_difficulty_instruction(req.difficulty, req.topics)
        custom_block = get_reference_content(
            reference_question_id=req.reference_question_id,
            custom_instructions=req.custom_instructions,
        )

        prompt = MCQ_PROMPT.format(
            count=req.count,
            sac_thue=req.sac_thue,
            exam_session=req.exam_session,
            tax_rates=ctx["tax_rates"],
            syllabus=ctx["syllabus"],
            regulations=ctx["regulations"],
            sample=ctx["sample"],
            sample_note=ctx.get("sample_note", ""),
            syllabus_codes_instruction=syllabus_instr,
            difficulty_instruction=diff_instr,
            custom_instructions=custom_block,
        )

        result = call_ai(prompt, model_tier=req.model_tier, system_prompt=MCQ_SYSTEM, provider=req.provider)
        content_json = parse_ai_json(result["content"])
        content_html = render_question_html(content_json)
        duration_ms = int((time.time() - start) * 1000)

        # Extract syllabus codes from generated content
        generated_codes = []
        for q in content_json.get("questions", []):
            generated_codes.extend(q.get("syllabus_codes", []))

        q_id = _save_question(
            "MCQ", req.sac_thue, 1, "MCQ",
            content_json, content_html,
            result["model"], result["provider"],
            req.exam_session, duration_ms,
            result["prompt_tokens"], result["completion_tokens"],
            session_id=session_id, user_id=req.user_id,
            syllabus_codes=list(set(generated_codes)) or None,
        )

        return {
            "id": q_id,
            "question_id": q_id,
            "content_json": content_json,
            "content_html": content_html,
            "model_used": result["model"],
            "provider_used": result["provider"],
            "prompt_tokens": result["prompt_tokens"],
            "completion_tokens": result["completion_tokens"],
            "duration_ms": duration_ms,
        }
    except HTTPException:
        raise
    except Exception as e:
        duration_ms = int((time.time() - start) * 1000)
        _log_failure("MCQ", req.sac_thue, e, duration_ms)
        logger.error(f"MCQ generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/scenario")
def generate_scenario(req: ScenarioGenerateRequest):
    start = time.time()
    try:
        session_id = _resolve_session_id(req.session_id)
        if not session_id:
            raise HTTPException(400, "No exam session configured. Please create a session first.")

        ctx = build_context(session_id, req.sac_thue, "SCENARIO_10")
        syllabus_instr = build_syllabus_instruction(req.syllabus_codes or [])
        diff_instr = build_difficulty_instruction(req.difficulty)
        industry_instr = f"Set the scenario in the {req.scenario_industry} industry." if req.scenario_industry else ""
        custom_block = get_reference_content(
            reference_question_id=req.reference_question_id,
            custom_instructions=req.custom_instructions,
        )

        prompt = SCENARIO_PROMPT.format(
            question_number=req.question_number,
            sac_thue=req.sac_thue,
            marks=req.marks,
            exam_session=req.exam_session,
            tax_rates=ctx["tax_rates"],
            syllabus=ctx["syllabus"],
            regulations=ctx["regulations"],
            sample=ctx["sample"],
            sample_note=ctx.get("sample_note", ""),
            industry_instruction=industry_instr,
            question_type="SCENARIO_10",
            syllabus_codes_instruction=syllabus_instr,
            difficulty_instruction=diff_instr,
            custom_instructions=custom_block,
        )

        result = call_ai(prompt, model_tier=req.model_tier, system_prompt=SCENARIO_SYSTEM, provider=req.provider)
        content_json = parse_ai_json(result["content"])
        content_html = render_question_html(content_json)
        duration_ms = int((time.time() - start) * 1000)

        q_id = _save_question(
            "SCENARIO_10", req.sac_thue, 2, req.question_number,
            content_json, content_html,
            result["model"], result["provider"],
            req.exam_session, duration_ms,
            result["prompt_tokens"], result["completion_tokens"],
            session_id=session_id, user_id=req.user_id,
        )

        return {
            "id": q_id,
            "question_id": q_id,
            "content_json": content_json,
            "content_html": content_html,
            "model_used": result["model"],
            "provider_used": result["provider"],
            "prompt_tokens": result["prompt_tokens"],
            "completion_tokens": result["completion_tokens"],
            "duration_ms": duration_ms,
        }
    except HTTPException:
        raise
    except Exception as e:
        duration_ms = int((time.time() - start) * 1000)
        _log_failure("SCENARIO_10", req.sac_thue, e, duration_ms)
        logger.error(f"Scenario generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/longform")
def generate_longform(req: LongformGenerateRequest):
    start = time.time()
    try:
        session_id = _resolve_session_id(req.session_id)
        if not session_id:
            raise HTTPException(400, "No exam session configured. Please create a session first.")

        ctx = build_context(session_id, req.sac_thue, "LONGFORM_15")
        syllabus_instr = build_syllabus_instruction(req.syllabus_codes or [])
        diff_instr = build_difficulty_instruction(req.difficulty)
        custom_block = get_reference_content(
            reference_question_id=req.reference_question_id,
            custom_instructions=req.custom_instructions,
        )

        prompt = LONGFORM_PROMPT.format(
            question_number=req.question_number,
            sac_thue=req.sac_thue,
            marks=req.marks,
            exam_session=req.exam_session,
            tax_rates=ctx["tax_rates"],
            syllabus=ctx["syllabus"],
            regulations=ctx["regulations"],
            sample=ctx["sample"],
            sample_note=ctx.get("sample_note", ""),
            syllabus_codes_instruction=syllabus_instr,
            difficulty_instruction=diff_instr,
            custom_instructions=custom_block,
        )

        result = call_ai(prompt, model_tier=req.model_tier, system_prompt=LONGFORM_SYSTEM, provider=req.provider)
        content_json = parse_ai_json(result["content"])
        content_html = render_question_html(content_json)
        duration_ms = int((time.time() - start) * 1000)

        q_id = _save_question(
            "LONGFORM_15", req.sac_thue, 3, req.question_number,
            content_json, content_html,
            result["model"], result["provider"],
            req.exam_session, duration_ms,
            result["prompt_tokens"], result["completion_tokens"],
            session_id=session_id, user_id=req.user_id,
        )

        return {
            "id": q_id,
            "question_id": q_id,
            "content_json": content_json,
            "content_html": content_html,
            "model_used": result["model"],
            "provider_used": result["provider"],
            "prompt_tokens": result["prompt_tokens"],
            "completion_tokens": result["completion_tokens"],
            "duration_ms": duration_ms,
        }
    except HTTPException:
        raise
    except Exception as e:
        duration_ms = int((time.time() - start) * 1000)
        _log_failure("LONGFORM_15", req.sac_thue, e, duration_ms)
        logger.error(f"Longform generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/refine")
def refine_question(req: RefineRequest):
    """Refine a generated question via conversational chat."""
    system = """You are a senior ACCA TX(VNM) examiner refining an exam question based on the user's feedback.
Return the COMPLETE updated question in the EXACT SAME JSON format as the input — do not omit any fields.
Only change what the user asks to change.
You can understand and respond to instructions in both English and Vietnamese.
Before the JSON, write 1-2 sentences explaining what you changed."""

    current_q_str = json.dumps(req.current_content, ensure_ascii=False, indent=2)

    messages = [
        {"role": "user", "content": f"Here is the current question JSON:\n\n{current_q_str}"},
        {"role": "assistant", "content": "I have the question. What would you like me to change?"}
    ]

    for msg in req.conversation_history:
        if not (msg["role"] == "assistant" and "What would you like" in msg.get("content", "")):
            messages.append({"role": msg["role"], "content": msg["content"]})

    messages.append({
        "role": "user",
        "content": req.user_message + "\n\nReturn your explanation followed by the complete updated JSON."
    })

    if len(messages) > 18:
        messages = messages[:2] + messages[-16:]

    try:
        result = call_ai(messages=messages, model_tier=req.model_tier, system_prompt=system, provider=req.provider)
        raw = result["content"]

        json_start = raw.find('{')
        assistant_note = raw[:json_start].strip() if json_start > 5 else "Question updated!"
        updated_content = parse_ai_json(raw)
        content_html = render_question_html(updated_content)

        return {
            "content": updated_content,
            "content_html": content_html,
            "assistant_message": assistant_note,
            "model_used": result["model"],
            "provider_used": result["provider"],
        }
    except Exception as e:
        logger.error(f"Refine failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
