"""End-to-end wiring: the CLI staleness reader threads the PID-reuse baseline (#2575).

WP02 co-writes a ``shell_pid_created_at`` identity baseline alongside ``shell_pid``
at every claim site, and ``core.stale_detection`` compares it. Post-#2816 both
``shell_pid`` and the baseline are runtime slots sourced ONLY from the reduced
event-log snapshot (never WP frontmatter) — the two doors stay consistent. This
file proves the fix is NOT dormant: the CLI status reader (``tasks_status_cmd``)
surfaces the SNAPSHOT baseline into the per-WP row dicts that feed
``check_doing_wps_for_staleness`` (ignoring any decoy frontmatter/row value), so a
recycled PID (live PID + mismatched snapshot baseline) is caught as stale-eligible
through the real consumer — not merely by the unit-level companion.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from specify_cli.cli.commands.agent import tasks_status_cmd
from specify_cli.cli.commands.agent.tasks_status_cmd import _StatusState, _st_load_work_packages
from specify_cli.core.stale_detection import LIVE_CLAIM_PROCESS_REASON, check_doing_wps_for_staleness
from specify_cli.frontmatter import SHELL_PID_BASELINE_FIELD
from specify_cli.status.models import InnerStateChanged, Lane, StatusEvent, WPInnerStateDelta
from specify_cli.status.store import append_annotations_atomic_verified, append_event
from specify_cli.workspace.context import ResolvedWorkspace

pytestmark = pytest.mark.fast


def _write_wp(tasks_dir: Path, *, shell_pid: str, baseline: str | None) -> None:
    """Author a WP with DECOY frontmatter ``shell_pid``/baseline.

    Post-#2816 these frontmatter values are runtime slots the reader must IGNORE
    (snapshot is the sole authority); they are written here as decoys precisely to
    prove they never leak into the row.
    """
    tasks_dir.mkdir(parents=True, exist_ok=True)
    baseline_line = f'{SHELL_PID_BASELINE_FIELD}: "{baseline}"\n' if baseline is not None else ""
    (tasks_dir / "WP01.md").write_text(
        "---\n"
        "work_package_id: WP01\n"
        "title: Example\n"
        "phase: Phase 1\n"
        "agent: claude\n"
        f'shell_pid: "{shell_pid}"\n'
        f"{baseline_line}"
        "history: []\n"
        "---\n\n# Body\n",
        encoding="utf-8",
    )


def _seed_snapshot_runtime(
    feature_dir: Path, wp_id: str, *, shell_pid: str, baseline: str | None
) -> None:
    """Seed the reduced snapshot's runtime ``shell_pid``/``shell_pid_created_at`` slots.

    Post-#2816 these are event-sourced only, so the CLI reader and the staleness
    consumer both resolve them here (a lane event so the WP exists in the snapshot,
    then an ``InnerStateChanged`` delta carrying the runtime slots).
    """
    feature_dir.mkdir(parents=True, exist_ok=True)
    append_event(
        feature_dir,
        StatusEvent(
            event_id=f"test-{wp_id}-in_progress",
            mission_slug=feature_dir.name,
            wp_id=wp_id,
            from_lane=Lane.PLANNED,
            to_lane=Lane.IN_PROGRESS,
            at="2026-01-01T00:00:00+00:00",
            actor="test",
            force=True,
            execution_mode="worktree",
        ),
    )
    delta = (
        WPInnerStateDelta(shell_pid=int(shell_pid), shell_pid_created_at=baseline)
        if baseline is not None
        else WPInnerStateDelta(shell_pid=int(shell_pid))
    )
    append_annotations_atomic_verified(
        feature_dir,
        [
            InnerStateChanged(
                event_id="01KXRNT" + "0" * 19,
                wp_id=wp_id,
                at="2026-01-01T00:00:30+00:00",
                actor="test",
                delta=delta,
            )
        ],
    )


def _lane_workspace(tmp_path: Path) -> ResolvedWorkspace:
    """A resolvable lane workspace (has a ``.git`` marker so ``.exists`` is True)."""
    lane_dir = tmp_path / ".worktrees" / "mission-lane-a"
    lane_dir.mkdir(parents=True, exist_ok=True)
    (lane_dir / ".git").write_text("gitdir: /somewhere\n", encoding="utf-8")
    return ResolvedWorkspace(
        mission_slug="mission",
        wp_id="WP01",
        execution_mode="code_change",
        mode_source="test",
        resolution_kind="lane_workspace",
        workspace_name="mission-lane-a",
        worktree_path=lane_dir,
        branch_name="kitty/mission-lane-a",
        lane_id="a",
        lane_wp_ids=["WP01"],
    )


def test_cli_reader_threads_baseline_into_row_dict(tmp_path: Path) -> None:
    """``_st_load_work_packages`` surfaces the SNAPSHOT ``shell_pid``/baseline into each row.

    Post-#2816 both are runtime slots read from the reduced snapshot (never
    frontmatter). This is the field the two ``check_doing_wps_for_staleness``
    callers (``_st_emit_json`` and ``_st_render_human``, sharing row objects via
    ``_kanban_rollup``) read as ``wp.get(SHELL_PID_BASELINE_FIELD)``. Decoy
    frontmatter values prove the snapshot wins.
    """
    tasks_dir = tmp_path / "tasks"
    # Decoy frontmatter values the reader must IGNORE.
    _write_wp(tasks_dir, shell_pid="9999", baseline="0.0")
    # Authoritative snapshot slots.
    _seed_snapshot_runtime(tmp_path, "WP01", shell_pid="4242", baseline="1700000000.5")

    st = _StatusState(mission="mission", json_output=True, stale_threshold=10)
    st.mission_slug = "mission"
    st.main_repo_root = tmp_path
    st.feature_dir = tmp_path
    st.tasks_dir = tasks_dir

    _st_load_work_packages(st)

    assert len(st.work_packages) == 1
    row = st.work_packages[0]
    assert row["shell_pid"] == "4242"
    assert row[SHELL_PID_BASELINE_FIELD] == "1700000000.5"


def test_cli_reader_baseline_absent_defaults_to_none(tmp_path: Path) -> None:
    """A claimed WP whose snapshot carries ``shell_pid`` but NO baseline yields ``None``.

    Additive degradation (D3a): the baseline is snapshot-sourced, so a snapshot
    slot without ``shell_pid_created_at`` surfaces ``None`` — even though a decoy
    frontmatter baseline is present (it is ignored).
    """
    tasks_dir = tmp_path / "tasks"
    _write_wp(tasks_dir, shell_pid="9999", baseline="0.0")
    _seed_snapshot_runtime(tmp_path, "WP01", shell_pid="4242", baseline=None)

    st = _StatusState(mission="mission", json_output=True, stale_threshold=10)
    st.mission_slug = "mission"
    st.main_repo_root = tmp_path
    st.feature_dir = tmp_path
    st.tasks_dir = tasks_dir

    _st_load_work_packages(st)

    assert st.work_packages[0]["shell_pid"] == "4242"
    assert st.work_packages[0][SHELL_PID_BASELINE_FIELD] is None


def test_recycled_pid_caught_through_check_doing_wps(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A live PID + MISMATCHED baseline is stale-eligible through the real consumer.

    Feeds ``check_doing_wps_for_staleness`` a doing-WP row shaped exactly like the
    CLI reader now produces (``shell_pid`` + ``SHELL_PID_BASELINE_FIELD``). Because
    the baseline does not match the live process's creation time, the claim is NOT
    trusted alive: the ``live_claim_process`` short-circuit is bypassed and staleness
    falls through to the commit-timestamp heuristic (never a hard-stale flag).
    """
    monkeypatch.setattr(
        "specify_cli.core.stale_detection.resolve_workspace_for_wp",
        lambda root, slug, wp_id, **_kw: _lane_workspace(tmp_path),
    )

    # Snapshot is the authority (#2816): a live PID + MISMATCHED snapshot baseline.
    _seed_snapshot_runtime(
        tmp_path / "kitty-specs" / "mission",
        "WP01",
        shell_pid=str(os.getpid()),  # a genuinely live PID
        baseline="1.0",  # deliberately wrong creation-time baseline
    )

    doing_wps = [
        {
            "id": "WP01",
            # Decoy row values (correct-looking) the consumer must IGNORE now that
            # claim-liveness is snapshot-sourced.
            "shell_pid": str(os.getpid()),
            SHELL_PID_BASELINE_FIELD: "1.0",
        }
    ]

    results = check_doing_wps_for_staleness(
        main_repo_root=tmp_path,
        mission_slug="mission",
        doing_wps=doing_wps,
        threshold_minutes=10,
    )

    assert "WP01" in results
    # Did NOT take the trusted-alive short-circuit: the mismatched baseline defeated it.
    assert results["WP01"].stale.reason != LIVE_CLAIM_PROCESS_REASON


def test_matching_baseline_still_trusts_live_pid_through_check_doing_wps(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Contrast: a MATCHING baseline preserves the trusted-alive short-circuit.

    Proves the divergence above is caused by the threaded baseline, not by an
    unrelated code path: same wiring, correct baseline -> ``live_claim_process``.
    """
    from specify_cli.core.process_liveness import capture_creation_time_baseline

    monkeypatch.setattr(
        "specify_cli.core.stale_detection.resolve_workspace_for_wp",
        lambda root, slug, wp_id, **_kw: _lane_workspace(tmp_path),
    )

    own_pid = os.getpid()
    baseline = capture_creation_time_baseline(own_pid)
    assert baseline is not None

    # Snapshot is the authority (#2816): live PID + MATCHING snapshot baseline.
    _seed_snapshot_runtime(
        tmp_path / "kitty-specs" / "mission",
        "WP01",
        shell_pid=str(own_pid),
        baseline=baseline,
    )

    doing_wps = [
        {
            "id": "WP01",
            # Decoy row values with a WRONG baseline: if the consumer still read
            # the row it would defeat the trust — proving the snapshot wins.
            "shell_pid": str(own_pid),
            SHELL_PID_BASELINE_FIELD: "1.0",
        }
    ]

    results = check_doing_wps_for_staleness(
        main_repo_root=tmp_path,
        mission_slug="mission",
        doing_wps=doing_wps,
        threshold_minutes=10,
    )

    assert results["WP01"].stale.reason == LIVE_CLAIM_PROCESS_REASON


def test_module_exposes_load_work_packages_seam() -> None:
    """Guard: the phase helper the wiring lives in stays importable at its seam."""
    assert hasattr(tasks_status_cmd, "_st_load_work_packages")
