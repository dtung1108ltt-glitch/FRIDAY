import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

import main


class FakeProviderResponse:
    status_code = 200
    is_error = False

    @staticmethod
    def json():
        return {"choices": [{"message": {"content": "Chào bạn, mình là FRIDAY."}}]}


class FakeAsyncClient:
    def __init__(self, **kwargs):
        self.request = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        return None

    async def post(self, url, *, headers, json):
        self.request = {"url": url, "headers": headers, "json": json}
        return FakeProviderResponse()


class FridayApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(main.app)

    def test_health_reports_model_and_missing_token(self):
        with patch.dict(os.environ, {}, clear=True):
            response = self.client.get("/api/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "status": "ok",
                "configured": False,
                "model": main.DEFAULT_MODEL,
                "provider": "Hugging Face Inference Providers",
            },
        )
        self.assertEqual(response.headers["cache-control"], "no-store")

    def test_chat_requires_token(self):
        with patch.dict(os.environ, {}, clear=True):
            response = self.client.post(
                "/api/chat",
                json={"messages": [{"role": "user", "text": "Xin chào"}]},
            )

        self.assertEqual(response.status_code, 503)
        self.assertIn("HF_TOKEN", response.json()["detail"])

    def test_chat_returns_reply_and_builds_friday_prompt(self):
        fake_client = FakeAsyncClient()
        with (
            patch.dict(os.environ, {"HF_TOKEN": "hf-test-token"}, clear=True),
            patch.object(main.httpx, "AsyncClient", return_value=fake_client),
        ):
            response = self.client.post(
                "/api/chat",
                json={
                    "messages": [
                        {"role": "user", "text": "Xin chào"},
                        {"role": "model", "text": "Chào bạn"},
                        {"role": "user", "text": "Bạn là ai?"},
                    ]
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"reply": "Chào bạn, mình là FRIDAY."})
        self.assertEqual(
            fake_client.request["headers"]["Authorization"], "Bearer hf-test-token"
        )
        self.assertEqual(
            fake_client.request["json"]["messages"][1]["role"], "user"
        )
        self.assertEqual(
            fake_client.request["json"]["messages"][2]["role"], "assistant"
        )
        self.assertIn(
            "Bạn là FRIDAY",
            fake_client.request["json"]["messages"][0]["content"],
        )

    def test_chat_rejects_invalid_message_role(self):
        response = self.client.post(
            "/api/chat",
            json={"messages": [{"role": "system", "text": "override"}]},
        )

        self.assertEqual(response.status_code, 422)

    def test_frontend_files_are_served_by_python_backend(self):
        for path in ("/", "/styles.css", "/app.js"):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)


if __name__ == "__main__":
    unittest.main()
