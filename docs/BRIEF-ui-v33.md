# ExamsGen — UI Fix Brief v3.3
**Date:** March 2026
**Scope:** Generate page UI improvements — 3 changes requested

---

## Change 1: Remove "Exam Session Label" input field

**Location:** `frontend/src/pages/Generate.jsx` — Step 2 Configure grid

**Problem:** The "Exam Session Label" field (variable `examSession`, default "Jun2026") is confusing. The session name is already set when user creates the exam session — there is no need to override it per-generation. It's just a label injected into the prompt.

**Fix:**
- Remove the `<div>` block containing the "Exam Session Label" input entirely from the JSX
- Keep the `examSession` state variable but auto-populate it from the selected session's `exam_date` field (this already happens in the `useEffect` for sessions — just don't render the manual input)
- The grid now has one fewer field — move **Syllabus Codes** (currently `col-span-2` at the bottom) up into the main 2-column grid so the layout stays balanced

**Before (in grid):**
```
[Tax Type]         [Count]
[Topics]           [Difficulty]
[AI Provider]      [Exam Session Label]  ← REMOVE THIS
[Syllabus Codes — col-span-2]           ← MOVE UP
```

**After:**
```
[Tax Type]         [Count]
[Topics]           [Difficulty]
[AI Provider]      [Syllabus Codes]      ← moved up, no longer col-span-2
```

For Scenario and Longform types, apply same logic — remove "Exam Session Label" and place Syllabus Codes in the freed slot.

---

## Change 2: Add Syllabus Codes to question output display

**Location:** `backend/routes/generate.py` + `backend/prompts.py` + `backend/html_renderer.py`

**Problem:** Generated questions have `syllabus_codes` in their JSON (e.g. `["CIT-2d", "CIT-2n"]`) but the HTML output doesn't display them visibly. User sees no confirmation of which syllabus items were tested.

### 2a. Prompt — ask Claude to also output a human-readable regulation reference summary

In `MCQ_PROMPT` (and Scenario/Longform prompts), add to REQUIREMENTS section:

```
- In the correct answer explanation, include a line: "Syllabus items tested: [list codes and topic names, e.g. CIT-2d: Depreciation of fixed assets]"
- This line must appear AFTER the regulation references
```

### 2b. HTML renderer — display syllabus codes as tags below the question

In `backend/html_renderer.py`, in the MCQ rendering section, after the regulation refs block, add:

```python
# After regulation_refs block:
syllabus_codes = q.get("syllabus_codes", [])
if syllabus_codes:
    codes_html = "".join(
        f'<span style="display:inline-block;background:#e8f5e9;color:#2e7d32;border:1px solid #a5d6a7;'
        f'border-radius:4px;padding:2px 8px;font-size:11px;margin:2px 3px 2px 0;font-weight:600;">'
        f'{code}</span>'
        for code in syllabus_codes
    )
    html += (
        f'<div style="margin-top:10px;padding-top:8px;border-top:1px solid #e5e7eb;">'
        f'<span style="font-size:11px;color:#6b7280;font-weight:600;text-transform:uppercase;'
        f'letter-spacing:0.05em;">Syllabus codes tested: </span>{codes_html}</div>'
    )
```

Apply similar rendering for Scenario and Longform (show `regulation_refs` + `syllabus_codes` at end of each sub-question or at the question level).

---

## Change 3: Improve "Custom Instructions" section — question picker + sample previews

**Location:** `frontend/src/pages/Generate.jsx` — `showCustom` section

### 3a. Improve "Based on question from bank" picker

**Current:** A plain `<select>` dropdown with label like `"MCQ CIT — scenario... (Mar 24)"`

**Fix:** Replace the `<select>` with a richer list — when expanded, show each question as a card with:
- Question type badge (MCQ / Scenario / Longform)
- Tax type badge (CIT / PIT etc)
- First 100 chars of scenario as preview
- Date created
- Click to select (highlight selected card with green border)

Implementation — update `GET /api/questions/for-reference` to return more data:

```python
# In backend/routes/questions.py — get_questions_for_reference()
# Add to the returned dict:
{
    "id": q_id,
    "label": label,          # keep existing
    "question_type": q_type,
    "sac_thue": q_sac,
    "snippet": snippet,       # first 100 chars of scenario
    "created_at": date_str,
}
```

Frontend — replace `<select>` with card list:

```jsx
{referenceOptions.length > 0 && (
  <div>
    <label className="block text-sm font-medium mb-2">Based on question from bank</label>
    <div className="space-y-2 max-h-48 overflow-y-auto border rounded-lg p-2 bg-gray-50">
      {/* "None" option */}
      <div
        onClick={() => setReferenceId('')}
        className={`cursor-pointer rounded-lg px-3 py-2 text-sm border transition-all ${
          referenceId === '' ? 'border-brand-500 bg-brand-50' : 'border-transparent hover:bg-white hover:border-gray-200'
        }`}
      >
        <span className="text-gray-400 italic">— None —</span>
      </div>
      {referenceOptions.map((q) => (
        <div
          key={q.id}
          onClick={() => setReferenceId(String(q.id))}
          className={`cursor-pointer rounded-lg px-3 py-2 text-sm border transition-all ${
            referenceId === String(q.id)
              ? 'border-brand-500 bg-brand-50'
              : 'border-transparent hover:bg-white hover:border-gray-200'
          }`}
        >
          <div className="flex items-center gap-2 mb-1">
            <span className="bg-blue-100 text-blue-700 text-xs font-semibold px-2 py-0.5 rounded">
              {q.question_type?.replace('_10','').replace('_15','')}
            </span>
            <span className="bg-green-100 text-green-700 text-xs font-semibold px-2 py-0.5 rounded">
              {q.sac_thue}
            </span>
            <span className="text-xs text-gray-400 ml-auto">{q.created_at}</span>
          </div>
          {q.snippet && (
            <p className="text-xs text-gray-600 truncate">{q.snippet}</p>
          )}
        </div>
      ))}
    </div>
  </div>
)}
```

### 3b. Add "Sample Examples" preview section

**New feature:** Show available sample files for the current tax type + question type, with a preview of first few lines.

**New backend endpoint** — add to `backend/routes/sessions.py`:

```python
@router.get("/{session_id}/samples/preview")
def get_sample_previews(session_id: int, sac_thue: str, exam_type: str = "MCQ"):
    """Return list of sample files with first 300 chars of text content as preview."""
    from backend.context_builder import _load_files, _extract_with_cap
    import os
    DATA_DIR = os.getenv("DATA_DIR", "/app/data")

    files = _load_files(session_id, "sample", tax_type=sac_thue, exam_type=exam_type)
    result = []
    for f in files:
        file_path = f["path"]
        if not os.path.isabs(file_path):
            file_path = os.path.join(DATA_DIR, file_path)
        try:
            from backend.document_extractor import extract_text
            text = extract_text(file_path)
            preview = text[:400].strip()
        except Exception:
            preview = ""
        result.append({
            "name": f["name"] or f["path"],
            "tax_type": f["tax_type"],
            "exam_type": f["exam_type"],
            "preview": preview,
        })
    return result
```

**New API call** in `frontend/src/api.js`:

```js
getSamplePreviews: ({ session_id, sac_thue, exam_type }) => {
  const params = new URLSearchParams({ sac_thue, exam_type })
  return request(`/sessions/${session_id}/samples/preview?${params}`)
},
```

**Frontend** — add to `showCustom` section, below the question bank picker:

```jsx
// Add state:
const [samplePreviews, setSamplePreviews] = useState([])

// Add useEffect to load sample previews when session/type/sac_thue changes:
useEffect(() => {
  if (!sessionId || !type || !sac_thue) return
  const examTypeMap = { mcq: 'MCQ', scenario: 'Scenario', longform: 'Longform' }
  api.getSamplePreviews({ session_id: sessionId, sac_thue, exam_type: examTypeMap[type] })
    .then(setSamplePreviews)
    .catch(() => setSamplePreviews([]))
}, [sessionId, type, sac_thue])

// In showCustom JSX, add after the question bank picker:
{samplePreviews.length > 0 && (
  <div>
    <label className="block text-sm font-medium mb-2">
      Sample Examples in Knowledge Base
      <span className="text-xs text-gray-400 font-normal ml-2">
        ({sac_thue} · {type?.toUpperCase()})
      </span>
    </label>
    <div className="space-y-2">
      {samplePreviews.map((s, i) => (
        <div key={i} className="border rounded-lg p-3 bg-gray-50 text-xs">
          <div className="flex items-center gap-2 mb-1">
            <span className="font-semibold text-gray-700">{s.name}</span>
            <span className="bg-orange-100 text-orange-700 font-semibold px-2 py-0.5 rounded">
              {s.exam_type}
            </span>
          </div>
          {s.preview && (
            <p className="text-gray-500 leading-relaxed whitespace-pre-wrap font-mono text-[11px] max-h-24 overflow-y-auto">
              {s.preview}
            </p>
          )}
        </div>
      ))}
    </div>
    <p className="text-xs text-gray-400 mt-1">
      These examples are automatically used as style references when generating.
    </p>
  </div>
)}
```

---

## Summary of file changes

| File | Change |
|---|---|
| `frontend/src/pages/Generate.jsx` | Remove "Exam Session Label" input; move Syllabus Codes into grid; replace question picker select with card list; add sample preview section |
| `frontend/src/api.js` | Add `getSamplePreviews()` |
| `backend/routes/sessions.py` | Add `GET /{session_id}/samples/preview` endpoint |
| `backend/routes/questions.py` | Return `question_type`, `sac_thue`, `snippet`, `created_at` in for-reference endpoint |
| `backend/html_renderer.py` | Add syllabus codes tags display after each question |
| `backend/prompts.py` | Add instruction to include "Syllabus items tested: [codes + names]" line in correct answer |
