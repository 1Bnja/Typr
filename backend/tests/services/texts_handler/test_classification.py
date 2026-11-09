"""Deterministic classification tests independent of database configuration."""

from collections import Counter
import json
from pathlib import Path
import subprocess
import sys
import unittest

from app.services.texts_handler import TextFacade
from app.services.texts_handler.context import TextContext
from app.services.texts_handler.processing import TextProcessingStep
from app.services.texts_handler.processing.classiffy import ClassifyTextStep


ROOT = Path(__file__).resolve().parents[4]
REFERENCE = ROOT / "backend/tests/fixtures/text_calibration.json"


class Recorder(TextProcessingStep):
    def __init__(self):
        super().__init__()
        self.calls = []

    def handle(self, context):
        self.calls.append((context.content, context.difficulty))


class ClassificationTests(unittest.TestCase):
    def classify(self, content, language="eng"):
        return TextFacade().process(content, language).classification

    def normalized_context(self, content, language="eng"):
        from app.services.texts_handler.processing.normalize import NormalizeTextStep
        from app.services.texts_handler.processing.validate import ValidateTextStep

        context = TextContext(content, language)
        first = ValidateTextStep()
        first.set_next(NormalizeTextStep())
        first.handle(context)
        return context

    def test_step_assigns_difficulty_before_delegating(self):
        context = self.normalized_context("Hello world.")
        handler, recorder = ClassifyTextStep(), Recorder()
        handler.set_next(recorder)
        handler.handle(context)
        self.assertIsNotNone(context.difficulty)
        self.assertEqual(recorder.calls, [(context.content, context.difficulty)])
        self.assertEqual(context.classification.difficulty, context.difficulty)

    def test_calibration_scores_and_all_metrics_match_reference(self):
        reference = json.loads(REFERENCE.read_text())
        levels = Counter()
        for row in reference["results"]:
            with self.subTest(identifier=row["id"]):
                result = self.classify(row["content"], row["language"])
                for field in (
                    "nonspace_characters",
                    "unique_characters",
                    "word_count",
                    "entropy_bits",
                    "mean_word_length",
                    "max_word_length",
                    "mean_key_cost",
                    "score",
                ):
                    self.assertAlmostEqual(
                        getattr(result, field), row[field], places=11
                    )
                for field in ("normalized", "contributions"):
                    for name, value in row[field].items():
                        self.assertAlmostEqual(
                            getattr(result, field)[name], value, places=11
                        )
                self.assertEqual(result.difficulty.value, row["actual"])
                levels[result.difficulty.value] += 1
        self.assertEqual(levels, {"medium": 8, "advanced": 8})

    def test_keyboard_maps_match_frozen_reference(self):
        from app.services.texts_handler.processing.classiffy.keyboard import keyboard

        reference = json.loads(REFERENCE.read_text())
        for language, expected in reference["keyboards"].items():
            layout = keyboard(language)
            self.assertEqual(set(layout.sequences), set(expected["alphabet"]))
            self.assertAlmostEqual(layout.maximum_cost, expected["max_cost"], places=12)
            for char, data in expected["characters"].items():
                self.assertEqual(
                    layout.sequences[char], tuple(map(tuple, data["sequence"]))
                )
                self.assertAlmostEqual(layout.costs[char], data["cost"], places=12)

    def test_known_entropy_and_case_punctuation(self):
        for text, expected in (("aaaaaaaa", 0), ("aaaabbbb", 1), ("abababab", 1)):
            self.assertAlmostEqual(self.classify(text).entropy_bits, expected)
        result = self.classify("a A!")
        self.assertEqual(result.nonspace_characters, 3)
        self.assertEqual(result.unique_characters, 3)
        self.assertAlmostEqual(result.entropy_bits, 1.584962500721156)

    def test_word_measurement_contraction_decimal_and_hyphen(self):
        result = self.classify("don't 9.30 well-known")
        self.assertEqual(result.word_count, 3)
        self.assertAlmostEqual(result.mean_word_length, (4 + 3 + 9) / 3)
        self.assertEqual(result.max_word_length, 9)

    def test_threshold_boundaries_without_rounding(self):
        from app.services.texts_handler.processing.classiffy import difficulty_for_score

        for score, expected in (
            (0, "easy"),
            (24.999999999, "easy"),
            (25, "medium"),
            (49.999999999, "medium"),
            (50, "advanced"),
            (74.999999999, "advanced"),
            (75, "expert"),
            (100, "expert"),
        ):
            with self.subTest(score=score):
                self.assertEqual(difficulty_for_score(score).value, expected)

    def test_long_input_has_fixed_call_depth(self):
        result = self.classify("a" * 5000)
        self.assertEqual(result.nonspace_characters, 5000)
        self.assertEqual(result.normalized["mean_length"], 1)
        self.assertEqual(result.normalized["max_length"], 1)

    def test_spaces_do_not_change_character_distribution(self):
        joined, spaced = self.classify("aaaa"), self.classify("a a a a")
        self.assertEqual(joined.entropy_bits, spaced.entropy_bits)
        self.assertEqual(joined.unique_characters, spaced.unique_characters)
        self.assertEqual(joined.mean_key_cost, spaced.mean_key_cost)

    def test_punctuation_only_has_zero_word_metrics(self):
        result = self.classify("!?")
        self.assertEqual(result.word_count, 0)
        self.assertEqual(result.mean_word_length, 0)
        self.assertEqual(result.max_word_length, 0)
        self.assertTrue(0 <= result.score <= 100)

    def test_repeatability_and_immutable_explanation(self):
        result = self.classify("Hello world.")
        self.assertEqual(result, self.classify("Hello world."))
        self.assertEqual(result.version, "text-difficulty-v1")
        self.assertAlmostEqual(sum(result.contributions.values()), result.score)
        with self.assertRaises(TypeError):
            result.normalized["entropy"] = 0

    def test_keyboard_cost_invariants(self):
        from app.services.texts_handler.processing.classiffy.keyboard import keyboard

        english, spanish = keyboard("eng"), keyboard("spa")
        self.assertGreater(english.costs["A"], english.costs["a"])
        self.assertGreater(spanish.costs["á"], spanish.costs["a"])
        self.assertGreater(spanish.costs["ü"], spanish.costs["u"])
        self.assertEqual(spanish.sequences["ñ"], (("AC10", False),))
        self.assertNotIn("¿", english.sequences)

    def test_existing_enum_module_reexports_identical_pure_enums(self):
        from app.text_enums import Difficulty, Language

        # Load the source without executing app.models.__init__ or requiring SQLAlchemy.
        code = """
import importlib.util
import sys
from types import ModuleType
class SAEnum:
    def __init__(self, enum_cls, *args, **kwargs):
        self.enum_class = enum_cls
stub = ModuleType('sqlalchemy')
stub.Enum = SAEnum
sys.modules['sqlalchemy'] = stub
from app.text_enums import Difficulty, Language
spec = importlib.util.spec_from_file_location('compat_enums', sys.argv[1])
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
assert module.Difficulty is Difficulty
assert module.Language is Language
assert module.DIFFICULTY_ENUM.enum_class is Difficulty
assert module.LANGUAGE_ENUM.enum_class is Language
"""
        subprocess.run(
            [sys.executable, "-c", code, str(ROOT / "backend/app/models/enums.py")],
            check=True,
        )
        self.assertEqual(
            [value.value for value in Difficulty],
            ["easy", "medium", "advanced", "expert"],
        )
        self.assertEqual([value.value for value in Language], ["spa", "eng"])


if __name__ == "__main__":
    unittest.main()
