# BRIEF: Remove Legacy KB Targeting from Generate Page

## Context
The "Knowledge Base Targeting" section in the Generate page is legacy code (from old `kb_syllabus`, `kb_regulation`, `kb_sample` CRUD via `KBMultiSelect` component). This is being replaced by the new Reference Materials system in `BRIEF-v2-major-redesign.md`.

## What to Remove

In `frontend/src/pages/Generate.jsx`, **remove** the entire "Knowledge Base Targeting" sub-section inside Custom Instructions. Specifically:

1. Remove the section with label "Knowledge Base Targeting" (the `<div>` containing `KBMultiSelect` components for syllabus, regulations, and style references)
2. Remove related state variables:
   - `kbSyllabusIds` / `setKbSyllabusIds`
   - `kbRegulationIds` / `setKbRegulationIds`  
   - `kbSampleIds` / `setKbSampleIds`
3. Remove `KBMultiSelect` import if it's only used in this section
4. Remove `kb_syllabus_ids`, `kb_regulation_ids`, `kb_sample_ids` from all 3 generate API calls (mcq/scenario/longform)

## What to Keep

- The Custom Instructions section itself (✏️ Custom Instructions) — keep it
- The "Base on existing question" dropdown (reference_question_id) — keep it  
- The "Paste sample or describe" textarea (custom_instructions) — keep it
- The Refine chat section — keep it

## Notes

- `KBMultiSelect` component file can be deleted if no longer used elsewhere
- The new Reference Materials pickers will be added in a separate brief (BRIEF-v2-major-redesign.md)
- Backend endpoints for old `/api/kb/syllabus`, `/api/kb/regulations`, `/api/kb/samples` can stay for now (they'll be updated in v2)
