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
- [x] All tests pass (2026-10-26: 47 tests, Ruff and mypy clean).
- [x] Running it on Mazen's real file gives row and trade counts, a date range and an instrument count that match a manual count of the file, with no rows skipped.
- [ ] Holdings after the last trade match what Sharesies shows (Mazen checks with `uv run trademind import data/private/sharesies-transactions.csv --holdings`).

## M2: Market Prices

- `PriceSource` interface (section 4.3).
- Yahoo provider (section 4.2).
- A fake provider with hand-made prices, used in all tests.
- Disk cache for prices.
- Split and consolidation adjustment for trades (section 4.1).
- Delisted shares: fall back to the user's own trade prices, and add a data note.
- Exchange rates to NZD.
- `EnrichedHistory` model (section 6.2).
- A price check inside `enrich`: for every share, the median of (trade price / market close on the same day). If it is outside 0.8 to 1.25, the market prices are not used, and the share falls back to own trade prices with a note. This replaces the separate check script, and tests any provider against real trades.
- CLI: `trademind enrich <file>` prints coverage, the price check and the data notes for each instrument.

**Done when:**
- [x] All tests pass, with no internet calls in tests (2026-10-26: 99 tests, Ruff and mypy clean).
- [x] Mazen's file enriches without errors. The delisted ASX share shows as delisted with a data note.
- [x] The consolidations are adjusted. Two were found in the real file, and after adjusting, the trade prices agree with the market (ratio 1.00 to 1.01).
- [x] A second run uses the cache and makes no network calls (1 second, against 18 seconds the first time).

**Found while testing on real data (2026-10-26):** Yahoo's prices for one share that had a consolidation are about 1.7 times too low before the consolidation, on both its listings. It looks like Yahoo applied a second adjustment (probably for a capital raising) that it does not list as a split. The price check caught it, and that share now uses own trade prices only. This is a reason to compare any new provider against real trades before trusting it.

## M3: Patterns

- Overtrading (section 5.1). Check the turnover definition against the Barber and Odean paper first.
- Disposition effect (section 5.2).
- Buying after a run-up (section 5.3).
- Confidence levels (section 5.4).
- `Report` model (section 6.3).
- CLI: `trademind analyse <file> --format json`.
- Tests for each pattern: detected, not detected and not enough data.

- Also built: a text report (`--format text`) in the reporting layer, and the standard-library statistics tests (no SciPy).

**Done when:**
- [x] All tests pass (2026-10-26: 143 tests, Ruff and mypy clean). Each pattern has a detected, not-detected and not-enough-data scenario worked out by hand.
- [ ] Mazen runs it on his own data and the results make sense to him. Anything surprising gets checked by hand against the trades.
- [x] Any threshold change is written into section 5 with the reason. The one addition is the NZ$500 minimum for overtrading months.

**Checks made on Mazen's real data (2026-10-26):**
- Portfolio values computed from the trades, Yahoo prices and exchange rates were checked against Mazen's own records and agreed within a few percent.
- The first results were given to Mazen to review. They are not recorded here, because this repo is public and they are personal. One caution from them: turnover cannot tell a reallocation or a forced sale from a habit, so the report states what happened and does not claim a motive.

This is the first point where TradeMind is useful. A good place to pause and decide whether the patterns are worth showing to others.

## M4: AI Explanations

- `ChatModel` interface, with Groq (Mazen's own free key) and Ollama providers.
- Facts written by code for each finding, so the model only rewords them (see section 7 for why this changed).
- Reply checks: advice, share names, greetings and lists, numbers, time spans, number words, and claims about causes, motives, other people or good and bad.
- One retry with the reason, then fall back to the facts as written by the tool.
- Cache of accepted explanations (memory or disk).
- CLI: `trademind analyse <file> --explain groq|ollama`.

**Done when:**
- [x] Tests pass using a fake model (2026-10-26: 196 tests, Ruff and mypy clean). The providers are tested with mock transports, with no internet and no real keys.
- [x] Mazen's report has an explanation for each finding. Tested on the real report with local Ollama (`qwen2.5:14b`): 9 seconds, and 1 second from the cache.
- [x] With the AI turned off or failing, the report still works. A failing model falls back to the facts, marked `explained_by: "tool"`.
- [x] Run against Groq with a real free key (2026-10-27). The first guess at a model (`llama-3.1-8b-instant`) had been retired (HTTP 404), so the default is now `qwen/qwen3.8-27b`. On the real report, 7 of 9 replies passed the checks first time, and the 2 that failed wrote "thirteen" for 13. The check now accepts a number word whose value is one of the facts. After that, all 3 findings were written by the AI with no fallback. The `gpt-oss` models return empty text because they use the reply's token budget on hidden "thinking". Groq retires models, so a 404 now says to pick a new one with `GROQ_MODEL`.

**Found while testing on real data (2026-10-26):** a 4B model invented time spans and misread a p-value. That led to the facts design. `gemma3:12b` still invented details, all caught by the checks. `qwen2.5:14b` was reliable.

## M5: Web API

- FastAPI endpoints (section 8).
- Background jobs and an in-memory store that deletes uploads and reports after 1 hour.
- Upload size and type checks. One error shape.
- Logs with counts and timings only (section 10, Privacy).

- CLI: `trademind serve` runs the API. Settings pick the price source (Yahoo behind the disk cache) and Groq if a key is set.

**Done when:**
- [x] API tests pass for each endpoint and each error case (section 1.2) (2026-10-26: 227 tests, Ruff and mypy clean).
- [x] A test shows the data is gone after `DELETE` and after the 1-hour expiry.
- [x] The generated API docs page lists every endpoint. A test checks `/api/openapi.json` and `/api/docs`.
- [x] Tested for real: the server was started, Mazen's real export was uploaded with curl, the status moved through the steps, the report came back, and `DELETE` removed it.

## M6: Web Frontend

- React with TypeScript and Vite in `frontend/`.
- Upload, progress and report screens (section 9).
- Sharesies export steps on the upload screen.
- The FastAPI app serves the built frontend.

- Security headers on every response (Content Security Policy, no sniffing, no referrer, no framing).
- CI: a frontend job that type checks, lints, tests and builds.

**Done when:**
- [x] The full flow works locally. Tested in a real browser against the real server with live market prices: upload, progress, report, download link and delete. The test file had made-up trades, because the browser cannot read files from disk. Mazen's real export has been run through the same API with curl (M5), and through the CLI.
- [x] It works on a phone screen (375 px wide, light and dark mode): no sideways scrolling, a 16 px gutter, buttons at least 44 px high.
- [x] Every error case from section 1.2 shows the right message: bad file type, empty file and too big (checked in the page), unrecognised broker and no trades (the server's message, which never repeats the file), skipped rows and missing prices (data notes), market data down (failure screen), AI down (the tool's own text), network down (retries, then the failure screen).
- [x] Keyboard-only use works, and colour contrast passes. A keyboard test covers the skip link, the file field and Enter on the button. A Python test measures every text colour pair in both themes. The keyboard test found a real problem: focus jumped to the heading on first load, so the skip link was skipped. Fixed.
- [x] 65 frontend tests and 267 backend tests pass. Type check, ESLint, Ruff and mypy are clean.

**Left for Mazen:** try it with his own export in his own browser (`uv run trademind serve` after `npm run build` in `frontend/`), and look at it on a real phone.

## M7: Deploy

- Dockerfile for the single container, a compose file with a proxy (Caddy, automatic HTTPS), and step-by-step instructions in `deploy/README.md`.
- A Catalyst Cloud VM on Mazen's personal account. Separate from the homelab (section 11).
- TLS and a subdomain under `mazenkhallaf.com`.
- Secrets set on the server, not in the image.
- Hardening: firewall, updates, no open admin dashboards. In the app: rate limiting per visitor, security headers, no web addresses in logs.
- An uptime check.
- Decide the market data question for public use (see "Open Issue" below).

**Done when:**
- [x] The image builds and runs (2026-10-26). 228 MB. It runs as a non-root user with a read-only filesystem, no extra privileges and a 512 MB limit, and used about 54 MB. Docker's health check passes. CI builds it and checks that it answers on every push.
- [x] The whole stack was run locally with a proxy (using `localhost`): HTTPS works, HTTP redirects to HTTPS, HSTS and the security headers are set, the app's port cannot be reached except through the proxy, a 7 MB upload is refused by the proxy and a 5.5 MB one by the app, and the 4th upload in an hour with a limit of 3 gets `429`.
- [x] No secret is in the image or the repo. `.dockerignore` keeps `.env`, `data/` and `.git` out of the image.
- [x] Logs hold counts and timings only. A test run showed no report ids and no trade data in the app logs, and the proxy has no access log.
- [x] A new deploy is one documented command (`docker compose up -d --build`).
- [x] The Catalyst VM, firewall, floating IP and Docker disk were made with Terraform (2026-10-30), from Mazen's `catalyst-homelab` repo. It is a separate VM, not in the `default` group, not on Tailscale, and SSH is limited to one address.
- [x] Docker, security updates and fail2ban were set up with Ansible, and TradeMind was deployed. Tested live over plain HTTP on the IP: the invite-only gate works (no code and a wrong code get 401, the right code gets past), the security headers are set, the app's own port is closed from outside, a made-up CSV ran through the full pipeline in 6 seconds with real Yahoo prices, delete worked, and the logs held counts and timings only.
- [x] The `A` record `trademind.mazenkhallaf.com` → `202.49.241.99` was added at Namecheap and `make deploy-trademind` was run again (2026-10-30). Caddy got the HTTPS certificate. HTTP redirects to HTTPS, HSTS and the other security headers are set, and uploads with no code or a wrong code get 401 over HTTPS.
- [x] Grades on 2026-10-30: SSL Labs gave A+ (TLS 1.2 and 1.3 only, HSTS on, certificate trusted). securityheaders.com gave A. It lists one missing header, `Permissions-Policy`.
- [x] The site is in Uptime Kuma on the management VM, checking `/api/health` every 60 seconds.
- [x] Settle the market data question (below): invite-only, built 2026-10-27. Set `ACCESS_CODE` on the server.
- [x] The site works at its public URL over HTTPS (2026-10-30): `https://trademind.mazenkhallaf.com` answers `/api/health` with 200 and a certificate that verifies.

## M8: Test Users

- Find 5 people who invest through Sharesies.
- A short way for them to give feedback.
- Fix what they find.
- README written as a case study: the problem, the design decisions, what was learned.

**Done when:**
- [ ] Every item in the vision's "Definition of Done for v1" is ticked.

## Decided: Market Data for Public Use (2026-10-27)

The spec says to use Yahoo while building and a licensed provider for a public launch (section 4.2). The tests showed that no free, licensed provider covers several years of ASX, NZX and US prices. Mazen's rule is that v1 costs nothing, and those two don't fit together.

**Decision: invite-only.** Uploads need an access code, given to the 5 test users. A private test is a smaller step than a public service, though it is still not a licensed use of Yahoo's data. Paying for a provider is left for if the project ever goes public.

Mazen's concern was that this makes the project less useful as a portfolio piece. The answer was to keep the project visible without needing market data:
- The code is public, with tests, CI, docs and screenshots.
- An **example report** is open to everyone. It is built from made-up trades through the real pipeline (`scripts/make_sample_report.py`), so it needs no market data and no code.
- Anyone can run the whole thing themselves with their own file.

- [x] Decide (2026-10-27): invite-only, with an open example report.

## Later (After v1)

From `02-spec.md` section 13: more brokers (each needs a real sample export), more patterns, PDF and email output, a buy-and-hold comparison, a halal lens.
