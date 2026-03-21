# BRIEF: KB Regulations — Chunked Parse + Syllabus Suggest + Filters
## Repo: phanvuhoang/examsgen

---

## Problem 1: Parse only returns ~30 items (3 Articles)

Current code truncates input to `text[:20000]` before sending to AI. A full regulation
document like Decree 320 (CIT) has 200+ paragraphs across 20+ articles — 20,000 chars
only covers the first few articles.

**Fix: Chunked parsing** — split document into overlapping chunks by article boundaries,
parse each chunk separately, merge results.

---

## Problem 2: No Syllabus Code suggestions after parsing

After parsing regulation paragraphs, each row has no `syllabus_codes` — user must manually
link them. This should be auto-suggested during parse (same AI call that parses the paragraph
can also match it to syllabus items).

---

## Problem 3: No filter by regulation file or syllabus code in the Regulations tab

When a tax type has multiple uploaded regulation files (Law + Decree + Circular), the parsed
paragraphs list mixes everything together with no way to filter by source document or
syllabus code.

---

## PART 1: Chunked Parsing with Auto Syllabus Matching

### 1.1 Update `POST /api/kb/regulations/parse-doc` in `backend/routes/kb.py`

Replace the current single-pass parse with a chunked approach:

```python
@router.post("/regulations/parse-doc")
def parse_regulation_doc(data: dict):
    session_id = data['session_id']
    tax_type = data['tax_type']
    file_path = data['file_path']
    doc_ref = data.get('doc_ref', '')

    # 1. Clear existing rows for this file (smart re-parse)
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "DELETE FROM kb_regulation_parsed WHERE session_id = %s AND source_file = %s",
            (session_id, file_path)
        )
        cleared = cur.rowcount

    # 2. Extract full text
    full_path = f"/app/data/{file_path}"
    text = extract_text_from_file(full_path)
    if not text or len(text) < 100:
        raise HTTPException(400, "Could not extract text from file")

    # 3. Load syllabus items for matching context
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT COALESCE(syllabus_code, section_code) as code,
                   COALESCE(topic, section_title) as topic,
                   COALESCE(detailed_syllabus, content) as detail
            FROM kb_syllabus
            WHERE session_id = %s AND COALESCE(tax_type, sac_thue) = %s
              AND COALESCE(syllabus_code, section_code) IS NOT NULL
            ORDER BY COALESCE(syllabus_code, section_code)
        """, (session_id, tax_type))
        syllabus_rows = cur.fetchall()

    syllabus_context = ""
    if syllabus_rows:
        syllabus_list = "\n".join(
            f"- [{r[0]}] {r[1]}: {r[2][:80]}" for r in syllabus_rows[:80]
        )
        syllabus_context = f"\n\nAVAILABLE SYLLABUS CODES (match paragraphs to these if relevant):\n{syllabus_list}"

    # 4. Split text into article-based chunks (~8000 chars each, overlap at article boundaries)
    chunks = _split_into_article_chunks(text, max_chars=8000)

    # 5. Parse each chunk
    all_rows = []
    doc_slug = re.sub(r'[^A-Za-z0-9]', '', doc_ref.replace('/', '-').replace(' ', ''))[:20]

    for chunk_idx, chunk_text in enumerate(chunks):
        prompt = f"""Parse this Vietnamese tax regulation document chunk into individual paragraphs.

For each paragraph extract:
- article_no: article number if present (e.g. "Article 12" or "Điều 12"). If this chunk is a continuation, infer from context.
- paragraph_no: sequential number within that article (1, 2, 3...). Reset to 1 for each new article.
- paragraph_text: the complete text of this paragraph (keep original wording, do not summarize)
- tags: 3-6 English keywords
- syllabus_codes: array of matching syllabus codes from the list below (empty array [] if none match well){syllabus_context}

Return ONLY valid JSON array, no markdown:
[
  {{
    "article_no": "Article 9",
    "paragraph_no": 1,
    "paragraph_text": "...",
    "tags": "deductible,expenses,conditions",
    "syllabus_codes": ["B2a", "B2b"]
  }}
]

DOCUMENT TYPE: regulation | TAX TYPE: {tax_type} | SOURCE: {doc_ref} | CHUNK {chunk_idx + 1}/{len(chunks)}

DOCUMENT CHUNK:
{chunk_text}"""

        result = call_ai(prompt, model_tier="fast")
        chunks_parsed = parse_ai_json_list(result['content'])

        # Insert parsed rows
        with get_db() as conn:
            cur = conn.cursor()
            for item in chunks_parsed:
                art = re.sub(r'[^0-9]', '', str(item.get('article_no', '0')))
                p = item.get('paragraph_no', 0)
                reg_code = f"{tax_type}-{doc_slug}-Art{art}-P{p}"

                # Handle duplicate reg_codes within same doc (append chunk index)
                syllabus_codes = item.get('syllabus_codes', [])
                if isinstance(syllabus_codes, str):
                    syllabus_codes = [s.strip() for s in syllabus_codes.split(',') if s.strip()]

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

                all_rows.append({
                    "reg_code": reg_code,
                    "article_no": item.get('article_no'),
                    "paragraph_no": p,
                    "paragraph_text": item.get('paragraph_text', '')[:200],
                    "syllabus_codes": syllabus_codes,
                    "tags": item.get('tags', '')
                })

    return {
        "parsed": len(all_rows),
        "chunks_processed": len(chunks),
        "re_parsed": cleared > 0,
        "cleared": cleared,
        "rows": all_rows
    }


def _split_into_article_chunks(text: str, max_chars: int = 8000) -> list:
    """
    Split regulation text into chunks at article boundaries.
    Each chunk <= max_chars. Tries to split at 'Article N' / 'Điều N' boundaries.
    """
    import re as _re

    # Find article start positions
    article_pattern = _re.compile(
        r'(?:^|\n)\s*(?:Article|Điều|ARTICLE|ĐIỀU)\s+\d+',
        _re.MULTILINE | _re.IGNORECASE
    )
    matches = list(article_pattern.finditer(text))

    if not matches:
        # No article boundaries found — split by char count with overlap
        chunks = []
        step = max_chars - 500  # 500 char overlap
        for i in range(0, len(text), step):
            chunks.append(text[i:i + max_chars])
            if i + max_chars >= len(text):
                break
        return chunks

    # Build chunks by grouping articles until max_chars reached
    chunks = []
    current_chunk_start = 0
    current_chunk_articles = []

    for i, match in enumerate(matches):
        article_start = match.start()
        article_end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        article_text = text[article_start:article_end]

        # If single article > max_chars, split it alone
        if len(article_text) > max_chars:
            if current_chunk_articles:
                chunks.append(text[current_chunk_start:article_start])
                current_chunk_articles = []
                current_chunk_start = article_start
            # Split oversized article by paragraphs
            for j in range(0, len(article_text), max_chars - 200):
                chunks.append(article_text[j:j + max_chars])
            current_chunk_start = article_end
            continue

        # Check if adding this article exceeds max_chars
        current_size = article_start - current_chunk_start
        if current_chunk_articles and current_size + len(article_text) > max_chars:
            # Flush current chunk
            chunks.append(text[current_chunk_start:article_start])
            current_chunk_start = article_start
            current_chunk_articles = []

        current_chunk_articles.append(match.group())

    # Flush remaining
    if current_chunk_start < len(text):
        chunks.append(text[current_chunk_start:])

    return [c for c in chunks if c.strip()]
```

**Add `ON CONFLICT DO NOTHING`** to the INSERT — requires a unique index on `kb_regulation_parsed`:
```sql
CREATE UNIQUE INDEX IF NOT EXISTS idx_kb_reg_parsed_code_session
  ON kb_regulation_parsed(session_id, reg_code);
```
Add this to `backend/database.py` in `init_db()`.

### 1.2 Progress feedback for long parses

For large documents (many chunks), parsing can take 30-60 seconds. Add a **streaming progress endpoint** OR use a simple polling approach:

**Simple approach (recommended):** Return immediately with a job_id, poll for completion.

```python
# In-memory job store (fine for single-instance deployment)
_parse_jobs = {}  # job_id -> {"status": "running"|"done"|"failed", "parsed": N, "total_chunks": N}

@router.post("/regulations/parse-doc-async")
def parse_regulation_doc_async(data: dict, background_tasks: BackgroundTasks):
    import uuid
    job_id = str(uuid.uuid4())[:8]
    _parse_jobs[job_id] = {"status": "running", "parsed": 0, "total_chunks": 0, "rows": []}

    background_tasks.add_task(_run_parse_job, job_id, data)
    return {"job_id": job_id}

@router.get("/regulations/parse-job/{job_id}")
def get_parse_job(job_id: str):
    job = _parse_jobs.get(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return job

def _run_parse_job(job_id: str, data: dict):
    """Background task — runs the chunked parse and updates job status."""
    try:
        # ... same logic as parse_regulation_doc above ...
        # Update _parse_jobs[job_id] after each chunk:
        #   _parse_jobs[job_id]["parsed"] += len(chunk_rows)
        #   _parse_jobs[job_id]["total_chunks"] = len(chunks)
        _parse_jobs[job_id]["status"] = "done"
    except Exception as e:
        _parse_jobs[job_id]["status"] = "failed"
        _parse_jobs[job_id]["error"] = str(e)
```

**Frontend polling:**
```javascript
// After clicking [Parse]:
const { job_id } = await api.parseRegulationDocAsync(data)
setParseStatus({ jobId: job_id, parsed: 0, status: 'running' })

// Poll every 2 seconds
const poll = setInterval(async () => {
  const job = await api.getParseJob(job_id)
  setParseStatus(job)
  if (job.status === 'done' || job.status === 'failed') {
    clearInterval(poll)
    fetchItems()  // refresh the parsed items list
  }
}, 2000)
```

**Progress UI on the [Parse] button:**
```jsx
{parseStatus?.jobId === file.id && (
  <span className="text-xs text-gray-500 ml-2">
    {parseStatus.status === 'running'
      ? `Parsing... ${parseStatus.parsed} paragraphs (chunk ${parseStatus.chunk}/${parseStatus.total_chunks})`
      : parseStatus.status === 'done'
        ? `✓ ${parseStatus.parsed} paragraphs parsed`
        : `✗ Parse failed`
    }
  </span>
)}
```

---

## PART 2: Filter by Regulation File + Syllabus Code

### 2.1 Backend — Update GET /api/kb/regulations/parsed

Add `source_file` and `syllabus_code` filter params:

```python
@router.get("/regulations/parsed")
def list_regulation_parsed(
    session_id: Optional[int] = None,
    tax_type: Optional[str] = None,
    source_file: Optional[str] = None,      # ← NEW: filter by uploaded file
    syllabus_code: Optional[str] = None,     # ← NEW: filter by syllabus code match
    article_no: Optional[str] = None,        # ← NEW: filter by article
    search: Optional[str] = None,
    limit: int = Query(100, le=500),
    offset: int = 0,
):
    with get_db() as conn:
        cur = conn.cursor()
        query = """SELECT id, session_id, tax_type, reg_code, doc_ref, article_no,
                          paragraph_no, paragraph_text, syllabus_codes, tags, source_file
                   FROM kb_regulation_parsed WHERE is_active = TRUE"""
        params = []

        if session_id:
            query += " AND session_id = %s"
            params.append(session_id)
        if tax_type:
            query += " AND tax_type = %s"
            params.append(tax_type)
        if source_file:
            query += " AND source_file = %s"
            params.append(source_file)
        if syllabus_code:
            # Filter paragraphs that have this syllabus code in their array
            query += " AND syllabus_codes @> %s"
            params.append([syllabus_code])
        if article_no:
            query += " AND article_no ILIKE %s"
            params.append(f"%{article_no}%")
        if search:
            query += " AND (reg_code ILIKE %s OR paragraph_text ILIKE %s OR tags ILIKE %s)"
            params += [f"%{search}%", f"%{search}%", f"%{search}%"]

        # Count
        count_q = query.replace(
            "SELECT id, session_id, tax_type, reg_code, doc_ref, article_no,\n                          paragraph_no, paragraph_text, syllabus_codes, tags, source_file",
            "SELECT COUNT(*)"
        )
        cur.execute(count_q, params)
        total = cur.fetchone()[0]

        query += " ORDER BY doc_ref, article_no, paragraph_no LIMIT %s OFFSET %s"
        cur.execute(query, params + [limit, offset])
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description]

    return {"total": total, "items": [dict(zip(cols, r)) for r in rows]}
```

### 2.2 Backend — GET /api/kb/regulations/files (list uploaded files with counts)

```python
@router.get("/regulations/files")
def list_regulation_files(session_id: int, tax_type: Optional[str] = None):
    """Return distinct source files with their paragraph counts."""
    with get_db() as conn:
        cur = conn.cursor()
        query = """
            SELECT source_file, doc_ref, tax_type, COUNT(*) as paragraph_count
            FROM kb_regulation_parsed
            WHERE session_id = %s AND is_active = TRUE
        """
        params = [session_id]
        if tax_type:
            query += " AND tax_type = %s"
            params.append(tax_type)
        query += " GROUP BY source_file, doc_ref, tax_type ORDER BY doc_ref"
        cur.execute(query, params)
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in rows]
```

### 2.3 Frontend — Regulations Tab: Filter Bar

Above the parsed paragraphs table, add a filter bar:

```jsx
{/* Filter bar */}
<div className="flex flex-wrap gap-3 mb-4 items-center">

  {/* Filter by Tax Type — already exists */}
  <select value={taxType} onChange={e => { setTaxType(e.target.value); setRegFileFilter(''); setSyllabusFilter('') }}
    className="border rounded-lg px-3 py-2 text-sm">
    <option value="">All Tax Types</option>
    {taxTypes.map(t => <option key={t.code} value={t.code}>{t.code}</option>)}
  </select>

  {/* Filter by Regulation File — NEW */}
  <select value={regFileFilter} onChange={e => setRegFileFilter(e.target.value)}
    className="border rounded-lg px-3 py-2 text-sm min-w-[200px]">
    <option value="">All Regulation Files</option>
    {regFiles.map(f => (
      <option key={f.source_file} value={f.source_file}>
        {f.doc_ref || f.source_file.split('/').pop()} ({f.paragraph_count} ¶)
      </option>
    ))}
  </select>

  {/* Filter by Syllabus Code — NEW */}
  <div className="relative">
    <input
      value={syllabusFilter}
      onChange={e => setSyllabusFilter(e.target.value)}
      placeholder="Filter by syllabus code..."
      className="border rounded-lg px-3 py-2 text-sm w-48"
    />
    {syllabusFilter && (
      <button onClick={() => setSyllabusFilter('')}
        className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600">✕</button>
    )}
  </div>

  {/* Filter by Article — NEW */}
  <input
    value={articleFilter}
    onChange={e => setArticleFilter(e.target.value)}
    placeholder="Article... e.g. 9"
    className="border rounded-lg px-3 py-2 text-sm w-32"
  />

  {/* Search — existing */}
  <input value={search} onChange={e => setSearch(e.target.value)}
    placeholder="Search text..."
    className="border rounded-lg px-3 py-2 text-sm flex-1 min-w-[150px]" />

  {/* Clear filters */}
  {(regFileFilter || syllabusFilter || articleFilter || search) && (
    <button onClick={() => { setRegFileFilter(''); setSyllabusFilter(''); setArticleFilter(''); setSearch('') }}
      className="text-xs text-gray-500 hover:text-gray-700 underline">
      Clear filters
    </button>
  )}
</div>
```

**New state:**
```javascript
const [regFileFilter, setRegFileFilter] = useState('')
const [syllabusFilter, setSyllabusFilter] = useState('')
const [articleFilter, setArticleFilter] = useState('')
const [regFiles, setRegFiles] = useState([])  // list from /api/kb/regulations/files
```

**Load reg files** when session/taxType changes:
```javascript
useEffect(() => {
  if (!sessionId) return
  const params = { session_id: sessionId }
  if (taxType) params.tax_type = taxType
  api.getRegulationFiles(params).then(setRegFiles).catch(() => setRegFiles([]))
}, [sessionId, taxType])
```

**Pass filters to fetch:**
```javascript
const fetchItems = async () => {
  const params = { session_id: sessionId }
  if (taxType) params.tax_type = taxType
  if (regFileFilter) params.source_file = regFileFilter
  if (syllabusFilter) params.syllabus_code = syllabusFilter
  if (articleFilter) params.article_no = articleFilter
  if (search) params.search = search
  const data = await api.getRegulationsParsed(params)
  setItems(data.items || [])
  setTotal(data.total || 0)
}

useEffect(() => { fetchItems() }, [sessionId, taxType, regFileFilter, syllabusFilter, articleFilter, search])
```

### 2.4 Show Syllabus Codes in Parsed Table

Each row in the regulations table should show its syllabus_codes as small chips:

```jsx
{/* In table row, add a Syllabus Codes column */}
<td className="px-3 py-2">
  <div className="flex flex-wrap gap-1">
    {(item.syllabus_codes || []).map(code => (
      <button key={code}
        onClick={() => setSyllabusFilter(code)}  // click chip to filter by this code
        className="px-1.5 py-0.5 bg-blue-50 text-blue-600 text-xs font-mono rounded border border-blue-100 hover:bg-blue-100 cursor-pointer"
        title="Click to filter by this syllabus code"
      >
        {code}
      </button>
    ))}
    {(!item.syllabus_codes || item.syllabus_codes.length === 0) && (
      <span className="text-gray-300 text-xs">—</span>
    )}
  </div>
</td>
```

Clicking a syllabus code chip → sets `syllabusFilter` to that code → filters the list.

### 2.5 api.js additions

```javascript
getRegulationsParsed: async (params = {}) => {
  const q = new URLSearchParams(params)
  const res = await fetch(`/api/kb/regulations/parsed?${q}`, { headers: authHeaders() })
  return res.ok ? res.json() : { total: 0, items: [] }
},

getRegulationFiles: async (params = {}) => {
  const q = new URLSearchParams(params)
  const res = await fetch(`/api/kb/regulations/files?${q}`, { headers: authHeaders() })
  return res.ok ? res.json() : []
},

parseRegulationDocAsync: async (data) => {
  const res = await fetch(`/api/sessions/${data.session_id}/parse-and-match`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify(data)
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
},

getParseJob: async (jobId) => {
  const res = await fetch(`/api/kb/regulations/parse-job/${jobId}`, { headers: authHeaders() })
  return res.ok ? res.json() : { status: 'failed' }
},
```

---

## SUMMARY — Files to Create/Modify

| Action | File | Change |
|--------|------|--------|
| MODIFY | `backend/routes/kb.py` | Chunked `parse_regulation_doc` with syllabus matching; add async parse job endpoints; add `GET /regulations/files`; add `source_file`+`syllabus_code`+`article_no` filters to `GET /regulations/parsed` |
| MODIFY | `backend/database.py` | Add unique index `idx_kb_reg_parsed_code_session` on `(session_id, reg_code)` in `init_db()` |
| MODIFY | `frontend/src/pages/KnowledgeBase.jsx` | Filter bar (reg file, syllabus code, article); syllabus code chips in table rows (clickable); parse progress polling |
| MODIFY | `frontend/src/api.js` | Add `getRegulationsParsed`, `getRegulationFiles`, `getParseJob`, `parseRegulationDocAsync` |

---

## NOTES FOR CLAUDE CODE

1. **Chunked parse is the main fix** — split by article boundaries, each chunk ~8000 chars. A 200-paragraph decree = ~10-15 chunks = ~10-15 AI calls (fast model, ~2-3s each = 20-40s total). Background task + polling handles this gracefully.

2. **`_parse_jobs` dict** is in-memory — fine for single instance. If container restarts, job is lost, but user can just click Parse again.

3. **Unique index on `(session_id, reg_code)`** — needed for `ON CONFLICT DO NOTHING` during chunked insert. Add in `database.py` `init_db()` using `CREATE UNIQUE INDEX IF NOT EXISTS`.

4. **`parse_ai_json_list`** — must handle cases where AI returns partial JSON or wraps in markdown. Same robust parsing as `parse_ai_json` but for arrays.

5. **syllabus_codes from AI** — AI may return `["B2a", "B2c"]` (array) or `"B2a, B2c"` (string). Handle both: if string, split by comma; if array, use directly.

6. **Clickable syllabus chips** in the table — clicking sets the `syllabusFilter` state, which triggers a re-fetch filtered by that code. This is a nice UX for exploring related paragraphs.

7. **Regulation file dropdown** uses `/api/kb/regulations/files` which returns grouped counts — shows `"Decree 320/2025 (47 ¶)"` so user knows how many paragraphs each file has.

8. **Table columns for Regulations** (update from current): RegCode | Article | Paragraph Text | **Syllabus Codes** | Tags | Actions

9. **Don't break existing parse-and-match** on the sessions route — the new chunked logic replaces the kb.py parse endpoint but the sessions route that calls it should still work.
