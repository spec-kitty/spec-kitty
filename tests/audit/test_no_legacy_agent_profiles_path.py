"""Regression guards for the removed legacy doctrine profile path."""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = [pytest.mark.integration]

REPO_ROOT = Path(__file__).resolve().parents[2]
LEGACY_DIRNAME = "agent" + "-" + "profiles"
LEGACY_PATH = REPO_ROOT / "src" / "charter" / "offering" / LEGACY_DIRNAME
ACTIVE_CODEBASE_PATHS: tuple[Path, ...] = (
    REPO_ROOT / "src",
    REPO_ROOT / "tests",
    REPO_ROOT / "docs",
    REPO_ROOT / "architecture",
    REPO_ROOT / "research",
    REPO_ROOT / "README.md",
    REPO_ROOT / "CHANGELOG.md",
    REPO_ROOT / "AGENTS.md",
    REPO_ROOT / "pyproject.toml",
)


# Generated artifacts that MIRROR doc content rather than reference the removed
# doctrine directory. The Common Docs retrieval index stores heading-anchor
# slugs, so a legitimately-named heading such as "Pillar 1: Agent Profiles"
# yields a slug equal to LEGACY_DIRNAME -- a coincidental substring, NOT the
# deleted doctrine directory this guard targets. Excluding the generated index
# keeps the guard focused on genuine source references.
# (This comment intentionally avoids the contiguous hyphenated literal so the
# guard does not flag itself.)
_GENERATED_EXCLUSIONS: frozenset[Path] = frozenset(
    {REPO_ROOT / "docs" / "development" / "3-2-docs-retrieval-index.yaml"}
)

# Curated docs that name the live GitHub domain label literally called
# "agent" + "-" + "profiles" (the "Agent profile system" label in the issue
# tracker), which is a coincidental substring match -- NOT a reference to the
# deleted src/charter/offering/<hyphenated> doctrine directory this guard
# targets. The label name is fixed by GitHub and must appear verbatim in the
# label taxonomy, so excluding the doc keeps the guard focused on genuine
# source-path references.
# (This comment intentionally avoids the contiguous hyphenated literal so the
# guard does not flag itself.)
_LEGITIMATE_LABEL_REFERENCES: frozenset[Path] = frozenset(
    {REPO_ROOT / "docs" / "development" / "how-to" / "manage-issue-tracker.md"}
)

_EXCLUDED_FILES: frozenset[Path] = _GENERATED_EXCLUSIONS | _LEGITIMATE_LABEL_REFERENCES


def _active_codebase_files() -> list[Path]:
    files: list[Path] = []
    for path in ACTIVE_CODEBASE_PATHS:
        if not path.exists():
            continue
        if path.is_file():
            files.append(path)
            continue
        files.extend(
            candidate
            for candidate in path.rglob("*")
            if candidate.is_file()
            and candidate not in _EXCLUDED_FILES
            and "__pycache__" not in candidate.parts
            and candidate.suffix not in {".pyc", ".html", ".htm"}
        )
    return sorted(files)


def test_legacy_agent_profiles_directory_removed() -> None:
    """The old hyphenated doctrine directory must stay deleted."""
    assert not LEGACY_PATH.exists(), (
        "Legacy doctrine path reintroduced: "
        f"{LEGACY_PATH.relative_to(REPO_ROOT)}"
    )


def test_no_legacy_agent_profiles_path_literals_in_active_codebase() -> None:
    """The active codebase must not mention the removed hyphenated path."""
    violations = [
        path.relative_to(REPO_ROOT).as_posix()
        for path in _active_codebase_files()
        if LEGACY_DIRNAME in path.read_text(encoding="utf-8", errors="ignore")
    ]
    assert violations == [], (
        f"Found legacy {LEGACY_DIRNAME!r} path references in active codebase files: "
        + ", ".join(violations)
    )
