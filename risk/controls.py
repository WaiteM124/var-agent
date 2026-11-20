"""Deterministic limit checks over a positions frame.

These are illustrative desk-style controls for the synthetic book, not a
production pre-trade engine and not wired to an order-management system.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import pandas as pd

from risk.portfolio import aggregate_precomputed_var


@dataclass(frozen=True)
class LimitConfig:
    max_position_notional: float = 5_000_000
    max_trader_notional: float = 15_000_000
    max_desk_notional: float = 25_000_000
    max_portfolio_var_95: float = 2_000_000
    max_commodity_share: float = 0.70


@dataclass(frozen=True)
class Breach:
    code: str
    message: str
    value: float
    limit: float
    context: str

    def to_dict(self) -> dict:
        return asdict(self)


def check_limits(frame: pd.DataFrame, config: LimitConfig | None = None) -> list[Breach]:
    """Return every limit breach; an empty list means the book is inside limits."""
    cfg = config or LimitConfig()
    breaches: list[Breach] = []
    if frame.empty:
        return breaches

    for _, row in frame.iterrows():
        notional = float(row["notional_usd"])
        if notional > cfg.max_position_notional:
            breaches.append(
                Breach(
                    code="POSITION_NOTIONAL",
                    message=(
                        f"Position {row['position_id']} notional "
                        f"{notional:,.0f} exceeds {cfg.max_position_notional:,.0f}"
                    ),
                    value=notional,
                    limit=cfg.max_position_notional,
                    context=str(row["position_id"]),
                )
            )

    trader_totals = frame.groupby("trader", sort=False)["notional_usd"].sum()
    for trader, total in trader_totals.items():
        total_f = float(total)
        if total_f > cfg.max_trader_notional:
            breaches.append(
                Breach(
                    code="TRADER_NOTIONAL",
                    message=(f"Trader {trader} notional {total_f:,.0f} exceeds {cfg.max_trader_notional:,.0f}"),
                    value=total_f,
                    limit=cfg.max_trader_notional,
                    context=str(trader),
                )
            )

    desk_totals = frame.groupby("desk", sort=False)["notional_usd"].sum()
    for desk, total in desk_totals.items():
        total_f = float(total)
        if total_f > cfg.max_desk_notional:
            breaches.append(
                Breach(
                    code="DESK_NOTIONAL",
                    message=(f"Desk {desk} notional {total_f:,.0f} exceeds {cfg.max_desk_notional:,.0f}"),
                    value=total_f,
                    limit=cfg.max_desk_notional,
                    context=str(desk),
                )
            )

    book_notional = float(frame["notional_usd"].sum())
    if book_notional > 0:
        commodity_totals = frame.groupby("commodity", sort=False)["notional_usd"].sum()
        for commodity, total in commodity_totals.items():
            share = float(total) / book_notional
            if share > cfg.max_commodity_share:
                breaches.append(
                    Breach(
                        code="COMMODITY_CONCENTRATION",
                        message=(
                            f"{commodity} is {share:.1%} of book notional, "
                            f"above the {cfg.max_commodity_share:.0%} concentration limit"
                        ),
                        value=share,
                        limit=cfg.max_commodity_share,
                        context=str(commodity),
                    )
                )

    agg = aggregate_precomputed_var(frame, confidence=95)
    book_var = float(agg["portfolio_var_95_1d_usd"])
    if book_var > cfg.max_portfolio_var_95:
        breaches.append(
            Breach(
                code="PORTFOLIO_VAR_95",
                message=(f"Book 95% 1-day VaR {book_var:,.0f} exceeds {cfg.max_portfolio_var_95:,.0f}"),
                value=book_var,
                limit=cfg.max_portfolio_var_95,
                context="portfolio",
            )
        )

    return breaches
