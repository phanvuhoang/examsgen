# BRIEF: Fix Parse → Show in UI (source_file mismatch + is_active bug)
## Repo: phanvuhoang/examsgen

---

## Root Cause Analysis

When user clicks [Parse] on an uploaded file, the parsed items ARE inserted into DB,
but they **never appear in the UI**. Two bugs cause this:

---

## Bug 1: `source_file` stored as full path, queried as basename

### What happens
- Frontend sends `file_path: "sessions/December2026/regulations/PIT_Circular.docx"`
- `_run_parse_job` stores `source_file = file_path` → full relative path stored in DB:
  `"sessions/December2026/regulations/PIT_Circular.docx"`
- `GET /regulations/files` groups by `source_file` → returns the full path
- `fetchParsed()` then filters with `source_file = "sessions/December2026/regulations/PIT_Circular.docx"`
- `GET /regulations/parsed` WHERE `source_file = %s` matches ✅ (same full path)

So Bug 1 is actually **not** the cause of items not showing. Let's check Bug 2.

---

## Bug 2: `is_active` column missing default — newly inserted rows have `is_active = NULL`

### What happens
In `_run_parse_job` (line 558–569), the INSERT is:
```python
cur.execute("""
    INSERT INTO kb_regulation_parsed
      (session_id, tax_type, reg_code, doc_ref, article_no, paragraph_no,
       paragraph_text, syllabus_codes, tags, source_file)
    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    ON CONFLICT DO NOTHING
""", ...)
```

**`is_active` is NOT included** in the INSERT → it gets whatever the DB default is.

In `GET /regulations/parsed`, the query filters:
```sql
WHERE is_active = TRUE
```

If `is_active` defaults to `NULL` (not `TRUE`), then `NULL = TRUE` is `FALSE` → **zero rows returned**.

Also in `GET /regulations/files`:
```sql
WHERE session_id = %s AND is_active = TRUE
```
Same issue → the newly parsed file doesn't even appear in the file dropdown.

### Why yesterday's 3 docs show fine
The `/tmp/parse_cit_regs.py` script explicitly set `is_active = TRUE` in its INSERT.
The async parse job does NOT → `is_active = NULL` → invisible.

---

## Fix 1: Add `is_active = TRUE` to INSERT in `_run_parse_job`

In `backend/routes/kb.py`, find `_run_parse_job` function (~line 558), update the INSERT:

```python
# BEFORE:
cur.execute("""
    INSERT INTO kb_regulation_parsed
      (session_id, tax_type, reg_code, doc_ref, article_no, paragraph_no,
       paragraph_text, syllabus_codes, tags, source_file)
    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    ON CONFLICT DO NOTHING
""", (session_id, tax_type, reg_code, doc_ref,
      item.get('article_no'), p,
      item.get('paragraph_text', ''),
      syllabus_codes,
      item.get('tags', ''),
      file_path))

# AFTER:
cur.execute("""
    INSERT INTO kb_regulation_parsed
      (session_id, tax_type, reg_code, doc_ref, article_no, paragraph_no,
       paragraph_text, syllabus_codes, tags, source_file, is_active)
    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s, TRUE)
    ON CONFLICT DO NOTHING
""", (session_id, tax_type, reg_code, doc_ref,
      item.get('article_no'), p,
      item.get('paragraph_text', ''),
      syllabus_codes,
      item.get('tags', ''),
      file_path))
```

---

## Fix 2: Also fix the DB column default (belt + suspenders)

In `backend/database.py`, find the `CREATE TABLE kb_regulation_parsed` block and ensure
`is_active` has a proper default:

```sql
-- BEFORE (likely):
is_active BOOLEAN,

-- AFTER:
is_active BOOLEAN NOT NULL DEFAULT TRUE,
```

Also add a migration ALTER to fix existing NULL rows:
```python
cur.execute("""
    ALTER TABLE kb_regulation_parsed
        ALTER COLUMN is_active SET DEFAULT TRUE;
""")
cur.execute("""
    UPDATE kb_regulation_parsed SET is_active = TRUE WHERE is_active IS NULL;
""")
```
Add these two lines to the migration block in `init_db()`.

---

## Fix 3: ON CONFLICT DO NOTHING → silent failure on duplicate reg_code

### Problem
The INSERT uses `ON CONFLICT DO NOTHING`. If the same file is parsed twice (re-parse),
or if there's a `reg_code` collision (e.g., two chunks produce same article+paragraph_no),
the row is silently skipped → lower-than-expected count, no error shown.

### Fix
Change to `ON CONFLICT (session_id, reg_code) DO UPDATE` (upsert) so re-parses
always update existing rows instead of silently skipping:

```python
cur.execute("""
    INSERT INTO kb_regulation_parsed
      (session_id, tax_type, reg_code, doc_ref, article_no, paragraph_no,
       paragraph_text, syllabus_codes, tags, source_file, is_active)
    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s, TRUE)
    ON CONFLICT (session_id, reg_code) DO UPDATE SET
      paragraph_text = EXCLUDED.paragraph_text,
      syllabus_codes = EXCLUDED.syllabus_codes,
      tags           = EXCLUDED.tags,
      is_active      = TRUE
""", (session_id, tax_type, reg_code, doc_ref,
      item.get('article_no'), p,
      item.get('paragraph_text', ''),
      syllabus_codes,
      item.get('tags', ''),
      file_path))
```

---

## Fix 4: Heal existing NULL rows via one-time migration

Already covered in Fix 2 migration. But also add to `init_db()` to be safe:

```python
# Heal any NULL is_active rows from buggy inserts
cur.execute("UPDATE kb_regulation_parsed SET is_active = TRUE WHERE is_active IS NULL")
```

---

## SUMMARY — Files to Modify

| File | Change |
|---|---|
| `backend/routes/kb.py` | `_run_parse_job`: add `is_active` to INSERT columns + value `TRUE`; change `ON CONFLICT DO NOTHING` → `ON CONFLICT (session_id, reg_code) DO UPDATE SET ... is_active = TRUE` |
| `backend/database.py` | ALTER `is_active` column to `NOT NULL DEFAULT TRUE`; UPDATE existing NULL rows; add healing migration |

---

## NOTES FOR CLAUDE CODE

1. **Primary fix is in `_run_parse_job`** — add `is_active` to INSERT. This is the single line that fixes "parse done but nothing shows".
2. **DB migration is secondary** — prevents regression. Add to the existing migration block in `init_db()`, not a new function.
3. **Do NOT change the UI or fetchParsed** — the display logic is correct; only the INSERT is wrong.
4. **Test after fix:** Parse a new file → items should immediately appear in the Regulations tab without page refresh.
5. **The 3 existing docs (CIT)** are fine — they used the standalone script which set `is_active = TRUE` explicitly.
