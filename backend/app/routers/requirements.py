import json
from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter, HTTPException


router = APIRouter(
    prefix="/requirements",
    tags=["Requirements"],
)


BASE_DIR = Path(__file__).resolve().parents[3]

ARTIFACTS_DIR = BASE_DIR / "artifacts"

REQUIREMENT_FILE = (
    ARTIFACTS_DIR /
    "requirement_analysis.json"
)

COVERAGE_FILE = (
    ARTIFACTS_DIR /
    "coverage_report.json"
)


# ============================================================
# HELPERS
# ============================================================

def load_json(
    path: Path
) -> Dict[str, Any]:

    if not path.exists():

        raise HTTPException(
            status_code=404,
            detail=f"File not found: {path.name}",
        )

    try:

        with open(
            path,
            "r",
            encoding="utf-8",
        ) as file:

            return json.load(file)

    except json.JSONDecodeError as exc:

        raise HTTPException(
            status_code=500,
            detail=f"Invalid JSON in {path.name}: {exc}",
        )


# ============================================================
# REQUIREMENTS LIST
# ============================================================

@router.get("")
async def get_requirements():

    data = load_json(
        REQUIREMENT_FILE
    )

    requirements = data.get(
        "requirements",
        []
    )

    return {
        "total": len(requirements),
        "requirements": requirements,
    }


# ============================================================
# COVERAGE REPORT
#
# IMPORTANT:
# Keep this route BEFORE /{requirement_id}
# ============================================================

@router.get("/coverage/report")
async def get_coverage():

    return load_json(
        COVERAGE_FILE
    )


# ============================================================
# REQUIREMENT BY ID
# ============================================================

@router.get("/{requirement_id}")
async def get_requirement(
    requirement_id: str,
):

    data = load_json(
        REQUIREMENT_FILE
    )

    requirements = data.get(
        "requirements",
        []
    )

    for requirement in requirements:

        if (
            requirement.get(
                "requirement_id"
            )
            == requirement_id
        ):

            return requirement

    raise HTTPException(
        status_code=404,
        detail="Requirement not found",
    )