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

REQUIREMENTS_FILE = BASE_DIR / "requirements.txt"
OUTPUT_FILE = ARTIFACTS_DIR / "requirement_analysis.json"

ENV_FILE = BASE_DIR / ".env"

load_dotenv(ENV_FILE)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv(
    "GEMINI_MODEL",
    "gemini-3.5-flash-lite"
)

if not GEMINI_API_KEY:
    raise RuntimeError(
        "GEMINI_API_KEY is missing. "
        "Add it to C:\\ai-test-intelligence\\.env"
    )


# ============================================================
# PYDANTIC MODELS
# ============================================================

class Requirement(BaseModel):
    requirement_id: str
    title: str
    description: str
    type: str
    priority: str
    acceptance_criteria: List[str]
    assumptions: List[str] = []


class RequirementTestScenario(BaseModel):
    requirement_id: str
    scenario_id: str
    title: str
    type: str
    priority: str
    preconditions: List[str] = []
    steps: List[str]
    expected_result: str


class CoverageItem(BaseModel):
    requirement_id: str
    covered: bool
    coverage_level: str
    matching_journeys: List[str] = []
    missing_coverage: List[str] = []
    recommendation: str = ""


class RequirementAnalysis(BaseModel):
    application_summary: str
    requirements: List[Requirement]
    test_scenarios: List[RequirementTestScenario]
    coverage: List[CoverageItem]
    overall_coverage_summary: str
    critical_gaps: List[str]


# ============================================================
# HELPERS
# ============================================================

def load_text_file(path: Path) -> str:

    if not path.exists():
        raise FileNotFoundError(
            f"Requirements file not found: {path}"
        )

    with open(
        path,
        "r",
        encoding="utf-8"
    ) as file:
        return file.read()


def load_json(path: Path):

    if not path.exists():
        return {}

    with open(
        path,
        "r",
        encoding="utf-8"
    ) as file:
        return json.load(file)


def save_json(path: Path, data):

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
# BUILD CONTEXT
# ============================================================

def build_application_context():

    site_map = load_json(
        ARTIFACTS_DIR / "site_map.json"
    )

    journeys = load_json(
        ARTIFACTS_DIR / "ai_journeys.json"
    )

    return {
        "site_map": site_map,
        "journeys": journeys,
    }


# ============================================================
# AI REQUIREMENT ANALYSIS
# ============================================================

def analyze_requirements(
    requirements_text: str,
    application_context: dict
):

    client = genai.Client(
        api_key=GEMINI_API_KEY
    )

    context_json = json.dumps(
        application_context,
        indent=2,
        ensure_ascii=False
    )

    prompt = f"""
You are a Senior Business Analyst, Product Analyst,
and SDET working on an AI-powered test intelligence platform.

You have two sources of information:

SOURCE 1:
The application's requirements.

SOURCE 2:
The application's actual explored UI, site map,
and AI-generated journeys.

Your task is to build a traceable requirements-to-testing model.

============================================================
REQUIREMENTS
============================================================

{requirements_text}

============================================================
ACTUAL APPLICATION CONTEXT
============================================================

{context_json}

============================================================
IMPORTANT RULES
============================================================

1. Requirements are authoritative for what the system is
   supposed to do.

2. The actual UI/site map is authoritative for what was
   actually discovered in the application.

3. Never invent application functionality.

4. Never claim that a requirement is implemented merely
   because it exists in the requirements.

5. Clearly distinguish:
   - requirement
   - expected behavior
   - discovered UI behavior
   - test coverage
   - missing coverage

6. Generate acceptance criteria only from the supplied
   requirement when possible.

7. Generate test scenarios that can realistically validate
   the requirement.

8. Identify positive and negative scenarios where appropriate.

9. Identify boundary or validation scenarios when the
   requirement implies them.

10. Match requirements to existing journeys only when there
    is evidence that the journey actually tests the requirement.

11. If a requirement has no matching journey, mark it as
    uncovered.

12. If the UI does not appear to support a required behavior,
    explicitly identify this as a coverage or product gap.
    Do not automatically call it a bug.

13. Do not assume undocumented backend behavior.

14. Do not invent API endpoints, database tables, error
    messages, pages, buttons, or workflows.

15. Use stable requirement IDs such as:
    REQ-001, REQ-002, etc.

16. Use scenario IDs such as:
    TC-REQ-001-01, TC-REQ-001-02, etc.

17. Coverage levels must be one of:
    FULL
    PARTIAL
    NONE

18. Requirement type may include:
    Functional
    Non-Functional
    Business Rule
    Validation
    Security
    Performance
    Usability

19. Requirement priority should be:
    Critical
    High
    Medium
    Low

20. The final result must be useful for:
    - Business Analysts
    - Product Managers
    - SDETs
    - QA Engineers

============================================================
OBJECTIVE
============================================================

Create:

A. Structured requirements

B. Acceptance criteria

C. Requirement-specific test scenarios

D. Mapping between requirements and existing journeys

E. Coverage analysis

F. Critical coverage gaps

The analysis should answer:

"Do our current automated journeys actually cover
what the requirements say the application should do?"

Return only structured JSON matching the requested schema.
"""

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config={
            "response_mime_type": "application/json",
            "response_schema": RequirementAnalysis,
            "temperature": 0.1,
        },
    )

    if not response.parsed:
        raise RuntimeError(
            "Gemini returned no structured requirement analysis."
        )

    return response.parsed


# ============================================================
# PRINT REPORT
# ============================================================

def print_report(
    analysis: RequirementAnalysis
):

    print()
    print("=" * 70)
    print("REQUIREMENT INTELLIGENCE REPORT")
    print("=" * 70)

    print()
    print("APPLICATION SUMMARY")
    print("-" * 70)
    print(
        analysis.application_summary
    )

    print()
    print("REQUIREMENTS")
    print("-" * 70)

    for requirement in analysis.requirements:

        print(
            f"{requirement.requirement_id} | "
            f"{requirement.priority} | "
            f"{requirement.title}"
        )

        print(
            f"    Type: {requirement.type}"
        )

        print(
            f"    {requirement.description}"
        )

        if requirement.acceptance_criteria:

            print(
                "    Acceptance Criteria:"
            )

            for criterion in (
                requirement.acceptance_criteria
            ):
                print(
                    f"      - {criterion}"
                )

    print()
    print("TEST SCENARIOS")
    print("-" * 70)

    for scenario in analysis.test_scenarios:

        print(
            f"{scenario.scenario_id} | "
            f"{scenario.requirement_id} | "
            f"{scenario.title}"
        )

        print(
            f"    Type: {scenario.type}"
        )

        print(
            f"    Priority: {scenario.priority}"
        )

        print(
            f"    Expected: "
            f"{scenario.expected_result}"
        )

    print()
    print("COVERAGE")
    print("-" * 70)

    for item in analysis.coverage:

        print(
            f"{item.requirement_id}: "
            f"{item.coverage_level}"
        )

        if item.matching_journeys:

            print(
                "    Matching journeys:"
            )

            for journey in (
                item.matching_journeys
            ):
                print(
                    f"      - {journey}"
                )

        if item.missing_coverage:

            print(
                "    Missing coverage:"
            )

            for gap in (
                item.missing_coverage
            ):
                print(
                    f"      - {gap}"
                )

        if item.recommendation:

            print(
                f"    Recommendation: "
                f"{item.recommendation}"
            )

    print()
    print("OVERALL COVERAGE")
    print("-" * 70)

    print(
        analysis.overall_coverage_summary
    )

    print()
    print("CRITICAL GAPS")
    print("-" * 70)

    if analysis.critical_gaps:

        for gap in analysis.critical_gaps:
            print(
                f"- {gap}"
            )

    else:

        print(
            "No critical gaps identified."
        )


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 70)
    print("AI TEST INTELLIGENCE - REQUIREMENT ANALYZER")
    print("=" * 70)

    print(
        f"Requirements: {REQUIREMENTS_FILE}"
    )

    print(
        f"Gemini model: {GEMINI_MODEL}"
    )

    print()

    requirements_text = load_text_file(
        REQUIREMENTS_FILE
    )

    print(
        "Requirements loaded."
    )

    application_context = (
        build_application_context()
    )

    print(
        "Application context loaded."
    )

    print()
    print(
        "Analyzing requirements with Gemini..."
    )

    analysis = analyze_requirements(
        requirements_text,
        application_context
    )

    output = analysis.model_dump()

    save_json(
        OUTPUT_FILE,
        output
    )

    print_report(
        analysis
    )

    print()
    print("=" * 70)
    print("ANALYSIS COMPLETE")
    print("=" * 70)

    print(
        f"Output: {OUTPUT_FILE}"
    )


if __name__ == "__main__":
    main()