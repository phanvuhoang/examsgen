# ExamsGen — ACCA TX(VNM) Question Generator

## Project Summary

Build a production-ready web application called **ExamsGen** that uses AI (Claude/GPT-4) to automatically generate ACCA TX(VNM) professional exam questions about Vietnam taxation. The app reads official Vietnamese tax regulations and syllabus documents, then generates scenario-based questions matching the exact style, structure, difficulty, and format of real ACCA past exam papers.

**GitHub:** `examsgen` (already created)  
**Deploy target:** Docker on VPS (Ubuntu), reverse-proxied via Traefik, domain `examsgen.gpt4vn.com`  
**Primary user:** Single admin user (Phase 1), extendable to subscribers (Phase 2)

---

## Exam Structure Context

The ACCA TX(VNM) exam has 3 parts with fixed structure:

### Part 1 — Multiple Choice Questions (MCQ)
- Each MCQ = 2 marks
- 4 options (A/B/C/D), one correct answer
- Topics: CIT, PIT, VAT, FCT, Tax Administration, Transfer Pricing
- Sample files: `Sample CIT questions.docx`, `Sample VAT questions.docx`, etc.

### Part 2 — Scenario Questions (10 marks each)
- 4 questions, each covering one tax type
- Q1 = CIT (Corporate Income Tax)
- Q2 = PIT (Personal Income Tax)  
- Q3 = FCT (Foreign Contractor Tax)
- Q4 = VAT (Value Added Tax)
- Each has 3-5 sub-questions integrated into one business scenario
- Sample files: `Sample Q1.docx` through `Sample Q4.docx`

### Part 3 — Long-form Scenario Questions (15 marks each)
- 2 questions
- Q5 = CIT (complex, multi-issue scenario)
- Q6 = PIT (complex, multi-issue scenario)
- 5-6 sub-questions with detailed marking schemes
- Sample files: `Sample Q5.docx`, `Sample Q6.docx`

**Tax types covered:** CIT, VAT, PIT, FCT, Tax Administration (QLT), Transfer Pricing (TP)

---

## Tech Stack

- **Backend:** Python FastAPI + Uvicorn
- **Frontend:** React + Tailwind CSS (Vite build)
- **Database:** PostgreSQL
- **AI:** Claudible API (primary, OpenAI-compatible endpoint) → Anthropic API (fallback) → OpenAI API (secondary fallback)
- **File storage:** Local mounted volume `/app/data/`
- **Export:** python-docx for Word output
- **Auth:** Simple password middleware (Phase 1)
- **Brand color:** `#028a39`

---

## Environment Variables

```env
# AI Primary — Claudible (OpenAI-compatible)
CLAUDIBLE_BASE_URL=https://claudible.io/v1
CLAUDIBLE_API_KEY=sk-...
CLAUDIBLE_MODEL_STRONG=claude-opus-4.6
CLAUDIBLE_MODEL_FAST=claude-sonnet-4.6

# AI Fallback — Anthropic direct
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_MODEL_STRONG=claude-opus-4-5
ANTHROPIC_MODEL_FAST=claude-sonnet-4-5

# AI Secondary fallback — OpenAI
OPENAI_API_KEY=sk-proj-...
OPENAI_MODEL=gpt-4.1

# Database
DATABASE_URL=postgresql://user:password@host:5432/examsgen

# Auth
APP_PASSWORD=your_password
SECRET_KEY=random_secret_for_sessions
```

**CRITICAL:** Use the `requests` Python library for all AI API calls. Do NOT use `urllib` — it gets blocked by Cloudflare on the Claudible endpoint.

**AI Provider fallback logic:**
1. Try Claudible (3 retries, handle 503/429)
2. On failure → try Anthropic direct
3. On failure → try OpenAI
4. Use `claude-opus-4.6` / `claude-opus-4-5` / `gpt-4.1` for Part 2 & Part 3 (complex scenarios)
5. Use `claude-sonnet-4.6` / `claude-sonnet-4-5` / `gpt-4.1` for MCQ (faster/cheaper)

---

## File Organization (mounted at `/app/data/`)

```
/app/data/
  regulations/
    CIT/       ← CIT Law, CIT Decree, CIT Circulars (ENG preferred)
    VAT/       ← VAT Law, VAT Decree, VAT Circulars
    PIT/       ← PIT Law, PIT Circulars
    FCT/       ← FCT Circulars
    TP/        ← Transfer Pricing Decree
    ADMIN/     ← Tax Administration Law, Circulars
    SHARED/    ← Tax Rates file (used by ALL question types)
  syllabus/
    CIT_Syllabus.docx
    VAT_Syllabus.docx
    PIT_Syllabus.docx
    FCT_Syllabus.docx
    TaxAdmin_TP_Syllabus.docx
  samples/
    MCQ_CIT.docx, MCQ_VAT.docx, MCQ_PIT.docx, MCQ_FCT.docx,
    MCQ_TaxAdmin.docx, MCQ_TP.docx
    Q1_CIT.docx, Q2_PIT.docx, Q3_FCT.docx, Q4_VAT.docx
    Q5_CIT_LongForm.docx, Q6_PIT_LongForm.docx
```

Files are `.doc` and `.docx` format. Implement text extraction for both:
- `.docx`: unzip and parse `word/document.xml`, strip XML tags
- `.doc`: read binary, extract UTF-16 LE text chunks (chunks where every other byte is 0x00 and the printable ASCII byte is in range 32-126)

---

## Database Schema

```sql
CREATE TABLE regulations (
    id SERIAL PRIMARY KEY,
    sac_thue VARCHAR(20) NOT NULL,
    ten_van_ban VARCHAR(500),
    loai VARCHAR(50),           -- LAW | DECREE | CIRCULAR | SYLLABUS | TAXRATES
    ngon_ngu VARCHAR(5) DEFAULT 'ENG',
    file_path VARCHAR(500),
    file_name VARCHAR(500),
    is_active BOOLEAN DEFAULT TRUE,
    uploaded_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE questions (
    id SERIAL PRIMARY KEY,
    question_type VARCHAR(20) NOT NULL,  -- MCQ | SCENARIO_10 | LONGFORM_15
    sac_thue VARCHAR(20) NOT NULL,
    question_part INTEGER,               -- 1, 2, or 3
    question_number VARCHAR(10),         -- MCQ | Q1 | Q2 | Q3 | Q4 | Q5 | Q6
    content_json JSONB NOT NULL,
    content_html TEXT,
    model_used VARCHAR(100),
    provider_used VARCHAR(50),
    exam_session VARCHAR(20) DEFAULT 'Jun2026',
    created_at TIMESTAMP DEFAULT NOW(),
    is_starred BOOLEAN DEFAULT FALSE,
    notes TEXT,
    user_id INTEGER DEFAULT 1            -- for Phase 2 multi-user
);

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

## API Endpoints

```
POST /api/auth/login           → check APP_PASSWORD, return session token
GET  /api/health               → health check

GET  /api/regulations          → list all regulations (grouped by sac_thue)
POST /api/regulations/upload   → multipart upload .doc/.docx file
PATCH /api/regulations/{id}    → toggle is_active
DELETE /api/regulations/{id}   → soft delete
GET  /api/regulations/{id}/text → extract and return text content

POST /api/generate/mcq         → generate MCQ batch
POST /api/generate/scenario    → generate 10-mark scenario
POST /api/generate/longform    → generate 15-mark long-form

GET  /api/questions            → list questions (filters: type, sac_thue, starred, date)
GET  /api/questions/{id}       → full question detail
PATCH /api/questions/{id}/star → toggle starred
DELETE /api/questions/{id}     → delete

POST /api/export/word          → export question IDs to .docx, return file download
```

---

## Generation Request & Response

### MCQ Request
```json
POST /api/generate/mcq
{
  "sac_thue": "CIT",
  "count": 5,
  "exam_session": "Jun2026",
  "topics": ["deductible expenses", "depreciation"],
  "difficulty": "standard"
}
```

### Scenario Request
```json
POST /api/generate/scenario
{
  "question_number": "Q1",
  "sac_thue": "CIT",
  "marks": 10,
  "exam_session": "Jun2026",
  "scenario_industry": null
}
```

### Long-form Request
```json
POST /api/generate/longform
{
  "question_number": "Q5",
  "sac_thue": "CIT",
  "marks": 15,
  "exam_session": "Jun2026"
}
```

---

## Prompt Strategy (CRITICAL for quality)

### Context Assembly Order (for each generation)
1. Tax Rates (SHARED — always include, ~2K tokens)
2. Syllabus for this sac_thue (~1K tokens)
3. Active ENG regulations for this sac_thue (trim to fit, newest first, max ~40K tokens total)
4. Sample question of same type (~2K tokens)

### MCQ Prompt
```
You are a senior ACCA TX(VNM) examiner. Generate {count} MCQs on {sac_thue} for the {exam_session} exam.

REQUIREMENTS:
- Each MCQ = 2 marks
- 4 options A/B/C/D, one correct marked [key]  
- Scenario-based with specific VND amounts
- Requires multi-step calculation (not just recall)
- Distractors = specific, plausible student mistakes (wrong rate / wrong time apportionment / wrong base)
- Each option: show calculation working + explanation citing specific article/decree

TAX RATES: {tax_rates}
SYLLABUS: {syllabus}  
REGULATIONS: {regulations}
SAMPLE FORMAT (follow exactly): {sample}

Generate {count} new MCQs covering different topics and different company scenarios.
```

### Scenario (10 marks) Prompt
```
You are a senior ACCA TX(VNM) examiner. Generate Question {question_number} — a 10-mark scenario question on {sac_thue}.

STRUCTURE:
- One integrated business scenario (Vietnamese company/individual)
- {sub_questions} sub-questions labelled (a), (b), (c)...
- Marks per sub-question shown in brackets, summing to exactly 10
- Each sub-question tests a DIFFERENT aspect of {sac_thue}
- Include full marking scheme at the end

SAMPLE FORMAT: {sample_q}
REGULATIONS: {regulations}

Generate the question now. Make it CHALLENGING — students must APPLY regulations, not just recall.
```

### Long-form (15 marks) Prompt
Same structure as scenario but:
- Marks sum to 15
- More complex integrated scenario (multiple issues per sub-question)
- 5-6 sub-questions
- Mix of calculation AND written explanation sub-questions
- Detailed marking scheme showing each individual mark

---

## Frontend Pages

### `/` — Dashboard
- Cards: total questions (MCQ / Scenario / Long-form)
- Quick generate buttons
- Recent questions list (last 10)

### `/generate` — Question Generator
- Step 1: Choose type (3 cards: MCQ | Scenario Q1-Q4 | Long-form Q5-Q6)
- Step 2: Configure (sac_thue, count for MCQ, options)
- [Generate] → spinner → result preview
- Result: rendered HTML question + [Save] [Export Word] [Regenerate] buttons
- Show: model used, tokens used, generation time

### `/bank` — Question Bank
- Filter sidebar: Type / Sac Thue / Starred / Date range
- Card grid with question preview
- Click → modal with full question
- Bulk select + export

### `/regulations` — Document Management
- Tabs: CIT | VAT | PIT | FCT | TP | Admin | Shared
- List of uploaded files per tab with: name, type, language, active toggle, preview button
- Drag-and-drop upload area

### `/settings` — Settings
- API keys (show masked, click to edit)
- Default exam session
- Default model preference

---

## Output JSON Structure

### MCQ
```json
{
  "type": "MCQ",
  "sac_thue": "CIT",
  "exam_session": "Jun2026",
  "questions": [{
    "number": 1,
    "marks": 2,
    "scenario": "On 1 January 2026, ABC Manufacturing JSC...",
    "question": "What is the deductible interest expense for CIT purposes?",
    "options": {
      "A": {"text": "VND 900 million", "calculation": "20,000 × 1.5 × ...", "explanation": "Correct per Article...", "is_key": true},
      "B": {"text": "VND 1,200 million", "calculation": "full amount", "explanation": "Wrong — ignores 150% equity cap", "is_key": false},
      "C": {"text": "VND 600 million", "calculation": "...", "explanation": "Wrong — uses 100% equity", "is_key": false},
      "D": {"text": "VND 0", "calculation": "...", "explanation": "Wrong — interest is deductible if conditions met", "is_key": false}
    },
    "regulation_refs": ["Article 9, Law 67/2025/QH15"]
  }]
}
```

### Scenario
```json
{
  "type": "SCENARIO_10",
  "question_number": "Q1",
  "sac_thue": "CIT",
  "marks": 10,
  "scenario": "You should assume today is 1 February 2026...",
  "sub_questions": [{
    "label": "(a)",
    "marks": 3,
    "question": "Calculate the CIT liability...",
    "answer": "Step 1: ...",
    "marking_scheme": [
      {"point": "Identify non-deductible fine (VND 400m)", "mark": 1},
      {"point": "Apply interest cap correctly", "mark": 1},
      {"point": "Correct total deductible expenses", "mark": 1}
    ]
  }]
}
```

---

## Docker & Deployment

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
RUN cd frontend && npm install && npm run build
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

Serve React build as static files from FastAPI using `StaticFiles`. Single Docker container, no nginx needed.

Network: `coolify` (external Docker network on VPS)

Traefik labels:
```
traefik.enable=true
traefik.http.routers.examsgen.rule=Host(`examsgen.gpt4vn.com`)
traefik.http.routers.examsgen.tls.certresolver=letsencrypt
traefik.http.services.examsgen.loadbalancer.server.port=8000
```

---

## Important Implementation Notes

1. **Regulations text extraction:** Implement both `.docx` (zipfile + XML parse) and `.doc` (UTF-16 LE binary scan) extractors. Both formats exist in the data.

2. **Context window management:** Total prompt must stay under 150,000 chars (~37K tokens). If regulations are too long, truncate: keep first N chars of each file, prioritizing newer regulations.

3. **Streaming:** Implement SSE streaming for the generate endpoint so UI shows tokens appearing in real-time (better UX for 30-60 second generations).

4. **Word export:** Use `python-docx` to create properly formatted exam-style documents with correct fonts (Times New Roman), margins, and numbering.

5. **Phase 1 auth:** Simple middleware checking `Authorization: Bearer {APP_PASSWORD}` or session cookie. No user registration needed.

6. **Error handling:** If AI returns malformed JSON, retry once with stricter prompt ("return ONLY valid JSON, no markdown"). Then fall back to storing raw text.

7. **Sample files seeding:** On first startup, check if `/app/data/samples/` is empty. If so, log warning that admin must upload sample files via the Regulations UI.
