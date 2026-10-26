# TradeMind: Spec

Status: agreed 2026-10-26. Covers Sharesies only. IBKR is added once a sample export is available.

Read `01-vision.md` first. This doc says **what** v1 does and the data shapes between layers. `03-milestones.md` will say in what order it gets built.

Items marked **Decision** need Mazen's answer before building that part.

## 1. User Flows

### 1.1 Main Flow: Upload and Get a Report

1. The user opens the site. The home page says in two or three lines what TradeMind does, which brokers it supports, and that uploads are not stored.
2. The user clicks "How do I export my trades?" and sees the steps for their broker.
3. The user drops a CSV onto the page, or picks one.
4. The site checks the file straight away (size, file type) and shows the broker it recognised.
5. The user clicks **Analyse**.
6. A progress view shows the steps: reading trades, getting market prices, finding patterns, writing explanations.
7. The report page shows:
   - A summary: period covered, number of trades, markets, how many trades were left out and why.
   - One card per pattern: detected, not detected, or not enough data.
   - For each card: what the pattern is, the numbers behind it, a confidence level, the trades that show it, and a plain-English explanation.
   - Data notes: anything that went wrong, for example a share with no price data.
   - A short line saying this is information about past behaviour, not financial advice.
8. The user can download the report as JSON.

### 1.2 Error Flows

| Situation | What the user sees |
|---|---|
| File is not a CSV, or is larger than 5 MB | A message before upload, with the limits |
| CSV does not match a supported broker | "We couldn't recognise this file", with the list of supported brokers and the export steps |
| Some rows can't be read | The report still runs. Data notes list the skipped rows by row number and reason |
| No buy or sell trades in the file | "No trades found", with no report |
| Market prices missing for some shares | The report runs without those shares. Data notes name them |
| Market data service down | "We couldn't get market prices. Try again later" |
| AI explanation service down | The report shows without the plain-English text. The numbers and evidence stay |

### 1.3 CLI Flow

```bash
trademind analyse data/private/sharesies-transactions.csv --format json
```

The CLI uses the same layers as the web app. It lets Mazen run his own data locally, and shows the analysis works without the web app.

## 2. Input: Sharesies Transaction Report

Exported from Sharesies: Account → Reports → Transaction Report, CSV.

| Column | Example | Notes |
|---|---|---|
| Trade ID | text | Unique per row |
| Trade date | `2024-03-04 13:30:27.800000 (UTC)` | Always UTC, with a `(UTC)` suffix |
| Instrument code | `ABC` | Ticker, without the exchange suffix |
| Instrument name | text | |
| Market code | `ASX`, `NYSE`, `NZX` | Other US markets (for example NASDAQ) are likely but not yet seen |
| Quantity | `0.250000` | Can be fractional |
| Price | `12.340` | Per share, in the trade currency |
| Transaction type | `BUY`, `SELL` | |
| Currency | `aud`, `usd`, `nzd` | Lower case |
| Amount | `3.085` | Quantity × Price. Does **not** include the fee |
| Transaction fee | `0.01543` | Separate from Amount |
| Transaction method | `BUY`, `SELL`, `TRANSFER OUT` | Transfers are not decisions to sell |
| Portfolio | `Investments` | |
| Initiated by | the user's first name, `System`, `Operator` | `System` rows look like auto-invest or dividend reinvestment |

Facts found in a real export:
- One order can show up as several rows on the same day for the same share (split fills).
- `System` and `Operator` rows exist and are not the user's own decisions.

## 3. Rules for Turning Rows into Trades

- **Trade time:** parse as UTC. For daily price lookups, use the trade's date in the market's own time zone (Sydney for ASX, Auckland for NZX, New York for US markets).
- **Side:** `BUY` → buy, `SELL` → sell, `TRANSFER OUT` → transfer out. Any other value → skip the row with a data note.
- **Who decided:** "Initiated by" `System` or `Operator` → `initiated_by = platform`. Everything else → `user`.
- **Decisions vs fills:** rows for the same share, same side, same market date and same initiator (the user, or the platform) are one **decision**. Transfers out are not decisions. Patterns count decisions, not rows. Holdings and cost use every row.
- **Unknown rows:** a row with an unknown method, an unknown market, a bad number or a bad date is skipped, with its row number and reason in `skipped_rows`. The rest of the file still loads.
- **Selling more than held:** the position goes to zero and a warning is shown. It means the history is missing earlier buys or transfers in.
- **Platform trades:** count towards holdings and cost, but are left out when judging the user's behaviour.
- **Transfers out:** remove shares from holdings at cost. Not counted as a sale.
- **Cost basis:** average cost per share, per instrument. Fees are added to the cost of buys and taken off the proceeds of sells.
- **Money:** use `Decimal`, never `float`, for prices, quantities and amounts.

## 4. Market Data

### 4.1 What Is Needed

- Daily closing prices for every instrument, from 1 year before its first trade to the last trade date. The year before is needed for the run-up baseline (see 5.3).
- Split and consolidation events for every instrument. Trade quantities and prices before an event are adjusted to match the price series. Otherwise a 1-for-25 consolidation looks like a 2,400% jump.
- A way to handle delisted shares (see 4.2).
- Exchange rates to NZD, daily, only for the overtrading measure (see 5.1).

### 4.2 Source

**Decision: market data provider.** It must:
1. Cover ASX, NZX and US shares, including ETFs.
2. Give at least 6 years of daily history. Mazen's history starts in 2021.
3. Handle splits.
4. Allow showing results derived from the data to users.
5. Have a free or cheap tier that works for one user with caching.

**Test results (2026-10-24).** Tested against every share in Mazen's real Sharesies history, which covers ASX, NZX and NYSE.

| Provider | Key needed | Result |
|---|---|---|
| Yahoo Finance (unofficial chart API) | No | Covers every instrument except one delisted ASX share. History back to 2016 or earlier. Returns split events. **Not licensed** for use in an app, and can change without notice |
| Twelve Data | For prices | Lists 2,019 ASX and 233 NZX shares. All ASX and NZX data needs the paid **Pro** plan. Its stock list is missing the delisted share, 2 listed investment companies and 1 stapled security. Personal plans are non-commercial |
| Stooq | No | Blocks scripted access with a browser check. Not usable |
| EODHD (free key) | Yes | ASX and US work, and a share consolidation is returned correctly. **No NZX exchange at all.** Free plan stops at 1 year back, so delisted coverage could not be checked. 20 calls a day |
| Alpha Vantage (free key) | Yes | **No ASX or NZX shares** in its symbol search. `.AX` and `.NZ` tickers return nothing. Full history is a paid feature. Ruled out |
| Marketstack (free key) | Yes | ASX, NZX and US tickers all work. Free plan stops at 1 year back. **Gaps:** about 10% fewer trading days than other sources for ASX and NZX, and it **missed a share consolidation** (no split factor, empty splits list). No data for the delisted share |

What the test showed about the data itself:
- **Delisted shares are real.** A share that was traded a lot has since been delisted. A provider without delisted data loses part of the history.
- **Splits and consolidations are real.** A few of the shares tested had share consolidations during the period. Trade quantities before each one must be adjusted, or every pattern that uses price changes gives wrong results.

**Conclusion:** no free, licensed source gives several years of ASX, NZX and US prices with correct splits. A public launch needs a paid plan, or a smaller scope.

**Recommendation:**
- For building and for Mazen's own CLI runs: use Yahoo behind the `PriceSource` interface. It has the best coverage for free.
- Decide the launch provider at the launch milestone, not now. Candidates: a paid EODHD plan (ASX and US, correct splits) plus a second source for NZX, or a paid Twelve Data plan. Check delisted coverage and the licence for showing results to users before paying.
- Every provider gets checked against the same test set (the 6 cases above), so data gaps like Marketstack's show up before they reach a report.
- Delisted shares with no price data: use the user's own trade prices as the only price points, run only the patterns that work with them, and add a data note.
- Price check (added after testing on real data): for each share, the median of (trade price / market close on the same day) must be between 0.8 and 1.25. If not, the market prices are rejected and the share is treated like one with no prices. Yahoo's prices for one share were about 1.7 times too low before a consolidation, because of an adjustment Yahoo did not list as a split. Sharesies exports trades on the old, unadjusted basis, so trades before a split are rescaled to match.

- [x] Test providers with free keys (2026-10-24). Results above.
- [ ] Pick the paid provider for the public launch (at the launch milestone).

### 4.3 Design

- The rest of the system talks to a `PriceSource` interface, not to a provider. Swapping providers means writing one new class.
- Prices are cached on disk by instrument and date range. Prices are public data, so caching them is fine. Only prices are cached, never user data.
- Tests use a fake `PriceSource` with hand-made prices. Tests never call the internet.

## 5. Pattern Definitions

Each pattern returns one of three results: **detected**, **not detected**, or **not enough data**. Thresholds below are starting values. They get tuned with hand-made test scenarios and Mazen's own data, and every change is noted here with the reason.

Only user decisions are judged. Platform trades are left out.

### 5.1 Overtrading

**Question:** does the user trade a large share of their portfolio each year?

**Measure:** monthly turnover, as defined by Barber and Odean (checked against the paper on 2026-10-26).
- For each month, purchase turnover = value of the user's buys in the month ÷ portfolio value at the start of the month. Sales turnover is the same with the user's sells. The paper reports the two separately (means of 6.49% and 6.23% a month).
- Monthly turnover = the average of purchase turnover and sales turnover.
- Yearly turnover = average monthly turnover × 12.
- Portfolio value is holdings × closing prices, converted to NZD. Platform trades count towards holdings. Shares without market prices are valued at the last own trade price.
- Differences from the paper: trades are valued at the trade price (the paper uses the start-of-month price), and months that start with a portfolio under NZ$500 are left out. A new investor adding money to a tiny portfolio shows huge turnover that says nothing about trading habits. Months are calendar months by market date, and the start-of-month holdings use UTC month boundaries.

**Result:**
- Not enough data: fewer than 6 months with a portfolio of NZ$500 or more, or fewer than 10 user decisions in those months.
- Detected: average monthly turnover above 8.8% (about 105% a year).
- Not detected: otherwise.

**Context shown:** Barber and Odean studied 66,465 US households from 1991 to 1996. The average household turned over more than 75% of its portfolio a year. The paper calls households with monthly turnover above 8.8% frequent traders. They earned 11.4% a year after costs, against 18.5% for those that traded least. The most active fifth averaged more than 250% a year. The 8.8% threshold is taken from this.

**Limit:** turnover does not say why someone traded. Selling a share that fails a halal screen, moving between brokers, and rebalancing all count as turnover. The report states what happened and does not claim a motive.

**Evidence:** the 3 months with the highest turnover, and the 5 largest decisions in each.

### 5.2 Disposition Effect

**Question:** does the user sell shares that are up more readily than shares that are down?

**Measure:** Odean's method.
- On each day the user makes a sell decision, look at every share they hold:
  - Sold that day and price above average cost → **realised gain**.
  - Sold that day and price below average cost → **realised loss**.
  - Not sold and that day's close above average cost → **paper gain**.
  - Not sold and that day's close below average cost → **paper loss**.
- Proportion of gains realised (PGR) = realised gains ÷ (realised gains + paper gains).
- Proportion of losses realised (PLR) = realised losses ÷ (realised losses + paper losses).
- Disposition score = PGR − PLR.

**Result:**
- Not enough data: fewer than 10 sell decisions, or fewer than 5 gain cases or 5 loss cases in total.
- Detected: PGR is greater than PLR and the difference passes a one-sided two-proportion z-test (pooled) at the 5% level.
- Not detected: otherwise.

**Details:**
- "Held" means held at the start of the market day. A share bought and sold on the same day has no earlier cost, so it is not counted. A sale at exactly the average cost is neither a gain nor a loss.
- Average cost is the running average from the holdings helper, including buy fees.
- Shares without market prices are left out completely, both their sales and their paper results. Counting their sales without their paper results would bias the result. The finding names them in its notes.

**Limit:** a paper gain or loss is counted again on every sell day, so observations are not independent and the p-value is more optimistic than it looks. Odean's test has the same limit. Forced sales, such as selling a share that fails a halal screen, also count.

**Evidence:** the 5 sales with the biggest gain and the 5 with the biggest loss, each with how far above or below the average cost it was sold.

### 5.3 Buying After a Run-Up

**Question:** does the user tend to buy right after a share has risen sharply?

**Measure:**
- For each user buy decision, take the share's return over the previous 20 trading days.
- Compare it with all 20-day returns for that share in the year before the buy.
- If the buy's return is in the top 10% of that year → a **run-up buy**.
- By chance, about 10% of buys would be run-up buys. Run-up share = run-up buys ÷ all buys checked.

**Result:**
- Not enough data: fewer than 15 buy decisions with a full year of prior prices.
- Detected: run-up share is significantly above 10% (one-sided exact binomial test at the 5% level).
- Not detected: otherwise.

**Details:**
- "The previous 20 trading days" ends on the last close before the buy day, so the buy price itself is never used. Trading days are the bars in the price series.
- The comparison set is every 20-day return ending in the 365 days before the buy. A buy needs at least 200 of them, about 80% of a trading year. Otherwise it is not counted.
- A return that ties with others is in the top 10% only if 10% or fewer of the comparison returns are at least as large. A flat price therefore never produces a run-up.
- Shares without market prices are left out, and the finding names them in its notes.

**Limit:** buys of the same share close together share the same price history, so they are not independent.

**Evidence:** the 10 run-up buys with the biggest rise, with the 20-day rise before each one.

### 5.4 Confidence

Each finding states its sample size (decisions and cases) and a confidence level:
- **Low:** just over the minimum.
- **Medium:** 2× the minimum or more.
- **High:** 4× the minimum or more.

## 6. Data Contracts

All shapes are Pydantic models in `core/`. Field names below are the JSON names.

### 6.1 Ingestion → Enrichment: `ImportResult`

```json
{
  "broker": "sharesies",
  "trades": [
    {
      "id": "row-12",
      "source_id": "Trade ID value",
      "executed_at": "2024-03-04T13:30:27.800Z",
      "market": "NYSE",
      "symbol": "ABC",
      "name": "Example Corp",
      "side": "buy",
      "quantity": "0.250000",
      "price": "12.340",
      "currency": "USD",
      "fee": "0.01543",
      "initiated_by": "user"
    }
  ],
  "skipped_rows": [
    { "row": 40, "reason": "Unknown transaction method: DIVIDEND" }
  ]
}
```

- `side`: `buy`, `sell`, `transfer_out` (later `transfer_in`).
- `initiated_by`: `user` or `platform`.
- Numbers are strings in JSON so no precision is lost.

### 6.2 Enrichment → Analysis: `EnrichedHistory`

```json
{
  "trades": ["...same trade objects as above..."],
  "decisions": [
    {
      "id": "d-7",
      "trade_ids": ["row-12", "row-13"],
      "market_date": "2024-03-04",
      "market": "NYSE",
      "symbol": "ABC",
      "side": "buy",
      "quantity": "0.5",
      "avg_price": "12.35",
      "initiated_by": "user"
    }
  ],
  "prices": {
    "NYSE:ABC": { "currency": "USD", "closes": { "2024-03-04": "12.35" } }
  },
  "fx_to_nzd": { "USD": { "2024-03-04": "1.08" } },
  "missing_prices": ["ASX:XYZ"]
}
```

Holdings and average cost for any date are worked out from trades by a shared helper in `core/`, so every pattern uses the same numbers.

### 6.3 Analysis → Reporting and API: `Report`

This is the main output of TradeMind.

```json
{
  "schema_version": "1.0",
  "generated_at": "2026-10-24T10:00:00Z",
  "broker": "sharesies",
  "period": { "start": "2024-03-04", "end": "2025-01-31" },
  "summary": {
    "trades_read": 0,
    "decisions": 0,
    "user_decisions": 0,
    "platform_decisions": 0,
    "markets": ["ASX", "NYSE", "NZX"],
    "instruments": 0
  },
  "findings": [
    {
      "pattern": "disposition_effect",
      "title": "Selling winners, holding losers",
      "result": "detected",
      "confidence": "medium",
      "sample": { "decisions": 0, "cases": 0 },
      "metrics": { "pgr": 0.0, "plr": 0.0, "score": 0.0, "p_value": 0.0 },
      "threshold": "PGR above PLR, p < 0.05",
      "evidence": [
        { "decision_id": "d-7", "note": "Sold on 2024-03-14, 18.0% above your average cost" },
        { "decision_id": null, "note": "A summary line that is not one decision" }
      ],
      "notes": ["Shares without market prices were left out: ..."],
      "explanation": null,
      "explained_by": null
    }
  ],
  "data_notes": [
    { "level": "warning", "message": "No price data for ASX:XYZ. Its trades were left out." }
  ],
  "disclaimer": "This report describes past trading behaviour. It is not financial advice."
}
```

- `result`: `detected`, `not_detected`, `insufficient_data`.
- `confidence`: `low`, `medium`, `high`, or `null` when there is not enough data.
- `explanation`: filled in by the explanation step. `null` if that step was not run.
- `explained_by`: `"ai"` for a model's rewording of the facts, `"tool"` for text written by code (used when the model fails or is rejected, and for "not enough data").
- `schema_version` changes when the shape changes, so API users know.

## 7. AI Explanations

**Design change after testing (2026-10-26).** The first design gave the model the raw metrics. A 4 billion parameter model then mixed up labels ("36 trades, which was 168.48%" when 58 was months), invented time spans ("over the past two and a half years") and misread a p-value, saying a result was "unlikely to be chance" when no pattern was found. Wrong claims in a report about someone's own behaviour are worse than none. So:

- **Code writes the facts.** Each finding gets 3 to 5 plain sentences written by code (`reporting/facts.py`), including the conclusion ("so this pattern was not found"). They are always correct.
- **The model only rewords the facts.** It is told to add nothing: no new fact, number, time span, cause or comparison.
- **The reply is checked.** It is thrown away if it gives advice, names a share, is not just plain sentences (greeting, heading or list), uses a number that is not in the facts, uses a time word or number word that is not in the facts, or uses a word about causes, motives, other people or good and bad that the facts do not use. One retry, with the reason. Accepted replies are cached.
- **The fallback is the facts.** If the model fails or is rejected twice, the facts are shown as they are, marked `explained_by: "tool"`. Every finding always has an explanation. A data note says how many used the fallback.
- **Not enough data** is explained by code with no model call.
- **What the model sees:** only the facts for one finding. No trade list, share names, dates or amounts. `explained_by` is `"ai"` or `"tool"`.
- The checks cannot catch every wrong claim, only the kinds listed. The facts and the metrics are always in the report beside the wording.

**Providers.** Each is a small class behind a `ChatModel` interface (`reporting/providers.py`).
- **Groq, free tier (decided 2026-10-26).** Needs no card. Its terms say API inputs and outputs are not used for training. Gemini's free tier was ruled out because Google says free-tier content is used to improve its products. The default model is `llama-3.1-8b-instant`, set with `GROQ_MODEL`. It has not been tested yet, because the project has no Groq key. See the open item below.
- **Ollama, local.** No key, and nothing leaves the machine. Default `qwen2.5:14b`, set with `OLLAMA_MODEL`. In tests on the real report, `qwen2.5:14b` followed the rules. `gemma3:12b` kept inventing details, and every one was caught. `gemma3:4b` was not reliable enough.
- Free-tier rate limits are low, so explanations are cached by a hash of the model and the facts, and a failing service is not called again in the same run.

- [ ] Get a free Groq key and run the explanation step against it. Check how often the replies pass the checks.

## 8. API

| Method | Path | What it does |
|---|---|---|
| `POST` | `/api/analyses` | Upload a CSV (multipart). Returns `202` with `{ "id": "..." }` |
| `GET` | `/api/analyses/{id}` | Returns status (`queued`, `running`, `done`, `failed`), the current step, and the `Report` when done |
| `DELETE` | `/api/analyses/{id}` | Deletes the upload and report now |
| `GET` | `/api/health` | Health check |

- The work runs in the background because getting prices can take a while.
- Uploads and reports are held in memory only. They are deleted when the user deletes them or 1 hour after the report is done, whichever comes first.
- Upload limit: 5 MB.
- Errors use one shape: `{ "error": { "code": "unrecognised_broker", "message": "..." } }`.

## 9. Frontend

Three screens:
1. **Upload:** what it does, privacy note, export steps per broker, drop zone, Analyse button.
2. **Progress:** the four steps, with the current one marked. Polls `GET /api/analyses/{id}`.
3. **Report:** summary, finding cards, data notes, disclaimer, Download JSON button, Delete my data button.

Must work on a phone screen. Must meet basic accessibility: labels on inputs, keyboard use, enough colour contrast.

## 10. Non-Functional Requirements

| Area | Requirement |
|---|---|
| Privacy | Uploads and reports in memory only. Never write them to disk or logs. Logs record counts and timings, not content |
| Speed | 1,000 trades across 30 shares: report in under 60 seconds with an empty price cache, under 10 seconds with a full one |
| Reliability | Price or AI failures reduce the report. They don't crash it |
| Testing | Every pattern has tests with hand-made scenarios: detected, not detected, not enough data |
| Security | Secrets in environment variables only. File type and size checked before reading |

## 11. Tech Stack

| Part | Proposal | Why |
|---|---|---|
| Language | Python 3.13 | Strong for data work. Supported until October 2029, and the libraries below all support it |
| Python tooling | uv | Installs Python, manages the virtual environment and the lock file in one tool |
| Web API | FastAPI | Typed, generates API docs, already known |
| Data models | Pydantic v2 | Checks every contract between layers |
| Data handling | pandas | Price series and date maths |
| Statistics | Python standard library (`math`) | The two tests needed (normal tail and exact binomial tail) are a few lines each. This avoids SciPy and its size |
| Data handling | Plain Python with `Decimal` | pandas was in the first proposal. Money needs exact numbers, and the data is small. Add pandas only if a real need appears |
| CLI | Typer | Small, built on the same type hints |
| Tests | pytest | Standard |
| Lint and format | Ruff | One fast tool for both |
| Frontend | React with TypeScript, built with Vite | Shows modern frontend skills. Typed match to the API |
| Packaging | One Docker container. FastAPI serves the API and the built frontend | One thing to deploy. Runs the same on a laptop, a VM or any cloud |
| Hosting | **Catalyst Cloud**, on Mazen's personal account (it has funding for personal projects). Most likely a **separate VM** from the homelab, so a public app can't reach the Obsidian sync or other homelab services. To be worked out in the deploy milestone | No cost to Mazen. Keeps the public app apart from private services |
| CI | GitHub Actions: lint, type check, tests on every push | Visible quality signal on a public repo |

Stack confirmed by Mazen on 2026-10-26. Hosting details are settled in the deploy milestone. Rule for v1: nothing that costs Mazen money.

## 12. Folder Layout

```
TradeMind/
├── src/trademind/
│   ├── core/          shared models, settings, errors, holdings helper
│   ├── ingestion/     one reader per broker
│   ├── enrichment/    PriceSource interface, providers, cache
│   ├── analysis/      one module per pattern
│   ├── reporting/     explanations and output formats
│   ├── api/           FastAPI app
│   └── cli.py
├── tests/             mirrors src, plus hand-made CSV scenarios
├── frontend/          React app
├── data/private/      real exports, ignored by git
└── docs/
```

## 13. Later (Not v1)

- IBKR reader (waiting on a sample export).
- More patterns: panic selling after market drops, concentration in one share, trading around news.
- PDF and email output from the same `Report`.
- Comparison with a simple buy-and-hold of the same money.
- A halal lens: screening status of shares traded.

## 14. Decisions Needed

- [ ] Market data provider (section 4.2). Proposed: Yahoo for building, a paid licensed provider chosen at the launch milestone.
- [x] AI provider (section 7): Groq free tier. Decided 2026-10-26.
- [x] Tech stack (section 11): confirmed 2026-10-26.
- [x] Hosting (section 11): Catalyst Cloud personal account, likely a separate VM. Decided 2026-10-26. Details in the deploy milestone.
- [x] Pattern thresholds (section 5): accepted as starting values 2026-10-26.

## References

- [Barber and Odean, "Trading Is Hazardous to Your Wealth"](https://faculty.haas.berkeley.edu/odean/papers/returns/individual_investor_performance_final.pdf): 66,465 households, 1991 to 1996. The average household turned over more than 75% of its portfolio a year. Households with monthly turnover above 8.8% earned 11.4% a year net, against 18.5% for those that traded least. Source of the overtrading measure and threshold.
- [Odean, "Are Investors Reluctant to Realize Their Losses?" (Journal of Finance, 1998)](https://doi.org/10.1111/0022-1082.00072): source of the PGR and PLR method for the disposition effect.
- [Groq pricing and free tier (eesel)](https://eesel.ai/blog/groq-pricing) and [Groq community: rate limits](https://community.groq.com/t/what-are-the-rate-limits-for-the-groq-api-for-the-free-and-dev-tier-plans/42): free tier with no card. Limits are per model and per organisation. Check console.groq.com for current figures.
- [Best free AI APIs in 2026 (aireiter)](https://aireiter.com/blog/best-free-ai-api): Groq does not train on API inputs or outputs. Logs, where kept, are held up to 30 days.
- [Simon Willison on the Gemini API terms](https://simonwillison.net/2024/Oct/17/gemini-terms-of-service): Gemini free-tier content can be used to improve Google's products. Paid-tier content cannot.
- Provider tests run on 2026-10-24 with free keys against 6 cases: a normal ASX share, a delisted ASX share, an ASX listed investment company, an ASX share that had a consolidation, an NZX share and an NYSE ETF. Results are in section 4.2.
- [EODHD: API knowledge base](https://eodhd.com/knowledgebase/api-for-): free plan is 20 calls a day, past year only.
- [Twelve Data: end-of-day pricing](https://support.twelvedata.com/en/articles/12682324-end-of-day-pricing-market-data): lists NZX (XNZE). Personal plans are non-commercial.
- [Marketstack guide](https://blog.apilayer.com/stock-data-api-guide-how-to-get-real-time-and-historical-stock-prices-using-rest-endpoints/): free tier limits differ between sources. Check the official page.
- [QVeris: free EOD stock data APIs](https://api.qveris.ai/guides/free-eod-stock-data-api): comparison of free tiers and licence limits.
- [Alpha Vantage API limits (Macroption)](https://www.macroption.com/alpha-vantage-api-limits/): free key at about 25 requests a day.
