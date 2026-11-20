from __future__ import annotations

import os
from typing import Any

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

from risk.controls import LimitConfig, check_limits
from risk.portfolio import aggregate_precomputed_var, filter_positions, load_positions
from risk.var import expected_shortfall, simulate_portfolio_pnl, var_from_pnl

load_dotenv()

app = FastAPI(
    title="VaR Risk Agent",
    version="0.2.0",
    description=(
        "Deterministic portfolio, VaR, and limit-check endpoints run without cloud "
        "credentials. POST /query calls the LangGraph agent and requires Azure OpenAI."
    ),
)
security = HTTPBearer()
API_KEY = os.getenv("AGENT_API_KEY")
_BOOK = load_positions()


def verify_key(credentials: HTTPAuthorizationCredentials = Security(security)) -> str:
    if not API_KEY:
        raise HTTPException(status_code=503, detail="AGENT_API_KEY is not set")
    if credentials.credentials != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return credentials.credentials


class QueryRequest(BaseModel):
    message: str


class QueryResponse(BaseModel):
    answer: str


class BookFilter(BaseModel):
    trader: str | None = None
    desk: str | None = None
    commodity: str | None = None


class MonteCarloRequest(BookFilter):
    confidence: int = Field(default=95, description="95 or 99")
    n_paths: int = Field(default=20_000, ge=100, le=100_000)
    seed: int = 42
    correlation: float = Field(default=0.4, ge=0.0, lt=1.0)


def _slice(trader: str | None, desk: str | None, commodity: str | None):
    return filter_positions(_BOOK, trader=trader, desk=desk, commodity=commodity)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/portfolio")
def portfolio(trader: str | None = None, desk: str | None = None, commodity: str | None = None) -> dict[str, Any]:
    frame = _slice(trader, desk, commodity)
    return {
        "var_95": aggregate_precomputed_var(frame, 95),
        "var_99": aggregate_precomputed_var(frame, 99),
        "positions": frame.to_dict(orient="records"),
    }


@app.get("/controls")
def controls(trader: str | None = None, desk: str | None = None, commodity: str | None = None) -> dict[str, Any]:
    frame = _slice(trader, desk, commodity)
    breaches = check_limits(frame, LimitConfig())
    return {
        "breach_count": len(breaches),
        "breaches": [b.to_dict() for b in breaches],
        "limits": LimitConfig().__dict__,
    }


@app.post("/monte-carlo")
def monte_carlo(request: MonteCarloRequest) -> dict[str, Any]:
    frame = _slice(request.trader, request.desk, request.commodity)
    if request.confidence not in {95, 99}:
        raise HTTPException(status_code=422, detail="confidence must be 95 or 99")
    pnl = simulate_portfolio_pnl(
        frame,
        n_paths=request.n_paths,
        seed=request.seed,
        correlation=request.correlation,
    )
    return {
        "positions_count": int(len(frame)),
        "n_paths": request.n_paths,
        "seed": request.seed,
        "correlation": request.correlation,
        "confidence": request.confidence,
        "var_usd": round(var_from_pnl(pnl, request.confidence), 2),
        "expected_shortfall_usd": round(expected_shortfall(pnl, request.confidence), 2),
        "pnl_mean_usd": round(float(pnl.mean()), 2) if len(frame) else 0.0,
        "pnl_std_usd": round(float(pnl.std()), 2) if len(frame) else 0.0,
    }


@app.post("/query", response_model=QueryResponse)
def run_query(request: QueryRequest, _: str = Depends(verify_key)) -> QueryResponse:
    from agent.agent import query

    return QueryResponse(answer=query(request.message))
