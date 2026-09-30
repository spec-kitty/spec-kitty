"""WP06 / T013 — completeness gate for the Bucket-2 workflow migration manifest.

Mission `workflow-mechanics-self-doc-01M02SF1` ("Bucket 2") audited the
~49 workflow/CI/git/status-and-sync **mechanics** entries in the operator's
local, gitignored agent-memory file and produced a resolution for each,
grouped into three clusters (A &#8212; landing/git, B &#8212; CI, C &#8212;
status/mission/sync). The working audit that classified each entry
(``work/bucket2-workflow-memory-audit.md``) is gitignored and does not exist
in this worktree or in CI &#8212; so the manifest at
:mod:`docs/archive/development/agent-memory-workflow-migration-manifest.md` **is**
the committed authority, not a summary of one.

This module does **not** hardcode the 49-entry list as an inline literal
(that would be the exact tautology this gate exists to prevent &#8212; a test
that can only ever agree with itself). Instead it parses the manifest's own
Cluster A/B/C markdown tables at collection/run time and asserts three
structural properties against whatever rows are actually there:

1. all three clusters (A, B, C) are present;
2. every parsed row carries exactly one recognised resolution token
   (``home:`` / ``already-home:`` / ``learned-fact:`` / ``keep-private`` /
   ``charter-candidate``);
3. every path-bearing token (``home:``, ``already-home:``,
   ``learned-fact:``) resolves to a real file on disk; the two pathless
   tokens (``keep-private``, ``charter-candidate``) are recognised without a
   path.

A manifest edited to drop a cluster, leave a row unresolved, or point a
path-bearing token at a file that doesn't exist goes red here &#8212; the
whole point being that the manifest's claims are checked, not merely
displayed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Final

import pytest

pytestmark = pytest.mark.fast

_REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[2]
_MANIFEST_PATH: Final[Path] = _REPO_ROOT / "docs" / "archive" / "development" / "agent-memory-workflow-migration-manifest.md"

_EXPECTED_CLUSTERS: Final[tuple[str, ...]] = ("A", "B", "C")

# A cluster heading looks like: "## Cluster A &#8212; Landing / git (17)"
_CLUSTER_HEADING_RE: Final[re.Pattern[str]] = re.compile(r"^##\s+Cluster\s+(?P<cluster>[A-C])\b(?P<rest>.*)$")

# A markdown table row: "| memory entry text | resolution text |"
# Skip separator rows ("| --- | --- |") and the header row itself.
_TABLE_ROW_RE: Final[re.Pattern[str]] = re.compile(r"^\|(?P<cells>.+)\|\s*$")

# Path-bearing tokens must resolve to a real file; pathless tokens are
# recognised without a path check. Longer/more-specific tokens are listed
# first so ``already-home:`` is matched before a hypothetical bare ``home:``
# substring match could misfire on it.
_PATH_TOKENS: Final[tuple[str, ...]] = (
    "already-home:",
    "learned-fact:",
    "home:",
)
_PATHLESS_TOKENS: Final[tuple[str, ...]] = (
    "keep-private",
    "charter-candidate",
)
_RESOLUTION_TOKENS: Final[tuple[str, ...]] = _PATH_TOKENS + _PATHLESS_TOKENS

# Matches a markdown link target: [text](path) — used to pull the raw path
# out of a path-bearing resolution cell so we can check it exists on disk.
_MD_LINK_RE: Final[re.Pattern[str]] = re.compile(r"\[[^\]]*\]\((?P<target>[^)]+)\)")

# The *governing* token for a row is the bolded token at the START of the
# resolution cell (e.g. "**home:** [`x`](y) — rationale"). Matching only
# here — rather than a bare substring search over the whole cell — prevents
# a token word mentioned in prose (e.g. a correction note that says "the
# draft proposed `learned-fact:`, but...") from being mistaken for the
# row's actual resolution.
_LEADING_TOKEN_RE: Final[re.Pattern[str]] = re.compile(r"^\*\*(?P<token>already-home:|learned-fact:|home:|keep-private|charter-candidate)\*\*")


@dataclass(frozen=True)
class ManifestRow:
    """One parsed memory-entry row from a Cluster A/B/C table."""

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
    """Parse every memory-entry table row out of the manifest's A/B/C sections.

    Walks the document top to bottom, tracking the current ``## Cluster <X>``
    heading. Within a cluster, every markdown table row that is not a header
    ("Memory entry | Resolution") and not a separator row
    (``| --- | --- |``) is treated as one memory-entry row.
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
    """Return the recognised resolution token *governing* a resolution cell.

    Only the bolded token leading the cell counts as the row's resolution —
    see :data:`_LEADING_TOKEN_RE` for why a bare substring search over the
    whole cell is unsafe here.
    """
    match = _LEADING_TOKEN_RE.match(resolution_cell.strip())
    if match:
        return match.group("token")
    return None


def _extract_home_path(resolution_cell: str) -> str | None:
    """Pull the path out of a path-bearing resolution's markdown link, if any."""
    link_match = _MD_LINK_RE.search(resolution_cell)
    if link_match:
        return link_match.group("target")
    return None


@pytest.fixture(scope="module")
def manifest_text() -> str:
    assert _MANIFEST_PATH.is_file(), (
        f"Workflow migration manifest missing at {_MANIFEST_PATH}. This test derives its checks from that file's own content — it cannot run without it."
    )
    return _MANIFEST_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def manifest_rows(manifest_text: str) -> list[ManifestRow]:
    rows = parse_manifest_rows(manifest_text)
    assert rows, (
        "Parsed zero memory-entry rows out of the manifest's Cluster A/B/C "
        "tables — either the manifest is empty of content or the table "
        "shape drifted from what this parser expects. Fix the manifest or "
        "the parser, not this assertion."
    )
    return rows


class TestAllClustersPresent:
    """Property (1): all three A/B/C clusters are present in the manifest."""

    def test_all_three_clusters_present(self, manifest_rows: list[ManifestRow]) -> None:
        present_clusters = {row.cluster for row in manifest_rows}
        missing = set(_EXPECTED_CLUSTERS) - present_clusters
        assert not missing, (
            f"Manifest is missing memory-entry rows for cluster(s) {sorted(missing)}. Expected all of {_EXPECTED_CLUSTERS} to have at least one row."
        )

    def test_no_unexpected_clusters(self, manifest_rows: list[ManifestRow]) -> None:
        present_clusters = {row.cluster for row in manifest_rows}
        unexpected = present_clusters - set(_EXPECTED_CLUSTERS)
        assert not unexpected, (
            f"Manifest has row(s) under unrecognised cluster heading(s) "
            f"{sorted(unexpected)}. The fixed taxonomy is A/B/C; a new "
            "cluster needs a deliberate update to _EXPECTED_CLUSTERS."
        )


class TestManifestCoversFortyNineEntries:
    """The mission's audit covers exactly 49 memory entries across A/B/C."""

    def test_row_count_is_forty_nine(self, manifest_rows: list[ManifestRow]) -> None:
        assert len(manifest_rows) == 49, (
            f"Expected exactly 49 memory-entry rows across Cluster A/B/C, "
            f"found {len(manifest_rows)}. The Bucket-2 audit scoped exactly "
            "49 workflow/CI/git/status-and-sync mechanics entries — a "
            "count drift means a row was added, dropped, or merged without "
            "updating this pin."
        )


class TestEveryRowResolved:
    """Property (2): every memory-entry row carries a recognised resolution."""

    def test_every_row_has_a_resolution_token(self, manifest_rows: list[ManifestRow]) -> None:
        unresolved = [row for row in manifest_rows if _resolution_token(row.resolution_cell) is None]
        assert not unresolved, f"Row(s) with no recognised resolution token ({', '.join(_RESOLUTION_TOKENS)}): " + "; ".join(
            f"[{row.cluster}] {row.entry_cell!r} -> {row.resolution_cell!r}" for row in unresolved
        )


class TestPathBearingResolutionsExist:
    """Property (3a): every ``home:``/``already-home:``/``learned-fact:`` path exists."""

    def test_every_path_bearing_resolution_exists_on_disk(self, manifest_rows: list[ManifestRow]) -> None:
        path_rows = [row for row in manifest_rows if _resolution_token(row.resolution_cell) in _PATH_TOKENS]
        assert path_rows, (
            "Expected at least one path-bearing resolution across the "
            "manifest — found none. Either the manifest lost its "
            "home:/already-home:/learned-fact: rows or the parser regressed."
        )

        missing: list[str] = []
        for row in path_rows:
            raw_path = _extract_home_path(row.resolution_cell)
            if raw_path is None:
                missing.append(f"[{row.cluster}] {row.entry_cell!r}: path-bearing resolution has no parseable markdown link in {row.resolution_cell!r}")
                continue

            # Manifest links are relative to docs/development/ (the
            # manifest's own directory), matching how the file renders on
            # GitHub and any static-site docs build.
            resolved = (_MANIFEST_PATH.parent / raw_path).resolve()
            if not resolved.exists():
                missing.append(f"[{row.cluster}] {row.entry_cell!r}: path {raw_path!r} does not exist (resolved: {resolved})")

        assert not missing, "Broken path-bearing resolution(s) in manifest:\n" + "\n".join(missing)


class TestPathlessTokensRecognisedWithoutPath:
    """Property (3b): ``keep-private``/``charter-candidate`` need no path."""

    def test_pathless_rows_do_not_require_a_link(self, manifest_rows: list[ManifestRow]) -> None:
        pathless_rows = [row for row in manifest_rows if _resolution_token(row.resolution_cell) in _PATHLESS_TOKENS]
        assert pathless_rows, (
            "Expected at least one keep-private/charter-candidate row across "
            "the manifest — found none. Either the manifest lost its "
            "pathless rows or the parser regressed."
        )
        for row in pathless_rows:
            token = _resolution_token(row.resolution_cell)
            assert token in _PATHLESS_TOKENS
            # No assertion that a link is absent — a pathless row may still
            # cross-reference another row's path in prose. The only
            # contract here is that recognition does not *require* a link.


class TestManifestNotATautology:
    """Guard against the parser degenerating into an inline-literal echo.

    The mission task text explicitly warns against a completeness test that
    hardcodes the memory-entry list and therefore can only ever agree with
    itself. These tests pin observable, parser-level behaviour instead of
    the manifest's specific content, so a manifest edit that breaks a real
    invariant (missing cluster, unresolved row, dead path) is caught by the
    tests above using data extracted from the file, not duplicated by hand.
    """

    def test_parser_rejects_row_with_no_recognised_token(self) -> None:
        synthetic = "## Cluster A — synthetic\n\n| Memory entry | Resolution |\n|---|---|\n| `some_entry` | this row has no resolution token at all |\n"
        rows = parse_manifest_rows(synthetic)
        assert len(rows) == 1
        assert _resolution_token(rows[0].resolution_cell) is None

    def test_parser_flags_missing_cluster(self) -> None:
        synthetic = "## Cluster A — synthetic\n\n| Memory entry | Resolution |\n|---|---|\n| `some_entry` | **keep-private** |\n"
        rows = parse_manifest_rows(synthetic)
        present_clusters = {row.cluster for row in rows}
        missing = set(_EXPECTED_CLUSTERS) - present_clusters
        assert missing == {"B", "C"}

    def test_parser_flags_dead_home_path(self, tmp_path: Path) -> None:
        synthetic_manifest = tmp_path / "synthetic-manifest.md"
        synthetic_manifest.write_text(
            "## Cluster A — synthetic\n\n| Memory entry | Resolution |\n|---|---|\n| `some_entry` | **home:** [`nope.py`](definitely/does/not/exist.py) |\n",
            encoding="utf-8",
        )
        text = synthetic_manifest.read_text(encoding="utf-8")
        rows = parse_manifest_rows(text)
        assert len(rows) == 1
        raw_path = _extract_home_path(rows[0].resolution_cell)
        assert raw_path == "definitely/does/not/exist.py"
        resolved = (synthetic_manifest.parent / raw_path).resolve()
        assert not resolved.exists()

    def test_parser_recognises_pathless_tokens_without_a_link(self) -> None:
        synthetic = (
            "## Cluster A — synthetic\n\n"
            "| Memory entry | Resolution |\n"
            "|---|---|\n"
            "| `some_entry_1` | **keep-private** — no link at all |\n"
            "| `some_entry_2` | **charter-candidate** — no link at all |\n"
        )
        rows = parse_manifest_rows(synthetic)
        assert len(rows) == 2
        for row in rows:
            token = _resolution_token(row.resolution_cell)
            assert token in _PATHLESS_TOKENS
            assert _extract_home_path(row.resolution_cell) is None
