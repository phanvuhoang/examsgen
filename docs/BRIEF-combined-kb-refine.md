# BRIEF: Knowledge Base + Conversational Refinement
## ExamsGen — Two New Features for Claude Code

**Repo:** phanvuhoang/examsgen  
**Files to create/modify:** see each section below

---

## Overview

Two features to add:

1. **Knowledge Base (KB)** — A structured mini-database of syllabus chunks, regulation paragraphs, and curated sample questions. When generating, user can pick specific KB items → AI receives focused context → more precise, harder questions.

2. **Conversational Refinement** — After a question is generated, a chat panel lets the user refine it iteratively in English or Vietnamese. AI remembers the conversation and returns updated question JSON each time.

Both features are additive — existing generate flow continues to work unchanged.

---

# PART 1: KNOWLEDGE BASE

## 1.1 Database Tables

Add to `backend/database.py` (in the `init_db()` function):

```sql
-- Syllabus items (one row per topic/item)
CREATE TABLE IF NOT EXISTS kb_syllabus (
    id SERIAL PRIMARY KEY,
    sac_thue VARCHAR(20) NOT NULL,
    section_code VARCHAR(50),
    section_title VARCHAR(500),
    content TEXT NOT NULL,
    tags VARCHAR(500),
    source_file VARCHAR(200),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Regulation paragraphs (one row per article/paragraph)
CREATE TABLE IF NOT EXISTS kb_regulation (
    id SERIAL PRIMARY KEY,
    sac_thue VARCHAR(20) NOT NULL,
    regulation_ref VARCHAR(200),
    content TEXT NOT NULL,
    tags VARCHAR(500),
    syllabus_ids INTEGER[] DEFAULT '{}',
    source_file VARCHAR(200),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Curated sample questions
CREATE TABLE IF NOT EXISTS kb_sample (
    id SERIAL PRIMARY KEY,
    question_type VARCHAR(20) NOT NULL,
    sac_thue VARCHAR(20) NOT NULL,
    title VARCHAR(300),
    content TEXT NOT NULL,
    exam_tricks TEXT,
    syllabus_ids INTEGER[] DEFAULT '{}',
    regulation_ids INTEGER[] DEFAULT '{}',
    source VARCHAR(100) DEFAULT 'manual',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);
```

## 1.2 Backend — KB Routes

Create `backend/routes/kb.py`:

```python
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
import json, logging
from backend.database import get_db
from backend.ai_provider import call_ai

router = APIRouter(prefix="/api/kb", tags=["kb"])
logger = logging.getLogger(__name__)

# --- Models ---

class SyllabusItem(BaseModel):
    sac_thue: str
    section_code: Optional[str] = None
    section_title: Optional[str] = None
    content: str
    tags: Optional[str] = None
    source_file: Optional[str] = None

class RegulationItem(BaseModel):
    sac_thue: str
    regulation_ref: Optional[str] = None
    content: str
    tags: Optional[str] = None
    syllabus_ids: Optional[List[int]] = []
    source_file: Optional[str] = None

class SampleItem(BaseModel):
    question_type: str
    sac_thue: str
    title: Optional[str] = None
    content: str
    exam_tricks: Optional[str] = None
    syllabus_ids: Optional[List[int]] = []
    regulation_ids: Optional[List[int]] = []
    source: str = "manual"

class ParseRequest(BaseModel):
    file_type: str        # "syllabus" | "regulation"
    sac_thue: str
    file_path: str        # relative to /app/data/

# --- Syllabus CRUD ---

@router.get("/syllabus")
def list_syllabus(sac_thue: Optional[str] = None, search: Optional[str] = None):
    with get_db() as conn:
        cur = conn.cursor()
        query = "SELECT id, sac_thue, section_code, section_title, content, tags, is_active, created_at FROM kb_syllabus WHERE 1=1"
        params = []
        if sac_thue:
            query += " AND sac_thue = %s"
            params.append(sac_thue)
        if search:
            query += " AND (section_title ILIKE %s OR tags ILIKE %s OR content ILIKE %s)"
            params += [f"%{search}%", f"%{search}%", f"%{search}%"]
        query += " ORDER BY sac_thue, section_code, id"
        cur.execute(query, params)
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in rows]

@router.post("/syllabus")
def create_syllabus(item: SyllabusItem):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO kb_syllabus (sac_thue, section_code, section_title, content, tags, source_file) VALUES (%s,%s,%s,%s,%s,%s) RETURNING id",
            (item.sac_thue, item.section_code, item.section_title, item.content, item.tags, item.source_file)
        )
        return {"id": cur.fetchone()[0]}

@router.put("/syllabus/{item_id}")
def update_syllabus(item_id: int, item: SyllabusItem):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "UPDATE kb_syllabus SET sac_thue=%s, section_code=%s, section_title=%s, content=%s, tags=%s WHERE id=%s",
            (item.sac_thue, item.section_code, item.section_title, item.content, item.tags, item_id)
        )

@router.delete("/syllabus/{item_id}")
def delete_syllabus(item_id: int):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM kb_syllabus WHERE id=%s", (item_id,))

# --- Regulation CRUD --- (same pattern as syllabus)

@router.get("/regulations")
def list_regulations(sac_thue: Optional[str] = None, search: Optional[str] = None):
    with get_db() as conn:
        cur = conn.cursor()
        query = "SELECT id, sac_thue, regulation_ref, content, tags, syllabus_ids, is_active, created_at FROM kb_regulation WHERE 1=1"
        params = []
        if sac_thue:
            query += " AND sac_thue = %s"; params.append(sac_thue)
        if search:
            query += " AND (regulation_ref ILIKE %s OR tags ILIKE %s OR content ILIKE %s)"
            params += [f"%{search}%", f"%{search}%", f"%{search}%"]
        query += " ORDER BY sac_thue, regulation_ref, id"
        cur.execute(query, params)
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in rows]

@router.post("/regulations")
def create_regulation(item: RegulationItem):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO kb_regulation (sac_thue, regulation_ref, content, tags, syllabus_ids, source_file) VALUES (%s,%s,%s,%s,%s,%s) RETURNING id",
            (item.sac_thue, item.regulation_ref, item.content, item.tags, item.syllabus_ids or [], item.source_file)
        )
        return {"id": cur.fetchone()[0]}

@router.put("/regulations/{item_id}")
def update_regulation(item_id: int, item: RegulationItem):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "UPDATE kb_regulation SET sac_thue=%s, regulation_ref=%s, content=%s, tags=%s, syllabus_ids=%s WHERE id=%s",
            (item.sac_thue, item.regulation_ref, item.content, item.tags, item.syllabus_ids or [], item_id)
        )

@router.delete("/regulations/{item_id}")
def delete_regulation(item_id: int):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM kb_regulation WHERE id=%s", (item_id,))

# --- Sample CRUD ---

@router.get("/samples")
def list_samples(sac_thue: Optional[str] = None, question_type: Optional[str] = None, search: Optional[str] = None):
    with get_db() as conn:
        cur = conn.cursor()
        query = "SELECT id, question_type, sac_thue, title, content, exam_tricks, syllabus_ids, regulation_ids, source, created_at FROM kb_sample WHERE 1=1"
        params = []
        if sac_thue:
            query += " AND sac_thue = %s"; params.append(sac_thue)
        if question_type:
            query += " AND question_type = %s"; params.append(question_type)
        if search:
            query += " AND (title ILIKE %s OR exam_tricks ILIKE %s OR content ILIKE %s)"
            params += [f"%{search}%", f"%{search}%", f"%{search}%"]
        query += " ORDER BY sac_thue, question_type, id"
        cur.execute(query, params)
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in rows]

@router.post("/samples")
def create_sample(item: SampleItem):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO kb_sample (question_type, sac_thue, title, content, exam_tricks, syllabus_ids, regulation_ids, source) VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
            (item.question_type, item.sac_thue, item.title, item.content, item.exam_tricks, item.syllabus_ids or [], item.regulation_ids or [], item.source)
        )
        return {"id": cur.fetchone()[0]}

@router.post("/samples/import-from-bank")
def import_from_bank(data: dict):
    """Import a question from the question bank into kb_sample."""
    question_id = data.get("question_id")
    title = data.get("title", "")
    exam_tricks = data.get("exam_tricks", "")
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT question_type, sac_thue, content_json FROM questions WHERE id=%s", (question_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, "Question not found")
        cur.execute(
            "INSERT INTO kb_sample (question_type, sac_thue, title, content, exam_tricks, source) VALUES (%s,%s,%s,%s,%s,%s) RETURNING id",
            (row[0], row[1], title, json.dumps(row[2]) if not isinstance(row[2], str) else row[2], exam_tricks, f"question_bank:{question_id}")
        )
        return {"id": cur.fetchone()[0]}

@router.put("/samples/{item_id}")
def update_sample(item_id: int, item: SampleItem):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "UPDATE kb_sample SET title=%s, exam_tricks=%s, syllabus_ids=%s, regulation_ids=%s WHERE id=%s",
            (item.title, item.exam_tricks, item.syllabus_ids or [], item.regulation_ids or [], item_id)
        )

@router.delete("/samples/{item_id}")
def delete_sample(item_id: int):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM kb_sample WHERE id=%s", (item_id,))

# --- Auto-parse file into chunks ---

@router.post("/parse-file")
def parse_file(req: ParseRequest):
    """Use AI to chunk a regulation or syllabus file into KB items."""
    import os
    from backend.context_builder import extract_text_from_file

    file_path = f"/app/data/{req.file_path}"
    if not os.path.exists(file_path):
        raise HTTPException(404, f"File not found: {req.file_path}")

    text = extract_text_from_file(file_path)
    if not text or len(text) < 100:
        raise HTTPException(400, "Could not extract text from file")

    # Truncate if too long (keep first 15000 chars for parsing)
    text_for_ai = text[:15000]

    prompt = f"""You are parsing a Vietnamese tax document for an exam question knowledge base.

Split this document into logical chunks. Each chunk should be:
- One coherent rule or topic (roughly one article, clause, or syllabus item)
- Self-contained enough to be exam context

For each chunk return:
- section_code: article/section number if present (e.g. "Article 9.2" or "Section B3")
- section_title: short title max 8 words
- content: full text of this chunk (keep original wording)
- tags: 3-8 comma-separated English keywords

Return ONLY valid JSON array, no markdown:
[
  {{
    "section_code": "Article 9",
    "section_title": "Deductible expenses general conditions",
    "content": "...",
    "tags": "deductible,expenses,conditions,genuine,invoice"
  }}
]

DOCUMENT TYPE: {req.file_type} | TAX TYPE: {req.sac_thue}

DOCUMENT:
{text_for_ai}"""

    result = call_ai(prompt, model_tier="fast")
    chunks = parse_ai_json_list(result["content"])

    # Save to appropriate table
    saved_ids = []
    with get_db() as conn:
        cur = conn.cursor()
        for chunk in chunks:
            if req.file_type == "syllabus":
                cur.execute(
                    "INSERT INTO kb_syllabus (sac_thue, section_code, section_title, content, tags, source_file) VALUES (%s,%s,%s,%s,%s,%s) RETURNING id",
                    (req.sac_thue, chunk.get("section_code"), chunk.get("section_title"), chunk.get("content",""), chunk.get("tags"), req.file_path)
                )
            else:
                cur.execute(
                    "INSERT INTO kb_regulation (sac_thue, regulation_ref, content, tags, source_file) VALUES (%s,%s,%s,%s,%s) RETURNING id",
                    (req.sac_thue, chunk.get("section_code"), chunk.get("content",""), chunk.get("tags"), req.file_path)
                )
            saved_ids.append(cur.fetchone()[0])

    return {"created": len(saved_ids), "ids": saved_ids, "chunks": chunks}
```

Note: Add `parse_ai_json_list` to `ai_provider.py` — same as `parse_ai_json` but expects a JSON array `[...]` instead of object `{...}`.

## 1.3 Register KB router

In `backend/main.py`, add:
```python
from backend.routes.kb import router as kb_router
app.include_router(kb_router)
```

## 1.4 Updated Generate Models

Add to ALL 3 request models in `backend/models.py`:
```python
kb_syllabus_ids: Optional[List[int]] = None
kb_regulation_ids: Optional[List[int]] = None
kb_sample_ids: Optional[List[int]] = None
```

## 1.5 Updated Context Builder

Add to `backend/context_builder.py`:
```python
def build_kb_context(kb_syllabus_ids=None, kb_regulation_ids=None, kb_sample_ids=None) -> str:
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
```

In `routes/generate.py`, in each handler after building context, add:
```python
from backend.context_builder import build_kb_context

kb_block = build_kb_context(
    kb_syllabus_ids=req.kb_syllabus_ids,
    kb_regulation_ids=req.kb_regulation_ids,
    kb_sample_ids=req.kb_sample_ids
)

# Inject into prompt — add {kb_context} placeholder to prompts.py
# kb_block goes BEFORE the general regulations context
```

In `backend/prompts.py`, add `{kb_context}` near the top of each prompt template, before `TAX RATES:`:
```
{kb_context}
```
When empty string, renders as nothing.

## 1.6 KB Manager Page (Frontend)

Create `frontend/src/pages/KnowledgeBase.jsx`.

**Layout:** 3 tabs at top: `Syllabus | Regulations | Sample Questions`

Each tab:
- Search bar (filter by sac_thue dropdown + text search)
- Table list of items (id, section_code/ref, title/tags, sac_thue, actions)
- [+ Add manually] button → inline form or modal:
  - Syllabus: sac_thue select, section_code input, section_title input, content textarea, tags input
  - Regulation: sac_thue, regulation_ref, content textarea, tags, [Link syllabus items] multi-select
  - Sample: type select, sac_thue, title, content textarea, exam_tricks input, link syllabus + regulation
- [Auto-parse file] button (Syllabus and Regulation tabs only):
  - Dropdown of available files in data/syllabus/ or data/regulations/
  - sac_thue select
  - [Parse] → loading → shows created chunks → [Done]
- Each row: [Edit] [Delete] buttons, tags shown as small badges

**Sample Questions tab extra:**
- [Import from Question Bank] button → modal showing last 50 questions, pick one, enter title + exam_tricks → save

Add KB to navigation (between Generate and Question Bank):
```jsx
<NavLink to="/kb">Knowledge Base</NavLink>
```

## 1.7 KB Targeting in Generate.jsx

In the Custom Instructions section (already exists), add a new sub-section **after** the existing fields:

```jsx
{/* KB Targeting */}
<div className="border-t pt-4 mt-2">
  <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">
    Knowledge Base Targeting
  </p>

  {/* Syllabus items */}
  <KBMultiSelect
    label="Syllabus items to test"
    endpoint={`/api/kb/syllabus?sac_thue=${sac_thue}`}
    value={kbSyllabusIds}
    onChange={setKbSyllabusIds}
    displayKey="section_title"
    hintKey="tags"
  />

  {/* Regulation paragraphs */}
  <KBMultiSelect
    label="Regulation paragraphs"
    endpoint={`/api/kb/regulations?sac_thue=${sac_thue}`}
    value={kbRegulationIds}
    onChange={setKbRegulationIds}
    displayKey="regulation_ref"
    hintKey="tags"
  />

  {/* Style references */}
  <KBMultiSelect
    label="Style references (sample questions)"
    endpoint={`/api/kb/samples?sac_thue=${sac_thue}&question_type=${type}`}
    value={kbSampleIds}
    onChange={setKbSampleIds}
    displayKey="title"
    hintKey="exam_tricks"
  />
</div>
```

Create a reusable `KBMultiSelect` component:
- Fetches items from endpoint on mount
- Search input to filter
- Shows selected items as removable tags
- Dropdown to add more
- Passes selected id array via onChange

Add state:
```javascript
const [kbSyllabusIds, setKbSyllabusIds] = useState([])
const [kbRegulationIds, setKbRegulationIds] = useState([])
const [kbSampleIds, setKbSampleIds] = useState([])
```

Pass to all 3 generate API calls:
```javascript
kb_syllabus_ids: kbSyllabusIds.length ? kbSyllabusIds : null,
kb_regulation_ids: kbRegulationIds.length ? kbRegulationIds : null,
kb_sample_ids: kbSampleIds.length ? kbSampleIds : null,
```

---

# PART 2: CONVERSATIONAL REFINEMENT

## 2.1 New Backend Endpoint

Add to `backend/routes/generate.py`:

```python
class RefineRequest(BaseModel):
    current_content: dict
    conversation_history: List[dict]    # [{role: "user"|"assistant", content: str}]
    user_message: str
    model_tier: str = "fast"
    sac_thue: str
    question_type: str

@router.post("/refine")
def refine_question(req: RefineRequest):
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

    # Add history (skip first assistant greeting if present)
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
        "provider_used": result["provider"]
    }
```

Note: `call_ai` needs to accept `messages` list directly (not just a prompt string). Check if it already supports this; if not, add an overload:
```python
def call_ai(prompt: str = None, messages: list = None, model_tier: str = "fast", system_prompt: str = None):
    if messages is None:
        messages = [{"role": "user", "content": prompt}]
    if system_prompt:
        messages = [{"role": "system", "content": system_prompt}] + messages
    # ... rest of existing logic
```

## 2.2 api.js Addition

```javascript
refineQuestion: async (data) => {
  const res = await fetch('/api/generate/refine', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify(data)
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
},

getKBSyllabus: async (params = {}) => {
  const q = new URLSearchParams(params)
  const res = await fetch(`/api/kb/syllabus?${q}`, { headers: authHeaders() })
  return res.ok ? res.json() : []
},

getKBRegulations: async (params = {}) => {
  const q = new URLSearchParams(params)
  const res = await fetch(`/api/kb/regulations?${q}`, { headers: authHeaders() })
  return res.ok ? res.json() : []
},

getKBSamples: async (params = {}) => {
  const q = new URLSearchParams(params)
  const res = await fetch(`/api/kb/samples?${q}`, { headers: authHeaders() })
  return res.ok ? res.json() : []
},
```

## 2.3 Generate.jsx — Refine Chat UI

Add state:
```javascript
const [chatHistory, setChatHistory] = useState([])
const [chatInput, setChatInput] = useState('')
const [chatLoading, setChatLoading] = useState(false)
const [currentContent, setCurrentContent] = useState(null)
```

When question is generated successfully, add to the existing success handler:
```javascript
setCurrentContent(result.content_json)
setChatHistory([{
  role: 'assistant',
  content: 'Question ready! Ask me to adjust anything — in English or Vietnamese.'
}])
```

When user clicks Regenerate, reset:
```javascript
setChatHistory([])
setCurrentContent(null)
```

Refine handler:
```javascript
const handleRefine = async () => {
  if (!chatInput.trim() || chatLoading) return
  const userMsg = { role: 'user', content: chatInput }
  setChatHistory(prev => [...prev, userMsg])
  setChatInput('')
  setChatLoading(true)
  try {
    const data = await api.refineQuestion({
      current_content: currentContent,
      conversation_history: chatHistory,
      user_message: chatInput,
      model_tier: modelTier,
      sac_thue,
      question_type: type === 'mcq' ? 'MCQ' : type === 'scenario' ? 'SCENARIO_10' : 'LONGFORM_15'
    })
    setResult(prev => ({ ...prev, content_json: data.content, content_html: data.content_html }))
    setCurrentContent(data.content)
    setChatHistory(prev => [...prev, { role: 'assistant', content: data.assistant_message }])
  } catch (err) {
    setChatHistory(prev => [...prev, { role: 'assistant', content: '❌ Refinement failed. Please try again.' }])
  } finally {
    setChatLoading(false)
  }
}
```

Chat UI — add below question result preview (visible only when `result` is not null):
```jsx
{result && (
  <div className="mt-6 border rounded-xl overflow-hidden shadow-sm">
    <div className="bg-gray-50 px-4 py-2 border-b flex items-center gap-2">
      <span className="text-sm font-semibold text-gray-700">✏️ Refine this question</span>
      <span className="text-xs text-gray-400">English or Vietnamese</span>
    </div>

    <div className="p-4 space-y-3 max-h-72 overflow-y-auto" id="chat-scroll">
      {chatHistory.map((msg, i) => (
        <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
          <div className={`max-w-[85%] px-3 py-2 rounded-lg text-sm leading-relaxed ${
            msg.role === 'user'
              ? 'bg-[#028a39] text-white'
              : 'bg-gray-100 text-gray-700'
          }`}>
            {msg.content}
          </div>
        </div>
      ))}
      {chatLoading && (
        <div className="flex justify-start">
          <div className="bg-gray-100 text-gray-500 px-3 py-2 rounded-lg text-sm animate-pulse">
            Updating question...
          </div>
        </div>
      )}
    </div>

    <div className="border-t p-3 flex gap-2">
      <input
        value={chatInput}
        onChange={e => setChatInput(e.target.value)}
        onKeyDown={e => e.key === 'Enter' && !e.shiftKey && handleRefine()}
        placeholder="E.g: Make harder, add loss carry-forward... hoặc: Thêm vấn đề chuyển giá"
        className="flex-1 border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#028a39]"
        disabled={chatLoading}
      />
      <button
        onClick={handleRefine}
        disabled={chatLoading || !chatInput.trim()}
        className="px-4 py-2 bg-[#028a39] text-white rounded-lg text-sm font-medium hover:bg-[#027a32] disabled:opacity-40 transition-colors"
      >
        Send
      </button>
    </div>
  </div>
)}
```

Auto-scroll chat to bottom when new messages arrive:
```javascript
useEffect(() => {
  const el = document.getElementById('chat-scroll')
  if (el) el.scrollTop = el.scrollHeight
}, [chatHistory, chatLoading])
```

---

# SUMMARY — Files to Create/Modify

| Action | File |
|--------|------|
| CREATE | `backend/routes/kb.py` |
| MODIFY | `backend/database.py` — add 3 new CREATE TABLE statements in init_db() |
| MODIFY | `backend/main.py` — register kb_router |
| MODIFY | `backend/models.py` — add kb_* fields to all 3 request models + new RefineRequest |
| MODIFY | `backend/context_builder.py` — add build_kb_context() |
| MODIFY | `backend/prompts.py` — add {kb_context} placeholder to MCQ_PROMPT, SCENARIO_PROMPT, LONGFORM_PROMPT |
| MODIFY | `backend/routes/generate.py` — add /refine endpoint + wire kb_context into existing handlers |
| MODIFY | `backend/ai_provider.py` — ensure call_ai() accepts messages list directly |
| CREATE | `frontend/src/pages/KnowledgeBase.jsx` |
| CREATE | `frontend/src/components/KBMultiSelect.jsx` |
| MODIFY | `frontend/src/pages/Generate.jsx` — add KB targeting UI + refine chat |
| MODIFY | `frontend/src/api.js` — add refineQuestion + getKB* methods |
| MODIFY | `frontend/src/App.jsx` (or router file) — add /kb route |
| MODIFY | Navigation component — add Knowledge Base nav link |

---

# IMPORTANT NOTES FOR CLAUDE CODE

1. **Test after each major section** — run backend first to verify DB tables created, then test API, then frontend
2. **KB features are purely additive** — if kb_syllabus_ids/kb_regulation_ids/kb_sample_ids are null/empty, generate works exactly as before
3. **parse_ai_json_list**: same logic as parse_ai_json but looks for `[` instead of `{` as JSON start
4. **KBMultiSelect**: build as a simple reusable component — fetch on mount, show selected as tags with ×, search to filter dropdown
5. **Auto-scroll chat**: always scroll to bottom after new message
6. **Save button after refinement**: save `currentContent` state (latest version), not original `result`
7. **Brand color**: `#028a39` for all primary buttons and highlights
8. **call_ai() messages param**: if current implementation only takes `prompt: str`, add an overload that takes `messages: List[dict]` — the refine endpoint needs to pass full conversation history
