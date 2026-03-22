# BRIEF: Fix Bulk Delete + Pagination + Import Parsed Regulations
## Repo: phanvuhoang/examsgen

---

## PART 1: Fix Bulk Delete (Route Ordering Bug)

### Root Cause
FastAPI matches routes in declaration order. Currently in `backend/routes/kb.py`:

```
Line 109: @router.delete("/syllabus/{item_id}")      ← declared FIRST
Line 877: @router.delete("/syllabus/bulk")            ← declared AFTER ← BUG

Line 778: @router.delete("/regulation-parsed/{item_id}")  ← declared FIRST
Line 890: @router.delete("/regulation-parsed/bulk")       ← declared AFTER ← BUG
```

When frontend calls `DELETE /api/kb/syllabus/bulk`, FastAPI matches it to
`/syllabus/{item_id}` with `item_id="bulk"` → 422 Unprocessable Entity.
**Fix: move `/bulk` endpoints BEFORE the `/{item_id}` endpoints.**

### Fix — Move bulk delete definitions to BEFORE the /{item_id} routes

In `backend/routes/kb.py`:

1. **Cut** the `@router.delete("/syllabus/bulk")` block (lines 877–887) and
   **paste it BEFORE** `@router.delete("/syllabus/{item_id}")` (line 109).

2. **Cut** the `@router.delete("/regulation-parsed/bulk")` block (lines 890–900) and
   **paste it BEFORE** `@router.delete("/regulation-parsed/{item_id}")` (line 778).

Final order should be:
```python
# ── Syllabus ──────────────────────────────────────────────────
@router.get("/syllabus")
@router.post("/syllabus")
@router.put("/syllabus/{item_id}")
@router.delete("/syllabus/bulk")        # ← BEFORE /{item_id}
@router.delete("/syllabus/{item_id}")

# ── Regulation Parsed ─────────────────────────────────────────
@router.put("/regulation-parsed/{item_id}")
@router.delete("/regulation-parsed/bulk")    # ← BEFORE /{item_id}
@router.delete("/regulation-parsed/{item_id}")
```

Also add `setSelectedIds(new Set())` after successful bulk delete in the frontend
(currently missing — line 350 calls `fetchParsed()` but doesn't clear selection before):

```javascript
const handleBulkDelete = async () => {
  if (!window.confirm(`Delete ${selectedIds.size} items? This cannot be undone.`)) return
  await api.bulkDeleteKBItems('regulation-parsed', [...selectedIds])
  setSelectedIds(new Set())   // ← add this line (currently missing)
  fetchParsed()
  fetchRegFiles()
}
```

Same fix for the SyllabusTab `handleBulkDelete` — add `setSelectedIds(new Set())` before `fetchItems()`.

---

## PART 2: Fix Pagination — Show All Items (not just 100)

### Root Cause
- Backend default: `limit: int = Query(100, le=500)` → caps at 100 even for 754 items
- Frontend `api.getRegulationsParsed(params)` never passes `limit` → always gets 100
- No pagination UI → user can't see remaining 654 items

### Fix A — Backend: raise default + max limit

In `backend/routes/kb.py`, update `@router.get("/regulations/parsed")`:

```python
# Change:
limit: int = Query(100, le=500),
# To:
limit: int = Query(1000, le=2000),
```

### Fix B — Frontend: pass limit=1000, show count + simple pagination

In `frontend/src/pages/KnowledgeBase.jsx`, update `fetchParsed`:

```javascript
const fetchParsed = async () => {
  if (!sessionId) return
  setLoading(true)
  try {
    const params = { session_id: sessionId, limit: 1000 }   // ← add limit: 1000
    if (taxType) params.tax_type = taxType
    if (regFileFilter) params.source_file = regFileFilter
    if (syllabusFilter) params.syllabus_code = syllabusFilter
    if (articleFilter) params.article_no = articleFilter
    if (search) params.search = search
    const data = await api.getRegulationsParsed(params)
    setParsedRows(data.items || [])
    setTotal(data.total || 0)
    setSelectedIds(new Set())
  } catch { setParsedRows([]); setTotal(0) }
  finally { setLoading(false) }
}
```

### Fix C — Frontend: show "Showing X of Y" counter

Replace the current `{total} paragraphs` display (line 521) with:

```jsx
<span className="text-xs text-gray-400 ml-auto">
  Showing {parsedRows.length} of {total} items
</span>
```

---

## PART 3: Delete Existing Parsed Data (3 documents from yesterday's import)

**Do this via direct DB query in the parse-doc-async or a one-time cleanup:**

Add a "Clear All Parsed" button to the Regulations tab toolbar (next to existing buttons):

```jsx
<button
  onClick={handleClearAll}
  disabled={parsedRows.length === 0}
  className="px-3 py-1.5 text-sm bg-red-600 hover:bg-red-700 text-white rounded disabled:opacity-50"
  title="Delete ALL parsed items for this session"
>
  🗑 Clear All ({total})
</button>
```

```javascript
const handleClearAll = async () => {
  if (!window.confirm(`Delete ALL ${total} parsed items for this session? This cannot be undone.`)) return
  // Select all IDs and bulk delete
  const allData = await api.getRegulationsParsed({ session_id: sessionId, tax_type: taxType, limit: 5000 })
  const allIds = (allData.items || []).map(i => i.id)
  if (allIds.length > 0) {
    await api.bulkDeleteKBItems('regulation-parsed', allIds)
  }
  fetchParsed()
  fetchRegFiles()
}
```

---

## PART 4: Import Parsed Regulations (CSV/JSON upload)

Allow importing pre-parsed + syllabus-matched regulation items from an external file
(similar to how Syllabus tab handles CSV/Excel upload).

This supports the workflow where parsing & matching is done outside the app
(e.g., via script, or in a future standalone tool) and results are imported in bulk.

### 4.1 Backend — New endpoint: `POST /api/kb/regulation-parsed/import`

```python
@router.post("/regulation-parsed/import")
def import_regulation_parsed(data: dict):
    """
    Bulk import pre-parsed regulation items.
    Accepts list of rows with: reg_code, doc_ref, article_no, paragraph_text,
    syllabus_codes (optional), tags (optional), source_file (optional).
    Clears existing rows for same (session_id, source_file) before insert if replace=True.
    """
    session_id  = data['session_id']
    tax_type    = data['tax_type']
    rows        = data['rows']         # list of dicts
    replace     = data.get('replace', True)
    source_file = data.get('source_file', 'imported')

    if not rows:
        return {"imported": 0}

    with get_db() as conn:
        cur = conn.cursor()

        if replace:
            cur.execute(
                "DELETE FROM kb_regulation_parsed WHERE session_id = %s AND source_file = %s",
                (session_id, source_file)
            )
            cleared = cur.rowcount
        else:
            cleared = 0

        inserted = 0
        for row in rows:
            reg_code       = row.get('reg_code', '').strip()
            paragraph_text = row.get('paragraph_text', '').strip()
            if not reg_code or not paragraph_text:
                continue   # skip rows missing required fields

            syllabus_codes = row.get('syllabus_codes', [])
            if isinstance(syllabus_codes, str):
                # Accept comma-separated string: "B2a,B2b" → ["B2a","B2b"]
                syllabus_codes = [s.strip() for s in syllabus_codes.split(',') if s.strip()]

            article_no  = row.get('article_no', '')
            clause_no   = row.get('clause_no', 0)
            doc_ref     = row.get('doc_ref', '')
            tags        = row.get('tags', '')
            src_file    = row.get('source_file', source_file)

            cur.execute("""
                INSERT INTO kb_regulation_parsed
                  (session_id, tax_type, reg_code, doc_ref, article_no, paragraph_no,
                   paragraph_text, syllabus_codes, tags, source_file, is_active)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, TRUE)
                ON CONFLICT (session_id, reg_code) DO UPDATE SET
                  paragraph_text = EXCLUDED.paragraph_text,
                  syllabus_codes = EXCLUDED.syllabus_codes,
                  doc_ref        = EXCLUDED.doc_ref,
                  article_no     = EXCLUDED.article_no,
                  tags           = EXCLUDED.tags
            """, (
                session_id, tax_type, reg_code, doc_ref, article_no,
                int(clause_no or 0), paragraph_text, syllabus_codes, tags, src_file,
            ))
            inserted += 1

    return {"imported": inserted, "cleared": cleared, "source_file": source_file}
```

Also add `POST /api/kb/regulation-parsed/upload` for CSV/Excel file upload
(reuse the same pattern as `/syllabus/upload`):

```python
@router.post("/regulation-parsed/upload")
async def upload_regulation_parsed(
    file: UploadFile = File(...),
    session_id: int = Form(...),
    tax_type: str = Form(...),
    replace: bool = Form(True),
):
    """
    Upload CSV or Excel file of pre-parsed regulation items.
    Required columns: reg_code, paragraph_text
    Optional columns: doc_ref, article_no, clause_no, syllabus_codes, tags, source_file
    """
    import pandas as pd
    import io

    content = await file.read()
    try:
        if file.filename.endswith('.csv'):
            df = pd.read_csv(io.BytesIO(content))
        else:
            df = pd.read_excel(io.BytesIO(content))
    except Exception as e:
        return {"error": f"Cannot read file: {e}"}

    required_cols = {'reg_code', 'paragraph_text'}
    if not required_cols.issubset(df.columns):
        missing = required_cols - set(df.columns)
        return {"error": f"Missing required columns: {missing}"}

    rows = df.where(pd.notnull(df), None).to_dict('records')
    source_file = file.filename

    return import_regulation_parsed({
        "session_id":  session_id,
        "tax_type":    tax_type,
        "rows":        rows,
        "replace":     replace,
        "source_file": source_file,
    })
```

### 4.2 Frontend — Add Import button to Regulations tab

In the Regulations tab toolbar (next to Parse button), add an **Import** button
that opens an upload modal (same pattern as Syllabus upload modal):

```jsx
{/* Import parsed regulations button */}
<label className="px-3 py-1.5 text-sm bg-green-600 hover:bg-green-700 text-white rounded cursor-pointer">
  📥 Import CSV/Excel
  <input
    type="file"
    accept=".csv,.xlsx,.xls"
    className="hidden"
    onChange={handleImportFile}
  />
</label>
```

```javascript
const handleImportFile = async (e) => {
  const file = e.target.files[0]
  if (!file || !taxType || !sessionId) { alert('Select tax type first'); return }

  const fd = new FormData()
  fd.append('file', file)
  fd.append('session_id', sessionId)
  fd.append('tax_type', taxType)
  fd.append('replace', 'true')

  setLoading(true)
  try {
    const res = await fetch('/api/kb/regulation-parsed/upload', {
      method: 'POST',
      headers: { Authorization: `Bearer ${localStorage.getItem('token')}` },
      body: fd,
    })
    const data = await res.json()
    if (data.error) {
      alert(`Import failed: ${data.error}`)
    } else {
      setToast(`Imported ${data.imported} items (cleared ${data.cleared} existing)`)
      fetchParsed()
      fetchRegFiles()
    }
  } catch (err) {
    alert(`Import error: ${err.message}`)
  } finally {
    setLoading(false)
    e.target.value = ''
  }
}
```

**Preview before import (optional but nice):**
Same as syllabus — show a preview modal with first 5 rows + total count before confirming.
If preview is too complex, skip it and just import directly with a success toast.

### 4.3 Required columns for import file

| Column | Required | Format | Notes |
|---|---|---|---|
| `reg_code` | ✅ | `CIT-Decree320-2025-Art23.1.a` | Unique per session |
| `paragraph_text` | ✅ | Plain text | Max 1200 chars recommended |
| `doc_ref` | optional | `Decree 320/2025/ND-CP` | |
| `article_no` | optional | `Article 23` | |
| `clause_no` | optional | `1` | Numeric |
| `syllabus_codes` | optional | `B2a,B2b` or JSON array | Comma-separated OK |
| `tags` | optional | `Deductible Expenses` | Article title/topic |
| `source_file` | optional | `decree320.csv` | Groups items by file |

---

## SUMMARY — Files to Create/Modify

| Action | File | Change |
|--------|------|--------|
| MODIFY | `backend/routes/kb.py` | Move `/syllabus/bulk` before `/syllabus/{item_id}`; move `/regulation-parsed/bulk` before `/regulation-parsed/{item_id}`; raise default limit to 1000; add `POST /regulation-parsed/import`; add `POST /regulation-parsed/upload` |
| MODIFY | `frontend/src/pages/KnowledgeBase.jsx` | Add `limit: 1000` to fetchParsed; fix "Showing X of Y"; add `setSelectedIds(new Set())` after bulk delete; add "Clear All" button; add "Import CSV/Excel" button + handler |

---

## NOTES FOR CLAUDE CODE

1. **Route ordering is critical in FastAPI** — `/bulk` MUST be declared before `/{item_id}` or it will never match
2. **Do NOT change the bulk delete logic itself** — only move the route definitions earlier in the file
3. **limit=1000 is safe** — 754 items × ~1.2KB avg = ~900KB payload, well within browser limits
4. **"Clear All" button** — fetch all IDs then bulk delete (don't add a new DB endpoint; reuse existing bulk delete)
5. **Import CSV/Excel** — reuse pandas (already in requirements.txt from syllabus upload); same upload pattern
6. **`syllabus_codes` CSV format** — accept both `"B2a,B2b"` (string) and `["B2a","B2b"]` (JSON array) — normalize on backend
7. **ON CONFLICT DO UPDATE** in import — idempotent, safe to re-import same file
8. **No route ordering issues with new endpoints** — `/regulation-parsed/import` and `/regulation-parsed/upload` are POST, not DELETE, so no conflict with `/{item_id}` DELETE routes
9. **After any delete/import, always call both `fetchParsed()` AND `fetchRegFiles()`** so the file list counts update too
