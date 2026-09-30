"""Architecture docs consistency checks.

Verifies structural integrity of the architecture corpus:
- Required directories and files are present.
- ADR files follow the naming convention.
- ADR files contain required sections.

Note: bare-relative link resolution is now owned by the unified gate in
:mod:`tests.docs.test_relative_link_fixer` (WP02/T027, FR-005).  The
hand-rolled link-resolution tests that previously lived here
(``test_architecture_relative_links_resolve`` and
``test_user_journey_persona_links_resolve``) have been retired — they
are superseded by ``check_dead_body_links`` operating across the full
``docs/`` tree.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit]

REPO_ROOT = Path(__file__).resolve().parents[2]
# Common Docs structural fold (Mission B): the architecture corpus moved under
# ``docs/`` — living design to ``docs/architecture/``, ADRs to ``docs/adr/<era>/``,
# audience personas to ``docs/context/audience/``, user journeys to
# ``docs/plans/user_journey/``.
ARCH_DIR = REPO_ROOT / "docs" / "architecture"
ADR_DIR = REPO_ROOT / "docs" / "adr"
AUDIENCE_DIR = REPO_ROOT / "docs" / "context" / "audience"
USER_JOURNEY_DIR = REPO_ROOT / "docs" / "plans" / "user_journey"

ADR_TRACKS = {
    "1.x": ADR_DIR / "1.x",
    "2.x": ADR_DIR / "2.x",
}

ADR_FILENAME_RE = re.compile(r"^\d{4}-\d{2}-\d{2}-\d+-.+\.md$")

REQUIRED_ARCH_PATHS: list[Path] = [
    ARCH_DIR / "README.md",
    ARCH_DIR / "adr-template.md",
    ADR_DIR,
    AUDIENCE_DIR / "index.md",
    AUDIENCE_DIR / "internal",
    AUDIENCE_DIR / "external",
    ADR_DIR / "1.x",
    ADR_DIR / "2.x",
    USER_JOURNEY_DIR,
]

# Each entry is a tuple of (human-readable label, compiled pattern).
# The pattern is searched in the ADR text with re.MULTILINE so it anchors
# to line boundaries, avoiding false positives on inline mentions.
_CONTEXT_SECTION_RE = re.compile(r"^##\s+Context(\s+and\s+Problem\s+Statement)?\s*$", re.MULTILINE)
_DECISION_SECTION_RE = re.compile(r"^##\s+Decision(\s+Outcome)?\s*$", re.MULTILINE)

REQUIRED_ADR_SECTION_CHECKS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("Context / Context and Problem Statement", _CONTEXT_SECTION_RE),
    ("Decision / Decision Outcome", _DECISION_SECTION_RE),
)


def _collect_adr_files() -> list[tuple[str, Path]]:
    """Return (track_label, path) for every ADR file in both tracks.

    ``README.md`` / ``index.md`` era-landing pages are excluded because they are
    not ADRs (the era index was normalized README.md -> index.md per #2227).
    """
    result: list[tuple[str, Path]] = []
    for track, adr_dir in ADR_TRACKS.items():
        if adr_dir.is_dir():
            for path in sorted(adr_dir.glob("*.md")):
                if path.name.lower() in ("readme.md", "index.md"):
                    continue
                result.append((track, path))
    return result


ADR_FILES = _collect_adr_files()
ADR_IDS = [f"{track}::{path.name}" for track, path in ADR_FILES]


# ---------------------------------------------------------------------------
# Structural tests
# ---------------------------------------------------------------------------


def test_architecture_required_paths_exist() -> None:
    missing = [str(p.relative_to(REPO_ROOT)) for p in REQUIRED_ARCH_PATHS if not p.exists()]
    assert not missing, f"Missing required architecture paths: {missing}"


def test_architecture_adr_directories_are_not_empty() -> None:
    empty = [
        str(adr_dir.relative_to(REPO_ROOT))
        for adr_dir in ADR_TRACKS.values()
        if adr_dir.is_dir() and not list(adr_dir.glob("*.md"))
    ]
    assert not empty, f"ADR directories are empty (expected at least one .md file): {empty}"


# ---------------------------------------------------------------------------
# ADR naming convention
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("track,adr_path", ADR_FILES, ids=ADR_IDS)
def test_adr_filename_follows_naming_convention(track: str, adr_path: Path) -> None:
    assert ADR_FILENAME_RE.match(adr_path.name), (
        f"ADR in track '{track}' does not follow naming convention "
        f"'YYYY-MM-DD-N-descriptive-title.md': {adr_path.name}"
    )


# ---------------------------------------------------------------------------
# ADR required sections
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("track,adr_path", ADR_FILES, ids=ADR_IDS)
def test_adr_contains_required_sections(track: str, adr_path: Path) -> None:
    if not REQUIRED_ADR_SECTION_CHECKS:
        pytest.skip("No required section checks defined")
    text = adr_path.read_text(encoding="utf-8")
    missing_sections = [
        label
        for label, pattern in REQUIRED_ADR_SECTION_CHECKS
        if not pattern.search(text)
    ]
    assert not missing_sections, (
        f"ADR '{adr_path.relative_to(REPO_ROOT)}' (track '{track}') is missing "
        f"required sections: {missing_sections}"
    )


