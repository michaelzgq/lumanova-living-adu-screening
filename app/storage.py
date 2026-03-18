from __future__ import annotations

import csv
import json
from io import StringIO
from pathlib import Path

from .models import LeadRecord, ScreeningAnswers


def _normalized_email(value: str) -> str:
    return str(value or "").strip().casefold()


def _normalized_phone(value: str) -> str:
    return "".join(ch for ch in str(value or "") if ch.isdigit())


def _normalized_wechat(value: str) -> str:
    return str(value or "").strip().casefold()


def _normalized_address(value: str) -> str:
    return " ".join(str(value or "").strip().casefold().split())


class LeadRepository:
    def __init__(self, file_path: Path) -> None:
        self.file_path = Path(file_path)
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_file()

    def _ensure_file(self) -> None:
        if not self.file_path.exists():
            self.file_path.write_text(
                json.dumps({"version": 1, "leads": []}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

    def list_leads(self) -> list[LeadRecord]:
        self._ensure_file()
        payload = json.loads(self.file_path.read_text(encoding="utf-8"))
        return [LeadRecord.from_dict(item) for item in reversed(payload.get("leads", []))]

    def save_lead(self, lead: LeadRecord) -> None:
        self._ensure_file()
        payload = json.loads(self.file_path.read_text(encoding="utf-8"))
        payload.setdefault("leads", []).append(lead.to_dict())
        self.file_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def update_lead(self, lead: LeadRecord) -> None:
        self._ensure_file()
        payload = json.loads(self.file_path.read_text(encoding="utf-8"))
        leads = payload.setdefault("leads", [])
        for index, item in enumerate(leads):
            if item.get("id") == lead.id:
                leads[index] = lead.to_dict()
                break
        else:
            leads.append(lead.to_dict())
        self.file_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def delete_lead(self, lead_id: str) -> bool:
        self._ensure_file()
        payload = json.loads(self.file_path.read_text(encoding="utf-8"))
        leads = payload.setdefault("leads", [])
        original_count = len(leads)
        payload["leads"] = [item for item in leads if item.get("id") != lead_id]
        deleted = len(payload["leads"]) != original_count
        if deleted:
            self.file_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        return deleted

    def find_duplicate_lead(self, answers: ScreeningAnswers) -> LeadRecord | None:
        normalized_email = _normalized_email(answers.email)
        normalized_phone = _normalized_phone(answers.phone)
        normalized_wechat = _normalized_wechat(answers.wechat_id)
        normalized_address = _normalized_address(answers.property_address)

        for lead in self.list_leads():
            existing = lead.answers
            email_match = normalized_email and _normalized_email(existing.email) == normalized_email
            phone_match = normalized_phone and _normalized_phone(existing.phone) == normalized_phone
            wechat_match = normalized_wechat and _normalized_wechat(existing.wechat_id) == normalized_wechat
            address_match = normalized_address and _normalized_address(existing.property_address) == normalized_address

            if email_match or phone_match or wechat_match:
                return lead
            if address_match and (
                _normalized_email(existing.email) == normalized_email
                or _normalized_phone(existing.phone) == normalized_phone
                or _normalized_wechat(existing.wechat_id) == normalized_wechat
                or not normalized_email and not normalized_phone and not normalized_wechat
            ):
                return lead
        return None

    def export_csv(self) -> str:
        return export_leads_csv(self.list_leads())


def export_leads_csv(leads: list[LeadRecord]) -> str:
    if not leads:
        return ""

    rows = []
    for lead in leads:
        rows.append(
            {
                "lead_id": lead.id,
                "created_at": lead.created_at,
                "full_name": lead.answers.full_name,
                "email": lead.answers.email,
                "phone": lead.answers.phone,
                "wechat_id": lead.answers.wechat_id,
                "contact_preference": lead.answers.contact_preference,
                "best_contact_time": lead.answers.best_contact_time,
                "source_tag": lead.answers.source_tag,
                "utm_source": lead.answers.utm_source,
                "utm_medium": lead.answers.utm_medium,
                "utm_campaign": lead.answers.utm_campaign,
                "property_address": lead.answers.property_address,
                "jurisdiction": lead.result.jurisdiction_label,
                "project": lead.result.project_label,
                "path": lead.result.recommended_path,
                "risk_tier": lead.result.risk_tier,
                "stage": lead.stage,
                "disposition_reason": lead.disposition_reason,
                "assigned_to": lead.assigned_to,
                "next_action": lead.next_action,
                "external_sync_status": lead.external_sync_status,
                "external_sync_at": lead.external_sync_at,
                "recommended_service": lead.result.recommended_service,
                "summary": lead.result.summary,
            }
        )

    fieldnames = list(rows[0].keys())
    buffer = StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue()
