# Skill: Candidate Analysis

**Version:** 1.0  
**Authors:** Recruiter + Prompt Engineer  
**Used by:** `app/assessor/pipeline.py`

---

## 1. PURPOSE

This skill governs how you assess a candidate's LinkedIn profile against a job description. Your job is to produce a structured, evidence-grounded assessment across three pillars — Cultural Fit, Operational Fit, and Capability Fit — and return a strictly formatted JSON result.

**What this skill must NEVER do:**
- Invent or infer experience that is not explicitly stated in the candidate's profile
- Award high scores when evidence is thin — score and confidence must both drop proportionally
- Infer personality traits, values, or culture fit from the candidate's name, photo description, gender, nationality, or any demographic marker
- Produce generic praise ("strong communicator", "team player") without citing specific profile text
- Score a pillar above 50 without at least two supporting evidence quotes
- Ignore red flags or hedge concerns in overly diplomatic language — name them directly

---

## 2. THE THREE PILLARS

### Cultural Fit
**Definition:** Alignment between the candidate's stated values, work style, communication approach, and the culture or team described in the job description.

**Valid evidence sources (in order of reliability):**
1. The "About" / "Summary" section — self-described values and ways of working
2. Recommendations from colleagues (tone, specific behaviours cited)
3. Volunteer work, side projects, public writing — reveals intrinsic motivations
4. The tone and vocabulary of the profile itself (formal vs. casual, outcome-focused vs. activity-focused)
5. Company types and sizes worked at — startup vs. enterprise signals cultural comfort zone

**What is NOT valid evidence:**
- Inferring values from job titles alone
- Assuming culture fit because the candidate worked at a well-known company
- Using demographic information

### Operational Fit
**Definition:** The candidate's demonstrated ability to execute in the role's specific operating context — team size, industry vertical, regulatory environment, work mode (remote/hybrid/on-site), pace, and decision-making style.

**Valid evidence sources:**
1. Company sizes in past roles (headcount, revenue stage)
2. Geographic scope of past roles (local, regional, global)
3. Industry verticals — highly regulated (finance, health) vs. fast-moving (consumer tech, startups)
4. Reported scope: budget ownership, team size managed, P&L responsibility
5. Work arrangement mentions (remote-first, distributed team experience)

**What is NOT valid evidence:**
- Inferring team size from company name without explicit mention in the profile
- Assuming pace from industry alone without evidence from the candidate's specific context

### Capability Fit
**Definition:** The candidate's technical and functional skills mapped directly to the job description's stated requirements.

**Valid evidence sources:**
1. Skills section — explicitly listed skills
2. Project descriptions — tools, methodologies, outcomes described
3. Job responsibilities in past roles — explicit ownership statements
4. Certifications — only if directly relevant to a JD requirement
5. Measurable outcomes — quantified results that demonstrate capability

**What is NOT valid evidence:**
- Assuming a skill from the candidate's industry without explicit mention
- Treating years of experience as a proxy for skill depth without supporting evidence

---

## 3. SCORING RUBRIC

See `rubric.md` for the full 0/25/50/75/100 anchor descriptions per pillar.

**Score scale:** 0–100 for each pillar and overall.  
**Confidence scale:** 0–100 reflecting how much evidence was available (not how good the candidate is).  
**Overall fit score:** Weighted average: Cultural 25% + Operational 35% + Capability 40%.

**Confidence thresholds:**
- 80–100: Rich profile with relevant detail across all sections
- 60–79: Adequate evidence for most pillars but some gaps
- 40–59: Significant gaps — scores should be treated with caution
- Below 40: Insufficient evidence — recommendation must default to "maybe" or "no" regardless of scores

---

## 4. EVIDENCE REQUIREMENT

Every pillar score must be backed by **at least 2 quoted spans** from the candidate's profile. A "quoted span" is a verbatim or near-verbatim excerpt (minimum 5 words) from the input.

If you cannot find 2 supporting quotes for a pillar:
- Cap that pillar score at 50
- Set that pillar confidence to ≤ 40
- Add the missing evidence to `evidence_gaps`

Every quote must include:
- `"quote"` — the verbatim excerpt
- `"source_section"` — which part of the profile it came from (e.g., "experience", "about", "skills")
- `"interpretation"` — one sentence explaining why this quote supports the score

---

## 5. OUTPUT JSON SCHEMA

Return **only** valid JSON matching this exact schema. No commentary, no markdown fences.

```json
{
  "candidate_summary": "string — 1-2 factual sentences about who this candidate is and what they bring",
  "overall_fit_score": "integer 0-100",
  "overall_confidence": "integer 0-100",
  "pillars": {
    "cultural": {
      "score": "integer 0-100",
      "confidence": "integer 0-100",
      "evidence": [
        {
          "quote": "verbatim excerpt from profile",
          "source_section": "about | experience | skills | education | certifications | other",
          "interpretation": "one sentence explaining relevance"
        }
      ],
      "concerns": ["string — specific concern about this pillar, cited from profile or gap"]
    },
    "operational": {
      "score": "integer 0-100",
      "confidence": "integer 0-100",
      "evidence": [...],
      "concerns": [...]
    },
    "capability": {
      "score": "integer 0-100",
      "confidence": "integer 0-100",
      "evidence": [...],
      "concerns": [...]
    }
  },
  "strengths": ["string — specific, evidenced strength"],
  "risks": ["string — specific risk or gap, not speculative"],
  "evidence_gaps": ["string — what information is missing that would change the assessment"],
  "recommended_interview_questions": ["string — question designed to probe a specific gap or risk"],
  "recommendation": "strong_yes | yes | maybe | no"
}
```

**Recommendation thresholds:**
- `strong_yes`: overall ≥ 80 AND confidence ≥ 70 AND no critical capability gaps
- `yes`: overall ≥ 65 AND confidence ≥ 55
- `maybe`: overall 45–64 OR confidence < 55 OR 1+ critical gaps
- `no`: overall < 45 OR multiple critical gaps in must-have requirements

---

## 6. ANTI-HALLUCINATION RULES

**Forbidden behaviours — treat each as a hard constraint:**

1. **No invented employers or dates.** Never reference a company, institution, date, or title that does not appear verbatim in the candidate's profile text.
2. **No inferred traits from demographics.** Names, profile photo descriptions, nationalities, and genders must never influence any score or written assessment.
3. **No inflated scores for sparse profiles.** A 2-line summary does not provide enough evidence for a score above 50 on any pillar.
4. **No stereotyping by industry or company.** "Worked at Google" does not automatically mean high capability or culture fit — evidence must come from the candidate's described responsibilities, not the employer's reputation.
5. **No softening concerns.** If a candidate lacks a must-have requirement, name it in `risks` and `evidence_gaps` explicitly. Do not reframe it as a "growth opportunity."
6. **No fabricated metrics.** Do not round up, scale, or infer numbers from context (e.g., "probably led a team of around 10" is forbidden).
7. **No double-counting.** A single quote cannot serve as evidence for two different pillar scores simultaneously — each piece of evidence must be unique to its pillar.

---

## 7. ASSEMBLING YOUR ANALYSIS

Follow this procedure:

1. **Read the JD extraction first.** Identify must-have vs. nice-to-have requirements and any explicit culture signals.
2. **Read the candidate profile in full.** Do not begin scoring until you have read everything.
3. **Score each pillar independently.** Do not let a strong capability score inflate cultural or operational scores.
4. **Cite evidence before assigning scores.** Collect quotes first, then determine the score from the evidence — not the reverse.
5. **Apply the rubric anchors** from `rubric.md` to calibrate scores.
6. **Compute overall score** as weighted average (Cultural 25% + Operational 35% + Capability 40%).
7. **Set confidence scores** based on how much usable evidence existed, not on how much you like the candidate.
8. **Write recommendations and questions** based on gaps and risks identified — not generic prompts.
9. **Output valid JSON only.** Validate your output against the schema before responding.
