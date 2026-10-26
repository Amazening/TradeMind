"""Reporting: turn a `Report` into something a person can read."""

from trademind.reporting.explain import ExplanationCache, explain_report, explain_with_facts
from trademind.reporting.models import ChatModel
from trademind.reporting.providers import GroqModel, OllamaModel
from trademind.reporting.text import render_text

__all__ = [
    "ChatModel",
    "ExplanationCache",
    "GroqModel",
    "OllamaModel",
    "explain_report",
    "explain_with_facts",
    "render_text",
]
