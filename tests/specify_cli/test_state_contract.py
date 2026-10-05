"""Unit tests for the state contract module."""

import json
import os
from dataclasses import FrozenInstanceError
from pathlib import PurePosixPath

import pytest

from specify_cli.state.contract import (
    STATE_SURFACES,
    AuthorityClass,
    GitClass,
    StateFormat,
    StateRoot,
    get_runtime_gitignore_entries,
    get_surfaces_by_authority,
    get_surfaces_by_git_class,
    get_surfaces_by_root,
    is_primary_owned_path,
    primary_owned_paths,
)


# ---------------------------------------------------------------------------
# Uniqueness and completeness
# ---------------------------------------------------------------------------


pytestmark = [pytest.mark.unit, pytest.mark.fast]

def test_surface_names_unique():
    """Every surface must have a unique name."""
    names = [s.name for s in STATE_SURFACES]
    assert len(names) == len(set(names)), f"Duplicate names: {[n for n in names if names.count(n) > 1]}"


def test_minimum_surface_count():
    """The registry must contain at least 30 surfaces from the audit."""
    assert len(STATE_SURFACES) >= 30, f"Only {len(STATE_SURFACES)} surfaces registered"


def test_path_patterns_unique():
    """Every surface must have a unique path_pattern."""
    patterns = [s.path_pattern for s in STATE_SURFACES]
    assert len(patterns) == len(set(patterns)), (
        f"Duplicate patterns: {[p for p in patterns if patterns.count(p) > 1]}"
    )


# ---------------------------------------------------------------------------
# Enum coverage
# ---------------------------------------------------------------------------


def test_all_state_roots_used():
    """At least one surface per StateRoot value."""
    roots_used = {s.root for s in STATE_SURFACES}
    for root in StateRoot:
        assert root in roots_used, f"StateRoot.{root.name} has no surfaces"


def test_all_git_classes_used():
    """At least one surface per GitClass value (except retired classes)."""
    # INSIDE_REPO_NOT_IGNORED was retired in feature 054: all surfaces using it
    # were either removed (active_mission_marker) or reclassified (charter).
    retired_classes = {GitClass.INSIDE_REPO_NOT_IGNORED}
    classes_used = {s.git_class for s in STATE_SURFACES}
    for gc in GitClass:
        if gc in retired_classes:
            continue
        assert gc in classes_used, f"GitClass.{gc.name} has no surfaces"


def test_all_authority_classes_used():
    """At least one surface per AuthorityClass value."""
    authorities_used = {s.authority for s in STATE_SURFACES}
    for auth in AuthorityClass:
        assert auth in authorities_used, f"AuthorityClass.{auth.name} has no surfaces"


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------


def test_to_dict_serializable():
    """to_dict() must produce a JSON-serializable dict with correct keys."""
    for s in STATE_SURFACES:
        d = s.to_dict()
        # Must not raise
        json.dumps(d)
        # Spot-check enum serialization
        assert d["name"] == s.name
        assert d["root"] == s.root.value
        assert d["format"] == s.format.value
        assert d["authority"] == s.authority.value
        assert d["git_class"] == s.git_class.value
        assert d["primary_owned"] is s.primary_owned
        assert set(d) == {
            "name",
            "path_pattern",
            "root",
            "format",
            "authority",
            "git_class",
            "owner_module",
            "creation_trigger",
            "deprecated",
            "atomic_write",
            "notes",
            "primary_owned",
        }


def test_enum_values_are_strings():
    """str-based enums must serialize to their string values directly."""
    for root in StateRoot:
        assert isinstance(root.value, str)
    for auth in AuthorityClass:
        assert isinstance(auth.value, str)
    for gc in GitClass:
        assert isinstance(gc.value, str)
    for fmt in StateFormat:
        assert isinstance(fmt.value, str)


# ---------------------------------------------------------------------------
# Frozen dataclass
# ---------------------------------------------------------------------------


def test_frozen():
    """StateSurface instances are immutable."""
    s = STATE_SURFACES[0]
    with pytest.raises(FrozenInstanceError):
        s.name = "modified"  # type: ignore[misc]


def test_frozen_cannot_add_attribute():
    """Cannot add new attributes to frozen dataclass instances."""
    s = STATE_SURFACES[0]
    with pytest.raises(FrozenInstanceError):
        s.extra = "value"  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Helper: get_surfaces_by_root
# ---------------------------------------------------------------------------


def test_get_surfaces_by_root_project():
    """PROJECT root returns non-empty list with correct root values."""
    project = get_surfaces_by_root(StateRoot.PROJECT)
    assert len(project) > 0
    assert all(s.root == StateRoot.PROJECT for s in project)


def test_get_surfaces_by_root_feature():
    """FEATURE root returns non-empty list with correct root values."""
    feature = get_surfaces_by_root(StateRoot.FEATURE)
    assert len(feature) > 0
    assert all(s.root == StateRoot.FEATURE for s in feature)


def test_get_surfaces_by_root_all_roots_sum():
    """Surfaces from all roots sum to total count."""
    total = sum(len(get_surfaces_by_root(r)) for r in StateRoot)
    assert total == len(STATE_SURFACES)


def test_get_surfaces_by_root_returns_new_list():
    """Helper returns a new list, not a view."""
    a = get_surfaces_by_root(StateRoot.PROJECT)
    b = get_surfaces_by_root(StateRoot.PROJECT)
    assert a == b
    assert a is not b


# ---------------------------------------------------------------------------
# Helper: get_surfaces_by_git_class
# ---------------------------------------------------------------------------


def test_get_surfaces_by_git_class_tracked():
    """TRACKED git class returns non-empty list."""
    tracked = get_surfaces_by_git_class(GitClass.TRACKED)
    assert len(tracked) > 0
    assert all(s.git_class == GitClass.TRACKED for s in tracked)


def test_get_surfaces_by_git_class_ignored():
    """IGNORED git class returns non-empty list."""
    ignored = get_surfaces_by_git_class(GitClass.IGNORED)
    assert len(ignored) > 0
    assert all(s.git_class == GitClass.IGNORED for s in ignored)


# ---------------------------------------------------------------------------
# Helper: get_surfaces_by_authority
# ---------------------------------------------------------------------------


def test_get_surfaces_by_authority_authoritative():
    """AUTHORITATIVE authority returns non-empty list."""
    auth = get_surfaces_by_authority(AuthorityClass.AUTHORITATIVE)
    assert len(auth) > 0
    assert all(s.authority == AuthorityClass.AUTHORITATIVE for s in auth)


def test_get_surfaces_by_authority_derived():
    """DERIVED authority returns non-empty list."""
    derived = get_surfaces_by_authority(AuthorityClass.DERIVED)
    assert len(derived) > 0
    assert all(s.authority == AuthorityClass.DERIVED for s in derived)


# ---------------------------------------------------------------------------
# Helper: get_runtime_gitignore_entries
# ---------------------------------------------------------------------------


def test_runtime_gitignore_entries_exact():
    """Gitignore entries must contain all expected canonical patterns."""
    entries = get_runtime_gitignore_entries()
    expected = [
        ".agents/skills/",
        ".kittify/charter/context-state.json",
        ".kittify/derived/",
        ".kittify/dossiers/",
        ".kittify/encoding-provenance/",
        ".kittify/events/",
        ".kittify/lint-report.json",
        ".kittify/logs/",
        ".kittify/merge-state.json",
        ".kittify/migrations/",
        ".kittify/missions/__pycache__/",
        ".kittify/runtime/",
        ".kittify/skills-manifest.json",
        ".kittify/sync-state.json",
        ".kittify/workspaces/",
        ".worktrees/",
        "kitty-ops/ops-index.jsonl",
        # FIX-M2-05: FEATURE-rooted leg -- the dossier SNAPSHOT is nested
        # inside each mission's own kitty-specs/<feature>/ tree, a different
        # physical location than the PROJECT-rooted ".kittify/dossiers/"
        # above (that entry's sole remaining backing surface is
        # dossier_parity_baseline, a genuinely project-rooted sibling).
        "kitty-specs/*/.kittify/dossiers/",
    ]
    assert entries == expected


def test_missions_pycache_not_collapsed():
    """Regression: missions/__pycache__/ must NOT be collapsed to missions/.

    The missions/ directory contains mission configs and templates that are
    resolved at runtime. Only the __pycache__/ subdirectory is disposable.
    """
    entries = get_runtime_gitignore_entries()
    assert ".kittify/missions/__pycache__/" in entries, (
        "missions/__pycache__/ must appear as a specific entry"
    )
    assert ".kittify/missions/" not in entries, (
        "missions/ is too broad -- only missions/__pycache__/ should be ignored"
    )


def test_runtime_gitignore_entries_no_placeholders():
    """Gitignore entries must not contain unsubstituted template tokens.

    ``<...>`` template placeholders must never leak through -- every entry
    must be directly consumable by ``.gitignore``. A literal ``*`` IS valid
    gitignore syntax and is expected in exactly two shapes: the pre-existing
    ``__pycache__/`` collapse, and (FIX-M2-05) the ``kitty-specs/*/`` prefix
    every FEATURE-rooted entry carries -- the single-``*`` mission-glob
    substituting ``<feature>`` (see :func:`get_runtime_gitignore_entries`'s
    FEATURE-rooted leg), not an unsubstituted placeholder.
    """
    entries = get_runtime_gitignore_entries()
    for entry in entries:
        assert "<" not in entry, f"Placeholder in gitignore entry: {entry}"
        assert (
            "*" not in entry
            or entry.endswith("__pycache__/")
            or entry.startswith("kitty-specs/*/")
        ), f"Unexpected wildcard in gitignore entry: {entry}"


def test_runtime_gitignore_entries_sorted():
    """Gitignore entries must be sorted."""
    entries = get_runtime_gitignore_entries()
    assert entries == sorted(entries)


def test_runtime_gitignore_entries_only_project_ignored():
    """Every gitignore entry must trace back to an IGNORED surface.

    PROJECT-rooted entries trace to a PROJECT/IGNORED surface directly.
    FEATURE-rooted entries (FIX-M2-05: the ``kitty-specs/*/`` prefix
    substitutes ``<feature>``) trace to a FEATURE/IGNORED surface whose
    ``kitty-specs/<feature>/`` prefix is stripped before comparing.
    """
    entries = get_runtime_gitignore_entries()
    for entry in entries:
        if entry.startswith("kitty-specs/*/"):
            rel_entry = entry.removeprefix("kitty-specs/*/")
            matching = [
                s
                for s in STATE_SURFACES
                if s.root == StateRoot.FEATURE
                and s.git_class == GitClass.IGNORED
                and s.path_pattern.removeprefix("kitty-specs/<feature>/").startswith(
                    rel_entry.rstrip("/")
                )
            ]
            assert len(matching) >= 1, f"Gitignore entry {entry!r} has no backing FEATURE surface"
            continue
        # Entry is either a concrete path or a directory-level collapse
        # Either way, at least one registry surface must match
        if entry.endswith("/"):
            # Directory pattern: at least one surface path_pattern must start with this prefix
            matching = [
                s
                for s in STATE_SURFACES
                if s.root == StateRoot.PROJECT
                and s.git_class == GitClass.IGNORED
                and s.path_pattern.startswith(entry.rstrip("/"))
            ]
        else:
            matching = [
                s
                for s in STATE_SURFACES
                if s.root == StateRoot.PROJECT
                and s.git_class == GitClass.IGNORED
                and s.path_pattern == entry
            ]
        assert len(matching) >= 1, f"Gitignore entry {entry!r} has no backing surface"


# ---------------------------------------------------------------------------
# Deprecated surfaces
# ---------------------------------------------------------------------------


def test_deprecated_surfaces():
    """At least one deprecated surface exists."""
    deprecated = [s for s in STATE_SURFACES if s.deprecated]
    assert len(deprecated) >= 1


def test_deprecated_authority_class():
    """Deprecated surfaces use AuthorityClass.DEPRECATED."""
    deprecated = [s for s in STATE_SURFACES if s.deprecated]
    for s in deprecated:
        assert s.authority == AuthorityClass.DEPRECATED, (
            f"{s.name} is deprecated but authority is {s.authority}"
        )


# ---------------------------------------------------------------------------
# Charter Git policy (feature 054)
# ---------------------------------------------------------------------------


def test_charter_references_surface_retired():
    """consolidate-charter-bundle (WP07): charter_references is RETIRED.

    The four legacy IGNORED/DERIVED bundle surfaces (charter_references,
    charter_governance, charter_directives, charter_sync_metadata) are
    folded into the single git-tracked ``charter_yaml`` surface -- see
    ``test_charter_yaml_is_authoritative_tracked`` below.
    """
    names = {s.name for s in STATE_SURFACES}
    assert "charter_references" not in names
    assert "charter_governance" not in names
    assert "charter_directives" not in names
    assert "charter_sync_metadata" not in names


def test_charter_yaml_is_authoritative_tracked():
    """charter_yaml must be AUTHORITATIVE / TRACKED (data-model.md Landmine 1).

    Replaces the four retired IGNORED/DERIVED bundle surfaces: governance
    and directives are hand-authored sections, catalog is a DERIVED-but-
    committed projection -- all inside one git-tracked file.
    """
    surface = next(s for s in STATE_SURFACES if s.name == "charter_yaml")
    assert surface.authority == AuthorityClass.AUTHORITATIVE, (
        f"Expected AUTHORITATIVE, got {surface.authority}"
    )
    assert surface.git_class == GitClass.TRACKED, (
        f"Expected TRACKED, got {surface.git_class}"
    )
    assert surface.path_pattern == ".kittify/charter/charter.yaml"


def test_charter_library_is_authoritative_tracked():
    """charter_library must be AUTHORITATIVE / TRACKED (shared team knowledge)."""
    surface = next(s for s in STATE_SURFACES if s.name == "charter_library")
    assert surface.authority == AuthorityClass.AUTHORITATIVE, (
        f"Expected AUTHORITATIVE, got {surface.authority}"
    )
    assert surface.git_class == GitClass.TRACKED, (
        f"Expected TRACKED, got {surface.git_class}"
    )


def test_charter_answers_is_authoritative_tracked():
    """charter_interview_answers must be AUTHORITATIVE / TRACKED (shared team knowledge)."""
    surface = next(s for s in STATE_SURFACES if s.name == "charter_interview_answers")
    assert surface.authority == AuthorityClass.AUTHORITATIVE, (
        f"Expected AUTHORITATIVE, got {surface.authority}"
    )
    assert surface.git_class == GitClass.TRACKED, (
        f"Expected TRACKED, got {surface.git_class}"
    )


def test_no_deferred_notes_remain():
    """No state surface notes field should contain the word 'deferred'."""
    deferred = [s for s in STATE_SURFACES if "deferred" in s.notes.lower()]
    assert len(deferred) == 0, (
        f"Found surfaces with deferred notes: {[s.name for s in deferred]}"
    )


# ---------------------------------------------------------------------------
# Section coverage (spot checks)
# ---------------------------------------------------------------------------


def test_section_a_project_surfaces_present():
    """Key Section A surfaces exist."""
    names = {s.name for s in STATE_SURFACES}
    expected = {
        "project_config",
        "project_metadata",
        "workspace_context",
        "merge_resume_state",
        "runtime_feature_index",
        "runtime_run_snapshot",
        "runtime_run_event_log",
        "runtime_frozen_template",
        "glossary_fallback_events",
        "dossier_snapshot",
        "dossier_parity_baseline",
    }
    missing = expected - names
    assert not missing, f"Missing Section A surfaces: {missing}"


def test_section_b_charter_surfaces_present():
    """Key Section B surfaces exist."""
    names = {s.name for s in STATE_SURFACES}
    expected = {
        "charter_source",
        "charter_interview_answers",
        "charter_library",
        "charter_yaml",
        "charter_context_state",
    }
    missing = expected - names
    assert not missing, f"Missing Section B surfaces: {missing}"


def test_section_c_feature_surfaces_present():
    """Key Section C surfaces exist."""
    names = {s.name for s in STATE_SURFACES}
    expected = {
        "feature_metadata",
        "canonical_status_log",
        "canonical_status_snapshot",
        "wp_prompt_frontmatter",
        "wp_activity_log",
        "tasks_status_block",
    }
    missing = expected - names
    assert not missing, f"Missing Section C surfaces: {missing}"


def test_section_d_git_internal_present():
    """Section D git-internal surface exists."""
    names = {s.name for s in STATE_SURFACES}
    assert "review_feedback_artifact" in names


def test_section_e_sync_surfaces_present():
    """Key Section E surfaces exist."""
    names = {s.name for s in STATE_SURFACES}
    expected = {
        "sync_config",
        "sync_credentials",
        "lamport_clock",
        "active_queue_scope",
        "legacy_queue",
        "scoped_queue",
        "tracker_cache",
    }
    missing = expected - names
    assert not missing, f"Missing Section E surfaces: {missing}"


def test_credential_lock_surface_is_removed():
    """The credential store locks its own file, not a lockfile sidecar."""
    assert all(surface.name != "credential_lock" for surface in STATE_SURFACES)
    assert all(
        surface.path_pattern != "~/.spec-kitty/credentials.lock"
        for surface in STATE_SURFACES
    )


def test_section_e_historical_sync_rows_are_fully_tombstoned():
    """Historical sync rows are deprecated and excluded from live authorities."""
    surfaces_by_name = {s.name: s for s in STATE_SURFACES}
    historical_names = {
        "lamport_clock",
        "active_queue_scope",
        "sync_daemon_control",
        "legacy_queue",
        "scoped_queue",
        "project_sync_store",
        "project_sync_egress_lock",
        "project_sync_layout_generation",
        "project_sync_layout_generation_lock",
        "project_sync_layout_generation_marker",
        "project_sync_migration_reports",
    }
    for name in historical_names:
        surface = surfaces_by_name[name]
        assert surface.authority is AuthorityClass.DEPRECATED
        assert surface.deprecated is True
        assert surface.owner_module == "legacy"
        assert surface.creation_trigger == "historical"
        assert surface.to_dict()["authority"] == AuthorityClass.DEPRECATED.value
        assert surface.to_dict()["deprecated"] is True

    live_authorities = {
        AuthorityClass.AUTHORITATIVE,
        AuthorityClass.LOCAL_RUNTIME,
    }
    authority_names = {
        authority: {surface.name for surface in get_surfaces_by_authority(authority)}
        for authority in live_authorities
    }
    assert all(
        name not in names
        for names in authority_names.values()
        for name in historical_names
    )
    tracker_cache = surfaces_by_name["tracker_cache"]
    assert tracker_cache.authority is AuthorityClass.AUTHORITATIVE
    assert tracker_cache.deprecated is False
    assert tracker_cache.name in authority_names[AuthorityClass.AUTHORITATIVE]


def test_section_f_global_runtime_present():
    """Key Section F surfaces exist."""
    names = {s.name for s in STATE_SURFACES}
    expected = {
        "runtime_version_stamp",
        "runtime_update_lock",
        "runtime_staging_dirs",
    }
    missing = expected - names
    assert not missing, f"Missing Section F surfaces: {missing}"


def test_section_g_legacy_present():
    """All Section G legacy surfaces exist."""
    names = {s.name for s in STATE_SURFACES}
    expected = {
        "legacy_session_json",
        "legacy_lamport_clock",
        "legacy_mission_sessions",
        "legacy_reset_backups",
    }
    missing = expected - names
    assert not missing, f"Missing Section G surfaces: {missing}"


# ---------------------------------------------------------------------------
# Primary-owned declaration (#5457)
# ---------------------------------------------------------------------------

_METADATA = ".kittify/metadata.yaml"


@pytest.mark.parametrize(
    "path",
    [_METADATA, "./" + _METADATA, ".kittify\\metadata.yaml", ".\\.kittify\\metadata.yaml", PurePosixPath(_METADATA)],
)
def test_metadata_forms_are_primary_owned(path: str | os.PathLike[str]) -> None:
    assert is_primary_owned_path(path) is True


@pytest.mark.parametrize(
    "path",
    [
        "metadata.yaml",
        "sub/.kittify/metadata.yaml",
        "kitty-specs/x/.kittify/metadata.yaml",
        ".kittify/metadata.yml",
        ".kittify/config.yaml",
        ".gitattributes",
        ".gitignore",
        ".kittify/charter/charter.md",
        "/repo/.kittify/metadata.yaml",
        "C:/repo/.kittify/metadata.yaml",
        "",
    ],
)
def test_other_paths_are_not_primary_owned(path: str) -> None:
    assert is_primary_owned_path(path) is False


def test_primary_owned_surfaces_are_tracked_project_literals() -> None:
    owned = [s for s in STATE_SURFACES if s.primary_owned]
    assert owned
    for surface in owned:
        assert surface.git_class == GitClass.TRACKED
        assert surface.root == StateRoot.PROJECT
        assert not any(ch in surface.path_pattern for ch in "<*?")


def test_primary_owned_set_is_pinned() -> None:
    # Deliberate pin: adding a primary-owned surface must be a reviewed decision.
    assert primary_owned_paths() == frozenset({_METADATA})
