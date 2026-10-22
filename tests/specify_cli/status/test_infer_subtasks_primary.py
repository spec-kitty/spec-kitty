"""Regression test — subtask-completeness gate under the #2816 IC-10 model.

Proves, through the PRODUCTION ``agent status emit`` -> transition route (NOT a
direct call to ``_infer_subtasks_complete``), that a native
``in_progress -> for_review`` transition (no ``--subtasks-complete``, no
``--force``) resolves subtask-completeness from the **frontmatter-roster +
event-sourced snapshot** model that WP13/IC-10 (FR-016 / SC-010) installed:

* The subtask **roster** (which ``T###`` ids belong to the WP) is the authored
  ``subtasks:`` list in the PRIMARY WP frontmatter — NOT the ``tasks.md``
  checkbox rows, which the cutover retired as the completion proxy.
* **Completion** comes solely from the reduced event-log snapshot's
  ``subtasks`` slot; a fully-``[x]``-checked ``tasks.md`` no longer allows the
  transition on its own.
* Fail-closed: a WP with an authored roster but a silent snapshot BLOCKS — and
  an absent (or emptied) ``tasks.md`` can no longer silently disable the guard.
* Empty roster ("nothing to block on") -> allow.
* PRIMARY-surface threading survives (coord topology): the gate reads the
  PRIMARY frontmatter roster and PRIMARY snapshot, never the coord-branch husk.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from specify_cli.cli.commands.agent.tasks_shared import _check_unchecked_subtasks
from specify_cli.cli.commands.agent.status import app

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

runner = CliRunner()


@pytest.fixture(autouse=True)
def _disable_emit_side_effects(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep these tests focused on the local transition + completeness gate."""
    import specify_cli.status.emit as status_emit

    monkeypatch.setattr(status_emit, "_status_fan_out", lambda *args, **kwargs: None)
def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _make_git_repo(root: Path) -> Path:
    repo = root / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True, text=True)
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test User")
    (repo / ".kittify").mkdir()
    (repo / "README.md").write_text("test repo\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "init")
    return repo


def _status_event(slug: str, wp_id: str, from_lane: str, to_lane: str, event_id: str) -> dict:
    return {
        "event_id": event_id,
        "mission_slug": slug,
        "wp_id": wp_id,
        "from_lane": from_lane,
        "to_lane": to_lane,
        "at": "2026-06-01T12:00:00+00:00",
        "actor": "codex",
        "force": False,
        "execution_mode": "worktree",
        "evidence": None,
        "reason": None,
        "review_ref": None,
        "feature_slug": slug,
    }


def _write_events(feature_dir: Path, events: list[dict]) -> None:
    feature_dir.mkdir(parents=True, exist_ok=True)
    feature_dir.joinpath("status.events.jsonl").write_text(
        "\n".join(json.dumps(event) for event in events) + "\n",
        encoding="utf-8",
    )


def _write_roster(feature_dir: Path, wp_id: str, subtasks: list[str]) -> None:
    """Author a WP frontmatter file whose ``subtasks:`` list IS the gate roster.

    Since #2816 IC-10 the subtask roster is sourced from this authored list
    (static design intent), NOT ``tasks.md`` checkbox rows. An empty *subtasks*
    still writes the file (``subtasks: []``) so the "empty authored roster ->
    nothing to block on" edge is exercised as a real authored surface.
    """
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    lines = ["---", f"work_package_id: {wp_id}"]
    if subtasks:
        lines.append("subtasks:")
        lines.extend(f"- {task_id}" for task_id in subtasks)
    else:
        lines.append("subtasks: []")
    lines.extend(["---", "", f"# {wp_id}", ""])
    (tasks_dir / f"{wp_id}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _seed_snapshot_subtasks(feature_dir: Path, wp_id: str, subtasks: dict[str, object]) -> None:
    """Append an ``InnerStateChanged`` annotation so the reduced snapshot's
    ``subtasks`` slot reports *subtasks* (the sole completion authority)."""
    from specify_cli.status.models import InnerStateChanged, WPInnerStateDelta
    from specify_cli.status.store import append_annotations_atomic_verified

    append_annotations_atomic_verified(
        feature_dir,
        [
            InnerStateChanged(
                event_id="01KXANN0000000000000000000",
                wp_id=wp_id,
                at="2026-06-01T12:00:30+00:00",
                actor="codex",
                delta=WPInnerStateDelta(subtasks=subtasks),
            )
        ],
    )


def _build_coord_mission(
    tmp_path: Path,
    slug: str,
    *,
    roster: list[str] | None,
    tasks_md_body: str | None,
    snapshot_subtasks: dict[str, object] | None = None,
) -> Path:
    """Build a coord-topology mission with a PRIMARY planning surface and a coord
    branch whose event log already has WP01 in ``in_progress`` -- the only lane
    from which ``in_progress -> for_review`` is a legal edge.

    ``roster=None`` authors NO WP frontmatter file (empty roster -> allow);
    ``roster=[...]`` authors the PRIMARY ``tasks/WP01.md`` roster. ``tasks_md_body``
    optionally seeds the PRIMARY ``tasks.md`` -- retained ONLY to prove its
    checkbox content no longer drives the gate. The coord-husk dir intentionally
    never gets a roster or a ``tasks.md`` of its own: those are PRIMARY-partition
    artifacts, so a pre-cutover read through the coord husk would find nothing --
    the PRIMARY-surface threading this gate must preserve.
    """
    mission_id = "01ABCDEF1234567890123456"
    mid8 = mission_id[:8]
    coord_branch = f"kitty/mission-{slug}-{mid8}"
    repo = _make_git_repo(tmp_path)

    primary_dir = repo / "kitty-specs" / slug
    primary_dir.mkdir(parents=True)
    (primary_dir / "meta.json").write_text(
        json.dumps(
            {
                "mission_id": mission_id,
                "coordination_branch": coord_branch,
                "mission_slug": slug,
            }
        ),
        encoding="utf-8",
    )
    if tasks_md_body is not None:
        (primary_dir / "tasks.md").write_text(tasks_md_body, encoding="utf-8")
    if roster is not None:
        _write_roster(primary_dir, "WP01", roster)
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "primary planning artifacts")

    _git(repo, "checkout", "-b", coord_branch)
    coord_branch_dir = repo / "kitty-specs" / f"{slug}-{mid8}"
    _write_events(
        coord_branch_dir,
        [
            _status_event(slug, "WP01", "planned", "claimed", "01HXYZ0123456789ABCDEFGH40"),
            _status_event(slug, "WP01", "claimed", "in_progress", "01HXYZ0123456789ABCDEFGH41"),
        ],
    )
    if snapshot_subtasks is not None:
        _seed_snapshot_subtasks(coord_branch_dir, "WP01", snapshot_subtasks)
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "coord in_progress")
    _git(repo, "checkout", "main")

    # Materialize the coord worktree the SAME way production does so that a
    # coord-husk read path genuinely resolves to an existing directory rather
    # than falling back to primary via the create-window gate.
    from specify_cli.coordination.workspace import CoordinationWorkspace

    CoordinationWorkspace.resolve(repo, slug, mid8)

    return repo


def _emit_for_review(repo: Path, slug: str, *, implementation_evidence_present: bool = False):
    """Drive the native ``agent status emit ... --to for_review`` transition.

    ``--subtasks-complete`` and ``--force`` are deliberately never passed --
    completeness is INFERRED through the production route from the PRIMARY
    frontmatter roster + PRIMARY snapshot. ``implementation_evidence_present``
    is a separate, unrelated guard; the "allowed" cases pass it explicitly so
    the subtasks-completeness gate under test is isolated, while the "blocked"
    cases never reach the implementation-evidence guard (subtasks short-circuit).
    """
    args = [
        "emit",
        "WP01",
        "--to",
        "for_review",
        "--actor",
        "codex",
        "--mission",
        slug,
        "--json",
    ]
    if implementation_evidence_present:
        args.append("--implementation-evidence-present")
    with patch(
        "specify_cli.cli.commands.agent.status.locate_project_root",
        return_value=repo,
    ):
        return runner.invoke(app, args)


def test_coord_checked_tasks_md_no_longer_allows_without_snapshot(tmp_path: Path) -> None:
    """Cutover crux: a fully ``[x]``-checked PRIMARY ``tasks.md`` no longer allows.

    Old model: all-checked ``tasks.md`` -> allow. New model: the checkbox proxy
    is retired -- with an authored PRIMARY roster and a SILENT snapshot the gate
    fail-closes and BLOCKS, proving completion no longer comes from the boxes.
    """
    slug = "coord-checked-retired"
    tasks_md = "# Tasks\n\n## WP01\n- [x] T001 implement thing\n"
    repo = _build_coord_mission(tmp_path, slug, roster=["T001"], tasks_md_body=tasks_md)

    result = _emit_for_review(repo, slug)

    assert result.exit_code != 0, result.stdout
    assert "completed subtasks" in result.stdout


def test_coord_missing_authored_roster_fails_closed(tmp_path: Path) -> None:
    """An unresolvable PRIMARY roster is corruption, not an empty authored list."""
    slug = "coord-no-roster"
    repo = _build_coord_mission(tmp_path, slug, roster=None, tasks_md_body=None)

    result = _emit_for_review(repo, slug, implementation_evidence_present=True)

    assert result.exit_code != 0
    assert "Cannot resolve subtask roster" in result.stdout


def test_coord_absent_tasks_md_still_blocks_with_roster(tmp_path: Path) -> None:
    """Fail-closed T009 successor: an absent ``tasks.md`` cannot disable the guard.

    With the checkbox proxy retired, ``tasks.md`` presence is irrelevant. An
    authored PRIMARY roster + silent snapshot still BLOCKS -- an emptied/absent
    ``tasks.md`` can no longer silently empty the roster and fall open.
    """
    slug = "coord-absent"
    repo = _build_coord_mission(tmp_path, slug, roster=["T001"], tasks_md_body=None)

    result = _emit_for_review(repo, slug)

    assert result.exit_code != 0, result.stdout
    assert "completed subtasks" in result.stdout


def test_coord_allows_empty_authored_roster(tmp_path: Path) -> None:
    """Zero-rows edge: an authored-but-empty ``subtasks: []`` roster -> allow."""
    slug = "coord-empty-roster"
    repo = _build_coord_mission(tmp_path, slug, roster=[], tasks_md_body=None)

    result = _emit_for_review(repo, slug, implementation_evidence_present=True)

    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["from_lane"] == "in_progress"
    assert payload["to_lane"] == "for_review"


def test_coord_reads_roster_from_primary_and_completion_from_status_surface(
    tmp_path: Path,
) -> None:
    """The two authority legs remain distinct under coordination topology."""
    from specify_cli.status import Lane

    slug = "coord-split-authority"
    repo = _build_coord_mission(
        tmp_path,
        slug,
        roster=["T001"],
        tasks_md_body=None,
        snapshot_subtasks={"T001": Lane.DONE},
    )

    result = _emit_for_review(repo, slug, implementation_evidence_present=True)

    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["from_lane"] == "in_progress"
    assert payload["to_lane"] == "for_review"


def test_move_task_guard_uses_status_surface_parent_directory(tmp_path: Path) -> None:
    """The shared move-task gate must dereference the status artifact to its dir."""
    from specify_cli.status import Lane

    slug = "coord-shared-gate-status-parent"
    repo = _build_coord_mission(
        tmp_path,
        slug,
        roster=["T001"],
        tasks_md_body=None,
        snapshot_subtasks={"T001": Lane.DONE},
    )

    assert _check_unchecked_subtasks(repo, slug, "WP01", False) == []


def test_mark_status_writes_completion_to_coord_status_partition(tmp_path: Path) -> None:
    """mark-status reads the PRIMARY roster but writes the coord status stream."""
    from specify_cli.cli.commands.agent import tasks as tasks_module
    from specify_cli.coordination import resolve_status_surface
    from specify_cli.status import read_event_stream

    slug = "coord-mark-status-authority"
    repo = _build_coord_mission(
        tmp_path,
        slug,
        roster=["T001"],
        tasks_md_body="# Tasks\n\n## WP01\n- [ ] T001 implement thing\n",
    )
    primary_dir = repo / "kitty-specs" / slug

    with (
        patch.object(tasks_module, "locate_project_root", return_value=repo),
        patch.object(tasks_module, "_find_mission_slug", return_value=slug),
        patch.object(
            tasks_module,
            "_ensure_target_branch_checked_out",
            return_value=(repo, "main"),
        ),
        patch.object(tasks_module, "_emit_sparse_session_warning"),
    ):
        result = runner.invoke(
            tasks_module.app,
            [
                "mark-status",
                "T001",
                "--status",
                "done",
                "--mission",
                slug,
                "--json",
                "--no-auto-commit",
            ],
        )

    assert result.exit_code == 0, result.stdout
    status_dir = resolve_status_surface(repo, slug).parent
    stream = read_event_stream(status_dir)
    subtask_annotations = [
        annotation
        for annotation in stream.annotations
        if annotation.delta.subtasks is not None
    ]
    assert subtask_annotations[-1].delta.subtasks == {"T001": "done"}
    assert not (primary_dir / "status.events.jsonl").exists()


def _build_flat_mission(
    tmp_path: Path,
    slug: str,
    *,
    roster: list[str],
    snapshot_subtasks: dict[str, object] | None,
) -> Path:
    """Build a FLAT (single_branch) mission whose PRIMARY event log already has
    WP01 in ``in_progress`` and (optionally) a reduced ``subtasks`` snapshot slot.

    A flat mission has no coordination branch, so ``in_progress -> for_review``
    routes through ``emit_status_transition`` directly, exercising the
    ``resolve_subtasks_gate_dir`` inference branch in ``status/emit.py``. The
    PRIMARY dir carries BOTH the event log and the authored roster, so the whole
    frontmatter-roster + snapshot resolution runs against one surface.
    """
    mission_id = "01FLAT7654321098765432109"
    repo = _make_git_repo(tmp_path)
    primary_dir = repo / "kitty-specs" / slug
    primary_dir.mkdir(parents=True)
    (primary_dir / "meta.json").write_text(
        json.dumps(
            {"mission_id": mission_id, "mission_slug": slug, "topology": "single_branch"}
        ),
        encoding="utf-8",
    )
    _write_roster(primary_dir, "WP01", roster)
    _write_events(
        primary_dir,
        [
            _status_event(slug, "WP01", "planned", "claimed", "01HXYZ0123456789ABCDEFGH40"),
            _status_event(slug, "WP01", "claimed", "in_progress", "01HXYZ0123456789ABCDEFGH41"),
        ],
    )
    if snapshot_subtasks is not None:
        _seed_snapshot_subtasks(primary_dir, "WP01", snapshot_subtasks)
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "flat mission in_progress")
    return repo


def test_flat_mission_allows_when_snapshot_all_done(tmp_path: Path) -> None:
    """FR-016 allow: a flat mission whose PRIMARY snapshot marks every roster id
    DONE resolves completeness through ``resolve_subtasks_gate_dir`` -> allowed."""
    from specify_cli.status.models import Lane

    slug = "flat-allowed"
    repo = _build_flat_mission(
        tmp_path, slug, roster=["T001"], snapshot_subtasks={"T001": Lane.DONE}
    )

    result = _emit_for_review(repo, slug, implementation_evidence_present=True)

    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["from_lane"] == "in_progress"
    assert payload["to_lane"] == "for_review"


def test_flat_mission_blocks_when_snapshot_incomplete(tmp_path: Path) -> None:
    """The flat emit path is fail-closed: a roster id still not DONE in the PRIMARY
    snapshot -> blocked (no fail-open), proving the seam-resolved dir feeds the gate."""
    from specify_cli.status.models import Lane

    slug = "flat-blocked"
    repo = _build_flat_mission(
        tmp_path,
        slug,
        roster=["T001", "T002"],
        snapshot_subtasks={"T001": Lane.DONE, "T002": Lane.PLANNED},
    )

    result = _emit_for_review(repo, slug)

    assert result.exit_code != 0, result.stdout
    assert "completed subtasks" in result.stdout
