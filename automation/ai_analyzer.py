import os
import json
import base64
from pathlib import Path
from typing import List

from dotenv import load_dotenv
from pydantic import BaseModel, Field
from google import genai
from google.genai import types


# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent
ARTIFACTS_DIR = BASE_DIR / "artifacts"

UI_MODEL_FILE = ARTIFACTS_DIR / "ui_model.json"
SCREENSHOT_FILE = ARTIFACTS_DIR / "page.png"
OUTPUT_FILE = ARTIFACTS_DIR / "ai_test_analysis.json"

ENV_FILE = BASE_DIR / ".env"

load_dotenv(ENV_FILE)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")


# ============================================================
# VALIDATION
# ============================================================

if not GEMINI_API_KEY:
    raise RuntimeError(
        "GEMINI_API_KEY is missing.\n"
        "Add it to C:\\ai-test-intelligence\\.env"
    )


# ============================================================
# PYDANTIC SCHEMAS
# ============================================================

class TestAction(BaseModel):
    action: str = Field(
        description=(
            "Executable action. Supported values: "
            "navigate, fill, click, select, check, uncheck, "
            "press, wait, assert_visible, assert_text, assert_url"
        )
    )

    target: str = Field(
        default="",
        description="Human-readable UI element target."
    )

    value: str = Field(
        default="",
        description="Value to enter/select/assert when required."
    )


class TestCase(BaseModel):
    title: str
    type: str
    priority: str
    actions: List[TestAction]
    expected_result: str


class UIAnalysis(BaseModel):
    page_type: str
    summary: str
    important_elements: List[str]
    user_flows: List[str]
    test_cases: List[TestCase]


# ============================================================
# GEMINI CLIENT
# ============================================================

def create_client():
    return genai.Client(
        api_key=GEMINI_API_KEY
    )


# ============================================================
# LOAD UI MODEL
# ============================================================

def load_ui_model():
    if not UI_MODEL_FILE.exists():
        raise FileNotFoundError(
            f"UI model not found:\n{UI_MODEL_FILE}\n\n"
            "Run ui_scanner.py first."
        )

    with open(UI_MODEL_FILE, "r", encoding="utf-8") as file:
        return json.load(file)


# ============================================================
# LOAD SCREENSHOT
# ============================================================

def load_screenshot():
    if not SCREENSHOT_FILE.exists():
        raise FileNotFoundError(
            f"Screenshot not found:\n{SCREENSHOT_FILE}\n\n"
            "Run ui_scanner.py first."
        )

    with open(SCREENSHOT_FILE, "rb") as file:
        image_bytes = file.read()

    return image_bytes


# ============================================================
# BUILD AI PROMPT
# ============================================================

def build_prompt(ui_model):
    return f"""
You are an expert QA automation engineer and AI test architect.

You are analyzing a real web application's UI.

You have TWO sources of information:

1. Structured DOM/UI information extracted from the real page.
2. A screenshot of the actual page.

Use BOTH sources together.

IMPORTANT:
- The DOM/UI model is the source of truth for actual interactive elements.
- The screenshot provides visual context and layout information.
- Do not invent UI elements that are not present.
- Do not assume functionality that cannot be supported by the DOM/UI model.
- Generate tests that can realistically be executed using Playwright.
- Test actions must use human-readable targets.
- Do not generate CSS/XPath selectors.
- The executor will resolve targets dynamically.

SUPPORTED ACTIONS:

navigate
fill
click
select
check
uncheck
press
wait
assert_visible
assert_text
assert_url

ACTION RULES:

navigate:
target = URL

fill:
target = input/textarea name or label
value = text to enter

click:
target = button/link/interactive element

select:
target = select element
value = option to select

check:
target = checkbox

uncheck:
target = checkbox

press:
target = input/element
value = keyboard key such as Enter

wait:
value = milliseconds

assert_visible:
target = element/text that should be visible

assert_text:
target = element
value = expected text

assert_url:
value = expected URL or URL fragment

TEST GENERATION RULES:

Generate meaningful functional test cases.

Include appropriate combinations of:

- Positive scenarios
- Negative scenarios
- Validation scenarios
- Boundary scenarios
- Navigation scenarios
- Authentication scenarios
- Required field validation
- Invalid input validation
- Error handling
- Important UI behavior

Only generate scenarios relevant to this actual page.

For example, if this is a login page, consider:

- Valid login
- Empty username
- Empty password
- Invalid credentials
- Locked account
- Required field validation
- Error messages
- Navigation after successful login

But DO NOT invent scenarios that require UI functionality that does not exist.

IMPORTANT:

Every generated action must reference an element that can reasonably be found from the supplied UI model or visible screenshot.

Avoid vague actions such as:

"verify login works"

Instead generate executable actions such as:

fill Username with standard_user
fill Password with secret_sauce
click Login
assert_url contains inventory

The final result must be structured JSON matching the supplied schema.

------------------------------------------------------------
STRUCTURED UI MODEL
------------------------------------------------------------

{json.dumps(ui_model, indent=2)}

------------------------------------------------------------
END UI MODEL
------------------------------------------------------------

Analyze the UI model and screenshot together and generate the structured test plan.
"""


# ============================================================
# AI ANALYSIS
# ============================================================

def analyze_ui(ui_model, screenshot_bytes):
    client = create_client()

    prompt = build_prompt(ui_model)

    print()
    print("=" * 70)
    print("Sending UI model + screenshot to Gemini...")
    print("=" * 70)

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=[
            types.Part.from_text(
                text=prompt
            ),
            types.Part.from_bytes(
                data=screenshot_bytes,
                mime_type="image/png"
            ),
        ],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=UIAnalysis,
            temperature=0.2,
        ),
    )

    if not response.parsed:
        raise RuntimeError(
            "Gemini did not return structured parsed output."
        )

    return response.parsed


# ============================================================
# SAVE RESULT
# ============================================================

def save_result(analysis):
    ARTIFACTS_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    result = analysis.model_dump()

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8"
    ) as file:
        json.dump(
            result,
            file,
            indent=2,
            ensure_ascii=False
        )

    return result


# ============================================================
# DISPLAY RESULT
# ============================================================

def display_result(result):
    print()
    print("=" * 70)
    print("AI UI ANALYSIS")
    print("=" * 70)

    print(f"\nPage Type:")
    print(result["page_type"])

    print(f"\nSummary:")
    print(result["summary"])

    print("\nImportant Elements:")
    for element in result["important_elements"]:
        print(f"  - {element}")

    print("\nUser Flows:")
    for flow in result["user_flows"]:
        print(f"  - {flow}")

    print()
    print("=" * 70)
    print(f"GENERATED TEST CASES: {len(result['test_cases'])}")
    print("=" * 70)

    for index, test in enumerate(
        result["test_cases"],
        start=1
    ):
        print()
        print(f"TEST {index}")
        print("-" * 70)

        print(f"Title    : {test['title']}")
        print(f"Type     : {test['type']}")
        print(f"Priority : {test['priority']}")

        print("\nActions:")

        for action_index, action in enumerate(
            test["actions"],
            start=1
        ):
            action_name = action["action"]
            target = action.get("target", "")
            value = action.get("value", "")

            if value:
                print(
                    f"  {action_index}. "
                    f"{action_name} | "
                    f"target={target} | "
                    f"value={value}"
                )
            else:
                print(
                    f"  {action_index}. "
                    f"{action_name} | "
                    f"target={target}"
                )

        print(
            f"\nExpected Result:\n"
            f"  {test['expected_result']}"
        )

    print()
    print("=" * 70)
    print(f"Saved AI analysis:")
    print(OUTPUT_FILE)
    print("=" * 70)


# ============================================================
# MAIN
# ============================================================

def main():
    print()
    print("=" * 70)
    print("AI TEST INTELLIGENCE - GEMINI UI ANALYZER")
    print("=" * 70)

    print(f"\nModel: {GEMINI_MODEL}")

    print("\nLoading UI model...")
    ui_model = load_ui_model()

    print(
        f"Loaded UI model from: {UI_MODEL_FILE}"
    )

    print("\nLoading screenshot...")
    screenshot_bytes = load_screenshot()

    print(
        f"Loaded screenshot from: {SCREENSHOT_FILE}"
    )

    analysis = analyze_ui(
        ui_model,
        screenshot_bytes
    )

    result = save_result(
        analysis
    )

    display_result(
        result
    )


if __name__ == "__main__":
    main()