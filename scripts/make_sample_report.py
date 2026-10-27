"""Makes the example report shown on the website: frontend/public/sample-report.json.

Everything in it is made up. The shares are invented (DEMOA to DEMOE), the prices are a seeded
random walk, and the trades follow simple rules for three habits. It then goes through the real
pipeline, so the report is exactly what TradeMind would produce for a person with those habits.

Run from the project folder:

    uv run python scripts/make_sample_report.py          explanations written by the tool
    uv run python scripts/make_sample_report.py --groq   explanations written by Groq (needs a key)

The result is the same every time, apart from the explanation wording and the time stamp.
"""

import argparse
import random
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from trademind.analysis import analyse
from trademind.core.models import ImportResult, InitiatedBy, Report, Side, Trade
from trademind.core.settings import get_settings
from trademind.enrichment import PriceHistory, enrich
from trademind.reporting import (
    ChatModel,
    ExplanationCache,
    GroqModel,
    explain_report,
    explain_with_facts,
)

# Chosen by trying seeds until the example showed two habits found and one not found, at levels
# that look believable. Any seed works. Only the numbers change.
SEED = 111
SHARES = {
    "DEMOA": ("Demo Mining Ltd", 12.0),
    "DEMOB": ("Demo Foods Ltd", 8.5),
    "DEMOC": ("Demo Telecom Ltd", 4.2),
    "DEMOD": ("Demo Health Ltd", 31.0),
    "DEMOE": ("Demo Energy Ltd", 6.8),
}
PRICES_FROM = date(2021, 1, 4)
TRADING_FROM = date(2022, 3, 1)
TRADING_TO = date(2025, 6, 30)
WINDOW = 20  # trading days
# The made-up investor's habits. These numbers are chosen so the example shows two habits found
# and one not found, at levels that look believable.
BUY_CHANCE = 0.04  # chance of a buy on any trading day, when there is cash
CHASE_RISES = 0.12  # how often a buy goes to the share that has just risen most
SELL_WINNER_CHANCE = 0.12  # chance of selling a share that is up 4% or more, each day
OUTPUT = Path(__file__).resolve().parent.parent / "frontend" / "public" / "sample-report.json"


def _weekdays(start: date, end: date) -> list[date]:
    days: list[date] = []
    day = start
    while day <= end:
        if day.weekday() < 5:
            days.append(day)
        day += timedelta(days=1)
    return days


def _make_prices(rng: random.Random, days: list[date]) -> dict[str, dict[date, float]]:
    """A random walk for each share, with a sharp run of rises every few months."""
    prices: dict[str, dict[date, float]] = {}
    for symbol, (_, start_price) in SHARES.items():
        price = start_price
        series: dict[date, float] = {}
        run_left = 0
        for day in days:
            if run_left == 0 and rng.random() < 0.012:
                run_left = rng.randint(8, 14)
            drift = 0.017 if run_left else 0.0002
            if run_left:
                run_left -= 1
            price = max(0.5, price * (1 + drift + rng.gauss(0, 0.014)))
            series[day] = round(price, 3)
        prices[symbol] = series
    return prices


class _MadeUpPrices:
    """The price source for this script. It never touches the internet."""

    def __init__(self, prices: dict[str, dict[date, float]]) -> None:
        self._prices = prices

    def fetch_prices(self, market: str, symbol: str, start: date, end: date) -> PriceHistory | None:
        series = self._prices.get(symbol)
        if series is None:
            return None
        closes = {d: Decimal(str(p)) for d, p in series.items() if start <= d <= end}
        return PriceHistory(currency="AUD", closes=closes, splits=[])

    def fetch_fx_to_nzd(self, currency: str, start: date, end: date) -> dict[date, Decimal] | None:
        days = _weekdays(start, end)
        return {d: Decimal("1.08") for d in days}


def _make_trades(rng: random.Random, prices: dict[str, dict[date, float]]) -> list[Trade]:
    """Someone who buys after sharp rises, sells winners quickly, holds losers, and trades a lot."""
    days = _weekdays(TRADING_FROM, TRADING_TO)
    all_days = sorted(next(iter(prices.values())))
    index = {d: i for i, d in enumerate(all_days)}
    held: dict[str, tuple[Decimal, Decimal]] = {}  # symbol -> (quantity, cost per share)
    cash = Decimal(20000)
    trades: list[Trade] = []

    def trailing_rise(symbol: str, day: date) -> float:
        i = index[day]
        return prices[symbol][all_days[i - 1]] / prices[symbol][all_days[i - 1 - WINDOW]] - 1

    def add(day: date, symbol: str, side: Side, quantity: Decimal, price: Decimal) -> None:
        n = len(trades) + 1
        trades.append(
            Trade(
                id=f"row-{n + 1}",
                source_id=f"DEMO{n:04d}",
                executed_at=datetime(day.year, day.month, day.day, 1, 0, tzinfo=UTC),
                market="ASX",
                symbol=symbol,
                name=SHARES[symbol][0],
                side=side,
                quantity=quantity,
                price=price,
                currency="AUD",
                fee=Decimal("1.00"),
                initiated_by=InitiatedBy.USER,
            )
        )

    for day in days:
        if (day.day <= 3 and day.weekday() == 0) or (day.day == 1):
            cash += Decimal(3000)  # money added each month
        # Sell: winners go quickly. Losers are held.
        for symbol, (quantity, cost) in list(held.items()):
            price = Decimal(str(prices[symbol][day]))
            change = price / cost - 1
            if (change >= Decimal("0.04") and rng.random() < SELL_WINNER_CHANCE) or (
                change <= Decimal("-0.2") and rng.random() < 0.01
            ):
                add(day, symbol, Side.SELL, quantity, price)
                cash += quantity * price - 1
                del held[symbol]
        # Buy: usually the share that has just risen the most.
        if cash >= 3000 and rng.random() < BUY_CHANCE:
            candidates = [s for s in SHARES if s not in held]
            if candidates:
                if rng.random() < CHASE_RISES:
                    symbol = max(candidates, key=lambda s: trailing_rise(s, day))
                else:
                    symbol = rng.choice(candidates)
                price = Decimal(str(prices[symbol][day]))
                amount = Decimal(rng.choice([3000, 4000, 5000]))
                quantity = (amount / price).quantize(Decimal("1"))
                if quantity > 0:
                    add(day, symbol, Side.BUY, quantity, price)
                    held[symbol] = (quantity, price)
                    cash -= quantity * price + 1
    return trades


def build_report(model: ChatModel | None = None, seed: int = SEED) -> Report:
    rng = random.Random(seed)
    prices = _make_prices(rng, _weekdays(PRICES_FROM, TRADING_TO))
    trades = _make_trades(rng, prices)
    imported = ImportResult(broker="sharesies", trades=trades, skipped_rows=[])
    report = analyse(enrich(imported, _MadeUpPrices(prices)))
    if model is None:
        return explain_with_facts(report)
    return explain_report(report, model, ExplanationCache())


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--groq", action="store_true", help="write the explanations with Groq")
    args = parser.parse_args()

    model: ChatModel | None = None
    if args.groq:
        settings = get_settings()
        model = GroqModel(settings.groq_api_key, settings.groq_model)

    report = build_report(model)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")

    print(f"Wrote {OUTPUT}")
    print(f"{report.summary.trades_read} made-up trades, {report.summary.decisions} decisions")
    for finding in report.findings:
        print(f"  {finding.title}: {finding.result} ({finding.explained_by})")


if __name__ == "__main__":
    main()
