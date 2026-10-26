"""Ingestion: read a broker CSV, check it, and turn it into standard trades."""

import csv
import io
from pathlib import Path

from trademind.core.errors import NoTradesError, UnrecognisedBrokerError
from trademind.core.models import ImportResult, Side
from trademind.ingestion import sharesies

SUPPORTED_BROKERS = (sharesies.NAME,)


def import_csv(data: bytes | str) -> ImportResult:
    """Detect the broker from the header and read the trades.

    Raises UnrecognisedBrokerError if no supported broker matches, and NoTradesError if the file
    has no buys or sells.
    """
    text = data.decode("utf-8-sig") if isinstance(data, bytes) else data.lstrip("﻿")
    header = next(csv.reader(io.StringIO(text)), [])

    if not sharesies.matches(header):
        raise UnrecognisedBrokerError(
            "This file is not from a supported broker. Supported: " + ", ".join(SUPPORTED_BROKERS)
        )
    result = sharesies.parse(text)

    if not any(trade.side in (Side.BUY, Side.SELL) for trade in result.trades):
        raise NoTradesError("No buy or sell trades were found in this file.")
    return result


def import_file(path: Path) -> ImportResult:
    return import_csv(path.read_bytes())
