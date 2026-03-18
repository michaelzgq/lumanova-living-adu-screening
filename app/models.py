from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def parse_iso_datetime(value: str) -> datetime | None:
    raw_value = str(value or "").strip()
    if not raw_value:
        return None
    try:
        parsed = datetime.fromisoformat(raw_value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def clean_text(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def clean_block(value: Any) -> str:
    return str(value or "").strip()


@dataclass
class ScreeningAnswers:
    property_address: str = ""
    brief_goal: str = ""
    jurisdiction: str = ""
    owner_on_title: str = ""
    project_type: str = ""
    structure_type: str = ""
    hillside: str = ""
    basement: str = ""
    addition_without_permit: str = ""
    unpermitted_work: str = ""
    prior_violation: str = ""
    prior_plans: str = ""
    separate_utility_request: str = ""
    full_name: str = ""
    email: str = ""
    phone: str = ""
    wechat_id: str = ""
    contact_preference: str = ""
    best_contact_time: str = ""
    consent_to_contact: str = ""
    source_tag: str = ""
    utm_source: str = ""
    utm_medium: str = ""
    utm_campaign: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ScreeningAnswers":
        return cls(
            property_address=clean_block(data.get("property_address")),
            brief_goal=clean_block(data.get("brief_goal")),
            jurisdiction=clean_text(data.get("jurisdiction")),
            owner_on_title=clean_text(data.get("owner_on_title")),
            project_type=clean_text(data.get("project_type")),
            structure_type=clean_text(data.get("structure_type")),
            hillside=clean_text(data.get("hillside")),
            basement=clean_text(data.get("basement")),
            addition_without_permit=clean_text(data.get("addition_without_permit")),
            unpermitted_work=clean_text(data.get("unpermitted_work")),
            prior_violation=clean_text(data.get("prior_violation")),
            prior_plans=clean_text(data.get("prior_plans")),
            separate_utility_request=clean_text(data.get("separate_utility_request")),
            full_name=clean_text(data.get("full_name")),
            email=clean_text(data.get("email")),
            phone=clean_text(data.get("phone")),
            wechat_id=clean_text(data.get("wechat_id")),
            contact_preference=clean_text(data.get("contact_preference")),
            best_contact_time=clean_block(data.get("best_contact_time")),
            consent_to_contact=clean_text(data.get("consent_to_contact")),
            source_tag=clean_text(data.get("source_tag")),
            utm_source=clean_text(data.get("utm_source")),
            utm_medium=clean_text(data.get("utm_medium")),
            utm_campaign=clean_text(data.get("utm_campaign")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "property_address": self.property_address,
            "brief_goal": self.brief_goal,
            "jurisdiction": self.jurisdiction,
            "owner_on_title": self.owner_on_title,
            "project_type": self.project_type,
            "structure_type": self.structure_type,
            "hillside": self.hillside,
            "basement": self.basement,
            "addition_without_permit": self.addition_without_permit,
            "unpermitted_work": self.unpermitted_work,
            "prior_violation": self.prior_violation,
            "prior_plans": self.prior_plans,
            "separate_utility_request": self.separate_utility_request,
            "full_name": self.full_name,
            "email": self.email,
            "phone": self.phone,
            "wechat_id": self.wechat_id,
            "contact_preference": self.contact_preference,
            "best_contact_time": self.best_contact_time,
            "consent_to_contact": self.consent_to_contact,
            "source_tag": self.source_tag,
            "utm_source": self.utm_source,
            "utm_medium": self.utm_medium,
            "utm_campaign": self.utm_campaign,
        }


@dataclass
class ScreeningResult:
    risk_tier: str
    recommended_path: str
    recommended_service: str
    jurisdiction_label: str
    project_label: str
    extracted_keywords: list[str] = field(default_factory=list)
    blocker_labels: list[str] = field(default_factory=list)
    blocker_tags: list[str] = field(default_factory=list)
    rationale: list[str] = field(default_factory=list)
    next_steps: list[str] = field(default_factory=list)
    summary: str = ""
    knowledge_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "risk_tier": self.risk_tier,
            "recommended_path": self.recommended_path,
            "recommended_service": self.recommended_service,
            "jurisdiction_label": self.jurisdiction_label,
            "project_label": self.project_label,
            "extracted_keywords": self.extracted_keywords,
            "blocker_labels": self.blocker_labels,
            "blocker_tags": self.blocker_tags,
            "rationale": self.rationale,
            "next_steps": self.next_steps,
            "summary": self.summary,
            "knowledge_ids": self.knowledge_ids,
        }


@dataclass
class LeadRecord:
    id: str
    created_at: str
    answers: ScreeningAnswers
    result: ScreeningResult
    stage: str = "new"
    assigned_to: str = ""
    next_action: str = ""
    internal_notes: str = ""
    disposition_reason: str = ""
    last_updated_at: str = ""
    external_sync_status: str = "local_only"
    external_sync_at: str = ""
    external_sync_error: str = ""

    @classmethod
    def create(cls, answers: ScreeningAnswers, result: ScreeningResult) -> "LeadRecord":
        created_at = utc_now_iso()
        initial_stage = initial_stage_for_lead(answers, result)
        return cls(
            id=str(uuid4()),
            created_at=created_at,
            answers=answers,
            result=result,
            stage=initial_stage,
            next_action=suggested_next_action_for_lead(answers, result, initial_stage),
            last_updated_at=created_at,
            external_sync_status="local_only",
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LeadRecord":
        return cls(
            id=clean_text(data.get("id")),
            created_at=clean_text(data.get("created_at")),
            answers=ScreeningAnswers.from_dict(data.get("answers", {})),
            result=ScreeningResult(**data.get("result", {})),
            stage=clean_text(data.get("stage")) or "new",
            assigned_to=clean_text(data.get("assigned_to")),
            next_action=clean_block(data.get("next_action")),
            internal_notes=clean_block(data.get("internal_notes")),
            disposition_reason=clean_text(data.get("disposition_reason")),
            last_updated_at=clean_text(data.get("last_updated_at")) or clean_text(data.get("created_at")),
            external_sync_status=clean_text(data.get("external_sync_status")) or "local_only",
            external_sync_at=clean_text(data.get("external_sync_at")),
            external_sync_error=clean_block(data.get("external_sync_error")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "created_at": self.created_at,
            "answers": self.answers.to_dict(),
            "result": self.result.to_dict(),
            "stage": self.stage,
            "assigned_to": self.assigned_to,
            "next_action": self.next_action,
            "internal_notes": self.internal_notes,
            "disposition_reason": self.disposition_reason,
            "last_updated_at": self.last_updated_at or self.created_at,
            "external_sync_status": self.external_sync_status or "local_only",
            "external_sync_at": self.external_sync_at,
            "external_sync_error": self.external_sync_error,
        }


def initial_stage_for_lead(answers: ScreeningAnswers, result: ScreeningResult) -> str:
    blocker_tags = set(result.blocker_tags)
    if result.recommended_path in {"B", "C"}:
        return "needs_review"
    if result.risk_tier in {"Yellow", "Orange", "Red"}:
        return "needs_review"
    if "owner_not_ready" in blocker_tags or "jurisdiction_unknown" in blocker_tags:
        return "needs_review"
    if answers.owner_on_title and answers.owner_on_title != "Yes":
        return "needs_review"
    return "new"


def suggested_next_action_for_lead(answers: ScreeningAnswers, result: ScreeningResult, stage: str) -> str:
    if stage == "needs_review":
        if result.recommended_path == "B":
            return "Senior review first. Check records, violations, and existing conditions before calling."
        if result.recommended_path == "C":
            return "Review blockers and permit history, then decide whether to call or request more documents."
        return "Review intake details and confirm whether the lead is ready for first contact."
    if answers.owner_on_title and answers.owner_on_title != "Yes":
        return "Confirm owner authority or decision-maker status before investing more review time."
    return "Make first contact within 24 hours and confirm project intent, ownership, and timeline."


def backfill_lead_defaults(lead: LeadRecord) -> bool:
    changed = False
    suggested_stage = initial_stage_for_lead(lead.answers, lead.result)
    if lead.stage == "new" and suggested_stage == "needs_review":
        lead.stage = suggested_stage
        changed = True
    if not lead.next_action.strip():
        lead.next_action = suggested_next_action_for_lead(lead.answers, lead.result, lead.stage)
        changed = True
    if not lead.last_updated_at.strip():
        lead.last_updated_at = lead.created_at
        changed = True
    return changed


def lead_needs_attention(lead: LeadRecord, hours: int = 24) -> bool:
    if lead.stage not in {"new", "needs_review", "contacted"}:
        return False
    reference_time = parse_iso_datetime(lead.last_updated_at or lead.created_at)
    if reference_time is None:
        return True
    return datetime.now(timezone.utc) - reference_time >= timedelta(hours=hours)


def lead_priority_key(lead: LeadRecord) -> tuple[int, int, str]:
    stage_rank = {
        "needs_review": 0,
        "new": 1,
        "contacted": 2,
        "qualified": 3,
        "screening_booked": 4,
        "proposal_sent": 5,
        "nurture": 6,
        "closed_won": 7,
        "closed_lost": 8,
        "archived": 9,
    }
    risk_rank = {
        "Red": 0,
        "Orange": 1,
        "Yellow": 2,
        "Green": 3,
    }
    reference_time = lead.last_updated_at or lead.created_at or ""
    return (
        stage_rank.get(lead.stage, 99),
        risk_rank.get(lead.result.risk_tier, 99),
        reference_time,
    )
