"""Tests for ambient-warning de-duplication + scoped rendering (#3971).

Covers the three halves of the #3971 contract on the charter-preflight
advisory channel:

* the ``warnings`` list is de-duplicated (first occurrence, stable order);
* each distinct ambient warning is surfaced at most once per command run
  (process lifetime) — a repeated hook invocation prints the duplicate no
  more;
* the single surfaced instance carries its scope (consumer + repo root,
  advisory-only note), and every ambient warning text keeps a concrete
  remedy (an exact recovery command).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.charter_runtime.preflight.ambient_warning import (
    dedupe_warnings,
    record_surfaced,
    render_ambient_warning,
    _reset_surfaced_for_testing,
    warning_already_surfaced,
)
from specify_cli.charter_runtime.preflight.result import CharterPreflightResult
from specify_cli.charter_runtime.preflight.runner import (
    _FRESH_PROJECT_MISSING_CHARTER_WARNING,
    _LEGACY_CHARTER_BUNDLE_WARNING,
)


pytestmark = pytest.mark.fast


@pytest.fixture(autouse=True)
def _reset_surfaced_latch() -> None:
    """Reset the process-lifetime surfaced latch around every test case.

    The latch is exactly the "once per command run" budget; a test process
    is one long command run, so without this fixture the first test would
    consume every other test's emission. Mirrors the
    ``retrospective.deprecation`` reset pattern.
    """
    _reset_surfaced_for_testing()
    yield
    _reset_surfaced_for_testing()


def _advisory_result(warnings: list[str]) -> CharterPreflightResult:
    return CharterPreflightResult(
        passed=True,
        checks=[],
        auto_refresh_applied=False,
        auto_refresh_actions=[],
        blocked_reason=None,
        warnings=warnings,
    )


# ---------------------------------------------------------------------------
# dedupe_warnings
# ---------------------------------------------------------------------------


def test_dedupe_warnings_keeps_first_occurrence_in_order() -> None:
    assert dedupe_warnings(["a", "b", "a", "c", "b"]) == ["a", "b", "c"]


def test_dedupe_warnings_is_identity_on_duplicate_free_input() -> None:
    assert dedupe_warnings(["a", "b"]) == ["a", "b"]
    assert dedupe_warnings([]) == []


# ---------------------------------------------------------------------------
# emit_advisory_warnings — once per command run, scope attached
# ---------------------------------------------------------------------------


def test_emit_suppresses_duplicates_within_one_result(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from specify_cli.charter_runtime.preflight.hook import emit_advisory_warnings

    emit_advisory_warnings(
        _advisory_result(["ambient one", "ambient one", "ambient two"]),
        consumer="next",
        repo_root=tmp_path,
    )
    err = capsys.readouterr().err
    assert err.count("Warning: ambient one") == 1
    assert err.count("Warning: ambient two") == 1


def test_emit_surfaces_each_distinct_warning_once_per_command_run(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A repeated hook invocation in the same process prints the duplicate no more."""
    from specify_cli.charter_runtime.preflight.hook import emit_advisory_warnings

    for _ in range(3):
        emit_advisory_warnings(
            _advisory_result(["ambient one", "ambient two"]),
            consumer="next",
            repo_root=tmp_path,
        )
    err = capsys.readouterr().err
    assert err.count("Warning: ambient one") == 1
    assert err.count("Warning: ambient two") == 1


def test_emit_attaches_scope_to_single_surfaced_instance(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from specify_cli.charter_runtime.preflight.hook import emit_advisory_warnings

    emit_advisory_warnings(
        _advisory_result(["ambient one"]),
        consumer="implement",
        repo_root=tmp_path,
    )
    err = capsys.readouterr().err
    line = err.strip()
    # Historical prefix kept (existing consumers match on the substring)…
    assert line.startswith("Warning: ambient one")
    # …with the scope of the single surfaced instance appended.
    assert "consumer 'implement'" in line
    assert f"repo root '{tmp_path}'" in line
    assert "advisory only" in line
    assert "shown once per command run" in line


def test_run_preflight_or_abort_scopes_and_dedupes_across_consumers(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The shared hook threads its consumer/repo_root into the scoped render."""
    from specify_cli.charter_runtime.preflight import hook as hook_mod

    monkeypatch.setattr(
        hook_mod,
        "run_charter_preflight",
        lambda **_: _advisory_result(["ambient one"]),
    )
    hook_mod.run_preflight_or_abort(tmp_path, consumer="next")
    err = capsys.readouterr().err
    assert "Warning: ambient one" in err
    assert "consumer 'next'" in err
    assert f"repo root '{tmp_path}'" in err

    # Same ambient condition reported by a second consumer in the same
    # command run: already surfaced, prints nothing.
    hook_mod.run_preflight_or_abort(tmp_path, consumer="implement")
    assert capsys.readouterr().err == ""


# ---------------------------------------------------------------------------
# latch helpers
# ---------------------------------------------------------------------------


def test_latch_records_and_resets() -> None:
    assert not warning_already_surfaced("ambient one")
    record_surfaced("ambient one")
    assert warning_already_surfaced("ambient one")
    _reset_surfaced_for_testing()
    assert not warning_already_surfaced("ambient one")


# ---------------------------------------------------------------------------
# remedy guard — every ambient warning keeps a concrete remedy
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("warning",),
    [
        pytest.param(_FRESH_PROJECT_MISSING_CHARTER_WARNING, id="missing_charter"),
        pytest.param(_LEGACY_CHARTER_BUNDLE_WARNING, id="legacy_bundle"),
    ],
)
def test_rendered_ambient_warning_carries_concrete_remedy(
    warning: str,
    tmp_path: Path,
) -> None:
    """The single surfaced instance must include an exact recovery command.

    The remedy travels in the warning text itself (the two runner constants
    are the ambient warnings this channel surfaces today); this guard fails
    if a future edit to a constant drops the recovery command.
    """
    line = render_ambient_warning(warning, consumer="next", repo_root=tmp_path)
    assert line.startswith(f"Warning: {warning}")
    assert "run `spec-kitty charter" in line
