"""#7860: ``move-task``'s evidence leg and auto-commit guard for a default Mission's planning lane.

Before a default Mission lands, a planning work package is judged on its own window on the Mission
branch (the coordination branch): ``move-task`` asks the one decision,
:func:`~specify_cli.consolidation.wp_evidence.planning_evidence_window`, as consolidate's claim
does, names the Mission branch in its refusal, and appends the in-flight guidance (FR-007) only for
owned work found on the target branch only. Its deliverables auto-commit never runs in the shared
checkout of the Mission branch, so a sibling work package's dirty files stay untouched (FR-013).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from mission_runtime import ActionContextError
from specify_cli.cli.commands.agent import tasks as tasks_module
from specify_cli.cli.commands.agent import tasks_move_task as move_task_module
from specify_cli.consolidation import wp_evidence
from specify_cli.consolidation.git_probes import GitProbeError
from specify_cli.lanes import single_branch_landing
from specify_cli.lanes.compute import PLANNING_LANE_ID
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.lanes.persistence import write_lanes_json
from specify_cli.status import read_events
from specify_cli.status.models import Lane
from specify_cli.workspace.context import MISSION_BRANCH_CHECKOUT_KIND, REPO_ROOT_KIND, ResolvedWorkspace
from tests._support.git_cli import git_out

pytestmark = [pytest.mark.git_repo]

_SLUG = "fx-01M8A725"
_MISSION_BRANCH = f"kitty/mission-{_SLUG}"
_PIN = "plan0000"
_START = "claim0000"
_OWNED = f"kitty-specs/{_SLUG}/research/notes.md"


def _manifest(pin: str = _PIN) -> LanesManifest:
    return LanesManifest(
        version=1,
        mission_slug=_SLUG,
        mission_id=None,
        mission_branch=_MISSION_BRANCH,
        target_branch="main",
        lanes=[ExecutionLane(PLANNING_LANE_ID, ("WP02",), (_OWNED,), (), (), 0)],
        computed_at="2026-11-26T00:00:00+00:00",
        computed_from="test",
        planning_artifact_wps=["WP02"],
        planning_commit_sha=pin,
    )


def _state(repo: Path = Path(), *, target_lane: Lane = Lane.FOR_REVIEW, json_output: bool = True) -> move_task_module._MoveTaskState:
    return move_task_module._MoveTaskState(
        task_id="WP02",
        to=target_lane.value,
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
        json_output=json_output,
        target_lane=target_lane,
        feature_dir=repo / "kitty-specs" / _SLUG,
        old_lane=Lane.IN_PROGRESS,
        mission_slug=_SLUG,
        main_repo_root=repo,
    )


# ---------------------------------------------------------------- unit: the evidence leg


class _Facts:
    def __init__(self) -> None:
        self.windows: list[tuple[str, str]] = []
        self.paths: set[str] = set()
        self.planning_window: tuple[str, str] | None | Exception = (_START, _MISSION_BRANCH)
        self.target_only: tuple[str, ...] | Exception = ()


@pytest.fixture
def planning(monkeypatch: pytest.MonkeyPatch) -> _Facts:
    facts = _Facts()

    def _paths(_repo: Path, window: tuple[str, str], _slug: str) -> frozenset[str]:
        facts.windows.append(window)
        return frozenset(facts.paths)

    def _window(*_args: object, **_kwargs: object) -> tuple[str, str] | None:
        if isinstance(facts.planning_window, Exception):
            raise facts.planning_window
        return facts.planning_window

    def _target_only(*_args: object, **_kwargs: object) -> tuple[str, ...]:
        if isinstance(facts.target_only, Exception):
            raise facts.target_only
        return facts.target_only

    monkeypatch.setattr(move_task_module, "_mt_lanes_manifest", lambda _st: _manifest())
    monkeypatch.setattr(single_branch_landing, "is_single_branch_mission", lambda _repo, _manifest: False)
    monkeypatch.setattr(wp_evidence, "evidence_paths", _paths)
    monkeypatch.setattr(wp_evidence, "planning_evidence_window", _window)
    monkeypatch.setattr(wp_evidence, "target_only_owned_commits", _target_only)
    monkeypatch.setattr(move_task_module, "_mt_owned_file_patterns", lambda _st: (_OWNED,))
    monkeypatch.setattr(move_task_module, "_mt_mission_branch_checkout", lambda _st, _m: ", checked out in /coord")
    return facts


@pytest.mark.unit
def test_owned_work_on_the_mission_branch_passes_on_the_planning_window(planning: _Facts) -> None:
    planning.paths = {_OWNED}

    move_task_module._mt_require_implementation_evidence(_state())

    assert planning.windows == [(_START, _MISSION_BRANCH)]


@pytest.mark.unit
def test_a_hollow_planning_work_package_is_refused_naming_the_mission_branch(planning: _Facts) -> None:
    with pytest.raises(ActionContextError) as refused:
        move_task_module._mt_require_implementation_evidence(_state())

    message = str(refused.value)
    assert refused.value.code == wp_evidence.IMPLEMENTATION_MISSING
    assert f"{_START}..{_MISSION_BRANCH} ({PLANNING_LANE_ID})" in message
    assert f"on the Mission branch {_MISSION_BRANCH} (the coordination branch, checked out in /coord)" in message
    assert "found on the target branch only" not in message, "a hollow work package never gets the in-flight addendum"


@pytest.mark.unit
def test_owned_work_on_the_target_only_is_named_with_both_remedies(planning: _Facts) -> None:
    planning.target_only = ("abc1234",)

    with pytest.raises(ActionContextError) as refused:
        move_task_module._mt_require_implementation_evidence(_state())

    message = str(refused.value)
    assert "found on the target branch only: abc1234" in message
    assert f"cherry-pick abc1234 onto the Mission branch {_MISSION_BRANCH}" in message
    assert f"{wp_evidence.ATTEST_NO_IMPLEMENTATION_FLAG} WP02" in message


@pytest.mark.unit
def test_a_probe_error_keeps_the_refusal(planning: _Facts) -> None:
    planning.target_only = GitProbeError("boom")

    with pytest.raises(ActionContextError) as refused:
        move_task_module._mt_require_implementation_evidence(_state())

    assert refused.value.code == wp_evidence.IMPLEMENTATION_MISSING
    assert "could not check the target branch: boom" in str(refused.value)


@pytest.mark.unit
@pytest.mark.parametrize("code", [wp_evidence.EVIDENCE_WINDOW_UNCOMPUTABLE, wp_evidence.IMPLEMENTATION_UNREADABLE])
def test_an_unprovable_planning_window_refuses(planning: _Facts, code: str) -> None:
    planning.planning_window = wp_evidence.PlanningWindowUnresolved(code, "the start cannot be proven")
    planning.paths = {_OWNED}

    with pytest.raises(ActionContextError) as refused:
        move_task_module._mt_require_implementation_evidence(_state())

    assert refused.value.code == code
    assert "the start cannot be proven" in str(refused.value)
    assert planning.windows == [], "nothing is diffed on an unprovable window"


@pytest.mark.unit
def test_every_other_shape_keeps_the_target_window(planning: _Facts) -> None:
    planning.planning_window = None
    planning.paths = {_OWNED}

    move_task_module._mt_require_implementation_evidence(_state())

    assert planning.windows == [(_PIN, "main")]


@pytest.mark.unit
def test_an_unreadable_window_diff_refuses_unreadable(planning: _Facts, monkeypatch: pytest.MonkeyPatch) -> None:
    def _broken(*_args: object, **_kwargs: object) -> frozenset[str]:
        raise GitProbeError("bad object")

    monkeypatch.setattr(wp_evidence, "evidence_paths", _broken)

    with pytest.raises(ActionContextError) as refused:
        move_task_module._mt_require_implementation_evidence(_state())

    assert refused.value.code == wp_evidence.IMPLEMENTATION_UNREADABLE
    assert f"Make the Mission branch {_MISSION_BRANCH} (the coordination branch) readable" in str(refused.value)


# ---------------------------------------------------------------- real git


def _git(repo: Path, *args: str) -> str:
    return git_out(repo, *args).strip()


def _event(n: int, from_lane: str, to_lane: str) -> dict[str, Any]:
    return {
        "actor": "claude:sonnet:implementer",
        "at": f"2026-11-26T00:00:{n:02d}+00:00",
        "event_id": f"01M8A7{n:020d}",
        "evidence": None,
        "execution_mode": "direct_repo",
        "mission_slug": _SLUG,
        "force": False,
        "from_lane": from_lane,
        "reason": None,
        "review_ref": None,
        "to_lane": to_lane,
        "wp_id": "WP02",
    }


def _default_mission(tmp_path: Path) -> tuple[Path, str]:
    """A default Mission on its Mission branch (held by the repository root checkout), WP02 claimed in its own commit."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "README.md").write_text("x\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "init")
    pin = _git(repo, "rev-parse", "HEAD")
    _git(repo, "switch", "-qc", _MISSION_BRANCH)
    feature_dir = repo / "kitty-specs" / _SLUG
    feature_dir.mkdir(parents=True)
    meta = {
        "mission_slug": _SLUG,
        "mission_id": "01M8A725AAAAAAAAAAAAAAAAAA",
        "target_branch": "main",
        "topology": "lanes_with_coord",
        "topology_source": "default",
        "mission_branch": _MISSION_BRANCH,
        "coordination_branch": _MISSION_BRANCH,
    }
    (feature_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    write_lanes_json(feature_dir, _manifest(pin))
    (feature_dir / "research").mkdir()
    (feature_dir / "research" / "notes.md").write_text("planning-time draft\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "planning")
    events = [_event(1, "planned", "claimed"), _event(2, "claimed", "in_progress")]
    (feature_dir / "status.events.jsonl").write_text("".join(json.dumps(e) + "\n" for e in events), encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "chore: claim WP02")
    return repo, _git(repo, "rev-parse", "HEAD")


@pytest.fixture
def real_mission(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, str]:
    repo, claim_commit = _default_mission(tmp_path)
    monkeypatch.setattr(move_task_module, "_mt_lanes_manifest", lambda _st: _manifest(_git(repo, "rev-parse", "main")))
    monkeypatch.setattr(move_task_module, "_mt_owned_file_patterns", lambda _st: (_OWNED,))
    monkeypatch.setattr(move_task_module, "_mt_status_events", lambda st: read_events(st.feature_dir))
    return repo, claim_commit


@pytest.mark.integration
def test_real_git_owned_work_after_the_claim_moves_into_review(real_mission: tuple[Path, str]) -> None:
    repo, _claim = real_mission
    (repo / _OWNED).write_text("# WP02 research\n", encoding="utf-8")
    _git(repo, "commit", "-qam", "feat(WP02): research notes")

    move_task_module._mt_require_implementation_evidence(_state(repo))


@pytest.mark.integration
def test_real_git_a_pre_claim_draft_is_not_evidence(real_mission: tuple[Path, str]) -> None:
    repo, claim_commit = real_mission

    with pytest.raises(ActionContextError) as refused:
        move_task_module._mt_require_implementation_evidence(_state(repo))

    assert refused.value.code == wp_evidence.IMPLEMENTATION_MISSING
    assert f"{claim_commit}..{_MISSION_BRANCH} ({PLANNING_LANE_ID})" in str(refused.value)


# ---------------------------------------------------------------- T025: the auto-commit guard


def _workspace(path: Path, kind: str, branch: str) -> ResolvedWorkspace:
    return ResolvedWorkspace(
        mission_slug=_SLUG,
        wp_id="WP02",
        execution_mode="planning_artifact",
        mode_source="frontmatter",
        resolution_kind=kind,
        workspace_name=f"{_SLUG}-{PLANNING_LANE_ID}",
        worktree_path=path,
        branch_name=branch,
        lane_id=PLANNING_LANE_ID,
        lane_wp_ids=["WP02", "WP03"],
    )


@pytest.mark.integration
@pytest.mark.parametrize("kind", [MISSION_BRANCH_CHECKOUT_KIND, REPO_ROOT_KIND])
def test_the_shared_checkout_is_never_swept_into_a_deliverables_commit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str) -> None:
    repo, _claim = _default_mission(tmp_path)
    sibling_modified = repo / "kitty-specs" / _SLUG / "research" / "notes.md"
    sibling_untracked = repo / "kitty-specs" / _SLUG / "research" / "WP03-draft.md"
    sibling_modified.write_text("WP03 half-done edit\n", encoding="utf-8")
    sibling_untracked.write_text("WP03 untracked draft\n", encoding="utf-8")
    head_before = _git(repo, "rev-parse", "HEAD")
    monkeypatch.setattr(tasks_module, "resolve_workspace_for_wp", lambda *_args: _workspace(repo, kind, _MISSION_BRANCH))

    move_task_module._mt_commit_lane_deliverables(_state(repo, json_output=False))

    assert _git(repo, "rev-parse", "HEAD") == head_before, "no deliverables commit in a shared checkout"
    assert sibling_modified.read_text(encoding="utf-8") == "WP03 half-done edit\n"
    assert sibling_untracked.read_text(encoding="utf-8") == "WP03 untracked draft\n"
    porcelain = _git(repo, "status", "--porcelain", "--untracked-files=all")
    assert f"M kitty-specs/{_SLUG}/research/notes.md" in porcelain
    assert f"?? kitty-specs/{_SLUG}/research/WP03-draft.md" in porcelain


@pytest.mark.unit
def test_the_auto_commit_note_names_the_mission_branch_checkout(tmp_path: Path) -> None:
    phrase = move_task_module._mt_shared_checkout_phrase(_workspace(tmp_path, MISSION_BRANCH_CHECKOUT_KIND, _MISSION_BRANCH))

    assert phrase == f"the checkout of the Mission branch {_MISSION_BRANCH} ({tmp_path}), which other work packages share"
    assert move_task_module._mt_shared_checkout_phrase(_workspace(tmp_path, REPO_ROOT_KIND, "main")) == "the repository root checkout"
