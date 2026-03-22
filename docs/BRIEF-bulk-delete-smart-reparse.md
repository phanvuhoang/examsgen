# BRIEF: Bulk Delete + Smart Re-parse + Rule-Based Parser for KB
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
            cur.execute(
                "DELETE FROM kb_syllabus WHERE session_id = %s AND COALESCE(tax_type, sac_thue) = %s",
                (session_id, tax_type)
            )
            cleared = cur.rowcount
        else:
            cleared = 0

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

```jsx
{existingCount > 0 && (
  <div className="mb-3 p-2 bg-amber-50 border border-amber-200 rounded text-xs text-amber-700">
    ⚠️ This will replace {existingCount} existing syllabus items for {taxType}.
  </div>
)}
```

### 2.4 Frontend — [Parse] button: Show Re-parse indicator

In the Regulations tab, when [Parse] is clicked on a file that already has parsed rows, show:
```
"Re-parsing CIT_Decree_320_2025_ENG.docx (clearing 47 existing paragraphs)..."
```
The response from `parse-doc` includes `re_parsed: true` and `cleared: 47` — use these to show the message.

---

## PART 3: Rule-Based Parser (Replace AI Parser for .docx/.doc files)

### Problem with current AI parser
- AI parser outputs ~31–203 items per file (inconsistent)
- Granularity is wrong: paragraph-level instead of sub-clause level
- Duplicates common when re-parsing
- Cannot reach sub-clause level: Art23.1.a, Art23.1.b etc.

### Solution: Rule-based parser integrated into backend

Replace the AI parse path for `.docx`/`.doc`/`.txt` files with a deterministic rule-based parser.
AI is still used **after parsing** to suggest `syllabus_codes` per item.

### 3.1 New parse logic — `backend/utils/rule_parser.py`

Create this new file:

```python
"""
Rule-Based Regulation Parser
Parses Law/Decree/Circular docx/txt into sub-clause level items.
Format: {TAX_TYPE}-{DocSlug}-Art{N}.{clause}.{letter}
Example: CIT-Decree320-2025-Art23.1.a
"""
import re
from typing import List, Dict, Optional

try:
    from docx import Document as DocxDocument
    HAS_DOCX = True
except ImportError:
    HAS_DOCX = False

# ── Regex Patterns ─────────────────────────────────────────────────────────────
ART_RE    = re.compile(r'^Article\s+(\d+)\.\s+(.+)$', re.MULTILINE)
CLAUSE_RE = re.compile(r'^\s*(\d+)\.\s+\S', re.MULTILINE)
LETTER_RE = re.compile(r'^\s*([a-z]\d*)\)\s+\S', re.MULTILINE)


def extract_text_from_file(file_path: str) -> str:
    """Extract plain text from .docx, .doc, or .txt file."""
    if file_path.endswith('.txt'):
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()
    if file_path.endswith('.docx') and HAS_DOCX:
        doc = DocxDocument(file_path)
        return '\n'.join(p.text for p in doc.paragraphs if p.text.strip())
    # Fallback: try antiword for .doc
    import subprocess
    try:
        result = subprocess.run(['antiword', file_path], capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            return result.stdout
    except Exception:
        pass
    raise ValueError(f"Cannot extract text from {file_path}: unsupported format or missing tool")


def parse_regulation_text(text: str, doc_slug: str, tax_type: str, doc_ref: str) -> List[Dict]:
    """
    Parse regulation text into sub-clause level items.
    Returns list of dicts ready for DB insert into kb_regulation_parsed.
    """
    items = []
    art_splits = list(ART_RE.finditer(text))

    for i, art_match in enumerate(art_splits):
        art_no    = art_match.group(1)
        art_title = art_match.group(2).strip()
        art_start = art_match.end()
        art_end   = art_splits[i + 1].start() if i + 1 < len(art_splits) else len(text)
        art_body  = text[art_start:art_end].strip()

        clause_splits = list(CLAUSE_RE.finditer(art_body))

        if not clause_splits:
            # No numbered clauses → whole article = one item
            items.append(_make_item(
                reg_code=f'{tax_type}-{doc_slug}-Art{art_no}',
                doc_ref=doc_ref, art_no=art_no, art_title=art_title,
                clause_no=None, letter_no=None,
                text=art_body[:1000], tax_type=tax_type,
            ))
            continue

        for j, cl_match in enumerate(clause_splits):
            cl_no_m = re.match(r'(\d+)', art_body[cl_match.start():])
            cl_no   = cl_no_m.group(1) if cl_no_m else str(j + 1)
            cl_start = cl_match.start()
            cl_end   = clause_splits[j + 1].start() if j + 1 < len(clause_splits) else len(art_body)
            cl_body  = art_body[cl_start:cl_end].strip()

            letter_splits = list(LETTER_RE.finditer(cl_body))

            if not letter_splits:
                # No lettered sub-clauses → whole clause = one item
                items.append(_make_item(
                    reg_code=f'{tax_type}-{doc_slug}-Art{art_no}.{cl_no}',
                    doc_ref=doc_ref, art_no=art_no, art_title=art_title,
                    clause_no=cl_no, letter_no=None,
                    text=cl_body[:1000], tax_type=tax_type,
                ))
                continue

            intro = cl_body[:letter_splits[0].start()].strip()

            for k, lt_match in enumerate(letter_splits):
                segment = cl_body[lt_match.start():].lstrip()
                lt_letter_m = re.match(r'([a-z]\d*)\)', segment)
                if not lt_letter_m:
                    continue
                lt_letter = lt_letter_m.group(1)
                lt_start  = lt_match.start()
                lt_end    = letter_splits[k + 1].start() if k + 1 < len(letter_splits) else len(cl_body)
                lt_text   = cl_body[lt_start:lt_end].strip()
                full_text = (intro[:300] + '\n' + lt_text) if intro else lt_text

                items.append(_make_item(
                    reg_code=f'{tax_type}-{doc_slug}-Art{art_no}.{cl_no}.{lt_letter}',
                    doc_ref=doc_ref, art_no=art_no, art_title=art_title,
                    clause_no=cl_no, letter_no=lt_letter,
                    text=full_text[:1200], tax_type=tax_type,
                ))

    return items


def _make_item(reg_code, doc_ref, art_no, art_title, clause_no, letter_no, text, tax_type):
    return {
        'reg_code': reg_code,
        'doc_ref': doc_ref,
        'article_no': f'Article {art_no}',
        'clause_no': clause_no,
        'letter_no': letter_no,
        'paragraph_text': text,
        'title': art_title,
        'tax_type': tax_type,
    }
```

### 3.2 Update `POST /api/kb/regulations/parse-doc` to use rule-based parser

In `backend/routes/kb.py`, modify the `parse-doc` endpoint:

```python
from backend.utils.rule_parser import extract_text_from_file, parse_regulation_text

@router.post("/regulations/parse-doc")
def parse_regulation_doc(data: dict):
    session_id  = data['session_id']
    tax_type    = data['tax_type']
    file_path   = data['file_path']   # absolute path inside container, e.g. /app/data/regs/decree320.docx
    doc_ref     = data.get('doc_ref', '')
    doc_slug    = data.get('doc_slug', '')   # e.g. "Decree320-2025"

    # If doc_slug not provided, derive from filename
    if not doc_slug:
        import os
        base = os.path.splitext(os.path.basename(file_path))[0]
        doc_slug = base.replace(' ', '-').replace('_', '-')

    # ── Clear existing rows for this file (idempotent re-parse) ──
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "DELETE FROM kb_regulation_parsed WHERE session_id = %s AND source_file = %s",
            (session_id, os.path.basename(file_path))
        )
        cleared = cur.rowcount

    # ── Rule-based parse ──
    try:
        text  = extract_text_from_file(file_path)
        items = parse_regulation_text(text, doc_slug, tax_type, doc_ref)
    except Exception as e:
        return {"error": str(e), "parsed": 0}

    # ── Insert into DB ──
    source_file = os.path.basename(file_path)
    inserted = 0
    with get_db() as conn:
        cur = conn.cursor()
        for item in items:
            cur.execute("""
                INSERT INTO kb_regulation_parsed
                  (session_id, tax_type, reg_code, doc_ref, article_no, paragraph_no,
                   paragraph_text, syllabus_codes, tags, source_file, is_active)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, TRUE)
                ON CONFLICT (session_id, reg_code) DO UPDATE SET
                  paragraph_text = EXCLUDED.paragraph_text,
                  doc_ref        = EXCLUDED.doc_ref,
                  article_no     = EXCLUDED.article_no
            """, (
                session_id, item['tax_type'], item['reg_code'], item['doc_ref'],
                item['article_no'], int(item['clause_no'] or 0),
                item['paragraph_text'],
                [],            # syllabus_codes: empty until AI-tagged
                item['title'][:200],
                source_file,
            ))
            inserted += 1

    return {
        "parsed":    inserted,
        "cleared":   cleared,
        "re_parsed": cleared > 0,
        "doc_slug":  doc_slug,
        "source":    "rule-based",
    }
```

### 3.3 New endpoint: `POST /api/kb/regulations/tag-syllabus`

After parsing, the UI can call this endpoint to AI-tag `syllabus_codes` for all untagged items in a session:

```python
@router.post("/regulations/tag-syllabus")
def tag_syllabus_codes(data: dict):
    """
    Use AI (Claudible claude-haiku) to suggest syllabus_codes for
    regulation items that have empty syllabus_codes.
    Runs in batches of 20.
    """
    session_id = data['session_id']
    tax_type   = data.get('tax_type')   # optional filter
    force      = data.get('force', False)  # if True, re-tag even items that already have codes

    with get_db() as conn:
        cur = conn.cursor()

        # Load syllabus for context
        cur.execute("""
            SELECT COALESCE(syllabus_code, section_code),
                   COALESCE(topic, section_title),
                   COALESCE(detailed_syllabus, content)
            FROM kb_syllabus
            WHERE session_id = %s
              AND (%s IS NULL OR COALESCE(tax_type, sac_thue) = %s)
              AND COALESCE(syllabus_code, section_code) IS NOT NULL
            ORDER BY COALESCE(syllabus_code, section_code)
        """, (session_id, tax_type, tax_type))
        syllabus_rows = cur.fetchall()

        if not syllabus_rows:
            return {"error": "No syllabus loaded for this session", "tagged": 0}

        # Load untagged (or all if force=True) regulation items
        if force:
            cur.execute("""
                SELECT id, reg_code, paragraph_text
                FROM kb_regulation_parsed
                WHERE session_id = %s
                  AND (%s IS NULL OR tax_type = %s)
                ORDER BY id
            """, (session_id, tax_type, tax_type))
        else:
            cur.execute("""
                SELECT id, reg_code, paragraph_text
                FROM kb_regulation_parsed
                WHERE session_id = %s
                  AND (%s IS NULL OR tax_type = %s)
                  AND (syllabus_codes IS NULL OR syllabus_codes = '{}')
                ORDER BY id
            """, (session_id, tax_type, tax_type))
        items = cur.fetchall()  # [(id, reg_code, paragraph_text), ...]

    if not items:
        return {"tagged": 0, "message": "No untagged items found"}

    # Build syllabus list string for prompt
    syllabus_list = '\n'.join(
        f'- [{r[0]}] {r[1]}: {r[2][:80] if r[2] else ""}' for r in syllabus_rows[:80]
    )

    tagged = 0
    batch_size = 20

    for i in range(0, len(items), batch_size):
        batch = items[i:i + batch_size]
        items_text = '\n\n'.join(
            f'[{item[1]}]\n{item[2][:300]}' for item in batch
        )

        prompt = f"""You are an ACCA TX(VNM) exam analyst. For each regulation item below, identify which syllabus items it relates to.

SYLLABUS ITEMS:
{syllabus_list}

REGULATION ITEMS TO CLASSIFY:
{items_text}

Return ONLY valid JSON (no markdown), mapping reg_code to array of matching syllabus codes:
{{
  "CIT-Decree320-2025-Art9.1.a": ["B2a", "B2b"],
  "CIT-Decree320-2025-Art23.1.a": ["C1a"]
}}

Rules:
- Only include codes that ACTUALLY appear in the syllabus list above
- If no good match, use empty array []
- Be precise: only codes directly relevant to what the item governs
"""

        try:
            # Use internal AI proxy (Claudible)
            from backend.utils.ai_client import call_ai   # existing helper
            response_text = call_ai(
                model='claude-haiku-4-5',
                messages=[{'role': 'user', 'content': prompt}],
                max_tokens=2000,
            )
            import json, re as _re
            json_match = _re.search(r'\{[\s\S]+\}', response_text)
            if json_match:
                batch_result = json.loads(json_match.group())
                # Update DB
                with get_db() as conn:
                    cur = conn.cursor()
                    for item in batch:
                        codes = batch_result.get(item[1], [])
                        if codes or force:
                            cur.execute(
                                "UPDATE kb_regulation_parsed SET syllabus_codes = %s WHERE id = %s",
                                (codes, item[0])
                            )
                            tagged += 1
        except Exception as e:
            import logging
            logging.warning(f"AI tagging batch {i//batch_size + 1} failed: {e}")
            continue

    return {"tagged": tagged, "total_items": len(items), "syllabus_count": len(syllabus_rows)}
```

### 3.4 UI — Regulations Tab: Fix display + add "Tag Syllabus" button

#### Fix pagination — show ALL items (not just 100)

In `GET /api/kb/regulation-parsed`, currently returns max 100. Fix to return all (or proper pagination):

```python
@router.get("/regulation-parsed")
def get_regulation_parsed(session_id: int, tax_type: str = None, limit: int = 1000, offset: int = 0):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, reg_code, doc_ref, article_no, paragraph_text,
                   syllabus_codes, tags, source_file, is_active
            FROM kb_regulation_parsed
            WHERE session_id = %s
              AND (%s IS NULL OR tax_type = %s)
            ORDER BY
              -- Sort by natural article order: Art1 < Art2 < ... < Art10 (not lexicographic)
              regexp_replace(reg_code, '.*Art(\d+).*', '\1')::int,
              -- Then by clause number
              COALESCE(NULLIF(regexp_replace(reg_code, '.*\.(\d+)\.[a-z].*', '\1'), reg_code), '0')::int,
              -- Then by letter
              reg_code
            LIMIT %s OFFSET %s
        """, (session_id, tax_type, tax_type, limit, offset))
        rows = cur.fetchall()
        # Also return total count
        cur.execute("""
            SELECT COUNT(*) FROM kb_regulation_parsed
            WHERE session_id = %s AND (%s IS NULL OR tax_type = %s)
        """, (session_id, tax_type, tax_type))
        total = cur.fetchone()[0]
    return {"items": [dict(zip([c.name for c in cur.description], r)) for r in rows], "total": total}
```

**Note on sorting:** Use `regexp_replace(...::int)` to sort numerically, not lexicographically (so Art2 < Art10, not Art10 < Art2).

#### Add "Tag Syllabus" button to Regulations tab toolbar

```jsx
{/* In the Regulations tab toolbar, next to [Parse] button */}
<button
  onClick={handleTagSyllabus}
  disabled={tagLoading || regulationItems.length === 0}
  className="px-3 py-1.5 text-sm bg-purple-600 hover:bg-purple-700 text-white rounded disabled:opacity-50"
>
  {tagLoading ? 'Tagging...' : `🏷 Tag Syllabus (${untaggedCount} untagged)`}
</button>
```

```javascript
const handleTagSyllabus = async () => {
  setTagLoading(true)
  const res = await api.tagSyllabus(activeSessionId, activeTaxType)
  setTagLoading(false)
  if (res.tagged > 0) {
    toast.success(`Tagged ${res.tagged}/${res.total_items} items`)
    fetchRegulationItems()  // refresh to show updated syllabus_codes
  } else {
    toast.info('No untagged items found')
  }
}

const untaggedCount = regulationItems.filter(i => !i.syllabus_codes || i.syllabus_codes.length === 0).length
```

Add to `api.js`:
```javascript
tagSyllabus: async (sessionId, taxType = null) => {
  const res = await fetch('/api/kb/regulations/tag-syllabus', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ session_id: sessionId, tax_type: taxType })
  })
  return res.json()
},
```

---

## SUMMARY — Files to Create/Modify

| Action | File | Change |
|--------|------|--------|
| CREATE | `backend/utils/rule_parser.py` | Rule-based parser (Part 3.1) |
| MODIFY | `backend/routes/kb.py` | Update `parse-doc` → rule-based; add `DELETE /syllabus/bulk`; add `DELETE /regulation-parsed/bulk`; add `POST /regulations/tag-syllabus`; fix `GET /regulation-parsed` pagination + sort |
| MODIFY | `frontend/src/pages/KnowledgeBase.jsx` | Checkbox + bulk delete; "Tag Syllabus" button; fix pagination display; re-parse warning |
| MODIFY | `frontend/src/api.js` | Add `bulkDeleteKBItems`, `tagSyllabus` |

---

## NOTES FOR CLAUDE CODE

1. **Rule-based parser takes priority** over AI parser for `.docx`/`.doc`/`.txt` files — AI parser is removed from this code path
2. **AI tagging is separate** (button-triggered), not auto-run during parse — keeps parse fast
3. **Sorting:** Use numeric sort on article/clause numbers, not lexicographic — Art2 must come before Art10
4. **Pagination:** Default `limit=1000` (not 100) — 754 items must all show. Add "Showing X of Y" counter in UI
5. **Checkbox column width**: `w-8`, centered
6. **Select-all state**: 3 states — none / some (indeterminate) / all
7. **Bulk delete confirmation**: `window.confirm()` — no custom modal
8. **Re-parse default = clear first**: Idempotent, no user prompt
9. **`replace=True` default** for syllabus bulk-insert: always replace old data
10. **Trash icon**: use inline SVG (Part 1.5), don't add icon library
11. **Bulk action bar**: sticky top, only visible when `selectedIds.size > 0`
12. **`call_ai` helper**: reuse existing `backend/utils/ai_client.py` — do NOT call external APIs directly
13. **`python-docx` dependency**: should already be in requirements.txt; if not, add it
