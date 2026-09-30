"""The real docs tree is clean under every spelling pass (issue #5426, FR-006 / FR-007).

These tests run the production entry points against the real repository, not a fixture tree. Each
pass asserts zero findings AND that the scanned count equals an independent on-disk oracle, so a
pass that silently looks at nothing (or at less than it should) goes red instead of green.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Final

import pytest

from scripts.docs import check_spelling as cs
from scripts.release import validate_release

pytestmark = [pytest.mark.unit, pytest.mark.fast]

REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[2]
CHANGELOG: Final[Path] = REPO_ROOT / cs.DEFAULT_CHANGELOG

# Skip trees that [tool.codespell] excludes; the oracle below re-derives the scanned set from disk
# without going through `_is_skipped`, so a wrong or over-broad skip glob shows up as a mismatch.
_TYPO_ROOTS: Final[tuple[str, ...]] = ("docs", "packs/built-in")
_US_ROOTS: Final[tuple[str, ...]] = ("docs/guides", "docs/context")
_SKIPPED_TREES: Final[tuple[str, ...]] = ("docs/archive", "docs/reports", "docs/plans")
_SKIPPED_FILES: Final[tuple[str, ...]] = ("docs/api/cli-commands.md",)


def _report(result: cs.PassResult) -> str:
    return "\n".join(cs.format_finding(finding) for finding in result.findings)


def _on_disk_markdown(roots: tuple[str, ...], extra_files: tuple[str, ...] = ()) -> int:
    """Independent count: real ``*.md`` files under *roots* (plus *extra_files*), minus skips and symlinks."""
    found: set[Path] = set()
    for root in roots:
        found.update((REPO_ROOT / root).rglob("*.md"))
    found.update(REPO_ROOT / name for name in extra_files)
    count = 0
    for path in found:
        rel = path.relative_to(REPO_ROOT).as_posix()
        if path.is_symlink() or not path.is_file():
            continue
        if rel in _SKIPPED_FILES or any(rel == tree or rel.startswith(tree + "/") for tree in _SKIPPED_TREES):
            continue
        count += 1
    return count


def test_typo_pass_clean() -> None:
    result = cs.run_pass("typo", REPO_ROOT, CHANGELOG)
    oracle = _on_disk_markdown(_TYPO_ROOTS, ("README.md",))
    assert oracle > 0
    assert result.scanned == oracle, f"typo pass scanned {result.scanned} file(s); {oracle} exist on disk"
    assert not result.findings, f"typo findings:\n{_report(result)}"


def test_us_pass_clean() -> None:
    result = cs.run_pass("us", REPO_ROOT, CHANGELOG)
    oracle = _on_disk_markdown(_US_ROOTS)
    assert oracle > 0
    assert result.scanned == oracle, f"US pass scanned {result.scanned} file(s); {oracle} exist on disk"
    assert not result.findings, f"US-spelling findings:\n{_report(result)}"


def _assert_unreleased_pass_clean(changelog: Path) -> None:
    """The live-file contract: zero findings, and the scan covered exactly the section's lines."""
    result = cs.run_pass("unreleased", REPO_ROOT, changelog)
    section = validate_release.unreleased_section(changelog.read_text(encoding="utf-8"))
    expected = 0 if section is None else len(section.lines)
    assert result.scanned == expected, f"Unreleased pass scanned {result.scanned} line(s); the section has {expected}"
    assert not result.findings, f"Unreleased US-spelling findings:\n{_report(result)}"


def test_unreleased_us_pass_clean() -> None:
    _assert_unreleased_pass_clean(CHANGELOG)


def test_unreleased_us_pass_still_clean_right_after_a_release_cut(release_cut_changelog: Path) -> None:
    """A fresh empty Unreleased section is a pass; no test may pin the section's current size."""
    _assert_unreleased_pass_clean(release_cut_changelog)


def test_production_entry_point_exits_zero() -> None:
    """`python -m scripts.docs.check_spelling` (all passes) is the exact command CI runs."""
    proc = subprocess.run(
        [sys.executable, "-m", "scripts.docs.check_spelling"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert proc.returncode == 0, f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"


# ---------------------------------------------------------------------------
# T018: glossary heading renames keep their legacy anchors (operator decision 01M3RFQ90SJVVDQ7C4AV6W13FM)
# ---------------------------------------------------------------------------

# (page, legacy anchor id, new US heading line)
RENAMED_HEADINGS: Final[tuple[tuple[str, str, str], ...]] = (
    ("docs/context/charter.md", "organisation-tier", "### Organization Tier"),
    ("docs/context/execution.md", "communication-artefact", "### communication artifact"),
    ("docs/guides/gstack-glossary-observations.md", "trail-behaviour", "## Trail Behavior"),
)


@pytest.mark.parametrize(("page", "legacy_id", "heading"), RENAMED_HEADINGS)
def test_renamed_heading_keeps_legacy_anchor(page: str, legacy_id: str, heading: str) -> None:
    """The old slug stays reachable: the legacy anchor sits directly above the new US heading."""
    lines = (REPO_ROOT / page).read_text(encoding="utf-8").splitlines()
    assert heading in lines, f"{page} has no {heading!r} heading"
    above = lines[lines.index(heading) - 2 : lines.index(heading)]
    assert above == [f'<a id="{legacy_id}"></a>', ""], f"{page}: legacy anchor {legacy_id!r} is not directly above {heading!r}"


@pytest.mark.parametrize("legacy_slug", ["organisation-tier", "communication-artefact"])
def test_no_in_page_links_to_legacy_slugs(legacy_slug: str) -> None:
    """In-page links moved to the new slug; only the legacy anchor itself keeps the old one."""
    offenders = [
        f"{path.relative_to(REPO_ROOT).as_posix()}:{number}"
        for path in sorted((REPO_ROOT / "docs" / "context").rglob("*.md"))
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1)
        if f"](#{legacy_slug})" in line
    ]
    assert not offenders, f"links still target #{legacy_slug}: {offenders}"


def test_communication_artifact_alias_row_records_uk_spelling() -> None:
    """The ratified UK spelling survives as an alias in the entry's table (the YAML has no aliases)."""
    text = (REPO_ROOT / "docs/context/execution.md").read_text(encoding="utf-8")
    entry = text.split("### communication artifact\n", 1)[1].split("\n---\n", 1)[0]
    alias_rows = [line for line in entry.splitlines() if line.startswith("| **Alias**")]
    assert len(alias_rows) == 1, f"expected exactly one Alias row, found {alias_rows}"
    assert "communication artefact" in alias_rows[0]
