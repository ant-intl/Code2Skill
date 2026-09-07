import os
import unittest
from unittest.mock import patch

from code2skill.config import ModelConfig


class ModelConfigTests(unittest.TestCase):
    def test_model_url_can_be_loaded_from_environment(self):
        config = ModelConfig("env:CODE2SKILL_TEST_MODEL_URL", "test-model")
        with patch.dict(
            os.environ,
            {"CODE2SKILL_TEST_MODEL_URL": "model-endpoint"},
        ):
            self.assertEqual(config.resolved_base_url(), "model-endpoint")

    def test_missing_model_url_environment_variable_fails_closed(self):
        config = ModelConfig("env:CODE2SKILL_TEST_MISSING_URL", "test-model")
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ValueError):
                config.resolved_base_url()


if __name__ == "__main__":
    unittest.main()
