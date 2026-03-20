# ExamsGen — AI-Powered ACCA TX(VNM) Exam Question Generator
## Comprehensive Product Description for Super-App Creator

---

## What is this app?

**ExamsGen** is a web application for an ACCA TX(VNM) tax educator to generate, refine, and manage professional exam questions about Vietnamese taxation. 

The user is an experienced tax consultant (30 years, Big 4 Vietnam) who also teaches ACCA TX(VNM). He needs to create original practice exam questions that:
- Match the exact style, structure, and difficulty of real ACCA past exam papers
- Are grounded in current Vietnamese tax law (specific articles, decrees, circulars)
- Can be customized for different exam sessions (June 2026, December 2026, etc.)
- Can be exported to Word documents for distribution to students

The app uses AI (Claude/GPT) to generate questions, and the user can refine them through natural conversation.

---

## The ACCA TX(VNM) Exam Structure

**Section A — Multiple Choice (MCQ)**
- 2 marks each, 4 options (A/B/C/D), one correct
- Scenario-based with specific VND amounts
- Requires multi-step calculation
- All 6 tax types tested: CIT, VAT, PIT, FCT, Tax Administration, Transfer Pricing

**Section B — Scenario Questions**
- Q1 = CIT (10 marks), Q2 = PIT (10 marks), Q3 = FCT (10 marks), Q4 = VAT (10 marks)
- One business scenario with 3-5 sub-questions (a)(b)(c)...
- Mix of calculation and written explanation

**Section C — Long-form Questions**
- Q5 = CIT complex (15 marks), Q6 = PIT complex (15 marks)
- 5-6 sub-questions, higher difficulty

**Tax types:** CIT (Corporate Income Tax), VAT, PIT (Personal Income Tax), FCT (Foreign Contractor Tax), Tax Administration, Transfer Pricing

---

## Current App — What's Already Built

### Tech Stack
- **Backend:** Python FastAPI, PostgreSQL (external), Docker
- **Frontend:** React (Vite), Tailwind CSS
- **AI:** OpenAI-compatible API (primary: Claudible proxy, fallback: Anthropic, fallback: OpenAI)
- **Deploy:** Single Docker container, serves React static files + API, Traefik reverse proxy

### Core Features Working Today

**1. Question Generation**
Three endpoints: `/api/generate/mcq`, `/api/generate/scenario`, `/api/generate/longform`
- Select: tax type, exam session, AI model (Sonnet/Opus), difficulty
- AI reads active regulation files + syllabus as context
- Returns full JSON with scenario + questions + answers + mark scheme
- Default MCQ: 3 questions, max_tokens 8000, robust JSON parsing with fallbacks

**2. Conversational Refinement**
After generating, a chat panel lets user refine the question:
- `/api/generate/refine` accepts: current question JSON + conversation history + new instruction
- Understands English and Vietnamese instructions
- Returns updated complete question JSON + plain-text explanation of changes
- Frontend: chat bubble UI below question preview, auto-scrolls, Enter to send

**3. Question Bank**
- All generated questions saved to `questions` table (PostgreSQL, JSONB content)
- Filter by type, tax type, starred, session, date
- Star/annotate questions
- Export selected questions to Word (.docx)
- Import question into Knowledge Base as style reference

**4. Exam Sessions** ← KEY ARCHITECTURE
Each session is an independent container:
- `exam_sessions` table: id, name, exam_window_start/end, regulations_cutoff, fiscal_year_end, tax_year
- June 2026: regulations_cutoff = 2025-12-31, fiscal_year_end = 2025-12-31, tax_year = 2025
- December 2026: same cutoffs (ACCA uses same regulations for both 2026 sessions)
- Sessions are selectable from global navbar selector (stored in localStorage)
- Generate prompt automatically injects: "Only use regulations effective up to {cutoff}. Fiscal year ends {fiscal_year_end}."
- Sessions can be cloned: copy all KB items from one session to another (`/api/sessions/{id}/clone-from/{source_id}`)

**5. Knowledge Base (KB)** ← Session-scoped
Three tables, all have `session_id` foreign key:

`kb_syllabus` — syllabus items (one row per topic)
- Fields: sac_thue, section_code, section_title, content, tags, session_id

`kb_regulation` — regulation paragraphs (one row per article/clause)  
- Fields: sac_thue, regulation_ref, content, tags, syllabus_ids[], session_id

`kb_sample` — curated sample questions as style references
- Fields: question_type, sac_thue, title, content, exam_tricks, syllabus_ids[], regulation_ids[], session_id

**6. AI Parse & Match** (`/api/sessions/{id}/parse-and-match`)
- Upload a regulation or syllabus .doc/.docx file
- AI chunks it into ~30-50 logical paragraphs, auto-tags each
- If regulation: AI auto-matches each chunk to existing syllabus items (suggests links)
- Returns chunks with suggested syllabus_ids for user review
- Review Panel: user can edit section_code, section_title, tags, approve/reject each chunk, adjust syllabus links
- Save approved chunks: `/api/sessions/{id}/save-parsed-chunks`

**7. KB-Targeted Generation**
In the Generate page, under "Custom Instructions":
- Multi-select syllabus items to test
- Multi-select regulation paragraphs to use  
- Multi-select style reference samples
- Selected items injected into prompt with HIGH PRIORITY instruction: "Question MUST cover these specifically"

**8. Custom Instructions (free-form)**
- Paste any Q&A as style reference, OR
- Describe in English/Vietnamese: "Write a Q1 CIT scenario about a manufacturing company with deductible expense issues and time apportionment"

**9. Regulation File Management**
- Upload .doc/.docx files via UI
- Organized by folder: regulations/CIT/, regulations/VAT/, etc.
- Toggle files active/inactive per session
- Pre-loaded files: CIT Law 67/2025, VAT Law 48/2024, VAT Decree 181/2025, PIT VBHN, FCT Circular 103/2014, Tax Admin VBHN, Transfer Pricing Decree 132/2020, Tax Rates reference

---

## What Still Needs Improvement / New Features

The app works well. These are the enhancement ideas — the super-app creator should assess which to implement and suggest the best approach:

### Enhancement 1: Better Session Management UX
Currently session selector is in navbar. Needs:
- Dedicated `/sessions` page with card grid (each session = a card)
- Card shows: name, exam window, cutoff date, stats (X syllabus items, Y regulation chunks, Z questions)
- [+ New Session] modal with fields: name, exam_window dates, regulations_cutoff, fiscal_year_end, tax_year
- [Carry Forward KB] option when creating new session — copies KB items from a previous session
- [Edit] session details
- After creation: prompt "Parse regulation files now?" or "Carry forward from [previous session]?"

### Enhancement 2: Parse & Match Review UX Polish
The current review panel works but needs to be cleaner:
- Show chunks as cards, not table rows
- Full content preview expandable per chunk
- Bulk select/deselect
- Edit tags inline (tag chips with ×, input to add)
- Progress indicator during AI parse (it takes 10-20 seconds)
- After save: "Parsed 34 chunks. Want to parse another file?"

### Enhancement 3: Match Quality Improvement  
Currently AI matches regulation chunks to syllabus items in one shot. Needs:
- Show match confidence visually (e.g. green = strong match, yellow = weak)
- Allow user to search and manually add/remove syllabus links per chunk
- "Unmapped" filter to find regulation chunks with no syllabus link

### Enhancement 4: Question Export Polish
Current Word export works. Needs:
- Better formatting: question number, marks per sub-question, clear answer/mark scheme section
- Cover page: session name, exam window, date generated
- Option to export questions only (no answers) vs questions + answers

### Enhancement 5: Difficulty Calibration
Currently "Hard" difficulty setting doesn't reliably produce harder questions. Needs:
- Per-session "difficulty profile" with specific instructions (e.g. "always include time apportionment, always add a loss carry-forward issue")
- Style fingerprinting: analyze past questions to extract common tricks per sac_thue
- "Harder than sample X" instruction in prompt

---

## Data Already in the System

**Regulation files loaded** (~13 files):
- CIT: CIT Law 67/2025 ENG, CIT VBHN 14/2022, CIT Circular 78/2014 ENG, CIT Decree 218/2013
- VAT: VAT Law 48/2024 ENG, VAT Decree 181/2025 ENG, VAT Circular 219/2013 ENG  
- PIT: PIT VBHN 02/2023 ENG
- FCT: FCT Circular 103/2014 ENG
- Tax Admin: VBHN 15 ENG
- Transfer Pricing: TP Decree 132/2020 ENG
- Shared: Tax Rates Jun2026, ACCA Syllabus TX(VNM) Jun2026

**Exam sessions:**
- June 2026 (active, default) — regulations_cutoff 2025-12-31
- December 2026 — regulations_cutoff 2025-12-31

**Knowledge Base:** Freshly set up — a few items, needs population via Parse & Match

**Question Bank:** ~10-20 test questions generated during development

---

## Technical Constraints (Non-negotiable)

1. **Single Docker container** — backend serves frontend static files via FastAPI StaticFiles
2. **External PostgreSQL** — connection string via DATABASE_URL env var
3. **AI via requests library** (not httpx, not aiohttp — Cloudflare blocks some)
4. **OpenAI-compatible API format** for primary provider (Claudible)
5. **Port 8000** inside container
6. **Volume mount** `/app/data` for uploaded regulation files (persists across deploys)
7. **Password auth** via `APP_PASSWORD` env var — simple single-user
8. **No real-time features** — no websockets needed, polling is fine for long operations

---

## Environment Variables

```
DATABASE_URL=postgresql://...
APP_PASSWORD=...
SECRET_KEY=...
CLAUDIBLE_API_KEY=...
CLAUDIBLE_BASE_URL=https://claudible.io/v1
CLAUDIBLE_MODEL_STRONG=claude-opus-4.6
CLAUDIBLE_MODEL_FAST=claude-sonnet-4.6
ANTHROPIC_API_KEY=...   (fallback)
OPENAI_API_KEY=...      (fallback)
```

---

## Brand

- Primary color: `#028a39` (dark green)
- Professional, clean UI for tax educators
- No animations except loading spinners
- Tables and forms should be compact — this is a power-user tool

---

## What I Want From You (Super-App Creator)

Please review this description and:

1. **Identify any gaps or ambiguities** in the current feature set — what's unclear?
2. **Suggest architecture improvements** if you see better ways to structure anything
3. **Prioritize the enhancements** listed above — which give the most value?
4. **Build a complete, production-quality version** that includes:
   - Everything in "Current App" (already built, keep it working)
   - All 5 enhancements above
   - Your own suggestions if any
5. **Tell me what files you'll create/modify** before starting

The app is already functional and deployed. The goal is to improve it into a polished, reliable tool that a tax professional can use daily without developer support.

Ask me any clarifying questions before you start coding.
