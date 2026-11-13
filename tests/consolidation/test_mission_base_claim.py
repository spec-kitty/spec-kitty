"""Claim-level units for the Mission base bound (#7560, WP03).

A Mission branch cut from a fork of the target carries the fork's history, which the target
lacks. That history predates the Mission: the #6771 guard walks drop it (so the fork's pin can be
declared), and the claim carries it as ``pre_mission_*`` for the window axes. A commit the
Mission authored after its base is still Mission work and still refuses. A probe failure while
resolving the pre-Mission history degrades to today's bound (nothing exempted).
"""

from __future__ import annotations

import io
import json
import subprocess
from dataclasses import dataclass, fields, replace
from pathlib import Path

import pytest

from specify_cli.consolidation import reconciliation_claim, reconciliation_closed_world
from specify_cli.consolidation._constants import DEPENDENCY_REF_COVERS_MISSION_WORK
from specify_cli.consolidation.git_probes import GitProbeError
from specify_cli.consolidation.mission_base import MissionBase, MissionBaseProvenance, MissionBaseReason
from specify_cli.consolidation.reconciliation import (
    ApprovedWpCommitSet,
    ExternalDependencyAttribution,
    PreMissionHistory,
    _mission_spines,
    _pre_mission_attribution,
    _recorded_work_hit,
    build_approved_wp_set,
    mission_base_note,
    resolve_external_dependency_refs,
)
from specify_cli.lanes.compute import lane_created_branch
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.lanes.persistence import write_lanes_json
from tests.consolidation.reconciliation_family import setattr_reconciliation_family

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_TARGET = "main"
_SLUG = "mission-base-claim-01M7560A"
_MISSION_ID = "01M7560A000000000000000000"
_PIN = "dep-pin"


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=True).stdout.strip()


def _commit_file(repo: Path, path: str, content: str, message: str | None = None) -> str:
    target = repo / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    _git(repo, "add", path)
    _git(repo, "commit", "-qm", message or f"add {path}")
    return _git(repo, "rev-parse", "HEAD")


def _manifest() -> LanesManifest:
    return LanesManifest(
        version=1,
        mission_slug=_SLUG,
        mission_id=_MISSION_ID,
        mission_branch=f"kitty/mission-{_SLUG}",
        target_branch=_TARGET,
        lanes=[
            ExecutionLane(
                lane_id="lane-a",
                wp_ids=("WP01",),
                write_scope=("u",),
                predicted_surfaces=("code",),
                depends_on_lanes=(),
                parallel_group=0,
            )
        ],
        computed_at="2026-11-12T00:00:00+00:00",
        computed_from="test-mission-base-claim",
    )


def _init(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", _TARGET)
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "user.email", "test@example.invalid")
    _git(repo, "config", "commit.gpgsign", "false")
    return repo


@dataclass(frozen=True)
class _Fork:
    repo: Path
    manifest: LanesManifest
    window_base: str
    base: str
    scaffold: str
    lane_commit: str
    pin_merge: str
    pre_mission: frozenset[str]


@pytest.fixture
def fork_repo(tmp_path: Path) -> _Fork:
    """The #7560 fork shape: the Mission branch is cut from the pin of a fork the target lacks.

    ``main``: R -> T. ``dep-pin``: R -> P1 -> (merge of Q) -> P2. The Mission branch starts at
    P2 (the Mission base): S scaffolds ``kitty-specs/<slug>/``, the lane adds L on top of S, and
    the Mission branch fast-forwards to L. The window base is T, so ``T..P2`` is pre-Mission.
    """
    repo = _init(tmp_path)
    root = _commit_file(repo, "README.md", "root\n")
    window_base = _commit_file(repo, "t.txt", "target\n")
    _git(repo, "checkout", "-q", "-b", _PIN, root)
    p1 = _commit_file(repo, "p/one.txt", "one\n")
    _git(repo, "checkout", "-q", "-b", "pin-side", p1)
    q = _commit_file(repo, "p/q.txt", "q\n")
    _git(repo, "checkout", "-q", _PIN)
    _git(repo, "merge", "-q", "--no-ff", "--no-edit", "pin-side")
    pin_merge = _git(repo, "rev-parse", "HEAD")
    base = _commit_file(repo, "p/two.txt", "two\n")

    manifest = _manifest()
    _git(repo, "checkout", "-q", "-b", manifest.mission_branch, base)
    scaffold = _commit_file(repo, f"kitty-specs/{_SLUG}/spec.md", "# spec\n")
    lane_branch = lane_created_branch(manifest, "lane-a")
    _git(repo, "checkout", "-q", "-b", lane_branch, scaffold)
    lane_commit = _commit_file(repo, "u/own.txt", "own\n")
    _git(repo, "checkout", "-q", manifest.mission_branch)
    _git(repo, "merge", "-q", "--ff-only", lane_branch)
    return _Fork(repo, manifest, window_base, base, scaffold, lane_commit, pin_merge, frozenset({p1, q, pin_merge, base}))


def _resolve(fork: _Fork, ref: str, *, pre_mission: frozenset[str] = frozenset()) -> ExternalDependencyAttribution:
    return resolve_external_dependency_refs(
        fork.repo,
        refs=(ref,),
        window_base=fork.window_base,
        mission_branch=fork.manifest.mission_branch,
        lanes_manifest=fork.manifest,
        coord_base_ref=fork.scaffold,
        pre_mission=pre_mission,
    )


# --- T013: the guard walks -------------------------------------------------------------


def test_fork_pin_is_declarable_once_pre_mission_history_leaves_the_spine(fork_repo: _Fork) -> None:
    """Red control first: without the pre-Mission set the pin's commits sit on the Mission spine."""
    unbounded = _resolve(fork_repo, _PIN)
    assert unbounded.refusal is not None
    assert f"Error code: {DEPENDENCY_REF_COVERS_MISSION_WORK}." in unbounded.refusal

    bounded = _resolve(fork_repo, _PIN, pre_mission=fork_repo.pre_mission)
    assert bounded.refusal is None
    # The declared window is unchanged: window_base..ref, not bounded at the base.
    assert bounded.shas == fork_repo.pre_mission
    assert bounded.pins == {_PIN: fork_repo.base}


def test_post_base_commit_on_the_mission_branch_still_refuses(fork_repo: _Fork) -> None:
    """A commit the Mission authored after its base is Mission work, whatever side branch names it."""
    repo = fork_repo.repo
    direct = _commit_file(repo, "m.txt", "direct\n", "direct commit on the mission branch")
    _git(repo, "branch", "side", direct)

    outcome = _resolve(fork_repo, "side", pre_mission=fork_repo.pre_mission)

    assert outcome.refusal is not None
    assert f"Error code: {DEPENDENCY_REF_COVERS_MISSION_WORK}." in outcome.refusal
    assert direct[:10] in outcome.refusal
    assert not outcome.shas and not outcome.blobs


def test_recorded_tip_walk_skips_pre_mission_history_only(fork_repo: _Fork) -> None:
    repo, window_base, base, lane_commit = fork_repo.repo, fork_repo.window_base, fork_repo.base, fork_repo.lane_commit
    pre_mission = fork_repo.pre_mission
    window = _git(repo, "rev-list", f"{window_base}..{lane_commit}").splitlines()
    tip_on_base = {base: "kitty/mission-x-lane-z"}

    # A recorded tip at the Mission base: its first-parent history is all pre-Mission.
    assert _recorded_work_hit(repo, window_base, window, frozenset(), tip_on_base) is not None
    assert _recorded_work_hit(repo, window_base, window, frozenset(), tip_on_base, pre_mission) is None

    # A recorded lane head above the base still hits, on the post-base commit itself.
    hit = _recorded_work_hit(repo, window_base, window, frozenset({lane_commit}), tip_on_base, pre_mission)
    assert hit is not None
    assert hit[0] == lane_commit
    assert hit[0] not in pre_mission


# --- T012: the pre-Mission attribution --------------------------------------------------


def test_pre_mission_attribution_carries_shas_and_final_state(fork_repo: _Fork) -> None:
    repo, window_base, base = fork_repo.repo, fork_repo.window_base, fork_repo.base
    mission_base = MissionBase(base, MissionBaseProvenance.RECORDED)

    history = _pre_mission_attribution(repo, window_base, mission_base, feature_dir=None, lanes_manifest=None)

    assert history.base == mission_base
    assert history.shas == fork_repo.pre_mission
    assert {path for path, _blob in history.blobs} == {"p/one.txt", "p/q.txt", "p/two.txt"}
    assert history.deletions == frozenset()


def test_pre_mission_blobs_are_read_from_the_base_tree_not_a_side_branch_walk(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A side branch's newer intermediate blob is not the range's final state: the base tree is."""
    repo = _init(tmp_path)
    window_base = _commit_file(repo, "README.md", "root\n")
    monkeypatch.setenv("GIT_COMMITTER_DATE", "2020-01-01T00:00:00Z")
    _git(repo, "checkout", "-q", "-b", "dep")
    _commit_file(repo, "f.txt", "chain\n")
    chain_blob = _git(repo, "rev-parse", "HEAD:f.txt")
    monkeypatch.setenv("GIT_COMMITTER_DATE", "2021-01-01T00:00:00Z")
    _git(repo, "checkout", "-q", "-b", "side", window_base)
    _commit_file(repo, "f.txt", "side\n")
    side_blob = _git(repo, "rev-parse", "HEAD:f.txt")
    monkeypatch.setenv("GIT_COMMITTER_DATE", "2022-01-01T00:00:00Z")
    _git(repo, "checkout", "-q", "dep")
    _git(repo, "merge", "-q", "--no-ff", "-s", "ours", "-m", "merge side keeping the chain's f.txt", "side")
    base = MissionBase(_git(repo, "rev-parse", "HEAD"), MissionBaseProvenance.RECORDED)

    history = _pre_mission_attribution(repo, window_base, base, feature_dir=None, lanes_manifest=None)

    assert history.blobs == frozenset({("f.txt", chain_blob)})
    assert ("f.txt", side_blob) not in history.blobs


def test_pre_mission_attribution_of_an_empty_range_costs_no_extra_probe(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _init(tmp_path)
    base = _commit_file(repo, "a.txt", "a\n")
    window_base = _commit_file(repo, "b.txt", "b\n")

    def _forbidden(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("an empty pre-Mission range must not walk")

    setattr_reconciliation_family(monkeypatch, "patch_id_of", _forbidden)
    setattr_reconciliation_family(monkeypatch, "_final_authored_walk", _forbidden)
    mission_base = MissionBase(base, MissionBaseProvenance.DERIVED, "no mission_base_sha recorded")

    assert _pre_mission_attribution(repo, window_base, mission_base, feature_dir=None, lanes_manifest=None) == PreMissionHistory(mission_base)


def test_pre_mission_probe_failure_degrades_to_todays_bound(fork_repo: _Fork, monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom(*_args: object, **_kwargs: object) -> tuple[str, ...]:
        raise GitProbeError("rev-list exploded")

    monkeypatch.setattr(reconciliation_closed_world, "pre_mission_history", _boom)
    base = fork_repo.base

    history = _pre_mission_attribution(
        fork_repo.repo, fork_repo.window_base, MissionBase(base, MissionBaseProvenance.RECORDED), feature_dir=None, lanes_manifest=None
    )

    assert history.shas == frozenset()
    assert history.blobs == frozenset() and history.deletions == frozenset()
    assert history.base.sha is None
    assert history.base.provenance is MissionBaseProvenance.UNAVAILABLE
    assert history.base.reason == "a git probe failed"  # a short clause: the raw git error never reaches the note
    assert history.base.kind is MissionBaseReason.PROBE_FAILED


def test_pre_mission_range_holding_a_recorded_lane_head_is_degraded(fork_repo: _Fork) -> None:
    """HIGH-1: a ``lane_head`` stamp of this Mission inside ``window_base..base`` means the base sits above Mission work."""
    repo, manifest, base = fork_repo.repo, fork_repo.manifest, fork_repo.base
    feature_dir = _write_mission(repo, manifest, claim_stamp=fork_repo.pin_merge, approve_stamp=fork_repo.lane_commit, mission_base_sha=base)

    history = _pre_mission_attribution(
        repo, fork_repo.window_base, MissionBase(base, MissionBaseProvenance.RECORDED), feature_dir=feature_dir, lanes_manifest=manifest
    )

    assert history == PreMissionHistory(
        MissionBase(None, MissionBaseProvenance.UNAVAILABLE, "pre-Mission range holds Mission work", MissionBaseReason.RANGE_HOLDS_MISSION_WORK)
    )


def test_pre_mission_range_holding_a_recorded_lane_tip_is_degraded(fork_repo: _Fork) -> None:
    repo, manifest, base = fork_repo.repo, fork_repo.manifest, fork_repo.base
    feature_dir = _write_mission(repo, manifest, claim_stamp=fork_repo.scaffold, approve_stamp=fork_repo.lane_commit, mission_base_sha=base)
    _git(repo, "update-ref", f"refs/spec-kitty/lane-tip/{lane_created_branch(manifest, 'lane-a')}", fork_repo.pin_merge)

    history = _pre_mission_attribution(
        repo, fork_repo.window_base, MissionBase(base, MissionBaseProvenance.RECORDED), feature_dir=feature_dir, lanes_manifest=manifest
    )

    assert history.shas == frozenset() and history.base.sha is None
    assert history.base.kind is MissionBaseReason.RANGE_HOLDS_MISSION_WORK


def test_honest_pre_mission_range_passes_the_mission_work_guard(fork_repo: _Fork) -> None:
    repo, manifest, base = fork_repo.repo, fork_repo.manifest, fork_repo.base
    feature_dir = _write_mission(repo, manifest, claim_stamp=fork_repo.scaffold, approve_stamp=fork_repo.lane_commit, mission_base_sha=base)
    _git(repo, "update-ref", f"refs/spec-kitty/lane-tip/{lane_created_branch(manifest, 'lane-a')}", fork_repo.lane_commit)
    mission_base = MissionBase(base, MissionBaseProvenance.RECORDED)

    history = _pre_mission_attribution(repo, fork_repo.window_base, mission_base, feature_dir=feature_dir, lanes_manifest=manifest)

    assert history.base == mission_base and history.shas == fork_repo.pre_mission


def test_unreadable_mission_work_guard_degrades(fork_repo: _Fork, monkeypatch: pytest.MonkeyPatch) -> None:
    repo, manifest, base = fork_repo.repo, fork_repo.manifest, fork_repo.base
    feature_dir = _write_mission(repo, manifest, claim_stamp=fork_repo.scaffold, approve_stamp=fork_repo.lane_commit, mission_base_sha=base)
    mission_base = MissionBase(base, MissionBaseProvenance.RECORDED)
    (feature_dir / "status.events.jsonl").write_text("{not json\n", encoding="utf-8")

    unreadable_log = _pre_mission_attribution(repo, fork_repo.window_base, mission_base, feature_dir=feature_dir, lanes_manifest=manifest)
    assert unreadable_log.shas == frozenset() and unreadable_log.base.kind is MissionBaseReason.PROBE_FAILED

    def _boom(*_args: object, **_kwargs: object) -> dict[str, str]:
        raise GitProbeError("for-each-ref exploded")

    setattr_reconciliation_family(monkeypatch, "_mission_tip_shas", _boom)
    unreadable_tips = _pre_mission_attribution(repo, fork_repo.window_base, mission_base, feature_dir=None, lanes_manifest=manifest)
    assert unreadable_tips.shas == frozenset() and unreadable_tips.base.kind is MissionBaseReason.PROBE_FAILED


def test_claim_with_a_mission_stamp_below_the_base_exempts_nothing(fork_repo: _Fork) -> None:
    """The claim builder runs the guard: a forged base above a stamped Mission commit exempts no history."""
    repo, manifest, base = fork_repo.repo, fork_repo.manifest, fork_repo.base
    feature_dir = _write_mission(repo, manifest, claim_stamp=fork_repo.pin_merge, approve_stamp=fork_repo.lane_commit, mission_base_sha=base)

    claim = build_approved_wp_set(repo, feature_dir, manifest, coord_base_ref=fork_repo.scaffold, excluded_window_base=fork_repo.window_base)

    assert claim.pre_mission_shas == frozenset()
    assert claim.mission_base is not None and claim.mission_base.kind is MissionBaseReason.RANGE_HOLDS_MISSION_WORK


def test_lane_spine_below_the_coordination_base_skips_pre_mission_history(fork_repo: _Fork) -> None:
    """``_mission_spines``' lane-spine skip: a coordination base below the Mission base walks pre-Mission commits."""
    spines = _mission_spines(
        fork_repo.repo, fork_repo.manifest, coord_base_ref=fork_repo.window_base, window_base=fork_repo.window_base, pre_mission=fork_repo.pre_mission
    )

    assert not set(spines) & fork_repo.pre_mission
    lane_label = "lane lane-a's first-parent spine"
    assert spines[fork_repo.lane_commit] == lane_label and spines[fork_repo.scaffold] == lane_label


# --- T014: the note line ---------------------------------------------------------------


def test_mission_base_note_cases() -> None:
    sha = "0123456789abcdef0123456789abcdef01234567"
    derived = MissionBase(sha, MissionBaseProvenance.DERIVED, "no mission_base_sha recorded")
    with_history = ApprovedWpCommitSet(mission_base=derived, pre_mission_shas=frozenset({"a", "b"}))
    assert mission_base_note(with_history) == (
        "Mission base 0123456789 (derived: no mission_base_sha recorded): 2 commit(s) of history the target lacks "
        "predate this Mission and are not judged as Mission work (#7560)."
    )
    recorded = ApprovedWpCommitSet(mission_base=MissionBase(sha, MissionBaseProvenance.RECORDED), pre_mission_shas=frozenset({"a"}))
    assert mission_base_note(recorded) == (
        "Mission base 0123456789 (recorded): 1 commit(s) of history the target lacks predate this Mission and are not judged as Mission work (#7560)."
    )

    unavailable = ApprovedWpCommitSet(mission_base=MissionBase(None, MissionBaseProvenance.UNAVAILABLE, "git probe failed: x", MissionBaseReason.PROBE_FAILED))
    assert mission_base_note(unavailable) == ("Mission base unavailable (a git probe failed); reconciliation windows are bounded by the target's pre-run tip only.")

    assert mission_base_note(ApprovedWpCommitSet(mission_base=MissionBase(sha, MissionBaseProvenance.RECORDED))) is None
    assert mission_base_note(ApprovedWpCommitSet()) is None


# --- T012 / NFR-001: the claim builder --------------------------------------------------

_CHAIN = (("planned", "claimed"), ("claimed", "in_progress"), ("in_progress", "for_review"), ("for_review", "in_review"), ("in_review", "approved"))


def _write_mission(repo: Path, manifest: LanesManifest, *, claim_stamp: str, approve_stamp: str, mission_base_sha: str) -> Path:
    feature_dir = repo / "kitty-specs" / _SLUG
    (feature_dir / "tasks").mkdir(parents=True, exist_ok=True)
    (feature_dir / "meta.json").write_text(
        json.dumps(
            {
                "mission_slug": _SLUG,
                "mission_id": _MISSION_ID,
                "mission_type": "software-dev",
                "target_branch": _TARGET,
                "mission_base_sha": mission_base_sha,
            }
        ),
        encoding="utf-8",
    )
    (feature_dir / "tasks" / "WP01-work.md").write_text(
        "---\nwork_package_id: WP01\ntitle: WP01 work\ndependencies: []\nsubtasks: []\nowned_files:\n  - u/**\n---\n# WP01\n",
        encoding="utf-8",
    )
    # The planning commit opens the owned-file evidence window (#6715): the claim stamp is on the lane.
    manifest.planning_commit_sha = claim_stamp
    write_lanes_json(feature_dir, manifest)
    events = []
    for seq, (frm, to) in enumerate(_CHAIN):
        row: dict[str, object] = {
            "actor": "reviewer-renata" if to == "approved" else "claude",
            "at": f"2026-11-12T00:00:{seq:02d}+00:00",
            "event_id": f"01M7560{seq:019d}",
            "evidence": None,
            "execution_mode": "worktree",
            "feature_slug": _SLUG,
            "force": False,
            "from_lane": frm,
            "reason": None,
            "review_ref": None,
            "to_lane": to,
            "wp_id": "WP01",
        }
        stamp = claim_stamp if to in ("claimed", "in_progress") else approve_stamp if to == "approved" else None
        if stamp is not None:
            row["policy_metadata"] = {"lane_head": stamp}
        events.append(row)
    (feature_dir / "status.events.jsonl").write_text("".join(json.dumps(e, sort_keys=True) + "\n" for e in events), encoding="utf-8")
    return feature_dir


def test_claim_where_the_target_reaches_the_base_is_unchanged(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """NFR-001: when the target already reaches the Mission base, only ``mission_base`` differs from today's claim."""
    repo = _init(tmp_path)
    base = _commit_file(repo, "README.md", "root\n")
    manifest = _manifest()
    lane_branch = lane_created_branch(manifest, "lane-a")
    _git(repo, "checkout", "-q", "-b", lane_branch, base)
    # The Mission's scaffold commit anchors the recorded base (its first parent is the origin).
    scaffold = _commit_file(repo, f"kitty-specs/{manifest.mission_slug}/spec.md", "spec\n")
    lane_commit = _commit_file(repo, "u/own.txt", "own\n")
    _git(repo, "branch", manifest.mission_branch, lane_commit)
    _git(repo, "checkout", "-q", _TARGET)
    feature_dir = _write_mission(repo, manifest, claim_stamp=scaffold, approve_stamp=lane_commit, mission_base_sha=base)

    claim = build_approved_wp_set(repo, feature_dir, manifest, coord_base_ref=scaffold, excluded_window_base=base)
    assert claim.refusal is None, claim.refusal
    assert claim.mission_base == MissionBase(base, MissionBaseProvenance.RECORDED)
    assert claim.pre_mission_shas == frozenset()
    assert claim.pre_mission_blobs == frozenset() and claim.pre_mission_deletions == frozenset()
    assert mission_base_note(claim) is None

    unavailable = MissionBase(None, MissionBaseProvenance.UNAVAILABLE, "forced")
    monkeypatch.setattr(reconciliation_claim, "resolve_mission_base", lambda *_a, **_k: unavailable)
    today = build_approved_wp_set(repo, feature_dir, manifest, coord_base_ref=scaffold, excluded_window_base=base)
    assert today.mission_base == unavailable
    assert replace(claim, mission_base=unavailable) == today
    assert [f.name for f in fields(ApprovedWpCommitSet) if getattr(claim, f.name) != getattr(today, f.name)] == ["mission_base"]


def test_claim_on_a_fork_carries_the_pre_mission_history(fork_repo: _Fork) -> None:
    repo, manifest = fork_repo.repo, fork_repo.manifest
    base, scaffold, lane_commit, window_base = fork_repo.base, fork_repo.scaffold, fork_repo.lane_commit, fork_repo.window_base
    feature_dir = _write_mission(repo, manifest, claim_stamp=scaffold, approve_stamp=lane_commit, mission_base_sha=base)

    claim = build_approved_wp_set(repo, feature_dir, manifest, coord_base_ref=scaffold, excluded_window_base=window_base)

    assert claim.refusal is None, claim.refusal
    assert claim.mission_base == MissionBase(base, MissionBaseProvenance.RECORDED)
    assert claim.pre_mission_shas == fork_repo.pre_mission
    assert {path for path, _blob in claim.pre_mission_blobs} == {"p/one.txt", "p/q.txt", "p/two.txt"}
    note = mission_base_note(claim)
    assert note is not None and note.startswith(f"Mission base {base[:10]} (recorded): 4 commit(s)")


def test_refused_claim_still_carries_the_mission_base(fork_repo: _Fork) -> None:
    """A REFUSE-shaped claim carries ``mission_base`` (the note can print), and no pre-Mission exemption."""
    repo, manifest = fork_repo.repo, fork_repo.manifest
    base, scaffold, window_base = fork_repo.base, fork_repo.scaffold, fork_repo.window_base
    feature_dir = _write_mission(repo, manifest, claim_stamp=scaffold, approve_stamp=scaffold, mission_base_sha=base)

    claim = build_approved_wp_set(repo, feature_dir, manifest, coord_base_ref=scaffold, excluded_window_base=window_base, external_dependency_refs=("no-such-ref",))

    assert claim.refusal is not None
    assert claim.mission_base == MissionBase(base, MissionBaseProvenance.RECORDED)
    assert claim.pre_mission_shas == frozenset()


@pytest.mark.parametrize("json_output", [False, True])
def test_the_note_is_printed_but_never_under_json(json_output: bool) -> None:
    """One printer serves the run and the forecast; ``--json`` (quiet) keeps the payload valid JSON."""
    from rich.console import Console

    from specify_cli.consolidation.reconciliation import print_mission_base_note

    sink = io.StringIO()
    shown = Console(file=sink, width=400, color_system=None)
    claim = ApprovedWpCommitSet(mission_base=MissionBase(None, MissionBaseProvenance.UNAVAILABLE, "no [base]"))

    print_mission_base_note(claim, shown, quiet=json_output)
    print_mission_base_note(None, shown)
    print_mission_base_note(ApprovedWpCommitSet(), shown)

    expected = "Note: Mission base unavailable (no [base]); reconciliation windows are bounded by the target's pre-run tip only."
    assert sink.getvalue().strip() == ("" if json_output else expected)
