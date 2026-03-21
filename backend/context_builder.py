import os
import json
import logging

from backend.config import (
    REGULATIONS_DIR, SYLLABUS_DIR, SAMPLES_DIR,
    SAC_THUE_SYLLABUS, MAX_CONTEXT_CHARS, MAX_REGULATION_CHARS,
)
from backend.document_extractor import extract_text
from backend.database import get_db

logger = logging.getLogger(__name__)


def get_tax_rates() -> str:
    """Load shared tax rates file."""
    for fname in os.listdir(os.path.join(REGULATIONS_DIR, "SHARED")):
        if "Tax_Rates" in fname:
            return extract_text(os.path.join(REGULATIONS_DIR, "SHARED", fname))
    return ""


def get_syllabus(sac_thue: str) -> str:
    """Load syllabus for the given tax type."""
    fname = SAC_THUE_SYLLABUS.get(sac_thue, "")
    if not fname:
        return ""
    path = os.path.join(SYLLABUS_DIR, fname)
    return extract_text(path)


def get_regulations_text(sac_thue: str) -> str:
    """Load active regulation texts from DB and filesystem."""
    # First try from DB
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT file_path, ten_van_ban FROM regulations "
                "WHERE sac_thue = %s AND is_active = TRUE AND ngon_ngu = 'ENG' "
                "ORDER BY uploaded_at DESC",
                (sac_thue,),
            )
            rows = cur.fetchall()
            if rows:
                parts = []
                total = 0
                for file_path, name in rows:
                    text = extract_text(file_path)
                    if total + len(text) > MAX_REGULATION_CHARS:
                        text = text[: MAX_REGULATION_CHARS - total]
                    parts.append(f"## {name or file_path}\n{text}")
                    total += len(text)
                    if total >= MAX_REGULATION_CHARS:
                        break
                return "\n\n".join(parts)
    except Exception as e:
        logger.warning(f"DB query for regulations failed, falling back to filesystem: {e}")

    # Fallback: read directly from filesystem
    reg_dir = os.path.join(REGULATIONS_DIR, sac_thue)
    if not os.path.isdir(reg_dir):
        return ""
    parts = []
    total = 0
    for fname in sorted(os.listdir(reg_dir)):
        path = os.path.join(reg_dir, fname)
        text = extract_text(path)
        if total + len(text) > MAX_REGULATION_CHARS:
            text = text[: MAX_REGULATION_CHARS - total]
        parts.append(f"## {fname}\n{text}")
        total += len(text)
        if total >= MAX_REGULATION_CHARS:
            break
    return "\n\n".join(parts)


def get_sample(sac_thue: str, question_type: str, question_number: str = None) -> str:
    """Load sample question file."""
    if question_type == "MCQ":
        fname = f"MCQ_{sac_thue}.docx"
    elif question_type == "SCENARIO_10":
        qn = question_number or {"CIT": "Q1", "PIT": "Q2", "FCT": "Q3", "VAT": "Q4"}.get(sac_thue, "Q1")
        fname = f"{qn}_{sac_thue}.docx"
    elif question_type == "LONGFORM_15":
        qn = question_number or ("Q5" if sac_thue == "CIT" else "Q6")
        fname = f"{qn}_{sac_thue}_LongForm.docx"
    else:
        return ""

    path = os.path.join(SAMPLES_DIR, fname)
    return extract_text(path)


def build_context(sac_thue: str, question_type: str, question_number: str = None) -> dict:
    """Assemble all context parts for a generation request."""
    tax_rates = get_tax_rates()
    syllabus = get_syllabus(sac_thue)
    regulations = get_regulations_text(sac_thue)
    sample = get_sample(sac_thue, question_type, question_number)

    # Trim if total context exceeds limit
    total = len(tax_rates) + len(syllabus) + len(regulations) + len(sample)
    if total > MAX_CONTEXT_CHARS:
        # Prioritize: tax_rates > syllabus > sample > regulations
        available = MAX_CONTEXT_CHARS - len(tax_rates) - len(syllabus) - len(sample)
        if available > 0:
            regulations = regulations[:available]
        else:
            regulations = regulations[:10000]

    return {
        "tax_rates": tax_rates,
        "syllabus": syllabus,
        "regulations": regulations,
        "sample": sample,
    }


def format_question_as_text(content: dict) -> str:
    """Convert stored question JSON back to readable plain text for use as prompt reference."""
    parts = []
    q_type = content.get("type", "")

    if q_type == "MCQ":
        for q in content.get("questions", []):
            parts.append(f"Question {q.get('number', '')}")
            if q.get("scenario"):
                parts.append(q["scenario"])
            parts.append(q.get("question", ""))
            for letter in ["A", "B", "C", "D"]:
                opt = q.get("options", {}).get(letter, {})
                key = " [KEY]" if opt.get("is_key") else ""
                parts.append(f"  {letter}. {opt.get('text', '')}{key}")
                if opt.get("explanation"):
                    parts.append(f"     {opt['explanation']}")
            parts.append("")
    elif q_type in ("SCENARIO_10", "LONGFORM_15"):
        qn = content.get("question_number", "")
        marks = content.get("marks", "")
        parts.append(f"Question {qn} ({marks} marks)")
        parts.append(content.get("scenario", ""))
        for sq in content.get("sub_questions", []):
            parts.append(f"\n{sq.get('label', '')} ({sq.get('marks', '')} marks)")
            parts.append(sq.get("question", ""))
            if sq.get("answer"):
                parts.append(f"Answer: {sq['answer']}")
            for ms in sq.get("marking_scheme", []):
                parts.append(f"  - {ms.get('point', '')} [{ms.get('mark', '')} mark(s)]")

    return "\n".join(parts)


def extract_text_from_file(file_path: str) -> str:
    """Extract text from a file (wrapper for use by KB parse)."""
    return extract_text(file_path)


def build_full_context(req, session_id: int) -> str:
    """Build the v2 context block from structured KB references (syllabus_codes, reg_codes, etc.)."""
    import re as _re
    import json as _json
    parts = []

    # 1. Session economic parameters
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("SELECT parameters FROM exam_sessions WHERE id = %s", (session_id,))
            row = cur.fetchone()
        if row and row[0]:
            params = row[0] if isinstance(row[0], list) else _json.loads(row[0])
            if params:
                params_text = "\n".join(f"- {p['key']}: {p['value']} {p.get('unit', '')}" for p in params)
                parts.append(f"EXAM ECONOMIC PARAMETERS (use these figures in calculations):\n{params_text}")
    except Exception as e:
        logger.warning(f"Failed to load session parameters: {e}")

    # 2. Syllabus items
    syllabus_codes = getattr(req, 'syllabus_codes', None)
    if syllabus_codes:
        try:
            with get_db() as conn:
                cur = conn.cursor()
                placeholders = ','.join(['%s'] * len(syllabus_codes))
                cur.execute(f"""
                    SELECT syllabus_code, topic, detailed_syllabus
                    FROM kb_syllabus WHERE session_id=%s AND syllabus_code IN ({placeholders})
                """, [session_id] + list(syllabus_codes))
                rows = cur.fetchall()
            if rows:
                items = "\n".join(f"- [{r[0]}] {r[1] or ''}: {r[2] or ''}" for r in rows)
                parts.append(f"SYLLABUS ITEMS TO TEST (question MUST cover these):\n{items}")
        except Exception as e:
            logger.warning(f"Failed to load syllabus items: {e}")

    # 3. Regulation paragraphs
    reg_codes = getattr(req, 'reg_codes', None)
    if reg_codes:
        try:
            with get_db() as conn:
                cur = conn.cursor()
                placeholders = ','.join(['%s'] * len(reg_codes))
                cur.execute(f"""
                    SELECT reg_code, doc_ref, paragraph_text
                    FROM kb_regulation_parsed WHERE session_id=%s AND reg_code IN ({placeholders})
                """, [session_id] + list(reg_codes))
                rows = cur.fetchall()
            if rows:
                items = "\n".join(f"- [{r[0]}] ({r[1] or ''}): {r[2]}" for r in rows)
                parts.append(f"REGULATION PARAGRAPHS TO CITE:\n{items}")
        except Exception as e:
            logger.warning(f"Failed to load regulation paragraphs: {e}")

    # 4. Tax rates for this tax type
    sac_thue = getattr(req, 'sac_thue', None)
    if sac_thue:
        try:
            with get_db() as conn:
                cur = conn.cursor()
                cur.execute("""
                    SELECT table_name, content FROM kb_tax_rates
                    WHERE session_id=%s AND tax_type=%s AND is_active=TRUE
                    ORDER BY display_order
                """, (session_id, sac_thue))
                rows = cur.fetchall()
            if rows:
                rate_blocks = []
                for r in rows:
                    clean = _re.sub(r'<[^>]+>', ' ', r[1]).strip()
                    rate_blocks.append(f"=== {r[0]} ===\n{clean}")
                parts.append("TAX RATES (use these in calculations):\n" + "\n\n".join(rate_blocks))
        except Exception as e:
            logger.warning(f"Failed to load tax rates: {e}")

    # 5. Sample question references
    sample_question_ids = getattr(req, 'sample_question_ids', None)
    if sample_question_ids:
        try:
            with get_db() as conn:
                cur = conn.cursor()
                placeholders = ','.join(['%s'] * len(sample_question_ids))
                cur.execute(f"SELECT title, content, answer FROM sample_questions WHERE id IN ({placeholders})",
                            sample_question_ids)
                rows = cur.fetchall()
            if rows:
                refs = []
                for r in rows:
                    q_clean = _re.sub(r'<[^>]+>', ' ', r[1]).strip()[:1500]
                    a_clean = _re.sub(r'<[^>]+>', ' ', (r[2] or '')).strip()[:500]
                    refs.append(f"=== STYLE REFERENCE: {r[0] or 'Sample'} ===\nQuestion: {q_clean}\nAnswer: {a_clean}")
                parts.append("STYLE REFERENCES (replicate structure and difficulty):\n\n" + "\n\n".join(refs))
        except Exception as e:
            logger.warning(f"Failed to load sample questions: {e}")

    # 6. Question bank references
    question_bank_ids = getattr(req, 'question_bank_ids', None)
    if question_bank_ids:
        try:
            with get_db() as conn:
                cur = conn.cursor()
                placeholders = ','.join(['%s'] * len(question_bank_ids))
                cur.execute(f"SELECT content_json FROM questions WHERE id IN ({placeholders})",
                            question_bank_ids)
                rows = cur.fetchall()
            if rows:
                refs = []
                for r in rows:
                    content = r[0] if isinstance(r[0], dict) else _json.loads(r[0])
                    refs.append(f"=== QUESTION BANK REFERENCE ===\n{_json.dumps(content, ensure_ascii=False)[:2000]}")
                parts.append("QUESTION BANK REFERENCES:\n" + "\n\n".join(refs))
        except Exception as e:
            logger.warning(f"Failed to load question bank references: {e}")

    # 7. MCQ subtype instruction
    mcq_subtype = getattr(req, 'mcq_subtype', None)
    if mcq_subtype:
        subtype_map = {
            'MCQ-1': "Generate SINGLE correct answer MCQs. One option is clearly correct, three are plausible distractors.",
            'MCQ-N': "Generate MULTIPLE correct answers MCQs. Two or more options are correct. Clearly state 'Select ALL that apply'.",
            'MCQ-FIB': "Generate FILL-IN-THE-BLANK MCQs. A statement with one blank, candidates choose from a word bank of 5-6 options.",
        }
        instruction = subtype_map.get(mcq_subtype, '')
        if instruction:
            parts.append(f"MCQ FORMAT INSTRUCTION: {instruction}")

    return "\n\n---\n\n".join(parts)


def build_kb_context(kb_syllabus_ids=None, kb_regulation_ids=None, kb_sample_ids=None) -> str:
    """Build focused context from Knowledge Base selections."""
    parts = []
    with get_db() as conn:
        cur = conn.cursor()

        if kb_syllabus_ids:
            cur.execute("SELECT section_code, section_title, content FROM kb_syllabus WHERE id = ANY(%s)", (kb_syllabus_ids,))
            rows = cur.fetchall()
            items_text = "\n".join(f"- [{r[0] or ''}] {r[1] or ''}: {r[2]}" for r in rows)
            parts.append(f"SYLLABUS ITEMS TO TEST (question MUST cover these specifically):\n{items_text}")

        if kb_regulation_ids:
            cur.execute("SELECT regulation_ref, content FROM kb_regulation WHERE id = ANY(%s)", (kb_regulation_ids,))
            rows = cur.fetchall()
            items_text = "\n".join(f"- [{r[0] or ''}]: {r[1]}" for r in rows)
            parts.append(f"REGULATION PARAGRAPHS TO USE (cite these articles specifically in the question):\n{items_text}")

        if kb_sample_ids:
            cur.execute("SELECT title, content, exam_tricks FROM kb_sample WHERE id = ANY(%s)", (kb_sample_ids,))
            rows = cur.fetchall()
            style_parts = []
            for r in rows:
                style_parts.append(f"=== STYLE REFERENCE: {r[0] or 'Sample'} ===")
                if r[2]:
                    style_parts.append(f"Key exam tricks in this sample: {r[2]}")
                style_parts.append(r[1])
            parts.append("STYLE REFERENCES — replicate structure, difficulty and exam tricks:\n" + "\n".join(style_parts))

    return "\n\n".join(parts)


def get_reference_content(reference_question_id: int = None, custom_instructions: str = None) -> str:
    """Build the custom instructions block to inject into prompt."""
    parts = []

    if reference_question_id:
        try:
            with get_db() as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT content_json, question_type, sac_thue FROM questions WHERE id = %s",
                    (reference_question_id,),
                )
                row = cur.fetchone()
            if row:
                content = json.loads(row[0]) if isinstance(row[0], str) else row[0]
                ref_text = format_question_as_text(content)
                parts.append(
                    f"REFERENCE QUESTION (write a NEW question with SIMILAR style, structure and difficulty):\n{ref_text}"
                )
        except Exception as e:
            logger.warning(f"Failed to load reference question {reference_question_id}: {e}")

    if custom_instructions:
        if len(custom_instructions) > 300 and any(
            kw in custom_instructions for kw in ["Answer", "VND", "marks", "Calculate"]
        ):
            parts.append(
                f"SAMPLE TO REPLICATE (write a NEW question with SIMILAR style, structure, difficulty and topic):\n{custom_instructions}"
            )
        else:
            parts.append(f"SPECIFIC INSTRUCTIONS FROM EXAMINER:\n{custom_instructions}")

    return "\n\n".join(parts)
