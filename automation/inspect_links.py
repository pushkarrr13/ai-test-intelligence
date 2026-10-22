import asyncio
from pathlib import Path

from playwright.async_api import async_playwright


# ============================================================
# CONFIGURATION
# ============================================================

USERNAME = "standard_user"
PASSWORD = "secret_sauce"

URL = "https://www.saucedemo.com/"

BASE_DIR = Path(__file__).resolve().parent.parent

ARTIFACTS_DIR = BASE_DIR / "artifacts"

OUTPUT_FILE = ARTIFACTS_DIR / "link_debug.json"


# ============================================================
# MAIN
# ============================================================

async def main():

    ARTIFACTS_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    async with async_playwright() as playwright:

        browser = await playwright.chromium.launch(
            headless=True
        )

        context = await browser.new_context(
            viewport={
                "width": 1440,
                "height": 900
            }
        )

        page = await context.new_page()

        # ----------------------------------------------------
        # OPEN LOGIN PAGE
        # ----------------------------------------------------

        print()
        print("=" * 70)
        print("OPENING SAUCEDEMO")
        print("=" * 70)

        await page.goto(
            URL,
            wait_until="domcontentloaded",
            timeout=30000
        )

        await page.wait_for_timeout(
            1000
        )

        print(
            f"Initial URL:"
            f"\n{page.url}"
        )

        # ----------------------------------------------------
        # LOGIN
        # ----------------------------------------------------

        print()
        print("=" * 70)
        print("LOGIN")
        print("=" * 70)

        username = page.locator(
            'input[name="user-name"]'
        )

        password = page.locator(
            'input[name="password"]'
        )

        login_button = page.locator(
            'input[type="submit"]'
        )

        print(
            f"Username fields:"
            f" {await username.count()}"
        )

        print(
            f"Password fields:"
            f" {await password.count()}"
        )

        print(
            f"Login buttons:"
            f" {await login_button.count()}"
        )

        await username.fill(
            USERNAME
        )

        await password.fill(
            PASSWORD
        )

        await login_button.click()

        await page.wait_for_timeout(
            1500
        )

        print(
            f"\nAfter login URL:"
            f"\n{page.url}"
        )

        # ----------------------------------------------------
        # PAGE INFORMATION
        # ----------------------------------------------------

        print()
        print("=" * 70)
        print("PAGE INFORMATION")
        print("=" * 70)

        print(
            f"Title:"
            f"\n{await page.title()}"
        )

        print(
            f"Anchor count:"
            f" {await page.locator('a').count()}"
        )

        print(
            f"Button count:"
            f" {await page.locator('button').count()}"
        )

        # ----------------------------------------------------
        # EXTRACT EVERY ANCHOR
        # ----------------------------------------------------

        print()
        print("=" * 70)
        print("ANCHOR INSPECTION")
        print("=" * 70)

        anchors = await page.locator(
            "a"
        ).evaluate_all(
            """
            elements => elements.map((element, index) => {

                const rect =
                    element.getBoundingClientRect();

                const style =
                    window.getComputedStyle(element);

                return {

                    index: index,

                    text:
                        (
                            element.innerText
                            ||
                            element.textContent
                            ||
                            ""
                        )
                        .trim()
                        .replace(/\\s+/g, " "),

                    href_attribute:
                        element.getAttribute("href"),

                    href_property:
                        element.href,

                    target:
                        element.getAttribute("target"),

                    id:
                        element.id || null,

                    class_name:
                        element.className || null,

                    role:
                        element.getAttribute("role"),

                    data_test:
                        element.getAttribute("data-test"),

                    aria_label:
                        element.getAttribute("aria-label"),

                    visible:
                        rect.width > 0 &&
                        rect.height > 0 &&
                        style.visibility !== "hidden" &&
                        style.display !== "none",

                    x:
                        Math.round(rect.x),

                    y:
                        Math.round(rect.y),

                    width:
                        Math.round(rect.width),

                    height:
                        Math.round(rect.height),

                    outer_html:
                        element.outerHTML.substring(
                            0,
                            1000
                        )
                };
            })
            """
        )

        # ----------------------------------------------------
        # PRINT ANCHORS
        # ----------------------------------------------------

        for anchor in anchors:

            print()
            print(
                "-" * 70
            )

            print(
                f"INDEX:"
                f" {anchor['index']}"
            )

            print(
                f"TEXT:"
                f" {anchor['text']}"
            )

            print(
                f"HREF ATTRIBUTE:"
                f" {anchor['href_attribute']}"
            )

            print(
                f"HREF PROPERTY:"
                f" {anchor['href_property']}"
            )

            print(
                f"DATA-TEST:"
                f" {anchor['data_test']}"
            )

            print(
                f"CLASS:"
                f" {anchor['class_name']}"
            )

            print(
                f"VISIBLE:"
                f" {anchor['visible']}"
            )

            print(
                f"OUTER HTML:"
                f"\n{anchor['outer_html']}"
            )

        # ----------------------------------------------------
        # ALL ELEMENTS WITH HREF
        # ----------------------------------------------------

        print()
        print("=" * 70)
        print("ALL ELEMENTS WITH HREF")
        print("=" * 70)

        href_elements = await page.locator(
            "[href]"
        ).evaluate_all(
            """
            elements => elements.map((element, index) => ({

                index: index,

                tag:
                    element.tagName.toLowerCase(),

                href:
                    element.getAttribute("href"),

                resolved_href:
                    element.href || null,

                text:
                    (
                        element.innerText
                        ||
                        element.textContent
                        ||
                        ""
                    )
                    .trim()
                    .replace(/\\s+/g, " ")
                    .substring(0, 300),

                id:
                    element.id || null,

                class_name:
                    element.className || null,

                data_test:
                    element.getAttribute("data-test")
            }))
            """
        )

        print(
            f"Total elements with href:"
            f" {len(href_elements)}"
        )

        for element in href_elements:

            print()
            print(
                f"[{element['tag']}]"
            )

            print(
                f"href="
                f"{element['href']}"
            )

            print(
                f"resolved="
                f"{element['resolved_href']}"
            )

            print(
                f"text="
                f"{element['text']}"
            )

            print(
                f"data-test="
                f"{element['data_test']}"
            )

        # ----------------------------------------------------
        # SAVE DEBUG DATA
        # ----------------------------------------------------

        debug_data = {

            "url":
                page.url,

            "title":
                await page.title(),

            "anchor_count":
                len(anchors),

            "anchors":
                anchors,

            "href_elements":
                href_elements
        }

        with open(
            OUTPUT_FILE,
            "w",
            encoding="utf-8"
        ) as file:

            import json

            json.dump(
                debug_data,
                file,
                indent=2,
                ensure_ascii=False
            )

        print()
        print("=" * 70)
        print("DEBUG COMPLETE")
        print("=" * 70)

        print(
            f"\nDebug file:"
        )

        print(
            OUTPUT_FILE
        )

        await browser.close()


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":

    asyncio.run(
        main()
    )