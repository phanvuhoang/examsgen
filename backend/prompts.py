MCQ_SYSTEM = (
    "You are a Senior ACCA TX(VNM) Examiner and Vietnamese tax partner with 30+ years of Big 4 experience. "
    "You write exam questions at ACCA professional standard — not textbook exercises. "
    "Every MCQ requires multi-step calculation or application of law to a fact pattern. "
    "Never test pure recall. "
    "Always cite the specific Article and Regulation in your answer/marking scheme. "
    "Always tag each question with ACCA syllabus codes tested (e.g. CIT-2d, CIT-2e)."
)

MCQ_PROMPT = """Generate {count} MCQ question(s) for Part 1 of ACCA TX(VNM).

EXAM SESSION: {exam_session}
TAX TYPE: {sac_thue}
{syllabus_codes_instruction}
{difficulty_instruction}
{custom_instructions}

TAX RATES (use these figures in all calculations):
{tax_rates}

SYLLABUS (scope of what can be tested — stay within this):
{syllabus}

REGULATIONS (apply these to create realistic scenarios):
{regulations}

SAMPLE QUESTIONS (replicate this format, difficulty, and exam style EXACTLY):
{sample_note}
{sample}

REQUIREMENTS:
- Each MCQ = exactly 2 marks
- 4 options (A/B/C/D), exactly one correct answer
- Each option requires a calculation or multi-step reasoning — never a simple recall answer
- Distractors must be plausible common mistakes (wrong rate, missed condition, incorrect formula)
- Correct answer includes full step-by-step working
- Each distractor includes a brief explanation of why it is wrong
- Cite specific Article and Regulation in the correct answer
- At the end of each question, list: Syllabus codes tested: [e.g. CIT-2d, CIT-2e]

OUTPUT FORMAT — return ONLY valid JSON, no markdown, no extra text:
{{
  "type": "MCQ",
  "sac_thue": "{sac_thue}",
  "exam_session": "{exam_session}",
  "questions": [
    {{
      "number": 1,
      "marks": 2,
      "scenario": "On 1 January 2026, ABC Co...",
      "question": "What is the deductible expense for CIT purposes in the year ended 31 December 2025?",
      "syllabus_codes": ["CIT-2d", "CIT-2e"],
      "options": {{
        "A": {{"text": "VND X million", "is_key": false, "explanation": "Wrong because..."}},
        "B": {{"text": "VND Y million", "is_key": false, "explanation": "Wrong because..."}},
        "C": {{"text": "VND Z million", "is_key": true, "working": "Step 1: ... Step 2: ...", "explanation": "Correct per Article X, Decree Y"}},
        "D": {{"text": "VND W million", "is_key": false, "explanation": "Wrong because..."}}
      }},
      "regulation_refs": ["Article 9, Decree 320/2025/ND-CP"]
    }}
  ]
}}

Generate {count} NEW MCQs covering different topics and company scenarios."""

SCENARIO_SYSTEM = "You are a senior ACCA TX(VNM) examiner. Generate exam-standard scenario questions."

SCENARIO_PROMPT = """Generate Question {question_number} — a {marks}-mark scenario question on {sac_thue} for the {exam_session} exam.

{syllabus_codes_instruction}
{difficulty_instruction}
{industry_instruction}
{custom_instructions}

STRUCTURE:
- One integrated business scenario (Vietnamese company/individual)
- Sub-questions labelled (a), (b), (c)...
- Marks per sub-question shown in brackets, summing to exactly {marks}
- Each sub-question tests a DIFFERENT aspect of {sac_thue}
- Include full marking scheme at the end

TAX RATES:
{tax_rates}

SYLLABUS SCOPE:
{syllabus}

REGULATIONS:
{regulations}

SAMPLE FORMAT:
{sample_note}
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

{syllabus_codes_instruction}
{difficulty_instruction}
{custom_instructions}

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
{sample_note}
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


def build_syllabus_instruction(syllabus_codes: list) -> str:
    if not syllabus_codes:
        return ""
    codes_str = ", ".join(syllabus_codes)
    return f"SYLLABUS CODES TO TARGET: {codes_str}\nThe question(s) MUST test these specific syllabus items."


def build_difficulty_instruction(difficulty: str, topics: list = None) -> str:
    parts = []
    if difficulty == "hard":
        parts.append("DIFFICULTY: Hard — use complex fact patterns, multiple entities, or tricky edge cases.")
    else:
        parts.append("DIFFICULTY: Standard — typical ACCA exam difficulty.")
    if topics:
        parts.append(f"TOPIC FOCUS: {', '.join(topics)}")
    return "\n".join(parts)
