# ADR-001: Deterministic risk core separate from the LLM agent

**Status:** Accepted (reconstructed from code)  
**Date:** 2026-11-20  

---

## Context

The product answers risk questions over a synthetic energy book. An LLM can help with natural language, but market-risk figures must be independently testable and must not depend on model memory or hallucination.

## Decision

Put all numeric risk behaviour in the `risk/` package (`portfolio`, `var`, `controls`). The LangGraph agent in `agent/` exposes tools that call those functions and is instructed to quote tool output. FastAPI demo routes (`/portfolio`, `/controls`, `/monte-carlo`) call `risk/` directly. CI and the worked example exercise only the deterministic path.

## Alternatives rejected

- **LLM computes or estimates VaR in-prompt.** Rejected: non-reproducible, untestable, unsafe for any risk narrative.
- **Single blended “agent score” mixing model judgment with maths.** Rejected: breaks auditability; contradicts the showcase goal of tool-grounded answers.
- **Agent-only surface with no direct HTTP tools.** Rejected: would force Azure credentials for every demo and for CI.

## Consequences

- Known-answer tests in `tests/` are the source of truth for book totals, limit breaches, and seeded Monte Carlo behaviour.
- Prompt changes must not alter numeric contracts; tool signatures and `risk/` APIs are the contracts.
- Extending methodology retrieval (Azure AI Search) does not change how VaR is calculated.
