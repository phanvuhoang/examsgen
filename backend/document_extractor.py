import zipfile
import re
import os
import logging

logger = logging.getLogger(__name__)


def parse_sample_examples(file_path: str) -> list:
    """
    Split a sample questions docx into individual examples.
    Splits on 'Example N:' (with colon) — the standard format in ACCA sample files.
    Avoids false positives like 'per Example 10, Circular...' which have no colon.
    Returns list of dicts: {example_number, title, content}
    """
    try:
        text = extract_text(file_path)
    except Exception as e:
        logger.warning(f"Cannot extract {file_path}: {e}")
        return []

    # Split on 'Example N:' — colon required to avoid matching inline references
    pattern = re.compile(r'(Example\s+\d+\s*:)', re.IGNORECASE)
    parts = pattern.split(text)
    # parts = [preamble, heading1, content1, heading2, content2, ...]

    examples = []
    i = 1  # skip preamble (index 0)
    while i < len(parts) - 1:
        heading_raw = parts[i].strip()  # e.g. "Example 2:"
        content = parts[i + 1].strip() if i + 1 < len(parts) else ""
        # Skip very short content — likely false positives
        if len(content) < 50:
            i += 2
            continue
        num_match = re.search(r'\d+', heading_raw)
        example_number = int(num_match.group()) if num_match else (len(examples) + 1)
        title = f"Example {example_number}"
        examples.append({
            "example_number": example_number,
            "title": title,
            "content": f"{title}: {content}",
        })
        i += 2

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
