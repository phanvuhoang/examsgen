# BRIEF: Custom Instructions for Generate Page

## Feature Overview

Add a "Custom Instructions" section to the Generate page, giving users 3 ways to guide question generation:

1. **Pick from Question Bank** — select an existing question as style reference
2. **Paste Sample** — paste any Q&A text as a style/content reference  
3. **Describe in own words** — free-text box (English or Vietnamese) to describe what question to generate

Options 2 and 3 are combined into ONE textarea (paste sample OR describe — whichever the user wants).

---

## UI Changes — Generate.jsx

Add a collapsible section below the existing options, labeled:

```
✏️ Custom Instructions (optional)
```

When expanded, show:

### Section A: "Base on existing question"
```
[ ] Use a question from the bank as style reference
    ↓ (if checked, show dropdown)
    [Select question... ▼]  — searchable dropdown, shows: "Q1 CIT — ABC JSC scenario (2026-03-15)"
```

### Section B: "Paste sample or describe"
```
Label: "Sample question or description"
Hint:  "Paste a Q&A you want to replicate, OR describe the question you want in English/Vietnamese"
       Large textarea (8 rows)
       Placeholder: "E.g: 'Write a Q1 CIT question about a manufacturing company with deductible expense issues and a loss carry-forward scenario'
       Or paste a complete sample question here..."
```

Both A and B are optional and independent — user can use one, both, or neither.

---

## Backend Changes

### 1. models.py — add fields to all 3 request models

```python
class MCQGenerateRequest(BaseModel):
    ...existing fields...
    reference_question_id: Optional[int] = None   # question bank id
    custom_instructions: Optional[str] = None      # pasted sample OR free description

class ScenarioGenerateRequest(BaseModel):
    ...existing fields...
    reference_question_id: Optional[int] = None
    custom_instructions: Optional[str] = None

class LongformGenerateRequest(BaseModel):
    ...existing fields...
    reference_question_id: Optional[int] = None
    custom_instructions: Optional[str] = None
```

### 2. New API endpoint — GET /api/questions/for-reference

Returns a lightweight list of questions for the dropdown:
```json
[
  {
    "id": 42,
    "label": "MCQ CIT — 3 questions (2026-03-15)",
    "question_type": "MCQ",
    "sac_thue": "CIT",
    "created_at": "2026-03-15T10:30:00"
  }
]
```

Filter by same `question_type` and `sac_thue` as the current generate request (pass as query params: `?type=MCQ&sac_thue=CIT`).

### 3. context_builder.py — load reference content

```python
def get_reference_content(reference_question_id: int = None, custom_instructions: str = None) -> str:
    """Build the custom instructions block to inject into prompt."""
    parts = []
    
    if reference_question_id:
        # Load from DB
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("SELECT content_json, question_type, sac_thue FROM questions WHERE id = %s", 
                       (reference_question_id,))
            row = cur.fetchone()
        if row:
            content = json.loads(row[0]) if isinstance(row[0], str) else row[0]
            # Convert JSON back to readable text for the prompt
            ref_text = format_question_as_text(content)
            parts.append(f"REFERENCE QUESTION (write a NEW question with SIMILAR style, structure and difficulty):\n{ref_text}")
    
    if custom_instructions:
        # Could be a pasted sample or a description — inject as-is
        # Detect if it looks like a pasted question (long, contains "Answer" or "VND") 
        # vs a description (short, instructional)
        if len(custom_instructions) > 300 and any(kw in custom_instructions for kw in ['Answer', 'VND', 'marks', 'Calculate']):
            parts.append(f"SAMPLE TO REPLICATE (write a NEW question with SIMILAR style, structure, difficulty and topic):\n{custom_instructions}")
        else:
            parts.append(f"SPECIFIC INSTRUCTIONS FROM EXAMINER:\n{custom_instructions}")
    
    return "\n\n".join(parts)
```

### 4. prompts.py — inject custom instructions block

Add `{custom_instructions}` placeholder to ALL 3 prompt templates (MCQ_PROMPT, SCENARIO_PROMPT, LONGFORM_PROMPT), placed just before "Generate now":

```
{custom_instructions}

Generate {count} NEW question(s) now:
```

When `custom_instructions` is empty string, it renders as nothing (no extra whitespace).

### 5. routes/generate.py — wire it up

In each route handler, after building `prompt`:

```python
# Build custom instructions block
from backend.context_builder import get_reference_content

custom_block = get_reference_content(
    reference_question_id=req.reference_question_id,
    custom_instructions=req.custom_instructions
)

prompt = MCQ_PROMPT.format(
    ...existing fields...,
    custom_instructions=custom_block,
)
```

---

## Frontend Changes — Generate.jsx

### State additions
```javascript
const [showCustom, setShowCustom] = useState(false)
const [referenceId, setReferenceId] = useState('')
const [customInstructions, setCustomInstructions] = useState('')
const [referenceOptions, setReferenceOptions] = useState([])
```

### Load reference options when type/sac_thue changes
```javascript
useEffect(() => {
  if (type && sac_thue) {
    api.getQuestionsForReference({ type, sac_thue })
       .then(setReferenceOptions)
       .catch(() => {})
  }
}, [type, sac_thue])
```

### UI section (add after existing options, before Generate button)

```jsx
<div className="border-t pt-4 mt-4">
  <button
    onClick={() => setShowCustom(!showCustom)}
    className="flex items-center gap-2 text-sm font-medium text-gray-600 hover:text-gray-900"
  >
    <span>{showCustom ? '▼' : '▶'}</span>
    ✏️ Custom Instructions (optional)
  </button>

  {showCustom && (
    <div className="mt-3 space-y-4">
      
      {/* Section A: Pick from bank */}
      {referenceOptions.length > 0 && (
        <div>
          <label className="block text-sm font-medium mb-1">
            Base on question from bank
          </label>
          <select
            value={referenceId}
            onChange={(e) => setReferenceId(e.target.value)}
            className="w-full border rounded-lg px-3 py-2 text-sm"
          >
            <option value="">— None —</option>
            {referenceOptions.map(q => (
              <option key={q.id} value={q.id}>{q.label}</option>
            ))}
          </select>
        </div>
      )}

      {/* Section B: Paste or describe */}
      <div>
        <label className="block text-sm font-medium mb-1">
          Paste a sample or describe what you want
        </label>
        <textarea
          value={customInstructions}
          onChange={(e) => setCustomInstructions(e.target.value)}
          rows={6}
          className="w-full border rounded-lg px-3 py-2 text-sm resize-y"
          placeholder={
            "Paste a complete Q&A to replicate its style...\n\nOR describe in English/Vietnamese:\n" +
            "'Write a Q1 CIT scenario about a manufacturing company with issues on deductible expenses, depreciation of a leased machine, and a tax loss carry-forward from prior year.'"
          }
        />
        <p className="text-xs text-gray-400 mt-1">
          Supports English and Vietnamese. Paste a question to replicate, or describe in your own words.
        </p>
      </div>

    </div>
  )}
</div>
```

### Pass to API calls
Add to all 3 `api.generateXxx()` calls:
```javascript
reference_question_id: referenceId ? parseInt(referenceId) : null,
custom_instructions: customInstructions || null,
```

---

## api.js — add getQuestionsForReference

```javascript
getQuestionsForReference: async ({ type, sac_thue }) => {
  const params = new URLSearchParams({ type, sac_thue })
  const res = await fetch(`/api/questions/for-reference?${params}`, { headers: authHeaders() })
  if (!res.ok) return []
  return res.json()
},
```

---

## Notes

- Custom Instructions section is **collapsed by default** — don't clutter the UI
- When `reference_question_id` is set AND `custom_instructions` is also set → inject BOTH into prompt (they complement each other)
- `format_question_as_text()` helper: convert the stored JSON back to readable plain text (scenario + questions + answers) — don't dump raw JSON into the prompt
- If question bank is empty, hide "Base on question from bank" dropdown entirely
- Keep existing `topics` field working independently alongside these new fields
