# Decision records

Lightweight architecture decision records (ADRs) for this repository.

## Format

Each record is a markdown file named `ADR-NNN-short-slug.md` and should include:

1. **Status** — Proposed | Accepted | Superseded | Deprecated  
2. **Date** — when the decision was made (or reconstructed)  
3. **Context** — the problem and constraints  
4. **Decision** — what we chose  
5. **Alternatives rejected** — what we did not choose, and why  
6. **Consequences** — follow-on effects, trade-offs, and follow-ups  

Mark records **reconstructed from code** when the reasoning was not written down at the time and has been inferred from the current tree and README.

## Index

| ADR | Title |
|---|---|
| [ADR-001](ADR-001-deterministic-risk-core.md) | Deterministic risk core separate from the LLM agent |
| [ADR-002](ADR-002-lazy-azure-clients.md) | Lazy Azure client construction for the agent path |
| [ADR-003](ADR-003-precomputed-vs-monte-carlo-var.md) | Pre-computed, parametric, and Monte Carlo VaR as distinct figures |
