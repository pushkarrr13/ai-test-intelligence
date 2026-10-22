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


async def load_test_cases():

    if not AI_ANALYSIS_PATH.exists():

        raise FileNotFoundError(
            f"AI analysis not found:\n"
            f"{AI_ANALYSIS_PATH}\n\n"
            f"Run ai_analyzer.py first."
        )

    with open(
        AI_ANALYSIS_PATH,
        "r",
        encoding="utf-8"
    ) as file:

        data = json.load(file)

    return data.get("test_cases", [])


async def execute_test(
    browser,
    test_case
):

    title = test_case["title"]

    steps = test_case["steps"]

    print()
    print("=" * 60)
    print(f"TEST: {title}")
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
            "type",
            "unknown"
        ),
        "priority": test_case.get(
            "priority",
            "unknown"
        ),
        "status": "NOT_EXECUTED",
        "steps": steps,
        "error": None,
        "screenshot": None
    }

    try:

        # ------------------------------------------------
        # IMPORTANT:
        # This first version demonstrates execution
        # of the known SauceDemo login flow.
        # Later we will replace this with our AI
        # action interpreter.
        # ------------------------------------------------

        await page.goto(
            "https://www.saucedemo.com/",
            wait_until="domcontentloaded"
        )

        title_lower = title.lower()

        if "standard user" in title_lower:

            await page.locator(
                "#user-name"
            ).fill(
                "standard_user"
            )

            await page.locator(
                "#password"
            ).fill(
                "secret_sauce"
            )

            await page.locator(
                "#login-button"
            ).click()

            await page.wait_for_load_state(
                "networkidle"
            )

            if "/inventory.html" not in page.url:

                raise AssertionError(
                    "User was not redirected to "
                    "the inventory page."
                )

        elif "empty credentials" in title_lower:

            await page.locator(
                "#login-button"
            ).click()

            error = page.locator(
                '[data-test="error"]'
            )

            await error.wait_for(
                state="visible"
            )

        elif "invalid password" in title_lower:

            await page.locator(
                "#user-name"
            ).fill(
                "standard_user"
            )

            await page.locator(
                "#password"
            ).fill(
                "wrong_password"
            )

            await page.locator(
                "#login-button"
            ).click()

            error = page.locator(
                '[data-test="error"]'
            )

            await error.wait_for(
                state="visible"
            )

        elif "locked out" in title_lower:

            await page.locator(
                "#user-name"
            ).fill(
                "locked_out_user"
            )

            await page.locator(
                "#password"
            ).fill(
                "secret_sauce"
            )

            await page.locator(
                "#login-button"
            ).click()

            error = page.locator(
                '[data-test="error"]'
            )

            await error.wait_for(
                state="visible"
            )

        else:

            result["status"] = "SKIPPED"

            result["error"] = (
                "No execution strategy implemented "
                "for this test yet."
            )

            return result

        result["status"] = "PASSED"

        print("STATUS: PASSED")

    except Exception as error:

        result["status"] = "FAILED"

        result["error"] = str(error)

        screenshot_path = (
            ARTIFACT_DIR /
            f"failure_{abs(hash(title))}.png"
        )

        await page.screenshot(
            path=str(screenshot_path),
            full_page=True
        )

        result["screenshot"] = str(
            screenshot_path
        )

        print("STATUS: FAILED")

        print(
            f"ERROR: {error}"
        )

    finally:

        await page.close()

    return result


async def main():

    print()
    print("=" * 60)
    print("          AI TEST EXECUTION ENGINE")
    print("=" * 60)

    test_cases = await load_test_cases()

    print(
        f"\nLoaded {len(test_cases)} AI-generated test cases."
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

            results.append(result)

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
        1
        for result in results
        if result["status"] == "PASSED"
    )

    failed = sum(
        1
        for result in results
        if result["status"] == "FAILED"
    )

    skipped = sum(
        1
        for result in results
        if result["status"] == "SKIPPED"
    )

    print()
    print("=" * 60)
    print("              EXECUTION SUMMARY")
    print("=" * 60)

    print(f"Total:    {len(results)}")
    print(f"Passed:   {passed}")
    print(f"Failed:   {failed}")
    print(f"Skipped:  {skipped}")

    print()
    print(
        f"Results saved to:\n{RESULTS_PATH}"
    )


if __name__ == "__main__":

    asyncio.run(main())