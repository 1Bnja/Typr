"""Generation remains an explicit, database-independent facade operation."""

import ast
import json
from importlib import import_module
from io import StringIO
from pathlib import Path
import subprocess
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import MagicMock, Mock, patch

from app.services.texts_handler import TextFacade
from app.services.texts_handler.load import load_phrases
from app.text_enums import Difficulty


class GenerationTests(unittest.TestCase):
    PHRASE = "Hola, mundo. Practicar cada día mejora la velocidad al escribir."

    def setUp(self):
        self.config = ModuleType("app.config")
        self.config.settings = SimpleNamespace(
            gemini_api_key="test-only-key", gemini_model="test-only-model"
        )
        self.google = ModuleType("google")
        self.google.genai = ModuleType("google.genai")
        self.google.genai.Client = MagicMock()
        self.google.genai.errors = SimpleNamespace(
            ServerError=type("ServerError", (Exception,), {}),
            ClientError=type("ClientError", (Exception,), {}),
        )
        self.google.genai.types = SimpleNamespace(
            Type=SimpleNamespace(ARRAY="ARRAY", STRING="STRING", OBJECT="OBJECT", BOOLEAN="BOOLEAN"),
            Schema=lambda **kwargs: kwargs,
            GenerateContentConfig=lambda **kwargs: kwargs,
        )
        self.client = self.google.genai.Client.return_value.__enter__.return_value
        self.client.interactions.create.return_value = SimpleNamespace(
            output_text="  Hola, mundo.\nOtra frase.\n"
        )
        patcher = patch.dict(
            sys.modules, {"app.config": self.config, "google": self.google, "google.genai": self.google.genai}
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

    def test_prompt_requests_exact_word_counts(self):
        prompt = self.generator().PROMPT
        for count in (20, 30, 40):
            self.assertIn(f"Exactamente {count} palabras por frase", prompt)
        self.assertNotIn("Longitud de", prompt)

    def test_group_prompt_uses_observed_counts_for_corrections(self):
        generator = self.generator()
        prompt = generator.group_prompt(Difficulty.ADVANCED, 3, (35, 45, 52))
        self.assertIn("1 por debajo de 40", prompt)
        self.assertIn("2 por encima de 40", prompt)
        self.assertIn("Amplía las cortas y recorta las largas", prompt)

    def test_group_generation_uses_fixed_length_word_arrays(self):
        generator = self.generator()
        words = ["palabra"] * 39 + ["final."]
        self.client.models.generate_content.return_value = SimpleNamespace(
            text=json.dumps([words, words])
        )
        with patch.object(generator, "review_phrases", return_value=[True, True]) as review:
            result = generator.generate_group_text(Difficulty.ADVANCED, 2)
        self.assertEqual([len(line.split()) for line in result.splitlines()], [40, 40])
        review.assert_called_once_with([generator.capitalize_initial(" ".join(words))] * 2)
        call = self.client.models.generate_content.call_args.kwargs
        schema = call["config"]["response_schema"]
        self.assertEqual((schema["min_items"], schema["max_items"]), (6, 6))
        self.assertEqual((schema["items"]["min_items"], schema["items"]["max_items"]), (40, 40))

    def test_group_generation_drops_words_that_break_the_schema(self):
        generator = self.generator()
        valid = ["palabra"] * 19 + ["final."]
        invalid = ["dos palabras"] + valid[1:]
        self.client.models.generate_content.return_value = SimpleNamespace(
            text=json.dumps([invalid, valid])
        )
        with patch.object(generator, "review_phrases", return_value=[True]):
            result = generator.generate_group_text(Difficulty.EASY, 2)
        self.assertEqual(result, generator.capitalize_initial(" ".join(valid)))

    def test_replacement_group_avoids_another_provider_quality_call(self):
        generator = self.generator()
        words = ["palabra"] * 19 + ["final."]
        self.client.models.generate_content.return_value = SimpleNamespace(
            text=json.dumps([words])
        )
        with patch.object(generator, "review_phrases") as review:
            result = generator.generate_group_text(
                Difficulty.EASY, 1, review_quality=False
            )
        self.assertEqual(result, generator.capitalize_initial(" ".join(words)))
        review.assert_not_called()

    def test_group_generation_sends_unfinished_phrases_to_quality_review(self):
        generator = self.generator()
        complete = ["palabra"] * 19 + ["final."]
        unfinished = ["palabra"] * 19 + ["otra"]
        self.client.models.generate_content.return_value = SimpleNamespace(
            text=json.dumps([complete, unfinished, complete])
        )
        with patch.object(generator, "review_phrases", return_value=[False, False, True]) as review:
            result = generator.generate_group_text(Difficulty.EASY, 3)
        self.assertEqual(result, generator.capitalize_initial(" ".join(complete)))
        review.assert_called_once_with([
            generator.capitalize_initial(" ".join(complete)),
            generator.capitalize_initial(" ".join(unfinished)) + ".",
            generator.capitalize_initial(" ".join(complete)),
        ])

    def test_quality_review_requires_one_boolean_decision_per_phrase(self):
        generator = self.generator()
        self.client.models.generate_content.return_value = SimpleNamespace(
            text=json.dumps([{"apta": False, "motivo": "Final abrupto."},
                             {"apta": True, "motivo": "Idea completa."}])
        )
        self.assertEqual(generator.review_phrases(["Frase incompleta.", "Frase natural."]), [False, True])
        self.client.models.generate_content.return_value = SimpleNamespace(
            text=json.dumps([{"apta": True}])
        )
        with self.assertRaisesRegex(ValueError, "one decision per phrase"):
            generator.review_phrases(["Una frase.", "Otra frase."])

    def test_group_generation_retries_temporary_provider_overload(self):
        generator = self.generator()
        error = self.google.genai.errors.ServerError()
        error.code = 503
        words = ["palabra"] * 19 + ["final."]
        self.client.models.generate_content.side_effect = [
            error, SimpleNamespace(text=json.dumps([words]))
        ]
        with patch.object(generator.time, "sleep") as sleep, patch.object(generator, "review_phrases", return_value=[True]):
            result = generator.generate_group_text(Difficulty.EASY, 1)
        self.assertEqual(result, generator.capitalize_initial(" ".join(words)))
        self.assertEqual(self.client.models.generate_content.call_count, 2)
        sleep.assert_called_once_with(1)

    def test_group_generation_waits_for_the_reported_minute_quota_reset(self):
        generator = self.generator()
        error = self.google.genai.errors.ClientError()
        error.code = 429
        error.details = {"error": {"details": [{"retryDelay": "2s"}]}}
        words = ["palabra"] * 19 + ["final."]
        self.client.models.generate_content.side_effect = [
            error, SimpleNamespace(text=json.dumps([words]))
        ]
        with patch.object(generator.time, "sleep") as sleep:
            result = generator.generate_group_text(
                Difficulty.EASY, 1, review_quality=False
            )
        self.assertEqual(result, generator.capitalize_initial(" ".join(words)))
        self.assertEqual(self.client.models.generate_content.call_count, 2)
        sleep.assert_called_once_with(3)

    def test_generate_endpoint_explains_an_exhausted_provider_quota(self):
        from fastapi import HTTPException
        from app.routers.texts import generate_texts

        error = self.google.genai.errors.ClientError()
        error.code = 429
        with patch.object(TextFacade, "generate_phrases", side_effect=error):
            with self.assertRaises(HTTPException) as caught:
                generate_texts()
        self.assertEqual(caught.exception.status_code, 429)
        self.assertIn("Espera un minuto", caught.exception.detail)
        self.assertEqual(caught.exception.headers["Retry-After"], "60")

    def test_revise_phrase_requests_multiple_exact_versions(self):
        generator = self.generator()
        with patch.object(generator, "generate_text", return_value=" Frase revisada. \n Otra versión. ") as generate:
            self.assertEqual(
                generator.revise_phrase(Difficulty.ADVANCED, "Tema original.", 31),
                ["Frase revisada.", "Otra versión."],
            )
        prompt = generate.call_args.args[0]
        self.assertIn("Amplía", prompt)
        self.assertIn("Tema original.", prompt)
        self.assertIn("exactamente 40", prompt)
        self.assertIn("seis versiones", prompt)

    @staticmethod
    def group_lines(word_count, start=0, count=10):
        lines = []
        for index in range(start, start + count):
            words = ["alfa" * (index + 1), *(["palabra"] * (word_count - 1))]
            if word_count >= 30:
                words[1:4] = ["rápido", "camino,", "pueblo,"]
            if word_count >= 40:
                words[4:8] = ["fácil", "2025", "viaje;", "destino,"]
            lines.append(" ".join(words) + ".")
        return "\n".join(lines)

    def test_generated_levels_require_increasing_typing_features(self):
        matches = self.generator().matches_typing_difficulty
        plain = " ".join(["palabra"] * 40) + "."
        medium = self.generator().capitalize_initial(self.group_lines(30, count=1))
        advanced = self.generator().capitalize_initial(self.group_lines(40, count=1))
        self.assertFalse(matches(plain, Difficulty.MEDIUM))
        self.assertFalse(matches(plain, Difficulty.ADVANCED))
        self.assertTrue(matches(medium, Difficulty.MEDIUM))
        self.assertFalse(matches(medium, Difficulty.ADVANCED))
        self.assertTrue(matches(advanced, Difficulty.ADVANCED))

    def test_generation_capitalizes_the_initial_without_changing_other_words(self):
        capitalize = self.generator().capitalize_initial
        self.assertEqual(capitalize("ella busca sus llaves."), "Ella busca sus llaves.")
        self.assertEqual(capitalize("¿por qué llegaste tarde?"), "¿Por qué llegaste tarde?")
        self.assertEqual(capitalize("¡qué sorpresa!"), "¡Qué sorpresa!")
        self.assertEqual(len(capitalize("ella busca sus llaves.").split()), 4)

    def test_generation_rejects_isolated_closing_words_and_bad_colons(self):
        complete = self.generator().has_complete_ending
        self.assertFalse(complete("La reunión terminó temprano. ¡Adelante!"))
        self.assertFalse(complete("La reunión terminó temprano? hoy."))
        self.assertFalse(complete("Los expertos afirman que: la obra es valiosa."))
        self.assertTrue(complete("La reunión terminó temprano y todos volvieron a casa."))

    def test_generation_requests_small_groups_and_returns_only_valid_phrases(self):
        generator = self.generator()
        outputs = [self.group_lines(count) for count in (20, 30, 40)]
        with patch.object(generator, "generate_group_text", side_effect=outputs) as generate:
            phrases = TextFacade().generate_phrases()
        self.assertEqual(len(phrases), 30)
        self.assertEqual([len(phrase.split()) for phrase in phrases], [20] * 10 + [30] * 10 + [40] * 10)
        self.assertTrue(all(phrase[0].isupper() for phrase in phrases))
        self.assertEqual(
            [call.args for call in generate.call_args_list],
            [(Difficulty.EASY, 10, ()), (Difficulty.MEDIUM, 10, ()), (Difficulty.ADVANCED, 10, ())],
        )
        self.assertTrue(all(call.kwargs["review_quality"] for call in generate.call_args_list))

    def test_generation_repairs_short_phrases_before_returning(self):
        generator = self.generator()
        outputs = [
            self.group_lines(20, count=8) + "\n" + self.group_lines(17, start=8, count=2),
            self.group_lines(30),
            self.group_lines(40),
        ]
        repairs = [[self.group_lines(20, start=index, count=1)] for index in (8, 9)]
        with (
            patch.object(generator, "generate_group_text", side_effect=outputs) as generate,
            patch.object(generator, "revise_phrase", side_effect=repairs) as revise,
        ):
            phrases = TextFacade().generate_phrases()
        self.assertEqual(len(phrases), 30)
        self.assertEqual([len(phrase.split()) for phrase in phrases[:10]], [20] * 10)
        self.assertEqual(generate.call_count, 3)
        self.assertEqual(revise.call_count, 2)

    def test_generation_selects_an_exact_revision_among_imperfect_versions(self):
        generator = self.generator()
        outputs = [
            self.group_lines(20, count=9) + "\n" + self.group_lines(17, start=9, count=1),
            self.group_lines(30),
            self.group_lines(40),
        ]
        revisions = [
            self.group_lines(18, start=9, count=1),
            self.group_lines(20, start=9, count=1),
        ]
        with (
            patch.object(generator, "generate_group_text", side_effect=outputs),
            patch.object(generator, "revise_phrase", return_value=revisions) as revise,
        ):
            phrases = TextFacade().generate_phrases()
        self.assertEqual(len(phrases), 30)
        self.assertEqual(len(phrases[9].split()), 20)
        revise.assert_called_once()

    def test_generation_retries_plain_medium_phrases(self):
        generator = self.generator()
        plain = " ".join(["palabra"] * 30) + "."
        outputs = [
            self.group_lines(20),
            self.group_lines(30, count=9) + "\n" + plain,
            self.group_lines(30, start=9, count=1),
            self.group_lines(40),
        ]
        with patch.object(generator, "generate_group_text", side_effect=outputs) as generate:
            phrases = TextFacade().generate_phrases()
        self.assertEqual(len(phrases), 30)
        self.assertNotIn(plain, phrases)
        self.assertEqual(generate.call_args_list[2].args[0:2], (Difficulty.MEDIUM, 1))

    def test_generation_retries_when_a_repair_stays_short(self):
        generator = self.generator()
        outputs = [
            self.group_lines(20, count=8) + "\n" + self.group_lines(17, start=8, count=2),
            self.group_lines(20, start=8, count=2),
            self.group_lines(30),
            self.group_lines(40),
        ]
        with (
            patch.object(generator, "generate_group_text", side_effect=outputs) as generate,
            patch.object(generator, "revise_phrase", side_effect=lambda _level, content, _count: [content]),
        ):
            phrases = TextFacade().generate_phrases()
        self.assertEqual(len(phrases), 30)
        self.assertEqual(generate.call_args_list[1].args, (Difficulty.EASY, 2, (20,) * 8 + (17,) * 2))
        self.assertFalse(generate.call_args_list[1].kwargs["review_quality"])

    def test_generation_fails_if_a_group_never_meets_its_range(self):
        generator = self.generator()
        with (
            patch.object(generator, "generate_group_text", return_value=self.group_lines(17)) as generate,
            patch.object(generator, "revise_phrase", side_effect=lambda _level, content, _count: [content]),
        ):
            with self.assertRaisesRegex(RuntimeError, "ten valid easy phrases"):
                TextFacade().generate_phrases()
        self.assertEqual(generate.call_count, 8)

    def test_generated_groups_accept_exact_counts_and_reject_outliers(self):
        phrases = [" ".join(["practicar"] * count) + "." for count in (20, 30, 40)]
        summary = load_phrases(
            phrases, "spa", dry_run=True,
            expected_word_ranges=((20, 20), (30, 30), (40, 40)),
        )
        self.assertEqual([item.status for item in summary.phrases], ["valid"] * 3)
        self.assertEqual([item.difficulty.value for item in summary.phrases], ["easy", "medium", "advanced"])

        outliers = [" ".join(["practicar"] * count) + "." for count in (19, 31, 41)]
        rejected = load_phrases(
            outliers, "spa", dry_run=True,
            expected_word_ranges=((20, 20), (30, 30), (40, 40)),
        )
        self.assertEqual([item.status for item in rejected.phrases], ["rejected"] * 3)
        self.assertEqual([item.reason_code for item in rejected.phrases], ["word_count_mismatch"] * 3)

    def test_save_batch_accepts_only_exact_counts(self):
        for word_count, expected in ((20, "valid"), (30, "valid"), (40, "valid"), (19, "rejected"), (29, "rejected"), (31, "rejected"), (41, "rejected")):
            with self.subTest(word_count=word_count):
                phrase = " ".join(["practicar"] * word_count) + "."
                summary = load_phrases(
                    [phrase], "spa", dry_run=True,
                    allowed_word_counts=frozenset({20, 30, 40}),
                )
                self.assertEqual(summary.phrases[0].status, expected)

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
        self.client.interactions.create.return_value.output_text = " Hola ,mundo. Practicar cada día mejora la velocidad al escribir. "
        facade = TextFacade()
        raw = facade.generate()
        context = facade.process(raw, "spa")
        self.assertEqual(raw, " Hola ,mundo. Practicar cada día mejora la velocidad al escribir. ")
        self.assertEqual(context.content, self.PHRASE)
        self.assertIsNotNone(context.classification)

    def test_generated_text_can_be_explicitly_persisted(self):
        self.client.interactions.create.return_value.output_text = " Hola ,mundo. Practicar cada día mejora la velocidad al escribir. "
        expected = TextFacade().process(self.PHRASE, "spa")
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
assert TextFacade().process('Hola, mundo. Practicar cada día mejora la velocidad al escribir.', 'spa').classification is not None
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
