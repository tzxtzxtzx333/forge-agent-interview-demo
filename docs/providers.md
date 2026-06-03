# Provider Verification

This document records the current provider matrix for Forge Agent as implemented today.
It is a verification guide, not a blanket claim that every model from every provider behaves identically.

## Capability Matrix

| Provider | Env var / dependency | Default base URL | Tool calling | Streaming | Text fallback | Known limitations | Smoke command |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `anthropic` | `ANTHROPIC_API_KEY`, `anthropic` package | SDK default | yes | yes | no | `on_thought` is accepted for interface compatibility and ignored | `python scripts/smoke_provider.py --provider anthropic --model claude-sonnet-4-5` |
| `openai` | `OPENAI_API_KEY`, `openai` package | SDK default | yes | yes | no | Uses the OpenAI chat completions interface | `python scripts/smoke_provider.py --provider openai --model gpt-4o` |
| `deepseek` | `DEEPSEEK_API_KEY`, `openai` package | `https://api.deepseek.com` | model-dependent | yes | yes | `deepseek-reasoner` / `deepseek-r1` use text fallback instead of native tool calls | `python scripts/smoke_provider.py --provider deepseek --model deepseek-chat` |
| `groq` | `GROQ_API_KEY`, `openai` package | `https://api.groq.com/openai/v1` | yes | yes | no | Behavior depends on the selected Groq-hosted model | `python scripts/smoke_provider.py --provider groq --model llama3-70b-8192` |
| `ollama` | optional `OLLAMA_API_KEY`, `openai` package, local `ollama serve` | `http://localhost:11434/v1` | model-dependent | yes | no | Requires a local Ollama server; tool calling depends on the selected model | `python scripts/smoke_provider.py --provider ollama --model llama3` |

## Notes

- The smoke script is a minimal connectivity check, not a benchmark.
- Missing API keys or a stopped local Ollama server produce a clear `[SKIP]` message instead of a Python traceback.
- `pytest` does not call real provider endpoints. Network-dependent checks stay in `scripts/smoke_provider.py`.
