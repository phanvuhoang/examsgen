# ExamsGen — UI Brief v3.4
**Date:** March 2026
**Scope:** 6 feature requests — calculations display, syllabus codes, sample parsing, hover previews, session variables

---

## Change 1: Show calculation steps in explanations

**Location:** `backend/prompts.py` — MCQ_PROMPT, SCENARIO_PROMPT, LONGFORM_PROMPT

**Problem:** When questions involve calculations, the explanation doesn't always show step-by-step workings clearly.

**Fix — update REQUIREMENTS section in all 3 prompts:**

```
- For any question involving calculations, the correct answer MUST include explicit step-by-step workings:
  Step 1: [describe what you are calculating] → VND X million
  Step 2: [next step] → VND Y million
  Final answer: VND Z million
- Each calculation step must show the formula, the numbers substituted, and the result
- Wrong answer explanations must also show the calculation the student mistakenly performed and why it gives the wrong result
- Never just state the final number — always show how it was derived
```

In the JSON output format, update the `working` field description:

```
"working": "Step 1: Identify deductible salary cap → 3 × VND 4.96m × 850 = VND 12,648m\nStep 2: Voluntary pension within limit → min(VND 2,052m, 3m × 12 × 850) = VND 2,052m\nStep 3: Life insurance overseas insurer → non-deductible (VND 945m add-back)\nTotal deductible = VND 68,400m + VND 12,312m + VND 2,052m + VND 1,368m = VND 84,132m"
```

---

## Change 2: Fix Syllabus Code format — use Code column from xlsx

**Location:** `backend/context_builder.py` + `backend/prompts.py`

**Problem:** Syllabus xlsx files have a "Code" column (e.g. `C2d`, `C2n`) but the prompts currently use verbose descriptions. Claude is tagging with formats like `CIT-2d` instead of the actual code from the file.

**Fix 1 — Extract syllabus codes from xlsx properly in `context_builder.py`:**

When loading syllabus files, also extract just the Code column values as a structured list and include it separately in context:

```python
import openpyxl

def _extract_syllabus_codes(file_path: str) -> list[str]:
    """Extract Code column values from syllabus xlsx. Returns list like ['C2a', 'C2b', 'C2d']"""
    try:
        if not os.path.isabs(file_path):
            file_path = os.path.join(DATA_DIR, file_path)
        wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
        ws = wb.active
        codes = []
        header_row = None
        code_col = None
        for i, row in enumerate(ws.iter_rows(values_only=True)):
            if header_row is None:
                # Find Code column index
                for j, cell in enumerate(row):
                    if cell and str(cell).strip().lower() in ('code', 'syllabus code', 'syllabus_code'):
                        code_col = j
                        header_row = i
                        break
                continue
            if code_col is not None and row[code_col]:
                val = str(row[code_col]).strip()
                if val:
                    codes.append(val)
        wb.close()
        return codes
    except Exception as e:
        logger.warning(f"Failed to extract syllabus codes from {file_path}: {e}")
        return []
```

Return syllabus_codes list in context dict:

```python
# In build_context(), after loading syllabus:
all_syllabus_codes = []
for f in syllabus_files:
    all_syllabus_codes.extend(_extract_syllabus_codes(f["path"]))

return {
    "tax_rates": tax_rates,
    "syllabus": syllabus,
    "regulations": regulations,
    "sample": sample,
    "syllabus_codes_list": all_syllabus_codes,   # NEW: list of actual code strings
}
```

**Fix 2 — Inject codes into prompt in `routes/generate.py`:**

```python
ctx = build_context(session_id, req.sac_thue, "MCQ")

# Build syllabus codes hint from actual file codes
codes_from_file = ctx.get("syllabus_codes_list", [])
if codes_from_file:
    codes_hint = f"AVAILABLE SYLLABUS CODES (use EXACTLY these codes, e.g. C2d not CIT-2d): {', '.join(codes_from_file)}"
else:
    codes_hint = ""
```

Pass `codes_hint` into the prompt by adding it to the `{syllabus_codes_instruction}` block:

```python
def build_syllabus_instruction(syllabus_codes: list, codes_from_file: list = None) -> str:
    parts = []
    if codes_from_file:
        parts.append(f"AVAILABLE SYLLABUS CODES (tag questions using EXACTLY these codes): {', '.join(codes_from_file)}")
    if syllabus_codes:
        codes_str = ", ".join(syllabus_codes)
        parts.append(f"SYLLABUS CODES TO TARGET: {codes_str}\nThe question(s) MUST test these specific syllabus items.")
    return "\n".join(parts)
```

Update calls to `build_syllabus_instruction()` in all 3 generate routes to pass `codes_from_file=ctx.get("syllabus_codes_list", [])`.

---

## Change 3: Parse Sample files into individual Examples

**Location:** `backend/routes/sessions.py` + `backend/document_extractor.py` + DB + `frontend/src/pages/Documents.jsx`

### 3a. New DB table: `sample_examples`

Add to `backend/database.py` migrations:

```sql
CREATE TABLE IF NOT EXISTS sample_examples (
    id SERIAL PRIMARY KEY,
    session_id INTEGER REFERENCES exam_sessions(id) ON DELETE CASCADE,
    file_id INTEGER REFERENCES session_files(id) ON DELETE CASCADE,
    example_number INTEGER NOT NULL,           -- 1, 2, 3...
    title VARCHAR(200),                         -- "Example 1" or heading text
    content TEXT NOT NULL,                      -- full raw text of this example
    syllabus_codes TEXT[],                      -- AI-tagged codes, e.g. {C2d, C2n}
    tax_type VARCHAR(20),
    exam_type VARCHAR(20),
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_sample_examples_session ON sample_examples(session_id);
CREATE INDEX IF NOT EXISTS idx_sample_examples_file ON sample_examples(file_id);
```

### 3b. Parser: split file by "Example N" headings

Add to `backend/document_extractor.py`:

```python
import re

def parse_sample_examples(file_path: str) -> list[dict]:
    """
    Split a sample questions docx into individual examples.
    Splits on patterns like: 'Example 1', 'Example 2', 'EXAMPLE 1', etc.
    Returns list of dicts: {example_number, title, content}
    """
    try:
        text = extract_text(file_path)
    except Exception as e:
        logger.warning(f"Cannot extract {file_path}: {e}")
        return []

    # Split on "Example N" pattern (case-insensitive, at line start or after newline)
    pattern = re.compile(r'(?:^|\n)(Example\s+\d+[^\n]*)', re.IGNORECASE)
    parts = pattern.split(text)

    examples = []
    # parts alternates: [preamble, heading1, content1, heading2, content2, ...]
    i = 1  # skip preamble
    while i < len(parts) - 1:
        heading = parts[i].strip()
        content = parts[i + 1].strip() if i + 1 < len(parts) else ""
        # Extract example number from heading
        num_match = re.search(r'\d+', heading)
        example_number = int(num_match.group()) if num_match else (len(examples) + 1)
        if content:
            examples.append({
                "example_number": example_number,
                "title": heading,
                "content": f"{heading}\n\n{content}",
            })
        i += 2

    return examples
```

### 3c. Auto-parse on upload

In `backend/routes/sessions.py`, in the `upload_file()` endpoint, after saving the file record, if `file_type == "sample"`, auto-parse and store examples:

```python
if file_type == "sample":
    from backend.document_extractor import parse_sample_examples
    examples = parse_sample_examples(full_path)
    if examples:
        with get_db() as conn:
            cur = conn.cursor()
            # Delete old examples for this file (in case of re-upload)
            cur.execute("DELETE FROM sample_examples WHERE file_id = %s", (file_id,))
            for ex in examples:
                cur.execute("""
                    INSERT INTO sample_examples (session_id, file_id, example_number, title, content, tax_type, exam_type)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (session_id, file_id, ex["example_number"], ex["title"], ex["content"], tax_type, exam_type))
        logger.info(f"Parsed {len(examples)} examples from {filename}")
```

### 3d. New endpoints for examples

Add to `backend/routes/sessions.py`:

```python
@router.get("/{session_id}/examples")
def list_sample_examples(session_id: int, sac_thue: str = None, exam_type: str = None):
    """List parsed sample examples for a session, optionally filtered."""
    with get_db() as conn:
        cur = conn.cursor()
        query = """
            SELECT se.id, se.file_id, se.example_number, se.title,
                   LEFT(se.content, 200) as preview,
                   se.syllabus_codes, se.tax_type, se.exam_type,
                   sf.display_name as file_name
            FROM sample_examples se
            JOIN session_files sf ON se.file_id = sf.id
            WHERE se.session_id = %s
        """
        params = [session_id]
        if sac_thue:
            query += " AND se.tax_type = %s"
            params.append(sac_thue)
        if exam_type:
            query += " AND se.exam_type = %s"
            params.append(exam_type)
        query += " ORDER BY se.tax_type, se.exam_type, se.example_number"
        cur.execute(query, params)
        rows = cur.fetchall()
    return [
        {
            "id": r[0], "file_id": r[1], "example_number": r[2],
            "title": r[3], "preview": r[4], "syllabus_codes": r[5] or [],
            "tax_type": r[6], "exam_type": r[7], "file_name": r[8],
        }
        for r in rows
    ]

@router.get("/{session_id}/examples/{example_id}/full")
def get_example_full(session_id: int, example_id: int):
    """Get full content of a specific example."""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT content, title, syllabus_codes FROM sample_examples WHERE id = %s AND session_id = %s",
                    (example_id, session_id))
        row = cur.fetchone()
    if not row:
        raise HTTPException(404, "Example not found")
    return {"content": row[0], "title": row[1], "syllabus_codes": row[2] or []}

@router.post("/{session_id}/examples/{example_id}/tag")
def tag_example_with_ai(session_id: int, example_id: int):
    """Use AI to tag this example with syllabus codes."""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT content, tax_type FROM sample_examples WHERE id = %s AND session_id = %s",
                    (example_id, session_id))
        row = cur.fetchone()
    if not row:
        raise HTTPException(404, "Example not found")

    content, tax_type = row
    from backend.ai_provider import call_ai
    prompt = f"""Read this ACCA TX(VNM) exam question and identify which ACCA syllabus codes it tests.

TAX TYPE: {tax_type}

QUESTION:
{content[:2000]}

Return ONLY a JSON array of syllabus code strings, e.g.: ["C2d", "C2n", "C3a"]
Use the short code format (e.g. C2d, P4a, V2b) — not verbose descriptions.
Return [] if you cannot determine the codes."""

    result = call_ai(prompt, model_tier="fast")
    try:
        import json, re
        text = result["content"].strip()
        # Extract JSON array
        match = re.search(r'\[.*?\]', text, re.DOTALL)
        codes = json.loads(match.group()) if match else []
    except Exception:
        codes = []

    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("UPDATE sample_examples SET syllabus_codes = %s WHERE id = %s",
                    (codes, example_id))

    return {"syllabus_codes": codes}

@router.post("/{session_id}/examples/tag-all")
def tag_all_examples(session_id: int, background_tasks: BackgroundTasks):
    """Queue AI tagging for all untagged examples in this session."""
    def _tag_all():
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("SELECT id FROM sample_examples WHERE session_id = %s AND (syllabus_codes IS NULL OR syllabus_codes = '{}')",
                        (session_id,))
            ids = [r[0] for r in cur.fetchall()]
        for eid in ids:
            try:
                tag_example_with_ai(session_id, eid)
            except Exception as e:
                logger.warning(f"Tag failed for example {eid}: {e}")
    background_tasks.add_task(_tag_all)
    return {"message": f"Tagging queued for session {session_id}"}
```

Add `BackgroundTasks` import: `from fastapi import BackgroundTasks`.

### 3e. Documents.jsx — show examples in collapsible folder under Sample Questions tab

In `frontend/src/pages/Documents.jsx`, when `activeTab === 'sample'`, after the file list, add an "Examples" section:

```jsx
// Add state:
const [examples, setExamples] = useState([])
const [examplesLoading, setExamplesLoading] = useState(false)
const [expandedFiles, setExpandedFiles] = useState({})  // fileId → true/false
const [taggingAll, setTaggingAll] = useState(false)

// Load examples when sample tab is active:
useEffect(() => {
  if (activeTab === 'sample' && sessionId) {
    setExamplesLoading(true)
    api.getSampleExamples(sessionId)
      .then(setExamples)
      .catch(() => setExamples([]))
      .finally(() => setExamplesLoading(false))
  }
}, [activeTab, sessionId, files])  // reload when files change

// Group examples by file:
const examplesByFile = examples.reduce((acc, ex) => {
  const key = `${ex.file_id}|${ex.file_name}`
  if (!acc[key]) acc[key] = { file_name: ex.file_name, file_id: ex.file_id, examples: [] }
  acc[key].examples.push(ex)
  return acc
}, {})

// Render below file list, inside sample tab:
{activeTab === 'sample' && Object.keys(examplesByFile).length > 0 && (
  <div className="mt-6">
    <div className="flex items-center justify-between mb-3">
      <h4 className="text-sm font-semibold text-gray-700">Parsed Examples</h4>
      <button
        onClick={async () => {
          setTaggingAll(true)
          try { await api.tagAllExamples(sessionId) }
          catch { /* background task, ignore */ }
          finally { setTaggingAll(false) }
        }}
        disabled={taggingAll}
        className="text-xs px-3 py-1 bg-purple-50 border border-purple-200 text-purple-700 rounded-lg hover:bg-purple-100 disabled:opacity-50"
      >
        {taggingAll ? '⏳ Tagging...' : '✨ AI Tag All'}
      </button>
    </div>
    <div className="space-y-2">
      {Object.values(examplesByFile).map(({ file_name, file_id, examples: exs }) => (
        <div key={file_id} className="border rounded-lg overflow-hidden">
          {/* Collapsible file header */}
          <button
            className="w-full flex items-center justify-between px-4 py-3 bg-gray-50 hover:bg-gray-100 text-left"
            onClick={() => setExpandedFiles(prev => ({ ...prev, [file_id]: !prev[file_id] }))}
          >
            <div className="flex items-center gap-2">
              <span className="text-sm">{expandedFiles[file_id] ? '▼' : '▶'}</span>
              <span className="text-sm font-medium">{file_name}</span>
              <span className="text-xs bg-blue-100 text-blue-700 px-2 py-0.5 rounded-full">
                {exs.length} examples
              </span>
            </div>
          </button>
          {/* Example list */}
          {expandedFiles[file_id] && (
            <div className="divide-y">
              {exs.map((ex) => (
                <ExampleRow
                  key={ex.id}
                  example={ex}
                  sessionId={sessionId}
                  onTagged={(codes) => {
                    setExamples(prev => prev.map(e => e.id === ex.id ? { ...e, syllabus_codes: codes } : e))
                  }}
                />
              ))}
            </div>
          )}
        </div>
      ))}
    </div>
  </div>
)}
```

**New `ExampleRow` component** in `Documents.jsx`:

```jsx
function ExampleRow({ example, sessionId, onTagged }) {
  const [tagging, setTagging] = useState(false)
  const [showFull, setShowFull] = useState(false)
  const [fullContent, setFullContent] = useState(null)

  const handleTag = async (e) => {
    e.stopPropagation()
    setTagging(true)
    try {
      const res = await api.tagExample(sessionId, example.id)
      onTagged(res.syllabus_codes)
    } catch { alert('Tagging failed') }
    finally { setTagging(false) }
  }

  const handleToggleFull = async () => {
    if (!showFull && !fullContent) {
      const res = await api.getExampleFull(sessionId, example.id)
      setFullContent(res.content)
    }
    setShowFull(!showFull)
  }

  return (
    <div className="px-4 py-3">
      <div className="flex items-center justify-between">
        <button onClick={handleToggleFull} className="flex-1 text-left">
          <span className="text-sm font-medium text-gray-700">{example.title}</span>
          {!showFull && (
            <p className="text-xs text-gray-400 mt-0.5 truncate">{example.preview}</p>
          )}
        </button>
        <div className="flex items-center gap-2 ml-3 shrink-0">
          {example.syllabus_codes?.length > 0 ? (
            <div className="flex flex-wrap gap-1">
              {example.syllabus_codes.map(c => (
                <span key={c} className="text-xs bg-green-100 text-green-700 px-1.5 py-0.5 rounded font-mono">
                  {c}
                </span>
              ))}
            </div>
          ) : (
            <button
              onClick={handleTag}
              disabled={tagging}
              className="text-xs px-2 py-1 bg-purple-50 border border-purple-200 text-purple-600 rounded hover:bg-purple-100 disabled:opacity-50"
            >
              {tagging ? '...' : '✨ AI Tag'}
            </button>
          )}
        </div>
      </div>
      {showFull && fullContent && (
        <div className="mt-2 p-3 bg-gray-50 rounded text-xs text-gray-600 whitespace-pre-wrap max-h-64 overflow-y-auto font-mono leading-relaxed">
          {fullContent}
        </div>
      )}
    </div>
  )
}
```

---

## Change 4: Sample examples list in Generate page Custom Instructions

**Location:** `frontend/src/pages/Generate.jsx` — getSamplePreviews + display

**Problem:** Currently the "Sample Examples in Knowledge Base" section shows 1 text preview per file. Should show individual examples (from `sample_examples` table) as a list of cards.

**Fix — update `getSamplePreviews` → use `getSampleExamples` instead:**

In `frontend/src/api.js`, the existing `getSamplePreviews` returns file-level previews. Add:

```js
getSampleExamples: (session_id, params = {}) => {
  const qs = new URLSearchParams(params).toString()
  return request(`/sessions/${session_id}/examples${qs ? `?${qs}` : ''}`)
},
getExampleFull: (session_id, example_id) =>
  request(`/sessions/${session_id}/examples/${example_id}/full`),
tagExample: (session_id, example_id) =>
  request(`/sessions/${session_id}/examples/${example_id}/tag`, { method: 'POST' }),
tagAllExamples: (session_id) =>
  request(`/sessions/${session_id}/examples/tag-all`, { method: 'POST' }),
```

**In Generate.jsx**, replace the `samplePreviews` section with `sampleExamples`:

```jsx
// State:
const [sampleExamples, setSampleExamples] = useState([])

// useEffect:
useEffect(() => {
  if (!sessionId || !sac_thue) return
  api.getSampleExamples(sessionId, { sac_thue })
    .then(setSampleExamples)
    .catch(() => setSampleExamples([]))
}, [sessionId, sac_thue])

// Render in showCustom section:
{sampleExamples.length > 0 && (
  <div>
    <label className="block text-sm font-medium mb-2">
      Sample Examples in Knowledge Base
      <span className="text-xs text-gray-400 font-normal ml-2">
        {sampleExamples.length} examples · {sac_thue}
      </span>
    </label>
    <div className="space-y-1 max-h-56 overflow-y-auto border rounded-lg p-2 bg-gray-50">
      {sampleExamples.map((ex) => (
        <ExampleCard
          key={ex.id}
          example={ex}
          sessionId={sessionId}
          onSelect={(content) => {
            setCustomInstructions(content)
            setShowCustom(true)
          }}
        />
      ))}
    </div>
    <p className="text-xs text-gray-400 mt-1">
      Click an example to use as style reference in Custom Instructions.
      The full sample file is still used automatically for context.
    </p>
  </div>
)}
```

**New `ExampleCard` component** (lightweight hover preview, reuse in Generate page):

```jsx
function ExampleCard({ example, sessionId, onSelect }) {
  const [hoverContent, setHoverContent] = useState(null)
  const [showTooltip, setShowTooltip] = useState(false)

  const handleMouseEnter = async () => {
    setShowTooltip(true)
    if (!hoverContent) {
      try {
        const res = await api.getExampleFull(sessionId, example.id)
        setHoverContent(res.content?.slice(0, 1000) + (res.content?.length > 1000 ? '...' : ''))
      } catch { setHoverContent(example.preview) }
    }
  }

  return (
    <div className="relative">
      <div
        onMouseEnter={handleMouseEnter}
        onMouseLeave={() => setShowTooltip(false)}
        onClick={async () => {
          const res = await api.getExampleFull(sessionId, example.id)
          onSelect(res.content)
        }}
        className="cursor-pointer flex items-center gap-2 px-3 py-2 rounded-lg hover:bg-white hover:border-gray-200 border border-transparent transition-all"
      >
        <span className="text-xs font-medium text-gray-700 flex-1 truncate">
          {example.title}
        </span>
        {example.syllabus_codes?.length > 0 && (
          <div className="flex gap-1 shrink-0">
            {example.syllabus_codes.slice(0, 3).map(c => (
              <span key={c} className="text-xs bg-green-100 text-green-700 px-1 rounded font-mono">{c}</span>
            ))}
            {example.syllabus_codes.length > 3 && (
              <span className="text-xs text-gray-400">+{example.syllabus_codes.length - 3}</span>
            )}
          </div>
        )}
      </div>
      {/* Hover tooltip */}
      {showTooltip && hoverContent && (
        <div className="absolute z-50 left-full ml-2 top-0 w-96 bg-white border border-gray-200 shadow-xl rounded-lg p-3 text-xs text-gray-600 whitespace-pre-wrap font-mono leading-relaxed max-h-72 overflow-y-auto">
          {hoverContent}
        </div>
      )}
    </div>
  )
}
```

---

## Change 5: Hover preview in "Based on question from bank"

**Location:** `frontend/src/pages/Generate.jsx` — referenceOptions card list

**Fix:** In the reference question card list (added in v3.3), add hover tooltip showing full question preview (~1000 chars).

**New backend endpoint** — add to `backend/routes/questions.py`:

```python
@router.get("/{question_id}/preview")
def get_question_preview(question_id: int):
    """Return first 1000 chars of question content as plain text."""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT content_json, question_type, sac_thue FROM questions WHERE id = %s", (question_id,))
        row = cur.fetchone()
    if not row:
        raise HTTPException(404, "Not found")
    from backend.context_builder import format_question_as_text
    content = row[0] if isinstance(row[0], dict) else json.loads(row[0])
    text = format_question_as_text(content)
    return {"preview": text[:1000] + ("..." if len(text) > 1000 else ""), "question_type": row[1], "sac_thue": row[2]}
```

Add API call in `frontend/src/api.js`:

```js
getQuestionPreview: (question_id) => request(`/questions/${question_id}/preview`),
```

**Update the reference question cards in Generate.jsx** to use same hover pattern as ExampleCard above:

```jsx
// Replace the card list from v3.3 with hover-enabled version:
{referenceOptions.map((q) => (
  <ReferenceCard
    key={q.id}
    question={q}
    selected={referenceId === String(q.id)}
    onSelect={() => setReferenceId(referenceId === String(q.id) ? '' : String(q.id))}
  />
))}

function ReferenceCard({ question, selected, onSelect }) {
  const [hoverContent, setHoverContent] = useState(null)
  const [showTooltip, setShowTooltip] = useState(false)

  const handleMouseEnter = async () => {
    setShowTooltip(true)
    if (!hoverContent) {
      try {
        const res = await api.getQuestionPreview(question.id)
        setHoverContent(res.preview)
      } catch { setHoverContent(question.snippet) }
    }
  }

  return (
    <div className="relative">
      <div
        onClick={onSelect}
        onMouseEnter={handleMouseEnter}
        onMouseLeave={() => setShowTooltip(false)}
        className={`cursor-pointer rounded-lg px-3 py-2 text-sm border transition-all ${
          selected ? 'border-brand-500 bg-brand-50' : 'border-transparent hover:bg-white hover:border-gray-200'
        }`}
      >
        <div className="flex items-center gap-2 mb-0.5">
          <span className="bg-blue-100 text-blue-700 text-xs font-semibold px-2 py-0.5 rounded">
            {question.question_type?.replace('_10','').replace('_15','')}
          </span>
          <span className="bg-green-100 text-green-700 text-xs font-semibold px-2 py-0.5 rounded">
            {question.sac_thue}
          </span>
          <span className="text-xs text-gray-400 ml-auto">{question.created_at}</span>
        </div>
        {question.snippet && (
          <p className="text-xs text-gray-500 truncate">{question.snippet}</p>
        )}
      </div>
      {showTooltip && hoverContent && (
        <div className="absolute z-50 left-full ml-2 top-0 w-96 bg-white border border-gray-200 shadow-xl rounded-lg p-3 text-xs text-gray-600 whitespace-pre-wrap font-mono leading-relaxed max-h-72 overflow-y-auto">
          {hoverContent}
        </div>
      )}
    </div>
  )
}
```

---

## Change 6: Session Variables (Exchange Rate, Minimum Salary, custom vars)

**Location:** `backend/database.py` + `backend/routes/sessions.py` + `frontend/src/pages/Sessions.jsx` + `backend/context_builder.py` + `backend/prompts.py`

### 6a. DB — `session_variables` table (new, replaces old `parameters` JSONB)

Add to migrations in `backend/database.py`:

```sql
CREATE TABLE IF NOT EXISTS session_variables (
    id SERIAL PRIMARY KEY,
    session_id INTEGER REFERENCES exam_sessions(id) ON DELETE CASCADE,
    var_key VARCHAR(100) NOT NULL,       -- e.g. "exchange_rate_usd_vnd"
    var_label VARCHAR(200) NOT NULL,     -- e.g. "Exchange Rate (1 USD = ? VND)"
    var_value VARCHAR(500) NOT NULL,     -- e.g. "25,450"
    var_unit VARCHAR(50),                -- e.g. "VND", "%", "VND/month"
    description TEXT,                    -- optional notes
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE (session_id, var_key)
);
-- Seed default variables for existing sessions:
INSERT INTO session_variables (session_id, var_key, var_label, var_value, var_unit, description)
SELECT id, 'exchange_rate_usd_vnd', 'Exchange Rate (1 USD = ? VND)', '25,450', 'VND', 'Used to convert USD amounts to VND in calculations'
FROM exam_sessions
ON CONFLICT (session_id, var_key) DO NOTHING;

INSERT INTO session_variables (session_id, var_key, var_label, var_value, var_unit, description)
SELECT id, 'min_salary_si', 'Minimum Salary for Social/Health Insurance', '4,960,000', 'VND/month', 'Base for calculating compulsory SI/HI contributions'
FROM exam_sessions
ON CONFLICT (session_id, var_key) DO NOTHING;
```

### 6b. New endpoints in `backend/routes/sessions.py`

```python
@router.get("/{session_id}/variables")
def list_variables(session_id: int):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, var_key, var_label, var_value, var_unit, description
            FROM session_variables WHERE session_id = %s ORDER BY id
        """, (session_id,))
        rows = cur.fetchall()
    return [{"id": r[0], "key": r[1], "label": r[2], "value": r[3], "unit": r[4], "description": r[5]} for r in rows]

@router.post("/{session_id}/variables")
def create_variable(session_id: int, data: dict):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO session_variables (session_id, var_key, var_label, var_value, var_unit, description)
            VALUES (%s, %s, %s, %s, %s, %s) RETURNING id
        """, (session_id, data["key"], data["label"], data["value"], data.get("unit",""), data.get("description","")))
        new_id = cur.fetchone()[0]
    return {"id": new_id}

@router.put("/{session_id}/variables/{var_id}")
def update_variable(session_id: int, var_id: int, data: dict):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            UPDATE session_variables SET var_label=%s, var_value=%s, var_unit=%s, description=%s
            WHERE id=%s AND session_id=%s
        """, (data["label"], data["value"], data.get("unit",""), data.get("description",""), var_id, session_id))
    return {"ok": True}

@router.delete("/{session_id}/variables/{var_id}")
def delete_variable(session_id: int, var_id: int):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM session_variables WHERE id=%s AND session_id=%s", (var_id, session_id))
    return {"ok": True}
```

### 6c. Sessions.jsx — add Variables section to session edit form

Inside the create/edit form (below `assumed_date` and `carry_forward` fields), add:

```jsx
// State (inside Sessions component, when editSession is active):
const [variables, setVariables] = useState([])
const [newVar, setNewVar] = useState({ key: '', label: '', value: '', unit: '', description: '' })
const [addingVar, setAddingVar] = useState(false)

// Load variables when editing:
useEffect(() => {
  if (editSession?.id) {
    api.getSessionVariables(editSession.id).then(setVariables).catch(() => setVariables([]))
  }
}, [editSession])

// Render inside form, after carry-forward section:
{editSession && (
  <div className="col-span-2 border-t pt-4">
    <div className="flex items-center justify-between mb-3">
      <label className="text-xs font-semibold text-gray-600 uppercase tracking-wide">
        Global Variables
      </label>
      <button
        type="button"
        onClick={() => setAddingVar(true)}
        className="text-xs px-2 py-1 bg-brand-50 text-brand-600 border border-brand-200 rounded hover:bg-brand-100"
      >
        + Add Variable
      </button>
    </div>
    <div className="space-y-2">
      {variables.map((v) => (
        <VariableRow
          key={v.id}
          variable={v}
          onUpdate={async (data) => {
            await api.updateSessionVariable(editSession.id, v.id, data)
            api.getSessionVariables(editSession.id).then(setVariables)
          }}
          onDelete={async () => {
            await api.deleteSessionVariable(editSession.id, v.id)
            setVariables(prev => prev.filter(x => x.id !== v.id))
          }}
        />
      ))}
      {addingVar && (
        <div className="border rounded-lg p-3 bg-gray-50 space-y-2">
          <div className="grid grid-cols-2 gap-2">
            <input placeholder="Key (e.g. exchange_rate_usd_vnd)" value={newVar.key}
              onChange={(e) => setNewVar({...newVar, key: e.target.value})}
              className="col-span-2 border rounded px-2 py-1 text-xs" />
            <input placeholder="Label (e.g. Exchange Rate 1 USD = ? VND)" value={newVar.label}
              onChange={(e) => setNewVar({...newVar, label: e.target.value})}
              className="col-span-2 border rounded px-2 py-1 text-xs" />
            <input placeholder="Value (e.g. 25,450)" value={newVar.value}
              onChange={(e) => setNewVar({...newVar, value: e.target.value})}
              className="border rounded px-2 py-1 text-xs" />
            <input placeholder="Unit (e.g. VND)" value={newVar.unit}
              onChange={(e) => setNewVar({...newVar, unit: e.target.value})}
              className="border rounded px-2 py-1 text-xs" />
          </div>
          <div className="flex gap-2">
            <button
              onClick={async () => {
                await api.createSessionVariable(editSession.id, newVar)
                api.getSessionVariables(editSession.id).then(setVariables)
                setNewVar({ key: '', label: '', value: '', unit: '', description: '' })
                setAddingVar(false)
              }}
              className="text-xs px-3 py-1 bg-brand-500 text-white rounded hover:bg-brand-600"
            >Save</button>
            <button onClick={() => setAddingVar(false)}
              className="text-xs px-3 py-1 border rounded hover:bg-gray-100">Cancel</button>
          </div>
        </div>
      )}
    </div>
    <p className="text-xs text-gray-400 mt-2">
      Variables are injected into every prompt for this session (exchange rates, salary caps, etc.)
    </p>
  </div>
)}
```

**`VariableRow` component:**

```jsx
function VariableRow({ variable, onUpdate, onDelete }) {
  const [editing, setEditing] = useState(false)
  const [form, setForm] = useState({ label: variable.label, value: variable.value, unit: variable.unit || '', description: variable.description || '' })

  if (editing) {
    return (
      <div className="border rounded-lg p-3 bg-white space-y-2">
        <div className="grid grid-cols-2 gap-2">
          <input value={form.label} onChange={(e) => setForm({...form, label: e.target.value})}
            className="col-span-2 border rounded px-2 py-1 text-xs" placeholder="Label" />
          <input value={form.value} onChange={(e) => setForm({...form, value: e.target.value})}
            className="border rounded px-2 py-1 text-xs" placeholder="Value" />
          <input value={form.unit} onChange={(e) => setForm({...form, unit: e.target.value})}
            className="border rounded px-2 py-1 text-xs" placeholder="Unit" />
        </div>
        <div className="flex gap-2">
          <button onClick={async () => { await onUpdate(form); setEditing(false) }}
            className="text-xs px-3 py-1 bg-brand-500 text-white rounded">Save</button>
          <button onClick={() => setEditing(false)} className="text-xs px-3 py-1 border rounded">Cancel</button>
        </div>
      </div>
    )
  }

  return (
    <div className="flex items-center gap-3 border rounded-lg px-3 py-2 bg-white text-xs">
      <div className="flex-1 min-w-0">
        <span className="font-medium text-gray-700">{variable.label}</span>
        <span className="ml-2 font-mono text-brand-600">{variable.value}</span>
        {variable.unit && <span className="ml-1 text-gray-400">{variable.unit}</span>}
      </div>
      <button onClick={() => setEditing(true)} className="text-gray-400 hover:text-gray-700 px-1">✎</button>
      <button onClick={onDelete} className="text-red-400 hover:text-red-600 px-1">✕</button>
    </div>
  )
}
```

### 6d. Inject variables into prompts via `context_builder.py`

Add to `build_context()`:

```python
# Load session variables
variables = []
try:
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT var_label, var_value, var_unit
            FROM session_variables WHERE session_id = %s ORDER BY id
        """, (session_id,))
        variables = [{"label": r[0], "value": r[1], "unit": r[2] or ""} for r in cur.fetchall()]
except Exception as e:
    logger.warning(f"Failed to load session variables: {e}")

if variables:
    var_lines = "\n".join(f"- {v['label']}: {v['value']} {v['unit']}".strip() for v in variables)
    session_vars_text = f"SESSION VARIABLES (apply these globally to all calculations):\n{var_lines}"
else:
    session_vars_text = ""

return {
    "tax_rates": tax_rates,
    "syllabus": syllabus,
    "regulations": regulations,
    "sample": sample,
    "syllabus_codes_list": all_syllabus_codes,
    "session_vars": session_vars_text,   # NEW
}
```

**In `prompts.py`**, add `{session_vars}` at the top of all 3 prompt templates, right after the header:

```python
MCQ_PROMPT = """Generate {count} MCQ question(s) for Part 1 of ACCA TX(VNM).

EXAM SESSION: {exam_session}
TAX TYPE: {sac_thue}
{session_vars}
{syllabus_codes_instruction}
...
```

**In all 3 generate routes**, pass `session_vars=ctx.get("session_vars", "")` to the prompt format call.

**Add API calls** in `frontend/src/api.js`:

```js
getSessionVariables: (session_id) => request(`/sessions/${session_id}/variables`),
createSessionVariable: (session_id, data) => request(`/sessions/${session_id}/variables`, { method: 'POST', body: JSON.stringify(data) }),
updateSessionVariable: (session_id, var_id, data) => request(`/sessions/${session_id}/variables/${var_id}`, { method: 'PUT', body: JSON.stringify(data) }),
deleteSessionVariable: (session_id, var_id) => request(`/sessions/${session_id}/variables/${var_id}`, { method: 'DELETE' }),
```

---

## Summary of file changes

| File | Changes |
|---|---|
| `backend/prompts.py` | Add calculation steps requirement; add `{session_vars}` placeholder |
| `backend/context_builder.py` | Add `_extract_syllabus_codes()` from xlsx; load session vars; return `syllabus_codes_list`, `session_vars` |
| `backend/routes/generate.py` | Pass `session_vars` + `codes_from_file` to prompts; update `build_syllabus_instruction()` calls |
| `backend/prompts.py` | Update `build_syllabus_instruction()` to accept `codes_from_file` |
| `backend/document_extractor.py` | Add `parse_sample_examples()` |
| `backend/database.py` | Add `sample_examples` table + `session_variables` table + seed defaults |
| `backend/routes/sessions.py` | Add examples endpoints (list/full/tag/tag-all) + variables CRUD |
| `backend/routes/questions.py` | Add `GET /{id}/preview` endpoint |
| `frontend/src/api.js` | Add `getSampleExamples`, `getExampleFull`, `tagExample`, `tagAllExamples`, `getQuestionPreview`, variables CRUD |
| `frontend/src/pages/Documents.jsx` | Add parsed examples collapsible section with AI tag button |
| `frontend/src/pages/Generate.jsx` | Replace sample previews with example cards; add hover tooltips; add ReferenceCard with hover |
| `frontend/src/pages/Sessions.jsx` | Add session variables section with CRUD UI |
