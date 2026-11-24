"""Offline eval helpers: risk known-answers and fixture-driven agent checks.

No Azure or LangChain imports. Tool behaviour mirrors ``agent.agent`` tools by
calling the same ``risk/`` functions those tools wrap.
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any

import numpy as np

from risk.controls import LimitConfig, check_limits
from risk.portfolio import (
    DEFAULT_POSITIONS_PATH,
    aggregate_precomputed_var,
    filter_positions,
    load_positions,
)
from risk.var import historical_var, parametric_var, simulate_portfolio_pnl, var_from_pnl

ROOT = Path(__file__).resolve().parent
CASES_DIR = ROOT / "cases"
FIXTURES_DIR = ROOT / "fixtures"
BASELINE_PATH = ROOT / "baseline.json"
RESULTS_PATH = ROOT / "results.json"

_BOOK = load_positions(DEFAULT_POSITIONS_PATH)

# Material dollar-like magnitudes claimed in answers must appear in tool output.
_MATERIAL_ABS = 100.0

_NUMBER_RE = re.compile(r"(?<![\w/])(?P<sign>-)?(?P<body>\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+\.\d+|\d+)(?![\w/])")

_REFUSAL_MARKERS = (
    "out of scope",
    "cannot",
    "can't",
    "do not have",
    "don't have",
    "unable",
    "only answer",
    "synthetic book",
    "demo book",
    "no live",
    "not available",
    "defer",
    "outside",
)


def load_case_files() -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for path in sorted(CASES_DIR.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            cases.extend(data)
        else:
            cases.append(data)
    return cases


def load_fixture(name: str) -> dict[str, Any]:
    path = FIXTURES_DIR / name
    return json.loads(path.read_text(encoding="utf-8"))


def invoke_tool(name: str, args: dict[str, Any] | None = None) -> str:
    """Execute a tool by name using the same risk functions as the LangGraph tools."""
    args = dict(args or {})
    if name == "get_positions":
        frame = filter_positions(
            _BOOK,
            trader=args.get("trader"),
            desk=args.get("desk"),
            commodity=args.get("commodity"),
        )
        return frame.to_json(orient="records", indent=2)
    if name == "calculate_portfolio_var":
        frame = filter_positions(_BOOK, trader=args.get("trader"), desk=args.get("desk"))
        confidence = str(args.get("confidence", "95"))
        return json.dumps(aggregate_precomputed_var(frame, confidence), indent=2)
    if name == "check_trading_controls":
        frame = filter_positions(
            _BOOK,
            trader=args.get("trader"),
            desk=args.get("desk"),
            commodity=args.get("commodity"),
        )
        breaches = check_limits(frame, LimitConfig())
        return json.dumps(
            {"breach_count": len(breaches), "breaches": [b.to_dict() for b in breaches]},
            indent=2,
        )
    if name == "get_risk_methodology":
        raise RuntimeError("get_risk_methodology requires Azure and is not available offline")
    raise ValueError(f"unknown tool: {name}")


def extract_numbers(text: str) -> list[float]:
    values: list[float] = []
    for match in _NUMBER_RE.finditer(text):
        raw = (match.group("sign") or "") + match.group("body").replace(",", "")
        try:
            values.append(float(raw))
        except ValueError:
            continue
    return values


def numbers_close(a: float, b: float, *, rel: float = 1e-9, abs_tol: float = 1e-6) -> bool:
    return math.isclose(a, b, rel_tol=rel, abs_tol=abs_tol)


def grounded_numbers(answer: str, tool_outputs: list[str]) -> tuple[bool, list[float]]:
    """Return whether every material number in ``answer`` appears in tool outputs."""
    allowed = extract_numbers("\n".join(tool_outputs))
    claimed = [n for n in extract_numbers(answer) if abs(n) >= _MATERIAL_ABS]
    invented: list[float] = []
    for value in claimed:
        if not any(numbers_close(value, allowed_value, rel=1e-9, abs_tol=0.51) for allowed_value in allowed):
            invented.append(value)
    return (len(invented) == 0, invented)


def looks_like_refusal(answer: str) -> bool:
    lowered = answer.lower()
    return any(marker in lowered for marker in _REFUSAL_MARKERS)


def run_risk_case(case: dict[str, Any]) -> dict[str, Any]:
    kind = case["kind"]
    expect = case["expect"]
    detail: dict[str, Any] = {}

    if kind == "risk_parametric":
        got = parametric_var(
            float(case["inputs"]["notional"]),
            float(case["inputs"]["volatility_1d"]),
            case["inputs"].get("confidence", 95),
        )
        detail["got"] = got
        detail["expected"] = expect["value"]
        ok = math.isclose(
            got,
            float(expect["value"]),
            rel_tol=float(expect.get("rel_tol", 0.0)),
            abs_tol=float(expect.get("abs_tol", 1e-9)),
        )
        return {"pass": ok, "detail": detail}

    if kind == "risk_historical":
        got = historical_var(case["inputs"]["pnl"], case["inputs"].get("confidence", 95))
        detail["got"] = got
        detail["expected"] = expect["value"]
        ok = math.isclose(
            got,
            float(expect["value"]),
            rel_tol=float(expect.get("rel_tol", 0.0)),
            abs_tol=float(expect.get("abs_tol", 1e-9)),
        )
        return {"pass": ok, "detail": detail}

    if kind == "risk_monte_carlo":
        inputs = case["inputs"]
        frame = _BOOK
        if inputs.get("position_id"):
            frame = _BOOK.loc[_BOOK["position_id"] == inputs["position_id"]].copy()
        pnl = simulate_portfolio_pnl(
            frame,
            n_paths=int(inputs.get("n_paths", 20_000)),
            seed=int(inputs.get("seed", 42)),
            correlation=float(inputs.get("correlation", 0.4)),
        )
        got = var_from_pnl(pnl, inputs.get("confidence", 95))
        detail["got"] = got
        if "value" in expect:
            detail["expected"] = expect["value"]
            ok = math.isclose(
                got,
                float(expect["value"]),
                rel_tol=float(expect.get("rel_tol", 1e-12)),
                abs_tol=float(expect.get("abs_tol", 1e-6)),
            )
        elif "min" in expect and "max" in expect:
            detail["range"] = [expect["min"], expect["max"]]
            ok = float(expect["min"]) <= got <= float(expect["max"])
        else:
            raise ValueError(f"monte carlo case {case['id']} missing expect value or range")
        if expect.get("deterministic_repeat"):
            pnl_b = simulate_portfolio_pnl(
                frame,
                n_paths=int(inputs.get("n_paths", 20_000)),
                seed=int(inputs.get("seed", 42)),
                correlation=float(inputs.get("correlation", 0.4)),
            )
            detail["deterministic"] = bool(np.array_equal(pnl, pnl_b))
            ok = ok and detail["deterministic"]
        return {"pass": ok, "detail": detail}

    if kind == "risk_precomputed":
        frame = filter_positions(
            _BOOK,
            trader=case["inputs"].get("trader"),
            desk=case["inputs"].get("desk"),
            commodity=case["inputs"].get("commodity"),
        )
        got = aggregate_precomputed_var(frame, case["inputs"].get("confidence", 95))
        detail["got"] = got
        ok = True
        for key, expected in expect.items():
            if got.get(key) != expected:
                ok = False
                detail["mismatch"] = {"key": key, "got": got.get(key), "expected": expected}
                break
        return {"pass": ok, "detail": detail}

    raise ValueError(f"unsupported risk kind: {kind}")


def run_agent_fixture_case(case: dict[str, Any]) -> dict[str, Any]:
    fixture = load_fixture(case["fixture"])
    expect = case["expect"]
    tool_calls: list[dict[str, Any]] = []
    tool_outputs: list[str] = []
    final_answer = ""

    for turn in fixture["turns"]:
        if "tool_calls" in turn:
            for call in turn["tool_calls"]:
                name = call["name"]
                args = call.get("args") or {}
                tool_calls.append({"name": name, "args": args})
                tool_outputs.append(invoke_tool(name, args))
        if "content" in turn and turn["content"] is not None:
            final_answer = str(turn["content"])

    detail: dict[str, Any] = {
        "question": fixture.get("question"),
        "tools_called": [c["name"] for c in tool_calls],
        "answer_preview": final_answer[:240],
    }

    ok = True
    reasons: list[str] = []

    expected_tools = expect.get("tools")
    if expected_tools is not None:
        called = [c["name"] for c in tool_calls]
        if called != list(expected_tools):
            ok = False
            reasons.append(f"tools {called} != expected {expected_tools}")

    if expect.get("forbid_tools"):
        forbidden = set(expect["forbid_tools"])
        hit = forbidden.intersection(c["name"] for c in tool_calls)
        if hit:
            ok = False
            reasons.append(f"forbidden tools called: {sorted(hit)}")

    if expect.get("grounded", False):
        grounded, invented = grounded_numbers(final_answer, tool_outputs)
        detail["invented_numbers"] = invented
        if not grounded:
            ok = False
            reasons.append(f"ungrounded numbers: {invented}")

    for needle in expect.get("must_contain", []):
        if str(needle) not in final_answer:
            ok = False
            reasons.append(f"missing substring: {needle!r}")

    for needle in expect.get("must_not_contain", []):
        if str(needle).lower() in final_answer.lower():
            ok = False
            reasons.append(f"forbidden substring: {needle!r}")

    if expect.get("refusal", False):
        if tool_calls and not expect.get("allow_tools_on_refusal", False):
            ok = False
            reasons.append("refusal case must not call tools")
        if not looks_like_refusal(final_answer):
            ok = False
            reasons.append("answer lacks refusal/deferral language")
        material = [n for n in extract_numbers(final_answer) if abs(n) >= _MATERIAL_ABS]
        if material:
            ok = False
            reasons.append(f"refusal answer claimed material numbers: {material}")

    detail["reasons"] = reasons
    return {"pass": ok, "detail": detail}


def run_case(case: dict[str, Any]) -> dict[str, Any]:
    kind = case["kind"]
    if kind.startswith("risk_"):
        outcome = run_risk_case(case)
    elif kind.startswith("agent_"):
        outcome = run_agent_fixture_case(case)
    else:
        raise ValueError(f"unsupported case kind: {kind}")
    return {
        "id": case["id"],
        "label": case["label"],
        "kind": kind,
        "pass": bool(outcome["pass"]),
        "detail": outcome.get("detail", {}),
    }


def summarise(results: list[dict[str, Any]]) -> dict[str, Any]:
    by_label: dict[str, list[bool]] = {}
    for row in results:
        by_label.setdefault(row["label"], []).append(bool(row["pass"]))
    label_rates = {label: (sum(flags) / len(flags) if flags else 0.0) for label, flags in sorted(by_label.items())}
    total = len(results)
    passed = sum(1 for row in results if row["pass"])
    return {
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "pass_rate": (passed / total) if total else 0.0,
        "by_label": label_rates,
        "failed_ids": [row["id"] for row in results if not row["pass"]],
    }


def compare_to_baseline(summary: dict[str, Any], baseline: dict[str, Any]) -> list[str]:
    """Return human-readable regression messages; empty means baseline met."""
    regressions: list[str] = []
    min_rate = float(baseline.get("min_pass_rate", 1.0))
    if float(summary["pass_rate"]) + 1e-12 < min_rate:
        regressions.append(f"overall pass_rate {summary['pass_rate']:.4f} < baseline {min_rate:.4f}")
    for label, floor in sorted(baseline.get("by_label", {}).items()):
        got = float(summary["by_label"].get(label, 0.0))
        if got + 1e-12 < float(floor):
            regressions.append(f"label {label!r} pass_rate {got:.4f} < baseline {float(floor):.4f}")
    return regressions
