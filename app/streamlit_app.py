"""
streamlit_app.py — Professional Profile Agent UI.

Two tabs:
  Tab 1: Candidate Assessor — assess LinkedIn profiles against a JD
  Tab 2: Profile Curator    — tailor CV and write cover letter for a job

Run with: streamlit run app/streamlit_app.py

Session state keys:
  assessor_results  — persists across tab switches (list of assessment tuples)
  curation_result   — persists across tab switches (curation tuple)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import streamlit as st

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
from app.curator.cv_builder import (
    render_cv_html,
    render_cover_letter_html,
    render_cv_pdf,
    render_cover_letter_pdf,
)
from app.feedback import loop as feedback_loop

# ---------------------------------------------------------------------------
# Page config — must be first Streamlit call
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Professional Profile Agent",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ---------------------------------------------------------------------------
# Global CSS overrides
# Theme is forced to light in .streamlit/config.toml.
# These rules add belt-and-suspenders colour declarations for key components.
# ---------------------------------------------------------------------------

st.markdown("""
<style>
  /* --- Layout --- */
  .block-container { padding-top: 1.5rem; padding-bottom: 2rem; }

  /* --- Recommendation badges --- */
  .score-badge {
    display: inline-block;
    padding: 5px 14px;
    border-radius: 20px;
    font-weight: 700;
    font-size: 0.88rem;
    letter-spacing: 0.3px;
  }
  .badge-strong-yes { background: #16a34a; color: #ffffff; }
  .badge-yes        { background: #2563eb; color: #ffffff; }
  .badge-maybe      { background: #d97706; color: #ffffff; }
  .badge-no         { background: #dc2626; color: #ffffff; }

  /* --- Pillar label above progress bars --- */
  .pillar-label {
    font-size: 0.78rem;
    font-weight: 600;
    color: #374151;
    margin-bottom: 2px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }

  /* --- Evidence quote blocks --- */
  .evidence-quote {
    background-color: #f0f4ff;
    border-left: 3px solid #6366f1;
    padding: 10px 14px;
    margin: 8px 0;
    font-size: 0.88rem;
    border-radius: 0 6px 6px 0;
    color: #1a1a1a;
  }
  .evidence-quote em {
    color: #4b5563;
    display: block;
    margin-top: 4px;
    font-size: 0.82rem;
  }

  /* --- Section dividers --- */
  .candidate-header {
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    padding: 12px 16px;
    margin-bottom: 8px;
  }

  /* --- URL hint text --- */
  .url-hint {
    font-size: 0.78rem;
    color: #6b7280;
    margin-top: -6px;
    margin-bottom: 10px;
  }

  /* --- File list for multi-upload --- */
  .file-list { color: #374151; font-size: 0.88rem; }
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Cached clients and pipelines
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
# Input helpers
# ---------------------------------------------------------------------------

def parse_uploaded_file(uploaded_file) -> str:
    """Parse a single uploaded file to clean plain text."""
    file_bytes = uploaded_file.read()
    input_type = detect_input_type(uploaded_file.name, file_bytes)
    if input_type == "pdf":
        return parse_pdf(file_bytes)
    if input_type == "docx":
        return parse_docx(file_bytes)
    return parse_pasted_text(file_bytes.decode("utf-8", errors="replace"))


def resolve_jd_input(
    uploaded_file, url_input: str, pasted_text: str
) -> tuple[str, str | None]:
    """
    Resolve JD text from whichever source is provided.
    Priority: file > URL > pasted text.
    Returns (text, error_or_None).
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


# ---------------------------------------------------------------------------
# Rendering helpers
# ---------------------------------------------------------------------------

def recommendation_badge(rec: str) -> str:
    labels = {
        "strong_yes": ("Strong Yes", "badge-strong-yes"),
        "yes": ("Yes", "badge-yes"),
        "maybe": ("Maybe", "badge-maybe"),
        "no": ("No", "badge-no"),
    }
    label, cls = labels.get(rec, (rec.replace("_", " ").title(), "badge-maybe"))
    return f'<span class="score-badge {cls}">{label}</span>'


# ---------------------------------------------------------------------------
# Tab 1: Candidate Assessor
# ---------------------------------------------------------------------------

def render_assessor_tab():
    st.header("Candidate Assessor")
    st.caption(
        "Upload candidate LinkedIn profile PDFs and score them against a job description "
        "across Cultural, Operational, and Capability Fit."
    )

    col1, col2 = st.columns([1, 1], gap="large")

    with col1:
        st.subheader("Job Description")

        jd_file = st.file_uploader(
            "Upload JD (PDF or DOCX)",
            type=["pdf", "docx"],
            key="jd_file_assessor",
        )
        jd_url = st.text_input(
            "Or paste a job posting URL",
            key="jd_url_assessor",
            placeholder="https://www.linkedin.com/jobs/view/...",
        )
        st.markdown(
            '<p class="url-hint">LinkedIn, Seek, Indeed, or any company careers page</p>',
            unsafe_allow_html=True,
        )
        jd_text_input = st.text_area(
            "Or paste JD text directly",
            height=150,
            key="jd_text_assessor",
            placeholder="Paste the full job description here...",
        )
        additional_context = st.text_area(
            "Additional context (optional)",
            height=80,
            key="additional_context",
            placeholder="Hiring manager notes, team culture, priorities not in the JD...",
        )

    with col2:
        st.subheader("Candidate Profiles")
        st.caption(
            "Export from LinkedIn: open a profile → More → Save to PDF. "
            "Select multiple files at once."
        )
        candidate_files = st.file_uploader(
            "Upload LinkedIn profile PDFs",
            type=["pdf", "docx"],
            accept_multiple_files=True,
            key="candidate_files",
        )
        if candidate_files:
            st.markdown(
                f'<p class="file-list">📎 {len(candidate_files)} file(s) ready: '
                + ", ".join(f.name for f in candidate_files)
                + "</p>",
                unsafe_allow_html=True,
            )

    run_btn = st.button("▶ Run Assessment", type="primary", use_container_width=True)

    if run_btn:
        # --- Clear previous results so fresh run replaces old ---
        st.session_state.pop("assessor_results", None)

        jd_text, jd_error = resolve_jd_input(jd_file, jd_url, jd_text_input)
        if jd_error:
            st.error(jd_error)
        elif not jd_text.strip():
            st.error("Please provide a job description — upload a file, enter a URL, or paste the text.")
        elif not candidate_files:
            st.error("Please upload at least one candidate LinkedIn profile PDF.")
        else:
            candidate_inputs = []
            for f in candidate_files:
                try:
                    profile_text = parse_uploaded_file(f)
                    if profile_text.strip():
                        name = Path(f.name).stem.replace("_", " ").replace("-", " ").title()
                        candidate_inputs.append({"name": name, "profile_text": profile_text})
                    else:
                        st.warning(f"Skipped {f.name} — no readable text extracted.")
                except Exception as e:
                    st.warning(f"Skipped {f.name} — {e}")

            if not candidate_inputs:
                st.error("None of the uploaded files could be parsed.")
            else:
                try:
                    few_shot = feedback_loop.get_recent_high_quality_examples("assessment", n=2)
                    corrections = feedback_loop.get_recent_corrections("assessment", n=2)
                except Exception:
                    few_shot, corrections = [], []

                pipeline = get_assessor_pipeline()
                n = len(candidate_inputs)
                with st.spinner(
                    f"Analysing {n} candidate{'s' if n > 1 else ''}… "
                    f"approx. {20 * n}–{40 * n} seconds."
                ):
                    results = pipeline.assess_batch(
                        jd_text=jd_text,
                        candidates=candidate_inputs,
                        additional_context=additional_context,
                        few_shot_examples=few_shot or None,
                        avoid_patterns=corrections or None,
                    )

                if results:
                    st.session_state["assessor_results"] = results
                else:
                    st.error("No results returned. Check your inputs and try again.")

    # Always render if results are in session state
    if "assessor_results" in st.session_state:
        _render_assessment_results(st.session_state["assessor_results"])


def _render_assessment_results(results: list):
    st.divider()
    st.subheader("Assessment Results")

    # Summary table
    table_data = []
    for name, assessment, _ in results:
        if assessment is None:
            table_data.append({
                "Candidate": name, "Overall": "Error", "Cultural": "—",
                "Operational": "—", "Capability": "—", "Confidence": "—",
                "Recommendation": "Error",
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

    all_json = [
        {"candidate": name, "result": assessment.model_dump() if assessment else None}
        for name, assessment, _ in results
    ]
    st.download_button(
        "⬇ Download All Results (JSON)",
        data=json.dumps(all_json, indent=2),
        file_name="assessment_results.json",
        mime="application/json",
    )

    st.divider()

    for name, assessment, record_id in results:
        # Candidate header card
        st.markdown(
            f'<div class="candidate-header"><strong>{name}</strong></div>',
            unsafe_allow_html=True,
        )

        if assessment is None:
            st.error(f"Assessment failed for {name}.")
            st.divider()
            continue

        # Top metrics row
        col_score, col_rec, col_conf = st.columns([1, 1, 1])
        with col_score:
            st.metric("Overall Fit", f"{assessment.overall_fit_score}/100")
        with col_rec:
            st.markdown("**Recommendation**")
            st.markdown(recommendation_badge(assessment.recommendation), unsafe_allow_html=True)
        with col_conf:
            st.metric("Confidence", f"{assessment.overall_confidence}%")

        st.caption(assessment.candidate_summary)
        st.markdown("")

        # Pillar scores
        p1, p2, p3 = st.columns(3)
        for col, label, pillar in [
            (p1, "Cultural Fit", assessment.pillars.cultural),
            (p2, "Operational Fit", assessment.pillars.operational),
            (p3, "Capability Fit", assessment.pillars.capability),
        ]:
            with col:
                st.markdown(f'<div class="pillar-label">{label}</div>', unsafe_allow_html=True)
                st.progress(
                    pillar.score / 100,
                    text=f"{pillar.score}/100  ·  confidence {pillar.confidence}%",
                )
                for concern in pillar.concerns:
                    st.caption(f"⚠ {concern}")

        # Evidence
        with st.expander("📋 Evidence quotes"):
            for pillar_label, pillar in [
                ("Cultural", assessment.pillars.cultural),
                ("Operational", assessment.pillars.operational),
                ("Capability", assessment.pillars.capability),
            ]:
                if pillar.evidence:
                    st.markdown(f"**{pillar_label} Fit**")
                    for ev in pillar.evidence:
                        st.markdown(
                            f'<div class="evidence-quote">'
                            f'"{ev.quote}"'
                            f'<em>Source: {ev.source_section} — {ev.interpretation}</em>'
                            f'</div>',
                            unsafe_allow_html=True,
                        )
                    st.markdown("")

        # Strengths / Risks
        sc, rc = st.columns(2)
        with sc:
            if assessment.strengths:
                st.markdown("**✅ Strengths**")
                for s in assessment.strengths:
                    st.markdown(f"- {s}")
        with rc:
            if assessment.risks:
                st.markdown("**⚠ Risks**")
                for r in assessment.risks:
                    st.markdown(f"- {r}")

        if assessment.evidence_gaps:
            with st.expander("🔍 Evidence gaps"):
                for g in assessment.evidence_gaps:
                    st.markdown(f"- {g}")

        if assessment.recommended_interview_questions:
            with st.expander("💬 Recommended interview questions"):
                for i, q in enumerate(assessment.recommended_interview_questions, 1):
                    st.markdown(f"**{i}.** {q}")

        # Feedback
        with st.expander("⭐ Rate this assessment"):
            thumbs = st.radio(
                "Overall quality",
                options=["👍 Thumbs up", "👎 Thumbs down"],
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
                        thumbs_up="up" in thumbs,
                        ratings={"accuracy": accuracy, "usefulness": usefulness},
                        comment=comment,
                    )
                    st.success("Feedback saved — thank you!")
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
        "Every change is grounded in your existing experience — nothing is invented."
    )

    col1, col2 = st.columns([1, 1], gap="large")

    with col1:
        st.subheader("Job Description")
        jd_file = st.file_uploader(
            "Upload JD (PDF or DOCX)",
            type=["pdf", "docx"],
            key="jd_file_curator",
        )
        jd_url = st.text_input(
            "Or paste a job posting URL",
            key="jd_url_curator",
            placeholder="https://www.seek.com.au/job/...",
        )
        st.markdown(
            '<p class="url-hint">LinkedIn, Seek, Indeed, or any company careers page</p>',
            unsafe_allow_html=True,
        )
        jd_text_input = st.text_area(
            "Or paste JD text directly",
            height=150,
            key="jd_text_curator",
            placeholder="Paste the full job description here...",
        )

    with col2:
        st.subheader("Your Profile")
        cv_file = st.file_uploader(
            "Upload your CV (PDF or DOCX)",
            type=["pdf", "docx"],
            key="cv_file",
        )
        cv_text_input = st.text_area(
            "Or paste your CV text",
            height=130,
            key="cv_text",
            placeholder="Paste your current CV here...",
        )
        linkedin_file = st.file_uploader(
            "Upload your LinkedIn PDF (optional)",
            type=["pdf"],
            key="linkedin_file",
            help="Me → View Profile → More → Save to PDF",
        )
        linkedin_text_input = st.text_area(
            "Or paste your LinkedIn profile text (optional)",
            height=90,
            key="linkedin_text",
            placeholder="Paste your LinkedIn profile here...",
        )
        user_notes = st.text_area(
            "Additional notes (optional)",
            height=65,
            key="user_notes",
            placeholder="Things to emphasise, aspects to downplay, any extra context...",
        )

    curate_btn = st.button("✨ Curate My Profile", type="primary", use_container_width=True)

    if curate_btn:
        st.session_state.pop("curation_result", None)

        jd_text, jd_error = resolve_jd_input(jd_file, jd_url, jd_text_input)
        if jd_error:
            st.error(jd_error)
        elif not jd_text.strip():
            st.error("Please provide a job description — upload a file, enter a URL, or paste the text.")
        else:
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
                st.error("Please provide your CV — upload a file or paste the text.")
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

            try:
                few_shot = feedback_loop.get_recent_high_quality_examples("curation", n=2)
                corrections = feedback_loop.get_recent_corrections("curation", n=2)
            except Exception:
                few_shot, corrections = [], []

            pipeline = get_curator_pipeline()
            with st.spinner("Curating your profile… this takes 30–60 seconds."):
                try:
                    curation, record_id = pipeline.curate(
                        jd_text=jd_text,
                        current_cv_text=cv_text,
                        linkedin_text=linkedin_text,
                        user_notes=user_notes,
                        few_shot_examples=few_shot or None,
                        avoid_patterns=corrections or None,
                    )
                    st.session_state["curation_result"] = (curation, record_id)
                except Exception as e:
                    st.error(f"Curation failed: {e}")
                    return

    # Always render if results are in session state
    if "curation_result" in st.session_state:
        curation, record_id = st.session_state["curation_result"]
        _render_curation_results(curation, record_id)


def _render_curation_results(curation, record_id: int):
    st.divider()
    st.subheader("Curation Results")

    role = curation.jd_extraction.role_title
    company = curation.jd_extraction.company or ""
    target = f"**{role}**" + (f" at **{company}**" if company else "")
    st.caption(f"Tailored for: {target}")

    gap_tab, cv_tab, cl_tab = st.tabs(["📊 Gap Analysis", "📄 Tailored CV", "✉ Cover Letter"])

    with gap_tab:
        _render_gap_analysis(curation.gap_analysis)

    with cv_tab:
        _render_tailored_cv(curation, record_id, role, company)

    with cl_tab:
        _render_cover_letter(curation, record_id, role, company)

    if curation.rationale_log:
        with st.expander("💡 Why these changes? (Rationale log)"):
            for entry in curation.rationale_log:
                st.markdown(f"**Change:** {entry.change}")
                st.markdown(f"**Reason:** {entry.reason}")
                st.markdown(f"**Evidence:** _{entry.evidence}_")
                st.divider()

    with st.expander("⭐ Rate this curation"):
        thumbs = st.radio(
            "Overall quality",
            options=["👍 Thumbs up", "👎 Thumbs down"],
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
                    thumbs_up="up" in thumbs,
                    ratings={"accuracy": accuracy, "usefulness": usefulness},
                    comment=comment,
                )
                st.success("Feedback saved — thank you!")
            except Exception as e:
                st.error(f"Could not save feedback: {e}")


def _render_gap_analysis(gap_analysis):
    strong = gap_analysis.strong_matches
    partial = gap_analysis.partial_matches
    missing = gap_analysis.missing

    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("✅ Strong Matches", len(strong))
    with c2:
        st.metric("🟡 Partial Matches", len(partial))
    with c3:
        critical = sum(1 for m in missing if m.impact == "critical")
        st.metric(
            "🔴 Missing",
            len(missing),
            delta=f"{critical} critical" if critical else None,
            delta_color="inverse",
        )

    if strong:
        st.markdown("**Strong Matches**")
        for m in strong:
            st.markdown(f"- ✅ **{m.requirement}** — {m.evidence_summary}")

    if partial:
        st.markdown("**Partial Matches**")
        for m in partial:
            st.markdown(f"- 🟡 **{m.requirement}**: {m.what_exists} _(gap: {m.what_is_missing})_")

    if missing:
        st.markdown("**Missing Requirements**")
        for m in missing:
            icon = {"critical": "🔴", "moderate": "🟡", "low": "🟢"}.get(m.impact, "•")
            st.markdown(f"- {icon} **{m.requirement}** ({m.impact} impact)")


def _render_tailored_cv(curation, record_id: int, role: str, company: str):
    cv_dict = curation.tailored_cv.model_dump()
    cv_html = render_cv_html(cv_dict)

    st.markdown("**Preview**")
    st.components.v1.html(cv_html, height=620, scrolling=True)

    dl1, dl2, dl3 = st.columns(3)

    with dl1:
        st.download_button(
            "⬇ Download CV (HTML)",
            data=cv_html.encode("utf-8"),
            file_name=f"cv_{role.replace(' ', '_')[:30]}.html",
            mime="text/html",
            key=f"cv_html_dl_{record_id}",
            use_container_width=True,
        )

    with dl2:
        try:
            pdf_bytes = render_cv_pdf(cv_dict)
            st.download_button(
                "⬇ Download CV (PDF)",
                data=pdf_bytes,
                file_name=f"cv_{role.replace(' ', '_')[:30]}.pdf",
                mime="application/pdf",
                key=f"cv_pdf_dl_{record_id}",
                use_container_width=True,
            )
        except Exception as e:
            st.caption(f"PDF generation error: {e}")

    with dl3:
        st.info("💡 Tip: You can also print the HTML preview to PDF from your browser (Ctrl+P / Cmd+P).", icon=None)


def _render_cover_letter(curation, record_id: int, role: str, company: str):
    cl_text = st.text_area(
        "Cover letter (editable — make it your own)",
        value=curation.cover_letter,
        height=360,
        key=f"cl_text_{record_id}",
    )

    word_count = len(cl_text.split())
    if 200 <= word_count <= 400:
        st.success(f"{word_count} words — ideal length ✓", icon=None)
    else:
        st.warning(f"{word_count} words — aim for 250–350 words")

    dl1, dl2, dl3 = st.columns(3)

    with dl1:
        cl_html = render_cover_letter_html(cl_text, role_title=role, company=company)
        st.download_button(
            "⬇ Download Cover Letter (HTML)",
            data=cl_html.encode("utf-8"),
            file_name=f"cover_letter_{role.replace(' ', '_')[:30]}.html",
            mime="text/html",
            key=f"cl_html_dl_{record_id}",
            use_container_width=True,
        )

    with dl2:
        try:
            cl_pdf = render_cover_letter_pdf(cl_text, role_title=role, company=company)
            st.download_button(
                "⬇ Download Cover Letter (PDF)",
                data=cl_pdf,
                file_name=f"cover_letter_{role.replace(' ', '_')[:30]}.pdf",
                mime="application/pdf",
                key=f"cl_pdf_dl_{record_id}",
                use_container_width=True,
            )
        except Exception as e:
            st.caption(f"PDF generation error: {e}")

    with dl3:
        st.info("💡 Edit the letter above before downloading — make it sound like you.", icon=None)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def main():
    st.title("Professional Profile Agent")
    st.caption("AI-powered candidate assessment and CV curation, powered by Claude (Anthropic).")

    # Early API key check with a clear, actionable error
    try:
        _ = settings.anthropic_api_key
    except KeyError as e:
        st.error(str(e))
        st.stop()

    tab1, tab2 = st.tabs(["🔍 Candidate Assessor", "✨ Profile Curator"])

    with tab1:
        render_assessor_tab()

    with tab2:
        render_curator_tab()


if __name__ == "__main__":
    main()
