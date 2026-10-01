"""Shared path constants for Spec Kitty repository layout."""

from __future__ import annotations

KITTY_SPECS_DIR = "kitty-specs"
KITTIFY_DIR = ".kittify"
WORKTREES_DIR = ".worktrees"

# Canonical filename for retrospective records — the single source of truth for
# the name "retrospective.yaml" (FR-010 / Sonar S1192).  All path-composition
# sites MUST import and use this constant; bare string literals are forbidden.
RETROSPECTIVE_FILENAME = "retrospective.yaml"

# Canonical filename for the repo-global charter-lint decay report, written to
# ``<repo_root>/.kittify/lint-report.json`` by the lint engine and read back by
# the dossier stager.  All path-composition sites MUST
# use ``core.paths.lint_report_path`` / this constant; bare literals are
# forbidden (#2628 SSOT fold).
LINT_REPORT_FILENAME = "lint-report.json"

# Canonical filename for a bulk-edit mission's occurrence map, written to
# ``kitty-specs/<mission>/occurrence_map.yaml`` (DIRECTIVE_035).  The semantic
# owner is ``specify_cli.bulk_edit.occurrence_map``; this is the shared path
# literal (Sonar S1192) so the two kitty-specs lane guards below express the
# occurrence-map exception once instead of duplicating the string.
OCCURRENCE_MAP_FILENAME = "occurrence_map.yaml"


def is_occurrence_map_path(path: str) -> bool:
    """Return True when *path* is a mission occurrence map (the #2980 exception SSOT).

    The single authority both ``kitty-specs/`` lane guards consult — the
    pre-commit ownership guard (``policy.commit_guard``) and the ``move-task``
    lane-hygiene guard (``cli.commands.agent.tasks_shared``) — to permit a
    bulk-edit mission's own ``kitty-specs/<mission>/occurrence_map.yaml`` on an
    implementation lane. DIRECTIVE_035 requires the map be kept current *as the
    sweep proceeds*, which means the implementing lane writes it; without this
    single exception the commit guard warned while ``move-task`` blocked, so the
    map could not be kept current without a manual unwind (#2980).

    Matches exactly ``kitty-specs/<mission>/occurrence_map.yaml`` — the map lives
    directly under the mission directory (three path segments). Every other
    ``kitty-specs/`` path stays governed.

    The match is filename-scoped, not mission-scoped: *any* mission's
    occurrence map passes, and that widening is identical across both guards
    (the #2980 symmetry goal — the guards must never disagree). Tightening it
    to the lane's own mission is deliberately deferred until cross-mission
    occurrence-map writes become a real vector (#3559).
    """
    if not path.startswith(f"{KITTY_SPECS_DIR}/"):
        return False
    if not path.endswith(f"/{OCCURRENCE_MAP_FILENAME}"):
        return False
    return path.count("/") == 2

# Named scalar aliases for individual built-in mission-type identifiers, used at
# the CLI comparison sites.  The canonical *roster* (the full built-in set) is
# ``charter.offering.missions.mission_type_repository.builtin_mission_type_ids`` (#2669) —
# these are per-type named constants for readability, not a competing roster.
# All callers MUST import a name from here rather than embedding inline literals.
MISSION_TYPE_SOFTWARE_DEV = "software-dev"
MISSION_TYPE_DOCUMENTATION = "documentation"
MISSION_TYPE_RESEARCH = "research"

__all__ = [
    "KITTY_SPECS_DIR",
    "KITTIFY_DIR",
    "RETROSPECTIVE_FILENAME",
    "LINT_REPORT_FILENAME",
    "OCCURRENCE_MAP_FILENAME",
    "WORKTREES_DIR",
    "MISSION_TYPE_SOFTWARE_DEV",
    "MISSION_TYPE_DOCUMENTATION",
    "MISSION_TYPE_RESEARCH",
    "is_occurrence_map_path",
]
