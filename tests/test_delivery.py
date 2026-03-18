from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from app.delivery import apply_delivery_result, deliver_lead, webhook_configured
from app.models import LeadRecord, ScreeningAnswers
from app.rules import compute_screening


class _FakeResponse:
    def __init__(self, status: int = 200, body: bytes = b"ok") -> None:
        self.status = status
        self._body = body

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # noqa: ANN001
        return None

    def getcode(self) -> int:
        return self.status

    def read(self) -> bytes:
        return self._body


class DeliveryTests(unittest.TestCase):
    def build_lead(self) -> LeadRecord:
        answers = ScreeningAnswers.from_dict(
            {
                "property_address": "123 Main St, Pasadena, CA",
                "brief_goal": "I want to convert my garage into a legal rental unit.",
                "jurisdiction": "pasadena",
                "owner_on_title": "Yes",
                "project_type": "garage_conversion",
                "structure_type": "detached_garage",
                "full_name": "Test User",
                "email": "test@example.com",
                "consent_to_contact": "Yes",
            }
        )
        return LeadRecord.create(answers, compute_screening(answers))

    def test_webhook_not_configured(self) -> None:
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ADU_LEAD_WEBHOOK_URL", None)
            self.assertFalse(webhook_configured())
            result = deliver_lead(self.build_lead(), "lead.created")
            self.assertFalse(result.configured)
            self.assertFalse(result.success)
            lead = apply_delivery_result(self.build_lead(), result)
            self.assertEqual(lead.external_sync_status, "local_only")

    def test_webhook_success(self) -> None:
        with patch.dict(
            os.environ,
            {"ADU_LEAD_WEBHOOK_URL": "https://example.com/webhook"},
            clear=False,
        ):
            with patch("app.delivery.request.urlopen", return_value=_FakeResponse(status=200, body=b"accepted")):
                result = deliver_lead(self.build_lead(), "lead.created")
                self.assertTrue(result.configured)
                self.assertTrue(result.success)
                self.assertEqual(result.status_code, 200)
                lead = apply_delivery_result(self.build_lead(), result)
                self.assertEqual(lead.external_sync_status, "synced")
                self.assertEqual(lead.external_sync_error, "")


if __name__ == "__main__":
    unittest.main()
