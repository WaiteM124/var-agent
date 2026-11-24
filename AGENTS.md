# AGENTS.md — VaR Agent contributor & agent guide

Single source of truth for humans and AI agents (including Cursor) working in this repository.

**Product:** VaR Agent — a proof-of-concept risk assistant over a **synthetic** 15-position energy-trading book. It exposes deterministic VaR / limit tools, a FastAPI surface, an optional Streamlit UI, and a LangGraph natural-language path that calls those same tools (Azure OpenAI + Azure AI Search for methodology retrieval).

**Owner:** Miles Waite. Public showcase / portfolio piece. This is a demo, not a production ETRM or a live market-risk engine. Do not use it for real trading decisions.

---

## Repository map

| Path | Role |
|---|---|
| `risk/` | Deterministic portfolio load/filter/aggregate, parametric + Monte Carlo VaR, limit checks |
| `agent/` | LangGraph agent: tools wrap `risk/`; Azure OpenAI + Azure AI Search only for `/query` |
| `main.py` | FastAPI app: `/health`, `/portfolio`, `/controls`, `/monte-carlo`, authenticated `/query` |
| `streamlit_app.py` | Streamlit UI — Limit checks / Monte Carlo in-process; Ask the agent → `POST /query` |
| `data/positions.csv` | Synthetic book (invented traders and notionals) |
| `docs/` | Methodology notes (`var.md`, `monte_carlo.md`, `trading_controls.md`) indexed for retrieval |
| `docs/decisions/` | Architecture decision records |
| `examples/run_var_example.py` | Seeded worked Monte Carlo example (no cloud); writes `examples/output/` |
| `tests/` | Known-answer tests for book aggregation, VaR, limits, and FastAPI demo endpoints |
| `.github/workflows/ci.yml` | PR/push CI: pinned ruff + pytest + worked example |

Stack: **Python 3.11+** (CI uses 3.12), pandas, NumPy, pytest, ruff, FastAPI, LangGraph, Azure OpenAI, Azure AI Search, Streamlit. Deterministic core, tests, and the worked example need **no cloud credentials**.

---

## Product principles (non-negotiable)

1. **Risk numbers come from deterministic code, never the LLM.** VaR, expected shortfall, aggregations, and limit breaches are computed in `risk/` (and the FastAPI routes that call it). The agent may only **quote** tool output. Do not invent figures in prompts, docs, or UI copy that a tool did not return.
2. **Keep the three VaR figures distinct.** Pre-computed book VaR (sum of CSV columns), undiversified parametric VaR, and Monte Carlo VaR are different estimators with documented assumptions. Do not conflate them or “reconcile” them away in code or narrative.
3. **Synthetic demo, explicit limits.** The book is invented; controls are illustrative post-hoc checks, not a pre-trade OMS gate. State assumptions (seed, correlation, delta-only options, horizon) whenever reporting MC or parametric results.
4. **Azure only on the agent path.** Lazy-construct Azure clients on first `/query` (or methodology tool use). `/health`, `/portfolio`, `/controls`, `/monte-carlo`, Streamlit Limit checks / Monte Carlo, pytest, and `examples/run_var_example.py` must keep working offline.

---

## Engineering standards

- **Typed code.** Type hints on public functions and methods. Pydantic models at FastAPI request/response boundaries (`main.py`). Prefer clear contracts at tool and package boundaries.
- **Tests as the spec.** Prefer known-answer / golden cases for book totals, parametric VaR, seeded Monte Carlo determinism, and default limit breaches. Cover happy path and edge cases (empty book, bad confidence, invalid correlation).
- **Green before PR.** `ruff check` / `ruff format --check` and pytest must pass locally. CI must stay green.
- **Small, focused PRs.** One concern per PR; clear title and description; state assumptions and out-of-scope items.
- **No secrets in git.** Use `.env` (gitignored) or a secret manager. Never commit API keys, credentials, connection strings, or private keys. Prefer `.env.example` for documentation. Do not put secrets in git remotes or CI logs.
- **Pin versions for production-bound work.** Prefer pinned dependency and model / deployment names (`AZURE_OPENAI_DEPLOYMENT`, embedding deployment, API version) when hardening; do not silently bump models in a feature PR. CI pins `ruff`.
- **Structured logging.** Prefer structured / contextual logs when adding observability; never log secrets or bearer tokens. (This PoC is light on logging today — follow this when extending.)
- **Evaluate AI / LLM output; never trust blindly.** Agent answers must be grounded in tool results. There is no automated LLM eval suite yet; do not claim evaluated agent quality without measured evidence. Deterministic risk maths are covered by pytest and the worked example.
- **Docs track behaviour.** Update README / ADRs / this file when behaviour, contracts, or run instructions change. Do not invent features or numbers in docs.

### Definition of done

- [ ] Principles above respected (especially deterministic risk numbers; distinct VaR figures; offline core)
- [ ] Types and boundary contracts in place where APIs change
- [ ] Tests added or updated; known-answer cases for risk maths / limits
- [ ] Lint and tests pass (`ruff` + `pytest`; CI equivalents)
- [ ] No secrets introduced
- [ ] Docs updated if behaviour or workflow changed

---

## How to run and test

### Setup

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[dev]"            # includes pinned ruff + pytest + FastAPI test deps
cp .env.example .env               # only needed for /query and Ask the agent
```

Optional app / UI extras:

```bash
pip install -r requirements.txt              # or: pip install -e ".[app]"
pip install -r streamlit_requirements.txt
```

### Run (deterministic — no Azure)

```bash
pytest -q
python examples/run_var_example.py
uvicorn main:app --reload --port 8000
# GET  /health /portfolio /controls
# POST /monte-carlo
```

### Run (agent path — Azure required)

Set `AGENT_API_KEY`, `AZURE_OPENAI_*`, and `AZURE_SEARCH_*` (see `.env.example` and README). Then:

```bash
uvicorn main:app --reload --port 8000
streamlit run streamlit_app.py
# POST /query requires Authorization: Bearer $AGENT_API_KEY
```

### Test and lint

```bash
ruff check .
ruff format --check .
pytest -q
python examples/run_var_example.py   # also run in CI
```

There is **no** LLM / agent eval suite in this repository. CI therefore has no eval-gate job: the deterministic pytest suite and worked example are cheap, seeded, and required on every PR. An Azure-backed agent eval should be added later as a **manual or scheduled** check (needs credentials, non-deterministic, cost), not as a blocking PR job.

---

## Workflow for agents

1. **Read before writing.** Inspect the real layout, ADRs, neighbouring tests, and README figures. Prefer matching existing patterns over inventing new ones.
2. **Plan large changes.** For multi-file or cross-cutting work, outline the approach, files touched, and risks before coding. Keep scope to the assigned task.
3. **Do not weaken tests.** Never delete, skip, or loosen assertions solely to make CI pass. Fix the code or add a justified, documented test change.
4. **State assumptions in the PR.** Call out env expectations, concurrent work, and follow-ups.
5. **Docs/config-only vs product code.** If the task says docs/config only, do not change application behaviour.
6. **Cursor rules.** Follow `.cursor/rules/*.mdc`; they summarise this file for scoped globs. When in conflict, **this file wins**.

---

## Related docs

- [CONTRIBUTING.md](CONTRIBUTING.md) — short human setup and PR conventions
- [README.md](README.md) — product overview, architecture, worked example, env vars
- [docs/decisions/](docs/decisions/) — decision records
