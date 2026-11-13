"""Parity of the three claim-input sources (FR-012, FR-013, CI-1..CI-3; WP09).

The forecast (``LIVE``), the fresh run (``LIVE_THEN_SAVED``) and the resume (``SAVED``) obtain their
claim inputs from ONE constructor, :func:`specify_cli.consolidation.claim_inputs.claim_inputs`, and
build the claim through ONE adapter, :func:`~specify_cli.consolidation.claim_inputs.build_claim`.

The integration tests observe the :class:`ClaimInputs` each real ``consolidate`` run hands to
``build_claim`` (the call site's binding is replaced by a spy that records the value and stops the
run before anything moves). Equality follows FR-013: refs compare by resolved SHA, ``status_dir`` by
resolved path and event-log digest. WP17 aligned the forecast's excluded canceled set and coordination
base with the fresh run's (FR-013); each was a strict ``xfail`` here until its fix commit.

A fixture that cannot reach the claim raises :class:`FixtureNotReached` (a ``RuntimeError``), so a
broken fixture ERRORS a strict ``xfail(raises=AssertionError)`` test instead of hiding behind it.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import replace
from collections.abc import Iterator, Mapping
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any, cast

import pytest

from charter.hasher import hash_content
from specify_cli.consolidation import claim_inputs as ci
from specify_cli.consolidation import forecast, phase_claim, phase_gate, status_surface
from specify_cli.consolidation.claim_inputs import ClaimInputContext, ClaimInputs, ClaimInputSource, claim_inputs
from specify_cli.consolidation.config import MergeStrategy
from specify_cli.consolidation.rollback import capture_pre_mutation_snapshot, rebaseline_after_full_restore
from specify_cli.consolidation.state import ConsolidationState
from specify_cli.lanes.compute import lane_created_branch
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from tests.consolidation import characterization_support as cs
from tests.consolidation.characterization_support import DEP_BRANCH, ShapeMission, lane_checkout
from tests.terminus.canceled_dependency_support import _commit_in

_FULL_SHA = re.compile(r"[0-9a-f]{40}")
_STATUS_EVENTS = "status.events.jsonl"


class FixtureNotReached(RuntimeError):
    """The run never reached ``build_claim``: a fixture problem, never the asserted divergence."""


class _ClaimInputsSeen(Exception):
    """Raised by the spy right after it recorded the inputs, so the run stops before any branch moves."""


# --------------------------------------------------------------------------- helpers


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True).stdout.strip()


def _ref_sha(repo: Path, ref: str) -> str:
    """A ref name or SHA resolved to its commit SHA (FR-013 compares refs by resolved SHA)."""
    return _git(repo, "rev-parse", "--verify", f"{ref}^{{commit}}")


def _status_dir_identity(path: Path) -> tuple[Path, str]:
    """``(resolved path, sha256 of the event log)``: the FR-013 identity of a status directory."""
    return path.resolve(), hash_content((path / _STATUS_EVENTS).read_text(encoding="utf-8"))


def _captured_inputs(mission: ShapeMission, mode: str, consumer: ModuleType, *extra: str) -> ClaimInputs:
    """The :class:`ClaimInputs` a real ``consolidate`` of *mode* hands to *consumer*'s ``build_claim``."""
    seen: list[ClaimInputs] = []

    def _spy(_repo_root: Path, _manifest: LanesManifest, inputs: ClaimInputs) -> Any:
        seen.append(inputs)
        raise _ClaimInputsSeen

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(consumer, "build_claim", _spy)
        result = cs.run_in_process(mission, cs.consolidate_args(mission, mode, *extra))
    if not seen:
        raise FixtureNotReached(f"the {mode} run never built its claim inputs:\n{result.output}")
    return seen[0]


def _forecast_and_fresh(mission: ShapeMission, *extra: str) -> tuple[ClaimInputs, ClaimInputs]:
    """Both captures on one unmutated Mission: the forecast first (it moves nothing), then the fresh run."""
    live = _captured_inputs(mission, "forecast", forecast, *extra)
    fresh = _captured_inputs(mission, "fresh", phase_claim, *extra)
    if live.source is not ClaimInputSource.LIVE or fresh.source is not ClaimInputSource.LIVE_THEN_SAVED:
        raise FixtureNotReached(f"unexpected sources: forecast {live.source}, fresh run {fresh.source}")
    return live, fresh


def _approved(tmp: Path, shape: str) -> ShapeMission:
    mission = cs.build_shape(tmp, shape)
    cs.apply_stamp(mission, "present")
    cs.set_window_states(mission, "recorded")
    return mission


@pytest.fixture(scope="module")
def templates(tmp_path_factory: pytest.TempPathFactory) -> dict[str, ShapeMission]:
    return {shape: _approved(tmp_path_factory.mktemp(shape), shape) for shape in ("dependency_chain", "single_lane", "mixed_lane_canceled_wp")}


@pytest.fixture
def chain(templates: dict[str, ShapeMission], tmp_path: Path) -> ShapeMission:
    return cs.copy_mission(templates["dependency_chain"], tmp_path / "chain")


def _with_dependency_ref(mission: ShapeMission, scratch: Path) -> ShapeMission:
    """An external branch merged into the lane and the lane re-approved (the #6771 model, as the corpus builds it)."""
    from tests.terminus.conftest import restamp_approvals_at_lane_tips

    repo = mission.repo
    root_commit = _git(repo, "rev-list", "--max-parents=0", mission.target_branch)
    _git(repo, "branch", DEP_BRANCH, root_commit)
    dep_wt = scratch / "dep-wt"
    _git(repo, "worktree", "add", "-q", str(dep_wt), DEP_BRANCH)
    _commit_in(dep_wt, "src/dep/mod0.py", "DEP = 0\n", "feat(dep): mod0")
    _git(repo, "worktree", "remove", str(dep_wt))
    with lane_checkout(mission, mission.lane_branches["WP01"]) as lane:
        _git(lane, "merge", "-q", "--no-ff", "--no-edit", DEP_BRANCH)
    restamp_approvals_at_lane_tips(mission.coord_mission())
    return mission


# --------------------------------------------------------------------------- LIVE and LIVE_THEN_SAVED agree


def test_live_and_live_then_saved_agree_on_target_base(chain: ShapeMission) -> None:
    live, fresh = _forecast_and_fresh(chain)

    assert live.target_base is not None and fresh.target_base is not None
    assert _ref_sha(chain.repo, live.target_base) == _ref_sha(chain.repo, fresh.target_base)


def test_live_and_live_then_saved_agree_on_dependency_anchors(chain: ShapeMission) -> None:
    live, fresh = _forecast_and_fresh(chain)

    assert live.dependency_anchors, "the chain's dependency lane must be an anchor"
    assert dict(live.dependency_anchors) == dict(fresh.dependency_anchors)


def test_live_and_live_then_saved_agree_on_dependency_refs_and_pins(templates: dict[str, ShapeMission], tmp_path: Path) -> None:
    mission = _with_dependency_ref(cs.copy_mission(templates["single_lane"], tmp_path / "m"), tmp_path)
    live, fresh = _forecast_and_fresh(mission, "--dependency-ref", DEP_BRANCH)

    assert live.dependency_refs == fresh.dependency_refs == (DEP_BRANCH,)
    assert {r: _ref_sha(mission.repo, s) for r, s in live.dependency_pins.items()} == {r: _ref_sha(mission.repo, s) for r, s in fresh.dependency_pins.items()}


def test_live_and_live_then_saved_agree_on_strategy(chain: ShapeMission) -> None:
    live, fresh = _forecast_and_fresh(chain)

    assert live.strategy == fresh.strategy == MergeStrategy.SQUASH.value


def test_saved_reads_the_persisted_record(chain: ShapeMission) -> None:
    """A resume after a SIGKILL right after the claim anchors were saved reads every value from ``state.json``."""
    record = cs.interrupt_after_claim(chain)
    frozen = record.get("pre_interrupt_lane_tips")
    if not frozen or not record.get("pre_mutation_coord_sha"):
        raise FixtureNotReached(f"the interrupted record must hold frozen anchors: {sorted(record)}")

    saved = _captured_inputs(chain, "resume", phase_claim)

    assert saved.source is ClaimInputSource.SAVED
    assert saved.target_base == record["pre_mutation_target_sha"]
    assert saved.coord_base == record["pre_mutation_coord_sha"]
    assert saved.dependency_anchors, "the chain's dependency lane must be frozen as an anchor"
    assert set(saved.dependency_anchors) <= set(frozen), "dependency_anchors share the key space of pre_interrupt_lane_tips"
    assert all(frozen[branch] == sha for branch, sha in saved.dependency_anchors.items()), "the anchors are the frozen tips"
    assert saved.strategy == record["strategy"]
    assert saved.dependency_refs == tuple(record.get("dependency_refs", ()))
    assert dict(saved.dependency_pins) == record.get("dependency_ref_pins", {})


# --------------------------------------------------------------------------- the divergences WP17 aligned


def test_forecast_excluded_canceled_set_equals_fresh_run(templates: dict[str, ShapeMission], tmp_path: Path) -> None:
    mission = cs.copy_mission(templates["mixed_lane_canceled_wp"], tmp_path / "m")
    live, fresh = _forecast_and_fresh(mission)
    if not fresh.excluded_canceled_wp_ids:
        raise FixtureNotReached("the mixed lane's canceled work package must be excluded by the fresh run")

    assert live.excluded_canceled_wp_ids == fresh.excluded_canceled_wp_ids


def test_forecast_coord_base_resolves_to_fresh_run_sha(chain: ShapeMission) -> None:
    live, fresh = _forecast_and_fresh(chain)
    if not _FULL_SHA.fullmatch(fresh.coord_base):
        raise FixtureNotReached(f"the fresh run must build from a coordination SHA, it used {fresh.coord_base!r}")

    assert _FULL_SHA.fullmatch(live.coord_base), f"the forecast must pass a resolved SHA, it passed {live.coord_base!r}"
    assert live.coord_base == fresh.coord_base


def test_forecast_status_dir_equals_fresh_run(chain: ShapeMission) -> None:
    """Not a divergence on a Mission whose coordination worktree holds its log (WP09 finding; planned as a strict ``xfail``, it passed).

    The forecast reads through the status read door (``_forecast_claim_status_dir``), the fresh run
    through the write accessor (``entry_preflight._resolve_run_status_dir``). They can resolve different
    directories only when the coordination worktree is empty or unmaterialized:

    * the coordination branch already carries the log (post-fix): the door is ref-sourced, so the
      forecast refuses with ``CLAIM_REFUSED_FORECAST`` before it builds any claim;
    * the branch holds no log yet (pre-fix): the door takes its declared pre-seed fallback, so the
      forecast builds its claim from the write checkout while the fresh run seeds and reads the
      coordination worktree. Same log bytes, another directory: a named legacy residual pinned in
      ``test_forecast_fresh_run_parity.py``.
    """
    live, fresh = _forecast_and_fresh(chain)

    assert _status_dir_identity(live.status_dir) == _status_dir_identity(fresh.status_dir)


# --------------------------------------------------------------------------- unit: the adapter passes today's keyword arguments

_REPO = Path("/repo")
_STATUS = Path("/repo/kitty-specs/m")
_MISSION_BRANCH = "kitty/mission-m-01ABCDEF"
_TARGET = "a" * 40
_COORD = "c" * 40
_CHECKPOINT = "d" * 40
_REFS = ("dep-branch",)
_PINS = {"dep-branch": "e" * 40}
_EXCLUDED = frozenset({"WP09"})
_COORD_REF = "kitty/mission-m-01ABCDEF-coord"


def _manifest() -> LanesManifest:
    lane = ExecutionLane(lane_id="lane-a", wp_ids=("WP01",), write_scope=("src/**",), predicted_surfaces=(), depends_on_lanes=(), parallel_group=0)
    lane_b = ExecutionLane(lane_id="lane-b", wp_ids=("WP02",), write_scope=("lib/**",), predicted_surfaces=(), depends_on_lanes=("lane-a",), parallel_group=1)
    return LanesManifest(
        version=1,
        mission_slug="m-01ABCDEF",
        mission_id="01ABCDEF" + "0" * 18,
        mission_branch=_MISSION_BRANCH,
        target_branch="main",
        lanes=[lane, lane_b],
        computed_at="2026-11-09T00:00:00+00:00",
        computed_from="test",
    )


_LANE_A = lane_created_branch(_manifest(), "lane-a")
_LANE_B = lane_created_branch(_manifest(), "lane-b")


def _state() -> ConsolidationState:
    state = ConsolidationState(mission_id="m", mission_slug="m", target_branch="main", wp_order=[])
    state.pre_mutation_target_sha = _TARGET
    state.pre_mutation_coord_sha = _COORD
    state.pre_interrupt_lane_tips = {_LANE_A: "1" * 40, _LANE_B: "2" * 40}
    state.strategy = "merge"
    state.dependency_refs = list(_REFS)
    state.dependency_ref_pins = dict(_PINS)
    return state


def _context(**overrides: Any) -> ClaimInputContext:
    values: dict[str, Any] = {
        "repo_root": _REPO,
        "manifest": _manifest(),
        "status_dir": _STATUS,
        "strategy": "squash",
        "resolved_target_base": _TARGET,
        "resolved_coord_sha": _COORD,
        "checkpoint_sha": _CHECKPOINT,
        "state": _state(),
        "dependency_refs": _REFS,
        "dependency_pins": _PINS,
        "excluded_canceled_wp_ids": _EXCLUDED,
    }
    values.update(overrides)
    return ClaimInputContext(**values)


@pytest.fixture
def recorded(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[tuple[tuple[Any, ...], dict[str, Any]]]]:
    """Record every call ``claim_inputs`` makes to the builder; no git is read (tips resolve to nothing)."""
    calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []
    monkeypatch.setattr(ci, "build_approved_wp_set", lambda *a, **k: calls.append((a, k)) or "claim")
    monkeypatch.setattr(ci, "capture_branch_tip", lambda _repo, branch: f"tip-of-{branch}")
    monkeypatch.setattr(ci, "acceptably_canceled_wp_ids", lambda _repo, _slug: set(_EXCLUDED))
    monkeypatch.setattr(status_surface, "status_surface_ref", lambda _repo, _slug: _COORD_REF)
    monkeypatch.setattr(status_surface, "run_command", lambda cmd, **_k: (0, f"{_COORD}\n", "") if cmd == ["git", "rev-parse", _COORD_REF] else (1, "", "unknown"))
    yield calls


def _normalized(kwargs: Mapping[str, Any]) -> dict[str, Any]:
    """Keyword arguments with the builder's defaults filled in (an omitted excluded set is the default ``()``)."""
    out = dict(kwargs)
    out["excluded_canceled_wp_ids"] = frozenset(out.get("excluded_canceled_wp_ids", ()))
    out["external_dependency_pins"] = dict(out.get("external_dependency_pins") or {})
    out["external_dependency_refs"] = tuple(out.get("external_dependency_refs", ()))
    frozen = out.get("frozen_dependency_tips")
    out["frozen_dependency_tips"] = dict(frozen) if frozen is not None else None
    return out


def test_fresh_run_coord_base_falls_back_to_checkpoint_then_mission_branch(recorded: list[Any]) -> None:
    """``coord_base_sha or checkpoint.sha or mission_branch``, exactly as ``_capture_reconciliation_claim`` resolved it."""
    assert claim_inputs(ClaimInputSource.LIVE_THEN_SAVED, _context(resolved_coord_sha=None)).coord_base == _CHECKPOINT
    assert claim_inputs(ClaimInputSource.LIVE_THEN_SAVED, _context(resolved_coord_sha=None, checkpoint_sha=None)).coord_base == _MISSION_BRANCH


def test_live_reads_lane_tips_live_and_derives_dependency_anchors(recorded: list[Any], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ci, "acceptably_canceled_wp_ids", lambda _repo, _slug: set())
    inputs = claim_inputs(ClaimInputSource.LIVE, _context(state=None))

    assert dict(inputs.dependency_anchors) == {_LANE_A: f"tip-of-{_LANE_A}"}, "lane-b depends on lane-a, nothing depends on lane-b"


@pytest.mark.parametrize(("slug", "expected_slug"), [("resolved-slug", "resolved-slug"), (None, "m-01ABCDEF")])
def test_live_derives_the_fresh_runs_excluded_set(recorded: list[Any], monkeypatch: pytest.MonkeyPatch, slug: str | None, expected_slug: str) -> None:
    """FR-013: ``LIVE`` asks ``acceptably_canceled_wp_ids`` (the fresh run's call) by the resolved slug, else the manifest's."""
    asked: list[tuple[Path, str]] = []

    def _canceled(repo: Path, mission_slug: str) -> set[str]:
        asked.append((repo, mission_slug))
        return {"WP02"}

    monkeypatch.setattr(ci, "acceptably_canceled_wp_ids", _canceled)

    inputs = claim_inputs(ClaimInputSource.LIVE, _context(state=None, excluded_canceled_wp_ids=frozenset(), mission_slug=slug))

    assert asked == [(_REPO, expected_slug)]
    assert inputs.excluded_canceled_wp_ids == frozenset({"WP02"}), "the context's own excluded set is not LIVE's source"


@pytest.mark.parametrize(
    ("surface_ref", "rev_parse", "expected"),
    [
        (_COORD_REF, (0, f"{_COORD}\n", ""), _COORD),
        (None, (0, f"{_COORD}\n", ""), _MISSION_BRANCH),
        (_COORD_REF, (128, "", "fatal: bad revision"), _MISSION_BRANCH),
        (_COORD_REF, (0, "  \n", ""), _MISSION_BRANCH),
    ],
    ids=["surface-ref-resolves", "no-surface-ref", "rev-parse-fails", "rev-parse-empty"],
)
def test_live_coord_base_resolves_like_the_fresh_run(
    recorded: list[Any], monkeypatch: pytest.MonkeyPatch, surface_ref: str | None, rev_parse: tuple[int, str, str], expected: str
) -> None:
    """FR-013: the status surface ref rev-parsed to a SHA, else the ``mission_branch`` name (``checkpoint.sha or mission_branch``)."""
    asked: list[str] = []

    def _surface_ref(_repo: Path, slug: str) -> str | None:
        asked.append(slug)
        return surface_ref

    monkeypatch.setattr(status_surface, "status_surface_ref", _surface_ref)
    monkeypatch.setattr(status_surface, "run_command", lambda *_a, **_k: rev_parse)

    inputs = claim_inputs(ClaimInputSource.LIVE, _context(state=None, mission_slug="resolved-slug"))

    assert inputs.coord_base == expected
    assert asked == ["resolved-slug"], "the surface ref is resolved by the run's slug"


def test_live_lane_tips_skip_planning_canceled_and_unresolved_lanes(monkeypatch: pytest.MonkeyPatch) -> None:
    manifest = _manifest()
    planning = ExecutionLane(lane_id="lane-planning", wp_ids=("WP03",), write_scope=(), predicted_surfaces=(), depends_on_lanes=(), parallel_group=0)
    manifest = replace(manifest, lanes=[*manifest.lanes, planning])
    monkeypatch.setattr(ci, "capture_branch_tip", lambda _repo, branch: None if branch.endswith("lane-b") else "sha")

    tips = ci.live_lane_tips(_REPO, manifest, frozenset({"WP01"}))

    assert tips == {}, "lane-a is fully canceled, lane-b does not resolve, the planning lane is never a tip"


def test_saved_reads_the_record_never_live(recorded: list[Any], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ci, "capture_branch_tip", lambda *_a: pytest.fail("SAVED must not read a lane tip live (CI-3)"))
    state = _state()
    state.pre_mutation_refs = {_MISSION_BRANCH: "5" * 40}  # an interrupted run's snapshot: the record decides

    inputs = claim_inputs(ClaimInputSource.SAVED, _context(state=state, resolved_target_base="f" * 40, resolved_coord_sha="f" * 40))

    assert inputs.target_base == _TARGET and inputs.coord_base == _COORD
    assert dict(inputs.dependency_anchors) == {_LANE_A: "1" * 40}
    assert inputs.strategy == "merge"
    assert inputs.dependency_refs == _REFS and dict(inputs.dependency_pins) == _PINS


def test_saved_with_a_snapshot_freezes_the_mission_tip_never_live(recorded: list[Any], monkeypatch: pytest.MonkeyPatch) -> None:
    """#7626 / c52a0626: an interrupted run's resume trusts the Mission branch only as its snapshot froze it."""
    monkeypatch.setattr(ci, "capture_branch_tip", lambda *_a: pytest.fail("a resume holding a snapshot must not read the Mission branch live"))
    state = _state()
    state.pre_mutation_refs = {_MISSION_BRANCH: "5" * 40, "main": _TARGET}

    inputs = claim_inputs(ClaimInputSource.SAVED, _context(state=state))

    assert inputs.mission_branch_tip == "5" * 40


def test_saved_with_a_snapshot_lacking_the_mission_branch_trusts_no_mission_tip(recorded: list[Any], monkeypatch: pytest.MonkeyPatch) -> None:
    """A snapshot exists but names no Mission branch (absent at that run's start): nothing is read live, nothing is trusted."""
    monkeypatch.setattr(ci, "capture_branch_tip", lambda *_a: pytest.fail("a resume holding a snapshot must not read the Mission branch live"))
    state = _state()
    state.pre_mutation_refs = {"main": _TARGET}

    inputs = claim_inputs(ClaimInputSource.SAVED, _context(state=state))

    assert inputs.mission_branch_tip is None


def test_saved_after_a_rebaseline_reads_the_mission_tip_live(recorded: list[Any], monkeypatch: pytest.MonkeyPatch) -> None:
    """#7626 follow-up (operator ruling): a record that holds NO snapshot was rebaselined after a full
    restore (#6770), so no branch moved in this run yet. Like a fresh run, it reads the Mission tip
    live, before the first mutation: what the operator committed on the Mission branch between
    attempts is trusted history. Lane tips still come from the record (CI-3)."""
    reads: list[str] = []

    def read(_repo: Path, branch: str) -> str:
        if branch != _MISSION_BRANCH:
            pytest.fail(f"SAVED must not read a lane tip live (CI-3), read {branch}")
        reads.append(branch)
        return "m" * 40

    monkeypatch.setattr(ci, "capture_branch_tip", read)
    state = _state()
    state.pre_mutation_refs = {}

    inputs = claim_inputs(ClaimInputSource.SAVED, _context(state=state, rebaselined=True))

    assert inputs.mission_branch_tip == "m" * 40
    assert reads == [_MISSION_BRANCH]
    assert dict(inputs.dependency_anchors) == {_LANE_A: "1" * 40}


def test_saved_with_no_snapshot_but_not_rebaselined_trusts_no_mission_tip(recorded: list[Any], monkeypatch: pytest.MonkeyPatch) -> None:
    """Squad MAJOR (#7626 follow-up): an empty snapshot alone is not a rebaseline. A legacy record (written
    before the snapshot existed, possibly after its own lane merges) keeps c52a0626's rule: no live read,
    no trusted Mission tip, so this attempt's own merges never become trusted roots."""
    monkeypatch.setattr(ci, "capture_branch_tip", lambda *_a: pytest.fail("a non-rebaselined resume must not read the Mission branch live"))
    state = _state()
    state.pre_mutation_refs = {}

    inputs = claim_inputs(ClaimInputSource.SAVED, _context(state=state))

    assert inputs.mission_branch_tip is None


@pytest.mark.parametrize(
    ("refs", "target_sha", "expected"),
    [
        ({}, None, True),  # what rebaseline_after_full_restore leaves
        ({}, "a" * 40, False),  # a legacy record: target tip persisted, no snapshot
        ({_MISSION_BRANCH: "5" * 40}, None, False),  # a snapshot exists
        ({_MISSION_BRANCH: "5" * 40}, "a" * 40, False),  # an interrupted run
    ],
)
def test_record_was_rebaselined_reads_the_rebaseline_signature(refs: dict[str, str], target_sha: str | None, expected: bool) -> None:
    state = _state()
    state.pre_mutation_refs = dict(refs)
    state.pre_mutation_target_sha = target_sha

    assert ci.record_was_rebaselined(state) is expected
    assert ci.record_was_rebaselined(None) is False


def test_rebaseline_leaves_the_signature_record_was_rebaselined_reads() -> None:
    """The predicate and its one writer agree: a full restore's rebaseline yields a rebaselined record."""
    from specify_cli.consolidation.rollback import rebaseline_after_full_restore

    state = _state()
    state.pre_mutation_refs = {_MISSION_BRANCH: "5" * 40, "main": _TARGET}
    assert not ci.record_was_rebaselined(state)

    rebaseline_after_full_restore(state, ())

    assert ci.record_was_rebaselined(state)


@pytest.mark.parametrize(("persisted_target", "expected"), [(None, True), ("a" * 40, False)])
def test_claim_phase_reads_the_rebaseline_signature_before_repersisting_the_target(
    monkeypatch: pytest.MonkeyPatch, persisted_target: str | None, expected: bool
) -> None:
    """The claim phase re-persists the transaction target tip before it builds the inputs, which would
    hide the signature: it must read ``record_was_rebaselined`` first (squad MAJOR fold, #7626)."""
    seen: list[ClaimInputContext] = []

    class _Stop(Exception):
        pass

    def fake_claim_inputs(_source: ClaimInputSource, context: ClaimInputContext) -> ClaimInputs:
        seen.append(context)
        raise _Stop

    def repersist(_repo: Path, _branch: str, state: ConsolidationState) -> str:
        state.pre_mutation_target_sha = state.pre_mutation_target_sha or "b" * 40
        return state.pre_mutation_target_sha

    monkeypatch.setattr(phase_claim, "detect_legacy_in_flight_state", lambda *_a, **_k: None)
    monkeypatch.setattr(phase_claim, "write_post_fix_marker", lambda *_a: None)
    monkeypatch.setattr(phase_claim, "_capture_coord_checkpoint", lambda _run: None)
    monkeypatch.setattr(phase_claim, "_enforce_resume_anchor_integrity", lambda *_a, **_k: None)
    monkeypatch.setattr(phase_claim, "_resolve_pre_mutation_coord_sha", lambda *_a: _COORD)
    monkeypatch.setattr(phase_claim, "_resolve_pre_mutation_target_sha", repersist)
    monkeypatch.setattr(phase_claim, "claim_inputs", fake_claim_inputs)
    state = _state()
    state.pre_mutation_refs = {}
    state.pre_mutation_target_sha = persisted_target
    run = SimpleNamespace(
        main_repo=_REPO,
        canonical_id="m",
        feature_dir=_STATUS,
        lanes_manifest=_manifest(),
        is_resume=True,
        state=state,
        strategy=MergeStrategy.SQUASH,
        dependency_refs=_REFS,
        dependency_ref_pins={},
        excluded_canceled_wp_ids=_EXCLUDED,
        claim_inputs=None,
        coord_checkpoint=None,
    )

    with pytest.raises(_Stop):
        phase_claim._capture_reconciliation_claim(cast(Any, run))

    assert state.pre_mutation_target_sha is not None, "the target tip was re-persisted before the inputs were built"
    assert seen[0].rebaselined is expected


def test_live_then_saved_reuses_the_tips_the_claim_phase_captured(recorded: list[Any], monkeypatch: pytest.MonkeyPatch) -> None:
    """M7: a fresh run's dependency anchors come from the tips the claim phase just captured, never a second read."""

    def read(_repo: Path, branch: str) -> str:
        # Only the Mission branch is read live (its tip is frozen into the inputs, #7626); a lane tip must not be.
        if branch != _context(state=state).manifest.mission_branch:
            pytest.fail("LIVE_THEN_SAVED must reuse the captured tips")
        return "m" * 40

    state = _state()
    monkeypatch.setattr(ci, "capture_branch_tip", read)

    inputs = claim_inputs(ClaimInputSource.LIVE_THEN_SAVED, _context(state=state))

    assert dict(inputs.dependency_anchors) == {_LANE_A: "1" * 40}
    assert inputs.mission_branch_tip == "m" * 40


def test_live_then_saved_reads_live_when_nothing_was_captured(recorded: list[Any]) -> None:
    """A run with no status-surface checkpoint captured no tips; the fresh run then reads them live."""
    state = _state()
    state.pre_interrupt_lane_tips = {}

    inputs = claim_inputs(ClaimInputSource.LIVE_THEN_SAVED, _context(state=state))

    assert dict(inputs.dependency_anchors) == {_LANE_A: f"tip-of-{_LANE_A}"}


def test_saved_without_a_saved_base_keeps_todays_resolution(recorded: list[Any]) -> None:
    """A record that holds no base keeps the value the call site resolved (today's behaviour, CI-3)."""
    state = _state()
    state.pre_mutation_target_sha = None
    state.pre_mutation_coord_sha = None

    inputs = claim_inputs(ClaimInputSource.SAVED, _context(state=state, resolved_coord_sha=None))

    assert inputs.target_base == _TARGET
    assert inputs.coord_base == _CHECKPOINT


def test_saved_requires_a_record() -> None:
    with pytest.raises(ValueError, match="SAVED"):
        claim_inputs(ClaimInputSource.SAVED, _context(state=None))


def test_claim_inputs_is_immutable(recorded: list[Any]) -> None:
    pins = dict(_PINS)
    inputs = claim_inputs(ClaimInputSource.LIVE_THEN_SAVED, _context(dependency_pins=pins))
    pins["other"] = "x"

    assert "other" not in inputs.dependency_pins, "the value holds its own copy"
    with pytest.raises(TypeError):
        cast(dict[str, str], inputs.dependency_anchors)["x"] = "y"


@pytest.mark.parametrize(("is_resume", "source"), [(False, ClaimInputSource.LIVE_THEN_SAVED), (True, ClaimInputSource.SAVED)])
def test_gate_rebuild_keeps_the_live_mission_branch_name(monkeypatch: pytest.MonkeyPatch, is_resume: bool, source: ClaimInputSource) -> None:
    """The gate's defensive rebuild uses the run's source with the documented ``mission_branch`` override (T052)."""
    seen: list[ClaimInputs] = []
    monkeypatch.setattr(phase_gate, "build_claim", lambda _r, _m, inputs: seen.append(inputs) or "rebuilt")
    run = SimpleNamespace(
        main_repo=_REPO,
        feature_dir=_STATUS,
        lanes_manifest=_manifest(),
        approved_wp_set=None,
        claim_inputs=None,  # no claim phase ran: the rebuild resolves its own inputs (WP18 reuses the claim's when it did)
        is_resume=is_resume,
        state=_state(),
        strategy=MergeStrategy.MERGE,
        target_expected_old_sha=_TARGET,
        excluded_canceled_wp_ids=_EXCLUDED,
        dependency_refs=_REFS,
        dependency_ref_pins={},
        coord_checkpoint=None,
    )
    monkeypatch.setattr(ci, "capture_branch_tip", lambda *_a: None)

    assert phase_gate._reconciliation_claim_for_gate(cast(Any, run)) == "rebuilt"

    assert seen[0].source is source
    assert seen[0].coord_base == _MISSION_BRANCH
    assert seen[0].target_base == _TARGET
    assert seen[0].excluded_canceled_wp_ids == _EXCLUDED


def test_a_rebaselined_coordination_resume_gate_reads_the_tip_the_claim_trusted(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """#7626 on a coordination topology, claim to gate over a real repository.

    The coordination branch shares the Mission branch's name, and a rebaseline keeps
    ``pre_mutation_coord_sha``, so the snapshot taken after the claim seeds that branch from the tip
    BEFORE the operator's commit. The gate must not re-read the Mission tip from that snapshot: it reuses
    the claim phase's one inputs value, so the claim and the gate trust the same (live) tip.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "t")
    _git(repo, "config", "commit.gpgsign", "false")
    _git(repo, "commit", "-q", "--allow-empty", "-m", "base")
    _git(repo, "checkout", "-qb", _MISSION_BRANCH)
    _git(repo, "commit", "-q", "--allow-empty", "-m", "pre-rollback tip")
    before = _git(repo, "rev-parse", "HEAD")
    _git(repo, "commit", "-q", "--allow-empty", "-m", "operator conflict resolution")
    operator_tip = _git(repo, "rev-parse", "HEAD")
    _git(repo, "checkout", "-q", "main")
    manifest = _manifest()
    state = _state()
    state.pre_mutation_refs = {_MISSION_BRANCH: before}
    state.pre_mutation_coord_ref, state.pre_mutation_coord_sha = _MISSION_BRANCH, before
    rebaseline_after_full_restore(state, ())
    assert state.pre_mutation_coord_sha == before, "a coordination topology keeps its anchor across a rebaseline"
    assert ci.record_was_rebaselined(state)

    inputs = claim_inputs(
        ClaimInputSource.SAVED,
        ClaimInputContext(repo_root=repo, manifest=manifest, status_dir=_STATUS, strategy="merge", resolved_target_base=_TARGET, state=state, rebaselined=True),
    )
    capture_pre_mutation_snapshot(repo, state, manifest, coord_ref=_MISSION_BRANCH, is_resume=True)
    assert state.pre_mutation_refs[_MISSION_BRANCH] == before, "the snapshot seeds the shared branch from the older anchor"

    seen: list[ClaimInputs] = []
    monkeypatch.setattr(phase_gate, "build_claim", lambda _r, _m, got: seen.append(got) or "rebuilt")
    run = SimpleNamespace(
        main_repo=repo, lanes_manifest=manifest, approved_wp_set=None, claim_inputs=inputs, dependency_ref_pins={}, strategy=MergeStrategy.MERGE
    )

    assert phase_gate._reconciliation_claim_for_gate(cast(Any, run)) == "rebuilt"

    assert inputs.mission_branch_tip == operator_tip
    assert seen == [inputs] and seen[0].mission_branch_tip == operator_tip
