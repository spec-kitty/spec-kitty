"""Coord-BRANCH-vs-``target_branch`` staleness (WP06, coord-commit-integrity-01KY5JS8).

FR-008: ``_coord_branch_stale_vs_target_finding`` / ``doctor coordination
--check-staleness`` / the non-blocking ``finalize-tasks`` WARN.
FR-009: ``doctor coordination --fix``'s Gap-1 fast-forward -- ONLY when the
coord branch is a strict ancestor of ``target_branch`` AND the coord worktree
is clean; anything else FAILS LOUD with a unified diff and mutates NOTHING
(C-005 warn-first). C-003: ``--fix`` stays minimized to this one behaviour.

Distinct from the pre-existing ``_coord_worktree_stale_finding`` (worktree
HEAD vs its OWN coord branch tip) -- Gap-1 compares the coord BRANCH tip
against ``target_branch``, the residual case where the coord branch itself
has fallen behind (or diverged from) the branch it publishes onto.

Fast unit tests (monkeypatched ``subprocess``) cover the extracted predicate
helpers in isolation; the (a)-(d) contract tests use a REAL git repo per the
WP directive ("Use the real-git coord fixture").
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest
import typer

from mission_runtime import MissionArtifactKind

from specify_cli.cli.commands import _coordination_doctor as cd
from specify_cli.cli.commands.agent import tasks_finalize
from specify_cli.agent_tasks_ports import TasksPorts
from tests.mocked_env import setup_mocked_env
from tests.specify_cli.cli.commands.agent.test_tasks_ports import (
    FakeCoordCommitRouter,
    FakeFsReader,
    FakeGitOps,
    FakeRender,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_MISSION = "coord-staleness-01KY5JS8"


# ===========================================================================
# Fast unit tests -- extracted helpers in isolation (monkeypatched subprocess)
# ===========================================================================


def test_rev_parse_returns_stripped_sha(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(subprocess, "check_output", lambda *a, **k: "deadbeef\n")
    assert cd._rev_parse(tmp_path, "HEAD") == "deadbeef"


def test_rev_parse_returns_empty_on_failure(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def _boom(*_a: Any, **_k: Any) -> str:
        raise subprocess.CalledProcessError(1, "git")

    monkeypatch.setattr(subprocess, "check_output", _boom)
    assert cd._rev_parse(tmp_path, "HEAD") == ""


def test_is_ff_candidate_false_for_equal_shas(tmp_path: Path) -> None:
    assert cd._is_ff_candidate(tmp_path, "abc", "abc") is False


def test_is_ff_candidate_false_for_blank_input(tmp_path: Path) -> None:
    assert cd._is_ff_candidate(tmp_path, "", "abc") is False
    assert cd._is_ff_candidate(tmp_path, "abc", "") is False


def test_is_ff_candidate_true_when_merge_base_reports_ancestor(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a, 0)
    )
    assert cd._is_ff_candidate(tmp_path, "a", "b") is True


def test_is_ff_candidate_false_when_diverged(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a, 1)
    )
    assert cd._is_ff_candidate(tmp_path, "a", "b") is False


def test_fast_forward_finding_none_when_equal(tmp_path: Path) -> None:
    assert cd._fast_forward_finding(
        subject_sha="a", tip_sha="a", repo_root=tmp_path,
        message="m", next_step="n", error_code="E",
    ) is None


def test_fast_forward_finding_none_when_not_ff_candidate(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(cd, "_is_ff_candidate", lambda *a: False)
    assert cd._fast_forward_finding(
        subject_sha="a", tip_sha="b", repo_root=tmp_path,
        message="m", next_step="n", error_code="E",
    ) is None


def test_fast_forward_finding_returns_warning_when_ff_candidate(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(cd, "_is_ff_candidate", lambda *a: True)
    finding = cd._fast_forward_finding(
        subject_sha="a", tip_sha="b", repo_root=tmp_path,
        message="m", next_step="n", error_code="E",
    )
    assert finding is not None
    assert finding.severity == "warning"
    assert finding.error_code == "E"


def test_resolve_coord_short_uses_resolver(monkeypatch: pytest.MonkeyPatch) -> None:
    from specify_cli.lanes import branch_naming

    monkeypatch.setattr(branch_naming, "resolve_mid8", lambda *a, **k: "01ABCDEF")
    assert cd._resolve_coord_short("m", "01ABCDEF00000000000000000A") == "01ABCDEF"


def test_resolve_coord_short_falls_back_to_prefix(monkeypatch: pytest.MonkeyPatch) -> None:
    from specify_cli.lanes import branch_naming

    monkeypatch.setattr(branch_naming, "resolve_mid8", lambda *a, **k: "")
    assert cd._resolve_coord_short("m", "01ABCDEF00000000000000000A") == "01ABCDEF"


def test_coord_branch_stale_vs_target_finding_none_when_equal(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(cd, "_rev_parse", lambda *a: "same-sha")
    assert cd._coord_branch_stale_vs_target_finding(tmp_path, "coord", "main") is None


def test_coord_branch_stale_vs_target_finding_stale(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    shas = {"refs/heads/coord": "coord-sha", "refs/heads/main": "main-sha"}
    monkeypatch.setattr(cd, "_rev_parse", lambda _cwd, ref: shas[ref])
    monkeypatch.setattr(cd, "_is_ff_candidate", lambda *a: True)
    finding = cd._coord_branch_stale_vs_target_finding(tmp_path, "coord", "main")
    assert finding is not None
    assert finding.severity == "warning"
    assert finding.error_code == cd._COORD_STALE_VS_TARGET_CODE
    assert "behind target branch" in finding.message


def test_coord_branch_stale_vs_target_finding_diverged(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    shas = {"refs/heads/coord": "coord-sha", "refs/heads/main": "main-sha"}
    monkeypatch.setattr(cd, "_rev_parse", lambda _cwd, ref: shas[ref])
    monkeypatch.setattr(cd, "_is_ff_candidate", lambda *a: False)
    finding = cd._coord_branch_stale_vs_target_finding(tmp_path, "coord", "main")
    assert finding is not None
    assert finding.severity == "warning"
    assert finding.error_code == cd._COORD_DIVERGED_VS_TARGET_CODE
    assert "diverged" in finding.message


def test_check_coord_branch_staleness_skips_legacy_mission(tmp_path: Path) -> None:
    assert cd._check_coord_branch_staleness(tmp_path, {}) == []


def test_check_coord_branch_staleness_skips_missing_target_branch(tmp_path: Path) -> None:
    meta = {"coordination_branch": "coord", "mission_slug": "m", "mission_id": "01ABCDEF00000000000000000A"}
    assert cd._check_coord_branch_staleness(tmp_path, meta) == []


def test_check_coord_branch_staleness_delegates(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # A-3 dedup: `_check_coord_branch_staleness` now resolves both SHAs via the
    # shared `_coord_vs_target_shas` preamble before delegating; both refs must
    # be readable (and non-equal) or the shared helper short-circuits to `[]`
    # before `_coord_branch_stale_vs_target_finding` is ever reached.
    shas = {"refs/heads/coord": "coord-sha", "refs/heads/main": "main-sha"}
    monkeypatch.setattr(cd, "_rev_parse", lambda _cwd, ref: shas[ref])
    sentinel = cd.DoctorFinding(severity="warning", message="m", error_code="E")
    monkeypatch.setattr(cd, "_coord_branch_stale_vs_target_finding", lambda *a: sentinel)
    meta = {
        "coordination_branch": "coord", "mission_slug": "m",
        "mission_id": "01ABCDEF00000000000000000A", "target_branch": "main",
    }
    assert cd._check_coord_branch_staleness(tmp_path, meta) == [sentinel]


def test_coord_vs_target_shas_none_when_target_branch_missing(tmp_path: Path) -> None:
    meta = {"coordination_branch": "coord", "mission_slug": "m", "mission_id": "01ABCDEF00000000000000000A"}
    assert cd._coord_vs_target_shas(tmp_path, meta) is None


def test_coord_vs_target_shas_none_when_sha_unreadable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(cd, "_rev_parse", lambda *_a: "")
    meta = {
        "coordination_branch": "coord", "mission_slug": "m",
        "mission_id": "01ABCDEF00000000000000000A", "target_branch": "main",
    }
    assert cd._coord_vs_target_shas(tmp_path, meta) is None


def test_coord_vs_target_shas_returns_tuple_when_resolvable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    shas = {"refs/heads/coord": "coord-sha", "refs/heads/main": "main-sha"}
    monkeypatch.setattr(cd, "_rev_parse", lambda _cwd, ref: shas[ref])
    meta = {
        "coordination_branch": "coord", "mission_slug": "m",
        "mission_id": "01ABCDEF00000000000000000A", "target_branch": "main",
    }
    assert cd._coord_vs_target_shas(tmp_path, meta) == (
        "coord", "main", "coord-sha", "main-sha",
    )


def test_unified_diff_returns_empty_on_os_error(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def _boom(*_a: Any, **_k: Any) -> Any:
        raise OSError("no git")

    monkeypatch.setattr(subprocess, "run", _boom)
    assert cd._unified_diff(tmp_path, "coord", "main") == ""


def test_fix_one_staleness_requires_declared_ref_postcondition(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A completed merge is not success until the declared coord ref reaches target."""
    from specify_cli import coordination as coord_mod

    monkeypatch.setattr(
        cd,
        "_coord_vs_target_shas",
        lambda *_a: ("coord", "main", "coord-sha", "target-sha"),
    )
    monkeypatch.setattr(cd, "_is_ff_candidate", lambda *_a: True)
    monkeypatch.setattr(
        cd,
        "_coordination_identity",
        lambda *_a: ("coord", "mission", "01ABCDEF00000000000000000A"),
    )
    monkeypatch.setattr(cd, "_resolve_coord_short", lambda *_a: "01ABCDEF")
    monkeypatch.setattr(
        coord_mod.CoordinationWorkspace,
        "worktree_path",
        staticmethod(lambda *_a: tmp_path),
    )
    monkeypatch.setattr(cd, "_coord_worktree_foreign_repo_finding", lambda *_a: None)
    monkeypatch.setattr(cd, "_coord_worktree_head_finding", lambda *_a: None)
    monkeypatch.setattr(cd, "_coord_worktree_dirty_finding", lambda *_a: None)
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *a, **k: subprocess.CompletedProcess(a, 0, stdout="", stderr=""),
    )
    monkeypatch.setattr(cd, "_rev_parse", lambda *_a: "unexpected-sha")

    finding = cd._fix_one_mission_coord_staleness(tmp_path, {})

    assert finding is not None
    # #4950 second-opinion follow-up: distinct code -- a fast-forward DID run
    # in the worktree, so this is not the "nothing was mutated" BLOCKED case.
    assert finding.error_code == cd._COORD_STALE_FIX_POSTCONDITION_CODE
    assert finding.error_code != cd._COORD_STALE_FIX_BLOCKED_CODE
    assert "postcondition" in finding.message
    assert str(tmp_path) in finding.message
    assert "Fast-forwarded" not in capsys.readouterr().out


def test_fix_one_staleness_merges_target_sha_not_branch_name(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """#4950 follow-up: merge the same SHA the postcondition checks against.

    ``target_branch`` can advance between resolving ``target_sha`` (via
    ``_coord_vs_target_shas``) and running the merge; merging the SHA keeps
    the move and the postcondition check pinned to the exact same commit.
    """
    from specify_cli import coordination as coord_mod

    monkeypatch.setattr(
        cd,
        "_coord_vs_target_shas",
        lambda *_a: ("coord", "main", "coord-sha", "target-sha"),
    )
    monkeypatch.setattr(cd, "_is_ff_candidate", lambda *_a: True)
    monkeypatch.setattr(
        cd,
        "_coordination_identity",
        lambda *_a: ("coord", "mission", "01ABCDEF00000000000000000A"),
    )
    monkeypatch.setattr(cd, "_resolve_coord_short", lambda *_a: "01ABCDEF")
    monkeypatch.setattr(
        coord_mod.CoordinationWorkspace,
        "worktree_path",
        staticmethod(lambda *_a: tmp_path),
    )
    monkeypatch.setattr(cd, "_coord_worktree_foreign_repo_finding", lambda *_a: None)
    monkeypatch.setattr(cd, "_coord_worktree_head_finding", lambda *_a: None)
    monkeypatch.setattr(cd, "_coord_worktree_dirty_finding", lambda *_a: None)
    monkeypatch.setattr(cd, "_rev_parse", lambda *_a: "target-sha")

    captured: dict[str, list[str]] = {}

    def _fake_run(cmd: list[str], **_k: Any) -> subprocess.CompletedProcess[str]:
        captured["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", _fake_run)

    finding = cd._fix_one_mission_coord_staleness(tmp_path, {})

    assert finding is None
    assert captured["cmd"][-3:] == ["merge", "--ff-only", "target-sha"]


def test_fix_one_staleness_merge_failure_returns_finding_without_raising(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    """#4950 follow-up: a failed `--ff-only` must surface as a finding, not raise."""
    from specify_cli import coordination as coord_mod

    monkeypatch.setattr(
        cd,
        "_coord_vs_target_shas",
        lambda *_a: ("coord", "main", "coord-sha", "target-sha"),
    )
    monkeypatch.setattr(cd, "_is_ff_candidate", lambda *_a: True)
    monkeypatch.setattr(
        cd,
        "_coordination_identity",
        lambda *_a: ("coord", "mission", "01ABCDEF00000000000000000A"),
    )
    monkeypatch.setattr(cd, "_resolve_coord_short", lambda *_a: "01ABCDEF")
    monkeypatch.setattr(
        coord_mod.CoordinationWorkspace,
        "worktree_path",
        staticmethod(lambda *_a: tmp_path),
    )
    monkeypatch.setattr(cd, "_coord_worktree_foreign_repo_finding", lambda *_a: None)
    monkeypatch.setattr(cd, "_coord_worktree_head_finding", lambda *_a: None)
    monkeypatch.setattr(cd, "_coord_worktree_dirty_finding", lambda *_a: None)

    def _fake_run(cmd: list[str], **k: Any) -> subprocess.CompletedProcess[str]:
        result = subprocess.CompletedProcess(
            cmd, 128, stdout="", stderr="fatal: Not possible to fast-forward, aborting.",
        )
        if k.get("check"):
            raise subprocess.CalledProcessError(
                128, cmd, output=result.stdout, stderr=result.stderr,
            )
        return result

    monkeypatch.setattr(subprocess, "run", _fake_run)

    finding = cd._fix_one_mission_coord_staleness(tmp_path, {})

    assert finding is not None
    assert finding.error_code == cd._COORD_STALE_FIX_BLOCKED_CODE
    assert "fatal: Not possible to fast-forward" in finding.message
    assert "Fast-forwarded" not in capsys.readouterr().out


@pytest.mark.git_repo
@pytest.mark.non_sandbox
def test_e_merge_failure_for_one_mission_does_not_block_another(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    """#4950 follow-up (renata-LOW-shaped): a failed ``--ff-only`` for one
    mission must not raise or abort fixing an unrelated, healthy mission in
    the same ``--fix`` run.
    """
    repo = tmp_path / "repo"
    _init_repo(repo)

    # Mission A: a real strict-ancestor candidate whose merge we force to fail.
    fail_slug = "merge-fail-mission"
    fail_branch = "coord-fail"
    _git(repo, "branch", fail_branch)
    (repo / "advance-a.txt").write_text("a\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "advance target for A")
    fail_dir = repo / "kitty-specs" / fail_slug
    fail_dir.mkdir(parents=True)
    (fail_dir / "meta.json").write_text(
        json.dumps({
            "mission_slug": fail_slug,
            "mission_id": "01ABCDEF0000000000000FAIL",
            "coordination_branch": fail_branch,
            "target_branch": _TARGET_BRANCH,
        }),
        encoding="utf-8",
    )
    fail_worktree = tmp_path / "fail-wt"
    _git(repo, "worktree", "add", str(fail_worktree), fail_branch)

    # Mission B: a real, healthy strict-ancestor candidate that must still
    # be fast-forwarded despite mission A's merge failure.
    ok_slug = "merge-ok-mission"
    ok_branch = "coord-ok"
    _git(repo, "branch", ok_branch)
    ok_dir = repo / "kitty-specs" / ok_slug
    ok_dir.mkdir(parents=True)
    (ok_dir / "meta.json").write_text(
        json.dumps({
            "mission_slug": ok_slug,
            "mission_id": "01ABCDEF00000000000000OK01",
            "coordination_branch": ok_branch,
            "target_branch": _TARGET_BRANCH,
        }),
        encoding="utf-8",
    )
    ok_worktree = tmp_path / "ok-wt"
    _git(repo, "worktree", "add", str(ok_worktree), ok_branch)

    _patch_worktree_path_by_slug(
        monkeypatch,
        {fail_slug: fail_worktree, ok_slug: ok_worktree},
        fallback=tmp_path / "no-such-worktree",
    )

    real_run = subprocess.run

    def _selective_merge_failure(
        cmd: list[str], **k: Any
    ) -> subprocess.CompletedProcess[str]:
        if "merge" in cmd and str(fail_worktree) in cmd:
            result = subprocess.CompletedProcess(
                cmd, 128, stdout="", stderr="fatal: forced failure for A",
            )
            if k.get("check"):
                raise subprocess.CalledProcessError(
                    128, cmd, output=result.stdout, stderr=result.stderr,
                )
            return result
        return real_run(cmd, **k)

    monkeypatch.setattr(subprocess, "run", _selective_merge_failure)
    monkeypatch.setattr(cd, "locate_project_root", lambda: repo)
    monkeypatch.setattr(cd, "_check_git_version", lambda: [])
    monkeypatch.setattr(cd, "_check_tracked_worktrees_content", lambda _r: [])

    target_sha = _git(repo, "rev-parse", _TARGET_BRANCH).stdout.strip()

    with pytest.raises(typer.Exit) as exc:
        cd.run_coordination_health(json_output=True, fix=True)

    out = capsys.readouterr().out
    assert exc.value.exit_code == 1
    assert cd._COORD_STALE_FIX_BLOCKED_CODE in out
    assert "fatal: forced failure for A" in out

    # Mission A's merge genuinely failed -- nothing mutated there.
    assert _git(fail_worktree, "rev-parse", "HEAD").stdout.strip() != target_sha
    # Mission B was NOT blocked by A's failure -- it really fast-forwarded.
    assert _git(ok_worktree, "rev-parse", "HEAD").stdout.strip() == target_sha
    assert _git(repo, "rev-parse", ok_branch).stdout.strip() == target_sha


def test_coord_worktree_foreign_repo_finding_resolves_relative_common_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """#4950 fold: ``--path-format=absolute`` needs git >= 2.31, newer than
    this module's declared ``_MIN_GIT_VERSION`` (2, 25). On an older git the
    flag is echoed back unrecognised and ``--git-common-dir`` comes back
    RELATIVE (e.g. ``.git``) in the main checkout, while the worktree side
    still reports an absolute common dir -- a raw string compare would then
    refuse every legitimate coordination worktree. Monkeypatch
    ``_git_rev_parse_query`` to reproduce exactly that shape (relative from
    the main repo, absolute from the worktree, resolving to the SAME
    directory) and assert the finding does NOT refuse.
    """
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    worktree = tmp_path / "elsewhere" / "coord-wt"
    worktree.mkdir(parents=True)
    common_dir_abs = (repo_root / ".git").resolve()

    def fake_rev_parse(cwd: Path, *args: str) -> str:
        if "--show-toplevel" in args:
            return str(worktree)
        assert "--git-common-dir" in args
        if cwd == repo_root:
            return ".git"  # relative, as an old git reports in the main checkout
        return str(common_dir_abs)  # absolute, as git reports for a linked worktree

    monkeypatch.setattr(cd, "_git_rev_parse_query", fake_rev_parse)

    finding = cd._coord_worktree_foreign_repo_finding(repo_root, worktree, "coord")

    assert finding is None


@pytest.mark.git_repo
@pytest.mark.non_sandbox
def test_a_foreign_clone_fix_fails_closed_without_mutation(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    """#4950 second-opinion follow-up: a foreign clone must be refused pre-mutation.

    The recorded coordination worktree is a SEPARATE ``git clone`` of the
    repo (not a linked worktree) with the coord branch checked out and the
    target branch's commit present. Branch-NAME equality alone
    (``_coord_worktree_head_finding``) passes -- the clone really is on a
    branch called "coord" -- so before this fold, the fast-forward ran and
    genuinely succeeded *inside the clone* while the declared branch in
    ``repo_root`` never moved (a real repro of the postcondition-failure
    code path -- see the git-common-dir/toplevel check this test now
    exercises). ``_coord_worktree_foreign_repo_finding`` catches the
    identity mismatch BEFORE any mutation: the clone's local branch must
    stay put too, not just ``repo_root``'s declared ref.
    """
    repo = tmp_path / "repo"
    mission_slug = "foreign-clone-mission"
    _make_strict_ancestor_repo(repo, mission_slug)

    clone = tmp_path / "foreign-clone"
    subprocess.run(
        ["git", "clone", "--quiet", str(repo), str(clone)],
        check=True, capture_output=True, text=True,
    )
    _git(clone, "checkout", "-q", _COORD_BRANCH)
    _git(clone, "config", "user.email", "test@test.com")
    _git(clone, "config", "user.name", "Test")
    _git(clone, "config", "commit.gpgsign", "false")
    _patch_worktree_path(monkeypatch, clone)

    monkeypatch.setattr(cd, "locate_project_root", lambda: repo)
    monkeypatch.setattr(cd, "_check_git_version", lambda: [])
    monkeypatch.setattr(cd, "_check_tracked_worktrees_content", lambda _r: [])

    coord_sha_before = _git(repo, "rev-parse", _COORD_BRANCH).stdout.strip()
    clone_head_before = _git(clone, "rev-parse", "HEAD").stdout.strip()
    target_sha = _git(repo, "rev-parse", _TARGET_BRANCH).stdout.strip()
    assert coord_sha_before != target_sha, "fixture precondition: coord must start behind target"
    assert clone_head_before == coord_sha_before

    with pytest.raises(typer.Exit) as exc:
        cd.run_coordination_health(json_output=True, fix=True)

    out = capsys.readouterr().out
    assert exc.value.exit_code == 1
    assert cd._COORD_STALE_FIX_BLOCKED_CODE in out
    assert "does not belong to this repository" in out
    assert "Fast-forwarded" not in out
    # Nothing mutated -- neither the declared ref in repo_root NOR the clone.
    assert _git(repo, "rev-parse", _COORD_BRANCH).stdout.strip() == coord_sha_before
    assert _git(clone, "rev-parse", "HEAD").stdout.strip() == clone_head_before


@pytest.mark.git_repo
@pytest.mark.non_sandbox
def test_e_wrong_branch_mismatch_for_one_mission_does_not_block_another(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    """Pin: one mission's wrong-branch coord worktree must not block fixing
    an unrelated, healthy mission in the same ``--fix`` run.

    Distinct from ``test_e_one_diverged_mission_does_not_block_fix_for_other_missions``
    (a DIVERGED coord branch) and
    ``test_e_merge_failure_for_one_mission_does_not_block_another`` (a failed
    merge): here mission A's coord branch is itself a perfectly good
    fast-forward candidate -- the problem is that its recorded WORKTREE has
    the wrong branch checked out (#4920/#4950's original bug shape).
    """
    repo = tmp_path / "repo"
    _init_repo(repo)

    # Mission A: coord branch is a strict-ancestor fast-forward candidate,
    # but the recorded worktree has a DIFFERENT branch checked out.
    mismatch_slug = "mismatch-mission"
    mismatch_branch = "coord-mismatch"
    wrong_branch = "wrong-branch-for-mismatch"
    _git(repo, "branch", mismatch_branch)
    _git(repo, "branch", wrong_branch, mismatch_branch)
    (repo / "advance-a.txt").write_text("a\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "advance target for A")
    mismatch_dir = repo / "kitty-specs" / mismatch_slug
    mismatch_dir.mkdir(parents=True)
    (mismatch_dir / "meta.json").write_text(
        json.dumps({
            "mission_slug": mismatch_slug,
            "mission_id": "01ABCDEF0000000000MISMTCH",
            "coordination_branch": mismatch_branch,
            "target_branch": _TARGET_BRANCH,
        }),
        encoding="utf-8",
    )
    mismatch_worktree = tmp_path / "mismatch-wt"
    _git(repo, "worktree", "add", str(mismatch_worktree), wrong_branch)

    # Mission B: a real, healthy strict-ancestor candidate that must still
    # be fast-forwarded despite mission A's refusal.
    ok_slug = "healthy-mission"
    ok_branch = "coord-healthy"
    _git(repo, "branch", ok_branch)
    ok_dir = repo / "kitty-specs" / ok_slug
    ok_dir.mkdir(parents=True)
    (ok_dir / "meta.json").write_text(
        json.dumps({
            "mission_slug": ok_slug,
            "mission_id": "01ABCDEF000000000000HLTHY",
            "coordination_branch": ok_branch,
            "target_branch": _TARGET_BRANCH,
        }),
        encoding="utf-8",
    )
    ok_worktree = tmp_path / "healthy-wt"
    _git(repo, "worktree", "add", str(ok_worktree), ok_branch)

    _patch_worktree_path_by_slug(
        monkeypatch,
        {mismatch_slug: mismatch_worktree, ok_slug: ok_worktree},
        fallback=tmp_path / "no-such-worktree",
    )
    monkeypatch.setattr(cd, "locate_project_root", lambda: repo)
    monkeypatch.setattr(cd, "_check_git_version", lambda: [])
    monkeypatch.setattr(cd, "_check_tracked_worktrees_content", lambda _r: [])

    mismatch_coord_sha_before = _git(repo, "rev-parse", mismatch_branch).stdout.strip()
    mismatch_wt_head_before = _git(mismatch_worktree, "rev-parse", "HEAD").stdout.strip()
    target_sha = _git(repo, "rev-parse", _TARGET_BRANCH).stdout.strip()

    with pytest.raises(typer.Exit) as exc:
        cd.run_coordination_health(json_output=True, fix=True)

    out = capsys.readouterr().out
    assert exc.value.exit_code == 1
    assert cd._COORD_STALE_FIX_BLOCKED_CODE in out
    assert f"is on {wrong_branch!r}, not {mismatch_branch!r}" in out

    # Mission A refused, unmutated.
    assert _git(repo, "rev-parse", mismatch_branch).stdout.strip() == mismatch_coord_sha_before
    assert _git(mismatch_worktree, "rev-parse", "HEAD").stdout.strip() == mismatch_wt_head_before

    # Mission B was NOT blocked by A's refusal -- it really fast-forwarded.
    assert _git(ok_worktree, "rev-parse", "HEAD").stdout.strip() == target_sha
    assert _git(repo, "rev-parse", ok_branch).stdout.strip() == target_sha


def test_check_and_warn_coord_staleness_no_meta_is_silent(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    cd.check_and_warn_coord_staleness(tmp_path, tmp_path)
    assert capsys.readouterr().out == ""


def test_check_and_warn_coord_staleness_prints_finding(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "meta.json").write_text(
        json.dumps({
            "coordination_branch": "coord", "mission_slug": "m",
            "mission_id": "01ABCDEF00000000000000000A", "target_branch": "main",
        }),
        encoding="utf-8",
    )
    sentinel = cd.DoctorFinding(
        severity="warning", message="coord is stale", next_step="run --fix", error_code="E",
    )
    monkeypatch.setattr(cd, "_check_coord_branch_staleness", lambda *a: [sentinel])
    cd.check_and_warn_coord_staleness(tmp_path, tmp_path)
    out = capsys.readouterr().out
    assert "coord is stale" in out
    assert "run --fix" in out


# ===========================================================================
# Real-git contract tests (a)-(d)
# ===========================================================================

_MISSION_ID = "01KY5JS800000000000000STAL"
_COORD_BRANCH = "coord"
_TARGET_BRANCH = "main"


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True, text=True
    )


def _init_repo(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["git", "init", "-qb", _TARGET_BRANCH, str(repo)], check=True, capture_output=True
    )
    _git(repo, "config", "user.email", "test@test.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "README.md").write_text("init\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "init")


def _seed_stale_meta(repo: Path, mission_slug: str) -> Path:
    """Write ``kitty-specs/<slug>/meta.json`` declaring the coord/target branches."""
    feature_dir = repo / "kitty-specs" / mission_slug
    feature_dir.mkdir(parents=True, exist_ok=True)
    (feature_dir / "meta.json").write_text(
        json.dumps({
            "mission_slug": mission_slug,
            "mission_id": _MISSION_ID,
            "coordination_branch": _COORD_BRANCH,
            "target_branch": _TARGET_BRANCH,
        }, sort_keys=True),
        encoding="utf-8",
    )
    return feature_dir


def _make_strict_ancestor_repo(repo: Path, mission_slug: str) -> Path:
    """coord (1 commit) is a STRICT ancestor of main (2 commits)."""
    _init_repo(repo)
    _git(repo, "branch", _COORD_BRANCH)
    (repo / "advance.txt").write_text("advance\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "advance target")
    return _seed_stale_meta(repo, mission_slug)


def _make_diverged_repo(repo: Path, mission_slug: str) -> Path:
    """coord and main each carry a commit the other lacks -- diverged."""
    _init_repo(repo)
    _git(repo, "branch", _COORD_BRANCH)
    _git(repo, "checkout", "-q", _COORD_BRANCH)
    (repo / "coord-only.txt").write_text("coord-only\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "coord-only commit")
    _git(repo, "checkout", "-q", _TARGET_BRANCH)
    (repo / "target-only.txt").write_text("target-only\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "target-only commit")
    return _seed_stale_meta(repo, mission_slug)


def _add_coord_worktree(repo: Path, tmp_path: Path) -> Path:
    worktree = tmp_path / "coord-wt"
    _git(repo, "worktree", "add", str(worktree), _COORD_BRANCH)
    return worktree


def _patch_worktree_path(monkeypatch: pytest.MonkeyPatch, worktree: Path) -> None:
    from specify_cli import coordination as coord_mod

    monkeypatch.setattr(
        coord_mod.CoordinationWorkspace, "worktree_path", staticmethod(lambda *_a: worktree)
    )


@pytest.mark.git_repo
@pytest.mark.non_sandbox
def test_a_strict_ancestor_check_staleness_reports_and_fix_fast_forwards(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """(a) strict-ancestor -> ``--check-staleness`` reports stale + ``--fix`` FFs (clean worktree)."""
    repo = tmp_path / "repo"
    mission_slug = "a-mission"
    _make_strict_ancestor_repo(repo, mission_slug)
    worktree = _add_coord_worktree(repo, tmp_path)
    _patch_worktree_path(monkeypatch, worktree)

    monkeypatch.setattr(cd, "locate_project_root", lambda: repo)
    monkeypatch.setattr(cd, "_check_git_version", lambda: [])
    monkeypatch.setattr(cd, "_check_tracked_worktrees_content", lambda _r: [])

    # --check-staleness reports the stale finding, non-blockingly.
    with pytest.raises(typer.Exit) as exc:
        cd.run_coordination_health(json_output=True, check_staleness=True)
    assert exc.value.exit_code == 0
    assert cd._COORD_STALE_VS_TARGET_CODE in capsys.readouterr().out

    target_sha = _git(repo, "rev-parse", _TARGET_BRANCH).stdout.strip()
    coord_sha_before = _git(repo, "rev-parse", _COORD_BRANCH).stdout.strip()
    assert coord_sha_before != target_sha, "fixture precondition: coord must start behind target"

    # --fix fast-forwards the (clean) coord worktree.
    with pytest.raises(typer.Exit) as exc:
        cd.run_coordination_health(json_output=True, fix=True)
    assert exc.value.exit_code == 0

    assert _git(worktree, "rev-parse", "HEAD").stdout.strip() == target_sha
    assert _git(repo, "rev-parse", _COORD_BRANCH).stdout.strip() == target_sha


@pytest.mark.git_repo
@pytest.mark.non_sandbox
def test_a_wrong_branch_worktree_fix_fails_closed_without_mutation(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """#4920: ``--fix`` must not advance the wrong branch checked out at the coord path."""
    repo = tmp_path / "repo"
    mission_slug = "wrong-branch-mission"
    _make_strict_ancestor_repo(repo, mission_slug)

    wrong_branch = "wrong-branch"
    _git(repo, "branch", wrong_branch, _COORD_BRANCH)
    worktree = tmp_path / "wrong-branch-wt"
    _git(repo, "worktree", "add", str(worktree), wrong_branch)
    _patch_worktree_path(monkeypatch, worktree)

    monkeypatch.setattr(cd, "locate_project_root", lambda: repo)
    monkeypatch.setattr(cd, "_check_git_version", lambda: [])
    monkeypatch.setattr(cd, "_check_tracked_worktrees_content", lambda _r: [])

    coord_sha_before = _git(repo, "rev-parse", _COORD_BRANCH).stdout.strip()
    wrong_sha_before = _git(repo, "rev-parse", wrong_branch).stdout.strip()
    target_sha_before = _git(repo, "rev-parse", _TARGET_BRANCH).stdout.strip()
    worktree_head_before = _git(worktree, "rev-parse", "HEAD").stdout.strip()
    assert coord_sha_before == wrong_sha_before == worktree_head_before
    assert coord_sha_before != target_sha_before

    with pytest.raises(typer.Exit) as exc:
        cd.run_coordination_health(json_output=True, fix=True)

    out = capsys.readouterr().out
    assert _git(repo, "rev-parse", _COORD_BRANCH).stdout.strip() == coord_sha_before
    assert _git(repo, "rev-parse", wrong_branch).stdout.strip() == wrong_sha_before
    assert _git(worktree, "rev-parse", "HEAD").stdout.strip() == worktree_head_before
    assert _git(repo, "rev-parse", _TARGET_BRANCH).stdout.strip() == target_sha_before
    assert exc.value.exit_code == 1
    assert cd._COORD_STALE_FIX_BLOCKED_CODE in out
    # #4950: a dedicated message -- no coord..target diff, no "inspect the
    # diff above" advice, and the actual branch name is named directly.
    assert f"is on {wrong_branch!r}, not 'coord'" in out
    assert "checked out in a mismatched worktree" not in out
    assert "diff --git" not in out
    assert "Fast-forwarded" not in out


@pytest.mark.git_repo
@pytest.mark.non_sandbox
def test_a_detached_worktree_fix_fails_closed_without_mutation(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """#4950: a detached-HEAD coord worktree must refuse ``--fix``, not mutate."""
    repo = tmp_path / "repo"
    mission_slug = "detached-mission"
    _make_strict_ancestor_repo(repo, mission_slug)
    worktree = _add_coord_worktree(repo, tmp_path)
    _patch_worktree_path(monkeypatch, worktree)
    _git(worktree, "checkout", "--detach", "HEAD")

    monkeypatch.setattr(cd, "locate_project_root", lambda: repo)
    monkeypatch.setattr(cd, "_check_git_version", lambda: [])
    monkeypatch.setattr(cd, "_check_tracked_worktrees_content", lambda _r: [])

    coord_sha_before = _git(repo, "rev-parse", _COORD_BRANCH).stdout.strip()
    worktree_head_before = _git(worktree, "rev-parse", "HEAD").stdout.strip()
    target_sha_before = _git(repo, "rev-parse", _TARGET_BRANCH).stdout.strip()

    with pytest.raises(typer.Exit) as exc:
        cd.run_coordination_health(json_output=True, fix=True)

    out = capsys.readouterr().out
    assert _git(repo, "rev-parse", _COORD_BRANCH).stdout.strip() == coord_sha_before
    assert _git(worktree, "rev-parse", "HEAD").stdout.strip() == worktree_head_before
    assert _git(repo, "rev-parse", _TARGET_BRANCH).stdout.strip() == target_sha_before
    assert exc.value.exit_code == 1
    assert cd._COORD_STALE_FIX_BLOCKED_CODE in out
    assert "is on '<detached>', not 'coord'" in out
    assert "checked out in a mismatched worktree" not in out
    assert "diff --git" not in out
    assert "Fast-forwarded" not in out


@pytest.mark.git_repo
@pytest.mark.non_sandbox
def test_a_detached_worktree_head_finding_silences_symbolic_ref_stderr(
    tmp_path: Path, capfd: pytest.CaptureFixture[str],
) -> None:
    """#4950: git's `fatal: ref HEAD is not a symbolic ref` must not leak.

    ``capsys`` cannot see this -- git writes straight to the real stderr
    file descriptor, bypassing Python's ``sys.stderr`` -- so this needs
    ``capfd``, which captures at the OS file-descriptor level.
    """
    repo = tmp_path / "repo"
    _make_strict_ancestor_repo(repo, "detached-stderr-mission")
    worktree = tmp_path / "detached-wt"
    _git(repo, "worktree", "add", "--detach", str(worktree), _COORD_BRANCH)

    capfd.readouterr()  # discard `worktree add`'s own output

    finding = cd._coord_worktree_head_finding(worktree, _COORD_BRANCH)

    assert finding is not None
    assert "fatal:" not in capfd.readouterr().err


@pytest.mark.git_repo
@pytest.mark.non_sandbox
def test_b_diverged_fix_fails_loud_and_mutates_nothing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """(b) diverged -> ``--fix`` fails loud with a diff, mutates nothing."""
    repo = tmp_path / "repo"
    mission_slug = "b-mission"
    _make_diverged_repo(repo, mission_slug)
    worktree = _add_coord_worktree(repo, tmp_path)
    _patch_worktree_path(monkeypatch, worktree)

    monkeypatch.setattr(cd, "locate_project_root", lambda: repo)
    monkeypatch.setattr(cd, "_check_git_version", lambda: [])
    monkeypatch.setattr(cd, "_check_tracked_worktrees_content", lambda _r: [])

    coord_sha_before = _git(repo, "rev-parse", _COORD_BRANCH).stdout.strip()
    worktree_head_before = _git(worktree, "rev-parse", "HEAD").stdout.strip()

    with pytest.raises(typer.Exit) as exc:
        cd.run_coordination_health(json_output=True, fix=True)
    assert exc.value.exit_code == 1

    out = capsys.readouterr().out
    assert "Refusing to fast-forward" in out
    assert "diff --git" in out  # the unified diff was printed

    # (renata) byte-identical before/after — zero mutation.
    assert _git(repo, "rev-parse", _COORD_BRANCH).stdout.strip() == coord_sha_before
    assert _git(worktree, "rev-parse", "HEAD").stdout.strip() == worktree_head_before


@pytest.mark.git_repo
@pytest.mark.non_sandbox
def test_c_dirty_worktree_fix_fails_loud(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """(c) dirty coord worktree -> ``--fix`` fails loud (even though strict-ancestor)."""
    repo = tmp_path / "repo"
    mission_slug = "c-mission"
    _make_strict_ancestor_repo(repo, mission_slug)
    worktree = _add_coord_worktree(repo, tmp_path)
    _patch_worktree_path(monkeypatch, worktree)

    # Dirty the coord worktree (uncommitted change) — the strict-ancestor
    # precondition alone must NOT be enough to fast-forward.
    (worktree / "dirty.txt").write_text("uncommitted\n", encoding="utf-8")

    monkeypatch.setattr(cd, "locate_project_root", lambda: repo)
    monkeypatch.setattr(cd, "_check_git_version", lambda: [])
    monkeypatch.setattr(cd, "_check_tracked_worktrees_content", lambda _r: [])

    coord_sha_before = _git(repo, "rev-parse", _COORD_BRANCH).stdout.strip()

    with pytest.raises(typer.Exit) as exc:
        cd.run_coordination_health(json_output=True, fix=True)
    assert exc.value.exit_code == 1

    out = capsys.readouterr().out
    assert "Refusing to fast-forward" in out

    # Byte-identical before/after — zero mutation — and the dirty file survives.
    assert _git(repo, "rev-parse", _COORD_BRANCH).stdout.strip() == coord_sha_before
    assert (worktree / "dirty.txt").exists()
    assert _porcelain(worktree) != ""


def _porcelain(worktree: Path) -> str:
    return subprocess.run(
        ["git", "-C", str(worktree), "status", "--porcelain"],
        check=True, capture_output=True, text=True,
    ).stdout.strip()


def _build_finalize_fixture(feature_dir: Path) -> None:
    """Primary planning surface: tasks.md + one WP frontmatter file."""
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    (feature_dir / "tasks.md").write_text(
        "# Tasks\n\n## WP01\n\nNo explicit dependencies.\n", encoding="utf-8",
    )
    (tasks_dir / "WP01-test.md").write_text(
        "---\nwork_package_id: WP01\ntitle: Test WP01\nexecution_mode: code_change\n---\n# WP01\n",
        encoding="utf-8",
    )


def _fake_finalize_ports(feature_dir: Path) -> TasksPorts:
    fs = FakeFsReader(
        planning_dirs={MissionArtifactKind.WORK_PACKAGE_TASK: feature_dir},
        default_planning_dir=feature_dir,
    )
    return TasksPorts(
        fs=fs, coord=FakeCoordCommitRouter(), git=FakeGitOps(), render=FakeRender(),
    )


@pytest.mark.git_repo
@pytest.mark.non_sandbox
def test_d_finalize_tasks_surfaces_warn_and_exits_0(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """(d) ``finalize-tasks`` on a stale-coord mission surfaces the WARN AND still succeeds.

    Isolates the WP06 hook (real coord/target branches drive the actual
    staleness detection) from the unrelated phase B/C/D machinery (dependency
    parsing/frontmatter writes/STATUS_STATE bootstrap), which is out of scope
    for this WP and requires a full coordination-topology fixture to exercise
    safely. ``_ft_resolve_context`` — and this WP's one-liner hook right after
    it — run for REAL.
    """
    repo = tmp_path / "repo"
    mission_slug = "d-mission"
    feature_dir = _make_strict_ancestor_repo(repo, mission_slug)
    _build_finalize_fixture(feature_dir)
    ports = _fake_finalize_ports(feature_dir)

    monkeypatch.setattr(tasks_finalize, "_ft_validate", lambda st: None)
    monkeypatch.setattr(tasks_finalize, "_ft_apply_writes", lambda st: None)
    monkeypatch.setattr(tasks_finalize, "_ft_output", lambda st: None)

    with setup_mocked_env(
        repo,
        command_module="specify_cli.cli.commands.agent.tasks",
        mission_slug=mission_slug,
        target_branch=_TARGET_BRANCH,
    ):
        # HUMAN mode (json_output=False): the advisory staleness WARN is a
        # human-facing hint printed via the shared stdout console. It is gated
        # OFF under ``--json`` so the machine-readable payload stays pure JSON
        # (a ``--json`` WARN line broke ``json.loads`` on the finalize stdout --
        # see ``test_coord_loop_tasks::test_finalize_tasks_primary_leg_reads_primary_tasks_md``).
        # FR-008's "surface the WARN" contract lives in human mode; this test
        # exercises exactly that. Must NOT raise -- finalize stays non-blocking.
        tasks_finalize._do_finalize_tasks(
            mission=mission_slug, json_output=False, validate_only=True, ports=ports,
        )

    out = capsys.readouterr().out
    assert "behind target branch" in out


# ===========================================================================
# (e) renata LOW: blast-radius regression -- one mission's unsafe Gap-1
# precondition must not abort ``--fix`` for an UNRELATED mission.
# ===========================================================================


def _patch_worktree_path_by_slug(
    monkeypatch: pytest.MonkeyPatch, mapping: dict[str, Path], fallback: Path,
) -> None:
    """Route ``CoordinationWorkspace.worktree_path`` by ``mission_slug``.

    The single-worktree ``_patch_worktree_path`` helper above is fine for the
    (a)-(d) single-mission fixtures; a two-mission blast-radius fixture needs
    each mission's coord worktree to resolve independently (a shared stub
    would make the never-created mission's worktree wrongly appear to exist).
    """
    from specify_cli import coordination as coord_mod

    def _route(_repo_root: Path, mission_slug: str, _mid8: str) -> Path:
        return mapping.get(mission_slug, fallback)

    monkeypatch.setattr(
        coord_mod.CoordinationWorkspace, "worktree_path", staticmethod(_route)
    )


@pytest.mark.git_repo
@pytest.mark.non_sandbox
def test_e_one_diverged_mission_does_not_block_fix_for_other_missions(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    """(e, renata LOW) one mission's diverged Gap-1 state must not abort ``--fix``
    for an UNRELATED mission's flatten-cleanup in the same run.

    Regression for the blast-radius bug: ``_apply_coord_staleness_fixes`` used
    to raise (via the removed ``_fail_loud_coord_staleness``) the instant ANY
    mission's coord branch was diverged, aborting the whole ``--fix`` command
    before an unrelated, already-safe ``COORDINATION_WORKTREE_NEVER_CREATED``
    flatten fix for a DIFFERENT mission ever ran. It must now surface a
    blocked-fix ``error`` finding for the diverged mission and still apply the
    other mission's fix.
    """
    repo = tmp_path / "repo"
    diverged_slug = "diverged-mission"
    _make_diverged_repo(repo, diverged_slug)
    diverged_worktree = _add_coord_worktree(repo, tmp_path)

    # An UNRELATED mission whose coordination_branch was never created --
    # exactly the flatten-cleanup case a bare `--fix` is meant to repair.
    flat_slug = "flatten-mission"
    flat_dir = repo / "kitty-specs" / flat_slug
    flat_dir.mkdir(parents=True)
    (flat_dir / "meta.json").write_text(
        json.dumps({
            "mission_slug": flat_slug,
            "mission_id": "01ABCDEF00000000000000FLAT",
            "coordination_branch": "kitty/mission-flatten-mission-neverexisted",
        }),
        encoding="utf-8",
    )

    _patch_worktree_path_by_slug(
        monkeypatch,
        {diverged_slug: diverged_worktree},
        fallback=tmp_path / "no-such-worktree",
    )

    monkeypatch.setattr(cd, "locate_project_root", lambda: repo)
    monkeypatch.setattr(cd, "_check_git_version", lambda: [])
    monkeypatch.setattr(cd, "_check_tracked_worktrees_content", lambda _r: [])

    with pytest.raises(typer.Exit) as exc:
        cd.run_coordination_health(json_output=True, fix=True)
    # The diverged mission IS a real, surfaced error -- overall exit stays 1.
    assert exc.value.exit_code == 1

    out = capsys.readouterr().out
    assert cd._COORD_STALE_FIX_BLOCKED_CODE in out

    # The unrelated mission's flatten fix must have applied regardless.
    flattened_meta = json.loads((flat_dir / "meta.json").read_text())
    assert "coordination_branch" not in flattened_meta, (
        "an unrelated mission's diverged Gap-1 state must not block the "
        "flatten-cleanup fix for a different mission in the same --fix run"
    )
