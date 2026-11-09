"""Configuration extraction and deliberately inactive update contract."""

import ast
from importlib import import_module
from pathlib import Path
import unittest
from unittest.mock import Mock

from app.services.texts_handler import TextFacade


class WeightsConfigurationTests(unittest.TestCase):
    def test_configuration_is_owned_by_constants_module(self):
        weights = import_module(
            "app.services.texts_handler.processing.classiffy.weights"
        )
        classifier = import_module("app.services.texts_handler.processing.classiffy")
        self.assertIs(classifier.WEIGHTS, weights.WEIGHTS)
        self.assertAlmostEqual(sum(weights.WEIGHTS.values()), 1, delta=1e-12)
        self.assertEqual(weights.THRESHOLDS, (25, 50, 75))
        self.assertEqual(weights.MEAN_WORD_LENGTH_SCALE, 12)
        self.assertEqual(weights.MAX_WORD_LENGTH_SCALE, 24)
        self.assertEqual(weights.SCORE_SCALE, 100)
        tree = ast.parse(Path(weights.__file__).read_text())
        self.assertFalse(
            any(
                isinstance(node, (ast.FunctionDef, ast.ClassDef))
                for node in ast.walk(tree)
            )
        )

    def test_update_remains_pass_only_and_has_no_database_calls(self):
        db = Mock()
        facade = TextFacade(db)
        self.assertIsNone(facade.update())
        db.assert_not_called()
        self.assertEqual(db.mock_calls, [])
        tree = ast.parse(
            Path(import_module("app.services.texts_handler").__file__).read_text()
        )
        method = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and node.name == "update"
        )
        self.assertEqual(len(method.body), 1)
        self.assertIsInstance(method.body[0], ast.Pass)


if __name__ == "__main__":
    unittest.main()
