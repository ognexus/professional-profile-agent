"""
schemas.py — Pydantic models for the Candidate Assessment output.
Matches the JSON schema defined in skills/candidate_analysis/SKILL.md.
"""

from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, Field


class EvidenceItem(BaseModel):
    quote: str = Field(..., description="Verbatim excerpt from the candidate profile")
    source_section: str = Field(..., description="Which section the quote came from")
    interpretation: str = Field(..., description="One sentence explaining relevance to the pillar")


class PillarAssessment(BaseModel):
    score: int = Field(..., ge=0, le=100)
    confidence: int = Field(..., ge=0, le=100)
    evidence: list[EvidenceItem] = Field(default_factory=list)
    concerns: list[str] = Field(default_factory=list)


class PillarResults(BaseModel):
    cultural: PillarAssessment
    operational: PillarAssessment
    capability: PillarAssessment


class AssessmentResult(BaseModel):
    candidate_summary: str
    overall_fit_score: int = Field(..., ge=0, le=100)
    overall_confidence: int = Field(..., ge=0, le=100)
    pillars: PillarResults
    strengths: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    evidence_gaps: list[str] = Field(default_factory=list)
    recommended_interview_questions: list[str] = Field(default_factory=list)
    recommendation: Literal["strong_yes", "yes", "maybe", "no"]


# ---- JD parsing schema ----

class JDMustHave(BaseModel):
    requirement: str
    jd_quote: str


class JDExtraction(BaseModel):
    role_title: str
    company: str | None = None
    team_context: str | None = None
    must_have_requirements: list[str] = Field(default_factory=list)
    nice_to_have_requirements: list[str] = Field(default_factory=list)
    responsibilities: list[str] = Field(default_factory=list)
    culture_signals: list[str] = Field(default_factory=list)
    compensation: str | None = None
    location_and_work_mode: str | None = None
    red_flags: list[str] = Field(default_factory=list)
