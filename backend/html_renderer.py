"""Render question JSON to HTML for preview display."""


def render_question_html(content: dict) -> str:
    q_type = content.get("type", "")
    if q_type == "MCQ":
        return _render_mcq(content)
    elif q_type in ("SCENARIO_10", "LONGFORM_15"):
        return _render_scenario(content)
    return f"<pre>{content}</pre>"


def _render_mcq(content: dict) -> str:
    html_parts = []
    questions = content.get("questions", [])
    for q in questions:
        html_parts.append(f'<div class="mcq-question">')
        html_parts.append(f'<h4>Question {q.get("number", "")}</h4>')
        if q.get("scenario"):
            html_parts.append(f'<p class="scenario">{q["scenario"]}</p>')
        html_parts.append(f'<p class="question-text"><strong>{q.get("question", "")}</strong></p>')
        html_parts.append('<div class="options">')
        for letter in ["A", "B", "C", "D"]:
            opt = q.get("options", {}).get(letter, {})
            key_class = ' class="correct"' if opt.get("is_key") else ""
            html_parts.append(f'<div{key_class}><strong>{letter}.</strong> {opt.get("text", "")}</div>')
        html_parts.append("</div>")

        # Answer section
        html_parts.append('<details class="answer-details"><summary>Show Answer & Explanations</summary>')
        for letter in ["A", "B", "C", "D"]:
            opt = q.get("options", {}).get(letter, {})
            marker = " ✓ CORRECT" if opt.get("is_key") else ""
            html_parts.append(f'<div class="explanation"><strong>{letter}{marker}:</strong> ')
            if opt.get("calculation"):
                html_parts.append(f'<em>Calculation:</em> {opt["calculation"]}. ')
            html_parts.append(f'{opt.get("explanation", "")}</div>')

        if q.get("regulation_refs"):
            html_parts.append(f'<p class="refs"><em>References: {", ".join(q["regulation_refs"])}</em></p>')
        html_parts.append("</details></div>")

    return "\n".join(html_parts)


def _render_scenario(content: dict) -> str:
    html_parts = []
    q_num = content.get("question_number", "")
    marks = content.get("marks", "")
    sac_thue = content.get("sac_thue", "")

    html_parts.append(f'<div class="scenario-question">')
    html_parts.append(f'<h3>Question {q_num} — {sac_thue} ({marks} marks)</h3>')
    html_parts.append(f'<div class="scenario-text">{content.get("scenario", "")}</div>')

    # Sub-questions (question only)
    for sq in content.get("sub_questions", []):
        html_parts.append(f'<div class="sub-question">')
        html_parts.append(f'<p><strong>{sq.get("label", "")} ({sq.get("marks", "")} marks)</strong></p>')
        html_parts.append(f'<p>{sq.get("question", "")}</p>')
        html_parts.append("</div>")

    # Marking scheme
    html_parts.append('<details class="answer-details"><summary>Show Marking Scheme</summary>')
    for sq in content.get("sub_questions", []):
        html_parts.append(f'<div class="marking-scheme">')
        html_parts.append(f'<h4>{sq.get("label", "")}</h4>')
        if sq.get("answer"):
            html_parts.append(f'<p>{sq["answer"]}</p>')
        for ms in sq.get("marking_scheme", []):
            html_parts.append(f'<div class="mark-point">• {ms.get("point", "")} [{ms.get("mark", "")} mark(s)]</div>')
        html_parts.append("</div>")
    html_parts.append("</details></div>")

    return "\n".join(html_parts)
