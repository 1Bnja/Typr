"""Behavioral tests for the text validation and normalization chain."""

from enum import Enum
from pathlib import Path
import re
import subprocess
import sys
import unittest

from app.services.texts_handler.context import TextContext
from app.services.texts_handler.processing import TextProcessingStep
from app.services.texts_handler.processing.validate import ValidateTextStep


class Recorder(TextProcessingStep):
    def __init__(self):
        super().__init__()
        self.contents = []

    def handle(self, context):
        self.contents.append(context.content)


class Language(str, Enum):
    SPA = "spa"
    ENG = "eng"


class TextProcessingTests(unittest.TestCase):
    def normalize(self, content, language="spa"):
        from app.services.texts_handler.processing.normalize import NormalizeTextStep

        context = TextContext(content, language)
        first = ValidateTextStep()
        first.set_next(NormalizeTextStep())
        first.handle(context)
        return context.content

    def test_context_initializes_input_and_empty_difficulty(self):
        context = TextContext("Hello", "eng")
        self.assertEqual(context.content, "Hello")
        self.assertEqual(context.language, "eng")
        self.assertIsNone(context.difficulty)

    def test_chain_delegates_in_order(self):
        first, second, last = TextProcessingStep(), TextProcessingStep(), Recorder()
        self.assertIs(first.set_next(second), second)
        second.set_next(last)
        first.handle(TextContext("Hola", "spa"))
        self.assertEqual(last.contents, ["Hola"])

    def test_validation_preserves_raw_content_and_delegates(self):
        handler, recorder = ValidateTextStep(), Recorder()
        handler.set_next(recorder)
        handler.handle(TextContext(" Hola\n mundo ", Language.SPA))
        self.assertEqual(recorder.contents, [" Hola\n mundo "])

    def test_invalid_input_stops_chain(self):
        handler, recorder = ValidateTextStep(), Recorder()
        handler.set_next(recorder)
        with self.assertRaises(ValueError):
            handler.handle(TextContext("Hola🙂", "spa"))
        self.assertEqual(recorder.contents, [])

    def test_unsupported_language_rejected(self):
        for language in ("es", "fr", "", None, 1, []):
            with self.subTest(language=language), self.assertRaises(ValueError):
                ValidateTextStep().handle(TextContext("Hello", language))

    def test_empty_and_non_string_input_rejected(self):
        for content in ("", " \t\r\n ", None, 12, []):
            with self.subTest(content=content), self.assertRaises(ValueError):
                ValidateTextStep().handle(TextContext(content, "spa"))

    def test_explicit_character_allowlist(self):
        for content in (
            "hello🙂",
            "hello\x00",
            "hello\u200b",
            "hello\u00a0world",
            "hello\vworld",
            "a_b",
            "a@b",
            "１２",
            "é",
            "ñ",
            "ü",
            "¿Hi?",
            "¡Hi!",
        ):
            with self.subTest(content=content), self.assertRaises(ValueError):
                ValidateTextStep().handle(TextContext(content, "eng"))

    def test_spanish_alphabet_case_and_punctuation(self):
        content = 'ÁÉÍÓÚáéíóúÑñÜü 0123456789. , ; : ¿? ¡! "() -'
        context = TextContext(content, "spa")
        ValidateTextStep().handle(context)
        self.assertEqual(context.content, content)

    def test_decomposed_accents_not_silently_rewritten(self):
        with self.assertRaises(ValueError):
            self.normalize("pingu\u0308ino", "spa")

    def test_raw_maximum_length(self):
        ValidateTextStep().handle(TextContext("a" * 5000, "eng"))
        with self.assertRaises(ValueError):
            ValidateTextStep().handle(TextContext("a" * 5001, "eng"))

    def test_normalized_maximum_length(self):
        with self.assertRaises(ValueError):
            self.normalize("a." * 2000, "eng")

    def test_spanish_apostrophes_and_quote_pairs(self):
        for content in (
            "don't",
            "don’t",
            "'hola",
            "hola'",
            "’hola‘",
            "‘hola'",
            "'hola’",
            "‘hola",
            "hola’",
        ):
            with self.subTest(content=content), self.assertRaises(ValueError):
                self.normalize(content)

    def test_valid_straight_and_typographic_quotes(self):
        for raw, expected in (
            ("'a'", "'a'"),
            ("‘hola mundo’", "'hola mundo'"),
            ("Dijo: ‘ hola ’.", "Dijo: 'hola'."),
        ):
            with self.subTest(raw=raw):
                self.assertEqual(self.normalize(raw), expected)

    def test_english_contractions_preserved(self):
        self.assertEqual(
            self.normalize("Don't stop, we're ready.", "eng"),
            "Don't stop, we're ready.",
        )

    def test_english_unpaired_quotes_rejected(self):
        for content in ("'hello", "hello'", "don’t"):
            with self.subTest(content=content), self.assertRaises(ValueError):
                self.normalize(content, "eng")

    def test_whitespace_and_basic_punctuation(self):
        cases = (
            (" \tHola\r\n mundo  ", "Hola mundo"),
            ("Hola ,mundo.Hola", "Hola, mundo. Hola"),
            ("¿ Hola ?", "¿Hola?"),
            ("¡ Hola !", "¡Hola!"),
            ('Dijo : " Hola ,mundo . "', 'Dijo: "Hola, mundo."'),
            ("( Hola ) . Adiós", "(Hola). Adiós"),
            ("Hola...Adiós!?", "Hola... Adiós!?"),
        )
        for raw, expected in cases:
            with self.subTest(raw=raw):
                self.assertEqual(self.normalize(raw), expected)
                self.assertEqual(self.normalize(expected), expected)

    def test_decimals_preserved(self):
        self.assertEqual(
            self.normalize("Versión 3.14.El valor es 9.30."),
            "Versión 3.14. El valor es 9.30.",
        )

    def test_normalization_delegates_canonical_content(self):
        from app.services.texts_handler.processing.normalize import NormalizeTextStep

        handler, recorder = NormalizeTextStep(), Recorder()
        handler.set_next(recorder)
        first = ValidateTextStep()
        first.set_next(handler)
        first.handle(TextContext(" Hola ,mundo ", "spa"))
        self.assertEqual(recorder.contents, ["Hola, mundo"])

    def test_normalizer_rejects_unvalidated_direct_use(self):
        from app.services.texts_handler.processing.normalize import NormalizeTextStep

        with self.assertRaises(ValueError) as caught:
            NormalizeTextStep().handle(TextContext("Hola\x00", "spa"))
        self.assertEqual(caught.exception.code, "not_validated")

    def test_calibration_examples_unchanged(self):
        root = Path(__file__).resolve().parents[4]
        document = root / "docs/issues-camilo/t-02.1/calibration-examples.md"
        rows = re.findall(
            r"^\| (?:SPA|ENG)-\d+ \| `([^`]+)` \| `[^`]+` \| `([^`]+)`",
            document.read_text(),
            re.M,
        )
        self.assertEqual(len(rows), 16)
        for language, content in rows:
            with self.subTest(content=content):
                self.assertEqual(self.normalize(content, language), content)

    def test_validation_error_has_machine_code(self):
        try:
            ValidateTextStep().handle(TextContext("🙂", "eng"))
        except ValueError as error:
            self.assertEqual(error.code, "invalid_character")
        else:
            self.fail("Invalid input must raise a validation error")

    def test_error_precedence_is_preserved(self):
        from app.services.texts_handler.processing.validate import validate_content

        for content, language, code in (
            (None, [], "unsupported_language"),
            (None, "eng", "invalid_content"),
            ("a" * 5000 + "🙂", "eng", "content_too_long"),
            ("'🙂", "eng", "invalid_character"),
        ):
            with self.subTest(code=code), self.assertRaises(ValueError) as caught:
                validate_content(content, language)
            self.assertEqual(caught.exception.code, code)

    def test_whitespace_does_not_change_quote_roles_or_decimal_boundaries(self):
        cases = (
            (" \t‘ hola ’\r\n, mundo", "'hola', mundo"),
            ("3\t.\n14", "3. 14"),
            ("3.14\t.\r\nHola", "3.14. Hola"),
            ("don't\tstop", "don't stop"),
        )
        for raw, expected in cases:
            with self.subTest(raw=raw):
                self.assertEqual(self.normalize(raw, "eng"), expected)
                self.assertEqual(self.normalize(expected, "eng"), expected)

    def test_import_does_not_initialize_database(self):
        code = """
import sys
from app.services.texts_handler.processing.validate import ValidateTextStep
from app.services.texts_handler.processing.normalize import NormalizeTextStep
assert 'app.database' not in sys.modules
assert 'app.config' not in sys.modules
assert 'app.models' not in sys.modules
"""
        subprocess.run([sys.executable, "-c", code], check=True)


if __name__ == "__main__":
    unittest.main()
