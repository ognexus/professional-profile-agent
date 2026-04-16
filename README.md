# Professional Profile Agent

> AI-powered candidate assessment and CV curation, built on [Claude](https://anthropic.com) by Anthropic.

A local, privacy-first tool with two capabilities:

| Use Case | What it does |
|----------|-------------|
| **Candidate Assessor** | Upload multiple LinkedIn profile PDFs and score them against a job description across Cultural, Operational, and Capability Fit — with evidence quotes, confidence scores, and recommended interview questions |
| **Profile Curator** | Tailor your CV and generate a cover letter for a specific job, grounded strictly in your existing experience. No hallucination — every change is cited and explained |

---

## Quickstart

### 1. Clone and install

```bash
git clone https://github.com/ognexus/professional-profile-agent.git
cd professional-profile-agent
pip install -r requirements.txt
```

### 2. Configure your API key

```bash
cp .env.example .env
# Open .env and add your ANTHROPIC_API_KEY
```

Get a key at [console.anthropic.com](https://console.anthropic.com).

### 3. Run locally

```bash
uvicorn api.index:app --reload
```

The app opens at `http://localhost:8000`.

---

## Features

### Candidate Assessor (Tab 1)

- **Multi-file upload** — drop in multiple LinkedIn profile PDFs at once; each is assessed independently
- **Flexible JD input** — paste a job posting URL (LinkedIn, Seek, Indeed, company careers page), upload a PDF/DOCX, or paste text directly
- **Three-pillar analysis** across Cultural Fit, Operational Fit, and Capability Fit
- **Evidence-grounded scoring** — every score is backed by verbatim quotes from the candidate's profile; no generic praise
- **Confidence scores** — separate score reflecting how much usable evidence was available
- **Recommendations** — `Strong Yes / Yes / Maybe / No` with reasoning
- **Interview questions** — targeted at the specific gaps found in each profile
- **Summary comparison table** — sort candidates side-by-side by any dimension
- **JSON export** of all results
- **Feedback loop** — rate each assessment; top-rated outputs improve future analyses automatically (in-context learning)

### Profile Curator (Tab 2)

- **Flexible JD input** — URL, PDF/DOCX upload, or pasted text
- **Gap analysis** — strong matches, partial matches, and missing requirements with impact classification
- **Tailored CV** — same facts, reframed in the JD's vocabulary, reordered by relevance
- **Cover letter** — 250–350 words, evidence-based, no AI clichés, editable in-app
- **Rationale log** — every non-trivial CV change explained with the source evidence behind it
- **HTML + PDF download** for CV and cover letter
- **Feedback loop** — rate curations to improve future outputs

---

## Architecture

```
profile-agent/
├── app/
│   ├── streamlit_app.py        # Two-tab Streamlit UI
│   ├── config.py               # Environment & settings
│   ├── core/
│   │   ├── claude_client.py    # Anthropic SDK wrapper (JSON mode + prompt caching)
│   │   ├── parsers.py          # PDF / DOCX / URL / text → plain text
│   │   └── storage.py          # SQLite persistence
│   ├── assessor/               # Use Case 1 — pipeline + Pydantic schemas
│   ├── curator/                # Use Case 2 — pipeline + CV/PDF builder
│   └── feedback/               # In-context self-improvement loop
│
├── skills/                     # The intelligence lives here — plain markdown
│   ├── candidate_analysis/     # Assessment rubric, 3-pillar definitions, scoring anchors
│   ├── profile_curation/       # Curation process, hard prohibitions, CV principles
│   └── jd_parsing/             # Structured JD extraction
│
├── agents/                     # Recruiter and career coach persona definitions
├── prompts/                    # Assembled system prompt templates
├── tests/
│   ├── eval_cases/             # 3 JDs × 6 candidate profiles × 2 user CVs (golden test data)
│   ├── test_parsers.py         # 19 unit tests
│   ├── test_assessor.py        # 7 unit tests (mocked client)
│   ├── test_curator.py         # 11 unit tests (mocked client)
│   └── test_eval.py            # End-to-end eval tests (real API, marked @pytest.mark.eval)
├── scripts/
│   └── run_eval.py             # Full eval run with summary table
└── docs/
    ├── SKILLS_GUIDE.md         # How to edit and add skills safely
    └── PROMPT_ENGINEERING_NOTES.md  # Design decisions behind the prompts
```

---

## How the Skills System Works

The analysis logic lives in **markdown files** in `/skills/`, not buried in Python. This means:

- A recruiter or domain expert can read and propose changes without touching code
- Skill changes are diff-able in git — you can see exactly what changed
- After any skill edit, run `pytest -m eval` to catch regressions before they reach users

Key skill files:

| File | Purpose |
|------|---------|
| `skills/candidate_analysis/SKILL.md` | Three-pillar rubric, evidence requirements, anti-hallucination rules |
| `skills/candidate_analysis/rubric.md` | 0/25/50/75/100 anchor descriptions per pillar |
| `skills/profile_curation/SKILL.md` | Curation process, three levers, hard prohibitions |
| `skills/profile_curation/cv_principles.md` | CV structure, bullet patterns, ATS guidance |
| `skills/jd_parsing/SKILL.md` | JD extraction schema (used by both pipelines) |

See [`docs/SKILLS_GUIDE.md`](docs/SKILLS_GUIDE.md) for a full guide on editing and extending skills.

---

## Deploying to Vercel

The app runs as a FastAPI server on Vercel. You need a [Vercel Pro](https://vercel.com/pricing) account ($20/month) — the free Hobby tier has a 10-second function timeout which is too short for Claude API calls (typically 20–60 seconds).

### Prerequisites
- [Vercel account](https://vercel.com) (Pro plan)
- [Vercel CLI](https://vercel.com/docs/cli): `npm i -g vercel`
- Your Anthropic API key

### Steps

1. **Install the Vercel CLI and log in:**
   ```bash
   npm i -g vercel
   vercel login
   ```

2. **From the project root, run:**
   ```bash
   vercel
   ```
   Follow the prompts — link to your Vercel account, accept defaults for project name and framework.

3. **Set environment variables** (do this once via CLI or in the Vercel dashboard):
   ```bash
   vercel env add ANTHROPIC_API_KEY
   # When prompted, paste your key and select all environments (Production, Preview, Development)

   vercel env add DB_PATH
   # Value: /tmp/profile_agent.db
   # (Vercel Lambda has a writable /tmp — history won't persist across cold starts, but core features work)
   ```

   Or add them in the Vercel dashboard: **Project → Settings → Environment Variables**

4. **Deploy to production:**
   ```bash
   vercel --prod
   ```

5. **Your app is live** at the URL Vercel prints (e.g. `https://professional-profile-agent.vercel.app`). Share it with anyone who needs access.

> **Note on history:** SQLite is stored in `/tmp` on Vercel, which resets on cold starts. Assessments and curations run correctly; the feedback loop history is ephemeral. For persistent history, run locally instead.

---

## Running Tests

```bash
# Unit tests (no API key required — client is mocked)
pytest tests/test_parsers.py tests/test_assessor.py tests/test_curator.py -v

# End-to-end eval tests (hits real API — costs ~$1–3 per run)
pytest -m eval tests/test_eval.py -v

# Full eval summary table
python scripts/run_eval.py
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| UI | Vanilla HTML/CSS/JS (served by FastAPI StaticFiles) |
| AI | [Anthropic Claude API](https://anthropic.com) (`claude-sonnet-4-6` for analysis, `claude-haiku-4-5` for JD parsing) |
| Data validation | [Pydantic v2](https://docs.pydantic.dev) |
| Storage | SQLite (stdlib) |
| Document parsing | [pypdf](https://github.com/py-pdf/pypdf), [python-docx](https://python-docx.readthedocs.io) |
| URL fetching | [requests](https://requests.readthedocs.io) + [BeautifulSoup4](https://beautiful-soup-4.readthedocs.io) |
| PDF output | [ReportLab](https://reportlab.com) (pure Python, no system libs required) |
| API layer | [FastAPI](https://fastapi.tiangolo.com) (stub — ready for productisation) |

---

## Design Principles

**Evidence-grounded, not hallucinated.** Every score and every claim cites a verbatim source span. If there isn't enough evidence, scores drop and confidence drops — the tool doesn't paper over gaps.

**Skills as versioned markdown.** The intelligence is in `/skills/` — readable by non-engineers, diff-able in git, and regression-tested via the eval harness.

**No LinkedIn scraping.** Inputs are PDF exports or URLs to public job postings. Candidate profiles are uploaded as LinkedIn PDF exports (LinkedIn → Profile → More → Save to PDF).

**In-context self-improvement.** Rate any output thumbs up/down. Top-rated past outputs are injected as few-shot examples in future prompts; low-rated ones become "failure modes to avoid." No fine-tuning required.

**Honest about gaps.** If a candidate lacks a must-have requirement, the tool names it directly. If a job needs something your CV doesn't have, the gap analysis says so — and the CV doesn't pretend otherwise.

---

## Limitations

- **No LinkedIn scraping** — candidate profiles must be uploaded as PDF exports
- **Single-user** — no authentication or multi-tenant support in v0.1.0
- **English only** — prompts and rubrics are English-language
- **Cost** — approximately $0.10–$0.30 per candidate assessment, $0.20–$0.50 per CV curation (using `claude-sonnet-4-6`)
- **PDF output** — uses ReportLab (pure Python, bundled in requirements.txt — no system libraries needed)

---

## Roadmap

- [ ] Concurrent batch assessment (async pipeline)
- [ ] CSV bulk upload for candidate shortlists
- [ ] Multi-user authentication + session isolation
- [ ] ATS integration (Greenhouse, Lever webhooks)
- [ ] Browser extension for one-click LinkedIn PDF capture
- [ ] Proxycurl API as optional live LinkedIn data source
- [ ] Multi-language support

---

## License

MIT — see [LICENSE](LICENSE) for details.
