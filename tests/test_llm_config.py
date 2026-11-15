"""LLM_URL / LLM_API_KEY / LLM_MODEL configuration, for any OpenAI-compatible server."""

import json
import unittest
from unittest.mock import MagicMock, patch

import httpx
from openai import BadRequestError

from backend import llm_config

LLM_VARS = [
    "LLM_URL", "LLM_API_KEY", "LLM_MODEL", "LLM_TIMEOUT_SECONDS",
    "GOOGLE_API_KEY", "GEMINI_MODEL", "GEMINI_TIMEOUT_SECONDS",
]


def settings_with(**env):
    cleared = {name: "" for name in LLM_VARS}
    with patch.dict("os.environ", {**cleared, **env}):
        return llm_config.read_settings()


class LLMSettingsTests(unittest.TestCase):
    def test_new_variables_choose_the_server_key_and_model(self):
        settings = settings_with(
            LLM_URL="http://localhost:11434/v1", LLM_API_KEY="k", LLM_MODEL="gpt-oss:20b"
        )

        self.assertEqual(settings.url, "http://localhost:11434/v1")
        self.assertEqual(settings.api_key, "k")
        self.assertEqual(settings.model, "gpt-oss:20b")
        self.assertFalse(settings.url_is_default)
        self.assertEqual(settings.provider_label, "http://localhost:11434/v1")

    def test_new_variables_win_over_the_old_gemini_names(self):
        settings = settings_with(
            LLM_API_KEY="new", GOOGLE_API_KEY="old", LLM_MODEL="m-new", GEMINI_MODEL="m-old"
        )

        self.assertEqual((settings.api_key, settings.model), ("new", "m-new"))

    def test_old_gemini_env_files_keep_working(self):
        settings = settings_with(GOOGLE_API_KEY="old-key", GEMINI_MODEL="gemini-x")

        self.assertEqual(settings.url, llm_config.GOOGLE_OPENAI_URL)
        self.assertEqual((settings.api_key, settings.model), ("old-key", "gemini-x"))
        self.assertTrue(settings.is_configured)

    def test_a_local_server_needs_no_key_but_the_default_endpoint_does(self):
        self.assertTrue(settings_with(LLM_URL="http://localhost:11434/v1").is_configured)
        self.assertFalse(settings_with().is_configured)
        self.assertIsNone(llm_config.make_client(settings_with()))

    def test_client_uses_the_configured_url_and_timeout(self):
        settings = settings_with(LLM_URL="http://localhost:9999/v1", LLM_TIMEOUT_SECONDS="120")

        client = llm_config.make_client(settings)

        self.assertEqual(str(client.base_url), "http://localhost:9999/v1/")
        self.assertEqual(client.timeout, 120.0)

    def test_missing_configuration_message_names_the_new_variables(self):
        for name in ("LLM_URL", "LLM_API_KEY", "LLM_MODEL"):
            self.assertIn(name, llm_config.MISSING_CONFIG_MESSAGE)


class JsonHandlingTests(unittest.TestCase):
    def test_plain_fenced_and_wrapped_json_all_parse(self):
        for content in (
            '{"status": "answered"}',
            '```json\n{"status": "answered"}\n```',
            'Here is the JSON:\n{"status": "answered"}\nDone.',
        ):
            self.assertEqual(llm_config.parse_json_object(content), {"status": "answered"})

    def test_non_objects_are_rejected(self):
        for content in ("[1, 2]", "no json here"):
            with self.assertRaises(json.JSONDecodeError):
                llm_config.parse_json_object(content)

    def test_a_server_without_json_mode_is_asked_again_without_it(self):
        refusal = BadRequestError(
            "response_format is not supported",
            response=httpx.Response(400, request=httpx.Request("POST", "http://x")),
            body=None,
        )
        client = MagicMock()
        client.chat.completions.create.side_effect = [refusal, "ok", "ok again"]

        with patch.object(llm_config, "_json_mode_supported", True):
            first = llm_config.chat_json(client, model="m", messages=[])
            second = llm_config.chat_json(client, model="m", messages=[])

        self.assertEqual((first, second), ("ok", "ok again"))
        calls = client.chat.completions.create.call_args_list
        self.assertIn("response_format", calls[0].kwargs)
        # After one refusal, JSON mode is not tried again.
        self.assertNotIn("response_format", calls[1].kwargs)
        self.assertNotIn("response_format", calls[2].kwargs)

    def test_other_bad_requests_are_not_swallowed(self):
        error = BadRequestError(
            "model not found",
            response=httpx.Response(400, request=httpx.Request("POST", "http://x")),
            body=None,
        )
        client = MagicMock()
        client.chat.completions.create.side_effect = error

        with patch.object(llm_config, "_json_mode_supported", True):
            with self.assertRaises(BadRequestError):
                llm_config.chat_json(client, model="m", messages=[])


if __name__ == "__main__":
    unittest.main()
