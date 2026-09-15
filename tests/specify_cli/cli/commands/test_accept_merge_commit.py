"""``spec-kitty accept --mode pr --merge-commit`` integration tests (issue #4231).

A mission accepted through a GitHub PR never passes through
``spec-kitty merge``, so its ``meta.json`` never carried
``baseline_merge_commit`` — leaving post-merge review unreachable and the
lightweight dead-code gate failing a cleanly merged mission. These tests pin
the accept-side repair:

* ``--merge-commit`` outside ``--mode pr`` is a clean usage error (exit 2).
* An unverifiable SHA is a clean error (exit 1) raised BEFORE any acceptance
  write — nothing is mutated on the refused paths.
* An unmerged Specify-only branch commit is refused: first introduction is
  not landing, so only the target-branch membership check separates it from
  a real PR merge (#4231 monitor finding).
* A verified merge commit is recorded into the mission's ``meta.json``
  (``baseline_merge_commit`` = the merge commit's first parent,
  ``pr_merge_commit`` = the landing commit) and the tree stays clean.

The fixture builds the real elements-first shape: a mission branch merged
into ``main`` by a PR-shaped ``--no-ff`` merge commit whose first parent
predates the mission corpus, with accept running on the mission branch.
"""

from __future__ import annotations

import json
import subprocess
from kernel.clock import now_utc_iso
from pathlib import Path

import pytest
import typer

from specify_cli.acceptance.matrix import (
    AcceptanceCriterion,
    AcceptanceMatrix,
    write_acceptance_matrix,
)
from specify_cli.cli.commands.accept import accept
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.lanes.persistence import write_lanes_json
from specify_cli.status.emit import build_claim_policy_metadata
from specify_cli.status.models import Lane, StatusEvent
from specify_cli.status.reducer import materialize
from specify_cli.status.store import append_event

# Real git + the real accept pipeline: mutmut's forked sandbox cannot host it.
pytestmark = [pytest.mark.non_sandbox, pytest.mark.git_repo]

_SLUG = "321-pr-accepted-mission-01TEST"
_MISSION_ID = "01TESTPRACCEPTMUTATION00000"
_MISSION_BRANCH = f"kitty/mission-{_SLUG}"


def _git(repo_root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo_root), *args],
        check=True,
        capture_output=True,
        text=True,
    )


def _create_pr_merged_feature(repo_root: Path, *, merged: bool = True, squash: bool = False) -> tuple[Path, str, str]:
    """Create an accept-ready mission whose PR already merged into main.

    Returns ``(feature_dir, merge_commit, pre_merge_parent)``. The base
    commit on main predates ``kitty-specs/`` entirely; the mission branch
    carries the corpus; a ``--no-ff`` merge lands it on main (the PR-shaped
    merge commit); accept then runs on the mission branch, as it does in the
    elements-first programme. With ``squash=True`` the landing is a
    single-parent squash commit instead — the shape that needs the
    operator's ``--attest-first-landing-commit`` attestation.

    With ``merged=False`` the branch is NEVER merged and the returned
    "merge commit" is the single corpus commit on the unmerged branch — the
    #4231 monitor repro shape: it introduces the corpus (parent lacks it) but
    never landed on the target branch.
    """
    _git(repo_root, "init", ".")
    _git(repo_root, "config", "user.email", "test@test.com")
    _git(repo_root, "config", "user.name", "Test")
    _git(repo_root, "branch", "-M", "main")

    # .kittify marker anchors find_repo_root() to this repo (paired with the
    # SPECIFY_REPO_ROOT env var set by the test).
    (repo_root / ".kittify").mkdir()
    for required_dir in ("src", "tests", "docs"):
        path = repo_root / required_dir
        path.mkdir()
        (path / ".gitkeep").write_text("")

    # Base commit on main WITHOUT the mission corpus.
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-m", "base")

    _git(repo_root, "checkout", "-b", _MISSION_BRANCH)

    feature_dir = repo_root / "kitty-specs" / _SLUG
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)
    (feature_dir / "contracts").mkdir(parents=True, exist_ok=True)

    meta = {
        "mission_number": "321",
        "slug": _SLUG,
        "mission_slug": _SLUG,
        "mission_id": _MISSION_ID,
        "mid8": _MISSION_ID[:8],
        "friendly_name": "PR Accepted Mission",
        "mission_type": "software-dev",
        "target_branch": "main",
        "created_at": "2026-01-01T00:00:00Z",
    }
    (feature_dir / "meta.json").write_text(json.dumps(meta, indent=2) + "\n")

    for fname in ("spec.md", "plan.md", "tasks.md"):
        (feature_dir / fname).write_text(f"# {fname}\nDone.\n")

    (tasks_dir / "WP01-test.md").write_text(
        "---"
        '\nwork_package_id: "WP01"'
        '\ntitle: "Test WP"'
        '\nlane: "done"'
        '\nassignee: "test-agent"'
        '\nagent: "test-agent"'
        '\nshell_pid: "12345"'
        "\nsubtasks: []"
        "\n---"
        "\n# WP01\nDone.\n"
    )

    # Event-sourced done state (the same planned -> claimed -> done legs the
    # clean-tree regression fixture seeds).
    append_event(
        feature_dir,
        StatusEvent(
            event_id="01TESTPRACCEPTMUTATION0001",
            mission_slug=_SLUG,
            wp_id="WP01",
            from_lane=Lane.PLANNED,
            to_lane=Lane.CLAIMED,
            at="2026-01-01T00:00:00+00:00",
            actor="test-agent",
            force=False,
            execution_mode="direct_repo",
            policy_metadata=build_claim_policy_metadata(
                shell_pid=12345,
                shell_pid_created_at="2026-01-01T00:00:00+00:00",
                agent="test-agent",
            ),
        ),
    )
    append_event(
        feature_dir,
        StatusEvent(
            event_id="01TESTPRACCEPTMUTATION0002",
            mission_slug=_SLUG,
            wp_id="WP01",
            from_lane=Lane.CLAIMED,
            to_lane=Lane.DONE,
            at=now_utc_iso(),
            actor="test-agent",
            force=True,
            execution_mode="direct_repo",
            reason="Test setup: skip to done",
        ),
    )
    materialize(feature_dir)

    write_lanes_json(
        feature_dir,
        LanesManifest(
            version=1,
            mission_slug=_SLUG,
            mission_id=_SLUG,
            mission_branch=_MISSION_BRANCH,
            target_branch="main",
            lanes=[
                ExecutionLane(
                    lane_id="lane-a",
                    wp_ids=("WP01",),
                    write_scope=("src/**",),
                    predicted_surfaces=("test",),
                    depends_on_lanes=(),
                    parallel_group=0,
                )
            ],
            computed_at="2026-04-05T12:00:00Z",
            computed_from="test",
        ),
    )

    write_acceptance_matrix(
        feature_dir,
        AcceptanceMatrix(
            mission_slug=_SLUG,
            criteria=[
                AcceptanceCriterion(
                    criterion_id="AC1",
                    description="feature behaves as specified",
                    proof_type="automated_test",
                    pass_fail="pass",
                )
            ],
            negative_invariants=[],
        ),
    )

    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-m", "mission corpus")

    # The PR-shaped landing on main: first parent predates the corpus.
    _git(repo_root, "checkout", "main")
    if merged and squash:
        _git(repo_root, "merge", "--squash", "-q", _MISSION_BRANCH)
        _git(repo_root, "commit", "-m", f"Squash PR: land {_SLUG}")
        merge_commit = _git(repo_root, "rev-parse", "HEAD").stdout.strip()
        pre_merge_parent = _git(repo_root, "rev-parse", "HEAD^1").stdout.strip()
    elif merged:
        _git(
            repo_root,
            "merge",
            "--no-ff",
            "-m",
            f"Merge PR: land {_SLUG}",
            _MISSION_BRANCH,
        )
        merge_commit = _git(repo_root, "rev-parse", "HEAD").stdout.strip()
        pre_merge_parent = _git(repo_root, "rev-parse", "HEAD^1").stdout.strip()
    else:
        # The unmerged branch's single corpus commit; its parent is the base.
        merge_commit = _git(repo_root, "rev-parse", _MISSION_BRANCH).stdout.strip()
        pre_merge_parent = _git(repo_root, "rev-parse", f"{_MISSION_BRANCH}^1").stdout.strip()

    # Accept runs on the mission branch (the elements-first operator flow).
    _git(repo_root, "checkout", _MISSION_BRANCH)
    return feature_dir, merge_commit, pre_merge_parent


def _porcelain(repo_root: Path) -> str:
    return subprocess.run(
        ["git", "-C", str(repo_root), "status", "--porcelain"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def test_accept_pr_mode_records_verified_merge_as_baseline(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``accept --mode pr --merge-commit <sha> --attest-first-landing-commit`` records real merge evidence.

    A two-parent merge landing is recordable only under the operator's
    attestation (two parents alone do not prove the first parent is the
    pre-landing target tip — the internal-merge landing is graph-identical),
    and the persisted evidence class names the attestation.
    """
    repo_root = (tmp_path / "repo").resolve()
    repo_root.mkdir()
    feature_dir, merge_commit, pre_merge_parent = _create_pr_merged_feature(repo_root)
    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(repo_root))
    monkeypatch.chdir(repo_root)

    # Unattested: a clean pre-write exit-1 refusal, nothing recorded.
    with pytest.raises(typer.Exit) as exit_info:
        accept(
            mission=_SLUG,
            mode="pr",
            actor="tester",
            test=[],
            json_output=True,
            lenient=False,
            no_commit=False,
            diagnose=False,
            allow_fail=False,
            merge_commit=merge_commit,
        )
    assert exit_info.value.exit_code == 1
    assert "baseline_merge_commit" not in (feature_dir / "meta.json").read_text(encoding="utf-8")

    # Successful (non-json) attested accept returns normally; no Exit is raised.
    accept(
        mission=_SLUG,
        mode="pr",
        actor="tester",
        test=[],
        json_output=False,
        lenient=False,
        no_commit=False,
        diagnose=False,
        allow_fail=False,
        merge_commit=merge_commit,
        attest_first_landing=True,
    )

    meta = json.loads((feature_dir / "meta.json").read_text(encoding="utf-8"))
    assert meta["baseline_merge_commit"] == pre_merge_parent, (
        f"baseline must be the merge commit's first parent (the pre-landing target tip), not the merge commit itself: {meta}"
    )
    assert meta["pr_merge_commit"] == merge_commit
    assert meta["pr_merge_evidence"] == "merge-commit-parent-attested"
    assert meta["acceptance_mode"] == "pr"

    # The recording is swept into the residual finalize commit: clean tree.
    assert _porcelain(repo_root) == "", "accept left a dirty working tree"


def test_accept_merge_commit_outside_pr_mode_is_usage_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``--merge-commit`` with a non-pr mode is a clean exit-2 usage error."""
    repo_root = (tmp_path / "repo").resolve()
    repo_root.mkdir()
    feature_dir, merge_commit, _parent = _create_pr_merged_feature(repo_root)
    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(repo_root))
    monkeypatch.chdir(repo_root)

    with pytest.raises(typer.Exit) as exc_info:
        accept(
            mission=_SLUG,
            mode="local",
            actor="tester",
            test=[],
            json_output=True,
            lenient=False,
            no_commit=False,
            diagnose=False,
            allow_fail=False,
            merge_commit=merge_commit,
        )

    assert exc_info.value.exit_code == 2
    # Refused before any acceptance write: meta.json carries no baseline.
    meta = json.loads((feature_dir / "meta.json").read_text(encoding="utf-8"))
    assert "baseline_merge_commit" not in meta
    assert "pr_merge_commit" not in meta


def test_accept_unverifiable_merge_commit_fails_clean(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A SHA that resolves to nothing is a clean exit-1 error, pre-write."""
    repo_root = (tmp_path / "repo").resolve()
    repo_root.mkdir()
    feature_dir, _merge_commit, _parent = _create_pr_merged_feature(repo_root)
    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(repo_root))
    monkeypatch.chdir(repo_root)

    with pytest.raises(typer.Exit) as exc_info:
        accept(
            mission=_SLUG,
            mode="pr",
            actor="tester",
            test=[],
            json_output=True,
            lenient=False,
            no_commit=False,
            diagnose=False,
            allow_fail=False,
            merge_commit="deadbeef" * 5,
        )

    assert exc_info.value.exit_code == 1
    meta = json.loads((feature_dir / "meta.json").read_text(encoding="utf-8"))
    assert "baseline_merge_commit" not in meta
    assert "pr_merge_commit" not in meta


def test_accept_no_commit_verifies_but_does_not_write(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``--no-commit`` is report-only: the evidence is verified, nothing recorded."""
    repo_root = (tmp_path / "repo").resolve()
    repo_root.mkdir()
    feature_dir, merge_commit, _parent = _create_pr_merged_feature(repo_root)
    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(repo_root))
    monkeypatch.chdir(repo_root)

    accept(
        mission=_SLUG,
        mode="pr",
        actor="tester",
        test=[],
        json_output=True,
        lenient=False,
        no_commit=True,
        diagnose=False,
        allow_fail=False,
        merge_commit=merge_commit,
        attest_first_landing=True,
    )

    meta = json.loads((feature_dir / "meta.json").read_text(encoding="utf-8"))
    assert "baseline_merge_commit" not in meta
    assert "pr_merge_commit" not in meta


def test_accept_unmerged_specify_commit_fails_clean(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """An unmerged Specify-only branch commit is not merge evidence (#4231 monitor).

    The branch's single corpus commit introduces ``meta.json`` (its parent
    lacks it), so every first-introduction check passes — but it never landed
    on the target branch, so the accept-side verification refuses it before
    any acceptance write.
    """
    repo_root = (tmp_path / "repo").resolve()
    repo_root.mkdir()
    feature_dir, specify_commit, _parent = _create_pr_merged_feature(repo_root, merged=False)
    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(repo_root))
    monkeypatch.chdir(repo_root)

    with pytest.raises(typer.Exit) as exc_info:
        accept(
            mission=_SLUG,
            mode="pr",
            actor="tester",
            test=[],
            json_output=True,
            lenient=False,
            no_commit=False,
            diagnose=False,
            allow_fail=False,
            merge_commit=specify_commit,
        )

    assert exc_info.value.exit_code == 1
    meta = json.loads((feature_dir / "meta.json").read_text(encoding="utf-8"))
    assert "baseline_merge_commit" not in meta
    assert "pr_merge_commit" not in meta


def test_accept_single_parent_landing_needs_attestation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A squash landing is single-parent: attested, never presented as proven.

    The squash commit's parent IS the pre-landing tip, but git cannot prove
    that (an impl-before-corpus replay is graph-identical), so the bare call
    is a clean pre-write exit-1 refusal, and the attested call records the
    anchor with ``pr_merge_evidence: corpus-parent-attested`` naming the
    operator's attestation — never a git proof (#4231 fix round).
    """
    repo_root = (tmp_path / "repo").resolve()
    repo_root.mkdir()
    feature_dir, squash_commit, pre_squash_tip = _create_pr_merged_feature(repo_root, squash=True)
    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(repo_root))
    monkeypatch.chdir(repo_root)

    with pytest.raises(typer.Exit) as exc_info:
        accept(
            mission=_SLUG,
            mode="pr",
            actor="tester",
            test=[],
            json_output=True,
            lenient=False,
            no_commit=False,
            diagnose=False,
            allow_fail=False,
            merge_commit=squash_commit,
        )

    assert exc_info.value.exit_code == 1
    meta = json.loads((feature_dir / "meta.json").read_text(encoding="utf-8"))
    assert "baseline_merge_commit" not in meta
    assert "pr_merge_commit" not in meta
    assert "pr_merge_evidence" not in meta

    accept(
        mission=_SLUG,
        mode="pr",
        actor="tester",
        test=[],
        json_output=False,
        lenient=False,
        no_commit=False,
        diagnose=False,
        allow_fail=False,
        merge_commit=squash_commit,
        attest_first_landing=True,
    )

    meta = json.loads((feature_dir / "meta.json").read_text(encoding="utf-8"))
    assert meta["baseline_merge_commit"] == pre_squash_tip
    assert meta["pr_merge_commit"] == squash_commit
    assert meta["pr_merge_evidence"] == "corpus-parent-attested"
