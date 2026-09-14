"""WP03 (#2649) -- characterization tests for ``_json_safe_output`` and
``_run_recover_mode`` BEFORE their S3776 degod extraction.

These pin the extraction-fragile invariants called out by the WP03 tracer so
the helper-extraction in T012/T013 cannot silently collapse them:

``_json_safe_output`` (T010):
1. ``console._file`` is reset to ``None`` in the ``finally`` block AND
   ``console.quiet`` is saved/restored across the call -- two INDEPENDENT
   resets, not one.
2. Dual exception arms differ by design: ``typer.Exit`` is re-raised
   **verbatim** (the very same instance); a bare ``Exception`` is **wrapped**
   in a fresh ``typer.Exit(1)`` (with ``__cause__`` set). Do NOT merge them.
3. The ``getattr(exc, "exit_code", 1)`` guard suppresses the JSON payload
   when a ``typer.Exit`` carries ``exit_code=0``; otherwise the summary is
   the last 20 non-blank, rstripped lines captured from the console.

``_run_recover_mode`` (T011) has four ``json_output`` vs console dual-render
branches:
1. Error path (``TaskCliError``/``typer.Exit`` from context resolution) --
   json-error emit vs a bare ``raise typer.Exit(1)`` (no console line).
2. No-recovery-needed path (``needs_recovery`` empty) -- json "ok" payload
   vs the console "no crashed sessions" message.
3. Recovery-needed path (non-empty) -- the console-only recovery table,
   THEN the final json payload (subset of fields: no ``contexts_recreated``)
   vs the console recovery-complete summary (superset: includes
   ``contexts_recreated``).
4. The recovery-needed path additionally renders an "Errors:" block on the
   console (and the same list under ``errors`` in the json payload) when
   ``report.errors`` is non-empty.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
import typer

from specify_cli.cli.commands import implement as implement_module
from specify_cli.cli.commands.implement import _json_safe_output, _run_recover_mode
from specify_cli.cli.console import console
from specify_cli.lanes import recovery as recovery_module
from specify_cli.lanes.recovery import RecoveryReport, RecoveryState
from specify_cli.task_utils import TaskCliError

pytestmark = pytest.mark.fast


@pytest.fixture(autouse=True)
def _restore_console_state() -> Iterator[None]:
    """The decorator/function under test mutate the process-wide ``console``
    singleton -- restore it so no test leaks state into a sibling test."""
    previous_quiet = console.quiet
    previous_file = console._file
    yield
    console.quiet = previous_quiet
    console._file = previous_file


# ---------------------------------------------------------------------------
# T010 -- _json_safe_output
# ---------------------------------------------------------------------------


def test_console_file_reset_unconditionally_and_quiet_restored_to_prior_true() -> None:
    @_json_safe_output
    def _ok(*, wp_id: str | None = None, json_output: bool = False) -> str:
        console.print("hello")
        return "done"

    console.quiet = True  # arbitrary prior value the wrapper must restore
    result = _ok(wp_id="WP01", json_output=True)

    assert result == "done"
    assert console.quiet is True  # restored, not flipped to the capture value
    assert console._file is None  # unconditional finally-block reset


def test_console_quiet_restored_to_prior_false_when_not_json() -> None:
    @_json_safe_output
    def _ok(*, wp_id: str | None = None, json_output: bool = False) -> None:
        return None

    console.quiet = False
    _ok(wp_id="WP01", json_output=False)

    assert console.quiet is False
    assert console._file is None


def test_typer_exit_reraised_verbatim_same_instance() -> None:
    original = typer.Exit(code=3)

    @_json_safe_output
    def _fails(*, wp_id: str | None = None, json_output: bool = False) -> None:
        raise original

    with pytest.raises(typer.Exit) as excinfo:
        _fails(wp_id="WP07", json_output=False)

    assert excinfo.value is original  # same instance -- not re-wrapped
    assert excinfo.value.exit_code == 3


def test_bare_exception_wrapped_in_fresh_typer_exit_1() -> None:
    @_json_safe_output
    def _fails(*, wp_id: str | None = None, json_output: bool = False) -> None:
        raise ValueError("boom")

    with pytest.raises(typer.Exit) as excinfo:
        _fails(wp_id="WP07", json_output=False)

    assert excinfo.value.exit_code == 1
    assert isinstance(excinfo.value.__cause__, ValueError)
    assert str(excinfo.value.__cause__) == "boom"


def test_bare_exception_json_payload_includes_wp_id(capsys: pytest.CaptureFixture[str]) -> None:
    @_json_safe_output
    def _fails(*, wp_id: str | None = None, json_output: bool = False) -> None:
        raise ValueError("boom")

    with pytest.raises(typer.Exit):
        _fails(wp_id="WP09", json_output=True)

    payload = json.loads(capsys.readouterr().out.strip())
    assert payload == {"status": "error", "error": "boom", "wp_id": "WP09"}


def test_typer_exit_nonzero_emits_last_20_nonblank_lines_summary(capsys: pytest.CaptureFixture[str]) -> None:
    @_json_safe_output
    def _fails(*, wp_id: str | None = None, json_output: bool = False) -> None:
        for i in range(25):
            console.print(f"line {i}")
            if i % 5 == 0:
                console.print("")  # blank lines must be dropped from the summary
        raise typer.Exit(code=1)

    with pytest.raises(typer.Exit):
        _fails(wp_id="WP03", json_output=True)

    payload = json.loads(capsys.readouterr().out.strip())
    assert payload["status"] == "error"
    assert payload["wp_id"] == "WP03"
    lines = payload["error"].splitlines()
    assert len(lines) == 20  # (20-line tail window)
    assert lines[0] == "line 5"  # last 20 of the 25 non-blank "line N" entries
    assert lines[-1] == "line 24"


def test_typer_exit_zero_suppresses_json_payload(capsys: pytest.CaptureFixture[str]) -> None:
    @_json_safe_output
    def _ok_exit(*, wp_id: str | None = None, json_output: bool = False) -> None:
        console.print("should not appear in any payload")
        raise typer.Exit(code=0)

    with pytest.raises(typer.Exit) as excinfo:
        _ok_exit(wp_id="WP03", json_output=True)

    assert excinfo.value.exit_code == 0
    assert capsys.readouterr().out.strip() == ""


def test_wp_id_resolved_from_positional_arg_when_not_a_kwarg(capsys: pytest.CaptureFixture[str]) -> None:
    @_json_safe_output
    def _fails(wp_id_positional: str, *, json_output: bool = False) -> None:
        raise ValueError("boom")

    with pytest.raises(typer.Exit):
        _fails("WP11", json_output=True)

    payload = json.loads(capsys.readouterr().out.strip())
    assert payload["wp_id"] == "WP11"


# ---------------------------------------------------------------------------
# T011 -- _run_recover_mode
# ---------------------------------------------------------------------------


def _patch_context(monkeypatch: pytest.MonkeyPatch, repo_root: Path, mission_slug: str) -> None:
    monkeypatch.setattr(implement_module, "find_repo_root", lambda: repo_root)
    monkeypatch.setattr(
        implement_module,
        "detect_feature_context",
        lambda _mission, repo_root=None: (None, mission_slug),
    )


def _state(*, recovery_action: str, wp_id: str = "WP04") -> RecoveryState:
    return RecoveryState(
        wp_id=wp_id,
        lane_id="lane-a",
        branch_name="kitty/mission-x-lane-a",
        branch_exists=True,
        worktree_exists=False,
        context_exists=True,
        status_lane="in_progress",
        has_commits=True,
        recovery_action=recovery_action,
    )


class TestRecoverErrorPath:
    """Branch 1: context resolution fails (TaskCliError/typer.Exit)."""

    def test_json_output_emits_error_payload_and_exits_1(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.setattr(implement_module, "find_repo_root", lambda: tmp_path)

        def _raise(_mission: str | None, repo_root: Path | None = None) -> tuple[str | None, str]:
            raise TaskCliError("mission not found")

        monkeypatch.setattr(implement_module, "detect_feature_context", _raise)

        with pytest.raises(typer.Exit) as excinfo:
            _run_recover_mode("WP01", "missing-mission", json_output=True)

        assert excinfo.value.exit_code == 1
        payload = json.loads(capsys.readouterr().out.strip())
        assert payload == {"status": "error", "error": "mission not found"}

    def test_console_output_raises_without_json_payload(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.setattr(implement_module, "find_repo_root", lambda: tmp_path)

        def _raise(_mission: str | None, repo_root: Path | None = None) -> tuple[str | None, str]:
            raise TaskCliError("mission not found")

        monkeypatch.setattr(implement_module, "detect_feature_context", _raise)

        with pytest.raises(typer.Exit) as excinfo:
            _run_recover_mode("WP01", "missing-mission", json_output=False)

        assert excinfo.value.exit_code == 1
        assert capsys.readouterr().out.strip() == ""


class TestRecoverNoActionNeeded:
    """Branch 2: scan finds no crashed sessions (needs_recovery empty)."""

    def test_json_output_ok_payload(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _patch_context(monkeypatch, tmp_path, "my-mission")
        monkeypatch.setattr(
            recovery_module,
            "scan_recovery_state",
            lambda repo_root, mission_slug: [_state(recovery_action="no_action")],
        )

        def _fail_run_recovery(*_args: Any, **_kwargs: Any) -> RecoveryReport:
            raise AssertionError("run_recovery must not be called when nothing needs recovery")

        monkeypatch.setattr(recovery_module, "run_recovery", _fail_run_recovery)

        _run_recover_mode("WP01", "my-mission", json_output=True)

        payload = json.loads(capsys.readouterr().out.strip())
        assert payload == {
            "status": "ok",
            "message": "No crashed implementation sessions found.",
            "recovered_wps": [],
            "worktrees_recreated": 0,
            "transitions_emitted": 0,
            "errors": [],
        }

    def test_console_output_message(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _patch_context(monkeypatch, tmp_path, "my-mission")
        monkeypatch.setattr(recovery_module, "scan_recovery_state", lambda repo_root, mission_slug: [])

        def _fail_run_recovery(*_args: Any, **_kwargs: Any) -> RecoveryReport:
            raise AssertionError("run_recovery must not be called")

        monkeypatch.setattr(recovery_module, "run_recovery", _fail_run_recovery)

        _run_recover_mode("WP01", "my-mission", json_output=False)

        out = capsys.readouterr().out
        assert "No crashed implementation sessions found." in out
        # No JSON payload leaked onto the console-mode stdout.
        with pytest.raises(json.JSONDecodeError):
            json.loads(out)


class TestRecoverNeedsRecovery:
    """Branch 3 (+4): needs_recovery non-empty -- table/summary + report."""

    def _report(self, *, errors: list[str] | None = None) -> RecoveryReport:
        return RecoveryReport(
            recovered_wps=["WP04"],
            worktrees_recreated=1,
            contexts_recreated=2,
            transitions_emitted=3,
            errors=errors or [],
        )

    def test_json_output_final_payload_omits_contexts_recreated(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _patch_context(monkeypatch, tmp_path, "my-mission")
        monkeypatch.setattr(
            recovery_module,
            "scan_recovery_state",
            lambda repo_root, mission_slug: [_state(recovery_action="recreate_worktree")],
        )
        monkeypatch.setattr(recovery_module, "run_recovery", lambda repo_root, mission_slug: self._report())

        _run_recover_mode("WP01", "my-mission", json_output=True)

        out = capsys.readouterr().out.strip()
        # Exactly one JSON object on stdout: no rich table rendered in json mode.
        payload = json.loads(out)
        assert payload == {
            "status": "ok",
            "recovered_wps": ["WP04"],
            "worktrees_recreated": 1,
            "transitions_emitted": 3,
            "errors": [],
        }
        assert "contexts_recreated" not in payload

    def test_console_output_table_and_summary_include_contexts_recreated(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _patch_context(monkeypatch, tmp_path, "my-mission")
        monkeypatch.setattr(
            recovery_module,
            "scan_recovery_state",
            lambda repo_root, mission_slug: [_state(recovery_action="recreate_worktree")],
        )
        monkeypatch.setattr(recovery_module, "run_recovery", lambda repo_root, mission_slug: self._report())

        _run_recover_mode("WP01", "my-mission", json_output=False)

        out = capsys.readouterr().out
        assert "Recovery Scan Results" in out  # the scan table header
        assert "WP04" in out
        assert "Recovery complete" in out
        assert "WPs recovered: WP04" in out
        assert "Worktrees recreated: 1" in out
        assert "Contexts recreated: 2" in out
        assert "Status transitions emitted: 3" in out

    def test_console_output_renders_errors_block_when_present(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _patch_context(monkeypatch, tmp_path, "my-mission")
        monkeypatch.setattr(
            recovery_module,
            "scan_recovery_state",
            lambda repo_root, mission_slug: [_state(recovery_action="recreate_worktree")],
        )
        monkeypatch.setattr(
            recovery_module,
            "run_recovery",
            lambda repo_root, mission_slug: self._report(errors=["worktree lock held"]),
        )

        _run_recover_mode("WP01", "my-mission", json_output=False)

        out = capsys.readouterr().out
        assert "Errors:" in out
        assert "worktree lock held" in out

    def test_json_output_includes_errors_list(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _patch_context(monkeypatch, tmp_path, "my-mission")
        monkeypatch.setattr(
            recovery_module,
            "scan_recovery_state",
            lambda repo_root, mission_slug: [_state(recovery_action="recreate_worktree")],
        )
        monkeypatch.setattr(
            recovery_module,
            "run_recovery",
            lambda repo_root, mission_slug: self._report(errors=["worktree lock held"]),
        )

        _run_recover_mode("WP01", "my-mission", json_output=True)

        payload = json.loads(capsys.readouterr().out.strip())
        assert payload["errors"] == ["worktree lock held"]
