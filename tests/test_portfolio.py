from __future__ import annotations

from pathlib import Path

import pytest

from risk.portfolio import (
    DEFAULT_POSITIONS_PATH,
    aggregate_precomputed_var,
    filter_positions,
    load_positions,
    signed_notional,
)

BOOK = load_positions()


def test_default_book_shape_and_types():
    assert DEFAULT_POSITIONS_PATH.exists()
    assert len(BOOK) == 15
    assert BOOK["delta"].dtype.kind == "f"
    assert (BOOK["notional_usd"] > 0).all()


def test_load_normalises_unicode_minus(tmp_path: Path):
    csv = tmp_path / "positions.csv"
    csv.write_text(
        "position_id,trader,desk,commodity,instrument,direction,notional_usd,"
        "price,volatility_1d,var_95_1d,var_99_1d,delta,status\n"
        "P002,Sarah Jones,Crude Oil,WTI Crude,Futures,Short,3200000,79.20,0.019,"
        "120960,181440,−1.0,Active\n",
        encoding="utf-8",
    )
    frame = load_positions(csv)
    assert frame.loc[0, "delta"] == pytest.approx(-1.0)


def test_full_book_precomputed_var_95():
    result = aggregate_precomputed_var(BOOK, 95)
    assert result["positions_count"] == 15
    assert result["total_notional_usd"] == 41_350_000
    assert result["portfolio_var_95_1d_usd"] == 1_886_960
    assert result["var_as_pct_notional"] == 4.563
    assert result["largest_var_position"] == "P010"
    assert result["confidence_level"] == "95%"


def test_full_book_precomputed_var_99():
    result = aggregate_precomputed_var(BOOK, "99")
    assert result["portfolio_var_99_1d_usd"] == 2_830_440
    assert result["largest_var_position"] == "P010"


def test_filter_by_trader_desk_commodity():
    john = filter_positions(BOOK, trader="john")
    assert set(john["trader"]) == {"John Smith"}
    assert int(john["notional_usd"].sum()) == 15_600_000

    crude = filter_positions(BOOK, desk="crude")
    assert set(crude["desk"]) == {"Crude Oil"}
    assert int(crude["notional_usd"].sum()) == 29_600_000

    brent = filter_positions(BOOK, commodity="brent")
    assert (brent["commodity"] == "Brent Crude").all()
    assert len(brent) == 4


def test_combined_filters_and_empty():
    out = filter_positions(BOOK, trader="john", desk="natural gas")
    assert out.empty
    result = aggregate_precomputed_var(out, 95)
    assert result["positions_count"] == 0
    assert result["portfolio_var_95_1d_usd"] == 0
    assert result["largest_var_position"] is None


def test_signed_notional_long_short():
    signed = signed_notional(BOOK)
    longs = BOOK["direction"].str.lower().eq("long")
    assert (signed[longs] > 0).all()
    assert (signed[~longs] < 0).all()
    assert signed.abs().tolist() == BOOK["notional_usd"].tolist()


def test_signed_notional_rejects_bad_direction():
    bad = BOOK.head(1).copy()
    bad["direction"] = "flat"
    with pytest.raises(ValueError, match="direction"):
        signed_notional(bad)


def test_aggregate_rejects_bad_confidence():
    with pytest.raises(ValueError, match="confidence"):
        aggregate_precomputed_var(BOOK, 90)
