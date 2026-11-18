"""#7692 T013-T017: the retarget phase, the claim's status surface and the rollback, on real git.

``_phase_retarget_record`` is the first mutation inside the one rollback door. These tests drive
it directly through a minimal run (the real ``ConsolidationState``, snapshot and rollback
authority; nothing about git is mocked) on the #5783 fixtures, retargeting a Mission recorded
for ``main`` onto ``develop``:

* explicit ``lanes``: the record is written on the Mission branch AND on ``develop`` (root
  checkout), both post tips are recorded, ``committed`` is persisted, and a second call is a
  no-op (NFR-002);
* the claim's status surface follows ``develop``; ``main`` never enters the snapshot (squad A2);
* a refused ``develop`` commit is undone byte for byte and exits 1 into the door;
* the rollback authority undoes both commits and the re-baseline keeps the retarget, uncommitted;
* a Mission branch without ``meta.json`` gets no copy (only ``develop`` is written);
* attestations under a retarget land on ``develop`` (coordination-less) and stay on the
  coordination branch otherwise (orchestrator ruling (A)).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
import typer

from specify_cli.consolidation import executor, phase_advance, phase_claim, rollback, run_state
from specify_cli.consolidation.state import ConsolidationState, load_state, save_state
from specify_cli.lanes.persistence import read_lanes_json
from tests.terminus.conftest import CoordMission, build_coord_mission
from tests.terminus.lanes_fixture import build_lanes_mission

pytestmark = [pytest.mark.git_repo]

_AT = "2026-11-17T09:00:00+00:00"


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True).stdout.strip()


def _rev(repo: Path, ref: str) -> str:
    return _git(repo, "rev-parse", ref)


def _meta_on(m: CoordMission, ref: str) -> dict[str, Any]:
    loaded: dict[str, Any] = json.loads(_git(m.repo, "show", f"{ref}:kitty-specs/{m.slug}/meta.json"))
    return loaded


def _retarget_record(source: str = "main", to: str = "develop", *, committed: bool = False) -> dict[str, Any]:
    return {"from": source, "to": to, "actor": "operator", "at": _AT, "reason": "move the Mission to develop", "committed": committed}


def _run(m: CoordMission, *, retarget: dict[str, Any] | None = None) -> Any:
    """A minimal run over a fresh record retargeting to ``develop``, with the claim's snapshot taken."""
    manifest = read_lanes_json(m.feature_dir)
    assert manifest is not None
    manifest.target_branch = "develop"
    state = ConsolidationState(mission_id=m.mission_id, mission_slug=m.slug, target_branch="develop", wp_order=["WP01"])
    state.retarget = retarget if retarget is not None else _retarget_record()
    save_state(state, m.repo)
    run = SimpleNamespace(
        main_repo=m.repo,
        mission_slug=m.slug,
        canonical_id=m.mission_id,
        state=state,
        lanes_manifest=manifest,
        is_resume=False,
        own_pre_claim_moves={},
        coord_checkpoint=None,
    )
    run.coord_checkpoint = run_state._capture_coord_checkpoint(run)
    phase_claim._capture_snapshot_and_begin_attempt(run)
    return run


def _lanes_onto_develop(tmp_path: Path) -> CoordMission:
    m = build_lanes_mission(tmp_path, target_branch="main")
    _git(m.repo, "branch", "develop", "main")
    _git(m.repo, "checkout", "-q", "develop")
    return m


# --- explicit lanes ---------------------------------------------------------------------------


def test_lanes_retarget_writes_both_copies_and_records_both_moves(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    m = _lanes_onto_develop(tmp_path)
    run = _run(m)
    mission_before, develop_before, main_before = _rev(m.repo, m.coord_branch), _rev(m.repo, "develop"), _rev(m.repo, "main")

    phase_advance._phase_retarget_record(run)

    entry = {"from": "main", "to": "develop", "actor": "operator", "at": _AT, "reason": "move the Mission to develop"}
    for ref in (m.coord_branch, "develop"):
        meta = _meta_on(m, ref)
        assert meta["target_branch"] == "develop", ref
        assert meta["retarget_history"] == [entry], ref
        assert _git(m.repo, "log", "-1", "--format=%s", ref) == f"chore({m.slug}): retarget main -> develop"
        assert _git(m.repo, "show", "--name-only", "--format=", ref) == f"kitty-specs/{m.slug}/meta.json", "one file per commit"
    assert _rev(m.repo, f"{m.coord_branch}^") == mission_before
    assert _rev(m.repo, "develop^") == develop_before
    assert _rev(m.repo, "main") == main_before, "the old recorded target receives nothing"
    assert _git(m.repo, "status", "--porcelain", "--", f"kitty-specs/{m.slug}") == "", "the root checkout is clean on develop"

    persisted = load_state(m.repo, m.mission_id)
    assert persisted is not None and persisted.retarget is not None and persisted.retarget["committed"] is True
    assert persisted.post_mutation_refs == {m.coord_branch: _rev(m.repo, m.coord_branch), "develop": _rev(m.repo, "develop")}
    assert "Retarget recorded: main -> develop" in capsys.readouterr().out


def test_claim_status_surface_follows_the_new_target_and_main_is_never_snapshotted(tmp_path: Path) -> None:
    """Squad A2: on explicit lanes the status surface IS the target; a retarget reads it as ``develop``."""
    m = _lanes_onto_develop(tmp_path)
    run = _run(m)

    assert run.coord_checkpoint.ref == "develop"
    assert "main" not in run.state.pre_mutation_refs
    assert "main" not in run.state.unsettled_refs
    assert {"develop", m.coord_branch} <= set(run.state.pre_mutation_refs)


def test_claim_status_surface_without_a_retarget_is_the_recorded_target(tmp_path: Path) -> None:
    """Control: the mapping is the only reason ``main`` stays out of the snapshot."""
    m = _lanes_onto_develop(tmp_path)
    manifest = read_lanes_json(m.feature_dir)
    assert manifest is not None
    run = SimpleNamespace(
        main_repo=m.repo, mission_slug=m.slug, state=ConsolidationState(mission_id=m.mission_id, mission_slug=m.slug, target_branch="develop", wp_order=[])
    )
    checkpoint = run_state._capture_coord_checkpoint(run)
    assert checkpoint is not None and checkpoint.ref == "main"


def test_second_call_is_a_no_op(tmp_path: Path) -> None:
    """NFR-002: a resumed run re-enters the phase (even with ``committed`` true) and writes nothing twice."""
    m = _lanes_onto_develop(tmp_path)
    run = _run(m)
    phase_advance._phase_retarget_record(run)
    tips = (_rev(m.repo, m.coord_branch), _rev(m.repo, "develop"))

    phase_advance._phase_retarget_record(run)

    assert (_rev(m.repo, m.coord_branch), _rev(m.repo, "develop")) == tips
    assert len(_meta_on(m, "develop")["retarget_history"]) == 1


def test_no_retarget_is_a_no_op(tmp_path: Path) -> None:
    m = _lanes_onto_develop(tmp_path)
    run = _run(m)
    run.state.retarget = None
    tips = (_rev(m.repo, m.coord_branch), _rev(m.repo, "develop"))

    phase_advance._phase_retarget_record(run)

    assert (_rev(m.repo, m.coord_branch), _rev(m.repo, "develop")) == tips


def test_refused_new_target_commit_undoes_the_file_bytes_and_exits_into_the_door(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from specify_cli.git import bookkeeping_commit
    from specify_cli.git.commit_helpers import SafeCommitError

    m = _lanes_onto_develop(tmp_path)
    run = _run(m)
    meta_path = m.feature_dir / "meta.json"
    original = meta_path.read_bytes()
    develop_before = _rev(m.repo, "develop")

    def _refuse(**_kwargs: object) -> None:
        raise SafeCommitError("a hook rejected the commit")

    monkeypatch.setattr(bookkeeping_commit, "commit_merge_bookkeeping", _refuse)

    with pytest.raises(typer.Exit) as excinfo:
        phase_advance._phase_retarget_record(run)

    assert excinfo.value.exit_code == 1
    assert meta_path.read_bytes() == original
    assert _rev(m.repo, "develop") == develop_before
    persisted = load_state(m.repo, m.mission_id)
    assert persisted is not None and persisted.retarget is not None and persisted.retarget["committed"] is False
    assert "a hook rejected the commit" in capsys.readouterr().out


def test_dirty_meta_on_the_new_target_refuses_before_writing_it(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    m = _lanes_onto_develop(tmp_path)
    run = _run(m)
    meta_path = m.feature_dir / "meta.json"
    meta_path.write_text(meta_path.read_text(encoding="utf-8") + " ", encoding="utf-8")
    develop_before = _rev(m.repo, "develop")

    with pytest.raises(typer.Exit):
        phase_advance._phase_retarget_record(run)

    assert _rev(m.repo, "develop") == develop_before
    assert "uncommitted changes" in capsys.readouterr().out


def test_rollback_undoes_both_commits_and_the_rebaseline_keeps_the_retarget_uncommitted(tmp_path: Path) -> None:
    m = _lanes_onto_develop(tmp_path)
    run = _run(m)
    snapshot = dict(run.state.pre_mutation_refs)
    phase_advance._phase_retarget_record(run)

    executor._report_rollback(run, anchor_before=None)

    assert _rev(m.repo, "develop") == snapshot["develop"]
    assert _rev(m.repo, m.coord_branch) == snapshot[m.coord_branch]
    assert _meta_on(m, "develop")["target_branch"] == "main"
    assert json.loads((m.feature_dir / "meta.json").read_text(encoding="utf-8"))["target_branch"] == "main", "the checkout was resynced"
    persisted = load_state(m.repo, m.mission_id)
    assert persisted is not None
    assert persisted.retarget == _retarget_record(), "the re-baseline keeps the retarget, uncommitted"
    assert persisted.pre_mutation_refs == {}, "and is a real full-restore re-baseline"


def test_rebaseline_marks_a_committed_retarget_uncommitted() -> None:
    state = ConsolidationState(mission_id="M", mission_slug="m", target_branch="develop", wp_order=[])
    state.retarget = _retarget_record(committed=True)

    assert rollback.rebaseline_after_full_restore(state, ()) is True
    assert state.retarget == _retarget_record(committed=False)
    assert rollback.rebaseline_after_full_restore(state, ()) is False, "idempotent"


def test_abort_clears_the_whole_record_including_the_retarget(tmp_path: Path) -> None:
    from specify_cli.consolidation.state import clear_state

    state = ConsolidationState(mission_id="M", mission_slug="m", target_branch="develop", wp_order=[])
    state.retarget = _retarget_record()
    save_state(state, tmp_path)

    assert clear_state(tmp_path, "M") is True
    assert load_state(tmp_path, "M") is None


def test_lanes_fixture_lanes_never_touch_meta_so_the_mission_branch_commit_leaves_them_fresh(tmp_path: Path) -> None:
    """Risk pin (lane staleness): a lane that touched ``meta.json`` would go stale after the Mission-branch commit."""
    m = _lanes_onto_develop(tmp_path)
    mission_tip = _rev(m.repo, m.coord_branch)
    for lane in m.lane_branches.values():
        base = _git(m.repo, "merge-base", lane, mission_tip)
        assert f"kitty-specs/{m.slug}/meta.json" not in _git(m.repo, "diff", "--name-only", base, lane).splitlines()


# --- holders: a Mission branch without meta.json; coordination --------------------------------


def test_mission_branch_without_meta_gets_no_copy(tmp_path: Path) -> None:
    m = _lanes_onto_develop(tmp_path)
    _git(m.repo, "checkout", "-q", m.coord_branch)
    _git(m.repo, "rm", "-q", f"kitty-specs/{m.slug}/meta.json")
    _git(m.repo, "commit", "-qm", "drop the record from the mission branch")
    _git(m.repo, "checkout", "-q", "develop")
    run = _run(m)
    mission_before = _rev(m.repo, m.coord_branch)

    phase_advance._phase_retarget_record(run)

    assert _rev(m.repo, m.coord_branch) == mission_before
    assert _meta_on(m, "develop")["target_branch"] == "develop"


def test_coord_mission_writes_every_holder_and_keeps_the_coordination_status_surface(tmp_path: Path) -> None:
    """Explicit coord: the fixture's coordination (Mission) branch carries ``meta.json``, so the holder rule writes it too."""
    m = build_coord_mission(tmp_path)
    _git(m.repo, "branch", "develop", "main")
    _git(m.repo, "checkout", "-q", "develop")
    run = _run(m)
    main_before = _rev(m.repo, "main")

    assert run.coord_checkpoint.ref == m.coord_branch, "the mapping never touches a coordination branch"
    phase_advance._phase_retarget_record(run)

    assert _meta_on(m, m.coord_branch)["target_branch"] == "develop"
    assert _meta_on(m, "develop")["target_branch"] == "develop"
    assert _rev(m.repo, "main") == main_before


# --- attestations under a retarget (orchestrator ruling (A)) ----------------------------------


def test_attestation_lands_on_the_new_target_on_a_coordination_less_mission(tmp_path: Path) -> None:
    from specify_cli.consolidation.no_implementation_attestation import record_no_implementation_attestation

    m = _lanes_onto_develop(tmp_path)
    main_before, develop_before = _rev(m.repo, "main"), _rev(m.repo, "develop")

    event = record_no_implementation_attestation(
        repo_root=m.repo,
        feature_dir=m.feature_dir,
        mission_slug=m.slug,
        wp_id="WP01",
        current_lane="approved",
        reason="docs only",
        actor="operator",
        retarget=("main", "develop"),
    )

    assert event is not None
    assert _rev(m.repo, "main") == main_before, "the old recorded target receives nothing"
    assert _rev(m.repo, "develop") != develop_before
    assert "docs only" in _git(m.repo, "show", f"develop:kitty-specs/{m.slug}/status.events.jsonl")


def test_attestation_without_the_mapping_targets_the_recorded_target(tmp_path: Path) -> None:
    """Control: without ``retarget`` the door resolves the recorded ``main`` (the root checkout is on ``develop``)."""
    from specify_cli.coordination import status_transition
    from specify_cli.status import Lane, TransitionRequest

    m = _lanes_onto_develop(tmp_path)
    request = TransitionRequest(feature_dir=m.feature_dir, mission_slug=m.slug, wp_id="WP01", to_lane=Lane.APPROVED, actor="operator", repo_root=m.repo)
    identity, _available = status_transition._resolve_transaction_entry(request, m.slug)

    assert identity.destination_ref == "main"
    assert status_transition._retargeted_identity(identity, ("main", "develop")).destination_ref == "develop"
    assert status_transition._retargeted_identity(identity, None) is identity


def test_attestation_mapping_leaves_a_coordination_destination_alone(tmp_path: Path) -> None:
    from specify_cli.coordination import status_transition
    from specify_cli.status import Lane, TransitionRequest

    m = build_coord_mission(tmp_path)
    request = TransitionRequest(feature_dir=m.feature_dir, mission_slug=m.slug, wp_id="WP01", to_lane=Lane.APPROVED, actor="operator", repo_root=m.repo)
    identity, _available = status_transition._resolve_transaction_entry(request, m.slug)

    assert identity.destination_ref == m.coord_branch
    assert status_transition._retargeted_identity(identity, ("main", "develop")) is identity


def test_executor_threads_the_retarget_into_every_attestation_recorder(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from specify_cli.consolidation import approved_attestation, canceled_attestation, no_implementation_attestation

    seen: list[tuple[str, object]] = []
    monkeypatch.setattr(canceled_attestation, "validate_attestation_request", lambda wp_ids, *_a, **_k: tuple(wp_ids))
    monkeypatch.setattr(canceled_attestation, "record_canceled_superseded_attestation", lambda **kw: seen.append(("canceled", kw["retarget"])))
    monkeypatch.setattr(approved_attestation, "record_approved_reviewed_attestation", lambda **kw: seen.append(("approved", kw["retarget"])))
    monkeypatch.setattr(no_implementation_attestation, "record_no_implementation_attestation", lambda **kw: seen.append(("none", kw["retarget"])))
    monkeypatch.setattr(executor, "_resolve_merge_actor", lambda *_a: "operator")
    monkeypatch.setattr(executor, "placement_seam", lambda *_a: SimpleNamespace(read_dir=lambda _kind: tmp_path))
    from specify_cli.consolidation import done_bookkeeping

    monkeypatch.setattr(done_bookkeeping, "_resolve_merge_actor", lambda *_a: "operator")
    pair = ("main", "develop")

    executor._record_canceled_attestations(tmp_path, "m", wp_ids=("WP02",), reason="r", acceptably_canceled=frozenset({"WP02"}), retarget=pair)
    executor._record_approved_attestations(tmp_path, "m", {"WP01": "approved"}, "r", retarget=pair)
    executor._record_no_implementation_attestations(tmp_path, "m", {"WP03": "approved"}, "r", retarget=pair)

    assert seen == [("canceled", pair), ("approved", pair), ("none", pair)]


def test_run_retarget_pair_prefers_the_persisted_record(tmp_path: Path) -> None:
    assert executor._run_retarget_pair(tmp_path, "M", None) is None
    assert executor._run_retarget_pair(tmp_path, "M", _retarget_record(to="release")) == ("main", "release")
    state = ConsolidationState(mission_id="M", mission_slug="m", target_branch="develop", wp_order=[])
    state.retarget = _retarget_record()
    save_state(state, tmp_path)
    assert executor._run_retarget_pair(tmp_path, "M", _retarget_record(to="release")) == ("main", "develop")


def test_build_retarget_record(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(executor, "_resolve_merge_actor", lambda *_a: "operator")

    assert executor._build_retarget_record(tmp_path, None, None) is None
    assert executor._build_retarget_record(tmp_path, ("develop", "develop"), None) is None, "FR-012"
    record = executor._build_retarget_record(tmp_path, ("main", "develop"), None)
    assert record is not None
    assert {k: record[k] for k in ("from", "to", "actor", "committed")} == {"from": "main", "to": "develop", "actor": "operator", "committed": False}
    assert record["reason"] == "operator retarget via spec-kitty consolidate --target develop --retarget"
    assert record["at"]
    custom = executor._build_retarget_record(tmp_path, ("main", "develop"), "  release train  ")
    assert custom is not None and custom["reason"] == "release train"


# --- C-006: a commit-to-target single_branch Mission (T017 2b) ---------------------------------


def test_single_branch_commit_to_target_retarget_refuses_before_anything_moves(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Pinned outcome (T017 2b): REFUSED with ``RETARGET_WRITE_BRANCH_IS_RECORDED_TARGET``, nothing moves.

    The Mission's ``lanes.json`` names the recorded target ``main`` as its ``mission_branch``.
    Before this refusal existed the run was witnessed (WP03 probe, real executor) landing on
    ``develop`` with exit 0 and then DELETING ``main`` as the Mission's branch in its cleanup.
    """
    from tests.terminus.test_protected_target_preflight import _build_commit_to_target_single_branch

    from specify_cli.consolidation import preflight

    m = _build_commit_to_target_single_branch(tmp_path, "01M7692S")
    _git(m.repo, "branch", "develop", "main")
    _git(m.repo, "checkout", "-q", "develop")
    manifest = read_lanes_json(m.feature_dir)
    assert manifest is not None and manifest.mission_branch == "main"
    manifest.target_branch = "develop"
    tips = {b: _rev(m.repo, b) for b in ("main", "develop")}

    with pytest.raises(typer.Exit) as excinfo:
        executor._refuse_protected_status_target_or_continue(m.repo, m.slug, manifest, m.mission_id, retarget=True)

    assert excinfo.value.exit_code == 1
    assert preflight.RETARGET_WRITE_BRANCH_IS_RECORDED_TARGET in " ".join(capsys.readouterr().out.split())
    assert {b: _rev(m.repo, b) for b in ("main", "develop")} == tips
    assert load_state(m.repo, m.mission_id) is None, "no merge record is written"


# --- the mutate and the run record --------------------------------------------------------------


def test_retarget_mutate_dedupes_and_repairs_a_malformed_history() -> None:
    mutate = phase_advance._retarget_mutate(_retarget_record())
    meta: dict[str, Any] = {"target_branch": "main", "retarget_history": "garbage"}

    assert mutate(meta) is True
    assert meta["target_branch"] == "develop"
    assert [row["at"] for row in meta["retarget_history"]] == [_AT]
    assert mutate(meta) is False, "the same retarget is never recorded twice"

    later = phase_advance._retarget_mutate({**_retarget_record(), "at": "2026-11-18T09:00:00+00:00"})
    assert later(meta) is True, "a later retarget appends its own entry"
    assert len(meta["retarget_history"]) == 2


def test_retarget_mutate_adds_the_entry_when_the_target_already_reads_the_new_one() -> None:
    meta: dict[str, Any] = {"target_branch": "develop"}
    assert phase_advance._retarget_mutate(_retarget_record())(meta) is True
    assert len(meta["retarget_history"]) == 1


def test_load_or_create_merge_state_records_and_keeps_the_retarget(tmp_path: Path) -> None:
    from specify_cli.consolidation.resolve import _load_or_create_merge_state

    def _load(retarget: dict[str, Any] | None) -> tuple[ConsolidationState, bool]:
        return _load_or_create_merge_state(
            main_repo=tmp_path, mission_slug="m", canonical_id="M", target_branch="develop", wp_order=["WP01"], push_requested=False, retarget=retarget
        )

    state, is_resume = _load(_retarget_record())
    assert (is_resume, state.retarget) == (False, _retarget_record()), "a fresh record is born with it"

    state, is_resume = _load(None)
    assert (is_resume, state.retarget) == (True, _retarget_record()), "a resume keeps it; never overwritten with None"

    state, _ = _load(_retarget_record(to="release"))
    assert state.retarget == _retarget_record(), "a persisted retarget always wins"


def test_loaded_record_without_a_retarget_adopts_one_only_without_a_snapshot(tmp_path: Path) -> None:
    from specify_cli.consolidation.resolve import _load_or_create_merge_state

    save_state(ConsolidationState(mission_id="M", mission_slug="m", target_branch="develop", wp_order=["WP01"], pre_mutation_refs={"develop": "a1"}), tmp_path)
    kwargs: dict[str, Any] = {
        "main_repo": tmp_path,
        "mission_slug": "m",
        "canonical_id": "M",
        "target_branch": "develop",
        "wp_order": ["WP01"],
        "push_requested": False,
    }

    state, _ = _load_or_create_merge_state(**kwargs, retarget=_retarget_record())
    assert state.retarget is None, "a record describing an earlier attempt's branches never adopts one"

    state.pre_mutation_refs = {}
    save_state(state, tmp_path)
    state, _ = _load_or_create_merge_state(**kwargs, retarget=_retarget_record())
    assert state.retarget == _retarget_record(), "a re-baselined / zero-progress record adopts it"
    persisted = load_state(tmp_path, "M")
    assert persisted is not None and persisted.retarget == _retarget_record()


def test_persist_retarget_committed_is_idempotent(tmp_path: Path) -> None:
    state = ConsolidationState(mission_id="M", mission_slug="m", target_branch="develop", wp_order=[])
    run = SimpleNamespace(main_repo=tmp_path, state=state)

    phase_advance._persist_retarget_committed(run)  # no retarget: nothing to persist
    assert load_state(tmp_path, "M") is None

    state.retarget = _retarget_record()
    phase_advance._persist_retarget_committed(run)
    persisted = load_state(tmp_path, "M")
    assert persisted is not None and persisted.retarget is not None and persisted.retarget["committed"] is True


# --- review cycle 1: a retarget adopted by a re-baselined record moves its landing target ------


def test_adopted_retarget_moves_the_records_landing_target_and_drops_old_target_anchors(tmp_path: Path) -> None:
    """A snapshot-less record left by a plain run on ``main`` adopts the retarget AND its target (no landing on ``main``)."""
    from specify_cli.consolidation.resolve import _load_or_create_merge_state

    leftover = ConsolidationState(mission_id="M", mission_slug="m", target_branch="main", wp_order=["WP01"])
    leftover.pre_mutation_target_sha = "a" * 40  # a zero-progress record that froze the old target's tip
    leftover.pre_mutation_coord_ref, leftover.pre_mutation_coord_sha = "main", "a" * 40
    leftover.pre_interrupt_lane_tips = {"lane-a": "b" * 40}
    save_state(leftover, tmp_path)

    state, resumed = _load_or_create_merge_state(
        main_repo=tmp_path, mission_slug="m", canonical_id="M", target_branch="develop", wp_order=["WP01"], push_requested=False, retarget=_retarget_record()
    )

    assert resumed is True
    persisted = load_state(tmp_path, "M")
    assert persisted is not None
    for record in (state, persisted):
        assert record.target_branch == "develop"
        assert record.retarget == _retarget_record()
        assert record.pre_mutation_target_sha is None
        assert (record.pre_mutation_coord_ref, record.pre_mutation_coord_sha, record.pre_interrupt_lane_tips) == (None, None, {})


def test_adopted_retarget_keeps_a_coordination_anchor(tmp_path: Path) -> None:
    """On a coordination topology the anchor names the coordination branch, not the old target: it stays."""
    from specify_cli.consolidation.resolve import _load_or_create_merge_state

    leftover = ConsolidationState(mission_id="M", mission_slug="m", target_branch="main", wp_order=["WP01"])
    leftover.pre_mutation_coord_ref, leftover.pre_mutation_coord_sha = "kitty/mission-m", "c" * 40
    save_state(leftover, tmp_path)

    state, _ = _load_or_create_merge_state(
        main_repo=tmp_path, mission_slug="m", canonical_id="M", target_branch="develop", wp_order=["WP01"], push_requested=False, retarget=_retarget_record()
    )

    assert state.target_branch == "develop"
    assert (state.pre_mutation_coord_ref, state.pre_mutation_coord_sha) == ("kitty/mission-m", "c" * 40)


def _consolidate_in_process(m: CoordMission, *, target: str, retarget: bool, fail_merge_lanes: bool = False) -> subprocess.CompletedProcess[str]:
    """Drive the real executor entry (the CLI flag lands with WP02) in a fresh interpreter, like ``run_terminus``."""
    import sys

    from tests.terminus.conftest import _cli_env

    inject = "executor._phase_merge_lanes = _boom\n" if fail_merge_lanes else ""
    code = (
        "from pathlib import Path\n"
        "from specify_cli.consolidation import executor\n"
        "def _boom(run):\n    raise RuntimeError('injected failure')\n"
        f"{inject}"
        f"executor._run_lane_based_consolidation(Path('.'), {m.slug!r}, push=False, delete_branch=None, remove_worktree=None, "
        f"target_override={target!r}, retarget={retarget!r}, assume_yes=True)\n"
    )
    return subprocess.run([sys.executable, "-c", code], cwd=str(m.repo), env=_cli_env(m.home), capture_output=True, text=True, check=False, timeout=300)


def test_retarget_after_a_rebaselined_plain_run_lands_on_the_new_target(tmp_path: Path) -> None:
    """Review cycle 1: a plain run on ``release`` fails and is re-baselined; ``--target develop --retarget`` then lands on ``develop``."""
    m = build_lanes_mission(tmp_path, target_branch="release")
    failed = _consolidate_in_process(m, target="release", retarget=False, fail_merge_lanes=True)
    assert failed.returncode != 0 and "injected failure" in failed.stderr
    leftover = load_state(m.repo, m.mission_id)
    assert leftover is not None and leftover.target_branch == "release" and leftover.pre_mutation_refs == {}, "a re-baselined record is kept"

    _git(m.repo, "branch", "develop", "release")
    _git(m.repo, "checkout", "-q", "develop")
    release_before, develop_before = _rev(m.repo, "release"), _rev(m.repo, "develop")

    result = _consolidate_in_process(m, target="develop", retarget=True)

    assert result.returncode == 0, result.stdout + result.stderr
    assert _rev(m.repo, "release") == release_before, "the old recorded target never moves"
    subjects = _git(m.repo, "log", "--format=%s", f"{develop_before}..develop").splitlines()
    assert subjects[-1] == f"chore({m.slug}): retarget release -> develop", "the retarget commit is the first after the pre-run tip"
    assert subjects.count(f"chore({m.slug}): retarget release -> develop") == 1
    assert any("squash merge of mission" in subject for subject in subjects), "the landing is on develop"
    meta = _meta_on(m, "develop")
    assert meta["target_branch"] == "develop" and len(meta["retarget_history"]) == 1


# --- mission review LOW-2: a git error on the Mission-branch write is the named refusal -------


def test_a_hook_rejecting_the_mission_branch_commit_is_the_named_refusal(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    m = _lanes_onto_develop(tmp_path)
    run = _run(m)
    hook = m.repo / ".git" / "hooks" / "pre-commit"
    hook.parent.mkdir(parents=True, exist_ok=True)
    hook.write_text("#!/bin/sh\necho 'policy hook says no' >&2\nexit 1\n", encoding="utf-8")
    hook.chmod(0o755)
    tips = (_rev(m.repo, m.coord_branch), _rev(m.repo, "develop"))

    with pytest.raises(typer.Exit) as excinfo:
        phase_advance._phase_retarget_record(run)

    assert excinfo.value.exit_code == 1
    out = " ".join(capsys.readouterr().out.split())
    assert f"Error: Cannot record the retarget main -> develop: {m.coord_branch}:" in out, out
    assert "policy hook says no" in out, out
    assert (_rev(m.repo, m.coord_branch), _rev(m.repo, "develop")) == tips
    persisted = load_state(m.repo, m.mission_id)
    assert persisted is not None and persisted.retarget is not None and persisted.retarget["committed"] is False


def test_a_dirty_checkout_holding_the_mission_branch_is_the_named_refusal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from specify_cli.consolidation import meta_write
    from specify_cli.git.ref_advance import RefAdvanceDirtyWorktreeError

    m = _lanes_onto_develop(tmp_path)
    run = _run(m)

    def _dirty(_repo: Path, branch: str, new_sha: str, **_kwargs: object) -> None:
        raise RefAdvanceDirtyWorktreeError(worktree_path=m.repo / "wt", branch=branch, old_sha="a" * 40, new_sha=new_sha, dirty_entries=[" M x.py"])

    monkeypatch.setattr(meta_write, "advance_branch_ref", _dirty)

    with pytest.raises(typer.Exit) as excinfo:
        phase_advance._phase_retarget_record(run)

    assert excinfo.value.exit_code == 1
    out = " ".join(capsys.readouterr().out.split())
    assert f"Error: Cannot record the retarget main -> develop: {m.coord_branch}: Refusing to advance branch" in out, out


def test_rebaseline_drops_a_spent_attestation_undo_seed() -> None:
    """Review R2-a: the full restore undid the attestations the seed named; the seed is spent."""
    state = ConsolidationState(mission_id="M", mission_slug="m", target_branch="develop", wp_order=[])
    state.retarget = {**_retarget_record(committed=False), "attestation_undo": {"branch": "develop", "before": "b0", "after": "a1"}}

    assert rollback.rebaseline_after_full_restore(state, ()) is True
    assert state.retarget == _retarget_record(committed=False)
    assert rollback.rebaseline_after_full_restore(state, ()) is False, "idempotent"
