"""Facade composition and isolated stage contracts without persistence."""

import ast
from pathlib import Path
import unittest
from unittest.mock import patch

from app.services.texts_handler import TextFacade
from app.services.texts_handler.context import TextContext
from app.services.texts_handler.errors import TextValidationError
from app.services.texts_handler.processing.classiffy import ClassifyTextStep
from app.services.texts_handler.processing.normalize import NormalizeTextStep
from app.services.texts_handler.processing.validate import ValidateTextStep

ROOT = Path(__file__).resolve().parents[4]
PROCESSING = ROOT / "backend/app/services/texts_handler/processing"


class ChainIntegrationTests(unittest.TestCase):
    def test_facade_builds_default_chain_and_processes_raw_text(self):
        facade = TextFacade()
        self.assertIsInstance(facade.chain, ValidateTextStep)
        self.assertIsInstance(facade.chain.next, NormalizeTextStep)
        self.assertIsInstance(facade.chain.next.next, ClassifyTextStep)
        self.assertIsNone(facade.chain.next.next.next)
        context = facade.process("  Hola ,mundo.Hola ", "spa")
        self.assertEqual(context.content, "Hola, mundo. Hola")
        self.assertIsNotNone(context.classification)
        self.assertEqual(context.difficulty, context.classification.difficulty)

    def test_each_stage_runs_once_and_in_order(self):
        calls = []
        classes = (ValidateTextStep, NormalizeTextStep, ClassifyTextStep)
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
        from app.services.texts_handler.processing import (
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

    def test_concrete_steps_do_not_import_each_other(self):
        concrete = {"validate", "normalize", "classiffy", "duplicate", "persist"}
        for name in concrete:
            with self.subTest(handler=name):
                path = PROCESSING / (
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
            NormalizeTextStep().handle(context)
        self.assertEqual(caught.exception.code, "not_validated")
        ValidateTextStep().handle(context)
        NormalizeTextStep().handle(context)
        self.assertEqual(context.content, "'hola'")

    def test_stale_validation_is_not_reused(self):
        for attribute, replacement in (("content", "don't"), ("language", "eng")):
            with self.subTest(attribute=attribute):
                context = TextContext("‘ hola ’", "spa")
                ValidateTextStep().handle(context)
                setattr(context, attribute, replacement)
                with self.assertRaises(TextValidationError) as caught:
                    NormalizeTextStep().handle(context)
                self.assertEqual(caught.exception.code, "not_validated")
                self.assertIsNone(context.classification)

    def test_classifier_requires_current_normalized_input(self):
        for attribute, replacement in (("content", "🙂"), ("language", "spa")):
            with self.subTest(attribute=attribute):
                context = TextContext("Hello.", "eng")
                ValidateTextStep().handle(context)
                with self.assertRaises(TextValidationError) as caught:
                    ClassifyTextStep().handle(context)
                self.assertEqual(caught.exception.code, "not_normalized")
                NormalizeTextStep().handle(context)
                setattr(context, attribute, replacement)
                with self.assertRaises(TextValidationError) as caught:
                    ClassifyTextStep().handle(context)
                self.assertEqual(caught.exception.code, "not_normalized")

    def test_invalid_or_expanded_input_never_reaches_classification(self):
        for content, code in (
            ("🙂", "invalid_character"),
            ("a." * 2000, "content_too_long"),
        ):
            with (
                self.subTest(code=code),
                patch.object(ClassifyTextStep, "handle") as classify,
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


if __name__ == "__main__":
    unittest.main()
