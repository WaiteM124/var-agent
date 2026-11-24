# ADR-004: Offline deterministic eval suite with CI eval-gate

**Status:** Accepted  
**Date:** 2026-11-24  

---

## Context

`AGENTS.md` requires that risk numbers come from deterministic code and that agent answers stay grounded in tool output. Pytest covers unit contracts, but there was no labelled, regression-gated eval suite for:

- known-answer VaR maths (parametric, historical on a fixed series, seeded Monte Carlo),
- agent tool routing and answer grounding under recorded/mock LLM turns,
- refusal or deferral on out-of-scope questions.

A live Azure agent eval needs credentials, incurs cost, and is non-deterministic, so it must not block every PR. Contributors still need a cheap, offline gate that fails when quality drops below a committed baseline.

## Decision

1. Add an **offline** eval suite under `evals/` with labelled cases in `evals/cases/`, a runner `evals/run_evals.py`, committed `evals/baseline.json`, and run output in `evals/results.json`.
2. The suite uses only the `risk/` package and fixture LLM transcripts. It does **not** call Azure OpenAI, Azure AI Search, or require any repository secrets.
3. Add a required CI job **`eval-gate`** on every PR/push that runs the offline suite and fails if any aggregate pass-rate drops below baseline.
4. Add an optional workflow **`eval-live.yml`** triggered only by `workflow_dispatch`, using GitHub Actions secrets for a real Azure agent smoke eval. It is not a required status check.

## Alternatives rejected

- **Require live LLM evals on every PR.** Rejected: needs secrets, cost, flakiness; contradicts the offline-core principle (ADR-001 / ADR-002).
- **Fold all evals into pytest only.** Rejected: pytest remains the unit contract; labelled cases + baseline regression are a clearer product gate and match the requested `evals/` layout.
- **Mock Azure inside the LangGraph graph for CI.** Rejected for the PR gate: heavier deps and tighter coupling. Offline cases exercise tool routing/grounding via fixtures over the same `risk/` functions the tools wrap.

## Consequences

- CI grows a second required job (`eval-gate`) alongside lint/test; both must stay green.
- Updating fixtures or baselines is deliberate: do not lower baseline scores to green CI without documenting why.
- Live Azure quality remains optional and manual; document secrets and how to run it in `AGENTS.md`.
- Extending agent prompts or tools should add or adjust offline fixture cases when routing/grounding behaviour changes.
