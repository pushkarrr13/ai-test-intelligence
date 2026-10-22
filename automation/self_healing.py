import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from playwright.async_api import Page, Locator


# ============================================================
# CONFIG
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent
ARTIFACTS_DIR = BASE_DIR / "artifacts"

HEALING_REPORT_FILE = ARTIFACTS_DIR / "self_healing_report.json"


# ============================================================
# DATA MODEL
# ============================================================

@dataclass
class Candidate:
    tag: str
    text: str
    element_id: str
    name: str
    aria_label: str
    placeholder: str
    data_test: str
    data_testid: str
    role: str
    input_type: str
    visible: bool


@dataclass
class HealingResult:
    success: bool
    original_target: str
    healed_target: str
    strategy: str
    confidence: float
    reason: str
    locator: Optional[Locator] = None


# ============================================================
# TEXT HELPERS
# ============================================================

def normalize(value: Optional[str]) -> str:
    if not value:
        return ""

    return re.sub(
        r"\s+",
        " ",
        str(value).strip()
    ).lower()


def tokenize(value: str) -> set:
    value = normalize(value)

    value = re.sub(
        r"[^a-z0-9\s_-]",
        " ",
        value
    )

    return {
        token
        for token in re.split(r"[\s_-]+", value)
        if token
    }


def semantic_target(target: str) -> str:
    value = normalize(target)

    dynamic_patterns = [
        r",?\s*empty$",
        r",?\s*with\s+\d+\s+items?$",
        r"\s*\(\d+\)$",
        r",?\s*\d+\s+items?$",
        r"\s+\d+$",
    ]

    for pattern in dynamic_patterns:
        value = re.sub(
            pattern,
            "",
            value,
            flags=re.IGNORECASE
        ).strip()

    return value


# ============================================================
# SIMILARITY
# ============================================================

def token_similarity(a: str, b: str) -> float:
    a_tokens = tokenize(a)
    b_tokens = tokenize(b)

    if not a_tokens or not b_tokens:
        return 0.0

    intersection = len(a_tokens & b_tokens)
    union = len(a_tokens | b_tokens)

    if union == 0:
        return 0.0

    return intersection / union


def string_similarity(a: str, b: str) -> float:
    a = normalize(a)
    b = normalize(b)

    if not a or not b:
        return 0.0

    if a == b:
        return 1.0

    if a in b or b in a:
        return 0.85

    return token_similarity(a, b)


# ============================================================
# DOM EXTRACTION
# ============================================================

async def extract_candidates(page: Page) -> List[Candidate]:
    raw_elements = await page.locator(
        """
        button,
        a,
        input,
        select,
        textarea,
        [role="button"],
        [role="link"],
        [role="checkbox"],
        [role="radio"],
        [role="textbox"],
        [data-test],
        [data-testid]
        """
    ).evaluate_all(
        """
        elements => elements.map(el => {
            const style = window.getComputedStyle(el);

            const rect = el.getBoundingClientRect();

            const visible =
                style.display !== 'none' &&
                style.visibility !== 'hidden' &&
                rect.width > 0 &&
                rect.height > 0;

            return {
                tag: el.tagName.toLowerCase(),
                text: (el.innerText || el.value || '').trim(),
                id: el.id || '',
                name: el.getAttribute('name') || '',
                ariaLabel: el.getAttribute('aria-label') || '',
                placeholder: el.getAttribute('placeholder') || '',
                dataTest: el.getAttribute('data-test') || '',
                dataTestId: el.getAttribute('data-testid') || '',
                role: el.getAttribute('role') || '',
                type: el.getAttribute('type') || '',
                visible
            };
        })
        """
    )

    candidates = []

    for item in raw_elements:
        candidates.append(
            Candidate(
                tag=item.get("tag", ""),
                text=item.get("text", ""),
                element_id=item.get("id", ""),
                name=item.get("name", ""),
                aria_label=item.get("ariaLabel", ""),
                placeholder=item.get("placeholder", ""),
                data_test=item.get("dataTest", ""),
                data_testid=item.get("dataTestId", ""),
                role=item.get("role", ""),
                input_type=item.get("type", ""),
                visible=item.get("visible", False),
            )
        )

    return candidates


# ============================================================
# CANDIDATE SCORING
# ============================================================

def score_candidate(
    target: str,
    candidate: Candidate,
    action: str
) -> Tuple[float, str]:

    original = normalize(target)
    semantic = semantic_target(target)

    scores: List[Tuple[float, str]] = []

    fields = {
        "data-test": candidate.data_test,
        "data-testid": candidate.data_testid,
        "id": candidate.element_id,
        "name": candidate.name,
        "aria-label": candidate.aria_label,
        "placeholder": candidate.placeholder,
        "text": candidate.text,
    }

    weights = {
        "data-test": 1.00,
        "data-testid": 1.00,
        "id": 0.95,
        "name": 0.90,
        "aria-label": 0.95,
        "placeholder": 0.85,
        "text": 0.80,
    }

    for field_name, field_value in fields.items():
        if not field_value:
            continue

        direct_score = string_similarity(
            original,
            field_value
        )

        semantic_score = string_similarity(
            semantic,
            field_value
        )

        similarity = max(
            direct_score,
            semantic_score
        )

        weighted_score = (
            similarity *
            weights[field_name]
        )

        scores.append(
            (
                weighted_score,
                field_name
            )
        )

    if not scores:
        return 0.0, "none"

    best_score, best_field = max(
        scores,
        key=lambda x: x[0]
    )

    # --------------------------------------------------------
    # ACTION-AWARE BOOSTING
    # --------------------------------------------------------

    if action == "click":
        if candidate.tag in ["button", "a"]:
            best_score += 0.05

        if candidate.role in ["button", "link"]:
            best_score += 0.05

        if candidate.input_type in [
            "button",
            "submit"
        ]:
            best_score += 0.05

    elif action == "fill":
        if candidate.tag in [
            "input",
            "textarea"
        ]:
            best_score += 0.08

    elif action == "select":
        if candidate.tag == "select":
            best_score += 0.10

    elif action in [
        "check",
        "uncheck"
    ]:
        if candidate.input_type == "checkbox":
            best_score += 0.10

    if candidate.visible:
        best_score += 0.03
    else:
        best_score -= 0.20

    best_score = min(
        max(best_score, 0.0),
        1.0
    )

    return best_score, best_field


# ============================================================
# BUILD LOCATOR
# ============================================================

def locator_from_candidate(
    page: Page,
    candidate: Candidate,
    matched_field: str
) -> Tuple[Optional[Locator], str]:

    if matched_field == "data-test" and candidate.data_test:
        return (
            page.locator(
                f'[data-test="{candidate.data_test}"]'
            ),
            f'data-test={candidate.data_test}'
        )

    if matched_field == "data-testid" and candidate.data_testid:
        return (
            page.locator(
                f'[data-testid="{candidate.data_testid}"]'
            ),
            f'data-testid={candidate.data_testid}'
        )

    if matched_field == "id" and candidate.element_id:
        return (
            page.locator(
                f'#{candidate.element_id}'
            ),
            f'id={candidate.element_id}'
        )

    if matched_field == "name" and candidate.name:
        return (
            page.locator(
                f'[name="{candidate.name}"]'
            ),
            f'name={candidate.name}'
        )

    if matched_field == "aria-label" and candidate.aria_label:
        return (
            page.get_by_label(
                candidate.aria_label,
                exact=True
            ),
            f'aria-label={candidate.aria_label}'
        )

    if matched_field == "placeholder" and candidate.placeholder:
        return (
            page.get_by_placeholder(
                candidate.placeholder,
                exact=True
            ),
            f'placeholder={candidate.placeholder}'
        )

    if matched_field == "text" and candidate.text:
        if candidate.role == "button" or candidate.tag == "button":
            return (
                page.get_by_role(
                    "button",
                    name=candidate.text,
                    exact=True
                ),
                f'button-text={candidate.text}'
            )

        if candidate.role == "link" or candidate.tag == "a":
            return (
                page.get_by_role(
                    "link",
                    name=candidate.text,
                    exact=True
                ),
                f'link-text={candidate.text}'
            )

        return (
            page.get_by_text(
                candidate.text,
                exact=True
            ),
            f'text={candidate.text}'
        )

    return None, "unknown"


# ============================================================
# SELF HEAL
# ============================================================

async def heal_locator(
    page: Page,
    target: str,
    action: str,
    minimum_confidence: float = 0.60
) -> HealingResult:

    print()
    print("    SELF-HEALING ACTIVATED")
    print(f"    Original target : {target}")
    print(f"    Action          : {action}")

    candidates = await extract_candidates(page)

    scored_candidates = []

    for candidate in candidates:
        score, field = score_candidate(
            target,
            candidate,
            action
        )

        scored_candidates.append(
            (
                score,
                field,
                candidate
            )
        )

    scored_candidates.sort(
        key=lambda x: x[0],
        reverse=True
    )

    if not scored_candidates:
        return HealingResult(
            success=False,
            original_target=target,
            healed_target="",
            strategy="none",
            confidence=0.0,
            reason="No interactive DOM candidates found.",
        )

    best_score, matched_field, best_candidate = (
        scored_candidates[0]
    )

    print(
        f"    Best confidence : "
        f"{best_score:.2f}"
    )

    print(
        f"    Matched field   : "
        f"{matched_field}"
    )

    if best_score < minimum_confidence:
        return HealingResult(
            success=False,
            original_target=target,
            healed_target="",
            strategy=matched_field,
            confidence=best_score,
            reason=(
                "Best candidate was below the "
                "minimum confidence threshold."
            ),
        )

    locator, healed_target = locator_from_candidate(
        page,
        best_candidate,
        matched_field
    )

    if locator is None:
        return HealingResult(
            success=False,
            original_target=target,
            healed_target="",
            strategy=matched_field,
            confidence=best_score,
            reason="Could not construct locator from candidate.",
        )

    try:
        count = await locator.count()

        if count == 0:
            return HealingResult(
                success=False,
                original_target=target,
                healed_target=healed_target,
                strategy=matched_field,
                confidence=best_score,
                reason="Generated locator matched zero elements.",
            )

        if count > 1:
            locator = locator.first

        if not await locator.is_visible():
            return HealingResult(
                success=False,
                original_target=target,
                healed_target=healed_target,
                strategy=matched_field,
                confidence=best_score,
                reason="Generated locator is not visible.",
            )

    except Exception as exc:
        return HealingResult(
            success=False,
            original_target=target,
            healed_target=healed_target,
            strategy=matched_field,
            confidence=best_score,
            reason=f"Locator validation failed: {exc}",
        )

    print(
        f"    Healed target   : "
        f"{healed_target}"
    )

    print(
        f"    Strategy        : "
        f"{matched_field}"
    )

    return HealingResult(
        success=True,
        original_target=target,
        healed_target=healed_target,
        strategy=matched_field,
        confidence=best_score,
        reason="Equivalent visible DOM element found.",
        locator=locator,
    )


# ============================================================
# REPORTING
# ============================================================

def load_existing_report() -> Dict[str, Any]:
    if not HEALING_REPORT_FILE.exists():
        return {
            "total_healing_attempts": 0,
            "successful_heals": 0,
            "failed_heals": 0,
            "heals": [],
        }

    try:
        with open(
            HEALING_REPORT_FILE,
            "r",
            encoding="utf-8"
        ) as file:
            return json.load(file)

    except Exception:
        return {
            "total_healing_attempts": 0,
            "successful_heals": 0,
            "failed_heals": 0,
            "heals": [],
        }


def record_healing(
    result: HealingResult,
    journey_title: str = "",
    step_number: int = 0,
    action: str = "",
):
    report = load_existing_report()

    report["total_healing_attempts"] += 1

    if result.success:
        report["successful_heals"] += 1
    else:
        report["failed_heals"] += 1

    report["heals"].append(
        {
            "journey": journey_title,
            "step": step_number,
            "action": action,
            "original_target": result.original_target,
            "healed_target": result.healed_target,
            "strategy": result.strategy,
            "confidence": round(
                result.confidence,
                3
            ),
            "success": result.success,
            "reason": result.reason,
        }
    )

    HEALING_REPORT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with open(
        HEALING_REPORT_FILE,
        "w",
        encoding="utf-8"
    ) as file:
        json.dump(
            report,
            file,
            indent=2,
            ensure_ascii=False
        )