from __future__ import annotations

import json
from typing import Any
from urllib import error, parse, request

from .config import get_setting
from .models import LeadRecord, parse_iso_datetime


def remote_lead_source_configured() -> bool:
    return bool(get_setting("ADU_LEAD_WEBHOOK_URL", ""))


def _build_remote_list_url(limit: int = 200) -> str:
    base_url = get_setting("ADU_LEAD_WEBHOOK_URL", "")
    if not base_url:
        return ""
    parsed = parse.urlparse(base_url)
    query = parse.parse_qs(parsed.query, keep_blank_values=True)
    query["action"] = ["list"]
    query["limit"] = [str(limit)]
    rebuilt = parsed._replace(query=parse.urlencode(query, doseq=True))
    return parse.urlunparse(rebuilt)


def fetch_remote_leads(limit: int = 200) -> tuple[list[LeadRecord], str]:
    url = _build_remote_list_url(limit)
    if not url:
        return [], "remote_not_configured"

    timeout_seconds = float(get_setting("ADU_LEAD_WEBHOOK_TIMEOUT_SECONDS", "8") or "8")
    req = request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "lumanova-living-adu-screening/1.0",
        },
        method="GET",
    )
    try:
        with request.urlopen(req, timeout=timeout_seconds) as response:
            body = response.read().decode("utf-8", errors="ignore")
    except error.HTTPError as exc:
        return [], f"remote_http_{exc.code}"
    except Exception as exc:  # noqa: BLE001
        return [], f"remote_error:{exc}"

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return [], "remote_invalid_json"

    lead_items = payload.get("leads", [])
    if not isinstance(lead_items, list):
        return [], "remote_invalid_shape"

    parsed_leads: list[LeadRecord] = []
    for item in lead_items:
        if not isinstance(item, dict):
            continue
        try:
            lead = LeadRecord.from_dict(item)
        except Exception:  # noqa: BLE001
            continue
        if not lead.external_sync_status:
            lead.external_sync_status = "synced"
        parsed_leads.append(lead)
    return parsed_leads, ""


def merge_local_and_remote_leads(local_leads: list[LeadRecord], remote_leads: list[LeadRecord]) -> list[LeadRecord]:
    merged: dict[str, LeadRecord] = {}

    for lead in local_leads:
        merged[lead.id] = lead

    for lead in remote_leads:
        existing = merged.get(lead.id)
        if existing is None:
            merged[lead.id] = lead
            continue

        existing_dt = parse_iso_datetime(existing.last_updated_at or existing.created_at or "")
        remote_dt = parse_iso_datetime(lead.last_updated_at or lead.created_at or "")
        if existing_dt is None and remote_dt is not None:
            merged[lead.id] = lead
            continue
        if existing_dt is not None and remote_dt is not None and remote_dt >= existing_dt:
            merged[lead.id] = lead

    return sorted(
        merged.values(),
        key=lambda lead: parse_iso_datetime(lead.created_at or "") or parse_iso_datetime("1970-01-01T00:00:00+00:00"),
        reverse=True,
    )
