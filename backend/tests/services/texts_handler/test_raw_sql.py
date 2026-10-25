"""Raw SQL contracts are tested without loading database configuration."""

import ast
from pathlib import Path
import unittest
from unittest.mock import Mock

from app.services.texts_handler.handler import duplicate, persist

ROOT = Path(__file__).resolve().parents[3]


def connector_function():
    tree = ast.parse((ROOT / "app/database.py").read_text())
    function = next(
        (
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "execute_sql"
        ),
        None,
    )
    if function is None:
        raise AssertionError("The existing connector must expose execute_sql.")
    namespace = {}
    module = ast.Module(
        body=[
            ast.ImportFrom(
                module="__future__", names=[ast.alias(name="annotations")], level=0
            ),
            function,
        ],
        type_ignores=[],
    )
    exec(compile(ast.fix_missing_locations(module), "connector", "exec"), namespace)
    return namespace["execute_sql"]


class RawSqlTests(unittest.TestCase):
    def test_existing_connector_passes_sql_and_parameters_directly_to_driver(self):
        execute_sql = connector_function()
        db = Mock(spec=("connection", "commit", "rollback", "close"))
        sql = "SELECT id FROM texts WHERE content = %(content)s LIMIT 1"
        parameters = {"content": "Don't interpolate this."}
        result = execute_sql(db, sql, parameters)
        self.assertIs(result, db.connection.return_value.exec_driver_sql.return_value)
        db.connection.assert_called_once_with()
        db.connection.return_value.exec_driver_sql.assert_called_once_with(
            sql, parameters
        )
        db.commit.assert_not_called()
        db.rollback.assert_not_called()
        db.close.assert_not_called()

    def test_duplicate_statement_is_explicit_parameterized_sql(self):
        sql = " ".join(duplicate.DUPLICATE_SQL.split())
        self.assertEqual(
            sql, "SELECT id FROM texts WHERE content = %(content)s LIMIT 1"
        )

    def test_insert_uses_schema_enum_names_and_returning(self):
        sql = " ".join(persist.INSERT_SQL.split())
        self.assertIn("INSERT INTO texts", sql)
        self.assertIn("CAST(%(language)s AS text_language)", sql)
        self.assertIn("CAST(%(difficulty)s AS difficulty)", sql)
        self.assertIn(
            "RETURNING id, content, language, difficulty, ideal_time_ms, record_user_id",
            sql,
        )

    def test_handlers_have_no_orm_or_sql_builder_operations(self):
        for filename in ("duplicate.py", "persist.py"):
            with self.subTest(filename=filename):
                tree = ast.parse(
                    (ROOT / "app/services/texts_handler/handler" / filename).read_text()
                )
                for node in ast.walk(tree):
                    if isinstance(node, ast.ImportFrom):
                        self.assertNotEqual(node.module, "app.models.text")
                    if isinstance(node, ast.Call):
                        if isinstance(node.func, ast.Name):
                            self.assertNotIn(node.func.id, ("select", "text", "Text"))
                        if isinstance(node.func, ast.Attribute):
                            self.assertNotIn(
                                node.func.attr,
                                ("add", "flush", "refresh", "query", "where", "limit"),
                            )


if __name__ == "__main__":
    unittest.main()
