"""
Streaming output tests.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from agent.core import Agent, AgentConfig
from agent.event_log import EventLog
from agent.task import Action, ActionType, Task, ToolCall
from llm.base import LLMMessage, LLMResponse, MockBackend
from tools.base import NoopTool, ToolRegistry


class TestStreamingMixin:
    def test_default_stream_calls_complete(self):
        script = [Action(ActionType.FINISH, "done", message="ok")]
        backend = MockBackend(script)
        collected = []
        result = backend.stream(
            [LLMMessage(role="user", content="go")],
            [],
            on_text=lambda t: collected.append(t),
        )
        assert result.action.action_type == ActionType.FINISH
        assert len(collected) > 0

    def test_stream_returns_llm_response(self):
        script = [Action(ActionType.FINISH, "done", message="ok")]
        backend = MockBackend(script)
        result = backend.stream([LLMMessage(role="user", content="go")], [])
        assert isinstance(result, LLMResponse)


class TestAgentConfigStream:
    def test_stream_default_false(self):
        cfg = AgentConfig()
        assert cfg.stream is False
        assert cfg.stream_callback is None

    def test_stream_can_be_enabled(self):
        cb = lambda t: None
        cfg = AgentConfig(stream=True, stream_callback=cb)
        assert cfg.stream is True
        assert cfg.stream_callback is cb


class TestCoreStreamPath:
    def _make_streaming_backend(self, script):
        backend = MockBackend(script)
        stream_calls = []

        def fake_stream(messages, tools, on_text=None, on_thought=None):
            stream_calls.append(
                {
                    "messages": messages,
                    "on_text": on_text,
                    "on_thought": on_thought,
                }
            )
            if on_thought:
                on_thought("thinking... ")
            if on_text:
                on_text("I will ")
                on_text("fix the ")
                on_text("bug.")
            return backend.complete(messages, tools)

        backend.stream = fake_stream
        backend._stream_calls = stream_calls
        return backend

    def test_stream_true_calls_stream_method(self, tmp_path):
        script = [Action(ActionType.FINISH, "done", message="ok")]
        backend = self._make_streaming_backend(script)

        collected_text = []
        cfg = AgentConfig(
            stream=True,
            stream_callback=lambda t: collected_text.append(t),
        )
        registry = ToolRegistry().register(NoopTool("shell"))
        agent = Agent(backend, registry, cfg)
        task = Task(task_id="st1", description="fix", repo_path=str(tmp_path), max_steps=3)

        with EventLog.create(task, log_dir=str(tmp_path / "logs")) as log:
            result = agent.run(task, log)

        assert result.is_success()
        assert len(backend._stream_calls) >= 1
        assert "".join(collected_text) == "I will fix the bug."

    def test_stream_false_calls_complete(self, tmp_path):
        script = [Action(ActionType.FINISH, "done", message="ok")]
        backend = self._make_streaming_backend(script)
        original_complete_count = [0]
        original_complete = backend.complete

        def counting_complete(messages, tools):
            original_complete_count[0] += 1
            return original_complete(messages, tools)

        backend.complete = counting_complete
        cfg = AgentConfig(stream=False)
        registry = ToolRegistry().register(NoopTool("shell"))
        agent = Agent(backend, registry, cfg)
        task = Task(task_id="st2", description="fix", repo_path=str(tmp_path), max_steps=3)

        with EventLog.create(task, log_dir=str(tmp_path / "logs")) as log:
            result = agent.run(task, log)

        assert result.is_success()
        assert original_complete_count[0] >= 1
        assert len(backend._stream_calls) == 0

    def test_stream_callback_receives_streamed_text(self, tmp_path):
        script = [
            Action(ActionType.TOOL_CALL, "thinking...", ToolCall("shell", {"cmd": "ls"})),
            Action(ActionType.FINISH, "done", message="ok"),
        ]
        backend = self._make_streaming_backend(script)

        all_text = []
        cfg = AgentConfig(
            stream=True,
            stream_callback=lambda t: all_text.append(t),
        )
        registry = ToolRegistry().register(NoopTool("shell"))
        agent = Agent(backend, registry, cfg)
        task = Task(task_id="st3", description="fix", repo_path=str(tmp_path), max_steps=5)

        with EventLog.create(task, log_dir=str(tmp_path / "logs")) as log:
            agent.run(task, log)

        assert len(all_text) > 0

    def test_stream_no_callback_still_works(self, tmp_path):
        script = [Action(ActionType.FINISH, "done", message="ok")]
        backend = self._make_streaming_backend(script)
        cfg = AgentConfig(stream=True, stream_callback=None)
        registry = ToolRegistry().register(NoopTool("shell"))
        agent = Agent(backend, registry, cfg)
        task = Task(task_id="st4", description="fix", repo_path=str(tmp_path), max_steps=3)

        with EventLog.create(task, log_dir=str(tmp_path / "logs")) as log:
            result = agent.run(task, log)

        assert result.is_success()

    def test_stream_retry_on_error(self, tmp_path):
        attempt = 0
        script = [Action(ActionType.FINISH, "done", message="ok")]
        base_backend = MockBackend(script)

        def flaky_stream(messages, tools, on_text=None, on_thought=None):
            nonlocal attempt
            attempt += 1
            if attempt < 2:
                raise ConnectionError("stream interrupted")
            if on_text:
                on_text("ok")
            return base_backend.complete(messages, tools)

        base_backend.stream = flaky_stream
        cfg = AgentConfig(stream=True, llm_max_retries=3, llm_retry_delay=0.01)
        registry = ToolRegistry().register(NoopTool("shell"))
        agent = Agent(base_backend, registry, cfg)
        task = Task(task_id="st5", description="fix", repo_path=str(tmp_path), max_steps=3)

        with EventLog.create(task, log_dir=str(tmp_path / "logs")) as log:
            result = agent.run(task, log)

        assert result.is_success()
        assert attempt == 2

    def test_anthropic_compatible_stream_signature_does_not_raise_typeerror(self, tmp_path):
        script = [Action(ActionType.FINISH, "done", message="ok")]
        backend = MockBackend(script)
        stream_calls = []

        def anthropic_style_stream(messages, tools, on_text=None, on_thought=None):
            stream_calls.append(
                {
                    "on_text": on_text,
                    "on_thought": on_thought,
                }
            )
            if on_text:
                on_text("done")
            return backend.complete(messages, tools)

        backend.stream = anthropic_style_stream
        cfg = AgentConfig(
            stream=True,
            stream_callback=lambda t: None,
            thought_callback=lambda t: None,
        )
        registry = ToolRegistry().register(NoopTool("shell"))
        agent = Agent(backend, registry, cfg)
        task = Task(task_id="st6", description="fix", repo_path=str(tmp_path), max_steps=3)

        with EventLog.create(task, log_dir=str(tmp_path / "logs")) as log:
            result = agent.run(task, log)

        assert result.is_success()
        assert len(stream_calls) == 1
        assert stream_calls[0]["on_text"] is not None
        assert stream_calls[0]["on_thought"] is not None


class TestCliStreamOption:
    def test_stream_option_registered(self):
        from click.testing import CliRunner
        from entry.cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["run", "--help"])
        assert "--stream" in result.output or "-s" in result.output

    def test_stream_default_on(self):
        from click.testing import CliRunner
        from entry.cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["run", "--help"])
        assert "stream" in result.output.lower()

    def test_run_stream_does_not_replay_step_events(self, tmp_path):
        from click.testing import CliRunner
        from entry.cli import cli

        class StreamingBackend:
            model_name = "mock-stream"

            def complete(self, messages, tools):
                return LLMResponse(
                    action=Action(ActionType.FINISH, "done", message="final summary"),
                    raw_content="final summary",
                    input_tokens=1,
                    output_tokens=1,
                )

            def stream(self, messages, tools, on_text=None, on_thought=None):
                if on_text:
                    on_text("streamed output")
                return self.complete(messages, tools)

        def fake_build_app_components(config, repo_path, sandbox=False, confirm=False, chat_mode=False):
            return {
                "backend": StreamingBackend(),
                "runtime": None,
                "confirm_callback": None,
                "registry": ToolRegistry().register(NoopTool("shell")),
            }

        with patch("entry.cli.load_config") as mock_load_config, patch(
            "entry.cli.merge_cli_overrides",
            side_effect=lambda config, **_: config,
        ), patch("entry.cli._build_app_components", side_effect=fake_build_app_components):
            mock_load_config.return_value = MagicMock(
                llm=MagicMock(provider="anthropic", model="claude-test", api_key="k", base_url=None, max_tokens=128),
                agent=MagicMock(max_steps=3, budget_tokens=1000, log_dir=str(tmp_path / "logs")),
                context=MagicMock(history_window=10),
            )
            runner = CliRunner()
            result = runner.invoke(
                cli,
                ["run", "--repo", str(tmp_path), "--task", "demo"],
                obj={},
            )

        assert result.exit_code == 0
        assert "[Step " not in result.output
        assert "Tool:" not in result.output
        assert "Summary : final summary" in result.output


class TestBackendStreamMethod:
    def test_anthropic_backend_has_stream(self):
        from llm.anthropic_backend import AnthropicBackend

        assert hasattr(AnthropicBackend, "stream")
        assert callable(AnthropicBackend.stream)

    def test_openai_compat_backend_has_stream(self):
        from llm.openai_compat import OpenAICompatBackend

        assert hasattr(OpenAICompatBackend, "stream")
        assert callable(OpenAICompatBackend.stream)

    def test_anthropic_stream_signature(self):
        import inspect
        from llm.anthropic_backend import AnthropicBackend

        sig = inspect.signature(AnthropicBackend.stream)
        assert "on_text" in sig.parameters
        assert "on_thought" in sig.parameters

    def test_openai_stream_signature(self):
        import inspect
        from llm.openai_compat import OpenAICompatBackend

        sig = inspect.signature(OpenAICompatBackend.stream)
        assert "on_text" in sig.parameters
        assert "on_thought" in sig.parameters
