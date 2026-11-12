"""The retired docsite generator is named nowhere on a living file (#6943; ADR 2026-10-31-1 D-13 step 5).

The doc-kitty site replaced the legacy generator at the cutover (#6938), and #6943
removed what the cutover left behind. Its done-when is that a case-insensitive
``git grep`` for the legacy tool's name finds nothing outside immutable history.
This gate keeps it that way: it scans every tracked regular text file and fails on
any hit outside :data:`IMMUTABLE_HISTORY` and :data:`GENERATED`.

The excluded sets are data, not a list of offenders: :data:`IMMUTABLE_HISTORY` is the
immutable-history list of the #6943 Mission (its spec, C-001), whose bodies never change, and :data:`GENERATED` holds files a tool rewrites
from those sources. The tool's name is built from two fragments so this file does
not flag itself. A self-test plants a mention in a temporary tree.
"""

from __future__ import annotations

import subprocess
from collections.abc import Iterable
from pathlib import Path
from typing import Final

import pytest

pytestmark = [pytest.mark.architectural, pytest.mark.fast]

_REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[2]

#: The legacy tool's name, lower case, in two fragments so this file never names it.
LEGACY_TOOL: Final[str] = "doc" + "fx"

#: History whose bodies never change (spec C-001): path prefixes and single files.
IMMUTABLE_HISTORY: Final[tuple[str, ...]] = (
    "docs/adr/",
    "docs/changelog/",
    "CHANGELOG.md",
    "docs/plans/",
    "docs/reports/",
    "docs/archive/",
    "kitty-specs/",
    "kitty-ops/",
    ".kittify/evidence/",
    ".kittify/migrations/",
    # The #4562 bulk-edit record at the repository root.
    "occurrence_map.yaml",
    # A dated timeline of the project's history.
    "docs/assets/spec-kitty-evolution-v1-to-v3.html",
)

#: Files a tool regenerates from the history above (the retrieval index quotes ADR text).
GENERATED: Final[tuple[str, ...]] = (
    "docs/development/docs-retrieval-index.yaml",
    ".github/ci-shard-timings.json",
)

#: A living tree this size or larger is scanned; a smaller one means the listing broke.
_MINIMUM_SCANNED: Final[int] = 5000


def is_excluded(rel: str) -> bool:
    """True for a path in immutable history or a generated file."""
    return any(rel == entry or (entry.endswith("/") and rel.startswith(entry)) for entry in (*IMMUTABLE_HISTORY, *GENERATED))


def tracked_regular_files(repo: Path) -> list[str]:
    """Tracked regular files (no symlinks, no submodules), repository-relative."""
    raw = subprocess.run(["git", "-C", str(repo), "ls-files", "-s", "-z"], check=True, capture_output=True).stdout
    paths: list[str] = []
    for record in raw.split(b"\x00"):
        if not record:
            continue
        meta, path = record.split(b"\t", 1)
        if meta.split()[0] in {b"100644", b"100755"}:
            paths.append(path.decode("utf-8", "surrogateescape"))
    return paths


def mentions(repo: Path, paths: Iterable[str]) -> list[str]:
    """``path:line`` of every living line that names the legacy tool (binary files skipped)."""
    found: list[str] = []
    for rel in paths:
        if is_excluded(rel):
            continue
        blob = (repo / rel).read_bytes()
        if b"\x00" in blob or LEGACY_TOOL.encode() not in blob.lower():
            continue
        text = blob.decode("utf-8", "replace")
        found.extend(f"{rel}:{number}" for number, line in enumerate(text.splitlines(), 1) if LEGACY_TOOL in line.lower())
    return found


def test_no_living_file_names_the_legacy_tool() -> None:
    paths = [rel for rel in tracked_regular_files(_REPO_ROOT) if (_REPO_ROOT / rel).is_file()]
    assert len([rel for rel in paths if not is_excluded(rel)]) >= _MINIMUM_SCANNED
    assert mentions(_REPO_ROOT, paths) == []


def test_every_excluded_entry_exists() -> None:
    """A stale exclusion would silently widen the gate's blind spot."""
    missing = [entry for entry in (*IMMUTABLE_HISTORY, *GENERATED) if not (_REPO_ROOT / entry.rstrip("/")).exists()]
    assert missing == []


def test_the_scan_finds_a_planted_mention(tmp_path: Path) -> None:
    (tmp_path / "docs" / "guides").mkdir(parents=True)
    (tmp_path / "docs" / "guides" / "build.md").write_text(f"Run {LEGACY_TOOL.upper()} to build.\n", encoding="utf-8")
    (tmp_path / "docs" / "adr").mkdir()
    (tmp_path / "docs" / "adr" / "old.md").write_text(f"We chose {LEGACY_TOOL}.\n", encoding="utf-8")
    (tmp_path / "logo.png").write_bytes(b"\x89PNG\x00" + LEGACY_TOOL.encode())

    found = mentions(tmp_path, ["docs/guides/build.md", "docs/adr/old.md", "logo.png"])

    assert found == ["docs/guides/build.md:1"]  # the ADR is history and the image is binary


def test_a_living_file_without_a_mention_passes(tmp_path: Path) -> None:
    """Positive control on the same scan."""
    (tmp_path / "README.md").write_text("Build the docs with doc-kitty.\n", encoding="utf-8")
    assert mentions(tmp_path, ["README.md"]) == []
