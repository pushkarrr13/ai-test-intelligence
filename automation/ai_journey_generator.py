import os
import json
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

SITE_MAP_FILE = (
    ARTIFACTS_DIR /
    "site_map.json"
)

OUTPUT_FILE = (
    ARTIFACTS_DIR /
    "ai_journeys.json"
)

ENV_FILE = BASE_DIR / ".env"

load_dotenv(
    ENV_FILE
)

GEMINI_API_KEY = os.getenv(
    "GEMINI_API_KEY"
)

GEMINI_MODEL = os.getenv(
    "GEMINI_MODEL",
    "gemini-3.5-flash-lite"
)


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

class JourneyAction(BaseModel):

    action: str = Field(
        description=(
            "Executable action. Supported values: "
            "navigate, fill, click, select, check, "
            "uncheck, press, wait, assert_visible, "
            "assert_text, assert_url"
        )
    )

    target: str = Field(
        default="",
        description=(
            "Human-readable target based on an actual "
            "element in the discovered UI."
        )
    )

    value: str = Field(
        default="",
        description=(
            "Value used by fill, select, press, "
            "wait, assert_text or assert_url."
        )
    )


class Journey(BaseModel):

    title: str

    description: str

    type: str

    priority: str

    preconditions: List[str]

    actions: List[JourneyAction]

    expected_result: str


class JourneyAnalysis(BaseModel):

    application_summary: str

    important_pages: List[str]

    important_flows: List[str]

    journeys: List[Journey]


# ============================================================
# GEMINI CLIENT
# ============================================================

def create_client():

    return genai.Client(
        api_key=GEMINI_API_KEY
    )


# ============================================================
# LOAD SITE MAP
# ============================================================

def load_site_map():

    if not SITE_MAP_FILE.exists():

        raise FileNotFoundError(
            f"Site map not found:\n"
            f"{SITE_MAP_FILE}\n\n"
            f"Run web_explorer.py first."
        )

    with open(
        SITE_MAP_FILE,
        "r",
        encoding="utf-8"
    ) as file:

        return json.load(file)


# ============================================================
# LOAD PAGE UI MODELS
# ============================================================

def load_page_models(site_map):

    page_models = []

    for page in site_map.get(
        "pages",
        []
    ):

        ui_model_path = page.get(
            "ui_model"
        )

        if not ui_model_path:
            continue

        full_path = (
            BASE_DIR /
            ui_model_path
        )

        if not full_path.exists():
            continue

        try:

            with open(
                full_path,
                "r",
                encoding="utf-8"
            ) as file:

                ui_model = json.load(
                    file
                )

            page_models.append(
                {
                    "page": page,
                    "ui_model": ui_model
                }
            )

        except Exception as error:

            print(
                f"Could not load:"
                f" {full_path}"
            )

            print(
                f"Error: {error}"
            )

    return page_models


# ============================================================
# BUILD APPLICATION CONTEXT
# ============================================================

def build_application_context(
    site_map,
    page_models
):

    context = {

        "site_map": {

            "base_url":
                site_map.get(
                    "base_url"
                ),

            "authenticated":
                site_map.get(
                    "authenticated"
                ),

            "total_pages":
                site_map.get(
                    "total_pages"
                ),

            "navigation":
                site_map.get(
                    "navigation",
                    {}
                )
        },

        "pages": []
    }

    for item in page_models:

        page = item[
            "page"
        ]

        ui_model = item[
            "ui_model"
        ]

        context[
            "pages"
        ].append(
            {
                "page_id":
                    page.get(
                        "page_id"
                    ),

                "url":
                    page.get(
                        "url"
                    ),

                "title":
                    page.get(
                        "title"
                    ),

                "depth":
                    page.get(
                        "depth"
                    ),

                "authenticated":
                    page.get(
                        "authenticated"
                    ),

                "stats":
                    ui_model.get(
                        "stats",
                        {}
                    ),

                "elements":
                    ui_model.get(
                        "elements",
                        []
                    ),

                "headings":
                    ui_model.get(
                        "headings",
                        []
                    ),

                "forms":
                    ui_model.get(
                        "forms",
                        []
                    ),

                "links":
                    ui_model.get(
                        "links",
                        []
                    )
            }
        )

    return context


# ============================================================
# PROMPT
# ============================================================

def build_prompt(
    application_context
):

    return f"""
You are an expert SDET, QA architect and AI test-planning
engineer.

You are analyzing a REAL web application that has already
been explored using Playwright.

The exploration produced:

1. A site map.
2. Page URLs.
3. DOM/UI models.
4. Interactive elements.
5. Navigation/state transitions.

Your task is to generate realistic END-TO-END USER JOURNEYS
for this application.

============================================================
CRITICAL RULES
============================================================

DO NOT invent pages.

DO NOT invent buttons.

DO NOT invent inputs.

DO NOT invent functionality.

DO NOT assume an element exists simply because it is common
on similar websites.

Only use elements present in the supplied UI models.

The generated journeys must be executable by a generic
Playwright engine.

============================================================
SUPPORTED ACTIONS
============================================================

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

============================================================
ACTION RULES
============================================================

navigate:

Use only a URL that exists in the discovered application.

Example:

action = navigate
value = https://example.com/page


fill:

target = actual input name, label, placeholder or
human-readable field name.

Example:

target = Username
value = standard_user


click:

target = actual visible button/link/action.

Examples:

Login
Cart
Sauce Labs Backpack
Add to cart


select:

target = actual select element.

value = actual option.


check/uncheck:

target = actual checkbox.


press:

target = actual input/element.

value = keyboard key such as:

Enter
Escape
Tab


wait:

value = milliseconds.


assert_visible:

target = actual text or element.


assert_text:

target = actual element.

value = expected text.


assert_url:

value = URL or URL fragment actually observed
in the application.


============================================================
JOURNEY TYPES
============================================================

Generate appropriate journeys such as:

- Authentication
- Core business flow
- Navigation
- Product exploration
- Cart flow
- Checkout flow
- Validation
- Negative scenarios
- Boundary scenarios

Only generate journey types supported by the discovered
application.

============================================================
IMPORTANT
============================================================

A click may change the application state without changing
the URL.

This is especially important for modern SPAs.

Therefore, do not assume:

click -> URL change

A click can also cause:

click -> DOM change
click -> modal
click -> drawer
click -> product details
click -> cart update
click -> validation message

Use the discovered UI evidence.

============================================================
JOURNEY QUALITY
============================================================

Each journey should represent a meaningful user goal.

Avoid generating many nearly identical tests.

Prefer complete flows.

For example:

Login
↓
Open product
↓
Add product
↓
Open cart
↓
Verify product


rather than:

Click product

as a standalone journey.

============================================================
TEST DATA
============================================================

Use only test data that is explicitly visible in the
discovered application or supplied by the exploration.

For known SauceDemo login:

Username:
standard_user

Password:
secret_sauce

Do not invent other credentials.

============================================================
PRECONDITIONS
============================================================

Clearly identify prerequisites.

For example:

"User is logged in"

or:

"Application is on the inventory page"

============================================================
EXPECTED RESULTS
============================================================

Expected results must be supported by the discovered UI.

Do not claim an action succeeded unless there is observable
evidence to validate it.

============================================================
APPLICATION CONTEXT
============================================================

{json.dumps(
    application_context,
    indent=2,
    ensure_ascii=False
)}

============================================================
END APPLICATION CONTEXT
============================================================

Generate the most useful set of end-to-end journeys for
this discovered application.

Return ONLY structured JSON matching the supplied schema.
"""


# ============================================================
# AI ANALYSIS
# ============================================================

def generate_journeys(
    application_context
):

    client = create_client()

    prompt = build_prompt(
        application_context
    )

    print()
    print("=" * 70)
    print("SENDING APPLICATION TO GEMINI")
    print("=" * 70)

    print(
        f"\nModel:"
        f" {GEMINI_MODEL}"
    )

    print(
        f"Pages analyzed:"
        f" {len(application_context['pages'])}"
    )

    response = client.models.generate_content(

        model=GEMINI_MODEL,

        contents=[
            types.Part.from_text(
                text=prompt
            )
        ],

        config=types.GenerateContentConfig(

            response_mime_type="application/json",

            response_schema=JourneyAnalysis,

            temperature=0.2
        )
    )

    if not response.parsed:

        raise RuntimeError(
            "Gemini did not return structured "
            "journey analysis."
        )

    return response.parsed


# ============================================================
# SAVE RESULT
# ============================================================

def save_result(
    analysis
):

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

def display_result(
    result
):

    print()
    print("=" * 70)
    print("AI APPLICATION ANALYSIS")
    print("=" * 70)

    print()
    print(
        "Application Summary:"
    )

    print(
        result[
            "application_summary"
        ]
    )

    print()
    print(
        "Important Pages:"
    )

    for page in result[
        "important_pages"
    ]:

        print(
            f"  - {page}"
        )

    print()
    print(
        "Important Flows:"
    )

    for flow in result[
        "important_flows"
    ]:

        print(
            f"  - {flow}"
        )

    print()
    print("=" * 70)
    print(
        f"GENERATED JOURNEYS:"
        f" {len(result['journeys'])}"
    )
    print("=" * 70)

    for index, journey in enumerate(
        result["journeys"],
        start=1
    ):

        print()
        print(
            f"JOURNEY {index}"
        )

        print(
            "-" * 70
        )

        print(
            f"Title:"
            f" {journey['title']}"
        )

        print(
            f"Type:"
            f" {journey['type']}"
        )

        print(
            f"Priority:"
            f" {journey['priority']}"
        )

        print()
        print(
            "Description:"
        )

        print(
            f"  {journey['description']}"
        )

        print()
        print(
            "Preconditions:"
        )

        for condition in journey[
            "preconditions"
        ]:

            print(
                f"  - {condition}"
            )

        print()
        print(
            "Actions:"
        )

        for action_index, action in enumerate(
            journey["actions"],
            start=1
        ):

            action_name = action[
                "action"
            ]

            target = action.get(
                "target",
                ""
            )

            value = action.get(
                "value",
                ""
            )

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

        print()
        print(
            "Expected Result:"
        )

        print(
            f"  {journey['expected_result']}"
        )

    print()
    print("=" * 70)

    print(
        "Saved:"
    )

    print(
        OUTPUT_FILE
    )

    print(
        "=" * 70
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("=" * 70)
    print("AI TEST INTELLIGENCE - JOURNEY GENERATOR")
    print("=" * 70)

    print()
    print(
        "Loading site map..."
    )

    site_map = load_site_map()

    print(
        f"Discovered pages:"
        f" {site_map.get('total_pages', 0)}"
    )

    print()
    print(
        "Loading page UI models..."
    )

    page_models = load_page_models(
        site_map
    )

    print(
        f"Loaded UI models:"
        f" {len(page_models)}"
    )

    if not page_models:

        raise RuntimeError(
            "No page UI models were found."
        )

    print()
    print(
        "Building application context..."
    )

    application_context = (
        build_application_context(
            site_map,
            page_models
        )
    )

    analysis = generate_journeys(
        application_context
    )

    result = save_result(
        analysis
    )

    display_result(
        result
    )


if __name__ == "__main__":

    main()