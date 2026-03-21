# BRIEF: Bulk Delete + Smart Re-parse for KB
## Repo: phanvuhoang/examsgen

---

## PART 1: Bulk Delete for Syllabus + Regulation Parsed Items

Add checkbox selection and bulk delete to both the Syllabus tab and Regulations (parsed paragraphs) tab in Knowledge Base.

### 1.1 UI Pattern (same for both tabs)

Add a checkbox column as the **first column** of each table. Add a "Select all" checkbox in the header.

```
☐  | Code  | Topics | Detailed Syllabus          | Actions
☑  | A1a   | ...    | Understand who is subject  | [Edit][🗑]
☑  | A1b   | ...    | Distinguish between...     | [Edit][🗑]
☐  | B2a   | ...    | Identify deductible...     | [Edit][🗑]
```

When 1+ items are selected, show a **bulk action bar** above the table:

```
┌─────────────────────────────────────────────────────────────┐
│  ✓ 2 items selected      [🗑 Delete selected]  [✕ Clear]   │
└─────────────────────────────────────────────────────────────┘
```

**[🗑 Delete selected]** → confirmation dialog:
```
Delete 2 items?
This will permanently remove the selected syllabus/regulation items.
[ Cancel ]  [ Delete ]
```
On confirm → bulk delete API → refresh list → clear selection.

### 1.2 State additions (per tab component)

```javascript
const [selectedIds, setSelectedIds] = useState(new Set())

const toggleSelect = (id) => {
  setSelectedIds(prev => {
    const next = new Set(prev)
    next.has(id) ? next.delete(id) : next.add(id)
    return next
  })
}

const toggleSelectAll = () => {
  if (selectedIds.size === items.length) {
    setSelectedIds(new Set())
  } else {
    setSelectedIds(new Set(items.map(i => i.id)))
  }
}

const handleBulkDelete = async () => {
  if (!window.confirm(`Delete ${selectedIds.size} items? This cannot be undone.`)) return
  await api.bulkDeleteKBItems(type, [...selectedIds])  // type = 'syllabus' | 'regulation-parsed'
  setSelectedIds(new Set())
  fetchItems()
}
```

### 1.3 New Backend Endpoints

#### DELETE /api/kb/syllabus/bulk
```python
@router.delete("/syllabus/bulk")
def bulk_delete_syllabus(data: dict):
    """Delete multiple syllabus items by id list."""
    ids = data.get('ids', [])
    if not ids:
        return {"deleted": 0}
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM kb_syllabus WHERE id = ANY(%s) RETURNING id", (ids,))
        deleted = len(cur.fetchall())
    return {"deleted": deleted}
```

#### DELETE /api/kb/regulation-parsed/bulk
```python
@router.delete("/regulation-parsed/bulk")
def bulk_delete_reg_parsed(data: dict):
    """Delete multiple parsed regulation items by id list."""
    ids = data.get('ids', [])
    if not ids:
        return {"deleted": 0}
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM kb_regulation_parsed WHERE id = ANY(%s) RETURNING id", (ids,))
        deleted = len(cur.fetchall())
    return {"deleted": deleted}
```

### 1.4 api.js additions

```javascript
bulkDeleteKBItems: async (type, ids) => {
  // type: 'syllabus' | 'regulation-parsed'
  const res = await fetch(`/api/kb/${type}/bulk`, {
    method: 'DELETE',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ ids })
  })
  return res.ok
},
```

### 1.5 Individual Delete button

Replace the text "✕" or "Delete" action button with a **trash icon** (🗑 or SVG):

```jsx
<button
  onClick={() => handleDelete(item.id)}
  className="text-red-400 hover:text-red-600 transition-colors"
  title="Delete"
>
  <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
    <path fillRule="evenodd" d="M9 2a1 1 0 00-.894.553L7.382 4H4a1 1 0 000 2v10a2 2 0 002 2h8a2 2 0 002-2V6a1 1 0 100-2h-3.382l-.724-1.447A1 1 0 0011 2H9zM7 8a1 1 0 012 0v6a1 1 0 11-2 0V8zm5-1a1 1 0 00-1 1v6a1 1 0 102 0V8a1 1 0 00-1-1z" clipRule="evenodd" />
  </svg>
</button>
```

---

## PART 2: Smart Re-parse (Avoid Duplicates)

### Problem
If parse is interrupted mid-way, or user wants to re-parse a file, clicking [Parse] again creates **duplicate rows** because there's no deduplication logic.

### Solution: Auto-clear before re-parse

When [Parse] is clicked on a file that **already has parsed items** in the DB (same `source_file` + `session_id`), automatically **delete existing rows for that file first**, then re-parse.

No confirmation dialog needed — parsing is idempotent when you clear first.

### 2.1 Backend — Update parse-doc to clear first

In `backend/routes/kb.py`, update `POST /api/kb/regulations/parse-doc`:

```python
@router.post("/regulations/parse-doc")
def parse_regulation_doc(data: dict):
    session_id = data['session_id']
    tax_type = data['tax_type']
    file_path = data['file_path']
    doc_ref = data.get('doc_ref', '')

    # ── Clear existing parsed rows for this file (smart re-parse) ──
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "DELETE FROM kb_regulation_parsed WHERE session_id = %s AND source_file = %s",
            (session_id, file_path)
        )
        deleted_count = cur.rowcount

    # ── Rest of parse logic (unchanged) ──
    # ... extract text, call AI, insert new rows ...

    # Log if re-parse
    if deleted_count > 0:
        import logging
        logging.info(f"Re-parse: cleared {deleted_count} existing rows for {file_path}")

    # Return includes re_parse info
    return {
        "parsed": len(rows),
        "rows": rows,
        "re_parsed": deleted_count > 0,
        "cleared": deleted_count
    }
```

### 2.2 Backend — Update syllabus bulk-insert to clear first

In `POST /api/kb/syllabus/bulk-insert`, add a `replace` flag:

```python
@router.post("/syllabus/bulk-insert")
def bulk_insert_syllabus(data: dict):
    session_id = data['session_id']
    tax_type = data['tax_type']
    rows = data['rows']
    replace = data.get('replace', True)  # default: replace existing for this session+tax_type

    with get_db() as conn:
        cur = conn.cursor()

        if replace:
            # Clear existing syllabus for this session + tax_type before inserting
            cur.execute(
                "DELETE FROM kb_syllabus WHERE session_id = %s AND COALESCE(tax_type, sac_thue) = %s",
                (session_id, tax_type)
            )
            cleared = cur.rowcount
        else:
            cleared = 0

        # Insert new rows (unchanged UPDATE+INSERT logic)
        for row in rows:
            code = row.get('code') or row.get('syllabus_code', '')
            topic = row.get('topics') or row.get('topic', '')
            detail = row.get('detailed_syllabus', '')
            cur.execute("""
                UPDATE kb_syllabus
                SET topic = %s, detailed_syllabus = %s, section_title = %s, content = %s
                WHERE session_id = %s AND tax_type = %s AND syllabus_code = %s
            """, (topic, detail, topic, detail, session_id, tax_type, code))
            if cur.rowcount == 0:
                cur.execute("""
                    INSERT INTO kb_syllabus (session_id, tax_type, syllabus_code, topic, detailed_syllabus,
                                            sac_thue, section_code, section_title, content)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (session_id, tax_type, code, topic, detail,
                      tax_type, code, topic, detail))

    return {"inserted": len(rows), "cleared": cleared}
```

### 2.3 Frontend — Upload Preview Modal: Show Warning if Re-uploading

When user confirms import in the syllabus upload modal, if the DB already has items for this session + tax_type, show a small warning:

```jsx
{existingCount > 0 && (
  <div className="mb-3 p-2 bg-amber-50 border border-amber-200 rounded text-xs text-amber-700">
    ⚠️ This will replace {existingCount} existing syllabus items for {taxType}.
  </div>
)}
```

To get `existingCount`: call `GET /api/kb/syllabus?session_id=X&tax_type=Y` before showing confirm step and count the results.

### 2.4 Frontend — [Parse] button: Show Re-parse indicator

In the Regulations tab, when [Parse] is clicked on a file that already has parsed rows, show a loading message like:

```
"Re-parsing CIT_Decree_320_2025_ENG.docx (clearing 47 existing paragraphs)..."
```

The response from `parse-doc` now includes `re_parsed: true` and `cleared: 47` — use these to show the message.

---

## SUMMARY — Files to Create/Modify

| Action | File | Change |
|--------|------|--------|
| MODIFY | `backend/routes/kb.py` | Add `DELETE /syllabus/bulk`, `DELETE /regulation-parsed/bulk`; update `parse-doc` to clear first; update `bulk-insert` to clear+replace |
| MODIFY | `frontend/src/pages/KnowledgeBase.jsx` | Add checkbox column + Select All; bulk action bar; trash icon for individual delete; re-parse warning message; re-upload warning |
| MODIFY | `frontend/src/api.js` | Add `bulkDeleteKBItems` |

---

## NOTES FOR CLAUDE CODE

1. **Checkbox column width**: `w-8`, centered — don't let it take up space
2. **Select-all state**: 3 states — none selected, some selected (indeterminate), all selected. Use `indeterminate` attribute on the header checkbox when `0 < selected < total`
3. **Bulk delete confirmation**: use `window.confirm()` — no need for a custom modal, keep it simple
4. **Re-parse default = clear first**: Don't ask the user — just clear and re-parse. This is the expected behavior (idempotent).
5. **replace=true default** for syllabus bulk-insert: always replace. If user uploaded wrong file and re-uploads the correct one, they expect the old data to be gone.
6. **Trash icon**: use inline SVG (the one in Part 1.5 above) — don't add a new icon library dependency
7. **Bulk action bar**: show ABOVE the table, only when `selectedIds.size > 0`. Use `sticky top-0` with a slight shadow so it's visible when scrolling long lists.
