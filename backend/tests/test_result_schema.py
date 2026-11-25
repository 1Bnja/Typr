import os
import unittest

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite://")
os.environ.setdefault("JWT_SECRET", "result-schema-tests-only-secret-not-for-production")

from pydantic import ValidationError

from app.schemas.game import GameParticipantResult
from app.schemas.practice import PracticeMatchCreate, PracticeTextInput
from app.schemas.text import TextInput


class ResultSchemaTests(unittest.TestCase):
    minimum = {"timeMs": 1, "ppm": 0, "precisionPct": 0, "progress": 0}

    def test_accepts_inclusive_result_boundaries(self):
        for values in (self.minimum, {"timeMs": 60_000, "ppm": 60,
                                      "precisionPct": 100, "progress": 1}):
            with self.subTest(values=values):
                result = GameParticipantResult.model_validate(values)
                self.assertEqual(result.model_dump(by_alias=True), values)

    def test_rejects_out_of_range_and_nonfinite_result_metrics(self):
        invalid = {
            "timeMs": (0, -1),
            "ppm": (-1,),
            "precisionPct": (-0.1, 100.1),
            "progress": (-0.01, 1.01),
        }
        for field, values in invalid.items():
            for value in (*values, float("nan"), float("inf"), -float("inf")):
                with self.subTest(field=field, value=value):
                    with self.assertRaises(ValidationError) as error:
                        GameParticipantResult.model_validate({**self.minimum, field: value})
                    self.assertEqual(error.exception.errors()[0]["loc"], (field,))

    def test_text_and_practice_inputs_do_not_declare_record_fields(self):
        for model in (TextInput, PracticeTextInput, PracticeMatchCreate):
            with self.subTest(model=model.__name__):
                properties = model.model_json_schema()["properties"]
                self.assertTrue({"idealTimeMs", "recordUserId"}.isdisjoint(properties))
