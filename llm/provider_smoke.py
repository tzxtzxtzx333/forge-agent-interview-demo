"""
Provider smoke helpers.
"""

from __future__ import annotations

import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

from llm.base import LLMMessage
from llm.provider_matrix import get_provider_entry
from llm.router import create_backend


DEFAULT_PROMPT = "Reply with exactly: pong"


@dataclass
class SmokeResult:
    status: str
    message: str

    @property
    def exit_code(self) -> int:
        if self.status == "ok":
            return 0
        if self.status == "skip":
            return 2
        return 1


def get_missing_prerequisite_reason(
    provider: str,
    env: dict[str, str] | None = None,
    base_url: str | None = None,
) -> str | None:
    runtime_env = env if env is not None else os.environ
    entry = get_provider_entry(provider)
    provider_name = provider.lower().strip()
    env_var = str(entry["env_var"])

    if provider_name != "ollama" and not runtime_env.get(env_var):
        return f"Missing required environment variable: {env_var}"

    if provider_name == "ollama":
        resolved_base_url = base_url or str(entry["default_base_url"])
        if not is_ollama_server_available(resolved_base_url):
            return (
                f"Ollama is not reachable at {resolved_base_url}. "
                f"Start the local server with 'ollama serve'."
            )

    return None


def is_ollama_server_available(base_url: str, timeout: float = 2.0) -> bool:
    parsed = urllib.parse.urlparse(base_url)
    root_path = parsed.path
    if root_path.endswith("/v1"):
        root_path = root_path[:-3]
    tags_path = (root_path.rstrip("/") + "/api/tags") or "/api/tags"
    probe_url = urllib.parse.urlunparse(
        (parsed.scheme, parsed.netloc, tags_path, "", "", "")
    )
    try:
        with urllib.request.urlopen(probe_url, timeout=timeout) as response:
            return 200 <= getattr(response, "status", 0) < 300
    except (urllib.error.URLError, TimeoutError, ValueError, OSError):
        return False


def run_provider_smoke(
    provider: str,
    model: str,
    *,
    base_url: str | None = None,
    env: dict[str, str] | None = None,
    prompt: str = DEFAULT_PROMPT,
) -> SmokeResult:
    runtime_env = env if env is not None else os.environ
    normalized = provider.lower().strip()
    reason = get_missing_prerequisite_reason(
        normalized,
        env=runtime_env,
        base_url=base_url,
    )
    if reason:
        return SmokeResult(status="skip", message=reason)

    entry = get_provider_entry(normalized)
    api_key = runtime_env.get(str(entry["env_var"])) or None

    try:
        backend = create_backend(
            provider=normalized,
            model=model,
            api_key=api_key,
            base_url=base_url,
            max_tokens=64,
        )
    except (ImportError, ValueError) as exc:
        return SmokeResult(status="skip", message=str(exc))

    try:
        response = backend.complete(
            [LLMMessage(role="user", content=prompt)],
            [],
        )
    except Exception as exc:
        classified = _classify_runtime_exception(normalized, exc)
        if classified is not None:
            return SmokeResult(status="skip", message=classified)
        return SmokeResult(status="error", message=str(exc))

    content = (response.raw_content or "").strip()
    snippet = content[:80] if content else "(empty response)"
    return SmokeResult(
        status="ok",
        message=f"Provider smoke passed for {normalized}/{model}. Response: {snippet}",
    )


def _classify_runtime_exception(provider: str, exc: Exception) -> str | None:
    text = str(exc).lower()
    connection_markers = (
        "connection",
        "timed out",
        "timeout",
        "max retries exceeded",
        "name resolution",
        "nodename nor servname",
        "connection refused",
        "failed to establish",
    )
    if any(marker in text for marker in connection_markers):
        if provider == "ollama":
            return (
                "Ollama request failed because the local service is unavailable. "
                "Start 'ollama serve' and retry."
            )
        return "Provider smoke skipped because the remote service is unavailable."
    return None
