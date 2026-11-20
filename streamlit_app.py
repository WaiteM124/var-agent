from __future__ import annotations

import os

import pandas as pd
import requests
import streamlit as st

from risk.controls import LimitConfig, check_limits
from risk.portfolio import aggregate_precomputed_var, load_positions
from risk.var import expected_shortfall, simulate_portfolio_pnl, var_from_pnl

AGENT_URL = str(st.secrets.get("AGENT_URL", os.getenv("AGENT_URL", "http://localhost:8000"))).rstrip("/")
API_KEY = str(st.secrets.get("API_KEY", os.getenv("AGENT_API_KEY", "")))

st.set_page_config(page_title="VaR Risk Agent", page_icon="📊", layout="centered")

st.markdown(
    """
<style>
    .answer-box { background-color: #1e2130; border-left: 4px solid #00b4d8; padding: 1rem;
                  border-radius: 4px; margin-top: 1rem; color: #ffffff; font-size: 0.95rem;
                  line-height: 1.6; }
    h1 { color: #00b4d8; }
</style>
""",
    unsafe_allow_html=True,
)

st.title("📊 VaR Risk Agent")
st.caption(
    "Synthetic energy-trading book — deterministic VaR, Monte Carlo and limit checks "
    "run locally with no cloud credentials. Natural-language questions use the FastAPI "
    "agent and require Azure OpenAI."
)

book = load_positions()
pre95 = aggregate_precomputed_var(book, 95)

col1, col2, col3 = st.columns(3)
col1.metric("Positions", f"{pre95['positions_count']}")
col2.metric("Total notional", f"${pre95['total_notional_usd']:,.0f}")
col3.metric("Pre-computed 95% VaR", f"${pre95['portfolio_var_95_1d_usd']:,.0f}")

st.markdown("---")

tab_limits, tab_mc, tab_ask = st.tabs(["Limit checks", "Monte Carlo", "Ask the agent"])

with tab_limits:
    st.subheader("Default limit checks")
    st.write(
        "These use the same `risk.controls` checks as `GET /controls` and the worked "
        "example. They do not require Azure."
    )
    breaches = check_limits(book, LimitConfig())
    if not breaches:
        st.success("No default limits are breached.")
    else:
        st.warning(f"{len(breaches)} breach(es) on the synthetic book.")
        st.dataframe(pd.DataFrame([b.to_dict() for b in breaches]), hide_index=True, use_container_width=True)

with tab_mc:
    st.subheader("Seeded 1-day Monte Carlo")
    st.write(
        "Runs locally in this process (same implementation as `examples/run_var_example.py`). "
        "Default seed 42 and 20,000 paths match the committed chart in the README."
    )
    n_paths = st.slider("Paths", min_value=1000, max_value=20_000, value=5_000, step=1000)
    seed = st.number_input("Seed", value=42, step=1)
    rho = st.slider("Pairwise correlation", min_value=0.0, max_value=0.9, value=0.4, step=0.1)
    if st.button("Run simulation", type="primary"):
        with st.spinner("Simulating..."):
            pnl = simulate_portfolio_pnl(book, n_paths=int(n_paths), seed=int(seed), correlation=float(rho))
            var95 = var_from_pnl(pnl, 95)
            es95 = expected_shortfall(pnl, 95)
        m1, m2 = st.columns(2)
        m1.metric("MC 95% VaR", f"${var95:,.0f}")
        m2.metric("MC 95% expected shortfall", f"${es95:,.0f}")
        chart = pd.DataFrame({"pnl_usd_millions": pnl / 1_000_000})
        st.bar_chart(chart["pnl_usd_millions"].value_counts(bins=40).sort_index())
        st.caption("Histogram is a rough Streamlit chart; the README figure is the committed matplotlib plot.")

with tab_ask:
    st.subheader("Natural-language query")
    st.write(
        "This tab posts to `POST /query` on the FastAPI service. It needs the API running "
        "and Azure OpenAI / Azure AI Search credentials on the server."
    )
    examples = [
        "What is the total portfolio VaR at 95% confidence?",
        "Which trader has the highest risk exposure?",
        "Are any default trading limits breached?",
        "Show me all Brent Crude positions.",
        "Explain the VaR methodology for our crude oil positions.",
    ]
    selected = st.selectbox("Example questions", [""] + examples, label_visibility="collapsed")
    question = st.text_input(
        "Ask a risk question:",
        value=selected,
        placeholder="e.g. What is the portfolio VaR at 99% confidence?",
    )
    if st.button("Analyse", type="primary") and question:
        if not API_KEY:
            st.error("Set AGENT_API_KEY or the Streamlit secret API_KEY before querying the agent.")
        else:
            with st.spinner("Querying the risk agent..."):
                try:
                    response = requests.post(
                        f"{AGENT_URL}/query",
                        headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
                        json={"message": question},
                        timeout=60,
                    )
                    if response.status_code == 200:
                        answer = response.json()["answer"]
                        st.markdown(f'<div class="answer-box">{answer}</div>', unsafe_allow_html=True)
                    else:
                        st.error(f"Error {response.status_code}: {response.text}")
                except Exception as exc:
                    st.error(f"Connection error: {exc}")

st.markdown("---")
st.caption(
    "Deterministic path: FastAPI `/portfolio`, `/controls`, `/monte-carlo` and the "
    "`risk` package. Agent path: LangGraph + Azure OpenAI + Azure AI Search."
)
