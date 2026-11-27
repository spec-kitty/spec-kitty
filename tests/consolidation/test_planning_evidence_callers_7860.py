"""#7860 (T019, FR-003/FR-005): every caller of the evidence axis judges a default Mission's planning lane alike.

One real-git fixture: a default Mission that has not landed, its Mission branch held by the
repository root checkout, two planning work packages in ``lane-planning``, each claimed and
approved in its own status commit. WP02 committed its owned file on the Mission branch after its
claim; WP03 is hollow. Each caller of the axis is driven:

* ``mission_evidence_report`` (``accept`` and the orchestrator API's ``accept-mission`` /
  ``consolidate-mission``);
* ``evaluate_evidence`` as ``reconciliation_claim.build_approved_wp_set`` calls it (the
  ``consolidate`` claim);
* ``plan_no_implementation_attestations`` (``--attest-no-implementation``): it lifts the hollow
  planning work package, and refuses a request it would not lift;
* ``move-task``'s evidence leg.

Every refusal carries the same window text, WP02 passes everywhere and WP03 is refused
everywhere. The sibling case (a commit inside WP02's window that touches only WP03's file) and the
wording of an unreadable window start (WP04 review) are pinned here as well.
"""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import pytest

import mission_runtime
from mission_runtime import ActionContextError
from specify_cli.cli.commands.agent import tasks_move_task as move_task_module
from specify_cli.consolidation import wp_evidence
from specify_cli.consolidation.no_implementation_attestation import AttestationError, plan_no_implementation_attestations
from specify_cli.lanes import single_branch_landing
from specify_cli.lanes.compute import PLANNING_LANE_ID
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.lanes.persistence import read_lanes_json, write_lanes_json
from specify_cli.status import materialize_snapshot, read_events
from specify_cli.status.models import Lane
from tests._support.git_cli import git_out

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_SLUG = "callers-01M8DDDD"
_MISSION_ID = "01M8DDDDDDDDDDDDDDDDDDDDDD"
_MISSION_BRANCH = f"kitty/mission-{_SLUG}"
_TARGET = "main"
_MISSION_DIR = f"kitty-specs/{_SLUG}"
_IMPLEMENTER = "claude:sonnet:implementer"
_REVIEWER = "codex:gpt:reviewer"
_OWNED = {"WP02": f"{_MISSION_DIR}/research/notes.md", "WP03": f"{_MISSION_DIR}/research/other.md"}
_Reason = Literal["git_unavailable", "no_commit", "ambiguous"]
_WINDOW = re.compile(r"[0-9a-f]{40}\.\." + re.escape(_MISSION_BRANCH) + re.escape(f" ({PLANNING_LANE_ID})"))


@dataclass
class _Fixture:
    repo: Path
    counter: list[int] = field(default_factory=lambda: [0])

    @property
    def feature_dir(self) -> Path:
        return self.repo / _MISSION_DIR

    def manifest(self) -> LanesManifest:
        manifest = read_lanes_json(self.feature_dir)
        assert manifest is not None
        return manifest


def _git(repo: Path, *args: str) -> str:
    return git_out(repo, *args).strip()


def _commit_file(repo: Path, relpath: str, text: str, message: str) -> str:
    path = repo / relpath
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    _git(repo, "add", "--", relpath)
    _git(repo, "commit", "-qm", message)
    return _git(repo, "rev-parse", "HEAD")


def _event(fx: _Fixture, wp_id: str, from_lane: str, to_lane: str, actor: str) -> dict[str, Any]:
    fx.counter[0] += 1
    n = fx.counter[0]
    return {
        "actor": actor,
        "at": f"2026-11-26T00:{n // 60:02d}:{n % 60:02d}+00:00",
        "event_id": f"01M8DD{n:020d}",
        "evidence": None,
        "execution_mode": "direct_repo",
        "mission_slug": _SLUG,
        "force": False,
        "from_lane": from_lane,
        "reason": None,
        "review_ref": None,
        "to_lane": to_lane,
        "wp_id": wp_id,
    }


def _transition(fx: _Fixture, wp_id: str, hops: Sequence[tuple[str, str, str]], message: str) -> None:
    """Append the hops as status events and commit them in one commit, as the Mission branch carries them."""
    log = fx.feature_dir / "status.events.jsonl"
    with log.open("a", encoding="utf-8") as handle:
        for from_lane, to_lane, actor in hops:
            handle.write(json.dumps(_event(fx, wp_id, from_lane, to_lane, actor), sort_keys=True) + "\n")
    _git(fx.repo, "add", "--", str(log.relative_to(fx.repo)))
    _git(fx.repo, "commit", "-qm", message)


def _claim(fx: _Fixture, wp_id: str) -> None:
    _transition(fx, wp_id, (("planned", "claimed", _IMPLEMENTER), ("claimed", "in_progress", _IMPLEMENTER)), f"chore: claim {wp_id}")


def _approve(fx: _Fixture, wp_id: str) -> None:
    hops = (("in_progress", "for_review", _IMPLEMENTER), ("for_review", "in_review", _REVIEWER), ("in_review", "approved", _REVIEWER))
    _transition(fx, wp_id, hops, f"chore: approve {wp_id}")


def _build(tmp_path: Path) -> _Fixture:
    """A default, not-landed Mission on its Mission branch (held by the repository root checkout), WP02 and WP03 planned."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", _TARGET)
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")
    _commit_file(repo, "README.md", "x\n", "init")
    pin = _git(repo, "rev-parse", "HEAD")
    _git(repo, "switch", "-qc", _MISSION_BRANCH)
    fx = _Fixture(repo)
    (fx.feature_dir / "tasks").mkdir(parents=True)
    meta = {
        "mission_slug": _SLUG,
        "mission_id": _MISSION_ID,
        "target_branch": _TARGET,
        "topology": "lanes_with_coord",
        "topology_source": "default",
        "mission_branch": _MISSION_BRANCH,
        "coordination_branch": _MISSION_BRANCH,
    }
    (fx.feature_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    for wp_id, owned in _OWNED.items():
        (fx.feature_dir / "tasks" / f"{wp_id}-work.md").write_text(
            f"---\nwork_package_id: {wp_id}\ntitle: {wp_id}\ndependencies: []\nexecution_mode: planning_artifact\nowned_files:\n  - {owned}\n---\n# {wp_id}\n",
            encoding="utf-8",
        )
    manifest = LanesManifest(
        version=1,
        mission_slug=_SLUG,
        mission_id=_MISSION_ID,
        mission_branch=_MISSION_BRANCH,
        target_branch=_TARGET,
        lanes=[ExecutionLane(PLANNING_LANE_ID, tuple(_OWNED), tuple(_OWNED.values()), (), (), 0)],
        computed_at="2026-11-26T00:00:00+00:00",
        computed_from="test",
        planning_artifact_wps=list(_OWNED),
        planning_commit_sha=pin,
    )
    write_lanes_json(fx.feature_dir, manifest)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "planning")
    return fx


@pytest.fixture
def mission(tmp_path: Path) -> _Fixture:
    """WP02 real (owned commit after its claim), WP03 hollow; both approved by an independent reviewer."""
    fx = _build(tmp_path)
    _claim(fx, "WP02")
    _commit_file(fx.repo, _OWNED["WP02"], "# notes\n", "feat(WP02): research notes")
    _claim(fx, "WP03")
    _approve(fx, "WP02")
    _approve(fx, "WP03")
    return fx


def _windows(text: str) -> set[str]:
    return set(_WINDOW.findall(text))


def _move_task_state(fx: _Fixture, wp_id: str) -> move_task_module._MoveTaskState:
    return move_task_module._MoveTaskState(
        task_id=wp_id,
        to=Lane.FOR_REVIEW.value,
        mission=_SLUG,
        agent="claude",
        assignee=None,
        shell_pid=None,
        note=None,
        review_feedback_file=None,
        approval_ref=None,
        reviewer=None,
        self_review_fallback=False,
        intended_reviewer=None,
        reviewer_failure_reason=None,
        done_override_reason=None,
        force=False,
        tracker_ref=None,
        skip_review_artifact_check=False,
        auto_commit=None,
        json_output=True,
        target_lane=Lane.FOR_REVIEW,
        feature_dir=fx.feature_dir,
        old_lane=Lane.IN_PROGRESS,
        mission_slug=_SLUG,
        main_repo_root=fx.repo,
    )


def _move_task(fx: _Fixture, wp_id: str, monkeypatch: pytest.MonkeyPatch) -> str | None:
    """``move-task``'s evidence leg for *wp_id*: ``None`` on a pass, else the refusal text.

    Only its inputs are supplied (the manifest, the owned patterns, the event log); the decision
    is the real one.
    """
    monkeypatch.setattr(move_task_module, "_mt_lanes_manifest", lambda _st: fx.manifest())
    monkeypatch.setattr(move_task_module, "_mt_owned_file_patterns", lambda st: (_OWNED[st.task_id],))
    monkeypatch.setattr(move_task_module, "_mt_status_events", lambda st: read_events(st.feature_dir))
    monkeypatch.setattr(single_branch_landing, "is_single_branch_mission", lambda _repo, _manifest: False)
    try:
        move_task_module._mt_require_implementation_evidence(_move_task_state(fx, wp_id))
    except ActionContextError as exc:
        return str(exc)
    return None


def test_every_caller_passes_the_real_wp_and_refuses_the_hollow_one_on_one_window(mission: _Fixture, monkeypatch: pytest.MonkeyPatch) -> None:
    fx = mission
    work_packages = materialize_snapshot(fx.feature_dir).work_packages or {}

    accept_report = wp_evidence.mission_evidence_report(fx.repo, fx.feature_dir, fx.manifest(), excluded_canceled_wp_ids=frozenset())
    claim_report = wp_evidence.evaluate_evidence(fx.repo, fx.feature_dir, fx.manifest(), work_packages, frozenset(), events=lambda: read_events(fx.feature_dir))
    lifted = plan_no_implementation_attestations(fx.feature_dir, fx.manifest(), ["WP03"], "owes no implementation", repo_root=fx.repo, excluded_canceled_wp_ids=())
    real_move = _move_task(fx, "WP02", monkeypatch)
    hollow_move = _move_task(fx, "WP03", monkeypatch)

    assert accept_report.verdicts == {"WP03": wp_evidence.IMPLEMENTATION_MISSING}
    assert claim_report.verdicts == {"WP03": wp_evidence.IMPLEMENTATION_MISSING}
    assert lifted == {"WP03": "approved"}, "the attestation lifts the hollow planning work package"
    assert real_move is None, real_move
    assert hollow_move is not None and wp_evidence.IMPLEMENTATION_MISSING in hollow_move
    assert accept_report.refusal is not None and claim_report.refusal is not None
    windows = [_windows(text) for text in (accept_report.refusal, claim_report.refusal, hollow_move)]
    assert len(windows[0]) == 1, accept_report.refusal
    assert windows[0] == windows[1] == windows[2], f"every caller names the same window: {windows}"


def test_the_attestation_lifts_only_a_real_implementation_missing(mission: _Fixture, monkeypatch: pytest.MonkeyPatch) -> None:
    """A planning window that cannot be proven is not lifted by ``--attest-no-implementation`` (nothing recorded)."""
    fx = mission

    def _unprovable(*_args: object, **_kwargs: object) -> str:
        raise mission_runtime.ClaimCommitUnresolved("WP03", "ambiguous")

    monkeypatch.setattr(mission_runtime, "commit_introducing_status_event", _unprovable)

    with pytest.raises(AttestationError) as refused:
        plan_no_implementation_attestations(fx.feature_dir, fx.manifest(), ["WP03"], "owes no implementation", repo_root=fx.repo, excluded_canceled_wp_ids=())

    assert wp_evidence.EVIDENCE_WINDOW_UNCOMPUTABLE in str(refused.value)


def test_a_sibling_commit_inside_the_window_is_not_evidence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Two planning WPs share the checkout: a commit in WP02's window touching only WP03's file is WP03's, not WP02's."""
    fx = _build(tmp_path)
    _claim(fx, "WP02")
    _claim(fx, "WP03")
    _commit_file(fx.repo, _OWNED["WP03"], "# other\n", "feat(WP03): other research")
    _approve(fx, "WP02")
    _approve(fx, "WP03")

    report = wp_evidence.mission_evidence_report(fx.repo, fx.feature_dir, fx.manifest(), excluded_canceled_wp_ids=frozenset())
    hollow_move = _move_task(fx, "WP02", monkeypatch)
    sibling_move = _move_task(fx, "WP03", monkeypatch)

    assert report.verdicts == {"WP02": wp_evidence.IMPLEMENTATION_MISSING}
    assert hollow_move is not None and f"{wp_evidence.IMPLEMENTATION_MISSING}: WP02" in hollow_move
    assert sibling_move is None, sibling_move


# ---------------------------------------------------------------- the unproven start's wording (WP04 review)


@pytest.mark.parametrize(
    ("reason", "code", "present", "absent"),
    [
        ("git_unavailable", wp_evidence.IMPLEMENTATION_UNREADABLE, "git could not read the history of the Mission branch", "commit its status events"),
        ("no_commit", wp_evidence.EVIDENCE_WINDOW_UNCOMPUTABLE, "commit its status events on the Mission branch", "git could not read"),
        ("ambiguous", wp_evidence.EVIDENCE_WINDOW_UNCOMPUTABLE, "no single commit on the Mission branch", "git could not read"),
    ],
)
def test_an_unproven_window_start_is_worded_by_its_reason(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, reason: _Reason, code: str, present: str, absent: str
) -> None:
    fx = _build(tmp_path)
    _claim(fx, "WP02")

    def _unresolved(*_args: object, **_kwargs: object) -> str:
        raise mission_runtime.ClaimCommitUnresolved("WP02", reason)

    monkeypatch.setattr(mission_runtime, "commit_introducing_status_event", _unresolved)
    lane = fx.manifest().lanes[0]

    with pytest.raises(wp_evidence.PlanningWindowUnresolved) as refused:
        wp_evidence.planning_evidence_window(fx.repo, fx.manifest(), lane, "WP02", lambda: read_events(fx.feature_dir))

    assert refused.value.code == code
    assert present in refused.value.detail
    assert absent not in refused.value.detail


# ---------------------------------------------------------------- the claim's event reader (review 5 issue 3)


class _ReachedAuthorship(Exception):
    """Raised by the spy once the claim has handed the authorship walk its inputs."""


def test_the_claim_hands_the_authorship_walk_the_reader_that_proves_each_window_start(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``build_approved_wp_set`` must pass ``_collect_authored`` the claim's event reader; without it the planning lane credits nothing.

    The window starts are read with the real reader (no autouse stub here), so dropping
    ``events=event_log.read`` from the claim, or handing a reader that cannot prove the claims,
    turns this red.
    """
    from specify_cli.consolidation import planning_lane_walk as planning_walk
    from specify_cli.consolidation import reconciliation_claim

    fx = _build(tmp_path)
    _claim(fx, "WP02")
    claim_wp02 = _git(fx.repo, "rev-parse", "HEAD")
    _commit_file(fx.repo, _OWNED["WP02"], "# notes\n", "feat(WP02): research notes")
    _claim(fx, "WP03")
    claim_wp03 = _git(fx.repo, "rev-parse", "HEAD")
    _commit_file(fx.repo, _OWNED["WP03"], "# other\n", "feat(WP03): other research")
    _approve(fx, "WP02")
    _approve(fx, "WP03")
    seen: dict[str, object] = {}

    def _spy(*_args: object, **kwargs: object) -> object:
        seen.update(kwargs)
        raise _ReachedAuthorship

    monkeypatch.setattr(reconciliation_claim, "_collect_authored", _spy)
    manifest = fx.manifest()
    with pytest.raises(_ReachedAuthorship):
        reconciliation_claim.build_approved_wp_set(fx.repo, fx.feature_dir, manifest, coord_base_ref=_git(fx.repo, "rev-parse", "HEAD"))

    events = seen.get("events")
    assert callable(events), f"the claim handed the authorship walk no event reader: {seen.get('events')!r}"
    lane = manifest.lanes[0]
    assert planning_walk._planning_window_starts(fx.repo, manifest, lane, ("WP02", "WP03"), events) == {"WP02": claim_wp02, "WP03": claim_wp03}


@pytest.mark.parametrize("recorded", [True, False], ids=["recorded", "derived"])
def test_the_claim_starts_the_taint_walk_only_at_a_recorded_mission_base(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, recorded: bool) -> None:
    """Review 10 issue 1: ``build_approved_wp_set`` hands the taint walk the Mission base only when it is recorded.

    A derived base (the scaffold commit's first parent) can sit above a commit made on the Mission
    branch before the scaffold, so it must start nothing (mirrors ``_pre_mission_attribution``).
    The notes receive the whole base so they can name a derived one.
    """
    from specify_cli.consolidation import reconciliation_claim
    from specify_cli.consolidation.mission_base import MissionBaseProvenance
    from specify_cli.consolidation.planning_lane_scope import planning_lane_notes as real_notes
    from specify_cli.consolidation.reconciliation_authorship import _collect_authored as real_collect

    fx = _build(tmp_path)
    cut = _git(fx.repo, "rev-parse", f"{_TARGET}")
    if recorded:
        meta = json.loads((fx.feature_dir / "meta.json").read_text(encoding="utf-8"))
        meta["mission_base_sha"] = cut
        (fx.feature_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
        _git(fx.repo, "commit", "-qam", "record the Mission base")
    _claim(fx, "WP02")
    _commit_file(fx.repo, _OWNED["WP02"], "# notes\n", "feat(WP02): research notes")
    _approve(fx, "WP02")
    _claim(fx, "WP03")
    _commit_file(fx.repo, _OWNED["WP03"], "# other\n", "feat(WP03): other research")
    _approve(fx, "WP03")
    seen: dict[str, object] = {}

    def _collect(*args: Any, **kwargs: Any) -> Any:
        seen["taint"] = kwargs.get("mission_base")
        return real_collect(*args, **kwargs)

    def _notes(*args: Any) -> Any:
        seen["notes"] = args[-1]
        return real_notes(*args)

    monkeypatch.setattr(reconciliation_claim, "_collect_authored", _collect)
    monkeypatch.setattr(reconciliation_claim, "planning_lane_notes", _notes)

    claim = reconciliation_claim.build_approved_wp_set(fx.repo, fx.feature_dir, fx.manifest(), coord_base_ref=_git(fx.repo, "rev-parse", "HEAD"))

    assert claim.refusal is None, claim.refusal
    base = seen["notes"]
    assert getattr(base, "sha", None) == cut
    assert getattr(base, "provenance", None) is (MissionBaseProvenance.RECORDED if recorded else MissionBaseProvenance.DERIVED)
    assert seen["taint"] == (cut if recorded else None)


def test_the_claim_names_a_planning_lane_a_canceled_work_package_empties(tmp_path: Path) -> None:
    """Review 5 issue 2: the claim carries the planning lane's note (ruling R1), naming the lane and the canceled work package."""
    from specify_cli.consolidation import reconciliation_claim

    fx = _build(tmp_path)
    _claim(fx, "WP02")
    _commit_file(fx.repo, _OWNED["WP02"], "# notes\n", "feat(WP02): research notes")
    _approve(fx, "WP02")
    _transition(fx, "WP03", (("planned", "canceled", "op"),), "chore: drop WP03")

    claim = reconciliation_claim.build_approved_wp_set(
        fx.repo, fx.feature_dir, fx.manifest(), coord_base_ref=_git(fx.repo, "rev-parse", "HEAD"), excluded_canceled_wp_ids=("WP03",)
    )

    assert claim.refusal is None, claim.refusal
    (lane_note,) = claim.planning_lane_notes
    note = lane_note.text
    assert note.startswith(f"The planning lane {PLANNING_LANE_ID} credits none of its work") and "WP03 is canceled" in note
