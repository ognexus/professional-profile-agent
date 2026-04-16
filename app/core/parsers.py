"""
parsers.py — Normalise various input types into clean plain text for LLM consumption.

Supported input types:
  - PDF (bytes)   → parse_pdf()
  - DOCX (bytes)  → parse_docx()
  - Pasted text   → parse_pasted_text()
  - Web URL       → fetch_url_text()

Utilities:
  - detect_input_type()     — infer type from filename + content
  - extract_linkedin_sections() — best-effort section splitter for LinkedIn exports
"""

from __future__ import annotations

import io
import re
import unicodedata
from typing import Literal


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def parse_pdf(file_bytes: bytes) -> str:
    """
    Extract text from a PDF, preserving section breaks as double newlines.
    Strips common LinkedIn PDF header/footer noise (page numbers, "LinkedIn" watermarks).
    """
    try:
        from pypdf import PdfReader
    except ImportError as e:
        raise ImportError("pypdf is required: pip install pypdf") from e

    reader = PdfReader(io.BytesIO(file_bytes))
    pages: list[str] = []

    for page in reader.pages:
        raw = page.extract_text() or ""
        cleaned = _clean_page_text(raw)
        if cleaned.strip():
            pages.append(cleaned)

    # Join pages with a double newline to signal section break
    text = "\n\n".join(pages)
    return _normalise_whitespace(text)


def parse_docx(file_bytes: bytes) -> str:
    """
    Extract text from a DOCX, preserving paragraph structure as newlines.
    """
    try:
        from docx import Document
    except ImportError as e:
        raise ImportError("python-docx is required: pip install python-docx") from e

    doc = Document(io.BytesIO(file_bytes))
    paragraphs: list[str] = []

    for para in doc.paragraphs:
        text = para.text.strip()
        if text:
            paragraphs.append(text)

    return _normalise_whitespace("\n".join(paragraphs))


def parse_pasted_text(text: str) -> str:
    """
    Light cleanup of pasted text: remove zero-width chars, normalise unicode,
    collapse excessive blank lines — but preserve intentional linebreaks.
    """
    if not text:
        return ""
    # Remove zero-width and invisible characters
    text = _remove_invisible_chars(text)
    # Normalise unicode (NFC)
    text = unicodedata.normalize("NFC", text)
    # Collapse 3+ consecutive blank lines into 2
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Trim trailing whitespace per line
    text = "\n".join(line.rstrip() for line in text.splitlines())
    return text.strip()


def fetch_url_text(url: str, timeout: int = 15) -> str:
    """
    Fetch the text content of a web page (e.g. a LinkedIn job posting URL).

    Strategy:
      1. GET the page with a browser-like User-Agent
      2. Parse with BeautifulSoup, extract main content blocks
      3. Strip navigation, footers, scripts, and other noise
      4. Return clean plain text suitable for an LLM

    Raises:
        ValueError: if the URL is empty or clearly not a URL
        RuntimeError: if the fetch fails (network error, 4xx/5xx, etc.)
    """
    url = url.strip()
    if not url:
        raise ValueError("URL is empty")
    if not url.startswith(("http://", "https://")):
        raise ValueError(f"Not a valid URL: {url!r}")

    try:
        import requests
        from bs4 import BeautifulSoup
    except ImportError as e:
        raise ImportError(
            "requests and beautifulsoup4 are required: pip install requests beautifulsoup4"
        ) from e

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
    }

    try:
        response = requests.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()
    except requests.exceptions.Timeout:
        raise RuntimeError(f"Request timed out after {timeout}s: {url}")
    except requests.exceptions.ConnectionError as e:
        raise RuntimeError(f"Could not connect to {url}: {e}")
    except requests.exceptions.HTTPError as e:
        raise RuntimeError(f"HTTP error fetching {url}: {e}")

    soup = BeautifulSoup(response.text, "lxml")

    # Remove noise elements
    for tag in soup(["script", "style", "nav", "header", "footer",
                      "aside", "form", "noscript", "iframe", "img"]):
        tag.decompose()

    # Try to find the main content container (common patterns across job sites)
    main_content = (
        soup.find("main")
        or soup.find("article")
        or soup.find(id=re.compile(r"job[-_]?desc|description|content|main", re.I))
        or soup.find(class_=re.compile(r"job[-_]?desc|description|content|main", re.I))
        or soup.body
    )

    if main_content is None:
        main_content = soup

    # Extract text preserving block-level structure
    lines: list[str] = []
    for element in main_content.find_all(
        ["p", "li", "h1", "h2", "h3", "h4", "h5", "h6", "div", "span", "td"]
    ):
        text = element.get_text(separator=" ", strip=True)
        if text and len(text) > 15:  # skip tiny fragments
            lines.append(text)

    # Deduplicate adjacent identical lines (common in scraped pages)
    deduped: list[str] = []
    for line in lines:
        if not deduped or line != deduped[-1]:
            deduped.append(line)

    raw = "\n".join(deduped)
    return _normalise_whitespace(raw)


def detect_input_type(
    filename: str, content: bytes | str
) -> Literal["pdf", "docx", "text"]:
    """
    Infer input type from filename extension, falling back to content sniffing.
    """
    name = (filename or "").lower()
    if name.endswith(".pdf"):
        return "pdf"
    if name.endswith(".docx"):
        return "docx"
    if name.endswith((".doc", ".txt", ".md")):
        return "text"

    # Content sniffing as fallback
    if isinstance(content, bytes):
        if content[:4] == b"%PDF":
            return "pdf"
        # DOCX is a zip file starting with PK
        if content[:2] == b"PK":
            return "docx"

    return "text"


# LinkedIn section header patterns (order matters — more specific first)
_LINKEDIN_SECTIONS = [
    "Experience",
    "Education",
    "Skills",
    "Certifications",
    "Licenses & Certifications",
    "Courses",
    "Recommendations",
    "Volunteer Experience",
    "Publications",
    "Projects",
    "Languages",
    "Accomplishments",
    "Interests",
    "About",
    "Headline",
    "Summary",
]

_SECTION_RE = re.compile(
    r"^(" + "|".join(re.escape(s) for s in _LINKEDIN_SECTIONS) + r")\s*$",
    re.MULTILINE | re.IGNORECASE,
)


def extract_linkedin_sections(raw_text: str) -> dict[str, str]:
    """
    Best-effort parser that splits a LinkedIn profile export into named sections.
    Returns a dict like {"headline": "...", "about": "...", "experience": "...", ...}.

    Does NOT over-engineer — uses simple header matching. If a section isn't found,
    it won't appear in the dict. The "raw" key always contains the full text.
    """
    if not raw_text:
        return {"raw": ""}

    sections: dict[str, str] = {"raw": raw_text}

    # Find all section header positions
    matches = list(_SECTION_RE.finditer(raw_text))

    if not matches:
        # No recognisable structure — treat everything as raw experience text
        sections["experience"] = raw_text
        return sections

    # Extract text between consecutive headers
    for i, match in enumerate(matches):
        header = match.group(1).lower().replace(" ", "_").replace("&", "and")
        # Normalise some aliases
        header = _normalise_section_name(header)

        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(raw_text)
        body = raw_text[start:end].strip()

        if header in sections:
            # Append to existing (duplicate section headers can appear in exports)
            sections[header] = sections[header] + "\n\n" + body
        else:
            sections[header] = body

    # Try to extract headline from first ~3 lines before any section header
    first_section_start = matches[0].start()
    preamble = raw_text[:first_section_start].strip()
    if preamble:
        lines = [l.strip() for l in preamble.splitlines() if l.strip()]
        if lines:
            sections.setdefault("headline", lines[0])
        if len(lines) > 1:
            sections.setdefault("about", "\n".join(lines[1:]))

    return sections


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _clean_page_text(raw: str) -> str:
    """Remove LinkedIn PDF boilerplate: page numbers, URL footers, watermarks."""
    lines = raw.splitlines()
    cleaned: list[str] = []
    for line in lines:
        stripped = line.strip()
        # Skip pure page-number lines ("1", "2 of 5", etc.)
        if re.fullmatch(r"\d+(\s+of\s+\d+)?", stripped):
            continue
        # Skip LinkedIn URL footers
        if "linkedin.com" in stripped.lower() and len(stripped) < 80:
            continue
        # Skip "Contact" header-only lines that appear as artifacts
        if stripped.lower() in {"contact", "linkedin"}:
            continue
        cleaned.append(line)
    return "\n".join(cleaned)


def _normalise_whitespace(text: str) -> str:
    """Collapse intra-line multiple spaces; preserve intentional newlines."""
    # Collapse multiple spaces (but not newlines) to a single space
    text = re.sub(r"[ \t]+", " ", text)
    # Collapse 3+ newlines to 2
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _remove_invisible_chars(text: str) -> str:
    """Strip zero-width spaces, BOM, soft hyphens, and similar invisible chars."""
    invisible = {
        "\u200b",  # zero-width space
        "\u200c",  # zero-width non-joiner
        "\u200d",  # zero-width joiner
        "\ufeff",  # BOM
        "\u00ad",  # soft hyphen
        "\u2060",  # word joiner
    }
    return "".join(ch for ch in text if ch not in invisible)


def _normalise_section_name(name: str) -> str:
    """Map section name aliases to canonical keys."""
    aliases = {
        "licenses_and_certifications": "certifications",
        "volunteer_experience": "volunteer",
        "summary": "about",
    }
    return aliases.get(name, name)
