"""Unit tests for specify_cli.compat.safety — safety registry and classify()."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from specify_cli.compat.safety import (
    SAFETY_REGISTRY,
    Safety,
    classify,
    register_safety,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


pytestmark = [pytest.mark.unit, pytest.mark.fast]

def _inv(command_path: tuple[str, ...], raw_args: tuple[str, ...] = ()) -> SimpleNamespace:
    """Build a minimal Invocation-like object for testing."""
    return SimpleNamespace(command_path=command_path, raw_args=raw_args)


# ---------------------------------------------------------------------------
# T014 / T015: Seed entries are SAFE
# ---------------------------------------------------------------------------


SEEDED_SAFE_PATHS = [
    ("upgrade",),
    ("init",),
    ("status",),
    ("doctor",),
    ("help",),
    ("version",),
    ("agent", "check-prerequisites"),
    ("agent", "mission", "branch-context"),
    ("agent", "mission", "check-prerequisites"),
    # NOTE: ("agent", "mission", "setup-plan") is intentionally absent —
    # it scaffolds plan.md and commits to the target branch (project mutation)
    # and must be UNSAFE under schema mismatch (FIX A, P2).
    ("agent", "context", "resolve"),
    ("agent", "tasks", "status"),
]


@pytest.mark.parametrize("path", SEEDED_SAFE_PATHS)
def test_seeded_entries_are_safe(path: tuple[str, ...]) -> None:
    """Every seed entry in SAFETY_REGISTRY classifies as SAFE."""
    result = classify(_inv(path))
    assert result == Safety.SAFE, f"Expected SAFE for {path!r}, got {result!r}"


def test_seeded_paths_present_in_registry() -> None:
    """All seeded paths are keys in SAFETY_REGISTRY."""
    for path in SEEDED_SAFE_PATHS:
        assert path in SAFETY_REGISTRY, f"{path!r} missing from SAFETY_REGISTRY"


# ---------------------------------------------------------------------------
# T015: Fail-closed — unregistered entries return UNSAFE
# ---------------------------------------------------------------------------


def test_unregistered_path_is_unsafe() -> None:
    """An unregistered command_path returns UNSAFE (fail-closed)."""
    result = classify(_inv(("not-a-real-command",)))
    assert result == Safety.UNSAFE


def test_unknown_nested_path_is_unsafe() -> None:
    """Unregistered nested paths are also UNSAFE."""
    result = classify(_inv(("agent", "unknown-subcommand")))
    assert result == Safety.UNSAFE


# ---------------------------------------------------------------------------
# T015: register_safety() — predicate is consulted
# ---------------------------------------------------------------------------


def test_register_safety_string_normalised() -> None:
    """A string command_path is normalised to a single-element tuple."""
    register_safety("__test_normalise_str__", None)
    assert ("__test_normalise_str__",) in SAFETY_REGISTRY
    # Cleanup
    del SAFETY_REGISTRY[("__test_normalise_str__",)]


def test_registered_predicate_is_consulted() -> None:
    """A registered SafetyPredicate is called by classify()."""
    called: list[bool] = []

    def always_safe(inv: object) -> Safety:
        called.append(True)
        return Safety.SAFE

    register_safety(("__test_predicate__",), always_safe)
    try:
        result = classify(_inv(("__test_predicate__",)))
        assert result == Safety.SAFE
        assert called == [True]
    finally:
        del SAFETY_REGISTRY[("__test_predicate__",)]


def test_predicate_that_raises_is_unsafe() -> None:
    """A predicate that raises an exception causes classify() to return UNSAFE."""

    def exploding_predicate(inv: object) -> Safety:
        raise RuntimeError("boom")

    register_safety(("__test_explode__",), exploding_predicate)
    try:
        result = classify(_inv(("__test_explode__",)))
        assert result == Safety.UNSAFE
    finally:
        del SAFETY_REGISTRY[("__test_explode__",)]


def test_register_safety_overrides_existing_entry() -> None:
    """register_safety() replaces a previously registered entry."""
    # First registration: always safe
    register_safety(("__test_override__",), None)
    assert classify(_inv(("__test_override__",))) == Safety.SAFE

    # Second registration: always unsafe
    register_safety(("__test_override__",), lambda inv: Safety.UNSAFE)
    assert classify(_inv(("__test_override__",))) == Safety.UNSAFE

    # Cleanup
    del SAFETY_REGISTRY[("__test_override__",)]


def test_register_safety_overrides_seeded_entry_and_restores() -> None:
    """register_safety() can temporarily override a seeded entry."""
    original = SAFETY_REGISTRY[("upgrade",)]
    try:
        register_safety(("upgrade",), lambda inv: Safety.UNSAFE)
        assert classify(_inv(("upgrade",))) == Safety.UNSAFE
    finally:
        SAFETY_REGISTRY[("upgrade",)] = original

    # Restored
    assert classify(_inv(("upgrade",))) == Safety.SAFE


# ---------------------------------------------------------------------------
# Safety enum sanity
# ---------------------------------------------------------------------------


def test_safety_enum_values() -> None:
    assert Safety.SAFE == "safe"
    assert Safety.UNSAFE == "unsafe"
    assert Safety.SAFE != Safety.UNSAFE


# ---------------------------------------------------------------------------
# Threading note (documented, not directly tested in unit tests)
# ---------------------------------------------------------------------------
# SAFETY_REGISTRY is a plain dict.  CPython's GIL guarantees atomic individual
# dict reads/writes.  Concurrent classify() and register_safety() calls from
# different threads are therefore safe without additional locking.
# A full concurrent stress test would require threading machinery not
# appropriate for a unit-test file; the policy is documented in safety.py.
