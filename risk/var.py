"""Parametric and Monte Carlo 1-day VaR for the synthetic book.

The sample book's ``var_95_1d`` / ``var_99_1d`` columns are pre-computed and are
*not* produced by these functions. Most rows equal ``notional * volatility * 2``
(95%) or ``* 3`` (99%); one row differs slightly. Treat the pre-computed book
VaR and the estimators below as separate figures.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

# Standard normal quantiles
Z_SCORES = {
    95: 1.6448536269514722,
    99: 2.3263478740408408,
}


def z_score(confidence: int | str) -> float:
    level = int(confidence)
    if level not in Z_SCORES:
        raise ValueError("confidence must be 95 or 99")
    return Z_SCORES[level]


def parametric_var(
    notional: float,
    volatility_1d: float,
    confidence: int | str = 95,
) -> float:
    """Undiversified 1-day parametric VaR: ``|notional| * |vol| * z``.

    This is a linear, normal-assumption figure. It does not apply option delta
    or net long/short direction; pass the exposure you want to measure.
    """
    return abs(float(notional)) * abs(float(volatility_1d)) * z_score(confidence)


def position_signs(frame: pd.DataFrame) -> np.ndarray:
    direction = frame["direction"].str.strip().str.lower()
    sign = direction.map({"long": 1.0, "short": -1.0}).to_numpy(dtype=float)
    if np.isnan(sign).any():
        raise ValueError("unrecognised direction values in frame")
    return sign


def simulate_portfolio_pnl(
    frame: pd.DataFrame,
    *,
    n_paths: int = 20_000,
    seed: int = 42,
    correlation: float = 0.4,
    horizon_days: float = 1.0,
    use_delta: bool = True,
) -> np.ndarray:
    """Seeded 1-day GBM Monte Carlo P&L for the book, in USD.

    Assumptions (kept deliberately simple and documented):

    * Each position follows geometric Brownian motion with its ``volatility_1d``
      as the daily sigma and zero drift (the usual short-horizon risk measure).
    * Shocks are jointly normal with constant pairwise correlation ``correlation``.
    * Options are delta-approximated (no gamma, vega, or expiry effects).
    * No collateral, margining, or liquidity adjustment.

    Returns a 1-d array of portfolio P&L draws (positive = profit).
    """
    if n_paths < 1:
        raise ValueError("n_paths must be positive")
    if not 0.0 <= correlation < 1.0:
        raise ValueError("correlation must be in [0, 1)")
    if frame.empty:
        return np.zeros(n_paths, dtype=float)

    n = len(frame)
    vols = frame["volatility_1d"].to_numpy(dtype=float)
    notionals = frame["notional_usd"].to_numpy(dtype=float)
    signs = position_signs(frame)
    if use_delta:
        deltas = frame["delta"].to_numpy(dtype=float)
    else:
        deltas = np.ones(n, dtype=float)

    if n == 1 or correlation == 0.0:
        rng = np.random.default_rng(seed)
        shocks = rng.standard_normal((n_paths, n))
    else:
        corr = np.full((n, n), float(correlation))
        np.fill_diagonal(corr, 1.0)
        # Numerical guard for a constant-correlation matrix.
        eig = np.linalg.eigvalsh(corr)
        if eig.min() <= 0:
            corr = corr + np.eye(n) * (1e-10 - eig.min())
        chol = np.linalg.cholesky(corr)
        rng = np.random.default_rng(seed)
        shocks = rng.standard_normal((n_paths, n)) @ chol.T

    t = float(horizon_days)
    log_returns = (-0.5 * vols**2) * t + vols * math.sqrt(t) * shocks
    simple_returns = np.exp(log_returns) - 1.0
    exposure = notionals * signs * deltas
    return simple_returns @ exposure


def var_from_pnl(pnl: np.ndarray, confidence: int | str = 95) -> float:
    """VaR as a positive loss number: ``-quantile(pnl, 1 - confidence/100)``."""
    level = int(confidence)
    if not 0 < level < 100:
        raise ValueError("confidence must be between 0 and 100")
    alpha = 1.0 - level / 100.0
    return float(-np.quantile(pnl, alpha))


def historical_var(pnl: np.ndarray | list[float], confidence: int | str = 95) -> float:
    """Historical VaR from a fixed P&L series (positive loss number).

    This is the empirical quantile of the supplied path — the same estimator as
    ``var_from_pnl``. Use a pinned series in tests/evals so the answer is analytic.
    """
    return var_from_pnl(np.asarray(pnl, dtype=float), confidence)


def expected_shortfall(pnl: np.ndarray, confidence: int | str = 95) -> float:
    """Expected Shortfall (CVaR): mean loss in the tail beyond VaR, positive."""
    var = var_from_pnl(pnl, confidence)
    tail = pnl[pnl <= -var]
    if tail.size == 0:
        return var
    return float(-tail.mean())
