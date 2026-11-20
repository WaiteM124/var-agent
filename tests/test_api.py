from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_portfolio_full_book():
    data = client.get("/portfolio").json()
    assert data["var_95"]["positions_count"] == 15
    assert data["var_95"]["total_notional_usd"] == 41_350_000
    assert data["var_95"]["portfolio_var_95_1d_usd"] == 1_886_960
    assert data["var_99"]["portfolio_var_99_1d_usd"] == 2_830_440
    assert len(data["positions"]) == 15


def test_portfolio_trader_filter():
    data = client.get("/portfolio", params={"trader": "john"}).json()
    assert data["var_95"]["total_notional_usd"] == 15_600_000
    assert {row["trader"] for row in data["positions"]} == {"John Smith"}


def test_controls_default_breaches():
    data = client.get("/controls").json()
    assert data["breach_count"] == 3
    assert {b["code"] for b in data["breaches"]} == {
        "POSITION_NOTIONAL",
        "TRADER_NOTIONAL",
        "DESK_NOTIONAL",
    }


def test_monte_carlo_is_seeded():
    payload = {"n_paths": 2_000, "seed": 42, "correlation": 0.4, "confidence": 95}
    first = client.post("/monte-carlo", json=payload).json()
    second = client.post("/monte-carlo", json=payload).json()
    assert first["var_usd"] == second["var_usd"]
    assert first["expected_shortfall_usd"] == second["expected_shortfall_usd"]
    assert first["var_usd"] > 0
    assert first["expected_shortfall_usd"] > first["var_usd"]
    assert first["positions_count"] == 15


def test_query_without_api_key_is_unavailable(monkeypatch: pytest.MonkeyPatch):
    import main as main_mod

    monkeypatch.setattr(main_mod, "API_KEY", None)
    response = client.post(
        "/query",
        json={"message": "What is the VaR?"},
        headers={"Authorization": "Bearer test"},
    )
    assert response.status_code == 503
