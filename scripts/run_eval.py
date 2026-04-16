#!/usr/bin/env python3
"""
run_eval.py — Run the full eval suite and print a summary table.

Usage:
    python scripts/run_eval.py

Requires ANTHROPIC_API_KEY in the environment. Hits the real API.
Costs approximately $1-3 per full run depending on model.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.claude_client import ClaudeClient
from app.assessor.pipeline import AssessorPipeline
from app.curator.pipeline import CuratorPipeline

EVAL_DIR = Path(__file__).parent.parent / "tests" / "eval_cases"

ASSESSOR_CASES = [
    # (jd_file, profile_file, expected_tier)  — "strong" = expected > 70, "weak" = expected < 50
    ("jd_tech_ic.md", "candidate_strong_tech.md", "strong"),
    ("jd_consulting.md", "candidate_strong_consulting.md", "strong"),
    ("jd_education.md", "candidate_strong_education.md", "strong"),
    ("jd_tech_ic.md", "candidate_weak_tech.md", "weak"),
    ("jd_consulting.md", "candidate_weak_consulting.md", "weak"),
    ("jd_education.md", "candidate_weak_education.md", "weak"),
]

CURATOR_CASES = [
    ("jd_tech_ic.md", "user_cv_tech.md"),
    ("jd_consulting.md", "user_cv_consulting.md"),
]


def _load(filename: str) -> str:
    return (EVAL_DIR / filename).read_text(encoding="utf-8")


def run_assessor_eval(pipeline: AssessorPipeline) -> list[dict]:
    results = []
    for jd_file, profile_file, expected_tier in ASSESSOR_CASES:
        print(f"  Assessing: {profile_file[:30]} vs {jd_file[:25]}...", end=" ", flush=True)
        start = time.time()
        try:
            jd_text = _load(jd_file)
            profile_text = _load(profile_file)
            result, _ = pipeline.assess(jd_text=jd_text, candidate_profile_text=profile_text)
            elapsed = time.time() - start

            if expected_tier == "strong":
                passed = result.overall_fit_score >= 70
            else:
                passed = result.overall_fit_score < 50

            results.append({
                "jd": jd_file,
                "profile": profile_file,
                "expected": expected_tier,
                "score": result.overall_fit_score,
                "confidence": result.overall_confidence,
                "recommendation": result.recommendation,
                "passed": passed,
                "elapsed": round(elapsed, 1),
            })
            status = "PASS" if passed else "FAIL"
            print(f"{status} (score={result.overall_fit_score}, {elapsed:.1f}s)")
        except Exception as e:
            elapsed = time.time() - start
            results.append({
                "jd": jd_file,
                "profile": profile_file,
                "expected": expected_tier,
                "score": None,
                "passed": False,
                "elapsed": round(elapsed, 1),
                "error": str(e),
            })
            print(f"ERROR: {e}")
    return results


def run_curator_eval(pipeline: CuratorPipeline) -> list[dict]:
    results = []
    for jd_file, user_cv_file in CURATOR_CASES:
        print(f"  Curating: {user_cv_file[:30]} for {jd_file[:25]}...", end=" ", flush=True)
        start = time.time()
        try:
            content = _load(user_cv_file)
            cv_text = content
            linkedin_text = ""
            if "**LinkedIn Profile Text**" in content:
                parts = content.split("**LinkedIn Profile Text**")
                cv_text = parts[0]
                linkedin_text = parts[1] if len(parts) > 1 else ""

            jd_text = _load(jd_file)
            result, _ = pipeline.curate(
                jd_text=jd_text,
                current_cv_text=cv_text,
                linkedin_text=linkedin_text,
            )
            elapsed = time.time() - start
            cl = result.cover_letter
            word_count = len(cl.split())
            passed = 200 <= word_count <= 400

            results.append({
                "jd": jd_file,
                "user_cv": user_cv_file,
                "strong_matches": len(result.gap_analysis.strong_matches),
                "missing": len(result.gap_analysis.missing),
                "cover_letter_words": word_count,
                "passed": passed,
                "elapsed": round(elapsed, 1),
            })
            status = "PASS" if passed else "FAIL"
            print(f"{status} ({word_count} words, {elapsed:.1f}s)")
        except Exception as e:
            elapsed = time.time() - start
            results.append({
                "jd": jd_file,
                "user_cv": user_cv_file,
                "passed": False,
                "elapsed": round(elapsed, 1),
                "error": str(e),
            })
            print(f"ERROR: {e}")
    return results


def print_summary(assessor_results: list[dict], curator_results: list[dict]):
    print("\n" + "=" * 70)
    print("EVAL SUMMARY")
    print("=" * 70)

    print("\nASSESSOR RESULTS")
    print(f"{'Profile':<35} {'Expected':<8} {'Score':<6} {'Pass':<5} {'Secs'}")
    print("-" * 70)
    assessor_pass = 0
    for r in assessor_results:
        profile = r["profile"][:34]
        expected = r["expected"]
        score = str(r.get("score", "ERR"))
        passed = "YES" if r["passed"] else "NO"
        elapsed = r["elapsed"]
        print(f"{profile:<35} {expected:<8} {score:<6} {passed:<5} {elapsed}s")
        if r["passed"]:
            assessor_pass += 1

    print(f"\nAssessor pass rate: {assessor_pass}/{len(assessor_results)}")

    print("\nCURATOR RESULTS")
    print(f"{'User CV':<30} {'Matches':<8} {'Missing':<8} {'CL Words':<10} {'Pass':<5} {'Secs'}")
    print("-" * 70)
    curator_pass = 0
    for r in curator_results:
        user_cv = r["user_cv"][:29]
        matches = str(r.get("strong_matches", "ERR"))
        missing = str(r.get("missing", "ERR"))
        words = str(r.get("cover_letter_words", "ERR"))
        passed = "YES" if r["passed"] else "NO"
        elapsed = r["elapsed"]
        print(f"{user_cv:<30} {matches:<8} {missing:<8} {words:<10} {passed:<5} {elapsed}s")
        if r["passed"]:
            curator_pass += 1

    print(f"\nCurator pass rate: {curator_pass}/{len(curator_results)}")

    total = len(assessor_results) + len(curator_results)
    total_pass = assessor_pass + curator_pass
    print(f"\nOVERALL: {total_pass}/{total} cases passed")
    print("=" * 70)


def main():
    print("Professional Profile Agent — Eval Run")
    print("=" * 70)

    client = ClaudeClient()
    assessor = AssessorPipeline(client)
    curator = CuratorPipeline(client)

    print("\nRunning assessor eval cases...")
    assessor_results = run_assessor_eval(assessor)

    print("\nRunning curator eval cases...")
    curator_results = run_curator_eval(curator)

    print_summary(assessor_results, curator_results)


if __name__ == "__main__":
    main()
