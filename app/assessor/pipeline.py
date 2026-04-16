"""
pipeline.py — Candidate Assessor pipeline.

Flow for each candidate:
  1. Parse JD via jd_parsing skill → structured JD dict
  2. Run candidate analysis skill with: parsed JD + candidate profile + optional context
  3. Validate against Pydantic schema; retry once on failure
  4. Store result in SQLite
  5. Return AssessmentResult
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from pydantic import ValidationError

from app.assessor.schemas import AssessmentResult, JDExtraction
from app.config import settings
from app.core import storage

logger = logging.getLogger(__name__)


def _load_skill(*parts: str) -> str:
    """Load a skill or prompt markdown file by path parts."""
    path = Path(*parts)
    if not path.is_absolute():
        path = settings.skills_dir.parent / path
    return path.read_text(encoding="utf-8")


class AssessorPipeline:
    def __init__(self, claude_client):
        self._claude = claude_client
        self._jd_system = self._build_jd_system()
        self._assessor_system = self._build_assessor_system()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def assess(
        self,
        jd_text: str,
        candidate_profile_text: str,
        additional_context: str = "",
        few_shot_examples: list[dict] | None = None,
        avoid_patterns: list[dict] | None = None,
    ) -> tuple[AssessmentResult, int]:
        """
        Assess a single candidate.

        Returns:
            (AssessmentResult, record_id)  — record_id is the SQLite row id
        """
        # Step 1: Parse JD
        jd_structured = self._parse_jd(jd_text)

        # Step 2: Build assessor system prompt (with optional few-shot examples)
        system = self._build_runtime_assessor_system(few_shot_examples, avoid_patterns)

        # Step 3: Run candidate analysis
        user_message = self._build_assessment_message(
            jd_structured, candidate_profile_text, additional_context
        )
        result_dict, usage = self._claude.complete_json(
            system=system,
            messages=[{"role": "user", "content": user_message}],
        )

        # Step 4: Validate; retry once on schema failure
        assessment = self._validate_with_retry(
            result_dict, system, user_message, usage
        )

        # Step 5: Store
        record_id = storage.save_assessment(
            jd_text=jd_text,
            candidate_text=candidate_profile_text,
            result=result_dict,
        )

        logger.info(
            "Assessment complete [score=%d, confidence=%d, record_id=%d, tokens_in=%d, tokens_out=%d]",
            assessment.overall_fit_score,
            assessment.overall_confidence,
            record_id,
            usage.get("input_tokens", 0),
            usage.get("output_tokens", 0),
        )

        return assessment, record_id

    def assess_batch(
        self,
        jd_text: str,
        candidates: list[dict],
        additional_context: str = "",
        few_shot_examples: list[dict] | None = None,
        avoid_patterns: list[dict] | None = None,
    ) -> list[tuple[str, AssessmentResult, int]]:
        """
        Assess multiple candidates sequentially.

        Args:
            candidates: List of {"name": str, "profile_text": str}

        Returns:
            List of (candidate_name, AssessmentResult, record_id)
        """
        # Parse JD once for the batch
        _ = self._parse_jd(jd_text)  # validates the JD upfront

        results = []
        for candidate in candidates:
            name = candidate.get("name", "Unknown")
            profile_text = candidate.get("profile_text", "")
            logger.info("Assessing candidate: %s", name)
            try:
                assessment, record_id = self.assess(
                    jd_text=jd_text,
                    candidate_profile_text=profile_text,
                    additional_context=additional_context,
                    few_shot_examples=few_shot_examples,
                    avoid_patterns=avoid_patterns,
                )
                results.append((name, assessment, record_id))
            except Exception as exc:
                logger.error("Failed to assess %s: %s", name, exc)
                results.append((name, None, -1))  # type: ignore[arg-type]
        return results

    # ------------------------------------------------------------------
    # Internal: system prompt assembly
    # ------------------------------------------------------------------

    def _build_jd_system(self) -> str:
        skill = _load_skill("skills/jd_parsing/SKILL.md")
        preamble = _load_skill("prompts/jd_extractor.md")
        return f"{skill}\n\n---\n\n{preamble}"

    def _build_assessor_system(self) -> str:
        persona = _load_skill("agents/recruiter_persona.md")
        skill = _load_skill("skills/candidate_analysis/SKILL.md")
        rubric = _load_skill("skills/candidate_analysis/rubric.md")
        preamble = _load_skill("prompts/assessor_system.md")
        return f"{persona}\n\n---\n\n{skill}\n\n---\n\n{rubric}\n\n---\n\n{preamble}"

    def _build_runtime_assessor_system(
        self,
        few_shot_examples: list[dict] | None,
        avoid_patterns: list[dict] | None,
    ) -> str:
        system = self._assessor_system
        if few_shot_examples:
            examples_text = "\n\n".join(
                f"Example (rated highly):\nContext: {ex.get('context', '')}\nOutput: {json.dumps(ex.get('result', {}), indent=2)}"
                for ex in few_shot_examples
            )
            system += f"\n\n## Past Examples Rated Highly\n\n{examples_text}"
        if avoid_patterns:
            patterns_text = "\n\n".join(
                f"Failure to avoid:\n{p.get('comment', '')}\nBad output snippet: {json.dumps(p.get('result', {}), indent=2)}"
                for p in avoid_patterns
            )
            system += f"\n\n## Past Mistakes to Avoid\n\n{patterns_text}"
        return system

    # ------------------------------------------------------------------
    # Internal: JD parsing
    # ------------------------------------------------------------------

    def _parse_jd(self, jd_text: str) -> dict:
        result_dict, _ = self._claude.complete_json(
            system=self._jd_system,
            messages=[{"role": "user", "content": f"Parse this job description:\n\n{jd_text}"}],
            model=settings.anthropic_model_fast,
            cache_system=False,  # JD parsing is fast and cheap — skip cache overhead
        )
        # Light validation
        try:
            JDExtraction(**result_dict)
        except ValidationError as e:
            logger.warning("JD extraction schema mismatch (continuing): %s", e)
        return result_dict

    # ------------------------------------------------------------------
    # Internal: candidate assessment message
    # ------------------------------------------------------------------

    def _build_assessment_message(
        self,
        jd_structured: dict,
        candidate_text: str,
        additional_context: str,
    ) -> str:
        parts = [
            "## Structured Job Description\n\n" + json.dumps(jd_structured, indent=2),
            "## Candidate Profile\n\n" + candidate_text,
        ]
        if additional_context.strip():
            parts.append("## Additional Context from Hiring Manager\n\n" + additional_context)
        parts.append("Please assess this candidate following the skill exactly. Return valid JSON only.")
        return "\n\n".join(parts)

    # ------------------------------------------------------------------
    # Internal: validation + retry
    # ------------------------------------------------------------------

    def _validate_with_retry(
        self,
        result_dict: dict,
        system: str,
        original_message: str,
        usage: dict,
    ) -> AssessmentResult:
        try:
            return AssessmentResult(**result_dict)
        except ValidationError as e:
            logger.warning("Schema validation failed on first attempt, retrying: %s", e)
            retry_message = (
                f"{original_message}\n\n"
                f"Your previous response had schema errors:\n{e}\n\n"
                "Please fix them and return valid JSON only."
            )
            result_dict_retry, _ = self._claude.complete_json(
                system=system,
                messages=[{"role": "user", "content": retry_message}],
            )
            return AssessmentResult(**result_dict_retry)
