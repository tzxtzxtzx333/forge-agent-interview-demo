from __future__ import annotations

import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from llm.provider_smoke import run_provider_smoke


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a minimal provider connectivity smoke test."
    )
    parser.add_argument("--provider", required=True, help="Provider name")
    parser.add_argument("--model", required=True, help="Model name")
    parser.add_argument("--base-url", default=None, help="Override base URL")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    result = run_provider_smoke(
        provider=args.provider,
        model=args.model,
        base_url=args.base_url,
    )
    prefix = {
        "ok": "[OK]",
        "skip": "[SKIP]",
        "error": "[ERROR]",
    }[result.status]
    print(f"{prefix} {result.message}")
    return result.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
