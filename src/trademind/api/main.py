"""Builds the app from settings. Run with `trademind serve`, or with uvicorn:

uvicorn trademind.api.main:build_app --factory
"""

import logging

from fastapi import FastAPI

from trademind.api.app import create_app
from trademind.core.settings import get_settings
from trademind.enrichment import CachedPriceSource, PriceSource, YahooPriceSource
from trademind.reporting import ChatModel, GroqModel

logger = logging.getLogger("trademind.api")


def _log_to_console() -> None:
    """Show TradeMind's own log lines (counts and timings only) next to uvicorn's."""
    root = logging.getLogger("trademind")
    if not root.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(levelname)s:     %(name)s: %(message)s"))
        root.addHandler(handler)
    root.setLevel(logging.INFO)


def build_app() -> FastAPI:
    _log_to_console()
    settings = get_settings()
    # Yahoo is for development. It is not licensed for a public app (spec section 4.2).
    source: PriceSource = CachedPriceSource(YahooPriceSource(), settings.price_cache_dir)
    model: ChatModel | None = None
    if settings.groq_api_key is not None:
        model = GroqModel(settings.groq_api_key, settings.groq_model)
        logger.info("Explanations: AI (%s), with the tool's own text as the fallback.", model.name)
    else:
        logger.info("No GROQ_API_KEY set: explanations are written by the tool, not by AI.")
    if not (settings.frontend_dir / "index.html").is_file():
        logger.info(
            "No built frontend at %s. Only the API is served. Run `npm run build` in frontend/.",
            settings.frontend_dir,
        )
    return create_app(
        price_source=source,
        chat_model=model,
        static_dir=settings.frontend_dir,
        uploads_per_hour=settings.uploads_per_hour or None,
    )
