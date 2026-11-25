import unittest

from fastapi.testclient import TestClient

from app.main import app


class RegistrationValidationTests(unittest.TestCase):
    def test_validation_returns_only_safe_field_and_type(self):
        valid = {
            "username": "fixture_user",
            "email": "fixture-user@example.com",
            "password": "fixture-password",
        }
        cases = (
            ("username", "u2", "string_too_short"),
            ("username", "fixture_username_1234", "string_too_long"),
            ("email", "fixture-invalid-email", "value_error"),
            ("password", "fixture", "string_too_short"),
            ("password", "é" * 40, "value_error"),
        )
        with TestClient(app) as client:
            for field, value, kind in cases:
                with self.subTest(field=field, kind=kind):
                    payload = {**valid, field: value}
                    response = client.post("/api/v1/auth/register", json=payload)
                    self.assertEqual(response.status_code, 422)
                    self.assertTrue(all(value not in response.text for value in payload.values()))
                    self.assertEqual(
                        response.json(), {"detail": [{"loc": ["body", field], "type": kind}]}
                    )

    def test_body_validation_does_not_return_the_submitted_object(self):
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/auth/register",
                json=[{"password": "fixture-password"}],
            )
        self.assertEqual(response.status_code, 422)
        self.assertNotIn("fixture-password", response.text)
        self.assertEqual(
            response.json(), {"detail": [{"loc": ["body"], "type": "model_attributes_type"}]}
        )
