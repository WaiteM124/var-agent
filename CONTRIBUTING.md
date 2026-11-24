# Contributing

Short human guide. Agents and detailed product rules: see [AGENTS.md](AGENTS.md).

## Setup

**Prerequisites:** Python 3.11+ (3.12 recommended; matches CI), pip.

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[dev]"            # pinned ruff, pytest, FastAPI test deps
cp .env.example .env               # only for /query and the Streamlit agent tab
```

Optional: `pip install -r requirements.txt` (or `pip install -e ".[app]"`) and `pip install -r streamlit_requirements.txt` for the full API + UI stack.

### Pre-commit (recommended)

```bash
pip install pre-commit
pre-commit install
```

This runs the pinned ruff hooks and gitleaks on staged files before each commit. You can also run `pre-commit run --all-files` locally.

## Running

```bash
uvicorn main:app --reload --port 8000
# Deterministic: GET /health /portfolio /controls ; POST /monte-carlo
python examples/run_var_example.py
streamlit run streamlit_app.py     # Limit checks / Monte Carlo offline; Ask the agent needs Azure
```

## Tests and lint

```bash
ruff check .
ruff format --check .
pytest -q
python examples/run_var_example.py
python evals/run_evals.py
```

CI requires lint, pytest, the worked example, and the offline **eval-gate** on every PR. Optional live Azure smoke: Actions → `eval-live` → Run workflow (needs secrets; see `AGENTS.md`).

## Branch and PR conventions

- Branch from `main` with a short, descriptive name.
- Keep PRs **small and focused** on one concern.
- Fill in the pull request template checklist.
- State assumptions, concurrent work, and follow-ups in the description.
- Do not commit secrets; use env vars or a secret manager.
- Do not delete or weaken tests solely to make CI pass.

## Definition of done

- Product principles in `AGENTS.md` respected (deterministic risk numbers; distinct VaR figures; offline core)
- Tests added/updated and passing; lint clean
- No secrets in the change
- Docs updated when behaviour or workflow changes
- CI green on the PR
