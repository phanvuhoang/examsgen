import zipfile
import re
import os
import logging

logger = logging.getLogger(__name__)


def parse_sample_examples(file_path: str) -> list:
    """
    Split a sample questions docx into individual examples.
    Handles 3 formats found in ACCA sample files:
      - 'Example 1: text...'   (colon)
      - 'Example 5 MBM JSC...' (space + text, no colon)
    Excludes inline references like 'Example 10, point 2.16' or 'Example 8 of Circular'.
    Returns list of dicts: {example_number, title, content}
    """
    try:
        text = extract_text(file_path)
    except Exception as e:
        logger.warning(f"Cannot extract {file_path}: {e}")
        return []

    # Match 'Example N' where N is followed by:
    #   - colon: 'Example 1:'
    #   - space + uppercase letter or digit (start of company name/year): 'Example 5 MBM'
    # Exclude: 'Example N,' (inline ref) or 'Example N of/point/in' (inline ref)
    pattern = re.compile(
        r'(Example\s+\d+)'
        r'(?=\s*:|'          # followed by colon
        r'\s+[A-Z0-9])',     # OR space + uppercase/digit (company name/year)
        re.IGNORECASE
    )

    # Find all valid heading positions
    headings = []
    for m in pattern.finditer(text):
        pos = m.start()
        after = text[m.end():m.end()+30]
        # Exclude inline refs: 'Example N of', 'Example N point', 'Example N,'
        if re.match(r'\s*(of|point|,|\.)', after, re.IGNORECASE):
            continue
        num_match = re.search(r'\d+', m.group())
        n = int(num_match.group()) if num_match else 0
        headings.append((pos, m.end(), n))

    examples = []
    for idx, (start, end, n) in enumerate(headings):
        # Content goes from after heading to start of next heading (or end of text)
        next_start = headings[idx + 1][0] if idx + 1 < len(headings) else len(text)
        content = text[start:next_start].strip()
        if len(content) < 50:
            continue
        title = f"Example {n}"
        examples.append({
            "example_number": n,
            "title": title,
            "content": content,
        })

    return examples


def extract_text(file_path: str) -> str:
    """Extract text from .docx or .doc files."""
    if not os.path.exists(file_path):
        logger.warning(f"File not found: {file_path}")
        return ""
    if file_path.endswith(".docx"):
        return extract_docx(file_path)
    elif file_path.endswith(".doc"):
        return extract_doc_binary(file_path)
    return ""


def extract_docx(path: str) -> str:
    """Extract text from .docx (Office Open XML)."""
    try:
        with zipfile.ZipFile(path) as z:
            with z.open("word/document.xml") as f:
                xml = f.read().decode("utf-8")
        text = re.sub(r"<[^>]+>", " ", xml)
        return re.sub(r"\s+", " ", text).strip()
    except Exception as e:
        logger.error(f"Error extracting docx {path}: {e}")
        return ""


def extract_doc_binary(path: str) -> str:
    """Extract UTF-16 LE text from legacy .doc binary format."""
    try:
        with open(path, "rb") as f:
            data = f.read()
        text_chunks = []
        i = 0
        while i < len(data) - 1:
            if data[i + 1] == 0 and 32 <= data[i] < 127:
                chunk = bytearray()
                while (
                    i < len(data) - 1
                    and data[i + 1] == 0
                    and (32 <= data[i] < 127 or data[i] in [9, 10, 13])
                ):
                    chunk.append(data[i])
                    i += 2
                if len(chunk) > 15:
                    text_chunks.append(chunk.decode("ascii", errors="ignore"))
            else:
                i += 1
        text = " ".join(text_chunks)
        return re.sub(r"\s+", " ", text).strip()
    except Exception as e:
        logger.error(f"Error extracting doc {path}: {e}")
        return ""
