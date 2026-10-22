import json
from pathlib import Path
from typing import Any, Dict, List


# ============================================================
# CONFIG
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent
ARTIFACTS_DIR = BASE_DIR / "artifacts"

REQUIREMENT_ANALYSIS_FILE = (
    ARTIFACTS_DIR / "requirement_analysis.json"
)

JOURNEYS_FILE = (
    ARTIFACTS_DIR / "ai_journeys.json"
)

EXECUTION_FILE = (
    ARTIFACTS_DIR / "journey_execution_results.json"
)

OUTPUT_FILE = (
    ARTIFACTS_DIR / "coverage_report.json"
)


# ============================================================
# FILE HELPERS
# ============================================================

def load_json(path: Path) -> Dict[str, Any]:

    if not path.exists():
        raise FileNotFoundError(
            f"Required file not found: {path}"
        )

    with open(
        path,
        "r",
        encoding="utf-8"
    ) as file:
        return json.load(file)


def save_json(
    path: Path,
    data: Dict[str, Any]
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
# NORMALIZATION
# ============================================================

def normalize(value: Any) -> str:

    if value is None:
        return ""

    return (
        str(value)
        .strip()
        .lower()
    )


def contains_match(
    requirement_text: str,
    journey_text: str
) -> bool:

    requirement_text = normalize(
        requirement_text
    )

    journey_text = normalize(
        journey_text
    )

    if not requirement_text:
        return False

    if not journey_text:
        return False

    # Direct match
    if requirement_text in journey_text:
        return True

    # Keyword match
    keywords = [
        word
        for word in requirement_text.split()
        if len(word) >= 5
    ]

    if not keywords:
        return False

    matches = sum(
        1
        for keyword in keywords
        if keyword in journey_text
    )

    return (
        matches >= max(
            1,
            len(keywords) // 3
        )
    )


# ============================================================
# BUILD JOURNEY TEXT
# ============================================================

def journey_to_text(
    journey: Dict[str, Any]
) -> str:

    parts: List[str] = []

    parts.append(
        journey.get(
            "title",
            ""
        )
    )

    parts.append(
        journey.get(
            "description",
            ""
        )
    )

    parts.extend(
        journey.get(
            "preconditions",
            []
        )
    )

    parts.append(
        journey.get(
            "expected_result",
            ""
        )
    )

    for action in journey.get(
        "actions",
        []
    ):

        parts.append(
            action.get(
                "action",
                ""
            )
        )

        parts.append(
            action.get(
                "target",
                ""
            )
        )

        parts.append(
            action.get(
                "value",
                ""
            )
        )

    return " ".join(
        str(part)
        for part in parts
        if part
    )


# ============================================================
# BUILD EXECUTION MAP
# ============================================================

def build_execution_map(
    execution_data: Dict[str, Any]
) -> Dict[int, Dict[str, Any]]:

    execution_map = {}

    for journey in execution_data.get(
        "journeys",
        []
    ):

        index = journey.get(
            "journey_index"
        )

        if index is None:
            continue

        execution_map[
            int(index)
        ] = journey

    return execution_map


# ============================================================
# FIND MATCHING JOURNEYS
# ============================================================

def find_matching_journeys(
    requirement: Dict[str, Any],
    journeys: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:

    requirement_id = normalize(
        requirement.get(
            "requirement_id"
        )
    )

    requirement_text = " ".join(
        [
            str(
                requirement.get(
                    "title",
                    ""
                )
            ),
            str(
                requirement.get(
                    "description",
                    ""
                )
            ),
            " ".join(
                requirement.get(
                    "acceptance_criteria",
                    []
                )
            ),
        ]
    )

    matches = []

    for index, journey in enumerate(
        journeys,
        start=1
    ):

        journey_text = journey_to_text(
            journey
        )

        score = 0

        # ----------------------------------------------------
        # Requirement ID directly mentioned
        # ----------------------------------------------------

        if requirement_id in normalize(
            journey_text
        ):
            score += 5

        # ----------------------------------------------------
        # Requirement keywords
        # ----------------------------------------------------

        req_words = {
            word
            for word in normalize(
                requirement_text
            ).split()
            if len(word) >= 5
        }

        journey_words = {
            word
            for word in normalize(
                journey_text
            ).split()
            if len(word) >= 5
        }

        if req_words and journey_words:

            overlap = (
                req_words &
                journey_words
            )

            score += min(
                len(overlap),
                5
            )

        if score >= 2:

            matches.append(
                {
                    "journey_index": index,
                    "journey": journey,
                    "score": score,
                }
            )

    matches.sort(
        key=lambda item: item["score"],
        reverse=True
    )

    return matches


# ============================================================
# VERIFY COVERAGE USING EXECUTION
# ============================================================

def evaluate_requirement(
    requirement: Dict[str, Any],
    matches: List[Dict[str, Any]],
    execution_map: Dict[int, Dict[str, Any]]
) -> Dict[str, Any]:

    requirement_id = requirement.get(
        "requirement_id",
        ""
    )

    matching_journeys = []
    passed_journeys = []
    failed_journeys = []

    for match in matches:

        journey_index = (
            match["journey_index"]
        )

        journey = match["journey"]

        title = journey.get(
            "title",
            f"Journey {journey_index}"
        )

        matching_journeys.append(
            title
        )

        execution = execution_map.get(
            journey_index
        )

        if execution:

            status = normalize(
                execution.get(
                    "status"
                )
            )

            if status == "passed":

                passed_journeys.append(
                    title
                )

            elif status == "failed":

                failed_journeys.append(
                    title
                )

    # --------------------------------------------------------
    # COVERAGE LEVEL
    # --------------------------------------------------------

    if not matching_journeys:

        coverage_level = "NONE"

    elif passed_journeys:

        coverage_level = "FULL"

    elif failed_journeys:

        coverage_level = "PARTIAL"

    else:

        coverage_level = "PARTIAL"

    # --------------------------------------------------------
    # MISSING COVERAGE
    # --------------------------------------------------------

    missing = []

    acceptance_criteria = (
        requirement.get(
            "acceptance_criteria",
            []
        )
    )

    if not matching_journeys:

        missing.extend(
            acceptance_criteria
        )

    elif not passed_journeys:

        missing.append(
            "A passing automated journey "
            "has not been demonstrated."
        )

    elif failed_journeys:

        missing.append(
            "At least one matching journey "
            "is currently failing."
        )

    # --------------------------------------------------------
    # RECOMMENDATION
    # --------------------------------------------------------

    if coverage_level == "FULL":

        recommendation = (
            "Requirement has matching automated "
            "coverage with at least one passing journey."
        )

    elif coverage_level == "PARTIAL":

        recommendation = (
            "Review the matching journeys and add "
            "or repair automated scenarios for "
            "the uncovered behavior."
        )

    else:

        recommendation = (
            "Create an automated test journey "
            "covering this requirement."
        )

    return {
        "requirement_id": requirement_id,
        "title": requirement.get(
            "title",
            ""
        ),
        "priority": requirement.get(
            "priority",
            ""
        ),
        "coverage_level": coverage_level,
        "matching_journeys": matching_journeys,
        "passed_journeys": passed_journeys,
        "failed_journeys": failed_journeys,
        "missing_coverage": missing,
        "recommendation": recommendation,
    }


# ============================================================
# JOURNEY EXECUTION SUMMARY
# ============================================================

def build_execution_summary(
    execution_data: Dict[str, Any]
) -> Dict[str, Any]:

    journeys = execution_data.get(
        "journeys",
        []
    )

    total = len(journeys)

    passed = sum(
        1
        for journey in journeys
        if normalize(
            journey.get("status")
        ) == "passed"
    )

    failed = total - passed

    total_steps = sum(
        journey.get(
            "total_steps",
            0
        )
        for journey in journeys
    )

    passed_steps = sum(
        journey.get(
            "passed_steps",
            0
        )
        for journey in journeys
    )

    failed_steps = sum(
        journey.get(
            "failed_steps",
            0
        )
        for journey in journeys
    )

    healed_steps = sum(
        journey.get(
            "healed_steps",
            0
        )
        for journey in journeys
    )

    return {
        "total_journeys": total,
        "passed_journeys": passed,
        "failed_journeys": failed,
        "total_steps": total_steps,
        "passed_steps": passed_steps,
        "failed_steps": failed_steps,
        "healed_steps": healed_steps,
    }


# ============================================================
# COVERAGE PERCENTAGE
# ============================================================

def calculate_coverage_percentage(
    coverage_items: List[Dict[str, Any]]
) -> float:

    total = len(
        coverage_items
    )

    if total == 0:
        return 0.0

    covered = sum(
        1
        for item in coverage_items
        if item.get(
            "coverage_level"
        ) == "FULL"
    )

    return round(
        covered / total * 100,
        2
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 70)
    print(
        "AI TEST INTELLIGENCE - COVERAGE ENGINE"
    )
    print("=" * 70)

    requirement_data = load_json(
        REQUIREMENT_ANALYSIS_FILE
    )

    journey_data = load_json(
        JOURNEYS_FILE
    )

    execution_data = load_json(
        EXECUTION_FILE
    )

    requirements = requirement_data.get(
        "requirements",
        []
    )

    journeys = journey_data.get(
        "journeys",
        []
    )

    execution_map = (
        build_execution_map(
            execution_data
        )
    )

    print()
    print(
        f"Requirements : {len(requirements)}"
    )

    print(
        f"Journeys     : {len(journeys)}"
    )

    print(
        f"Executions   : {len(execution_map)}"
    )

    # --------------------------------------------------------
    # REQUIREMENT COVERAGE
    # --------------------------------------------------------

    coverage_items = []

    for requirement in requirements:

        requirement_id = requirement.get(
            "requirement_id",
            ""
        )

        print()
        print(
            f"Analyzing {requirement_id}..."
        )

        matches = find_matching_journeys(
            requirement,
            journeys
        )

        coverage = evaluate_requirement(
            requirement,
            matches,
            execution_map
        )

        coverage_items.append(
            coverage
        )

        print(
            f"    Coverage: "
            f"{coverage['coverage_level']}"
        )

        print(
            f"    Matching journeys: "
            f"{len(coverage['matching_journeys'])}"
        )

    # --------------------------------------------------------
    # SUMMARY
    # --------------------------------------------------------

    full = sum(
        1
        for item in coverage_items
        if item["coverage_level"]
        == "FULL"
    )

    partial = sum(
        1
        for item in coverage_items
        if item["coverage_level"]
        == "PARTIAL"
    )

    none = sum(
        1
        for item in coverage_items
        if item["coverage_level"]
        == "NONE"
    )

    total_requirements = len(
        coverage_items
    )

    coverage_percentage = (
        calculate_coverage_percentage(
            coverage_items
        )
    )

    critical_gaps = []

    for item in coverage_items:

        if item["coverage_level"] == "NONE":

            critical_gaps.append(
                {
                    "requirement_id":
                        item["requirement_id"],
                    "title":
                        item["title"],
                    "priority":
                        item["priority"],
                    "reason":
                        "No matching automated journey."
                }
            )

        elif (
            item["coverage_level"]
            == "PARTIAL"
        ):

            critical_gaps.append(
                {
                    "requirement_id":
                        item["requirement_id"],
                    "title":
                        item["title"],
                    "priority":
                        item["priority"],
                    "reason":
                        "Requirement is not fully "
                        "validated by passing automation."
                }
            )

    execution_summary = (
        build_execution_summary(
            execution_data
        )
    )

    # --------------------------------------------------------
    # FINAL REPORT
    # --------------------------------------------------------

    report = {
        "generated_by":
            "AI Test Intelligence",

        "requirements": {
            "total":
                total_requirements,

            "fully_covered":
                full,

            "partially_covered":
                partial,

            "not_covered":
                none,

            "coverage_percentage":
                coverage_percentage,
        },

        "execution": execution_summary,

        "coverage": coverage_items,

        "critical_gaps": critical_gaps,
    }

    save_json(
        OUTPUT_FILE,
        report
    )

    # --------------------------------------------------------
    # CONSOLE REPORT
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("REQUIREMENT COVERAGE SUMMARY")
    print("=" * 70)

    print(
        f"Total requirements : "
        f"{total_requirements}"
    )

    print(
        f"Fully covered     : "
        f"{full}"
    )

    print(
        f"Partially covered : "
        f"{partial}"
    )

    print(
        f"Not covered       : "
        f"{none}"
    )

    print(
        f"Coverage          : "
        f"{coverage_percentage}%"
    )

    print()
    print("EXECUTION SUMMARY")
    print("-" * 70)

    print(
        f"Journeys passed : "
        f"{execution_summary['passed_journeys']}"
    )

    print(
        f"Journeys failed : "
        f"{execution_summary['failed_journeys']}"
    )

    print(
        f"Steps passed    : "
        f"{execution_summary['passed_steps']}"
    )

    print(
        f"Steps failed    : "
        f"{execution_summary['failed_steps']}"
    )

    print(
        f"Healed steps    : "
        f"{execution_summary['healed_steps']}"
    )

    print()
    print("COVERAGE MATRIX")
    print("-" * 70)

    for item in coverage_items:

        print(
            f"{item['requirement_id']:<12} "
            f"{item['coverage_level']:<10} "
            f"{item['title']}"
        )

    print()
    print("GAPS")
    print("-" * 70)

    if critical_gaps:

        for gap in critical_gaps:

            print(
                f"- {gap['requirement_id']} | "
                f"{gap['priority']} | "
                f"{gap['title']}"
            )

            print(
                f"  {gap['reason']}"
            )

    else:

        print(
            "No coverage gaps detected."
        )

    print()
    print("=" * 70)
    print("COVERAGE ANALYSIS COMPLETE")
    print("=" * 70)

    print(
        f"Report: {OUTPUT_FILE}"
    )


if __name__ == "__main__":
    main()