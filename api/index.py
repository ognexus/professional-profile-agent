"""
api/index.py — FastAPI application for the Professional Profile Agent.

Serves both the REST API and the static web frontend (public/).

Endpoints:
  POST /api/assess            — assess one or more candidate PDFs against a JD
  POST /api/curate            — tailor a CV and generate a cover letter
  POST /api/feedback/{t}/{id} — record thumbs-up/down feedback
  GET  /api/cv-pdf/{id}       — download tailored CV as PDF
  GET  /api/cl-pdf/{id}       — download cover letter as PDF
  GET  /health                — health check

Entry point for Vercel (exports `app` as ASGI handler).
Local dev: uvicorn api.index:app --reload
"""

from __future__ import annotations

import sys
import json
import logging
from pathlib import Path
from typing import Optional

# ── Make project root importable ─────────────────────────────────────────────
_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT))

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.core.parsers import (
    parse_pdf, parse_docx, parse_pasted_text, fetch_url_text, detect_input_type
)
from app.assessor.pipeline import AssessorPipeline
from app.curator.pipeline import CuratorPipeline
from app.curator.cv_builder import render_cv_pdf, render_cover_letter_pdf
from app.core import storage
from app.feedback.loop import record_feedback

logger = logging.getLogger(__name__)

# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Professional Profile Agent",
    version="0.3.0",
    docs_url="/api/docs",
    redoc_url=None,
)

# ── Helpers ───────────────────────────────────────────────────────────────────


async def _file_to_text(upload: UploadFile) -> str:
    """Read an uploaded file and return its plain-text content."""
    raw = await upload.read()
    input_type = detect_input_type(upload.filename or "", raw)
    if input_type == "pdf":
        return parse_pdf(raw)
    if input_type == "docx":
        return parse_docx(raw)
    # Plain text / unknown → treat as pasted text
    return parse_pasted_text(raw.decode("utf-8", errors="replace"))


async def _resolve_jd(
    jd_file: Optional[UploadFile],
    jd_url: Optional[str],
    jd_text: Optional[str],
) -> str:
    """Return JD text from the first non-empty source (file > URL > text)."""
    if jd_file and jd_file.filename:
        return await _file_to_text(jd_file)
    if jd_url and jd_url.strip():
        try:
            return fetch_url_text(jd_url.strip())
        except Exception as exc:
            raise HTTPException(status_code=422, detail=f"Could not fetch URL: {exc}")
    if jd_text and jd_text.strip():
        return parse_pasted_text(jd_text)
    raise HTTPException(
        status_code=422,
        detail="Provide a job description via file upload, URL, or pasted text.",
    )


# ── API routes ────────────────────────────────────────────────────────────────


@app.get("/health")
async def health():
    return {"status": "ok", "version": "0.3.0"}


@app.post("/api/assess")
async def assess_candidates(
    candidates: list[UploadFile] = File(...),
    jd_file: Optional[UploadFile] = File(None),
    jd_url: Optional[str] = Form(None),
    jd_text: Optional[str] = Form(None),
):
    """
    Assess one or more candidate PDF profiles against a job description.
    Returns a list of scored assessment results.
    """
    # Resolve JD
    jd = await _resolve_jd(jd_file, jd_url, jd_text)

    # Parse candidate profiles
    candidate_dicts: list[dict] = []
    for upload in candidates:
        if not upload.filename:
            continue
        text = await _file_to_text(upload)
        name = Path(upload.filename).stem.replace("_", " ").replace("-", " ").title()
        candidate_dicts.append({"name": name, "profile_text": text})

    if not candidate_dicts:
        raise HTTPException(status_code=422, detail="No valid candidate files uploaded.")

    try:
        pipeline = AssessorPipeline()
        if len(candidate_dicts) == 1:
            result, record_id = pipeline.assess(
                jd_text=jd,
                candidate_profile_text=candidate_dicts[0]["profile_text"],
            )
            results = [(candidate_dicts[0]["name"], result, record_id)]
        else:
            results = pipeline.assess_batch(jd_text=jd, candidates=candidate_dicts)
    except Exception as exc:
        logger.exception("Assessment pipeline error")
        raise HTTPException(status_code=500, detail=str(exc))

    return JSONResponse(content={
        "results": [
            {
                "candidate_name": name,
                "record_id": record_id,
                "assessment": result.model_dump(),
            }
            for name, result, record_id in results
        ]
    })


@app.post("/api/curate")
async def curate_profile(
    jd_file: Optional[UploadFile] = File(None),
    jd_url: Optional[str] = Form(None),
    jd_text: Optional[str] = Form(None),
    cv_file: Optional[UploadFile] = File(None),
    cv_text: Optional[str] = Form(None),
    linkedin_file: Optional[UploadFile] = File(None),
    linkedin_text: Optional[str] = Form(None),
    user_notes: Optional[str] = Form(None),
):
    """
    Tailor a CV and generate a cover letter for a specific job description.
    """
    jd = await _resolve_jd(jd_file, jd_url, jd_text)

    # CV text
    if cv_file and cv_file.filename:
        cv = await _file_to_text(cv_file)
    elif cv_text and cv_text.strip():
        cv = parse_pasted_text(cv_text)
    else:
        raise HTTPException(status_code=422, detail="Provide your CV via file upload or pasted text.")

    # LinkedIn text (optional but helpful)
    if linkedin_file and linkedin_file.filename:
        linkedin = await _file_to_text(linkedin_file)
    elif linkedin_text and linkedin_text.strip():
        linkedin = parse_pasted_text(linkedin_text)
    else:
        linkedin = ""  # optional

    try:
        pipeline = CuratorPipeline()
        curation, record_id = pipeline.curate(
            jd_text=jd,
            current_cv_text=cv,
            linkedin_text=linkedin,
            user_notes=user_notes or "",
        )
    except Exception as exc:
        logger.exception("Curation pipeline error")
        raise HTTPException(status_code=500, detail=str(exc))

    return JSONResponse(content={
        "record_id": record_id,
        "curation": curation.model_dump(),
    })


@app.post("/api/feedback/{record_type}/{record_id}")
async def submit_feedback(record_type: str, record_id: int, request: Request):
    """
    Record thumbs-up/down feedback for an assessment or curation result.
    Body: {"thumbs_up": true, "comment": "optional note"}
    """
    if record_type not in ("assessment", "curation"):
        raise HTTPException(status_code=422, detail="record_type must be 'assessment' or 'curation'")
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=422, detail="Request body must be JSON")

    thumbs_up: bool = bool(body.get("thumbs_up", True))
    comment: str = str(body.get("comment", ""))

    try:
        record_feedback(
            record_type=record_type,  # type: ignore[arg-type]
            record_id=record_id,
            thumbs_up=thumbs_up,
            comment=comment,
        )
    except Exception as exc:
        logger.exception("Feedback recording error")
        raise HTTPException(status_code=500, detail=str(exc))

    return {"ok": True}


@app.get("/api/cv-pdf/{record_id}")
async def download_cv_pdf(record_id: int):
    """Generate and return the tailored CV as a PDF for a stored curation result."""
    record = storage.get_cv(record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Curation record not found.")

    result_json = record.get("result_json", {})
    tailored_cv = result_json.get("tailored_cv", {})
    jd_extraction = result_json.get("jd_extraction", {})
    role_title = jd_extraction.get("role_title", "")

    try:
        pdf_bytes = render_cv_pdf(tailored_cv, candidate_name="")
    except Exception as exc:
        logger.exception("CV PDF generation error")
        raise HTTPException(status_code=500, detail=str(exc))

    filename = f"CV_{role_title.replace(' ', '_') or 'tailored'}.pdf"
    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/api/cl-pdf/{record_id}")
async def download_cl_pdf(record_id: int):
    """Generate and return the cover letter as a PDF for a stored curation result."""
    record = storage.get_cv(record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Curation record not found.")

    result_json = record.get("result_json", {})
    cover_letter = result_json.get("cover_letter", "")
    jd_extraction = result_json.get("jd_extraction", {})
    role_title = jd_extraction.get("role_title", "")
    company = jd_extraction.get("company", "")

    try:
        pdf_bytes = render_cover_letter_pdf(
            cover_letter, role_title=role_title, company=company
        )
    except Exception as exc:
        logger.exception("Cover letter PDF generation error")
        raise HTTPException(status_code=500, detail=str(exc))

    filename = f"Cover_Letter_{company.replace(' ', '_') or 'letter'}.pdf"
    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ── Static frontend — must be mounted LAST ────────────────────────────────────

_PUBLIC = _ROOT / "public"
if _PUBLIC.exists():
    app.mount("/", StaticFiles(directory=_PUBLIC, html=True), name="static")
