import os
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
