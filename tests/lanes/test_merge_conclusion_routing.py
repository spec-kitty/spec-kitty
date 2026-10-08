"""The routed merge-conclusion sites still produce the same commits (#5443, FR-013).

Every merge, revert and squash conclusion in the consolidation pipeline, the
lane allocator, the coordination repair and the lifecycle rollback now runs
through ``specify_cli.git.merge_conclusion``. These tests drive each site
through its existing entry function, never the owner, and pin what the
repository holds afterwards: subject, parents, tree, signing behaviour and
the caller's failure path. They are green before and after the routing; the
one exception is marked in its docstring (the consolidation amend is now
path-scoped, C-005).
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from kernel.clock import now_utc
from specify_cli.cli.commands.agent.workflow import _revert_coordination_commit
from specify_cli.consolidation.config import MergeStrategy
from specify_cli.coordination.coherence import _revert_recorded_sha
from specify_cli.coordination.types import CommitReceipt
from specify_cli.lanes.branch_naming import code_lane_branch_name
from specify_cli.lanes.consolidation import (
    _complete_merge_after_target_owned_resolution,
    _make_merge_env,
    _merge_branch_into,
    _preserve_target_newer_planning_artifacts,
)
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.lanes.worktree_allocator import DependencyLaneMergeConflictError, _merge_dependency_lane_tips

pytestmark = [pytest.mark.git_repo, pytest.mark.non_sandbox]

TARGET = "work"
SOURCE = "kitty/mission-demo-01M5443A"
CODE = "src/demo.py"
METADATA = ".kittify/metadata.yaml"
MISSION_SLUG = "demo-routing"
SPEC_REL = f"kitty-specs/{MISSION_SLUG}/spec.md"


def _git(cwd: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=False)
    if check and result.returncode != 0:
        raise AssertionError(f"git {args} failed: {result.stderr}")
    return result


def _out(cwd: Path, *args: str) -> str:
    return _git(cwd, *args).stdout.strip()


@pytest.fixture(autouse=True)
def _hermetic_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    for key in list(os.environ):
        if key.startswith(("GIT_", "SPEC_KITTY_")):
            monkeypatch.delenv(key)
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("SPEC_KITTY_NO_UPGRADE_CHECK", "1")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / ".config"))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")


def _write(repo: Path, rel: str, text: str) -> None:
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    _git(repo, "add", "--", rel)


def _commit(repo: Path, files: dict[str, str], message: str) -> str:
    for rel, text in files.items():
        _write(repo, rel, text)
    _git(repo, "commit", "-q", "-m", message)
    return _out(repo, "rev-parse", "HEAD")


def _init(repo: Path, branch: str = TARGET) -> Path:
    repo.mkdir(parents=True)
    _git(repo, "init", "-q", "--template=", "-b", branch)
    for key, value in (("user.email", "t@example.com"), ("user.name", "T"), ("commit.gpgsign", "false")):
        _git(repo, "config", key, value)
    return repo


def _parents(repo: Path, rev: str = "HEAD") -> list[str]:
    return _out(repo, "rev-list", "--parents", "-n", "1", rev).split()[1:]


def _subject(repo: Path, rev: str = "HEAD") -> str:
    return _out(repo, "log", "-1", "--format=%s", rev)


def _staged(repo: Path) -> set[str]:
    return set(_out(repo, "diff", "--cached", "--name-only").splitlines())


def _has_ref(repo: Path, ref: str) -> bool:
    return _git(repo, "rev-parse", "-q", "--verify", ref, check=False).returncode == 0


def _in_tree(repo: Path, rev: str, rel: str) -> bool:
    return _git(repo, "cat-file", "-e", f"{rev}:{rel}", check=False).returncode == 0


def _break_signing(repo: Path) -> None:
    _git(repo, "config", "commit.gpgsign", "true")
    _git(repo, "config", "gpg.program", "/bin/false")


def _two_branch_repo(tmp_path: Path) -> Path:
    """``TARGET`` and a diverged ``SOURCE``; the operator's checkout sits on ``other`` with a stray staged file."""
    repo = _init(tmp_path / "repo")
    _commit(repo, {"README.md": "base\n"}, "base")
    _git(repo, "branch", SOURCE)
    _commit(repo, {"target.txt": "target\n"}, "target work")
    _git(repo, "checkout", "-q", SOURCE)
    _commit(repo, {CODE: "def demo() -> int:\n    return 1\n"}, "mission work")
    _git(repo, "checkout", "-q", "-b", "other", TARGET)
    _write(repo, "stray.txt", "operator work\n")
    return repo


# 1 / 2: _merge_branch_into -----------------------------------------------------


def test_squash_strategy_lands_one_commit_and_leaves_the_operator_index_alone(tmp_path: Path) -> None:
    repo = _two_branch_repo(tmp_path)
    before = _out(repo, "rev-parse", TARGET)

    assert _merge_branch_into(repo, SOURCE, TARGET, strategy=MergeStrategy.SQUASH) is True

    assert _parents(repo, TARGET) == [before]
    assert _subject(repo, TARGET) == f"feat({SOURCE}): squash merge of mission"
    assert _out(repo, "show", f"{TARGET}:{CODE}") == "def demo() -> int:\n    return 1"
    assert _out(repo, "show", f"{TARGET}:target.txt") == "target"
    assert not _in_tree(repo, TARGET, "stray.txt")
    assert _staged(repo) == {"stray.txt"}


def test_squash_strategy_never_signs(tmp_path: Path) -> None:
    repo = _two_branch_repo(tmp_path)
    _break_signing(repo)
    assert _merge_branch_into(repo, SOURCE, TARGET, strategy=MergeStrategy.SQUASH) is True
    assert _subject(repo, TARGET) == f"feat({SOURCE}): squash merge of mission"


def _install_post_checkout_hook(repo: Path) -> None:
    """An operator hook that drops an untracked ``.env.local`` and edits a tracked file in every checkout."""
    hook = Path(_out(repo, "rev-parse", "--path-format=absolute", "--git-common-dir")) / "hooks" / "post-checkout"
    hook.parent.mkdir(parents=True, exist_ok=True)
    hook.write_text("#!/bin/sh\necho 'SECRET=operator' > .env.local\necho 'hook edit' >> README.md\n", encoding="utf-8")
    hook.chmod(0o755)


def test_squash_strategy_survives_a_post_checkout_hook_that_dirties_the_merge_worktree(tmp_path: Path) -> None:
    """A ``post-checkout`` hook writing an untracked file must not block the squash, nor leak into it.

    ``git merge --squash`` plus ``commit -m`` commits only staged content, so
    the FreshWorktree proof checks the index alone (#5443 WP05 fold).
    """
    repo = _two_branch_repo(tmp_path)
    _install_post_checkout_hook(repo)
    before = _out(repo, "rev-parse", TARGET)

    assert _merge_branch_into(repo, SOURCE, TARGET, strategy=MergeStrategy.SQUASH) is True

    assert _parents(repo, TARGET) == [before]
    assert _subject(repo, TARGET) == f"feat({SOURCE}): squash merge of mission"
    assert set(_out(repo, "diff-tree", "--no-commit-id", "--name-only", "-r", TARGET).splitlines()) == {CODE}
    assert not _in_tree(repo, TARGET, ".env.local")
    assert _out(repo, "show", f"{TARGET}:README.md") == "base"


def test_merge_strategy_records_both_parents_and_its_subject(tmp_path: Path) -> None:
    repo = _two_branch_repo(tmp_path)
    before = _out(repo, "rev-parse", TARGET)

    assert _merge_branch_into(repo, SOURCE, TARGET, strategy=MergeStrategy.MERGE) is True

    assert _parents(repo, TARGET) == [before, _out(repo, "rev-parse", SOURCE)]
    assert _subject(repo, TARGET) == f"Merge {SOURCE} into {TARGET}"
    assert not _in_tree(repo, TARGET, "stray.txt")
    assert _staged(repo) == {"stray.txt"}


def test_merge_strategy_honours_signing(tmp_path: Path) -> None:
    """The committing merge never disabled signing: a broken signer still fails it, and nothing lands."""
    repo = _two_branch_repo(tmp_path)
    _break_signing(repo)
    before = _out(repo, "rev-parse", TARGET)

    with pytest.raises(RuntimeError, match=f"Merge of {SOURCE} into {TARGET} failed"):
        _merge_branch_into(repo, SOURCE, TARGET, strategy=MergeStrategy.MERGE)

    assert _out(repo, "rev-parse", TARGET) == before


# 3: _complete_merge_after_target_owned_resolution ------------------------------


def _conflicted(tmp_path: Path, ours: dict[str, str], theirs: dict[str, str]) -> Path:
    repo = _init(tmp_path / "conflicted", "ours")
    _commit(repo, {METADATA: "version: base\n", CODE: "x = 0\n"}, "base")
    _git(repo, "branch", "theirs")
    _commit(repo, ours, "ours")
    _git(repo, "checkout", "-q", "theirs")
    _commit(repo, theirs, "theirs")
    _git(repo, "checkout", "-q", "ours")
    assert _git(repo, "merge", "--no-edit", "-m", "Merge theirs into ours", "theirs", check=False).returncode != 0
    return repo


def test_target_owned_conflict_is_concluded_with_the_merge_message(tmp_path: Path) -> None:
    repo = _conflicted(tmp_path, {METADATA: "version: ours\n"}, {METADATA: "version: theirs\n", CODE: "x = 2\n"})
    _break_signing(repo)
    theirs = _out(repo, "rev-parse", "theirs")

    assert _complete_merge_after_target_owned_resolution(repo, _make_merge_env()) is True

    assert len(_parents(repo)) == 2
    assert _parents(repo)[1] == theirs
    assert _subject(repo) == "Merge theirs into ours"
    assert not _has_ref(repo, "MERGE_HEAD")


def test_genuine_conflict_is_left_in_progress(tmp_path: Path) -> None:
    repo = _conflicted(tmp_path, {METADATA: "version: ours\n", CODE: "x = 1\n"}, {METADATA: "version: theirs\n", CODE: "x = 2\n"})
    head = _out(repo, "rev-parse", "HEAD")

    assert _complete_merge_after_target_owned_resolution(repo, _make_merge_env()) is False

    assert _out(repo, "rev-parse", "HEAD") == head
    assert _has_ref(repo, "MERGE_HEAD")


# 4: _preserve_target_newer_planning_artifacts ----------------------------------


def _squash_worktree_with_stale_spec(tmp_path: Path) -> tuple[Path, Path, str]:
    """A target that refined ``spec.md`` after the fork, and a temp worktree whose squash commit clobbered it."""
    repo = _init(tmp_path / "planning")
    _commit(repo, {SPEC_REL: "# Spec\n\nbase\n"}, "base planning")
    _git(repo, "branch", SOURCE)
    _commit(repo, {SPEC_REL: "# Spec\n\nrefined on the target\n"}, "refine spec on target")
    _git(repo, "checkout", "-q", SOURCE)
    _commit(repo, {CODE: "x = 1\n"}, "mission code")
    _git(repo, "checkout", "-q", TARGET)
    wt = tmp_path / "kitty-merge-wt"
    _git(repo, "worktree", "add", "--detach", str(wt), TARGET)
    squash = _commit(wt, {SPEC_REL: "# Spec\n\nbase\n", CODE: "x = 1\n"}, f"feat({SOURCE}): squash merge of mission")
    return repo, wt, squash


def test_restored_planning_artifact_is_amended_into_the_squash_commit(tmp_path: Path) -> None:
    repo, wt, squash = _squash_worktree_with_stale_spec(tmp_path)
    parent = _parents(wt, squash)

    restored = _preserve_target_newer_planning_artifacts(repo, wt, SOURCE, TARGET, _make_merge_env())

    assert restored == [SPEC_REL]
    assert _out(wt, "rev-parse", "HEAD") != squash, "the squash commit was amended"
    assert _parents(wt) == parent, "amended in place, not a new commit"
    assert _subject(wt) == f"feat({SOURCE}): squash merge of mission"
    assert _out(wt, "show", f"HEAD:{SPEC_REL}") == "# Spec\n\nrefined on the target"
    assert _out(wt, "show", f"HEAD:{CODE}") == "x = 1"


def test_amend_records_only_the_restored_paths(tmp_path: Path) -> None:
    """C-005's recorded exception (``commit --amend --only -- <restored>``): a stray staged file stays out.

    This one is red before the routing: the old pathspec-less ``--amend`` swept
    the stray file into the squash commit.
    """
    repo, wt, _ = _squash_worktree_with_stale_spec(tmp_path)
    _write(wt, "stray.txt", "operator work\n")

    assert _preserve_target_newer_planning_artifacts(repo, wt, SOURCE, TARGET, _make_merge_env()) == [SPEC_REL]

    assert _out(wt, "show", f"HEAD:{SPEC_REL}") == "# Spec\n\nrefined on the target"
    assert not _in_tree(wt, "HEAD", "stray.txt")
    assert _staged(wt) == {"stray.txt"}


# 5: coherence._revert_recorded_sha ---------------------------------------------


def _coord_repo(tmp_path: Path) -> tuple[Path, str]:
    repo = _init(tmp_path / "coord")
    _commit(repo, {"status.events.jsonl": "{}\n"}, "base")
    sha = _commit(repo, {"status.events.jsonl": "{}\n{}\n"}, "status: recorded strand")
    return repo, sha


def test_recorded_strand_commit_is_reverted(tmp_path: Path) -> None:
    repo, sha = _coord_repo(tmp_path)

    assert _revert_recorded_sha(repo, sha, _make_merge_env()) is None

    assert _subject(repo) == 'Revert "status: recorded strand"'
    assert _parents(repo) == [sha]


def test_recorded_strand_revert_refuses_over_a_stray_staged_file(tmp_path: Path) -> None:
    repo, sha = _coord_repo(tmp_path)
    _write(repo, "stray.txt", "operator work\n")

    diagnostic = _revert_recorded_sha(repo, sha, _make_merge_env())

    assert diagnostic
    assert _out(repo, "rev-parse", "HEAD") == sha
    assert _staged(repo) == {"stray.txt"}


def test_recorded_strand_revert_honours_signing(tmp_path: Path) -> None:
    repo, sha = _coord_repo(tmp_path)
    _break_signing(repo)
    assert _revert_recorded_sha(repo, sha, _make_merge_env())
    assert _out(repo, "rev-parse", "HEAD") == sha


# 6: workflow._revert_coordination_commit ----------------------------------------


def _receipt(repo: Path, sha: str) -> CommitReceipt:
    return CommitReceipt(commit_sha=sha, committed_at=now_utc(), destination_ref=TARGET, worktree_root=repo, event_ids=())


def test_lifecycle_rollback_reverts_the_commit_without_signing(tmp_path: Path) -> None:
    repo, sha = _coord_repo(tmp_path)
    _break_signing(repo)

    _revert_coordination_commit(_receipt(repo, sha))

    assert _subject(repo) == 'Revert "status: recorded strand"'
    assert _parents(repo) == [sha]


def test_lifecycle_rollback_failure_raises_and_keeps_the_index(tmp_path: Path) -> None:
    repo, sha = _coord_repo(tmp_path)
    _write(repo, "stray.txt", "operator work\n")

    with pytest.raises(RuntimeError, match="failed to rollback lifecycle coordination commit after lane sync refusal"):
        _revert_coordination_commit(_receipt(repo, sha))

    assert _out(repo, "rev-parse", "HEAD") == sha
    assert _staged(repo) == {"stray.txt"}


# 7: worktree_allocator._merge_dependency_lane_tips -------------------------------


def _lane(lane_id: str, depends_on: tuple[str, ...], group: int) -> ExecutionLane:
    return ExecutionLane(
        lane_id=lane_id, wp_ids=("WP01",), write_scope=("src/**",), predicted_surfaces=("core",), depends_on_lanes=depends_on, parallel_group=group
    )


def _dependency_setup(tmp_path: Path) -> tuple[Path, Path, ExecutionLane, LanesManifest]:
    repo = _init(tmp_path / "lanes", "main")
    _commit(repo, {"seed.txt": "seed\n"}, "seed")
    dep_branch = code_lane_branch_name(MISSION_SLUG, "lane-a")
    _git(repo, "checkout", "-q", "-b", dep_branch)
    _commit(repo, {"src/a.py": "a = 1\n"}, "lane a work")
    _git(repo, "checkout", "-q", "main")
    dependent = repo / ".worktrees" / f"{MISSION_SLUG}-lane-b"
    _git(repo, "worktree", "add", "-q", "-b", code_lane_branch_name(MISSION_SLUG, "lane-b"), str(dependent), "main")
    _commit(dependent, {"src/b.py": "b = 1\n"}, "lane b work")
    lane_a, lane_b = _lane("lane-a", (), 0), _lane("lane-b", ("lane-a",), 1)
    manifest = LanesManifest(
        version=1,
        mission_slug=MISSION_SLUG,
        mission_id="01M5443ROUTING0000000000000",
        mission_branch=f"kitty/mission-{MISSION_SLUG}",
        target_branch="main",
        lanes=[lane_a, lane_b],
        computed_at="2026-10-07T00:00:00Z",
        computed_from="test",
    )
    return repo, dependent, lane_b, manifest


def test_dependency_lane_merge_records_its_subject_and_parents(tmp_path: Path) -> None:
    repo, dependent, lane_b, manifest = _dependency_setup(tmp_path)
    before = _out(dependent, "rev-parse", "HEAD")

    _merge_dependency_lane_tips(repo, dependent, MISSION_SLUG, lane_b, manifest)

    assert _subject(dependent) == "Merge dependency lane lane-a into lane-b"
    assert _parents(dependent) == [before, _out(repo, "rev-parse", code_lane_branch_name(MISSION_SLUG, "lane-a"))]


def test_dependency_lane_merge_honours_signing(tmp_path: Path) -> None:
    """The allocator never disabled signing: a broken signer fails the merge, which rolls back and raises."""
    repo, dependent, lane_b, manifest = _dependency_setup(tmp_path)
    _break_signing(repo)
    before = _out(dependent, "rev-parse", "HEAD")

    with pytest.raises(DependencyLaneMergeConflictError):
        _merge_dependency_lane_tips(repo, dependent, MISSION_SLUG, lane_b, manifest)

    assert _out(dependent, "rev-parse", "HEAD") == before
    assert not _has_ref(dependent, "MERGE_HEAD")
