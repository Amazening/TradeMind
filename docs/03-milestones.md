# TradeMind: Milestones

Status: draft, 2026-10-26.

Each milestone is small, ends in something that works, and has a clear "done". Build them in order. Each one gets its own branch, and is merged to `main` when its "done" list is ticked.

Section numbers refer to `02-spec.md`.

## Overview

| # | Milestone | What exists at the end |
|---|---|---|
| M0 | Project setup | An empty project that installs, lints, tests and runs CI |
| M1 | Read Sharesies trades | `trademind import` reads Mazen's real file correctly |
| M2 | Market prices | Every trade has prices around it, with splits handled |
| M3 | Patterns | `trademind analyse` gives a full JSON report. **First useful version for Mazen** |
| M4 | AI explanations | Findings come with plain-English text |
| M5 | Web API | The report can be made over HTTP |
| M6 | Web frontend | Upload, progress and report screens |
| M7 | Deploy | Live at a public URL on Catalyst Cloud |
| M8 | Test users | 5 people have used it. v1 is done |

M0 to M3 give a working tool from the command line. M4 to M8 turn it into a public web app.

## M0: Project Setup

- uv project with Python 3.13, the `src/trademind/` layout (section 12) and empty layer packages.
- Ruff for lint and format. mypy in strict mode, with the Pydantic plugin (chosen because it needs no Node.js and Pydantic supports it directly).
- pytest with one placeholder test.
- Settings module that reads `.env` (section 10, Security).
- GitHub Actions: lint, type check and tests on every push.
- Mazen creates the new public repo `Amazening/TradeMind` and adds it as the remote.
- README with one paragraph on what TradeMind is and how to run the tests.

**Done when:**
- [x] `uv run pytest` passes locally (2026-10-26: 4 tests, plus Ruff and mypy clean).
- [ ] CI passes on GitHub (after Mazen creates the repo and pushes).
- [ ] `git log` shows no secrets or personal data.

## M1: Read Sharesies Trades

- Core models: `Trade`, `ImportResult` (section 6.1).
- Sharesies reader following the rules in sections 2 and 3: UTC times, sides, `initiated_by`, fees, `Decimal` money, skipped rows with reasons.
- Broker detection from the CSV header.
- Decisions: group same share, same side, same market date (section 3).
- Holdings and average cost helper in `core/`.
- CLI: `trademind import <file>` prints a summary (rows, trades, decisions, skipped rows, markets).
- Hand-made test CSVs: normal trades, split fills, platform trades, a transfer out, bad rows.

**Done when:**
- [ ] All tests pass.
- [ ] Running it on Mazen's file gives row and trade counts that match a manual count in a spreadsheet.
- [ ] Holdings after the last trade match what Sharesies shows (Mazen checks).

## M2: Market Prices

- `PriceSource` interface (section 4.3).
- Yahoo provider (section 4.2).
- A fake provider with hand-made prices, used in all tests.
- Disk cache for prices.
- Split and consolidation adjustment for trades (section 4.1).
- Delisted shares: fall back to the user's own trade prices, and add a data note.
- Exchange rates to NZD.
- `EnrichedHistory` model (section 6.2).
- A check script that runs the 6 test cases from section 4.2 against any provider.

**Done when:**
- [ ] All tests pass, with no internet calls in tests.
- [ ] Mazen's file enriches without errors. The delisted ASX share shows as delisted with a data note.
- [ ] A share consolidation is adjusted: no fake 2,400% jump.
- [ ] A second run uses the cache and makes no network calls.

## M3: Patterns

- Overtrading (section 5.1). Check the turnover definition against the Barber and Odean paper first.
- Disposition effect (section 5.2).
- Buying after a run-up (section 5.3).
- Confidence levels (section 5.4).
- `Report` model (section 6.3).
- CLI: `trademind analyse <file> --format json`.
- Tests for each pattern: detected, not detected and not enough data.

**Done when:**
- [ ] All tests pass.
- [ ] Mazen runs it on his own data and the results make sense to him. Anything surprising gets checked by hand against the trades.
- [ ] Any threshold change is written into section 5 with the reason.

This is the first point where TradeMind is useful. A good place to pause and decide whether the patterns are worth showing to others.

## M4: AI Explanations

- `Explainer` interface.
- Groq provider (Mazen's own free key) and Ollama provider for local use.
- Prompt that sends only summary numbers (section 7).
- Check that rejects advice words and numbers not in the metrics.
- Cache explanations by finding content.

**Done when:**
- [ ] Tests pass using a fake explainer.
- [ ] Mazen's report has an explanation for each finding.
- [ ] With the AI turned off or failing, the report still works.

## M5: Web API

- FastAPI endpoints (section 8).
- Background jobs and an in-memory store that deletes uploads and reports after 1 hour.
- Upload size and type checks. One error shape.
- Logs with counts and timings only (section 10, Privacy).

**Done when:**
- [ ] API tests pass for each endpoint and each error case (section 1.2).
- [ ] A test shows the data is gone after `DELETE` and after the 1-hour expiry.
- [ ] The generated API docs page lists every endpoint.

## M6: Web Frontend

- React with TypeScript and Vite in `frontend/`.
- Upload, progress and report screens (section 9).
- Sharesies export steps on the upload screen.
- The FastAPI app serves the built frontend.

**Done when:**
- [ ] The full flow works locally with Mazen's file.
- [ ] It works on a phone screen.
- [ ] Every error case from section 1.2 shows the right message.
- [ ] Keyboard-only use works, and colour contrast passes.

## M7: Deploy

- Dockerfile for the single container.
- A Catalyst Cloud VM on Mazen's personal account. Most likely separate from the homelab (section 11).
- TLS and a subdomain under `mazenkhallaf.com`.
- Secrets set on the server, not in the image.
- Basic hardening: firewall, updates, no open admin dashboards.
- An uptime check.
- Decide the market data question for public use (see "Open Issue" below).

**Done when:**
- [ ] The site works at its public URL over HTTPS.
- [ ] A new deploy is one documented command.
- [ ] No secret is in the image or the repo.

## M8: Test Users

- Find 5 people who invest through Sharesies.
- A short way for them to give feedback.
- Fix what they find.
- README written as a case study: the problem, the design decisions, what was learned.

**Done when:**
- [ ] Every item in the vision's "Definition of Done for v1" is ticked.

## Open Issue: Market Data for Public Use

The spec says to use Yahoo while building and a licensed provider for the public launch (section 4.2). The tests showed that no free, licensed provider covers several years of ASX, NZX and US prices. Mazen's rule is that v1 costs nothing.

These two don't fit together. Options, to decide at M7:
1. Pay for a provider at launch.
2. Keep the site invite-only for the 5 test users and treat it as a private test, not a public service.
3. Limit public use to what a free licensed source covers. This loses NZX or history.

- [ ] Decide at M7.

## Later (After v1)

From `02-spec.md` section 13: IBKR reader, more patterns, PDF and email output, a buy-and-hold comparison, a halal lens.
