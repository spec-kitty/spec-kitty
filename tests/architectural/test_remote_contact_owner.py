"""Class gate: ``src/kernel/git/`` is the only place that contacts a git remote (FR-013, C-004, SC-005).

Mission ``second-clone-origin-reconciliation-01M48V8W``. A caller that builds a
``fetch`` / ``ls-remote`` / ``pull`` / ``clone`` / ``remote show`` argv has to
re-decide the timeout, the no-prompt environment and what "unreachable" means.
``kernel.git.remote`` owns those decisions; callers ask it by intent.

The rule is the census in ``_remote_contact_census.py`` (the single authority;
this gate does not restate it). It runs over every ``src/**/*.py`` file except
``src/kernel/git/`` and requires **zero** hits. ``push`` is out of scope (FR-015).

**There is no allowlist, and none may be added** (ADR
``2026-09-30-1-allowlist-ratchets-are-priced-debt``): a new hit is fixed by
calling ``kernel.git.remote`` (``remote_heads``, ``fetch_branches``,
``fetch_tags``, ``clone_repository``, ``describe_remote_head``).

Baseline over the planning base: 5 hits in 4 files (``git_source`` x2,
``remote_probes``, ``push_preflight``, ``protection_policy``).

Non-vacuity (standing order 5): a scanned-file floor, a planted violation per
argv form, the ``remote show -n`` negative control, and an owner-bypass
positive control proving the census finds contact inside the owner.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.architectural._remote_contact_census import OWNER_ROOT, Hit, census, classify_argv, iter_py_files, src_files

pytestmark = pytest.mark.architectural

# 1394 files scanned at the planning base (owner included); leave ~10% headroom.
_SCANNED_FILE_FLOOR = 1250

_FIX_HINT = (
    "Call kernel.git.remote (remote_heads / fetch_branches / fetch_tags / clone_repository / describe_remote_head) instead of building a remote-contacting argv"
)


def _plant(tmp_path: Path, body: str) -> list[Hit]:
    planted = tmp_path / "planted.py"
    planted.write_text(body, encoding="utf-8")
    return census([planted])


def _kinds(hits: list[Hit]) -> set[str]:
    return {hit.kind for hit in hits}


def test_no_remote_contact_outside_kernel_git() -> None:
    hits = census(src_files())
    assert not hits, (
        "Remote-contacting git argv outside src/kernel/git/ (there is no allowlist):\n"
        + "\n".join(f"  {hit.rel}:{hit.lineno}: {hit.kind}" for hit in hits)
        + f"\n{_FIX_HINT}"
    )


def test_census_scans_enough_files() -> None:
    scanned = [p for p in src_files() if OWNER_ROOT not in p.resolve().parents]
    assert len(scanned) >= _SCANNED_FILE_FLOOR, f"only {len(scanned)} source files scanned; the gate is vacuous below {_SCANNED_FILE_FLOOR}"


def test_owner_bypass_positive_control_finds_contact_inside_the_owner() -> None:
    owner_hits = census(iter_py_files(OWNER_ROOT), skip_owner=False)
    assert any(hit.rel.endswith("kernel/git/remote.py") for hit in owner_hits), "the census is blind to src/kernel/git/remote.py"
    assert census(iter_py_files(OWNER_ROOT)) == [], "the owner exclusion in census() stopped working"


@pytest.mark.parametrize(
    ("kind", "body"),
    [
        ("fetch", 'def f():\n    return ["git", "fetch", "origin"]\n'),
        ("ls-remote", 'def f():\n    return ["git", "ls-remote", "--heads", "origin"]\n'),
        ("pull", 'def f():\n    return ("git", "pull", "--ff-only")\n'),
        ("clone", 'def f(url, dest):\n    return ["git", "clone", url, dest]\n'),
        ("remote-show", 'def f():\n    return ["git", "remote", "show", "origin"]\n'),
        ("fetch", 'def f(repo):\n    return ["git", "-C", str(repo), "fetch", "--prune"]\n'),
        ("fetch", 'def f(repo):\n    return ["git", "-c", "core.x=1", "-C", repo, "fetch"]\n'),
        ("remote-show", 'def f(repo):\n    return ["git", "-C", str(repo), "remote", "show", "origin"]\n'),
        ("fetch", 'def f():\n    return _run(["fetch", "origin"])\n'),
        ("remote-show", 'def f():\n    return _run(["remote", "show", "origin"])\n'),
        ("fetch", 'def f(root):\n    return _git(root, "fetch", "--tags")\n'),
        ("ls-remote", 'def f(cwd):\n    return run_git(cwd, "ls-remote", "origin")\n'),
        ("fetch", 'def f(deadline, root):\n    return deadline.run(root, "fetch", "origin")\n'),
        ("clone", 'def f(url):\n    return run_git(None, "clone", "--depth", "1", url)\n'),
        ("fetch", 'def f(self, root):\n    return self.callback(root, "fetch", "origin")\n'),
        ("fetch", 'def f(runner, root):\n    return runner.command(root, "fetch")\n'),
        ("remote-update", 'def f():\n    return ["git", "remote", "update"]\n'),
        ("remote-prune", 'def f(cwd):\n    return run_git(cwd, "remote", "prune", "origin")\n'),
        ("remote-set-head", 'def f():\n    return ["git", "remote", "set-head", "origin", "-a"]\n'),
        ("fetch", 'FETCH = "fetch"\n\n\ndef f():\n    return ["git", FETCH, "origin"]\n'),
        ("fetch", 'def f():\n    return ["git", "--no-pager", "fetch", "origin"]\n'),
        ("fetch", 'def f():\n    return ["git", "-P", "fetch", "origin"]\n'),
        ("fetch", 'def f(d):\n    return ["git", "--git-dir", d, "fetch", "origin"]\n'),
        ("ls-remote", 'def f(d, w):\n    return ["git", "--git-dir", d, "--work-tree", w, "--namespace", "ns", "-c", "a=b", "ls-remote", "origin"]\n'),
        ("pull", 'def f():\n    return ["git", "--git-dir=/x/.git", "--no-pager", "pull"]\n'),
    ],
    ids=[
        "fetch",
        "ls-remote",
        "pull-tuple",
        "clone",
        "remote-show",
        "dash-C-fetch",
        "dash-c-dash-C-fetch",
        "dash-C-remote-show",
        "wrapper-list-fetch",
        "wrapper-list-remote-show",
        "wrapper-positional-fetch",
        "run-git-ls-remote",
        "deadline-run-fetch",
        "clone-depth-no-cwd",
        "method-named-callback-with-argv",
        "method-named-command-with-argv",
        "remote-update",
        "remote-prune",
        "remote-set-head-auto",
        "constant-indirection",
        "no-pager-fetch",
        "dash-P-fetch",
        "git-dir-fetch",
        "git-dir-work-tree-namespace-ls-remote",
        "git-dir-equals-no-pager-pull",
    ],
)
def test_planted_contact_is_reported(tmp_path: Path, kind: str, body: str) -> None:
    assert kind in _kinds(_plant(tmp_path, body))


def test_remote_show_dash_n_is_not_contact(tmp_path: Path) -> None:
    assert _plant(tmp_path, 'def f():\n    return ["git", "remote", "show", "-n", "origin"]\n') == []


@pytest.mark.parametrize(
    "source",
    [
        'run(["git", "push", "origin", "main"])',
        'run(["git", "remote", "get-url", "origin"])',
        'run(["git", "remote", "set-head", "origin", "main"])',
        'run(["git", "remote", "set-head", "origin", "-d"])',
        'run(["git", "remote", "rename", "a", "b"])',
        'run(["git", "remote"])',
        'run(["git", "rev-parse", "HEAD"])',
        'run(["git", "config", "--get", "remote.origin.fetch"])',
        'app.command("fetch")(fetch)',
        'sync_app.command("pull")',
        'parser.add_argument("fetch")',
    ],
)
def test_non_contact_code_is_not_flagged(tmp_path: Path, source: str) -> None:
    assert _plant(tmp_path, source + "\n") == []


def test_classify_argv_ignores_unresolved_tokens() -> None:
    assert classify_argv([None, None]) is None
    assert classify_argv([None, "fetch", None]) == "fetch"
