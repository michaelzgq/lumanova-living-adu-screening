from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.models import LeadRecord, ScreeningAnswers
from app.rules import compute_screening
from app.storage import LeadRepository


class StorageTests(unittest.TestCase):
    def build_lead(self) -> LeadRecord:
        answers = ScreeningAnswers.from_dict(
            {
                "property_address": "123 Main St, Pasadena, CA",
                "brief_goal": "I want to convert my garage into a legal rental unit.",
                "jurisdiction": "pasadena",
                "owner_on_title": "Yes",
                "project_type": "garage_conversion",
                "structure_type": "detached_garage",
                "hillside": "No",
                "basement": "No",
                "addition_without_permit": "No",
                "unpermitted_work": "No",
                "prior_violation": "No",
                "prior_plans": "No",
                "contact_preference": "Phone",
                "best_contact_time": "Weekdays after 4pm",
                "consent_to_contact": "Yes",
                "source_tag": "wechat_sgv",
                "utm_source": "wechat",
                "utm_medium": "social",
                "utm_campaign": "march_test",
                "full_name": "Test User",
                "email": "test@example.com",
                "phone": "555-111-2222",
                "wechat_id": "mike-adu-test",
            }
        )
        result = compute_screening(answers)
        return LeadRecord.create(answers, result)

    def test_repository_persists_extended_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = LeadRepository(Path(temp_dir) / "leads.json")
            lead = self.build_lead()
            repo.save_lead(lead)

            saved = repo.list_leads()[0]
            self.assertEqual(saved.answers.contact_preference, "Phone")
            self.assertEqual(saved.answers.best_contact_time, "Weekdays after 4pm")
            self.assertEqual(saved.answers.consent_to_contact, "Yes")
            self.assertEqual(saved.answers.source_tag, "wechat_sgv")
            self.assertEqual(saved.answers.utm_source, "wechat")
            self.assertEqual(saved.answers.wechat_id, "mike-adu-test")
            self.assertEqual(saved.stage, "new")

    def test_repository_updates_stage_and_notes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = LeadRepository(Path(temp_dir) / "leads.json")
            lead = self.build_lead()
            repo.save_lead(lead)

            lead.stage = "qualified"
            lead.assigned_to = "Mike"
            lead.internal_notes = "Customer sounds serious."
            repo.update_lead(lead)

            saved = repo.list_leads()[0]
            self.assertEqual(saved.stage, "qualified")
            self.assertEqual(saved.assigned_to, "Mike")
            self.assertEqual(saved.internal_notes, "Customer sounds serious.")

    def test_repository_finds_duplicate_by_wechat(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = LeadRepository(Path(temp_dir) / "leads.json")
            lead = self.build_lead()
            repo.save_lead(lead)

            duplicate_answers = ScreeningAnswers.from_dict(
                {
                    "property_address": "456 Another St, Pasadena, CA",
                    "brief_goal": "Need ADU help.",
                    "wechat_id": "MIKE-ADU-TEST",
                }
            )

            duplicate = repo.find_duplicate_lead(duplicate_answers)

            self.assertIsNotNone(duplicate)
            self.assertEqual(duplicate.id, lead.id)

    def test_repository_deletes_lead(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = LeadRepository(Path(temp_dir) / "leads.json")
            lead = self.build_lead()
            repo.save_lead(lead)

            deleted = repo.delete_lead(lead.id)

            self.assertTrue(deleted)
            self.assertEqual(repo.list_leads(), [])

    def test_repository_finds_duplicate_by_email(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = LeadRepository(Path(temp_dir) / "leads.json")
            lead = self.build_lead()
            repo.save_lead(lead)

            duplicate_answers = ScreeningAnswers.from_dict(
                {
                    "property_address": "999 New Address, Pasadena, CA",
                    "brief_goal": "I want to check an ADU.",
                    "email": "TEST@example.com",
                }
            )

            duplicate = repo.find_duplicate_lead(duplicate_answers)

            self.assertIsNotNone(duplicate)
            self.assertEqual(duplicate.id, lead.id)


if __name__ == "__main__":
    unittest.main()
