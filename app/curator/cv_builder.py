"""
cv_builder.py — Render the tailored CV and cover letter as HTML and PDF.

Functions:
  render_cv_html(tailored_cv: dict) -> str   — ATS-friendly single-column HTML
  render_cv_pdf(html: str) -> bytes           — via weasyprint (if available)
  render_cover_letter_pdf(text, header) -> bytes
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# HTML rendering
# ---------------------------------------------------------------------------


def render_cv_html(tailored_cv: dict, candidate_name: str = "") -> str:
    """
    Render a tailored CV dict as clean, ATS-friendly single-column HTML.
    The dict shape matches TailoredCV from app/curator/schemas.py.
    """
    sections: list[str] = []

    # Header
    if candidate_name:
        sections.append(f'<h1 class="name">{_esc(candidate_name)}</h1>')

    # Summary
    summary = tailored_cv.get("summary", "")
    if summary:
        sections.append(
            f'<section class="cv-summary"><h2>Profile</h2><p>{_esc(summary)}</p></section>'
        )

    # Experience
    experience = tailored_cv.get("experience", [])
    if experience:
        exp_html = '<section class="cv-experience"><h2>Experience</h2>'
        for role in experience:
            employer = _esc(role.get("employer", ""))
            title = _esc(role.get("title", ""))
            dates = _esc(role.get("dates", ""))
            bullets = role.get("bullets", [])
            exp_html += f"""
<div class="role">
  <div class="role-header">
    <span class="role-title">{title}</span>
    <span class="role-meta">{employer} &mdash; {dates}</span>
  </div>
  <ul>
    {"".join(f'<li>{_esc(b)}</li>' for b in bullets)}
  </ul>
</div>"""
        exp_html += "</section>"
        sections.append(exp_html)

    # Skills
    skills = tailored_cv.get("skills", [])
    if skills:
        skills_str = " &middot; ".join(_esc(s) for s in skills)
        sections.append(
            f'<section class="cv-skills"><h2>Skills</h2><p>{skills_str}</p></section>'
        )

    # Education
    education = tailored_cv.get("education", [])
    if education:
        edu_html = '<section class="cv-education"><h2>Education</h2>'
        for edu in education:
            institution = _esc(edu.get("institution", ""))
            qualification = _esc(edu.get("qualification", ""))
            dates = _esc(edu.get("dates", ""))
            edu_html += f'<div class="edu-entry"><strong>{qualification}</strong> &mdash; {institution} ({dates})</div>'
        edu_html += "</section>"
        sections.append(edu_html)

    # Certifications
    certs = tailored_cv.get("certifications", [])
    if certs:
        certs_html = '<section class="cv-certs"><h2>Certifications</h2><ul>'
        for cert in certs:
            certs_html += f"<li>{_esc(cert)}</li>"
        certs_html += "</ul></section>"
        sections.append(certs_html)

    body = "\n".join(sections)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>CV</title>
<style>
  body {{
    font-family: 'Georgia', serif;
    font-size: 11pt;
    line-height: 1.5;
    color: #1a1a1a;
    max-width: 800px;
    margin: 40px auto;
    padding: 0 40px;
  }}
  h1.name {{
    font-size: 22pt;
    margin-bottom: 4px;
    border-bottom: 2px solid #1a1a1a;
    padding-bottom: 6px;
  }}
  h2 {{
    font-size: 12pt;
    text-transform: uppercase;
    letter-spacing: 1px;
    border-bottom: 1px solid #ccc;
    margin-top: 20px;
    margin-bottom: 8px;
    padding-bottom: 2px;
  }}
  .cv-summary p {{
    margin: 0;
  }}
  .role {{
    margin-bottom: 14px;
  }}
  .role-header {{
    display: flex;
    justify-content: space-between;
    font-weight: bold;
  }}
  .role-meta {{
    font-weight: normal;
    color: #555;
    font-size: 10pt;
  }}
  ul {{
    margin: 4px 0 0 0;
    padding-left: 18px;
  }}
  li {{
    margin-bottom: 3px;
  }}
  .edu-entry {{
    margin-bottom: 6px;
  }}
  @media print {{
    body {{ margin: 20px; padding: 0; }}
    h2 {{ page-break-after: avoid; }}
    .role {{ page-break-inside: avoid; }}
  }}
</style>
</head>
<body>
{body}
</body>
</html>"""


def render_cover_letter_html(text: str, candidate_name: str = "", role_title: str = "", company: str = "") -> str:
    """Render a plain-text cover letter as a simple, printable HTML page."""
    header_parts = []
    if candidate_name:
        header_parts.append(f'<p class="cl-name"><strong>{_esc(candidate_name)}</strong></p>')
    if role_title and company:
        header_parts.append(f'<p class="cl-re">Re: {_esc(role_title)} — {_esc(company)}</p>')
    elif role_title:
        header_parts.append(f'<p class="cl-re">Re: {_esc(role_title)}</p>')

    # Convert newlines to paragraphs
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    body_html = "\n".join(f"<p>{_esc(p)}</p>" for p in paragraphs)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Cover Letter</title>
<style>
  body {{
    font-family: 'Georgia', serif;
    font-size: 11pt;
    line-height: 1.6;
    color: #1a1a1a;
    max-width: 720px;
    margin: 60px auto;
    padding: 0 40px;
  }}
  .cl-name {{ font-size: 14pt; margin-bottom: 4px; }}
  .cl-re {{ color: #555; margin-bottom: 24px; }}
  p {{ margin-bottom: 14px; }}
</style>
</head>
<body>
{"".join(header_parts)}
{body_html}
</body>
</html>"""


# ---------------------------------------------------------------------------
# PDF rendering (requires weasyprint)
# ---------------------------------------------------------------------------


def render_cv_pdf(html: str) -> bytes:
    """Convert CV HTML to PDF bytes using weasyprint."""
    try:
        from weasyprint import HTML
        return HTML(string=html).write_pdf()
    except ImportError:
        logger.warning(
            "weasyprint not installed — returning empty bytes. "
            "Install with: pip install weasyprint"
        )
        return b""


def render_cover_letter_pdf(text: str, candidate_name: str = "", role_title: str = "", company: str = "") -> bytes:
    """Convert cover letter text to PDF bytes using weasyprint."""
    html = render_cover_letter_html(text, candidate_name, role_title, company)
    return render_cv_pdf(html)


# ---------------------------------------------------------------------------
# Internal
# ---------------------------------------------------------------------------


def _esc(text: Any) -> str:
    """HTML-escape a value for safe embedding."""
    import html
    return html.escape(str(text))
