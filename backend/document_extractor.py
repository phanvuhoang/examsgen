import zipfile
import re
import os
import logging

logger = logging.getLogger(__name__)


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
