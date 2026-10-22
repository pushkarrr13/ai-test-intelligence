import asyncio
import hashlib
import json
import sys
from pathlib import Path
from urllib.parse import urlparse, urldefrag

from playwright.async_api import async_playwright


# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent

ARTIFACTS_DIR = BASE_DIR / "artifacts"
PAGES_DIR = ARTIFACTS_DIR / "pages"

SITE_MAP_FILE = ARTIFACTS_DIR / "site_map.json"

MAX_PAGES = 20
MAX_DEPTH = 3

PAGE_TIMEOUT = 30000

VIEWPORT_WIDTH = 1440
VIEWPORT_HEIGHT = 900

TEST_USERNAME = "standard_user"
TEST_PASSWORD = "secret_sauce"


# ============================================================
# EXPLORATION SAFETY
# ============================================================

# These actions should NOT be automatically clicked while
# discovering the application.

DANGEROUS_KEYWORDS = [
    "logout",
    "log out",
    "reset",
    "delete",
    "remove",
    "checkout",
    "place order",
    "cancel order",
    "submit order",
    "pay",
    "purchase",
    "confirm order",
    "complete order",
]


# ============================================================
# URL HELPERS
# ============================================================

def normalize_url(url):

    if not url:
        return ""

    url = urldefrag(url)[0]

    parsed = urlparse(url)

    scheme = parsed.scheme.lower()

    hostname = (
        parsed.hostname.lower()
        if parsed.hostname
        else ""
    )

    port = parsed.port

    if port is None:
        netloc = hostname

    elif (
        (scheme == "http" and port == 80)
        or
        (scheme == "https" and port == 443)
    ):
        netloc = hostname

    else:
        netloc = f"{hostname}:{port}"

    path = parsed.path or "/"

    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")

    normalized = (
        f"{scheme}://{netloc}{path}"
    )

    if parsed.query:
        normalized += f"?{parsed.query}"

    return normalized


def default_port(scheme):

    if scheme.lower() == "https":
        return 443

    return 80


def is_same_origin(
    base_url,
    target_url
):

    if not target_url:
        return False

    base = urlparse(base_url)
    target = urlparse(target_url)

    if not base.hostname or not target.hostname:
        return False

    base_port = (
        base.port
        or default_port(base.scheme)
    )

    target_port = (
        target.port
        or default_port(target.scheme)
    )

    return (
        base.scheme.lower()
        == target.scheme.lower()
        and
        base.hostname.lower()
        == target.hostname.lower()
        and
        base_port
        == target_port
    )


# ============================================================
# PAGE ID
# ============================================================

def generate_page_id(url):

    return hashlib.sha256(
        url.encode("utf-8")
    ).hexdigest()[:12]


# ============================================================
# SAFE ACTION CHECK
# ============================================================

def is_dangerous_action(
    text,
    aria_label,
    data_test
):

    combined = " ".join(
        [
            text or "",
            aria_label or "",
            data_test or "",
        ]
    ).lower()

    for keyword in DANGEROUS_KEYWORDS:

        if keyword in combined:
            return True

    return False


# ============================================================
# UI MODEL
# ============================================================

async def extract_ui_model(
    page,
    url
):

    title = await page.title()

    elements = await page.locator(
        """
        input,
        button,
        textarea,
        select,
        option,
        a,
        [role],
        [contenteditable="true"]
        """
    ).evaluate_all(
        """
        elements => elements.map((element, index) => {

            const rect =
                element.getBoundingClientRect();

            const style =
                window.getComputedStyle(element);

            const visible =
                rect.width > 0 &&
                rect.height > 0 &&
                style.visibility !== "hidden" &&
                style.display !== "none";

            return {

                index,

                tag:
                    element.tagName.toLowerCase(),

                type:
                    element.getAttribute("type")
                    || null,

                role:
                    element.getAttribute("role")
                    || null,

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
                    element.id
                    || null,

                name:
                    element.getAttribute("name")
                    || null,

                placeholder:
                    element.getAttribute("placeholder")
                    || null,

                aria_label:
                    element.getAttribute("aria-label")
                    || null,

                title:
                    element.getAttribute("title")
                    || null,

                href:
                    element.getAttribute("href")
                    || null,

                data_test:
                    element.getAttribute("data-test")
                    || null,

                value:
                    element.value
                    || null,

                required:
                    element.required
                    || false,

                disabled:
                    element.disabled
                    || false,

                checked:
                    element.checked
                    || false,

                visible,

                x:
                    Math.round(rect.x),

                y:
                    Math.round(rect.y),

                width:
                    Math.round(rect.width),

                height:
                    Math.round(rect.height)
            };
        })
        """
    )

    headings = await page.locator(
        "h1, h2, h3, h4, h5, h6"
    ).evaluate_all(
        """
        elements => elements.map(element => ({
            tag:
                element.tagName.toLowerCase(),

            text:
                (element.innerText || "")
                    .trim()
        }))
        """
    )

    forms = await page.locator(
        "form"
    ).evaluate_all(
        """
        forms => forms.map((form, index) => ({

            index,

            action:
                form.getAttribute("action")
                || null,

            method:
                form.getAttribute("method")
                || "get",

            inputs:
                Array.from(
                    form.querySelectorAll(
                        "input, textarea, select"
                    )
                ).map(element => ({

                    tag:
                        element.tagName.toLowerCase(),

                    type:
                        element.getAttribute("type")
                        || null,

                    name:
                        element.getAttribute("name")
                        || null,

                    id:
                        element.id
                        || null,

                    placeholder:
                        element.getAttribute("placeholder")
                        || null,

                    required:
                        element.required
                        || false
                }))
        }))
        """
    )

    visible_elements = [
        element
        for element in elements
        if element["visible"]
    ]

    buttons = [
        element
        for element in visible_elements
        if (
            element["tag"] == "button"
            or
            (
                element["tag"] == "input"
                and
                element["type"] in [
                    "button",
                    "submit",
                    "reset"
                ]
            )
            or
            element["role"] == "button"
        )
    ]

    inputs = [
        element
        for element in visible_elements
        if element["tag"] in [
            "input",
            "textarea",
            "select"
        ]
    ]

    links = [
        element
        for element in visible_elements
        if element["tag"] == "a"
    ]

    return {

        "url":
            url,

        "title":
            title,

        "elements":
            elements,

        "headings":
            headings,

        "forms":
            forms,

        "links":
            links,

        "stats": {

            "total_elements":
                len(elements),

            "visible_elements":
                len(visible_elements),

            "buttons":
                len(buttons),

            "inputs":
                len(inputs),

            "links":
                len(links),

            "forms":
                len(forms),

            "headings":
                len(headings)
        }
    }


# ============================================================
# PAGE SIGNATURE
# ============================================================

async def get_page_signature(page):

    try:

        signature = await page.locator(
            "body"
        ).inner_text(
            timeout=5000
        )

        signature = (
            signature
            .strip()
            .replace("\n", " ")
        )

        signature = " ".join(
            signature.split()
        )

        return signature[:3000]

    except Exception:

        return ""


# ============================================================
# LOGIN DETECTION
# ============================================================

async def detect_login_form(page):

    username_selectors = [
        'input[name="user-name"]',
        'input[name="username"]',
        'input[type="email"]',
        'input[placeholder*="Username" i]',
    ]

    password_selectors = [
        'input[name="password"]',
        'input[type="password"]',
        'input[placeholder*="Password" i]',
    ]

    username = None
    password = None

    for selector in username_selectors:

        locator = page.locator(
            selector
        )

        try:

            if await locator.count() > 0:

                candidate = locator.first

                if await candidate.is_visible():

                    username = candidate

                    break

        except Exception:
            continue

    for selector in password_selectors:

        locator = page.locator(
            selector
        )

        try:

            if await locator.count() > 0:

                candidate = locator.first

                if await candidate.is_visible():

                    password = candidate

                    break

        except Exception:
            continue

    if not username or not password:
        return None

    return {
        "username":
            username,

        "password":
            password
    }


# ============================================================
# LOGIN BUTTON
# ============================================================

async def find_login_button(page):

    selectors = [
        'input[type="submit"]',
        'button[type="submit"]',
    ]

    for selector in selectors:

        locator = page.locator(
            selector
        )

        try:

            count = await locator.count()

            for index in range(count):

                candidate = locator.nth(
                    index
                )

                if await candidate.is_visible():

                    return candidate

        except Exception:
            continue

    return None


# ============================================================
# LOGIN
# ============================================================

async def attempt_login(page):

    print()
    print("=" * 70)
    print("CHECKING FOR LOGIN FORM")
    print("=" * 70)

    login_form = await detect_login_form(
        page
    )

    if not login_form:

        print(
            "No login form detected."
        )

        return False

    print(
        "Login form detected."
    )

    login_button = await find_login_button(
        page
    )

    if not login_button:

        print(
            "Login button not detected."
        )

        return False

    try:

        print(
            "Filling username..."
        )

        await login_form[
            "username"
        ].fill(
            TEST_USERNAME
        )

        print(
            "Filling password..."
        )

        await login_form[
            "password"
        ].fill(
            TEST_PASSWORD
        )

        print(
            "Clicking login..."
        )

        await login_button.click()

        await page.wait_for_timeout(
            1500
        )

        print(
            "After login URL:"
        )

        print(
            page.url
        )

        if (
            "inventory"
            in page.url.lower()
        ):

            print(
                "Login successful."
            )

            return True

        inventory_marker = page.locator(
            ".inventory_list"
        )

        if await inventory_marker.count() > 0:

            print(
                "Login successful."
            )

            return True

        if not await detect_login_form(
            page
        ):

            print(
                "Login appears successful."
            )

            return True

        print(
            "Login may have failed."
        )

        return False

    except Exception as error:

        print(
            f"Login error:"
            f" {error}"
        )

        return False


# ============================================================
# SAVE PAGE
# ============================================================

async def save_page_artifacts(
    page,
    url,
    depth,
    authenticated
):

    page_id = generate_page_id(
        url
    )

    page_dir = (
        PAGES_DIR /
        page_id
    )

    page_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    ui_model = await extract_ui_model(
        page,
        url
    )

    ui_model[
        "page_id"
    ] = page_id

    ui_model[
        "depth"
    ] = depth

    ui_model[
        "authenticated"
    ] = authenticated

    ui_model_file = (
        page_dir /
        "ui_model.json"
    )

    screenshot_file = (
        page_dir /
        "page.png"
    )

    with open(
        ui_model_file,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            ui_model,
            file,
            indent=2,
            ensure_ascii=False
        )

    await page.screenshot(
        path=str(
            screenshot_file
        ),
        full_page=True
    )

    return {

        "page_id":
            page_id,

        "url":
            url,

        "title":
            ui_model[
                "title"
            ],

        "depth":
            depth,

        "authenticated":
            authenticated,

        "ui_model":
            str(
                ui_model_file.relative_to(
                    BASE_DIR
                )
            ),

        "screenshot":
            str(
                screenshot_file.relative_to(
                    BASE_DIR
                )
            ),

        "stats":
            ui_model[
                "stats"
            ]
    }


# ============================================================
# GET INTERACTIVE ELEMENTS
# ============================================================

async def get_interactive_elements(page):

    return await page.locator(
        """
        button,
        a,
        [role="button"],
        input[type="button"],
        input[type="submit"]
        """
    ).evaluate_all(
        """
        elements => elements.map((element, index) => {

            const rect =
                element.getBoundingClientRect();

            const style =
                window.getComputedStyle(element);

            const visible =
                rect.width > 0 &&
                rect.height > 0 &&
                style.visibility !== "hidden" &&
                style.display !== "none";

            return {

                index,

                tag:
                    element.tagName.toLowerCase(),

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
                    .substring(0, 200),

                aria_label:
                    element.getAttribute(
                        "aria-label"
                    )
                    || "",

                data_test:
                    element.getAttribute(
                        "data-test"
                    )
                    || "",

                id:
                    element.id
                    || "",

                href:
                    element.getAttribute(
                        "href"
                    )
                    || "",

                role:
                    element.getAttribute(
                        "role"
                    )
                    || "",

                visible,

                disabled:
                    element.disabled
                    || false
            };
        })
        """
    )


# ============================================================
# SAFE CLICK
# ============================================================

async def explore_interactive_element(
    page,
    base_url,
    element_info
):

    if not element_info["visible"]:
        return None

    if element_info["disabled"]:
        return None

    if is_dangerous_action(
        element_info["text"],
        element_info["aria_label"],
        element_info["data_test"]
    ):

        print(
            f"  SKIP dangerous:"
            f" {element_info['text']}"
        )

        return None

    before_url = normalize_url(
        page.url
    )

    before_signature = (
        await get_page_signature(
            page
        )
    )

    before_title = await page.title()

    # --------------------------------------------------------
    # Build locator
    # --------------------------------------------------------

    locator = None

    data_test = element_info[
        "data_test"
    ]

    element_id = element_info[
        "id"
    ]

    aria_label = element_info[
        "aria_label"
    ]

    text = element_info[
        "text"
    ]

    if data_test:

        locator = page.locator(
            f'[data-test="{data_test}"]'
        )

    elif element_id:

        locator = page.locator(
            f"#{element_id}"
        )

    elif aria_label:

        locator = page.locator(
            f'[aria-label="{aria_label}"]'
        )

    elif text:

        locator = page.get_by_text(
            text,
            exact=True
        )

    if not locator:
        return None

    try:

        if await locator.count() == 0:
            return None

        locator = locator.first

        if not await locator.is_visible():
            return None

        # ----------------------------------------------------
        # Click
        # ----------------------------------------------------

        description = (
            element_info["text"]
            or
            element_info["aria_label"]
            or
            element_info["data_test"]
            or
            element_info["id"]
        )

        print(
            f"  CLICK:"
            f" {description}"
        )

        try:

            async with page.expect_navigation(
                timeout=2500,
                wait_until="domcontentloaded"
            ):

                await locator.click(
                    timeout=5000
                )

        except Exception:

            # Many SPA/JS buttons do not trigger
            # browser navigation.

            try:

                await locator.click(
                    timeout=5000
                )

            except Exception:

                return None

        await page.wait_for_timeout(
            700
        )

        after_url = normalize_url(
            page.url
        )

        after_signature = (
            await get_page_signature(
                page
            )
        )

        after_title = await page.title()

        url_changed = (
            after_url
            != before_url
        )

        content_changed = (
            after_signature
            != before_signature
        )

        title_changed = (
            after_title
            != before_title
        )

        # ----------------------------------------------------
        # Determine whether this revealed a new state/page
        # ----------------------------------------------------

        changed = (
            url_changed
            or
            content_changed
            or
            title_changed
        )

        if not changed:

            print(
                "    No observable change."
            )

            return None

        if not is_same_origin(
            base_url,
            after_url
        ):

            print(
                "    Outside base origin."
            )

            return None

        print(
            f"    NEW STATE:"
            f" {after_url}"
        )

        return {

            "action":
                "click",

            "element":
                element_info,

            "from_url":
                before_url,

            "to_url":
                after_url,

            "url_changed":
                url_changed,

            "content_changed":
                content_changed,

            "title_changed":
                title_changed
        }

    except Exception as error:

        print(
            f"    Click failed:"
            f" {error}"
        )

        return None


# ============================================================
# EXPLORE PAGE INTERACTIONS
# ============================================================

async def explore_page_interactions(
    page,
    base_url,
    current_url,
    depth,
    authenticated,
    visited
):

    discovered_states = []

    print()
    print(
        "Interactive exploration:"
    )

    elements = await get_interactive_elements(
        page
    )

    print(
        f"  Interactive elements:"
        f" {len(elements)}"
    )

    # --------------------------------------------------------
    # Only inspect a reasonable number of elements.
    # --------------------------------------------------------

    for element in elements:

        if len(discovered_states) >= 10:
            break

        result = (
            await explore_interactive_element(
                page,
                base_url,
                element
            )
        )

        if not result:
            continue

        discovered_url = result[
            "to_url"
        ]

        if discovered_url in visited:
            continue

        discovered_states.append(
            {
                "url":
                    discovered_url,

                "depth":
                    depth + 1,

                "trigger":
                    result
            }
        )

        # ----------------------------------------------------
        # Restore original page
        # ----------------------------------------------------

        try:

            await page.goto(
                current_url,
                wait_until="domcontentloaded",
                timeout=PAGE_TIMEOUT
            )

            await page.wait_for_timeout(
                500
            )

        except Exception:

            pass

    return discovered_states


# ============================================================
# CRAWLER
# ============================================================

async def crawl_website(
    base_url
):

    base_url = normalize_url(
        base_url
    )

    print()
    print("=" * 70)
    print("AI TEST INTELLIGENCE - WEB EXPLORER V4")
    print("=" * 70)

    print(
        f"\nBase URL:"
    )

    print(
        base_url
    )

    print(
        f"\nMaximum Pages:"
        f" {MAX_PAGES}"
    )

    print(
        f"Maximum Depth:"
        f" {MAX_DEPTH}"
    )

    PAGES_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    visited = set()

    queue = []

    pages = []

    links_map = {}

    authenticated = False

    async with async_playwright() as playwright:

        browser = await playwright.chromium.launch(
            headless=True
        )

        context = await browser.new_context(
            viewport={
                "width":
                    VIEWPORT_WIDTH,

                "height":
                    VIEWPORT_HEIGHT
            }
        )

        page = await context.new_page()

        # ----------------------------------------------------
        # OPEN BASE
        # ----------------------------------------------------

        print()
        print(
            "Opening base URL..."
        )

        try:

            await page.goto(
                base_url,
                wait_until="domcontentloaded",
                timeout=PAGE_TIMEOUT
            )

            await page.wait_for_timeout(
                1000
            )

        except Exception as error:

            print(
                f"Could not open base URL:"
                f" {error}"
            )

            await browser.close()

            return

        # ----------------------------------------------------
        # LOGIN
        # ----------------------------------------------------

        authenticated = await attempt_login(
            page
        )

        current_url = normalize_url(
            page.url
        )

        queue.append(
            {
                "url":
                    current_url,

                "depth":
                    0
            }
        )

        # ----------------------------------------------------
        # MAIN CRAWL
        # ----------------------------------------------------

        while (
            queue
            and
            len(pages) < MAX_PAGES
        ):

            current = queue.pop(0)

            url = current[
                "url"
            ]

            depth = current[
                "depth"
            ]

            if url in visited:
                continue

            if depth > MAX_DEPTH:
                continue

            visited.add(
                url
            )

            print()
            print(
                "-" * 70
            )

            print(
                f"Page "
                f"{len(pages) + 1}"
                f"/{MAX_PAGES}"
            )

            print(
                f"Depth : {depth}"
            )

            print(
                f"URL   : {url}"
            )

            # ------------------------------------------------
            # NAVIGATE
            # ------------------------------------------------

            try:

                current_page_url = normalize_url(
                    page.url
                )

                if current_page_url != url:

                    await page.goto(
                        url,
                        wait_until="domcontentloaded",
                        timeout=PAGE_TIMEOUT
                    )

                    await page.wait_for_timeout(
                        700
                    )

            except Exception as error:

                print(
                    f"Navigation error:"
                    f" {error}"
                )

                continue

            # ------------------------------------------------
            # SAVE PAGE
            # ------------------------------------------------

            try:

                page_info = (
                    await save_page_artifacts(
                        page,
                        url,
                        depth,
                        authenticated
                    )
                )

                pages.append(
                    page_info
                )

                print(
                    f"Title :"
                    f" {page_info['title']}"
                )

                print(
                    f"Stats :"
                    f" {page_info['stats']}"
                )

            except Exception as error:

                print(
                    f"Page save error:"
                    f" {error}"
                )

                continue

            # ------------------------------------------------
            # EXPLORE INTERACTIVE ELEMENTS
            # ------------------------------------------------

            if depth < MAX_DEPTH:

                discovered_states = (
                    await explore_page_interactions(
                        page,
                        base_url,
                        url,
                        depth,
                        authenticated,
                        visited
                    )
                )

                links_map[
                    url
                ] = discovered_states

                print()
                print(
                    f"New states discovered:"
                    f" {len(discovered_states)}"
                )

                # ------------------------------------------------
                # QUEUE NEW STATES
                # ------------------------------------------------

                for state in discovered_states:

                    state_url = state[
                        "url"
                    ]

                    if state_url in visited:
                        continue

                    if any(
                        item["url"]
                        == state_url
                        for item in queue
                    ):
                        continue

                    if (
                        len(visited)
                        +
                        len(queue)
                        >= MAX_PAGES
                    ):
                        break

                    queue.append(
                        {
                            "url":
                                state_url,

                            "depth":
                                state[
                                    "depth"
                                ]
                        }
                    )

        await browser.close()

    # ========================================================
    # SAVE SITE MAP
    # ========================================================

    site_map = {

        "base_url":
            base_url,

        "authenticated":
            authenticated,

        "max_pages":
            MAX_PAGES,

        "max_depth":
            MAX_DEPTH,

        "total_pages":
            len(pages),

        "pages":
            pages,

        "navigation":
            links_map
    }

    with open(
        SITE_MAP_FILE,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            site_map,
            file,
            indent=2,
            ensure_ascii=False
        )

    # ========================================================
    # SUMMARY
    # ========================================================

    print()
    print("=" * 70)
    print("EXPLORATION COMPLETE")
    print("=" * 70)

    print(
        f"\nAuthenticated:"
        f" {authenticated}"
    )

    print(
        f"Pages discovered:"
        f" {len(pages)}"
    )

    print(
        f"\nSite map:"
    )

    print(
        SITE_MAP_FILE
    )

    print()
    print(
        "Discovered pages:"
    )

    for page_info in pages:

        print(
            f"  "
            f"{page_info.get('page_id', '-')}"
            f" | "
            f"{page_info.get('url', '-')}"
        )

    print()
    print("=" * 70)


# ============================================================
# MAIN
# ============================================================

def main():

    if len(sys.argv) < 2:

        print()
        print(
            "Usage:"
        )

        print(
            "python .\\automation\\web_explorer.py <URL>"
        )

        print()

        print(
            "Example:"
        )

        print(
            "python .\\automation\\web_explorer.py https://www.saucedemo.com/"
        )

        sys.exit(1)

    url = sys.argv[1]

    asyncio.run(
        crawl_website(
            url
        )
    )


if __name__ == "__main__":

    main()