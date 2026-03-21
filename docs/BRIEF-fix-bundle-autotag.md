# BRIEF: Fix Bundle — Auto-tag + Syllabus Display + Legacy KB Removal
## Repo: phanvuhoang/examsgen
## Priority: HIGH — fix existing bugs + add auto-tag feature

This brief bundles 3 things to do in one pass:
1. **Remove legacy KB Targeting** from Generate page
2. **Fix Syllabus display** (already fixed in backend, but frontend `getKBSyllabus` api call may need `tax_type` param check)
3. **Auto-suggest Syllabus Codes + RegCodes** when saving Sample Questions or generating Question Bank items

---

## PART 1: Remove Legacy KB Targeting from Generate Page

In `frontend/src/pages/Generate.jsx`, remove the **"Knowledge Base Targeting"** collapsible sub-section entirely.

**Remove:**
- The entire `<div>` block labeled "Knowledge Base Targeting" containing `KBMultiSelect` components for syllabus, regulations, and style references
- State variables: `kbSyllabusIds`, `kbRegulationIds`, `kbSampleIds`
- `kb_syllabus_ids`, `kb_regulation_ids`, `kb_sample_ids` fields from all 3 generate API calls

**Keep:**
- ✏️ Custom Instructions section (collapsed by default) — keep it
- "Base on existing question" dropdown (`reference_question_id`)
- "Paste sample or describe" textarea (`custom_instructions`)
- Refine chat section

Delete `frontend/src/components/KBMultiSelect.jsx` if it's only used in this section.

---

## PART 2: Auto-suggest Syllabus Codes + RegCodes

### Overview

When a user:
- **Generates** a question (MCQ/Scenario/Longform) → after saving to DB, auto-suggest relevant syllabus codes + reg codes based on question content
- **Adds/edits** a Sample Question → after saving, auto-suggest relevant syllabus codes + reg codes

The suggestion is **non-blocking**: question saves first, then suggestion appears as a toast/panel saying "We found X matching syllabus items — add them?"

### 2.1 New Backend Endpoint: POST /api/kb/suggest-codes

```python
@router.post("/suggest-codes")
def suggest_codes(data: dict):
    """
    Given question content (text), session_id, and tax_type,
    use AI to suggest relevant syllabus_codes and reg_codes.

    Request body:
    {
        "content": "full question text (plain text, strip HTML)",
        "tax_type": "CIT",
        "session_id": 2,
        "question_type": "MCQ"  // optional context
    }

    Returns:
    {
        "syllabus_codes": [
            {"code": "B2a", "topic": "Deductible expenses", "detail": "Identify deductible expenses...", "reason": "Question tests deductibility of salary"},
            {"code": "B2c", "topic": "Non-deductible expenses", "detail": "...", "reason": "..."}
        ],
        "reg_codes": [
            {"reg_code": "CIT-ND320-Art9-P1", "doc_ref": "Decree 320/2025", "text": "...", "reason": "..."}
        ]
    }
    """
    import re as _re

    content = data.get('content', '')
    tax_type = data.get('tax_type', '')
    session_id = data.get('session_id')
    question_type = data.get('question_type', '')

    # Strip HTML tags for cleaner AI input
    clean_content = _re.sub(r'<[^>]+>', ' ', content).strip()
    if len(clean_content) < 30:
        return {"syllabus_codes": [], "reg_codes": []}

    # Load available syllabus items for this session + tax_type
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT COALESCE(syllabus_code, section_code) as code,
                   COALESCE(topic, section_title) as topic,
                   COALESCE(detailed_syllabus, content) as detail
            FROM kb_syllabus
            WHERE session_id = %s AND COALESCE(tax_type, sac_thue) = %s
              AND COALESCE(syllabus_code, section_code) IS NOT NULL
            ORDER BY COALESCE(syllabus_code, section_code)
        """, (session_id, tax_type))
        syllabus_rows = cur.fetchall()

        # Load available reg paragraphs
        cur.execute("""
            SELECT reg_code, doc_ref, LEFT(paragraph_text, 200) as text
            FROM kb_regulation_parsed
            WHERE session_id = %s AND tax_type = %s AND is_active = TRUE
            ORDER BY reg_code
        """, (session_id, tax_type))
        reg_rows = cur.fetchall()

    if not syllabus_rows and not reg_rows:
        return {"syllabus_codes": [], "reg_codes": []}

    # Build compact lists for AI
    syllabus_list = "\n".join(f"- [{r[0]}] {r[1]}: {r[2][:100]}" for r in syllabus_rows[:60])
    reg_list = "\n".join(f"- [{r[0]}] ({r[1]}): {r[2]}" for r in reg_rows[:60])

    prompt = f"""You are an ACCA TX(VNM) exam analyst. Given a question, identify which syllabus items and regulation paragraphs it tests or references.

QUESTION ({question_type} — {tax_type}):
{clean_content[:2000]}

AVAILABLE SYLLABUS ITEMS:
{syllabus_list if syllabus_list else "(none loaded yet)"}

AVAILABLE REGULATION PARAGRAPHS:
{reg_list if reg_list else "(none loaded yet)"}

Return ONLY valid JSON (no markdown):
{{
    "syllabus_codes": [
        {{"code": "B2a", "reason": "Question directly tests deductibility of salary expenses"}}
    ],
    "reg_codes": [
        {{"reg_code": "CIT-ND320-Art9-P1", "reason": "The 5x salary cap rule is central to this question"}}
    ]
}}

Rules:
- Only suggest codes that ACTUALLY appear in the lists above
- Suggest 1-5 syllabus codes max, 0-3 reg codes max
- If nothing matches well, return empty arrays
- Be precise: only include codes directly relevant to what the question tests
"""

    result = call_ai(prompt, model_tier="fast")
    try:
        parsed = parse_ai_json(result['content'])
        suggested_codes = parsed.get('syllabus_codes', [])
        suggested_regs = parsed.get('reg_codes', [])

        # Enrich with full details from DB
        syllabus_map = {r[0]: {'topic': r[1], 'detail': r[2]} for r in syllabus_rows}
        reg_map = {r[0]: {'doc_ref': r[1], 'text': r[2]} for r in reg_rows}

        enriched_syllabus = []
        for s in suggested_codes:
            code = s.get('code', '')
            if code in syllabus_map:
                enriched_syllabus.append({
                    'code': code,
                    'topic': syllabus_map[code]['topic'],
                    'detail': syllabus_map[code]['detail'][:120],
                    'reason': s.get('reason', '')
                })

        enriched_regs = []
        for r in suggested_regs:
            rc = r.get('reg_code', '')
            if rc in reg_map:
                enriched_regs.append({
                    'reg_code': rc,
                    'doc_ref': reg_map[rc]['doc_ref'],
                    'text': reg_map[rc]['text'],
                    'reason': r.get('reason', '')
                })

        return {"syllabus_codes": enriched_syllabus, "reg_codes": enriched_regs}
    except Exception:
        return {"syllabus_codes": [], "reg_codes": []}
```

Register in `backend/routes/kb.py` (add to existing router).

Also add to `backend/main.py` if not already imported via kb router.

### 2.2 New Backend Endpoint: PATCH /api/questions/{id}/codes

To save syllabus_codes + reg_codes back to a generated question:

```python
# In backend/routes/questions.py
@router.patch("/{question_id}/codes")
def update_question_codes(question_id: int, data: dict):
    """Update syllabus_codes and reg_codes for a question."""
    syllabus_codes = data.get('syllabus_codes', [])
    reg_codes = data.get('reg_codes', [])
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "UPDATE questions SET syllabus_codes = %s, reg_codes = %s WHERE id = %s RETURNING id",
            (syllabus_codes, reg_codes, question_id)
        )
        if not cur.fetchone():
            raise HTTPException(404, "Question not found")
    return {"ok": True}
```

### 2.3 api.js — New Methods

```javascript
// Auto-suggest syllabus codes + reg codes for a question
suggestCodes: async (data) => {
  const res = await fetch('/api/kb/suggest-codes', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify(data)
  })
  if (!res.ok) return { syllabus_codes: [], reg_codes: [] }
  return res.json()
},

// Save codes back to a generated question
updateQuestionCodes: async (questionId, { syllabus_codes, reg_codes }) => {
  const res = await fetch(`/api/questions/${questionId}/codes`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ syllabus_codes, reg_codes })
  })
  return res.ok
},
```

### 2.4 Generate Page — Suggestion Panel After Generation

After a question is successfully generated and displayed, trigger auto-suggest **in the background** (non-blocking).

Add state:
```javascript
const [suggestions, setSuggestions] = useState(null)      // null = not loaded, {} = loaded
const [suggestLoading, setSuggestLoading] = useState(false)
const [savedCodes, setSavedCodes] = useState(false)
const [lastQuestionId, setLastQuestionId] = useState(null)
```

After `setResult(data)` in the generate success handler, also:
```javascript
setLastQuestionId(data.question_id)  // make sure _save_question returns and API returns question_id
setSuggestions(null)
setSavedCodes(false)
setSuggestLoading(true)

// Run suggestion in background — don't await in the main flow
api.suggestCodes({
  content: data.content_html || '',
  tax_type: sacThue,
  session_id: currentSessionId,
  question_type: type
}).then(s => {
  setSuggestions(s)
  setSuggestLoading(false)
}).catch(() => setSuggestLoading(false))
```

**Make sure generate endpoints return `question_id`** in response. In `backend/routes/generate.py`, update `_save_question` usage to include `question_id` in the return payload:
```python
# In each generate route handler, after saving:
q_id = _save_question(...)
return {
    ...existing fields...,
    "question_id": q_id   # ADD THIS
}
```

Suggestion UI — add below the question result, above the Refine chat:
```jsx
{/* Syllabus + RegCode Suggestions */}
{result && (
  <div className="mt-4 border rounded-xl overflow-hidden shadow-sm">
    <div className="bg-amber-50 px-4 py-2 border-b flex items-center gap-2">
      <span className="text-sm font-semibold text-amber-700">🏷️ Suggested Tags</span>
      <span className="text-xs text-amber-500">AI-detected syllabus & regulation references</span>
      {suggestLoading && <span className="text-xs text-gray-400 ml-auto animate-pulse">Analysing...</span>}
    </div>

    {!suggestLoading && suggestions && (
      <div className="p-4 space-y-3">
        {/* Syllabus codes */}
        {suggestions.syllabus_codes?.length > 0 && (
          <div>
            <p className="text-xs font-medium text-gray-600 mb-1">Syllabus Items</p>
            <div className="flex flex-wrap gap-2">
              {suggestions.syllabus_codes.map(s => (
                <div key={s.code} className="group relative">
                  <span className="inline-flex items-center px-2 py-1 bg-blue-50 border border-blue-200 rounded text-xs font-mono text-blue-700">
                    {s.code}
                    {/* Tooltip on hover */}
                    <span className="hidden group-hover:block absolute bottom-full left-0 mb-1 w-64 bg-gray-800 text-white text-xs rounded p-2 z-10 shadow-lg">
                      <strong>{s.topic}</strong><br/>{s.detail}<br/><em className="text-gray-300">{s.reason}</em>
                    </span>
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Reg codes */}
        {suggestions.reg_codes?.length > 0 && (
          <div>
            <p className="text-xs font-medium text-gray-600 mb-1">Regulation Paragraphs</p>
            <div className="flex flex-wrap gap-2">
              {suggestions.reg_codes.map(r => (
                <div key={r.reg_code} className="group relative">
                  <span className="inline-flex items-center px-2 py-1 bg-green-50 border border-green-200 rounded text-xs font-mono text-green-700">
                    {r.reg_code}
                    <span className="hidden group-hover:block absolute bottom-full left-0 mb-1 w-64 bg-gray-800 text-white text-xs rounded p-2 z-10 shadow-lg">
                      <strong>{r.doc_ref}</strong><br/>{r.text}<br/><em className="text-gray-300">{r.reason}</em>
                    </span>
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {suggestions.syllabus_codes?.length === 0 && suggestions.reg_codes?.length === 0 && (
          <p className="text-xs text-gray-400">No matching syllabus or regulation references found. Upload syllabus/regulations in Knowledge Base first.</p>
        )}

        {/* Save button — only show if there are suggestions and not yet saved */}
        {(suggestions.syllabus_codes?.length > 0 || suggestions.reg_codes?.length > 0) && !savedCodes && (
          <div className="pt-2 border-t">
            <button
              onClick={async () => {
                await api.updateQuestionCodes(lastQuestionId, {
                  syllabus_codes: suggestions.syllabus_codes.map(s => s.code),
                  reg_codes: suggestions.reg_codes.map(r => r.reg_code)
                })
                setSavedCodes(true)
              }}
              className="px-3 py-1.5 bg-[#028a39] text-white rounded text-xs font-medium hover:bg-[#027a32]"
            >
              ✓ Save these tags to question
            </button>
            <button
              onClick={() => setSuggestions({ syllabus_codes: [], reg_codes: [] })}
              className="ml-2 px-3 py-1.5 text-gray-500 text-xs hover:text-gray-700"
            >
              Dismiss
            </button>
          </div>
        )}
        {savedCodes && <p className="text-xs text-green-600">✓ Tags saved to question</p>}
      </div>
    )}
  </div>
)}
```

### 2.5 Sample Questions Page — Suggestion on Save

In `frontend/src/pages/SampleQuestions.jsx` (or wherever the add/edit form is):

After successfully creating or updating a sample question, trigger suggestion:

```javascript
const handleSave = async () => {
  // ... existing save logic ...
  const saved = await api.createSampleQuestion(formData)  // or updateSampleQuestion
  
  // Trigger suggestion in background
  api.suggestCodes({
    content: formData.content + ' ' + (formData.answer || ''),
    tax_type: formData.tax_type,
    session_id: currentSessionId,
    question_type: formData.question_type
  }).then(suggestions => {
    if (suggestions.syllabus_codes?.length > 0 || suggestions.reg_codes?.length > 0) {
      // Show inline suggestion in the form or as a toast
      setSuggestionsForItem(saved.id, suggestions)
    }
  })
}
```

Show suggestions as a panel inside the add/edit modal, with the same chip UI as Generate page. User can accept/dismiss before closing the modal.

Add a `PATCH /api/sample-questions/{id}/codes` endpoint (same pattern as questions):
```python
@router.patch("/{item_id}/codes")
def update_sample_question_codes(item_id: int, data: dict):
    """Update syllabus_codes and reg_codes for a sample question."""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "UPDATE sample_questions SET syllabus_codes = %s, reg_codes = %s WHERE id = %s RETURNING id",
            (data.get('syllabus_codes', []), data.get('reg_codes', []), item_id)
        )
        if not cur.fetchone():
            raise HTTPException(404, "Not found")
    return {"ok": True}
```

### 2.6 Question Bank — Show + Filter by Tags

In `frontend/src/pages/QuestionBank.jsx`:

**Show tags** on each question card:
```jsx
{/* Below question preview text */}
{item.syllabus_codes?.length > 0 && (
  <div className="flex flex-wrap gap-1 mt-1">
    {item.syllabus_codes.map(c => (
      <span key={c} className="px-1.5 py-0.5 bg-blue-50 text-blue-600 text-xs font-mono rounded border border-blue-100">{c}</span>
    ))}
    {item.reg_codes?.map(c => (
      <span key={c} className="px-1.5 py-0.5 bg-green-50 text-green-600 text-xs font-mono rounded border border-green-100">{c}</span>
    ))}
  </div>
)}
```

**Add filter** by syllabus code:
```jsx
{/* In filter bar */}
<input
  placeholder="Filter by syllabus code... e.g. B2a"
  value={syllabusFilter}
  onChange={e => setSyllabusFilter(e.target.value)}
  className="border rounded-lg px-3 py-2 text-sm w-40"
/>
```

Pass `syllabus_code` filter to `GET /api/questions`:
```
GET /api/questions?syllabus_code=B2a
```

Update `backend/routes/questions.py` GET list to support this filter:
```python
if syllabus_code:
    query += " AND syllabus_codes @> %s"
    params.append([syllabus_code])
```

Same for Sample Questions page — already has `syllabus_code` filter in backend, just wire up the UI.

---

## PART 3: Return question_id from Generate Endpoints

In `backend/routes/generate.py`, all 3 generate handlers (`/mcq`, `/scenario`, `/longform`) — add `question_id` to the return dict:

```python
# After q_id = _save_question(...)
return {
    "content_json": content,
    "content_html": content_html,
    "question_id": q_id,          # ← ADD THIS
    "model_used": result["model"],
    "provider_used": result["provider"],
    # ... other existing fields
}
```

---

## SUMMARY — Files to Create/Modify

| Action | File | Change |
|--------|------|--------|
| MODIFY | `backend/routes/kb.py` | Add `POST /suggest-codes` endpoint |
| MODIFY | `backend/routes/questions.py` | Add `PATCH /{id}/codes`, add `syllabus_code` filter to GET list |
| MODIFY | `backend/routes/sample_questions.py` | Add `PATCH /{id}/codes` endpoint |
| MODIFY | `backend/routes/generate.py` | Return `question_id` in all 3 generate responses |
| MODIFY | `frontend/src/api.js` | Add `suggestCodes`, `updateQuestionCodes` methods |
| MODIFY | `frontend/src/pages/Generate.jsx` | Remove legacy KB Targeting; add suggestion panel after result |
| MODIFY | `frontend/src/pages/SampleQuestions.jsx` | Add suggestion trigger on save; show suggestion chips in modal |
| MODIFY | `frontend/src/pages/QuestionBank.jsx` | Show syllabus/reg code chips on cards; add syllabus_code filter |
| DELETE | `frontend/src/components/KBMultiSelect.jsx` | Remove if unused |

---

## IMPORTANT NOTES FOR CLAUDE CODE

1. **Suggestion is non-blocking** — question saves first, suggestion runs async in background. Never block the save on suggestion.
2. **Suggestion only works if KB has data** — if `kb_syllabus` or `kb_regulation_parsed` is empty for that session+tax_type, return empty arrays gracefully (no error).
3. **HTML stripping** — strip HTML tags from content before sending to AI for suggestion. Use regex `re.sub(r'<[^>]+>', ' ', html)`.
4. **Tooltip on hover** — use `group-hover:block` Tailwind pattern for tooltip. Make sure `overflow-visible` on parent if needed.
5. **question_id in generate response** — all 3 endpoints (mcq, scenario, longform) must return it.
6. **Save tags button** — only show if there are suggestions AND `savedCodes` is false. After saving, show "✓ Tags saved" text instead.
7. **Reset suggestion state** when user generates a new question — reset `suggestions`, `savedCodes`, `lastQuestionId` to null/false.
8. **Syllabus filter in Question Bank** — filter by `syllabus_codes @> ARRAY['B2a']` (PostgreSQL array contains operator).
9. **brand color** is `#028a39` for all primary action buttons.
