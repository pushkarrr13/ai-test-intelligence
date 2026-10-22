import asyncio
import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

from dotenv import load_dotenv
from playwright.async_api import (
    Browser,
    BrowserContext,
    Locator,
    Page,
    async_playwright,
)

from self_healing import heal_locator, record_healing


# ============================================================
# CONFIG
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent
ARTIFACTS_DIR = BASE_DIR / "artifacts"

JOURNEYS_FILE = ARTIFACTS_DIR / "ai_journeys.json"
OUTPUT_FILE = ARTIFACTS_DIR / "journey_execution_results.json"
STATUS_FILE = ARTIFACTS_DIR / "execution_status.json"

STEP_EVIDENCE_DIR = ARTIFACTS_DIR / "journey_evidence"

ENV_FILE = BASE_DIR / ".env"

load_dotenv(ENV_FILE)

TEST_USERNAME = os.getenv(
    "TEST_USERNAME",
    "standard_user"
)

TEST_PASSWORD = os.getenv(
    "TEST_PASSWORD",
    "secret_sauce"
)

HEADLESS = (
    os.getenv(
        "PLAYWRIGHT_HEADLESS",
        "true"
    ).lower()
    == "true"
)

TIMEOUT = int(
    os.getenv(
        "PLAYWRIGHT_TIMEOUT",
        "10000"
    )
)

POST_ACTION_WAIT = int(
    os.getenv(
        "POST_ACTION_WAIT",
        "700"
    )
)

BASE_URL = os.getenv(
    "TARGET_URL",
    os.getenv("BASE_URL", "https://www.saucedemo.com/")
)


# ============================================================
# HELPERS
# ============================================================

def normalize_text(value: Optional[str]) -> str:
    if not value:
        return ""

    return re.sub(
        r"\s+",
        " ",
        str(value).strip()
    ).lower()


def semantic_target(target: str) -> str:
    value = normalize_text(target)

    patterns = [
        r",?\s*empty$",
        r",?\s*with\s+\d+\s+items?$",
        r"\s*\(\d+\)$",
        r",?\s*\d+\s+items?$",
    ]

    for pattern in patterns:
        value = re.sub(
            pattern,
            "",
            value,
            flags=re.IGNORECASE
        ).strip()

    return value


def safe_filename(value: str) -> str:
    value = re.sub(
        r"[^a-zA-Z0-9_-]+",
        "_",
        value
    )

    return value[:100]


def save_json(path: Path, data: Any):
    path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with open(
        path,
        "w",
        encoding="utf-8"
    ) as file:
        json.dump(
            data,
            file,
            indent=2,
            ensure_ascii=False
        )


def write_execution_status(status: str, message: str):
    save_json(
        STATUS_FILE,
        {
            "status": status,
            "message": message,
            "updated_at": datetime.now().isoformat(),
        },
    )


def load_json(path: Path):
    if not path.exists():
        raise FileNotFoundError(
            f"File not found: {path}"
        )

    with open(
        path,
        "r",
        encoding="utf-8"
    ) as file:
        return json.load(file)


# ============================================================
# LOCATOR RESOLUTION
# ============================================================

async def locator_exists(
    locator: Locator
) -> bool:

    try:
        count = await locator.count()

        if count == 0:
            return False

        for index in range(
            min(count, 5)
        ):
            candidate = locator.nth(index)

            try:
                if await candidate.is_visible():
                    return True
            except Exception:
                continue

        return False

    except Exception:
        return False


async def resolve_locator(
    page: Page,
    target: str,
    action: str
) -> Tuple[Optional[Locator], str]:

    target = str(target or "").strip()

    if not target:
        return None, "empty-target"

    semantic = semantic_target(target)

    # --------------------------------------------------------
    # 1. data-test
    # --------------------------------------------------------

    locator = page.locator(
        f'[data-test="{target}"]'
    )

    if await locator_exists(locator):
        return locator, "data-test"

    # --------------------------------------------------------
    # 2. data-testid
    # --------------------------------------------------------

    locator = page.locator(
        f'[data-testid="{target}"]'
    )

    if await locator_exists(locator):
        return locator, "data-testid"

    # --------------------------------------------------------
    # 3. ID
    # --------------------------------------------------------

    locator = page.locator(
        f'#{target}'
    )

    if await locator_exists(locator):
        return locator, "id"

    # --------------------------------------------------------
    # 4. NAME
    # --------------------------------------------------------

    locator = page.locator(
        f'[name="{target}"]'
    )

    if await locator_exists(locator):
        return locator, "name"

    # --------------------------------------------------------
    # 5. EXACT ARIA LABEL
    # --------------------------------------------------------

    try:
        locator = page.get_by_label(
            target,
            exact=True
        )

        if await locator_exists(locator):
            return locator, "aria-label"
    except Exception:
        pass

    try:
        locator = page.locator(
            f'[aria-label="{target}"]'
        )

        if await locator_exists(locator):
            return locator, "aria-label"
    except Exception:
        pass

    # --------------------------------------------------------
    # 6. SEMANTIC ARIA LABEL
    # --------------------------------------------------------

    if semantic and semantic != normalize_text(target):

        locator = page.locator(
            f'[aria-label*="{semantic}" i]'
        )

        if await locator_exists(locator):
            return locator, "semantic-aria-label"

        locator = page.locator(
            f'[data-test*="{semantic}" i]'
        )

        if await locator_exists(locator):
            return locator, "semantic-data-test"

        locator = page.locator(
            f'[data-testid*="{semantic}" i]'
        )

        if await locator_exists(locator):
            return locator, "semantic-data-testid"

    # --------------------------------------------------------
    # 7. SELECT
    # --------------------------------------------------------

    if action == "select":

        try:
            locator = page.get_by_label(
                target,
                exact=True
            )

            if await locator.count() > 0:
                return locator, "select-label"
        except Exception:
            pass

        locator = page.locator("select")

        count = await locator.count()

        if count == 1:
            return locator, "single-select"

    # --------------------------------------------------------
    # 8. PLACEHOLDER
    # --------------------------------------------------------

    try:
        locator = page.get_by_placeholder(
            target,
            exact=True
        )

        if await locator_exists(locator):
            return locator, "placeholder"
    except Exception:
        pass

    # --------------------------------------------------------
    # 9. ROLE BASED RESOLUTION
    # --------------------------------------------------------

    roles = []

    if action == "click":
        roles = [
            "button",
            "link",
            "checkbox",
            "radio",
        ]

    elif action in [
        "fill",
        "press",
    ]:
        roles = [
            "textbox",
        ]

    for role in roles:

        try:
            locator = page.get_by_role(
                role,
                name=target,
                exact=True
            )

            if await locator_exists(locator):
                return locator, f"role-{role}"
        except Exception:
            pass

    # --------------------------------------------------------
    # 10. PARTIAL ROLE NAME
    # --------------------------------------------------------

    if semantic:

        for role in roles:

            try:
                locator = page.get_by_role(
                    role,
                    name=re.compile(
                        re.escape(semantic),
                        re.IGNORECASE
                    )
                )

                if await locator_exists(locator):
                    return (
                        locator,
                        f"semantic-role-{role}"
                    )
            except Exception:
                pass

    # --------------------------------------------------------
    # 11. EXACT TEXT
    # --------------------------------------------------------

    try:
        locator = page.get_by_text(
            target,
            exact=True
        )

        if await locator_exists(locator):
            return locator, "exact-text"
    except Exception:
        pass

    # --------------------------------------------------------
    # 12. PARTIAL TEXT
    # --------------------------------------------------------

    if semantic:

        try:
            locator = page.get_by_text(
                re.compile(
                    re.escape(semantic),
                    re.IGNORECASE
                )
            )

            if await locator_exists(locator):
                return locator, "partial-text"
        except Exception:
            pass

    return None, "not-found"


# ============================================================
# DOM DIAGNOSTICS
# ============================================================

async def get_dom_diagnostics(
    page: Page,
    target: str
) -> Dict[str, Any]:

    semantic = semantic_target(target)

    diagnostics = {
        "target": target,
        "semantic_target": semantic,
        "data_test_count": 0,
        "data_testid_count": 0,
        "id_count": 0,
        "name_count": 0,
        "aria_label_count": 0,
        "exact_text_count": 0,
        "interactive_elements": [],
    }

    selectors = {
        "data_test_count":
            f'[data-test="{target}"]',

        "data_testid_count":
            f'[data-testid="{target}"]',

        "id_count":
            f'#{target}',

        "name_count":
            f'[name="{target}"]',

        "aria_label_count":
            f'[aria-label="{target}"]',
    }

    for key, selector in selectors.items():

        try:
            diagnostics[key] = await page.locator(
                selector
            ).count()
        except Exception:
            diagnostics[key] = 0

    try:
        diagnostics["exact_text_count"] = (
            await page.get_by_text(
                target,
                exact=True
            ).count()
        )
    except Exception:
        pass

    try:
        diagnostics["interactive_elements"] = (
            await page.locator(
                """
                button,
                a,
                input,
                select,
                textarea,
                [role="button"],
                [role="link"],
                [data-test],
                [data-testid]
                """
            ).evaluate_all(
                """
                elements => elements
                    .slice(0, 100)
                    .map(el => ({
                        tag: el.tagName.toLowerCase(),
                        text: (
                            el.innerText ||
                            el.value ||
                            ''
                        ).trim(),
                        id: el.id || '',
                        aria_label:
                            el.getAttribute(
                                'aria-label'
                            ) || '',
                        data_test:
                            el.getAttribute(
                                'data-test'
                            ) || '',
                        data_testid:
                            el.getAttribute(
                                'data-testid'
                            ) || '',
                        role:
                            el.getAttribute(
                                'role'
                            ) || ''
                    }))
                """
            )
        )

    except Exception:
        pass

    return diagnostics


# ============================================================
# EVIDENCE
# ============================================================

async def capture_step_evidence(
    page: Page,
    journey_index: int,
    step_index: int,
    status: str
) -> Dict[str, str]:

    journey_dir = (
        STEP_EVIDENCE_DIR /
        f"journey_{journey_index}"
    )

    journey_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    prefix = (
        f"step_{step_index:02d}_"
        f"{status.lower()}"
    )

    screenshot_path = (
        journey_dir /
        f"{prefix}.png"
    )

    dom_path = (
        journey_dir /
        f"{prefix}.html"
    )

    try:
        await page.screenshot(
            path=str(
                screenshot_path
            ),
            full_page=True
        )
    except Exception:
        screenshot_path = None

    try:
        html = await page.content()

        with open(
            dom_path,
            "w",
            encoding="utf-8"
        ) as file:
            file.write(html)

    except Exception:
        dom_path = None

    return {
        "screenshot": (
            str(screenshot_path)
            if screenshot_path
            else ""
        ),
        "dom": (
            str(dom_path)
            if dom_path
            else ""
        ),
    }


# ============================================================
# AUTHENTICATION
# ============================================================

async def authenticate(
    page: Page
) -> bool:

    print()
    print("AUTHENTICATION BOOTSTRAP")

    await page.goto(
        BASE_URL,
        wait_until="domcontentloaded"
    )

    await page.wait_for_timeout(
        POST_ACTION_WAIT
    )

    current_url = page.url

    print(
        f"Initial URL: {current_url}"
    )

    # Already authenticated.
    if "/inventory.html" in current_url:
        print(
            "Already authenticated."
        )
        return True

    # The demo credentials below belong only to SauceDemo. Public targets
    # such as Google must proceed without a SauceDemo-specific login step.
    hostname = (urlparse(BASE_URL).hostname or "").lower()
    if hostname not in {"saucedemo.com", "www.saucedemo.com"}:
        print("Generic target detected; skipping SauceDemo login bootstrap.")
        return True

    try:
        username = page.get_by_placeholder(
            "Username",
            exact=True
        )

        password = page.get_by_placeholder(
            "Password",
            exact=True
        )

        login = page.locator(
            '[data-test="login-button"]'
        )

        if (
            await username.count() == 0
            or await password.count() == 0
            or await login.count() == 0
        ):
            print(
                "Login form not detected."
            )
            return False

        await username.fill(
            TEST_USERNAME
        )

        await password.fill(
            TEST_PASSWORD
        )

        await login.click()

        await page.wait_for_timeout(
            POST_ACTION_WAIT
        )

        if "/inventory.html" in page.url:
            print(
                "Authentication bootstrap: PASSED"
            )

            print(
                f"Authenticated URL: "
                f"{page.url}"
            )

            return True

        print(
            f"Authentication did not reach "
            f"inventory. URL: {page.url}"
        )

        return False

    except Exception as exc:

        print(
            f"Authentication failed: {exc}"
        )

        return False


# ============================================================
# ACTION EXECUTION
# ============================================================

async def execute_action(
    page: Page,
    action: Dict[str, Any],
    journey_index: int,
    step_index: int,
    journey_title: str,
) -> Dict[str, Any]:

    action_name = normalize_text(
        action.get("action", "")
    )

    target = str(
        action.get("target", "")
    ).strip()

    value = str(
        action.get("value", "")
    ).strip()

    result = {
        "action": action_name,
        "target": target,
        "value": value,
        "status": "FAILED",
        "locator_strategy": "",
        "healed": False,
        "healing": {},
        "error": "",
        "evidence": {},
    }

    # --------------------------------------------------------
    # NAVIGATE
    # --------------------------------------------------------

    if action_name == "navigate":

        try:
            await page.goto(
                value,
                wait_until="domcontentloaded"
            )

            await page.wait_for_timeout(
                POST_ACTION_WAIT
            )

            result["status"] = "PASSED"

            result["evidence"] = (
                await capture_step_evidence(
                    page,
                    journey_index,
                    step_index,
                    "PASSED"
                )
            )

            return result

        except Exception as exc:

            result["error"] = str(exc)

            result["evidence"] = (
                await capture_step_evidence(
                    page,
                    journey_index,
                    step_index,
                    "FAILED"
                )
            )

            return result

    # --------------------------------------------------------
    # WAIT
    # --------------------------------------------------------

    if action_name == "wait":

        try:
            wait_ms = int(
                value or "1000"
            )

            await page.wait_for_timeout(
                wait_ms
            )

            result["status"] = "PASSED"

            result["evidence"] = (
                await capture_step_evidence(
                    page,
                    journey_index,
                    step_index,
                    "PASSED"
                )
            )

            return result

        except Exception as exc:

            result["error"] = str(exc)

            return result

    # --------------------------------------------------------
    # ASSERT URL
    # --------------------------------------------------------

    if action_name == "assert_url":

        expected = value

        try:
            if page.url == expected:
                result["status"] = "PASSED"
            else:
                result["error"] = (
                    f"Expected URL: {expected}; "
                    f"Actual URL: {page.url}"
                )

            result["evidence"] = (
                await capture_step_evidence(
                    page,
                    journey_index,
                    step_index,
                    result["status"]
                )
            )

            return result

        except Exception as exc:

            result["error"] = str(exc)

            return result

    # --------------------------------------------------------
    # RESOLVE LOCATOR
    # --------------------------------------------------------

    locator, strategy = await resolve_locator(
        page,
        target,
        action_name
    )

    result["locator_strategy"] = strategy

    # --------------------------------------------------------
    # SELF HEAL IF LOCATOR FAILED
    # --------------------------------------------------------

    if locator is None:

        print(
            "    Normal locator resolution FAILED."
        )

        diagnostics = (
            await get_dom_diagnostics(
                page,
                target
            )
        )

        result["diagnostics"] = diagnostics

        healing = await heal_locator(
            page,
            target,
            action_name
        )

        result["healing"] = {
            "success": healing.success,
            "original_target":
                healing.original_target,
            "healed_target":
                healing.healed_target,
            "strategy":
                healing.strategy,
            "confidence":
                healing.confidence,
            "reason":
                healing.reason,
        }

        record_healing(
            healing,
            journey_title=journey_title,
            step_number=step_index,
            action=action_name,
        )

        if healing.success:

            locator = healing.locator

            result["healed"] = True

            result["locator_strategy"] = (
                f"SELF-HEAL:{healing.strategy}"
            )

            print(
                "    Self-healing: PASSED"
            )

        else:

            result["error"] = (
                f"Unable to resolve target "
                f"'{target}'. "
                f"Self-healing failed."
            )

            result["evidence"] = (
                await capture_step_evidence(
                    page,
                    journey_index,
                    step_index,
                    "FAILED"
                )
            )

            return result

    # --------------------------------------------------------
    # EXECUTE ACTION
    # --------------------------------------------------------

    try:

        if action_name == "click":

            await locator.click(
                timeout=TIMEOUT
            )

        elif action_name == "fill":

            await locator.fill(
                value,
                timeout=TIMEOUT
            )

        elif action_name == "select":

            await locator.select_option(
                value,
                timeout=TIMEOUT
            )

        elif action_name == "check":

            await locator.check(
                timeout=TIMEOUT
            )

        elif action_name == "uncheck":

            await locator.uncheck(
                timeout=TIMEOUT
            )

        elif action_name == "press":

            await locator.press(
                value,
                timeout=TIMEOUT
            )

        elif action_name == "assert_visible":

            if not await locator.is_visible():
                raise AssertionError(
                    f"Element '{target}' "
                    f"is not visible."
                )

        elif action_name == "assert_text":

            actual_text = (
                await locator.inner_text()
            )

            if value.lower() not in actual_text.lower():
                raise AssertionError(
                    f"Expected text "
                    f"'{value}' not found. "
                    f"Actual text: "
                    f"'{actual_text}'"
                )

        else:

            raise ValueError(
                f"Unsupported action: "
                f"{action_name}"
            )

        await page.wait_for_timeout(
            POST_ACTION_WAIT
        )

        result["status"] = "PASSED"

        result["evidence"] = (
            await capture_step_evidence(
                page,
                journey_index,
                step_index,
                "PASSED"
            )
        )

        return result

    except Exception as first_error:

        print(
            f"    Action failed: {first_error}"
        )

        # ----------------------------------------------------
        # SECOND CHANCE SELF-HEAL
        # ----------------------------------------------------

        print(
            "    Attempting second-chance self-healing..."
        )

        healing = await heal_locator(
            page,
            target,
            action_name
        )

        result["healing_retry"] = {
            "success": healing.success,
            "original_target":
                healing.original_target,
            "healed_target":
                healing.healed_target,
            "strategy":
                healing.strategy,
            "confidence":
                healing.confidence,
            "reason":
                healing.reason,
        }

        record_healing(
            healing,
            journey_title=journey_title,
            step_number=step_index,
            action=action_name,
        )

        if not healing.success:

            result["error"] = str(
                first_error
            )

            result["evidence"] = (
                await capture_step_evidence(
                    page,
                    journey_index,
                    step_index,
                    "FAILED"
                )
            )

            return result

        try:

            healed_locator = (
                healing.locator
            )

            if action_name == "click":

                await healed_locator.click(
                    timeout=TIMEOUT
                )

            elif action_name == "fill":

                await healed_locator.fill(
                    value,
                    timeout=TIMEOUT
                )

            elif action_name == "select":

                await healed_locator.select_option(
                    value,
                    timeout=TIMEOUT
                )

            elif action_name == "check":

                await healed_locator.check(
                    timeout=TIMEOUT
                )

            elif action_name == "uncheck":

                await healed_locator.uncheck(
                    timeout=TIMEOUT
                )

            elif action_name == "press":

                await healed_locator.press(
                    value,
                    timeout=TIMEOUT
                )

            elif action_name == "assert_visible":

                if not await healed_locator.is_visible():
                    raise AssertionError(
                        "Healed element is not visible."
                    )

            elif action_name == "assert_text":

                actual_text = (
                    await healed_locator.inner_text()
                )

                if value.lower() not in actual_text.lower():
                    raise AssertionError(
                        f"Expected text "
                        f"'{value}' not found "
                        f"after healing."
                    )

            else:

                raise ValueError(
                    f"Unsupported action: "
                    f"{action_name}"
                )

            await page.wait_for_timeout(
                POST_ACTION_WAIT
            )

            result["status"] = "PASSED"
            result["healed"] = True

            result["locator_strategy"] = (
                f"SELF-HEAL-RETRY:"
                f"{healing.strategy}"
            )

            result["evidence"] = (
                await capture_step_evidence(
                    page,
                    journey_index,
                    step_index,
                    "PASSED_HEALED"
                )
            )

            print(
                "    Self-healing retry: PASSED"
            )

            return result

        except Exception as retry_error:

            result["error"] = (
                f"Original error: "
                f"{first_error}; "
                f"Healed retry error: "
                f"{retry_error}"
            )

            result["evidence"] = (
                await capture_step_evidence(
                    page,
                    journey_index,
                    step_index,
                    "FAILED"
                )
            )

            return result


# ============================================================
# JOURNEY EXECUTION
# ============================================================

async def execute_journey(
    browser: Browser,
    journey: Dict[str, Any],
    journey_index: int
) -> Dict[str, Any]:

    title = journey.get(
        "title",
        f"Journey {journey_index}"
    )

    description = journey.get(
        "description",
        ""
    )

    actions = journey.get(
        "actions",
        []
    )

    print()
    print("=" * 70)
    print(
        f"JOURNEY {journey_index}: {title}"
    )
    print("=" * 70)

    print(
        f"Description: {description}"
    )

    context: BrowserContext = (
        await browser.new_context()
    )

    page: Page = (
        await context.new_page()
    )

    page.set_default_timeout(
        TIMEOUT
    )

    result = {
        "journey_index": journey_index,
        "title": title,
        "description": description,
        "status": "FAILED",
        "total_steps": len(actions),
        "passed_steps": 0,
        "failed_steps": 0,
        "healed_steps": 0,
        "steps": [],
    }

    try:

        authenticated = await authenticate(
            page
        )

        if not authenticated:

            result["error"] = (
                "Authentication bootstrap failed."
            )

            return result

        for index, action in enumerate(
            actions,
            start=1
        ):

            print()

            print(
                f"[{index}/{len(actions)}] "
                f"{action.get('action')} "
                f"target='{action.get('target', '')}' "
                f"value='{action.get('value', '')}'"
            )

            step_result = await execute_action(
                page=page,
                action=action,
                journey_index=journey_index,
                step_index=index,
                journey_title=title,
            )

            result["steps"].append(
                step_result
            )

            if step_result["status"] == "PASSED":

                result["passed_steps"] += 1

                if step_result.get(
                    "healed",
                    False
                ):
                    result["healed_steps"] += 1

                if step_result.get(
                    "healed",
                    False
                ):
                    print(
                        "    PASS "
                        "[SELF-HEALED]"
                    )
                else:
                    print(
                        f"    PASS "
                        f"[{step_result.get('locator_strategy', '')}]"
                    )

            else:

                result["failed_steps"] += 1

                print(
                    f"    FAIL: "
                    f"{step_result.get('error', '')}"
                )

                # Stop journey at first
                # unrecoverable failure.
                break

        if (
            result["failed_steps"] == 0
            and result["passed_steps"]
            == result["total_steps"]
        ):
            result["status"] = "PASSED"

            print()
            print(
                "JOURNEY RESULT: PASSED"
            )

        else:

            result["status"] = "FAILED"

            print()
            print(
                "JOURNEY RESULT: FAILED"
            )

    except Exception as exc:

        result["error"] = str(exc)

        print(
            f"JOURNEY ERROR: {exc}"
        )

    finally:

        await context.close()

    return result


# ============================================================
# MAIN
# ============================================================

async def main():

    print("=" * 70)
    print("AI TEST INTELLIGENCE - JOURNEY EXECUTOR")
    print("=" * 70)

    journeys_data = load_json(
        JOURNEYS_FILE
    )

    journeys = journeys_data.get(
        "journeys",
        []
    )

    print(
        f"Base URL : {BASE_URL}"
    )

    print(
        f"Journeys : {len(journeys)}"
    )

    print(
        f"Headless : {HEADLESS}"
    )

    print(
        f"Timeout  : {TIMEOUT} ms"
    )

    print(
        f"Self-Healing: ENABLED"
    )

    STEP_EVIDENCE_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    async with async_playwright() as playwright:

        browser = await playwright.chromium.launch(
            headless=HEADLESS
        )

        results = []

        for index, journey in enumerate(
            journeys,
            start=1
        ):

            result = await execute_journey(
                browser,
                journey,
                index
            )

            results.append(
                result
            )

        await browser.close()

    # --------------------------------------------------------
    # SUMMARY
    # --------------------------------------------------------

    total = len(results)

    passed = sum(
        1
        for result in results
        if result["status"] == "PASSED"
    )

    failed = total - passed

    healed_steps = sum(
        result.get(
            "healed_steps",
            0
        )
        for result in results
    )

    output = {
        "base_url": BASE_URL,
        "total_journeys": total,
        "passed_journeys": passed,
        "failed_journeys": failed,
        "healed_steps": healed_steps,
        "journeys": results,
    }

    save_json(
        OUTPUT_FILE,
        output
    )

    write_execution_status(
        "completed",
        f"Execution finished: {passed} passed, {failed} failed.",
    )

    print()
    print("=" * 70)
    print("EXECUTION SUMMARY")
    print("=" * 70)

    print(
        f"Total journeys : {total}"
    )

    print(
        f"Passed         : {passed}"
    )

    print(
        f"Failed         : {failed}"
    )

    print(
        f"Healed steps   : {healed_steps}"
    )

    print()
    print(
        f"Results saved: {OUTPUT_FILE}"
    )

    print(
        f"Healing report: "
        f"{ARTIFACTS_DIR / 'self_healing_report.json'}"
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as exc:
        write_execution_status("failed", f"Execution failed: {exc}")
        raise
