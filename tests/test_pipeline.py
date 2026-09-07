import json
import tempfile
import unittest
from pathlib import Path

from code2skill.client import ScriptedClient
from code2skill.config import AppConfig, ModelConfig
from code2skill.pipeline import Code2SkillPipeline


SOURCE_TAG = {
    "keep_for_extraction": True,
    "selection_rationale": "Reusable validation flow.",
    "reusable_intent_score": 0.9,
    "procedural_steps_score": 0.9,
    "boundary_conditions_score": 0.9,
    "transferability_score": 0.9,
    "interface_sufficiency_score": 0.9,
    "non_triviality_score": 0.9,
    "selection_tags": ["validation"],
    "risk_tags": [],
}
SKILL = {
    "level": "composite",
    "name": "Validate positive values",
    "summary": "Validate an input before transforming it, preserve the interface, and raise an explicit error for invalid values.",
    "worth_extracting": True,
    "worth_reason": "Reusable guard-and-transform flow.",
    "skill_value_score": 0.9,
    "generality_score": 0.9,
    "abstraction_score": 0.8,
    "inputs": ["Numeric input"],
    "outputs": ["Transformed value"],
    "workflow": ["Validate the value", "Transform valid input"],
    "invariants": ["Reject negative input"],
    "error_cases": ["Negative input"],
    "implementation_notes": [],
    "evidence": ["Explicit guard"],
    "anti_goals": [],
    "confidence": 0.9,
}
FEATURES = {
    "transfer_title": "Validate input before deterministic transformation",
    "transfer_summary": "Guard an input before applying a transformation.",
    "when_to_use": "Use when invalid values must fail before mutation.",
    "task_family": "validation",
    "capability_tags": ["validate_input", "fail_fast", "return_structured_output"],
    "constraint_tags": ["return_error_on_failure"],
    "success_signal": "A valid result is returned.",
    "success_tags": ["output_returned"],
    "failure_modes": ["Invalid input", "Wrong result"],
    "interaction_pattern": "multi_step_workflow",
    "domain_hints": [],
    "retrieval_phrases": [
        "validate then transform",
        "reject invalid input",
        "input guard",
        "explicit error",
    ],
    "custom_tags": [],
    "notes": "",
}


class PipelineTests(unittest.TestCase):
    def run_case(self, equivalent, keep=False):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo = root / "repo"
            repo.mkdir()
            source = "def transform(value):\n    if value < 0:\n        raise ValueError('negative')\n    return value * 2\n"
            (repo / "logic.py").write_text(source, encoding="utf-8")
            responses = {
                "source_tagging": SOURCE_TAG,
                "extraction": SKILL,
                "regeneration": source,
                "equivalence": {
                    "equivalent": equivalent,
                    "confidence": 0.0 if equivalent else 0.9,
                    "reason": "match" if equivalent else "generation mismatch",
                    "differences": [] if equivalent else ["mismatch"],
                    "risk_level": "high",
                },
                "feature_tagging": FEATURES,
                "adjudication": {
                    "keep": keep,
                    "skill_is_correct": keep,
                    "generation_failed": keep,
                    "reason": "skill remains faithful",
                    "corrective_notes": [],
                },
            }
            client = ScriptedClient(responses)
            config = AppConfig(model=ModelConfig("offline", "offline"))
            config.pipeline.concurrency = 1
            manifest = Code2SkillPipeline(config, client).run(
                str(repo), str(root / "run")
            )
            accepted = [
                json.loads(line)
                for line in (root / "run" / "accepted_records.jsonl")
                .read_text()
                .splitlines()
            ]
            return manifest, accepted, client.calls

    def test_direct_accept_uses_equivalent_boolean(self):
        manifest, accepted, calls = self.run_case(True)
        self.assertEqual(manifest["summary"]["accepted_records"], 1)
        self.assertEqual(accepted[0]["accepted_stage"], "equivalence")
        self.assertIn("reconstruction", accepted[0])
        self.assertNotIn("adjudication", [call["stage"] for call in calls])

    def test_adjudicated_accept_omits_failed_reconstruction(self):
        manifest, accepted, calls = self.run_case(False, keep=True)
        self.assertEqual(manifest["summary"]["accepted_records"], 1)
        self.assertEqual(accepted[0]["accepted_stage"], "adjudication")
        self.assertNotIn("reconstruction", accepted[0])
        self.assertIn("adjudication", [call["stage"] for call in calls])

    def test_adjudication_keep_false_rejects(self):
        manifest, accepted, calls = self.run_case(False, keep=False)
        self.assertEqual(manifest["summary"]["accepted_records"], 0)
        self.assertEqual(accepted, [])
        self.assertNotIn("feature_tagging", [call["stage"] for call in calls])


if __name__ == "__main__":
    unittest.main()
