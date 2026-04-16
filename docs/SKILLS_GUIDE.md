# Skills Guide

## What Is a Skill?

A skill is a markdown file that defines how Claude should behave for a specific task. Skills live in the `/skills/` directory alongside the codebase. They are loaded at runtime by the pipeline and injected into the system prompt — Claude reads them as part of its operating instructions.

This architecture means you can change the analysis without touching Python code. A better rubric, a new pillar definition, a tighter anti-hallucination rule — all live in the skill file.

## Current Skills

| Skill | File | Used by |
|-------|------|---------|
| Candidate Analysis | `skills/candidate_analysis/SKILL.md` | `app/assessor/pipeline.py` |
| Candidate Scoring Rubric | `skills/candidate_analysis/rubric.md` | Loaded alongside SKILL.md |
| Profile Curation | `skills/profile_curation/SKILL.md` | `app/curator/pipeline.py` |
| CV Best Practices | `skills/profile_curation/cv_principles.md` | Loaded alongside SKILL.md |
| JD Parsing | `skills/jd_parsing/SKILL.md` | Both pipelines (JD extraction step) |

## How Skills Are Assembled Into System Prompts

Each pipeline builds the system prompt by concatenating:

```
[Agent persona]     agents/recruiter_persona.md or career_coach_persona.md
---
[Skill document]    skills/[skill_name]/SKILL.md
---
[Supporting doc]    skills/[skill_name]/rubric.md or cv_principles.md
---
[Preamble]         prompts/assessor_system.md or curator_system.md
```

This full concatenation is cached via Anthropic's prompt caching (cache_control: ephemeral) to reduce cost on repeated calls.

## How to Edit a Skill Safely

1. **Read the current skill** in full — understand what it currently specifies
2. **Make your change** — be precise and specific. Vague instructions produce vague outputs
3. **Run the unit tests** to verify the schema and pipeline still work:
   ```bash
   pytest tests/test_assessor.py tests/test_curator.py -v
   ```
4. **Run the eval harness** to verify the change doesn't regress real-API results:
   ```bash
   pytest -m eval tests/test_eval.py -v
   ```
5. **Compare scores** against the previous baseline. A skill change that improves one case should not regress others

## How to Add a New Skill

1. Create a new directory: `skills/new_skill_name/`
2. Write `skills/new_skill_name/SKILL.md` following the structure:
   - **Purpose** — what the skill does and what it must never do
   - **Definitions** — the concepts Claude must understand to do the task
   - **Process** — the numbered procedure Claude follows
   - **Output schema** — the exact JSON structure expected
   - **Anti-hallucination rules** — hard constraints, not guidelines
3. Add a corresponding prompt file in `prompts/` if needed
4. Wire it into a pipeline: load the skill file and prepend it to the system prompt
5. Add Pydantic schema validation for the output in `app/[feature]/schemas.py`
6. Add unit tests with a mocked client in `tests/test_[feature].py`
7. Add eval cases in `tests/eval_cases/` and update `tests/test_eval.py`
8. Document the skill here in this guide

## Skill Versioning

Skills are plain markdown files tracked in git. Version history is implicit in git history. If you make a significant change to a skill:

- Note the version at the top of the SKILL.md file
- Add a brief entry to `CHANGELOG.md`
- Run `pytest -m eval` and note the before/after pass rates

A prompt regression (eval tests that previously passed now fail) after a skill change is a strong signal the change is harmful — revert and rethink.

## Quality Bar for Skills

Every skill should be written as if a senior domain expert and a senior prompt engineer co-authored it. Specifically:

- **No vagueness.** "Be accurate" is not a rule. "Score above 50 only if you can cite at least 2 verbatim quotes from the candidate profile" is a rule.
- **No ambiguity in the output schema.** Every field must have a clear type and clear semantics.
- **Anti-hallucination rules must be explicit and enumerated.** List them as a bulleted list of forbidden behaviours.
- **Evidence requirements must be specific.** Not "use evidence", but "cite at least 2 verbatim quotes of minimum 5 words each."

## Example: Adding an "Interview Question Generator" Skill

Suppose you want to add a skill that generates 10 behavioural interview questions from an assessment result:

```
skills/interview_questions/
├── SKILL.md
```

`SKILL.md` would define:
- Purpose: generate 10 STAR-format behavioural interview questions targeted at the specific gaps and risks in an assessment result
- Process: read the assessment result → identify top 5 evidence gaps → generate 2 questions per gap
- Output: JSON array of `{"question": str, "targets": str, "type": "behavioural"|"situational"}`
- Prohibition: never invent new concerns not in the assessment; do not produce generic questions

Then you'd add a pipeline function, a Pydantic schema, and wire it into the Streamlit UI as an optional second step after assessment.
