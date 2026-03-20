MCQ_SYSTEM = "You are a senior ACCA TX(VNM) examiner with deep expertise in Vietnamese taxation law."

MCQ_PROMPT = """Generate {count} MCQ question(s) on {sac_thue} for the {exam_session} exam.

{session_context}

REQUIREMENTS:
- Each MCQ = 2 marks
- 4 options A/B/C/D, one correct marked with "is_key": true
- Scenario-based with specific VND amounts
- Requires multi-step calculation (not just recall)
- Distractors = specific, plausible student mistakes
- Keep calculation and explanation CONCISE (max 1-2 sentences each)

{kb_context}

TAX RATES:
{tax_rates}

SYLLABUS SCOPE:
{syllabus}

REGULATIONS:
{regulations}

{topics_instruction}

{custom_instructions}

Return ONLY valid JSON, no markdown, no extra text:
{{
  "type": "MCQ",
  "sac_thue": "{sac_thue}",
  "exam_session": "{exam_session}",
  "questions": [
    {{
      "number": 1,
      "marks": 2,
      "scenario": "Brief scenario max 3 sentences.",
      "question": "What is...?",
      "options": {{
        "A": {{"text": "VND X million", "calculation": "formula = result", "explanation": "Wrong because...", "is_key": false}},
        "B": {{"text": "VND Y million", "calculation": "formula = result", "explanation": "Correct per Article X.", "is_key": true}},
        "C": {{"text": "VND Z million", "calculation": "formula = result", "explanation": "Wrong because...", "is_key": false}},
        "D": {{"text": "VND W million", "calculation": "formula = result", "explanation": "Wrong because...", "is_key": false}}
      }},
      "regulation_refs": ["Article X, Decree Y"]
    }}
  ]
}}

Generate {count} NEW MCQs covering different topics and company scenarios."""

SCENARIO_SYSTEM = "You are a senior ACCA TX(VNM) examiner. Generate exam-standard scenario questions."

SCENARIO_PROMPT = """Generate Question {question_number} — a {marks}-mark scenario question on {sac_thue} for the {exam_session} exam.

{session_context}

STRUCTURE:
- One integrated business scenario (Vietnamese company/individual)
- Sub-questions labelled (a), (b), (c)...
- Marks per sub-question shown in brackets, summing to exactly {marks}
- Each sub-question tests a DIFFERENT aspect of {sac_thue}
- Include full marking scheme at the end

{industry_instruction}

{kb_context}

TAX RATES:
{tax_rates}

SYLLABUS SCOPE:
{syllabus}

REGULATIONS:
{regulations}

SAMPLE FORMAT:
{sample}

{custom_instructions}

Return ONLY valid JSON in this exact format:
{{
  "type": "{question_type}",
  "question_number": "{question_number}",
  "sac_thue": "{sac_thue}",
  "marks": {marks},
  "exam_session": "{exam_session}",
  "scenario": "You should assume today is 1 February 2026. ...",
  "sub_questions": [
    {{
      "label": "(a)",
      "marks": 3,
      "question": "Calculate...",
      "answer": "Step 1: ...",
      "marking_scheme": [
        {{"point": "Identify...", "mark": 1}},
        {{"point": "Apply...", "mark": 1}},
        {{"point": "Correct total", "mark": 1}}
      ]
    }}
  ],
  "regulation_refs": ["Article X, Law Y"]
}}

Make it CHALLENGING — students must APPLY regulations, not just recall."""

LONGFORM_SYSTEM = SCENARIO_SYSTEM

LONGFORM_PROMPT = """Generate Question {question_number} — a {marks}-mark long-form scenario question on {sac_thue} for the {exam_session} exam.

{session_context}

STRUCTURE:
- Complex integrated business scenario with MULTIPLE tax issues
- 5-6 sub-questions labelled (a), (b), (c), (d), (e), (f)
- Marks per sub-question shown in brackets, summing to exactly {marks}
- Mix of CALCULATION and WRITTEN EXPLANATION sub-questions
- Each sub-question tests a DIFFERENT aspect of {sac_thue}
- Include detailed marking scheme showing each individual mark

{kb_context}

TAX RATES:
{tax_rates}

SYLLABUS SCOPE:
{syllabus}

REGULATIONS:
{regulations}

SAMPLE FORMAT:
{sample}

{custom_instructions}

Return ONLY valid JSON in this exact format:
{{
  "type": "LONGFORM_15",
  "question_number": "{question_number}",
  "sac_thue": "{sac_thue}",
  "marks": {marks},
  "exam_session": "{exam_session}",
  "scenario": "You should assume today is 1 February 2026. ...",
  "sub_questions": [
    {{
      "label": "(a)",
      "marks": 3,
      "question": "Calculate...",
      "answer": "Step 1: ...",
      "marking_scheme": [
        {{"point": "Identify...", "mark": 1}},
        {{"point": "Apply...", "mark": 1}},
        {{"point": "Correct total", "mark": 1}}
      ]
    }}
  ],
  "regulation_refs": ["Article X, Law Y"]
}}

Make it COMPLEX — multiple interrelated issues requiring deep understanding of {sac_thue} regulations."""
