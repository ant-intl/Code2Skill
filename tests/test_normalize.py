import unittest

from code2skill import normalize


class NormalizeTests(unittest.TestCase):
    def test_boolean_strings_do_not_use_python_truthiness(self):
        self.assertFalse(normalize.as_bool("false"))
        self.assertTrue(normalize.as_bool("true"))
        self.assertFalse(normalize.as_bool("unknown"))

    def test_feature_vocab_is_enforced(self):
        result = normalize.features(
            {
                "transfer_title": "Validate state after mutation",
                "transfer_summary": "Mutate and verify.",
                "when_to_use": "Use for state changes.",
                "task_family": "invented",
                "capability_tags": ["status_check", "invented"],
                "constraint_tags": ["must_recheck_after_mutation", "invented"],
                "success_signal": "State is confirmed.",
                "success_tags": ["status_verified", "invented"],
                "failure_modes": ["Stale state"],
                "interaction_pattern": "invented",
                "domain_hints": [],
                "retrieval_phrases": ["verify state"],
                "custom_tags": [],
                "notes": "",
            }
        )
        self.assertEqual(result.task_family, "workflow")
        self.assertEqual(result.interaction_pattern, "single_step")
        self.assertEqual(result.capability_tags, ["status_check"])
        self.assertEqual(len(result.canonical_fingerprint), 64)


if __name__ == "__main__":
    unittest.main()
