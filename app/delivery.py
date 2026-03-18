from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib import error, request

from .config import get_setting
from .models import LeadRecord, utc_now_iso


@dataclass
class DeliveryResult:
    configured: bool
    success: bool
    status_code: int | None = None
    message: str = ""
    attempted_at: str = ""


def webhook_configured() -> bool:
    return bool(get_setting("ADU_LEAD_WEBHOOK_URL", ""))


def webhook_target_label() -> str:
    url = get_setting("ADU_LEAD_WEBHOOK_URL", "")
    if not url:
        return "Not configured"
    return url


def _build_headers() -> dict[str, str]:
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "lumanova-living-adu-screening/1.0",
    }
    bearer_token = get_setting("ADU_LEAD_WEBHOOK_BEARER_TOKEN", "")
    if bearer_token:
        headers["Authorization"] = f"Bearer {bearer_token}"
    raw_headers = get_setting("ADU_LEAD_WEBHOOK_HEADERS_JSON", "")
    if raw_headers:
        try:
            parsed = json.loads(raw_headers)
        except json.JSONDecodeError:
            parsed = {}
        if isinstance(parsed, dict):
            for key, value in parsed.items():
                headers[str(key)] = str(value)
    return headers


def _build_payload(lead: LeadRecord, event_type: str) -> dict[str, Any]:
    return {
        "event_type": event_type,
        "sent_at": utc_now_iso(),
        "lead": lead.to_dict(),
    }


def deliver_lead(lead: LeadRecord, event_type: str) -> DeliveryResult:
    url = get_setting("ADU_LEAD_WEBHOOK_URL", "")
    attempted_at = utc_now_iso()
    if not url:
        return DeliveryResult(
            configured=False,
            success=False,
            message="Webhook not configured.",
            attempted_at=attempted_at,
        )

    timeout_seconds = float(get_setting("ADU_LEAD_WEBHOOK_TIMEOUT_SECONDS", "8") or "8")
    payload = json.dumps(_build_payload(lead, event_type), ensure_ascii=False).encode("utf-8")
    req = request.Request(url, data=payload, headers=_build_headers(), method="POST")
    try:
        with request.urlopen(req, timeout=timeout_seconds) as response:
            status_code = getattr(response, "status", None) or response.getcode()
            response_body = response.read().decode("utf-8", errors="ignore")
            return DeliveryResult(
                configured=True,
                success=200 <= int(status_code) < 300,
                status_code=int(status_code),
                message=response_body[:400],
                attempted_at=attempted_at,
            )
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="ignore")
        return DeliveryResult(
            configured=True,
            success=False,
            status_code=int(exc.code),
            message=body[:400] or str(exc),
            attempted_at=attempted_at,
        )
    except Exception as exc:  # noqa: BLE001
        return DeliveryResult(
            configured=True,
            success=False,
            message=str(exc),
            attempted_at=attempted_at,
        )


def apply_delivery_result(lead: LeadRecord, result: DeliveryResult) -> LeadRecord:
    lead.external_sync_at = result.attempted_at
    if not result.configured:
        lead.external_sync_status = "local_only"
        lead.external_sync_error = ""
        return lead
    if result.success:
        lead.external_sync_status = "synced"
        lead.external_sync_error = ""
        return lead
    lead.external_sync_status = "failed"
    lead.external_sync_error = result.message
    return lead
