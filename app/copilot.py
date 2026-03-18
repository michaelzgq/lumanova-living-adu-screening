from __future__ import annotations

from dataclasses import dataclass, field

from .models import LeadRecord


@dataclass
class CopilotBrief:
    headline: str
    internal_priority: str
    lead_score: int
    lead_temperature: str
    recommended_owner: str
    lead_summary: str
    score_reasons: list[str] = field(default_factory=list)
    call_objectives: list[str] = field(default_factory=list)
    missing_information: list[str] = field(default_factory=list)
    document_requests: list[str] = field(default_factory=list)
    crm_handoff_note: str = ""
    outreach_draft: str = ""


def _yes(value: str) -> bool:
    return str(value or "").strip().casefold() == "yes"


def _not_sure(value: str) -> bool:
    return str(value or "").strip().casefold() == "not sure"


def _project_phrase(project_type: str) -> str:
    mapping = {
        "detached_adu": "a new detached ADU",
        "garage_conversion": "a garage conversion",
        "jadu": "a JADU-style conversion",
        "unpermitted_unit": "a legalization or rescue case",
        "unknown": "an unclear residential expansion case",
    }
    return mapping.get(project_type, "a residential expansion case")


def _structure_phrase(structure_type: str) -> str:
    mapping = {
        "detached_garage": "detached garage",
        "attached_garage": "attached garage",
        "existing_unit": "existing living unit",
        "house_interior_space": "interior house space",
        "not_sure": "unclear structure type",
    }
    return mapping.get(structure_type, "unclear structure type")


def _internal_priority(lead: LeadRecord) -> str:
    if lead.result.recommended_path == "B" or lead.result.risk_tier == "Red":
        return "High priority senior review"
    if lead.result.recommended_path == "C" or lead.result.risk_tier in {"Yellow", "Orange"}:
        return "Review before standard sales follow-up"
    return "Standard response window"


def _recommended_owner(lead: LeadRecord) -> str:
    if lead.result.recommended_path == "B" or lead.result.risk_tier == "Red":
        return "Senior reviewer / rescue specialist"
    if lead.result.recommended_path == "C" or lead.result.risk_tier in {"Yellow", "Orange"}:
        return "Reviewer first, then sales follow-up"
    return "Standard sales follow-up"


def _lead_score(lead: LeadRecord) -> tuple[int, list[str]]:
    answers = lead.answers
    score = 50
    reasons: list[str] = []

    if answers.owner_on_title == "Yes":
        score += 15
        reasons.append("Owner confirmed on title")
    else:
        score -= 12
        reasons.append("Ownership or decision-maker status still unclear")

    if answers.email or answers.phone or answers.wechat_id:
        score += 8
        reasons.append("At least one direct contact method is available")

    if answers.best_contact_time:
        score += 5
        reasons.append("Preferred follow-up timing is available")

    if lead.result.recommended_path == "A":
        score += 12
        reasons.append("Looks closer to a standard path")
    elif lead.result.recommended_path == "C":
        score -= 8
        reasons.append("Blocker diagnosis likely needed before standard sales follow-up")
    else:
        score -= 18
        reasons.append("Looks more like a rescue or legalization case")

    risk_adjustment = {
        "Green": 10,
        "Yellow": -2,
        "Orange": -10,
        "Red": -20,
    }
    score += risk_adjustment.get(lead.result.risk_tier, 0)
    if lead.result.risk_tier in {"Orange", "Red"}:
        reasons.append(f"Current risk tier is {lead.result.risk_tier.lower()}")

    if _yes(answers.prior_violation):
        score -= 10
        reasons.append("Prior violation or code-enforcement history exists")
    if _yes(answers.unpermitted_work) or _yes(answers.addition_without_permit):
        score -= 8
        reasons.append("Known unpermitted work may slow down conversion")
    if answers.jurisdiction == "unknown":
        score -= 6
        reasons.append("Jurisdiction is still not confirmed")

    bounded = max(0, min(100, score))
    return bounded, reasons


def _lead_temperature(score: int) -> str:
    if score >= 75:
        return "Hot"
    if score >= 50:
        return "Warm"
    return "Cold"


def _build_missing_information(lead: LeadRecord) -> list[str]:
    answers = lead.answers
    missing: list[str] = []
    if answers.owner_on_title != "Yes":
        missing.append("Confirm whether the person submitting is the actual owner or decision-maker.")
    if answers.jurisdiction == "unknown":
        missing.append("Confirm the governing city / county path before promising any next step.")
    if _not_sure(answers.hillside):
        missing.append("Clarify whether the site has hillside or special slope conditions.")
    if _not_sure(answers.basement):
        missing.append("Clarify whether any intended living area is below grade or in a basement.")
    if _not_sure(answers.addition_without_permit):
        missing.append("Confirm whether there are old additions that may not have permits.")
    if _not_sure(answers.unpermitted_work):
        missing.append("Confirm whether there is any existing unpermitted work on site.")
    if _not_sure(answers.prior_violation):
        missing.append("Ask whether the owner has received any correction, violation, or code-enforcement notice.")
    if _not_sure(answers.prior_plans):
        missing.append("Ask whether there are old plans, plan-check comments, or prior permit numbers.")
    if not answers.best_contact_time:
        missing.append("Ask when the owner is easiest to reach for a real follow-up.")
    return missing


def _build_document_requests(lead: LeadRecord) -> list[str]:
    answers = lead.answers
    requests = ["Property address confirmation and any prior permit numbers if available."]
    if lead.result.recommended_path in {"C", "B"}:
        requests.append("Any old plan set, correction comments, or city correspondence.")
    if _yes(answers.prior_violation):
        requests.append("Copy of any correction notice, violation letter, or code-enforcement paperwork.")
    if _yes(answers.prior_plans):
        requests.append("Prior plan-check comments, permit history, or stamped sheets already on hand.")
    if _yes(answers.unpermitted_work) or _yes(answers.addition_without_permit):
        requests.append("Photos of the existing structure and any known dates of past work.")
    if answers.project_type == "garage_conversion":
        requests.append("Photos showing whether the garage is attached or detached and its current condition.")
    return requests


def _build_call_objectives(lead: LeadRecord) -> list[str]:
    answers = lead.answers
    objectives = [
        "Confirm the owner's actual goal, timeline, and whether the project is still active.",
        "Verify ownership or decision-making authority before deeper review time is spent.",
    ]
    if lead.result.recommended_path == "A":
        objectives.extend(
            [
                "Verify the property address and whether the owner is looking for a straightforward screening only.",
                "Position the next step as a property record and path review before design spend.",
            ]
        )
    elif lead.result.recommended_path == "C":
        objectives.extend(
            [
                "Identify which blocker is real versus still uncertain.",
                "Set expectation that records and permit history may need review before anyone quotes a path.",
            ]
        )
    else:
        objectives.extend(
            [
                "Separate legalization questions from any new-construction idea the owner may have.",
                "Set expectation that this likely needs deeper review before discussing a clean fast-track path.",
            ]
        )
    if answers.contact_preference == "WeChat":
        objectives.append("Use a short, direct WeChat follow-up instead of a long call-first approach if possible.")
    return objectives


def _build_outreach_draft(lead: LeadRecord, brief: CopilotBrief) -> str:
    answers = lead.answers
    name = answers.full_name or "there"
    project_phrase = _project_phrase(answers.project_type)
    route_phrase = {
        "A": "a relatively standard path review",
        "C": "a blocker-review case",
        "B": "a rescue / legalization review",
    }.get(lead.result.recommended_path, "a manual review case")

    return (
        f"Hi {name}, thanks for submitting your property details. "
        f"We reviewed your intake and it currently looks closer to {route_phrase} for {project_phrase}. "
        f"Before anyone promises a path, we should confirm the address, records, and any existing issues on site. "
        f"If you're still actively exploring this project, reply with any old plans, notices, or permit information you already have, "
        f"and we can tell you what should be reviewed next."
    )


def _build_crm_handoff_note(lead: LeadRecord, brief: CopilotBrief) -> str:
    return (
        f"{brief.lead_temperature} lead ({brief.lead_score}/100). "
        f"Route: {lead.result.recommended_path}. "
        f"Risk: {lead.result.risk_tier}. "
        f"Owner: {lead.answers.owner_on_title or 'unknown'}. "
        f"Recommended owner: {brief.recommended_owner}. "
        f"Next action: {lead.next_action or 'Review manually.'}"
    )


def generate_copilot_brief(lead: LeadRecord) -> CopilotBrief:
    answers = lead.answers
    project_phrase = _project_phrase(answers.project_type)
    structure_phrase = _structure_phrase(answers.structure_type)
    route_phrase = {
        "A": "standard path",
        "C": "blocker diagnosis path",
        "B": "rescue / legalization path",
    }.get(lead.result.recommended_path, "manual review path")
    lead_summary = (
        f"This lead looks like {project_phrase} tied to a {structure_phrase}. "
        f"The current screen routed it into the {route_phrase} with {lead.result.risk_tier.lower()} risk."
    )
    lead_score, score_reasons = _lead_score(lead)

    brief = CopilotBrief(
        headline="AI Copilot draft",
        internal_priority=_internal_priority(lead),
        lead_score=lead_score,
        lead_temperature=_lead_temperature(lead_score),
        recommended_owner=_recommended_owner(lead),
        lead_summary=lead_summary,
        score_reasons=score_reasons,
    )
    brief.call_objectives = _build_call_objectives(lead)
    brief.missing_information = _build_missing_information(lead)
    brief.document_requests = _build_document_requests(lead)
    brief.outreach_draft = _build_outreach_draft(lead, brief)
    brief.crm_handoff_note = _build_crm_handoff_note(lead, brief)
    return brief
