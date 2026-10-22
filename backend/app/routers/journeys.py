import json
from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter, HTTPException


router = APIRouter(
    prefix="/journeys",
    tags=["Journeys"],
)


BASE_DIR = Path(__file__).resolve().parents[3]

ARTIFACTS_DIR = BASE_DIR / "artifacts"

JOURNEYS_FILE = (
    ARTIFACTS_DIR /
    "ai_journeys.json"
)

EXECUTION_FILE = (
    ARTIFACTS_DIR /
    "journey_execution_results.json"
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
# JOURNEY LIST
# ============================================================

@router.get("")
async def get_journeys():

    data = load_json(
        JOURNEYS_FILE
    )

    journeys = data.get(
        "journeys",
        []
    )

    return {
        "total": len(journeys),
        "journeys": journeys,
    }


# ============================================================
# EXECUTION RESULTS
#
# IMPORTANT:
# Keep this route BEFORE /{journey_id}
# ============================================================

@router.get("/execution/results")
async def get_execution_results():

    data = load_json(
        EXECUTION_FILE
    )

    return data


# ============================================================
# JOURNEY BY ID
#
# Keep dynamic routes AFTER static routes.
# ============================================================

@router.get("/{journey_id}")
async def get_journey(
    journey_id: int,
):

    data = load_json(
        JOURNEYS_FILE
    )

    journeys = data.get(
        "journeys",
        []
    )

    index = journey_id - 1

    if index < 0 or index >= len(journeys):

        raise HTTPException(
            status_code=404,
            detail="Journey not found",
        )

    return {
        "journey_id": journey_id,
        "journey": journeys[index],
    }