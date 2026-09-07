import tempfile
import unittest
from pathlib import Path

from code2skill.config import ScanConfig
from code2skill.source import scan_repository


class SourceTests(unittest.TestCase):
    def test_python_functions_are_extracted_and_tests_skipped(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "worker.py").write_text(
                "def work(value):\n    if value < 0:\n        raise ValueError('negative')\n    return value + 1\n",
                encoding="utf-8",
            )
            (root / "test_worker.py").write_text(
                "def test_work():\n    assert True\n    return None\n", encoding="utf-8"
            )
            units, skipped = scan_repository(root, ScanConfig())
            self.assertEqual([unit.symbol for unit in units], ["work"])
            self.assertTrue(any(item["reason"] == "test_file" for item in skipped))


if __name__ == "__main__":
    unittest.main()
