import unittest
from dataclasses import asdict

from code2skill.prompts import (
    adjudication_messages,
    demo_unit,
    equivalence_messages,
    extraction_messages,
    feature_messages,
    regeneration_messages,
)
from code2skill.schemas import SkillRecord, SourceUnitTag


class PromptBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.unit = demo_unit()
        self.unit.repo_name = "REPO_SENTINEL"
        self.unit.relative_path = "PATH_SENTINEL.py"
        self.unit.code = "SOURCE_BODY_SENTINEL"
        self.unit.unit_type = "UNIT_TYPE_SENTINEL"
        self.tag = SourceUnitTag(True, "tag sentinel", 1, 1, 1, 1, 1, 1)
        self.skill = SkillRecord(
            "atomic", "name", "SUMMARY_SENTINEL", True, "worth", 1, 1, 1
        )

    @staticmethod
    def body(messages):
        return "\n".join(message["content"] for message in messages)

    def test_extraction_sees_tag_and_source(self):
        body = self.body(extraction_messages(self.unit, self.tag))
        self.assertIn("SOURCE_BODY_SENTINEL", body)
        self.assertIn("tag sentinel", body)

    def test_regeneration_is_source_body_blind(self):
        body = self.body(regeneration_messages(self.unit, self.skill))
        for sentinel in ("SOURCE_BODY_SENTINEL", "REPO_SENTINEL", "PATH_SENTINEL"):
            self.assertNotIn(sentinel, body)
        self.assertIn("UNIT_TYPE_SENTINEL", body)
        self.assertIn("SUMMARY_SENTINEL", body)

    def test_judge_has_narrow_interface(self):
        body = self.body(
            equivalence_messages(self.unit, self.skill, "GENERATED_SENTINEL")
        )
        self.assertIn("SOURCE_BODY_SENTINEL", body)
        self.assertIn("GENERATED_SENTINEL", body)
        self.assertIn("SUMMARY_SENTINEL", body)
        self.assertNotIn("UNIT_TYPE_SENTINEL", body)
        self.assertNotIn("REPO_SENTINEL", body)

    def test_adjudicator_sees_full_skill_but_not_unit_type(self):
        body = self.body(
            adjudication_messages(
                self.unit, self.skill, "GENERATED_SENTINEL", "REASON_SENTINEL"
            )
        )
        self.assertIn("SUMMARY_SENTINEL", body)
        self.assertIn("SOURCE_BODY_SENTINEL", body)
        self.assertIn("REASON_SENTINEL", body)
        self.assertNotIn("UNIT_TYPE_SENTINEL", body)

    def test_feature_payload_uses_flat_paper_schema(self):
        payload = {
            "data_id": "record",
            "repo_name": "repo",
            "relative_path": "path.py",
            "symbol": "symbol",
            **asdict(self.skill),
            "accepted_stage": "equivalence",
            "rationale": "match",
        }
        body = self.body(feature_messages(payload))
        self.assertIn('"summary": "SUMMARY_SENTINEL"', body)
        self.assertNotIn('"skill": {', body)


if __name__ == "__main__":
    unittest.main()
