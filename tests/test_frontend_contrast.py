"""Colour contrast of the frontend (spec section 9). Reads the tokens from the stylesheet, so a
later colour change that breaks readability fails here. WCAG 2.x: 4.5:1 for normal text, 3:1 for
focus rings and other parts of the interface."""

import re
from pathlib import Path

import pytest

STYLES = Path(__file__).parent.parent / "frontend" / "src" / "styles.css"


def _tokens(block: str) -> dict[str, str]:
    return dict(re.findall(r"--([a-z-]+):\s*(#[0-9a-fA-F]{6})", block))


def _themes() -> dict[str, dict[str, str]]:
    css = STYLES.read_text(encoding="utf-8")
    light_match = re.search(r":root\s*\{(.*?)\n\}", css, re.DOTALL)
    dark_match = re.search(
        r"prefers-color-scheme: dark\)\s*\{\s*:root\s*\{(.*?)\n  \}", css, re.DOTALL
    )
    assert light_match and dark_match
    light = _tokens(light_match.group(1))
    return {"light": light, "dark": {**light, **_tokens(dark_match.group(1))}}


def _luminance(colour: str) -> float:
    channels = [int(colour[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def _ratio(a: str, b: str) -> float:
    lighter, darker = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


TEXT_PAIRS = [
    ("text", "bg"),
    ("text", "surface"),
    ("muted", "bg"),
    ("muted", "surface"),
    ("brand", "bg"),
    ("brand", "surface"),
    ("on-brand", "brand"),
    ("danger", "bg"),
    ("danger", "surface"),
    ("found-text", "found-bg"),
    ("notfound-text", "notfound-bg"),
    ("lack-text", "lack-bg"),
]
INTERFACE_PAIRS = [("focus", "bg"), ("focus", "surface"), ("warn-border", "surface")]


@pytest.mark.parametrize("theme", ["light", "dark"])
@pytest.mark.parametrize(("foreground", "background"), TEXT_PAIRS)
def test_text_has_enough_contrast(theme: str, foreground: str, background: str) -> None:
    colours = _themes()[theme]

    assert _ratio(colours[foreground], colours[background]) >= 4.5


@pytest.mark.parametrize("theme", ["light", "dark"])
@pytest.mark.parametrize(("foreground", "background"), INTERFACE_PAIRS)
def test_focus_rings_and_markers_have_enough_contrast(
    theme: str, foreground: str, background: str
) -> None:
    colours = _themes()[theme]

    assert _ratio(colours[foreground], colours[background]) >= 3.0


def test_the_ratio_function_matches_known_values() -> None:
    assert _ratio("#000000", "#ffffff") == pytest.approx(21.0)
    assert _ratio("#777777", "#ffffff") == pytest.approx(4.48, abs=0.02)
