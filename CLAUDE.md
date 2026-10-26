# TradeMind: Project Instructions

TradeMind reads a person's share trading history (a CSV export, for example from Sharesies) and shows them the behaviour patterns in it, such as panic selling, FOMO buying and overtrading.

It started as a 3-day hackathon demo built by a team of 6. Mazen is the only member still working on it. This repo is the rebuild, written from a plan.

The hackathon code is in `../TradeMind (OLD)/` (GitHub: `Amazening/TradeMind-hackathon`, private and archived). Use it as reference only. Do not copy code from it without checking with Mazen, because 6 people wrote it.

## How We Work on This Project

Work happens in phases. Do not skip ahead.

1. **Vision** (`docs/01-vision.md`): why the project exists, who it is for, whether it is worth doing, risks and open questions.
2. **Spec** (`docs/02-spec.md`): user flows, inputs and outputs, the data contracts between layers.
3. **Milestones** (`docs/03-milestones.md`): small, shippable steps, each with a clear "done".
4. **Build**: one milestone at a time.

Rules for each phase:
- Do not write product code until the spec and milestones are agreed.
- Decisions go in the docs with the reason behind them. If a later decision changes an earlier one, update the earlier doc and note the change.
- Ask Mazen before making product decisions. Give a recommendation, not a list of every option.
- Mazen's own project notes are in his Obsidian vault at `1 Projects/TradeMind.md`. The `docs/` folder in this repo is the source of truth for the product itself.

## Product Rules

- **No financial advice.** Output describes what the person did and what patterns it shows. It does not tell them what to buy, sell or hold. NZ law regulates financial advice, so keep everything factual and informational.
- **Halal by default.** Mazen invests by Islamic principles. Do not build features that encourage interest-based products, margin, short selling or speculation.
- **Privacy.** Trade histories are personal financial data. Keep as little as possible, for as short a time as possible. Never log raw uploads.

## Architecture (Planned)

The rebuild splits the work into five layers plus a shared core. Each layer has one job and passes a defined data shape to the next.

| Layer | Job |
|---|---|
| Ingestion | Read the CSV, validate it, turn it into one standard trade format |
| Enrichment | Add market data (prices before and after each trade) |
| Analysis | Detect behaviour patterns and score them. Output is structured JSON |
| Reporting | Turn the analysis JSON into HTML, PDF or email |
| Frontend | Upload a file, show progress, show the results |
| Core | Shared schemas, settings, errors and helpers |

The analysis JSON is the main product. The web app, an API or a CLI should all be able to use it without the reporting layer.

The data contracts between layers will be defined in `docs/02-spec.md`.

## Tech Stack

Hackathon code (for reference):
- Backend: Python, FastAPI, Pandas
- Frontend: React loaded from a CDN, plain CSS (`app/static/`)
- Market data: Alpha Vantage
- AI analysis: Groq
- PDF: fpdf2. Email: SMTP
- Hosting target: Azure App Service and Azure Static Web Apps

The stack for the rebuild is decided in the spec phase. Until then, do not add new dependencies.

## Running the Code

Python 3.13, managed with uv. On Mazen's Windows machine, uv keeps its Pythons in `D:\50-59 Development\51 Languages and RunTimes\51.04 Python` (set by the `UV_PYTHON_INSTALL_DIR` user variable). Use `uv run` and `uv add`, not `pip`.

```bash
uv sync
```

```bash
uv run pytest
```

```bash
uv run ruff check
```

```bash
uv run ruff format
```

```bash
uv run mypy src tests
```

```bash
uv run trademind --help
```

```bash
uv run trademind serve
```

The web API docs are then at http://127.0.0.1:8000/api/docs. Other commands: `trademind import <file>`, `trademind enrich <file>` and `trademind analyse <file> [--format text] [--explain groq|ollama]`.

Before saying any change is finished, run all four checks (pytest, ruff check, ruff format --check, mypy). CI runs the same checks (`.github/workflows/ci.yml`).

## Data

- `data/private/` holds Mazen's real broker exports (for example `sharesies-transactions.csv`). It is in `.gitignore`. Never commit it, copy rows from it into tests or docs, or quote real amounts from it in public files.
- Test data is hand-made and lives with the tests.

## Tests

Plan: pytest, with tests written alongside each layer. Each behaviour pattern gets a test that uses a small hand-made CSV scenario with a known expected result. The old repo has some scenario files (`evaluation_*.csv`) that can serve as ideas.

## Code Style

For the rebuild (Python):
- Format and lint with Ruff (rules in `pyproject.toml`). mypy in strict mode, so every function has type hints.
- Settings and secrets are read only in `src/trademind/core/settings.py`.
- Pydantic models for every data contract between layers.
- No secrets in code. Read them from environment variables through the settings module.
- No `print` for debugging in committed code. Use `logging`.
- Small functions with one job. Name things for what they mean in trading terms.

## Git

- Default branch: `main`. No GitHub remote yet. It will be a new public repo, `Amazening/TradeMind`.
- The repo will be public, so no secrets and no personal data in any commit.
- Work on a branch per milestone. Commit only when Mazen asks.
