"""Unit coverage for the #5939 single_branch implementation-evidence + independence axis.

The end-to-end guards live in ``tests/integration/test_5939_single_branch_autowalk_guards.py``;
this file pins the consolidate-side axis (``reconciliation._single_branch_evidence_refusal``) and
its pure helpers directly, over a tiny real git repo, so the fail-closed / refuse branches are
cheap to exercise.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from specify_cli.consolidation import reconciliation
from specify_cli.lanes.models import ExecutionLane, LanesManifest

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]


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


def _feature_dir(repo: Path, owned: str = "src/m1/**") -> Path:
    fd = repo / "kitty-specs" / "fx"
    (fd / "tasks").mkdir(parents=True)
    (fd / "tasks" / "WP01-m1.md").write_text(
        f"---\nwork_package_id: WP01\ntitle: WP01\ndependencies: []\nowned_files:\n  - {owned}\nsubtasks:\n  - T1\n---\n# WP01\n",
        encoding="utf-8",
    )
    return fd


def _manifest() -> LanesManifest:
    return LanesManifest(
        version=1,
        mission_slug="fx",
        mission_id=None,
        mission_branch="main",
        target_branch="main",
        lanes=[
            ExecutionLane(
                lane_id="lane-planning",
                wp_ids=["WP01"],
                write_scope=["src/m1/**"],
                predicted_surfaces=[],
                depends_on_lanes=[],
                parallel_group=0,
            )
        ],
        computed_at="now",
        computed_from="test",
    )


_APPROVED = {"WP01": {"lane": "approved"}}


def _refuse(repo: Path, fd: Path, window: tuple[str, str] | None, *, is_single_branch: bool = True) -> str | None:
    return reconciliation._single_branch_evidence_refusal(repo, fd, _manifest(), _APPROVED, frozenset(), window, is_single_branch=is_single_branch)


def test_not_single_branch_never_refuses(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    fd = _feature_dir(repo)
    assert _refuse(repo, fd, None, is_single_branch=False) is None


def test_single_branch_with_uncomputable_window_fails_closed(tmp_path: Path) -> None:
    """Change 2: a single_branch mission with approved work but no computable window REFUSES."""
    repo = _repo(tmp_path)
    fd = _feature_dir(repo)
    refusal = _refuse(repo, fd, None, is_single_branch=True)
    assert refusal is not None
    assert reconciliation._SB_WINDOW_UNCOMPUTABLE in refusal
    assert reconciliation.single_branch_refusal_codes(refusal) == [reconciliation._SB_WINDOW_UNCOMPUTABLE]


def test_no_approved_wps_never_refuses(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    fd = _feature_dir(repo)
    base = _git(repo, "rev-parse", "HEAD")
    result = reconciliation._single_branch_evidence_refusal(
        repo, fd, _manifest(), {"WP01": {"lane": "in_progress"}}, frozenset(), (base, "main"), is_single_branch=True
    )
    assert result is None


def test_approved_wp_with_no_implementation_commit_refuses(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    fd = _feature_dir(repo)
    base = _git(repo, "rev-parse", "HEAD")
    # A commit that touches a NON-owned path only: no implementation evidence for WP01.
    (repo / "docs.md").write_text("notes\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "docs only")
    refusal = _refuse(repo, fd, (base, "main"))
    assert refusal is not None
    assert reconciliation._SB_IMPLEMENTATION_MISSING in refusal
    assert "WP01" in refusal
    assert reconciliation.single_branch_refusal_codes(refusal) == [reconciliation._SB_IMPLEMENTATION_MISSING]


def _event(event_id: str, at: str, from_lane: str, to_lane: str, actor: str) -> dict[str, object]:
    return {
        "event_id": event_id,
        "at": at,
        "wp_id": "WP01",
        "from_lane": from_lane,
        "to_lane": to_lane,
        "actor": actor,
        "evidence": None,
        "execution_mode": "direct_repo",
        "feature_slug": "fx",
        "force": False,
        "reason": None,
        "review_ref": None,
    }


def _write_events(fd: Path, events: list[dict[str, object]]) -> None:
    """Write a minimal status.events.jsonl the role projections can read."""
    (fd / "status.events.jsonl").write_text("\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8")


def _impl_commit(repo: Path) -> None:
    (repo / "src" / "m1").mkdir(parents=True, exist_ok=True)
    (repo / "src" / "m1" / "real.py").write_text("V = 1\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "feat: implement m1")


def test_implementation_present_but_unknown_implementer_refuses_strict(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    fd = _feature_dir(repo)
    base = _git(repo, "rev-parse", "HEAD")
    # A real commit in owned_files clears axis (a); with no recorded implementer identity the
    # review is not a confirmable independent one, so STRICT axis (b) refuses (operator ruling:
    # a legit mission records a real implementer via `implement --agent <name>`).
    _impl_commit(repo)
    refusal = _refuse(repo, fd, (base, "main"))
    assert refusal is not None
    assert reconciliation._SB_REVIEW_NOT_INDEPENDENT in refusal
    assert reconciliation._SB_IMPLEMENTATION_MISSING not in refusal


def test_implementation_present_but_same_actor_review_refuses(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    fd = _feature_dir(repo)
    base = _git(repo, "rev-parse", "HEAD")
    _impl_commit(repo)
    # One actor stamped as BOTH implementer (the in_progress claim) and reviewer (the approval):
    # a provably hollow review, exactly the #5939 autowalk shape.
    _write_events(
        fd,
        [
            _event("01AAAAAAAAAAAAAAAAAAAAAAAA", "2026-02-08T12:00:00+00:00", "planned", "in_progress", "bob"),
            _event("01BBBBBBBBBBBBBBBBBBBBBBBB", "2026-02-08T12:05:00+00:00", "in_review", "approved", "bob"),
        ],
    )
    refusal = _refuse(repo, fd, (base, "main"))
    assert refusal is not None
    assert reconciliation._SB_REVIEW_NOT_INDEPENDENT in refusal
    assert reconciliation._SB_IMPLEMENTATION_MISSING not in refusal


def test_implementation_present_with_independent_review_passes(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    fd = _feature_dir(repo)
    base = _git(repo, "rev-parse", "HEAD")
    _impl_commit(repo)
    # Implementer alice, approver bob (distinct): an independent review clears axis (b).
    _write_events(
        fd,
        [
            _event("01CCCCCCCCCCCCCCCCCCCCCCCC", "2026-02-08T12:00:00+00:00", "planned", "in_progress", "alice"),
            _event("01DDDDDDDDDDDDDDDDDDDDDDDD", "2026-02-08T12:05:00+00:00", "in_review", "approved", "bob"),
        ],
    )
    assert _refuse(repo, fd, (base, "main")) is None


def test_unreadable_window_fails_closed(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    fd = _feature_dir(repo)
    refusal = _refuse(repo, fd, ("0" * 40, "main"))  # unresolvable base -> GitProbeError -> REFUSE
    assert refusal is not None
    assert reconciliation._SB_EVIDENCE_UNREADABLE in refusal


def test_owned_pattern_helpers_normalize_and_match() -> None:
    patterns = reconciliation._sb_owned_patterns(["./src/m1/**", "  ", "a\\b/*"])
    assert patterns == ("src/m1/**", "a/b/*")
    assert reconciliation._sb_matches_owned("src/m1/deep/x.py", ("src/m1/**",))
    assert reconciliation._sb_matches_owned("src/m1/x.py", ("src/m1/**",))
    assert not reconciliation._sb_matches_owned("src/m2/x.py", ("src/m1/**",))


def test_mirrored_owned_match_stays_in_lockstep_with_cli_layer() -> None:
    """N3: the mirrored owned-files match must agree with the CLI-layer original so they can't drift."""
    from specify_cli.cli.commands.agent import tasks_move_task as mt

    cases = [
        ("src/m1/deep/x.py", ("src/m1/**",)),
        ("src/m1/x.py", ("src/m1/**",)),
        ("src/m2/x.py", ("src/m1/**",)),
        ("a/b/c.py", ("a/b/*",)),
        ("./src/m1/y.py", ("src/m1/**",)),
    ]
    for path, patterns in cases:
        assert reconciliation._sb_matches_owned(path, patterns) == mt._mt_matches_owned_file(path, patterns)


def test_refusal_codes_reads_each_distinct_leading_code() -> None:
    text = (
        "Mission fx: ...\n"
        f"{reconciliation._SB_IMPLEMENTATION_MISSING}: WP01 ...\n"
        f"{reconciliation._SB_REVIEW_NOT_INDEPENDENT}: WP02 ...\n"
        f"{reconciliation._SB_IMPLEMENTATION_MISSING}: WP03 ...\n"
        "Recovery: ...\n"
    )
    assert reconciliation.single_branch_refusal_codes(text) == [
        reconciliation._SB_IMPLEMENTATION_MISSING,
        reconciliation._SB_REVIEW_NOT_INDEPENDENT,
    ]
