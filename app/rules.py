from __future__ import annotations

from typing import Iterable

from .models import ScreeningAnswers, ScreeningResult


JURISDICTION_LABELS = {
    "city_of_los_angeles": "City of Los Angeles (LADBS / LA City Planning / LAHD)",
    "unincorporated_la_county": "Unincorporated LA County (EPIC-LA / district offices)",
    "contract_city": "Contract City served through LA County systems",
    "pasadena": "Pasadena",
    "arcadia": "Arcadia",
    "monterey_park": "Monterey Park",
    "sgv_other": "Other SGV city / manual confirmation needed",
    "unknown": "Unknown jurisdiction - manual review needed",
}


PROJECT_LABELS = {
    "detached_adu": "New detached ADU path",
    "garage_conversion": "Existing garage conversion path",
    "jadu": "JADU path",
    "unpermitted_unit": "Unpermitted unit rescue / legalization path",
    "unknown": "Project type needs manual clarification",
}


STRUCTURE_LABELS = {
    "detached_garage": "Detached garage",
    "attached_garage": "Attached garage",
    "existing_unit": "Existing living unit",
    "house_interior_space": "Interior house space",
    "not_sure": "Not sure yet",
}


KEYWORD_GROUPS = {
    "garage_conversion": ("garage", "convert garage", "garage conversion"),
    "detached_adu": ("new adu", "detached adu", "build adu", "backyard unit"),
    "jadu": ("jadu", "junior adu"),
    "unpermitted_unit": ("legalize", "unpermitted", "violation", "citation", "without permit"),
    "hillside": ("hillside", "slope"),
    "basement": ("basement", "below grade"),
    "rent": ("rent", "rental", "tenant", "cash flow"),
    "permit_blocker": ("correction", "plan check", "permit approval", "blocked"),
}


BLOCKER_MESSAGES = {
    "owner_not_ready": "Lead is not confirmed as the owner on title, so decision-making authority is unclear.",
    "hillside": "Hillside or special slope review usually removes a project from the simplest standard path.",
    "basement": "Below-grade or basement living space is not a standard garage-conversion case.",
    "addition_without_permit": "Unpermitted additions usually complicate fast-track review and records alignment.",
    "unpermitted_work": "Existing unpermitted work typically requires deeper records review before any standard path can be trusted.",
    "prior_violation": "Prior correction notices, violations, or code enforcement materially raise risk and handling time.",
    "prior_plans": "Existing plan sets or correction notices indicate this is already in a blocker-diagnosis scenario.",
    "jurisdiction_unknown": "The governing city / county path is not confirmed yet, so routing is incomplete.",
}


def yes(value: str) -> bool:
    return (value or "").strip().casefold() == "yes"


def extract_keywords(*values: str) -> list[str]:
    haystack = " ".join(str(value or "") for value in values).casefold()
    keywords: list[str] = []
    for tag, phrases in KEYWORD_GROUPS.items():
        if any(phrase in haystack for phrase in phrases):
            keywords.append(tag)
    return keywords


def suggest_jurisdiction(address: str) -> str:
    normalized = (address or "").casefold()
    for phrase, key in (
        ("city of los angeles", "city_of_los_angeles"),
        ("los angeles", "city_of_los_angeles"),
        ("pasadena", "pasadena"),
        ("arcadia", "arcadia"),
        ("monterey park", "monterey_park"),
        ("alhambra", "sgv_other"),
        ("san gabriel", "sgv_other"),
        ("rosemead", "sgv_other"),
        ("temple city", "sgv_other"),
        ("south pasadena", "sgv_other"),
        ("el monte", "sgv_other"),
    ):
        if phrase in normalized:
            return key
    return "unknown"


def suggest_project_type(brief_goal: str) -> str:
    lowered = (brief_goal or "").casefold()
    if any(term in lowered for term in ("legalize", "unpermitted", "violation", "citation", "without permit")):
        return "unpermitted_unit"
    if "jadu" in lowered or "junior adu" in lowered:
        return "jadu"
    if "garage" in lowered:
        return "garage_conversion"
    if "adu" in lowered:
        return "detached_adu"
    return "unknown"


def label_for(mapping: dict[str, str], key: str, fallback: str = "Needs manual review") -> str:
    return mapping.get(key, fallback)


def unique(items: Iterable[str]) -> list[str]:
    seen: list[str] = []
    for item in items:
        if item and item not in seen:
            seen.append(item)
    return seen


def blocker_tags(answers: ScreeningAnswers, jurisdiction_key: str) -> list[str]:
    tags: list[str] = []
    if answers.owner_on_title and not yes(answers.owner_on_title):
        tags.append("owner_not_ready")
    if yes(answers.hillside):
        tags.append("hillside")
    if yes(answers.basement):
        tags.append("basement")
    if yes(answers.addition_without_permit):
        tags.append("addition_without_permit")
    if yes(answers.unpermitted_work):
        tags.append("unpermitted_work")
    if yes(answers.prior_violation):
        tags.append("prior_violation")
    if yes(answers.prior_plans):
        tags.append("prior_plans")
    if jurisdiction_key == "unknown":
        tags.append("jurisdiction_unknown")
    return unique(tags)


def compute_screening(answers: ScreeningAnswers) -> ScreeningResult:
    jurisdiction_key = answers.jurisdiction or suggest_jurisdiction(answers.property_address)
    project_key = answers.project_type or suggest_project_type(answers.brief_goal)
    keywords = unique(extract_keywords(answers.brief_goal, answers.property_address))
    blockers = blocker_tags(answers, jurisdiction_key)
    blocker_labels = [BLOCKER_MESSAGES[tag] for tag in blockers]
    severe_blockers = sum(
        1
        for tag in blockers
        if tag in {"prior_violation", "unpermitted_work", "addition_without_permit", "basement", "hillside"}
    )

    route = "A"
    if project_key == "unpermitted_unit" or yes(answers.prior_violation):
        route = "B"
    elif blockers:
        route = "C"

    if route == "B" and not yes(answers.prior_violation) and severe_blockers == 0:
        route = "C"

    risk_tier = "Green"
    if blockers or jurisdiction_key == "unknown" or not yes(answers.owner_on_title):
        risk_tier = "Yellow"
    if severe_blockers >= 2 or yes(answers.prior_violation):
        risk_tier = "Orange"
    if route == "B" and (yes(answers.prior_violation) or severe_blockers >= 3):
        risk_tier = "Red"

    if route == "A":
        recommended_service = "Paid Property Record + Jurisdiction Screening ($295-$595)"
    elif route == "C":
        recommended_service = "Paid Screening + Blocker Diagnosis ($295-$595 to start)"
    else:
        recommended_service = "Deep Records Review / Rescue Strategy ($1,500+ depending on complexity)"

    rationale = [
        "This first version only gives a preliminary routing result, not a final permit or legal opinion.",
        "Routing is based on jurisdiction, project intent, and blocker signals collected during intake.",
    ]
    if jurisdiction_key != "unknown":
        rationale.append(f"Address intake routed the property to: {label_for(JURISDICTION_LABELS, jurisdiction_key)}.")
    else:
        rationale.append("Jurisdiction could not be confidently confirmed from the address alone.")

    project_label = label_for(PROJECT_LABELS, project_key)
    rationale.append(f"Project intent currently looks closest to: {project_label}.")

    if route == "A":
        rationale.append("This appears closest to a standard path, assuming records and existing conditions stay clean.")
        next_steps = [
            "Confirm jurisdiction and property record details.",
            "Check whether the project fits the intended standard path for that city or county.",
            "Move into paid screening before spending on design or construction.",
        ]
        summary = "This lead looks closest to a standard ADU / garage-conversion path, but still needs paid screening before design spend."
    elif route == "C":
        rationale.append("Existing blockers suggest this should be handled as a blocker-diagnosis case before anyone promises a standard path.")
        next_steps = [
            "Pull records and permit history.",
            "Map blocker items against the selected jurisdiction.",
            "Decide whether the project stays in a standard path or escalates into rescue review.",
        ]
        summary = "This lead likely needs blocker diagnosis first. The goal is to learn what is blocking approval before moving into design."
    else:
        rationale.append("The combination of project type and blocker signals points to a rescue / legalization workflow, not a simple standard path.")
        next_steps = [
            "Perform deep records review and existing-conditions triage.",
            "Separate legalization strategy from new-construction strategy.",
            "Avoid design or construction commitments until the rescue path is clarified.",
        ]
        summary = "This lead looks like a rescue or legalization case. It should be handled as a higher-friction strategy review, not as a standard intake."

    knowledge_ids = unique([jurisdiction_key, project_key, route] + blockers + keywords)

    return ScreeningResult(
        risk_tier=risk_tier,
        recommended_path=route,
        recommended_service=recommended_service,
        jurisdiction_label=label_for(JURISDICTION_LABELS, jurisdiction_key),
        project_label=project_label,
        extracted_keywords=keywords,
        blocker_labels=blocker_labels,
        blocker_tags=blockers,
        rationale=rationale,
        next_steps=next_steps,
        summary=summary,
        knowledge_ids=knowledge_ids,
    )

