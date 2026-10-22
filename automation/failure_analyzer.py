import json
import os
from pathlib import Path
from typing import List

from dotenv import load_dotenv
from google import genai
from pydantic import BaseModel, Field


# ============================================================
# CONFIG
# ============================================================

ROOT_DIR = Path(__file__).resolve().parent.parent

ARTIFACT_DIR = ROOT_DIR / "artifacts"

EXECUTION_RESULTS = (
    ARTIFACT_DIR / "journey_execution_results.json"
)

OUTPUT_FILE = (
    ARTIFACT_DIR / "failure_analysis.json"
)

load_dotenv(ROOT_DIR / ".env")

GEMINI_API_KEY = os.getenv(
    "GEMINI_API_KEY"
)

GEMINI_MODEL = os.getenv(
    "GEMINI_MODEL",
    "gemini-3.5-flash-lite",
)


# ============================================================
# VALIDATION
# ============================================================

if not GEMINI_API_KEY:
    raise RuntimeError(
        "GEMINI_API_KEY is missing from .env"
    )


# ============================================================
# GEMINI CLIENT
# ============================================================

client = genai.Client(
    api_key=GEMINI_API_KEY
)


# ============================================================
# STRUCTURED OUTPUT SCHEMAS
# ============================================================

class FailureAnalysis(BaseModel):

    category: str = Field(
        description=(
            "Failure category. Use one of: "
            "UI_CHANGE, LOCATOR_FAILURE, "
            "APPLICATION_BUG, NETWORK_FAILURE, "
            "DATA_FAILURE, TIMING_FAILURE, "
            "ENVIRONMENT_FAILURE, TEST_ISSUE, "
            "UNKNOWN."
        )
    )

    root_cause: str = Field(
        description=(
            "Most likely root cause of the failure "
            "based strictly on the available evidence."
        )
    )

    evidence: List[str] = Field(
        description=(
            "Concrete pieces of evidence supporting "
            "the diagnosis."
        )
    )

    confidence: int = Field(
        description=(
            "Confidence from 0 to 100."
        )
    )

    application_bug: bool = Field(
        description=(
            "Whether the evidence suggests that "
            "the application itself is defective."
        )
    )

    suggested_fix: str = Field(
        description=(
            "Recommended next action for the "
            "automation/test engineer."
        )
    )

    selector_change: str = Field(
        description=(
            "If the failure appears related to a "
            "changed selector, describe the likely "
            "new selector or locator strategy. "
            "Otherwise return an empty string."
        )
    )

    explanation: str = Field(
        description=(
            "Short technical explanation of the "
            "failure."
        )
    )


class FailureAnalysisResponse(BaseModel):

    failures: List[FailureAnalysis]


# ============================================================
# HELPERS
# ============================================================

def load_json(path: Path):

    if not path.exists():
        raise FileNotFoundError(
            f"File not found:\n{path}"
        )

    with open(
        path,
        "r",
        encoding="utf-8"
    ) as file:

        return json.load(file)


def save_json(
    path: Path,
    data
):

    path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with open(
        path,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            data,
            file,
            indent=2,
            ensure_ascii=False
        )


# ============================================================
# BUILD FAILURE CONTEXT
# ============================================================

def build_failure_context(
    execution_results
):

    failures = []

    journeys = execution_results.get(
        "journeys",
        []
    )

    for journey in journeys:

        if journey.get(
            "status"
        ) != "failed":

            continue

        journey_title = journey.get(
            "title",
            ""
        )

        journey_error = journey.get(
            "error",
            ""
        )

        steps = journey.get(
            "steps",
            []
        )

        failed_steps = [
            step
            for step in steps
            if step.get(
                "status"
            ) == "failed"
        ]

        for step in failed_steps:

            failures.append(
                {
                    "journey_index": journey.get(
                        "journey_index"
                    ),
                    "journey_title": journey_title,
                    "journey_type": journey.get(
                        "type"
                    ),
                    "journey_priority": journey.get(
                        "priority"
                    ),
                    "expected_result": journey.get(
                        "expected_result"
                    ),
                    "journey_error": journey_error,

                    "step": step.get(
                        "step"
                    ),

                    "action": step.get(
                        "action"
                    ),

                    "target": step.get(
                        "target"
                    ),

                    "value": step.get(
                        "value"
                    ),

                    "locator_strategy": step.get(
                        "locator_strategy"
                    ),

                    "error": step.get(
                        "error"
                    ),

                    "before": step.get(
                        "before"
                    ),

                    "after": step.get(
                        "after"
                    ),

                    "screenshot": step.get(
                        "screenshot"
                    ),

                    "dom_snapshot": step.get(
                        "dom_snapshot"
                    ),
                }
            )

    return failures


# ============================================================
# AI ANALYSIS
# ============================================================

def analyze_failures(
    failures
):

    if not failures:

        return {
            "failures": []
        }

    prompt = f"""
You are the Failure Intelligence engine of an
AI-powered software testing platform.

Analyze the failed automated tests below.

Your job is NOT simply to repeat the error.

Determine the most likely technical reason for
each failure using only the available evidence.

Possible categories:

- UI_CHANGE
- LOCATOR_FAILURE
- APPLICATION_BUG
- NETWORK_FAILURE
- DATA_FAILURE
- TIMING_FAILURE
- ENVIRONMENT_FAILURE
- TEST_ISSUE
- UNKNOWN

Important rules:

1. Do not invent application behavior.
2. Do not assume something is an application bug
   merely because a test failed.
3. Distinguish locator/test problems from actual
   application defects.
4. Use the before/after page information.
5. Use locator strategy when available.
6. Use DOM snapshot information when available.
7. If evidence is insufficient, use UNKNOWN.
8. Confidence must reflect evidence quality.
9. If a selector appears to have changed, explain
   what evidence suggests the replacement.
10. The suggested fix must be practical for an
    SDET/automation engineer.

FAILED TEST DATA:

{json.dumps(
    failures,
    indent=2,
    ensure_ascii=False
)}
"""

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config={
            "response_mime_type": "application/json",
            "response_schema": FailureAnalysisResponse,
        },
    )

    return json.loads(
        response.text
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("=" * 70)
    print(
        "AI TEST INTELLIGENCE - FAILURE ANALYZER"
    )
    print("=" * 70)

    execution_results = load_json(
        EXECUTION_RESULTS
    )

    failures = build_failure_context(
        execution_results
    )

    print()
    print(
        f"Failed steps found: {len(failures)}"
    )

    if not failures:

        print()
        print(
            "No failures found."
        )

        save_json(
            OUTPUT_FILE,
            {
                "failures": [],
                "summary": {
                    "total_failures": 0
                }
            }
        )

        return

    print()
    print(
        "Sending failure evidence to Gemini..."
    )

    analysis = analyze_failures(
        failures
    )

    # --------------------------------------------------------
    # Add original execution evidence to result
    # --------------------------------------------------------

    final_output = {
        "summary": {
            "total_failures": len(
                failures
            )
        },

        "failures": []
    }

    ai_failures = analysis.get(
        "failures",
        []
    )

    for index, failure in enumerate(
        failures
    ):

        ai_analysis = (
            ai_failures[index]
            if index < len(ai_failures)
            else {}
        )

        final_output[
            "failures"
        ].append(
            {
                "execution_evidence": failure,
                "ai_analysis": ai_analysis,
            }
        )

    save_json(
        OUTPUT_FILE,
        final_output
    )

    # --------------------------------------------------------
    # Display
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print(
        "FAILURE INTELLIGENCE RESULTS"
    )
    print("=" * 70)

    for index, failure in enumerate(
        final_output["failures"],
        start=1
    ):

        evidence = failure[
            "execution_evidence"
        ]

        ai = failure[
            "ai_analysis"
        ]

        print()
        print(
            f"FAILURE {index}"
        )

        print(
            "-" * 70
        )

        print(
            "Journey:",
            evidence.get(
                "journey_title"
            )
        )

        print(
            "Step:",
            evidence.get(
                "step"
            )
        )

        print(
            "Action:",
            evidence.get(
                "action"
            )
        )

        print(
            "Target:",
            evidence.get(
                "target"
            )
        )

        print(
            "Error:",
            evidence.get(
                "error"
            )
        )

        print()

        print(
            "Category:",
            ai.get(
                "category"
            )
        )

        print(
            "Root Cause:",
            ai.get(
                "root_cause"
            )
        )

        print(
            "Application Bug:",
            ai.get(
                "application_bug"
            )
        )

        print(
            "Confidence:",
            ai.get(
                "confidence"
            )
        )

        print(
            "Explanation:",
            ai.get(
                "explanation"
            )
        )

        print(
            "Suggested Fix:",
            ai.get(
                "suggested_fix"
            )
        )

        if ai.get(
            "selector_change"
        ):

            print(
                "Selector Change:",
                ai.get(
                    "selector_change"
                )
            )

        print()

        evidence_items = ai.get(
            "evidence",
            []
        )

        if evidence_items:

            print(
                "Evidence:"
            )

            for item in evidence_items:

                print(
                    f"  - {item}"
                )

    print()
    print("=" * 70)

    print(
        "Saved:"
    )

    print(
        OUTPUT_FILE
    )

    print("=" * 70)


if __name__ == "__main__":
    main()