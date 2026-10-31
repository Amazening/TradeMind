"""The changelog and the version number must agree, so a report's version can be looked up."""

import json
import re
import tomllib
from pathlib import Path

from trademind import __version__

ROOT = Path(__file__).resolve().parent.parent


def test_newest_changelog_version_is_the_package_version() -> None:
    text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")

    newest = re.search(r"^## \[(\d+\.\d+\.\d+)\]", text, re.MULTILINE)

    assert newest is not None
    assert newest.group(1) == __version__


def test_the_front_end_has_the_same_version() -> None:
    package = json.loads((ROOT / "frontend" / "package.json").read_text(encoding="utf-8"))
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    assert package["version"] == project["project"]["version"]
