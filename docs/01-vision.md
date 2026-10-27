# TradeMind: Vision

Status: agreed 2026-10-24. Next phase: `02-spec.md`.

## Summary

TradeMind reads a person's trade history from a broker CSV and shows them the behaviour patterns in it. Each finding comes with the trades behind it and a note on how much evidence there is.

## Why We Are Building It

1. **Portfolio piece (main reason).** It shows a full system built properly: reading files, calling outside APIs, rules that can be tested, AI used with care, a report, and cloud hosting. The story is "a hackathon demo, rebuilt from a plan by the one person who stayed".
2. **A product later, maybe.** If people use it, it could earn money. This is not a goal for v1, but v1 should not block it.

## The Problem

Investors can see what they bought and sold, and whether they made money. They can't easily see the habits behind those trades.

Research on individual investors finds two clear patterns:
- People who trade the most tend to earn the lowest returns (Barber and Odean).
- Many investors sell shares that have gone up and keep shares that have gone down. This is called the disposition effect.

People repeat these habits when they can't see them. The link between the disposition effect and returns is still debated, so TradeMind describes the behaviour and does not claim a dollar cost.

## Users

| User | Why they matter |
|---|---|
| Mazen | First real user. His Sharesies history is the test data |
| Casual NZ and Australian investors | The wider audience. Use apps like Sharesies and Stake |

Mazen invests long term, so his own history may show few patterns. A short or clean result is still a valid result, and the report should handle it well.

## What v1 Does

- Reads trade history CSVs from **Sharesies**. IBKR was dropped on 2026-10-27: Mazen's IBKR history is too small to be useful, and a reader is not needed without data to test it on.
- Adds market prices around each trade.
- Detects three patterns with rules we write and test:
  - **Overtrading:** trading often compared with the size of the portfolio.
  - **Disposition effect:** selling winners sooner than losers.
  - **Buying after a run-up:** buying shortly after a sharp price rise.
- Gives each finding its evidence (the trades) and a confidence level based on how many trades it rests on.
- Uses AI only to write a plain-English explanation from the evidence. AI does not detect patterns.
- Returns the result as JSON, and shows it as a web page.

## What v1 Does Not Do

- No financial advice. No "buy", "sell" or "hold" suggestions for any share.
- No connecting to broker accounts. Upload only.
- No user accounts. No storing trade histories after the report is made.
- No PDF or email. These can come later as extra outputs from the JSON.
- No brokers beyond Sharesies. Each new broker needs a real sample export to build and test a reader.

## Definition of Done for v1

- [ ] Mazen runs his own Sharesies history through it and gets a correct report.
- [ ] 5 people upload their own CSV and say the report was useful.
- [ ] It is deployed and reachable from a public URL.
- [ ] Each pattern rule has tests based on small, hand-made trade scenarios.
- [ ] The README explains what it does, how to run it, and the main design decisions.

## Why Heuristics Find the Patterns and AI Only Explains Them

| | Rules (heuristics) | AI |
|---|---|---|
| Testable | Yes. Same input gives the same output | No. Output changes between runs |
| Explainable | Yes. The rule and the evidence are visible | Weak |
| Good at plain language | No | Yes |

Rules decide what is true. AI turns that into readable text. If the AI is down, the report still works without the explanation.

## Risks

| Risk | What we do about it |
|---|---|
| **Financial advice law.** The FMA regulates financial advice to retail clients in NZ. Recommending particular shares can count as advice | Describe past behaviour only. No product suggestions. Review the wording before launch |
| **Privacy.** Trade histories are personal financial data (Privacy Act 2020) | Process in memory, delete after the report, never log raw uploads |
| **Small samples.** A casual investor may have 20 to 50 trades | Show the trade count and a confidence level on every finding. Say so when there is too little data |
| **Market data limits.** The free Alpha Vantage key allows about 25 requests a day. ASX and NZX coverage is not confirmed | Cache prices. Pick the data source in the spec after checking coverage |
| **Broker CSV formats change** | One small reader per broker, each with a test using a sample file |
| **AI cost and reliability** | AI is optional. Reports work without it |
| **Code ownership.** The hackathon code had 6 authors | The rebuild is new code. Old code is reference only |
| **API keys** in the hackathon code and git history | Keep the old repo private. Build v1 in a fresh repo. Secrets live only in environment variables |

## Competitors

| Product | What it does | Difference from TradeMind |
|---|---|---|
| Essentia Analytics | Behaviour analysis for professional fund managers | Built for professionals, not retail investors |
| Mezzi | Personal finance app that claims to flag biases | US only, iPhone only, connects to US brokers |
| Trading journals (TradesViz, Jurnl-It, Mantis) | Import broker CSVs, track profit, notes and mood | Aimed at active traders. Do not clearly name biases |

## Open Questions

- [x] Export a Sharesies transaction report and record its columns. Columns: Trade ID, Trade date (UTC), Instrument code, Instrument name, Market code, Quantity (can be fractional), Price, Transaction type, Currency, Amount, Transaction fee, Transaction method (includes TRANSFER OUT), Portfolio, Initiated by (the user, System or Operator). Covers ASX, NYSE and NZX.
- [x] IBKR export: dropped (2026-10-27). Not useful for v1.
- [x] Check Mazen's own history has enough trades. Sharesies alone has several hundred, most of them on the ASX.
- [ ] Choose a market data source that covers US, ASX and NZX shares, and check its free limits.
- [x] Choose the AI provider for explanations: Groq free tier (see `02-spec.md` section 7). v1 must not cost money.
- [x] Public repo: the old repo stays private because its history has API keys. The rebuild goes in a fresh public repo.
- [ ] Decide how to find the 5 test users.
- [ ] Find a source for the "1-3% per year" figure in the old PRD, or drop it.

## References

- [Barber and Odean, "The Courage of Misguided Convictions"](https://faculty.haas.berkeley.edu/odean/Papers/Courage/Courage.pdf): heavy traders earn the lowest returns, and individual investors show the disposition effect.
- [AAII: trading more frequently leads to worse returns](https://www.aaii.com/files/journal/pdf/trading-more-frequently-leads-to-worse-returns.pdf): summary of the link between trading often and returns.
- [Frontiers 2024: disposition effect and returns](https://www.frontiersin.org/journals/behavioral-economics/articles/10.3389/frbhe.2024.1345875/full): the link between the disposition effect and returns is mixed.
- [CXO Advisory: research on individual investors](https://www.cxoadvisory.com/individual-investing/overview-of-research-on-individual-investors): overview of the research.
- [FMA: financial advice](https://www.fma.govt.nz/business/compliance/financial-advice/): regulated financial advice to retail clients needs a licensed provider.
- [FMA guide for finfluencers](https://www.fma.govt.nz/news-and-resources/media-releases/fma-releases-guide-for-finfluencers/): general talk is usually fine. Recommending particular products can become advice.
- [Mezzi blog](https://www.mezzi.com/blog/ai-in-behavioral-finance-managing-investor-bias) and [App Store listing](https://apps.apple.com/app/id6449714926): Mezzi's own feature claims.
- [Top free trade journaling tools for CSV import](https://quantamentaltrader.substack.com/p/top-free-trade-journaling-tools-for): overview of journal apps.
- [Alpha Vantage API limits (Macroption)](https://www.macroption.com/alpha-vantage-api-limits/): free key at about 25 requests a day. Third-party source, check the official page.
- [Snowball Analytics: exporting from Sharesies](https://help.snowball-analytics.com/import-sharesies/): how to export the Sharesies transaction report.
