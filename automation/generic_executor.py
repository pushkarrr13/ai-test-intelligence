import asyncio
import json
from pathlib import Path

from playwright.async_api import async_playwright


ROOT_DIR = Path(__file__).resolve().parent.parent

ARTIFACT_DIR = ROOT_DIR / "artifacts"

AI_ANALYSIS_PATH = (
    ARTIFACT_DIR / "ai_test_analysis.json"
)

RESULTS_PATH = (
    ARTIFACT_DIR / "execution_results.json"
)


# ============================================================
# LOCATOR RESOLUTION
# ============================================================

async def find_element(
    page,
    target
):

    target = target.strip()

    # Try label
    locator = page.get_by_label(
        target,
        exact=True
    )

    if await locator.count() > 0:
        return locator.first

    # Try role-based button
    locator = page.get_by_role(
        "button",
        name=target,
        exact=True
    )

    if await locator.count() > 0:
        return locator.first

    # Try role-based link
    locator = page.get_by_role(
        "link",
        name=target,
        exact=True
    )

    if await locator.count() > 0:
        return locator.first

    # Try placeholder
    locator = page.get_by_placeholder(
        target,
        exact=True
    )

    if await locator.count() > 0:
        return locator.first

    # Try text
    locator = page.get_by_text(
        target,
        exact=True
    )

    if await locator.count() > 0:
        return locator.first

    # Try ID
    locator = page.locator(
        f"#{target}"
    )

    if await locator.count() > 0:
        return locator.first

    raise Exception(
        f"Could not find UI element: {target}"
    )


# ============================================================
# ACTION EXECUTOR
# ============================================================

async def execute_action(
    page,
    action
):

    action_type = action["action"]

    target = action.get(
        "target",
        ""
    )

    value = action.get(
        "value",
        ""
    )

    print(
        f"      → {action_type}"
        f" | {target}"
        f" | {value}"
    )

    # --------------------------------------------------------
    # NAVIGATE
    # --------------------------------------------------------

    if action_type == "navigate":

        url = target

        if not url.startswith("http"):

            current_url = page.url

            base_url = (
                current_url.split(
                    "/",
                    3
                )[0:3]
            )

            base_url = "/".join(
                base_url
            )

            url = (
                base_url.rstrip("/")
                + "/"
                + target.lstrip("/")
            )

        await page.goto(
            url,
            wait_until="domcontentloaded"
        )

        return

    # --------------------------------------------------------
    # FIND ELEMENT
    # --------------------------------------------------------

    element = await find_element(
        page,
        target
    )

    # --------------------------------------------------------
    # FILL
    # --------------------------------------------------------

    if action_type == "fill":

        await element.fill(
            value
        )

    # --------------------------------------------------------
    # CLICK
    # --------------------------------------------------------

    elif action_type == "click":

        await element.click()

    # --------------------------------------------------------
    # SELECT
    # --------------------------------------------------------

    elif action_type == "select":

        await element.select_option(
            value
        )

    # --------------------------------------------------------
    # CHECK
    # --------------------------------------------------------

    elif action_type == "check":

        await element.check()

    # --------------------------------------------------------
    # UNCHECK
    # --------------------------------------------------------

    elif action_type == "uncheck":

        await element.uncheck()

    # --------------------------------------------------------
    # PRESS
    # --------------------------------------------------------

    elif action_type == "press":

        await element.press(
            value
        )

    # --------------------------------------------------------
    # WAIT
    # --------------------------------------------------------

    elif action_type == "wait":

        milliseconds = int(
            value or 1000
        )

        await page.wait_for_timeout(
            milliseconds
        )

        return

    # --------------------------------------------------------
    # ASSERT VISIBLE
    # --------------------------------------------------------

    elif action_type == "assert_visible":

        await element.wait_for(
            state="visible"
        )

    # --------------------------------------------------------
    # ASSERT TEXT
    # --------------------------------------------------------

    elif action_type == "assert_text":

        actual_text = (
            await element.inner_text()
        )

        if value not in actual_text:

            raise AssertionError(
                f"""
Text assertion failed.

Expected:
{value}

Actual:
{actual_text}
"""
            )

    # --------------------------------------------------------
    # ASSERT URL
    # --------------------------------------------------------

    elif action_type == "assert_url":

        if value not in page.url:

            raise AssertionError(
                f"""
URL assertion failed.

Expected:
{value}

Actual:
{page.url}
"""
            )

    else:

        raise Exception(
            f"Unsupported action: "
            f"{action_type}"
        )


# ============================================================
# TEST EXECUTION
# ============================================================

async def execute_test(
    browser,
    test_case
):

    title = test_case["title"]

    print()
    print("=" * 60)
    print(
        f"TEST: {title}"
    )
    print("=" * 60)

    page = await browser.new_page(
        viewport={
            "width": 1440,
            "height": 900
        }
    )

    result = {

        "title": title,

        "type": test_case.get(
            "type"
        ),

        "priority": test_case.get(
            "priority"
        ),

        "status": "NOT_EXECUTED",

        "actions": test_case.get(
            "actions",
            []
        ),

        "expected_result":
            test_case.get(
                "expected_result"
            ),

        "error": None,

        "screenshot": None
    }

    try:

        for action in test_case[
            "actions"
        ]:

            await execute_action(
                page,
                action
            )

        result["status"] = "PASSED"

        print(
            "\n      STATUS: PASSED"
        )

    except Exception as error:

        result["status"] = "FAILED"

        result["error"] = str(
            error
        )

        screenshot_path = (
            ARTIFACT_DIR /
            f"failure_{abs(hash(title))}.png"
        )

        await page.screenshot(
            path=str(
                screenshot_path
            ),
            full_page=True
        )

        result[
            "screenshot"
        ] = str(
            screenshot_path
        )

        print(
            "\n      STATUS: FAILED"
        )

        print(
            f"      ERROR: {error}"
        )

    finally:

        await page.close()

    return result


# ============================================================
# MAIN
# ============================================================

async def main():

    print()
    print("=" * 60)
    print("          GENERIC AI TEST EXECUTOR")
    print("=" * 60)

    if not AI_ANALYSIS_PATH.exists():

        raise FileNotFoundError(
            "AI analysis file not found."
        )

    with open(
        AI_ANALYSIS_PATH,
        "r",
        encoding="utf-8"
    ) as file:

        analysis = json.load(
            file
        )

    test_cases = analysis.get(
        "test_cases",
        []
    )

    print(
        f"\nLoaded {len(test_cases)} test cases."
    )

    async with async_playwright() as p:

        browser = await p.chromium.launch(
            headless=True
        )

        results = []

        for test_case in test_cases:

            result = await execute_test(
                browser,
                test_case
            )

            results.append(
                result
            )

        await browser.close()

    with open(
        RESULTS_PATH,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            results,
            file,
            indent=2,
            ensure_ascii=False
        )

    passed = sum(
        result["status"] == "PASSED"
        for result in results
    )

    failed = sum(
        result["status"] == "FAILED"
        for result in results
    )

    print()
    print("=" * 60)
    print("              EXECUTION SUMMARY")
    print("=" * 60)

    print(
        f"Total:   {len(results)}"
    )

    print(
        f"Passed:  {passed}"
    )

    print(
        f"Failed:  {failed}"
    )

    print()
    print(
        f"Results:\n{RESULTS_PATH}"
    )


if __name__ == "__main__":

    asyncio.run(main())