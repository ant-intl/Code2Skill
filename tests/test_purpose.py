import unittest

from code2skill.purpose import build_purpose_index


def record(data_id, workflow, level="atomic"):
    return {
        "data_id": data_id,
        "repo_name": "repo",
        "symbol": "validateConfig",
        "skill": {
            "level": level,
            "name": "Validate configuration schema",
            "summary": "Validate a configuration object against a schema and return actionable errors while preserving the supplied values for downstream processing.",
            "workflow": workflow,
            "inputs": ["Configuration object"],
            "outputs": ["Validated configuration"],
            "invariants": ["Reject malformed values"],
            "error_cases": ["Schema mismatch"],
            "evidence": ["Explicit validation branch"],
            "anti_goals": [],
        },
        "retrieval": {"task_family": "validation"},
    }


class PurposeTests(unittest.TestCase):
    def test_same_purpose_is_grouped_and_existing_record_selected(self):
        records = [
            record("short", ["Validate input"]),
            record(
                "rich", ["Load schema", "Validate input", "Return errors"], "composite"
            ),
        ]
        cards, edges, dropped = build_purpose_index(records)
        self.assertEqual(len(cards), 1)
        self.assertEqual(len(edges), 2)
        self.assertEqual(dropped, [])
        self.assertEqual(cards[0]["representative_data_id"], "rich")


if __name__ == "__main__":
    unittest.main()
