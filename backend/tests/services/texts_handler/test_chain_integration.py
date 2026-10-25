"""Facade composition and isolated stage contracts without persistence."""

import ast
from dataclasses import replace
import json
import inspect
from math import nextafter
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

from app.services.texts_handler import TextFacade
from app.services.texts_handler.context import TextContext
from app.services.texts_handler.errors import TextValidationError
from app.services.texts_handler.handler.classiffy import ClassifyTextHandler
from app.services.texts_handler.handler.normalize import NormalizeTextHandler
from app.services.texts_handler.handler.validate import ValidateTextHandler

ROOT = Path(__file__).resolve().parents[4]
HANDLERS = ROOT / "backend/app/services/texts_handler/handler"


class ChainIntegrationTests(unittest.TestCase):
    def test_facade_builds_default_chain_and_processes_raw_text(self):
        facade = TextFacade()
        self.assertIsInstance(facade.chain, ValidateTextHandler)
        self.assertIsInstance(facade.chain.next, NormalizeTextHandler)
        self.assertIsInstance(facade.chain.next.next, ClassifyTextHandler)
        self.assertIsNone(facade.chain.next.next.next)
        context = facade.process("  Hola ,mundo.Hola ", "spa")
        self.assertEqual(context.content, "Hola, mundo. Hola")
        self.assertIsNotNone(context.classification)
        self.assertEqual(context.difficulty, context.classification.difficulty)

    def test_each_stage_runs_once_and_in_order(self):
        calls = []
        classes = (ValidateTextHandler, NormalizeTextHandler, ClassifyTextHandler)
        original = {cls: cls.handle for cls in classes}

        def spy(cls):
            def handle(instance, context):
                calls.append(cls.__name__)
                return original[cls](instance, context)

            return handle

        with (
            patch.object(classes[0], "handle", spy(classes[0])),
            patch.object(classes[1], "handle", spy(classes[1])),
            patch.object(classes[2], "handle", spy(classes[2])),
        ):
            TextFacade().process("  ‘ Hola ’. ", "spa")
        self.assertEqual(calls, [cls.__name__ for cls in classes])

    def test_helpers_do_not_repeat_predecessor_work(self):
        from app.services.texts_handler.handler import (
            classiffy as classify,
            normalize,
            validate,
        )

        with patch.object(
            validate, "validate_content", wraps=validate.validate_content
        ) as checked:
            with patch.object(
                normalize, "normalize_content", wraps=normalize.normalize_content
            ) as canonical:
                with patch.object(
                    classify, "classify_text", wraps=classify.classify_text
                ) as scored:
                    TextFacade().process("‘ hola ’", "spa")
        self.assertEqual(
            (checked.call_count, canonical.call_count, scored.call_count), (1, 1, 1)
        )

    def test_concrete_handlers_do_not_import_each_other(self):
        concrete = {"validate", "normalize", "classiffy", "duplicate", "persist"}
        for name in concrete:
            with self.subTest(handler=name):
                path = HANDLERS / (
                    "classiffy/__init__.py" if name == "classiffy" else f"{name}.py"
                )
                tree = ast.parse(path.read_text())
                for node in ast.walk(tree):
                    if isinstance(node, ast.ImportFrom):
                        self.assertNotIn(node.module, concrete - {name})
                        if node.module is None:
                            self.assertTrue(
                                concrete.isdisjoint(alias.name for alias in node.names)
                            )

    def test_normalizer_requires_validation_and_uses_quote_metadata(self):
        context = TextContext("‘ hola ’", "spa")
        with self.assertRaises(TextValidationError) as caught:
            NormalizeTextHandler().handle(context)
        self.assertEqual(caught.exception.code, "not_validated")
        ValidateTextHandler().handle(context)
        NormalizeTextHandler().handle(context)
        self.assertEqual(context.content, "'hola'")

    def test_stale_validation_is_not_reused(self):
        for attribute, replacement in (("content", "don't"), ("language", "eng")):
            with self.subTest(attribute=attribute):
                context = TextContext("‘ hola ’", "spa")
                ValidateTextHandler().handle(context)
                setattr(context, attribute, replacement)
                with self.assertRaises(TextValidationError) as caught:
                    NormalizeTextHandler().handle(context)
                self.assertEqual(caught.exception.code, "not_validated")
                self.assertIsNone(context.classification)

    def test_classifier_requires_current_normalized_input(self):
        for attribute, replacement in (("content", "🙂"), ("language", "spa")):
            with self.subTest(attribute=attribute):
                context = TextContext("Hello.", "eng")
                ValidateTextHandler().handle(context)
                with self.assertRaises(TextValidationError) as caught:
                    ClassifyTextHandler().handle(context)
                self.assertEqual(caught.exception.code, "not_normalized")
                NormalizeTextHandler().handle(context)
                setattr(context, attribute, replacement)
                with self.assertRaises(TextValidationError) as caught:
                    ClassifyTextHandler().handle(context)
                self.assertEqual(caught.exception.code, "not_normalized")

    def test_invalid_or_expanded_input_never_reaches_classification(self):
        for content, code in (
            ("🙂", "invalid_character"),
            ("a." * 2000, "content_too_long"),
        ):
            with (
                self.subTest(code=code),
                patch.object(ClassifyTextHandler, "handle") as classify,
            ):
                with self.assertRaises(TextValidationError) as caught:
                    TextFacade().process(content, "eng")
                self.assertEqual(caught.exception.code, code)
                classify.assert_not_called()

    def test_process_calls_are_independent_and_create_requires_session(self):
        facade = TextFacade()
        first = facade.process("‘ Hola ’", "spa")
        second = facade.process("Hello.", "eng")
        self.assertIsNot(first, second)
        self.assertIsNot(first.classification, second.classification)
        self.assertEqual(first.content, "'Hola'")
        with self.assertRaisesRegex(RuntimeError, "database session"):
            facade.create("Hello.", "eng")

    def test_all_calibration_results_match_through_facade(self):
        reference = json.loads(
            (ROOT / "docs/issues-camilo/t-02.1/calibration-results.json").read_text()
        )
        facade = TextFacade()
        for row in reference["results"]:
            with self.subTest(identifier=row["id"]):
                context = facade.process(row["content"], row["language"])
                self.assertEqual(context.content, row["content"])
                self.assertAlmostEqual(
                    context.classification.score, row["score"], delta=1e-12
                )
                self.assertEqual(context.difficulty.value, row["actual"])

    def reference_comparison_result(self, adjust_score):
        process = TextFacade.process

        def adjusted_process(facade, content, language):
            context = process(facade, content, language)
            context.classification = replace(
                context.classification,
                score=adjust_score(context.classification.score),
            )
            return context

        case = ChainIntegrationTests(
            "test_all_calibration_results_match_through_facade"
        )
        result = unittest.TestResult()
        with patch.object(TextFacade, "process", adjusted_process):
            case.run(result)
        return result

    def test_reference_comparison_accepts_float_roundoff(self):
        result = self.reference_comparison_result(
            lambda score: nextafter(score, float("inf"))
        )
        self.assertEqual(result.errors, [])
        self.assertEqual(result.failures, [])

    def test_reference_comparison_rejects_material_score_change(self):
        result = self.reference_comparison_result(lambda score: score + 1e-6)
        self.assertEqual(result.errors, [])
        self.assertTrue(result.failures)

    def test_type_only_context_annotations_are_deferred(self):
        from app.services.texts_handler.handler.classiffy import classify_text

        self.assertEqual(
            inspect.get_annotations(classify_text)["context"], "TextContext"
        )

    def test_facade_import_and_processing_do_not_load_database(self):
        code = """
import sys
from app.services.texts_handler import TextFacade
result = TextFacade().process('Hello.', 'eng')
assert result.classification is not None
assert 'app.database' not in sys.modules
assert 'app.config' not in sys.modules
assert 'app.models' not in sys.modules
"""
        subprocess.run([sys.executable, "-c", code], check=True)


if __name__ == "__main__":
    unittest.main()
