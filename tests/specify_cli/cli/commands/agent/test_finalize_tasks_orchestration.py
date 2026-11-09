"""Characterisation pins for the ``finalize_tasks`` orchestration (#7410).

Written against the pre-split entrypoint and kept green across the
Validate -> Settle -> Write phase split. Every collaborator the entrypoint
calls is replaced on the ``mission_finalize`` module by a recorder, so the
tests pin the orchestration only: which phases run in which mode, in what
order, with which inputs, and what the failure handlers undo. The phase
bodies keep their own end-to-end coverage (``test_finalize_topology_settlement``,
``test_finalize_atomicity``, ``test_issue_4141_refresh_planning_commit``).
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
import typer

from specify_cli.cli.commands.agent import mission_finalize as seam

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_SLUG = "probe-mission"


@dataclass
class Harness:
    """Recorder state shared by the fakes."""

    tmp: Path
    calls: list[str] = field(default_factory=list)
    kwargs: dict[str, dict[str, Any]] = field(default_factory=dict)
    history: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    raise_in: dict[str, BaseException] = field(default_factory=dict)
    outline_finishes: bool = False
    meta_persisted: bool = False
    land_commit: bool = False
    decision: object | None = "decision"
    scope: Any = None
    meta_reads: int = 0

    @property
    def planning_dir(self) -> Path:
        return self.tmp / "kitty-specs" / _SLUG

    @property
    def settled_dir(self) -> Path:
        return self.tmp / "settled" / _SLUG

    def record(self, name: str, **kwargs: Any) -> None:
        self.calls.append(name)
        self.kwargs[name] = kwargs
        self.history.setdefault(name, []).append(kwargs)
        error = self.raise_in.get(name)
        if error is not None:
            raise error


def _branch_setup(h: Harness) -> seam._FinalizeBranchSetup:
    return seam._FinalizeBranchSetup(
        target_branch="main",
        merge_target_branch="main",
        mission_write_scope_snapshot={h.planning_dir / "meta.json": b"{}"},
        mission_write_scope_dir=h.planning_dir,
        meta_path_for_revert=h.planning_dir / "meta.json",
        meta_original_text="{}",
        target_branch_persist=seam.TargetBranchPersistOutcome(persisted=h.meta_persisted),
        meta_json_persisted=h.meta_persisted,
        owned_derived_dir=None,
        owned_derived_snapshot={},
    )


def _install(monkeypatch: pytest.MonkeyPatch, h: Harness) -> None:
    def fake(name: str, result: Any = None) -> Any:
        def _fn(*args: Any, **kwargs: Any) -> Any:
            h.record(name, args=args, **kwargs)
            return result() if callable(result) else result

        return _fn

    ctx = SimpleNamespace(owned=None, repo_root=h.tmp, mission_slug=_SLUG, planning_dir=h.planning_dir)
    req_gates = SimpleNamespace(
        tasks_dir=h.planning_dir / "tasks",
        functional_spec_requirement_ids={"FR-001"},
        preexisting_primary_files={h.planning_dir / "spec.md"},
        dep_resolution="deps",
    )
    own_gates = SimpleNamespace(
        state="state",
        tasks_md_stale=False,
        wp_frontmatters={"WP01": "fm"},
        eligibility=SimpleNamespace(eligible_wp_ids=["WP01"], all_canceled=False),
        lane_wp_manifests={"WP01": "manifest"},
        lane_wp_dependencies={"WP01": []},
        lane_wp_bodies={"WP01": "body"},
    )

    def read_meta(planning_dir: Path) -> dict[str, object]:
        h.meta_reads += 1
        h.record("_read_meta_for_emission", planning_dir=planning_dir)
        return {"read": h.meta_reads, "dir": str(planning_dir)}

    def outline(*args: Any, **kwargs: Any) -> bool:
        h.record("_finish_outline_validation_if_applicable", **kwargs)
        return h.outline_finishes

    def pipeline(*args: Any, **kwargs: Any) -> None:
        h.record("_run_commit_pipeline", args=args, **kwargs)
        if h.land_commit:
            kwargs["commit_landed"].landed = True
        error = h.raise_in.get("_run_commit_pipeline_after")
        if error is not None:
            raise error

    def scope_entry(*args: Any, **kwargs: Any) -> Any:
        h.record("_enter_api_authored_finalize_scope", **kwargs)
        return h.scope

    monkeypatch.setattr(seam, "_resolve_finalize_context", fake("_resolve_finalize_context", ctx))
    monkeypatch.setattr(seam, "_enter_api_authored_finalize_scope", scope_entry)
    monkeypatch.setattr(seam, "_run_finalize_branch_setup", fake("_run_finalize_branch_setup", lambda: _branch_setup(h)))
    monkeypatch.setattr(seam, "_preserve_or_capture_planning_commit_sha", fake("_preserve_or_capture_planning_commit_sha", "pin"))
    monkeypatch.setattr(seam, "_preflight_refresh_planning_commit", fake("_preflight_refresh_planning_commit"))
    monkeypatch.setattr(seam, "_refresh_bootstrap_dry_run_or_refuse", fake("_refresh_bootstrap_dry_run_or_refuse", "bootstrap"))
    monkeypatch.setattr(seam, "_refresh_worktree_status_findings", fake("_refresh_worktree_status_findings", ["finding"]))
    monkeypatch.setattr(seam, "_run_finalize_validation_gates", fake("_run_finalize_validation_gates", req_gates))
    monkeypatch.setattr(seam, "_finish_outline_validation_if_applicable", outline)
    monkeypatch.setattr(seam, "_run_finalize_ownership_gates", fake("_run_finalize_ownership_gates", own_gates))
    monkeypatch.setattr(seam, "_read_meta_for_emission", read_meta)
    monkeypatch.setattr(seam, "_warn_missing_meta", fake("_warn_missing_meta"))
    monkeypatch.setattr(seam, "_decide_topology_by_size", fake("_decide_topology_by_size", lambda: h.decision))
    monkeypatch.setattr(seam, "_bind_topology_decision", fake("_bind_topology_decision"))
    monkeypatch.setattr(seam, "_preflight_frozen_lane_membership", fake("_preflight_frozen_lane_membership", "frozen"))
    monkeypatch.setattr(seam, "_settle_or_refuse", fake("_settle_or_refuse", SimpleNamespace(planning_dir=h.settled_dir)))
    monkeypatch.setattr(seam, "_emit_tasks_started", fake("_emit_tasks_started"))
    monkeypatch.setattr(seam, "_emit_validate_only_report", fake("_emit_validate_only_report"))
    monkeypatch.setattr(seam, "_require_refresh_pin_decision", fake("_require_refresh_pin_decision"))
    monkeypatch.setattr(seam, "_commit_planning_pin_refresh", fake("_commit_planning_pin_refresh"))
    monkeypatch.setattr(seam, "_run_commit_pipeline", pipeline)
    monkeypatch.setattr(seam, "_revert_unpersisted_target_branch_override", fake("_revert_unpersisted_target_branch_override", "revert-error"))
    monkeypatch.setattr(seam, "_undo_finalize_with_settlement", fake("_undo_finalize_with_settlement", ("leftover", [Path("kept")])))
    monkeypatch.setattr(seam, "_report_target_branch_revert_failure", fake("_report_target_branch_revert_failure"))
    monkeypatch.setattr(seam, "_report_status_surface_leftover", fake("_report_status_surface_leftover"))
    monkeypatch.setattr(seam, "_report_write_scope_kept", fake("_report_write_scope_kept"))
    monkeypatch.setattr(seam, "_emit_finalize_error_with_revert_note", fake("_emit_finalize_error_with_revert_note"))


@pytest.fixture
def harness(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Harness:
    h = Harness(tmp=tmp_path)
    _install(monkeypatch, h)
    return h


def _run(**flags: Any) -> None:
    seam.finalize_tasks(
        feature=_SLUG,
        json_output=True,
        validate_only=flags.get("validate_only", False),
        target_branch_override=None,
        owned_checkout=None,
        refresh_planning_commit=flags.get("refresh_planning_commit", False),
        allow_orphaned=flags.get("allow_orphaned", False),
    )


_VALIDATE = [
    "_resolve_finalize_context",
    "_enter_api_authored_finalize_scope",
    "_run_finalize_branch_setup",
    "_run_finalize_validation_gates",
    "_finish_outline_validation_if_applicable",
    "_run_finalize_ownership_gates",
    "_read_meta_for_emission",
    "_warn_missing_meta",
    "_decide_topology_by_size",
    "_bind_topology_decision",
    "_preflight_frozen_lane_membership",
]


# ---------------------------------------------------------------------------
# Mode routing: which phases run, in which order
# ---------------------------------------------------------------------------


def test_plain_run_validates_settles_then_writes(harness: Harness) -> None:
    _run()

    assert harness.calls == [
        *_VALIDATE,
        "_settle_or_refuse",
        "_read_meta_for_emission",
        "_bind_topology_decision",
        "_emit_tasks_started",
        "_run_commit_pipeline",
    ]
    pipeline = harness.kwargs["_run_commit_pipeline"]
    # The write phase runs on the settled PRIMARY location (FR-061).
    assert pipeline["args"][0] == harness.settled_dir
    assert pipeline["args"][1] == harness.settled_dir / "tasks"
    assert pipeline["args"][12] == {harness.settled_dir / "spec.md"}
    assert pipeline["args"][10] == {"read": 2, "dir": str(harness.settled_dir)}
    assert pipeline["planning_sha"] is None
    assert pipeline["frozen"] == "frozen"
    assert pipeline["validate_only"] is False
    assert harness.kwargs["_emit_tasks_started"]["planning_dir"] == harness.settled_dir
    assert harness.kwargs["_emit_tasks_started"]["validate_only"] is False


def test_bind_marks_provisional_then_settled(harness: Harness) -> None:
    _run()

    binds = [(call["args"][1], call["settled"], call["preview"]) for call in harness.history["_bind_topology_decision"]]
    assert binds == [("decision", False, False), ("decision", True, False)]


def test_no_decision_skips_settlement_but_still_starts_tasks(harness: Harness) -> None:
    harness.decision = None
    _run()

    assert "_settle_or_refuse" not in harness.calls
    assert harness.calls[-2:] == ["_emit_tasks_started", "_run_commit_pipeline"]
    assert harness.kwargs["_run_commit_pipeline"]["args"][0] == harness.planning_dir


def test_validate_only_previews_without_settling(harness: Harness) -> None:
    _run(validate_only=True)

    assert harness.calls == [*_VALIDATE, "_emit_tasks_started", "_emit_validate_only_report"]
    assert harness.kwargs["_bind_topology_decision"]["preview"] is True
    assert harness.kwargs["_emit_tasks_started"]["validate_only"] is True
    report = harness.kwargs["_emit_validate_only_report"]
    assert report["planning_sha"] is None
    assert report["frozen"] == "frozen"
    assert report["refresh_status_findings"] == []
    assert "owned" not in report


def test_refresh_run_commits_only_the_pin(harness: Harness) -> None:
    _run(refresh_planning_commit=True)

    assert harness.calls == [
        "_resolve_finalize_context",
        "_enter_api_authored_finalize_scope",
        "_run_finalize_branch_setup",
        "_preserve_or_capture_planning_commit_sha",
        "_preflight_refresh_planning_commit",
        "_refresh_bootstrap_dry_run_or_refuse",
        "_run_finalize_validation_gates",
        "_finish_outline_validation_if_applicable",
        "_run_finalize_ownership_gates",
        "_read_meta_for_emission",
        "_warn_missing_meta",
        "_bind_topology_decision",
        "_require_refresh_pin_decision",
        "_commit_planning_pin_refresh",
    ]
    assert harness.kwargs["_run_finalize_ownership_gates"]["validate_only"] is True
    assert harness.kwargs["_preserve_or_capture_planning_commit_sha"]["refresh_planning_commit"] is True
    commit = harness.kwargs["_commit_planning_pin_refresh"]
    assert commit["args"][4] == "pin"
    assert commit["args"][7] == "bootstrap"


def test_refresh_validate_only_reports_findings_without_preflight(harness: Harness) -> None:
    _run(refresh_planning_commit=True, validate_only=True)

    assert "_preflight_refresh_planning_commit" not in harness.calls
    assert "_refresh_bootstrap_dry_run_or_refuse" not in harness.calls
    assert "_emit_tasks_started" not in harness.calls
    report = harness.kwargs["_emit_validate_only_report"]
    assert report["planning_sha"] == "pin"
    assert report["refresh_status_findings"] == ["finding"]
    assert report["frozen"] is None


def test_outline_validation_stops_before_ownership_gates(harness: Harness) -> None:
    harness.outline_finishes = True
    _run()

    assert harness.calls[-1] == "_finish_outline_validation_if_applicable"


def test_persisted_meta_is_reread_before_the_commit_pipeline(harness: Harness) -> None:
    harness.meta_persisted = True
    _run()

    assert harness.calls[-3:] == ["_emit_tasks_started", "_read_meta_for_emission", "_run_commit_pipeline"]
    assert harness.kwargs["_run_commit_pipeline"]["args"][10] == {"read": 3, "dir": str(harness.settled_dir)}


def test_api_authored_scope_is_confirmed_after_a_landed_commit(harness: Harness) -> None:
    confirmed: list[object] = []
    harness.scope = SimpleNamespace(confirm=confirmed.append)
    _run()

    assert confirmed == [{"result": "success"}]


# ---------------------------------------------------------------------------
# Failure handling: what a refused run undoes
# ---------------------------------------------------------------------------


def test_settlement_refusal_undoes_without_a_settlement_handle(harness: Harness) -> None:
    harness.raise_in["_settle_or_refuse"] = typer.Exit(1)

    with pytest.raises(typer.Exit) as exit_info:
        _run()

    assert exit_info.value.exit_code == 1
    undo = harness.kwargs["_undo_finalize_with_settlement"]
    assert undo["args"][0] is None
    assert undo["args"][2] == {harness.planning_dir / "meta.json": b"{}"}
    assert undo["args"][3] == harness.planning_dir
    assert harness.calls[-3:] == ["_report_target_branch_revert_failure", "_report_status_surface_leftover", "_report_write_scope_kept"]
    assert harness.kwargs["_report_status_surface_leftover"]["args"] == ("leftover",)
    assert harness.kwargs["_report_write_scope_kept"]["args"] == ([Path("kept")],)
    assert "_emit_finalize_error_with_revert_note" not in harness.calls


def test_exception_after_settlement_undoes_the_settlement(harness: Harness) -> None:
    error = RuntimeError("boom")
    harness.raise_in["_run_commit_pipeline"] = error

    with pytest.raises(typer.Exit) as exit_info:
        _run()

    assert exit_info.value.exit_code == 1
    assert harness.kwargs["_undo_finalize_with_settlement"]["args"][0].planning_dir == harness.settled_dir
    emitted = harness.kwargs["_emit_finalize_error_with_revert_note"]
    assert emitted["args"] == (error, "revert-error")
    assert emitted["status_leftover"] == "leftover"
    assert emitted["kept_files"] == [Path("kept")]


def test_failure_after_a_landed_commit_undoes_nothing(harness: Harness) -> None:
    harness.land_commit = True
    harness.raise_in["_run_commit_pipeline_after"] = RuntimeError("late")

    with pytest.raises(typer.Exit):
        _run()

    assert "_undo_finalize_with_settlement" not in harness.calls
    assert "_revert_unpersisted_target_branch_override" in harness.calls
    emitted = harness.kwargs["_emit_finalize_error_with_revert_note"]
    assert emitted["status_leftover"] is None
    assert emitted["kept_files"] == []


def test_failure_before_branch_setup_reverts_nothing_recorded(harness: Harness) -> None:
    harness.raise_in["_resolve_finalize_context"] = typer.Exit(2)

    with pytest.raises(typer.Exit) as exit_info:
        _run()

    assert exit_info.value.exit_code == 2
    revert = harness.kwargs["_revert_unpersisted_target_branch_override"]
    assert revert["args"] == (None, None)
    assert revert["meta_json_persisted"] is False
    assert revert["written_text"] is None
    assert "_undo_finalize_with_settlement" not in harness.calls


def test_revert_receives_the_branch_setup_meta_snapshot(harness: Harness) -> None:
    harness.meta_persisted = True
    harness.raise_in["_run_finalize_validation_gates"] = typer.Exit(1)

    with pytest.raises(typer.Exit):
        _run()

    revert = harness.kwargs["_revert_unpersisted_target_branch_override"]
    assert revert["args"] == (harness.planning_dir / "meta.json", "{}")
    assert revert["meta_json_persisted"] is True
    assert revert["meta_commit_progress"].committed is False


# ---------------------------------------------------------------------------
# Phase helpers, directly (#7410)
# ---------------------------------------------------------------------------


def _validated(h: Harness, decision: object | None) -> seam._FinalizeValidated:
    req_gates = SimpleNamespace(tasks_dir=h.planning_dir / "tasks", preexisting_primary_files={h.planning_dir / "spec.md"})
    return seam._FinalizeValidated(
        req_gates=req_gates,
        own_gates=SimpleNamespace(lane_wp_manifests={}, lane_wp_dependencies={}, wp_frontmatters={}, lane_wp_bodies={}),
        meta={"m": 1},
        topology_decision=decision,
        frozen=None,
    )


def test_settle_phase_only_previews_under_validate_only(harness: Harness) -> None:
    ctx = SimpleNamespace(planning_dir=harness.planning_dir)
    undo = seam._FinalizeUndoState()

    settled = seam._finalize_settle_phase(ctx, _validated(harness, "decision"), undo, "main", validate_only=True, json_output=True)

    assert settled == seam._FinalizeSettled(
        planning_dir=harness.planning_dir,
        tasks_dir=harness.planning_dir / "tasks",
        preexisting_primary_files={harness.planning_dir / "spec.md"},
        meta={"m": 1},
    )
    assert undo.settlement is None
    assert "_settle_or_refuse" not in harness.calls


def test_settle_phase_records_the_settlement_before_rebasing(harness: Harness) -> None:
    ctx = SimpleNamespace(planning_dir=harness.planning_dir, repo_root=harness.tmp, mission_slug=_SLUG)
    undo = seam._FinalizeUndoState()
    harness.raise_in["_read_meta_for_emission"] = RuntimeError("meta unreadable")

    with pytest.raises(RuntimeError):
        seam._finalize_settle_phase(ctx, _validated(harness, "decision"), undo, "main", validate_only=False, json_output=True)

    assert undo.settlement is not None and undo.settlement.planning_dir == harness.settled_dir


def test_refresh_findings_read_the_owned_roots(harness: Harness) -> None:
    owned = SimpleNamespace(repository_root=Path("/repo"), owned_root=Path("/owned"))
    ctx = SimpleNamespace(owned=owned, repo_root=Path("/ignored"), mission_slug=_SLUG)

    assert seam._refresh_status_findings_for(ctx) == ["finding"]
    assert harness.kwargs["_refresh_worktree_status_findings"]["args"] == (Path("/repo"), Path("/owned"), _SLUG)


def test_meta_for_commit_rereads_only_a_persisted_override(harness: Harness) -> None:
    settled = seam._FinalizeSettled(planning_dir=harness.planning_dir, tasks_dir=harness.planning_dir, preexisting_primary_files=set(), meta={"m": 1})

    assert seam._meta_for_commit(settled, _branch_setup(harness)) == {"m": 1}
    harness.meta_persisted = True
    assert seam._meta_for_commit(settled, _branch_setup(harness)) == {"read": 1, "dir": str(harness.planning_dir)}


def test_undo_without_a_write_scope_only_reverts_meta(harness: Harness) -> None:
    undo = seam._FinalizeUndoState(branch_setup=dataclasses.replace(_branch_setup(harness), mission_write_scope_dir=None))
    ledger, ledger_token, observer_token = seam.begin_write_ledger()
    try:
        outcome = seam._undo_refused_finalize(undo, ledger)
    finally:
        seam.end_write_ledger(ledger_token, observer_token)

    assert outcome == seam._FinalizeUndoOutcome(revert_error="revert-error", status_leftover=None, kept_files=[])
    assert "_undo_finalize_with_settlement" not in harness.calls
