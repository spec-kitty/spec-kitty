"""The landed proof against a named remote (#7214).

A fork clone keeps two remotes: ``origin`` is the fork, and the canonical
repository is ``upstream`` — exactly the shape the landing runbook prescribes
(``docs/development/how-to/pr-landing.md`` steps 2-3 fetch the PR and ``main``
from ``upstream``). Before #7214 the proof read ``refs/remotes/origin/<primary>``
unconditionally, so every landing worktree in such a clone was ``not_landed``
forever and ``--prune`` removed nothing.

Each case is real git with two bare remotes; the process probe is an empty fake
``/proc`` so nothing looks busy.
"""

from __future__ import annotations

import os
import subprocess
from collections.abc import Sequence
from pathlib import Path

import pytest

from kernel.git import run_git
from specify_cli.workspace import landed_worktrees
from specify_cli.workspace.landed_worktrees import (
    Reason,
    Verdict,
    WorktreeAssessment,
    assess_worktrees,
    prune_landed,
)
from specify_cli.workspace.process_probe import ProcessProbeResult, processes_with_cwd_under

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_OLD_DATE = "2001-02-03T04:05:06+00:00"


def _git(cwd: Path, *args: str, env: dict[str, str] | None = None) -> str:
    result = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True, check=False, env=env)
    if result.returncode != 0:
        raise AssertionError(f"git {' '.join(args)} failed in {cwd}: {result.stderr.strip() or result.stdout.strip()}")
    return result.stdout


def _rev(cwd: Path, rev: str) -> str:
    return _git(cwd, "rev-parse", rev).strip()


def _commit(cwd: Path, name: str, content: str) -> str:
    (cwd / name).write_text(content, encoding="utf-8")
    _git(cwd, "add", "-A")
    _git(cwd, "commit", "-q", "-m", f"add {name}")
    return _rev(cwd, "HEAD")


def _init(path: Path, *, trunk: str = "main") -> Path:
    path.mkdir()
    _git(path, "init", "-q", "-b", trunk)
    _git(path, "config", "user.email", "t@example.invalid")
    _git(path, "config", "user.name", "T")
    _git(path, "config", "commit.gpgsign", "false")
    (path / ".gitignore").write_text(".venv/\n", encoding="utf-8")
    _commit(path, "src.py", "x = 1\n")
    return path


def _land_on(worktree: Path, root: Path, remote: str, primary: str, branch: str) -> str:
    """Commit in *worktree*, then land it on ``<remote>/<primary>`` only (rebase-shaped: new SHA)."""
    tip = _commit(worktree, f"{branch}.txt", f"{branch}\n")
    _git(root, "cherry-pick", tip, env={**os.environ, "GIT_COMMITTER_DATE": _OLD_DATE})
    _git(root, "push", "-q", remote, primary)
    _git(root, "fetch", "-q", remote)
    landed = _rev(root, f"refs/remotes/{remote}/{primary}")
    assert landed != tip, "the rebase fixture must rewrite the SHA (non-vacuity)"
    return tip


@pytest.fixture
def fork_clone(tmp_path: Path) -> dict[str, object]:
    """A fork clone: the landing commit is on ``upstream/main``, ``origin/main`` is behind."""
    upstream = tmp_path / "upstream.git"
    origin = tmp_path / "origin.git"
    _git(tmp_path, "init", "-q", "--bare", "-b", "main", str(upstream))
    _git(tmp_path, "init", "-q", "--bare", "-b", "main", str(origin))
    root = _init(tmp_path / "repo")
    _git(root, "remote", "add", "origin", str(origin))
    _git(root, "remote", "add", "upstream", str(upstream))
    _git(root, "push", "-q", "-u", "origin", "main")
    _git(root, "push", "-q", "upstream", "main")

    worktree = tmp_path / "wt-land-7214"
    _git(root, "worktree", "add", "-q", "-b", "land-7214", str(worktree), "main")
    tip = _land_on(worktree, root, "upstream", "main", "land-7214")

    # The fork's own main never moves: that is the bug's precondition.
    assert _rev(root, "refs/remotes/origin/main") != _rev(root, "refs/remotes/upstream/main")
    assert subprocess.run(["git", "merge-base", "--is-ancestor", tip, "refs/remotes/origin/main"], cwd=root, check=False).returncode != 0, (
        "the landed tip must NOT be on origin/main (non-vacuity)"
    )
    return {"root": root, "worktree": worktree, "tip": tip, "upstream": upstream, "origin": origin}


def _probe(tmp_path: Path) -> landed_worktrees.ProbeFn:
    empty = tmp_path / "proc-empty"
    empty.mkdir(exist_ok=True)

    def probe(paths: Sequence[Path]) -> ProcessProbeResult:
        return processes_with_cwd_under(paths, proc_root=empty)

    return probe


def _verdict_of(assessment: WorktreeAssessment, worktree: Path):
    matches = [verdict for verdict in assessment.verdicts if verdict.path.resolve() == worktree.resolve()]
    assert len(matches) == 1, assessment
    return matches[0]


def _has_branch(root: Path, branch: str) -> bool:
    probe = subprocess.run(["git", "rev-parse", "--verify", "--quiet", f"refs/heads/{branch}"], cwd=root, capture_output=True, check=False)
    return probe.returncode == 0


def test_a_landing_on_the_named_remote_is_landed(fork_clone: dict[str, object], tmp_path: Path) -> None:
    """The issue: the commit is on upstream/main, so --remote upstream must call it landed."""
    root, worktree = fork_clone["root"], fork_clone["worktree"]
    assert isinstance(root, Path) and isinstance(worktree, Path)

    assessment = assess_worktrees(root, current_dir=root, probe=_probe(tmp_path), remote="upstream")
    verdict = _verdict_of(assessment, worktree)

    assert assessment.error is None
    assert assessment.remote == "upstream"
    assert assessment.primary_ref == "refs/remotes/upstream/main"
    assert (verdict.verdict, verdict.reason) == (Verdict.LANDED, Reason.LANDED)


def test_the_default_remote_is_still_origin(fork_clone: dict[str, object], tmp_path: Path) -> None:
    """No option: the same fixture stays not_landed against origin/main, exactly as before."""
    root, worktree = fork_clone["root"], fork_clone["worktree"]
    assert isinstance(root, Path) and isinstance(worktree, Path)

    assessment = assess_worktrees(root, current_dir=root, probe=_probe(tmp_path))
    verdict = _verdict_of(assessment, worktree)

    assert assessment.remote == "origin"
    assert assessment.primary_ref == "refs/remotes/origin/main"
    assert (verdict.verdict, verdict.reason) == (Verdict.NOT_LANDED, Reason.CONTENT_NOT_ON_PRIMARY)


def test_prune_removes_the_worktree_landed_on_the_named_remote(fork_clone: dict[str, object], tmp_path: Path) -> None:
    """--prune --remote upstream removes it, deletes the branch, and keeps its tip recreatable."""
    root, worktree = fork_clone["root"], fork_clone["worktree"]
    assert isinstance(root, Path) and isinstance(worktree, Path)

    still_there = prune_landed(root, current_dir=root, probe=_probe(tmp_path))
    assert still_there == [] and worktree.exists(), "origin/main does not hold the work: nothing is pruned"

    outcomes = prune_landed(root, current_dir=root, probe=_probe(tmp_path), remote="upstream")

    assert [(outcome.path.resolve(), outcome.removed, outcome.branch_deleted) for outcome in outcomes] == [(worktree.resolve(), True, True)]
    assert not worktree.exists()
    assert not _has_branch(root, "land-7214")
    assert outcomes[0].recreate == f"git branch land-7214 {fork_clone['tip']}"


def test_pruning_on_another_remote_than_the_report_fails_closed(fork_clone: dict[str, object], tmp_path: Path) -> None:
    """A prune told a different remote than the assessment keeps the worktree, with the fresh reason."""
    root, worktree = fork_clone["root"], fork_clone["worktree"]
    assert isinstance(root, Path) and isinstance(worktree, Path)

    assessment = assess_worktrees(root, current_dir=root, probe=_probe(tmp_path), remote="upstream")
    assert _verdict_of(assessment, worktree).verdict is Verdict.LANDED

    outcomes = prune_landed(root, current_dir=root, probe=_probe(tmp_path), assessment=assessment, remote="origin")

    assert [(outcome.removed, outcome.refusal) for outcome in outcomes] == [(False, Reason.CONTENT_NOT_ON_PRIMARY.value)]
    assert worktree.exists() and _has_branch(root, "land-7214")


def test_a_worktree_landed_on_neither_remote_is_kept(fork_clone: dict[str, object], tmp_path: Path) -> None:
    """Negative control: --remote upstream is not a licence to remove unlanded work."""
    root = fork_clone["root"]
    assert isinstance(root, Path)
    unlanded = root.parent / "wt-unlanded"
    _git(root, "worktree", "add", "-q", "-b", "unlanded", str(unlanded), "main")
    _commit(unlanded, "unlanded.txt", "not landed\n")

    outcomes = prune_landed(root, current_dir=root, probe=_probe(tmp_path), remote="upstream")

    assert unlanded.exists()
    assert [outcome.path.name for outcome in outcomes] == ["wt-land-7214"]


def test_an_unconfigured_remote_is_an_error_not_a_report(fork_clone: dict[str, object], tmp_path: Path) -> None:
    """A typo must not read as "nothing landed": one error naming the configured remotes, no verdicts."""
    root = fork_clone["root"]
    assert isinstance(root, Path)

    assessment = assess_worktrees(root, current_dir=root, probe=_probe(tmp_path), remote="upstrem")

    assert assessment.verdicts == ()
    assert assessment.primary_ref is None
    assert assessment.error is not None
    assert "no such remote 'upstrem'" in assessment.error
    assert "origin" in assessment.error and "upstream" in assessment.error
    assert prune_landed(root, current_dir=root, probe=_probe(tmp_path), remote="upstrem") == []


def test_a_blank_remote_is_refused_not_defaulted(fork_clone: dict[str, object], tmp_path: Path) -> None:
    """`--remote "$UNSET"` must not quietly prove against origin: the default is for an omitted option."""
    root = fork_clone["root"]
    assert isinstance(root, Path)

    assessment = assess_worktrees(root, current_dir=root, probe=_probe(tmp_path), remote="")

    assert assessment.verdicts == ()
    assert assessment.error == "a remote name is required; got ''"
    assert prune_landed(root, current_dir=root, probe=_probe(tmp_path), remote="  ") == []


def test_a_configured_but_unfetched_remote_names_the_missing_ref(fork_clone: dict[str, object], tmp_path: Path) -> None:
    """PRIMARY_REF_MISSING must name the ref and the fetch, for the remote the operator actually named."""
    root, worktree = fork_clone["root"], fork_clone["worktree"]
    assert isinstance(root, Path) and isinstance(worktree, Path)
    _git(root, "update-ref", "-d", "refs/remotes/upstream/main")

    verdict = _verdict_of(assess_worktrees(root, current_dir=root, probe=_probe(tmp_path), remote="upstream"), worktree)

    assert (verdict.verdict, verdict.reason) == (Verdict.UNPROVEN, Reason.PRIMARY_REF_MISSING)
    assert "refs/remotes/upstream/main" in verdict.detail
    assert "git fetch upstream" in verdict.detail


def test_the_primary_comes_from_the_named_remotes_head(tmp_path: Path) -> None:
    """A canonical trunk that is not `main`/`master`/`develop` resolves from <remote>/HEAD, not origin's."""
    upstream = tmp_path / "upstream.git"
    origin = tmp_path / "origin.git"
    _git(tmp_path, "init", "-q", "--bare", "-b", "trunk", str(upstream))
    _git(tmp_path, "init", "-q", "--bare", "-b", "main", str(origin))
    root = _init(tmp_path / "repo")
    _git(root, "remote", "add", "origin", str(origin))
    _git(root, "remote", "add", "upstream", str(upstream))
    _git(root, "push", "-q", "-u", "origin", "main")
    _git(root, "push", "-q", "upstream", "main:trunk")
    _git(root, "fetch", "-q", "upstream")
    _git(root, "remote", "set-head", "upstream", "trunk")

    worktree = tmp_path / "wt-land-trunk"
    _git(root, "worktree", "add", "-q", "-b", "land-trunk", str(worktree), "main")
    _commit(worktree, "trunk.txt", "trunk\n")
    _git(root, "cherry-pick", _rev(worktree, "HEAD"), env={**os.environ, "GIT_COMMITTER_DATE": _OLD_DATE})
    _git(root, "push", "-q", "upstream", "main:trunk")
    _git(root, "fetch", "-q", "upstream")

    assessment = assess_worktrees(root, current_dir=root, probe=_probe(tmp_path), remote="upstream")

    assert assessment.primary_ref == "refs/remotes/upstream/trunk"
    assert _verdict_of(assessment, worktree).verdict is Verdict.LANDED
    # Positive control: the default remote resolves its own trunk (origin/HEAD is unset,
    # so `main` is a common-name guess) and does NOT prove the trunk landing.
    default = assess_worktrees(root, current_dir=root, probe=_probe(tmp_path))
    assert default.primary_ref == "refs/remotes/origin/main"
    assert _verdict_of(default, worktree).verdict is Verdict.NOT_LANDED


def test_a_tip_on_another_remote_does_not_prove_a_landing(tmp_path: Path) -> None:
    """The proof is one named remote's primary ref, never "any remote-tracking ref" (NFR-003)."""
    upstream = tmp_path / "upstream.git"
    other = tmp_path / "other.git"
    _git(tmp_path, "init", "-q", "--bare", "-b", "main", str(upstream))
    _git(tmp_path, "init", "-q", "--bare", "-b", "main", str(other))
    root = _init(tmp_path / "repo")
    _git(root, "remote", "add", "upstream", str(upstream))
    _git(root, "remote", "add", "other", str(other))
    _git(root, "push", "-q", "-u", "upstream", "main")
    _git(root, "push", "-q", "other", "main")

    worktree = tmp_path / "wt-land-y"
    _git(root, "worktree", "add", "-q", "-b", "land-y", str(worktree), "main")
    _commit(worktree, "y.txt", "y\n")
    _git(root, "push", "-q", "other", "land-y")
    _git(root, "fetch", "-q", "other")

    verdict = _verdict_of(assess_worktrees(root, current_dir=root, probe=_probe(tmp_path), remote="upstream"), worktree)

    assert _rev(root, "refs/remotes/other/land-y") == _rev(root, "refs/heads/land-y")
    assert (verdict.verdict, verdict.reason) == (Verdict.NOT_LANDED, Reason.CONTENT_NOT_ON_PRIMARY)


def test_no_remote_is_contacted(fork_clone: dict[str, object], tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """NFR-001: --remote selects a ref to read; it never turns into a fetch."""
    root = fork_clone["root"]
    assert isinstance(root, Path)
    argv: list[tuple[str, ...]] = []

    def recording(requested_root: Path, *args: object, **kwargs: object):
        argv.append(tuple(str(arg) for arg in args))
        return real(requested_root, *args, **kwargs)  # type: ignore[arg-type]

    real = run_git
    monkeypatch.setattr(landed_worktrees, "run_git", recording)

    assess_worktrees(root, current_dir=root, probe=_probe(tmp_path), remote="upstream")
    prune_landed(root, current_dir=root, probe=_probe(tmp_path), remote="upstream")

    assert argv, "the probe must observe git traffic (non-vacuity)"
    network_subcommands = {"fetch", "pull", "ls-remote"}
    assert not [args for args in argv if args[0] in network_subcommands]
    # `git remote` alone lists configured names locally; update/prune go to the network.
    assert not [args for args in argv if args[:2] in {("remote", "update"), ("remote", "prune")}]
