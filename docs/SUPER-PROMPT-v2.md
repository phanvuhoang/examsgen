# ExamsGen — AI-Powered ACCA TX(VNM) Exam Question Generator
## Comprehensive Product Brief for Super-App Creator

---

## What is ExamsGen?

ExamsGen is a web application that helps ACCA TX(VNM) tax educators generate professional-quality exam questions about Vietnamese taxation. It uses AI (Claude/GPT-4) to create questions that match the exact style, structure, difficulty, and format of real ACCA past exam papers — but with fresh scenarios, different companies, and up-to-date regulations.

The target user is an experienced tax professional and ACCA instructor who wants to:
- Generate practice exam questions quickly without writing from scratch
- Ensure questions are grounded in current Vietnamese tax law
- Replicate the style of specific past exam questions
- Build a curated library of high-quality questions

---

## The ACCA TX(VNM) Exam Structure

The exam has 3 parts with fixed structure:

**Part 1 — MCQ (Multiple Choice)**
- 2 marks each, 4 options (A/B/C/D)
- Scenario-based, requires multi-step calculation
- Covers: CIT, VAT, PIT, FCT, Tax Administration, Transfer Pricing

**Part 2 — Scenario Questions (10 marks each)**
- Q1=CIT, Q2=PIT, Q3=FCT, Q4=VAT
- One business scenario with 3-5 sub-questions

**Part 3 — Long-form Questions (15 marks each)**
- Q5=CIT (complex), Q6=PIT (complex)
- 5-6 sub-questions, mix of calculation + written

Tax types: CIT (Corporate Income Tax), VAT, PIT (Personal Income Tax), FCT (Foreign Contractor Tax), Tax Administration, Transfer Pricing

---

## Core Features (Already Built)

### 1. Question Generation
- Generate any question type: MCQ / Scenario (10 marks) / Long-form (15 marks)
- Choose tax type (CIT, VAT, PIT, FCT, etc.)
- Choose AI model: Sonnet (fast) or Opus (best quality)
- AI reads uploaded regulations + syllabus + sample questions as context
- Returns full question with answer/marking scheme in JSON → rendered as HTML

### 2. Question Bank
- All generated questions saved to PostgreSQL database
- Filter by type, tax type, starred, date
- Export selected questions to Word (.docx)
- Star/annotate favorites

### 3. Regulation Document Management
- Upload .doc/.docx regulation files via UI
- Organized by tax type: CIT / VAT / PIT / FCT / TP / Admin / Shared
- Toggle which files are active for AI context
- Files pre-loaded: CIT Law 67/2025, VAT Law 48/2024, VAT Decree 181/2025, PIT VBHN 02, FCT Circular 103/2014, Tax Admin VBHN 15, Transfer Pricing Decree 132/2020, Tax Rates Jun2026, etc.

### 4. Custom Instructions
- **Pick from Question Bank**: select a saved question as style reference
- **Paste sample or describe**: textarea to paste any Q&A for style replication OR describe in English/Vietnamese what question to generate (e.g. "Write a CIT Q1 about a manufacturing company with issues on salary deductibility and depreciation of leased equipment")

---

## New Features Needed

### 5. Knowledge Base (KB) — The Core Enhancement

This is the main feature to add. Instead of feeding AI ALL regulations and ALL samples at once (which makes it generic), build a structured mini-database where the user can:

**a. Syllabus Chunking**
Break each syllabus document into individual items (one row per syllabus topic). Example rows:
- CIT-A1: "Definition of taxable income"
- CIT-B2: "Deductible expenses — general conditions"  
- CIT-B3: "Deductible expenses — salary and wages"
- CIT-C1: "Tax loss carry forward"

**b. Regulation Chunking**
Break regulations into individual paragraphs (one row per rule). Example rows:
- "Article 9.2c, Decree 320/2025: Salary expenses deductible if included in labor contract"
- "Article 9.2d, Decree 320/2025: Interest expense cap at 30% EBITDA, max 150% equity"
- "Article 4.8, Circular 96/2015: Depreciation — useful life per MOF schedule"

Each regulation chunk is linked to one or more syllabus items.

**c. Sample Question Library**
A curated library of sample questions (separate from the generated Question Bank). Each sample:
- Has a title and description of exam tricks it contains (e.g. "time apportionment, interest cap, foreign salary")
- Is linked to specific syllabus items and regulation paragraphs it tests
- Can be imported from the Question Bank or added manually

**d. Auto-Parse (AI-assisted)**
The app can auto-chunk regulation and syllabus files using AI — splitting into logical paragraphs and auto-generating tags. User reviews and approves the chunks. If user prefers, they can also copy-paste paragraphs manually.

### 6. KB-Targeted Generation

When generating a question, user can optionally specify:
- **Which syllabus items to test** (multi-select from KB)
- **Which regulation paragraphs to use** (multi-select from KB)  
- **Which sample questions to use as style reference** (multi-select from KB)

The AI then receives ONLY these specific, targeted items in its context — instead of entire documents. This produces:
- Questions that specifically test chosen regulation articles
- Questions that match the style and tricks of chosen samples
- Harder, more precise questions because context is focused

Example workflow:
> User selects: [CIT-B3 salary deductibility] + [Art.9.2d interest cap] + [Sample: Q1 Dec2023 time apportionment trick] → Generate → AI creates a scenario testing exactly these 2 rules in the style of Dec2023 Q1

---

## Technical Architecture

### Suggested Stack
The app should use whatever stack works best for a single-container deployment on a VPS with Docker. Current implementation uses Python FastAPI + React but the creator can suggest improvements.

### Key Requirements
- **Single Docker container** (backend serves frontend static files)
- **PostgreSQL database** (external, already provisioned)
- **AI API** using OpenAI-compatible endpoint (primary: Claudible proxy, fallback: Anthropic, fallback: OpenAI)
- **File handling**: .doc and .docx extraction (both formats)
- **Export**: Word document (.docx) for exam papers
- **Auth**: Simple password-based (single admin user for Phase 1)
- **Deploy**: Docker on VPS, Traefik reverse proxy, domain examsgen.gpt4vn.com

### Current DB Tables
```
regulations     — uploaded regulation/syllabus files metadata
questions       — generated questions (JSONB content)
generation_log  — AI usage logs
```

### New DB Tables Needed (KB Layer)
```
kb_syllabus         — syllabus chunks (id, sac_thue, section_code, section_title, content, tags)
kb_regulation       — regulation paragraphs (id, sac_thue, regulation_ref, content, tags, syllabus_ids[])
kb_sample_question  — curated samples (id, type, sac_thue, title, content, exam_tricks, syllabus_ids[], regulation_ids[])
kb_auto_parsed      — track AI parsing jobs
```

### AI Provider (IMPORTANT)
- Use `requests` library for ALL API calls (urllib is blocked by Cloudflare)
- Primary: Claudible (OpenAI-compatible endpoint, cost $0)
- Fallback: Anthropic direct API
- Fallback: OpenAI API
- Strong model (claude-opus-4.6 or equivalent) for scenario/longform generation
- Fast model (claude-sonnet-4.6 or equivalent) for MCQ and auto-parsing

---

## Pages / Navigation

Current pages:
1. **Dashboard** — stats + quick generate + recent questions
2. **Generate** — question generator with all options
3. **Question Bank** — browse/filter/export saved questions
4. **Regulations** — upload and manage regulation files
5. **Settings** — API keys, preferences

New page to add:
6. **Knowledge Base** (`/kb`) — manage syllabus chunks, regulation paragraphs, sample question library

---

## User Workflow (Target Experience)

### Quick generate (current capability)
1. Go to Generate
2. Pick type + tax + model
3. Optionally describe what you want
4. Click Generate → save to bank

### Precise KB-targeted generation (new capability)
1. Go to KB → upload/parse syllabus → review chunks
2. Go to KB → upload/parse regulation → review chunks → link to syllabus items
3. Go to KB → import a past exam question → annotate with exam tricks → link to chunks
4. Go to Generate → enable KB targeting
5. Search and select: 2 syllabus items + 3 regulation paragraphs + 1 style reference
6. Click Generate → AI produces precisely targeted question
7. Review → save to Question Bank → export to Word

---

## Brand & Design

- Primary color: `#028a39` (dark green)
- Clean professional UI suitable for tax/accounting educators
- No unnecessary animations — utility first

---

## What the App Does NOT Need (Phase 1)

- Multi-user registration/login (single admin user is enough)
- Real-time collaboration
- LMS integration
- Student-facing interface
- Automated marking/grading
- Mobile-specific optimization

---

## Questions for Super-App Creator

Feel free to ask if you need clarification on:
- The ACCA exam structure or question format
- How the KB targeting should work in the generate prompt
- The auto-parse chunking logic
- File format details (.doc binary extraction vs .docx XML)
- Deployment requirements

The goal is a working, production-quality app that a non-developer can use daily to generate exam questions. Reliability and output quality matter more than feature breadth.

---

## Feature 7: Conversational Question Refinement

After a question is generated, a **chat panel** appears below the preview. The user can chat with AI to refine the question iteratively — in English or Vietnamese.

Examples:
- *"Make it harder, add a loss carry-forward from prior year"*
- *"Thêm vấn đề về chuyển giá liên quan đến công ty mẹ Hàn Quốc"*
- *"Change the company to a food manufacturing firm with revenue ~50 billion VND"*
- *"Split part (b) into two sub-questions worth 2 marks each"*

The AI receives: current question JSON + full conversation history + new instruction → returns updated complete question JSON. The preview updates in real-time.

**Key design decisions:**
- Chat history lives in frontend state only — no backend storage needed
- Default model: Sonnet (fast enough, saves cost)
- Max 10 exchanges in history to avoid context overflow
- "Save to bank" always saves the LATEST version
- Reset chat when user clicks "Regenerate"
- Works for all question types: MCQ, Scenario, Long-form
