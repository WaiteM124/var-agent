from __future__ import annotations

import numpy as np
import pytest

from risk.portfolio import load_positions
from risk.var import (
    expected_shortfall,
    parametric_var,
    simulate_portfolio_pnl,
    var_from_pnl,
    z_score,
)

BOOK = load_positions()


def test_z_score_and_parametric_known_value():
    assert z_score(95) == pytest.approx(1.6448536269514722)
    # 5,000,000 * 0.021 * z_95
    assert parametric_var(5_000_000, 0.021, 95) == pytest.approx(172_709.63082990458)
    assert parametric_var(-5_000_000, 0.021, 95) == pytest.approx(172_709.63082990458)
    with pytest.raises(ValueError):
        z_score(90)


def test_precomputed_book_var_is_mostly_two_and_three_sigma():
    """Document the sample book's construction; do not treat it as model output."""
    two_sigma = BOOK["notional_usd"] * BOOK["volatility_1d"] * 2
    three_sigma = BOOK["notional_usd"] * BOOK["volatility_1d"] * 3
    close_95 = np.isclose(BOOK["var_95_1d"], two_sigma, rtol=0, atol=0.5)
    close_99 = np.isclose(BOOK["var_99_1d"], three_sigma, rtol=0, atol=0.5)
    assert close_95.sum() == 14
    assert close_99.sum() == 14
    # P002 is the documented exception (slightly below 2σ / 3σ).
    outlier = BOOK.loc[~close_95, "position_id"].tolist()
    assert outlier == ["P002"]


def test_monte_carlo_is_deterministic_with_seed():
    a = simulate_portfolio_pnl(BOOK, n_paths=2_000, seed=42, correlation=0.4)
    b = simulate_portfolio_pnl(BOOK, n_paths=2_000, seed=42, correlation=0.4)
    c = simulate_portfolio_pnl(BOOK, n_paths=2_000, seed=7, correlation=0.4)
    assert a.shape == (2_000,)
    np.testing.assert_array_equal(a, b)
    assert not np.array_equal(a, c)


def test_single_position_var_from_pnl_sign_and_scale():
    row = BOOK.loc[BOOK["position_id"] == "P001"].copy()
    pnl = simulate_portfolio_pnl(row, n_paths=30_000, seed=42, correlation=0.0)
    var95 = var_from_pnl(pnl, 95)
    es95 = expected_shortfall(pnl, 95)
    parametric = parametric_var(float(row["notional_usd"].iloc[0]), float(row["volatility_1d"].iloc[0]), 95)
    # Seeded GBM 95% VaR should be in the same region as parametric (not exact).
    assert var95 > 0
    assert es95 > var95
    assert 0.7 * parametric < var95 < 1.3 * parametric


def test_correlation_diversifies_relative_to_undiversified_sum():
    undiversified = sum(parametric_var(float(r.notional_usd), float(r.volatility_1d), 95) for r in BOOK.itertuples())
    pnl = simulate_portfolio_pnl(BOOK, n_paths=20_000, seed=42, correlation=0.4)
    mc_var = var_from_pnl(pnl, 95)
    # With rho < 1 the portfolio MC VaR should sit well below the sum of
    # stand-alone parametric VaRs. This is a sanity bound, not a calibration.
    assert mc_var < 0.85 * undiversified
    assert mc_var > 0


def test_empty_book_returns_zero_pnl():
    empty = BOOK.iloc[0:0]
    pnl = simulate_portfolio_pnl(empty, n_paths=100, seed=1)
    assert pnl.shape == (100,)
    assert np.all(pnl == 0)


def test_invalid_correlation_and_paths():
    with pytest.raises(ValueError, match="correlation"):
        simulate_portfolio_pnl(BOOK, correlation=1.0)
    with pytest.raises(ValueError, match="n_paths"):
        simulate_portfolio_pnl(BOOK, n_paths=0)
