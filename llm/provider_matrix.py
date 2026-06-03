"""
Provider capability matrix and smoke command helpers.
"""

from __future__ import annotations

from llm.router import _ENV_KEY_MAP, _PROVIDER_BASE_URLS


PROVIDER_MATRIX: dict[str, dict[str, object]] = {
    "anthropic": {
        "env_var": _ENV_KEY_MAP["anthropic"],
        "local_dependency": "anthropic",
        "default_base_url": _PROVIDER_BASE_URLS["anthropic"],
        "tool_calling_support": "yes",
        "streaming_support": "yes",
        "text_fallback_support": "no",
        "known_limitations": [
            "Streaming accepts on_thought for interface compatibility but ignores it.",
        ],
    },
    "openai": {
        "env_var": _ENV_KEY_MAP["openai"],
        "local_dependency": "openai",
        "default_base_url": _PROVIDER_BASE_URLS["openai"],
        "tool_calling_support": "yes",
        "streaming_support": "yes",
        "text_fallback_support": "no",
        "known_limitations": [
            "Uses the OpenAI chat completions interface only.",
        ],
    },
    "deepseek": {
        "env_var": _ENV_KEY_MAP["deepseek"],
        "local_dependency": "openai",
        "default_base_url": _PROVIDER_BASE_URLS["deepseek"],
        "tool_calling_support": "model-dependent",
        "streaming_support": "yes",
        "text_fallback_support": "yes",
        "known_limitations": [
            "deepseek-reasoner and deepseek-r1 do not use function calling.",
            "Text fallback parses model output instead of native tool calls.",
        ],
    },
    "groq": {
        "env_var": _ENV_KEY_MAP["groq"],
        "local_dependency": "openai",
        "default_base_url": _PROVIDER_BASE_URLS["groq"],
        "tool_calling_support": "yes",
        "streaming_support": "yes",
        "text_fallback_support": "no",
        "known_limitations": [
            "Behavior depends on the selected Groq-hosted model.",
        ],
    },
    "ollama": {
        "env_var": _ENV_KEY_MAP["ollama"],
        "local_dependency": "openai, local ollama serve",
        "default_base_url": _PROVIDER_BASE_URLS["ollama"],
        "tool_calling_support": "model-dependent",
        "streaming_support": "yes",
        "text_fallback_support": "no",
        "known_limitations": [
            "Requires a local Ollama server.",
            "Tool calling depends on the selected local model.",
        ],
    },
}


def get_provider_matrix() -> dict[str, dict[str, object]]:
    return PROVIDER_MATRIX


def get_provider_entry(provider: str) -> dict[str, object]:
    normalized = provider.lower().strip()
    if normalized not in PROVIDER_MATRIX:
        supported = ", ".join(sorted(PROVIDER_MATRIX))
        raise ValueError(f"Unsupported provider '{provider}'. Supported: {supported}")
    return PROVIDER_MATRIX[normalized]


def build_smoke_command(provider: str, model: str) -> str:
    entry = get_provider_entry(provider)
    cmd = f"python scripts/smoke_provider.py --provider {provider} --model {model}"
    default_base_url = entry["default_base_url"]
    if default_base_url:
        return cmd
    return cmd
