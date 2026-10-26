# TradeMind

TradeMind reads your share trading history (a CSV export from your broker) and shows you the behaviour patterns in it, such as trading too often, selling winners while holding losers, and buying after a sharp price rise. Each finding comes with the trades behind it and a note on how much evidence there is.

It describes past behaviour. It is not financial advice.

**Status:** being rebuilt from a plan. See [`docs/`](docs/) for the vision, spec and milestones.

## Development

Needs [uv](https://docs.astral.sh/uv/). uv installs the right Python version itself.

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
uv run mypy src tests
```

```bash
uv run trademind --help
```

Copy `.env.example` to `.env` for API keys. Never commit `.env`.
