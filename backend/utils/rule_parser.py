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
