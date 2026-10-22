import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel


router = APIRouter(
    prefix="/analysis",
    tags=["Analysis"],
)


BASE_DIR = Path(__file__).resolve().parents[3]

ARTIFACTS_DIR = BASE_DIR / "artifacts"

TARGET_CONFIG_FILE = (
    ARTIFACTS_DIR / "target_config.json"
)
JOURNEYS_FILE = ARTIFACTS_DIR / "ai_journeys.json"
GENERATION_STATUS_FILE = ARTIFACTS_DIR / "generation_status.json"
GENERATOR_SCRIPT = BASE_DIR / "automation" / "generate_target_tests.py"


def write_generation_status(status: str, message: str, process_id: int | None = None):
    data = {
        "status": status,
        "message": message,
        "updated_at": datetime.now().isoformat(),
    }
    if process_id is not None:
        data["process_id"] = process_id
    with open(GENERATION_STATUS_FILE, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=2)


class TargetRequest(BaseModel):
    url: str


def validate_url(url: str) -> str:

    url = url.strip()

    if not url:
        raise HTTPException(
            status_code=400,
            detail="URL cannot be empty.",
        )

    parsed = urlparse(url)

    if parsed.scheme not in {
        "http",
        "https",
    }:
        raise HTTPException(
            status_code=400,
            detail=(
                "URL must start with "
                "http:// or https://"
            ),
        )

    if not parsed.netloc:
        raise HTTPException(
            status_code=400,
            detail="Invalid URL.",
        )

    return url


@router.post("/target")
async def set_target(
    request: TargetRequest,
):

    url = validate_url(
        request.url
    )

    ARTIFACTS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    config = {
        "target_url": url,
        "status": "configured",
    }

    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(
        TARGET_CONFIG_FILE,
        "w",
        encoding="utf-8",
    ) as file:

        import json

        json.dump(
            config,
            file,
            indent=2,
        )

    # Do not leave journeys from the previous target visible while the new
    # site is being explored and analyzed.
    with open(JOURNEYS_FILE, "w", encoding="utf-8") as file:
        json.dump({"target_url": url, "journeys": []}, file, indent=2)

    write_generation_status("running", "Exploring target and generating test journeys.")
    try:
        process = subprocess.Popen(
            [sys.executable, str(GENERATOR_SCRIPT)],
            cwd=str(BASE_DIR),
            env={**os.environ, "TARGET_URL": url},
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0,
        )
        write_generation_status(
            "running",
            "Exploring target and generating test journeys.",
            process.pid,
        )
    except Exception as exc:
        write_generation_status("failed", f"Unable to start test generation: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))

    return {
        "status": "configured",
        "target_url": url,
        "generation_status": "running",
        "message": (
            "Target application URL "
            "configured successfully."
        ),
    }


@router.get("/generation")
async def get_generation_status():
    if not GENERATION_STATUS_FILE.exists():
        return {"status": "idle", "message": "No test generation has been started."}
    with open(GENERATION_STATUS_FILE, "r", encoding="utf-8") as file:
        status = json.load(file)
    if status.get("status") == "running":
        process_id = status.get("process_id")
        try:
            if not process_id:
                raise OSError("Missing process id")
            os.kill(int(process_id), 0)
        except (OSError, ValueError):
            status = {
                "status": "failed",
                "message": "Test generation stopped before completing. Check artifacts/target_generation.log.",
                "updated_at": datetime.now().isoformat(),
            }
            with open(GENERATION_STATUS_FILE, "w", encoding="utf-8") as file:
                json.dump(status, file, indent=2)
    return status


@router.get("/target")
async def get_target():

    if not TARGET_CONFIG_FILE.exists():

        return {
            "status": "not_configured",
            "target_url": None,
        }

    import json

    try:

        with open(
            TARGET_CONFIG_FILE,
            "r",
            encoding="utf-8",
        ) as file:

            return json.load(file)

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )
