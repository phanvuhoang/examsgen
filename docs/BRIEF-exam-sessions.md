# BRIEF: Exam Sessions Architecture Refactor
## ExamsGen — Exam Session Management + KB Restructure

**Repo:** phanvuhoang/examsgen

---

## Overview

Restructure the app around **Exam Sessions**. Each exam session (e.g. "June 2026", "December 2026") is an independent container with its own:
- Syllabus (chunked into KB items)
- Regulations (with a cutoff date — only regulations effective up to a specific date)
- Past Questions / Style References
- Settings: period test cutoff, tax year, exam window dates

Knowledge Base and Regulations pages become **session-scoped** (not global). The global Regulations page (upload management) remains but is used as a source to assign to sessions.

---

## 1. Database Changes

### New table: `exam_sessions`

```sql
CREATE TABLE IF NOT EXISTS exam_sessions (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,       -- "June 2026", "December 2026"
    exam_window_start DATE,                   -- e.g. 2026-06-01
    exam_window_end DATE,                     -- e.g. 2026-06-30
    regulations_cutoff DATE NOT NULL,         -- regulations effective up to this date
    fiscal_year_end DATE,                     -- fiscal period ceiling for exam scenarios
    tax_year INTEGER,                         -- e.g. 2025
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    is_default BOOLEAN DEFAULT FALSE,         -- the currently selected session
    created_at TIMESTAMP DEFAULT NOW()
);

-- Seed default session
INSERT INTO exam_sessions (name, exam_window_start, exam_window_end, regulations_cutoff, fiscal_year_end, tax_year, is_default)
VALUES ('June 2026', '2026-06-01', '2026-06-30', '2025-12-31', '2025-12-31', 2025, TRUE)
ON CONFLICT (name) DO NOTHING;
```

### Modify existing KB tables — add `session_id`

```sql
ALTER TABLE kb_syllabus ADD COLUMN IF NOT EXISTS session_id INTEGER REFERENCES exam_sessions(id);
ALTER TABLE kb_regulation ADD COLUMN IF NOT EXISTS session_id INTEGER REFERENCES exam_sessions(id);
ALTER TABLE kb_sample ADD COLUMN IF NOT EXISTS session_id INTEGER REFERENCES exam_sessions(id);
```

For existing rows without session_id, assign to the default session:
```sql
UPDATE kb_syllabus SET session_id = (SELECT id FROM exam_sessions WHERE is_default = TRUE) WHERE session_id IS NULL;
UPDATE kb_regulation SET session_id = (SELECT id FROM exam_sessions WHERE is_default = TRUE) WHERE session_id IS NULL;
UPDATE kb_sample SET session_id = (SELECT id FROM exam_sessions WHERE is_default = TRUE) WHERE session_id IS NULL;
```

### Modify `questions` table — add `session_id`

```sql
ALTER TABLE questions ADD COLUMN IF NOT EXISTS session_id INTEGER REFERENCES exam_sessions(id);
UPDATE questions SET session_id = (SELECT id FROM exam_sessions WHERE is_default = TRUE) WHERE session_id IS NULL;
```

---

## 2. Backend — Exam Sessions Routes

Create `backend/routes/sessions.py`:

```python
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from datetime import date
from backend.database import get_db
from backend.ai_provider import call_ai, parse_ai_json_list
from backend.context_builder import extract_text_from_file
import json, os

router = APIRouter(prefix="/api/sessions", tags=["sessions"])

class SessionCreate(BaseModel):
    name: str
    exam_window_start: Optional[date] = None
    exam_window_end: Optional[date] = None
    regulations_cutoff: date
    fiscal_year_end: date
    tax_year: int
    description: Optional[str] = None

class SessionUpdate(BaseModel):
    name: Optional[str] = None
    exam_window_start: Optional[date] = None
    exam_window_end: Optional[date] = None
    regulations_cutoff: Optional[date] = None
    fiscal_year_end: Optional[date] = None
    tax_year: Optional[int] = None
    description: Optional[str] = None

@router.get("/")
def list_sessions():
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT s.id, s.name, s.exam_window_start, s.exam_window_end,
                   s.regulations_cutoff, s.fiscal_year_end, s.tax_year,
                   s.description, s.is_active, s.is_default, s.created_at,
                   (SELECT COUNT(*) FROM kb_syllabus WHERE session_id = s.id) as syllabus_count,
                   (SELECT COUNT(*) FROM kb_regulation WHERE session_id = s.id) as regulation_count,
                   (SELECT COUNT(*) FROM kb_sample WHERE session_id = s.id) as sample_count,
                   (SELECT COUNT(*) FROM questions WHERE session_id = s.id) as question_count
            FROM exam_sessions s ORDER BY s.exam_window_start DESC
        """)
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in rows]

@router.post("/")
def create_session(session: SessionCreate):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO exam_sessions (name, exam_window_start, exam_window_end,
                regulations_cutoff, fiscal_year_end, tax_year, description)
            VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id
        """, (session.name, session.exam_window_start, session.exam_window_end,
              session.regulations_cutoff, session.fiscal_year_end,
              session.tax_year, session.description))
        return {"id": cur.fetchone()[0]}

@router.put("/{session_id}")
def update_session(session_id: int, session: SessionUpdate):
    with get_db() as conn:
        cur = conn.cursor()
        updates = {k: v for k, v in session.dict().items() if v is not None}
        if not updates:
            return {"ok": True}
        set_clause = ", ".join(f"{k} = %s" for k in updates)
        cur.execute(f"UPDATE exam_sessions SET {set_clause} WHERE id = %s",
                    list(updates.values()) + [session_id])

@router.post("/{session_id}/set-default")
def set_default_session(session_id: int):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("UPDATE exam_sessions SET is_default = FALSE")
        cur.execute("UPDATE exam_sessions SET is_default = TRUE WHERE id = %s", (session_id,))

@router.post("/{session_id}/clone-from/{source_id}")
def clone_session(session_id: int, source_id: int):
    """Copy all KB items from source session into target session."""
    with get_db() as conn:
        cur = conn.cursor()
        for table in ['kb_syllabus', 'kb_regulation', 'kb_sample']:
            if table == 'kb_syllabus':
                cur.execute(f"""
                    INSERT INTO {table} (sac_thue, section_code, section_title, content, tags, source_file, is_active, session_id)
                    SELECT sac_thue, section_code, section_title, content, tags, source_file, is_active, %s
                    FROM {table} WHERE session_id = %s
                """, (session_id, source_id))
            elif table == 'kb_regulation':
                cur.execute(f"""
                    INSERT INTO {table} (sac_thue, regulation_ref, content, tags, syllabus_ids, source_file, is_active, session_id)
                    SELECT sac_thue, regulation_ref, content, tags, '{{}}', source_file, is_active, %s
                    FROM {table} WHERE session_id = %s
                """, (session_id, source_id))
            else:
                cur.execute(f"""
                    INSERT INTO {table} (question_type, sac_thue, title, content, exam_tricks, syllabus_ids, regulation_ids, source, session_id)
                    SELECT question_type, sac_thue, title, content, exam_tricks, '{{}}', '{{}}', source, %s
                    FROM {table} WHERE session_id = %s
                """, (session_id, source_id))
        return {"ok": True, "message": f"KB cloned from session {source_id}"}

@router.post("/{session_id}/parse-and-match")
def parse_and_match(session_id: int, data: dict):
    """
    AI-powered: parse a regulation/syllabus file into chunks,
    then auto-match chunks to existing syllabus items (or each other).
    
    data = {
        "file_path": "regulations/CIT/CIT_Law_67_2025_ENG.doc",
        "file_type": "regulation",  // "regulation" | "syllabus"
        "sac_thue": "CIT"
    }
    """
    file_path = f"/app/data/{data['file_path']}"
    if not os.path.exists(file_path):
        raise HTTPException(404, f"File not found: {data['file_path']}")

    from backend.context_builder import extract_text_from_file
    text = extract_text_from_file(file_path)
    text_for_ai = text[:15000]
    file_type = data.get("file_type", "regulation")
    sac_thue = data.get("sac_thue", "CIT")

    # Step 1: Chunk the file
    chunk_prompt = f"""Parse this Vietnamese tax {file_type} document into logical chunks for an exam question database.

Each chunk = one coherent rule or topic (one article, clause, or syllabus item).

For each chunk return:
- section_code: article/section number if present
- section_title: short title max 8 words  
- content: full text of this chunk (preserve original wording)
- tags: 3-8 comma-separated English keywords

Return ONLY valid JSON array, no markdown, no extra text:
[{{"section_code":"...","section_title":"...","content":"...","tags":"..."}}]

DOCUMENT TYPE: {file_type} | TAX TYPE: {sac_thue}

DOCUMENT:
{text_for_ai}"""

    chunk_result = call_ai(chunk_prompt, model_tier="fast")
    chunks = parse_ai_json_list(chunk_result["content"])

    # Step 2: If regulation, try to match to existing syllabus items for this session
    syllabus_items = []
    if file_type == "regulation":
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("SELECT id, section_code, section_title, tags FROM kb_syllabus WHERE session_id = %s AND sac_thue = %s", (session_id, sac_thue))
            syllabus_items = [{"id": r[0], "section_code": r[1], "section_title": r[2], "tags": r[3]} for r in cur.fetchall()]

    if syllabus_items and len(chunks) <= 30:
        match_prompt = f"""Given these regulation chunks and syllabus items, suggest which syllabus item(s) each regulation chunk maps to.

SYLLABUS ITEMS:
{json.dumps(syllabus_items, ensure_ascii=False)}

REGULATION CHUNKS (indexed 0-based):
{json.dumps([{"index": i, "section_code": c.get("section_code"), "section_title": c.get("section_title"), "tags": c.get("tags")} for i, c in enumerate(chunks)], ensure_ascii=False)}

Return ONLY valid JSON array mapping chunk index to syllabus ids:
[{{"chunk_index": 0, "syllabus_ids": [1, 3]}}, ...]

If no match, use empty array for syllabus_ids. Cover all {len(chunks)} chunks."""

        match_result = call_ai(match_prompt, model_tier="fast")
        try:
            matches = parse_ai_json_list(match_result["content"])
            match_map = {m["chunk_index"]: m.get("syllabus_ids", []) for m in matches}
        except:
            match_map = {}
    else:
        match_map = {}

    # Attach suggested syllabus_ids to each chunk
    for i, chunk in enumerate(chunks):
        chunk["suggested_syllabus_ids"] = match_map.get(i, [])
        chunk["index"] = i

    return {
        "chunks": chunks,
        "total": len(chunks),
        "file_type": file_type,
        "sac_thue": sac_thue,
        "session_id": session_id,
        "has_syllabus_matches": bool(match_map)
    }

@router.post("/{session_id}/save-parsed-chunks")
def save_parsed_chunks(session_id: int, data: dict):
    """
    Save approved chunks from parse-and-match into KB tables.
    data = {
        "chunks": [...],   // from parse-and-match, user may have edited
        "file_type": "regulation" | "syllabus",
        "sac_thue": "CIT",
        "source_file": "regulations/CIT/..."
    }
    """
    chunks = data.get("chunks", [])
    file_type = data.get("file_type")
    sac_thue = data.get("sac_thue")
    source_file = data.get("source_file", "")
    saved = []

    with get_db() as conn:
        cur = conn.cursor()
        for chunk in chunks:
            if not chunk.get("content", "").strip():
                continue
            if file_type == "syllabus":
                cur.execute("""
                    INSERT INTO kb_syllabus (sac_thue, section_code, section_title, content, tags, source_file, session_id)
                    VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id
                """, (sac_thue, chunk.get("section_code"), chunk.get("section_title"),
                      chunk["content"], chunk.get("tags"), source_file, session_id))
            else:
                cur.execute("""
                    INSERT INTO kb_regulation (sac_thue, regulation_ref, content, tags, syllabus_ids, source_file, session_id)
                    VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id
                """, (sac_thue, chunk.get("section_code"), chunk["content"],
                      chunk.get("tags"), chunk.get("suggested_syllabus_ids", []),
                      source_file, session_id))
            saved.append(cur.fetchone()[0])

    return {"saved": len(saved), "ids": saved}
```

Register in `main.py`:
```python
from backend.routes.sessions import router as sessions_router
app.include_router(sessions_router)
```

---

## 3. Updated Generate — Session-Aware

### models.py

Add `session_id` to all 3 request models:
```python
session_id: Optional[int] = None   # if None, use default session
```

### routes/generate.py

At the top of each handler, resolve session:
```python
def get_session(session_id: int = None) -> dict:
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
```

Inject session context into prompt:
```python
session = get_session(req.session_id)
session_context = ""
if session:
    session_context = f"""EXAM SESSION: {session['name']}
REGULATIONS CUTOFF: Only use regulations effective up to {session['regulations_cutoff']}. Ignore any regulations enacted after this date.
FISCAL PERIOD: All scenarios must use fiscal year ending {session['fiscal_year_end']}. Do not use dates beyond {session['fiscal_year_end']} in scenarios.
TAX YEAR: {session['tax_year']}"""
```

Add `{session_context}` placeholder to all prompt templates (just after the first line).

Also filter KB queries by session_id when building context:
```python
kb_block = build_kb_context(
    kb_syllabus_ids=req.kb_syllabus_ids,
    kb_regulation_ids=req.kb_regulation_ids,
    kb_sample_ids=req.kb_sample_ids,
    session_id=session.get("id")   # passed but currently not filtering — already scoped by user selection
)
```

Save generated question with session_id:
```python
cur.execute("INSERT INTO questions (..., session_id) VALUES (..., %s)", (..., session.get("id")))
```

---

## 4. Frontend Changes

### 4.1 Global Session Selector

Add a **session selector** in the top navbar (visible on all pages):

```jsx
// SessionSelector component
const [sessions, setSessions] = useState([])
const [currentSessionId, setCurrentSessionId] = useLocalStorage('currentSessionId', null)

// Show as dropdown in navbar:
<select value={currentSessionId} onChange={e => setCurrentSessionId(e.target.value)}
  className="text-sm border rounded px-2 py-1">
  {sessions.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
</select>
```

Store selected session in `localStorage` so it persists. Pass `session_id` to all generate API calls.

### 4.2 New Page: Exam Sessions (`/sessions`)

Add nav link "Sessions" (first item in nav, or accessible from Settings).

**Layout:** Card grid of sessions, each card shows:
- Session name (e.g. "June 2026")
- Exam window dates
- Regulations cutoff date
- Fiscal year end
- Stats: X syllabus items, Y regulation chunks, Z samples, W questions
- [Set as Active] button (makes it default)
- [Edit] button

**Top of page:**
- [+ New Session] button → modal form:
  - Name (e.g. "December 2026")
  - Exam window: start date, end date
  - Regulations cutoff date (e.g. 31/12/2025)
  - Fiscal year end (e.g. 31/12/2025)
  - Tax year (e.g. 2025)
  - [Carry forward KB from...] dropdown → select existing session → copies all KB items

**Edit session modal:** same fields, plus [Carry Forward KB] button

### 4.3 Knowledge Base Page — Session-Scoped

The existing KB page (`/kb`) should:

1. Show current session name at the top: `📚 Knowledge Base — June 2026 ▼` (clicking ▼ switches session)

2. All API calls pass `session_id` as query param:
   ```
   GET /api/kb/syllabus?session_id=1&sac_thue=CIT
   ```

3. Add **[Parse & Match File]** button in Syllabus and Regulations tabs:
   - Shows a file picker (dropdown of available files in data/regulations/ or data/syllabus/)
   - Select file type (regulation/syllabus) and sac_thue
   - [Parse with AI] → calls `/api/sessions/{id}/parse-and-match`
   - Shows results in a **Review Panel**:

#### Review Panel (after parse-and-match)

```
📋 Parse Results: CIT Law 67/2025 → 34 chunks found

[✓ Select All] [✗ Deselect All] [Save Selected to KB]

┌──────────────────────────────────────────────────────┐
│ ☑ Article 1 — Scope of CIT                          │
│   Tags: scope, taxpayer, enterprise                  │
│   Matched syllabus: [A1 - Introduction to CIT]  ×   │
│   [Edit] [Preview ▼]                                 │
├──────────────────────────────────────────────────────┤
│ ☑ Article 9.2c — Salary expenses deductibility       │
│   Tags: deductible, salary, labor contract           │
│   Matched syllabus: [B3 - Salary expenses] ×         │
│                     [+ Link more syllabus items]     │
│   [Edit] [Preview ▼]                                 │
├──────────────────────────────────────────────────────┤
│ ☑ Article 9.2d — Interest expense cap                │
│   Tags: interest, cap, 30%, EBITDA, equity           │
│   Matched syllabus: [B4 - Financial expenses] ×      │
│   [Edit] [Preview ▼]                                 │
└──────────────────────────────────────────────────────┘

[Save 34 Selected Chunks to Knowledge Base]
```

Each chunk row:
- Checkbox (select/deselect for saving)
- section_code + section_title (editable inline)
- Tags (editable inline as comma-separated)  
- Suggested syllabus matches (shown as removable tags, can add more)
- [Preview] toggle to see full content

### 4.4 Generate Page — Session Context Display

Show current session info near the top of the Generate form:

```jsx
{currentSession && (
  <div className="text-xs text-gray-500 bg-gray-50 rounded px-3 py-2 mb-4 flex gap-4">
    <span>📅 Session: <strong>{currentSession.name}</strong></span>
    <span>📋 Reg cutoff: <strong>{currentSession.regulations_cutoff}</strong></span>
    <span>🗓 Fiscal year: <strong>{currentSession.fiscal_year_end}</strong></span>
  </div>
)}
```

The session_id is automatically passed to all generate calls — user doesn't need to select it again (they selected it in the global navbar selector).

---

## 5. Updated KB API — session_id filter

Update all KB list endpoints to accept `session_id` query param:

```python
@router.get("/syllabus")
def list_syllabus(session_id: Optional[int] = None, sac_thue: Optional[str] = None, search: Optional[str] = None):
    with get_db() as conn:
        cur = conn.cursor()
        query = "SELECT ... FROM kb_syllabus WHERE 1=1"
        params = []
        if session_id:
            query += " AND session_id = %s"; params.append(session_id)
        if sac_thue:
            query += " AND sac_thue = %s"; params.append(sac_thue)
        ...
```

Same for `/regulations` and `/samples` endpoints.

Also update POST endpoints to accept `session_id`:
```python
class SyllabusItem(BaseModel):
    ...
    session_id: Optional[int] = None   # if None, use default session
```

---

## 6. Navigation Updates

Update the nav (App.jsx or navbar component):

```
Sessions | Generate | Knowledge Base | Question Bank | Regulations | Settings
```

Add routes:
```jsx
<Route path="/sessions" element={<Sessions />} />
```

---

## 7. Seed December 2026 Session + Parse Existing Files

After implementing, the app should run this on first startup (or manually trigger):

### Auto-seed Dec 2026 session

In `database.py` init_db():
```sql
INSERT INTO exam_sessions (name, exam_window_start, exam_window_end, regulations_cutoff, fiscal_year_end, tax_year, is_default)
VALUES ('December 2026', '2026-12-01', '2026-12-31', '2025-12-31', '2025-12-31', 2025, FALSE)
ON CONFLICT (name) DO NOTHING;
```

### Trigger parse for December 2026

After the December 2026 session is created, the UI should offer:
*"This session has no KB items yet. Would you like to carry forward from June 2026, or parse regulation files?"*

Show two buttons:
- [Carry Forward from June 2026] → calls `/api/sessions/{dec_id}/clone-from/{jun_id}`
- [Parse Files] → opens the Parse & Match interface

---

## 8. Summary — Files to Create/Modify

| Action | File |
|--------|------|
| CREATE | `backend/routes/sessions.py` |
| MODIFY | `backend/database.py` — add exam_sessions table, alter kb_* + questions tables |
| MODIFY | `backend/main.py` — register sessions_router |
| MODIFY | `backend/models.py` — add session_id to all request models |
| MODIFY | `backend/prompts.py` — add {session_context} placeholder to all prompts |
| MODIFY | `backend/routes/generate.py` — inject session context, save session_id |
| MODIFY | `backend/routes/kb.py` — add session_id filter to all endpoints |
| CREATE | `frontend/src/pages/Sessions.jsx` |
| MODIFY | `frontend/src/pages/KnowledgeBase.jsx` — session scoping + Parse & Match UI |
| MODIFY | `frontend/src/pages/Generate.jsx` — show session info bar |
| MODIFY | `frontend/src/App.jsx` — add /sessions route |
| MODIFY | `frontend/src/components/Navbar.jsx` (or equivalent) — add global session selector |
| MODIFY | `frontend/src/api.js` — add sessions API calls |

---

## Important Notes for Claude Code

1. **Backward compatibility:** Existing questions/KB items must still work — assign to June 2026 session (default) if session_id is NULL
2. **Session selector in navbar** stores selection in `localStorage` — persists across page reloads
3. **Parse & Match Review Panel** is the most complex UI — build it as a separate component `ParseReviewPanel.jsx`
4. **Clone session** copies KB items but does NOT copy generated questions
5. **Regulations cutoff in prompt:** This is the most important session setting for exam quality — make sure it's prominently injected into every generate prompt
6. **fiscal_year_end in prompt:** AI must not create scenarios with dates beyond this — e.g. "fiscal year ended 31 December 2025" not "31 December 2026"
7. **After saving, offer to parse more files** — the workflow is iterative: parse one file → review → save → parse next file
