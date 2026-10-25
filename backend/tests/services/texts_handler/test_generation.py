"""Generation remains an explicit, database-independent facade operation."""

import ast
from importlib import import_module
from io import StringIO
from pathlib import Path
import subprocess
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import MagicMock, Mock, patch

from app.services.texts_handler import TextFacade


class GenerationTests(unittest.TestCase):
    def setUp(self):
        self.config = ModuleType("app.config")
        self.config.settings = SimpleNamespace(
            gemini_api_key="test-only-key", gemini_model="test-only-model"
        )
        self.google = ModuleType("google")
        self.google.genai = SimpleNamespace(Client=MagicMock())
        self.client = self.google.genai.Client.return_value.__enter__.return_value
        self.client.interactions.create.return_value = SimpleNamespace(
            output_text="  Hola, mundo.\nOtra frase.\n"
        )
        patcher = patch.dict(
            sys.modules, {"app.config": self.config, "google": self.google}
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def generator(self):
        return import_module("app.services.texts_handler.generator")

    def test_facade_returns_raw_output_without_running_either_chain(self):
        raw = "  Hola, mundo.\nOtra frase.\n"
        generator = self.generator()
        db = Mock()
        facade = TextFacade(db)
        with (
            patch.object(
                generator, "generate_text", return_value=raw, create=True
            ) as generate,
            patch.object(facade.chain, "handle") as process,
            patch.object(facade.creation_chain, "handle") as create,
        ):
            self.assertIs(facade.generate(), raw)
        generate.assert_called_once_with()
        process.assert_not_called()
        create.assert_not_called()
        self.assertEqual(db.mock_calls, [])

    def test_generator_returns_exact_text_and_closes_client(self):
        generator = self.generator()
        with patch("sys.stdout", new_callable=StringIO) as output:
            result = generator.generate_text()
        self.assertEqual(result, "  Hola, mundo.\nOtra frase.\n")
        self.assertEqual(output.getvalue(), "")
        self.google.genai.Client.assert_called_once_with(api_key="test-only-key")
        self.client.interactions.create.assert_called_once_with(
            model="test-only-model", input=generator.PROMPT
        )
        self.google.genai.Client.return_value.__exit__.assert_called_once_with(
            None, None, None
        )

    def test_missing_configuration_fails_before_constructing_client(self):
        generator = self.generator()
        for field in ("gemini_api_key", "gemini_model"):
            for missing in (None, "", "  "):
                with self.subTest(field=field, value=missing):
                    with patch.object(self.config.settings, field, missing):
                        with self.assertRaisesRegex(
                            RuntimeError, "GEMINI_API_KEY.*GEMINI_MODEL"
                        ):
                            generator.generate_text()
        self.google.genai.Client.assert_not_called()

    def test_non_text_or_empty_response_is_rejected(self):
        generator = self.generator()
        for value in (None, "", " \n\t", 42):
            with self.subTest(value=value):
                self.client.interactions.create.return_value = SimpleNamespace(
                    output_text=value
                )
                with self.assertRaisesRegex(ValueError, "non-empty text"):
                    generator.generate_text()
        self.assertEqual(self.google.genai.Client.return_value.__exit__.call_count, 4)

    def test_sdk_failure_propagates_and_client_is_closed(self):
        failure = RuntimeError("simulated provider failure")
        self.client.interactions.create.side_effect = failure
        with self.assertRaises(RuntimeError) as caught:
            self.generator().generate_text()
        self.assertIs(caught.exception, failure)
        exit_args = self.google.genai.Client.return_value.__exit__.call_args.args
        self.assertIs(exit_args[0], RuntimeError)
        self.assertIs(exit_args[1], failure)

    def test_generated_text_can_be_explicitly_processed(self):
        self.client.interactions.create.return_value.output_text = " Hola ,mundo. "
        facade = TextFacade()
        raw = facade.generate()
        context = facade.process(raw, "spa")
        self.assertEqual(raw, " Hola ,mundo. ")
        self.assertEqual(context.content, "Hola, mundo.")
        self.assertIsNotNone(context.classification)

    def test_generated_text_can_be_explicitly_persisted(self):
        self.client.interactions.create.return_value.output_text = " Hola ,mundo. "
        expected = TextFacade().process("Hola, mundo.", "spa")
        duplicate = Mock()
        duplicate.scalar.return_value = None
        insert = Mock()
        insert.mappings.return_value.one.return_value = {
            "id": 7,
            "content": expected.content,
            "language": "spa",
            "difficulty": expected.difficulty.value,
            "ideal_time_ms": None,
            "record_user_id": None,
        }
        db = Mock()
        connector = ModuleType("app.database")
        connector.execute_sql = Mock(side_effect=[duplicate, insert])
        with patch.dict(sys.modules, {"app.database": connector}):
            facade = TextFacade(db)
            raw = facade.generate()
            self.assertEqual(db.mock_calls, [])
            result = facade.create(raw, "spa")
        self.assertEqual(result.id, 7)
        self.assertEqual(result.content, expected.content)
        db.commit.assert_called_once_with()

    def test_imports_and_processing_do_not_load_generation_dependencies(self):
        code = """
import importlib.abc
import sys

class BlockExternalImports(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname in {'app.config', 'app.database', 'google'} or fullname.startswith('google.'):
            raise AssertionError('Unexpected dependency import: ' + fullname)

sys.meta_path.insert(0, BlockExternalImports())
from app.services.texts_handler import TextFacade
from app.services.texts_handler import generator
assert callable(generator.generate_text)
assert TextFacade().process('Hola.', 'spa').classification is not None
assert 'app.config' not in sys.modules
assert 'app.database' not in sys.modules
assert 'google' not in sys.modules
"""
        subprocess.run([sys.executable, "-c", code], check=True, capture_output=True)

    def test_gemini_settings_are_optional_outside_generation(self):
        root = Path(__file__).resolve().parents[3]
        tree = ast.parse((root / "app/config.py").read_text())
        settings = next(node for node in tree.body if isinstance(node, ast.ClassDef))
        fields = {
            node.target.id: node
            for node in settings.body
            if isinstance(node, ast.AnnAssign)
        }
        for name in ("gemini_api_key", "gemini_model"):
            with self.subTest(name=name):
                self.assertIsInstance(fields[name].value, ast.Constant)
                self.assertIsNone(fields[name].value.value)


if __name__ == "__main__":
    unittest.main()
