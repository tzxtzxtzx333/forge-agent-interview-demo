from __future__ import annotations

from unittest.mock import MagicMock, patch

from llm.base import LLMResponse
from llm.provider_matrix import PROVIDER_MATRIX, build_smoke_command
from llm.provider_smoke import (
    get_missing_prerequisite_reason,
    is_ollama_server_available,
    run_provider_smoke,
)
from llm.router import _ENV_KEY_MAP, _PROVIDER_BASE_URLS


class TestProviderMatrixStructure:
    def test_all_expected_providers_exist(self):
        assert set(PROVIDER_MATRIX) == {
            "anthropic",
            "openai",
            "deepseek",
            "groq",
            "ollama",
        }

    def test_entries_have_required_fields(self):
        required = {
            "env_var",
            "local_dependency",
            "default_base_url",
            "tool_calling_support",
            "streaming_support",
            "text_fallback_support",
            "known_limitations",
        }
        for entry in PROVIDER_MATRIX.values():
            assert required.issubset(entry.keys())
            assert isinstance(entry["known_limitations"], list)

    def test_router_config_matches_matrix(self):
        for provider, entry in PROVIDER_MATRIX.items():
            assert entry["env_var"] == _ENV_KEY_MAP[provider]
            assert entry["default_base_url"] == _PROVIDER_BASE_URLS[provider]


class TestSmokeCommandConstruction:
    def test_build_smoke_command(self):
        command = build_smoke_command("ollama", "llama3")
        assert command == "python scripts/smoke_provider.py --provider ollama --model llama3"


class TestSmokePreflight:
    def test_missing_key_message_for_remote_provider(self):
        reason = get_missing_prerequisite_reason(
            "deepseek",
            env={},
        )
        assert reason == "Missing required environment variable: DEEPSEEK_API_KEY"

    def test_ollama_unavailable_message(self):
        with patch("llm.provider_smoke.is_ollama_server_available", return_value=False):
            reason = get_missing_prerequisite_reason(
                "ollama",
                env={},
                base_url="http://localhost:11434/v1",
            )
        assert "Ollama is not reachable" in reason

    def test_ollama_available_message_is_none(self):
        with patch("llm.provider_smoke.is_ollama_server_available", return_value=True):
            reason = get_missing_prerequisite_reason(
                "ollama",
                env={},
                base_url="http://localhost:11434/v1",
            )
        assert reason is None


class TestProviderSmokeRunner:
    def test_missing_key_returns_skip(self):
        result = run_provider_smoke("openai", "gpt-4o", env={})
        assert result.status == "skip"
        assert "OPENAI_API_KEY" in result.message

    def test_backend_import_error_returns_skip(self):
        with patch("llm.provider_smoke.create_backend", side_effect=ImportError("openai package not installed")):
            result = run_provider_smoke(
                "openai",
                "gpt-4o",
                env={"OPENAI_API_KEY": "sk-test"},
            )
        assert result.status == "skip"
        assert "openai package not installed" in result.message

    def test_smoke_success_path(self):
        backend = MagicMock()
        backend.complete.return_value = LLMResponse(
            action=MagicMock(),
            raw_content="pong",
            input_tokens=1,
            output_tokens=1,
        )
        with patch("llm.provider_smoke.create_backend", return_value=backend):
            result = run_provider_smoke(
                "deepseek",
                "deepseek-chat",
                env={"DEEPSEEK_API_KEY": "sk-test"},
            )
        assert result.status == "ok"
        assert "deepseek/deepseek-chat" in result.message

    def test_connection_error_becomes_skip(self):
        backend = MagicMock()
        backend.complete.side_effect = ConnectionError("connection refused")
        with patch("llm.provider_smoke.create_backend", return_value=backend):
            result = run_provider_smoke(
                "deepseek",
                "deepseek-chat",
                env={"DEEPSEEK_API_KEY": "sk-test"},
            )
        assert result.status == "skip"
        assert "service is unavailable" in result.message.lower()


class TestOllamaAvailabilityProbe:
    def test_probe_false_on_url_error(self):
        with patch("urllib.request.urlopen", side_effect=OSError("down")):
            assert not is_ollama_server_available("http://localhost:11434/v1")
