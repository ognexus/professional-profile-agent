# Candidate Analysis — Scoring Rubric

**Version:** 1.0  
**Used by:** `skills/candidate_analysis/SKILL.md`

Each pillar is scored 0–100. Use these anchor descriptions to calibrate your scores.  
Scores between anchors (e.g., 60) should blend the nearest two descriptions proportionally.

---

## Cultural Fit

| Score | Anchor Description |
|-------|--------------------|
| **0** | No evidence of values, work style, or communication approach in the profile. Or evidence directly contradicts the stated culture (e.g., solo operator applying for a deeply collaborative role with no mention of teamwork anywhere). |
| **25** | One weak signal — e.g., one brief mention of a value that loosely aligns, but contradicted by other signals (e.g., profile emphasises individual achievement heavily for a "we not I" culture). |
| **50** | Some alignment, but evidence is generic or thin. The candidate doesn't actively contradict the culture, but there's no compelling evidence of a deep match. Values mentioned but not demonstrated with specific examples. |
| **75** | Clear alignment on 2+ culture dimensions with specific evidence. For example: profile explicitly describes collaborative ways of working, gives specific examples of cross-functional leadership, and has volunteer/community work that aligns with the stated company mission. |
| **100** | Exceptional alignment. The candidate's About section, writing tone, volunteer work, recommendations, and role choices all coherently tell a story that maps directly onto the specific culture described in the JD. Evidence is rich, specific, and cross-corroborated from multiple profile sections. |

---

## Operational Fit

| Score | Anchor Description |
|-------|--------------------|
| **0** | No relevant operational experience. E.g., candidate has only worked in large enterprises for a Series A startup role requiring "comfortable with ambiguity and building from zero", with no evidence of unstructured or early-stage context. |
| **25** | Significant operational mismatch on at least one key dimension (e.g., industry, team size, or work mode) with no compensating evidence. Only one dimension partially aligns. |
| **50** | Moderate fit — the candidate has operated in somewhat similar contexts, but key dimensions are missing or unclear. E.g., right industry, but always individual contributor with no evidence of the people management the role requires. |
| **75** | Strong operational match. Candidate has held a role with substantively similar operating context (team size, industry vertical, work mode, decision authority) within the last 5 years, with explicit evidence from the profile. At least 2 dimensions match clearly. |
| **100** | Near-perfect operational alignment. The candidate's current or most recent role is essentially the same operating context as the target role — same scale, same industry, same work mode, same structural position (e.g., IC vs. lead), with explicit, recent evidence from the profile. |

---

## Capability Fit

| Score | Anchor Description |
|-------|--------------------|
| **0** | No evidence of any must-have requirements from the JD. The candidate's background is entirely unrelated to the role's technical/functional demands. |
| **25** | 1 of 3+ must-have requirements evidenced. Candidate has a tangential background but lacks the core technical or functional skills named in the JD. |
| **50** | About half the must-have requirements evidenced, with the other half absent or only weakly implied. Nice-to-haves are mostly missing. Role could be a stretch with significant upskilling. |
| **75** | Has held a role with substantively similar scope at a comparable company within the last 3 years, with at least one quantified outcome that demonstrates the capability. Most must-have requirements evidenced; some nice-to-haves present. At most one significant gap in must-haves. |
| **100** | All must-have requirements directly evidenced with specific examples and measurable outcomes. Most nice-to-haves present. The candidate has done substantially the same work at comparable or greater scale and recency. No material capability gaps. |

---

## Confidence Score (applies across all pillars)

The confidence score reflects **how much reliable evidence was available** — not how good the candidate is.

| Score | Anchor Description |
|-------|--------------------|
| **0–20** | Profile is essentially empty — only a name/headline with no substantive content. No reliable scoring is possible. |
| **21–40** | Very sparse profile. Only 1–2 sections have any content. Assessment is based almost entirely on inference and must be treated with high scepticism. |
| **41–60** | Partial profile. Some sections are present but key evidence is missing (e.g., no About section, no quantified outcomes in Experience, no Skills listed). Scores are directional at best. |
| **61–80** | Adequate profile. Most key sections are present with reasonable detail. Some gaps remain (e.g., no Recommendations, limited quantification) but the overall picture is credible. |
| **81–100** | Rich, detailed profile. All major sections present, experience descriptions are specific and quantified, Recommendations provide third-party corroboration. Assessment is based on strong evidence. |

---

## Recommendation Thresholds

| Recommendation | Criteria |
|---------------|----------|
| `strong_yes` | overall_fit_score ≥ 80 AND overall_confidence ≥ 70 AND zero critical capability gaps (all JD must-haves evidenced) |
| `yes` | overall_fit_score ≥ 65 AND overall_confidence ≥ 55 |
| `maybe` | overall_fit_score 45–64, OR overall_confidence < 55, OR 1+ critical must-have capability gap |
| `no` | overall_fit_score < 45, OR 2+ critical must-have capability gaps regardless of other scores |

**Critical capability gap:** A must-have JD requirement for which there is zero evidence in the candidate's profile.
