# ExamsGen — Refactor Brief v3.0
**Date:** March 2026  
**Repo:** `phanvuhoang/examsgen`  
**Goal:** Simplify app — remove all KB parsing complexity, use raw file upload + direct AI generation

---

## Core Principle Change

**Old approach (overcomplicated):**
```
Upload .docx → parse into DB rows → tag syllabus → build context from DB → generate
```

**New approach (simple & correct):**
```
Upload .docx files → store as files → load full text into AI context → generate
```

No parsing. No KB tables. No rule_parser. Claude reads raw documents directly — same as Claude Projects.

---

## What to KEEP (already working well)

- `backend/ai_provider.py` — Claudible → Anthropic → OpenAI fallback logic ✅
- `backend/auth_middleware.py` — password auth ✅
- `backend/document_extractor.py` — extract text from .docx/.doc/.xlsx ✅
- `backend/html_renderer.py` — render question HTML ✅
- `backend/routes/auth.py` — login ✅
- `backend/routes/questions.py` — question bank CRUD ✅
- `backend/routes/export.py` — export to Word/PDF ✅
- DB tables: `questions`, `generation_log` ✅ (keep as-is)
- Frontend: keep existing React UI structure ✅

---

## What to REMOVE entirely

Delete these files/routes — no longer needed:
- `backend/utils/rule_parser.py` ← DELETE
- `backend/routes/kb.py` ← DELETE  
- `backend/routes/sessions.py` ← keep but simplify (see below)
- `backend/routes/sample_questions.py` ← DELETE (merge into regulations route)
- `backend/seed.py` ← DELETE
- DB tables to DROP: `kb_syllabus`, `kb_regulation_parsed`, `kb_regulation`, `kb_tax_rates`, `kb_sample`, `sample_questions`

---

## New Simple Architecture

### File Storage Structure (unchanged from before)
```
/app/data/
  sessions/
    {session_id}/
      regulations/
        CIT/
          Reg_CIT_Law67_2025.docx
          Reg_CIT_Decree320_2025.docx
          Reg_CIT-FCT_Circular20_2026.docx
        VAT/
          Reg_VAT_Law48_2024.docx
          Reg_VAT_Decree181_2025.docx
          Reg_VAT_Invoice_VBHN18.docx
          Reg_VAT-FCT_Circular69_2025.docx
        PIT/
          Reg_PIT_VBHN02.docx
        FCT/
          Reg_FCT_Circular103_2014.docx
        TP/
          Reg_TP_Decree132_2020.docx
          Reg_TP_Decree20_2025.docx
        TaxAdmin/
          Reg_TaxAdmin_VBHN15.docx
      syllabus/
        Syllabus_CIT_D27.xlsx
        Syllabus_VAT_D27.xlsx
        Syllabus_PIT_D27.xlsx
        Syllabus_FCT_D27.xlsx
        Syllabus_TP_D27.xlsx
        Syllabus_TaxAdmin_D27.xlsx
      rates/
        Rates_CIT.xlsx
        Rates_VAT.xlsx
        Rates_FCT.xlsx
        Rates_PIT_Employment.xlsx
        Rates_PIT_Business.xlsx
        Rates_PIT_NonEmployment.xlsx
        Rates_PIT_NetToGross.xlsx
        Rates_PIT_Relief.xlsx
        Rates_SHUI.xlsx
      samples/
        Sample_MCQ_CIT.docx
        Sample_MCQ_VAT.docx
        Sample_MCQ_PIT.docx
        Sample_MCQ_FCT.docx
        Sample_MCQ_TP.docx
        Sample_MCQ_TaxAdmin.docx
        Sample_Scenario_CIT.docx
        Sample_Scenario_VAT.docx
        Sample_Scenario_PIT.docx
        Sample_Scenario_FCT.docx
        Sample_Longform_CIT.docx
        Sample_Longform_PIT.docx
```

### DB Schema (simplified)

Keep only these tables:

```sql
-- Exam sessions
CREATE TABLE exam_sessions (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,          -- e.g. "June 2026"
    exam_date VARCHAR(20),               -- e.g. "Jun2026" (used in prompts)
    assumed_date VARCHAR(50),            -- e.g. "1 June 2026" (for scenario anchor)
    is_default BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Files uploaded per session
CREATE TABLE session_files (
    id SERIAL PRIMARY KEY,
    session_id INTEGER REFERENCES exam_sessions(id) ON DELETE CASCADE,
    file_type VARCHAR(20) NOT NULL,      -- 'regulation' | 'syllabus' | 'rates' | 'sample'
    tax_type VARCHAR(20),                -- CIT | VAT | PIT | FCT | TP | TaxAdmin | ALL
    exam_type VARCHAR(20),               -- MCQ | Scenario | Longform | ALL (for sample files)
    display_name VARCHAR(200),           -- e.g. "CIT Law 67/2025"
    file_name VARCHAR(500),              -- original filename
    file_path VARCHAR(500),              -- full path on disk
    file_size INTEGER,
    is_active BOOLEAN DEFAULT TRUE,
    uploaded_at TIMESTAMP DEFAULT NOW()
);

-- Generated questions (keep existing schema)
CREATE TABLE questions (
    id SERIAL PRIMARY KEY,
    session_id INTEGER REFERENCES exam_sessions(id),
    question_type VARCHAR(20) NOT NULL,  -- MCQ | SCENARIO_10 | LONGFORM_15
    sac_thue VARCHAR(20) NOT NULL,
    question_part INTEGER,
    question_number VARCHAR(10),
    content_json JSONB NOT NULL,
    content_html TEXT,
    syllabus_codes TEXT[],               -- e.g. {CIT-2d, CIT-2e} — from AI output
    model_used VARCHAR(100),
    provider_used VARCHAR(50),
    exam_session VARCHAR(20),
    created_at TIMESTAMP DEFAULT NOW(),
    is_starred BOOLEAN DEFAULT FALSE,
    notes TEXT,
    user_id INTEGER DEFAULT 1
);

-- Generation audit log (keep existing)
CREATE TABLE generation_log (
    id SERIAL PRIMARY KEY,
    question_id INTEGER REFERENCES questions(id),
    question_type VARCHAR(20),
    sac_thue VARCHAR(20),
    model_used VARCHAR(100),
    provider_used VARCHAR(50),
    prompt_tokens INTEGER,
    completion_tokens INTEGER,
    duration_ms INTEGER,
    status VARCHAR(20),
    error TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);
```

---

## New `context_builder.py` (replace entirely)

```python
"""
Simple context builder — reads raw files, no DB parsing.
Strategy: load all relevant files for the given tax type,
trim to fit within MAX_CONTEXT_CHARS (~600K chars = ~150K tokens, safe for Claudible 200K).
Priority order when trimming: rates > syllabus > samples > regulations (trim largest last).
"""
import os
import logging
from backend.document_extractor import extract_text
from backend.database import get_db

logger = logging.getLogger(__name__)

# ~600K chars ≈ 150K tokens — safe for Claudible 200K context window
MAX_CONTEXT_CHARS = 600_000
# Per-regulation file cap to prevent one huge file eating all context
MAX_PER_REG_CHARS = 150_000

TAX_TYPE_ALIASES = {
    "CIT": ["CIT"],
    "VAT": ["VAT"],
    "PIT": ["PIT"],
    "FCT": ["FCT", "CIT-FCT", "VAT-FCT"],  # FCT circulars may be tagged CIT-FCT or VAT-FCT
    "TP": ["TP"],
    "TaxAdmin": ["TaxAdmin"],
}


def _load_files(session_id: int, file_type: str, tax_type: str = None, exam_type: str = None) -> list[dict]:
    """Load active files from DB for the given session/type/taxtype."""
    with get_db() as conn:
        cur = conn.cursor()
        query = """
            SELECT file_path, display_name, tax_type, exam_type
            FROM session_files
            WHERE session_id = %s AND file_type = %s AND is_active = TRUE
        """
        params = [session_id, file_type]
        if tax_type:
            # Match primary tax_type OR aliases (e.g. FCT matches CIT-FCT, VAT-FCT)
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
    Returns dict with keys: tax_rates, syllabus, regulations, sample.
    All text values are pre-trimmed to fit within MAX_CONTEXT_CHARS total.
    """
    # Map question_type to exam_type label for sample lookup
    exam_type_map = {
        "MCQ": "MCQ",
        "SCENARIO_10": "Scenario",
        "LONGFORM_15": "Longform",
    }
    exam_type = exam_type_map.get(question_type, "MCQ")

    # 1. Tax rates (ALL tax_type — rates apply across all)
    rates_files = _load_files(session_id, "rates", tax_type=sac_thue) or _load_files(session_id, "rates")
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

    # 5. Trim total to MAX_CONTEXT_CHARS
    # Priority: rates (keep all) > syllabus (keep all) > sample (keep all) > regulations (trim last)
    fixed = len(tax_rates) + len(syllabus) + len(sample) + 5000  # 5K for prompt overhead
    reg_budget = MAX_CONTEXT_CHARS - fixed
    if len(regulations) > reg_budget and reg_budget > 0:
        logger.warning(f"Regulations for {sac_thue} trimmed from {len(regulations)} to {reg_budget} chars")
        regulations = regulations[:reg_budget] + "\n\n[... regulations trimmed to fit context ...]"
    elif reg_budget <= 0:
        logger.error(f"No context budget left for regulations! Fixed context = {fixed} chars")
        regulations = regulations[:50_000]

    return {
        "tax_rates": tax_rates,
        "syllabus": syllabus,
        "regulations": regulations,
        "sample": sample,
    }
```

---

## New `routes/sessions.py` (simplified)

Manage exam sessions and their uploaded files.

```python
# Endpoints:
GET    /api/sessions                    → list all sessions
POST   /api/sessions                    → create session {name, exam_date, assumed_date}
PUT    /api/sessions/{id}               → update session
DELETE /api/sessions/{id}               → delete session (cascade files)
POST   /api/sessions/{id}/default       → set as default session

# File management within a session:
GET    /api/sessions/{id}/files                   → list all files in session (grouped by type)
POST   /api/sessions/{id}/files                   → upload file (multipart)
DELETE /api/sessions/{id}/files/{file_id}         → delete file
PUT    /api/sessions/{id}/files/{file_id}/toggle  → activate/deactivate file

# Carry forward:
POST   /api/sessions/{id}/carry-forward           → copy all files from another session
  body: { "from_session_id": N }
  → copies file records (and optionally files on disk) from source session
```

---

## Updated `routes/generate.py`

Key change: pass `session_id` to `build_context()` instead of loading from filesystem by convention.

```python
# Generate endpoint signature change:
# OLD: ctx = build_context(req.sac_thue, "MCQ")
# NEW: ctx = build_context(session_id, req.sac_thue, "MCQ")

# session_id resolution (in each generate endpoint):
session_id = req.session_id
if not session_id:
    # use default session
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id FROM exam_sessions WHERE is_default = TRUE LIMIT 1")
        row = cur.fetchone()
        session_id = row[0] if row else None

if not session_id:
    raise HTTPException(400, "No exam session configured. Please create a session first.")
```

---

## Updated `routes/regulations.py` → rename to file_upload logic

Merge old `regulations` route into session file upload. Remove standalone `/api/regulations` endpoints — file management is now under `/api/sessions/{id}/files`.

Keep `/api/regulations` as a **compatibility alias** that redirects to default session's files.

---

## Updated `models.py`

Remove all KB-related fields from request models. Simplify:

```python
class MCQGenerateRequest(BaseModel):
    sac_thue: str
    count: int = 3
    topics: Optional[List[str]] = None
    exam_session: str = "Jun2026"
    difficulty: str = "standard"       # standard | hard
    model_tier: str = "fast"            # fast=sonnet, strong=opus
    provider: Optional[str] = None
    session_id: Optional[int] = None
    user_id: int = 1
    # Syllabus targeting (optional — passed as text hint to prompt, not DB lookup)
    syllabus_codes: Optional[List[str]] = None   # e.g. ["CIT-2d", "CIT-2n"]
    custom_instructions: Optional[str] = None    # free-text examiner notes

class ScenarioGenerateRequest(BaseModel):
    question_number: str               # Q1 | Q2 | Q3 | Q4
    sac_thue: str
    marks: int = 10
    exam_session: str = "Jun2026"
    scenario_industry: Optional[str] = None
    difficulty: str = "standard"
    model_tier: str = "strong"
    provider: Optional[str] = None
    session_id: Optional[int] = None
    user_id: int = 1
    syllabus_codes: Optional[List[str]] = None
    custom_instructions: Optional[str] = None

class LongformGenerateRequest(BaseModel):
    question_number: str               # Q5 | Q6
    sac_thue: str
    marks: int = 15
    exam_session: str = "Jun2026"
    difficulty: str = "standard"
    model_tier: str = "strong"
    provider: Optional[str] = None
    session_id: Optional[int] = None
    user_id: int = 1
    syllabus_codes: Optional[List[str]] = None
    custom_instructions: Optional[str] = None

# Keep RefineRequest, ExportRequest, StarRequest as-is
```

---

## Updated `prompts.py`

### Key changes to prompts:
1. Add `{syllabus_codes_instruction}` placeholder — injected when user targets specific codes
2. Add `{difficulty_instruction}` placeholder
3. Remove all KB context placeholders (`{kb_context}`, `{reg_codes}`, `{session_context}` etc.)

### MCQ System Prompt (replace MCQ_SYSTEM):
```
You are a Senior ACCA TX(VNM) Examiner and Vietnamese tax partner with 30+ years of Big 4 experience.
You write exam questions at ACCA professional standard — not textbook exercises.
Every MCQ requires multi-step calculation or application of law to a fact pattern.
Never test pure recall.
Always cite the specific Article and Regulation in your answer/marking scheme.
Always tag each question with ACCA syllabus codes tested (e.g. CIT-2d, CIT-2e).
```

### MCQ Prompt template:
```python
MCQ_PROMPT = """
Generate {count} MCQ question(s) for Part 1 of ACCA TX(VNM).

EXAM SESSION: {exam_session}
TAX TYPE: {sac_thue}
{syllabus_codes_instruction}
{difficulty_instruction}
{custom_instructions}

TAX RATES (use these figures in all calculations):
{tax_rates}

SYLLABUS (scope of what can be tested — stay within this):
{syllabus}

REGULATIONS (apply these to create realistic scenarios):
{regulations}

SAMPLE QUESTIONS (replicate this format, difficulty, and exam style EXACTLY):
{sample}

REQUIREMENTS:
- Each MCQ = exactly 2 marks
- 4 options (A/B/C/D), exactly one correct answer
- Each option requires a calculation or multi-step reasoning — never a simple recall answer
- Distractors must be plausible common mistakes (wrong rate, missed condition, incorrect formula)
- Correct answer includes full step-by-step working
- Each distractor includes a brief explanation of why it is wrong
- Cite specific Article and Regulation in the correct answer
- At the end of each question, list: Syllabus codes tested: [e.g. CIT-2d, CIT-2e]

OUTPUT FORMAT — return a JSON object:
{{
  "type": "MCQ",
  "sac_thue": "{sac_thue}",
  "exam_session": "{exam_session}",
  "questions": [
    {{
      "number": 1,
      "marks": 2,
      "scenario": "On 1 January 2026, ABC Co...",
      "question": "What is the deductible expense for CIT purposes in the year ended 31 December 2025?",
      "syllabus_codes": ["CIT-2d", "CIT-2e"],
      "options": {{
        "A": {{"text": "VND X million", "is_key": false, "explanation": "Wrong because..."}},
        "B": {{"text": "VND Y million", "is_key": false, "explanation": "Wrong because..."}},
        "C": {{"text": "VND Z million", "is_key": true, "working": "Step 1: ... Step 2: ...", "explanation": "Correct per Article X, Decree Y"}},
        "D": {{"text": "VND W million", "is_key": false, "explanation": "Wrong because..."}}
      }},
      "regulation_refs": ["Article 9, Decree 320/2025/ND-CP"]
    }}
  ]
}}
"""
```

### Helper to build prompt injections (add to prompts.py):
```python
def build_syllabus_instruction(syllabus_codes: list) -> str:
    if not syllabus_codes:
        return ""
    codes_str = ", ".join(syllabus_codes)
    return f"SYLLABUS CODES TO TARGET: {codes_str}\nThe question(s) MUST test these specific syllabus items."

def build_difficulty_instruction(difficulty: str, topics: list = None) -> str:
    parts = []
    if difficulty == "hard":
        parts.append("DIFFICULTY: Hard — use complex fact patterns, multiple entities, or tricky edge cases.")
    else:
        parts.append("DIFFICULTY: Standard — typical ACCA exam difficulty.")
    if topics:
        parts.append(f"TOPIC FOCUS: {', '.join(topics)}")
    return "\n".join(parts)
```

Apply same pattern (`{syllabus_codes_instruction}`, `{difficulty_instruction}`) to SCENARIO_PROMPT and LONGFORM_PROMPT.

---

## Frontend Changes

### Sessions Page (new) — `/sessions`
Simple CRUD for exam sessions:
- Create session (name, exam date, assumed date)
- List sessions with file counts
- Set default session
- **Carry Forward button** — copy all files from a previous session

### Documents Page (replaces Regulations) — `/documents`
Per-session file management:
- Session selector at top (dropdown)
- 4 tabs: Regulations | Syllabus | Tax Rates | Sample Questions
- Under Regulations tab: sub-tabs for each tax type (CIT | VAT | PIT | FCT | TP | TaxAdmin)
- Upload button per tab — drag & drop .docx/.xlsx
- File list: name, size, active toggle, delete button
- **No parsing UI** — just upload and done

### Generate Page — update session selector
- Add session dropdown at top of generate page
- Replace "KB" / "syllabus codes from DB" UI with simple text input: "Syllabus codes (optional): CIT-2d, CIT-2n"
- Keep all other generate UI as-is

### Question Bank — add `syllabus_codes` column to list view
Show syllabus tags on each question card.

---

## Migration Steps

1. Run DB migration:
   - DROP old KB tables
   - CREATE `session_files` table
   - ADD `syllabus_codes TEXT[]` to `questions`
   - ADD `session_id` to `questions` (may already exist)
   - CREATE `exam_sessions` table with new simplified schema

2. Create default session in seed:
```python
def seed():
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO exam_sessions (name, exam_date, assumed_date, is_default)
            VALUES ('June 2026', 'Jun2026', '1 June 2026', TRUE)
            ON CONFLICT DO NOTHING
        """)
```

3. Move existing files in `/app/data/` to `/app/data/sessions/1/` structure
4. Register existing files in `session_files` table via seed script

---

## What NOT to change

- `ai_provider.py` — perfect as-is
- `document_extractor.py` — perfect as-is  
- `html_renderer.py` — perfect as-is
- `routes/questions.py` — keep as-is (question bank CRUD)
- `routes/export.py` — keep as-is
- `routes/auth.py` — keep as-is
- Frontend question bank display and export — keep as-is
- Docker/deployment config — keep as-is

---

## Summary of Changes

| Component | Action |
|---|---|
| `context_builder.py` | Replace entirely (simpler, file-based) |
| `models.py` | Simplify (remove all KB fields) |
| `prompts.py` | Update templates (add syllabus_codes_instruction) |
| `routes/generate.py` | Small update (session_id → build_context) |
| `routes/sessions.py` | Rewrite (session CRUD + file management) |
| `routes/regulations.py` | Keep as alias only |
| `routes/kb.py` | DELETE |
| `routes/sample_questions.py` | DELETE |
| `backend/utils/rule_parser.py` | DELETE |
| `backend/seed.py` | Rewrite (simple default session seed) |
| DB | Drop KB tables, add session_files |
| Frontend Sessions page | NEW |
| Frontend Documents page | Rename + simplify (no parse UI) |
| Frontend Generate page | Add session selector + syllabus text input |

---

## File to save this brief

Save as: `docs/BRIEF-refactor-v3.md` in the repo root.

Claude Code instruction: "Read `docs/BRIEF-refactor-v3.md` and implement the refactor exactly as described. Delete the brief file after implementation. Push to GitHub when done."
