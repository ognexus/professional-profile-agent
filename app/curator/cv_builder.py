"""
cv_builder.py — Render the tailored CV and cover letter as HTML and PDF.

PDF generation uses ReportLab (pure Python, no system dependencies).
HTML generation is kept for in-app preview via st.components.v1.html().

Functions:
  render_cv_html(tailored_cv, candidate_name)        -> str   (HTML preview)
  render_cover_letter_html(text, ...)                -> str   (HTML preview)
  render_cv_pdf(tailored_cv, candidate_name)         -> bytes (PDF via reportlab)
  render_cover_letter_pdf(text, role_title, company) -> bytes (PDF via reportlab)
"""

from __future__ import annotations

import logging
from io import BytesIO
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# HTML rendering (for in-app preview)
# ---------------------------------------------------------------------------


def render_cv_html(tailored_cv: dict, candidate_name: str = "") -> str:
    """
    Render a tailored CV dict as clean, ATS-friendly single-column HTML.
    The dict shape matches TailoredCV from app/curator/schemas.py.
    """
    sections: list[str] = []

    if candidate_name:
        sections.append(f'<h1 class="name">{_esc(candidate_name)}</h1>')

    summary = tailored_cv.get("summary", "")
    if summary:
        sections.append(
            f'<section class="cv-summary"><h2>Profile</h2><p>{_esc(summary)}</p></section>'
        )

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

    skills = tailored_cv.get("skills", [])
    if skills:
        skills_str = " &middot; ".join(_esc(s) for s in skills)
        sections.append(
            f'<section class="cv-skills"><h2>Skills</h2><p>{skills_str}</p></section>'
        )

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
    font-family: Georgia, serif;
    font-size: 11pt;
    line-height: 1.5;
    color: #1a1a1a;
    background-color: #ffffff;
    max-width: 800px;
    margin: 40px auto;
    padding: 0 40px;
  }}
  h1.name {{
    font-size: 22pt;
    margin-bottom: 4px;
    border-bottom: 2px solid #1a1a1a;
    padding-bottom: 6px;
    color: #1a1a1a;
  }}
  h2 {{
    font-size: 12pt;
    text-transform: uppercase;
    letter-spacing: 1px;
    border-bottom: 1px solid #ccc;
    margin-top: 20px;
    margin-bottom: 8px;
    padding-bottom: 2px;
    color: #1a1a1a;
  }}
  .cv-summary p {{ margin: 0; color: #1a1a1a; }}
  .role {{ margin-bottom: 14px; }}
  .role-header {{ display: flex; justify-content: space-between; font-weight: bold; color: #1a1a1a; }}
  .role-title {{ color: #1a1a1a; }}
  .role-meta {{ font-weight: normal; color: #555; font-size: 10pt; }}
  ul {{ margin: 4px 0 0 0; padding-left: 18px; }}
  li {{ margin-bottom: 3px; color: #1a1a1a; }}
  .edu-entry {{ margin-bottom: 6px; color: #1a1a1a; }}
  p {{ color: #1a1a1a; }}
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


def render_cover_letter_html(
    text: str, candidate_name: str = "", role_title: str = "", company: str = ""
) -> str:
    """Render a plain-text cover letter as a simple, printable HTML page."""
    header_parts = []
    if candidate_name:
        header_parts.append(f'<p class="cl-name"><strong>{_esc(candidate_name)}</strong></p>')
    if role_title and company:
        header_parts.append(f'<p class="cl-re">Re: {_esc(role_title)} — {_esc(company)}</p>')
    elif role_title:
        header_parts.append(f'<p class="cl-re">Re: {_esc(role_title)}</p>')

    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    body_html = "\n".join(f"<p>{_esc(p)}</p>" for p in paragraphs)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Cover Letter</title>
<style>
  body {{
    font-family: Georgia, serif;
    font-size: 11pt;
    line-height: 1.6;
    color: #1a1a1a;
    background-color: #ffffff;
    max-width: 720px;
    margin: 60px auto;
    padding: 0 40px;
  }}
  .cl-name {{ font-size: 14pt; margin-bottom: 4px; color: #1a1a1a; }}
  .cl-re {{ color: #555; margin-bottom: 24px; }}
  p {{ margin-bottom: 14px; color: #1a1a1a; }}
</style>
</head>
<body>
{"".join(header_parts)}
{body_html}
</body>
</html>"""


# ---------------------------------------------------------------------------
# PDF rendering — ReportLab (pure Python, no system libraries required)
# ---------------------------------------------------------------------------


def render_cv_pdf(tailored_cv: dict, candidate_name: str = "") -> bytes:
    """
    Generate a clean, A4 CV PDF from a structured TailoredCV dict using ReportLab.
    No system-level dependencies (works locally and on Streamlit Cloud).
    """
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.lib import colors
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, HRFlowable, ListFlowable, ListItem,
    )
    from reportlab.lib.enums import TA_LEFT, TA_JUSTIFY

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=2 * cm,
        leftMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )

    # ---- Styles ----
    INDIGO = colors.HexColor("#4338ca")
    BLACK = colors.HexColor("#1a1a1a")
    GREY = colors.HexColor("#555555")

    name_style = ParagraphStyle(
        "Name", fontName="Helvetica-Bold", fontSize=20, textColor=BLACK,
        spaceAfter=4, leading=24,
    )
    section_heading_style = ParagraphStyle(
        "SectionHeading", fontName="Helvetica-Bold", fontSize=10,
        textColor=INDIGO, spaceBefore=14, spaceAfter=4,
        borderPadding=(0, 0, 2, 0), leading=14,
    )
    role_title_style = ParagraphStyle(
        "RoleTitle", fontName="Helvetica-Bold", fontSize=10,
        textColor=BLACK, spaceAfter=1, leading=13,
    )
    role_meta_style = ParagraphStyle(
        "RoleMeta", fontName="Helvetica-Oblique", fontSize=9,
        textColor=GREY, spaceAfter=4, leading=12,
    )
    body_style = ParagraphStyle(
        "Body", fontName="Helvetica", fontSize=9.5,
        textColor=BLACK, leading=13, spaceAfter=4, alignment=TA_JUSTIFY,
    )
    bullet_style = ParagraphStyle(
        "Bullet", fontName="Helvetica", fontSize=9.5,
        textColor=BLACK, leading=13, leftIndent=12, spaceAfter=2,
    )
    skills_style = ParagraphStyle(
        "Skills", fontName="Helvetica", fontSize=9.5,
        textColor=BLACK, leading=13, spaceAfter=4,
    )

    flowables = []

    # ---- Name ----
    if candidate_name:
        flowables.append(Paragraph(candidate_name, name_style))
        flowables.append(HRFlowable(width="100%", thickness=1.5, color=BLACK, spaceAfter=6))

    # ---- Summary ----
    summary = tailored_cv.get("summary", "")
    if summary:
        flowables.append(Paragraph("PROFILE", section_heading_style))
        flowables.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#cccccc"), spaceAfter=6))
        flowables.append(Paragraph(summary, body_style))

    # ---- Experience ----
    experience = tailored_cv.get("experience", [])
    if experience:
        flowables.append(Paragraph("EXPERIENCE", section_heading_style))
        flowables.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#cccccc"), spaceAfter=6))
        for role in experience:
            title = role.get("title", "")
            employer = role.get("employer", "")
            dates = role.get("dates", "")
            bullets = role.get("bullets", [])

            flowables.append(Paragraph(title, role_title_style))
            flowables.append(Paragraph(f"{employer}  ·  {dates}", role_meta_style))
            for bullet in bullets:
                flowables.append(Paragraph(f"• {bullet}", bullet_style))
            flowables.append(Spacer(1, 4))

    # ---- Skills ----
    skills = tailored_cv.get("skills", [])
    if skills:
        flowables.append(Paragraph("SKILLS", section_heading_style))
        flowables.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#cccccc"), spaceAfter=6))
        flowables.append(Paragraph("  ·  ".join(skills), skills_style))

    # ---- Education ----
    education = tailored_cv.get("education", [])
    if education:
        flowables.append(Paragraph("EDUCATION", section_heading_style))
        flowables.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#cccccc"), spaceAfter=6))
        for edu in education:
            qualification = edu.get("qualification", "")
            institution = edu.get("institution", "")
            dates = edu.get("dates", "")
            flowables.append(Paragraph(f"<b>{qualification}</b>  ·  {institution}  ·  {dates}", body_style))

    # ---- Certifications ----
    certs = tailored_cv.get("certifications", [])
    if certs:
        flowables.append(Paragraph("CERTIFICATIONS", section_heading_style))
        flowables.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#cccccc"), spaceAfter=6))
        for cert in certs:
            flowables.append(Paragraph(f"• {cert}", bullet_style))

    doc.build(flowables)
    return buffer.getvalue()


def render_cover_letter_pdf(
    text: str, role_title: str = "", company: str = "", candidate_name: str = ""
) -> bytes:
    """
    Generate a clean A4 cover letter PDF using ReportLab.
    No system-level dependencies.
    """
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.lib import colors
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable
    from reportlab.lib.enums import TA_JUSTIFY, TA_LEFT

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=2.5 * cm,
        leftMargin=2.5 * cm,
        topMargin=3 * cm,
        bottomMargin=3 * cm,
    )

    BLACK = colors.HexColor("#1a1a1a")
    GREY = colors.HexColor("#555555")
    INDIGO = colors.HexColor("#4338ca")

    name_style = ParagraphStyle(
        "CLName", fontName="Helvetica-Bold", fontSize=14,
        textColor=BLACK, spaceAfter=2, leading=18,
    )
    meta_style = ParagraphStyle(
        "CLMeta", fontName="Helvetica-Oblique", fontSize=10,
        textColor=GREY, spaceAfter=16, leading=13,
    )
    body_style = ParagraphStyle(
        "CLBody", fontName="Helvetica", fontSize=10.5,
        textColor=BLACK, leading=15, spaceAfter=10, alignment=TA_JUSTIFY,
    )

    flowables = []

    if candidate_name:
        flowables.append(Paragraph(candidate_name, name_style))

    if role_title or company:
        meta_text = " — ".join(filter(None, [role_title, company]))
        flowables.append(Paragraph(f"Re: {meta_text}", meta_style))
        flowables.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#cccccc"), spaceAfter=16))

    # Split on double newlines for paragraphs, single newlines within
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    for para in paragraphs:
        # Replace single newlines within a paragraph with a space
        para_text = para.replace("\n", " ")
        flowables.append(Paragraph(para_text, body_style))

    doc.build(flowables)
    return buffer.getvalue()


# ---------------------------------------------------------------------------
# Internal
# ---------------------------------------------------------------------------


def _esc(text: Any) -> str:
    """HTML-escape a value for safe embedding."""
    import html
    return html.escape(str(text))
