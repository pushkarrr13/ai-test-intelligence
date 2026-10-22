import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter, HTTPException


router = APIRouter(
    prefix="/execution",
    tags=["Execution"],
)


# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parents[3]

ARTIFACTS_DIR = BASE_DIR / "artifacts"

AUTOMATION_DIR = BASE_DIR / "automation"

EXECUTOR_FILE = (
    AUTOMATION_DIR /
    "journey_executor.py"
)

EXECUTION_RESULTS_FILE = (
    ARTIFACTS_DIR /
    "journey_execution_results.json"
)

EXECUTION_STATUS_FILE = (
    ARTIFACTS_DIR /
    "execution_status.json"
)


# ============================================================
# HELPERS
# ============================================================

def save_json(
    path: Path,
    data: Dict[str, Any],
):

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with open(
        path,
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            data,
            file,
            indent=2,
            ensure_ascii=False,
        )


def load_json(
    path: Path,
) -> Dict[str, Any]:

    if not path.exists():

        return {}

    try:

        with open(
            path,
            "r",
            encoding="utf-8",
        ) as file:

            return json.load(file)

    except Exception:

        return {}


def write_status(
    status: str,
    message: str,
    process_id: int | None = None,
):
    data = {
        "status": status,
        "message": message,
        "updated_at": datetime.now().isoformat(),
    }
    if process_id is not None:
        data["process_id"] = process_id
    save_json(EXECUTION_STATUS_FILE, data)


def process_is_running(process_id: int) -> bool:
    try:
        os.kill(process_id, 0)
        return True
    except (OSError, ValueError):
        return False


# ============================================================
# EXECUTION STATUS
# ============================================================

@router.get("/status")
async def get_execution_status():

    status = load_json(
        EXECUTION_STATUS_FILE
    )

    if not status:

        return {
            "status": "idle",
            "message": "No execution has been started.",
            "updated_at": None,
        }

    if status.get("status") == "running":
        process_id = status.get("process_id")
        if not process_id or not process_is_running(int(process_id)):
            status = {
                "status": "failed",
                "message": "Execution is no longer running. The previous run did not finish cleanly.",
                "updated_at": datetime.now().isoformat(),
            }
            save_json(EXECUTION_STATUS_FILE, status)

    return status


# ============================================================
# LATEST RESULTS
# ============================================================

@router.get("/results")
async def get_execution_results():

    if not EXECUTION_RESULTS_FILE.exists():

        return {
            "journeys": [],
            "message": "No execution results available.",
        }

    return load_json(
        EXECUTION_RESULTS_FILE
    )


# ============================================================
# RUN TEST JOURNEYS
# ============================================================

@router.post("/run")
async def run_test_journeys():

    if not EXECUTOR_FILE.exists():

        raise HTTPException(
            status_code=404,
            detail=(
                "journey_executor.py was not found at "
                f"{EXECUTOR_FILE}"
            ),
        )

    current_status = load_json(
        EXECUTION_STATUS_FILE
    )

    if current_status.get("status") == "running":
        process_id = current_status.get("process_id")
        if not process_id or process_is_running(int(process_id)):
            return {
                "status": "already_running",
                "message": "A test execution is already running.",
            }
        write_status("failed", "The previous execution process is no longer running.")

    ARTIFACTS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    write_status(
        "running",
        "Playwright journey execution started.",
    )

    # --------------------------------------------------------
    # Start executor as a separate process.
    #
    # This keeps FastAPI responsive while Playwright runs.
    # --------------------------------------------------------

    try:

        target_config = load_json(ARTIFACTS_DIR / "target_config.json")
        child_env = os.environ.copy()
        if target_config.get("target_url"):
            child_env["TARGET_URL"] = target_config["target_url"]

        process = subprocess.Popen(
            [
                sys.executable,
                str(EXECUTOR_FILE),
            ],
            cwd=str(BASE_DIR),
            env=child_env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=(
                subprocess.CREATE_NEW_PROCESS_GROUP
                if sys.platform == "win32"
                else 0
            ),
        )
        write_status(
            "running",
            "Playwright journey execution started.",
            process.pid,
        )

    except Exception as exc:

        write_status(
            "failed",
            f"Unable to start execution: {exc}",
        )

        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )

    return {
        "status": "started",
        "message": "Test execution started.",
        "process_id": process.pid,
        "started_at": datetime.now().isoformat(),
    }
