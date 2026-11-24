## Summary

<!-- What changed and why. State assumptions and out-of-scope items. -->

## Checklist

- [ ] **Principles respected** — risk numbers from deterministic code (not the LLM); VaR figures kept distinct; offline core / Azure only on the agent path ([AGENTS.md](../AGENTS.md))
- [ ] **Tests added or updated** — known-answer cases where risk maths or limits change; existing tests not weakened or deleted to pass
- [ ] **Tests and lint passing** — `ruff check` / `ruff format --check` and `pytest` (CI green; worked example in CI)
- [ ] **No secrets** — no API keys, credentials, connection strings, or private keys in code or this PR
- [ ] **Docs updated** — README / ADRs / `AGENTS.md` / `CONTRIBUTING.md` updated if behaviour or workflow changed

## Test plan

<!-- Commands run locally, or "rely on CI". -->
