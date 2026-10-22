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

BASE_DIR = Path(__file__).resolve().parent.parent
ARTIFACTS_DIR = BASE_DIR / "artifacts"

FAILURE_ANALYSIS_FILE = ARTIFACTS_DIR / "failure_analysis.json"
EXECUTION_RESULTS_FILE = ARTIFACTS_DIR / "journey_execution_results.json"
OUTPUT_FILE = ARTIFACTS_DIR / "bug_reports.json"

ENV_FILE = BASE_DIR / ".env"

load_dotenv(ENV_FILE)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")


if not GEMINI_API_KEY:
    raise RuntimeError(
        "GEMINI_API_KEY is missing. Add it to C:\\ai-test-intelligence\\.env"
    )


# ============================================================
# PYDANTIC MODELS
# ============================================================

class BugReport(BaseModel):
    bug_id: str = ""
    title: str

    severity: str = Field(
        description="One of: Critical, High, Medium, Low"
    )

    priority: str = Field(
        description="One of: P0, P1, P2, P3"
    )

    category: str

    status: str = "New"

    summary: str

    preconditions: List[str] = []

    steps_to_reproduce: List[str]

    expected_result: str

    actual_result: str

    environment: List[str] = []

    evidence: List[str] = []

    root_cause: str = ""

    suggested_fix: str = ""

    automation_impact: str = ""

    reproducibility: str = ""

    affected_area: str = ""


class BugReportCollection(BaseModel):
    bugs: List[BugReport]


# ============================================================
# HELPERS
# ============================================================

def load_json(path: Path):
    if not path.exists():
        raise FileNotFoundError(f"Required file not found: {path}")

    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def save_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=2, ensure_ascii=False)


def normalize_category(category: str) -> str:
    mapping = {
        "UI_CHANGE": "UI",
        "LOCATOR_FAILURE": "Automation / Locator",
        "APPLICATION_BUG": "Functional",
        "NETWORK_FAILURE": "Network",
        "DATA_FAILURE": "Data",
        "TIMING_FAILURE": "Performance / Timing",
        "ENVIRONMENT_FAILURE": "Environment",
        "TEST_ISSUE": "Test Issue",
        "UNKNOWN": "Unknown",
    }

    return mapping.get(category, category or "Unknown")


# ============================================================
# PREPARE FAILURE CONTEXT
# ============================================================

def build_failure_context(failure_analysis, execution_results):
    context = {
        "failure_analysis": failure_analysis,
        "execution_results": execution_results,
    }

    return json.dumps(
        context,
        indent=2,
        ensure_ascii=False,
    )


# ============================================================
# AI BUG GENERATION
# ============================================================

def generate_bug_reports(failure_analysis, execution_results):
    client = genai.Client(api_key=GEMINI_API_KEY)

    failure_context = build_failure_context(
        failure_analysis,
        execution_results,
    )

    prompt = f"""
You are an expert Senior SDET and QA Automation Engineer.

You are given:

1. AI failure analysis from an automated test execution.
2. The original journey execution results.

Your task is to convert genuine application/test failures into professional
software defect reports.

IMPORTANT RULES:

1. Do NOT invent failures.
2. Only create a bug when the evidence supports an actual application defect.
3. If the failure is clearly caused by the automation framework, locator,
   test data, timing, environment, or test design, do NOT report it as an
   application bug.
4. You may create an automation issue separately when appropriate.
5. Never invent URLs, buttons, pages, API responses, database values,
   error messages, or functionality.
6. Use only information present in the supplied execution evidence.
7. Make reproduction steps deterministic and numbered logically.
8. Expected result must describe what should happen.
9. Actual result must describe what actually happened.
10. Severity must be based on demonstrated impact, not speculation.
11. Priority must be based on the available evidence.
12. Keep the bug report suitable for Jira or another defect management tool.
13. Evidence should mention concrete artifacts such as screenshots, DOM,
    execution logs, or failure analysis when available.
14. If no genuine application bug exists, return an empty bugs list.

SEVERITY GUIDANCE:

Critical:
- Application cannot be used
- Data loss
- Security-critical failure
- Complete core workflow failure

High:
- Important business workflow is broken
- Major functionality is unusable
- Significant user impact

Medium:
- Functional issue with workaround
- Limited workflow impact
- Important UI/behavior defect

Low:
- Minor UI issue
- Cosmetic issue
- Low-impact behavior

PRIORITY:

P0 = immediate/blocking
P1 = urgent
P2 = normal
P3 = low

CATEGORY SHOULD REFLECT THE ACTUAL ISSUE.

The output must contain professional bug reports only.

FAILURE / EXECUTION CONTEXT:

{failure_context}
"""

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config={
            "response_mime_type": "application/json",
            "response_schema": BugReportCollection,
            "temperature": 0.1,
        },
    )

    if not response.parsed:
        raise RuntimeError("Gemini returned no structured bug reports.")

    return response.parsed


# ============================================================
# MAIN
# ============================================================

def main():
    print("=" * 70)
    print("AI BUG GENERATOR")
    print("=" * 70)

    print(f"Failure analysis : {FAILURE_ANALYSIS_FILE}")
    print(f"Execution results: {EXECUTION_RESULTS_FILE}")
    print(f"Gemini model     : {GEMINI_MODEL}")
    print()

    failure_analysis = load_json(FAILURE_ANALYSIS_FILE)
    execution_results = load_json(EXECUTION_RESULTS_FILE)

    print("Loaded failure analysis.")
    print("Loaded execution results.")
    print()

    print("Generating defect reports with Gemini...")

    result = generate_bug_reports(
        failure_analysis,
        execution_results,
    )

    bugs = result.bugs

    # Add stable local IDs.
    for index, bug in enumerate(bugs, start=1):
        bug.bug_id = f"BUG-{index:04d}"
        bug.category = normalize_category(bug.category)

    output = {
        "generated_by": "AI Test Intelligence",
        "model": GEMINI_MODEL,
        "total_bugs": len(bugs),
        "bugs": [
            bug.model_dump()
            for bug in bugs
        ],
    }

    save_json(
        OUTPUT_FILE,
        output,
    )

    print()
    print("=" * 70)
    print("BUG GENERATION COMPLETE")
    print("=" * 70)

    print(f"Total bugs generated: {len(bugs)}")
    print(f"Output: {OUTPUT_FILE}")
    print()

    if not bugs:
        print("No genuine application defects were identified.")
        print("This is expected if the execution failures were automation issues.")
        return

    for bug in bugs:
        print("-" * 70)
        print(f"{bug.bug_id}: {bug.title}")
        print(f"Severity : {bug.severity}")
        print(f"Priority : {bug.priority}")
        print(f"Category : {bug.category}")
        print(f"Status   : {bug.status}")
        print()
        print("Summary:")
        print(bug.summary)
        print()
        print("Expected:")
        print(bug.expected_result)
        print()
        print("Actual:")
        print(bug.actual_result)
        print()
        print("Root Cause:")
        print(bug.root_cause)
        print()
        print("Suggested Fix:")
        print(bug.suggested_fix)
        print()


if __name__ == "__main__":
    main()