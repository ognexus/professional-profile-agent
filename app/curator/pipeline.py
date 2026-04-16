"""
pipeline.py — Profile Curator pipeline.

Flow:
  1. Parse JD via jd_parsing skill → structured JD dict
  2. Run profile_curation skill with: parsed JD + CV text + LinkedIn text + user notes
  3. Validate against Pydantic schema; retry once on failure
  4. Store result in SQLite
  5. Return CurationResult
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from pydantic import ValidationError

from app.curator.schemas import CurationResult
from app.assessor.schemas import JDExtraction  # reuse JD parsing schema
from app.config import settings
from app.core import storage

logger = logging.getLogger(__name__)


def _load_skill(*parts: str) -> str:
    path = Path(*parts)
    if not path.is_absolute():
        path = settings.skills_dir.parent / path
    return path.read_text(encoding="utf-8")


class CuratorPipeline:
    def __init__(self, claude_client):
        self._claude = claude_client
        self._jd_system = self._build_jd_system()
        self._curator_system = self._build_curator_system()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def curate(
        self,
        jd_text: str,
        current_cv_text: str,
        linkedin_text: str,
        user_notes: str = "",
        few_shot_examples: list[dict] | None = None,
        avoid_patterns: list[dict] | None = None,
    ) -> tuple[CurationResult, int]:
        """
        Curate a user's CV and cover letter for a specific job.

        Returns:
            (CurationResult, record_id)
        """
        # Step 1: Parse JD
        jd_structured = self._parse_jd(jd_text)

        # Step 2: Build runtime system prompt
        system = self._build_runtime_curator_system(few_shot_examples, avoid_patterns)

        # Step 3: Run curation
        user_message = self._build_curation_message(
            jd_structured, current_cv_text, linkedin_text, user_notes
        )
        result_dict, usage = self._claude.complete_json(
            system=system,
            messages=[{"role": "user", "content": user_message}],
        )

        # Step 4: Validate; retry once on schema failure
        curation = self._validate_with_retry(result_dict, system, user_message)

        # Step 5: Store
        record_id = storage.save_cv(
            jd_text=jd_text,
            cv_text=current_cv_text,
            linkedin_text=linkedin_text,
            result=result_dict,
        )

        logger.info(
            "Curation complete [record_id=%d, gaps=%d, tokens_in=%d, tokens_out=%d]",
            record_id,
            len(curation.gap_analysis.missing),
            usage.get("input_tokens", 0),
            usage.get("output_tokens", 0),
        )

        return curation, record_id

    # ------------------------------------------------------------------
    # Internal: system prompt assembly
    # ------------------------------------------------------------------

    def _build_jd_system(self) -> str:
        skill = _load_skill("skills/jd_parsing/SKILL.md")
        preamble = _load_skill("prompts/jd_extractor.md")
        return f"{skill}\n\n---\n\n{preamble}"

    def _build_curator_system(self) -> str:
        persona = _load_skill("agents/career_coach_persona.md")
        skill = _load_skill("skills/profile_curation/SKILL.md")
        principles = _load_skill("skills/profile_curation/cv_principles.md")
        preamble = _load_skill("prompts/curator_system.md")
        return f"{persona}\n\n---\n\n{skill}\n\n---\n\n{principles}\n\n---\n\n{preamble}"

    def _build_runtime_curator_system(
        self,
        few_shot_examples: list[dict] | None,
        avoid_patterns: list[dict] | None,
    ) -> str:
        system = self._curator_system
        if few_shot_examples:
            examples_text = "\n\n".join(
                f"Example (rated highly):\nContext: {ex.get('context', '')}\nOutput: {json.dumps(ex.get('result', {}), indent=2)}"
                for ex in few_shot_examples
            )
            system += f"\n\n## Past Examples Rated Highly\n\n{examples_text}"
        if avoid_patterns:
            patterns_text = "\n\n".join(
                f"Failure to avoid:\n{p.get('comment', '')}"
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
            cache_system=False,
        )
        try:
            JDExtraction(**result_dict)
        except ValidationError as e:
            logger.warning("JD extraction schema mismatch (continuing): %s", e)
        return result_dict

    # ------------------------------------------------------------------
    # Internal: curation message
    # ------------------------------------------------------------------

    def _build_curation_message(
        self,
        jd_structured: dict,
        cv_text: str,
        linkedin_text: str,
        user_notes: str,
    ) -> str:
        parts = [
            "## Structured Job Description\n\n" + json.dumps(jd_structured, indent=2),
            "## Current CV\n\n" + cv_text,
            "## LinkedIn Profile\n\n" + linkedin_text,
        ]
        if user_notes.strip():
            parts.append("## Notes from User\n\n" + user_notes)
        parts.append(
            "Please curate my CV and cover letter for this job following the skill exactly. "
            "Return valid JSON only."
        )
        return "\n\n".join(parts)

    # ------------------------------------------------------------------
    # Internal: validation + retry
    # ------------------------------------------------------------------

    def _validate_with_retry(
        self,
        result_dict: dict,
        system: str,
        original_message: str,
    ) -> CurationResult:
        try:
            return CurationResult(**result_dict)
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
            return CurationResult(**result_dict_retry)
