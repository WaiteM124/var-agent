# ADR-003: Pre-computed, parametric, and Monte Carlo VaR as distinct figures

**Status:** Accepted (reconstructed from code)  
**Date:** 2026-11-20  

---

## Context

The sample CSV carries `var_95_1d` / `var_99_1d` columns that are mostly `notional × volatility × 2` (or × 3). Separately, `risk.var` implements undiversified parametric VaR and a seeded one-day GBM Monte Carlo. Stakeholders need clear figures without implying a single “true” VaR.

## Decision

Treat three measures as first-class and separate:

1. **Pre-computed book VaR** — `aggregate_precomputed_var` sums existing CSV columns (what the agent `calculate_portfolio_var` tool does).
2. **Undiversified parametric VaR** — `|N| σ z` via `parametric_var`.
3. **Monte Carlo VaR / ES** — `simulate_portfolio_pnl` + `var_from_pnl` / `expected_shortfall`, with documented assumptions (zero drift, constant pairwise correlation, delta-only options).

The worked example and README publish all three side by side and document why they differ. Limit checks use the pre-computed book VaR for the portfolio VaR limit.

## Alternatives rejected

- **Overwrite CSV columns from the Monte Carlo engine on each run.** Rejected: would hide the data artefact and break stable known-answer tests tied to fixed book totals.
- **Present only one VaR number in the UI/API.** Rejected: obscures methodology differences that the showcase is meant to teach.
- **Full revaluation with gamma/vega/expiry.** Rejected for this PoC: out of scope; delta approximation is explicitly documented.

## Consequences

- Tests lock book pre-computed totals (e.g. 95% VaR `$1,886,960`) and MC seed determinism rather than equality across estimators.
- Docs and agent prompts must not claim the tool “re-prices” the book when aggregating pre-computed columns.
- Changing MC defaults (paths, seed, correlation) requires updating `examples/output/` and README tables together.
