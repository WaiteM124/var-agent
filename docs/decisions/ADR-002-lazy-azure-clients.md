# ADR-002: Lazy Azure client construction for the agent path

**Status:** Accepted (reconstructed from code)  
**Date:** 2026-11-20  

---

## Context

Natural-language `/query` needs Azure OpenAI (chat + embeddings) and Azure AI Search. Contributors, CI, Streamlit Limit checks / Monte Carlo, and the worked example should not require cloud credentials.

## Decision

Construct Azure OpenAI and Azure AI Search clients lazily inside `agent.agent` on first use (`_azure_clients` / `_get_cached_clients`), not at import time. `POST /query` is the only FastAPI route that imports and runs the agent; it is gated by `AGENT_API_KEY` and returns 503 if the key is unset. Demo routes and `risk/` imports remain credential-free.

## Alternatives rejected

- **Eager client creation at module import.** Rejected: importing `agent` or starting the API would fail without Azure env vars, breaking offline demos and complicating tests.
- **Mock Azure always-on in process for all routes.** Rejected: unnecessary complexity for a PoC; deterministic routes already bypass the agent.
- **Require Azure for the entire FastAPI app.** Rejected: contradicts the README architecture (offline subgraph vs agent path).

## Consequences

- Missing Azure config surfaces as a runtime error on `/query` or methodology retrieval, not on `/health` or Monte Carlo.
- Tests can import `main:app` and exercise demo endpoints without patching Azure SDKs (they only assert `/query` auth behaviour).
- Dockerfile and local `uvicorn` flows work with `requirements.txt` / `[app]` extras even when `.env` Azure keys are empty, as long as `/query` is unused.
