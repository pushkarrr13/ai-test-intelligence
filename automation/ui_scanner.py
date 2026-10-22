import asyncio
import json
import sys
from pathlib import Path

from playwright.async_api import async_playwright


ROOT_DIR = Path(__file__).resolve().parent.parent
ARTIFACT_DIR = ROOT_DIR / "artifacts"
ARTIFACT_DIR.mkdir(exist_ok=True)


async def scan_page(url: str):

    async with async_playwright() as p:

        browser = await p.chromium.launch(
            headless=True
        )

        page = await browser.new_page(
            viewport={
                "width": 1440,
                "height": 900
            }
        )

        print(f"\n[1/7] Opening: {url}")

        await page.goto(
            url,
            wait_until="domcontentloaded",
            timeout=30000
        )

        await page.wait_for_timeout(1500)

        print("[2/7] Reading page metadata...")

        title = await page.title()

        print("[3/7] Extracting UI elements...")

        elements = await page.locator(
            """
            input,
            button,
            textarea,
            select,
            option,
            a,
            checkbox,
            [role],
            [contenteditable="true"]
            """
        ).evaluate_all(
            """
            elements => elements.map((el, index) => {

                const rect = el.getBoundingClientRect();

                const text =
                    (el.innerText ||
                     el.textContent ||
                     "").trim();

                return {

                    index: index,

                    tag: el.tagName.toLowerCase(),

                    type:
                        el.getAttribute("type"),

                    role:
                        el.getAttribute("role"),

                    text:
                        text.substring(0, 200),

                    id:
                        el.getAttribute("id"),

                    name:
                        el.getAttribute("name"),

                    placeholder:
                        el.getAttribute("placeholder"),

                    aria_label:
                        el.getAttribute("aria-label"),

                    title:
                        el.getAttribute("title"),

                    href:
                        el.getAttribute("href"),

                    value:
                        el.getAttribute("value"),

                    required:
                        el.hasAttribute("required"),

                    disabled:
                        el.hasAttribute("disabled"),

                    checked:
                        el.hasAttribute("checked"),

                    visible:
                        rect.width > 0 &&
                        rect.height > 0,

                    coordinates: {
                        x: Math.round(rect.x),
                        y: Math.round(rect.y),
                        width: Math.round(rect.width),
                        height: Math.round(rect.height)
                    }
                };
            })
            """
        )

        print("[4/7] Extracting headings...")

        headings = await page.locator(
            "h1, h2, h3, h4, h5, h6"
        ).evaluate_all(
            """
            elements => elements.map(el => ({
                tag: el.tagName.toLowerCase(),
                text: (el.innerText || "").trim()
            }))
            """
        )

        print("[5/7] Extracting forms...")

        forms = await page.locator(
            "form"
        ).evaluate_all(
            """
            forms => forms.map((form, index) => ({
                index: index,
                id: form.id,
                name: form.getAttribute("name"),
                action: form.getAttribute("action"),
                method: form.getAttribute("method"),
                inputs: Array.from(
                    form.querySelectorAll(
                        "input, textarea, select"
                    )
                ).map(input => ({
                    tag: input.tagName.toLowerCase(),
                    type: input.getAttribute("type"),
                    name: input.getAttribute("name"),
                    id: input.id,
                    placeholder:
                        input.getAttribute("placeholder"),
                    required:
                        input.hasAttribute("required")
                }))
            }))
            """
        )

        print("[6/7] Taking screenshot...")

        screenshot_path = (
            ARTIFACT_DIR / "page.png"
        )

        await page.screenshot(
            path=str(screenshot_path),
            full_page=True
        )

        print("[7/7] Building UI model...")

        ui_model = {

            "page": {
                "url": page.url,
                "title": title
            },

            "headings": headings,

            "forms": forms,

            "elements": elements,

            "statistics": {
                "total_elements": len(elements),
                "visible_elements": sum(
                    1
                    for element in elements
                    if element["visible"]
                ),
                "buttons": sum(
                    1
                    for element in elements
                    if element["tag"] == "button"
                    or element["role"] == "button"
                ),
                "inputs": sum(
                    1
                    for element in elements
                    if element["tag"] in [
                        "input",
                        "textarea",
                        "select"
                    ]
                ),
                "links": sum(
                    1
                    for element in elements
                    if element["tag"] == "a"
                ),
                "forms": len(forms),
                "headings": len(headings)
            },

            "screenshot": str(
                screenshot_path
            )
        }

        json_path = (
            ARTIFACT_DIR / "ui_model.json"
        )

        with open(
            json_path,
            "w",
            encoding="utf-8"
        ) as file:

            json.dump(
                ui_model,
                file,
                indent=2,
                ensure_ascii=False
            )

        await browser.close()

        return ui_model


async def main():

    if len(sys.argv) < 2:

        print(
            "\nUsage:"
            "\npython ui_scanner.py <URL>"
        )

        return

    url = sys.argv[1]

    try:

        result = await scan_page(url)

        stats = result["statistics"]

        print("\n")
        print("=" * 50)
        print("           AI UI SCANNER")
        print("=" * 50)

        print(f"URL:              {result['page']['url']}")
        print(f"Title:            {result['page']['title']}")
        print()

        print("UI STATISTICS")
        print("-" * 50)

        print(
            f"Total Elements:   {stats['total_elements']}"
        )

        print(
            f"Visible Elements: {stats['visible_elements']}"
        )

        print(
            f"Buttons:          {stats['buttons']}"
        )

        print(
            f"Inputs:           {stats['inputs']}"
        )

        print(
            f"Links:            {stats['links']}"
        )

        print(
            f"Forms:            {stats['forms']}"
        )

        print(
            f"Headings:         {stats['headings']}"
        )

        print()
        print("ARTIFACTS")
        print("-" * 50)

        print(
            f"UI Model:         {ARTIFACT_DIR / 'ui_model.json'}"
        )

        print(
            f"Screenshot:       {ARTIFACT_DIR / 'page.png'}"
        )

        print()
        print("DETECTED UI")
        print("-" * 50)

        for element in result["elements"]:

            if not element["visible"]:
                continue

            name = (
                element["text"]
                or element["placeholder"]
                or element["aria_label"]
                or element["name"]
                or element["id"]
                or "Unnamed"
            )

            print(
                f"[{element['tag']}] {name}"
            )

        print()
        print("=" * 50)
        print("SCAN COMPLETE")
        print("=" * 50)

    except Exception as error:

        print("\nSCAN FAILED")
        print(f"Error: {error}")


if __name__ == "__main__":

    asyncio.run(main())