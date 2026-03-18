from __future__ import annotations

import unittest

from app.models import (
    LeadRecord,
    ScreeningAnswers,
    backfill_lead_defaults,
    initial_stage_for_lead,
    lead_needs_attention,
    lead_priority_key,
    suggested_next_action_for_lead,
)
from app.rules import compute_screening, suggest_jurisdiction, suggest_project_type


class RuleTests(unittest.TestCase):
    def test_address_router_detects_city(self) -> None:
        self.assertEqual(
            suggest_jurisdiction("123 Main St, Pasadena, CA"),
            "pasadena",
        )
        self.assertEqual(
            suggest_jurisdiction("123 Main St, Los Angeles, CA"),
            "city_of_los_angeles",
        )

    def test_project_type_suggestion(self) -> None:
        self.assertEqual(
            suggest_project_type("I want to legalize an unpermitted unit."),
            "unpermitted_unit",
        )
        self.assertEqual(
            suggest_project_type("Can I convert my garage into an ADU?"),
            "garage_conversion",
        )

    def test_clean_standard_case_routes_to_a(self) -> None:
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
            }
        )
        result = compute_screening(answers)
        self.assertEqual(result.recommended_path, "A")
        self.assertEqual(result.risk_tier, "Green")

    def test_violation_case_routes_to_b(self) -> None:
        answers = ScreeningAnswers.from_dict(
            {
                "property_address": "123 Main St, Los Angeles, CA",
                "brief_goal": "I need to legalize a garage apartment after a violation.",
                "jurisdiction": "city_of_los_angeles",
                "owner_on_title": "Yes",
                "project_type": "unpermitted_unit",
                "structure_type": "existing_unit",
                "hillside": "No",
                "basement": "No",
                "addition_without_permit": "Yes",
                "unpermitted_work": "Yes",
                "prior_violation": "Yes",
                "prior_plans": "Yes",
            }
        )
        result = compute_screening(answers)
        self.assertEqual(result.recommended_path, "B")
        self.assertIn(result.risk_tier, {"Orange", "Red"})

    def test_complex_case_defaults_to_needs_review_stage(self) -> None:
        answers = ScreeningAnswers.from_dict(
            {
                "property_address": "123 Main St, Los Angeles, CA",
                "brief_goal": "I need to legalize a garage apartment after a violation.",
                "jurisdiction": "city_of_los_angeles",
                "owner_on_title": "Yes",
                "project_type": "unpermitted_unit",
                "structure_type": "existing_unit",
                "prior_violation": "Yes",
            }
        )
        result = compute_screening(answers)
        self.assertEqual(initial_stage_for_lead(answers, result), "needs_review")

    def test_clean_case_defaults_to_new_stage(self) -> None:
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
            }
        )
        result = compute_screening(answers)
        self.assertEqual(initial_stage_for_lead(answers, result), "new")

    def test_needs_review_case_gets_review_next_action(self) -> None:
        answers = ScreeningAnswers.from_dict(
            {
                "property_address": "123 Main St, Los Angeles, CA",
                "brief_goal": "I need to legalize a garage apartment after a violation.",
                "jurisdiction": "city_of_los_angeles",
                "owner_on_title": "Yes",
                "project_type": "unpermitted_unit",
                "structure_type": "existing_unit",
                "prior_violation": "Yes",
            }
        )
        result = compute_screening(answers)
        stage = initial_stage_for_lead(answers, result)

        self.assertEqual(stage, "needs_review")
        self.assertIn("Senior review first", suggested_next_action_for_lead(answers, result, stage))

    def test_attention_flag_marks_old_open_lead(self) -> None:
        answers = ScreeningAnswers.from_dict(
            {
                "property_address": "123 Main St, Pasadena, CA",
                "brief_goal": "I want to convert my garage into a legal rental unit.",
                "jurisdiction": "pasadena",
                "owner_on_title": "Yes",
                "project_type": "garage_conversion",
                "structure_type": "detached_garage",
            }
        )
        result = compute_screening(answers)
        lead = LeadRecord.create(answers, result)
        lead.stage = "new"
        lead.last_updated_at = "2026-03-14T00:00:00+00:00"

        self.assertTrue(lead_needs_attention(lead, hours=24))

    def test_priority_key_prefers_review_before_clean_new(self) -> None:
        clean_answers = ScreeningAnswers.from_dict(
            {
                "property_address": "123 Main St, Pasadena, CA",
                "brief_goal": "I want to convert my garage into a legal rental unit.",
                "jurisdiction": "pasadena",
                "owner_on_title": "Yes",
                "project_type": "garage_conversion",
                "structure_type": "detached_garage",
            }
        )
        complex_answers = ScreeningAnswers.from_dict(
            {
                "property_address": "123 Main St, Los Angeles, CA",
                "brief_goal": "I need to legalize a garage apartment after a violation.",
                "jurisdiction": "city_of_los_angeles",
                "owner_on_title": "Yes",
                "project_type": "unpermitted_unit",
                "structure_type": "existing_unit",
                "prior_violation": "Yes",
            }
        )
        clean_lead = LeadRecord.create(clean_answers, compute_screening(clean_answers))
        complex_lead = LeadRecord.create(complex_answers, compute_screening(complex_answers))

        self.assertLess(lead_priority_key(complex_lead), lead_priority_key(clean_lead))

    def test_backfill_defaults_updates_old_complex_lead(self) -> None:
        answers = ScreeningAnswers.from_dict(
            {
                "property_address": "123 Main St, Los Angeles, CA",
                "brief_goal": "I need to legalize a garage apartment after a violation.",
                "jurisdiction": "city_of_los_angeles",
                "owner_on_title": "Yes",
                "project_type": "unpermitted_unit",
                "structure_type": "existing_unit",
                "prior_violation": "Yes",
            }
        )
        lead = LeadRecord.create(answers, compute_screening(answers))
        lead.stage = "new"
        lead.next_action = ""
        changed = backfill_lead_defaults(lead)

        self.assertTrue(changed)
        self.assertEqual(lead.stage, "needs_review")
        self.assertIn("Senior review first", lead.next_action)


if __name__ == "__main__":
    unittest.main()
