"""Load, filter, and aggregate the synthetic positions book."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

NUMERIC_COLUMNS = (
    "notional_usd",
    "price",
    "volatility_1d",
    "var_95_1d",
    "var_99_1d",
    "delta",
)

DEFAULT_POSITIONS_PATH = Path(__file__).resolve().parent.parent / "data" / "positions.csv"


def _normalise_numeric(series: pd.Series) -> pd.Series:
    if series.dtype.kind in "fi":
        return series.astype(float)
    cleaned = series.astype(str).str.replace("\u2212", "-", regex=False).str.replace(",", "", regex=False).str.strip()
    return pd.to_numeric(cleaned, errors="raise")


def load_positions(path: str | Path | None = None) -> pd.DataFrame:
    """Load the positions CSV and coerce numeric columns (including Unicode minus signs)."""
    frame = pd.read_csv(path or DEFAULT_POSITIONS_PATH)
    missing = [col for col in NUMERIC_COLUMNS if col not in frame.columns]
    if missing:
        raise ValueError(f"positions file is missing columns: {missing}")
    out = frame.copy()
    for col in NUMERIC_COLUMNS:
        out[col] = _normalise_numeric(out[col])
    return out


def signed_notional(frame: pd.DataFrame) -> pd.Series:
    """Notional signed by trade direction: long positive, short negative."""
    direction = frame["direction"].str.strip().str.lower()
    sign = direction.map({"long": 1.0, "short": -1.0})
    if sign.isna().any():
        bad = sorted(frame.loc[sign.isna(), "direction"].unique())
        raise ValueError(f"unrecognised direction values: {bad}")
    return frame["notional_usd"].astype(float) * sign


def filter_positions(
    frame: pd.DataFrame,
    trader: str | None = None,
    desk: str | None = None,
    commodity: str | None = None,
) -> pd.DataFrame:
    """Return a copy filtered with case-insensitive substring matches."""
    out = frame.copy()
    if trader:
        out = out[out["trader"].str.contains(trader, case=False, na=False)]
    if desk:
        out = out[out["desk"].str.contains(desk, case=False, na=False)]
    if commodity:
        out = out[out["commodity"].str.contains(commodity, case=False, na=False)]
    return out.reset_index(drop=True)


def aggregate_precomputed_var(frame: pd.DataFrame, confidence: int | str = 95) -> dict:
    """Sum pre-computed 1-day VaR columns already present on the book.

    This is what the agent tool does: it does not re-estimate VaR from prices or
    volatilities. ``confidence`` must be 95 or 99.
    """
    level = str(confidence)
    if level not in {"95", "99"}:
        raise ValueError("confidence must be 95 or 99")
    col = f"var_{level}_1d"
    if frame.empty:
        return {
            "positions_count": 0,
            "total_notional_usd": 0,
            f"portfolio_var_{level}_1d_usd": 0,
            "var_as_pct_notional": 0.0,
            "largest_var_position": None,
            "confidence_level": f"{level}%",
        }
    total_var = float(frame[col].sum())
    total_notional = float(frame["notional_usd"].sum())
    var_pct = (total_var / total_notional) * 100 if total_notional else 0.0
    largest = frame.loc[frame[col].idxmax(), "position_id"]
    return {
        "positions_count": int(len(frame)),
        "total_notional_usd": int(total_notional),
        f"portfolio_var_{level}_1d_usd": int(total_var),
        "var_as_pct_notional": round(var_pct, 3),
        "largest_var_position": str(largest),
        "confidence_level": f"{level}%",
    }
