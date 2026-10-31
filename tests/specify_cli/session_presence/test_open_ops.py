"""WP06 T023/T024/T027 — open-Ops session presence surfaces.

Covers render_open_ops_section (0/1/N), render_open_ops_reminder, the
session-stop command's exit-0 guarantee, and the 1,000-file performance
budget (<0.5 s, same pro-rata budget as the WP04 sweep enumeration guard).
"""

from __future__ import annotations

import json
import time
from kernel.clock import UTC, datetime, timedelta
from pathlib import Path

import pytest

from tests._perf_helpers import assert_timing_budget

from specify_cli.invocation.writer import EVENTS_DIR
from specify_cli.session_presence.open_ops import (
    render_open_ops_reminder,
    render_open_ops_section,
)

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_NOW = datetime(2026, 6, 11, 12, 0, 0, tzinfo=UTC)


def _write_op(
    ops_dir: Path,
    invocation_id: str,
    profile_id: str = "implementer-iris",
    started_at: str | None = None,
    closed: bool = False,
) -> Path:
    ops_dir.mkdir(parents=True, exist_ok=True)
    started_at = started_at or (_NOW - timedelta(hours=26)).isoformat()
    lines = [
        json.dumps(
            {
                "event": "started",
                "invocation_id": invocation_id,
                "profile_id": profile_id,
                "started_at": started_at,
            }
        )
    ]
    if closed:
        lines.append(
            json.dumps(
                {
                    "event": "completed",
                    "invocation_id": invocation_id,
                    "outcome": "done",
                    "closed_by": "agent",
                    "completed_at": _NOW.isoformat(),
                }
            )
        )
    path = ops_dir / f"{invocation_id}.jsonl"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


class TestRenderOpenOpsSection:
    def test_zero_open_ops_no_dir_renders_empty(self, tmp_path: Path) -> None:
        assert render_open_ops_section(tmp_path, now=_NOW) == ""

    def test_zero_open_ops_all_closed_renders_empty(self, tmp_path: Path) -> None:
        _write_op(tmp_path / EVENTS_DIR, "01KTCLOSED0000000000000001", closed=True)
        assert render_open_ops_section(tmp_path, now=_NOW) == ""

    def test_one_open_op_renders_section(self, tmp_path: Path) -> None:
        _write_op(tmp_path / EVENTS_DIR, "01KTOPEN000000000000000001")
        section = render_open_ops_section(tmp_path, now=_NOW)
        assert "⚠ Open Ops (1): work that was dispatched but never closed" in section
        assert "01KTOPEN000000000000000001 (implementer-iris, 26h old)" in section
        assert (
            "close: spec-kitty profile-invocation complete "
            "--invocation-id 01KTOPEN000000000000000001 --outcome <done|failed|abandoned>"
        ) in section
        assert "Sweep stale ones: spec-kitty doctor ops --close-stale" in section

    def test_n_open_ops_renders_all(self, tmp_path: Path) -> None:
        ops_dir = tmp_path / EVENTS_DIR
        for i in range(3):
            _write_op(ops_dir, f"01KTOPEN00000000000000000{i}", profile_id=f"profile-{i}")
        _write_op(ops_dir, "01KTCLOSED0000000000000009", closed=True)
        section = render_open_ops_section(tmp_path, now=_NOW)
        assert "⚠ Open Ops (3)" in section
        for i in range(3):
            assert f"01KTOPEN00000000000000000{i}" in section
            assert f"profile-{i}" in section
        assert "01KTCLOSED" not in section

    def test_unparseable_first_line_still_lists_op(self, tmp_path: Path) -> None:
        ops_dir = tmp_path / EVENTS_DIR
        ops_dir.mkdir(parents=True)
        (ops_dir / "01KTBROKEN0000000000000001.jsonl").write_text(
            "not json\n", encoding="utf-8"
        )
        section = render_open_ops_section(tmp_path, now=_NOW)
        assert "01KTBROKEN0000000000000001 — close:" in section

    def test_1k_open_ops_renders_the_count(self, tmp_path: Path) -> None:
        """1,000 Op files render with the correct open-Ops count."""
        ops_dir = tmp_path / EVENTS_DIR
        for i in range(1000):
            _write_op(ops_dir, f"01KTPERF{i:018d}")
        section = render_open_ops_section(tmp_path, now=_NOW)
        assert "⚠ Open Ops (1000)" in section

    def test_scan_stays_on_the_root_checkout_without_git(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The session boundary is a git-free, root-checkout scan (#6661).

        Op records can live in a linked worktree since #6564, but listing those
        here would need a ``git worktree list`` on every session start/stop. The
        repository-wide surface is ``spec-kitty doctor ops``; this scan must not
        grow a git call, and must not report another checkout's Op.
        """
        from specify_cli.invocation import op_custody

        def _no_git(*args: object, **kwargs: object) -> None:
            raise AssertionError("session presence must not spawn a git subprocess")

        monkeypatch.setattr(op_custody, "_git_lines", _no_git)
        _write_op(tmp_path / EVENTS_DIR, "01KTOOTOP0000000000000001")
        _write_op(tmp_path / "lane" / EVENTS_DIR, "01KTLANEOP000000000000001")

        section = render_open_ops_section(tmp_path, now=_NOW)

        assert "01KTOOTOP0000000000000001" in section
        assert "01KTLANEOP000000000000001" not in section

    @pytest.mark.performance
    def test_perf_1k_open_ops_under_half_second(self, tmp_path: Path) -> None:
        """NFR pro-rata budget: 1,000 Op files rendered in < 0.5 s, no git calls."""
        ops_dir = tmp_path / EVENTS_DIR
        for i in range(1000):
            _write_op(ops_dir, f"01KTPERF{i:018d}")
        start = time.perf_counter()
        render_open_ops_section(tmp_path, now=_NOW)
        elapsed = time.perf_counter() - start
        assert_timing_budget(elapsed, 0.5, name="1k-file open-Ops render")


class TestRenderOpenOpsReminder:
    def test_empty_when_no_open_ops(self, tmp_path: Path) -> None:
        assert render_open_ops_reminder(tmp_path, now=_NOW) == ""

    def test_reminder_wraps_section(self, tmp_path: Path) -> None:
        _write_op(tmp_path / EVENTS_DIR, "01KTOPEN000000000000000001")
        reminder = render_open_ops_reminder(tmp_path, now=_NOW)
        assert "this session is ending with open Ops" in reminder
        assert "⚠ Open Ops (1)" in reminder
        assert "--outcome <done|failed|abandoned>" in reminder


class TestSessionStopCommand:
    """session-stop must always exit 0 and never block the host's stop flow."""

    def test_silent_outside_project(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from functools import partial

        from specify_cli.cli.commands import session_stop as session_stop_module

        # Bind the project-root walk to this test's own tree (#130): an
        # unbounded walk reads shared territory above tmp_path (/tmp, /) where
        # a stray .kittify/ from a sibling test would flip the verdict.
        monkeypatch.setattr(
            session_stop_module,
            "_find_project_root",
            partial(session_stop_module._find_project_root, stop=tmp_path),
        )
        monkeypatch.chdir(tmp_path)
        session_stop_module.session_stop()  # must not raise
        assert capsys.readouterr().out == ""

    def test_silent_with_zero_open_ops(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from specify_cli.cli.commands.session_stop import session_stop

        (tmp_path / ".kittify").mkdir()
        monkeypatch.chdir(tmp_path)
        session_stop()
        assert capsys.readouterr().out == ""

    def test_prints_reminder_with_open_ops(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from specify_cli.cli.commands.session_stop import session_stop

        (tmp_path / ".kittify").mkdir()
        _write_op(tmp_path / EVENTS_DIR, "01KTOPEN000000000000000001")
        monkeypatch.chdir(tmp_path)
        session_stop()  # must not raise even though Ops are open
        out = capsys.readouterr().out
        assert "open Ops" in out
        assert "01KTOPEN000000000000000001" in out

    def test_swallows_internal_errors(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from specify_cli.cli.commands import session_stop as session_stop_module

        (tmp_path / ".kittify").mkdir()
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(
            "specify_cli.session_presence.open_ops.render_open_ops_reminder",
            lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")),
        )
        session_stop_module.session_stop()  # exit-0 guarantee: never raises
        assert capsys.readouterr().out == ""


class TestSessionStartOpenOps:
    """session-start appends the open-Ops section only when open Ops exist."""

    @staticmethod
    def _run_session_start(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from unittest.mock import patch as mock_patch

        from specify_cli.cli.commands.session_start import session_start
        from specify_cli.session_presence.content import SessionPresenceContent

        monkeypatch.chdir(tmp_path)
        with (
            mock_patch(
                "specify_cli.session_presence.manager.SessionPresenceManager._build_content",
                return_value=SessionPresenceContent("3.2.0", "proj", "healthy", None),
            ),
            mock_patch(
                "specify_cli.core.agent_config.load_agent_config",
                return_value=None,
            ),
        ):
            session_start()

    def test_no_open_ops_no_extra_output(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        (tmp_path / ".kittify").mkdir()
        self._run_session_start(tmp_path, monkeypatch)
        out = capsys.readouterr().out
        assert "Spec Kitty" in out
        assert "Open Ops" not in out

    def test_open_ops_section_appended(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        (tmp_path / ".kittify").mkdir()
        _write_op(tmp_path / EVENTS_DIR, "01KTOPEN000000000000000001")
        self._run_session_start(tmp_path, monkeypatch)
        out = capsys.readouterr().out
        assert "⚠ Open Ops (1)" in out
        assert "01KTOPEN000000000000000001" in out
        assert "spec-kitty doctor ops --close-stale" in out
