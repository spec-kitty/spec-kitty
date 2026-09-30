"""``spec-kitty retrospect create`` / ``backfill`` auto-commit on a coordination-topology mission.

On a ``coord`` / ``lanes_with_coord`` mission the canonical event log lives in the
git-ignored coordination worktree (``.worktrees/<slug>-coord/``), while the
retrospective record lives in the primary checkout. The auto-commit goes through
the STANDARD mission commit router (``commit_for_mission``, kind
``RETROSPECTIVE``), which splits the batch by partition: the event log is
committed on the coordination branch, the record on the mission's target branch.
A protected target branch (``main``) refuses the record with a warning; the event
log still reaches the coordination branch.

The fixture is a real coord mission (``build_coord_mission``: real ``git init``,
coordination branch, materialized coordination worktree). WP01 is walked to
``done`` through the production status seam and committed on the coordination
branch, as the done bookkeeping would be. Only the Zeitgeist fan-out is patched;
a generator fault is injected where no real coord fixture reaches the branch.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from specify_cli.cli.commands.retrospect import app as retrospect_app
from specify_cli.coordination.surface_resolver import resolve_status_surface
from specify_cli.coordination.workspace import CoordinationWorkspace
from specify_cli.status.emit import emit_status_transition
from tests.terminus.conftest import CoordMission, build_coord_mission
from tests.terminus.conftest import _git_out as git_out

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

RUNNER = CliRunner()
_FANOUT_EDGE = "specify_cli.retrospective.lifecycle_events._fanout_live_work_retrospective"
_DONE_EVIDENCE = {"review": {"reviewer": "reviewer-renata", "verdict": "approved", "reference": "review-WP01"}}
_UNPROTECTED_TARGET = "feature/retrospect-coord"
_COMPLETED_AT = "2026-04-27T09:00:00+00:00"
_WINDOW = ["--since", "2026-04-01", "--until", "2026-05-31"]


def _completed_coord_mission(tmp_path: Path, *, target_branch: str = "main") -> tuple[CoordMission, Path]:
    """A coord mission whose only WP is ``done`` on the coordination branch; returns (mission, coord worktree)."""
    mission = build_coord_mission(tmp_path, target_branch=target_branch)
    repo = mission.repo
    (repo / ".kittify").mkdir(exist_ok=True)
    (repo / ".kittify" / "config.yaml").write_text("auto_commit: true\n", encoding="utf-8")
    git_out(repo, "add", "--", ".kittify")
    git_out(repo, "commit", "-q", "-m", "chore: enable auto-commit")

    surface = resolve_status_surface(repo, mission.slug)
    coord_root = CoordinationWorkspace.worktree_path(repo, mission.slug, mission.mid8)
    assert surface.is_relative_to(coord_root), f"fixture must put the canonical event log in the coord worktree: {surface}"
    emit_status_transition(
        surface.parent,
        wp_id="WP01",
        to_lane="done",
        actor="reviewer-renata",
        evidence=_DONE_EVIDENCE,
        mission_slug=mission.slug,
        repo_root=repo,
        fan_out=False,
    )
    git_out(coord_root, "add", "--", f"kitty-specs/{mission.slug}/status.events.jsonl")
    git_out(coord_root, "commit", "-q", "-m", "chore: WP01 done")
    return mission, coord_root


def _run(repo: Path, monkeypatch: pytest.MonkeyPatch, *args: str) -> Any:
    monkeypatch.chdir(repo)
    with patch(_FANOUT_EDGE):
        return RUNNER.invoke(retrospect_app, [*args, "--json"])


def _run_create(repo: Path, slug: str, monkeypatch: pytest.MonkeyPatch) -> tuple[int, str, str]:
    result = _run(repo, monkeypatch, "create", "--mission", slug)
    return result.exit_code, result.stdout, result.stderr


def _event_types(jsonl: str) -> list[str]:
    return [str(json.loads(line).get("type", "")) for line in jsonl.splitlines() if line.strip()]


def _register_for_backfill(mission: CoordMission) -> None:
    """Register the mission, completed inside ``_WINDOW``, in the backfill registry."""
    registry = mission.repo / ".kittify" / "missions" / mission.mission_id
    registry.mkdir(parents=True)
    (registry / "meta.json").write_text(
        json.dumps({"mission_id": mission.mission_id, "mission_slug": mission.slug, "completed_at": _COMPLETED_AT}),
        encoding="utf-8",
    )


def test_create_commits_the_record_on_an_unprotected_target_and_the_log_on_the_coordination_branch(
    tmp_path: Path, canonical_home: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    mission, coord_root = _completed_coord_mission(tmp_path, target_branch=_UNPROTECTED_TARGET)
    repo = mission.repo
    record_rel = f"kitty-specs/{mission.slug}/retrospective.yaml"
    events_rel = f"kitty-specs/{mission.slug}/status.events.jsonl"
    message = f"chore(retrospective): author retrospective for {mission.slug}"
    target_before = git_out(repo, "rev-parse", _UNPROTECTED_TARGET)
    coord_before = git_out(repo, "rev-parse", mission.coord_branch)

    exit_code, stdout, stderr = _run_create(repo, mission.slug, monkeypatch)

    assert exit_code == 0, stderr
    assert json.loads(stdout)["result"] == "success"
    assert stderr == ""
    # One commit on the target branch, carrying only the record, byte-identical to the file on disk.
    assert git_out(repo, "log", "--format=%s", f"{target_before}..{_UNPROTECTED_TARGET}") == message
    assert git_out(repo, "show", "--name-only", "--format=", _UNPROTECTED_TARGET) == record_rel
    assert git_out(repo, "show", f"{_UNPROTECTED_TARGET}:{record_rel}") == (repo / record_rel).read_text(encoding="utf-8").strip()
    assert git_out(repo, "status", "--porcelain", "--", record_rel) == ""
    # One commit on the coordination branch, carrying only the event log.
    assert git_out(repo, "log", "--format=%s", f"{coord_before}..{mission.coord_branch}") == message
    assert git_out(repo, "show", "--name-only", "--format=", mission.coord_branch) == events_rel
    assert git_out(coord_root, "status", "--porcelain", "--", events_rel) == ""


def test_create_on_a_protected_target_commits_the_log_and_warns_about_the_record(tmp_path: Path, canonical_home: None, monkeypatch: pytest.MonkeyPatch) -> None:
    mission, coord_root = _completed_coord_mission(tmp_path)
    repo = mission.repo
    record_rel = f"kitty-specs/{mission.slug}/retrospective.yaml"
    events_rel = f"kitty-specs/{mission.slug}/status.events.jsonl"
    main_before = git_out(repo, "rev-parse", "main")

    exit_code, stdout, stderr = _run_create(repo, mission.slug, monkeypatch)

    assert exit_code == 0, stderr
    assert json.loads(stdout)["result"] == "success"
    # The protected target refused the record: main did not move, the record is untracked,
    # and stderr says why, naming the record (and only the record).
    assert git_out(repo, "rev-parse", "main") == main_before
    assert git_out(repo, "status", "--porcelain", "--", record_rel) == f"?? {record_rel}"
    warning = " ".join(stderr.split())
    assert "target branch 'main' is protected" in warning
    assert "commit it from a feature branch (never the coordination branch) and land it through a pull request" in warning
    assert "mission branch" not in warning
    assert str(repo / record_rel) in stderr.replace("\n", "")
    assert "status.events.jsonl" not in warning
    # The event log still reached the coordination branch.
    assert git_out(repo, "log", "-1", "--format=%s", mission.coord_branch) == f"chore(retrospective): author retrospective for {mission.slug}"
    assert git_out(coord_root, "status", "--porcelain", "--", events_rel) == ""


def test_create_writes_and_commits_the_captured_event_on_the_coordination_branch(tmp_path: Path, canonical_home: None, monkeypatch: pytest.MonkeyPatch) -> None:
    mission, coord_root = _completed_coord_mission(tmp_path)
    repo = mission.repo
    events_rel = f"kitty-specs/{mission.slug}/status.events.jsonl"
    primary_log_before = (repo / events_rel).read_text(encoding="utf-8")

    exit_code, stdout, stderr = _run_create(repo, mission.slug, monkeypatch)

    assert exit_code == 0, stderr
    record_path = json.loads(stdout)["record_path"]
    # The canonical (coordination) event log gained exactly one RetrospectiveCaptured row, and the
    # coordination branch carries it.
    committed_coord_log = git_out(repo, "show", f"{mission.coord_branch}:{events_rel}")
    assert _event_types(committed_coord_log).count("RetrospectiveCaptured") == 1
    captured = json.loads(committed_coord_log.splitlines()[-1])
    assert captured["type"] == "RetrospectiveCaptured"
    assert captured["record_path"] == record_path
    assert git_out(coord_root, "status", "--porcelain", "--", events_rel) == ""
    # Nothing was stranded in the primary checkout's copy of the log.
    assert (repo / events_rel).read_text(encoding="utf-8") == primary_log_before
    assert git_out(repo, "status", "--porcelain", "--", events_rel) == ""


def test_backfill_writes_and_commits_the_captured_event_on_the_coordination_branch(tmp_path: Path, canonical_home: None, monkeypatch: pytest.MonkeyPatch) -> None:
    mission, coord_root = _completed_coord_mission(tmp_path, target_branch=_UNPROTECTED_TARGET)
    repo = mission.repo
    _register_for_backfill(mission)
    record_rel = f"kitty-specs/{mission.slug}/retrospective.yaml"
    events_rel = f"kitty-specs/{mission.slug}/status.events.jsonl"
    message = f"chore(retrospective): backfill retrospective for {mission.slug}"
    primary_log_before = (repo / events_rel).read_text(encoding="utf-8")
    target_before = git_out(repo, "rev-parse", _UNPROTECTED_TARGET)
    coord_before = git_out(repo, "rev-parse", mission.coord_branch)

    result = _run(repo, monkeypatch, "backfill", *_WINDOW)

    assert result.exit_code == 0, result.output
    report = json.loads(result.stdout)
    assert report["created"] == 1, report
    assert result.stderr == ""
    # The coordination branch carries exactly one RetrospectiveCaptured row, in one commit.
    committed_coord_log = git_out(repo, "show", f"{mission.coord_branch}:{events_rel}")
    assert _event_types(committed_coord_log).count("RetrospectiveCaptured") == 1
    assert json.loads(committed_coord_log.splitlines()[-1])["provenance_kind"] == "backfill"
    assert git_out(repo, "log", "--format=%s", f"{coord_before}..{mission.coord_branch}") == message
    assert git_out(coord_root, "status", "--porcelain", "--", events_rel) == ""
    # The record reached the target branch in one commit.
    assert git_out(repo, "log", "--format=%s", f"{target_before}..{_UNPROTECTED_TARGET}") == message
    assert git_out(repo, "show", "--name-only", "--format=", _UNPROTECTED_TARGET) == record_rel
    # The primary checkout's copy of the log is untouched.
    assert (repo / events_rel).read_text(encoding="utf-8") == primary_log_before
    assert git_out(repo, "status", "--porcelain", "--", events_rel) == ""


def test_backfill_emit_skipped_appends_to_the_coordination_log(tmp_path: Path, canonical_home: None, monkeypatch: pytest.MonkeyPatch) -> None:
    mission, coord_root = _completed_coord_mission(tmp_path, target_branch=_UNPROTECTED_TARGET)
    repo = mission.repo
    events_rel = f"kitty-specs/{mission.slug}/status.events.jsonl"
    assert _run(repo, monkeypatch, "create", "--mission", mission.slug).exit_code == 0
    _register_for_backfill(mission)
    primary_log_before = (repo / events_rel).read_text(encoding="utf-8")

    result = _run(repo, monkeypatch, "backfill", "--emit-skipped", *_WINDOW)

    assert result.exit_code == 0, result.output
    (skip,) = json.loads(result.stdout)["skipped"]
    assert skip["reason"] == "already_exists"
    coord_log = (coord_root / events_rel).read_text(encoding="utf-8")
    assert _event_types(coord_log).count("RetrospectiveSkipped") == 1
    assert (repo / events_rel).read_text(encoding="utf-8") == primary_log_before


@pytest.mark.parametrize(
    ("fault", "category"),
    [(FileNotFoundError("tasks.md vanished"), "missing_artifacts"), (RuntimeError("generator crashed"), "generator_exception")],
    ids=["missing-artifacts", "generator-crash"],
)
def test_backfill_emit_failures_appends_to_the_coordination_log(
    tmp_path: Path, canonical_home: None, monkeypatch: pytest.MonkeyPatch, fault: Exception, category: str
) -> None:
    """Injected: no real coord mission makes the deterministic generator fail."""
    mission, coord_root = _completed_coord_mission(tmp_path, target_branch=_UNPROTECTED_TARGET)
    repo = mission.repo
    events_rel = f"kitty-specs/{mission.slug}/status.events.jsonl"
    _register_for_backfill(mission)
    primary_log_before = (repo / events_rel).read_text(encoding="utf-8")

    with patch("specify_cli.cli.commands.retrospect.generate_retrospective", side_effect=fault):
        result = _run(repo, monkeypatch, "backfill", "--emit-failures", *_WINDOW)

    assert result.exit_code == 0, result.output
    (failure,) = json.loads(result.stdout)["failed"]
    assert failure["failure_category"] == category
    coord_rows = [json.loads(line) for line in (coord_root / events_rel).read_text(encoding="utf-8").splitlines() if line.strip()]
    (row,) = [r for r in coord_rows if r.get("type") == "RetrospectiveCaptureFailed"]
    assert row["failure_category"] == category
    assert (repo / events_rel).read_text(encoding="utf-8") == primary_log_before
