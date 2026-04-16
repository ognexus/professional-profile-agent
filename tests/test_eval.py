"""
test_eval.py — End-to-end eval tests that hit the real Anthropic API.

Run with: pytest -m eval tests/test_eval.py -v

These tests validate:
  Assessor:
    - Strong-fit candidates score > 70 overall
    - Weak-fit candidates score < 50 overall
    - All score evidence quotes appear (as substrings) in the source profile text
  Curator:
    - Every CV experience claim appears (fuzzy match ≥ 80%) in the source material
    - Cover letter is 200-400 words
    - Cover letter contains the company name
    - Cover letter doesn't contain banned phrases

NOTE: These tests cost real API credits. Run intentionally, not on every push.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

EVAL_DIR = Path(__file__).parent / "eval_cases"

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _load(filename: str) -> str:
    return (EVAL_DIR / filename).read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def client():
    from app.core.claude_client import ClaudeClient
    return ClaudeClient()


@pytest.fixture(scope="module")
def assessor(client):
    from app.assessor.pipeline import AssessorPipeline
    return AssessorPipeline(client)


@pytest.fixture(scope="module")
def curator(client):
    from app.curator.pipeline import CuratorPipeline
    return CuratorPipeline(client)


# ---------------------------------------------------------------------------
# Assessor: strong-fit candidates
# ---------------------------------------------------------------------------


@pytest.mark.eval
@pytest.mark.parametrize("jd_file,profile_file", [
    ("jd_tech_ic.md", "candidate_strong_tech.md"),
    ("jd_consulting.md", "candidate_strong_consulting.md"),
    ("jd_education.md", "candidate_strong_education.md"),
])
def test_strong_fit_scores_above_70(assessor, jd_file, profile_file):
    jd_text = _load(jd_file)
    profile_text = _load(profile_file)
    result, _ = assessor.assess(jd_text=jd_text, candidate_profile_text=profile_text)
    assert result.overall_fit_score >= 70, (
        f"Strong-fit candidate scored {result.overall_fit_score} — expected >= 70. "
        f"Profile: {profile_file}, JD: {jd_file}"
    )


# ---------------------------------------------------------------------------
# Assessor: weak-fit candidates
# ---------------------------------------------------------------------------


@pytest.mark.eval
@pytest.mark.parametrize("jd_file,profile_file", [
    ("jd_tech_ic.md", "candidate_weak_tech.md"),
    ("jd_consulting.md", "candidate_weak_consulting.md"),
    ("jd_education.md", "candidate_weak_education.md"),
])
def test_weak_fit_scores_below_50(assessor, jd_file, profile_file):
    jd_text = _load(jd_file)
    profile_text = _load(profile_file)
    result, _ = assessor.assess(jd_text=jd_text, candidate_profile_text=profile_text)
    assert result.overall_fit_score < 50, (
        f"Weak-fit candidate scored {result.overall_fit_score} — expected < 50. "
        f"Profile: {profile_file}, JD: {jd_file}"
    )


# ---------------------------------------------------------------------------
# Assessor: evidence quotes must appear in source text
# ---------------------------------------------------------------------------


@pytest.mark.eval
@pytest.mark.parametrize("jd_file,profile_file", [
    ("jd_tech_ic.md", "candidate_strong_tech.md"),
    ("jd_consulting.md", "candidate_strong_consulting.md"),
])
def test_evidence_quotes_exist_in_source(assessor, jd_file, profile_file):
    jd_text = _load(jd_file)
    profile_text = _load(profile_file)
    profile_lower = profile_text.lower()
    result, _ = assessor.assess(jd_text=jd_text, candidate_profile_text=profile_text)

    for pillar_name, pillar in [
        ("cultural", result.pillars.cultural),
        ("operational", result.pillars.operational),
        ("capability", result.pillars.capability),
    ]:
        for ev in pillar.evidence:
            # Check first 8 words of the quote appear somewhere in the profile
            quote_start = " ".join(ev.quote.lower().split()[:8])
            assert quote_start in profile_lower, (
                f"Pillar '{pillar_name}' evidence quote not found in source profile.\n"
                f"Quote: '{ev.quote}'\n"
                f"Profile: {profile_file}"
            )


# ---------------------------------------------------------------------------
# Curator: CV claims appear in source (fuzzy match)
# ---------------------------------------------------------------------------


@pytest.mark.eval
@pytest.mark.parametrize("jd_file,user_cv_file", [
    ("jd_tech_ic.md", "user_cv_tech.md"),
    ("jd_consulting.md", "user_cv_consulting.md"),
])
def test_tailored_cv_claims_in_source(curator, jd_file, user_cv_file):
    try:
        from rapidfuzz import fuzz
    except ImportError:
        pytest.skip("rapidfuzz not installed")

    content = _load(user_cv_file)
    # Split on ## headers to separate CV text and LinkedIn text
    cv_text = content
    linkedin_text = ""
    if "**LinkedIn Profile Text**" in content:
        parts = content.split("**LinkedIn Profile Text**")
        cv_text = parts[0]
        linkedin_text = parts[1] if len(parts) > 1 else ""

    jd_text = _load(jd_file)
    source_text = (cv_text + "\n\n" + linkedin_text).lower()

    result, _ = curator.curate(
        jd_text=jd_text,
        current_cv_text=cv_text,
        linkedin_text=linkedin_text,
    )

    for role in result.tailored_cv.experience:
        for bullet in role.bullets:
            # Take 6-word fragments and check fuzzy presence
            words = bullet.split()
            if len(words) >= 6:
                fragment = " ".join(words[:6]).lower()
                score = fuzz.partial_ratio(fragment, source_text)
                assert score >= 80, (
                    f"Tailored CV bullet may not be grounded in source:\n"
                    f"Bullet: '{bullet}'\n"
                    f"Fragment: '{fragment}'\n"
                    f"Fuzzy score: {score} (expected >= 80)"
                )


# ---------------------------------------------------------------------------
# Curator: cover letter quality
# ---------------------------------------------------------------------------

BANNED_PHRASES = [
    "in today's fast-paced world",
    "i am writing to express",
    "passionate about leveraging",
    "dynamic",
    "synergy",
    "results-driven",
]


@pytest.mark.eval
@pytest.mark.parametrize("jd_file,user_cv_file", [
    ("jd_tech_ic.md", "user_cv_tech.md"),
    ("jd_consulting.md", "user_cv_consulting.md"),
])
def test_cover_letter_quality(curator, jd_file, user_cv_file):
    content = _load(user_cv_file)
    cv_text = content
    linkedin_text = ""
    if "**LinkedIn Profile Text**" in content:
        parts = content.split("**LinkedIn Profile Text**")
        cv_text = parts[0]
        linkedin_text = parts[1] if len(parts) > 1 else ""

    jd_text = _load(jd_file)

    result, _ = curator.curate(
        jd_text=jd_text,
        current_cv_text=cv_text,
        linkedin_text=linkedin_text,
    )

    cl = result.cover_letter
    word_count = len(cl.split())

    # Word count check
    assert 200 <= word_count <= 400, (
        f"Cover letter word count {word_count} is outside 200-400 range. JD: {jd_file}"
    )

    # Company name check
    company = result.jd_extraction.company
    if company:
        assert company.lower() in cl.lower(), (
            f"Company name '{company}' not found in cover letter. JD: {jd_file}"
        )

    # Banned phrases check
    cl_lower = cl.lower()
    for phrase in BANNED_PHRASES:
        assert phrase not in cl_lower, (
            f"Banned phrase '{phrase}' found in cover letter. JD: {jd_file}"
        )
