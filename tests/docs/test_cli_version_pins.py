"""Living pages pin only released ``spec-kitty-cli`` versions (#7678).

A living page (``scripts.docs._living_pages``: the published set minus the history
folders), plus the repository-root ``README.md`` and ``CONTRIBUTING.md``, must not pin a
``spec-kitty-cli`` version that PyPI never published. ``==4.0.0`` and ``==3.2.6rc3`` were
both on living pages: an install line with such a pin fails. The known versions are a
checked-in snapshot (``fixtures/spec_kitty_cli_released_versions.txt``), so the check is
offline. A placeholder pin (``==<version>``, ``==X.Y.Z``) is not a version and is skipped.

The same pages must not show a 3.x or older ``spec-kitty --version`` sample output.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from scripts.docs import _living_pages as living

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DOCS = _REPO_ROOT / "docs"
_RELEASED = Path(__file__).parent / "fixtures" / "spec_kitty_cli_released_versions.txt"
_ROOT_PAGES = ("README.md", "CONTRIBUTING.md")

_PIN = re.compile(r"spec-kitty-cli\s*==\s*['\"]?(\d[0-9A-Za-z.+!-]*\w)")
_OLD_VERSION_OUTPUT = re.compile(r"spec-kitty-cli version [0-3]\.")


def released_versions() -> frozenset[str]:
    lines = _RELEASED.read_text(encoding="utf-8").splitlines()
    return frozenset(line.strip() for line in lines if line.strip() and not line.startswith("#"))


def pinned_versions(text: str) -> list[str]:
    return [match.group(1) for match in _PIN.finditer(text)]


def _living_texts() -> dict[str, str]:
    texts = {page: living.published_text((_DOCS / page).read_text(encoding="utf-8")) for page in living.living_pages(_DOCS)}
    for page in _ROOT_PAGES:
        texts[page] = (_REPO_ROOT / page).read_text(encoding="utf-8")
    return texts


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ("pipx install --force spec-kitty-cli==4.0.0rc8", ["4.0.0rc8"]),
        ("uv tool install 'spec-kitty-cli==4.0.0'", ["4.0.0"]),
        ('uvx --from "spec-kitty-cli==3.2.6rc3" spec-kitty', ["3.2.6rc3"]),
        ("pip install --upgrade 'spec-kitty-cli==<version>'", []),
        ("pipx install --force spec-kitty-cli==X.Y.Z", []),
        ("pipx install --pip-args=--pre spec-kitty-cli", []),
    ],
)
def test_a_pin_is_read_and_a_placeholder_is_not(line: str, expected: list[str]) -> None:
    assert pinned_versions(line) == expected


def test_the_snapshot_names_real_releases_and_no_yanked_or_missing_one() -> None:
    versions = released_versions()
    assert {"3.2.7", "4.0.0rc8"} <= versions  # non-vacuity
    assert not {"4.0.0", "3.2.6rc3", "4.1.5", "4.2.0a1"} & versions  # never published, or yanked


def test_no_living_page_pins_an_unreleased_cli_version() -> None:
    texts = _living_texts()
    assert len(texts) >= 300  # non-vacuity: the published living set
    known = released_versions()
    unreleased = {f"{page}: spec-kitty-cli=={version}" for page, text in texts.items() for version in pinned_versions(text) if version not in known}
    assert not unreleased, (
        "Living pages pin spec-kitty-cli versions that PyPI never published (or yanked). "
        "Pin a released version, or refresh tests/docs/fixtures/spec_kitty_cli_released_versions.txt "
        f"after a release: {sorted(unreleased)}"
    )


def test_no_living_page_shows_a_3x_version_output() -> None:
    stale = {
        f"{page}:{number}" for page, text in _living_texts().items() for number, line in enumerate(text.splitlines(), start=1) if _OLD_VERSION_OUTPUT.search(line)
    }
    assert not stale, f"Sample `spec-kitty --version` output shows a 3.x or older version: {sorted(stale)}"
