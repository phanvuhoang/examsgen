MCQ_SYSTEM = "You are a senior ACCA TX(VNM) examiner with deep expertise in Vietnamese taxation law."

MCQ_PROMPT = """Generate {count} MCQ question(s) on {sac_thue} for the {exam_session} exam.

REQUIREMENTS:
- Each MCQ = 2 marks
- 4 options A/B/C/D, one correct marked with "is_key": true
- Scenario-based with specific VND amounts
- Requires multi-step calculation (not just recall)
- Distractors = specific, plausible student mistakes (wrong rate / wrong time apportionment / wrong base)
- Each option must include: text, calculation working, explanation citing specific article/decree

TAX RATES:
{tax_rates}

SYLLABUS SCOPE:
{syllabus}

REGULATIONS:
{regulations}

SAMPLE FORMAT (follow EXACTLY):
{sample}

{topics_instruction}

Return ONLY valid JSON in this exact format:
{{
  "type": "MCQ",
  "sac_thue": "{sac_thue}",
  "exam_session": "{exam_session}",
  "questions": [
    {{
      "number": 1,
      "marks": 2,
      "scenario": "On 1 January 2026, ...",
      "question": "What is...?",
      "options": {{
        "A": {{"text": "VND X", "calculation": "...", "explanation": "...", "is_key": false}},
        "B": {{"text": "VND Y", "calculation": "...", "explanation": "...", "is_key": true}},
        "C": {{"text": "VND Z", "calculation": "...", "explanation": "...", "is_key": false}},
        "D": {{"text": "VND W", "calculation": "...", "explanation": "...", "is_key": false}}
      }},
      "regulation_refs": ["Article X, Law Y"]
    }}
  ]
}}

Generate {count} NEW MCQs. Different scenarios, different companies."""

SCENARIO_SYSTEM = "You are a senior ACCA TX(VNM) examiner. Generate exam-standard scenario questions."

SCENARIO_PROMPT = """Generate Question {question_number} — a {marks}-mark scenario question on {sac_thue} for the {exam_session} exam.

STRUCTURE:
- One integrated business scenario (Vietnamese company/individual)
- Sub-questions labelled (a), (b), (c)...
- Marks per sub-question shown in brackets, summing to exactly {marks}
- Each sub-question tests a DIFFERENT aspect of {sac_thue}
- Include full marking scheme at the end

{industry_instruction}

TAX RATES:
{tax_rates}

SYLLABUS SCOPE:
{syllabus}

REGULATIONS:
{regulations}

SAMPLE FORMAT:
{sample}

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

STRUCTURE:
- Complex integrated business scenario with MULTIPLE tax issues
- 5-6 sub-questions labelled (a), (b), (c), (d), (e), (f)
- Marks per sub-question shown in brackets, summing to exactly {marks}
- Mix of CALCULATION and WRITTEN EXPLANATION sub-questions
- Each sub-question tests a DIFFERENT aspect of {sac_thue}
- Include detailed marking scheme showing each individual mark

TAX RATES:
{tax_rates}

SYLLABUS SCOPE:
{syllabus}

REGULATIONS:
{regulations}

SAMPLE FORMAT:
{sample}

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
