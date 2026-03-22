# BRIEF: Fix ORDER BY crash on parsed regulations (::int cast on non-matching regex)
## Repo: phanvuhoang/examsgen

---

## Root Cause

In `backend/routes/kb.py`, `GET /regulations/parsed` has this ORDER BY:

```sql
ORDER BY
  doc_ref,
  (regexp_replace(reg_code, '.*Art(\d+).*', '\1', 'g'))::int,
  COALESCE(NULLIF(regexp_replace(reg_code, '.*\.(\d+)\.[a-z].*', '\1', 'g'), reg_code), '0')::int,
  reg_code
```

**Two problems:**

1. `regexp_replace(reg_code, '.*Art(\d+).*', '\1', 'g')::int`
   - If reg_code has no `Art` match (or article_no is empty → `Art-P1`), regexp_replace returns
     the **original string** unchanged → casting a full string like `PIT-TT80TTC-Art-P1` to `::int` → **PostgreSQL error: invalid input syntax for type integer**

2. `regexp_replace(reg_code, '.*\.(\d+)\.[a-z].*', '\1', 'g')::int`
   - Reg codes from async parse use format `PIT-TT80TTC-Art9-P1` (no dot separators)
   - No match → returns original string → `NULLIF(..., reg_code)` returns NULL → COALESCE gives '0' ✅ (this part is OK)
   - But part 1 still crashes first

**Result:** COUNT query works (returns 178), but the actual SELECT with ORDER BY crashes → backend returns 500 → frontend receives empty array → UI shows "Showing 0 of 178 items".

---

## Fix — Safe ORDER BY using NULLIF + CASE

Replace the ORDER BY clause in `GET /regulations/parsed` with a crash-safe version:

```python
query += """
    ORDER BY
      doc_ref,
      COALESCE(
        NULLIF(regexp_replace(reg_code, '.*Art(\\d+).*', '\\1', 'g'), reg_code),
        '0'
      )::int,
      COALESCE(
        NULLIF(regexp_replace(reg_code, '.*\\.(\\d+)\\.[a-z].*', '\\1', 'g'), reg_code),
        '0'
      )::int,
      reg_code
    LIMIT %s OFFSET %s"""
```

**Key change:** Wrap the first `regexp_replace` in `NULLIF(..., reg_code)` — same pattern as the second one.
- If regex matches → returns just the number string → safe to cast `::int`
- If regex does NOT match → `regexp_replace` returns the original `reg_code` → `NULLIF(original, original)` → NULL → `COALESCE(NULL, '0')` → `'0'::int` = 0 → **no crash**

---

## Also fix: article_no = '' generates reg_code 'PIT-DocSlug-Art-P1'

In `_run_parse_job` (~line 552):
```python
art = re.sub(r'[^0-9]', '', str(item.get('article_no', '0')))
```
If AI returns `article_no: "Introduction"` or `""`, `art` becomes `""` → reg_code = `PIT-...-Art-P1` → looks broken.

Fix with a fallback:
```python
art_raw = str(item.get('article_no', '') or '')
art = re.sub(r'[^0-9]', '', art_raw) or '0'   # fallback to '0' if no digits
p = item.get('paragraph_no', 0) or 0
reg_code = f'{tax_type}-{doc_slug}-Art{art}-P{p}'
```

---

## SUMMARY — Files to Modify

| File | Change |
|---|---|
| `backend/routes/kb.py` | Fix ORDER BY in `GET /regulations/parsed`: wrap first `regexp_replace` in `NULLIF(..., reg_code)` so non-matching codes don't crash `::int` cast |
| `backend/routes/kb.py` | Fix `_run_parse_job`: add `or '0'` fallback when `art` is empty string |

---

## NOTES FOR CLAUDE CODE

1. **One-line fix in ORDER BY** — just add `NULLIF(..., reg_code)` wrapper around the first `regexp_replace` cast
2. **Do NOT change COUNT query** — it doesn't have ORDER BY so it's already fine
3. **Do NOT change other endpoints** — only `GET /regulations/parsed` ORDER BY is affected
4. **After fix:** The 178 PIT Circular items will immediately show in UI without any re-parse
5. **Test:** Parse any file → should show results. Also verify CIT docs (existing) still sort correctly.
