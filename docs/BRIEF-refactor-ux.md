# BRIEF: Exam Session Refactor — UX + Architecture Polish
## ExamsGen — Changes from user feedback

**Repo:** phanvuhoang/examsgen  
**Context:** App is working. This brief is a focused UX/architecture cleanup, not a rebuild.

---

## Summary of Changes

1. Each Exam Session owns its files (folder-per-session) + Upload button
2. KB (Syllabus/Regulations/Samples) all live inside the Session — Regulations tab removed
3. Session selector: single global combo box in navbar only
4. Generate page: remove Exam Session box, replace with AI Provider selector
5. Sessions page: add Delete session with confirmation
6. Question Bank: add Exam Session filter
7. Nav reorder: Sessions → Knowledge Base → Generate → Question Bank → Settings
8. Multi-user preparation: user_id on questions table (already added to DB)

**DB migrations already applied** — do NOT re-run CREATE TABLE or ALTER TABLE for these:
- `exam_sessions.folder_path` ✅
- `regulations.session_id` ✅  
- `regulations.doc_type` ✅ (values: 'regulation' | 'syllabus' | 'sample_questions')
- `questions.session_id` ✅
- `questions.user_id` ✅
- All existing regulations assigned to June 2026 session ✅
- File paths updated to `sessions/june_2026/regulations/...` ✅

---

## 1. Session Folder Structure

Each session has a dedicated folder under `/app/data/sessions/{folder_name}/`:
```
/app/data/sessions/june_2026/
    regulations/        ← uploaded regulation .doc/.docx files
    syllabus/           ← uploaded syllabus files
    samples/            ← uploaded sample question files
/app/data/sessions/december_2026/
    regulations/
    syllabus/
    samples/
```

`folder_name` is auto-generated from session name: lowercase, spaces→underscore, non-alphanumeric removed.
E.g. "June 2026" → `june_2026`, "December 2026" → `december_2026`

**folder_path** column in `exam_sessions` already stores this (e.g. `sessions/june_2026`).

### Clone session — copy files too

When `/api/sessions/{id}/clone-from/{source_id}` is called:
1. Copy KB items in DB (already implemented)
2. Also `shutil.copytree` the source session folder to the new session folder
3. Update `regulations` rows: insert copies pointing to new session folder paths

---

## 2. Knowledge Base Page — Session-Scoped with Upload

The KB page (`/kb`) has 3 tabs: **Syllabus | Regulations | Sample Questions**

Each tab now has its own document management — same pattern as the current Regulations page.

### Document section (top of each tab)

```
Uploaded Files                                    [+ Upload File]
┌────────────────────────────────────────────────────┐
│ 📄 CIT_Law_67_2025_ENG.doc    CIT  [Parse] [✕]    │
│ 📄 VAT_Decree_181_2025_ENG.docx  VAT  [Parse] [✕]  │
│ 📄 PIT_VBHN_02.doc            PIT  [Parse] [✕]    │
└────────────────────────────────────────────────────┘
```

Upload button: opens file picker → accepts .doc/.docx → uploads to session folder:
- Syllabus tab → `sessions/{folder}/syllabus/`
- Regulations tab → `sessions/{folder}/regulations/`
- Sample Questions tab → `sessions/{folder}/samples/`

Saves to `regulations` table with:
- `session_id` = current session
- `doc_type` = 'syllabus' | 'regulation' | 'sample_questions'
- `file_path` = `sessions/{folder}/{subfolder}/filename.doc`

### Upload endpoint

```python
@router.post("/api/sessions/{session_id}/upload-doc")
async def upload_doc(session_id: int, doc_type: str, file: UploadFile):
    """Upload a document file into the session's folder."""
    # Get session folder_path
    # Save file to /app/data/{folder_path}/{doc_type_subfolder}/
    # Insert into regulations table
    # Return file info
```

`doc_type` maps to subfolder: `regulation`→`regulations/`, `syllabus`→`syllabus/`, `sample_questions`→`samples/`

### [Parse] button behavior

Clicking [Parse] on a file → calls `/api/sessions/{id}/parse-and-match` with that file's path and doc_type.

**Fix parse-and-match for doc_type='syllabus'**: currently only regulation→syllabus matching is done. Add:
- If doc_type='syllabus': chunk into kb_syllabus rows
- If doc_type='regulation': chunk into kb_regulation rows, match to syllabus
- If doc_type='sample_questions': chunk into kb_sample rows (each question = one chunk)

### KB items section (below uploaded files)

Keep existing KB items list (cards/table of chunked items).

Tabs show both the file list AND the parsed KB items from that tab's doc_type.

---

## 3. Remove Regulations Tab from Navigation

Delete the standalone `/regulations` page from nav and routing.

All file management moves into Knowledge Base (`/kb`), which is now the single place for:
- Uploading documents
- Parsing & reviewing chunks
- Managing KB items

**Keep** the backend upload/delete endpoints (they're reused), just remove the frontend page.

---

## 4. Navigation Reorder

New nav order:
```
Sessions | Knowledge Base | Generate | Question Bank | Settings
```

Remove "Regulations" from nav entirely.

---

## 5. Single Session Selector in Navbar

Remove any session selector from the Generate page.

Keep **one** session selector in the navbar (already exists). That's the single source of truth.

The current session controls:
- What KB items are available in Generate
- What session_id is used when generating questions
- What KB items show in Knowledge Base page

It does NOT filter Question Bank (Question Bank has its own session filter — see point 8).

Remove the "Set as Active" button inside the Sessions cards. The navbar selector IS the active session selector. When user changes navbar selector → update localStorage → all pages react.

---

## 6. Generate Page Changes

### Remove: Exam Session selector box
Already controlled by navbar. Remove the session dropdown from Generate.

### Add: AI Provider + Model selector

Replace the current AI Model selector (Sonnet/Opus) with a two-level selector:

**Level 1 — Provider:**
```
[ Claudible (default) ▼ ]    [ Anthropic ]    [ OpenAI ]
```
Or a single dropdown: `Claudible — Sonnet`, `Claudible — Opus`, `Anthropic — Sonnet`, `Anthropic — Opus`, `OpenAI — Fast`, `OpenAI — Strong`

**Level 2 — Model strength:** Fast (Sonnet-class) or Strong (Opus-class)

Backend: pass `provider` + `model_tier` to `call_ai()`.

`call_ai()` update:
```python
def call_ai(prompt=None, messages=None, model_tier="fast", system_prompt=None, provider=None):
    # provider: None (auto/default) | "claudible" | "anthropic" | "openai"
    # If provider is specified, use that provider directly (no fallback chain)
    # If provider is None, use existing fallback chain: claudible → anthropic → openai
```

New env vars needed:
```
OPENAI_FAST_MODEL=gpt-4o-mini    # default
OPENAI_STRONG_MODEL=gpt-4o       # default  
```

Frontend: pass `provider` field in all generate requests (mcq/scenario/longform/refine).

### Nav order on Generate page

Move generate button DOWN — currently it's above everything. The natural flow is:

```
1. Session context bar (read-only: session name, cutoff, fiscal year)
2. Question type selector
3. Tax type (sac_thue)
4. Options (count, difficulty, model)
5. Custom Instructions (collapsed)
6. Knowledge Base Targeting (collapsed)
7. [Generate] button ← at the bottom
```

---

## 7. Sessions Page — Delete Button

Each session card has a **[Delete]** button in a "Danger Zone" section at the bottom.

Clicking Delete → confirmation modal:
```
Delete "December 2026"?

This will permanently delete:
• X syllabus items
• Y regulation chunks  
• Z sample questions
• W generated questions
• All uploaded files in sessions/december_2026/

This cannot be undone.

[ Cancel ]  [ Delete permanently ]
```

On confirm:
1. Delete all `kb_syllabus`, `kb_regulation`, `kb_sample` WHERE session_id = X
2. Delete all `questions` WHERE session_id = X
3. Delete all `regulations` WHERE session_id = X
4. `shutil.rmtree` the session folder
5. Delete `exam_sessions` row
6. If deleted session was in localStorage, switch to default session

Backend endpoint:
```python
@router.delete("/{session_id}")
def delete_session(session_id: int):
    # Confirm not deleting the last session
    # Delete all related records
    # Remove folder
    # Return ok
```

---

## 8. Question Bank — Add Session Filter

Add a session filter dropdown to the Question Bank page:

```
Filter: [ All Sessions ▼ ]  [ All Types ▼ ]  [ All Tax Types ▼ ]  [ ★ Starred ]
```

"All Sessions" shows everything. Selecting a session filters to only questions from that session.

Backend: `GET /api/questions?session_id=1` — already has session_id column on questions table.

---

## 9. Multi-User Preparation (Structure Only — No Auth Yet)

**Goal:** Lay the groundwork so adding multi-user later is easy. No actual login system needed now.

### DB (already done):
- `questions.user_id INTEGER DEFAULT 1` ✅
- `questions.session_id INTEGER` ✅

### Conceptual separation:
- **Shared across users:** `exam_sessions`, `kb_syllabus`, `kb_regulation`, `kb_sample`, `regulations` (files)
- **Per-user:** `questions` (generated questions + question bank)

### Code changes needed now:
1. In all generate endpoints, accept optional `user_id` in request (default 1):
   ```python
   user_id: int = 1  # future: from auth token
   ```
   Save to `questions.user_id` when inserting.

2. In Question Bank list endpoint, accept optional `user_id` filter (default: return all, for now):
   ```python
   # GET /api/questions?user_id=1
   ```

3. Add a comment in `main.py` at the auth section:
   ```python
   # TODO: Replace APP_PASSWORD single-user auth with per-user JWT auth
   # user_id should come from JWT token, not hardcoded to 1
   ```

This is all — no actual multi-user UI needed now.

---

## 10. Files to Create/Modify

| Action | File | Change |
|--------|------|--------|
| MODIFY | `backend/routes/sessions.py` | Add DELETE endpoint, add upload-doc endpoint |
| MODIFY | `backend/routes/generate.py` | Remove session param (use default), add provider param, add user_id |
| MODIFY | `backend/routes/kb.py` | Filter by doc_type per tab, handle syllabus/sample parse |
| MODIFY | `backend/routes/questions.py` | Add session_id filter, add user_id filter |
| MODIFY | `backend/ai_provider.py` | Add provider param to call_ai() |
| MODIFY | `backend/routes/sessions.py` | parse-and-match handles all 3 doc_types |
| MODIFY | `frontend/src/App.jsx` | Remove /regulations route |
| MODIFY | `frontend/src/components/Navbar.jsx` | Reorder nav, keep only one session selector |
| MODIFY | `frontend/src/pages/KnowledgeBase.jsx` | Add upload section per tab, use doc_type |
| MODIFY | `frontend/src/pages/Generate.jsx` | Remove session box, add provider selector, move Generate button to bottom |
| MODIFY | `frontend/src/pages/Sessions.jsx` | Remove "Set Active" button, add Delete with confirm modal |
| MODIFY | `frontend/src/pages/QuestionBank.jsx` | Add session filter dropdown |
| DELETE | `frontend/src/pages/Regulations.jsx` | Remove this page |

---

## Notes for Claude Code

1. **Do not re-run DB migrations** — they're already applied. Just update Python models/schemas to match.
2. **Folder creation on session create:** when POST /api/sessions/ creates a session, also `os.makedirs` the 3 subfolders.
3. **parse-and-match for sample_questions:** treat each question as a separate chunk. Look for "Question X" or numbered sections to split. Auto-extract: title, question text, answer, tax type.
4. **Provider selector UI:** a single `<select>` with combined options is simplest: "Claudible Sonnet (fast)", "Claudible Opus (best)", "Anthropic Sonnet", "Anthropic Opus", "OpenAI Fast", "OpenAI Strong"
5. **Session delete confirmation** must show real counts from DB before user confirms.
6. **After nav reorder:** Sessions is the first item — it's the starting point for new users.
7. **Question Bank session filter:** "All Sessions" option must be the default (show all questions regardless of session).
