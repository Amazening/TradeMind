# TradeMind: Project Instructions

TradeMind reads a person's share trading history (a CSV export from their broker) and describes the behaviour patterns in it: trading a large share of the portfolio, selling winners sooner than losers, and buying after a sharp rise. Each finding comes with the trades behind it and how much data it rests on.

It started as a 3-day hackathon demo built by a team of 6. Mazen is the only member still working on it. This repo is the rebuild, written from a plan.

The hackathon code is in `../TradeMind (OLD)/` (GitHub: `Amazening/TradeMind-hackathon`, private and archived). Use it as reference only. Do not copy code from it without checking with Mazen, because 6 people wrote it.

## Where Things Are

| Doc | What it holds |
|---|---|
| `docs/01-vision.md` | Why we are building it, who it is for, risks, open questions |
| `docs/02-spec.md` | The spec: user flows, input format, row rules, market data, the three patterns, data contracts, AI explanations, API, frontend |
| `docs/03-milestones.md` | M0 to M8, each with a "done when" list that is ticked as it is met |

Mazen's own project notes are in his Obsidian vault at `1 Projects/TradeMind.md`. The `docs/` folder in this repo is the source of truth for the product.

## How We Work

- The spec and milestones are agreed. Build one milestone at a time, on its own branch (`m6-frontend` and so on), and merge it to `main` when its "done when" list is ticked.
- When something in the spec turns out to be wrong, change the spec and write down why. Several sections have a "found while testing" note. Keep doing that.
- Test against Mazen's real export (`data/private/`) before calling a data-handling change finished. Checks on real data have found problems that hand-made tests did not (a provider's prices being wrong, a missed share consolidation, a model inventing details).
- Ask Mazen before making product decisions. Give a recommendation, not a list of every option.
- Commit when Mazen asks, or when he has asked for a milestone to be completed.

## Product Rules

- **No financial advice.** Output describes what the person did and what patterns it shows. It never tells them what to buy, sell or hold, and never calls a result good or bad. NZ law regulates financial advice.
- **Halal by default.** Mazen invests by Islamic principles. Do not build features that encourage interest-based products, margin, short selling or speculation.
- **Privacy.** Trade histories are personal financial data. Keep as little as possible, for as short a time as possible. Uploads and reports live in memory only, for at most an hour. Logs hold counts and timings, never trades. Error replies never repeat anything from the file.
- **Costs nothing.** v1 must not cost Mazen money. Free tiers only.

## Architecture

Five layers plus a shared core, in `src/trademind/`. Each layer has one job and passes a defined Pydantic shape to the next.

| Layer | Folder | Job |
|---|---|---|
| Core | `core/` | Models, settings, errors, markets, splits, prices, holdings and decisions |
| Ingestion | `ingestion/` | Read a broker CSV into `Trade`s. One reader per broker (Sharesies so far) |
| Enrichment | `enrichment/` | Market prices, splits, exchange rates, a disk cache, and a check that rejects bad prices |
| Analysis | `analysis/` | The three patterns and the `Report` (the main product) |
| Reporting | `reporting/` | Explanations (facts written by code, optionally reworded by a model and checked), text output |
| API | `api/` | FastAPI: upload, status, delete. In-memory jobs |
| CLI | `cli.py` | `import`, `enrich`, `analyse`, `serve`, `version` |
| Frontend | `frontend/` | React and TypeScript: upload, progress and report screens |

Data flows `CSV -> ImportResult -> EnrichedHistory -> Report`. The `Report` JSON is the main product: the CLI, the API and the frontend all start from it.

Rules that matter:
- **Decisions, not rows.** Patterns count decisions: rows for the same share, side, market date and initiator are one decision. Platform trades (auto-invest and so on) count towards holdings but are never judged as the user's choices.
- **Money is `Decimal`**, never `float`. Statistics (p-values, turnover) are floats.
- **Provider data is checked against the user's own trades.** If a share's market prices disagree with the user's trade prices, they are not used. Never trust a provider because it has a clean API.
- **A model never gets raw numbers.** It rewrites sentences written by code. Its reply is checked and thrown away if it adds anything. The report is complete without a model.
- **Nothing in the code names a share, an amount or a date from Mazen's data.** Tests and docs use made-up values.

## Tech Stack

- Python 3.13, uv, FastAPI, Pydantic v2, Typer, httpx. No pandas and no SciPy: the data is small, and the two statistical tests are written with the standard library.
- Market data: Yahoo Finance's unofficial API for building and personal use (not licensed for a public app). A paid, licensed provider is chosen at the deploy milestone. See `docs/02-spec.md` section 4.2.
- Explanations: Groq free tier, or Ollama locally (`OLLAMA_MODEL`, default `qwen2.5:14b`).
- Frontend: React 19, TypeScript, Vite, Vitest, Testing Library, jest-axe, ESLint. No UI framework.
- Hosting (M7): Catalyst Cloud on Mazen's personal account, probably a separate VM from his homelab. One Docker container.

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
uv run trademind serve
```

Other commands: `trademind import <file> [--holdings]` (amounts as written in the file, no splits applied), `trademind enrich <file> [--holdings]` (holdings after splits), and `trademind analyse <file> [--format text] [--explain groq|ollama]`. The API docs are at http://127.0.0.1:8000/api/docs.

The frontend is in `frontend/`. Node 24. From that folder:

```bash
npm install
```

```bash
npm run typecheck
```

```bash
npm run lint
```

```bash
npm test
```

```bash
npm run build
```

`trademind serve` serves `frontend/dist` at the root if it has been built. For live editing, run `npm run dev` as well. It proxies `/api` to port 8000.

**Before saying a change is finished**, run the checks for the side you touched: Python (pytest, ruff check, ruff format --check, mypy) and frontend (typecheck, lint, test). CI runs both (`.github/workflows/ci.yml`).

## Data

- `data/private/` holds Mazen's real broker exports (for example `sharesies-transactions.csv`). It is in `.gitignore`. Never commit it, copy rows from it into tests or docs, or quote real amounts from it in public files.
- `.env` holds API keys. It is in `.gitignore`. `.env.example` lists the names. Never print, log or repeat a key.
- Test data is hand-made and lives with the tests (`tests/helpers.py`, `tests/scenarios.py`, and fixtures in the frontend).

## Tests

- Every pattern has a detected, not-detected and not-enough-data scenario worked out by hand on paper (`tests/test_overtrading.py` and so on). Tests never call the internet: providers are tested with mock transports and fake sources.
- The frontend tests use a fake `fetch`. Each screen has an axe check. The keyboard flow is tested. A Python test measures the colour contrast of every text pair in both themes.

## Code Style

Python:
- Ruff (rules in `pyproject.toml`), line length 100. mypy in strict mode, so every function has type hints.
- Settings and secrets are read only in `src/trademind/core/settings.py`.
- Pydantic models for every data contract between layers.
- No `print`. Use `logging`, and log counts and timings only.
- Small functions with one job. Name things for what they mean in trading terms. Comments say why, not what.

Frontend (TypeScript):
- Strict mode, no `any`. Components are small and take props.
- Text on screen is plain New Zealand English at a reading age of 12. Never describe a result as good or bad.
- No inline styles and no inline scripts, so the Content Security Policy holds. Colours are tokens in `styles.css`.
- Every new screen gets a test, including an axe check and a keyboard check where it takes input.

## Git

- Default branch: `main`. No GitHub remote yet. It will be a new public repo, `Amazening/TradeMind`.
- The repo will be public, so no secrets and no personal data in any commit.
- Commit messages end with the co-author line.
