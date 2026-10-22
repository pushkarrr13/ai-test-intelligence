import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException


router = APIRouter(
    prefix="/artifacts",
    tags=["Artifacts"],
)


BASE_DIR = Path(__file__).resolve().parents[3]

ARTIFACTS_DIR = BASE_DIR / "artifacts"


# ============================================================
# HELPERS
# ============================================================

def load_json_file(
    filename: str
) -> Any:

    path = ARTIFACTS_DIR / filename

    if not path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Artifact not found: {filename}",
        )

    try:

        with open(
            path,
            "r",
            encoding="utf-8",
        ) as file:

            return json.load(file)

    except json.JSONDecodeError:

        raise HTTPException(
            status_code=500,
            detail=f"Invalid JSON artifact: {filename}",
        )


# ============================================================
# LIST ARTIFACTS
# ============================================================

@router.get("")
async def list_artifacts():

    if not ARTIFACTS_DIR.exists():

        return {
            "artifacts": [],
        }

    files = []

    for path in ARTIFACTS_DIR.glob("*"):

        if path.is_file():

            files.append(
                {
                    "name": path.name,
                    "size": path.stat().st_size,
                    "extension": path.suffix,
                }
            )

    files.sort(
        key=lambda item: item["name"]
    )

    return {
        "artifacts": files,
    }


# ============================================================
# GET ARTIFACT
# ============================================================

@router.get("/{filename}")
async def get_artifact(
    filename: str,
):

    # Prevent path traversal.
    safe_name = Path(
        filename
    ).name

    return load_json_file(
        safe_name
    )


# ============================================================
# DASHBOARD SUMMARY
# ============================================================

@router.get("/summary/dashboard")
async def dashboard_summary():

    execution = {}
    coverage = {}
    failures = {}
    bugs = {}

    execution_path = (
        ARTIFACTS_DIR /
        "journey_execution_results.json"
    )

    coverage_path = (
        ARTIFACTS_DIR /
        "coverage_report.json"
    )

    failure_path = (
        ARTIFACTS_DIR /
        "failure_analysis.json"
    )

    bug_path = (
        ARTIFACTS_DIR /
        "bug_reports.json"
    )

    if execution_path.exists():

        execution = load_json_file(
            execution_path.name
        )

    if coverage_path.exists():

        coverage = load_json_file(
            coverage_path.name
        )

    if failure_path.exists():

        failures = load_json_file(
            failure_path.name
        )

    if bug_path.exists():

        bugs = load_json_file(
            bug_path.name
        )

    return {
        "execution": execution,
        "coverage": coverage,
        "failures": failures,
        "bugs": bugs,
    }