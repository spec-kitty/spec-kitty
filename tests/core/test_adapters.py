"""Unit tests for src/specify_cli/core/adapters.py (T010 / FR-004, FR-006).

Covers the PendingOriginConsumer registry contract:
- Safe default (no consumer registered): returns (False, False, None, meta)
- After registration: consumer is called with correct arguments
- Non-raising contract: consumer exceptions are caught and returned as error tuple
- Idempotent re-registration: re-registering the same qualified name replaces
  the existing entry
- State isolation: reset_origin_consumer() in teardown prevents state bleed
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from specify_cli.core.adapters import (
    PendingOriginConsumerNotRegisteredError,
    consume_pending_origin,
    register_pending_origin_consumer,
    reset_origin_consumer,
)

pytestmark = [pytest.mark.unit, pytest.mark.fast]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_DUMMY_META: dict[str, Any] = {"mission_slug": "test-mission", "mission_id": "01TESTULID1234567890ABCDEF"}


@pytest.fixture(autouse=True)
def _reset_consumer():
    """Ensure registry is clean before and after every test."""
    reset_origin_consumer()
    yield
    reset_origin_consumer()


# ---------------------------------------------------------------------------
# Safe default — no consumer registered
# ---------------------------------------------------------------------------


def test_no_consumer_returns_safe_default(tmp_path: Path) -> None:
    """consume_pending_origin returns (False, False, None, meta) when no consumer is registered."""
    meta = dict(_DUMMY_META)
    result = consume_pending_origin(tmp_path, tmp_path / "feature", meta)
    assert result == (False, False, None, meta)


def test_no_consumer_does_not_mutate_meta(tmp_path: Path) -> None:
    """consume_pending_origin with no consumer returns the original meta unchanged."""
    meta = {"key": "value", "nested": {"a": 1}}
    result = consume_pending_origin(tmp_path, tmp_path / "feature", meta)
    attempted, succeeded, error_msg, returned_meta = result
    assert not attempted
    assert not succeeded
    assert error_msg is None
    # The returned meta should be identical to the input (same object when no-op)
    assert returned_meta is meta


# ---------------------------------------------------------------------------
# Cold-miss fail-loud — staged binding present but no consumer registered
# ---------------------------------------------------------------------------


def _stage_pending_origin(repo_root: Path) -> Path:
    """Write a ``.kittify/pending-origin.yaml`` so a cold-miss is detectable."""
    kittify = repo_root / ".kittify"
    kittify.mkdir(parents=True, exist_ok=True)
    staged = kittify / "pending-origin.yaml"
    staged.write_text("provider: jira\nissue_id: '123'\nissue_key: ABC-123\n", encoding="utf-8")
    return staged


def test_cold_miss_with_staged_origin_raises(tmp_path: Path) -> None:
    """No consumer + a staged pending-origin file => fail loud, never silently drop."""
    staged = _stage_pending_origin(tmp_path)
    assert staged.is_file()

    with pytest.raises(PendingOriginConsumerNotRegisteredError) as exc_info:
        consume_pending_origin(tmp_path, tmp_path / "feature", dict(_DUMMY_META))

    # Diagnostic message must name the staged file and the missing import.
    message = str(exc_info.value)
    assert str(staged) in message
    assert "import specify_cli.tracker" in message


def test_registered_consumer_runs_even_with_staged_origin(tmp_path: Path) -> None:
    """When a consumer IS registered, the cold-miss guard never fires."""
    _stage_pending_origin(tmp_path)
    expected = (True, True, None, dict(_DUMMY_META))

    def _consumer(
        repo_root: Path,
        feature_dir: Path,
        meta: dict[str, Any],
    ) -> tuple[bool, bool, str | None, dict[str, Any]]:
        return expected

    register_pending_origin_consumer(_consumer)
    # Must NOT raise — registration short-circuits the cold-miss probe.
    result = consume_pending_origin(tmp_path, tmp_path / "feature", dict(_DUMMY_META))
    assert result == expected


# ---------------------------------------------------------------------------
# Consumer dispatch — registered consumer is called correctly
# ---------------------------------------------------------------------------


def test_registered_consumer_is_called(tmp_path: Path) -> None:
    """After registration consume_pending_origin calls the consumer with (repo_root, feature_dir, meta)."""
    calls: list[tuple[Path, Path, dict[str, Any]]] = []
    expected_result = (True, True, None, {"mission_slug": "bound", "origin": "jira"})

    def _consumer(
        repo_root: Path,
        feature_dir: Path,
        meta: dict[str, Any],
    ) -> tuple[bool, bool, str | None, dict[str, Any]]:
        calls.append((repo_root, feature_dir, meta))
        return expected_result

    register_pending_origin_consumer(_consumer)

    repo_root = tmp_path
    feature_dir = tmp_path / "kitty-specs" / "my-feature"
    meta = dict(_DUMMY_META)

    result = consume_pending_origin(repo_root, feature_dir, meta)

    assert len(calls) == 1
    assert calls[0] == (repo_root, feature_dir, meta)
    assert result == expected_result


def test_registered_consumer_result_propagated(tmp_path: Path) -> None:
    """Return value from the consumer is forwarded as-is."""
    expected = (True, False, "some error", {"extra": "data"})

    def _consumer(
        repo_root: Path,
        feature_dir: Path,
        meta: dict[str, Any],
    ) -> tuple[bool, bool, str | None, dict[str, Any]]:
        return expected

    register_pending_origin_consumer(_consumer)
    result = consume_pending_origin(tmp_path, tmp_path, {})
    assert result == expected


# ---------------------------------------------------------------------------
# Non-raising contract — consumer exceptions are caught
# ---------------------------------------------------------------------------


def test_consumer_exception_caught_and_returned(tmp_path: Path) -> None:
    """If the registered consumer raises, consume_pending_origin returns (True, False, str(exc), meta)."""

    def _bad_consumer(
        repo_root: Path,
        feature_dir: Path,
        meta: dict[str, Any],
    ) -> tuple[bool, bool, str | None, dict[str, Any]]:
        raise RuntimeError("tracker unavailable")

    register_pending_origin_consumer(_bad_consumer)
    meta = dict(_DUMMY_META)
    result = consume_pending_origin(tmp_path, tmp_path / "feature", meta)

    attempted, succeeded, error_msg, returned_meta = result
    assert attempted is True
    assert succeeded is False
    assert error_msg is not None
    assert "tracker unavailable" in error_msg
    # meta is unchanged
    assert returned_meta is meta


def test_consumer_exception_does_not_propagate(tmp_path: Path) -> None:
    """consume_pending_origin never raises even when the consumer raises."""

    def _raising_consumer(
        repo_root: Path,
        feature_dir: Path,
        meta: dict[str, Any],
    ) -> tuple[bool, bool, str | None, dict[str, Any]]:
        raise ValueError("critical internal error")

    register_pending_origin_consumer(_raising_consumer)
    # Must NOT raise — the non-raising contract is the whole point
    result = consume_pending_origin(tmp_path, tmp_path, {})
    assert result[1] is False  # succeeded is False


# ---------------------------------------------------------------------------
# Idempotent re-registration
# ---------------------------------------------------------------------------


def test_reregistration_replaces_existing_consumer(tmp_path: Path) -> None:
    """Re-registering a consumer with the same qualified name replaces the prior entry."""
    call_log: list[str] = []

    def _first_consumer(
        repo_root: Path,
        feature_dir: Path,
        meta: dict[str, Any],
    ) -> tuple[bool, bool, str | None, dict[str, Any]]:
        call_log.append("first")
        return (False, False, None, meta)

    def _second_consumer(
        repo_root: Path,
        feature_dir: Path,
        meta: dict[str, Any],
    ) -> tuple[bool, bool, str | None, dict[str, Any]]:
        call_log.append("second")
        return (True, True, None, meta)

    # Register first, then replace with second
    register_pending_origin_consumer(_first_consumer)
    register_pending_origin_consumer(_second_consumer)

    consume_pending_origin(tmp_path, tmp_path, {})

    # Only the second consumer should have run
    assert call_log == ["second"]


def test_second_registration_does_not_call_first(tmp_path: Path) -> None:
    """After re-registration, the old consumer is never called."""
    old_called = [False]

    def _old(
        repo_root: Path,
        feature_dir: Path,
        meta: dict[str, Any],
    ) -> tuple[bool, bool, str | None, dict[str, Any]]:
        old_called[0] = True
        return (False, False, None, meta)

    def _new(
        repo_root: Path,
        feature_dir: Path,
        meta: dict[str, Any],
    ) -> tuple[bool, bool, str | None, dict[str, Any]]:
        return (True, True, None, meta)

    register_pending_origin_consumer(_old)
    register_pending_origin_consumer(_new)
    consume_pending_origin(tmp_path, tmp_path, {})

    assert not old_called[0], "Old consumer must NOT be called after re-registration"


# ---------------------------------------------------------------------------
# reset_origin_consumer isolates state between tests
# ---------------------------------------------------------------------------


def test_reset_clears_registered_consumer(tmp_path: Path) -> None:
    """reset_origin_consumer() causes subsequent calls to return the safe default."""
    called = [False]

    def _consumer(
        repo_root: Path,
        feature_dir: Path,
        meta: dict[str, Any],
    ) -> tuple[bool, bool, str | None, dict[str, Any]]:
        called[0] = True
        return (True, True, None, meta)

    register_pending_origin_consumer(_consumer)
    reset_origin_consumer()

    meta = {}
    result = consume_pending_origin(tmp_path, tmp_path, meta)
    assert result == (False, False, None, meta)
    assert not called[0]


# ---------------------------------------------------------------------------
# Behavior-preservation: mission_creation.py no longer imports INTEGRATION set
# ---------------------------------------------------------------------------


def test_mission_creation_has_no_integration_imports() -> None:
    """mission_creation.py must contain zero import edges to the INTEGRATION set.

    This is the grep-equivalent check required by the WP acceptance criteria:
    no 'specify_cli.sync' or 'specify_cli.tracker' strings in mission_creation.py.
    """
    import ast

    from tests._support.mission_creation_source import FACADE, family_source

    # #5634: mission_creation.py was split into a module family; read all of it.
    assert FACADE.exists(), f"Source file not found: {FACADE}"
    source = family_source()

    # Simple text check — catches module-level, lazy, and TYPE_CHECKING imports
    integration_markers = [
        "specify_cli.sync",
        "specify_cli.tracker",
        "specify_cli.saas",
        "specify_cli.orchestrator_api",
        "specify_cli.saas_client",
    ]
    violations = [m for m in integration_markers if m in source]
    assert not violations, (
        f"Leak #1 still present in mission_creation.py — INTEGRATION imports found: {violations}"
    )

    # Additionally verify via AST that no import node targets the INTEGRATION set
    tree = ast.parse(source)
    bad_imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if any(alias.name.startswith(m) for m in integration_markers):
                    bad_imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if any(module.startswith(m) for m in integration_markers):
                bad_imports.append(module)

    assert not bad_imports, (
        f"AST scan: INTEGRATION imports remain in mission_creation.py: {bad_imports}"
    )
