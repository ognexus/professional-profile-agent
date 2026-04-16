"""
schemas.py — Pydantic models for the Profile Curation output.
Matches the JSON schema defined in skills/profile_curation/SKILL.md.
"""

from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, Field


# ---- JD extraction (reused from assessor but with richer structure) ----

class MustHave(BaseModel):
    requirement: str
    jd_quote: str


class NiceToHave(BaseModel):
    requirement: str
    jd_quote: str


class JDExtraction(BaseModel):
    role_title: str
    company: str | None = None
    must_haves: list[MustHave] = Field(default_factory=list)
    nice_to_haves: list[NiceToHave] = Field(default_factory=list)
    company_signals: list[str] = Field(default_factory=list)


# ---- Evidence inventory ----

class EvidenceItem(BaseModel):
    claim: str
    source: Literal["cv", "linkedin"]
    source_quote: str
    relevant_to: list[str] = Field(default_factory=list)


# ---- Gap analysis ----

class StrongMatch(BaseModel):
    requirement: str
    evidence_summary: str


class PartialMatch(BaseModel):
    requirement: str
    what_exists: str
    what_is_missing: str


class MissingItem(BaseModel):
    requirement: str
    impact: Literal["critical", "moderate", "low"]


class GapAnalysis(BaseModel):
    strong_matches: list[StrongMatch] = Field(default_factory=list)
    partial_matches: list[PartialMatch] = Field(default_factory=list)
    missing: list[MissingItem] = Field(default_factory=list)


# ---- Tailored CV ----

class ExperienceEntry(BaseModel):
    employer: str
    title: str
    dates: str
    bullets: list[str] = Field(default_factory=list)


class EducationEntry(BaseModel):
    institution: str
    qualification: str
    dates: str


class TailoredCV(BaseModel):
    summary: str
    experience: list[ExperienceEntry] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    education: list[EducationEntry] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)


# ---- Rationale log ----

class RationaleEntry(BaseModel):
    change: str
    reason: str
    evidence: str


# ---- Top-level result ----

class CurationResult(BaseModel):
    jd_extraction: JDExtraction
    evidence_inventory: list[EvidenceItem] = Field(default_factory=list)
    gap_analysis: GapAnalysis
    tailored_cv: TailoredCV
    cover_letter: str
    rationale_log: list[RationaleEntry] = Field(default_factory=list)
