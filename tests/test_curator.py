"""
test_curator.py — Unit tests for the Profile Curator pipeline and CV builder.
Claude client is mocked — these tests do NOT hit the Anthropic API.
"""

import json
import pytest
from unittest.mock import MagicMock, patch

from app.curator.pipeline import CuratorPipeline
from app.curator.schemas import CurationResult
from app.curator.cv_builder import render_cv_html, render_cover_letter_html


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SYNTHETIC_JD = """
Head of Product — EdTech Platform
Torrens University | Sydney, Australia | Hybrid

We are seeking a strategic Head of Product to lead our digital learning platform roadmap.

Requirements (must-have):
- 8+ years of product management experience, with at least 2 years in a leadership role
- Experience in education technology or learning platforms
- Strong stakeholder management and cross-functional leadership
- Data-driven approach with experience in product analytics

Nice to have:
- Experience with LMS platforms (Canvas, Moodle, Blackboard)
- Background in higher education sector

Culture: Mission-driven organisation. Collaborative decision-making. Long-term thinking over quick wins.
"""

SYNTHETIC_CV = """
Alex Rivera
Senior Product Manager

Experience
Senior Product Manager — LearnCo (2019–2024)
Led roadmap for a K-12 digital learning platform serving 200,000 students.
Managed a team of 5 PMs and collaborated with 30+ engineers across 3 squads.
Introduced OKR framework, improving on-time delivery from 60% to 85%.

Product Manager — TechStart (2016–2019)
Built B2B SaaS product analytics dashboard from zero to 500 enterprise clients.
Ran 12 A/B tests per quarter; improved conversion by 18% over 2 years.

Education
Bachelor of Information Technology — RMIT University (2012–2015)

Skills
Product Strategy · Roadmap Planning · OKRs · A/B Testing · SQL · Stakeholder Management · Agile
"""

SYNTHETIC_LINKEDIN = """
Alex Rivera
Head of Product (aspirational) | EdTech | Learning Platforms

About
Passionate about technology that improves how people learn. 8 years building digital education products at scale.

Experience
Senior Product Manager — LearnCo (2019–2024)
Drove the expansion of a K-12 platform from 50,000 to 200,000 students over 3 years.

Skills
Product Strategy · Learning Management Systems · Canvas · Agile · OKRs · SQL
"""

MOCK_JD_RESULT = {
    "role_title": "Head of Product",
    "company": "Torrens University",
    "team_context": "Digital learning platform team",
    "must_have_requirements": [
        "8+ years product management",
        "2+ years leadership",
        "EdTech or learning platforms experience",
        "Stakeholder management",
        "Product analytics",
    ],
    "nice_to_have_requirements": ["LMS platform experience", "Higher education background"],
    "responsibilities": [
        "Lead digital learning platform roadmap",
        "Cross-functional leadership",
    ],
    "culture_signals": ["Mission-driven", "Collaborative", "Long-term thinking"],
    "compensation": None,
    "location_and_work_mode": "Sydney, Hybrid",
    "red_flags": [],
}

MOCK_CURATION_RESULT = {
    "jd_extraction": {
        "role_title": "Head of Product",
        "company": "Torrens University",
        "must_haves": [
            {"requirement": "8+ years PM experience", "jd_quote": "8+ years of product management experience"},
            {"requirement": "2+ years leadership", "jd_quote": "at least 2 years in a leadership role"},
        ],
        "nice_to_haves": [
            {"requirement": "LMS experience", "jd_quote": "Canvas, Moodle, Blackboard"}
        ],
        "company_signals": ["Mission-driven", "Collaborative decision-making"],
    },
    "evidence_inventory": [
        {
            "claim": "8 years of product management experience",
            "source": "linkedin",
            "source_quote": "8 years building digital education products at scale",
            "relevant_to": ["8+ years PM experience"],
        },
        {
            "claim": "Managed team of 5 PMs",
            "source": "cv",
            "source_quote": "Managed a team of 5 PMs and collaborated with 30+ engineers",
            "relevant_to": ["2+ years leadership"],
        },
    ],
    "gap_analysis": {
        "strong_matches": [
            {"requirement": "8+ years PM experience", "evidence_summary": "8 years evidenced across LearnCo and TechStart"},
            {"requirement": "EdTech experience", "evidence_summary": "Led K-12 platform serving 200,000 students"},
        ],
        "partial_matches": [
            {
                "requirement": "2+ years in leadership",
                "what_exists": "Managed team of 5 PMs at LearnCo (5 years tenure)",
                "what_is_missing": "Exact years in formal leadership role not specified",
            }
        ],
        "missing": [
            {"requirement": "Higher education sector experience", "impact": "low"}
        ],
    },
    "tailored_cv": {
        "summary": (
            "Senior Product Manager with 8 years leading digital learning platforms, "
            "including a K-12 platform scaled from 50,000 to 200,000 students. "
            "Experienced in cross-functional leadership, OKR-driven delivery, and stakeholder management. "
            "Seeking a Head of Product role to drive strategic education technology outcomes at scale."
        ),
        "experience": [
            {
                "employer": "LearnCo",
                "title": "Senior Product Manager",
                "dates": "2019–2024",
                "bullets": [
                    "Led digital learning platform roadmap serving 200,000 students across K-12.",
                    "Managed a team of 5 PMs and collaborated with 30+ engineers across 3 squads.",
                    "Introduced OKR framework, improving on-time delivery from 60% to 85%.",
                ],
            },
            {
                "employer": "TechStart",
                "title": "Product Manager",
                "dates": "2016–2019",
                "bullets": [
                    "Built product analytics dashboard from zero to 500 enterprise clients.",
                    "Improved conversion by 18% through 12 A/B tests per quarter.",
                ],
            },
        ],
        "skills": [
            "Product Strategy",
            "Learning Management Systems",
            "Canvas",
            "OKRs",
            "Stakeholder Management",
            "Roadmap Planning",
            "A/B Testing",
            "SQL",
            "Agile",
        ],
        "education": [
            {
                "institution": "RMIT University",
                "qualification": "Bachelor of Information Technology",
                "dates": "2012–2015",
            }
        ],
        "certifications": [],
    },
    "cover_letter": (
        "The Head of Product role at Torrens University offers an opportunity to apply eight years of "
        "digital learning product leadership in a context where the mission — improving how people learn — "
        "aligns directly with my own career focus.\n\n"
        "At LearnCo, I led the product roadmap for a K-12 digital learning platform, scaling it from "
        "50,000 to 200,000 students over three years. This required close collaboration with curriculum "
        "teams, engineering squads, and executive stakeholders — the same cross-functional leadership "
        "the role describes. I introduced an OKR framework that lifted on-time delivery from 60% to 85%, "
        "demonstrating the data-driven, long-term thinking your culture values.\n\n"
        "My experience with LMS platforms, including Canvas, means I can contribute meaningfully from "
        "day one. I understand the technical and pedagogical constraints that shape learning platform "
        "decisions, and I know how to prioritise a roadmap that serves students, educators, and "
        "institutional stakeholders simultaneously.\n\n"
        "Torrens University's reputation for industry-connected education makes it a genuinely compelling "
        "context to operate in. I would welcome the opportunity to discuss how my background maps to "
        "your platform's next phase of development."
    ),
    "rationale_log": [
        {
            "change": "Added 'digital learning platform' framing to experience bullets",
            "reason": "Matches JD vocabulary; source says 'digital learning platform' in LinkedIn",
            "evidence": "8 years building digital education products at scale",
        },
        {
            "change": "Moved Canvas to top of skills list",
            "reason": "JD specifically names Canvas as a nice-to-have",
            "evidence": "Canvas listed in LinkedIn skills section",
        },
    ],
}


def make_mock_client():
    client = MagicMock()

    def mock_complete_json(system, messages, **kwargs):
        if "Parse this job description" in messages[-1]["content"]:
            return MOCK_JD_RESULT, {"input_tokens": 100, "output_tokens": 200}
        else:
            return MOCK_CURATION_RESULT, {"input_tokens": 800, "output_tokens": 600}

    client.complete_json.side_effect = mock_complete_json
    return client


# ---------------------------------------------------------------------------
# Pipeline tests
# ---------------------------------------------------------------------------


def test_curate_returns_curation_result():
    client = make_mock_client()
    pipeline = CuratorPipeline(client)
    result, record_id = pipeline.curate(
        jd_text=SYNTHETIC_JD,
        current_cv_text=SYNTHETIC_CV,
        linkedin_text=SYNTHETIC_LINKEDIN,
    )
    assert isinstance(result, CurationResult)
    assert result.tailored_cv.summary != ""
    assert result.cover_letter != ""
    assert record_id > 0


def test_curate_calls_jd_parser_first():
    client = make_mock_client()
    pipeline = CuratorPipeline(client)
    pipeline.curate(
        jd_text=SYNTHETIC_JD,
        current_cv_text=SYNTHETIC_CV,
        linkedin_text=SYNTHETIC_LINKEDIN,
    )
    first_call_messages = client.complete_json.call_args_list[0].kwargs["messages"]
    assert "Parse this job description" in first_call_messages[-1]["content"]


def test_curate_includes_cv_and_linkedin_in_message():
    client = make_mock_client()
    pipeline = CuratorPipeline(client)
    pipeline.curate(
        jd_text=SYNTHETIC_JD,
        current_cv_text=SYNTHETIC_CV,
        linkedin_text=SYNTHETIC_LINKEDIN,
    )
    second_call_messages = client.complete_json.call_args_list[1].kwargs["messages"]
    message_content = second_call_messages[-1]["content"]
    assert "Current CV" in message_content
    assert "LinkedIn Profile" in message_content


def test_curate_gap_analysis_has_missing_items():
    client = make_mock_client()
    pipeline = CuratorPipeline(client)
    result, _ = pipeline.curate(
        jd_text=SYNTHETIC_JD,
        current_cv_text=SYNTHETIC_CV,
        linkedin_text=SYNTHETIC_LINKEDIN,
    )
    assert len(result.gap_analysis.missing) >= 1
    assert result.gap_analysis.missing[0].impact in ("critical", "moderate", "low")


def test_pydantic_schema_validates_mock_result():
    result = CurationResult(**MOCK_CURATION_RESULT)
    assert result.tailored_cv.skills[0] == "Product Strategy"
    assert len(result.evidence_inventory) == 2


def test_few_shot_examples_injected_into_curator_system():
    client = make_mock_client()
    pipeline = CuratorPipeline(client)
    few_shot = [{"context": "Great EdTech PM", "result": MOCK_CURATION_RESULT}]
    pipeline.curate(
        jd_text=SYNTHETIC_JD,
        current_cv_text=SYNTHETIC_CV,
        linkedin_text=SYNTHETIC_LINKEDIN,
        few_shot_examples=few_shot,
    )
    second_call_system = client.complete_json.call_args_list[1].kwargs["system"]
    assert "Past Examples Rated Highly" in second_call_system


# ---------------------------------------------------------------------------
# CV builder tests
# ---------------------------------------------------------------------------


def test_render_cv_html_contains_employer():
    html = render_cv_html(MOCK_CURATION_RESULT["tailored_cv"], candidate_name="Alex Rivera")
    assert "LearnCo" in html
    assert "Alex Rivera" in html


def test_render_cv_html_contains_skills():
    html = render_cv_html(MOCK_CURATION_RESULT["tailored_cv"])
    assert "Product Strategy" in html
    assert "Canvas" in html


def test_render_cv_html_contains_education():
    html = render_cv_html(MOCK_CURATION_RESULT["tailored_cv"])
    assert "RMIT University" in html


def test_render_cover_letter_html_contains_body():
    html = render_cover_letter_html(
        MOCK_CURATION_RESULT["cover_letter"],
        candidate_name="Alex Rivera",
        role_title="Head of Product",
        company="Torrens University",
    )
    assert "Torrens University" in html
    assert "LearnCo" in html


def test_render_cv_html_escapes_special_chars():
    cv = {
        "summary": "I use <React> & write TypeScript",
        "experience": [],
        "skills": [],
        "education": [],
        "certifications": [],
    }
    html = render_cv_html(cv)
    assert "<React>" not in html
    assert "&lt;React&gt;" in html
