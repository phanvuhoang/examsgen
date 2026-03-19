# ACCA TX(VNM) Exam Question Generator — Claude Code Brief

## Project Overview

Build a web application that uses AI to generate ACCA TX(VNM) exam-standard questions about Vietnam taxation. The app reads official tax regulations and syllabus, then generates questions matching the style, difficulty, and format of real ACCA past exam papers.

**GitHub repo:** `examsgen`  
**Target domain:** `examsgen.gpt4vn.com` (or as configured)  
**Deploy:** Docker on VPS via SSH (72.62.197.183), reverse-proxy via Traefik

---

## Tech Stack

- **Backend:** Python FastAPI
- **Frontend:** React + Tailwind CSS
- **Database:** PostgreSQL (same VPS DB cluster, host `10.0.1.11`, user `legaldb_user`)
- **AI:** Claudible API (OpenAI-compatible) with Anthropic fallback
- **File storage:** Local `/app/data/` directory (mounted volume)
- **Brand color:** `#028a39` (green)

---

## Environment Variables

```env
# AI — Primary
CLAUDIBLE_BASE_URL=https://claudible.io/v1
CLAUDIBLE_API_KEY=your_claudible_key
CLAUDIBLE_MODEL_STRONG=claude-opus-4.6      # for Part 2 & Part 3 questions
CLAUDIBLE_MODEL_FAST=claude-sonnet-4.6      # for MCQ

# AI — Fallback (when Claudible returns 503/timeout)
ANTHROPIC_API_KEY=your_anthropic_key
ANTHROPIC_MODEL_STRONG=claude-opus-4-5
ANTHROPIC_MODEL_FAST=claude-sonnet-4-5

# AI — Secondary fallback
OPENAI_API_KEY=your_openai_key
OPENAI_MODEL=gpt-4.1

# Database
DATABASE_URL=postgresql://legaldb_user:PASSWORD@10.0.1.11:5432/examsgen

# App
APP_PASSWORD=your_admin_password   # simple password gate for Phase 1
SECRET_KEY=your_secret_key
```

---

## AI Provider Logic

```python
# Priority: Claudible → Anthropic → OpenAI
# Use `requests` library (NOT urllib — Cloudflare blocks urllib User-Agent)
# Retry logic: 3 attempts per provider, then fallback to next

async def call_ai(prompt, model_tier="strong"):
    providers = [
        ("claudible", CLAUDIBLE_BASE_URL, CLAUDIBLE_API_KEY, 
         CLAUDIBLE_MODEL_STRONG if model_tier=="strong" else CLAUDIBLE_MODEL_FAST),
        ("anthropic_compat", "https://api.anthropic.com/v1", ANTHROPIC_API_KEY,
         ANTHROPIC_MODEL_STRONG if model_tier=="strong" else ANTHROPIC_MODEL_FAST),
        ("openai", "https://api.openai.com/v1", OPENAI_API_KEY, OPENAI_MODEL),
    ]
    for provider_name, base_url, api_key, model in providers:
        for attempt in range(3):
            try:
                response = requests.post(
                    f"{base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}", 
                             "Content-Type": "application/json"},
                    json={"model": model, "messages": [...], "max_tokens": 6000},
                    timeout=120
                )
                if response.status_code == 200:
                    return response.json()['choices'][0]['message']['content']
                elif response.status_code in [503, 429]:
                    time.sleep(5 * (attempt + 1))
                    continue
            except:
                continue
    raise Exception("All AI providers failed")
```

---

## Database Schema

```sql
-- Regulations files metadata
CREATE TABLE regulations (
    id SERIAL PRIMARY KEY,
    sac_thue VARCHAR(20) NOT NULL,  -- CIT, VAT, PIT, FCT, TP, ADMIN
    ten_van_ban VARCHAR(500),
    loai VARCHAR(50),               -- LAW, DECREE, CIRCULAR, SYLLABUS, TAXRATES
    ngon_ngu VARCHAR(5) DEFAULT 'ENG',  -- ENG or VIE
    file_path VARCHAR(500),
    file_name VARCHAR(500),
    is_active BOOLEAN DEFAULT TRUE,
    uploaded_at TIMESTAMP DEFAULT NOW()
);

-- Generated questions bank
CREATE TABLE questions (
    id SERIAL PRIMARY KEY,
    question_type VARCHAR(20) NOT NULL,  -- MCQ, SCENARIO_10, LONGFORM_15
    sac_thue VARCHAR(20) NOT NULL,       -- CIT, VAT, PIT, FCT, TP, ADMIN, MIXED
    question_part INTEGER,               -- 1 (MCQ), 2 (Q1-Q4), 3 (Q5-Q6)
    question_number VARCHAR(10),         -- Q1, Q2, Q3, Q4, Q5, Q6, or MCQ
    content_json JSONB NOT NULL,         -- full structured question data
    content_html TEXT,                   -- rendered HTML for display
    regulation_ids INTEGER[],            -- which regulations were used
    model_used VARCHAR(100),
    provider_used VARCHAR(50),
    exam_session VARCHAR(20),            -- e.g. "Jun2026"
    created_at TIMESTAMP DEFAULT NOW(),
    is_starred BOOLEAN DEFAULT FALSE,
    notes TEXT
);

-- Generation sessions (audit log)  
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
    status VARCHAR(20),  -- success, failed
    error TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);
```

---

## File Storage Structure

```
/app/data/
  regulations/
    CIT/
      CIT_Law_67_2025_ENG.doc
      CIT_Decree_320_2025_ENG.doc
    VAT/
      VAT_Law_48_2024_ENG.doc
      VAT_Decree_181_2025_ENG.doc
    PIT/
    FCT/
    TP/
    ADMIN/
    SHARED/
      Tax_Rates_Jun2026.docx    ← used in all questions
  syllabus/
    CIT_Syllabus.docx
    VAT_Syllabus.docx
    PIT_Syllabus.docx
    FCT_Syllabus.docx
    TaxAdmin_TP_Syllabus.docx
  samples/
    MCQ_CIT_Sample.docx
    MCQ_VAT_Sample.docx
    MCQ_PIT_Sample.docx
    MCQ_FCT_Sample.docx
    MCQ_TaxAdmin_Sample.docx
    MCQ_TP_Sample.docx
    Q1_CIT_Sample.docx          ← 10-mark scenario
    Q2_PIT_Sample.docx
    Q3_FCT_Sample.docx
    Q4_VAT_Sample.docx
    Q5_CIT_LongForm_Sample.docx ← 15-mark long-form
    Q6_PIT_LongForm_Sample.docx
```

---

## API Endpoints

```
# Document Management
GET  /api/regulations          → list all uploaded regulations
POST /api/regulations/upload   → upload new regulation file
DELETE /api/regulations/{id}   → deactivate a regulation
GET  /api/regulations/{id}/preview → extract and show text content

# Question Generation
POST /api/generate/mcq         → generate MCQ batch
POST /api/generate/scenario    → generate Part 2 scenario question
POST /api/generate/longform    → generate Part 3 long-form question

# Question Bank
GET  /api/questions            → list generated questions (filter by type/sac_thue)
GET  /api/questions/{id}       → get full question detail
PUT  /api/questions/{id}/star  → star/unstar question
DELETE /api/questions/{id}     → delete question

# Export
POST /api/export/word          → export questions to .docx
POST /api/export/pdf           → export questions to PDF

# System
GET  /api/health               → health check
```

---

## Generation Request Payloads

### MCQ Generation
```json
POST /api/generate/mcq
{
  "sac_thue": "CIT",           // CIT | VAT | PIT | FCT | TP | ADMIN
  "count": 5,                  // number of MCQs (1-10)
  "topics": ["deductible expenses", "depreciation"],  // optional focus
  "exam_session": "Jun2026",
  "difficulty": "standard"     // standard | hard
}
```

### Scenario (Part 2) Generation
```json
POST /api/generate/scenario
{
  "question_number": "Q1",    // Q1 (CIT) | Q2 (PIT) | Q3 (FCT) | Q4 (VAT)
  "sac_thue": "CIT",
  "marks": 10,
  "sub_questions": 4,          // typically 3-5 sub-questions summing to 10 marks
  "exam_session": "Jun2026",
  "scenario_industry": null    // null = AI chooses, or "manufacturing", "services", etc.
}
```

### Long-form (Part 3) Generation
```json
POST /api/generate/longform
{
  "question_number": "Q5",    // Q5 (CIT) | Q6 (PIT)
  "sac_thue": "CIT",
  "marks": 15,
  "exam_session": "Jun2026"
}
```

---

## Prompt Engineering — Context Assembly

For each generation request, assemble context in this order:

```python
def build_context(sac_thue, question_type):
    parts = []
    
    # 1. Tax Rates (always included — used by all questions)
    parts.append(read_file("SHARED/Tax_Rates_Jun2026.docx"))
    
    # 2. Syllabus for this sac_thue (scope of what can be tested)
    parts.append(read_file(f"syllabus/{sac_thue}_Syllabus.docx"))
    
    # 3. Regulations for this sac_thue (active files only, ENG preferred)
    for reg in get_active_regulations(sac_thue, lang="ENG"):
        text = extract_text(reg.file_path)
        parts.append(f"## {reg.ten_van_ban}\n{text[:40000]}")
    
    # 4. Sample questions of same type
    if question_type == "MCQ":
        parts.append(read_sample(f"MCQ_{sac_thue}_Sample.docx"))
    elif question_type == "SCENARIO_10":
        q_num = SAC_THUE_TO_QUESTION[sac_thue]  # CIT→Q1, PIT→Q2, etc.
        parts.append(read_sample(f"{q_num}_{sac_thue}_Sample.docx"))
    elif question_type == "LONGFORM_15":
        q_num = "Q5" if sac_thue == "CIT" else "Q6"
        parts.append(read_sample(f"{q_num}_{sac_thue}_LongForm_Sample.docx"))
    
    return "\n\n".join(parts)
```

### MCQ Prompt Template
```
You are a senior ACCA TX(VNM) examiner. Generate {count} MCQ question(s) on {sac_thue}.

EXAM STANDARDS:
- Each MCQ = 2 marks
- 4 options (A/B/C/D), one correct marked [key]
- Requires multi-step calculation, NOT just recall
- Distractors = plausible common student mistakes
- Cite specific articles from 2025/2026 regulations

TAX RATES:
{tax_rates}

SYLLABUS SCOPE:
{syllabus}

REGULATIONS:
{regulations}

SAMPLE FORMAT (follow EXACTLY):
{sample_questions}

Generate {count} NEW MCQs. Different scenarios, different companies.
Topics to cover: {topics}
```

### Scenario (10 marks) Prompt Template
```
You are a senior ACCA TX(VNM) examiner. Generate a Part 2 scenario question worth 10 marks.

FORMAT: One integrated business scenario with {sub_questions} sub-questions.
Total marks must sum to exactly 10.
Each sub-question has a mark allocation shown in brackets e.g. (3 marks)

SCENARIO REQUIREMENTS:
- Vietnamese company or individual with realistic business context
- Multiple tax issues in ONE scenario (integrated)
- Each sub-question tests a DIFFERENT aspect
- Include a marking scheme at the end

SAMPLE QUESTION FORMAT:
{sample_q}

REGULATIONS:
{regulations}

Generate Question {question_number} on {sac_thue} (10 marks):
```

### Long-form (15 marks) Prompt Template  
Similar to scenario but:
- More complex integrated scenario
- More sub-questions (typically 5-6)
- Marks sum to 15
- More detailed marking scheme
- May involve computation AND written explanation sub-questions

---

## Document Text Extraction

```python
import zipfile, re, struct

def extract_text(file_path):
    """Extract text from .docx or .doc files"""
    if file_path.endswith('.docx'):
        return extract_docx(file_path)
    elif file_path.endswith('.doc'):
        return extract_doc_binary(file_path)
    return ""

def extract_docx(path):
    with zipfile.ZipFile(path) as z:
        with z.open('word/document.xml') as f:
            xml = f.read().decode('utf-8')
    text = re.sub(r'<[^>]+>', ' ', xml)
    return re.sub(r'\s+', ' ', text).strip()

def extract_doc_binary(path):
    """Extract UTF-16 LE text from legacy .doc binary format"""
    with open(path, 'rb') as f:
        data = f.read()
    text_chunks = []
    i = 0
    while i < len(data) - 1:
        if data[i+1] == 0 and 32 <= data[i] < 127:
            chunk = bytearray()
            while i < len(data)-1 and data[i+1]==0 and (32 <= data[i] < 127 or data[i] in [9,10,13]):
                chunk.append(data[i])
                i += 2
            if len(chunk) > 15:
                text_chunks.append(chunk.decode('ascii', errors='ignore'))
        else:
            i += 1
    text = ' '.join(text_chunks)
    return re.sub(r'\s+', ' ', text).strip()
```

---

## Frontend — Page Structure

### Main Layout
- **Left sidebar** (240px): Navigation menu
- **Main content**: Current page

### Pages

#### 1. Dashboard (`/`)
- Stats: total questions generated, by type, by sac_thue
- Quick generate buttons: [MCQ CIT], [Q1 CIT], [Q5 CIT], etc.
- Recent generations list

#### 2. Generate (`/generate`)
- **Step 1:** Select question type
  - Part 1: MCQ → select sac_thue + count (1-10)
  - Part 2: Scenario Q1/Q2/Q3/Q4 → auto-maps to sac_thue
  - Part 3: Long-form Q5/Q6 → auto-maps to sac_thue
- **Step 2:** Optional settings
  - Exam session (Jun 2026 default)
  - Topics focus (optional)
  - Industry/scenario hint (optional)
- **[Generate]** button → loading spinner → result panel
- **Result panel:**
  - Preview rendered question (HTML)
  - [Export Word] / [Export PDF] / [Save to Bank] buttons
  - [Regenerate] button (same params, new question)
  - Token usage + model used shown

#### 3. Question Bank (`/bank`)
- Filter by: type / sac_thue / date / starred
- List view with preview snippet
- Click → full question view
- Bulk export selected questions

#### 4. Regulations (`/regulations`)
- Tabs: CIT / VAT / PIT / FCT / TP / Admin / Shared
- Per tab: list of uploaded files (name, type, language, active toggle)
- [Upload File] button per tab
- File preview (extract text and show)
- [Set Active/Inactive] toggle

#### 5. Settings (`/settings`)
- API keys (masked, editable)
- Default exam session
- Default model (Sonnet/Opus)

---

## Question Output Format (JSON stored in DB)

### MCQ
```json
{
  "type": "MCQ",
  "sac_thue": "CIT",
  "exam_session": "Jun2026",
  "questions": [
    {
      "number": 1,
      "marks": 2,
      "scenario": "On 1 January 2026, ABC Co...",
      "question": "What is the deductible expense for CIT purposes?",
      "options": {
        "A": {"text": "VND 500 million", "calculation": "...", "explanation": "...", "is_key": false},
        "B": {"text": "VND 450 million", "calculation": "...", "explanation": "...", "is_key": false},
        "C": {"text": "VND 420 million", "calculation": "...", "explanation": "... per Article X Decree 320/2025", "is_key": true},
        "D": {"text": "VND 600 million", "calculation": "...", "explanation": "...", "is_key": false}
      },
      "regulation_refs": ["Article 9, Law 67/2025/QH15", "Article 15, Decree 320/2025/ND-CP"]
    }
  ]
}
```

### Scenario (10 marks)
```json
{
  "type": "SCENARIO_10",
  "question_number": "Q1",
  "sac_thue": "CIT",
  "marks": 10,
  "exam_session": "Jun2026",
  "scenario": "You should assume today is 1 February 2026. XYZ JSC is a Vietnamese company...",
  "sub_questions": [
    {
      "label": "(a)",
      "marks": 3,
      "question": "Calculate the deductible expenses...",
      "answer": "...",
      "marking_scheme": [
        {"point": "Identify non-deductible fine", "mark": 1},
        {"point": "Apply interest cap correctly", "mark": 1},
        {"point": "Correct total", "mark": 1}
      ]
    }
  ],
  "regulation_refs": ["..."]
}
```

---

## Export to Word (.docx)

Use `python-docx` library to generate properly formatted Word documents:

```python
from docx import Document
from docx.shared import Pt, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH

def export_to_word(questions, filename):
    doc = Document()
    # Header
    doc.add_heading('ACCA TX(VNM) — Generated Exam Questions', 0)
    doc.add_paragraph(f'Generated: {datetime.now().strftime("%d %B %Y")}')
    
    for q in questions:
        if q['type'] == 'MCQ':
            render_mcq_word(doc, q)
        elif q['type'] == 'SCENARIO_10':
            render_scenario_word(doc, q)
        elif q['type'] == 'LONGFORM_15':
            render_longform_word(doc, q)
    
    doc.save(filename)
```

---

## Docker Setup

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

```yaml
# docker-compose.yml
version: '3.8'
services:
  app:
    build: .
    ports: ["8000:8000"]
    environment:
      - CLAUDIBLE_BASE_URL=${CLAUDIBLE_BASE_URL}
      - CLAUDIBLE_API_KEY=${CLAUDIBLE_API_KEY}
      - CLAUDIBLE_MODEL_STRONG=${CLAUDIBLE_MODEL_STRONG}
      - CLAUDIBLE_MODEL_FAST=${CLAUDIBLE_MODEL_FAST}
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - DATABASE_URL=${DATABASE_URL}
      - APP_PASSWORD=${APP_PASSWORD}
    volumes:
      - /data/examsgen:/app/data
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.examsgen.rule=Host(`examsgen.gpt4vn.com`)"
      - "traefik.http.routers.examsgen.tls.certresolver=letsencrypt"
    networks:
      - coolify
networks:
  coolify:
    external: true
```

---

## Requirements.txt

```
fastapi==0.115.0
uvicorn==0.30.0
requests==2.32.0
psycopg2-binary==2.9.9
python-docx==1.1.2
python-multipart==0.0.9
pydantic==2.7.0
python-jose==3.3.0
passlib==1.7.4
aiofiles==23.2.1
```

---

## Deployment Script

```bash
#!/bin/bash
# deploy.sh — run on VPS
ssh root@72.62.197.183 << 'EOF'
  mkdir -p /data/examsgen/{regulations/{CIT,VAT,PIT,FCT,TP,ADMIN,SHARED},syllabus,samples}
  cd /opt/examsgen
  git pull origin main
  docker build -t examsgen .
  docker stop examsgen 2>/dev/null; docker rm examsgen 2>/dev/null
  docker run -d \
    --name examsgen \
    --network coolify \
    --env-file /opt/examsgen/.env \
    -v /data/examsgen:/app/data \
    -p 8001:8000 \
    examsgen
  echo "Deployed!"
EOF
```

---

## Notes for Claude Code

1. **Use `requests` library** for all AI API calls — `urllib` gets CF blocked by Claudible
2. **Regulations are .doc and .docx** — implement both extractors
3. **Context trimming:** if total context > 150K chars, prioritize: TaxRates > Syllabus > Latest regulations > Older regulations
4. **Phase 1:** Single user, simple password auth (`APP_PASSWORD` env var checked via middleware)
5. **Phase 2 (future):** Multi-user with JWT — design DB with `user_id` field on `questions` table even in Phase 1
6. **Primary color:** `#028a39` throughout UI
7. **Upload initial regulation files** after deployment — files listed in `/app/data/` folder structure above
8. **GitHub repo:** `examsgen` (already created by user)
