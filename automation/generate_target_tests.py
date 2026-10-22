import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
ARTIFACTS_DIR = BASE_DIR / "artifacts"
STATUS_FILE = ARTIFACTS_DIR / "generation_status.json"
JOURNEYS_FILE = ARTIFACTS_DIR / "ai_journeys.json"
LOG_FILE = ARTIFACTS_DIR / "target_generation.log"


def write_status(status: str, message: str) -> None:
    current = {}
    if STATUS_FILE.exists():
        try:
            current = json.loads(STATUS_FILE.read_text(encoding="utf-8"))
        except Exception:
            current = {}
    current.update({
        "status": status,
        "message": message,
        "updated_at": datetime.now().isoformat(),
    })
    STATUS_FILE.write_text(json.dumps(current, indent=2), encoding="utf-8")


def main() -> None:
    target_url = os.environ.get("TARGET_URL", "").strip()
    if not target_url:
        raise RuntimeError("TARGET_URL was not provided.")

    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    with LOG_FILE.open("w", encoding="utf-8") as log:
        for script, args in (
            ("web_explorer.py", [target_url]),
            ("ai_journey_generator.py", []),
        ):
            command = [sys.executable, str(BASE_DIR / "automation" / script), *args]
            log.write(f"\n$ {' '.join(command)}\n")
            log.flush()
            subprocess.run(
                command,
                cwd=BASE_DIR,
                env=os.environ.copy(),
                stdout=log,
                stderr=subprocess.STDOUT,
                check=True,
            )

    journeys = json.loads(JOURNEYS_FILE.read_text(encoding="utf-8"))
    journeys["target_url"] = target_url
    JOURNEYS_FILE.write_text(json.dumps(journeys, indent=2, ensure_ascii=False), encoding="utf-8")
    count = len(journeys.get("journeys", []))
    if count == 0:
        raise RuntimeError("AI analysis completed but produced no test journeys.")
    write_status("completed", f"Generated {count} test journeys for {target_url}.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        write_status("failed", f"Test generation failed: {exc}. See artifacts/target_generation.log.")
        raise
