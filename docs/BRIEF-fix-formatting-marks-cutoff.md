# BRIEF: Fix Formatting, Mark Structure, Answer Style & Cut-off Date

**Date:** 2026-03-25  
**Priority:** HIGH  
**Scope:** Backend (prompts.py, html_renderer.py, routes/sessions.py, database), Frontend (Generate.jsx, QuestionBank.jsx, index.css, Sessions page)

---

## Overview

Four fixes requested by the examiner (anh Hoàng):

1. **Rich formatting** in question/answer display (both Generate tab and Question Bank modal)
2. **Correct mark granularity** — minimum 0.5 mark per point; keep question complexity appropriate
3. **Concise answers with compact calculations** — tables where relevant; no verbose step-by-step
4. **Cut-off date field** — replace/extend "Exam date" with a `cutoff_date` field; scenarios use the year of that date

---

## Fix 1: Rich Formatting (HTML Renderer + CSS)

### Problem
`html_renderer.py` renders plain text inside `<p>` tags. AI-generated answers contain:
- Newlines that need `<br>` or paragraphs
- Calculation rows like `Annual salary = 50 mil × 9 = 450 mil (0.5 marks)` that should be table rows
- No visual separation between question, options, answer, marking scheme sections

### Changes required

#### `backend/html_renderer.py`

Rewrite `_render_mcq()` and `_render_scenario()` to:

1. **Convert newlines to HTML** — replace `\n` with `<br>` inside all text fields (scenario, question, answer, explanation, mark points)
2. **Auto-detect calculation tables** — if an answer string contains ≥ 2 lines matching pattern `[text] = [formula/number] [unit] ([marks])` or `[text] = [numbers] = [result]`, render them as an HTML table:
   ```html
   <table class="calc-table">
     <tr><td>Annual salary</td><td>50 mil × 9 months</td><td>= 450 mil</td><td class="marks">0.5 marks</td></tr>
   </table>
   ```
3. **Render answer section properly**:
   - Use `<div class="answer-block">` instead of bare `<p>`
   - Each `marking_scheme` point as `<div class="mark-point">` with mark pill
   - Regulation refs in a styled `<div class="refs">`
4. **MCQ options** — each option in its own `<div class="option">`, correct answer highlighted with ✓, wrong options with explanation on expand
5. **Question Bank modal** — already uses `dangerouslySetInnerHTML={{ __html: viewing.content_html }}`, so improved renderer will automatically fix it

#### `frontend/src/index.css`

Add styles for new classes:

```css
/* Calculation table */
.question-html .calc-table {
  @apply w-full border-collapse my-3 text-sm;
}
.question-html .calc-table td {
  @apply border border-gray-200 px-3 py-1.5;
}
.question-html .calc-table .marks {
  @apply text-right font-semibold text-brand-600 whitespace-nowrap w-24;
}

/* Answer block */
.question-html .answer-block {
  @apply mt-3 p-4 bg-gray-50 rounded-lg border-l-4 border-brand-400 text-sm;
}

/* Mark point pill */
.question-html .mark-point {
  @apply flex items-start gap-2 py-1 text-gray-700;
}
.question-html .mark-pill {
  @apply shrink-0 bg-brand-100 text-brand-700 text-xs font-bold px-2 py-0.5 rounded-full;
}

/* Option rows */
.question-html .option {
  @apply py-1.5 px-3 my-1 rounded border border-transparent;
}
.question-html .option.correct {
  @apply bg-green-50 border-l-4 border-brand-500;
}
.question-html .option.wrong {
  @apply text-gray-600;
}

/* Section headers inside question */
.question-html .section-label {
  @apply text-xs font-bold uppercase tracking-widest text-gray-400 mt-4 mb-1;
}
```

---

## Fix 2: Correct Mark Granularity in Prompts

### Problem
AI generates questions that are too complex for their mark allocation. The rule is:

- **Minimum 0.5 mark per point answered**
- 2-mark MCQ examples:
  - 4 small calculation points × 0.5 marks = 2 marks ✓
  - 2 large points × 1 mark = 2 marks ✓  
  - 1 large point × 1 mark + 2 small × 0.5 marks = 2 marks ✓
- Do NOT create 6–8-step calculation for a 2-mark question

### Changes required

#### `backend/prompts.py` — update MCQ_PROMPT

Replace the current REQUIREMENTS block with:

```
MARK ALLOCATION RULES (CRITICAL):
- Minimum 0.5 mark per answerable point
- A 2-mark MCQ should have EITHER:
  (a) 4 small calculation/identification points × 0.5 marks each, OR
  (b) 2 medium calculation points × 1 mark each, OR
  (c) 1 large calculation point (1 mark) + 2 small points (0.5 marks each)
- DO NOT create a question requiring 6+ calculation steps for only 2 marks
- The scenario MUST be solvable in ≤ 4 calculation steps total
- Keep fact patterns concise — 3-5 data points per MCQ, not 8-10
```

#### `backend/prompts.py` — update SCENARIO_PROMPT and LONGFORM_PROMPT

Add after STRUCTURE block:

```
MARK GRANULARITY RULES:
- Minimum 0.5 mark per answerable point
- Each sub-question's mark allocation must match its actual complexity
- Example for a 3-mark sub-question:
  - 3 steps × 1 mark each, OR
  - 2 steps × 1 mark + 2 items × 0.5 mark, OR
  - 6 items × 0.5 mark each
- Do not assign 1 mark to a trivial identification step that takes 5 seconds
- Do not require 10 calculation steps for a 2-mark question
```

---

## Fix 3: Concise Answers with Compact Calculations

### Problem
Current prompts demand verbose step-by-step working ("Step 1: [describe what you are calculating] → VND X million"). This creates answers that are too long and hard to read. The examiner wants concise answers in the style of ACCA marking schemes.

### Target style
```
Annual salary = 50 mil × 9 months = 450 mil                           (0.5 marks)
Less: Insurance deduction (statutory cap) = 4.5 mil                   (0.5 marks)
Taxable income = 450 − 4.5 = 445.5 mil                                (1 mark)
```
Or as a table when multiple rows:
| Item | Calculation | Amount (mil VND) | Marks |
|------|-------------|-----------------|-------|
| Annual salary | 50 × 9 | 450 | 0.5 |
| Less: Insurance | cap 4.5 | (4.5) | 0.5 |
| **Taxable income** | 450 − 4.5 | **445.5** | 1 |

### Changes required

#### `backend/prompts.py` — replace the step-by-step instruction in ALL THREE prompts

Remove all occurrences of:
```
- For any question involving calculations, include explicit step-by-step workings in the answer:
  Step 1: [describe what you are calculating] → VND X million
  Step 2: [next step] → VND Y million
  Final answer: VND Z million
- Each calculation step must show the formula, the numbers substituted, and the result
```

Replace with this in ALL THREE prompts (MCQ_PROMPT, SCENARIO_PROMPT, LONGFORM_PROMPT):
```
ANSWER FORMAT RULES:
- Answers must be CONCISE and CLEAR — like official ACCA marking schemes
- Show calculations inline: "Annual salary = 50 mil × 9 months = 450 mil (0.5 marks)"
- When ≥ 3 calculation rows exist, use a markdown table:
  | Item | Calculation | Amount (mil VND) | Marks |
  |------|-------------|-----------------|-------|
  | Annual salary | 50 × 9 | 450 | 0.5 |
- Each row = one mark point. Show mark allocation per row/point (e.g. 0.5 marks, 1 mark)
- DO NOT write verbose paragraphs explaining each step
- DO NOT write "Step 1:", "Step 2:" etc.
- Final answer line should be bolded or clearly marked
- For MCQ wrong options: one short sentence explaining the mistake (e.g. "Wrong rate applied: used 20% instead of 22%")
- Cite regulation reference on a separate line at the end: "Ref: Article X, Decree Y"
```

#### For MCQ JSON schema — update the `working` field description in the prompt:

Change:
```json
"working": "Step 1: [formula + numbers] → VND X million\nStep 2: [next step] → VND Y million\nFinal answer: VND Z million"
```
To:
```json
"working": "Annual salary = 50 mil × 9 = 450 mil (0.5 mk)\nLess insurance = 4.5 mil (0.5 mk)\nNet = 445.5 mil (1 mk)"
```

---

## Fix 4: Cut-off Date Field for Exam Sessions

### Problem
The "Exam date" field (e.g. "Jun2026") is only used as a label in the exam. There is no field that tells the AI "scenarios should happen in year 2025, regulations applicable as of 31 December 2025." The examiner wants:

- A `cutoff_date` field (e.g. `31 December 2025`)
- Scenarios in the generated question happen **within the tax year of the cutoff date** (e.g. if cutoff = 31 Dec 2025 → scenarios use year 2025)
- "Assumed today's date" in the question intro should be 1-2 months after cutoff (e.g. cutoff = 31 Dec 2025 → assumed date = "1 February 2026")

### Changes required

#### Database migration

```sql
ALTER TABLE exam_sessions ADD COLUMN IF NOT EXISTS cutoff_date VARCHAR(50);
```
Example values: `"31 December 2025"`, `"30 June 2026"`

#### `backend/routes/sessions.py`

Update `SessionCreate` and `SessionUpdate` Pydantic models:
```python
class SessionCreate(BaseModel):
    name: str
    exam_date: Optional[str] = None       # e.g. "Jun2026" (label only)
    assumed_date: Optional[str] = None    # e.g. "1 June 2026" (assumed today in scenario intro)
    cutoff_date: Optional[str] = None     # NEW: e.g. "31 December 2025"
```

Update `list_sessions()` SELECT to include `cutoff_date`.

Update `create_session()` INSERT to include `cutoff_date`.

Update `update_session()` to allow patching `cutoff_date`.

#### `backend/context_builder.py` (or wherever session vars are assembled for prompts)

When building the prompt, derive the `tax_year` from `cutoff_date`:
```python
# If cutoff_date = "31 December 2025", tax_year = "2025"
# If cutoff_date = "30 June 2026", tax_year = "2026"
import re
def get_tax_year_from_cutoff(cutoff_date: str) -> str:
    match = re.search(r'(20\d{2})', cutoff_date or '')
    return match.group(1) if match else ''
```

Inject into prompts as session vars:
```
CUTOFF DATE: {cutoff_date}  (regulations applicable as of this date)
TAX YEAR: {tax_year}        (scenarios happen in this calendar year)
ASSUMED TODAY: {assumed_date}  (use as "You should assume today is..." in scenario intro)
```

#### `backend/prompts.py`

In `{session_vars}` block (built by `context_builder.py`), ensure the cutoff + tax year instruction appears. Also update the hardcoded example in SCENARIO_PROMPT and LONGFORM_PROMPT:

Change:
```json
"scenario": "You should assume today is 1 February 2026. ..."
```
To use the injected `{assumed_date}`:
```json
"scenario": "You should assume today is {assumed_date}. All transactions occur in tax year {tax_year}. ..."
```

Add to REQUIREMENTS/STRUCTURE in all three prompts:
```
TIMELINE RULES:
- All scenarios, transactions, and company data occur in tax year {tax_year}
- Apply regulations that were effective as of {cutoff_date}
- Opening line of scenario: "You should assume today is {assumed_date}."
- Do NOT reference events in {tax_year_plus_1} or later unless asking about future obligations
```
Where `{tax_year_plus_1}` = tax_year + 1 (e.g. 2026 if cutoff is 2025).

#### Frontend — Sessions page (Settings or wherever sessions are managed)

Add `cutoff_date` input field alongside existing `exam_date` and `assumed_date` fields:
- Label: **"Cut-off Date"**
- Placeholder: `e.g. 31 December 2025`
- Help text: `"Regulations applicable as of this date. Scenarios use this tax year."`

Show `cutoff_date` in the session dropdown label if set:
```
Jun2026 — cutoff: 31 Dec 2025
```

#### Frontend — Generate.jsx

When a session is selected and has `cutoff_date`, show a small info badge below the session selector:
```
📅 Tax year: 2025 | Cut-off: 31 Dec 2025 | Assumed today: 1 Feb 2026
```

---

## Summary of Files to Change

| File | Change |
|------|--------|
| `backend/prompts.py` | (1) Replace step-by-step with concise answer format; (2) Add mark granularity rules; (3) Add timeline/cutoff rules in session_vars section |
| `backend/html_renderer.py` | Rewrite both renderers for rich formatting: newlines→html, calc tables, mark pills, styled sections |
| `backend/routes/sessions.py` | Add `cutoff_date` to models + SQL queries |
| `backend/context_builder.py` | Inject `cutoff_date`, `tax_year`, `assumed_date` into prompt session_vars |
| `frontend/src/index.css` | Add styles for calc-table, answer-block, mark-pill, option, section-label |
| `frontend/src/pages/Generate.jsx` | Show cutoff date info badge when session has cutoff_date |
| `frontend/src/pages/Sessions.jsx` (or Settings) | Add cutoff_date input field |
| DB migration | `ALTER TABLE exam_sessions ADD COLUMN cutoff_date VARCHAR(50)` |

---

## Testing Checklist

After implementation, verify:

- [ ] Generate an MCQ → question text and answer display with proper formatting (no raw `\n`)
- [ ] MCQ with 3+ calculation rows → renders as a table
- [ ] MCQ 2-mark question → answer has ≤ 4 calculation points, each with 0.5 or 1 mark
- [ ] Scenario question → marking scheme shows mark pills per point
- [ ] Question Bank modal → same rich formatting applies
- [ ] Create session with cutoff_date "31 December 2025" → info badge shows "Tax year: 2025"
- [ ] Generate question with that session → scenario intro says "today is 1 February 2026" and all transactions are in 2025
- [ ] Export to Word still works after renderer changes

---

*Brief written by Thanh (AI agent) — 2026-03-25*
