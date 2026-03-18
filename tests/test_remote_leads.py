from __future__ import annotations

import unittest

from app.models import LeadRecord, ScreeningAnswers, ScreeningResult
from app.remote_leads import merge_local_and_remote_leads


def make_lead(lead_id: str, *, created_at: str, updated_at: str, full_name: str) -> LeadRecord:
    return LeadRecord(
        id=lead_id,
        created_at=created_at,
        last_updated_at=updated_at,
        answers=ScreeningAnswers(full_name=full_name, property_address="123 Test St"),
        result=ScreeningResult(
            risk_tier="Green",
            recommended_path="A",
            recommended_service="Review",
            jurisdiction_label="Pasadena",
            project_label="Garage conversion",
        ),
    )


class RemoteLeadTests(unittest.TestCase):
    def test_remote_wins_when_more_recent(self) -> None:
        local = make_lead(
            "same-id",
            created_at="2026-03-17T10:00:00+00:00",
            updated_at="2026-03-17T10:05:00+00:00",
            full_name="Local Lead",
        )
        remote = make_lead(
            "same-id",
            created_at="2026-03-17T10:00:00+00:00",
            updated_at="2026-03-17T10:15:00+00:00",
            full_name="Remote Lead",
        )

        merged = merge_local_and_remote_leads([local], [remote])
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0].answers.full_name, "Remote Lead")

    def test_merge_keeps_distinct_ids(self) -> None:
        local = make_lead(
            "local-id",
            created_at="2026-03-17T10:00:00+00:00",
            updated_at="2026-03-17T10:05:00+00:00",
            full_name="Local Lead",
        )
        remote = make_lead(
            "remote-id",
            created_at="2026-03-17T11:00:00+00:00",
            updated_at="2026-03-17T11:05:00+00:00",
            full_name="Remote Lead",
        )

        merged = merge_local_and_remote_leads([local], [remote])
        self.assertEqual({lead.id for lead in merged}, {"local-id", "remote-id"})


if __name__ == "__main__":
    unittest.main()
