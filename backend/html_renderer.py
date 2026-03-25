"""Render question JSON to HTML for preview display."""
import re


def _nl(text: str) -> str:
    """Convert newlines to <br> tags."""
    if not text:
        return ""
    return str(text).replace("\n", "<br>")


def _calc_table(text: str) -> str:
    """
    If text contains ≥ 2 lines matching a calculation pattern, render as HTML table.
    Otherwise return text with newlines converted to <br>.
    Patterns detected: "Item = formula = result (marks)" or markdown table rows |col|col|...
    """
    if not text:
        return ""

    lines = [l.strip() for l in str(text).split("\n") if l.strip()]

    # Check for markdown table (lines starting with |)
    table_lines = [l for l in lines if l.startswith("|")]
    if len(table_lines) >= 3:
        # Render markdown table as HTML
        html_rows = []
        for i, line in enumerate(table_lines):
            # Skip separator rows (---|---)
            if re.match(r'^\|[-| :]+\|$', line):
                continue
            cells = [c.strip() for c in line.strip("|").split("|")]
            tag = "th" if i == 0 else "td"
            row_html = "".join(f"<{tag}>{c}</{tag}>" for c in cells)
            html_rows.append(f"<tr>{row_html}</tr>")
        return f'<table class="calc-table">{"".join(html_rows)}</table>'

    # Check for inline calc pattern: "text = expr = result (0.5 mk)" or "(0.5 marks)"
    calc_pattern = re.compile(
        r'^.{2,80}=.{2,}.+\([\d.]+\s*(mk|mark|marks)\)', re.IGNORECASE
    )
    calc_lines = [l for l in lines if calc_pattern.match(l)]

    if len(calc_lines) >= 2:
        rows = []
        for line in lines:
            # Try to parse: "Description = expr = result (X marks)"
            m = re.match(r'^(.*?)\s*=\s*(.*?)\s*=\s*([^\(=]+)\s*\(([\d.]+\s*(?:mk|marks?))\)', line, re.IGNORECASE)
            if m:
                desc, expr, result, marks = m.group(1), m.group(2), m.group(3).strip(), m.group(4)
                rows.append(
                    f'<tr><td>{desc}</td><td>{expr}</td><td>{result}</td>'
                    f'<td class="marks">{marks}</td></tr>'
                )
            else:
                # Single "text = result (X marks)"
                m2 = re.match(r'^(.*?)\s*=\s*([^\(]+)\s*\(([\d.]+\s*(?:mk|marks?))\)', line, re.IGNORECASE)
                if m2:
                    desc, result, marks = m2.group(1), m2.group(2).strip(), m2.group(3)
                    rows.append(
                        f'<tr><td>{desc}</td><td></td><td>{result}</td>'
                        f'<td class="marks">{marks}</td></tr>'
                    )
                else:
                    rows.append(f'<tr><td colspan="4">{line}</td></tr>')
        return f'<table class="calc-table">{"".join(rows)}</table>'

    # Default: newlines to <br>
    return _nl(text)


def _syllabus_tags(codes: list) -> str:
    if not codes:
        return ""
    tags = "".join(
        f'<span style="display:inline-block;background:#e8f5e9;color:#2e7d32;border:1px solid #a5d6a7;'
        f'border-radius:4px;padding:2px 8px;font-size:11px;margin:2px 3px 2px 0;font-weight:600;">'
        f'{code}</span>'
        for code in codes
    )
    return (
        f'<div style="margin-top:10px;padding-top:8px;border-top:1px solid #e5e7eb;">'
        f'<span style="font-size:11px;color:#6b7280;font-weight:600;text-transform:uppercase;'
        f'letter-spacing:0.05em;">Syllabus codes tested: </span>{tags}</div>'
    )


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
        html_parts.append('<div class="mcq-question">')
        html_parts.append(f'<h4>Question {q.get("number", "")}</h4>')

        if q.get("scenario"):
            html_parts.append(f'<p class="scenario">{_nl(q["scenario"])}</p>')

        html_parts.append(f'<p class="question-text"><strong>{_nl(q.get("question", ""))}</strong></p>')

        # Options
        html_parts.append('<div class="options" style="margin:12px 0;">')
        for letter in ["A", "B", "C", "D"]:
            opt = q.get("options", {}).get(letter, {})
            is_correct = opt.get("is_key", False)
            css_class = "option correct" if is_correct else "option wrong"
            marker = " ✓" if is_correct else ""
            html_parts.append(
                f'<div class="{css_class}"><strong>{letter}.{marker}</strong> {opt.get("text", "")}</div>'
            )
        html_parts.append("</div>")

        # Answer section
        html_parts.append('<details class="answer-details"><summary>Show Answer &amp; Explanations</summary>')
        html_parts.append('<div class="answer-block">')

        for letter in ["A", "B", "C", "D"]:
            opt = q.get("options", {}).get(letter, {})
            is_correct = opt.get("is_key", False)
            marker = " ✓ CORRECT" if is_correct else ""

            html_parts.append(f'<div class="explanation" style="margin-bottom:10px;">')
            html_parts.append(f'<div class="section-label">{letter}{marker}</div>')

            if is_correct and opt.get("working"):
                html_parts.append(f'<div style="margin:6px 0;">{_calc_table(opt["working"])}</div>')

            expl = opt.get("explanation", "")
            if expl:
                html_parts.append(f'<div>{_nl(expl)}</div>')

            html_parts.append('</div>')

        if q.get("regulation_refs"):
            html_parts.append(
                f'<div class="refs">References: {", ".join(q["regulation_refs"])}</div>'
            )

        html_parts.append('</div>')  # answer-block
        html_parts.append('</details>')

        html_parts.append(_syllabus_tags(q.get("syllabus_codes", [])))
        html_parts.append("</div>")  # mcq-question

    return "\n".join(html_parts)


def _render_scenario(content: dict) -> str:
    html_parts = []
    q_num = content.get("question_number", "")
    marks = content.get("marks", "")
    sac_thue = content.get("sac_thue", "")

    html_parts.append('<div class="scenario-question">')
    html_parts.append(f'<h3>Question {q_num} — {sac_thue} ({marks} marks)</h3>')

    if content.get("scenario"):
        html_parts.append(
            f'<div class="scenario-text" style="margin-bottom:16px;">{_nl(content["scenario"])}</div>'
        )

    # Sub-questions (question only)
    for sq in content.get("sub_questions", []):
        html_parts.append('<div class="sub-question">')
        html_parts.append(
            f'<p><strong>{sq.get("label", "")} ({sq.get("marks", "")} marks)</strong></p>'
        )
        html_parts.append(f'<p>{_nl(sq.get("question", ""))}</p>')
        html_parts.append("</div>")

    # Marking scheme
    html_parts.append('<details class="answer-details"><summary>Show Marking Scheme</summary>')

    for sq in content.get("sub_questions", []):
        html_parts.append('<div class="marking-scheme">')
        html_parts.append(
            f'<h4>{sq.get("label", "")} ({sq.get("marks", "")} marks)</h4>'
        )

        if sq.get("answer"):
            html_parts.append(
                f'<div class="answer-block">{_calc_table(sq["answer"])}</div>'
            )

        for ms in sq.get("marking_scheme", []):
            mark_val = ms.get("mark", "")
            point_text = _nl(ms.get("point", ""))
            html_parts.append(
                f'<div class="mark-point">'
                f'<span class="mark-pill">{mark_val} mk</span>'
                f'<span>{point_text}</span>'
                f'</div>'
            )
        html_parts.append("</div>")  # marking-scheme

    reg_refs = content.get("regulation_refs", [])
    if reg_refs:
        html_parts.append(
            f'<div class="refs">References: {", ".join(reg_refs)}</div>'
        )

    html_parts.append(_syllabus_tags(content.get("syllabus_codes", [])))
    html_parts.append("</details></div>")

    return "\n".join(html_parts)
