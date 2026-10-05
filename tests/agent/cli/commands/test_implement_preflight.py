"""Tests for the charter preflight hook in ``spec-kitty implement`` (T024 / T026).

Verifies the FR-006 caller contract: the preflight gate runs **before**
any worktree allocation or ``.kittify/`` modification. On failure we
exit 1 and ``create_lane_workspace`` is never invoked.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from unittest.mock import patch

import pytest
import typer

from specify_cli.charter_runtime.preflight.ambient_warning import _reset_surfaced_for_testing
from specify_cli.charter_runtime.preflight.result import CharterPreflightResult


pytestmark = pytest.mark.fast


@pytest.fixture(autouse=True)
def _fresh_charter_warning() -> Iterator[None]:
    """The charter preflight warning is shown once per process; re-arm it around each test.

    Any earlier test in the same xdist worker that runs ``implement`` in-process (the
    characterization, phase and reachability suites, among others) consumes the warning that
    ``test_hook_does_not_abort_on_fully_absent_charter_for_implement`` asserts. The outcome then
    depends on how ``--dist loadfile`` schedules files; re-arming here removes that dependency.
    """
    _reset_surfaced_for_testing()
    yield
    _reset_surfaced_for_testing()


def _pass_result() -> CharterPreflightResult:
    return CharterPreflightResult(
        passed=True,
        checks=[],
        auto_refresh_applied=False,
        auto_refresh_actions=[],
        blocked_reason=None,
    )


def _fail_result(reason: str = "synthesized DRG missing; run: spec-kitty charter synthesize") -> CharterPreflightResult:
    return CharterPreflightResult(
        passed=False,
        checks=[],
        auto_refresh_applied=False,
        auto_refresh_actions=[],
        blocked_reason=reason,
    )


def _call_implement_unwrapped(**kwargs):
    """Invoke ``implement`` bypassing ``@_json_safe_output`` and ``@require_main_repo``."""
    from specify_cli.cli.commands import implement as implement_mod

    fn = implement_mod.implement
    # Two decorators stacked → two ``__wrapped__`` hops.
    while hasattr(fn, "__wrapped__"):
        fn = fn.__wrapped__  # type: ignore[attr-defined]
    return fn(**kwargs)


def test_hook_does_not_abort_on_fully_absent_charter_for_implement(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """#3498: a fully-absent charter (fresh project) must be advisory for implement too.

    Uses the REAL runner (no mocking of ``run_charter_preflight``) so this
    exercises the actual ``allow_missing_charter`` wiring the hook must
    pass through.
    """
    from specify_cli.charter_runtime.preflight import hook as hook_mod

    result = hook_mod.run_preflight_or_abort(tmp_path, consumer="implement")

    assert result.passed is True
    assert result.blocked_reason is None
    assert "project charter is not initialized" in capsys.readouterr().err


def test_hook_does_not_abort_on_legacy_charter_bundle_for_implement(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """#3498/#2831: a legacy ``charter.md``-only bundle must also be advisory for implement."""
    from specify_cli.charter_runtime.preflight import hook as hook_mod

    charter_dir = tmp_path / ".kittify" / "charter"
    charter_dir.mkdir(parents=True)
    (charter_dir / "charter.md").write_text("# Charter\n", encoding="utf-8")

    result = hook_mod.run_preflight_or_abort(tmp_path, consumer="implement")

    assert result.passed is True
    assert result.blocked_reason is None
    warning = capsys.readouterr().err
    assert "charter.md-only bundle" in warning
    assert "spec-kitty charter generate --no-from-interview" in warning


def test_implement_still_blocks_and_no_worktree_alloc_on_invalid_charter_yaml(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Non-regression: genuinely broken charter state still blocks implement.

    Uses the REAL runner end-to-end through the ``implement`` command (not a
    mocked ``run_charter_preflight``) and confirms ``create_lane_workspace``
    is never invoked -- the still-blocking case must remain untouched.
    """
    from specify_cli.cli.commands import implement as implement_mod
    from specify_cli.cli.commands import implement_phases

    monkeypatch.setattr(implement_mod, "find_repo_root", lambda: tmp_path)

    charter_dir = tmp_path / ".kittify" / "charter"
    charter_dir.mkdir(parents=True)
    (charter_dir / "charter.yaml").write_text("not: [valid: yaml: at: all", encoding="utf-8")

    create_calls: list = []

    def _create(*args, **kwargs):  # pragma: no cover — assertion is on non-call
        create_calls.append((args, kwargs))
        raise AssertionError("create_lane_workspace must not be invoked when preflight fails")

    monkeypatch.setattr(implement_phases, "create_lane_workspace", _create)

    with pytest.raises(typer.Exit) as excinfo:
        _call_implement_unwrapped(
            wp_id="WP01",
            mission="042-test-feature",
            auto_commit=None,
            json_output=False,
            recover=False,
            base=None,
            acknowledge_not_bulk_edit=False,
            actor=None,
        )

    assert excinfo.value.exit_code == 1
    assert create_calls == []
    captured = capsys.readouterr()
    assert "charter_source" in captured.err


def test_implement_aborts_before_worktree_allocation_on_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Preflight failure exits 1 BEFORE ``create_lane_workspace`` is called."""
    from specify_cli.cli.commands import implement as implement_mod
    from specify_cli.cli.commands import implement_phases

    monkeypatch.setattr(implement_mod, "find_repo_root", lambda: tmp_path)

    create_calls: list = []

    def _create(*args, **kwargs):  # pragma: no cover — assertion is on non-call
        create_calls.append((args, kwargs))
        raise AssertionError(
            "create_lane_workspace must not be invoked when preflight fails"
        )

    monkeypatch.setattr(implement_phases, "create_lane_workspace", _create)

    with (
        patch(
            "specify_cli.charter_runtime.preflight.hook.run_charter_preflight",
            return_value=_fail_result(),
        ),
        pytest.raises(typer.Exit) as excinfo,
    ):
        _call_implement_unwrapped(
            wp_id="WP01",
            mission="042-test-feature",
            auto_commit=None,
            json_output=False,
            recover=False,
            base=None,
            acknowledge_not_bulk_edit=False,
            actor=None,
        )

    assert excinfo.value.exit_code == 1
    assert create_calls == []
    captured = capsys.readouterr()
    assert "synthesized DRG missing" in captured.err


def test_implement_proceeds_past_preflight_when_passed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """On success the gate releases control to the downstream stages."""
    from specify_cli.cli.commands import implement as implement_mod
    from specify_cli.cli.commands import implement_phases

    monkeypatch.setattr(implement_mod, "find_repo_root", lambda: tmp_path)

    sentinel = RuntimeError("reached detect_mission_context")

    def _detect(*_args, **_kwargs):
        raise sentinel

    # detect_mission_context is the very next call after preflight; reaching
    # it proves the gate let us through.
    monkeypatch.setattr(implement_phases, "detect_mission_context", _detect)

    with (
        patch(
            "specify_cli.charter_runtime.preflight.hook.run_charter_preflight",
            return_value=_pass_result(),
        ),
        pytest.raises(RuntimeError) as excinfo,
    ):
        _call_implement_unwrapped(
            wp_id="WP01",
            mission="042-test-feature",
            auto_commit=None,
            json_output=False,
            recover=False,
            base=None,
            acknowledge_not_bulk_edit=False,
            actor=None,
        )

    assert excinfo.value is sentinel
