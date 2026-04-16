"""
test_assessor.py — Unit tests for the Candidate Assessor pipeline.
Claude client is mocked — these tests do NOT hit the Anthropic API.
"""

import json
import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path

from app.assessor.pipeline import AssessorPipeline
from app.assessor.schemas import AssessmentResult


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SYNTHETIC_JD = """
Senior Product Manager — Payments
Acme Fintech Ltd | Sydney, Australia | Hybrid

We are looking for a Senior PM to lead our consumer payments roadmap.

Requirements (must-have):
- 5+ years of product management experience
- Experience in payments, fintech, or financial services
- Proven ability to work with engineering teams in an Agile environment
- Strong data analysis skills (SQL, A/B testing)

Nice to have:
- Experience with open banking or regulatory compliance
- Exposure to APAC markets

What you'll do:
- Own the payments product roadmap end-to-end
- Work cross-functionally with Engineering, Design, and Commercial
- Define and track key product metrics
- Engage with regulators and external partners

Culture: We move fast but care about quality. Data-driven decisions, collaborative environment, high ownership.
"""

SYNTHETIC_CANDIDATE = """
Jane Smith
Senior Product Manager | Fintech Specialist

About
I have 7 years of experience building payment products at scale. I thrive in cross-functional environments and believe deeply in evidence-based product decisions.

Experience
Senior Product Manager, Payments — Acme Corp (2020–Present)
Led the redesign of checkout flow using A/B testing, reducing cart abandonment by 22%.
Managed roadmap for 3 payment products across APAC markets.
Collaborated with engineering squads of 8-12 engineers in two-week sprints.

Product Manager — PayStart (2017–2020)
Launched mobile wallet MVP, reaching 500K users in first quarter.
Defined KPIs and built dashboards in SQL and Tableau for exec reporting.

Education
Bachelor of Commerce — University of Sydney (2013–2016)
Major in Finance and Information Systems.

Skills
Product Strategy · Roadmap Planning · SQL · A/B Testing · Agile · Payments · Open Banking

Certifications
Certified Scrum Product Owner (2019)
"""

MOCK_JD_RESULT = {
    "role_title": "Senior Product Manager — Payments",
    "company": "Acme Fintech Ltd",
    "team_context": "Consumer payments team, hybrid Sydney",
    "must_have_requirements": [
        "5+ years of product management experience",
        "Experience in payments, fintech, or financial services",
        "Agile environment experience",
        "Strong data analysis skills (SQL, A/B testing)",
    ],
    "nice_to_have_requirements": ["Open banking", "APAC markets experience"],
    "responsibilities": [
        "Own the payments product roadmap",
        "Work cross-functionally with Engineering, Design, and Commercial",
        "Define and track key product metrics",
    ],
    "culture_signals": ["Move fast but care about quality", "Data-driven decisions", "High ownership"],
    "compensation": None,
    "location_and_work_mode": "Sydney, Hybrid",
    "red_flags": [],
}

MOCK_ASSESSMENT_RESULT = {
    "candidate_summary": "Experienced payments PM with 7 years in fintech, strong data skills and APAC coverage.",
    "overall_fit_score": 85,
    "overall_confidence": 82,
    "pillars": {
        "cultural": {
            "score": 80,
            "confidence": 75,
            "evidence": [
                {
                    "quote": "I believe deeply in evidence-based product decisions",
                    "source_section": "about",
                    "interpretation": "Aligns directly with stated data-driven culture",
                },
                {
                    "quote": "thrive in cross-functional environments",
                    "source_section": "about",
                    "interpretation": "Matches 'collaborative environment' culture signal",
                },
            ],
            "concerns": [],
        },
        "operational": {
            "score": 88,
            "confidence": 85,
            "evidence": [
                {
                    "quote": "Managed roadmap for 3 payment products across APAC markets",
                    "source_section": "experience",
                    "interpretation": "Matches APAC and multi-product scope requirements",
                },
                {
                    "quote": "Collaborated with engineering squads of 8-12 engineers in two-week sprints",
                    "source_section": "experience",
                    "interpretation": "Demonstrates Agile working in comparable team context",
                },
            ],
            "concerns": [],
        },
        "capability": {
            "score": 87,
            "confidence": 88,
            "evidence": [
                {
                    "quote": "reducing cart abandonment by 22%",
                    "source_section": "experience",
                    "interpretation": "Quantified outcome demonstrating A/B testing capability",
                },
                {
                    "quote": "built dashboards in SQL and Tableau for exec reporting",
                    "source_section": "experience",
                    "interpretation": "Directly evidences SQL and data analysis skills from must-haves",
                },
            ],
            "concerns": [],
        },
    },
    "strengths": [
        "Deep payments domain expertise with quantified outcomes",
        "APAC market experience matching nice-to-have",
        "SQL and A/B testing directly evidenced",
    ],
    "risks": [],
    "evidence_gaps": ["No explicit mention of regulatory engagement despite JD requirement"],
    "recommended_interview_questions": [
        "Describe a time you worked with regulators or external compliance partners on a product decision.",
        "How do you balance speed of delivery with quality in a payments context?",
    ],
    "recommendation": "strong_yes",
}


def make_mock_client():
    """Return a mock ClaudeClient that returns deterministic responses."""
    client = MagicMock()

    def mock_complete_json(system, messages, **kwargs):
        # First call is JD parsing, second is candidate assessment
        if "Parse this job description" in messages[-1]["content"]:
            return MOCK_JD_RESULT, {"input_tokens": 100, "output_tokens": 200}
        else:
            return MOCK_ASSESSMENT_RESULT, {"input_tokens": 500, "output_tokens": 300}

    client.complete_json.side_effect = mock_complete_json
    return client


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_assess_returns_assessment_result():
    client = make_mock_client()
    pipeline = AssessorPipeline(client)
    result, record_id = pipeline.assess(
        jd_text=SYNTHETIC_JD,
        candidate_profile_text=SYNTHETIC_CANDIDATE,
    )
    assert isinstance(result, AssessmentResult)
    assert result.overall_fit_score == 85
    assert result.recommendation == "strong_yes"
    assert record_id > 0


def test_assess_stores_result_in_db(tmp_path):
    from app.core.storage import get_assessment, init_db

    db_path = tmp_path / "test.db"
    init_db(db_path)

    client = make_mock_client()
    pipeline = AssessorPipeline(client)

    with patch("app.assessor.pipeline.storage.save_assessment") as mock_save:
        mock_save.return_value = 42
        result, record_id = pipeline.assess(
            jd_text=SYNTHETIC_JD,
            candidate_profile_text=SYNTHETIC_CANDIDATE,
        )
        mock_save.assert_called_once()
        assert record_id == 42


def test_assess_calls_jd_parser_first():
    client = make_mock_client()
    pipeline = AssessorPipeline(client)
    pipeline.assess(
        jd_text=SYNTHETIC_JD,
        candidate_profile_text=SYNTHETIC_CANDIDATE,
    )
    # First complete_json call should be the JD parser
    first_call_messages = client.complete_json.call_args_list[0].kwargs["messages"]
    assert "Parse this job description" in first_call_messages[-1]["content"]


def test_assess_batch_returns_multiple_results():
    client = make_mock_client()
    pipeline = AssessorPipeline(client)
    candidates = [
        {"name": "Jane Smith", "profile_text": SYNTHETIC_CANDIDATE},
        {"name": "John Doe", "profile_text": SYNTHETIC_CANDIDATE},
    ]
    results = pipeline.assess_batch(jd_text=SYNTHETIC_JD, candidates=candidates)
    assert len(results) == 2
    for name, assessment, record_id in results:
        assert isinstance(assessment, AssessmentResult)


def test_pydantic_schema_validates_mock_result():
    """Ensure the mock result matches the schema exactly."""
    result = AssessmentResult(**MOCK_ASSESSMENT_RESULT)
    assert result.overall_fit_score == 85
    assert len(result.pillars.cultural.evidence) == 2
    assert result.recommendation == "strong_yes"


def test_few_shot_examples_injected_into_system():
    client = make_mock_client()
    pipeline = AssessorPipeline(client)
    few_shot = [{"context": "Great PM candidate", "result": MOCK_ASSESSMENT_RESULT}]
    pipeline.assess(
        jd_text=SYNTHETIC_JD,
        candidate_profile_text=SYNTHETIC_CANDIDATE,
        few_shot_examples=few_shot,
    )
    # The system prompt for the assessment call (second call) should contain the few-shot section
    second_call_system = client.complete_json.call_args_list[1].kwargs["system"]
    assert "Past Examples Rated Highly" in second_call_system


def test_avoid_patterns_injected_into_system():
    client = make_mock_client()
    pipeline = AssessorPipeline(client)
    avoid = [{"comment": "Do not over-score thin profiles", "result": {}}]
    pipeline.assess(
        jd_text=SYNTHETIC_JD,
        candidate_profile_text=SYNTHETIC_CANDIDATE,
        avoid_patterns=avoid,
    )
    second_call_system = client.complete_json.call_args_list[1].kwargs["system"]
    assert "Past Mistakes to Avoid" in second_call_system
