# BRIEF: ExamsGen v2 — Major Redesign
## Repo: phanvuhoang/examsgen
## Context: Extending existing working app — do NOT rebuild from scratch

This brief covers a significant expansion of ExamsGen. Build incrementally, test each section before moving on.

---

## PART 1: EXAM SESSION SETTINGS — Extended Schema

### 1.1 New DB columns for `exam_sessions`

```sql
-- Economic parameters (key-value pairs, flexible)
ALTER TABLE exam_sessions ADD COLUMN IF NOT EXISTS parameters JSONB DEFAULT '[]';
-- e.g. [{"key": "USD Exchange Rate", "value": "26500", "unit": "VND"}, {"key": "Monthly Base Salary (SHUI)", "value": "46800000", "unit": "VND"}]

-- Tax types for this session (array of objects)
ALTER TABLE exam_sessions ADD COLUMN IF NOT EXISTS tax_types JSONB DEFAULT '[]';
-- e.g. [{"code": "CIT", "name": "Corporate Income Tax"}, {"code": "PIT", ...}]

-- Question types for this session (array of objects)
ALTER TABLE exam_sessions ADD COLUMN IF NOT EXISTS question_types JSONB DEFAULT '[]';
-- e.g. [
--   {"code": "MCQ", "name": "Multiple Choice", "subtypes": [
--     {"code": "MCQ-1", "name": "Single correct answer", "description": "...", "sample": "..."},
--     {"code": "MCQ-N", "name": "Multiple correct answers", "description": "...", "sample": "..."},
--     {"code": "MCQ-FIB", "name": "Fill in the blank (words)", "description": "...", "sample": "..."}
--   ]},
--   {"code": "SCENARIO", "name": "Scenario Question", "subtypes": []},
--   {"code": "LONGFORM", "name": "Long-form Question", "subtypes": []}
-- ]
```

**Default values to seed** for new sessions:
```python
DEFAULT_TAX_TYPES = [
    {"code": "CIT", "name": "Corporate Income Tax"},
    {"code": "PIT", "name": "Personal Income Tax"},
    {"code": "FCT", "name": "Foreign Contractor Tax"},
    {"code": "VAT", "name": "Value Added Tax"},
    {"code": "TAX-ADMIN", "name": "Tax Administration"},
    {"code": "TP", "name": "Transfer Pricing"},
]

DEFAULT_QUESTION_TYPES = [
    {"code": "MCQ", "name": "Multiple Choice", "subtypes": [
        {"code": "MCQ-1", "name": "Single correct answer", "description": "One correct answer out of 4 options. Distractor options must be plausible.", "sample": ""},
        {"code": "MCQ-N", "name": "Multiple correct answers", "description": "Two or more correct answers. Candidates select all that apply.", "sample": ""},
        {"code": "MCQ-FIB", "name": "Fill in the blank (words)", "description": "Candidate fills in missing word(s) in a statement. Provide a word bank.", "sample": ""},
    ]},
    {"code": "SCENARIO", "name": "Scenario Question (10-15 marks)", "subtypes": []},
    {"code": "LONGFORM", "name": "Long-form Question (15-25 marks)", "subtypes": []},
]

DEFAULT_PARAMETERS = [
    {"key": "USD Exchange Rate", "value": "26500", "unit": "VND"},
    {"key": "Monthly Base Salary (SHUI)", "value": "46800000", "unit": "VND"},
]
```

### 1.2 Clone session — carry forward ALL settings + KB

When cloning a session (existing `/api/sessions/{id}/clone-from/{source_id}`):
- Copy `parameters`, `tax_types`, `question_types` from source
- Copy all KB items (kb_syllabus, kb_regulation_parsed, kb_tax_rates, kb_sample rows)
- Copy uploaded files via `shutil.copytree`
- User can then edit/add/delete anything in the cloned session

### 1.3 Sessions Page UI — Settings Panel

In the Session detail/edit view, add 3 collapsible sections:

#### Section A: Economic Parameters
```
Economic Parameters                              [+ Add Parameter]
┌─────────────────────────────────────────────────────────────┐
│ USD Exchange Rate        [ 26,500    ]  VND    [Edit] [✕]  │
│ Monthly Base Salary SHUI [ 46,800,000]  VND    [Edit] [✕]  │
│ [+ Add custom parameter]                                    │
└─────────────────────────────────────────────────────────────┘
```
Each row: key (text input), value (number input), unit (text input, optional), delete button.
[+ Add Parameter] appends a new blank row.

#### Section B: Tax Types
```
Tax Types                                        [+ Add Tax Type]
┌─────────────────────────────────────────────────────────────┐
│ CIT   Corporate Income Tax       [Edit] [✕]                │
│ PIT   Personal Income Tax        [Edit] [✕]                │
│ FCT   Foreign Contractor Tax     [Edit] [✕]                │
│ VAT   Value Added Tax            [Edit] [✕]                │
│ TAX-ADMIN  Tax Administration    [Edit] [✕]                │
│ TP    Transfer Pricing           [Edit] [✕]                │
└─────────────────────────────────────────────────────────────┘
```
[+ Add Tax Type] → inline form: code (short, e.g. "SCT"), name (full name).
[Edit] → inline edit. [✕] → delete with confirm if KB items exist for this type.

#### Section C: Question Types
```
Question Types                                   [+ Add Question Type]
┌─────────────────────────────────────────────────────────────┐
│ ▼ MCQ — Multiple Choice                    [Edit] [✕]      │
│   ├─ MCQ-1: Single correct answer          [Edit] [✕]      │
│   ├─ MCQ-N: Multiple correct answers       [Edit] [✕]      │
│   ├─ MCQ-FIB: Fill in the blank            [Edit] [✕]      │
│   └─ [+ Add MCQ subtype]                                   │
│                                                            │
│ ▶ SCENARIO — Scenario Question            [Edit] [✕]      │
│ ▶ LONGFORM — Long-form Question           [Edit] [✕]      │
└─────────────────────────────────────────────────────────────┘
```
[Edit] on a question type or subtype → modal with fields:
- Code (readonly after creation)
- Name
- Description (textarea — describe how this question type works)
- Sample (rich text editor — paste or write a sample question in this format)

[+ Add Question Type] → creates a new top-level type.
[+ Add MCQ subtype] → creates a subtype under MCQ (or any parent type).

**Save button** at bottom of entire settings panel → PATCH `/api/sessions/{id}` with updated parameters/tax_types/question_types.

---

## PART 2: KNOWLEDGE BASE — Restructured (3 Tabs)

Knowledge Base page (`/kb`) now has 3 tabs: **Syllabus | Regulations | Tax Rates**

Sample Questions is removed from KB and becomes its own top-level nav page (see Part 4).

### 2.1 Database — New/Updated Tables

#### Table: `kb_syllabus` (update existing)

```sql
-- Add session_id if not present, add structured fields
ALTER TABLE kb_syllabus ADD COLUMN IF NOT EXISTS session_id INTEGER REFERENCES exam_sessions(id);
ALTER TABLE kb_syllabus ADD COLUMN IF NOT EXISTS tax_type VARCHAR(30);
ALTER TABLE kb_syllabus ADD COLUMN IF NOT EXISTS syllabus_code VARCHAR(50);   -- unique key e.g. "A1a"
ALTER TABLE kb_syllabus ADD COLUMN IF NOT EXISTS topic VARCHAR(300);           -- Topics column
ALTER TABLE kb_syllabus ADD COLUMN IF NOT EXISTS detailed_syllabus TEXT;       -- Detailed syllabus column
-- Note: existing 'content' column can be kept as alias or migrated to detailed_syllabus
-- existing 'section_code', 'section_title', 'tags' columns remain
```

Add unique constraint:
```sql
CREATE UNIQUE INDEX IF NOT EXISTS idx_kb_syllabus_session_code 
  ON kb_syllabus(session_id, tax_type, syllabus_code);
```

#### Table: `kb_regulation_parsed` (NEW — replaces kb_regulation for structured parsed data)

```sql
CREATE TABLE IF NOT EXISTS kb_regulation_parsed (
    id SERIAL PRIMARY KEY,
    session_id INTEGER REFERENCES exam_sessions(id),
    tax_type VARCHAR(30) NOT NULL,
    reg_code VARCHAR(100),              -- e.g. "CIT-ND320-Art12-P30"
    doc_ref VARCHAR(200),               -- e.g. "Decree 320/2025/ND-CP"
    article_no VARCHAR(50),             -- e.g. "Article 12"
    paragraph_no INTEGER,               -- sequential within article, e.g. 30
    paragraph_text TEXT NOT NULL,
    syllabus_codes TEXT[],              -- array of syllabus_code strings that this para covers
    tags VARCHAR(500),
    source_file VARCHAR(300),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);
```

**Note:** Keep old `kb_regulation` table as-is for backward compatibility. New parsed regulations go into `kb_regulation_parsed`.

#### Table: `kb_tax_rates` (NEW)

```sql
CREATE TABLE IF NOT EXISTS kb_tax_rates (
    id SERIAL PRIMARY KEY,
    session_id INTEGER REFERENCES exam_sessions(id),
    tax_type VARCHAR(30) NOT NULL,
    table_name VARCHAR(200) NOT NULL,   -- e.g. "PIT on Employment Income", "VAT Standard Rates"
    content TEXT NOT NULL,              -- rich text / HTML content of the rate table
    source_file VARCHAR(300),           -- original uploaded file, if any
    display_order INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);
```

### 2.2 Syllabus Tab — Upload CSV/Excel

#### Upload Flow
1. User selects tax type (dropdown from session's tax_types)
2. User uploads CSV or Excel (.xlsx) file
3. App reads file, maps columns, previews data in table
4. User confirms → bulk insert into `kb_syllabus`

#### File Format
**Mandatory columns** (case-insensitive, flexible order):
- `Code` — syllabus code, unique key (e.g. "A1a", "C2b")
- `Topics` — topic group/heading
- `Detailed Syllabus` — the actual syllabus item text

Optional columns ignored on upload (future extension).

**Backend: POST /api/kb/syllabus/upload**
```python
@router.post("/syllabus/upload")
async def upload_syllabus(
    session_id: int = Form(...),
    tax_type: str = Form(...),
    file: UploadFile = File(...)
):
    """Parse CSV or Excel syllabus file, return preview rows."""
    import pandas as pd
    
    if file.filename.endswith('.csv'):
        df = pd.read_csv(file.file)
    elif file.filename.endswith(('.xlsx', '.xls')):
        df = pd.read_excel(file.file)
    else:
        raise HTTPException(400, "Only CSV or Excel files accepted")
    
    # Normalize column names
    df.columns = [c.strip().lower().replace(' ', '_') for c in df.columns]
    # Map: 'code'→'syllabus_code', 'topics'→'topic', 'detailed_syllabus'→'detailed_syllabus'
    
    required = {'code', 'topics', 'detailed_syllabus'}
    # also accept 'detailed syllabus' with space → already normalized
    
    missing = required - set(df.columns)
    if missing:
        raise HTTPException(400, f"Missing required columns: {missing}")
    
    rows = df[['code', 'topics', 'detailed_syllabus']].fillna('').to_dict('records')
    return {"preview": rows[:5], "total": len(rows), "rows": rows}
```

**Backend: POST /api/kb/syllabus/bulk-insert**
```python
@router.post("/syllabus/bulk-insert")
def bulk_insert_syllabus(data: dict):
    """Confirm and insert parsed syllabus rows. Upserts on (session_id, tax_type, syllabus_code)."""
    session_id = data['session_id']
    tax_type = data['tax_type']
    rows = data['rows']
    
    with get_db() as conn:
        cur = conn.cursor()
        for row in rows:
            cur.execute("""
                INSERT INTO kb_syllabus (session_id, tax_type, syllabus_code, topic, detailed_syllabus, section_code, section_title, content)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (session_id, tax_type, syllabus_code) DO UPDATE
                  SET topic = EXCLUDED.topic,
                      detailed_syllabus = EXCLUDED.detailed_syllabus,
                      section_title = EXCLUDED.detailed_syllabus
            """, (session_id, tax_type, row['code'], row['topics'], row['detailed_syllabus'],
                  row['code'], row['topics'], row['detailed_syllabus']))
    return {"inserted": len(rows)}
```

#### UI — Syllabus Tab
```
Syllabus                              Tax Type: [ CIT ▼ ]   [Upload CSV/Excel]

Uploaded syllabus for CIT (June 2026):   42 items             [Re-upload] [Clear all]

┌──────┬────────────────────┬─────────────────────────────────────────┬──────────┐
│ Code │ Topics             │ Detailed Syllabus                       │ Actions  │
├──────┼────────────────────┼─────────────────────────────────────────┼──────────┤
│ A1a  │ Taxable Persons    │ Understand who is subject to CIT...     │[Edit][✕] │
│ A1b  │ Taxable Persons    │ Distinguish between resident and...     │[Edit][✕] │
│ B2a  │ Deductible Expenses│ Identify deductible expenses under...   │[Edit][✕] │
└──────┴────────────────────┴─────────────────────────────────────────┴──────────┘

[+ Add item manually]
```

Upload modal:
1. Select tax type (dropdown)
2. File picker (CSV or .xlsx)
3. Preview table (first 5 rows + count)
4. [Confirm Import] button → bulk insert → success toast

[Edit] on a row → inline edit the 3 fields.

### 2.3 Regulations Tab — Upload + AI Parse + Edit

#### Upload Flow
1. Upload one or more regulation files per tax type (doc/docx/pdf/txt)
2. Each file shown with [Parse] button
3. [Parse] → AI chunks into paragraphs → shows editable table
4. User reviews, edits, sets syllabus_code links, saves

#### Upload: POST /api/kb/regulations/upload-doc
(Reuse existing upload endpoint, ensure it saves to `regulations` table with `doc_type='regulation'`)

#### Parse: POST /api/kb/regulations/parse-doc

```python
@router.post("/regulations/parse-doc")
def parse_regulation_doc(data: dict):
    """AI-parse a regulation document into kb_regulation_parsed rows."""
    session_id = data['session_id']
    tax_type = data['tax_type']
    file_path = data['file_path']   # relative path under /app/data/
    doc_ref = data.get('doc_ref', '')  # e.g. "Decree 320/2025/ND-CP"
    
    # 1. Extract text
    full_path = f"/app/data/{file_path}"
    text = extract_text_from_file(full_path)[:20000]
    
    # 2. AI parse prompt
    prompt = f"""Parse this Vietnamese tax regulation document into individual paragraphs.

For each paragraph, extract:
- article_no: article number (e.g. "Article 12" or "Điều 12")
- paragraph_no: sequential number within that article (1, 2, 3...)
- paragraph_text: the complete text of this paragraph
- tags: 3-6 English keywords describing this paragraph's topic

The RegCode will be auto-generated as: {tax_type}-{doc_ref_slug}-Art{{article}}-P{{paragraph}}

Return ONLY a valid JSON array:
[
  {{
    "article_no": "Article 12",
    "paragraph_no": 1,
    "paragraph_text": "...",
    "tags": "deductible,salary,5x cap,expenses"
  }}
]

DOCUMENT ({tax_type} — {doc_ref}):
{text}"""
    
    result = call_ai(prompt, model_tier="fast")
    chunks = parse_ai_json_list(result['content'])
    
    # 3. Build reg_codes and insert
    doc_slug = re.sub(r'[^A-Za-z0-9]', '', doc_ref.replace('/', '-').replace(' ', ''))[:20]
    rows = []
    with get_db() as conn:
        cur = conn.cursor()
        for chunk in chunks:
            art = re.sub(r'[^0-9]', '', chunk.get('article_no', '0'))
            p = chunk.get('paragraph_no', 0)
            reg_code = f"{tax_type}-{doc_slug}-Art{art}-P{p}"
            cur.execute("""
                INSERT INTO kb_regulation_parsed 
                  (session_id, tax_type, reg_code, doc_ref, article_no, paragraph_no, paragraph_text, tags, source_file)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                RETURNING id, reg_code
            """, (session_id, tax_type, reg_code, doc_ref,
                  chunk.get('article_no'), chunk.get('paragraph_no'),
                  chunk.get('paragraph_text',''), chunk.get('tags',''), file_path))
            row = cur.fetchone()
            rows.append({"id": row[0], "reg_code": row[1], **chunk})
    
    return {"parsed": len(rows), "rows": rows}
```

#### UI — Regulations Tab

```
Regulations           Tax Type: [ CIT ▼ ]      [+ Upload File]

Uploaded Files:
┌──────────────────────────────────────────────────────────────────┐
│ 📄 CIT_Decree_320_2025_ENG.docx     CIT   [Parse] [✕]          │
│ 📄 CIT_Law_67_2025_ENG.doc          CIT   [Parse] [✕]          │
└──────────────────────────────────────────────────────────────────┘

Parsed Paragraphs (CIT — 127 items)          [Search...] [Clear all]

┌─────────────────────┬───────────┬─────────────────────────────────┬─────────────────┬──────────┐
│ RegCode             │ Article   │ Paragraph Text (truncated)      │ Syllabus Codes  │ Actions  │
├─────────────────────┼───────────┼─────────────────────────────────┼─────────────────┼──────────┤
│ CIT-ND320-Art9-P1   │ Article 9 │ Deductible expenses are expend… │ B2a, B2b        │[Edit][✕] │
│ CIT-ND320-Art9-P2   │ Article 9 │ The following expenses are not… │ B2c             │[Edit][✕] │
└─────────────────────┴───────────┴─────────────────────────────────┴─────────────────┴──────────┘
```

[Edit] row → opens edit panel (rich text for paragraph_text) + multi-select for Syllabus Codes:
```
Edit Paragraph: CIT-ND320-Art9-P1
┌─────────────────────────────────────────────────────┐
│ Paragraph Text:                                     │
│ [Rich Text Editor — B I U • ≡ ⊞]                   │
│ Deductible expenses are expenditures that are...    │
│                                                     │
├─────────────────────────────────────────────────────┤
│ Syllabus Codes (link to relevant syllabus items):   │
│ [Search syllabus codes...] → shows dropdown list    │
│ ● B2a: Identify deductible expenses under...  [✕]  │
│ ● B2b: Apply the general conditions for...    [✕]  │
├─────────────────────────────────────────────────────┤
│ Tags: deductible, salary, expenses                  │
└─────────────────────────────────────────────────────┘
[Save]  [Cancel]
```

When clicking "Syllabus Codes" search → dropdown shows `{code}: {detailed_syllabus truncated}` filtered by same tax_type and session.

### 2.4 Tax Rates Tab — Upload + Rich Text Edit

Tax Rates stores rate tables per tax type. Can be uploaded or typed/pasted manually.

#### Upload: POST /api/kb/tax-rates/upload

```python
@router.post("/tax-rates/upload")
async def upload_tax_rates(
    session_id: int = Form(...),
    tax_type: str = Form(...),
    table_name: str = Form(...),
    file: UploadFile = File(...)
):
    """Read CSV/Excel and convert to HTML table, save to kb_tax_rates."""
    import pandas as pd
    if file.filename.endswith('.csv'):
        df = pd.read_csv(file.file)
    else:
        df = pd.read_excel(file.file)
    
    # Convert to HTML table
    html = df.to_html(index=False, classes='tax-rate-table', border=0)
    
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO kb_tax_rates (session_id, tax_type, table_name, content, source_file) VALUES (%s,%s,%s,%s,%s) RETURNING id",
            (session_id, tax_type, table_name, html, file.filename)
        )
        return {"id": cur.fetchone()[0]}
```

#### UI — Tax Rates Tab

```
Tax Rates             Tax Type: [ PIT ▼ ]      [+ Add Rate Table]

Rate Tables for PIT (June 2026):

┌─────────────────────────────────────────────────────────────────┐
│ PIT on Employment Income (Progressive Rates)     [Edit] [✕]    │
│ ┌────────────┬──────────┬─────────────────┐                    │
│ │ Tax Band   │ Rate (%) │ Annual Income   │                    │
│ │ Band 1     │ 5%       │ Up to 60M VND   │                    │
│ │ ...        │ ...      │ ...             │                    │
│ └────────────┴──────────┴─────────────────┘                    │
├─────────────────────────────────────────────────────────────────┤
│ PIT on Business Income (Flat Rates by Type)       [Edit] [✕]   │
│ ...                                                             │
└─────────────────────────────────────────────────────────────────┘
```

[+ Add Rate Table] → modal:
- Table Name (text input)
- Tax Type (dropdown)
- Upload CSV/Excel **OR** use Rich Text Editor to type/paste directly
- [Save]

[Edit] → opens Rich Text Editor pre-filled with existing content.

---

## PART 3: RICH TEXT EDITOR COMPONENT

Create a reusable `RichTextEditor` component used throughout the app (regulation paragraphs, tax rates, sample questions, question type descriptions/samples).

**Use `@uiw/react-md-editor` or `react-quill`** — whichever is already in package.json, otherwise use `react-quill` (lightweight, well-maintained).

If `react-quill` not installed: `npm install react-quill`

Toolbar options needed:
- Bold, Italic, Underline
- Bullet list, Ordered list
- Table (basic insert)
- Clean formatting

```jsx
// components/RichTextEditor.jsx
import ReactQuill from 'react-quill'
import 'react-quill/dist/quill.snow.css'

const TOOLBAR = [
  ['bold', 'italic', 'underline'],
  [{ 'list': 'ordered'}, { 'list': 'bullet' }],
  ['table'],
  ['clean']
]

export default function RichTextEditor({ value, onChange, placeholder, height = 200 }) {
  return (
    <ReactQuill
      theme="snow"
      value={value || ''}
      onChange={onChange}
      modules={{ toolbar: TOOLBAR }}
      placeholder={placeholder}
      style={{ height }}
    />
  )
}
```

Use `RichTextEditor` in:
- Regulation paragraph edit panel
- Tax rates add/edit
- Sample question content (Part 4)
- Question type description + sample fields (Part 1, Section C)

---

## PART 4: SAMPLE QUESTIONS — New Top-Level Page

Sample Questions is a standalone page (not inside KB), similar to Question Bank but for **past exam questions uploaded by the user** (not AI-generated).

### 4.1 DB — New Table

```sql
CREATE TABLE IF NOT EXISTS sample_questions (
    id SERIAL PRIMARY KEY,
    question_type VARCHAR(20) NOT NULL,     -- MCQ | SCENARIO | LONGFORM
    question_subtype VARCHAR(30),           -- MCQ-1 | MCQ-N | MCQ-FIB | null
    tax_type VARCHAR(30) NOT NULL,          -- CIT | PIT | VAT | etc.
    title VARCHAR(300),
    content TEXT NOT NULL,                  -- rich text HTML
    answer TEXT,                            -- rich text HTML
    marks INTEGER,
    exam_ref VARCHAR(200),                  -- e.g. "ACCA TX(VNM) June 2024"
    syllabus_codes TEXT[],                  -- array of syllabus_code strings
    reg_codes TEXT[],                       -- array of reg_code strings
    tags VARCHAR(500),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);
```

**Note:** Sample Questions are **global** (not session-scoped) — they apply to all sessions.

### 4.2 Backend — CRUD Endpoints

```
GET    /api/sample-questions              → list (filter: question_type, tax_type, subtype, search)
POST   /api/sample-questions              → create
GET    /api/sample-questions/{id}         → get single
PUT    /api/sample-questions/{id}         → update
DELETE /api/sample-questions/{id}         → delete
```

GET list params:
- `question_type` (MCQ/SCENARIO/LONGFORM)
- `tax_type` (CIT/PIT/etc.)
- `subtype` (MCQ-1/MCQ-N/MCQ-FIB)
- `search` (text search in title + content)
- `syllabus_code` (filter by syllabus code)

### 4.3 UI — Sample Questions Page (`/sample-questions`)

Layout mirrors Question Bank page.

```
Sample Questions                                          [+ Add Sample]

Filter: [All Types ▼] [All Tax Types ▼] [All Subtypes ▼] [Search...]

┌─────────────────────────────────────────────────────────────────────┐
│ MCQ • CIT • MCQ-1 (Single Answer)                                  │
│ Q: ABC Company incurred VND 500M salary expense...                  │
│ Syllabus: B2a, B2c | Ref: CIT-ND320-Art9-P1 | Source: June 2024   │
│                                          [View] [Edit] [Delete]     │
├─────────────────────────────────────────────────────────────────────┤
│ SCENARIO • PIT • —                                                  │
│ Mr. Nguyen Van A, a Vietnamese resident, earned...                  │
│ Syllabus: C1a, C1b | Ref: PIT-TT80-Art14-P2 | Source: Dec 2023    │
│                                          [View] [Edit] [Delete]     │
└─────────────────────────────────────────────────────────────────────┘
```

[+ Add Sample] → modal/drawer with:
- Question Type (MCQ / Scenario / Long-form) — dropdown
- MCQ Subtype (MCQ-1 / MCQ-N / MCQ-FIB / None) — shows only if type=MCQ
- Tax Type — dropdown
- Title (text input)
- Question Content — **RichTextEditor**
- Answer — **RichTextEditor**
- Marks (number input)
- Exam Reference (text, e.g. "ACCA TX(VNM) June 2024")
- Syllabus Codes (multi-select from loaded kb_syllabus for current session's codes)
- RegCodes (multi-select from kb_regulation_parsed, search by reg_code or text)
- Tags (text input)

[View] → readonly modal showing full question + answer rendered HTML
[Edit] → same form pre-filled
[Delete] → confirm dialog

### 4.4 Navigation

Add "Sample Questions" to navbar:
```
Sessions | Knowledge Base | Generate | Sample Questions | Question Bank | Settings
```

---

## PART 5: GENERATE PAGE — Enhanced Filtering

### 5.1 Updated Request Models (backend/models.py)

Add fields to all 3 request models:

```python
# Existing fields remain unchanged

# New: MCQ subtype selection
mcq_subtype: Optional[str] = None          # "MCQ-1" | "MCQ-N" | "MCQ-FIB" | None (auto)

# References — Syllabus
syllabus_codes: Optional[List[str]] = None  # list of syllabus_code strings to focus on

# References — Regulation paragraphs (by reg_code)
reg_codes: Optional[List[str]] = None       # list of reg_code strings to cite

# References — Sample questions (from sample_questions table)
sample_question_ids: Optional[List[int]] = None

# References — Question bank items (from questions table)
question_bank_ids: Optional[List[int]] = None
```

### 5.2 Updated Context Builder (backend/context_builder.py)

```python
def build_full_context(req, session_id: int) -> str:
    """Build the complete context block injected into the generation prompt."""
    parts = []
    
    # 1. Session economic parameters
    session = get_session(session_id)
    if session and session.get('parameters'):
        params = session['parameters']
        params_text = "\n".join(f"- {p['key']}: {p['value']} {p.get('unit','')}" for p in params)
        parts.append(f"EXAM ECONOMIC PARAMETERS (use these figures in calculations):\n{params_text}")
    
    # 2. Syllabus items
    if req.syllabus_codes:
        with get_db() as conn:
            cur = conn.cursor()
            placeholders = ','.join(['%s'] * len(req.syllabus_codes))
            cur.execute(f"""
                SELECT syllabus_code, topic, detailed_syllabus 
                FROM kb_syllabus WHERE session_id=%s AND syllabus_code IN ({placeholders})
            """, [session_id] + list(req.syllabus_codes))
            rows = cur.fetchall()
        if rows:
            items = "\n".join(f"- [{r[0]}] {r[1]}: {r[2]}" for r in rows)
            parts.append(f"SYLLABUS ITEMS TO TEST (question MUST cover these):\n{items}")
    
    # 3. Regulation paragraphs
    if req.reg_codes:
        with get_db() as conn:
            cur = conn.cursor()
            placeholders = ','.join(['%s'] * len(req.reg_codes))
            cur.execute(f"""
                SELECT reg_code, doc_ref, paragraph_text 
                FROM kb_regulation_parsed WHERE session_id=%s AND reg_code IN ({placeholders})
            """, [session_id] + list(req.reg_codes))
            rows = cur.fetchall()
        if rows:
            items = "\n".join(f"- [{r[0]}] ({r[1]}): {r[2]}" for r in rows)
            parts.append(f"REGULATION PARAGRAPHS TO CITE:\n{items}")
    
    # 4. Tax rates for this tax type (always inject if available)
    if hasattr(req, 'sac_thue') and req.sac_thue:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT table_name, content FROM kb_tax_rates 
                WHERE session_id=%s AND tax_type=%s AND is_active=TRUE 
                ORDER BY display_order
            """, (session_id, req.sac_thue))
            rows = cur.fetchall()
        if rows:
            rate_blocks = []
            for r in rows:
                # Strip HTML tags for prompt injection (keep numbers/text)
                import re as _re
                clean = _re.sub(r'<[^>]+>', ' ', r[1]).strip()
                rate_blocks.append(f"=== {r[0]} ===\n{clean}")
            parts.append("TAX RATES (use these in calculations):\n" + "\n\n".join(rate_blocks))
    
    # 5. Sample question references
    if req.sample_question_ids:
        with get_db() as conn:
            cur = conn.cursor()
            placeholders = ','.join(['%s'] * len(req.sample_question_ids))
            cur.execute(f"SELECT title, content, answer FROM sample_questions WHERE id IN ({placeholders})", 
                       req.sample_question_ids)
            rows = cur.fetchall()
        if rows:
            refs = []
            for r in rows:
                import re as _re
                q_clean = _re.sub(r'<[^>]+>', ' ', r[1]).strip()[:1500]
                a_clean = _re.sub(r'<[^>]+>', ' ', (r[2] or '')).strip()[:500]
                refs.append(f"=== STYLE REFERENCE: {r[0]} ===\nQuestion: {q_clean}\nAnswer: {a_clean}")
            parts.append("STYLE REFERENCES (replicate structure and difficulty):\n\n".join(refs))
    
    # 6. Question bank references (same logic)
    if req.question_bank_ids:
        with get_db() as conn:
            cur = conn.cursor()
            placeholders = ','.join(['%s'] * len(req.question_bank_ids))
            cur.execute(f"SELECT content_json FROM questions WHERE id IN ({placeholders})", 
                       req.question_bank_ids)
            rows = cur.fetchall()
        if rows:
            refs = []
            for r in rows:
                import json as _json
                content = r[0] if isinstance(r[0], dict) else _json.loads(r[0])
                refs.append(f"=== QUESTION BANK REFERENCE ===\n{_json.dumps(content, ensure_ascii=False)[:2000]}")
            parts.append("QUESTION BANK REFERENCES:\n" + "\n\n".join(refs))
    
    # 7. MCQ subtype instruction
    if hasattr(req, 'mcq_subtype') and req.mcq_subtype:
        subtype_map = {
            'MCQ-1': "Generate SINGLE correct answer MCQs. One option is clearly correct, three are plausible distractors.",
            'MCQ-N': "Generate MULTIPLE correct answers MCQs. Two or more options are correct. Clearly state 'Select ALL that apply'.",
            'MCQ-FIB': "Generate FILL-IN-THE-BLANK MCQs. A statement with one blank, candidates choose from a word bank of 5-6 options.",
        }
        instruction = subtype_map.get(req.mcq_subtype, '')
        if instruction:
            parts.append(f"MCQ FORMAT INSTRUCTION: {instruction}")
    
    return "\n\n---\n\n".join(parts)
```

### 5.3 Updated Generate UI (frontend/src/pages/Generate.jsx)

#### New state variables
```javascript
// MCQ subtype
const [mcqSubtype, setMcqSubtype] = useState('')  // '' = auto

// Syllabus reference
const [syllabusSearch, setSyllabusSearch] = useState('')
const [syllabusOptions, setSyllabusOptions] = useState([])
const [selectedSyllabusCodes, setSelectedSyllabusCodes] = useState([])

// RegCode reference
const [regSearch, setRegSearch] = useState('')
const [regOptions, setRegOptions] = useState([])
const [selectedRegCodes, setSelectedRegCodes] = useState([])

// Sample questions reference
const [sampleSearch, setSampleSearch] = useState('')
const [sampleOptions, setSampleOptions] = useState([])
const [selectedSampleIds, setSelectedSampleIds] = useState([])

// Question bank reference
const [qbSearch, setQbSearch] = useState('')
const [qbOptions, setQbOptions] = useState([])
const [selectedQbIds, setSelectedQbIds] = useState([])
```

#### UI Layout (within the existing Custom Instructions / KB Targeting section)

Add a new collapsible sub-section **"Reference Materials"** (replaces the old KB Targeting section):

```jsx
{/* MCQ Subtype — show only when type === 'mcq' */}
{type === 'mcq' && (
  <div>
    <label>MCQ Format</label>
    <select value={mcqSubtype} onChange={e => setMcqSubtype(e.target.value)}>
      <option value="">Auto (mixed)</option>
      <option value="MCQ-1">Single correct answer</option>
      <option value="MCQ-N">Multiple correct answers</option>
      <option value="MCQ-FIB">Fill in the blank</option>
    </select>
  </div>
)}

{/* Syllabus Code picker */}
<ReferenceMultiSelect
  label="Syllabus items to focus on"
  placeholder="Search by code or topic... e.g. B2a, deductible"
  fetchFn={(q) => api.searchSyllabus({ session_id: currentSessionId, tax_type: sacThue, q })}
  displayFn={(item) => `[${item.syllabus_code}] ${item.detailed_syllabus?.substring(0,80)}...`}
  selected={selectedSyllabusCodes}
  onSelect={(item) => setSelectedSyllabusCodes(prev => [...prev, item.syllabus_code])}
  onRemove={(code) => setSelectedSyllabusCodes(prev => prev.filter(c => c !== code))}
/>

{/* RegCode picker — filters based on selected syllabus codes if any */}
<ReferenceMultiSelect
  label="Regulation paragraphs to cite"
  placeholder="Search by RegCode or text... e.g. CIT-ND320, salary"
  fetchFn={(q) => api.searchRegulations({ session_id: currentSessionId, tax_type: sacThue, q,
                                           syllabus_codes: selectedSyllabusCodes })}
  displayFn={(item) => `[${item.reg_code}] ${item.paragraph_text?.substring(0,80)}...`}
  selected={selectedRegCodes}
  onSelect={(item) => setSelectedRegCodes(prev => [...prev, item.reg_code])}
  onRemove={(code) => setSelectedRegCodes(prev => prev.filter(c => c !== code))}
/>

{/* Sample Questions picker */}
<ReferenceMultiSelect
  label="Style references (sample questions)"
  placeholder="Search by title or content..."
  fetchFn={(q) => api.searchSampleQuestions({ question_type: type.toUpperCase(), tax_type: sacThue, q })}
  displayFn={(item) => `[${item.question_type}•${item.tax_type}] ${item.title}`}
  selected={selectedSampleIds}
  onSelect={(item) => setSelectedSampleIds(prev => [...prev, item.id])}
  onRemove={(id) => setSelectedSampleIds(prev => prev.filter(i => i !== id))}
/>

{/* Question Bank picker */}
<ReferenceMultiSelect
  label="Question bank references"
  placeholder="Search from your generated questions..."
  fetchFn={(q) => api.searchQuestions({ question_type: type.toUpperCase(), tax_type: sacThue, q })}
  displayFn={(item) => `[${item.question_type}•${item.sac_thue}] ${item.title || item.id}`}
  selected={selectedQbIds}
  onSelect={(item) => setSelectedQbIds(prev => [...prev, item.id])}
  onRemove={(id) => setSelectedQbIds(prev => prev.filter(i => i !== id))}
/>
```

#### `ReferenceMultiSelect` component (reusable)

Create `frontend/src/components/ReferenceMultiSelect.jsx`:

```jsx
/**
 * A searchable multi-select component for picking reference items.
 * Props:
 *   label: string
 *   placeholder: string
 *   fetchFn: async (query: string) => Item[]  — called on input change (debounced 300ms)
 *   displayFn: (item) => string               — how to display each item in dropdown
 *   selected: string[] | number[]             — selected ids/codes
 *   onSelect: (item) => void
 *   onRemove: (id) => void
 */
```

Behavior:
- Type in search box → debounced fetch → dropdown of results
- Click result → adds to selected chips row
- Selected items shown as removable chips: `[B2a: Identify deductible expenses ×]`
- If 0 results and query is non-empty → show "No matches found"
- If fetchFn not provided or fails silently → show empty

#### New search API endpoints

```
GET /api/kb/syllabus/search?session_id=1&tax_type=CIT&q=deductible
→ returns [{id, syllabus_code, topic, detailed_syllabus}]

GET /api/kb/regulations/search?session_id=1&tax_type=CIT&q=salary&syllabus_codes=B2a,B2b
→ returns [{id, reg_code, doc_ref, paragraph_text}]
  (if syllabus_codes provided, filter WHERE syllabus_codes && ARRAY[...])

GET /api/sample-questions/search?question_type=MCQ&tax_type=CIT&q=salary
→ returns [{id, question_type, tax_type, title}]

GET /api/questions/search?question_type=MCQ&tax_type=CIT&q=salary
→ returns [{id, question_type, sac_thue, title (or first 80 chars of content)}]
```

---

## PART 6: TAGGING — Question Bank & Sample Questions

Both Question Bank (`questions` table) and Sample Questions (`sample_questions` table) should support filtering by:
- question_type
- tax_type (sac_thue)
- mcq_subtype (for MCQ)
- syllabus_codes (overlap with selected codes)
- reg_codes (overlap with selected codes)

### 6.1 Add fields to `questions` table

```sql
ALTER TABLE questions ADD COLUMN IF NOT EXISTS mcq_subtype VARCHAR(30);
ALTER TABLE questions ADD COLUMN IF NOT EXISTS syllabus_codes TEXT[];
ALTER TABLE questions ADD COLUMN IF NOT EXISTS reg_codes TEXT[];
```

### 6.2 Auto-tag on generate

After AI generates a question, auto-extract syllabus/reg codes from the context used:

In each generate endpoint, after saving to DB:
```python
cur.execute("""
    UPDATE questions SET 
        mcq_subtype = %s,
        syllabus_codes = %s,
        reg_codes = %s
    WHERE id = %s
""", (req.mcq_subtype, req.syllabus_codes or [], req.reg_codes or [], question_id))
```

### 6.3 Question Bank UI updates

Add filter chips to Question Bank header:
```
Filter: [All Types ▼] [All Tax ▼] [All Subtypes ▼] [Syllabus: search...] [RegCode: search...] [Session ▼]
```

---

## PART 7: NEW API ENDPOINTS SUMMARY

```
# Session settings
PATCH  /api/sessions/{id}                         → update parameters/tax_types/question_types

# Syllabus
POST   /api/kb/syllabus/upload                    → parse CSV/Excel → preview
POST   /api/kb/syllabus/bulk-insert               → confirm + insert
GET    /api/kb/syllabus/search                    → search syllabus items
DELETE /api/kb/syllabus/{id}                      → delete item
PUT    /api/kb/syllabus/{id}                      → update item

# Regulations (new parsed table)
POST   /api/kb/regulations/parse-doc              → AI parse file → insert to kb_regulation_parsed
GET    /api/kb/regulations/parsed                 → list parsed (filter: session_id, tax_type)
GET    /api/kb/regulations/search                 → search parsed regulations
PUT    /api/kb/regulation-parsed/{id}             → update (edit text + syllabus_codes)
DELETE /api/kb/regulation-parsed/{id}             → delete

# Tax Rates
GET    /api/kb/tax-rates                          → list (filter: session_id, tax_type)
POST   /api/kb/tax-rates/upload                   → upload CSV/Excel → save as HTML
POST   /api/kb/tax-rates                          → create manually
PUT    /api/kb/tax-rates/{id}                     → update
DELETE /api/kb/tax-rates/{id}                     → delete

# Sample Questions
GET    /api/sample-questions                      → list (filter: type, tax_type, subtype, search)
GET    /api/sample-questions/search               → search
POST   /api/sample-questions                      → create
PUT    /api/sample-questions/{id}                 → update
DELETE /api/sample-questions/{id}                 → delete

# Questions (updates)
GET    /api/questions/search                      → search with filters
```

---

## PART 8: NAVIGATION FINAL ORDER

```
Sessions | Knowledge Base | Generate | Sample Questions | Question Bank | Settings
```

---

## PART 9: DB MIGRATIONS SUMMARY

Run these in order. Check IF NOT EXISTS before each — app may already have some columns.

```sql
-- 1. Exam Sessions
ALTER TABLE exam_sessions ADD COLUMN IF NOT EXISTS parameters JSONB DEFAULT '[]';
ALTER TABLE exam_sessions ADD COLUMN IF NOT EXISTS tax_types JSONB DEFAULT '[]';
ALTER TABLE exam_sessions ADD COLUMN IF NOT EXISTS question_types JSONB DEFAULT '[]';

-- Seed defaults for existing sessions (June 2026)
UPDATE exam_sessions SET 
    parameters = '[{"key":"USD Exchange Rate","value":"26500","unit":"VND"},{"key":"Monthly Base Salary (SHUI)","value":"46800000","unit":"VND"}]'::jsonb,
    tax_types = '[{"code":"CIT","name":"Corporate Income Tax"},{"code":"PIT","name":"Personal Income Tax"},{"code":"FCT","name":"Foreign Contractor Tax"},{"code":"VAT","name":"Value Added Tax"},{"code":"TAX-ADMIN","name":"Tax Administration"},{"code":"TP","name":"Transfer Pricing"}]'::jsonb,
    question_types = '[{"code":"MCQ","name":"Multiple Choice","subtypes":[{"code":"MCQ-1","name":"Single correct answer","description":"One correct answer out of 4 options","sample":""},{"code":"MCQ-N","name":"Multiple correct answers","description":"Two or more correct options. Candidates select all that apply.","sample":""},{"code":"MCQ-FIB","name":"Fill in the blank (words)","description":"Candidate fills missing word(s). Provide word bank.","sample":""}]},{"code":"SCENARIO","name":"Scenario Question (10-15 marks)","subtypes":[]},{"code":"LONGFORM","name":"Long-form Question (15-25 marks)","subtypes":[]}]'::jsonb
WHERE parameters = '[]'::jsonb OR parameters IS NULL;

-- 2. KB Syllabus
ALTER TABLE kb_syllabus ADD COLUMN IF NOT EXISTS session_id INTEGER REFERENCES exam_sessions(id);
ALTER TABLE kb_syllabus ADD COLUMN IF NOT EXISTS tax_type VARCHAR(30);
ALTER TABLE kb_syllabus ADD COLUMN IF NOT EXISTS syllabus_code VARCHAR(50);
ALTER TABLE kb_syllabus ADD COLUMN IF NOT EXISTS topic VARCHAR(300);
ALTER TABLE kb_syllabus ADD COLUMN IF NOT EXISTS detailed_syllabus TEXT;
CREATE UNIQUE INDEX IF NOT EXISTS idx_kb_syllabus_session_code ON kb_syllabus(session_id, tax_type, syllabus_code) WHERE syllabus_code IS NOT NULL;

-- 3. New kb_regulation_parsed table
CREATE TABLE IF NOT EXISTS kb_regulation_parsed (
    id SERIAL PRIMARY KEY,
    session_id INTEGER REFERENCES exam_sessions(id),
    tax_type VARCHAR(30) NOT NULL,
    reg_code VARCHAR(100),
    doc_ref VARCHAR(200),
    article_no VARCHAR(50),
    paragraph_no INTEGER,
    paragraph_text TEXT NOT NULL,
    syllabus_codes TEXT[],
    tags VARCHAR(500),
    source_file VARCHAR(300),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- 4. New kb_tax_rates table
CREATE TABLE IF NOT EXISTS kb_tax_rates (
    id SERIAL PRIMARY KEY,
    session_id INTEGER REFERENCES exam_sessions(id),
    tax_type VARCHAR(30) NOT NULL,
    table_name VARCHAR(200) NOT NULL,
    content TEXT NOT NULL,
    source_file VARCHAR(300),
    display_order INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- 5. New sample_questions table
CREATE TABLE IF NOT EXISTS sample_questions (
    id SERIAL PRIMARY KEY,
    question_type VARCHAR(20) NOT NULL,
    question_subtype VARCHAR(30),
    tax_type VARCHAR(30) NOT NULL,
    title VARCHAR(300),
    content TEXT NOT NULL,
    answer TEXT,
    marks INTEGER,
    exam_ref VARCHAR(200),
    syllabus_codes TEXT[],
    reg_codes TEXT[],
    tags VARCHAR(500),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- 6. Update questions table
ALTER TABLE questions ADD COLUMN IF NOT EXISTS mcq_subtype VARCHAR(30);
ALTER TABLE questions ADD COLUMN IF NOT EXISTS syllabus_codes TEXT[];
ALTER TABLE questions ADD COLUMN IF NOT EXISTS reg_codes TEXT[];
```

---

## IMPLEMENTATION ORDER FOR CLAUDE CODE

Build in this order — each step should be independently testable:

1. **DB migrations** → run all SQL above
2. **Session Settings UI** (Part 1) → parameters, tax_types, question_types editor
3. **KB: Syllabus tab** (Part 2.2) → upload CSV/Excel, preview, bulk-insert, table view
4. **KB: Regulations tab** (Part 2.3) → upload file, parse-doc, editable table with syllabus linking
5. **KB: Tax Rates tab** (Part 2.4) → upload/manual entry, rich text edit
6. **Sample Questions page** (Part 4) → full CRUD with rich text editor
7. **Generate: Reference pickers** (Part 5) → ReferenceMultiSelect, MCQ subtype, updated context builder
8. **Tagging** (Part 6) → auto-tag on generate, filter in Question Bank
9. **Nav update** (Part 8) → add Sample Questions to nav

---

## IMPORTANT NOTES FOR CLAUDE CODE

1. **Do NOT re-run already-applied migrations** — always use `IF NOT EXISTS` / `IF NOT EXISTS`
2. **`pandas` for CSV/Excel parsing** — add to requirements.txt if not present: `pandas openpyxl`
3. **`react-quill` for rich text** — add to package.json if not present: `npm install react-quill`
4. **RegCode format:** `{TaxType}-{DocRefSlug}-Art{N}-P{N}` e.g. `CIT-ND320-Art9-P1`
5. **Session clone** must copy ALL: parameters, tax_types, question_types, KB items, files
6. **Sample Questions** = global (no session_id) — applies to all sessions
7. **Tax types in dropdowns** should be loaded from current session's `tax_types` JSONB field — not hardcoded
8. **Question types in dropdowns** should be loaded from current session's `question_types` JSONB field — not hardcoded
9. **ReferenceMultiSelect** is fully reusable — build it once, use in Generate + Sample Questions forms
10. **Rich text stored as HTML** — use `dangerouslySetInnerHTML` to render it in readonly views
11. **Context builder** now uses `kb_regulation_parsed` (not old `kb_regulation`) for reg paragraph context
12. **`build_full_context()`** replaces the old `build_kb_context()` — remove old function after wiring up new one
13. **Tax rates always injected** into generate prompt when available for that session+tax_type — no user selection needed (it's automatic)
