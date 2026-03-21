# BRIEF: Fix Clone Session
## Repo: phanvuhoang/examsgen

---

## Problems Found

1. **`kb_regulation_parsed` clone fails on 2nd attempt** — unique index `(session_id, reg_code)` causes duplicate key error if clone is run twice
2. **`kb_syllabus` clone fails on 2nd attempt** — unique partial index `(session_id, tax_type, syllabus_code)` causes same issue
3. **`sample_questions` not cloned** — this is a global table (not session-scoped), which is correct design — no change needed

---

## Fix: Defensive Clone with Clear-Before-Copy

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

**Note on `syllabus_ids` / `regulation_ids` arrays in `kb_sample`:**
The old clone was copying `'{}', '{}'` (empty arrays) for `syllabus_ids` and `regulation_ids`. These are legacy fields from the old KB design — if the column still exists, keep copying as `'{}'` (empty). If column doesn't exist (was dropped in v2 redesign), remove from INSERT.

---

## Also: Show Clone Summary in UI

After clone completes, show a toast or inline message:
```
✓ Cloned from June 2026:
  • 87 syllabus items
  • 203 regulation paragraphs  
  • 4 tax rate tables
  • 12 KB samples
```

Use the `cloned` object from the API response.

---

## Files to Modify

| File | Change |
|------|--------|
| `backend/routes/sessions.py` | Replace `clone_session` with the fixed version above |

---

## Notes for Claude Code

1. **Delete before insert** — this makes clone safe to run multiple times (idempotent). If user accidentally clones twice, data is correct.
2. **Don't clone `questions` table** — generated questions belong to each session independently. Cloning them would be confusing.
3. **Don't clone `sample_questions`** — this is global (not session-scoped), shared across all sessions. Correct as-is.
4. **Return `cloned` counts** — helpful feedback for user to know what was transferred.
5. **`kb_regulation` `syllabus_ids` column** — old INT[] foreign key column. Copy as `'{}'` if column exists. If removed in v2 redesign, omit the column from INSERT.
