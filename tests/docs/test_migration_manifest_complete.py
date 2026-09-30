"""WP05 / T016 — completeness gate for the agent-memory migration manifest.

Mission `self-documenting-repo-01M0287X` audited the operator's local,
gitignored agent-memory file against the repo and produced a resolution for
every gap-filler lesson it contained, grouped into six clusters (G1-G6). The
working artifact that audit was run against (``work/memory-gap-filler-
analysis.md``) is gitignored and does not exist in this worktree or in CI —
so the manifest at
:mod:`docs/archive/development/agent-memory-migration-manifest.md` IS the committed
authority, not a summary of one.

This module does **not** hardcode the gap-filler list as an inline literal
(that would be the exact tautology this gate exists to prevent — a test that
can only ever agree with itself). Instead it parses the manifest's own
G1-G6 markdown tables at collection/run time and asserts three structural
properties against whatever rows are actually there:

1. all six clusters (G1-G6) are present;
2. every parsed row carries exactly one recognised resolution token
   (``home:`` / ``issue:`` / ``retired`` / ``not-remedy-bearing``);
3. every ``home:`` resolution's path exists on disk, resolved against the
   repo root.

A manifest edited to drop a cluster, leave a row unresolved, or point a
``home:`` path at a file that doesn't exist goes red here — the whole point
being that the manifest's claims are checked, not merely displayed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Final

import pytest

pytestmark = pytest.mark.fast

_REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[2]
_MANIFEST_PATH: Final[Path] = _REPO_ROOT / "docs" / "archive" / "development" / "agent-memory-migration-manifest.md"

_EXPECTED_CLUSTERS: Final[tuple[str, ...]] = ("G1", "G2", "G3", "G4", "G5", "G6")

# A cluster heading looks like: "## G1 — Gate-fix guidance (WP01, ...)"
_CLUSTER_HEADING_RE: Final[re.Pattern[str]] = re.compile(r"^##\s+(?P<cluster>G[1-6])\b(?P<rest>.*)$")

# A markdown table row: "| memory entry text | resolution text |"
# Skip separator rows ("| --- | --- |") and the header row itself.
_TABLE_ROW_RE: Final[re.Pattern[str]] = re.compile(r"^\|(?P<cells>.+)\|\s*$")

_RESOLUTION_TOKENS: Final[tuple[str, ...]] = (
    "home:",
    "issue:",
    "retired",
    "not-remedy-bearing",
)

# Matches a markdown link target: [text](path) — used to pull the raw path
# out of a `home:` resolution cell so we can check it exists on disk.
_MD_LINK_RE: Final[re.Pattern[str]] = re.compile(r"\[[^\]]*\]\((?P<target>[^)]+)\)")


@dataclass(frozen=True)
class ManifestRow:
    """One parsed gap-filler row from a G1-G6 table."""

    cluster: str
    entry_cell: str
    resolution_cell: str


def _is_separator_row(cells: str) -> bool:
    """True for markdown table separator rows like ``| --- | --- |``."""
    stripped = cells.strip()
    return bool(stripped) and all(c in "-:| " for c in stripped)


def _split_row_cells(cells: str) -> list[str]:
    return [cell.strip() for cell in cells.split("|")]


def parse_manifest_rows(text: str) -> list[ManifestRow]:
    """Parse every gap-filler table row out of the manifest's G1-G6 sections.

    Walks the document top to bottom, tracking the current ``## G<n>``
    cluster heading. Within a cluster, every markdown table row that is not
    a header ("Memory entry | Resolution") and not a separator row
    (``| --- | --- |``) is treated as one gap-filler entry.
    """
    rows: list[ManifestRow] = []
    current_cluster: str | None = None
    seen_header_in_section = False

    for line in text.splitlines():
        heading_match = _CLUSTER_HEADING_RE.match(line.strip())
        if heading_match:
            current_cluster = heading_match.group("cluster")
            seen_header_in_section = False
            continue

        if line.strip().startswith("## ") and not heading_match:
            # Left the current cluster's section (next top-level heading).
            current_cluster = None
            continue

        if current_cluster is None:
            continue

        row_match = _TABLE_ROW_RE.match(line.strip())
        if not row_match:
            continue

        cells_raw = row_match.group("cells")
        if _is_separator_row(cells_raw):
            continue

        cells = _split_row_cells(cells_raw)
        if len(cells) < 2:  # noqa: PLR2004 (2 = "entry" + "resolution" columns)
            continue

        entry_cell, resolution_cell = cells[0], cells[1]

        if not seen_header_in_section:
            # First non-separator row in the section is the header row
            # ("Memory entry | Resolution"); skip it, start collecting after.
            seen_header_in_section = True
            continue

        if not entry_cell:
            continue

        rows.append(
            ManifestRow(
                cluster=current_cluster,
                entry_cell=entry_cell,
                resolution_cell=resolution_cell,
            )
        )

    return rows


def _resolution_token(resolution_cell: str) -> str | None:
    """Return the recognised resolution token found in a resolution cell."""
    for token in _RESOLUTION_TOKENS:
        if token in resolution_cell:
            return token
    return None


def _extract_home_path(resolution_cell: str) -> str | None:
    """Pull the path out of a ``home:`` resolution's markdown link, if any."""
    link_match = _MD_LINK_RE.search(resolution_cell)
    if link_match:
        return link_match.group("target")
    return None


@pytest.fixture(scope="module")
def manifest_text() -> str:
    assert _MANIFEST_PATH.is_file(), (
        f"Migration manifest missing at {_MANIFEST_PATH}. This test derives its checks from that file's own content — it cannot run without it."
    )
    return _MANIFEST_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def manifest_rows(manifest_text: str) -> list[ManifestRow]:
    rows = parse_manifest_rows(manifest_text)
    assert rows, (
        "Parsed zero gap-filler rows out of the manifest's G1-G6 tables — "
        "either the manifest is empty of content or the table shape drifted "
        "from what this parser expects. Fix the manifest or the parser, "
        "not this assertion."
    )
    return rows


class TestAllClustersPresent:
    """Property (1): all six G1-G6 clusters are present in the manifest."""

    def test_all_six_clusters_present(self, manifest_rows: list[ManifestRow]) -> None:
        present_clusters = {row.cluster for row in manifest_rows}
        missing = set(_EXPECTED_CLUSTERS) - present_clusters
        assert not missing, f"Manifest is missing gap-filler rows for cluster(s) {sorted(missing)}. Expected all of {_EXPECTED_CLUSTERS} to have at least one row."

    def test_no_unexpected_clusters(self, manifest_rows: list[ManifestRow]) -> None:
        present_clusters = {row.cluster for row in manifest_rows}
        unexpected = present_clusters - set(_EXPECTED_CLUSTERS)
        assert not unexpected, (
            f"Manifest has row(s) under unrecognised cluster heading(s) "
            f"{sorted(unexpected)}. The fixed taxonomy is G1-G6; a new "
            "cluster needs a deliberate update to _EXPECTED_CLUSTERS."
        )


class TestEveryRowResolved:
    """Property (2): every gap-filler row carries a recognised resolution."""

    def test_every_row_has_a_resolution_token(self, manifest_rows: list[ManifestRow]) -> None:
        unresolved = [row for row in manifest_rows if _resolution_token(row.resolution_cell) is None]
        assert not unresolved, f"Row(s) with no recognised resolution token ({', '.join(_RESOLUTION_TOKENS)}): " + "; ".join(
            f"[{row.cluster}] {row.entry_cell!r} -> {row.resolution_cell!r}" for row in unresolved
        )


class TestHomePathsExist:
    """Property (3): every ``home:`` resolution's path exists on disk."""

    def test_every_home_path_exists_on_disk(self, manifest_rows: list[ManifestRow]) -> None:
        home_rows = [row for row in manifest_rows if "home:" in row.resolution_cell]
        assert home_rows, (
            "Expected at least one `home:` resolution across the manifest — found none. Either the manifest lost its home: rows or the parser regressed."
        )

        missing: list[str] = []
        for row in home_rows:
            raw_path = _extract_home_path(row.resolution_cell)
            if raw_path is None:
                missing.append(f"[{row.cluster}] {row.entry_cell!r}: `home:` resolution has no parseable markdown link in {row.resolution_cell!r}")
                continue

            # Manifest links are relative to docs/development/ (the
            # manifest's own directory), matching how the file renders on
            # GitHub and any static-site docs build.
            resolved = (_MANIFEST_PATH.parent / raw_path).resolve()
            if not resolved.exists():
                missing.append(f"[{row.cluster}] {row.entry_cell!r}: home path {raw_path!r} does not exist (resolved: {resolved})")

        assert not missing, "Broken `home:` path(s) in manifest:\n" + "\n".join(missing)


class TestManifestNotATautology:
    """Guard against the parser degenerating into an inline-literal echo.

    The mission task text explicitly warns against a completeness test that
    hardcodes the gap-filler list and therefore can only ever agree with
    itself. These tests pin observable, parser-level behaviour instead of
    the manifest's specific content, so a manifest edit that breaks a real
    invariant (missing cluster, unresolved row, dead path) is caught by the
    tests above using data extracted from the file, not duplicated by hand.
    """

    def test_parser_rejects_row_with_no_recognised_token(self) -> None:
        synthetic = "## G1 — synthetic\n\n| Memory entry | Resolution |\n|---|---|\n| `some_entry` | this row has no resolution token at all |\n"
        rows = parse_manifest_rows(synthetic)
        assert len(rows) == 1
        assert _resolution_token(rows[0].resolution_cell) is None

    def test_parser_flags_missing_cluster(self) -> None:
        synthetic = "## G1 — synthetic\n\n| Memory entry | Resolution |\n|---|---|\n| `some_entry` | **retired** |\n"
        rows = parse_manifest_rows(synthetic)
        present_clusters = {row.cluster for row in rows}
        missing = set(_EXPECTED_CLUSTERS) - present_clusters
        assert missing == {"G2", "G3", "G4", "G5", "G6"}

    def test_parser_flags_dead_home_path(self, tmp_path: Path) -> None:
        synthetic_manifest = tmp_path / "synthetic-manifest.md"
        synthetic_manifest.write_text(
            "## G1 — synthetic\n\n| Memory entry | Resolution |\n|---|---|\n| `some_entry` | **home:** [`nope.py`](definitely/does/not/exist.py) |\n",
            encoding="utf-8",
        )
        text = synthetic_manifest.read_text(encoding="utf-8")
        rows = parse_manifest_rows(text)
        assert len(rows) == 1
        raw_path = _extract_home_path(rows[0].resolution_cell)
        assert raw_path == "definitely/does/not/exist.py"
        resolved = (synthetic_manifest.parent / raw_path).resolve()
        assert not resolved.exists()
