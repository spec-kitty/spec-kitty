"""The contributor guidance for the docs lint stays present and honest (issue #5426, FR-015 / SC-004).

The how-to (``review-gates.md``) must tell a contributor how to run both checks, add an ignore word
and read a failure. The reference (``ci-gate-mechanics.md``) must describe the ``docs-lint`` CI job.
The compliant changelog example on the how-to page is run through the real guard, so the page can
never teach an entry shape the guard itself rejects.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Final

import pytest

from scripts.docs import check_changelog_style as ccs

pytestmark = [pytest.mark.unit, pytest.mark.fast]

REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[2]
HOW_TO: Final[Path] = REPO_ROOT / "docs" / "development" / "how-to" / "review-gates.md"
REFERENCE: Final[Path] = REPO_ROOT / "docs" / "development" / "reference" / "ci-gate-mechanics.md"

EXAMPLE_MARKER: Final[str] = "<!-- docs-lint-example -->"
_EXAMPLE_RE: Final[re.Pattern[str]] = re.compile(
    re.escape(EXAMPLE_MARKER) + r"\s*\n```[a-z]*\n(?P<entry>.*?)\n```",
    re.DOTALL,
)
_HEADING_RE: Final[re.Pattern[str]] = re.compile(r"^#{2,4}\s+`?docs-lint`?\b", re.MULTILINE)
_HOW_TO_TOKENS: Final[tuple[str, ...]] = (
    "make docs-lint",
    "ignore-words-list",
    "pyproject.toml",
    "--pass typo",
    "--pass us",
    "--pass unreleased",
    "check_changelog_style",
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


@pytest.mark.parametrize("token", _HOW_TO_TOKENS)
def test_how_to_names_every_command_and_the_ignore_list(token: str) -> None:
    assert token in _read(HOW_TO), f"review-gates.md must mention `{token}`"


def test_how_to_warns_against_bare_codespell() -> None:
    text = _read(HOW_TO)
    assert re.search(r"bare\s+`?codespell`?", text), "review-gates.md must warn against running bare codespell"


def test_reference_has_a_docs_lint_heading() -> None:
    assert _HEADING_RE.search(_read(REFERENCE)), "ci-gate-mechanics.md needs a `docs-lint` heading"


def test_pages_link_to_each_other() -> None:
    assert "ci-gate-mechanics.md" in _read(HOW_TO)
    assert "review-gates.md" in _read(REFERENCE)


def test_how_to_no_longer_uses_the_retired_sync_example() -> None:
    assert "sync could deliver" not in _read(HOW_TO)


def _example_entry() -> str:
    match = _EXAMPLE_RE.search(_read(HOW_TO))
    assert match is not None, f"review-gates.md needs a fenced example right after {EXAMPLE_MARKER}"
    return match.group("entry")


def test_compliant_example_passes_the_real_guard() -> None:
    entry = _example_entry()
    changelog = f"# Changelog\n\n## [Unreleased]\n\n### Fixed\n\n{entry}\n\n## [1.0.0] - 2026-01-01\n"
    errors = [finding for finding in ccs.check(changelog) if finding.severity == "error"]
    assert not errors, "the how-to's compliant example fails the guard:\n" + "\n".join(ccs.format_finding(finding) for finding in errors)


def test_compliant_example_is_not_vacuous() -> None:
    entry = _example_entry()
    assert entry.lstrip().startswith("- **"), "the example must lead with a bold headline"
    assert "**Before:**" in entry and "**After:**" in entry
    assert len(entry) <= ccs.LENGTH_WARNING_LIMIT
