# Changelog

## v0.1.0 — 2026-04-16

Initial build. Full v1 implementation of both use cases.

### What's In This Build

**Use Case 1: Candidate Assessor**
- Three-pillar assessment framework: Cultural Fit, Operational Fit, Capability Fit
- Evidence-grounded scoring — every score backed by verbatim quotes from the profile
- Confidence scoring — reflects how much evidence was available, not just fit quality
- Recommendation output: `strong_yes`, `yes`, `maybe`, `no`
- Recommended interview questions targeted at specific gaps and risks
- Batch assessment — up to 10 candidates in a single session
- Summary table with sortable results across candidates
- JSON export of all results
- Per-assessment feedback widget (thumbs up/down, star ratings, free text)

**Use Case 2: Profile Curator**
- Gap analysis: strong matches / partial matches / missing requirements
- Tailored CV — reframed, reordered, emphasis-adjusted — strictly within source facts
- Cover letter — 250–350 words, evidence-based, anti-cliché enforced
- Rationale log — explains every non-trivial change with source evidence
- HTML CV preview in-app
- HTML + PDF download (PDF requires weasyprint)
- Editable cover letter text area with word count indicator

**Infrastructure**
- `ClaudeClient` wrapper with JSON mode and prompt caching
- Input parsers for PDF, DOCX, and pasted text with LinkedIn section extractor
- SQLite persistence for assessments and CV curations
- Feedback loop: in-context few-shot learning from past rated outputs
- Pydantic schema validation with automatic retry on schema failure
- Streamlit UI with two tabs, error handling, and spinner states

**Skills and Prompts**
- `skills/candidate_analysis/SKILL.md` + `rubric.md`
- `skills/profile_curation/SKILL.md` + `cv_principles.md`
- `skills/jd_parsing/SKILL.md`
- `agents/recruiter_persona.md`
- `agents/career_coach_persona.md`

**Testing**
- 19 unit tests for parsers (`pytest tests/test_parsers.py`)
- 7 unit tests for assessor pipeline with mocked client (`pytest tests/test_assessor.py`)
- 11 unit tests for curator pipeline and CV builder (`pytest tests/test_curator.py`)
- 6 eval test cases with real API (`pytest -m eval tests/test_eval.py`)
- 3 JD golden cases (tech IC, consulting, education)
- 3 strong-fit candidate profiles
- 3 weak-fit candidate profiles
- 2 user CV profiles for curator eval

**Documentation**
- `README.md` — architecture, quickstart, design philosophy, limitations, roadmap
- `docs/SKILLS_GUIDE.md` — how skills work, how to edit and add them safely
- `docs/PROMPT_ENGINEERING_NOTES.md` — design decisions behind the prompt architecture
- `CHANGELOG.md` — this file

### Known Limitations

- No LinkedIn scraping — inputs must be pasted or uploaded manually
- Single-user — no authentication or session isolation
- English language only
- PDF export requires weasyprint (install separately: `pip install weasyprint`)
- Batch assessment is sequential — no concurrency in v1

### Roadmap (v0.2+)

- Concurrent batch assessment
- CSV bulk upload for candidate lists
- Multi-user authentication
- ATS webhooks (Greenhouse, Lever)
- Browser extension for one-click LinkedIn PDF capture
- Proxycurl API integration as optional data source
