import zipfile
import re
import os
import logging

logger = logging.getLogger(__name__)


def parse_sample_examples(file_path: str) -> list:
    """
    Split a sample questions docx into individual examples.
    Rule: Split on paragraphs styled as Heading 2 that match 'Example N:' pattern.
    If no Heading 2 found, fallback to 'Example N:' (colon required) in plain text.
    Returns list of dicts: {example_number, title, content}
    """
    if not os.path.exists(file_path):
        logger.warning(f"File not found: {file_path}")
        return []

    try:
        import zipfile
        from xml.etree import ElementTree as ET
        with zipfile.ZipFile(file_path) as z:
            with z.open("word/document.xml") as f:
                xml_content = f.read().decode("utf-8")
    except Exception as e:
        logger.warning(f"Cannot open docx {file_path}: {e}")
        return []

    # Parse XML — extract paragraphs with their style
    ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
    try:
        root = ET.fromstring(xml_content)
    except Exception as e:
        logger.warning(f"Cannot parse XML {file_path}: {e}")
        return []

    paragraphs = []  # list of (style_name, text)
    for para in root.iter('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p'):
        # Get style
        style = ''
        pPr = para.find('.//w:pStyle', ns)
        if pPr is not None:
            style = pPr.get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val', '')
        # Get text
        texts = []
        for r in para.iter('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t'):
            if r.text:
                texts.append(r.text)
        text = ''.join(texts).strip()
        if text:
            paragraphs.append((style, text))

    # Find heading paragraphs that match 'Example N:'
    heading_styles = {'Heading2', 'heading2', '2', 'Heading 2'}
    example_pattern = re.compile(r'^Example\s+\d+\s*:', re.IGNORECASE)

    # Strategy 1: Use Heading 2 style
    heading_indices = [
        i for i, (style, text) in enumerate(paragraphs)
        if style in heading_styles and example_pattern.match(text)
    ]

    # Strategy 2: Fallback — 'Example N:' anywhere in plain text (no heading style required)
    if not heading_indices:
        logger.info(f"No Heading2 found in {file_path}, falling back to colon pattern")
        heading_indices = [
            i for i, (style, text) in enumerate(paragraphs)
            if example_pattern.match(text)
        ]

    if not heading_indices:
        logger.warning(f"No examples found in {file_path}")
        return []

    # Build examples: heading paragraph + all content until next heading
    examples = []
    for idx, hi in enumerate(heading_indices):
        heading_text = paragraphs[hi][1]
        num_match = re.search(r'\d+', heading_text)
        example_number = int(num_match.group()) if num_match else (idx + 1)
        title = f"Example {example_number}"

        # Collect content paragraphs until next heading
        next_hi = heading_indices[idx + 1] if idx + 1 < len(heading_indices) else len(paragraphs)
        content_parts = [heading_text]
        for pi in range(hi + 1, next_hi):
            content_parts.append(paragraphs[pi][1])
        content = ' '.join(content_parts).strip()

        if len(content) < 50:
            continue

        examples.append({
            "example_number": example_number,
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
