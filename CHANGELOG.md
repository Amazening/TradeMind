# Changelog

Every change that alters what TradeMind says or does is listed here, newest first. Each report shows the version that made it, so a result can be matched to the rules that produced it.

The format follows [Keep a Changelog](https://keepachangelog.com). Versions follow [Semantic Versioning](https://semver.org), with these meanings while the version is below 1.0:

- **Minor** (0.2.0 to 0.3.0): a change to what a report says or the numbers in it, such as a new pattern or a new way to measure one.
- **Patch** (0.2.0 to 0.2.1): a fix or wording change that does not change a result.
- **1.0.0**: kept for when the site is open to the public.

The history before 0.1.0 is in git.

## [Unreleased]

## [0.2.0] - 2026-10-31

### Changed

- Overtrading now uses the smaller of what you bought and what you sold in a month, divided by the portfolio value at the start of the month. It used the average of the two, after Barber and Odean (2000). Money you add and invest is bought and never sold, so the average counted saving as trading. A tester who bought NZ$200 of a fund every week for 7 months and never sold was told he traded 18% of his portfolio a month. With the smaller figure a saver who never sells scores 0%. The 8.8% line is unchanged. A month needs both buys and sells to score, so the result is less likely to be "found" than before.
- The overtrading explanation says what the figure counts, and that added money is left out.
- Months with no turnover are no longer listed as the busiest months.

### Added

- Each report records the version of TradeMind that made it (`tool_version`), and the report page shows it. The report format is now 1.1.
- This changelog, and a test that fails if its newest version does not match `pyproject.toml`.
- An optional "Help improve TradeMind" section on the report page. It makes a short summary of how the file was read (counts and labels, no share names, dates or amounts), shows all of it, and lets the person copy it or save it and send it themselves. Nothing is sent from the page and nothing new is stored. The upload page's data-handling section says so.
- The report now has `diagnostics`: counts of the file's transaction methods, who started each row (the investor's own name shown as "you"), skipped rows and why, small buys, and how many shares had no market prices or were adjusted for splits.

### Known issues

- Small automatic buys made by Sharesies (a tester reported about 20c every few days) may be counted as the investor's own decisions. It is not known how the file labels them. The feedback summary now shows this, so a tester can send it.

## [0.1.0] - 2026-10-30

The first version that is live, at https://trademind.mazenkhallaf.com. Invite-only, with an access code.

### Added

- Reads the Sharesies Transaction Report CSV. Rows from the same order are grouped into one decision. Trades the platform made (such as dividend reinvestment) count towards holdings but are not judged as the investor's choices.
- Daily prices from Yahoo Finance, adjusted for share splits and checked against the investor's own trade prices.
- Three patterns: trading a large share of the portfolio, selling winners sooner than losers, and buying after a sharp rise. Each shows the trades behind it and how much data it rests on.
- Plain-language explanations. Code writes the facts, a model (Groq) only rewords them, and a checker rejects replies with new numbers, share names or advice.
- Web app and API: in-memory uploads that are deleted after an hour, an access code, an upload rate limit, security headers (A+ on SSL Labs and securityheaders.com), and an example report made from made-up trades.
- A "How your data is handled" section on the upload page.
- Command line: `import`, `enrich` and `analyse`, with `--holdings` to show what is held after splits.
- Deployment with Docker and HTTPS, on a cloud VM made with Terraform and Ansible.

### Fixed

- Holdings show the right amounts after a share split or consolidation, and ignore rounding dust.
- The chance labels say "or higher" and "or bigger".

[Unreleased]: https://github.com/Amazening/TradeMind/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/Amazening/TradeMind/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/Amazening/TradeMind/releases/tag/v0.1.0
