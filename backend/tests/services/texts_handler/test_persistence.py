"""Database orchestration uses mocks only; no credentials or network access."""

import ast
import importlib
from pathlib import Path
import subprocess
import sys
import types
import unittest
from dataclasses import FrozenInstanceError
from unittest.mock import Mock, call, patch

from app.services.texts_handler import TextFacade
from app.services.texts_handler.context import TextContext
from app.services.texts_handler.errors import TextDatabaseError, TextValidationError
from app.services.texts_handler.processing.classiffy import ClassifyTextStep
from app.services.texts_handler.processing.duplicate import DUPLICATE_SQL
from app.services.texts_handler.processing.persist import INSERT_SQL, PersistedText
from app.text_enums import Difficulty, Language

SESSION_METHODS = ("connection", "commit", "rollback", "close")


def connector_function():
    """Load only the actual connector function, never settings or engine setup."""
    source = Path(__file__).resolve().parents[3] / "app/database.py"
    tree = ast.parse(source.read_text())
    function = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "execute_sql"
    )
    module = ast.Module(
        body=[
            ast.ImportFrom(
                module="__future__", names=[ast.alias(name="annotations")], level=0
            ),
            function,
        ],
        type_ignores=[],
    )
    namespace = {}
    exec(compile(ast.fix_missing_locations(module), "connector", "exec"), namespace)
    return namespace["execute_sql"]


class PersistenceTests(unittest.TestCase):
    def setUp(self):
        self.reset_database()
        connector = types.ModuleType("app.database")
        connector.execute_sql = connector_function()
        patcher = patch.dict(sys.modules, {"app.database": connector})
        patcher.start()
        self.addCleanup(patcher.stop)

    def reset_database(self):
        self.db = Mock(spec=SESSION_METHODS)
        self.connection = self.db.connection.return_value
        self.lookup = Mock(name="lookup_result")
        self.lookup.scalar.return_value = None
        self.insert = Mock(name="insert_result")
        self.row = {
            "id": 42,
            "content": "Hello, world.",
            "language": "eng",
            "difficulty": TextFacade().process("Hello, world.", "eng").difficulty.value,
            "ideal_time_ms": None,
            "record_user_id": None,
        }
        self.insert.mappings.return_value.one.return_value = self.row
        self.connection.exec_driver_sql.side_effect = self.execute

    def execute(self, statement, parameters):
        if statement == DUPLICATE_SQL:
            return self.lookup
        if statement == INSERT_SQL:
            return self.insert
        self.fail("Unexpected SQL statement.")

    def handlers(self):
        duplicate = importlib.import_module(
            "app.services.texts_handler.processing.duplicate"
        )
        persist = importlib.import_module(
            "app.services.texts_handler.processing.persist"
        )
        return duplicate, persist

    def create(self, content=" Hello ,world. ", language="eng"):
        return TextFacade(self.db).create(content, language)

    def checked_context(self):
        duplicate, _ = self.handlers()
        context = TextFacade().process("Hello.", "eng")
        duplicate.CheckDuplicateTextStep(self.db).handle(context)
        return context

    def test_missing_session_is_explicit(self):
        with self.assertRaisesRegex(RuntimeError, "database session"):
            TextFacade().create("Hello.", "eng")

    def test_create_commits_in_order_and_returns_detached_snapshot(self):
        result = self.create()
        self.assertIsInstance(result, PersistedText)
        self.assertEqual(result.id, 42)
        self.assertEqual(result.content, "Hello, world.")
        self.assertEqual(result.language, Language.ENG)
        self.assertEqual(result.difficulty.value, self.row["difficulty"])
        self.assertIsNone(result.ideal_time_ms)
        self.assertIsNone(result.record_user_id)
        self.assertEqual(
            self.db.mock_calls,
            [
                call.connection(),
                call.connection().exec_driver_sql(
                    DUPLICATE_SQL, {"content": "Hello, world."}
                ),
                call.connection(),
                call.connection().exec_driver_sql(
                    INSERT_SQL,
                    {
                        "content": "Hello, world.",
                        "language": "eng",
                        "difficulty": self.row["difficulty"],
                    },
                ),
                call.commit(),
            ],
        )
        self.lookup.scalar.assert_called_once_with()
        self.insert.mappings.return_value.one.assert_called_once_with()
        self.db.close.assert_not_called()
        with self.assertRaises(FrozenInstanceError):
            result.id = 43

    def test_creation_chain_has_five_stages(self):
        current = TextFacade(self.db).creation_chain
        names = []
        while current:
            names.append(type(current).__name__)
            current = current.next
        self.assertEqual(
            names,
            [
                "ValidateTextStep",
                "NormalizeTextStep",
                "CheckDuplicateTextStep",
                "ClassifyTextStep",
                "PersistTextStep",
            ],
        )

    def test_creation_runs_each_stage_once_and_in_order(self):
        duplicate, persist = self.handlers()
        from app.services.texts_handler.processing.normalize import NormalizeTextStep
        from app.services.texts_handler.processing.validate import ValidateTextStep
        from contextlib import ExitStack

        classes = (
            ValidateTextStep,
            NormalizeTextStep,
            duplicate.CheckDuplicateTextStep,
            ClassifyTextStep,
            persist.PersistTextStep,
        )
        events = []

        def observe(cls, method):
            def handle(instance, context):
                events.append(cls.__name__)
                return method(instance, context)

            return handle

        with ExitStack() as stack:
            for cls in classes:
                stack.enter_context(
                    patch.object(cls, "handle", observe(cls, cls.handle))
                )
            self.create()
        self.assertEqual(events, [cls.__name__ for cls in classes])

    def test_canonical_comparison_keeps_case_and_has_no_language_argument(self):
        for content, language, expected in (
            (" Hola   mundo. ", "spa", "Hola mundo."),
            ("hola mundo.", "eng", "hola mundo."),
            (" ‘Hola’ ", "spa", "'Hola'"),
        ):
            with self.subTest(content=content):
                self.connection.exec_driver_sql.reset_mock()
                self.create(content, language)
                self.assertEqual(
                    self.connection.exec_driver_sql.call_args_list[0],
                    call(DUPLICATE_SQL, {"content": expected}),
                )
                insert_params = self.connection.exec_driver_sql.call_args_list[1].args[
                    1
                ]
                self.assertEqual(insert_params["content"], expected)
                self.assertEqual(insert_params["language"], language)
                self.assertIs(type(insert_params["language"]), str)
                self.assertIs(type(insert_params["difficulty"]), str)

    def test_facade_only_invokes_first_handler_for_creation(self):
        facade = TextFacade(self.db)
        result = object()

        def complete(context):
            context.persisted_text = result

        with patch.object(
            facade.creation_chain, "handle", side_effect=complete
        ) as first:
            self.assertIs(facade.create("Hello.", "eng"), result)
        first.assert_called_once()
        self.assertEqual(self.db.mock_calls, [])

    def test_duplicate_uses_canonical_content_and_stops_before_classification(self):
        for identifier in (0, 7):
            with self.subTest(identifier=identifier):
                self.db.reset_mock()
                self.lookup.scalar.return_value = identifier
                with patch.object(ClassifyTextStep, "handle") as classify:
                    with self.assertRaises(TextValidationError) as caught:
                        self.create(" Hello   world. ", "eng")
                self.assertEqual(caught.exception.code, "duplicate_content")
                self.connection.exec_driver_sql.assert_called_once_with(
                    DUPLICATE_SQL, {"content": "Hello world."}
                )
                classify.assert_not_called()
                self.db.commit.assert_not_called()

    def test_invalid_input_never_queries_database(self):
        for content in ("🙂", "a." * 2000):
            with self.subTest(content=content[:10]):
                with self.assertRaises(TextValidationError):
                    self.create(content)
                self.db.connection.assert_not_called()

    def test_lookup_failure_rolls_back_and_preserves_cause(self):
        failure = RuntimeError("private database details")
        self.lookup.scalar.side_effect = failure
        with self.assertRaises(TextDatabaseError) as caught:
            self.create()
        self.assertIs(caught.exception.__cause__, failure)
        self.assertNotIn("private", str(caught.exception))
        self.db.rollback.assert_called_once()
        self.db.commit.assert_not_called()
        self.connection.exec_driver_sql.assert_called_once()

    def test_write_failures_roll_back_without_success(self):
        for operation in ("connection", "execute", "mappings", "row", "commit"):
            with self.subTest(operation=operation):
                self.reset_database()
                context = self.checked_context()
                failure = RuntimeError(f"{operation} private detail")
                if operation == "connection":
                    self.db.connection.side_effect = failure
                elif operation == "execute":
                    self.connection.exec_driver_sql.side_effect = failure
                elif operation == "mappings":
                    self.insert.mappings.side_effect = failure
                elif operation == "row":
                    self.insert.mappings.return_value.one.side_effect = failure
                else:
                    self.db.commit.side_effect = failure
                _, persist = self.handlers()
                with self.assertRaises(TextDatabaseError) as caught:
                    persist.PersistTextStep(self.db).handle(context)
                self.assertIs(caught.exception.__cause__, failure)
                self.db.rollback.assert_called_once()
                self.db.close.assert_not_called()
                self.assertIsNone(context.persisted_text)
                if operation != "commit":
                    self.db.commit.assert_not_called()

    def test_failed_write_leaves_context_without_persisted_result(self):
        _, persist = self.handlers()
        context = self.checked_context()
        self.db.commit.side_effect = RuntimeError("constraint failure")
        with self.assertRaises(TextDatabaseError) as caught:
            persist.PersistTextStep(self.db).handle(context)
        self.assertEqual(caught.exception.code, "database_error")
        self.assertIsNone(context.persisted_text)

    def test_rollback_failure_preserves_original_database_cause(self):
        failure = RuntimeError("write failure")
        self.db.commit.side_effect = failure
        self.db.rollback.side_effect = RuntimeError("rollback failure")
        with self.assertRaises(TextDatabaseError) as caught:
            self.create()
        self.assertIs(caught.exception.__cause__, failure)
        self.assertEqual(caught.exception.code, "database_error")

    def test_injection_like_content_is_never_interpolated_into_sql(self):
        content = "Don't; DROP TABLE texts;"
        self.create(content)
        calls = self.connection.exec_driver_sql.call_args_list
        self.assertEqual(
            [entry.args[0] for entry in calls], [DUPLICATE_SQL, INSERT_SQL]
        )
        for entry in calls:
            self.assertEqual(entry.args[1]["content"], content)
            self.assertNotIn(content, entry.args[0])

    def test_returned_row_decoding_error_rolls_back_before_commit(self):
        self.row["difficulty"] = "not-a-level"
        with self.assertRaises(TextDatabaseError) as caught:
            self.create()
        self.assertIsInstance(caught.exception.__cause__, ValueError)
        self.db.rollback.assert_called_once()
        self.db.commit.assert_not_called()

    def test_returned_row_is_the_source_of_the_snapshot(self):
        self.row.update(
            id=19,
            content="Database returned this.",
            language="spa",
            difficulty="expert",
        )
        result = self.create()
        self.assertEqual(
            (result.id, result.content, result.language, result.difficulty),
            (19, "Database returned this.", Language.SPA, Difficulty.EXPERT),
        )

    def test_steps_require_predecessors_before_io(self):
        duplicate, persist = self.handlers()
        raw = TextContext("Hello.", "eng")
        with self.assertRaises(TextValidationError):
            duplicate.CheckDuplicateTextStep(self.db).handle(raw)
        classified = TextFacade().process("Hello.", "eng")
        with self.assertRaises(TextValidationError):
            persist.PersistTextStep(self.db).handle(classified)
        self.assertEqual(self.db.mock_calls, [])

    def test_changed_context_after_duplicate_check_cannot_be_saved(self):
        _, persist = self.handlers()
        for attribute, value in (
            ("content", "Other."),
            ("language", "spa"),
            ("difficulty", Difficulty.EXPERT),
        ):
            with self.subTest(attribute=attribute):
                context = self.checked_context()
                self.db.reset_mock()
                setattr(context, attribute, value)
                with self.assertRaises(TextValidationError):
                    persist.PersistTextStep(self.db).handle(context)
                self.assertEqual(self.db.mock_calls, [])

    def test_check_with_different_session_cannot_be_reused(self):
        _, persist = self.handlers()
        context = self.checked_context()
        other = Mock(spec=SESSION_METHODS)
        with self.assertRaises(TextValidationError):
            persist.PersistTextStep(other).handle(context)
        self.assertEqual(other.mock_calls, [])

    def test_terminal_persist_does_not_delegate_after_commit(self):
        _, persist = self.handlers()
        context = self.checked_context()
        handler = persist.PersistTextStep(self.db)
        following = Mock()
        handler.set_next(following)
        handler.handle(context)
        following.handle.assert_not_called()
        self.assertIsInstance(context.persisted_text, PersistedText)

    def test_same_context_cannot_be_persisted_twice(self):
        _, persist = self.handlers()
        context = self.checked_context()
        handler = persist.PersistTextStep(self.db)
        handler.handle(context)
        with self.assertRaises(TextValidationError) as caught:
            handler.handle(context)
        self.assertEqual(caught.exception.code, "already_persisted")
        self.db.commit.assert_called_once()

    def test_incomplete_creation_chain_does_not_report_success(self):
        facade = TextFacade(self.db)
        with patch.object(facade.creation_chain, "handle"):
            with self.assertRaisesRegex(RuntimeError, "persisted result"):
                facade.create("Hello.", "eng")

    def test_process_ignores_injected_session(self):
        context = TextFacade(self.db).process("Hello.", "eng")
        self.assertIsNotNone(context.difficulty)
        self.assertEqual(self.db.mock_calls, [])

    def test_imports_and_pure_processing_never_load_database_or_open_network(self):
        code = """
import socket, sys
from unittest.mock import patch
with patch.object(socket.socket, 'connect', side_effect=AssertionError('No network')):
    from app.services.texts_handler import TextFacade
    assert TextFacade().process('Hello.', 'eng').classification is not None
assert 'app.database' not in sys.modules
assert 'app.config' not in sys.modules
assert 'app.models' not in sys.modules
assert 'sqlalchemy' not in sys.modules
"""
        subprocess.run([sys.executable, "-c", code], check=True)


if __name__ == "__main__":
    unittest.main()
