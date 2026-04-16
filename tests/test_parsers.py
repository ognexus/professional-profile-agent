"""
test_parsers.py — Unit tests for app/core/parsers.py.
Uses synthetic fixtures only — no real personal data.
"""

import pytest
from app.core.parsers import (
    parse_pasted_text,
    detect_input_type,
    extract_linkedin_sections,
)


# ---------------------------------------------------------------------------
# parse_pasted_text
# ---------------------------------------------------------------------------


def test_parse_pasted_text_empty():
    assert parse_pasted_text("") == ""


def test_parse_pasted_text_removes_zero_width():
    text = "Hello\u200b World\u200c!"
    result = parse_pasted_text(text)
    assert "\u200b" not in result
    assert "\u200c" not in result
    assert "Hello World!" in result


def test_parse_pasted_text_collapses_excessive_blank_lines():
    text = "Line 1\n\n\n\n\nLine 2"
    result = parse_pasted_text(text)
    assert "\n\n\n" not in result
    assert "Line 1" in result
    assert "Line 2" in result


def test_parse_pasted_text_preserves_intentional_linebreaks():
    text = "Line A\nLine B\nLine C"
    result = parse_pasted_text(text)
    assert "Line A" in result
    assert "Line B" in result
    assert "Line C" in result


def test_parse_pasted_text_trims_trailing_whitespace():
    text = "Line 1   \nLine 2  \n"
    result = parse_pasted_text(text)
    for line in result.splitlines():
        assert line == line.rstrip()


# ---------------------------------------------------------------------------
# detect_input_type
# ---------------------------------------------------------------------------


def test_detect_input_type_pdf_by_extension():
    assert detect_input_type("resume.pdf", b"") == "pdf"


def test_detect_input_type_docx_by_extension():
    assert detect_input_type("cv.docx", b"") == "docx"


def test_detect_input_type_txt_by_extension():
    assert detect_input_type("profile.txt", b"some text") == "text"


def test_detect_input_type_pdf_by_magic_bytes():
    assert detect_input_type("unknown", b"%PDF-1.4 ...") == "pdf"


def test_detect_input_type_docx_by_magic_bytes():
    # DOCX is a ZIP — starts with PK
    assert detect_input_type("unknown", b"PK\x03\x04...") == "docx"


def test_detect_input_type_fallback_to_text():
    assert detect_input_type("notes", "some plain text content") == "text"


# ---------------------------------------------------------------------------
# extract_linkedin_sections — synthetic LinkedIn-style text
# ---------------------------------------------------------------------------

SYNTHETIC_LINKEDIN = """Jane Smith
Senior Product Manager | Fintech | Remote

About
Experienced product leader with 8 years building payment infrastructure at scale.
Passionate about cross-functional collaboration and data-driven decisions.

Experience
Senior Product Manager, Payments — Acme Corp (2020–Present)
Led the redesign of the checkout flow, reducing drop-off by 22%.
Managed a team of 4 PMs across APAC and EMEA.

Product Manager — Startup XYZ (2017–2020)
Launched mobile wallet feature with 500K+ users in first quarter.

Education
Bachelor of Commerce — University of Sydney (2013–2016)
Major in Finance and Information Systems.

Skills
Product Strategy · Roadmap Planning · SQL · A/B Testing · Stakeholder Management

Certifications
AWS Certified Cloud Practitioner (2022)
"""


def test_extract_linkedin_sections_returns_raw():
    result = extract_linkedin_sections(SYNTHETIC_LINKEDIN)
    assert "raw" in result
    assert "Jane Smith" in result["raw"]


def test_extract_linkedin_sections_experience():
    result = extract_linkedin_sections(SYNTHETIC_LINKEDIN)
    assert "experience" in result
    assert "Acme Corp" in result["experience"]
    assert "Startup XYZ" in result["experience"]


def test_extract_linkedin_sections_education():
    result = extract_linkedin_sections(SYNTHETIC_LINKEDIN)
    assert "education" in result
    assert "University of Sydney" in result["education"]


def test_extract_linkedin_sections_skills():
    result = extract_linkedin_sections(SYNTHETIC_LINKEDIN)
    assert "skills" in result
    assert "SQL" in result["skills"]


def test_extract_linkedin_sections_certifications():
    result = extract_linkedin_sections(SYNTHETIC_LINKEDIN)
    assert "certifications" in result
    assert "AWS" in result["certifications"]


def test_extract_linkedin_sections_about():
    result = extract_linkedin_sections(SYNTHETIC_LINKEDIN)
    assert "about" in result
    assert "payment infrastructure" in result["about"]


def test_extract_linkedin_sections_empty_input():
    result = extract_linkedin_sections("")
    assert result == {"raw": ""}


def test_extract_linkedin_sections_no_headers():
    raw = "This is just some random text with no LinkedIn section headers."
    result = extract_linkedin_sections(raw)
    assert "raw" in result
    assert "experience" in result  # fallback
