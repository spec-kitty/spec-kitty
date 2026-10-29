"""Unit coverage for the topology-neutral evidence + independence predicate (#6715).

``consolidation/wp_evidence.py`` is the one authority every landing surface asks. These tests
pin its pure helpers and the per-work-package verdict over a tiny real git repository, so every
refuse and fail-closed branch is exercised directly.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from specify_cli.consolidation import wp_evidence as ev
from specify_cli.lanes.models import ExecutionLane, LanesManifest

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_SLUG = "fx"
_LANE_BRANCH = "kitty/mission-fx-lane-a"


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True).stdout.strip()


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.name", "QA")
    _git(repo, "config", "user.email", "qa@example.invalid")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "seed.txt").write_text("seed\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "seed")
    return repo


def _commit(repo: Path, relpath: str, text: str = "x\n", message: str = "change") -> str:
    target = repo / relpath
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", message)
    return _git(repo, "rev-parse", "HEAD")


def _feature_dir(repo: Path, owned: dict[str, str]) -> Path:
    fd = repo / "kitty-specs" / _SLUG
    (fd / "tasks").mkdir(parents=True, exist_ok=True)
    for wp, glob in owned.items():
        (fd / "tasks" / f"{wp}-x.md").write_text(
            f"---\nwork_package_id: {wp}\ntitle: {wp}\ndependencies: []\nowned_files:\n  - {glob}\nsubtasks:\n  - T1\n---\n# {wp}\n",
            encoding="utf-8",
        )
    return fd


def _lane(lane_id: str, wp_ids: list[str]) -> ExecutionLane:
    return ExecutionLane(lane_id=lane_id, wp_ids=wp_ids, write_scope=[], predicted_surfaces=[], depends_on_lanes=[], parallel_group=0)


def _manifest(lanes: list[ExecutionLane], planning_commit: str | None) -> LanesManifest:
    return LanesManifest(
        version=1,
        mission_slug=_SLUG,
        mission_id=None,
        mission_branch="kitty/mission-fx",
        target_branch="main",
        lanes=lanes,
        computed_at="now",
        computed_from="test",
        planning_commit_sha=planning_commit,
    )


def _event(event_id: str, wp: str, from_lane: str, to_lane: str, actor: str, *, minute: int, metadata: dict[str, object] | None = None) -> dict[str, object]:
    event: dict[str, object] = {
        "event_id": event_id,
        "at": f"2026-02-08T12:{minute:02d}:00+00:00",
        "wp_id": wp,
        "from_lane": from_lane,
        "to_lane": to_lane,
        "actor": actor,
        "evidence": None,
        "execution_mode": "worktree",
        "feature_slug": _SLUG,
        "force": False,
        "reason": None,
        "review_ref": None,
    }
    if metadata is not None:
        event["policy_metadata"] = metadata
    return event


def _independent_review(fd: Path, wp: str, *, implementer: str = "alice", reviewer: str = "bob", seq: int = 0) -> list[dict[str, object]]:
    return [
        _event(f"01AAAAAAAAAAAAAAAAAAAAA{seq:03d}", wp, "planned", "in_progress", implementer, minute=seq),
        _event(f"01BBBBBBBBBBBBBBBBBBBBB{seq:03d}", wp, "in_progress", "for_review", implementer, minute=seq + 1),
        _event(f"01CCCCCCCCCCCCCCCCCCCCC{seq:03d}", wp, "for_review", "in_review", reviewer, minute=seq + 2),
        _event(f"01DDDDDDDDDDDDDDDDDDDDD{seq:03d}", wp, "in_review", "approved", reviewer, minute=seq + 3),
    ]


def _write_events(fd: Path, events: list[dict[str, object]]) -> None:
    (fd / "status.events.jsonl").write_text("\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8")


def _evaluate(
    repo: Path, fd: Path, manifest: LanesManifest, approved: dict[str, str], *, events: list[object] | None = None, single_branch: bool = False
) -> ev.EvidenceReport:
    work_packages = {wp: {"lane": lane} for wp, lane in approved.items()}
    return ev.evaluate_evidence(repo, fd, manifest, work_packages, (), events=lambda: events or [], is_single_branch=single_branch)


# --------------------------------------------------------------------------- pure helpers


def test_alias_table_maps_every_single_branch_code_to_a_neutral_code() -> None:
    assert ev._canonical_code(ev.SINGLE_BRANCH_IMPLEMENTATION_MISSING) == ev.IMPLEMENTATION_MISSING
    assert ev._canonical_code(ev.SINGLE_BRANCH_REVIEW_NOT_INDEPENDENT) == ev.REVIEW_NOT_INDEPENDENT
    assert ev._canonical_code(ev._SINGLE_BRANCH_EVIDENCE_UNREADABLE) == ev.IMPLEMENTATION_UNREADABLE
    assert ev._canonical_code(ev.SINGLE_BRANCH_IMPLEMENTATION_UNREADABLE) == ev.IMPLEMENTATION_UNREADABLE
    assert ev._canonical_code(ev.SINGLE_BRANCH_EVIDENCE_WINDOW_UNCOMPUTABLE) == ev.EVIDENCE_WINDOW_UNCOMPUTABLE
    assert ev._canonical_code(ev.IMPLEMENTATION_MISSING) == ev.IMPLEMENTATION_MISSING
    assert set(ev._SINGLE_BRANCH_ALIASES.values()) == set(ev._NEUTRAL_CODES)


def test_refusal_codes_reads_neutral_and_alias_codes_leading_a_line() -> None:
    text = (
        "Mission fx: header\n"
        f"{ev.IMPLEMENTATION_MISSING}: WP01 ...\n"
        f"{ev.SINGLE_BRANCH_IMPLEMENTATION_MISSING}: WP02 ...\n"
        f"{ev.REVIEW_NOT_INDEPENDENT}: WP03 ...\n"
        f"{ev.IMPLEMENTATION_MISSING}: WP04 ...\n"
        f"prose naming {ev.EVIDENCE_WINDOW_UNCOMPUTABLE}: not at line start\n"
    )
    assert ev._refusal_codes(text) == [ev.IMPLEMENTATION_MISSING, ev.SINGLE_BRANCH_IMPLEMENTATION_MISSING, ev.REVIEW_NOT_INDEPENDENT]


def test_owned_pattern_helpers_normalize_and_match() -> None:
    assert ev.owned_patterns(["./src/m1/**", "  ", "a\\b/*"]) == ("src/m1/**", "a/b/*")
    assert ev.matches_owned("src/m1/deep/x.py", ("src/m1/**",))
    assert ev.matches_owned("./src/m1/x.py", ("src/m1/**",))
    assert ev.matches_owned("tools/check.sh", ("tools/check.sh",))
    assert not ev.matches_owned("src/m2/x.py", ("src/m1/**",))
    assert not ev.has_owned_change(["src/m1/x.py"], ())


def test_bookkeeping_paths_are_not_evidence() -> None:
    for path in (f"kitty-specs/{_SLUG}/status.events.jsonl", f"kitty-specs/{_SLUG}/issue-matrix.json", f"kitty-specs/{_SLUG}/meta.json", ".kittify/config.yaml"):
        assert not ev._is_evidence_path(path, _SLUG), path
    assert ev._is_evidence_path(f"kitty-specs/{_SLUG}/research/notes.md", _SLUG)
    assert ev._is_evidence_path("src/m1/x.py", _SLUG)


def test_lane_window_is_lane_branch_for_code_and_target_for_planning() -> None:
    manifest = _manifest([_lane("lane-a", ["WP01"]), _lane("lane-planning", ["WP02"])], "abc123")
    assert ev.lane_evidence_window(manifest, manifest.lanes[0]) == ("abc123", _LANE_BRANCH)
    assert ev.lane_evidence_window(manifest, manifest.lanes[1]) == ("abc123", "main")
    assert ev.lane_evidence_window(_manifest([_lane("lane-a", ["WP01"])], None), manifest.lanes[0]) is None


def test_work_package_ownership_is_read_from_the_primary_partition(tmp_path: Path) -> None:
    """#2118: under coordination topology the coord-aware mission dir holds no ``tasks/``; ownership comes from the primary dir."""
    repo = _repo(tmp_path)
    fd = _feature_dir(repo, {"WP01": "src/m1/**"})
    coord_dir = repo / ".worktrees" / "fx-coord" / "kitty-specs" / _SLUG
    coord_dir.mkdir(parents=True)
    (coord_dir / "status.events.jsonl").write_text("", encoding="utf-8")

    assert ev._wp_task_dir(repo, _SLUG, coord_dir) == fd
    assert ev._owned_patterns_by_wp(repo, _SLUG, coord_dir, ["WP01"]) == {"WP01": ("src/m1/**",)}


def test_ownership_is_never_read_from_a_coordination_copy(tmp_path: Path) -> None:
    """Fail closed: with no ``tasks/`` on the primary partition, a stale coordination copy is not read."""
    repo = _repo(tmp_path)
    coord_dir = repo / ".worktrees" / "fx-coord" / "kitty-specs" / _SLUG
    (coord_dir / "tasks").mkdir(parents=True)
    (coord_dir / "tasks" / "WP01-x.md").write_text(
        "---\nwork_package_id: WP01\ntitle: WP01\ndependencies: []\nowned_files:\n  - src/**\nsubtasks:\n  - T1\n---\n# WP01\n",
        encoding="utf-8",
    )

    assert ev._wp_task_dir(repo, _SLUG, coord_dir) == repo / "kitty-specs" / _SLUG
    assert ev._owned_patterns_by_wp(repo, _SLUG, coord_dir, ["WP01"]) == {}


def test_attestation_reader_ignores_migration_actors_and_other_values() -> None:
    attest = SimpleNamespace(wp_id="WP01", actor="operator", policy_metadata={"attestation": ev.NO_IMPLEMENTATION})
    migration = SimpleNamespace(wp_id="WP02", actor="migration:backfill", policy_metadata={"attestation": ev.NO_IMPLEMENTATION})
    other = SimpleNamespace(wp_id="WP03", actor="operator", policy_metadata={"attestation": "approved_reviewed"})
    bare = SimpleNamespace(wp_id="WP04", actor="operator", policy_metadata=None)
    events = [attest, migration, other, bare]
    assert ev._attested_no_implementation(events, "WP01")
    assert not ev._attested_no_implementation(events, "WP02")
    assert not ev._attested_no_implementation(events, "WP03")
    assert not ev._attested_no_implementation(events, "WP04")
    assert ev._no_implementation_attested_wp_ids(events) == frozenset({"WP01"})


def test_constants_for_the_attestation_writers() -> None:
    assert ev.NO_IMPLEMENTATION == "no_implementation"
    assert ev.ATTEST_NO_IMPLEMENTATION_FLAG == "--attest-no-implementation"


# --------------------------------------------------------------------------- lanes / coord verdicts


def _lane_fixture(tmp_path: Path) -> tuple[Path, Path, str]:
    """A repo with a planning commit on main and a lane branch cut from it."""
    repo = _repo(tmp_path)
    fd = _feature_dir(repo, {"WP01": "src/m1/**"})
    planning = _commit(repo, f"kitty-specs/{_SLUG}/plan.md", "# plan\n", "planning")
    _git(repo, "branch", _LANE_BRANCH)
    return repo, fd, planning


def test_owned_change_on_the_lane_with_independent_review_passes(tmp_path: Path) -> None:
    repo, fd, planning = _lane_fixture(tmp_path)
    _git(repo, "checkout", "-q", _LANE_BRANCH)
    _commit(repo, "src/m1/real.py")
    _git(repo, "checkout", "-q", "main")
    _write_events(fd, _independent_review(fd, "WP01"))
    report = _evaluate(repo, fd, _manifest([_lane("lane-a", ["WP01"])], planning), {"WP01": "approved"})
    assert report.refusal is None
    assert report.codes == []


def test_lane_with_only_bookkeeping_and_foreign_commits_is_missing(tmp_path: Path) -> None:
    repo, fd, planning = _lane_fixture(tmp_path)
    _git(repo, "checkout", "-q", _LANE_BRANCH)
    _commit(repo, f"kitty-specs/{_SLUG}/status.events.jsonl", "{}\n", "chore: Start WP01 implementation")
    _commit(repo, "src/other.py", message="not owned")
    _git(repo, "checkout", "-q", "main")
    _write_events(fd, _independent_review(fd, "WP01"))
    report = _evaluate(repo, fd, _manifest([_lane("lane-a", ["WP01"])], planning), {"WP01": "approved"})
    assert report.refusal is not None
    assert report.codes == [ev.IMPLEMENTATION_MISSING]
    assert report.refusal.startswith(f"Mission {_SLUG}: work packages cannot be landed as reviewed:")
    assert f"{ev.IMPLEMENTATION_MISSING}: WP01" in report.refusal
    assert ev.ATTEST_NO_IMPLEMENTATION_FLAG in report.refusal


def test_commit_then_revert_counts_as_nothing(tmp_path: Path) -> None:
    repo, fd, planning = _lane_fixture(tmp_path)
    _git(repo, "checkout", "-q", _LANE_BRANCH)
    _commit(repo, "src/m1/real.py")
    _git(repo, "rm", "-q", "src/m1/real.py")
    _git(repo, "commit", "-qm", "revert")
    _git(repo, "checkout", "-q", "main")
    _write_events(fd, _independent_review(fd, "WP01"))
    report = _evaluate(repo, fd, _manifest([_lane("lane-a", ["WP01"])], planning), {"WP01": "done"})
    assert report.codes == [ev.IMPLEMENTATION_MISSING]


def test_self_review_is_not_independent(tmp_path: Path) -> None:
    repo, fd, planning = _lane_fixture(tmp_path)
    _git(repo, "checkout", "-q", _LANE_BRANCH)
    _commit(repo, "src/m1/real.py")
    _git(repo, "checkout", "-q", "main")
    _write_events(fd, _independent_review(fd, "WP01", implementer="claude", reviewer="claude"))
    report = _evaluate(repo, fd, _manifest([_lane("lane-a", ["WP01"])], planning), {"WP01": "approved"})
    assert report.codes == [ev.REVIEW_NOT_INDEPENDENT]
    assert "a reviewer who is not the implementer" in str(report.refusal)


def test_attestation_lifts_only_implementation_missing(tmp_path: Path) -> None:
    repo, fd, planning = _lane_fixture(tmp_path)
    attest = SimpleNamespace(wp_id="WP01", actor="operator", policy_metadata={"attestation": ev.NO_IMPLEMENTATION})
    manifest = _manifest([_lane("lane-a", ["WP01"])], planning)

    _write_events(fd, _independent_review(fd, "WP01"))
    lifted = _evaluate(repo, fd, manifest, {"WP01": "approved"}, events=[attest])
    assert lifted.refusal is None
    assert lifted.lifted_wp_ids == frozenset({"WP01"})

    _write_events(fd, _independent_review(fd, "WP01", implementer="claude", reviewer="claude"))
    still = _evaluate(repo, fd, manifest, {"WP01": "approved"}, events=[attest])
    assert still.codes == [ev.REVIEW_NOT_INDEPENDENT], "the attestation never lifts the independence refusal"
    assert still.lifted_wp_ids == frozenset({"WP01"})


# --------------------------------------------------------------------------- attestation scope (#6715 cycle 2)
#
# Operator ruling 2026-10-27: an attestation counts only while the work package has stayed in
# {approved, done} since it was recorded. A later non-migration move outside that set voids it.


def _attest(event_id: str, wp: str, lane: str, *, minute: int, actor: str = "operator") -> dict[str, object]:
    event = _event(event_id, wp, lane, lane, actor, minute=minute, metadata={"attestation": ev.NO_IMPLEMENTATION})
    event["force"] = True
    return event


def _hollow_lane(tmp_path: Path) -> tuple[Path, Path, LanesManifest]:
    """A lane whose window holds no owned change: the #6715 hollow case."""
    repo, fd, planning = _lane_fixture(tmp_path)
    return repo, fd, _manifest([_lane("lane-a", ["WP01"])], planning)


def _evaluate_log(repo: Path, fd: Path, manifest: LanesManifest, lane: str) -> ev.EvidenceReport:
    from specify_cli.status import read_events

    return ev.evaluate_evidence(repo, fd, manifest, {"WP01": {"lane": lane}}, (), events=lambda: read_events(fd), is_single_branch=False)


def test_a_reopened_and_reapproved_hollow_work_package_refuses_again(tmp_path: Path) -> None:
    """The cycle-1 probe inverted: the attestation spoke about the earlier approval, not the new one."""
    repo, fd, manifest = _hollow_lane(tmp_path)
    reopen = _event("01FFFFFFFFFFFFFFFFFFFFF000", "WP01", "approved", "planned", "bob", minute=6)
    reopen["force"] = True
    again = _independent_review(fd, "WP01", reviewer="carol", seq=10)
    _write_events(fd, [*_independent_review(fd, "WP01"), _attest("01EEEEEEEEEEEEEEEEEEEEE000", "WP01", "approved", minute=5), reopen, *again])

    report = _evaluate_log(repo, fd, manifest, "approved")
    assert report.codes == [ev.IMPLEMENTATION_MISSING]
    assert report.lifted_wp_ids == frozenset()


def test_a_rejection_after_the_attestation_voids_it(tmp_path: Path) -> None:
    repo, fd, manifest = _hollow_lane(tmp_path)
    events = [
        *_independent_review(fd, "WP01"),
        _attest("01EEEEEEEEEEEEEEEEEEEEE000", "WP01", "approved", minute=5),
        _event("01FFFFFFFFFFFFFFFFFFFFF000", "WP01", "approved", "in_progress", "bob", minute=6),
        _event("01FFFFFFFFFFFFFFFFFFFFF001", "WP01", "in_progress", "for_review", "alice", minute=7),
        _event("01FFFFFFFFFFFFFFFFFFFFF002", "WP01", "for_review", "in_review", "bob", minute=8),
        _event("01FFFFFFFFFFFFFFFFFFFFF003", "WP01", "in_review", "approved", "bob", minute=9),
    ]
    _write_events(fd, events)
    assert _evaluate_log(repo, fd, manifest, "approved").codes == [ev.IMPLEMENTATION_MISSING]


def test_the_runs_own_done_a_forced_self_transition_and_a_resume_keep_the_attestation(tmp_path: Path) -> None:
    repo, fd, manifest = _hollow_lane(tmp_path)
    reviewed = _event("01FFFFFFFFFFFFFFFFFFFFF001", "WP01", "done", "done", "operator", minute=7, metadata={"attestation": "approved_reviewed"})
    reviewed["force"] = True
    events = [
        *_independent_review(fd, "WP01"),
        _attest("01EEEEEEEEEEEEEEEEEEEEE000", "WP01", "approved", minute=5),
        _event("01FFFFFFFFFFFFFFFFFFFFF000", "WP01", "approved", "done", "spec-kitty", minute=6),
        reviewed,
    ]
    _write_events(fd, events)
    for _attempt in ("first run", "resume"):
        report = _evaluate_log(repo, fd, manifest, "done")
        assert report.refusal is None, _attempt
        assert report.lifted_wp_ids == frozenset({"WP01"}), _attempt


def test_a_re_attestation_after_rework_lifts_again(tmp_path: Path) -> None:
    repo, fd, manifest = _hollow_lane(tmp_path)
    reopen = _event("01FFFFFFFFFFFFFFFFFFFFF000", "WP01", "approved", "planned", "bob", minute=6)
    reopen["force"] = True
    events = [
        *_independent_review(fd, "WP01"),
        _attest("01EEEEEEEEEEEEEEEEEEEEE000", "WP01", "approved", minute=5),
        reopen,
        *_independent_review(fd, "WP01", reviewer="carol", seq=10),
        _attest("01EEEEEEEEEEEEEEEEEEEEE001", "WP01", "approved", minute=20),
    ]
    _write_events(fd, events)
    report = _evaluate_log(repo, fd, manifest, "approved")
    assert report.refusal is None
    assert report.lifted_wp_ids == frozenset({"WP01"})


def test_a_migration_transition_out_of_approved_does_not_void_the_attestation(tmp_path: Path) -> None:
    repo, fd, manifest = _hollow_lane(tmp_path)
    migration = _event("01FFFFFFFFFFFFFFFFFFFFF000", "WP01", "approved", "planned", "migration:backfill", minute=6)
    migration["force"] = True
    _write_events(fd, [*_independent_review(fd, "WP01"), _attest("01EEEEEEEEEEEEEEEEEEEEE000", "WP01", "approved", minute=5), migration])
    report = _evaluate_log(repo, fd, manifest, "approved")
    assert report.refusal is None
    assert report.lifted_wp_ids == frozenset({"WP01"})


def test_the_scope_is_read_in_append_order_not_by_wall_clock() -> None:
    """An attestation appended after a reopen counts, even if its clock reads earlier; and vice versa."""
    attest = SimpleNamespace(
        wp_id="WP01", actor="operator", to_lane="approved", at="2026-02-08T12:09:00+00:00", policy_metadata={"attestation": ev.NO_IMPLEMENTATION}
    )
    reopen = SimpleNamespace(wp_id="WP01", actor="bob", to_lane="planned", at="2026-02-08T12:01:00+00:00", policy_metadata=None)
    other_wp = SimpleNamespace(wp_id="WP02", actor="bob", to_lane="planned", at="2026-02-08T12:10:00+00:00", policy_metadata=None)
    assert not ev._attested_no_implementation([attest, reopen], "WP01")
    assert ev._attested_no_implementation([reopen, attest, other_wp], "WP01")
    assert ev._no_implementation_attested_wp_ids([attest, reopen]) == frozenset()
    assert ev._no_implementation_attested_wp_ids([reopen, attest, other_wp]) == frozenset({"WP01"})
    assert ev.in_force_no_implementation_attestation([reopen, attest], "WP01") is attest
    assert ev.in_force_no_implementation_attestation([attest, reopen], "WP01") is None


def test_unreadable_event_log_never_lifts_by_attestation(tmp_path: Path) -> None:
    repo, fd, planning = _lane_fixture(tmp_path)
    _write_events(fd, _independent_review(fd, "WP01"))
    report = ev.evaluate_evidence(
        repo, fd, _manifest([_lane("lane-a", ["WP01"])], planning), {"WP01": {"lane": "approved"}}, events=lambda: None, is_single_branch=False
    )
    assert report.codes == [ev.IMPLEMENTATION_MISSING]


def test_missing_planning_commit_is_uncomputable(tmp_path: Path) -> None:
    repo, fd, _planning = _lane_fixture(tmp_path)
    report = _evaluate(repo, fd, _manifest([_lane("lane-a", ["WP01"])], None), {"WP01": "approved"})
    assert report.codes == [ev.EVIDENCE_WINDOW_UNCOMPUTABLE]
    assert "finalize-tasks" in str(report.refusal)


def test_unreadable_window_is_unreadable(tmp_path: Path) -> None:
    repo, fd, _planning = _lane_fixture(tmp_path)
    report = _evaluate(repo, fd, _manifest([_lane("lane-a", ["WP01"])], "0" * 40), {"WP01": "approved"})
    assert report.codes == [ev.IMPLEMENTATION_UNREADABLE]


def test_planning_lane_is_windowed_to_the_target(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    fd = _feature_dir(repo, {"WP01": f"kitty-specs/{_SLUG}/research/**"})
    planning = _commit(repo, f"kitty-specs/{_SLUG}/plan.md", "# plan\n", "planning")
    _write_events(fd, _independent_review(fd, "WP01"))
    manifest = _manifest([_lane("lane-planning", ["WP01"])], planning)
    _commit(repo, f"kitty-specs/{_SLUG}/issue-matrix.json", "{}\n", "bookkeeping only")
    assert _evaluate(repo, fd, manifest, {"WP01": "approved"}).codes == [ev.IMPLEMENTATION_MISSING]
    _commit(repo, f"kitty-specs/{_SLUG}/research/notes.md", "# notes\n", "research")
    assert _evaluate(repo, fd, manifest, {"WP01": "approved"}).refusal is None


def test_unapproved_canceled_and_fully_canceled_lanes_are_not_judged(tmp_path: Path) -> None:
    repo, fd, planning = _lane_fixture(tmp_path)
    manifest = _manifest([_lane("lane-a", ["WP01"]), _lane("lane-b", ["WP02"])], planning)
    work_packages = {"WP01": {"lane": "in_progress"}, "WP02": {"lane": "approved"}}
    report = ev.evaluate_evidence(repo, fd, manifest, work_packages, {"WP02"}, events=list, is_single_branch=False)
    assert report == ev.EvidenceReport()


def test_lines_are_ordered_by_work_package(tmp_path: Path) -> None:
    repo, fd, planning = _lane_fixture(tmp_path)
    _feature_dir(repo, {"WP02": "tools/check.sh"})
    _git(repo, "branch", "kitty/mission-fx-lane-b")
    manifest = _manifest([_lane("lane-b", ["WP02"]), _lane("lane-a", ["WP01"])], planning)
    report = _evaluate(repo, fd, manifest, {"WP01": "approved", "WP02": "approved"})
    text = str(report.refusal)
    assert text.index("IMPLEMENTATION_MISSING: WP01") < text.index("IMPLEMENTATION_MISSING: WP02")


def test_a_removal_of_a_dependency_lanes_content_counts_as_evidence(tmp_path: Path) -> None:
    """A WP whose reviewed deliverable deletes content it absorbed from its dependency nets to nothing against the planning commit.

    The shared-file shape (a later WP edits an earlier WP's file, as the #5571 dependent-edit
    missions do): the merge-base window holds only lane-b's own commits since it absorbed lane-a.
    """
    repo = _repo(tmp_path)
    fd = _feature_dir(repo, {"WP01": "src/m1/**", "WP02": "src/m1/**"})
    planning = _commit(repo, f"kitty-specs/{_SLUG}/plan.md", "# plan\n", "planning")
    _git(repo, "branch", _LANE_BRANCH)
    _git(repo, "branch", "kitty/mission-fx-lane-b")
    _git(repo, "checkout", "-q", _LANE_BRANCH)
    _commit(repo, "src/m1/real.py")
    # lane-b takes lane-a in (the dependency merge) and then removes its file: its tree equals
    # the planning tree, so only the dependency window shows the work.
    _git(repo, "checkout", "-q", "kitty/mission-fx-lane-b")
    _git(repo, "merge", "-q", "--no-edit", _LANE_BRANCH)
    _git(repo, "rm", "-q", "src/m1/real.py")
    _git(repo, "commit", "-qm", "feat(WP02): drop the module")
    _git(repo, "checkout", "-q", "main")
    _write_events(fd, [*_independent_review(fd, "WP01"), *_independent_review(fd, "WP02", seq=10)])
    lane_a = _lane("lane-a", ["WP01"])
    lane_b = ExecutionLane(lane_id="lane-b", wp_ids=["WP02"], write_scope=[], predicted_surfaces=[], depends_on_lanes=["lane-a"], parallel_group=0)
    manifest = _manifest([lane_a, lane_b], planning)

    # The window starts where lane-b last absorbed lane-a (their merge base), not at lane-a's live tip.
    assert ev._dependency_evidence_windows(repo, manifest, lane_b) == [
        (_git(repo, "merge-base", _LANE_BRANCH, "kitty/mission-fx-lane-b"), "kitty/mission-fx-lane-b")
    ]
    assert _evaluate(repo, fd, manifest, {"WP01": "approved", "WP02": "approved"}).refusal is None


def test_a_dependency_window_does_not_excuse_a_work_package_that_committed_nothing(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    fd = _feature_dir(repo, {"WP01": "src/m1/**", "WP02": "src/m2/**"})
    planning = _commit(repo, f"kitty-specs/{_SLUG}/plan.md", "# plan\n", "planning")
    _git(repo, "branch", _LANE_BRANCH)
    _git(repo, "branch", "kitty/mission-fx-lane-b")
    _git(repo, "checkout", "-q", _LANE_BRANCH)
    _commit(repo, "src/m1/real.py")
    _git(repo, "checkout", "-q", "kitty/mission-fx-lane-b")
    _git(repo, "merge", "-q", "--no-edit", _LANE_BRANCH)
    _git(repo, "checkout", "-q", "main")
    _write_events(fd, [*_independent_review(fd, "WP01"), *_independent_review(fd, "WP02", seq=10)])
    lane_b = ExecutionLane(lane_id="lane-b", wp_ids=["WP02"], write_scope=[], predicted_surfaces=[], depends_on_lanes=["lane-a"], parallel_group=0)
    manifest = _manifest([_lane("lane-a", ["WP01"]), lane_b], planning)

    report = _evaluate(repo, fd, manifest, {"WP01": "approved", "WP02": "approved"})

    assert report.codes == [ev.IMPLEMENTATION_MISSING]
    assert "IMPLEMENTATION_MISSING: WP02" in str(report.refusal)


_LANE_B = "kitty/mission-fx-lane-b"


def _dependency_advanced_after_the_cut(tmp_path: Path, later_path: str) -> tuple[Path, Path, LanesManifest]:
    """Review cycle 1 probe: lane-b (hollow WP02) absorbs lane-a, then lane-a advances with *later_path*."""
    repo = _repo(tmp_path)
    fd = _feature_dir(repo, {"WP01": "src/m1/**", "WP02": "src/m2/**"})
    planning = _commit(repo, f"kitty-specs/{_SLUG}/plan.md", "# plan\n", "planning")
    _git(repo, "branch", _LANE_BRANCH)
    _git(repo, "branch", _LANE_B)
    _git(repo, "checkout", "-q", _LANE_BRANCH)
    _commit(repo, "src/m1/real.py")
    _git(repo, "checkout", "-q", _LANE_B)
    _git(repo, "merge", "-q", "--no-edit", _LANE_BRANCH)  # WP02 claimed: the dependency merge, nothing committed
    _git(repo, "checkout", "-q", _LANE_BRANCH)
    _commit(repo, later_path, "later\n", "the dependency lane advances after lane-b absorbed it")
    _git(repo, "checkout", "-q", "main")
    _write_events(fd, [*_independent_review(fd, "WP01"), *_independent_review(fd, "WP02", seq=10)])
    lane_b = ExecutionLane(lane_id="lane-b", wp_ids=["WP02"], write_scope=[], predicted_surfaces=[], depends_on_lanes=["lane-a"], parallel_group=0)
    return repo, fd, _manifest([_lane("lane-a", ["WP01"]), lane_b], planning)


def test_an_out_of_map_edit_on_a_dependency_lane_after_the_cut_does_not_excuse_a_hollow_work_package(tmp_path: Path) -> None:
    repo, fd, manifest = _dependency_advanced_after_the_cut(tmp_path, "src/m2/x.py")

    report = _evaluate(repo, fd, manifest, {"WP01": "approved", "WP02": "approved"})

    assert "IMPLEMENTATION_MISSING: WP02" in str(report.refusal), report.refusal


def test_an_in_model_dependency_advance_leaves_a_hollow_work_package_missing(tmp_path: Path) -> None:
    repo, fd, manifest = _dependency_advanced_after_the_cut(tmp_path, "src/m1/more.py")

    report = _evaluate(repo, fd, manifest, {"WP01": "approved", "WP02": "approved"})

    assert "IMPLEMENTATION_MISSING: WP02" in str(report.refusal), report.refusal
    assert "WP01" not in str(report.refusal)


def test_an_unreadable_dependency_window_is_unreadable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo, fd, manifest = _dependency_advanced_after_the_cut(tmp_path, "src/m1/more.py")
    planning = manifest.planning_commit_sha
    real = ev.changed_paths_in_range

    def flaky(repo_root: Path, base: str, tip: str) -> list[tuple[str, str]]:
        if base != planning:
            raise ev.GitProbeError(f"injected: {base}..{tip}")
        return real(repo_root, base, tip)

    monkeypatch.setattr(ev, "changed_paths_in_range", flaky)

    report = _evaluate(repo, fd, manifest, {"WP01": "approved", "WP02": "approved"})

    assert report.codes == [ev.IMPLEMENTATION_UNREADABLE], report.refusal
    assert "IMPLEMENTATION_UNREADABLE: WP02" in str(report.refusal)


def test_an_approved_work_package_in_no_lane_is_judged(tmp_path: Path) -> None:
    """The lanes path judges every approved work package, as single_branch does: one in no lane has no window."""
    repo, fd, planning = _lane_fixture(tmp_path)
    _git(repo, "checkout", "-q", _LANE_BRANCH)
    _commit(repo, "src/m1/real.py")
    _git(repo, "checkout", "-q", "main")
    _write_events(fd, _independent_review(fd, "WP01"))
    manifest = _manifest([_lane("lane-a", ["WP01"])], planning)

    report = _evaluate(repo, fd, manifest, {"WP01": "approved", "WP09": "approved"})

    assert report.codes == [ev.EVIDENCE_WINDOW_UNCOMPUTABLE], report.refusal
    assert "EVIDENCE_WINDOW_UNCOMPUTABLE: WP09" in str(report.refusal)


# --------------------------------------------------------------------------- single_branch keeps its voice


def test_single_branch_keeps_its_codes_and_text(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    fd = _feature_dir(repo, {"WP01": "src/m1/**"})
    planning = _git(repo, "rev-parse", "HEAD")
    _commit(repo, "docs.md")
    manifest = _manifest([_lane("lane-planning", ["WP01"])], planning)
    manifest.mission_branch = "main"
    report = _evaluate(repo, fd, manifest, {"WP01": "approved"}, single_branch=True)
    assert report.codes == [ev.SINGLE_BRANCH_IMPLEMENTATION_MISSING]
    assert str(report.refusal).startswith(f"Mission {_SLUG}: single_branch work packages cannot be landed as reviewed:")


def test_mission_evidence_report_reads_the_snapshot(tmp_path: Path) -> None:
    repo, fd, planning = _lane_fixture(tmp_path)
    _write_events(fd, _independent_review(fd, "WP01"))
    (fd / "meta.json").write_text(json.dumps({"mission_slug": _SLUG, "topology": "lanes"}), encoding="utf-8")
    report = ev.mission_evidence_report(repo, fd, _manifest([_lane("lane-a", ["WP01"])], planning))
    assert report.codes == [ev.IMPLEMENTATION_MISSING]
