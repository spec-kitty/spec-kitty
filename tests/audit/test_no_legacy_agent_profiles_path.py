"""Regression guards for the removed legacy doctrine profile path."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from tests._support.docfx_reports_guard import assert_docfx_does_not_publish_reports

pytestmark = [pytest.mark.integration]

REPO_ROOT = Path(__file__).resolve().parents[2]
LEGACY_DIRNAME = "agent" + "-" + "profiles"
LEGACY_PATH = REPO_ROOT / "src" / "charter" / "offering" / LEGACY_DIRNAME
DOCFX_CONFIG_PATH = REPO_ROOT / "docs" / "docfx.json"

# Scan roots and exclusions are all relative to the repository root, so the
# scan can be pointed at a synthetic tmp_path tree as well as the real repo.
ACTIVE_CODEBASE_PATHS: tuple[Path, ...] = (
    Path("src"),
    Path("tests"),
    Path("docs"),
    Path("architecture"),
    Path("research"),
    Path("README.md"),
    Path("CHANGELOG.md"),
    Path("AGENTS.md"),
    Path("pyproject.toml"),
)

_SKIPPED_SUFFIXES: frozenset[str] = frozenset({".pyc", ".html", ".htm"})


# Generated artifacts that MIRROR doc content rather than reference the removed
# doctrine directory. The Common Docs retrieval index stores heading-anchor
# slugs, so a legitimately-named heading such as "Pillar 1: Agent Profiles"
# yields a slug equal to LEGACY_DIRNAME -- a coincidental substring, NOT the
# deleted doctrine directory this guard targets. Excluding the generated index
# keeps the guard focused on genuine source references.
# (This comment intentionally avoids the contiguous hyphenated literal so the
# guard does not flag itself.)
_GENERATED_EXCLUSIONS: frozenset[Path] = frozenset({Path("docs") / "development" / "3-2-docs-retrieval-index.yaml"})

# Curated docs that name the live GitHub domain label literally called
# "agent" + "-" + "profiles" (the "Agent profile system" label in the issue
# tracker), which is a coincidental substring match -- NOT a reference to the
# deleted src/charter/offering/<hyphenated> doctrine directory this guard
# targets. The label name is fixed by GitHub and must appear verbatim in the
# label taxonomy, so excluding the doc keeps the guard focused on genuine
# source-path references.
# (This comment intentionally avoids the contiguous hyphenated literal so the
# guard does not flag itself.)
_LEGITIMATE_LABEL_REFERENCES: frozenset[Path] = frozenset({Path("docs") / "development" / "how-to" / "manage-issue-tracker.md"})

_EXCLUDED_FILES: frozenset[Path] = _GENERATED_EXCLUSIONS | _LEGITIMATE_LABEL_REFERENCES

# Dated report snapshots (e.g. docs/reports/tracer-friction-recon/2026-09-26/)
# are immutable point-in-time records that legitimately quote the retired
# doctrine directory as it stood on the recon date -- rewording them would
# falsify the historical record they exist to preserve (#5474). This mirrors
# the existing docs/reports/ exemption rather than inventing a new one:
# docs/development/reference/terminology-exemptions.md (Exempt Surface 5), and
# the immutable-historical-snapshot classification in ARCHIVE_PATH_PREFIXES
# (tests/architectural/test_no_dead_src_path_literals.py), pinned below by
# test_snapshot_exclusions_stay_archive_classified. The exemption is only safe
# while docfx never publishes docs/reports/ as live docs; that is asserted by
# test_docs_reports_exemption_is_not_published_as_live_docs below through the
# shared tests/_support/docfx_reports_guard.py implementation. Matching is a path-segment prefix anchored at the
# repo root (Path.is_relative_to), never a substring match.
# (This comment intentionally avoids the contiguous hyphenated literal so the
# guard does not flag itself.)
_SNAPSHOT_EXCLUDED_DIRS: tuple[Path, ...] = (Path("docs") / "reports",)


def _is_scanned(relative: Path) -> bool:
    """Return whether a repo-relative file path is part of the active scan."""
    return (
        relative not in _EXCLUDED_FILES
        and not any(relative.is_relative_to(excluded) for excluded in _SNAPSHOT_EXCLUDED_DIRS)
        and "__pycache__" not in relative.parts
        and relative.suffix not in _SKIPPED_SUFFIXES
    )


def _candidate_files(repo_root: Path) -> Iterator[Path]:
    for scan_path in ACTIVE_CODEBASE_PATHS:
        path = repo_root / scan_path
        if path.is_file():
            yield path
        elif path.is_dir():
            yield from (candidate for candidate in path.rglob("*") if candidate.is_file())


def _active_codebase_files(repo_root: Path) -> list[Path]:
    """Every file under ``repo_root`` that the legacy-path guard scans."""
    return sorted(path for path in _candidate_files(repo_root) if _is_scanned(path.relative_to(repo_root)))


def _find_violations(repo_root: Path) -> list[str]:
    """Repo-relative posix paths of scanned files quoting the removed path."""
    return [
        path.relative_to(repo_root).as_posix() for path in _active_codebase_files(repo_root) if LEGACY_DIRNAME in path.read_text(encoding="utf-8", errors="ignore")
    ]


def test_legacy_agent_profiles_directory_removed() -> None:
    """The old hyphenated doctrine directory must stay deleted."""
    assert not LEGACY_PATH.exists(), f"Legacy doctrine path reintroduced: {LEGACY_PATH.relative_to(REPO_ROOT)}"


def test_no_legacy_agent_profiles_path_literals_in_active_codebase() -> None:
    """The active codebase must not mention the removed hyphenated path."""
    violations = _find_violations(REPO_ROOT)
    assert violations == [], f"Found legacy {LEGACY_DIRNAME!r} path references in active codebase files: " + ", ".join(violations)


# --- Regression fixtures for #5474 -------------------------------------------
# The scan must skip dated docs/reports/ snapshots, but it must still flag every
# live surface, including sibling names that only share a string prefix with
# the snapshot tree.

_RETIRED_DOCTRINE_DIR = f"src/charter/offering/{LEGACY_DIRNAME}"
_SNAPSHOT_FIXTURES: tuple[str, ...] = (
    "docs/reports/tracer-friction-recon/2026-09-26/issue-coverage/group-E.md",
    "docs/reports/tracer-friction-recon/2026-09-26/issue-coverage/group-E.jsonl",
    "docs/reports/test-sanitation/2026-01-01/raw/head-census.json",
)
_LIVE_FIXTURES: tuple[str, ...] = (
    "docs/context/profile-guide.md",
    "docs/context/reports.md",
    "docs/reports.md",
    "docs/reportsXYZ/2026-09-26/summary.md",
    "src/charter/offering/profile_loader.py",
    "src/docs/reports/render.py",
    "tests/charter/test_profile_loader.py",
)


def _write_fixture(repo_root: Path, relative: str) -> None:
    path = repo_root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix == ".py":
        body = f'PROFILE_DIR = "{_RETIRED_DOCTRINE_DIR}/implementer.agent.yaml"\n'
    elif path.suffix in {".json", ".jsonl"}:
        body = f'{{"issue": 3664, "evidence": "{_RETIRED_DOCTRINE_DIR}/implementer.agent.yaml"}}\n'
    else:
        body = f"# Finding\n\nProfiles were loaded from `{_RETIRED_DOCTRINE_DIR}/` on the recon date.\n"
    path.write_text(body, encoding="utf-8")


def test_dated_report_snapshots_are_not_flagged(tmp_path: Path) -> None:
    """docs/reports/ holds immutable point-in-time snapshots quoting the old path."""
    for relative in _SNAPSHOT_FIXTURES:
        _write_fixture(tmp_path, relative)

    assert _find_violations(tmp_path) == []


def test_live_surfaces_and_prefix_near_misses_are_still_flagged(tmp_path: Path) -> None:
    """The snapshot exemption is a path-segment prefix anchored at the repo root."""
    for relative in (*_SNAPSHOT_FIXTURES, *_LIVE_FIXTURES):
        _write_fixture(tmp_path, relative)

    assert _find_violations(tmp_path) == sorted(_LIVE_FIXTURES)


def test_real_scan_covers_live_docs_but_not_report_snapshots() -> None:
    """Floor: the real scan stays non-vacuous and still reaches live docs/."""
    scanned = [path.relative_to(REPO_ROOT) for path in _active_codebase_files(REPO_ROOT)]
    reports_dir = Path("docs") / "reports"

    assert scanned, "the legacy-path guard scans no files at all"
    assert any(path.is_relative_to("src") for path in scanned)
    assert any(path.is_relative_to("docs") and not path.is_relative_to(reports_dir) for path in scanned), (
        "the legacy-path guard no longer scans any live docs/ page"
    )
    assert not any(path.is_relative_to(reports_dir) for path in scanned)


def test_snapshot_exclusions_stay_archive_classified() -> None:
    """The exemption is only honest while the archive classification agrees."""
    from tests.architectural.test_no_dead_src_path_literals import ARCHIVE_PATH_PREFIXES

    for excluded in _SNAPSHOT_EXCLUDED_DIRS:
        assert f"{excluded.as_posix()}/" in ARCHIVE_PATH_PREFIXES


def test_docs_reports_exemption_is_not_published_as_live_docs() -> None:
    """The docs/reports/ exemption is only safe while docfx never publishes it.

    Mirrors the equivalent guards in tests/contract/test_terminology_guards.py
    and tests/specify_cli/cli/test_decision_command_shape_consistency.py; all
    of them call the single shared implementation in
    tests/_support/docfx_reports_guard.py.
    """
    assert_docfx_does_not_publish_reports(DOCFX_CONFIG_PATH)
