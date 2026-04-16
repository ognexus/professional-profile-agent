# Skill: Job Description Parsing

**Version:** 1.0  
**Authors:** Recruiter + Prompt Engineer  
**Used by:** `app/assessor/pipeline.py`, `app/curator/pipeline.py`

---

## Purpose

Extract structured, usable data from a raw job description (JD). This skill is used as the first step in both the Candidate Assessment and Profile Curation pipelines. It ensures both pipelines work from a consistent, structured understanding of the role rather than reading the raw JD in full each time.

**Rules:**
- Extract verbatim quotes where possible — do not paraphrase requirements
- Mark anything inferred (not verbatim from the JD) with a trailing `[inferred]` note
- Never invent requirements, company details, or culture signals that are not present in the JD
- If a field cannot be determined from the JD, return `null` — do not guess

---

## Output JSON Schema

Return **only** valid JSON matching this exact schema. No commentary, no markdown fences.

```json
{
  "role_title": "string — exact title from the JD",
  "company": "string or null — company name if stated",
  "team_context": "string or null — team size, reporting line, function if mentioned",
  "must_have_requirements": [
    "string — verbatim or near-verbatim JD language for non-negotiable requirements"
  ],
  "nice_to_have_requirements": [
    "string — verbatim or near-verbatim JD language for preferred but not required"
  ],
  "responsibilities": [
    "string — key responsibilities described in the JD"
  ],
  "culture_signals": [
    "string — language hinting at culture, values, or ways of working. Examples: 'move fast and iterate', 'consensus-driven', 'data-informed', 'high-performance team'"
  ],
  "compensation": "string or null — salary range, equity, or total comp if stated",
  "location_and_work_mode": "string or null — location, remote/hybrid/on-site policy if stated",
  "red_flags": [
    "string — concerning language patterns in the JD. Examples: unrealistic skill combos ('5 years experience in a 3-year-old technology'), vague responsibilities, 'wear many hats' without scope clarity, excessive 'hustle' language"
  ]
}
```

---

## Classification Guidelines

### Must-have vs. Nice-to-have

Look for explicit language signals:

**Must-have indicators:**
- "Required", "must have", "essential", "you will need", "minimum X years of", "you must", listing in primary requirements section

**Nice-to-have indicators:**
- "Preferred", "nice to have", "bonus", "a plus", "advantageous", "ideally", "familiarity with", listing in secondary/preferred section

**Ambiguous:** If the JD doesn't clearly signal, default to `must_have` for requirements in the primary responsibilities section and `nice_to_have` for anything in secondary sections or listed after "additionally."

### Culture Signals

Extract direct quotes and note the cultural implication:

| JD Language | Cultural Signal |
|-------------|----------------|
| "Move fast", "fast-paced" | High velocity, low process, startup-like |
| "Consensus-driven", "collaborative decisions" | Flat hierarchy, slow to move |
| "Data-informed", "metrics-driven" | Analytical culture, expect to justify with data |
| "Wear many hats" | Resource-constrained, expects generalists |
| "High-performance team" | Competitive culture, high output expectations |
| "Mission-driven" | Values alignment matters more than compensation |
| "Work autonomously" | Low oversight, self-direction required |
| "Cross-functional" | Requires stakeholder management, not siloed |

### Red Flags

Identify any of the following:
- Skill combination that is unrealistic ("5 years of Kubernetes" when Kubernetes is ~8 years old is not a flag, but "5 years of GPT-4" for a 1-year-old tool is)
- Responsibilities so vague they could describe any role in any company
- Excessive "startup hustle" language without any mention of compensation, equity, or work-life balance
- Multiple conflicting signals (e.g., "collaborative culture" + "you will be the sole person in this function")
- Seniority mismatch (e.g., "Senior" in title but "0–2 years experience" in requirements)
- Salary / compensation listed significantly below market for the stated requirements

---

## Extraction Procedure

1. Read the entire JD before extracting anything
2. Identify the role title (first pass)
3. Find the "Requirements" or "Qualifications" section — this is the primary source for must-haves
4. Find the "Responsibilities" or "What you'll do" section
5. Scan for any "Preferred" or "Nice to have" section
6. Read the company description and any "About us" section for culture signals
7. Check for compensation and location information (often at top or bottom)
8. Identify red flags last — you need the full picture before flagging
9. Output valid JSON only
