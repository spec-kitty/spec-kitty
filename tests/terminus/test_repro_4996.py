"""Repro #4996 — the forward ref advance is NOT compare-and-swap (fails to fail closed).

Smoking gun (DEBRIEF §2, root R1): ``restore_branch_ref`` (rollback) IS
compare-and-swap — 3-arg ``git update-ref ref new old`` — while
``advance_branch_ref`` (the forward merge advance) is NOT — 2-arg
``git update-ref ref new`` (``git/ref_advance.py`` ~line 410). Same file, opposite
discipline. When the target/coord ref changed since it was read, the forward
advance must FAIL CLOSED; today it cannot. The contract (§"CAS advance contract")
mandates ``advance(ref, new_sha, expected_old_sha)`` performing
``git update-ref ref new_sha expected_old_sha`` — fixed by S-A (WP06).

RED-first: exercises the REAL ``advance_branch_ref`` on a REAL git repo — no
mocking of ``_run_git``/subprocess. Today the function has no ``expected_old_sha``
parameter at all (non-CAS), so the CAS contract cannot even be expressed → the
signature assertion fails → ``xfail(strict=True)``. Post-fix the parameter exists
and the behavioral half proves the advance fails closed on a stale expected-old
and never clobbers a concurrently-moved ref.
"""

from __future__ import annotations

import contextlib
import inspect
import subprocess
from pathlib import Path

import pytest

from specify_cli.git.ref_advance import advance_branch_ref
from tests.terminus.conftest import git_rev

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True)


def test_4996_forward_advance_is_compare_and_swap(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-qb", "main", str(repo)], check=True)
    _git(repo, "config", "user.email", "t@t.com")
    _git(repo, "config", "user.name", "T")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "a.txt").write_text("0\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "c0")
    _git(repo, "branch", "feature")
    stale_old = git_rev(repo, "feature")  # value a caller reads for its CAS expectation

    # A CONCURRENT writer advances `feature` after our read (ref changed since read).
    _git(repo, "checkout", "-q", "feature")
    (repo / "a.txt").write_text("1\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "concurrent c1")
    concurrent_sha = git_rev(repo, "feature")
    _git(repo, "checkout", "-q", "main")

    # Our own forward-advance target, a descendant of the STALE-read value.
    _git(repo, "checkout", "-q", "-b", "ours", stale_old)
    (repo / "b.txt").write_text("ours\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "our advance target")
    new_sha = git_rev(repo, "ours")
    _git(repo, "checkout", "-q", "main")

    # CAS contract: the forward advance must ACCEPT and enforce ``expected_old_sha``
    # (3-arg update-ref). Pre-fix it does not — the non-CAS smoking gun.
    params = inspect.signature(advance_branch_ref).parameters
    assert "expected_old_sha" in params, (
        "advance_branch_ref is NOT compare-and-swap — it takes no expected_old_sha "
        "(2-arg update-ref, ref_advance.py ~410); a concurrently-moved ref cannot be "
        "detected and would be clobbered (#4996 / contract §CAS advance)"
    )

    # Behavioral half (reachable only once the CAS param exists): a stale expected-old
    # must fail closed and NEVER clobber the concurrent writer's commit. The kwargs
    # dict keeps this forward-compatible and mypy-clean before/after the param lands.
    cas_kwargs: dict[str, str] = {"expected_old_sha": stale_old}
    with contextlib.suppress(Exception):
        advance_branch_ref(repo, "feature", new_sha, **cas_kwargs)
    assert git_rev(repo, "feature") == concurrent_sha, "CAS advance clobbered a concurrently-moved ref instead of failing closed (#4996)"
