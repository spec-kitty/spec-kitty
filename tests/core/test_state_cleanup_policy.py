"""Per-surface cleanup policy contract for the state registry (#5212).

Every ``STATE_SURFACES`` entry declares how it is retained and which command
cleans it. The invariants below make the committed tier unprunable by
construction: a tracked surface can never carry a pruning rule, and every
pruning rule names the one command that prunes.
"""

from __future__ import annotations

import dataclasses
import json
from typing import Any

import pytest

from specify_cli.state.contract import (
    CLEANUP_EVENT_LOGS_COMMAND,
    STATE_SURFACES,
    AuthorityClass,
    CleanupPolicy,
    GitClass,
    RetentionRule,
    StateFormat,
    StateRoot,
    StateSurface,
    get_surfaces_by_retention,
)

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_PRUNABLE_RULES = frozenset({RetentionRule.LEDGER_RETENTION, RetentionRule.REBUILDABLE})


def _prunable_tracked_violation(surface: StateSurface) -> bool:
    """Return True when a tracked surface carries a pruning retention rule."""
    return surface.git_class == GitClass.TRACKED and surface.cleanup_policy.retention in _PRUNABLE_RULES


def _surface_by_name(name: str) -> StateSurface:
    return next(s for s in STATE_SURFACES if s.name == name)


def test_every_surface_declares_a_cleanup_policy() -> None:
    for surface in STATE_SURFACES:
        assert isinstance(surface.cleanup_policy, CleanupPolicy), surface.name
        assert isinstance(surface.cleanup_policy.retention, RetentionRule), surface.name


def test_to_dict_emits_cleanup_policy() -> None:
    for surface in STATE_SURFACES:
        emitted = surface.to_dict()["cleanup_policy"]
        assert emitted == {
            "retention": surface.cleanup_policy.retention.value,
            "cleanup_command": surface.cleanup_policy.cleanup_command,
        }, surface.name
        assert json.loads(json.dumps(emitted)) == emitted


def test_policy_is_required() -> None:
    every_field_but_the_policy: dict[str, Any] = {
        "name": "synthetic",
        "path_pattern": ".kittify/synthetic.json",
        "root": StateRoot.PROJECT,
        "format": StateFormat.JSON,
        "authority": AuthorityClass.LOCAL_RUNTIME,
        "git_class": GitClass.IGNORED,
        "owner_module": "test",
        "creation_trigger": "test",
    }
    with pytest.raises(TypeError, match="cleanup_policy"):
        StateSurface(**every_field_but_the_policy)


def test_tracked_surfaces_are_never_prunable() -> None:
    violations = [s.name for s in STATE_SURFACES if _prunable_tracked_violation(s)]
    assert violations == []


def test_prunable_surfaces_are_gitignored() -> None:
    for surface in STATE_SURFACES:
        if surface.cleanup_policy.retention in _PRUNABLE_RULES:
            assert surface.git_class == GitClass.IGNORED, surface.name


def test_invariant_rejects_a_prunable_tracked_surface() -> None:
    canonical = _surface_by_name("canonical_status_log")
    assert not _prunable_tracked_violation(canonical)
    mutated = dataclasses.replace(
        canonical,
        cleanup_policy=CleanupPolicy(RetentionRule.LEDGER_RETENTION, CLEANUP_EVENT_LOGS_COMMAND),
    )
    assert _prunable_tracked_violation(mutated)


def test_local_tier_is_pinned() -> None:
    ledger = {s.name for s in get_surfaces_by_retention(RetentionRule.LEDGER_RETENTION)}
    assert ledger == {
        "runtime_run_snapshot",
        "runtime_run_event_log",
        "runtime_frozen_template",
        "glossary_fallback_events",
    }
    rebuildable = {s.name for s in get_surfaces_by_retention(RetentionRule.REBUILDABLE)}
    assert rebuildable == {"derived_mission_views"}
    # Operator ruling 2026-10-28: the Op index is never pruned (invocations list trusts a partial index).
    assert _surface_by_name("op_invocation_index").cleanup_policy == CleanupPolicy(RetentionRule.MANUAL)


def test_retention_surfaces_name_the_cleanup_command() -> None:
    assert CLEANUP_EVENT_LOGS_COMMAND == "spec-kitty doctor event-logs --apply"
    for surface in STATE_SURFACES:
        if surface.cleanup_policy.retention in _PRUNABLE_RULES:
            assert surface.cleanup_policy.cleanup_command == CLEANUP_EVENT_LOGS_COMMAND, surface.name


def test_owner_lifecycle_names_a_command() -> None:
    for surface in get_surfaces_by_retention(RetentionRule.OWNER_LIFECYCLE):
        assert surface.cleanup_policy.cleanup_command, surface.name


def test_deprecated_surfaces_are_retired() -> None:
    for surface in STATE_SURFACES:
        assert surface.deprecated == (surface.cleanup_policy.retention == RetentionRule.RETIRED), surface.name
