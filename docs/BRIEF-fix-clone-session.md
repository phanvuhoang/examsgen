# BRIEF: Fix Clone Session + Session Tagging for Questions & Sample Questions
## Repo: phanvuhoang/examsgen

---

## PART 1: Fix Clone Session (same as before)

### Problems Found

1. **`kb_regulation_parsed` clone fails on 2nd attempt** — unique index `(session_id, reg_code)` causes duplicate key error if clone is run twice
2. **`kb_syllabus` clone fails on 2nd attempt** — unique partial index `(session_id, tax_type, syllabus_code)` causes same issue
3. **`sample_questions` not cloned** — this is a global table (not session-scoped), which is correct design — no change needed

### Fix: Defensive Clone with Clear-Before-Copy

Update `POST /{session_id}/clone-from/{source_id}` in `backend/routes/sessions.py`:

```python
@router.post("/{session_id}/clone-from/{source_id}")
def clone_session(session_id: int, source_id: int):
    """Copy all KB items and settings from source session into target session.
    Safe to run multiple times — clears target KB data before copying.
    """
    with get_db() as conn:
        cur = conn.cursor()

        # 1. Copy session settings (parameters, tax_types, question_types)
        cur.execute("""
            UPDATE exam_sessions t SET
                parameters = s.parameters,
                tax_types = s.tax_types,
                question_types = s.question_types
            FROM exam_sessions s
            WHERE s.id = %s AND t.id = %s
        """, (source_id, session_id))

        # 2. Clear target KB before copying (makes clone idempotent)
        cur.execute("DELETE FROM kb_syllabus WHERE session_id = %s", (session_id,))
        cur.execute("DELETE FROM kb_regulation WHERE session_id = %s", (session_id,))
        cur.execute("DELETE FROM kb_regulation_parsed WHERE session_id = %s", (session_id,))
        cur.execute("DELETE FROM kb_tax_rates WHERE session_id = %s", (session_id,))
        cur.execute("DELETE FROM kb_sample WHERE session_id = %s", (session_id,))

        # 3. Copy kb_syllabus
        cur.execute("""
            INSERT INTO kb_syllabus (sac_thue, section_code, section_title, content, tags,
                                     source_file, is_active, session_id,
                                     tax_type, syllabus_code, topic, detailed_syllabus)
            SELECT sac_thue, section_code, section_title, content, tags,
                   source_file, is_active, %s,
                   tax_type, syllabus_code, topic, detailed_syllabus
            FROM kb_syllabus WHERE session_id = %s
        """, (session_id, source_id))

        # 4. Copy kb_regulation
        cur.execute("""
            INSERT INTO kb_regulation (sac_thue, regulation_ref, content, tags,
                                       source_file, is_active, session_id)
            SELECT sac_thue, regulation_ref, content, tags,
                   source_file, is_active, %s
            FROM kb_regulation WHERE session_id = %s
        """, (session_id, source_id))

        # 5. Copy kb_regulation_parsed
        cur.execute("""
            INSERT INTO kb_regulation_parsed (session_id, tax_type, reg_code, doc_ref,
                                              article_no, paragraph_no, paragraph_text,
                                              syllabus_codes, tags, source_file, is_active)
            SELECT %s, tax_type, reg_code, doc_ref,
                   article_no, paragraph_no, paragraph_text,
                   syllabus_codes, tags, source_file, is_active
            FROM kb_regulation_parsed WHERE session_id = %s
        """, (session_id, source_id))

        # 6. Copy kb_tax_rates
        cur.execute("""
            INSERT INTO kb_tax_rates (session_id, tax_type, table_name, content,
                                      source_file, display_order, is_active)
            SELECT %s, tax_type, table_name, content,
                   source_file, display_order, is_active
            FROM kb_tax_rates WHERE session_id = %s
        """, (session_id, source_id))

        # 7. Copy kb_sample
        cur.execute("""
            INSERT INTO kb_sample (question_type, sac_thue, title, content, exam_tricks,
                                   source, session_id)
            SELECT question_type, sac_thue, title, content, exam_tricks,
                   source, %s
            FROM kb_sample WHERE session_id = %s
        """, (session_id, source_id))

    # 8. Copy uploaded files (regulations, syllabus, samples folders)
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT folder_path FROM exam_sessions WHERE id = %s", (source_id,))
        row = cur.fetchone()
        src_folder = row[0] if row else None
        cur.execute("SELECT folder_path FROM exam_sessions WHERE id = %s", (session_id,))
        row = cur.fetchone()
        dst_folder = row[0] if row else None

    if src_folder and dst_folder:
        for sub in ['regulations', 'syllabus', 'samples']:
            src_path = os.path.join(DATA_DIR, src_folder, sub)
            dst_path = os.path.join(DATA_DIR, dst_folder, sub)
            if os.path.isdir(src_path):
                if os.path.isdir(dst_path):
                    shutil.rmtree(dst_path)
                shutil.copytree(src_path, dst_path)

    # Count what was cloned for response
    with get_db() as conn:
        cur = conn.cursor()
        counts = {}
        for table, col in [
            ('kb_syllabus', 'syllabus'),
            ('kb_regulation_parsed', 'reg_paragraphs'),
            ('kb_tax_rates', 'tax_rates'),
            ('kb_sample', 'kb_samples'),
        ]:
            cur.execute(f"SELECT COUNT(*) FROM {table} WHERE session_id = %s", (session_id,))
            counts[col] = cur.fetchone()[0]

    return {
        "ok": True,
        "message": f"KB cloned from session {source_id}",
        "cloned": counts
    }
```

Show clone summary in UI after clone completes:
```
✓ Cloned from June 2026:
  • 87 syllabus items
  • 203 regulation paragraphs
  • 4 tax rate tables
  • 12 KB samples
```

---

## PART 2: Session Tagging for Questions & Sample Questions

### Overview

Both `questions` (Question Bank) and `sample_questions` remain **global tables** — they are NOT scoped to a session. However, each item should be **tagged** with:

1. **`exam_session_id`** — which exam session it was created under (auto-set to active session, editable)
2. **`syllabus_codes`** — which syllabus codes it covers (already exists on `questions`, add to `sample_questions` if missing)
3. **`reg_codes`** — which regulation paragraphs it references (already exists on `questions`, add to `sample_questions` if missing)

This allows: "Show me all questions tagged for June 2026 session" or "Show me all questions covering syllabus code B2a".

### 2.1 DB Changes

```sql
-- Add exam_session_id to questions table (if not exists)
ALTER TABLE questions ADD COLUMN IF NOT EXISTS exam_session_id INTEGER REFERENCES exam_sessions(id);

-- Add exam_session_id to sample_questions table (if not exists)
ALTER TABLE sample_questions ADD COLUMN IF NOT EXISTS exam_session_id INTEGER REFERENCES exam_sessions(id);

-- syllabus_codes and reg_codes already exist on questions (added earlier)
-- Make sure they exist on sample_questions too:
ALTER TABLE sample_questions ADD COLUMN IF NOT EXISTS syllabus_codes TEXT[];
ALTER TABLE sample_questions ADD COLUMN IF NOT EXISTS reg_codes TEXT[];
```

Add these ALTER statements to `backend/database.py` in `init_db()` using `ADD COLUMN IF NOT EXISTS` — safe to run multiple times.

### 2.2 Backend — Auto-set exam_session_id on create

#### In `backend/routes/generate.py` — `_save_question()`

Add `exam_session_id` to the INSERT:

```python
def _save_question(question_type, sac_thue, question_part, question_number,
                   content_json, content_html, model_used, provider_used,
                   exam_session, duration_ms, prompt_tokens, completion_tokens,
                   session_id=None, user_id=1):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO questions (question_type, sac_thue, question_part, question_number, "
            "content_json, content_html, model_used, provider_used, exam_session, "
            "session_id, exam_session_id, user_id) "   # ← add exam_session_id
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id",
            (question_type, sac_thue, question_part, question_number,
             json.dumps(content_json), content_html, model_used, provider_used, exam_session,
             session_id, session_id, user_id),   # ← exam_session_id = session_id
        )
        ...
```

Note: `session_id` (existing field, stores the exam session id) and `exam_session_id` (new explicit FK) may be redundant — if `session_id` already is the exam session FK, just use that and skip adding a new column. Check the existing `questions` schema first:
- If `questions.session_id` already references `exam_sessions.id` → no new column needed, just make sure it's being set correctly
- If `questions.session_id` is something else → add `exam_session_id` as new column

#### In `backend/routes/sample_questions.py` — `create_sample_question()`

Add `exam_session_id` to model and INSERT:

```python
class SampleQuestionCreate(BaseModel):
    question_type: str
    question_subtype: Optional[str] = None
    tax_type: str
    title: Optional[str] = None
    content: str
    answer: Optional[str] = None
    marks: Optional[int] = None
    exam_ref: Optional[str] = None
    syllabus_codes: Optional[List[str]] = None
    reg_codes: Optional[List[str]] = None
    tags: Optional[str] = None
    exam_session_id: Optional[int] = None    # ← NEW: which session this was created for
```

```python
@router.post("")
def create_sample_question(item: SampleQuestionCreate):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO sample_questions
              (question_type, question_subtype, tax_type, title, content, answer, marks,
               exam_ref, syllabus_codes, reg_codes, tags, exam_session_id)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id
        """, (item.question_type, item.question_subtype, item.tax_type, item.title,
              item.content, item.answer, item.marks, item.exam_ref,
              item.syllabus_codes or [], item.reg_codes or [], item.tags,
              item.exam_session_id))
        return {"id": cur.fetchone()[0]}
```

Also update `PUT /{item_id}` to include `exam_session_id` in the UPDATE.

### 2.3 Backend — Filter by exam_session_id

#### `GET /api/questions` — add filter

```python
# In backend/routes/questions.py list handler:
if exam_session_id:
    query += " AND (session_id = %s OR exam_session_id = %s)"
    params += [exam_session_id, exam_session_id]
```

#### `GET /api/sample-questions` — add filter

```python
# In backend/routes/sample_questions.py list handler:
if exam_session_id:
    query += " AND exam_session_id = %s"
    params.append(exam_session_id)
```

### 2.4 Frontend — Pass active session_id when creating/generating

#### Generate page

When calling any generate endpoint, already passes `session_id` (the active session). Confirm the backend `_save_question` stores it as `exam_session_id`. No frontend change needed if backend is wired correctly.

#### Sample Questions page — add Session Tag field

In the add/edit form for Sample Questions, add a **Session** dropdown:

```jsx
<div>
  <label className="block text-sm font-medium mb-1">Exam Session</label>
  <select
    value={form.exam_session_id || ''}
    onChange={e => setForm({ ...form, exam_session_id: e.target.value ? parseInt(e.target.value) : null })}
    className="w-full border rounded-lg px-3 py-2 text-sm"
  >
    <option value="">— None (global) —</option>
    {sessions.map(s => (
      <option key={s.id} value={s.id}>{s.name}</option>
    ))}
  </select>
  <p className="text-xs text-gray-400 mt-0.5">Tag this question to a specific exam session. Defaults to current active session.</p>
</div>
```

**Default value:** When opening "Add" form, pre-fill `exam_session_id` with the current active session id (from `useCurrentSession()`).

### 2.5 Frontend — Session filter in Question Bank & Sample Questions

#### Question Bank page — add Session filter

```jsx
{/* In filter bar */}
<select
  value={sessionFilter}
  onChange={e => setSessionFilter(e.target.value)}
  className="border rounded-lg px-3 py-2 text-sm"
>
  <option value="">All Sessions</option>
  {sessions.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
</select>
```

Pass `exam_session_id` to the GET request when filter is set.

#### Sample Questions page — same pattern

Add session filter dropdown, same as Question Bank.

### 2.6 Frontend — Show session tag on cards

#### Question Bank cards

Below the existing syllabus/reg code chips, show session badge:

```jsx
{item.exam_session_id && (
  <span className="inline-flex items-center px-2 py-0.5 bg-purple-50 text-purple-600 text-xs rounded border border-purple-100">
    📅 {sessions.find(s => s.id === item.exam_session_id)?.name || `Session ${item.exam_session_id}`}
  </span>
)}
```

#### Sample Questions cards/rows — same pattern

---

## SUMMARY — Files to Create/Modify

| Action | File | Change |
|--------|------|--------|
| MODIFY | `backend/database.py` | Add `ALTER TABLE questions ADD COLUMN IF NOT EXISTS exam_session_id`; same for `sample_questions`; add `syllabus_codes`/`reg_codes` to `sample_questions` if missing |
| MODIFY | `backend/routes/sessions.py` | Replace `clone_session` with idempotent version (Part 1) |
| MODIFY | `backend/routes/generate.py` | Ensure `_save_question` sets `exam_session_id = session_id` |
| MODIFY | `backend/routes/sample_questions.py` | Add `exam_session_id` to model, INSERT, UPDATE, and GET filter |
| MODIFY | `backend/routes/questions.py` | Add `exam_session_id` filter to GET list |
| MODIFY | `frontend/src/pages/SampleQuestions.jsx` | Add Session dropdown in add/edit form; session filter in list; session badge on cards |
| MODIFY | `frontend/src/pages/QuestionBank.jsx` | Add session filter dropdown; session badge on cards |

---

## NOTES FOR CLAUDE CODE

1. **Check `questions.session_id` first** — if it's already an FK to `exam_sessions.id`, don't add `exam_session_id` as a duplicate column. Just make sure `_save_question` sets it and the GET filter uses it.

2. **`sample_questions.exam_session_id` default** — when user adds a sample question from the Sample Questions page, default to `useCurrentSession()`. User can override via dropdown.

3. **Global questions still work** — `exam_session_id = NULL` means "global, not tied to any session". The filter "All Sessions" shows everything including NULLs.

4. **Session badge color**: purple (`bg-purple-50 text-purple-600`) to visually distinguish from syllabus (blue) and reg (green) chips.

5. **`sessions` list for dropdowns**: already available via `api.getSessions()` — reuse existing call, don't add a new one.

6. **`ALTER TABLE ... ADD COLUMN IF NOT EXISTS`** — safe to run in `init_db()`, no migration needed.

7. **Don't change exam_session_id on clone** — when cloning, we do NOT copy `questions` or `sample_questions`, so no impact here.
