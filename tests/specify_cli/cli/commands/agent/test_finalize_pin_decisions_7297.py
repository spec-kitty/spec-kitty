"""#7793 / #7297: finalize's pin decisions for a single_branch Mission, over real git repositories.

The decision table is ``kitty-specs/single-branch-planning-pin-rebase-01M81KRS/contracts/pin-decisions.md``.
The real-CLI scenarios live in ``tests/integration/test_7793_single_branch_repin_patch_id.py``; these
tests pin each decision function's rows directly (no mocks of git).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
import typer

from specify_cli.cli.commands.agent import mission_finalize_pin_window as pin_window
from specify_cli.cli.commands.agent import mission_finalize_planning_pin as pin
from specify_cli.lanes.planning_commit_classify import PinClass

pytestmark = pytest.mark.git_repo

SLUG = "demo-01ABCDEF"
WP01 = (
    "---\nwork_package_id: WP01\ntitle: WP01 m1\ndependencies: []\nrequirement_refs: [FR-001]\n"
    "authoritative_surface: src/m1/\nowned_files:\n  - src/m1/**\nsubtasks:\n  - T1\n---\n# WP01\n"
)


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True).stdout.strip()


def _commit(repo: Path, rel: str, content: str, message: str) -> str:
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", message)
    return _git(repo, "rev-parse", "HEAD")


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "T")
    _git(root, "config", "commit.gpgsign", "false")
    _commit(root, "README.md", "init\n", "init")
    return root


def _planning_dir(repo: Path) -> Path:
    return repo / "kitty-specs" / SLUG


def _mission(repo: Path) -> tuple[str, str]:
    """``topic``: the planning commit (the pin), then WP01's implementation. Returns ``(pin, tip)``."""
    _git(repo, "checkout", "-q", "-b", "topic")
    planning = _commit(repo, f"kitty-specs/{SLUG}/tasks/WP01-m1.md", WP01, "planning")
    tip = _commit(repo, "src/m1/a.py", "X = 1\n", "WP01 implementation")
    return planning, tip


def _rebase(repo: Path) -> None:
    _git(repo, "checkout", "-q", "main")
    _commit(repo, "upstream.txt", "upstream\n", "main moves on")
    _git(repo, "checkout", "-q", "topic")
    _git(repo, "rebase", "-q", "main")


def _refresh(repo: Path, recorded: str | None, *, orphaned: bool, upstream_refs: tuple[str, ...] = ()) -> pin.PlanningCommitResolution:
    return pin._single_branch_refresh_resolution(
        upstream_refs=upstream_refs,
        repo_root=repo,
        mission_slug=SLUG,
        target_branch="topic",
        planning_dir=_planning_dir(repo),
        recorded=recorded,
        tip=_git(repo, "rev-parse", "topic"),
        orphaned=orphaned,
        json_output=True,
    )


def _refusal(capsys: pytest.CaptureFixture[str]) -> dict[str, str]:
    payload: dict[str, str] = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    return payload


# --- explicit re-pin / refresh (single_branch) -----------------------------------------------


def test_repin_follows_the_planning_commit_by_patch_id(repo: Path) -> None:
    recorded, _ = _mission(repo)
    _rebase(repo)

    resolution = _refresh(repo, recorded, orphaned=True)

    assert resolution.action == "repinned"
    assert resolution.matched_by == "patch_id"
    assert resolution.sha == _git(repo, "rev-parse", "topic~1")
    assert resolution.branch_tip == _git(repo, "rev-parse", "topic")


def test_repin_without_a_match_refuses_with_a_named_code(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _mission(repo)
    _rebase(repo)
    stray = _commit(repo, "elsewhere.txt", "a change no branch commit keeps\n", "stray")
    _git(repo, "reset", "-q", "--hard", "HEAD~1")

    with pytest.raises(typer.Exit):
        _refresh(repo, stray, orphaned=True)

    payload = _refusal(capsys)
    assert payload["error_code"] == pin_window.NO_PATCH_ID_MATCH
    assert "evidence window" in payload["error"]


def test_repin_with_two_copies_refuses_as_ambiguous(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    recorded, _ = _mission(repo)
    _rebase(repo)
    copy = _git(repo, "rev-parse", "topic~1")
    _git(repo, "checkout", "-q", "-b", "side", "main")
    _commit(repo, "noise.txt", "noise\n", "noise")
    _git(repo, "cherry-pick", copy)
    _git(repo, "checkout", "-q", "topic")
    _git(repo, "merge", "-q", "--no-edit", "side")

    with pytest.raises(typer.Exit):
        _refresh(repo, recorded, orphaned=True)

    assert _refusal(capsys)["error_code"] == pin_window.PATCH_ID_AMBIGUOUS


def test_refresh_to_the_tip_refuses_when_it_empties_the_window(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    recorded, _ = _mission(repo)

    with pytest.raises(typer.Exit):
        _refresh(repo, recorded, orphaned=False)

    payload = _refusal(capsys)
    assert payload["error_code"] == pin_window.WOULD_EMPTY_WINDOW
    assert "SINGLE_BRANCH_IMPLEMENTATION_MISSING" in payload["error"]


def test_refresh_before_any_implementation_moves_to_the_tip(repo: Path) -> None:
    _git(repo, "checkout", "-q", "-b", "topic")
    recorded = _commit(repo, f"kitty-specs/{SLUG}/tasks/WP01-m1.md", WP01, "planning")
    _commit(repo, f"kitty-specs/{SLUG}/spec.md", "# amended\n", "planning amendment")

    resolution = _refresh(repo, recorded, orphaned=False)

    assert (resolution.action, resolution.sha, resolution.matched_by) == ("refreshed", _git(repo, "rev-parse", "topic"), None)


def test_unreadable_ownership_fails_closed(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    recorded, _ = _mission(repo)
    (_planning_dir(repo) / "tasks" / "WP01-m1.md").write_text("---\nowned_files: [unterminated\n---\n", encoding="utf-8")

    with pytest.raises(typer.Exit):
        _refresh(repo, recorded, orphaned=False)

    assert _refusal(capsys)["error_code"] == "PLANNING_REFRESH_FAIL_CLOSED"


def test_lane_missions_keep_the_4827_repin_to_the_tip(repo: Path) -> None:
    recorded, _ = _mission(repo)
    _rebase(repo)
    tip = _git(repo, "rev-parse", "topic")

    resolution = pin._resolve_refresh_planning_commit_decision(
        repo_root=repo, mission_slug=SLUG, target_branch="topic", recorded=recorded, tip=tip, allow_orphaned=True, json_output=True
    )

    assert (resolution.action, resolution.sha, resolution.matched_by) == ("repinned", tip, None)


# --- automatic (no-flag) refresh ---------------------------------------------------------------


def _automatic(repo: Path, recorded: str, *, single_branch: bool = True) -> pin.PlanningCommitResolution:
    return pin._automatic_refresh_or_keep(
        repo_root=repo,
        mission_slug=SLUG,
        recorded=recorded,
        tip=_git(repo, "rev-parse", "topic"),
        single_branch_planning_dir=_planning_dir(repo) if single_branch else None,
    )


def test_a_derived_pin_is_preserved_by_a_plain_finalize(repo: Path) -> None:
    """#7297 item 1: a pin lanes.json marks as derived survives a genuine planning change."""
    _git(repo, "checkout", "-q", "-b", "topic")
    derived = _git(repo, "rev-parse", "HEAD")
    _commit(repo, f"kitty-specs/{SLUG}/tasks/WP01-m1.md", WP01, "planning")
    _commit(repo, f"kitty-specs/{SLUG}/spec.md", "# amended\n", "planning amendment")
    tip = _git(repo, "rev-parse", "topic")

    kept = pin._resolve_preserve_planning_commit_decision(
        repo_root=repo, mission_slug=SLUG, target_branch="topic", recorded=derived, tip=tip, json_output=True, recorded_derived=True
    )
    timely = pin._resolve_preserve_planning_commit_decision(repo_root=repo, mission_slug=SLUG, target_branch="topic", recorded=derived, tip=tip, json_output=True)

    assert (kept.action, kept.sha, kept.derived) == ("preserved", derived, True)
    assert (timely.action, timely.sha, timely.derived) == ("refreshed", tip, False)


def test_the_derived_marker_round_trips_and_stays_absent_otherwise() -> None:
    from specify_cli.lanes.models import LanesManifest

    base = {"version": 1, "mission_slug": SLUG, "mission_id": None, "mission_branch": "b", "target_branch": "main"}
    base |= {"lanes": [], "computed_at": "t", "computed_from": "f", "planning_commit_sha": "abc"}

    assert "planning_commit_derived" not in LanesManifest.from_dict(base).to_dict()
    assert LanesManifest.from_dict(base | {"planning_commit_derived": True}).to_dict()["planning_commit_derived"] is True
    assert LanesManifest.from_dict(base | {"planning_commit_derived": "yes"}).planning_commit_derived is False


def test_the_automatic_refresh_keeps_a_pin_that_windows_committed_work(repo: Path) -> None:
    recorded, _ = _mission(repo)
    _commit(repo, f"kitty-specs/{SLUG}/spec.md", "# amended\n", "planning amendment")

    resolution = _automatic(repo, recorded)

    assert (resolution.action, resolution.sha, resolution.refusal_reason) == ("kept_with_warning", recorded, "window_would_empty")


def test_the_automatic_refresh_keeps_the_pin_when_the_window_is_unreadable(repo: Path) -> None:
    recorded, _ = _mission(repo)
    (_planning_dir(repo) / "tasks" / "WP01-m1.md").write_text("---\nowned_files: [unterminated\n---\n", encoding="utf-8")

    resolution = _automatic(repo, recorded)

    assert (resolution.action, resolution.refusal_reason) == ("kept_with_warning", "window_unreadable")


def test_the_automatic_refresh_advances_a_pin_with_nothing_committed(repo: Path) -> None:
    _git(repo, "checkout", "-q", "-b", "topic")
    _commit(repo, "src/other.py", "Y = 1\n", "unrelated")
    recorded = _commit(repo, f"kitty-specs/{SLUG}/tasks/WP01-m1.md", WP01, "planning")
    _commit(repo, f"kitty-specs/{SLUG}/spec.md", "# amended\n", "planning amendment")

    resolution = _automatic(repo, recorded)

    assert (resolution.action, resolution.sha) == ("refreshed", _git(repo, "rev-parse", "topic"))


# --- reasons, texts, payload -------------------------------------------------------------------


@pytest.mark.parametrize(("tip", "reason"), [(None, "indeterminate_tip_uncapturable"), ("deadbeef", "no_pin_underivable")])
def test_indeterminate_reason_names_what_is_missing(repo: Path, monkeypatch: pytest.MonkeyPatch, tip: str | None, reason: str) -> None:
    """#7297 item 3: a resolved tip with no pin and nothing derivable is not "uncapturable"."""
    from specify_cli.cli.commands.agent import mission_finalize as mf

    monkeypatch.setattr(mf, "classify_recorded_pin", lambda *_a: PinClass.INDETERMINATE)
    resolution = pin._resolve_preserve_planning_commit_decision(repo_root=repo, mission_slug=SLUG, target_branch="main", recorded=None, tip=tip, json_output=True)

    assert (resolution.action, resolution.refusal_reason) == ("kept_with_warning", reason)


def _kept(reason: str, *, tip: str | None = "abc123") -> pin.PlanningCommitResolution:
    return pin.PlanningCommitResolution(sha="rec", action="kept_with_warning", previous_sha="rec", branch_tip=tip, refusal_reason=reason)


def test_kept_pin_warnings_name_a_next_step() -> None:
    no_pin = pin._kept_pin_warning("topic", _kept("no_pin_underivable"), SLUG)
    uncapturable = pin._kept_pin_warning("topic", _kept("indeterminate_tip_uncapturable", tip=None), SLUG)
    would_empty = pin._kept_pin_warning("topic", _kept("window_would_empty"), SLUG)
    unreadable = pin._kept_pin_warning("topic", _kept("window_unreadable"), SLUG)

    assert no_pin is not None and f"finalize-tasks --mission {SLUG} --refresh-planning-commit" in no_pin
    assert uncapturable is not None and "No action is needed" not in uncapturable and "re-run finalize-tasks" in uncapturable
    assert would_empty is not None and "no action is needed" in would_empty
    assert unreadable is not None and "re-run finalize-tasks" in unreadable
    assert pin._kept_pin_warning("topic", _kept("foreign"), SLUG) is None


def test_report_names_the_patch_id_match(monkeypatch: pytest.MonkeyPatch) -> None:
    from specify_cli.cli.commands.agent import mission_finalize as mf

    printed: list[str] = []
    monkeypatch.setattr(mf.console, "print", lambda message, *_a, **_k: printed.append(str(message)))
    resolution = pin.PlanningCommitResolution(sha="new", action="repinned", previous_sha="old", branch_tip="tip", matched_by="patch_id")

    pin._report_planning_sha_decision("topic", resolution, json_output=False)
    pin._report_planning_sha_decision("topic", _kept("no_pin_underivable"), json_output=False, mission_slug=SLUG)

    assert "same patch-id" in printed[0]
    assert "--refresh-planning-commit" in printed[1]


def test_payload_carries_matched_by_only_when_set() -> None:
    plain = pin.PlanningCommitResolution(sha="s", action="refreshed", previous_sha="p", branch_tip="s")
    followed = pin.PlanningCommitResolution(sha="s", action="repinned", previous_sha="p", branch_tip="t", matched_by="patch_id")

    assert "matched_by" not in pin._planning_commit_payload(plain, None)
    assert pin._planning_commit_payload(followed, None)["matched_by"] == "patch_id"


# --- pin window helpers ------------------------------------------------------------------------


def test_window_guard_passes_with_no_recorded_pin_or_no_ownership(repo: Path) -> None:
    _git(repo, "checkout", "-q", "-b", "topic")
    tip = _commit(repo, "src/m1/a.py", "X = 1\n", "work before any task file")

    assert pin_window.window_keeps_owned_work(repo, SLUG, _planning_dir(repo), recorded=None, candidate=tip, tip=tip)
    assert pin_window.window_keeps_owned_work(repo, SLUG, _planning_dir(repo), recorded="main", candidate=tip, tip=tip)


def test_window_guard_fails_closed_on_an_unreadable_window(repo: Path) -> None:
    _, tip = _mission(repo)

    with pytest.raises(pin_window.PinWindowUnreadable):
        pin_window.window_keeps_owned_work(repo, SLUG, _planning_dir(repo), recorded="0" * 40, candidate=tip, tip=tip)


def test_follow_orphaned_pin_reports_an_empty_diff_pin(repo: Path) -> None:
    _git(repo, "checkout", "-q", "-b", "topic")
    _git(repo, "commit", "-q", "--allow-empty", "-m", "empty planning")
    empty = _git(repo, "rev-parse", "HEAD")

    follow = pin_window.follow_orphaned_pin(repo, empty, "main")

    assert (follow.sha, follow.error_code) == (None, pin_window.NO_PATCH_ID_MATCH)
    assert "empty diff" in follow.reason


def test_follow_orphaned_pin_fails_closed_on_an_unknown_commit(repo: Path) -> None:
    with pytest.raises(pin_window.PinWindowUnreadable):
        pin_window.follow_orphaned_pin(repo, "0" * 40, "main")


def test_resolve_pin_line_reads_the_stored_topology(repo: Path) -> None:
    meta = {"mission_slug": SLUG, "topology": "single_branch", "mission_branch": "kitty/mission-demo-01ABCDEF", "target_branch": "main"}
    _planning_dir(repo).mkdir(parents=True)
    (_planning_dir(repo) / "meta.json").write_text(json.dumps(meta), encoding="utf-8")

    line = pin_window.resolve_pin_line(repo, SLUG, "main")

    assert (line.branch, line.single_branch) == ("kitty/mission-demo-01ABCDEF", True)


# --- execution has begun (#7793) ---------------------------------------------------------------


def _surface(mission_dir: Path) -> object:
    from mission_runtime import MissionTopology

    from specify_cli.status.read_surface import StatusReadSource, StatusReadSurface

    return StatusReadSurface(
        topology=MissionTopology.SINGLE_BRANCH,
        source=StatusReadSource.WRITE_CHECKOUT,
        mission_dir_name=mission_dir.name,
        path=mission_dir,
        repo_root=mission_dir.parent.parent,
        ref=None,
    )


def _event(event_id: str, from_lane: str, to_lane: str, actor: str = "claude") -> object:
    from specify_cli.status.models import Lane, StatusEvent

    return StatusEvent(
        event_id=event_id,
        mission_slug=SLUG,
        wp_id="WP01",
        from_lane=Lane(from_lane),
        to_lane=Lane(to_lane),
        at="2026-11-22T00:00:00Z",
        actor=actor,
        force=to_lane == "planned",
        execution_mode="direct_repo",
    )


@pytest.mark.parametrize(
    ("events", "begun"),
    [
        ([("01HX0000000000000000000001", "planned", "claimed"), ("01HX0000000000000000000002", "claimed", "planned")], True),
        ([("01HX0000000000000000000003", "planned", "claimed", "migration:backfill")], False),
        ([], False),
    ],
)
def test_a_work_package_rejected_back_to_planned_still_counts_as_begun(tmp_path: Path, events: list[tuple[str, ...]], begun: bool) -> None:
    """#7793: a rejected work package has committed work; finalize must not treat it as never run."""
    from tests._support.status_seed import seed_status_events

    mission_dir = tmp_path / "kitty-specs" / SLUG
    mission_dir.mkdir(parents=True)
    seed_status_events(mission_dir, [_event(*row) for row in events])

    assert pin._any_work_package_left_planned(_surface(mission_dir)) is begun


def test_a_non_surface_or_unreadable_log_is_not_begun(tmp_path: Path) -> None:
    mission_dir = tmp_path / "kitty-specs" / SLUG
    mission_dir.mkdir(parents=True)
    (mission_dir / "status.events.jsonl").write_text("{not json\n", encoding="utf-8")

    assert pin._any_work_package_left_planned(object()) is False
    assert pin._any_work_package_left_planned(_surface(mission_dir)) is False


def test_repin_refuses_a_match_that_is_only_on_the_upstream(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Review B2: the planning change also landed on main; its copy there is never the Mission's pin."""
    recorded, _ = _mission(repo)
    _git(repo, "checkout", "-q", "main")
    _commit(repo, "noise.txt", "noise\n", "main moves first")
    _git(repo, "cherry-pick", recorded)
    _commit(repo, "src/m1/b.py", "Y = 1\n", "later main work on an owned path")
    _git(repo, "checkout", "-q", "topic")
    _git(repo, "rebase", "-q", "main")

    with pytest.raises(typer.Exit):
        _refresh(repo, recorded, orphaned=True, upstream_refs=("main",))

    payload = _refusal(capsys)
    assert payload["error_code"] == pin_window.NO_PATCH_ID_MATCH
    assert "only on the upstream (main)" in payload["error"]


def test_window_guard_is_judged_per_work_package(repo: Path) -> None:
    """Review N2: keeping WP02's change does not excuse dropping WP01's."""
    _git(repo, "checkout", "-q", "-b", "topic")
    recorded = _commit(repo, f"kitty-specs/{SLUG}/tasks/WP01-m1.md", WP01, "planning")
    _commit(repo, f"kitty-specs/{SLUG}/tasks/WP02-m2.md", WP01.replace("WP01", "WP02").replace("m1", "m2"), "planning WP02")
    _commit(repo, "src/m1/a.py", "X = 1\n", "WP01 implementation")
    candidate = _git(repo, "rev-parse", "HEAD")
    tip = _commit(repo, "src/m2/a.py", "Z = 1\n", "WP02 implementation")

    assert not pin_window.window_keeps_owned_work(repo, SLUG, _planning_dir(repo), recorded=recorded, candidate=candidate, tip=tip)
    assert pin_window.window_keeps_owned_work(repo, SLUG, _planning_dir(repo), recorded=recorded, candidate=recorded, tip=tip)


# --- upstream recognition: remote-tracking refs and the residual (#7793 review B2) ------------


def _commit_to_target_mission(repo: Path) -> str:
    """A commit-to-target single_branch Mission on ``topic``; returns the planning commit (the pin)."""
    _git(repo, "checkout", "-q", "-b", "topic")
    meta = {"mission_slug": SLUG, "topology": "single_branch", "mission_branch": "topic", "target_branch": "topic"}
    _planning_dir(repo).mkdir(parents=True, exist_ok=True)
    (_planning_dir(repo) / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    planning = _commit(repo, f"kitty-specs/{SLUG}/tasks/WP01-m1.md", WP01, "planning")
    _commit(repo, "src/m1/a.py", "X = 1\n", "WP01 implementation")
    return planning


def _land_upstream_and_rebase(repo: Path, upstream: str, pin_commit: str) -> None:
    """The planning change lands on *upstream* with later owned work; ``topic`` is rebased onto it."""
    _git(repo, "checkout", "-q", "--detach", upstream)
    _commit(repo, "noise.txt", "noise\n", "upstream moves first")
    _git(repo, "cherry-pick", f"{pin_commit}~1..{pin_commit}")
    _commit(repo, "src/m1/b.py", "Y = 1\n", "later upstream work on an owned path")
    landed = _git(repo, "rev-parse", "HEAD")
    _git(repo, "checkout", "-q", "topic")
    _git(repo, "rebase", "-q", landed)
    return None


def test_a_stale_local_main_still_recognises_the_origin_copy(repo: Path, tmp_path: Path) -> None:
    """The rebase went onto origin/main while the local main is stale: the copy is still the upstream's."""
    origin = tmp_path / "origin.git"
    _git(tmp_path, "clone", "-q", "--bare", repo.as_posix(), origin.as_posix())
    _git(repo, "remote", "add", "origin", origin.as_posix())
    pin_commit = _commit_to_target_mission(repo)
    # Upstream work lands on origin/main only; the local main never moves.
    _land_upstream_and_rebase(repo, "main", pin_commit)
    _git(repo, "push", "-q", "origin", "HEAD~1:refs/heads/main")
    _git(repo, "fetch", "-q", "origin")

    line = pin_window.resolve_pin_line(repo, SLUG, "topic")
    follow = pin_window.follow_orphaned_pin(repo, pin_commit, "topic", upstream_refs=line.upstream_refs)

    assert "refs/remotes/origin/main" in line.upstream_refs
    assert (follow.sha, follow.error_code) == (None, pin_window.NO_PATCH_ID_MATCH)


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="#7793 review B2 residual (ADR 2026-10-04-5 Amendment 2026-11-22): an upstream that is neither the "
    "target nor the primary branch (nor their remote-tracking refs) is not recognised, so its copy of the "
    "planning commit is followed and the window widens to that branch's later commits.",
)
def test_residual_an_unrelated_upstream_copy_is_followed(repo: Path) -> None:
    pin_commit = _commit_to_target_mission(repo)
    _git(repo, "branch", "release", "main")
    _land_upstream_and_rebase(repo, "release", pin_commit)
    _git(repo, "branch", "-f", "release", "topic~1")

    line = pin_window.resolve_pin_line(repo, SLUG, "topic")
    follow = pin_window.follow_orphaned_pin(repo, pin_commit, "topic", upstream_refs=line.upstream_refs)

    assert follow.sha is None, "the copy on 'release' is the upstream's, not the Mission's"


# --- squad findings: the guard judges the Mission's own commits (F1, F4) ----------------------


def test_repin_is_not_refused_when_the_upstream_touched_another_work_packages_files(repo: Path) -> None:
    """Squad F1: an upstream change to a not-yet-started WP's owned file is not the Mission's work.

    Reading the recorded window across the rebase counted ``src/m2/b.py`` (main's change) as WP02's
    committed work, which the correct re-pin then "lost": the #7793 remedy refused.
    """
    _commit(repo, "src/m2/b.py", "B = 0\n", "main has WP02's module")
    _git(repo, "checkout", "-q", "-b", "topic")
    recorded = _commit(repo, f"kitty-specs/{SLUG}/tasks/WP01-m1.md", WP01, "planning")
    _commit(repo, f"kitty-specs/{SLUG}/tasks/WP02-m2.md", WP01.replace("WP01", "WP02").replace("m1", "m2"), "planning WP02")
    _commit(repo, "src/m1/a.py", "X = 1\n", "WP01 implementation")
    _git(repo, "checkout", "-q", "main")
    _commit(repo, "src/m2/b.py", "B = 1\n", "upstream changes WP02's file")
    _git(repo, "checkout", "-q", "topic")
    _git(repo, "rebase", "-q", "main")

    resolution = _refresh(repo, recorded, orphaned=True, upstream_refs=("main",))

    assert (resolution.action, resolution.matched_by) == ("repinned", "patch_id")
    assert resolution.sha == _git(repo, "rev-parse", "topic~2")


def test_a_refresh_with_no_recorded_pin_refuses_over_committed_work(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Squad F4: no pin and a tip refresh used to empty the window over the Mission's committed work."""
    _mission(repo)

    with pytest.raises(typer.Exit):
        _refresh(repo, None, orphaned=False, upstream_refs=("main",))

    payload = _refusal(capsys)
    assert payload["error_code"] == pin_window.WOULD_EMPTY_WINDOW
    assert "lanes.json by hand" in payload["error"]


def test_an_orphaned_pin_that_would_empty_the_window_names_the_manual_route(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Squad (docs) F7: keeping an orphaned pin is no way forward, so the refusal names the manual edit."""
    recorded, _ = _mission(repo)
    _rebase(repo)
    # The rebased planning copy sits after the implementation: following it would drop the work.
    _git(repo, "reset", "-q", "--hard", "main")
    _commit(repo, "src/m1/a.py", "X = 1\n", "WP01 implementation")
    _git(repo, "cherry-pick", recorded)

    with pytest.raises(typer.Exit):
        _refresh(repo, recorded, orphaned=True, upstream_refs=("main",))

    payload = _refusal(capsys)
    assert payload["error_code"] == pin_window.WOULD_EMPTY_WINDOW
    assert "orphaned" in payload["error"] and "lanes.json by hand" in payload["error"]


# --- per-PR wiring guards (squad test-fidelity review) -----------------------------------------


def test_the_refresh_decision_routes_a_single_branch_pin_to_the_patch_id_re_pin(repo: Path) -> None:
    """Squad T1: the #7793 entry seam itself, with the real classifier: orphaned single_branch -> patch-id."""
    recorded, _ = _mission(repo)
    _rebase(repo)
    tip = _git(repo, "rev-parse", "topic")

    resolution = pin._resolve_refresh_planning_commit_decision(
        repo_root=repo,
        mission_slug=SLUG,
        target_branch="topic",
        recorded=recorded,
        tip=tip,
        allow_orphaned=True,
        json_output=True,
        single_branch_planning_dir=_planning_dir(repo),
        upstream_refs=("main",),
    )

    assert (resolution.action, resolution.matched_by) == ("repinned", "patch_id")
    assert resolution.sha == _git(repo, "rev-parse", "topic~1") != tip


def test_preserve_or_capture_wires_the_pin_line_for_a_single_branch_mission(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Squad T1: from the finalize entry, a stored single_branch Mission re-pins by patch-id on its own branch."""
    from specify_cli.cli.commands.agent import mission_finalize as mf
    from specify_cli.lanes.models import LanesManifest
    from specify_cli.lanes.persistence import write_lanes_json

    recorded = _commit_to_target_mission(repo)
    write_lanes_json(
        _planning_dir(repo),
        LanesManifest(
            version=1,
            mission_slug=SLUG,
            mission_id=None,
            mission_branch="topic",
            target_branch="topic",
            lanes=[],
            computed_at="t",
            computed_from="f",
            planning_commit_sha=recorded,
        ),
    )
    _git(repo, "checkout", "-q", "main")
    _commit(repo, "upstream.txt", "upstream\n", "main moves on")
    _git(repo, "checkout", "-q", "topic")
    _git(repo, "rebase", "-q", "main")
    monkeypatch.setattr(mf, "_execution_has_begun", lambda *_a, **_k: True)

    resolution = pin._preserve_or_capture_planning_commit_sha(
        _planning_dir(repo), repo, SLUG, "topic", json_output=True, refresh_planning_commit=True, allow_orphaned=True
    )

    assert (resolution.action, resolution.matched_by) == ("repinned", "patch_id")


def test_a_kept_derived_pin_keeps_its_marker_when_the_tip_is_uncapturable(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Squad T3: the marker survives a kept_with_warning decision (no planning change can reach it there)."""
    from specify_cli.cli.commands.agent import mission_finalize as mf
    from specify_cli.lanes.models import LanesManifest
    from specify_cli.lanes.persistence import write_lanes_json

    _planning_dir(repo).mkdir(parents=True)
    write_lanes_json(
        _planning_dir(repo),
        LanesManifest(
            version=1,
            mission_slug=SLUG,
            mission_id=None,
            mission_branch="main",
            target_branch="main",
            lanes=[],
            computed_at="t",
            computed_from="f",
            planning_commit_sha=_git(repo, "rev-parse", "HEAD"),
            planning_commit_derived=True,
        ),
    )
    monkeypatch.setattr(mf, "_execution_has_begun", lambda *_a, **_k: True)
    monkeypatch.setattr(mf, "capture_branch_tip", lambda *_a: None)

    resolution = pin._preserve_or_capture_planning_commit_sha(_planning_dir(repo), repo, SLUG, "main", json_output=True)

    assert (resolution.action, resolution.derived) == ("kept_with_warning", True)


def test_the_text_mode_refusal_leads_with_its_code(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(typer.Exit):
        pin._refuse_planning_pin_with_code(pin_window.NO_PATCH_ID_MATCH, "no copy", json_output=False)
    with pytest.raises(typer.Exit):
        pin._refuse_planning_pin_refresh("unreadable", json_output=False)

    out = " ".join(capsys.readouterr().out.split())
    assert f"{pin_window.NO_PATCH_ID_MATCH}: no copy" in out
    assert "PLANNING_REFRESH_FAIL_CLOSED: Cannot refresh" in out


def test_remote_tracking_refs_degrade_to_none(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from kernel import git as kernel_git

    assert pin_window._remote_tracking_refs(repo, []) == []

    def boom(*_a: object, **_k: object) -> object:
        raise kernel_git.GitCommandError(argv=("for-each-ref",), cwd=repo, returncode=128, stderr="fatal")

    monkeypatch.setattr(kernel_git, "run_git", boom)
    assert pin_window._remote_tracking_refs(repo, ["main"]) == []


# --- Tier R review B1: a ref that already contains the pin is downstream, not upstream --------


def test_the_guard_keeps_mission_work_that_a_downstream_primary_also_contains(repo: Path) -> None:
    """Tier R B1: gitflow (develop merged into main) must not hide the Mission's work from the guard.

    ``main`` reaches the recorded pin, so it is downstream of the Mission and bounds nothing: the
    implementation it also carries is still the Mission's, and a refresh to the tip would empty
    the window.
    """
    _git(repo, "checkout", "-q", "-b", "develop")
    recorded = _commit(repo, f"kitty-specs/{SLUG}/tasks/WP01-m1.md", WP01, "planning")
    _commit(repo, "src/m1/a.py", "X = 1\n", "WP01 implementation")
    _git(repo, "checkout", "-q", "main")
    _git(repo, "merge", "-q", "--no-ff", "-m", "merge develop", "develop")
    _git(repo, "checkout", "-q", "develop")
    tip = _commit(repo, f"kitty-specs/{SLUG}/spec.md", "# amended\n", "planning amendment")

    assert not pin_window.window_keeps_owned_work(repo, SLUG, _planning_dir(repo), recorded=recorded, candidate=tip, tip=tip, upstream_refs=("main",))
    resolution = pin._automatic_refresh_or_keep(
        repo_root=repo, mission_slug=SLUG, recorded=recorded, tip=tip, single_branch_planning_dir=_planning_dir(repo), upstream_refs=("main",)
    )
    assert (resolution.action, resolution.refusal_reason) == ("kept_with_warning", "window_would_empty")


def test_a_lanes_mission_with_a_rejected_work_package_keeps_its_pin(repo: Path) -> None:
    """Tier R N3: the "ever left planned" rule holds on lane topologies too.

    Before #7793 a ``lanes`` Mission whose only WP was rejected back to planned read as not begun,
    so a plain finalize re-captured the target tip; now it classifies and preserves the pin.
    """
    from tests._support.status_seed import seed_status_events

    from specify_cli.lanes.models import LanesManifest
    from specify_cli.lanes.persistence import write_lanes_json

    mission_dir = _planning_dir(repo)
    mission_dir.mkdir(parents=True)
    (mission_dir / "meta.json").write_text(json.dumps({"mission_slug": SLUG, "topology": "lanes", "target_branch": "main"}), encoding="utf-8")
    pin_sha = _commit(repo, f"kitty-specs/{SLUG}/tasks/WP01-m1.md", WP01, "planning")
    write_lanes_json(
        mission_dir,
        LanesManifest(
            version=1,
            mission_slug=SLUG,
            mission_id=None,
            mission_branch="main",
            target_branch="main",
            lanes=[],
            computed_at="t",
            computed_from="f",
            planning_commit_sha=pin_sha,
        ),
    )
    seed_status_events(
        mission_dir,
        [_event("01HX0000000000000000000011", "planned", "claimed"), _event("01HX0000000000000000000012", "claimed", "planned")],
    )
    # The pin's bookkeeping lands in a finalize-style commit; only unrelated work follows it.
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", f"Add tasks for mission {SLUG}")
    _commit(repo, "src/unrelated.py", "U = 1\n", "the target moves on")

    resolution = pin._preserve_or_capture_planning_commit_sha(mission_dir, repo, SLUG, "main", json_output=True)

    assert (resolution.action, resolution.sha) == ("preserved", pin_sha)
