# BRIEF: UX Improvements — Assumed Date, Cutoff Date Picker, Syllabus Tags, Default Model, Topics/Industry, Collapsible Sidebar

**Date:** 2026-03-25  
**Priority:** HIGH  
**Stable base commit:** `340fac3` (format + cutoff date fix — already deployed and working)

---

## Overview — 6 fixes

1. **Assumed Date** → move from Session setting to per-question option in Generate tab
2. **Cut-off Date** → proper date picker with smart default logic
3. **Syllabus codes** → add to Scenario & Long-form question display (already in MCQ)
4. **Default AI model** → change to Anthropic / claude-haiku-4.5
5. **Topics / Industry** → add to ALL question types (MCQ, Scenario, Long-form)
6. **Collapsible sidebar** → toggle icon-only mode; remove session selector from sidebar header

---

## Fix 1: Assumed Date — Per-Question Option in Generate Tab

### Problem
`assumed_date` is currently a Session-level field, but only some questions need it (scenario/long-form). It shouldn't be mandatory for every question in a session.

### Changes

#### `backend/routes/sessions.py` + `backend/context_builder.py`
- Keep `assumed_date` in Session as optional fallback (don't remove it)
- But do NOT auto-inject `assumed_date` into every prompt as a TIMELINE RULE
- Only inject `assumed_date` into the prompt when it is explicitly passed per-request (see generate.py below)

#### `backend/routes/generate.py`
- All three generate endpoints (MCQ, Scenario, Longform) accept a new optional field: `assumed_date: Optional[str] = None`
- If provided, pass it to the prompt builder; if not provided, use empty string (no assumption line)

#### `backend/prompts.py`
- In TIMELINE RULES block of all 3 prompts, change assumed_date line:
  - If `assumed_date` is non-empty → include: `- Opening line of scenario: "You should assume today is {assumed_date}."`
  - If `assumed_date` is empty → remove that instruction entirely (don't force AI to invent a date)
- In the JSON output example schema for SCENARIO and LONGFORM:
  - Change `"scenario": "You should assume today is {assumed_date}..."` to be conditional:
    - If `assumed_date` non-empty → keep the instruction
    - If empty → `"scenario": "ABC Co is a manufacturing company in Vietnam..."`
- Implementation: In `context_builder.py` or `routes/generate.py`, build a `timeline_block` string conditionally:
  ```python
  def build_timeline_block(cutoff_date, tax_year, assumed_date):
      lines = ["TIMELINE RULES:"]
      if tax_year:
          lines.append(f"- All scenarios and transactions occur in tax year {tax_year}")
      if cutoff_date:
          lines.append(f"- Apply regulations effective as of {cutoff_date}")
      if assumed_date:
          lines.append(f'- Opening line of scenario: "You should assume today is {assumed_date}."')
      else:
          lines.append("- Do NOT include an 'assumed today is' line in the scenario")
      return "\n".join(lines)
  ```
  Then replace `{timeline_rules}` placeholder in prompts.

#### `frontend/src/pages/Generate.jsx`
- **Remove** the "Assumed today:" span from the info badge (it's moving to per-question)
- **Add** an optional "Assumed Date" control in the Configure section (Step 2), applicable for ALL question types:
  ```
  [ ] Include "Assume today is..." line
      [text input: e.g. 1 February 2026]
  ```
  - Checkbox: `useAssumedDate` (default: unchecked)
  - Text input: `assumedDateText` (default: empty, but pre-fill with session's `assumed_date` if set)
  - When unchecked: send `assumed_date: null` in API call
  - When checked + text filled: send `assumed_date: assumedDateText`
  - Place this control in the config grid, spanning full width, below other fields

---

## Fix 2: Cut-off Date → Proper Date Picker with Smart Default

### Problem
`cutoff_date` is currently a free-text `VARCHAR(50)` field. The examiner wants a date picker. Default should be auto-computed:
- June 2026 exam → default cutoff = 31 December 2025
- December 2026 exam → default cutoff = 31 December 2025
- June 2027 exam → default cutoff = 31 December 2026
- December 2027 exam → default cutoff = 31 December 2026

Logic: cutoff = 31 December of (exam year − 1)

### Changes

#### Database
```sql
ALTER TABLE exam_sessions ADD COLUMN cutoff_date_v2 DATE;
-- After data migration, rename or keep both
```
Actually: **keep `cutoff_date` as VARCHAR(50) in DB** for flexibility (different exam bodies use different cutoff formats). We'll store it as a formatted string like `"31 December 2025"` but derive it from a date picker in the UI.

#### `frontend/src/pages/Sessions.jsx`

Replace the `cutoff_date` free-text input with:
1. A `<input type="date">` date picker field
2. Auto-compute default when Session Name changes:
   - Parse the session name for a year (e.g. "June 2026" → year = 2026, "Dec 2026" → year = 2026)
   - Default cutoff_date = `${year - 1}-12-31` (date input format)
   - Allow manual override
3. Display format: store as `YYYY-MM-DD` in state, send to backend as formatted string `"31 December 2025"` (or keep as ISO date — backend just passes it to prompt as-is)

**Implementation detail:**
```jsx
// When name changes, auto-derive cutoff
const deriveCutoff = (name) => {
  const yearMatch = name.match(/(20\d{2})/)
  if (!yearMatch) return ''
  const year = parseInt(yearMatch[1])
  return `${year - 1}-12-31`  // ISO format for <input type="date">
}

// In name onChange:
const newName = e.target.value
setForm(prev => ({
  ...prev,
  name: newName,
  // Only auto-set if cutoff not manually changed yet
  cutoff_date: prev._cutoffManuallySet ? prev.cutoff_date : deriveCutoff(newName)
}))
```

Add a `_cutoffManuallySet` flag: once user manually edits the cutoff date picker, stop auto-computing.

**Display in session card:**
```
Cut-off: 31 Dec 2025  (next to exam_date)
```

#### `backend/routes/sessions.py`
- Accept `cutoff_date` as a date string (ISO `YYYY-MM-DD` or formatted) — no change needed since it's still VARCHAR
- Format it nicely for display: if backend receives `2025-12-31`, store as `"31 December 2025"` for prompt readability
  ```python
  from datetime import datetime
  def format_cutoff(date_str: str) -> str:
      try:
          d = datetime.strptime(date_str, '%Y-%m-%d')
          return d.strftime('%-d %B %Y')  # "31 December 2025"
      except:
          return date_str  # fallback: store as-is
  ```

---

## Fix 3: Syllabus Codes in Scenario & Long-form Display

### Problem
MCQ questions show syllabus code tags (green badges) after generation. Scenario and Long-form questions do NOT show syllabus codes even though the prompt asks for them.

### Root cause
The Scenario/Longform JSON schema does not include a top-level `syllabus_codes` field — only individual `sub_question` marking scheme lines have "Syllabus items tested" text inside the answer string.

### Changes

#### `backend/prompts.py` — SCENARIO_PROMPT and LONGFORM_PROMPT

Add `"syllabus_codes"` to the top-level JSON output schema:
```json
{
  "type": "SCENARIO_10",
  "question_number": "Q1",
  "sac_thue": "CIT",
  "marks": 10,
  "exam_session": "...",
  "syllabus_codes": ["CIT-2d", "CIT-3a"],   ← ADD THIS
  "scenario": "...",
  "sub_questions": [...]
}
```

Also add instruction:
```
- At the top level, include "syllabus_codes": [list of ALL unique syllabus codes tested across all sub-questions]
```

#### `backend/routes/questions.py` (or wherever questions are saved)
- When saving a Scenario/Longform question, extract `syllabus_codes` from the parsed JSON and store it in the DB `syllabus_codes` column (same as MCQ)

#### `backend/html_renderer.py` — `_render_scenario()`
After the regulation refs block, the existing code already renders syllabus codes if `content.get("syllabus_codes")` exists. 

**Verify:** Check that `_render_scenario()` does render syllabus codes tags. If it does, the fix is only in the prompt + DB save. If not, add the same rendering block as in `_render_mcq()`.

Current code in `_render_scenario()`:
```python
syllabus_codes = content.get("syllabus_codes", [])
if syllabus_codes:
    # already renders green badges
```
✓ Renderer is fine — just need prompt to include the field and DB save to capture it.

---

## Fix 4: Default AI Model → Anthropic Haiku 4.5

### Problem
Current default is `provider='anthropic'` and `modelTier='fast'` (= Sonnet 4.5). Change default to Haiku.

### Changes

#### `frontend/src/pages/Generate.jsx`
```jsx
// Change:
const [modelTier, setModelTier] = useState('fast')
const [provider, setProvider] = useState('anthropic')

// To:
const [modelTier, setModelTier] = useState('haiku')
const [provider, setProvider] = useState('anthropic')
```

Also update the dropdown so Haiku is visually marked as ⭐ Default (remove ⭐ from Sonnet):
```jsx
<option value="anthropic|haiku">Anthropic — Haiku 4.5 ⭐ Default (nhanh/rẻ)</option>
<option value="anthropic|fast">Anthropic — Sonnet 4.6</option>
```

---

## Fix 5: Topics / Industry in ALL Question Types

### Problem
- MCQ has "Topics" input ✓
- Scenario has "Industry" input ✓  
- Long-form has NEITHER ✗
- Each question type has its own separate fields

### Solution
Replace separate Topics and Industry fields with ONE shared **"Topics / Industry"** text field, visible for ALL question types (MCQ, Scenario, Long-form). Make it wider (full-width or col-span-2).

### Changes

#### `frontend/src/pages/Generate.jsx`

1. **Remove** the separate `topics` state and `industry` state — replace with one shared `topicsIndustry` state
2. **Remove** the Topics input from MCQ section and Industry input from Scenario section
3. **Add** a shared Topics / Industry field in the COMMON fields area (after AI Model selector, before Syllabus Codes), spanning full width:
   ```jsx
   <div className="col-span-2">
     <label className="block text-sm font-medium mb-1">
       Topics / Industry <span className="text-gray-400 font-normal">(optional, comma-separated)</span>
     </label>
     <input
       value={topicsIndustry}
       onChange={(e) => setTopicsIndustry(e.target.value)}
       placeholder="e.g. depreciation, loss carry-forward, manufacturing, real estate"
       className="w-full border rounded-lg px-3 py-2"
     />
     <p className="text-xs text-gray-400 mt-1">
       Topics to focus on, and/or company industry for the scenario
     </p>
   </div>
   ```
4. In `handleGenerate()`:
   - Parse `topicsIndustry` by comma: `const items = topicsIndustry.split(',').map(s => s.trim()).filter(Boolean)`
   - Pass `topics: items` for MCQ
   - Pass `scenario_industry: topicsIndustry` for Scenario (pass the raw string)
   - Pass `topics: items` for Longform (need to add topics support to longform prompt too)

#### `backend/routes/generate.py` — Longform endpoint
- Add `topics: Optional[List[str]] = None` to LongformRequest model
- Pass to prompt builder → `difficulty_instruction` already handles topics via `build_difficulty_instruction(difficulty, topics)`

---

## Fix 6: Collapsible Sidebar + Remove Session Selector from Header

### Problem
- Sidebar is always full-width (w-60), taking up screen space
- Session selector dropdown in sidebar header is redundant (Sessions page has "Set Active" button)

### Changes

#### `frontend/src/components/Layout.jsx`

1. **Add collapsed state:**
   ```jsx
   const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
   ```

2. **Remove** the session `<select>` from the sidebar header entirely

3. **Sidebar in expanded mode** (current behavior, width w-60):
   - Show logo, nav labels, toggle button (hamburger ☰) at top-right of sidebar

4. **Sidebar in collapsed mode** (width w-14):
   - Show only icons, no text labels
   - Each nav icon has a **tooltip** on hover (show label in a small floating div)
   - Toggle button (→ arrow or ☰) to re-expand

5. **Toggle button placement:** Top of sidebar, either:
   - Small button `≡` at top-right corner of sidebar, or
   - A button just below the logo area

6. **Implementation:**
   ```jsx
   <aside className={`${sidebarCollapsed ? 'w-14' : 'w-60'} bg-brand-500 text-white flex flex-col shrink-0 transition-all duration-200`}>
     {/* Header */}
     <div className="p-3 border-b border-brand-400 flex items-center justify-between">
       {!sidebarCollapsed && (
         <div>
           <h1 className="text-xl font-bold">ExamsGen</h1>
           <p className="text-brand-200 text-xs">ACCA TX(VNM)</p>
         </div>
       )}
       <button
         onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
         className="p-1.5 rounded hover:bg-brand-400 transition-colors ml-auto"
         title={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
       >
         <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
           <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
             d={sidebarCollapsed ? 'M13 5l7 7-7 7M5 5l7 7-7 7' : 'M4 6h16M4 12h16M4 18h16'} />
         </svg>
       </button>
     </div>

     {/* Nav */}
     <nav className="flex-1 p-2 space-y-1">
       {NAV_ITEMS.map(({ path, label, icon }) => (
         <NavLink key={path} to={path} end={path === '/'}
           className={({ isActive }) => `relative flex items-center gap-3 px-2 py-2.5 rounded-lg text-sm transition-colors group
             ${isActive ? 'bg-brand-600 text-white font-medium' : 'text-brand-100 hover:bg-brand-400'}`}
         >
           <svg className="w-5 h-5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
             <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d={icon} />
           </svg>
           {/* Label — hidden when collapsed */}
           {!sidebarCollapsed && <span>{label}</span>}
           {/* Tooltip — only when collapsed */}
           {sidebarCollapsed && (
             <span className="absolute left-full ml-2 px-2 py-1 bg-gray-900 text-white text-xs rounded
               opacity-0 group-hover:opacity-100 pointer-events-none whitespace-nowrap z-50 transition-opacity">
               {label}
             </span>
           )}
         </NavLink>
       ))}
     </nav>

     <div className="p-2 border-t border-brand-400">
       <button onClick={onLogout}
         className={`w-full text-left px-2 py-2 text-brand-200 hover:text-white text-sm rounded hover:bg-brand-400 transition-colors flex items-center gap-3`}>
         <svg className="w-5 h-5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
           <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
         </svg>
         {!sidebarCollapsed && 'Logout'}
       </button>
     </div>
   </aside>
   ```

7. **Generate.jsx** — Remove the session selector dropdown at top of Generate page (the one that reads sessions and lets you pick). The active session is now managed exclusively from the Sessions page. Instead, just show the active session name as a read-only badge:
   ```jsx
   {currentSession && (
     <div className="flex items-center gap-2 bg-gray-50 rounded-lg px-4 py-2 mb-5 border text-sm text-gray-600">
       <span>📋 Active session:</span>
       <strong>{currentSession.name}</strong>
       {currentSession.exam_date && <span className="text-gray-400">({currentSession.exam_date})</span>}
       <a href="/sessions" className="ml-auto text-xs text-brand-600 hover:underline">Change →</a>
     </div>
   )}
   ```

---

## Summary of Files to Change

| File | Changes |
|------|---------|
| `frontend/src/components/Layout.jsx` | (6) Collapsible sidebar, tooltips, remove session selector |
| `frontend/src/pages/Generate.jsx` | (1) Assumed date checkbox+input; (4) default model haiku; (5) shared Topics/Industry; (6) remove session dropdown → read-only badge |
| `frontend/src/pages/Sessions.jsx` | (2) cutoff_date → `<input type="date">` with auto-default from session name |
| `backend/routes/sessions.py` | (2) format_cutoff() to store "31 December 2025" from ISO input |
| `backend/routes/generate.py` | (1) add `assumed_date` param to all 3 endpoints; (5) add `topics` to longform |
| `backend/prompts.py` | (1) conditional assumed_date in TIMELINE RULES; (3) add `syllabus_codes` to scenario/longform JSON schema + instruction |
| `backend/context_builder.py` | (1) build_timeline_block() conditional assumed_date injection |
| `backend/routes/questions.py` | (3) save `syllabus_codes` from scenario/longform JSON to DB |

---

## Testing Checklist

- [ ] Generate MCQ → Haiku 4.5 selected by default ✓
- [ ] Generate Scenario → Topics/Industry field visible and works ✓
- [ ] Generate Long-form → Topics/Industry field visible ✓
- [ ] Generate with no "Assumed date" checked → no "You should assume today is..." in question ✓
- [ ] Generate with "Assumed date" checked + "1 February 2026" → scenario starts with that line ✓
- [ ] Session form: type "June 2026" → cutoff_date auto-fills to 2025-12-31 ✓
- [ ] Session form: type "December 2027" → cutoff_date auto-fills to 2026-12-31 ✓
- [ ] Manually change cutoff date → stays at manual value even if name changes ✓
- [ ] Generate Scenario → syllabus code badges appear after generation ✓
- [ ] Generate Long-form → syllabus code badges appear after generation ✓
- [ ] Sidebar collapse button → sidebar shrinks to icons only ✓
- [ ] Hover over icon in collapsed sidebar → tooltip shows label ✓
- [ ] Sidebar expand button → sidebar returns to full width ✓
- [ ] Generate page → no session dropdown (replaced by read-only active session badge) ✓

---

*Brief written by Thanh (AI agent) — 2026-03-25*
