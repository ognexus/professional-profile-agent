"""
streamlit_app.py — Professional Profile Agent UI.

Two tabs:
  Tab 1: Candidate Assessor — assess LinkedIn profiles against a JD
  Tab 2: Profile Curator    — tailor CV and write cover letter for a job

Run with: streamlit run app/streamlit_app.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import streamlit as st

# Ensure project root is on path when running from any directory
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import settings
from app.core.claude_client import ClaudeClient
from app.core.parsers import (
    parse_pdf,
    parse_docx,
    parse_pasted_text,
    detect_input_type,
    fetch_url_text,
)
from app.assessor.pipeline import AssessorPipeline
from app.assessor.schemas import AssessmentResult
from app.curator.pipeline import CuratorPipeline
from app.curator.cv_builder import render_cv_html, render_cover_letter_html, render_cv_pdf
from app.feedback import loop as feedback_loop

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Professional Profile Agent",
    page_icon="",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ---------------------------------------------------------------------------
# Shared styles
# ---------------------------------------------------------------------------

st.markdown("""
<style>
  .block-container { padding-top: 2rem; }
  .score-badge {
    display: inline-block;
    padding: 4px 12px;
    border-radius: 12px;
    font-weight: 700;
    font-size: 0.85rem;
    margin-right: 6px;
  }
  .badge-strong-yes { background: #16a34a; color: white; }
  .badge-yes        { background: #2563eb; color: white; }
  .badge-maybe      { background: #d97706; color: white; }
  .badge-no         { background: #dc2626; color: white; }
  .pillar-label { font-size: 0.8rem; color: #6b7280; margin-bottom: 2px; }
  .evidence-quote {
    background: #f3f4f6;
    border-left: 3px solid #6366f1;
    padding: 8px 12px;
    margin: 6px 0;
    font-size: 0.88rem;
    border-radius: 0 4px 4px 0;
  }
  .url-hint { font-size: 0.78rem; color: #9ca3af; margin-top: -8px; margin-bottom: 8px; }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Client init (cached)
# ---------------------------------------------------------------------------

@st.cache_resource
def get_client() -> ClaudeClient:
    return ClaudeClient()

@st.cache_resource
def get_assessor_pipeline() -> AssessorPipeline:
    return AssessorPipeline(get_client())

@st.cache_resource
def get_curator_pipeline() -> CuratorPipeline:
    return CuratorPipeline(get_client())

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def parse_uploaded_file(uploaded_file) -> str:
    """Parse a single uploaded file to plain text."""
    file_bytes = uploaded_file.read()
    input_type = detect_input_type(uploaded_file.name, file_bytes)
    if input_type == "pdf":
        return parse_pdf(file_bytes)
    elif input_type == "docx":
        return parse_docx(file_bytes)
    return parse_pasted_text(file_bytes.decode("utf-8", errors="replace"))


def resolve_jd_input(
    uploaded_file,
    url_input: str,
    pasted_text: str,
) -> tuple[str, str | None]:
    """
    Resolve the JD from whichever input is provided.
    Priority: uploaded file > URL > pasted text.

    Returns:
        (jd_text, error_message_or_None)
    """
    if uploaded_file is not None:
        try:
            return parse_uploaded_file(uploaded_file), None
        except Exception as e:
            return "", f"Could not parse uploaded file: {e}"

    if url_input.strip():
        try:
            text = fetch_url_text(url_input.strip())
            if not text.strip():
                return "", "The URL returned no readable content. Try pasting the JD text directly."
            return text, None
        except Exception as e:
            return "", f"Could not fetch URL: {e}"

    return parse_pasted_text(pasted_text), None


def recommendation_badge(rec: str) -> str:
    labels = {
        "strong_yes": ("Strong Yes", "badge-strong-yes"),
        "yes": ("Yes", "badge-yes"),
        "maybe": ("Maybe", "badge-maybe"),
        "no": ("No", "badge-no"),
    }
    label, cls = labels.get(rec, (rec, "badge-maybe"))
    return f'<span class="score-badge {cls}">{label}</span>'


# ---------------------------------------------------------------------------
# Tab 1: Candidate Assessor
# ---------------------------------------------------------------------------

def render_assessor_tab():
    st.header("Candidate Assessor")
    st.caption(
        "Upload candidate LinkedIn profile PDFs and assess them against a job description "
        "across Cultural, Operational, and Capability Fit."
    )

    col1, col2 = st.columns([1, 1])

    # ---- Left column: Job Description ----
    with col1:
        st.subheader("Job Description")

        jd_file = st.file_uploader(
            "Upload JD (PDF or DOCX)",
            type=["pdf", "docx"],
            key="jd_file_assessor",
            help="Upload a PDF or Word document of the job description.",
        )

        jd_url = st.text_input(
            "Or enter the job posting URL",
            key="jd_url_assessor",
            placeholder="https://www.linkedin.com/jobs/view/...",
        )
        st.markdown(
            '<div class="url-hint">Paste a link to the job posting — '
            'LinkedIn, Seek, Indeed, company careers page, etc.</div>',
            unsafe_allow_html=True,
        )

        jd_text_input = st.text_area(
            "Or paste JD text directly",
            height=160,
            key="jd_text_assessor",
            placeholder="Paste the full job description here as a fallback...",
        )

        additional_context = st.text_area(
            "Additional context (optional)",
            height=80,
            key="additional_context",
            placeholder="Hiring manager notes, team culture, priorities not captured in the JD...",
        )

    # ---- Right column: Candidates ----
    with col2:
        st.subheader("Candidate Profiles")
        st.caption(
            "Upload one or more LinkedIn profile PDFs. "
            "Each file is treated as one candidate."
        )

        candidate_files = st.file_uploader(
            "Upload LinkedIn profile PDFs",
            type=["pdf", "docx"],
            accept_multiple_files=True,
            key="candidate_files",
            help=(
                "Export profiles from LinkedIn: open a profile → More → Save to PDF. "
                "You can select multiple files at once."
            ),
        )

        if candidate_files:
            st.caption(f"{len(candidate_files)} file(s) selected:")
            for f in candidate_files:
                st.markdown(f"- {f.name}")

    # ---- Run ----
    run_btn = st.button("Run Assessment", type="primary", use_container_width=True)

    if run_btn:
        # Resolve JD
        jd_text, jd_error = resolve_jd_input(jd_file, jd_url, jd_text_input)
        if jd_error:
            st.error(jd_error)
            return
        if not jd_text.strip():
            st.error("Please provide a job description — upload a file, enter a URL, or paste the text.")
            return

        # Resolve candidates
        if not candidate_files:
            st.error("Please upload at least one candidate PDF.")
            return

        candidate_inputs = []
        parse_errors = []
        for f in candidate_files:
            try:
                profile_text = parse_uploaded_file(f)
                if profile_text.strip():
                    # Use filename (without extension) as the candidate label
                    name = Path(f.name).stem.replace("_", " ").replace("-", " ").title()
                    candidate_inputs.append({"name": name, "profile_text": profile_text})
                else:
                    parse_errors.append(f"{f.name}: no readable text extracted")
            except Exception as e:
                parse_errors.append(f"{f.name}: {e}")

        if parse_errors:
            for err in parse_errors:
                st.warning(f"Skipped — {err}")

        if not candidate_inputs:
            st.error("None of the uploaded files could be parsed. Please check the files and try again.")
            return

        # Load feedback examples for self-improvement
        try:
            few_shot = feedback_loop.get_recent_high_quality_examples("assessment", n=2)
            corrections = feedback_loop.get_recent_corrections("assessment", n=2)
        except Exception:
            few_shot, corrections = [], []

        pipeline = get_assessor_pipeline()
        n = len(candidate_inputs)
        with st.spinner(
            f"Analysing {n} candidate{'s' if n > 1 else ''}... "
            f"approx. {20 * n}–{40 * n} seconds."
        ):
            results = pipeline.assess_batch(
                jd_text=jd_text,
                candidates=candidate_inputs,
                additional_context=additional_context,
                few_shot_examples=few_shot or None,
                avoid_patterns=corrections or None,
            )

        if not results:
            st.error("No results returned. Check your inputs and try again.")
            return

        _render_assessment_results(results)


def _render_assessment_results(results: list[tuple[str, AssessmentResult | None, int]]):
    st.divider()
    st.subheader("Assessment Results")

    # Summary table
    table_data = []
    for name, assessment, _ in results:
        if assessment is None:
            table_data.append({
                "Candidate": name, "Overall": "Error",
                "Cultural": "-", "Operational": "-", "Capability": "-",
                "Confidence": "-", "Recommendation": "Error",
            })
        else:
            table_data.append({
                "Candidate": name,
                "Overall": f"{assessment.overall_fit_score}/100",
                "Cultural": f"{assessment.pillars.cultural.score}/100",
                "Operational": f"{assessment.pillars.operational.score}/100",
                "Capability": f"{assessment.pillars.capability.score}/100",
                "Confidence": f"{assessment.overall_confidence}%",
                "Recommendation": assessment.recommendation.replace("_", " ").title(),
            })

    st.dataframe(table_data, use_container_width=True, hide_index=True)

    # JSON download
    all_results_json = [
        {"candidate": name, "result": assessment.model_dump() if assessment else None}
        for name, assessment, _ in results
    ]
    st.download_button(
        "Download All Results (JSON)",
        data=json.dumps(all_results_json, indent=2),
        file_name="assessment_results.json",
        mime="application/json",
    )

    st.divider()

    # Per-candidate detail cards
    for name, assessment, record_id in results:
        st.markdown(f"### {name}")

        if assessment is None:
            st.error(f"Assessment failed for {name}.")
            continue

        # Header metrics
        col_score, col_rec, col_conf = st.columns([1, 1, 1])
        with col_score:
            st.metric("Overall Fit", f"{assessment.overall_fit_score}/100")
        with col_rec:
            st.markdown(recommendation_badge(assessment.recommendation), unsafe_allow_html=True)
        with col_conf:
            st.metric("Confidence", f"{assessment.overall_confidence}%")

        st.caption(assessment.candidate_summary)

        # Pillar progress bars
        pillars_col1, pillars_col2, pillars_col3 = st.columns(3)
        for col, pillar_name, pillar in [
            (pillars_col1, "Cultural Fit", assessment.pillars.cultural),
            (pillars_col2, "Operational Fit", assessment.pillars.operational),
            (pillars_col3, "Capability Fit", assessment.pillars.capability),
        ]:
            with col:
                st.markdown(f'<div class="pillar-label">{pillar_name}</div>', unsafe_allow_html=True)
                st.progress(
                    pillar.score / 100,
                    text=f"{pillar.score}/100  (confidence: {pillar.confidence}%)",
                )
                for concern in pillar.concerns:
                    st.caption(f"Concern: {concern}")

        # Evidence
        with st.expander("Evidence quotes"):
            for pillar_name, pillar in [
                ("Cultural", assessment.pillars.cultural),
                ("Operational", assessment.pillars.operational),
                ("Capability", assessment.pillars.capability),
            ]:
                if pillar.evidence:
                    st.markdown(f"**{pillar_name} Fit**")
                    for ev in pillar.evidence:
                        st.markdown(
                            f'<div class="evidence-quote">"{ev.quote}"<br/>'
                            f'<em>Source: {ev.source_section} — {ev.interpretation}</em></div>',
                            unsafe_allow_html=True,
                        )

        # Strengths / Risks
        str_col, risk_col = st.columns(2)
        with str_col:
            if assessment.strengths:
                st.markdown("**Strengths**")
                for s in assessment.strengths:
                    st.markdown(f"- {s}")
        with risk_col:
            if assessment.risks:
                st.markdown("**Risks**")
                for r in assessment.risks:
                    st.markdown(f"- {r}")

        if assessment.evidence_gaps:
            with st.expander("Evidence gaps"):
                for g in assessment.evidence_gaps:
                    st.markdown(f"- {g}")

        if assessment.recommended_interview_questions:
            with st.expander("Recommended interview questions"):
                for i, q in enumerate(assessment.recommended_interview_questions, 1):
                    st.markdown(f"{i}. {q}")

        # Feedback widget
        with st.expander("Rate this assessment"):
            thumbs = st.radio(
                "Overall quality",
                options=["Thumbs up", "Thumbs down"],
                key=f"thumbs_{record_id}",
                horizontal=True,
            )
            accuracy = st.slider("Accuracy", 1, 5, 3, key=f"acc_{record_id}")
            usefulness = st.slider("Usefulness", 1, 5, 3, key=f"use_{record_id}")
            comment = st.text_area("Comment (optional)", key=f"comment_{record_id}")
            if st.button("Submit feedback", key=f"fb_btn_{record_id}"):
                try:
                    feedback_loop.record_feedback(
                        record_type="assessment",
                        record_id=record_id,
                        thumbs_up=(thumbs == "Thumbs up"),
                        ratings={"accuracy": accuracy, "usefulness": usefulness},
                        comment=comment,
                    )
                    st.success("Feedback saved.")
                except Exception as e:
                    st.error(f"Could not save feedback: {e}")

        st.divider()


# ---------------------------------------------------------------------------
# Tab 2: Profile Curator
# ---------------------------------------------------------------------------

def render_curator_tab():
    st.header("Profile Curator")
    st.caption(
        "Tailor your CV and generate a cover letter for a specific job. "
        "Grounded entirely in your existing experience — no hallucination."
    )

    col1, col2 = st.columns([1, 1])

    # ---- Left column: Job Description ----
    with col1:
        st.subheader("Job Description")

        jd_file = st.file_uploader(
            "Upload JD (PDF or DOCX)",
            type=["pdf", "docx"],
            key="jd_file_curator",
            help="Upload a PDF or Word document of the job description.",
        )

        jd_url = st.text_input(
            "Or enter the job posting URL",
            key="jd_url_curator",
            placeholder="https://www.seek.com.au/job/...",
        )
        st.markdown(
            '<div class="url-hint">Paste a link to the job posting — '
            'LinkedIn, Seek, Indeed, company careers page, etc.</div>',
            unsafe_allow_html=True,
        )

        jd_text_input = st.text_area(
            "Or paste JD text directly",
            height=160,
            key="jd_text_curator",
            placeholder="Paste the full job description here as a fallback...",
        )

    # ---- Right column: Your Profile ----
    with col2:
        st.subheader("Your Profile")

        cv_file = st.file_uploader(
            "Upload your CV (PDF or DOCX)",
            type=["pdf", "docx"],
            key="cv_file",
        )
        cv_text_input = st.text_area(
            "Or paste your CV text",
            height=140,
            key="cv_text",
            placeholder="Paste your current CV here...",
        )

        linkedin_file = st.file_uploader(
            "Upload your LinkedIn PDF (optional)",
            type=["pdf"],
            key="linkedin_file",
            help="Export from LinkedIn: Me → View Profile → More → Save to PDF",
        )
        linkedin_text_input = st.text_area(
            "Or paste your LinkedIn profile text (optional)",
            height=100,
            key="linkedin_text",
            placeholder="Paste your LinkedIn profile here to supplement your CV...",
        )

        user_notes = st.text_area(
            "Additional notes (optional)",
            height=70,
            key="user_notes",
            placeholder="Things to emphasise, aspects to downplay, context the tool should know...",
        )

    curate_btn = st.button("Curate My Profile", type="primary", use_container_width=True)

    if curate_btn:
        # Resolve JD
        jd_text, jd_error = resolve_jd_input(jd_file, jd_url, jd_text_input)
        if jd_error:
            st.error(jd_error)
            return
        if not jd_text.strip():
            st.error("Please provide a job description — upload a file, enter a URL, or paste the text.")
            return

        # Resolve CV
        cv_text = ""
        if cv_file is not None:
            try:
                cv_text = parse_uploaded_file(cv_file)
            except Exception as e:
                st.error(f"Could not parse CV file: {e}")
                return
        if not cv_text.strip():
            cv_text = parse_pasted_text(cv_text_input)
        if not cv_text.strip():
            st.error("Please provide your current CV — upload a file or paste the text.")
            return

        # Resolve LinkedIn (optional)
        linkedin_text = ""
        if linkedin_file is not None:
            try:
                linkedin_text = parse_uploaded_file(linkedin_file)
            except Exception as e:
                st.warning(f"Could not parse LinkedIn file: {e} — continuing without it.")
        if not linkedin_text.strip():
            linkedin_text = parse_pasted_text(linkedin_text_input)

        pipeline = get_curator_pipeline()

        try:
            few_shot = feedback_loop.get_recent_high_quality_examples("curation", n=2)
            corrections = feedback_loop.get_recent_corrections("curation", n=2)
        except Exception:
            few_shot, corrections = [], []

        with st.spinner("Curating your profile... this takes 30–60 seconds."):
            try:
                curation, record_id = pipeline.curate(
                    jd_text=jd_text,
                    current_cv_text=cv_text,
                    linkedin_text=linkedin_text,
                    user_notes=user_notes,
                    few_shot_examples=few_shot or None,
                    avoid_patterns=corrections or None,
                )
            except Exception as e:
                st.error(f"Curation failed: {e}")
                return

        _render_curation_results(curation, record_id)


def _render_curation_results(curation, record_id: int):
    st.divider()
    st.subheader("Curation Results")

    role = curation.jd_extraction.role_title
    company = curation.jd_extraction.company or ""
    st.caption(f"Tailored for: **{role}**" + (f" at **{company}**" if company else ""))

    gap_tab, cv_tab, cl_tab = st.tabs(["Gap Analysis", "Tailored CV", "Cover Letter"])

    with gap_tab:
        _render_gap_analysis(curation.gap_analysis)

    with cv_tab:
        _render_tailored_cv(curation, record_id, role, company)

    with cl_tab:
        _render_cover_letter(curation, record_id, role, company)

    if curation.rationale_log:
        with st.expander("Why these changes? (Rationale log)"):
            for entry in curation.rationale_log:
                st.markdown(f"**Change:** {entry.change}")
                st.markdown(f"**Reason:** {entry.reason}")
                st.markdown(f"**Evidence:** _{entry.evidence}_")
                st.divider()

    with st.expander("Rate this curation"):
        thumbs = st.radio(
            "Overall quality",
            options=["Thumbs up", "Thumbs down"],
            key=f"cur_thumbs_{record_id}",
            horizontal=True,
        )
        accuracy = st.slider("Accuracy (stayed truthful?)", 1, 5, 3, key=f"cur_acc_{record_id}")
        usefulness = st.slider("Usefulness (helped your application?)", 1, 5, 3, key=f"cur_use_{record_id}")
        comment = st.text_area("Comment (optional)", key=f"cur_comment_{record_id}")
        if st.button("Submit feedback", key=f"cur_fb_btn_{record_id}"):
            try:
                feedback_loop.record_feedback(
                    record_type="curation",
                    record_id=record_id,
                    thumbs_up=(thumbs == "Thumbs up"),
                    ratings={"accuracy": accuracy, "usefulness": usefulness},
                    comment=comment,
                )
                st.success("Feedback saved.")
            except Exception as e:
                st.error(f"Could not save feedback: {e}")


def _render_gap_analysis(gap_analysis):
    strong = gap_analysis.strong_matches
    partial = gap_analysis.partial_matches
    missing = gap_analysis.missing

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Strong Matches", len(strong))
    with col2:
        st.metric("Partial Matches", len(partial))
    with col3:
        critical_count = sum(1 for m in missing if m.impact == "critical")
        st.metric(
            "Missing",
            len(missing),
            delta=f"{critical_count} critical" if critical_count else None,
            delta_color="inverse",
        )

    if strong:
        st.markdown("**Strong Matches**")
        for m in strong:
            st.markdown(f"- **{m.requirement}** — {m.evidence_summary}")

    if partial:
        st.markdown("**Partial Matches**")
        for m in partial:
            st.markdown(f"- **{m.requirement}**: {m.what_exists} _(gap: {m.what_is_missing})_")

    if missing:
        st.markdown("**Missing Requirements**")
        for m in missing:
            icon = {"critical": "🔴", "moderate": "🟡", "low": "🟢"}.get(m.impact, "")
            st.markdown(f"- {icon} **{m.requirement}** ({m.impact} impact)")


def _render_tailored_cv(curation, record_id: int, role: str, company: str):
    cv_html = render_cv_html(curation.tailored_cv.model_dump())

    st.markdown("**Preview**")
    st.components.v1.html(cv_html, height=600, scrolling=True)

    col1, col2 = st.columns(2)
    with col1:
        st.download_button(
            "Download CV (HTML)",
            data=cv_html.encode("utf-8"),
            file_name=f"cv_tailored_{role.replace(' ', '_')[:30]}.html",
            mime="text/html",
            key=f"cv_html_dl_{record_id}",
        )
    with col2:
        try:
            pdf_bytes = render_cv_pdf(cv_html)
            if pdf_bytes:
                st.download_button(
                    "Download CV (PDF)",
                    data=pdf_bytes,
                    file_name=f"cv_tailored_{role.replace(' ', '_')[:30]}.pdf",
                    mime="application/pdf",
                    key=f"cv_pdf_dl_{record_id}",
                )
        except Exception:
            st.caption("PDF export requires weasyprint: `pip install weasyprint`")


def _render_cover_letter(curation, record_id: int, role: str, company: str):
    cl_text = st.text_area(
        "Cover letter (editable)",
        value=curation.cover_letter,
        height=350,
        key=f"cl_text_{record_id}",
    )

    word_count = len(cl_text.split())
    colour = "green" if 200 <= word_count <= 400 else "red"
    st.markdown(
        f'<span style="color:{colour}; font-size:0.85rem;">{word_count} words</span>',
        unsafe_allow_html=True,
    )

    cl_html = render_cover_letter_html(cl_text, role_title=role, company=company)
    st.download_button(
        "Download Cover Letter (HTML)",
        data=cl_html.encode("utf-8"),
        file_name=f"cover_letter_{role.replace(' ', '_')[:30]}.html",
        mime="text/html",
        key=f"cl_html_dl_{record_id}",
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    st.title("Professional Profile Agent")
    st.caption("AI-powered candidate assessment and CV curation, powered by Claude.")

    # Check API key early — surface a clear error rather than a cryptic crash
    try:
        _ = settings.anthropic_api_key
    except (KeyError, AttributeError):
        st.error(
            "ANTHROPIC_API_KEY not found. Copy `.env.example` to `.env`, "
            "add your key, and restart the app."
        )
        st.stop()

    tab1, tab2 = st.tabs(["Candidate Assessor", "Profile Curator"])

    with tab1:
        render_assessor_tab()

    with tab2:
        render_curator_tab()


if __name__ == "__main__":
    main()
