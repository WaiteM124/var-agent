from __future__ import annotations

import json
import os
from typing import Annotated, Any

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import tool
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from typing_extensions import TypedDict

from risk.controls import LimitConfig, check_limits
from risk.portfolio import (
    DEFAULT_POSITIONS_PATH,
    aggregate_precomputed_var,
    filter_positions,
    load_positions,
)

load_dotenv()

_df = load_positions(DEFAULT_POSITIONS_PATH)

SYSTEM_PROMPT = """You are a risk analyst assistant for an energy trading desk.
You have access to a synthetic trading book and risk methodology documentation.
When asked about risk, retrieve the relevant positions first, calculate VaR, and
check limits. Quote specific position IDs and dollar amounts. Be precise and concise.
Do not invent figures that a tool did not return."""


class State(TypedDict):
    messages: Annotated[list, add_messages]


def _azure_clients() -> tuple[Any, Any, Any]:
    """Create Azure OpenAI and Search clients from the environment.

    Called on the first natural-language query, not at import time, so the
    deterministic tools and FastAPI demo endpoints can run without credentials.
    """
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    api_key = os.getenv("AZURE_OPENAI_KEY")
    if not endpoint or not api_key:
        raise RuntimeError("AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_KEY must be set for /query")

    from azure.core.credentials import AzureKeyCredential
    from azure.search.documents import SearchClient
    from langchain_openai import AzureChatOpenAI
    from openai import AzureOpenAI

    search_endpoint = os.getenv("AZURE_SEARCH_ENDPOINT")
    search_key = os.getenv("AZURE_SEARCH_KEY")
    if not search_endpoint or not search_key:
        raise RuntimeError("AZURE_SEARCH_ENDPOINT and AZURE_SEARCH_KEY must be set for methodology retrieval")

    openai_client = AzureOpenAI(
        azure_endpoint=endpoint,
        api_key=api_key,
        api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-01"),
    )
    search_client = SearchClient(
        endpoint=search_endpoint,
        index_name=os.getenv("AZURE_SEARCH_INDEX", "risk-docs"),
        credential=AzureKeyCredential(search_key),
    )
    llm = AzureChatOpenAI(
        azure_endpoint=endpoint,
        api_key=api_key,
        azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o"),
        api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-01"),
        temperature=0,
    )
    return openai_client, search_client, llm


@tool
def get_positions(trader: str | None = None, desk: str | None = None, commodity: str | None = None) -> str:
    """Get trading positions. Filter by trader name, desk, or commodity. Leave blank for all positions."""
    frame = filter_positions(_df, trader=trader, desk=desk, commodity=commodity)
    return frame.to_json(orient="records", indent=2)


@tool
def calculate_portfolio_var(
    trader: str | None = None,
    desk: str | None = None,
    confidence: str = "95",
) -> str:
    """Aggregate pre-computed 1-day VaR across positions. Confidence level: 95 or 99."""
    frame = filter_positions(_df, trader=trader, desk=desk)
    return json.dumps(aggregate_precomputed_var(frame, confidence), indent=2)


@tool
def check_trading_controls(
    trader: str | None = None,
    desk: str | None = None,
    commodity: str | None = None,
) -> str:
    """Check the selected positions against default notional, VaR, and concentration limits."""
    frame = filter_positions(_df, trader=trader, desk=desk, commodity=commodity)
    breaches = check_limits(frame, LimitConfig())
    return json.dumps(
        {"breach_count": len(breaches), "breaches": [b.to_dict() for b in breaches]},
        indent=2,
    )


@tool
def get_risk_methodology(query: str) -> str:
    """Retrieve risk methodology documentation (VaR, Monte Carlo, trading controls) from Azure AI Search."""
    from azure.search.documents.models import VectorizedQuery

    openai_client, search_client, _ = _get_cached_clients()
    embedding = (
        openai_client.embeddings.create(
            model=os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-3-small"),
            input=query,
        )
        .data[0]
        .embedding
    )
    vector_query = VectorizedQuery(vector=embedding, k_nearest_neighbors=2, fields="embedding")
    results = search_client.search(search_text=None, vector_queries=[vector_query], select=["content", "filename"])
    docs = [row["content"] for row in results]
    return "\n\n---\n\n".join(docs) if docs else "No relevant documentation found."


_CLIENTS: tuple[Any, Any, Any] | None = None
_GRAPH = None


def _get_cached_clients() -> tuple[Any, Any, Any]:
    global _CLIENTS
    if _CLIENTS is None:
        _CLIENTS = _azure_clients()
    return _CLIENTS


tools = [get_positions, calculate_portfolio_var, check_trading_controls, get_risk_methodology]


def _build_graph():
    _, _, llm = _get_cached_clients()
    llm_with_tools = llm.bind_tools(tools)
    tool_node = ToolNode(tools)

    def agent_node(state: State):
        messages = state["messages"]
        if not any(getattr(m, "type", None) == "system" for m in messages):
            messages = [SystemMessage(content=SYSTEM_PROMPT)] + list(messages)
        response = llm_with_tools.invoke(messages)
        return {"messages": [response]}

    def should_continue(state: State):
        last = state["messages"][-1]
        return "tools" if getattr(last, "tool_calls", None) else END

    graph = StateGraph(State)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", tool_node)
    graph.set_entry_point("agent")
    graph.add_conditional_edges("agent", should_continue)
    graph.add_edge("tools", "agent")
    return graph.compile()


def query(question: str) -> str:
    global _GRAPH
    if _GRAPH is None:
        _GRAPH = _build_graph()
    result = _GRAPH.invoke({"messages": [HumanMessage(content=question)]})
    return result["messages"][-1].content


if __name__ == "__main__":
    questions = [
        "What is the total portfolio VaR at 95% confidence?",
        "Which trader has the highest risk exposure?",
        "Are any default trading limits breached?",
    ]
    for question in questions:
        print(f"\nQ: {question}")
        print(f"A: {query(question)}\n{'=' * 60}")
