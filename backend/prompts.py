MCQ_SYSTEM = (
    "You are a Senior ACCA TX(VNM) Examiner and Vietnamese tax partner with 30+ years of Big 4 experience. "
    "You write exam questions at ACCA professional standard — not textbook exercises. "
    "Every MCQ requires multi-step calculation or application of law to a fact pattern. "
    "Never test pure recall. "
    "Always cite the specific Article and Regulation in your answer/marking scheme. "
    "Always tag each question with ACCA syllabus codes tested (e.g. C2d, C2n)."
)

MCQ_PROMPT = """Generate {count} MCQ question(s) for Part 1 of ACCA TX(VNM).

EXAM SESSION: {exam_session}
TAX TYPE: {sac_thue}
{session_vars}
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

MARK ALLOCATION RULES (CRITICAL):
- Minimum 0.5 mark per answerable point
- A 2-mark MCQ should have EITHER:
  (a) 4 small calculation/identification points × 0.5 marks each, OR
  (b) 2 medium calculation points × 1 mark each, OR
  (c) 1 large calculation point (1 mark) + 2 small points (0.5 marks each)
- DO NOT create a question requiring 6+ calculation steps for only 2 marks
- The scenario MUST be solvable in ≤ 4 calculation steps total
- Keep fact patterns concise — 3-5 data points per MCQ, not 8-10

ANSWER FORMAT RULES:
- Answers must be CONCISE and CLEAR — like official ACCA marking schemes
- Show calculations inline: "Annual salary = 50 mil × 9 months = 450 mil (0.5 marks)"
- When ≥ 3 calculation rows exist, use a markdown table:
  | Item | Calculation | Amount (mil VND) | Marks |
  |------|-------------|-----------------|-------|
  | Annual salary | 50 × 9 | 450 | 0.5 |
- Each row = one mark point. Show mark allocation per row/point (e.g. 0.5 marks, 1 mark)
- DO NOT write verbose paragraphs explaining each step
- DO NOT write "Step 1:", "Step 2:" etc.
- Final answer line should be bolded or clearly marked
- For MCQ wrong options: one short sentence explaining the mistake (e.g. "Wrong rate applied: used 20% instead of 22%")
- Cite regulation reference on a separate line at the end: "Ref: Article X, Decree Y"
- In the correct answer explanation, include a line: "Syllabus items tested: [list codes and topic names, e.g. C2d: Depreciation of fixed assets]" — after the regulation reference
- At the end of each question, list: Syllabus codes tested: [e.g. C2d, C2n]

TIMELINE RULES:
- All scenarios, transactions, and company data occur in tax year {tax_year}
- Apply regulations that were effective as of {cutoff_date}
- Opening line of scenario uses: "You should assume today is {assumed_date}."
- Do NOT reference events in years after {tax_year} unless asking about future obligations

OUTPUT FORMAT — return ONLY valid JSON, no markdown, no extra text:
{{
  "type": "MCQ",
  "sac_thue": "{sac_thue}",
  "exam_session": "{exam_session}",
  "questions": [
    {{
      "number": 1,
      "marks": 2,
      "scenario": "On 1 January {tax_year}, ABC Co...",
      "question": "What is the deductible expense for CIT purposes in the year ended 31 December {tax_year}?",
      "syllabus_codes": ["C2d", "C2n"],
      "options": {{
        "A": {{"text": "VND X million", "is_key": false, "explanation": "Wrong rate applied: used 20% instead of 22%"}},
        "B": {{"text": "VND Y million", "is_key": false, "explanation": "Wrong because..."}},
        "C": {{"text": "VND Z million", "is_key": true, "working": "Annual salary = 50 mil × 9 = 450 mil (0.5 mk)\nLess insurance = 4.5 mil (0.5 mk)\nNet = 445.5 mil (1 mk)", "explanation": "Correct per Article X, Decree Y\nSyllabus items tested: C2d: Depreciation of fixed assets"}},
        "D": {{"text": "VND W million", "is_key": false, "explanation": "Wrong because..."}}
      }},
      "regulation_refs": ["Article 9, Decree 320/2025/ND-CP"]
    }}
  ]
}}

Generate {count} NEW MCQs covering different topics and company scenarios."""

SCENARIO_SYSTEM = "You are a senior ACCA TX(VNM) examiner. Generate exam-standard scenario questions."

SCENARIO_PROMPT = """Generate Question {question_number} — a {marks}-mark scenario question on {sac_thue} for the {exam_session} exam.

{session_vars}
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
- In the marking scheme for each sub-question, include a line: "Syllabus items tested: [list codes and topic names, e.g. C2d: Depreciation of fixed assets]" — after the regulation references

MARK GRANULARITY RULES:
- Minimum 0.5 mark per answerable point
- Each sub-question's mark allocation must match its actual complexity
- Example for a 3-mark sub-question:
  - 3 steps × 1 mark each, OR
  - 2 steps × 1 mark + 2 items × 0.5 mark, OR
  - 6 items × 0.5 mark each
- Do not assign 1 mark to a trivial identification step that takes 5 seconds
- Do not require 10 calculation steps for a 2-mark question

ANSWER FORMAT RULES:
- Answers must be CONCISE and CLEAR — like official ACCA marking schemes
- Show calculations inline: "Annual salary = 50 mil × 9 months = 450 mil (0.5 marks)"
- When ≥ 3 calculation rows exist, use a markdown table:
  | Item | Calculation | Amount (mil VND) | Marks |
  |------|-------------|-----------------|-------|
  | Annual salary | 50 × 9 | 450 | 0.5 |
- Each row = one mark point. Show mark allocation per row/point
- DO NOT write verbose paragraphs explaining each step
- DO NOT write "Step 1:", "Step 2:" etc.
- Final answer line should be bolded or clearly marked
- Cite regulation reference on a separate line at the end: "Ref: Article X, Decree Y"

TIMELINE RULES:
- All scenarios, transactions, and company data occur in tax year {tax_year}
- Apply regulations that were effective as of {cutoff_date}
- Opening line of scenario: "You should assume today is {assumed_date}."
- Do NOT reference events in years after {tax_year} unless asking about future obligations

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
  "scenario": "You should assume today is {assumed_date}. All transactions occur in tax year {tax_year}. ...",
  "sub_questions": [
    {{
      "label": "(a)",
      "marks": 3,
      "question": "Calculate...",
      "answer": "Annual salary = 50 mil × 9 = 450 mil (0.5 mk)\nLess insurance = 4.5 mil (0.5 mk)\nNet = 445.5 mil (1 mk)",
      "marking_scheme": [
        {{"point": "Annual salary = 50 × 9 = 450 mil", "mark": 0.5}},
        {{"point": "Less insurance cap = 4.5 mil", "mark": 0.5}},
        {{"point": "Correct net = 445.5 mil", "mark": 1}}
      ]
    }}
  ],
  "regulation_refs": ["Article X, Law Y"]
}}

Make it CHALLENGING — students must APPLY regulations, not just recall."""

LONGFORM_SYSTEM = SCENARIO_SYSTEM

LONGFORM_PROMPT = """Generate Question {question_number} — a {marks}-mark long-form scenario question on {sac_thue} for the {exam_session} exam.

{session_vars}
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
- In the marking scheme for each sub-question, include a line: "Syllabus items tested: [list codes and topic names, e.g. C2d: Depreciation of fixed assets]" — after the regulation references

MARK GRANULARITY RULES:
- Minimum 0.5 mark per answerable point
- Each sub-question's mark allocation must match its actual complexity
- Do not assign 1 mark to a trivial identification step that takes 5 seconds
- Do not require 10 calculation steps for a 2-mark question

ANSWER FORMAT RULES:
- Answers must be CONCISE and CLEAR — like official ACCA marking schemes
- Show calculations inline: "Annual salary = 50 mil × 9 months = 450 mil (0.5 marks)"
- When ≥ 3 calculation rows exist, use a markdown table:
  | Item | Calculation | Amount (mil VND) | Marks |
  |------|-------------|-----------------|-------|
  | Annual salary | 50 × 9 | 450 | 0.5 |
- Each row = one mark point. Show mark allocation per row/point
- DO NOT write verbose paragraphs explaining each step
- DO NOT write "Step 1:", "Step 2:" etc.
- Final answer line should be bolded or clearly marked
- Cite regulation reference on a separate line at the end: "Ref: Article X, Decree Y"

TIMELINE RULES:
- All scenarios, transactions, and company data occur in tax year {tax_year}
- Apply regulations that were effective as of {cutoff_date}
- Opening line of scenario: "You should assume today is {assumed_date}."
- Do NOT reference events in years after {tax_year} unless asking about future obligations

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
  "scenario": "You should assume today is {assumed_date}. All transactions occur in tax year {tax_year}. ...",
  "sub_questions": [
    {{
      "label": "(a)",
      "marks": 3,
      "question": "Calculate...",
      "answer": "Annual salary = 50 mil × 9 = 450 mil (0.5 mk)\nLess insurance = 4.5 mil (0.5 mk)\nNet = 445.5 mil (1 mk)",
      "marking_scheme": [
        {{"point": "Annual salary = 50 × 9 = 450 mil", "mark": 0.5}},
        {{"point": "Less insurance cap = 4.5 mil", "mark": 0.5}},
        {{"point": "Correct net = 445.5 mil", "mark": 1}}
      ]
    }}
  ],
  "regulation_refs": ["Article X, Law Y"]
}}

Make it COMPLEX — multiple interrelated issues requiring deep understanding of {sac_thue} regulations."""


def build_syllabus_instruction(syllabus_codes: list, codes_from_file: list = None) -> str:
    parts = []
    if codes_from_file:
        parts.append(f"AVAILABLE SYLLABUS CODES (tag questions using EXACTLY these codes): {', '.join(codes_from_file)}")
    if syllabus_codes:
        codes_str = ", ".join(syllabus_codes)
        parts.append(f"SYLLABUS CODES TO TARGET: {codes_str}\nThe question(s) MUST test these specific syllabus items.")
    return "\n".join(parts)


def build_difficulty_instruction(difficulty: str, topics: list = None) -> str:
    parts = []
    if difficulty == "hard":
        parts.append("DIFFICULTY: Hard — use complex fact patterns, multiple entities, or tricky edge cases.")
    else:
        parts.append("DIFFICULTY: Standard — typical ACCA exam difficulty.")
    if topics:
        parts.append(f"TOPIC FOCUS: {', '.join(topics)}")
    return "\n".join(parts)
