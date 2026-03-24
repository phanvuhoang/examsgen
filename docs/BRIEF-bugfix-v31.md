# ExamsGen — Bug Fix Brief v3.2
**Date:** March 2026
**Priority:** CRITICAL — all generation bugs trace to one root cause

---

## Root Cause (confirmed)

ALL 3 symptoms below come from ONE bug — `_resolve_session_id()` returning session id=1 instead of session id=2:

| Symptom | Why |
|---|---|
| Output cites wrong regulations (e.g. Decree 132/2020 TP instead of CIT) | session 1 has no files → regulations="" → Claude uses internal knowledge |
| Output doesn't follow sample format | session 1 has no sample files → sample="" |
| Output has no syllabus tags | session 1 has no syllabus files → syllabus="" |

User uploaded all files (regulations, syllabus, rates, samples) into **session id=2**. But `_resolve_session_id()` resolves to session id=1 (the seeded default with no files).

**Verified:** `session_files` table has 30 rows all with `session_id=2`. Session id=1 has zero files.

---

## Fix 1 (CRITICAL): `_resolve_session_id()` in `routes/generate.py`

**Current behavior:** Falls back to `is_default=TRUE` session, which is session 1 (empty).

**Fix:** When default session has no files, fall back to most recent session that has files:

```python
def _resolve_session_id(session_id: int = None) -> int | None:
    with get_db() as conn:
        cur = conn.cursor()
        if session_id:
            cur.execute("SELECT id FROM exam_sessions WHERE id = %s", (session_id,))
            row = cur.fetchone()
            if row:
                return row[0]

        # Try default session
        cur.execute("SELECT id FROM exam_sessions WHERE is_default = TRUE ORDER BY id DESC LIMIT 1")
        row = cur.fetchone()
        if row:
            default_id = row[0]
            # Verify it has files
            cur.execute("SELECT COUNT(*) FROM session_files WHERE session_id = %s AND is_active = TRUE", (default_id,))
            count = cur.fetchone()[0]
            if count > 0:
                return default_id

        # Default session has no files — use most recent session WITH files
        cur.execute("""
            SELECT DISTINCT sf.session_id
            FROM session_files sf
            WHERE sf.is_active = TRUE
            ORDER BY sf.session_id DESC
            LIMIT 1
        """)
        row = cur.fetchone()
        if row:
            return row[0]

        # Absolute last resort: most recently created session
        cur.execute("SELECT id FROM exam_sessions ORDER BY id DESC LIMIT 1")
        row = cur.fetchone()
        return row[0] if row else None
```

**Also:** When session_id resolves successfully, update it to be the default so future requests don't need to fall back:

```python
# In startup/seed — if session 1 is empty and session 2 has files, make session 2 the default
def fix_default_session():
    with get_db() as conn:
        cur = conn.cursor()
        # Find session with most files
        cur.execute("""
            SELECT session_id, COUNT(*) as file_count
            FROM session_files
            WHERE is_active = TRUE
            GROUP BY session_id
            ORDER BY file_count DESC
            LIMIT 1
        """)
        row = cur.fetchone()
        if row:
            session_id = row[0]
            cur.execute("UPDATE exam_sessions SET is_default = FALSE WHERE is_default = TRUE")
            cur.execute("UPDATE exam_sessions SET is_default = TRUE WHERE id = %s", (session_id,))
            logger.info(f"Set session {session_id} as default (has {row[1]} files)")
```

Call `fix_default_session()` in the `startup()` event in `main.py`.

---

## Fix 2: Add diagnostic logging to `build_context()` in `context_builder.py`

So we can confirm files are loaded correctly after the fix:

```python
def build_context(session_id: int, sac_thue: str, question_type: str) -> dict:
    logger.info(f"build_context: session_id={session_id}, sac_thue={sac_thue}, question_type={question_type}")

    # ... existing code ...

    logger.info(f"  regulations: {len(reg_files)} files — {[f['name'] for f in reg_files]}")
    logger.info(f"  syllabus: {len(syllabus_files)} files — {[f['name'] for f in syllabus_files]}")
    logger.info(f"  sample: {len(sample_files)} files — {[f['name'] for f in sample_files]}")
    logger.info(f"  rates: {len(rates_files)} files — {[f['name'] for f in rates_files]}")
    logger.info(f"  total context chars: regulations={len(regulations)}, syllabus={len(syllabus)}, sample={len(sample)}, rates={len(tax_rates)}")

    return {
        "tax_rates": tax_rates,
        "syllabus": syllabus,
        "regulations": regulations,
        "sample": sample,
    }
```

---

## Fix 3: Reduce context size to fix Claudible timeout

**Problem:** MAX_CONTEXT_CHARS=600K → prompt too large → Claudible times out even with 300s limit.

**Fix in `context_builder.py`:**

```python
MAX_CONTEXT_CHARS = 300_000    # reduce from 600_000
MAX_PER_REG_CHARS = 80_000     # reduce from 150_000
```

**Fix in `ai_provider.py`:** Dynamic max_tokens instead of hardcoded 8000:

```python
# Replace hardcoded "max_tokens": 8000 with:
MAX_TOKENS_BY_TIER = {
    "fast": 3000,    # MCQ — shorter output needed
    "strong": 5000,  # Scenario/Longform — longer output
}

# In requests.post:
json={
    "model": model,
    "messages": messages,
    "max_tokens": MAX_TOKENS_BY_TIER.get(model_tier, 3000),
    "temperature": 0.7,
},
```

---

## Fix 4: Add `{sample_note}` to prompts when sample is from different tax type (minor)

In `context_builder.py`, after loading sample_files, detect if fallback was used:

```python
sample_note = ""
if sample_files:
    loaded_tax_type = sample_files[0].get("tax_type", sac_thue)
    if loaded_tax_type != sac_thue:
        sample_note = f"[STYLE REFERENCE NOTE: The sample below is from {loaded_tax_type} — replicate FORMAT and STRUCTURE only, not the tax content]"
```

Return in context dict and inject into all 3 prompts (MCQ/Scenario/Longform) just before `{sample}`:

```
SAMPLE QUESTIONS — replicate this format and difficulty EXACTLY:
{sample_note}
{sample}
```

Update `MCQ_PROMPT`, `SCENARIO_PROMPT`, `LONGFORM_PROMPT` in `prompts.py` to include `{sample_note}` placeholder.
Update `generate_mcq`, `generate_scenario`, `generate_longform` in `routes/generate.py` to pass `sample_note=ctx.get("sample_note", "")`.

---

## Summary

| Priority | File | Change |
|---|---|---|
| 🔴 CRITICAL | `routes/generate.py` | Fix `_resolve_session_id()` to find session with files |
| 🔴 CRITICAL | `main.py` | Call `fix_default_session()` at startup |
| 🟡 HIGH | `context_builder.py` | Reduce MAX_CONTEXT_CHARS to 300K, add logging, add sample_note |
| 🟡 HIGH | `ai_provider.py` | Dynamic max_tokens (3K fast, 5K strong) |
| 🟢 MINOR | `prompts.py` | Add `{sample_note}` placeholder |

## Testing checklist after fix

Generate 1 CIT MCQ and verify in logs:
- [ ] `build_context: session_id=2` (not 1)
- [ ] `regulations: 3 files — ['Reg CIT Law67 2025', 'Reg CIT Decree320 2025', 'Reg CIT FCT Circular20 2026']`
- [ ] `syllabus: 1 files — ['Syllabus CIT D27']`
- [ ] `sample: 1 files — ['Sample MCQ CIT']`
- [ ] Output cites articles from Decree 320/2025 or Law 67/2025 (not Decree 132/2020)
- [ ] Output JSON has `syllabus_codes` field populated
- [ ] Claudible completes without timeout
