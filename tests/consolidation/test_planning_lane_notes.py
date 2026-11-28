"""#7860 review 5 issue 2: a planning lane that credits nothing is named in the refusal.

Before a default Mission lands, the claim credits its planning lane's work on the Mission branch
only when every planning work package is approved (ruling R1), its ``owned_files`` are readable
and narrow, and each window start is proven (ruling R2). Otherwise the lane credits nothing and
the gate reports the content as un-attributable, which alone names neither the planning lane nor
the work package. :func:`planning_lane_notes` says which lane, why, which work packages, and the
remedy; the verifier prints it with an un-attributable FAIL. No verdict changes.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import pytest

from specify_cli.consolidation import planning_lane_scope
from specify_cli.consolidation import planning_lane_walk as planning_walk
from specify_cli.consolidation import git_probes
from specify_cli.consolidation.git_probes import GitProbeError
from specify_cli.consolidation.mission_base import MissionBase, MissionBaseProvenance
from specify_cli.consolidation.reconciliation import ApprovedWpCommitSet
from specify_cli.consolidation.reconciliation_claim_types import PlanningLaneNote
from specify_cli.consolidation.reconciliation_verifier import Divergence, VerifyResult, _with_attribution_hint
from specify_cli.lanes.compute import PLANNING_LANE_ID
from specify_cli.lanes.models import ExecutionLane, LanesManifest

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_SLUG = "notes-01M8FFFF"
_PLANNING = ExecutionLane(PLANNING_LANE_ID, ("WP02", "WP03"), ("curation/pkg/**",), (), (), 0)
_CODE = ExecutionLane("lane-a", ("WP01",), ("src/m1/**",), (), (), 0)
_APPROVED = {"WP01": {"lane": "approved"}, "WP02": {"lane": "approved"}, "WP03": {"lane": "done"}}
_OWNED = {"WP02": ("curation/pkg/**",), "WP03": ("docs/notes/x.md",)}
_RECORDED = MissionBase("base0000", MissionBaseProvenance.RECORDED)


def _manifest() -> LanesManifest:
    return LanesManifest(
        version=1,
        mission_slug=_SLUG,
        mission_id=None,
        mission_branch=f"kitty/mission-{_SLUG}",
        target_branch="main",
        lanes=[_CODE, _PLANNING],
        computed_at="2026-11-27T00:00:00+00:00",
        computed_from="test",
        planning_artifact_wps=["WP02", "WP03"],
        planning_commit_sha="pin0000",
    )


def _events() -> list[object]:
    return []


@pytest.fixture
def shape(monkeypatch: pytest.MonkeyPatch) -> dict[str, object]:
    """The Mission-branch window applies; ownership and window starts read from ``knobs`` (patched on the authorship module)."""
    knobs: dict[str, object] = {"window": ("pin0000", "coord0000"), "owned": dict(_OWNED), "unproven": set(), "scope": None, "opener": True, "taint": []}

    monkeypatch.setattr(planning_walk, "_planning_lane_mission_branch_window", lambda *_args: knobs["window"])

    def _ownership(_root: Path, _slug: str, wp_ids: tuple[str, ...]) -> dict[str, tuple[str, ...]]:
        owned = knobs["owned"]
        assert isinstance(owned, dict)
        return {wp: owned[wp] for wp in wp_ids if wp in owned}

    def _starts(_root: Path, _manifest: LanesManifest, _lane: ExecutionLane, wp_ids: tuple[str, ...], events: object) -> dict[str, str] | None:
        assert events is _events
        unproven = knobs["unproven"]
        assert isinstance(unproven, set)
        return None if any(wp in unproven for wp in wp_ids) else dict.fromkeys(wp_ids, "claim0")

    monkeypatch.setattr(planning_walk, "_planning_ownership", _ownership)
    monkeypatch.setattr(planning_walk, "_planning_window_starts", _starts)
    monkeypatch.setattr(planning_walk, "_planning_scope", lambda *_args: knobs["scope"])
    monkeypatch.setattr(planning_lane_scope, "_opener_recorded", lambda *_args: knobs["opener"])

    def _taint(_root: Path, mission_base: str | None, pin: str, coord: str) -> object:
        assert (pin, coord) == ("pin0000", "coord0000")
        if mission_base is None:
            return None
        assert mission_base == "base0000"
        return knobs["taint"]

    monkeypatch.setattr(planning_walk, "_taint_spine", _taint)
    return knobs


_ON_TARGET = object()


def _notes(
    work_packages: Mapping[str, Mapping[str, object]] = _APPROVED,
    sb_window: tuple[str, str] | None = None,
    base: MissionBase | None = _RECORDED,
    taint_base: object = _ON_TARGET,
) -> tuple[str, ...]:
    """The notes' texts; *taint_base* defaults to the claim's answer for a recorded base on the target (its sha)."""
    if taint_base is _ON_TARGET:
        taint_base = base.sha if base is not None and base.provenance is MissionBaseProvenance.RECORDED else None
    assert taint_base is None or isinstance(taint_base, str)
    notes: tuple[PlanningLaneNote, ...] = planning_lane_scope.planning_lane_notes(
        Path(), _manifest(), work_packages, "coord0000", sb_window, _events, base, taint_base=taint_base
    )
    return tuple(note.text for note in notes)


def test_a_credited_lane_gets_no_note(shape: dict[str, object]) -> None:
    shape["scope"] = planning_walk._PlanningScope(((("curation/pkg/**",), frozenset({"c1"})),))

    assert _notes() == ()


def test_a_credited_lane_with_no_readable_mission_base_gets_a_note(shape: dict[str, object]) -> None:
    """Review 9: a scoped lane whose taint walk cannot start at the Mission base credits nothing, and its note says why."""
    shape["scope"] = planning_walk._PlanningScope(((("curation/pkg/**",), frozenset({"c1"})),))
    shape["taint"] = None

    (text,) = _notes()

    assert "no recorded Mission base (`mission_base_sha` in the Mission's meta.json, the commit the Mission branch was cut from) can start" in text
    assert "none resolves, it is not below the planning commit" in text
    assert "Restore the Mission branch's history, or: Record a commit on `main`" in text
    assert "which `git merge-base main <scaffold>^` prints" in text
    assert text.endswith("then run `spec-kitty consolidate` again.")


@pytest.mark.parametrize("base", [None, MissionBase(None, MissionBaseProvenance.UNAVAILABLE, "gone")])
def test_a_credited_lane_with_no_mission_base_at_all_gets_the_unusable_base_note(shape: dict[str, object], base: MissionBase | None) -> None:
    shape["scope"] = planning_walk._PlanningScope(((("curation/pkg/**",), frozenset({"c1"})),))

    (text,) = _notes(base=base)

    assert "no recorded Mission base" in text and "records no usable Mission base" not in text


@pytest.mark.parametrize(("reason", "shown"), [("no mission_base_sha recorded", "no mission_base_sha recorded"), (None, "no `mission_base_sha` recorded")])
def test_a_credited_lane_with_a_derived_mission_base_gets_a_not_recorded_note(shape: dict[str, object], reason: str | None, shown: str) -> None:
    """Review 10: a derived base never starts the taint walk, and the note says the Mission records none, and the remedy."""
    shape["scope"] = planning_walk._PlanningScope(((("curation/pkg/**",), frozenset({"c1"})),))
    shape["taint"] = ["c1"]

    (text,) = _notes(base=MissionBase("base0000", MissionBaseProvenance.DERIVED, reason))

    assert f"the Mission records no usable Mission base ({shown})" in text
    assert "a commit made on the Mission branch before that scaffold" in text
    assert "Record a commit on `main` as `mission_base_sha` in the Mission's meta.json" in text
    assert "which `git merge-base main base0000` prints; commit it on the Mission branch (no command records it yet, #7892)" in text
    assert text.endswith("then run `spec-kitty consolidate` again.")


def test_a_credited_lane_with_a_recorded_base_off_the_target_gets_its_own_note(shape: dict[str, object]) -> None:
    """Review 11: a recorded base the claim found not on the target starts nothing, and the note says so."""
    shape["scope"] = planning_walk._PlanningScope(((("curation/pkg/**",), frozenset({"c1"})),))
    shape["taint"] = ["c1"]
    sha = "f" * 40

    (text,) = _notes(base=MissionBase(sha, MissionBaseProvenance.RECORDED), taint_base=None)

    assert f"the recorded Mission base `{'f' * 12}` (`mission_base_sha` in the Mission's meta.json) is not a commit on `main`" in text
    assert "records no usable Mission base" not in text and "no recorded Mission base" not in text
    assert f"which `git merge-base main {sha}` prints" in text and "#7892" in text
    assert text.endswith("then run `spec-kitty consolidate` again.")


def test_another_shape_gets_no_note(shape: dict[str, object]) -> None:
    assert _notes(sb_window=("sb0", "sb1")) == ()
    shape["window"] = None
    assert _notes() == ()


_IN_FLIGHT_ROWS = [({"lane": "in_progress"}, "WP03 is in_progress"), (None, "WP03 is no status row")]
_R1_NAMED = "the planning-lane credit rule, operator ruling R1); no attestation lifts this rule"


def _states(row: dict[str, object] | None) -> dict[str, dict[str, object]]:
    states: dict[str, dict[str, object]] = {"WP01": {"lane": "approved"}, "WP02": {"lane": "approved"}}
    if row is not None:
        states["WP03"] = row
    return states


@pytest.mark.parametrize(("row", "shown"), _IN_FLIGHT_ROWS)
def test_an_in_flight_work_package_is_named_with_its_review_remedy(shape: dict[str, object], row: dict[str, object] | None, shown: str) -> None:
    (note,) = _notes(_states(row))

    assert note.startswith(f"The planning lane {PLANNING_LANE_ID} credits none of its work on the Mission branch")
    assert shown in note and "WP02" not in note.split(":", 1)[1].split(".", 1)[0]
    assert _R1_NAMED in note
    assert "WP03: finish the review and approval" in note
    assert "--force" not in note and "--attest-no-implementation" not in note


def test_a_canceled_work_package_is_named_with_commands_that_run_as_printed(shape: dict[str, object]) -> None:
    """Review 6 N1-N3: real ids and ``--mission``; the forced moves are recorded acts; the attestation answers the evidence check."""
    (note,) = _notes(_states({"lane": "canceled"}))

    assert "WP03 is canceled" in note and _R1_NAMED in note
    assert f"`spec-kitty agent tasks move-task WP03 --to claimed --force --agent <implementer> --mission {_SLUG}`" in note
    assert f"`spec-kitty agent tasks move-task WP03 --to approved --force --agent <reviewer> --mission {_SLUG}`" in note
    assert f'`spec-kitty consolidate --mission {_SLUG} --attest-no-implementation WP03 --attest-reason "<why>"`' in note
    assert f"`spec-kitty agent action implement WP03 --agent <implementer> --mission {_SLUG}`" in note
    assert "other than the one that claimed it (else REVIEW_NOT_INDEPENDENT)" in note
    assert "operator transitions recorded in the status log" in note
    assert "it answers only the owned-file evidence check (IMPLEMENTATION_MISSING), not the planning-lane credit rule" in note
    assert "<WP>" not in note


def test_a_canceled_and_an_in_flight_work_package_each_get_their_remedy(shape: dict[str, object]) -> None:
    (note,) = _notes({"WP01": {"lane": "approved"}, "WP02": {"lane": "claimed"}, "WP03": {"lane": "canceled"}})

    assert "WP02 is claimed, WP03 is canceled" in note
    assert "WP02: finish the review and approval" in note
    assert f"move-task WP03 --to approved --force --agent <reviewer> --mission {_SLUG}" in note and "move-task WP02 --to approved" not in note


def test_an_unreadable_ownership_is_named(shape: dict[str, object]) -> None:
    shape["owned"] = {"WP02": _OWNED["WP02"]}

    (note,) = _notes()

    assert "the owned_files of WP03 cannot be read" in note


def test_a_too_broad_pattern_is_named(shape: dict[str, object]) -> None:
    shape["owned"] = {"WP02": ("src/**",), "WP03": _OWNED["WP03"]}

    (note,) = _notes()

    assert "too broad (WP02 'src/**')" in note and "two literal path segments" in note


def test_an_unproven_window_start_is_named_with_the_reopen_and_restart_remedy(shape: dict[str, object]) -> None:
    """Review 6 issue 2: every lane WP is approved here, and ``implement`` refuses an approved WP (#7754), so reopen first."""
    shape["unproven"] = {"WP03"}

    (note,) = _notes()

    reopen = f"`spec-kitty agent tasks move-task WP03 --to planned --review-feedback-file <file> --mission {_SLUG}`"
    implement = f"`spec-kitty agent action implement WP03 --agent <agent> --mission {_SLUG}`"
    assert "the claim of WP03 on the Mission branch cannot be proven" in note
    assert f"first reopen it with {reopen} and claim it with {implement}" in note
    assert f"run {reopen} again (a move to planned from claimed or in_progress starts a new window) and {implement}" in note
    assert "a commit made before the new claim does not count" in note and "reviewed and approved again" in note
    assert note.index(reopen) < note.index(implement)


def test_an_absent_opener_is_named_with_one_reopen(shape: dict[str, object]) -> None:
    """Review 7 item 4: with no window-opening event recorded, the first claim opens the window, so one reopen suffices."""
    shape["unproven"] = {"WP03"}
    shape["opener"] = False

    (note,) = _notes()

    reopen = f"`spec-kitty agent tasks move-task WP03 --to planned --review-feedback-file <file> --mission {_SLUG}`"
    implement = f"`spec-kitty agent action implement WP03 --agent <agent> --mission {_SLUG}`"
    assert note.count(reopen) == 1 and note.count(implement) == 1
    assert "no window-opening (claim) status event is recorded for WP03" in note


_REOPEN_X = "`spec-kitty agent tasks move-task WP09 --to planned --review-feedback-file <file> --mission m`"
_IMPLEMENT_X = "`spec-kitty agent action implement WP09 --agent <agent> --mission m`"


@pytest.mark.parametrize(("opener_recorded", "reopens"), [(False, 1), (True, 2), (None, 2)])
def test_the_restart_steps_follow_whether_an_opener_is_recorded(opener_recorded: bool | None, reopens: int) -> None:
    from specify_cli.consolidation.wp_evidence import planning_window_restart

    text = planning_window_restart("WP09", "m", opener_recorded=opener_recorded)

    assert text.count(_REOPEN_X) == reopens and text.count(_IMPLEMENT_X) == reopens
    assert text.index(_REOPEN_X) < text.index(_IMPLEMENT_X)
    assert "a commit made before the new claim does not count" in text and text.endswith("then re-run")
    if opener_recorded is None:
        # The shared text cannot know the case, so it says when the second reopen is needed and when it is not.
        assert "when a window-opening (claim) status event is recorded" in text and "when none is recorded" in text


@pytest.mark.parametrize("outcome", ["no_opener", "unprovable", "resolves", "no_reader"])
def test_the_opener_reading_comes_from_the_evidence_axis(monkeypatch: pytest.MonkeyPatch, outcome: str) -> None:
    from specify_cli.consolidation import wp_evidence

    def _window(*_args: object) -> tuple[str, str]:
        if outcome in ("no_opener", "unprovable"):
            raise wp_evidence.PlanningWindowUnresolved(wp_evidence.EVIDENCE_WINDOW_UNCOMPUTABLE, "x", opener_recorded=outcome == "unprovable")
        return ("claim0", "coord0000")

    monkeypatch.setattr(wp_evidence, "planning_evidence_window", _window)
    events = None if outcome == "no_reader" else _events

    recorded = planning_lane_scope._opener_recorded(Path(), _manifest(), _PLANNING, "WP02", events)

    assert recorded is {"no_opener": False, "unprovable": True}.get(outcome)


def _unreadable_raises(monkeypatch: pytest.MonkeyPatch) -> list[object]:
    """The three ``IMPLEMENTATION_UNREADABLE`` raises of the evidence axis, each driven through its own raise site."""
    import mission_runtime

    from specify_cli.consolidation import wp_evidence

    def _undecidable(*_args: object, **_kwargs: object) -> object:
        raise mission_runtime.PlanningWriteRefUnavailable("m", "meta.json unreadable")

    raised: list[object] = []
    with monkeypatch.context() as patch:
        patch.setattr(mission_runtime, "planning_write_ref", _undecidable)
        with pytest.raises(wp_evidence.PlanningWindowUnresolved) as write_branch:
            wp_evidence._planning_window_end(Path(), _manifest())
    raised.append(write_branch.value)
    with pytest.raises(wp_evidence.PlanningWindowUnresolved) as unreadable_log:
        wp_evidence._planning_window_start(Path(), _manifest(), "WP02", None, "kitty/mission-x")
    raised.append(unreadable_log.value)
    unavailable = mission_runtime.ClaimCommitUnresolved("WP02", "git_unavailable", "boom")
    raised.append(wp_evidence._unresolved_start(unavailable, "kitty/mission-x", "01EVENT"))
    return raised


def _raising(error: BaseException) -> object:
    def _window(*_args: object) -> None:
        raise error

    return _window


def test_the_unreadable_raises_say_nothing_about_the_opener(monkeypatch: pytest.MonkeyPatch) -> None:
    """Review 8 issue 3: an unreadable log, an undecidable write branch or unreadable git tells nothing about the opener.

    Each raise leaves ``opener_recorded`` at ``None``, so the planning-lane note prints the shared
    restart text, never the steps for an opener that is recorded but unprovable.
    """
    from specify_cli.consolidation import wp_evidence
    from specify_cli.consolidation.wp_evidence import IMPLEMENTATION_UNREADABLE, planning_window_restart

    for error in _unreadable_raises(monkeypatch):
        assert isinstance(error, wp_evidence.PlanningWindowUnresolved)
        assert error.code == IMPLEMENTATION_UNREADABLE and error.opener_recorded is None
        monkeypatch.setattr(wp_evidence, "planning_evidence_window", _raising(error))
        recorded = planning_lane_scope._opener_recorded(Path(), _manifest(), _PLANNING, "WP02", _events)
        assert recorded is None
        assert planning_window_restart("WP02", "m", opener_recorded=recorded) == planning_window_restart("WP02", "m")


def test_an_unprovable_claim_commit_records_its_opener() -> None:
    """Review 8 issue 3: only the unprovable-claim-commit raise sets ``opener_recorded`` True."""
    import mission_runtime

    from specify_cli.consolidation import wp_evidence

    error = wp_evidence._unresolved_start(mission_runtime.ClaimCommitUnresolved("WP02", "ambiguous", "two"), "kitty/mission-x", "01EVENT")

    assert error.code == wp_evidence.EVIDENCE_WINDOW_UNCOMPUTABLE and error.opener_recorded is True


def test_the_evidence_refusal_prints_the_same_restart_steps() -> None:
    from specify_cli.consolidation.wp_evidence import EVIDENCE_WINDOW_UNCOMPUTABLE, PLANNING_WINDOW_RECOVERY, planning_window_restart

    recovery = PLANNING_WINDOW_RECOVERY[EVIDENCE_WINDOW_UNCOMPUTABLE]

    assert planning_window_restart("<WP>", "<slug>") in recovery
    assert recovery.index("--to planned") < recovery.index("agent action implement")


def test_all_empty_ownership_is_named(shape: dict[str, object]) -> None:
    shape["owned"] = {"WP02": (), "WP03": ()}
    shape["scope"] = planning_walk._PlanningScope((((), frozenset()), ((), frozenset())))

    (note,) = _notes()

    assert "every planning work package's owned_files list is empty" in note


def test_an_unreadable_window_is_the_remaining_reason(shape: dict[str, object]) -> None:
    (note,) = _notes()

    assert "the commits of a work package's window on the Mission branch cannot be read" in note


# ---------------------------------------------------------------- rendering


_TEXT = "The planning lane lane-planning credits none of its work on the Mission branch to any work package (#7860): WP03 is canceled. Remedy."
_LANE_COMMIT = "c" * 40
_NOTE = PlanningLaneNote(_TEXT, ("curation/pkg/**",), frozenset({_LANE_COMMIT}))
_EMPTY_TEXT = (
    "The planning lane lane-planning credits none of its work on the Mission branch to any work package (#7860): "
    "every planning work package's owned_files list is empty."
)


def _claim(notes: tuple[PlanningLaneNote, ...] = (), refs: tuple[str, ...] = ()) -> ApprovedWpCommitSet:
    return ApprovedWpCommitSet(enforce_closed_world=True, planning_lane_notes=notes, external_dependency_refs=refs)


def _hint(divergence: Divergence, claim: ApprovedWpCommitSet) -> str:
    # A typed local: under ``follow_imports = "skip"`` the verifier's result reads as ``Any`` here.
    guidance: str = _with_attribution_hint(VerifyResult.failed(divergence), claim).recovery_guidance()
    return guidance


def test_an_un_attributable_fail_names_the_planning_lane_before_the_dependency_hint() -> None:
    result = _with_attribution_hint(VerifyResult.failed(Divergence(unattributable_blobs=(("curation/pkg/x.py", "b" * 40),))), _claim((_NOTE,)))

    text = result.recovery_guidance()

    assert _TEXT in text and "--dependency-ref" in text
    assert text.index(_TEXT) < text.index("--dependency-ref")
    assert result.status.name == "FAIL"


def test_a_declared_dependency_keeps_the_planning_note() -> None:
    text = _hint(Divergence(unattributable_deletions=("curation/pkg/x.py",)), _claim((_NOTE,), ("dep",)))

    assert _TEXT in text and "--dependency-ref" not in text


def test_a_code_lanes_stray_content_never_prints_the_planning_note() -> None:
    """Review 6 issue 3: the planning lane is empty, but the FAIL is about a code lane's path and commit."""
    claim = _claim((_NOTE,))

    for divergence in (
        Divergence(unattributable_blobs=(("src/m1/stray.py", "b" * 40),)),
        Divergence(unattributable_deletions=("src/m1/gone.py",)),
        Divergence(unattributable_content=(("d" * 40, "p" * 40),)),
    ):
        text = _hint(divergence, claim)
        assert _TEXT not in text and "--dependency-ref" in text


def test_an_un_attributable_commit_of_the_planning_walk_prints_the_note() -> None:
    assert _TEXT in _hint(Divergence(unattributable_content=((_LANE_COMMIT, "p" * 40),)), _claim((_NOTE,)))


def test_an_unreadable_planning_walk_lets_any_un_attributable_commit_print_the_note() -> None:
    unread = PlanningLaneNote(_TEXT, ("curation/pkg/**",), None)

    assert _TEXT in _hint(Divergence(unattributable_content=(("d" * 40, "p" * 40),)), _claim((unread,)))
    assert _TEXT not in _hint(Divergence(unattributable_blobs=(("src/m1/stray.py", "b" * 40),)), _claim((unread,)))


def test_a_note_with_no_patterns_explains_its_walks_own_paths_and_commits() -> None:
    """Review 7 issue 2: with every owned_files list empty, the note covers the walk's non-bookkeeping paths and commits."""
    empty = PlanningLaneNote(_EMPTY_TEXT, (), frozenset({_LANE_COMMIT}), frozenset({"curation/pkg/x.py"}))

    assert empty.explains(("curation/pkg/x.py",), ()) and empty.explains((), (_LANE_COMMIT,))
    assert not empty.explains(("curation/pkg/y.py", "src/m1/stray.py"), ("d" * 40,))
    assert not PlanningLaneNote(_TEXT, (), frozenset()).explains(("curation/pkg/x.py",), ("d" * 40,))


def test_the_every_owned_files_empty_note_prints_with_a_fail_about_the_walk() -> None:
    """Review 7 issue 2: the reason-4 note is reachable through the verifier, on the squash and closed-world axes alike."""
    claim = _claim((PlanningLaneNote(_EMPTY_TEXT, (), frozenset({_LANE_COMMIT}), frozenset({"curation/pkg/x.py"})),))

    assert _EMPTY_TEXT in _hint(Divergence(unattributable_blobs=(("curation/pkg/x.py", "b" * 40),)), claim)
    assert _EMPTY_TEXT in _hint(Divergence(unattributable_deletions=("curation/pkg/x.py",)), claim)
    assert _EMPTY_TEXT in _hint(Divergence(unattributable_content=((_LANE_COMMIT, "p" * 40),)), claim)
    assert _EMPTY_TEXT not in _hint(Divergence(unattributable_blobs=(("src/m1/stray.py", "b" * 40),)), claim)
    assert _EMPTY_TEXT not in _hint(Divergence(unattributable_content=(("d" * 40, "p" * 40),)), claim)


def test_the_note_rides_only_on_an_un_attributable_fail() -> None:
    claim = _claim((_NOTE,))
    missing = VerifyResult.failed(Divergence(missing_approved=(("WP01", "a" * 40),)))

    assert _TEXT not in _with_attribution_hint(missing, claim).recovery_guidance()
    assert _TEXT not in _with_attribution_hint(VerifyResult.refused("unreadable"), claim).recovery_guidance()
    assert _with_attribution_hint(VerifyResult.passed(), claim).is_pass


def test_no_note_keeps_the_hint_unchanged() -> None:
    failed = VerifyResult.failed(Divergence(unattributable_content=(("c" * 40, "p" * 40),)))

    assert _with_attribution_hint(failed, _claim()).attribution_hint == _with_attribution_hint(failed, ApprovedWpCommitSet()).attribution_hint


# ---------------------------------------------------------------- what a note covers


def test_a_note_covers_the_write_scope_and_the_readable_owned_files(shape: dict[str, object]) -> None:
    lane = ExecutionLane(PLANNING_LANE_ID, ("WP02", "WP03"), ("kitty-specs/x/research/**",), (), (), 0)

    assert planning_lane_scope._note_patterns(Path(), _manifest(), lane) == ("curation/pkg/**", "docs/notes/x.md", "kitty-specs/x/research/**")


def test_a_note_covers_the_walk_commits_that_change_a_path_in_its_scope(monkeypatch: pytest.MonkeyPatch) -> None:
    changed = {"c1": ["curation/pkg/x.py"], "c2": ["src/m1/y.py"], "c3": ["docs/notes/x.md", "README.md"]}
    monkeypatch.setattr(git_probes, "commits_in_range", lambda _root, base, tip: ["c1", "c2", "c3"] if (base, tip) == ("pin0000", "coord0000") else [])
    monkeypatch.setattr(git_probes, "changed_paths_of", lambda _root, sha: changed[sha])

    covered = planning_lane_scope._note_coverage(Path(), ("pin0000", "coord0000"), ("curation/pkg/**", "docs/notes/x.md"), _SLUG)
    assert covered == (frozenset({"c1", "c3"}), frozenset())


def test_with_no_patterns_a_note_covers_the_walks_non_bookkeeping_commits_and_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    """Review 7 issue 2: every owned_files list is empty, so the walk's own content is what the note explains."""
    changed = {"c1": ["curation/pkg/x.py", f"kitty-specs/{_SLUG}/status.events.jsonl"], "c2": [f"kitty-specs/{_SLUG}/status.events.jsonl"], "c3": ["README.md"]}
    monkeypatch.setattr(git_probes, "commits_in_range", lambda _root, _base, _tip: ["c1", "c2", "c3"])
    monkeypatch.setattr(git_probes, "changed_paths_of", lambda _root, sha: changed[sha])

    covered = planning_lane_scope._note_coverage(Path(), ("pin0000", "coord0000"), (), _SLUG)

    assert covered == (frozenset({"c1", "c3"}), frozenset({"curation/pkg/x.py", "README.md"}))


def test_an_unreadable_walk_covers_every_commit(monkeypatch: pytest.MonkeyPatch) -> None:
    def _unreadable(*_args: object) -> list[str]:
        raise GitProbeError("unreadable")

    monkeypatch.setattr(git_probes, "commits_in_range", _unreadable)

    assert planning_lane_scope._note_coverage(Path(), ("pin0000", "coord0000"), ("curation/pkg/**",), _SLUG) == (None, frozenset())
    assert planning_lane_scope._note_coverage(Path(), ("pin0000", "coord0000"), (), _SLUG) == (None, frozenset())


def test_the_claims_notes_carry_their_lanes_scope(shape: dict[str, object], monkeypatch: pytest.MonkeyPatch) -> None:
    def _coverage(_root: Path, window: tuple[str, str], patterns: tuple[str, ...], slug: str) -> tuple[frozenset[str], frozenset[str]]:
        return frozenset({f"{window[0]}:{len(patterns)}"}), frozenset({slug})

    monkeypatch.setattr(planning_lane_scope, "_note_coverage", _coverage)

    (note,) = planning_lane_scope.planning_lane_notes(Path(), _manifest(), _states({"lane": "canceled"}), "coord0000", None, _events)

    assert note.patterns == ("curation/pkg/**", "docs/notes/x.md")
    assert note.commits == frozenset({"pin0000:2"})
    assert note.paths == frozenset({_SLUG})
