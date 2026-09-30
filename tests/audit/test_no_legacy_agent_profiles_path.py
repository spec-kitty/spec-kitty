"""Regression guards for the removed legacy doctrine profile path."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

pytestmark = [pytest.mark.integration]

REPO_ROOT = Path(__file__).resolve().parents[2]
LEGACY_DIRNAME = "agent" + "-" + "profiles"
LEGACY_PATH = REPO_ROOT / "src" / "charter" / "offering" / LEGACY_DIRNAME

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
_GENERATED_EXCLUSIONS: frozenset[Path] = frozenset({Path("docs") / "development" / "docs-retrieval-index.yaml"})

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


def _is_scanned(relative: Path) -> bool:
    """Return whether a repo-relative file path is part of the active scan."""
    return relative not in _EXCLUDED_FILES and "__pycache__" not in relative.parts and relative.suffix not in _SKIPPED_SUFFIXES


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
