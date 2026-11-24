#!/usr/bin/env python3
"""Optional live Azure agent smoke eval (manual workflow_dispatch only).

Requires repository secrets / env:

* ``AGENT_API_KEY`` (optional here — this script calls ``agent.agent.query`` in-process)
* ``AZURE_OPENAI_ENDPOINT``, ``AZURE_OPENAI_KEY``
* ``AZURE_SEARCH_ENDPOINT``, ``AZURE_SEARCH_KEY``

This is intentionally non-gating: answers may vary. We only check that the agent
returns a non-empty string and, for in-scope prompts, that material substrings
from a deterministic tool call appear in the answer when present.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
_REPO_ROOT = ROOT.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

LIVE_CASES = ROOT / "live_cases" / "smoke.json"
LIVE_RESULTS = ROOT / "live_results.json"

REQUIRED_ENV = (
    "AZURE_OPENAI_ENDPOINT",
    "AZURE_OPENAI_KEY",
    "AZURE_SEARCH_ENDPOINT",
    "AZURE_SEARCH_KEY",
)


def _missing_env() -> list[str]:
    return [name for name in REQUIRED_ENV if not os.getenv(name)]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, default=LIVE_RESULTS)
    args = parser.parse_args(argv)

    missing = _missing_env()
    if missing:
        print("missing required env for live eval:", ", ".join(missing), file=sys.stderr)
        return 2

    cases = json.loads(LIVE_CASES.read_text(encoding="utf-8"))
    from agent.agent import query  # lazy: needs Azure + LangChain

    rows: list[dict] = []
    for case in cases:
        question = case["question"]
        try:
            answer = query(question)
            ok = isinstance(answer, str) and bool(answer.strip())
            missing = [needle for needle in case.get("prefer_contain", []) if needle not in (answer or "")]
            rows.append(
                {
                    "id": case["id"],
                    "pass": ok,
                    "prefer_missing": missing,
                    "answer_preview": (answer or "")[:400],
                }
            )
        except Exception as exc:  # noqa: BLE001
            rows.append({"id": case["id"], "pass": False, "error": str(exc)})

    passed = sum(1 for row in rows if row.get("pass"))
    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "mode": "live",
        "summary": {"total": len(rows), "passed": passed, "failed": len(rows) - passed},
        "cases": rows,
    }
    args.results.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"live evals: {passed}/{len(rows)} smoke checks passed; wrote {args.results}")
    return 0 if passed == len(rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
