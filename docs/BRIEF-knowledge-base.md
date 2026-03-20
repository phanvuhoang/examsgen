# BRIEF: Knowledge Base Layer for ExamsGen

## Overview

Thêm một "Knowledge Base" layer vào ExamsGen — một bộ database có cấu trúc giúp AI hiểu rõ mapping giữa syllabus ↔ regulations ↔ past exam questions. Khi generate, AI không còn phải đọc toàn bộ documents mà được cung cấp đúng các đoạn liên quan → output chuẩn hơn, khó hơn, đúng style hơn.

---

## Database Schema (thêm vào PostgreSQL `examsgen`)

### Table 1: `kb_syllabus` — Syllabus items

```sql
CREATE TABLE kb_syllabus (
    id SERIAL PRIMARY KEY,
    sac_thue VARCHAR(20) NOT NULL,       -- CIT | VAT | PIT | FCT | TP | ADMIN
    section_code VARCHAR(50),            -- e.g. "A1", "B2c", "C3"
    section_title VARCHAR(500),          -- e.g. "Deductible expenses"
    content TEXT NOT NULL,               -- full text of this syllabus item
    tags VARCHAR(500),                   -- comma-separated: "deductible,expenses,salary"
    source_file VARCHAR(200),            -- which syllabus file this came from
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);
```

### Table 2: `kb_regulation` — Regulation paragraphs

```sql
CREATE TABLE kb_regulation (
    id SERIAL PRIMARY KEY,
    sac_thue VARCHAR(20) NOT NULL,
    regulation_ref VARCHAR(200),         -- e.g. "Article 9, Decree 320/2025/ND-CP"
    content TEXT NOT NULL,               -- full text of this regulation paragraph
    tags VARCHAR(500),                   -- comma-separated: "deductible,salary,5x cap"
    syllabus_ids INTEGER[],              -- linked kb_syllabus.id rows
    source_file VARCHAR(200),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);
```

### Table 3: `kb_sample_question` — Curated sample questions

```sql
CREATE TABLE kb_sample_question (
    id SERIAL PRIMARY KEY,
    question_type VARCHAR(20) NOT NULL,  -- MCQ | SCENARIO_10 | LONGFORM_15
    sac_thue VARCHAR(20) NOT NULL,
    question_number VARCHAR(10),         -- Q1 | Q2 | MCQ | etc.
    title VARCHAR(300),                  -- short description e.g. "CIT deductible expenses + time apportionment"
    content TEXT NOT NULL,               -- full Q&A text
    exam_tricks TEXT,                    -- key tricks in this question e.g. "time apportionment, interest cap, asset revaluation"
    syllabus_ids INTEGER[],              -- linked kb_syllabus.id rows
    regulation_ids INTEGER[],            -- linked kb_regulation.id rows
    source VARCHAR(100),                 -- "manual_upload" | "question_bank:{id}" | "sample_file"
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);
```

### Table 4: `kb_auto_parsed` — Track auto-parsing jobs

```sql
CREATE TABLE kb_auto_parsed (
    id SERIAL PRIMARY KEY,
    source_type VARCHAR(20),             -- "syllabus" | "regulation"
    source_file VARCHAR(200),
    sac_thue VARCHAR(20),
    status VARCHAR(20),                  -- "pending" | "done" | "failed"
    items_created INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW()
);
```

---

## Auto-Parse Feature (AI-assisted chunking)

### Endpoint: POST /api/kb/parse-file

```json
{
  "file_type": "syllabus",     // "syllabus" | "regulation"
  "sac_thue": "CIT",
  "file_path": "data/syllabus/CIT_Syllabus.docx"
}
```

Backend:
1. Extract text from .docx/.doc
2. Call AI to chunk into logical paragraphs + auto-tag each

**Prompt for chunking:**
```
You are parsing a Vietnamese tax document for an exam question database.

Split this document into logical chunks. Each chunk should be:
- One coherent topic/rule (not too small, not too big — roughly one article or one syllabus item)
- Self-contained enough to be useful as exam context

For each chunk, return:
- section_code: the article/section number if present (e.g. "Article 9" or "Section B2")  
- section_title: a short title (max 10 words)
- content: the full text of this chunk
- tags: 3-8 comma-separated keywords (English) describing what this chunk covers

Return ONLY valid JSON array:
[
  {
    "section_code": "Article 9",
    "section_title": "Deductible expenses — general conditions",
    "content": "...",
    "tags": "deductible,expenses,conditions,genuine,invoice"
  }
]

DOCUMENT:
{document_text}
```

3. Save each chunk to `kb_syllabus` or `kb_regulation`
4. Return list of created items for user to review/edit tags

### Endpoint: GET /api/kb/parse-preview/{job_id}

Returns parsed items with edit capability before saving.

---

## Manual Input UI

For users who prefer to paste and tag manually:

### KB Manager page (`/kb`)

Tabs: **Syllabus** | **Regulations** | **Sample Questions**

#### Syllabus tab
- List of kb_syllabus items grouped by sac_thue
- [Auto-parse file] button → triggers /api/kb/parse-file
- [Add manually] → form: sac_thue, section_code, title, content textarea, tags input
- Each item: edit tags inline, toggle active, link to regulations

#### Regulations tab  
- Same structure
- Each item shows linked syllabus items (many-to-many)
- [Link to syllabus] → checkbox list of syllabus items

#### Sample Questions tab
- List of curated samples
- [Import from Question Bank] → shows list of saved questions, pick ones to promote to KB
- [Add manually] → paste Q&A, set title, exam_tricks, link to syllabus + regulation items
- Each item shows: question preview, exam_tricks, linked items

---

## Updated Generate Flow

### Request model changes

Add to all 3 request models:

```python
# KB-based targeting
kb_syllabus_ids: Optional[List[int]] = None    # specific syllabus items to test
kb_regulation_ids: Optional[List[int]] = None  # specific regulation paragraphs to use
kb_sample_ids: Optional[List[int]] = None      # style references from KB
```

### Context builder changes

```python
def build_kb_context(
    kb_syllabus_ids=None, 
    kb_regulation_ids=None, 
    kb_sample_ids=None
):
    parts = []
    
    if kb_syllabus_ids:
        items = fetch_kb_syllabus(kb_syllabus_ids)
        parts.append("SYLLABUS ITEMS TO TEST (question MUST cover these):\n" + 
                     "\n".join(f"- [{i.section_code}] {i.section_title}: {i.content}" 
                               for i in items))
    
    if kb_regulation_ids:
        items = fetch_kb_regulation(kb_regulation_ids)
        parts.append("REGULATION PARAGRAPHS TO USE (cite these specifically):\n" +
                     "\n".join(f"- [{i.regulation_ref}]: {i.content}"
                               for i in items))
    
    if kb_sample_ids:
        items = fetch_kb_samples(kb_sample_ids)
        style_block = []
        for s in items:
            style_block.append(f"=== STYLE REFERENCE: {s.title} ===")
            if s.exam_tricks:
                style_block.append(f"Key tricks: {s.exam_tricks}")
            style_block.append(s.content)
        parts.append("STYLE REFERENCES (replicate structure, difficulty, and tricks):\n" +
                     "\n".join(style_block))
    
    return "\n\n".join(parts)
```

### Updated prompt injection

KB context is injected BEFORE the general regulations context, with higher priority instruction:

```
{kb_context}

IMPORTANT: The question MUST specifically test the syllabus items and regulation paragraphs listed above.
If style references are provided, replicate their structure and difficulty level.
```

---

## Updated Generate UI (Generate.jsx)

### New section in Custom Instructions: "Knowledge Base Targeting"

```
[x] Use Knowledge Base targeting

  Syllabus items to test:
  [Search syllabus... ▼] [+ Add]
  ● [CIT-A2] Deductible expenses — general conditions  ×
  ● [CIT-B1] Interest expense cap (150%)  ×

  Regulation paragraphs:
  [Search regulations... ▼] [+ Add]
  ● [Art.9 Decree 320] Salary expenses deductibility  ×

  Style references from KB:
  [Search sample questions... ▼] [+ Add]
  ● Q1-CIT: Time apportionment + interest cap  ×
```

All 3 are searchable multi-select dropdowns (search by tag or title).

---

## New API Endpoints

```
# KB Management
GET  /api/kb/syllabus                    → list (filter: sac_thue, search)
POST /api/kb/syllabus                    → create item
PUT  /api/kb/syllabus/{id}              → update
DELETE /api/kb/syllabus/{id}            → delete

GET  /api/kb/regulations                 → list
POST /api/kb/regulations                 → create
PUT  /api/kb/regulations/{id}           → update
DELETE /api/kb/regulations/{id}         → delete

GET  /api/kb/samples                     → list
POST /api/kb/samples                     → create
POST /api/kb/samples/import-from-bank   → import from question bank
PUT  /api/kb/samples/{id}              → update
DELETE /api/kb/samples/{id}            → delete

POST /api/kb/parse-file                  → auto-parse regulation/syllabus file
GET  /api/kb/parse-job/{id}             → check parse job status

# Updated generate endpoints — accept kb_* fields in request body
POST /api/generate/mcq                   → (unchanged URL, new optional fields)
POST /api/generate/scenario              → (unchanged URL, new optional fields)
POST /api/generate/longform             → (unchanged URL, new optional fields)
```

---

## Implementation Notes for Claude Code

1. **Phased approach:** Build KB management (CRUD) first → then wire into generate flow
2. **Auto-parse is optional** — manual input must work without it
3. **KB targeting is optional** — existing generate still works without KB fields
4. **Tags are comma-separated strings** (not a separate table) — simpler for now
5. **syllabus_ids and regulation_ids** in `kb_sample_question` are PostgreSQL integer arrays
6. **Search in dropdowns:** search by tags OR title, case-insensitive
7. **KB page** is a new nav item between "Generate" and "Question Bank"
