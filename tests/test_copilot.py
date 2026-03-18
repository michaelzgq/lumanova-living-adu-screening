from __future__ import annotations

import unittest

from app.copilot import generate_copilot_brief
from app.models import LeadRecord, ScreeningAnswers
from app.rules import compute_screening


class CopilotTests(unittest.TestCase):
    def test_copilot_for_standard_lead_mentions_standard_review(self) -> None:
        answers = ScreeningAnswers.from_dict(
            {
                "property_address": "123 Main St, Pasadena, CA",
                "brief_goal": "I want to convert my garage into a legal rental unit.",
                "jurisdiction": "pasadena",
                "owner_on_title": "Yes",
                "project_type": "garage_conversion",
                "structure_type": "detached_garage",
                "full_name": "Test User",
            }
        )
        lead = LeadRecord.create(answers, compute_screening(answers))

        brief = generate_copilot_brief(lead)

        self.assertIn("standard path", brief.lead_summary)
        self.assertIn("standard path review", brief.outreach_draft.lower())
        self.assertGreaterEqual(brief.lead_score, 60)
        self.assertIn(brief.lead_temperature, {"Warm", "Hot"})
        self.assertIn("Standard sales follow-up", brief.recommended_owner)

    def test_copilot_for_rescue_lead_requests_violation_docs(self) -> None:
        answers = ScreeningAnswers.from_dict(
            {
                "property_address": "321 Rescue Ln, Los Angeles, CA 90031",
                "brief_goal": "I already have a garage apartment built without permits and need to legalize it.",
                "jurisdiction": "city_of_los_angeles",
                "owner_on_title": "Yes",
                "project_type": "unpermitted_unit",
                "structure_type": "existing_unit",
                "prior_violation": "Yes",
                "unpermitted_work": "Yes",
                "full_name": "Rescue Lead",
            }
        )
        lead = LeadRecord.create(answers, compute_screening(answers))

        brief = generate_copilot_brief(lead)

        self.assertIn("High priority senior review", brief.internal_priority)
        self.assertTrue(any("violation" in item.lower() for item in brief.document_requests))
        self.assertIn("rescue / legalization review", brief.outreach_draft.lower())
        self.assertLessEqual(brief.lead_score, 45)
        self.assertEqual(brief.lead_temperature, "Cold")
        self.assertIn("Senior reviewer", brief.recommended_owner)


if __name__ == "__main__":
    unittest.main()
