from __future__ import annotations

from pytest import approx

from risk.controls import LimitConfig, check_limits
from risk.portfolio import filter_positions, load_positions

BOOK = load_positions()


def test_default_limits_flag_known_concentrations():
    breaches = check_limits(BOOK)
    codes = {b.code for b in breaches}
    assert codes == {"POSITION_NOTIONAL", "TRADER_NOTIONAL", "DESK_NOTIONAL"}

    positions = {b.context for b in breaches if b.code == "POSITION_NOTIONAL"}
    assert positions == {"P010"}  # 6.5M vs 5M default cap

    traders = {b.context for b in breaches if b.code == "TRADER_NOTIONAL"}
    assert traders == {"John Smith"}  # 15.6M vs 15M

    desks = {b.context for b in breaches if b.code == "DESK_NOTIONAL"}
    assert desks == {"Crude Oil"}  # 29.6M vs 25M

    # Book pre-computed 95% VaR is 1,886,960, under the 2M default.
    assert "PORTFOLIO_VAR_95" not in codes
    # Brent is 19.2M / 41.35M = 46.4%, under a 70% commodity cap.
    assert "COMMODITY_CONCENTRATION" not in codes


def test_loose_limits_report_no_breaches():
    cfg = LimitConfig(
        max_position_notional=10_000_000,
        max_trader_notional=20_000_000,
        max_desk_notional=50_000_000,
        max_portfolio_var_95=5_000_000,
        max_commodity_share=0.99,
    )
    assert check_limits(BOOK, cfg) == []


def test_tight_var_and_concentration_limits():
    cfg = LimitConfig(
        max_position_notional=10_000_000,
        max_trader_notional=20_000_000,
        max_desk_notional=50_000_000,
        max_portfolio_var_95=1_000_000,
        max_commodity_share=0.40,
    )
    breaches = check_limits(BOOK, cfg)
    codes = {b.code for b in breaches}
    assert codes == {"PORTFOLIO_VAR_95", "COMMODITY_CONCENTRATION"}
    commodity = next(b for b in breaches if b.code == "COMMODITY_CONCENTRATION")
    assert commodity.context == "Brent Crude"
    assert commodity.value == approx(19_200_000 / 41_350_000)
    var_breach = next(b for b in breaches if b.code == "PORTFOLIO_VAR_95")
    assert var_breach.value == 1_886_960


def test_empty_book_has_no_breaches():
    assert check_limits(BOOK.iloc[0:0]) == []


def test_filtered_desk_inside_position_limits():
    shipping = filter_positions(BOOK, desk="Shipping")
    cfg = LimitConfig(
        max_position_notional=2_000_000,
        max_trader_notional=5_000_000,
        max_desk_notional=5_000_000,
        max_portfolio_var_95=1_000_000,
        max_commodity_share=1.0,
    )
    assert check_limits(shipping, cfg) == []
