# Prompt Engineering Notes

This document captures the key design decisions behind the prompt architecture of the Professional Profile Agent. It exists so that anyone iterating on the skills can understand *why* things are done a certain way — not just what they are.

---

## Why JSON Mode?

All analysis calls use `response_format="json"`, which instructs Claude to return only valid JSON with no surrounding text or markdown fences.

**Rationale:**
1. Downstream code (Pydantic validation, Streamlit rendering) needs structured data, not prose
2. JSON mode eliminates ambiguous parsing — no regex needed to extract data from text
3. It forces Claude to pre-commit to a schema, which reduces hallucinated field names and inconsistent structure
4. It enables automatic retry: if the output fails Pydantic validation, we can feed the error back to Claude in a retry call with the exact field that failed

**Trade-off:** JSON mode can sometimes make responses feel mechanical. We compensate by giving Claude rich, prose-style instructions within the system prompt — the output format is JSON, but the reasoning process is human-readable instruction.

---

## Why Three Pillars?

The Cultural / Operational / Capability split was chosen for three reasons:

1. **Separation of concerns.** These three dimensions are genuinely independent — a candidate can be a perfect cultural fit and a poor operational fit (e.g., a startup founder applying to a large corporate). A single "fit score" obscures this.

2. **Evidence specificity.** Each pillar has different evidence sources. Cultural fit comes from the About section and recommendations; operational fit from company types and scopes; capability from skills and quantified outcomes. Separating them forces Claude to draw from the right evidence for each dimension.

3. **Actionability.** A hiring manager who sees Cultural: 85, Operational: 40, Capability: 90 knows exactly what to probe in the interview — the operational context. A single 72/100 score gives them nothing to work with.

**Weighting:** Cultural 25% + Operational 35% + Capability 40%. Operational is weighted above Cultural because a misaligned operating context (wrong scale, wrong industry, wrong work mode) is a harder problem to solve than a cultural adjustment. Capability is highest because it's the most directly verifiable.

---

## Why Evidence-Grounding?

Every score must be backed by verbatim quotes from the candidate's profile. This is not just anti-hallucination hygiene — it's a design choice that makes the tool useful.

**Problem without evidence-grounding:** An LLM will produce confident-sounding assessments even when the profile is thin. A 1-line LinkedIn summary becomes "demonstrates strong strategic thinking and collaborative approach" — meaningless inference from nothing.

**With evidence-grounding:** If Claude cannot find 2 quotes for a pillar, it must cap the score at 50 and drop confidence. This means sparse profiles get appropriately sceptical assessments, and the confidence score communicates the reliability of the result.

**Implementation:** The SKILL.md file specifies that every evidence item must include `quote`, `source_section`, and `interpretation`. The Pydantic schema enforces this structure. The eval harness checks that quote substrings actually appear in the source text.

---

## Why the Confidence Score?

The fit score and the confidence score answer different questions:

- **Fit score:** "How well does this candidate match the role?"
- **Confidence score:** "How sure are we about the fit score?"

A candidate with a sparse profile might score 75 on capability based on 3 bullets — but the confidence should be 45 because there's almost no evidence to go on. A hiring manager needs to know that the 75 is speculative, not authoritative.

Without a confidence score, the tool would produce identical-seeming outputs for a richly evidenced 75 and a weakly evidenced 75 — a misleading equivalence.

---

## Why In-Context Learning (Not Fine-Tuning)?

The feedback loop works by injecting past high-rated outputs as few-shot examples and past low-rated outputs as "mistakes to avoid" cautions in the system prompt. No model weights are changed.

**Rationale:**
1. Fine-tuning requires data volume and infrastructure we don't have for a v1
2. The analysis changes with every JD — a fine-tuned model would be calibrated to past JDs, not the current one
3. In-context examples are transparent — you can read them, edit them, and remove bad ones
4. In-context learning degrades gracefully: 0 examples = baseline behaviour, 3 examples = better behaviour
5. The feedback mechanism gives users direct agency: their ratings immediately influence future outputs

**Limitation:** In-context examples take up token budget. We cap at 2-3 examples per prompt type. Future improvement: vector-embed past assessments and retrieve the most semantically similar ones rather than just the most recent.

---

## Why Skill Files as Markdown (Not Code)?

The intelligence of this tool is entirely in the prompt engineering, not the code. Putting skills in markdown files rather than f-strings buried in Python:

1. **Readability:** A recruiter or domain expert can read, understand, and propose changes to a markdown file without understanding Python
2. **Diff-ability:** Git diffs on skill changes are readable — you can see exactly what changed in the rubric
3. **Versioning:** Skills can be tagged, branched, and rolled back independently of the application code
4. **Testability:** The eval harness catches regressions when skill files change — skills are tested like code

**Analogy:** Skills are the "schema" of the tool. The code is just the delivery mechanism.

---

## Anti-Hallucination Pattern

Every skill includes an explicit "Anti-Hallucination Rules" section with a bullet list of forbidden behaviours. This is more effective than a general "be accurate" instruction for two reasons:

1. **Specificity activates avoidance.** Telling Claude "never reference an employer not verbatim in the profile" is more effective than "be truthful" — it gives Claude a specific check to run
2. **Enumeration is completeness.** Listing 7 specific forbidden behaviours makes it clear that the list is finite and deliberate — Claude treats it as a checklist, not a vague principle

The most important anti-hallucination rule in the profile curation skill: "Never embellish numbers or scope." This is where hallucination causes the most real-world harm — a CV that survives screening but fails at interview because the numbers don't hold up.

---

## Prompt Caching

Long system prompts (skill + rubric + persona = ~4,000 tokens) are cached via `cache_control: ephemeral` on the Anthropic API. This means:

- First call: full token cost for the system prompt
- Subsequent calls with the same system prompt within 5 minutes: ~10% of the original cost

In practice, assessing a batch of 5 candidates against the same JD means the system prompt is cached after the first call — 4 out of 5 assessments pay only the input token cost for the candidate profile, not the skill.

JD parsing calls skip caching (`cache_system=False`) because they use a smaller model and shorter system prompt — the overhead of caching management exceeds the saving.

---

## Schema Validation and Retry

After every Claude API call, the JSON output is parsed through a Pydantic model. If validation fails (e.g., a missing required field, wrong type, or value out of range):

1. The error is logged
2. A retry call is made with the original message plus the Pydantic error message appended
3. If the retry also fails, the exception propagates to the UI with a clear error message

This pattern catches the most common failure mode — Claude occasionally omits a required field or returns a score outside the 0-100 range. The retry, with the explicit error, almost always succeeds.

We deliberately retry only once. A second failure suggests a systemic prompt issue, not a random output quality fluctuation.
