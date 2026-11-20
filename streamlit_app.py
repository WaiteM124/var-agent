import os

import requests
import streamlit as st

AGENT_URL = st.secrets.get("AGENT_URL", os.getenv("AGENT_URL", "http://localhost:8000"))
API_KEY = st.secrets.get("API_KEY", os.getenv("AGENT_API_KEY", ""))

st.set_page_config(page_title="VaR Risk Agent", page_icon="📊", layout="centered")

st.markdown("""
<style>
    .main { background-color: #0e1117; }
    .stTextInput input { background-color: #1e2130; color: white; }
    .answer-box { background-color: #1e2130; border-left: 4px solid #00b4d8; padding: 1rem; border-radius: 4px; margin-top: 1rem; color: #ffffff; font-size: 0.95rem; line-height: 1.6; }
    h1 { color: #00b4d8; }
</style>
""", unsafe_allow_html=True)

st.title("📊 VaR Risk Agent")
st.caption("Natural language risk analysis over a synthetic energy trading portfolio — powered by Azure OpenAI + Azure AI Search")

st.markdown("---")

col1, col2, col3 = st.columns(3)
col1.metric("Positions", "15")
col2.metric("Total Notional", "$41.35M")
col3.metric("95% VaR", "$1.89M")

st.markdown("---")

st.markdown("**Try these questions:**")
examples = [
    "What is the total portfolio VaR at 95% confidence?",
    "Which trader has the highest risk exposure?",
    "Explain the VaR methodology for our crude oil positions.",
    "What are the trading controls for managing market risk?",
    "Show me all Brent Crude positions."
]

selected = st.selectbox("Example questions", [""] + examples, label_visibility="collapsed")

question = st.text_input("Ask a risk question:", value=selected, placeholder="e.g. What is the portfolio VaR at 99% confidence?")

if st.button("Analyse", type="primary") and question:
    if not API_KEY:
        st.error("Set AGENT_API_KEY or Streamlit secret API_KEY before querying the agent.")
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
            except Exception as e:
                st.error(f"Connection error: {e}")

st.markdown("---")
st.caption("Architecture: LangGraph agent · Azure OpenAI · Azure AI Search · FastAPI · Streamlit")
