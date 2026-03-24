"""
Simple context builder — reads raw files from session_files table, no DB parsing.
Strategy: load all relevant files for the given tax type,
trim to fit within MAX_CONTEXT_CHARS (~600K chars = ~150K tokens, safe for Claudible 200K).
Priority order when trimming: rates > syllabus > samples > regulations (trim largest last).
"""
import json
import logging
from backend.document_extractor import extract_text
from backend.database import get_db

logger = logging.getLogger(__name__)

# ~300K chars ≈ 75K tokens — keeps prompt well within Claudible limits
MAX_CONTEXT_CHARS = 300_000
# Per-regulation file cap to prevent one huge file eating all context
MAX_PER_REG_CHARS = 80_000

TAX_TYPE_ALIASES = {
    "CIT": ["CIT"],
    "VAT": ["VAT"],
    "PIT": ["PIT"],
    "FCT": ["FCT", "CIT-FCT", "VAT-FCT"],
    "TP": ["TP"],
    "TaxAdmin": ["TaxAdmin"],
    "ADMIN": ["TaxAdmin", "ADMIN"],
}


def _load_files(session_id: int, file_type: str, tax_type: str = None, exam_type: str = None) -> list:
    """Load active files from DB for the given session/type/tax_type."""
    with get_db() as conn:
        cur = conn.cursor()
        query = """
            SELECT file_path, display_name, tax_type, exam_type
            FROM session_files
            WHERE session_id = %s AND file_type = %s AND is_active = TRUE
        """
        params = [session_id, file_type]
        if tax_type:
            aliases = TAX_TYPE_ALIASES.get(tax_type, [tax_type])
            placeholders = ','.join(['%s'] * len(aliases))
            query += f" AND tax_type IN ({placeholders})"
            params.extend(aliases)
        if exam_type:
            query += " AND (exam_type = %s OR exam_type = 'ALL')"
            params.append(exam_type)
        query += " ORDER BY uploaded_at ASC"
        cur.execute(query, params)
        rows = cur.fetchall()
    return [{"path": r[0], "name": r[1], "tax_type": r[2], "exam_type": r[3]} for r in rows]


def _extract_with_cap(file_path: str, cap: int = MAX_PER_REG_CHARS) -> str:
    """Extract text from file, capped at `cap` chars."""
    try:
        text = extract_text(file_path)
        if len(text) > cap:
            text = text[:cap] + f"\n\n[... truncated at {cap} chars ...]"
        return text
    except Exception as e:
        logger.warning(f"Failed to extract {file_path}: {e}")
        return ""


def build_context(session_id: int, sac_thue: str, question_type: str) -> dict:
    """
    Build generation context for the given session, tax type, and question type.
    Returns dict with keys: tax_rates, syllabus, regulations, sample, sample_note.
    All text values are pre-trimmed to fit within MAX_CONTEXT_CHARS total.
    """
    logger.info(f"build_context: session_id={session_id}, sac_thue={sac_thue}, question_type={question_type}")

    exam_type_map = {
        "MCQ": "MCQ",
        "SCENARIO_10": "Scenario",
        "LONGFORM_15": "Longform",
    }
    exam_type = exam_type_map.get(question_type, "MCQ")

    # 1. Tax rates for this tax type (fall back to all rates if none specific)
    rates_files = _load_files(session_id, "rates", tax_type=sac_thue)
    if not rates_files:
        rates_files = _load_files(session_id, "rates")
    rates_parts = []
    for f in rates_files:
        text = _extract_with_cap(f["path"], cap=30_000)
        if text:
            rates_parts.append(f"## {f['name'] or f['path']}\n{text}")
    tax_rates = "\n\n".join(rates_parts)

    # 2. Syllabus for this tax type
    syllabus_files = _load_files(session_id, "syllabus", tax_type=sac_thue)
    syllabus_parts = []
    for f in syllabus_files:
        text = _extract_with_cap(f["path"], cap=40_000)
        if text:
            syllabus_parts.append(f"## {f['name'] or f['path']}\n{text}")
    syllabus = "\n\n".join(syllabus_parts)

    # 3. Sample question for this tax type + exam type
    sample_files = _load_files(session_id, "sample", tax_type=sac_thue, exam_type=exam_type)
    sample_note = ""
    if sample_files:
        loaded_tax = sample_files[0].get("tax_type", sac_thue)
        if loaded_tax and loaded_tax != sac_thue:
            sample_note = (
                f"[STYLE REFERENCE NOTE: The sample below is from {loaded_tax} — "
                f"replicate FORMAT and STRUCTURE only, not the tax content]"
            )
    sample_parts = []
    for f in sample_files:
        text = _extract_with_cap(f["path"], cap=50_000)
        if text:
            sample_parts.append(f"## {f['name'] or f['path']}\n{text}")
    sample = "\n\n".join(sample_parts)

    # 4. Regulations for this tax type
    reg_files = _load_files(session_id, "regulation", tax_type=sac_thue)
    reg_parts = []
    for f in reg_files:
        text = _extract_with_cap(f["path"], cap=MAX_PER_REG_CHARS)
        if text:
            reg_parts.append(f"## {f['name'] or f['path']}\n{text}")
    regulations = "\n\n".join(reg_parts)

    logger.info(f"  regulations: {len(reg_files)} files — {[f['name'] for f in reg_files]}")
    logger.info(f"  syllabus: {len(syllabus_files)} files — {[f['name'] for f in syllabus_files]}")
    logger.info(f"  sample: {len(sample_files)} files — {[f['name'] for f in sample_files]}")
    logger.info(f"  rates: {len(rates_files)} files — {[f['name'] for f in rates_files]}")

    # 5. Trim total to MAX_CONTEXT_CHARS
    fixed = len(tax_rates) + len(syllabus) + len(sample) + 5000
    reg_budget = MAX_CONTEXT_CHARS - fixed
    if len(regulations) > reg_budget and reg_budget > 0:
        logger.warning(f"Regulations for {sac_thue} trimmed from {len(regulations)} to {reg_budget} chars")
        regulations = regulations[:reg_budget] + "\n\n[... regulations trimmed to fit context ...]"
    elif reg_budget <= 0:
        logger.error(f"No context budget left for regulations! Fixed context = {fixed} chars")
        regulations = regulations[:50_000]

    logger.info(f"  total context chars: regulations={len(regulations)}, syllabus={len(syllabus)}, sample={len(sample)}, rates={len(tax_rates)}")

    return {
        "tax_rates": tax_rates,
        "syllabus": syllabus,
        "regulations": regulations,
        "sample": sample,
        "sample_note": sample_note,
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

    return "\n".join(parts)


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
