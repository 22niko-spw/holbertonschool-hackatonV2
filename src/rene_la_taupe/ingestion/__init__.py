# Pipeline d'ingestion — René LA TAUPE (Kévin)
# Parsing PDF/TXT/DOCX/MD/JSON, normalisation Unicode, découpage en chunks.

from __future__ import annotations

import io
import unicodedata
import uuid

SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md", ".json"}

# Catégories Unicode "invisibles" côté rendu mais exploitables pour de
# l'obfuscation (format chars type zero-width, overrides bidi, tags Unicode).
_INVISIBLE_CATEGORIES = {"Cf"}
_ZERO_WIDTH_CHARS = "​‌‍⁠﻿"


class UnsupportedFileTypeError(ValueError):
    pass


class DocumentParseError(ValueError):
    pass


def normalize_unicode(text: str) -> str:
    """
    Normalise le texte pour empêcher les contournements par obfuscation :
    - forme canonique NFKC (homoglyphes compatibles, ligatures, etc.)
    - suppression des caractères de contrôle et des caractères invisibles
      (zero-width space, joiners, marqueurs bidi, BOM...)
    """
    text = unicodedata.normalize("NFKC", text)
    cleaned_chars = []
    for ch in text:
        if ch in _ZERO_WIDTH_CHARS:
            continue
        if unicodedata.category(ch) in _INVISIBLE_CATEGORIES:
            continue
        if unicodedata.category(ch) == "Cc" and ch not in ("\n", "\t"):
            continue
        cleaned_chars.append(ch)
    return "".join(cleaned_chars)


def parse_document(filename: str, data: bytes) -> str:
    """Extrait le texte brut d'un fichier selon son extension."""
    ext = _extension(filename)
    if ext not in SUPPORTED_EXTENSIONS:
        raise UnsupportedFileTypeError(
            f"Type de fichier non supporté : '{ext}'. Supportés : {sorted(SUPPORTED_EXTENSIONS)}"
        )
    try:
        if ext == ".pdf":
            return _parse_pdf(data)
        if ext == ".docx":
            return _parse_docx(data)
        # .txt, .md, .json : texte brut
        return data.decode("utf-8", errors="replace")
    except (UnsupportedFileTypeError, DocumentParseError):
        raise
    except Exception as exc:
        raise DocumentParseError(f"Échec du parsing de '{filename}': {exc}") from exc


def _extension(filename: str) -> str:
    idx = filename.rfind(".")
    return filename[idx:].lower() if idx != -1 else ""


def _parse_pdf(data: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n".join(pages)


def _parse_docx(data: bytes) -> str:
    import docx

    document = docx.Document(io.BytesIO(data))
    return "\n".join(p.text for p in document.paragraphs)


def chunk_text(text: str, chunk_size_words: int = 200, overlap_words: int = 30) -> list[str]:
    """
    Découpe un texte en chunks de taille ~chunk_size_words mots, avec
    recouvrement, pour préserver le contexte aux frontières de chunk.
    """
    words = text.split()
    if not words:
        return []
    if chunk_size_words <= overlap_words:
        raise ValueError("chunk_size_words doit être strictement supérieur à overlap_words")

    chunks = []
    step = chunk_size_words - overlap_words
    for start in range(0, len(words), step):
        chunk_words = words[start : start + chunk_size_words]
        if not chunk_words:
            break
        chunks.append(" ".join(chunk_words))
        if start + chunk_size_words >= len(words):
            break
    return chunks


def new_doc_id() -> str:
    return f"DOC-{uuid.uuid4().hex[:8]}"


def new_corpus_id() -> str:
    return f"CORPUS-{uuid.uuid4().hex[:8]}"
