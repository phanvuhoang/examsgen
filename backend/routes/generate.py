import time
import json
import logging
from fastapi import APIRouter, HTTPException

from backend.models import MCQGenerateRequest, ScenarioGenerateRequest, LongformGenerateRequest, RefineRequest
from backend.ai_provider import call_ai, parse_ai_json
from backend.context_builder import build_context, get_reference_content, build_kb_context
from backend.prompts import (
    MCQ_SYSTEM, MCQ_PROMPT,
    SCENARIO_SYSTEM, SCENARIO_PROMPT,
    LONGFORM_SYSTEM, LONGFORM_PROMPT,
)
from backend.database import get_db
from backend.html_renderer import render_question_html

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/generate", tags=["generate"])


def get_session(session_id: int = None) -> dict:
    """Resolve exam session. Returns session dict or empty dict."""
    with get_db() as conn:
        cur = conn.cursor()
        if session_id:
            cur.execute("SELECT * FROM exam_sessions WHERE id = %s", (session_id,))
        else:
            cur.execute("SELECT * FROM exam_sessions WHERE is_default = TRUE LIMIT 1")
        row = cur.fetchone()
        if not row:
            return {}
        cols = [d[0] for d in cur.description]
        return dict(zip(cols, row))


def build_session_context(session: dict) -> str:
    """Build session context string for prompt injection."""
    if not session:
        return ""
    return f"""EXAM SESSION: {session['name']}
REGULATIONS CUTOFF: Only use regulations effective up to {session['regulations_cutoff']}. Ignore any regulations enacted after this date.
FISCAL PERIOD: All scenarios must use fiscal year ending {session['fiscal_year_end']}. Do not use dates beyond {session['fiscal_year_end']} in scenarios.
TAX YEAR: {session['tax_year']}"""


def _save_question(question_type, sac_thue, question_part, question_number,
                   content_json, content_html, model_used, provider_used,
                   exam_session, duration_ms, prompt_tokens, completion_tokens,
                   session_id=None):
    """Save question and generation log to DB. Returns question id."""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO questions (question_type, sac_thue, question_part, question_number, "
            "content_json, content_html, model_used, provider_used, exam_session, session_id) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id",
            (question_type, sac_thue, question_part, question_number,
             json.dumps(content_json), content_html, model_used, provider_used, exam_session,
             session_id),
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
    """Log a failed generation attempt."""
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
        session = get_session(req.session_id)
        session_ctx = build_session_context(session)
        ctx = build_context(req.sac_thue, "MCQ")
        topics_instruction = ""
        if req.topics:
            topics_instruction = f"Topics to focus on: {', '.join(req.topics)}"
        if req.difficulty == "hard":
            topics_instruction += "\nMake these HARDER than standard — multi-step with tricky edge cases."

        custom_block = get_reference_content(
            reference_question_id=req.reference_question_id,
            custom_instructions=req.custom_instructions,
        )
        kb_block = build_kb_context(
            kb_syllabus_ids=req.kb_syllabus_ids,
            kb_regulation_ids=req.kb_regulation_ids,
            kb_sample_ids=req.kb_sample_ids,
        )

        prompt = MCQ_PROMPT.format(
            count=req.count,
            sac_thue=req.sac_thue,
            exam_session=req.exam_session,
            tax_rates=ctx["tax_rates"],
            syllabus=ctx["syllabus"],
            regulations=ctx["regulations"],
            sample=ctx["sample"],
            topics_instruction=topics_instruction,
            custom_instructions=custom_block,
            kb_context=kb_block,
            session_context=session_ctx,
        )

        result = call_ai(prompt, model_tier=req.model_tier, system_prompt=MCQ_SYSTEM)
        content_json = parse_ai_json(result["content"])
        content_html = render_question_html(content_json)
        duration_ms = int((time.time() - start) * 1000)

        q_id = _save_question(
            "MCQ", req.sac_thue, 1, "MCQ",
            content_json, content_html,
            result["model"], result["provider"],
            req.exam_session, duration_ms,
            result["prompt_tokens"], result["completion_tokens"],
            session_id=session.get("id"),
        )

        return {
            "id": q_id,
            "content_json": content_json,
            "content_html": content_html,
            "model_used": result["model"],
            "provider_used": result["provider"],
            "prompt_tokens": result["prompt_tokens"],
            "completion_tokens": result["completion_tokens"],
            "duration_ms": duration_ms,
        }
    except Exception as e:
        duration_ms = int((time.time() - start) * 1000)
        _log_failure("MCQ", req.sac_thue, e, duration_ms)
        logger.error(f"MCQ generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/scenario")
def generate_scenario(req: ScenarioGenerateRequest):
    start = time.time()
    try:
        session = get_session(req.session_id)
        session_ctx = build_session_context(session)
        ctx = build_context(req.sac_thue, "SCENARIO_10", req.question_number)
        industry_instruction = ""
        if req.scenario_industry:
            industry_instruction = f"Set the scenario in the {req.scenario_industry} industry."

        custom_block = get_reference_content(
            reference_question_id=req.reference_question_id,
            custom_instructions=req.custom_instructions,
        )
        kb_block = build_kb_context(
            kb_syllabus_ids=req.kb_syllabus_ids,
            kb_regulation_ids=req.kb_regulation_ids,
            kb_sample_ids=req.kb_sample_ids,
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
            industry_instruction=industry_instruction,
            question_type="SCENARIO_10",
            custom_instructions=custom_block,
            kb_context=kb_block,
            session_context=session_ctx,
        )

        result = call_ai(prompt, model_tier=req.model_tier, system_prompt=SCENARIO_SYSTEM)
        content_json = parse_ai_json(result["content"])
        content_html = render_question_html(content_json)
        duration_ms = int((time.time() - start) * 1000)

        q_id = _save_question(
            "SCENARIO_10", req.sac_thue, 2, req.question_number,
            content_json, content_html,
            result["model"], result["provider"],
            req.exam_session, duration_ms,
            result["prompt_tokens"], result["completion_tokens"],
            session_id=session.get("id"),
        )

        return {
            "id": q_id,
            "content_json": content_json,
            "content_html": content_html,
            "model_used": result["model"],
            "provider_used": result["provider"],
            "prompt_tokens": result["prompt_tokens"],
            "completion_tokens": result["completion_tokens"],
            "duration_ms": duration_ms,
        }
    except Exception as e:
        duration_ms = int((time.time() - start) * 1000)
        _log_failure("SCENARIO_10", req.sac_thue, e, duration_ms)
        logger.error(f"Scenario generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/longform")
def generate_longform(req: LongformGenerateRequest):
    start = time.time()
    try:
        session = get_session(req.session_id)
        session_ctx = build_session_context(session)
        ctx = build_context(req.sac_thue, "LONGFORM_15", req.question_number)

        custom_block = get_reference_content(
            reference_question_id=req.reference_question_id,
            custom_instructions=req.custom_instructions,
        )
        kb_block = build_kb_context(
            kb_syllabus_ids=req.kb_syllabus_ids,
            kb_regulation_ids=req.kb_regulation_ids,
            kb_sample_ids=req.kb_sample_ids,
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
            custom_instructions=custom_block,
            kb_context=kb_block,
            session_context=session_ctx,
        )

        result = call_ai(prompt, model_tier=req.model_tier, system_prompt=LONGFORM_SYSTEM)
        content_json = parse_ai_json(result["content"])
        content_html = render_question_html(content_json)
        duration_ms = int((time.time() - start) * 1000)

        q_id = _save_question(
            "LONGFORM_15", req.sac_thue, 3, req.question_number,
            content_json, content_html,
            result["model"], result["provider"],
            req.exam_session, duration_ms,
            result["prompt_tokens"], result["completion_tokens"],
            session_id=session.get("id"),
        )

        return {
            "id": q_id,
            "content_json": content_json,
            "content_html": content_html,
            "model_used": result["model"],
            "provider_used": result["provider"],
            "prompt_tokens": result["prompt_tokens"],
            "completion_tokens": result["completion_tokens"],
            "duration_ms": duration_ms,
        }
    except Exception as e:
        duration_ms = int((time.time() - start) * 1000)
        _log_failure("LONGFORM_15", req.sac_thue, e, duration_ms)
        logger.error(f"Longform generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/refine")
def refine_question(req: RefineRequest):
    """Refine a generated question via conversational chat."""
    import json as _json

    system = """You are a senior ACCA TX(VNM) examiner refining an exam question based on the user's feedback.
Return the COMPLETE updated question in the EXACT SAME JSON format as the input — do not omit any fields.
Only change what the user asks to change.
You can understand and respond to instructions in both English and Vietnamese.
Before the JSON, write 1-2 sentences explaining what you changed."""

    current_q_str = _json.dumps(req.current_content, ensure_ascii=False, indent=2)

    messages = [
        {"role": "user", "content": f"Here is the current question JSON:\n\n{current_q_str}"},
        {"role": "assistant", "content": "I have the question. What would you like me to change?"}
    ]

    # Add conversation history
    for msg in req.conversation_history:
        if not (msg["role"] == "assistant" and "What would you like" in msg.get("content", "")):
            messages.append({"role": msg["role"], "content": msg["content"]})

    messages.append({
        "role": "user",
        "content": req.user_message + "\n\nReturn your explanation followed by the complete updated JSON."
    })

    # Trim history if too long (keep last 8 exchanges)
    if len(messages) > 18:
        messages = messages[:2] + messages[-16:]

    try:
        result = call_ai(messages=messages, model_tier=req.model_tier, system_prompt=system)
        raw = result["content"]

        # Extract assistant note (text before JSON)
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
