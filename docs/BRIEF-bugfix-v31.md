# ExamsGen — Bug Fix Brief v3.1
**Date:** March 2026
**Priority:** High — 3 bugs affecting generation quality

---

## Bug 1: Claudible timeout on large context

**Root cause:** When regulations are large (150K chars), the full prompt sent to Claudible exceeds what can be processed within 300s. Need to reduce context size.

**Fix in `context_builder.py`:**

Reduce `MAX_CONTEXT_CHARS` and `MAX_PER_REG_CHARS`:

```python
# Change these constants:
MAX_CONTEXT_CHARS = 300_000    # was 600_000 — keep within ~75K tokens for Claudible
MAX_PER_REG_CHARS = 80_000     # was 150_000 — cap each regulation file
```

**Fix in `ai_provider.py`:**

Reduce `max_tokens` per question type — MCQ doesn't need 8000 tokens:

```python
# Add a helper to get max_tokens per model_tier:
MAX_TOKENS_MAP = {
    "fast": 4000,    # MCQ — shorter output
    "strong": 6000,  # Scenario/Longform — longer output
}

# In the requests.post call, replace hardcoded 8000:
json={
    "model": model,
    "messages": messages,
    "max_tokens": MAX_TOKENS_MAP.get(model_tier, 4000),
    "temperature": 0.7,
},
```

---

## Bug 2: App uses old regulations instead of uploaded files

**Root cause:** There are TWO session systems in `/app/data/`:
- OLD (legacy): `/app/data/sessions/june_2026/regulations/...` — hardcoded files from old codebase
- NEW (current): `/app/data/sessions/2/regulation/...` — files uploaded by user via UI

The `_resolve_session_id()` function may be resolving to session id=1 (the seeded default) instead of session id=2 (where user uploaded files).

**Investigation needed:** Check what `_resolve_session_id()` returns and what session is actually `is_default=TRUE` in the DB.

**Fix in `routes/generate.py` — `_resolve_session_id()`:**

```python
def _resolve_session_id(session_id: int = None) -> int | None:
    with get_db() as conn:
        cur = conn.cursor()
        if session_id:
            cur.execute("SELECT id FROM exam_sessions WHERE id = %s", (session_id,))
        else:
            # Try default session first, then fall back to most recent
            cur.execute("""
                SELECT id FROM exam_sessions
                WHERE is_default = TRUE
                ORDER BY id DESC
                LIMIT 1
            """)
        row = cur.fetchone()
        if row:
            return row[0]
        # Last resort: use most recently created session
        cur.execute("SELECT id FROM exam_sessions ORDER BY id DESC LIMIT 1")
        row = cur.fetchone()
        return row[0] if row else None
```

**Also fix in `routes/generate.py`:** Log the resolved session_id clearly so it's visible in app logs:

```python
session_id = _resolve_session_id(req.session_id)
logger.info(f"Generating MCQ: session_id={session_id}, sac_thue={req.sac_thue}")
if not session_id:
    raise HTTPException(400, "No exam session configured. Please create a session first.")

ctx = build_context(session_id, req.sac_thue, "MCQ")
logger.info(f"Context built: regulations={len(ctx['regulations'])} chars, syllabus={len(ctx['syllabus'])} chars, sample={len(ctx['sample'])} chars, rates={len(ctx['tax_rates'])} chars")
```

This logging will confirm whether the right session/files are being loaded.

**Also:** Delete or ignore the old legacy data at `/app/data/sessions/june_2026/` — it is confusing and no longer used. Add to startup:

```python
# In seed.py or startup — ensure default session points to id with actual uploaded files
# Do NOT create a duplicate session 1 that has no files
```

---

## Bug 3: Sample file not used when generating (wrong tax type match)

**Root cause:** User uploaded `Sample_MCQ_CIT.docx` tagged as `tax_type='CIT'`. When generating **PIT** MCQs, `_load_files(session_id, 'sample', tax_type='PIT', exam_type='MCQ')` returns empty — no PIT sample exists yet → `sample = ""` → Claude generates from internal knowledge without following format.

**Fix in `context_builder.py` — `build_context()`:**

Add fallback: if no sample found for specific tax_type, load ANY sample of matching exam_type as style reference:

```python
# 3. Sample question — try specific tax type first, then fall back to any sample of same exam_type
sample_files = _load_files(session_id, "sample", tax_type=sac_thue, exam_type=exam_type)
if not sample_files:
    # Fallback: use any available sample of the same exam_type for style reference
    sample_files = _load_files(session_id, "sample", exam_type=exam_type)
    if sample_files:
        logger.info(f"No {sac_thue} sample found — using {sample_files[0]['tax_type']} sample as style reference")
```

**Additionally:** Update the prompt to explicitly tell Claude when a cross-tax sample is being used:

In `context_builder.py`, return metadata about the sample:

```python
sample_note = ""
if sample_files and sample_files[0].get("tax_type") != sac_thue:
    sample_note = f"[NOTE: Style reference below is from {sample_files[0].get('tax_type')} questions — adapt the FORMAT and STRUCTURE only, not the tax content]"
```

Return this in the context dict:
```python
return {
    "tax_rates": tax_rates,
    "syllabus": syllabus,
    "regulations": regulations,
    "sample": sample,
    "sample_note": sample_note,   # NEW field
}
```

Update `MCQ_PROMPT` in `prompts.py` to include sample_note:

```python
MCQ_PROMPT = """Generate {count} MCQ question(s) for Part 1 of ACCA TX(VNM).
...
SAMPLE QUESTIONS — replicate this format and difficulty EXACTLY:
{sample_note}
{sample}
...
```

Apply same sample fallback to `SCENARIO_PROMPT` and `LONGFORM_PROMPT`.

---

## Bug 4 (bonus): Output doesn't cite uploaded regulations — only uses internal knowledge

**Root cause:** Looking at the generated output, it cites `Decree 132/2020` and `Circular 96/2015` — these are **NOT in the uploaded regulations for session 2**. This confirms Bug 2 — regulations from session_files are NOT being loaded into the prompt.

**Additional verification step:** Add to `build_context()`:

```python
logger.info(f"Loaded regulations for {sac_thue}: {[f['name'] for f in reg_files]}")
logger.info(f"Loaded samples for {sac_thue}/{exam_type}: {[f['name'] for f in sample_files]}")
```

Check app logs after generation to confirm which files are actually loaded. If `reg_files = []`, the session_id bug is confirmed.

---

## Summary of changes

| File | Change |
|---|---|
| `backend/context_builder.py` | Reduce MAX_CONTEXT_CHARS to 300K, MAX_PER_REG_CHARS to 80K; add sample fallback; add logging |
| `backend/ai_provider.py` | Dynamic max_tokens per model_tier (4000 fast, 6000 strong) |
| `backend/routes/generate.py` | Fix `_resolve_session_id()` to use most recent session; add logging |
| `backend/prompts.py` | Add `{sample_note}` placeholder to MCQ/Scenario/Longform prompts |

---

## Testing after fix

After deploying, generate a PIT MCQ and check:
1. Logs show `session_id=2` (not 1)
2. Logs show `regulations=Reg_PIT_VBHN02` loaded
3. Output cites articles from `Reg_PIT_VBHN02` (not Decree 132/2020 which is TP)
4. Output follows MCQ format from sample file
5. Output includes `syllabus_codes` field in JSON
6. Claudible completes within 300s with reduced context
