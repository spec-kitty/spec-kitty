"""Probe-order proof for the protected single_branch mint.

The protected-mint decision core (``decide_protected_mint``) is fed facts the
adapter gathers lazily, in today's probe order, stopping at the first fact that
decides a refusal (so an error is raised exactly where it always was). This module pins that order on a
real repository, without any module patch: ``GIT_TRACE`` (an environment
change) records every git built-in the create runs. The full captured
sequences below document what ran before the decision cores were wired; the
assertions compare only their *mint view* (``_mint_view``): the mint's own
probes, the protection-resolution mark, the scaffold commit and the rollback's
``read-tree``. Probes owned by other subsystems (``safe_commit``, the
``git_ops`` Primary Branch walk, the rollback snapshot) are free to change
without turning these cells red.

Cells: the success cell (mint + scaffold commit), and the three refusal cells
that stop at a deciding probe -- target without a commit, a dirty write
checkout, and an existing mission branch. Each refusal cell also asserts the
later mint probes never ran.

The protection-resolution cells: the idempotent re-create of
a single_branch mission on an unprotected target with ``meta.json`` present
resolves protection once (it used to resolve it twice), and a fresh create
resolves it once, after the scaffold write. A ``git`` shim on ``PATH`` (an
environment change too) records, per git call, whether the scaffold exists.
"""

from __future__ import annotations

import os
import re
import shutil
from pathlib import Path

import pytest

from mission_runtime import MissionTopology
from specify_cli.core.mission_creation import _create_mission_core_failure_atomic, create_mission_core
from specify_cli.lanes.branch_naming import resolve_mid8
from tests.core._mission_create_golden import PRIMARY_BRANCH, build_repo, git

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_BUILTIN = "trace: built-in: git "
_MID8_RE = re.compile(r"(?<=-)[0-9A-Z]{8}(?=[/' ]|$)")
#: A fixed identity for the cells that must name the mission's mid8 up front
#: (an existing mission branch, a prior scaffold). Passed through the private
#: identity input of ``_create_mission_core_failure_atomic``, so the cell never
#: predicts a minted ULID from the clock.
_FIXED_MISSION_ID = "01K6PR0BE0RDERF1XED0000000"
_FIXED_MID8 = resolve_mid8("", mission_id=_FIXED_MISSION_ID)

_TARGET_PROBE = "rev-parse --verify --quiet 'main^{commit}'"
_RELEASE_PROBE = "rev-parse --verify --quiet 'release^{commit}'"
_STATUS_PROBE = "status --porcelain=v1 -z --"
_BRANCH_PROBE_PREFIX = "rev-parse --verify refs/heads/kitty/mission-"
_CHECKOUT_PREFIX = "checkout -b kitty/mission-"

# The rollback snapshot and root resolution that precede the mint's own probes.
_PRELUDE = [
    "rev-parse --is-inside-work-tree",
    "branch --show-current",
    "rev-parse HEAD",
    "write-tree",
    "branch --list 'kitty/mission-*' '--format=%(refname:short)'",
    "rev-parse --is-inside-work-tree",
    "rev-parse --is-inside-work-tree",
    "rev-parse --verify HEAD",
    "branch --show-current",
    "rev-parse --show-toplevel",
]
# Protection resolution (``resolve_primary_branch(bias=False)``) from ``main``.
_PROTECTION_ON_MAIN = [
    "symbolic-ref HEAD",
    "rev-parse --verify --quiet refs/heads/main",
    "symbolic-ref refs/remotes/origin/HEAD",
]
# The failure-atomic rollback that follows every refusal.
_ROLLBACK = [
    "branch --show-current",
    "rev-parse HEAD",
    "read-tree <TREE>",
    "branch --list 'kitty/mission-*' '--format=%(refname:short)'",
]

#: Captured on 633e164ec, before the decision cores were
#: wired; the success cell is cut after the scaffold commit (later hosted
#: fan-out probes depend on the environment, not on the mint).
EXPECTED: dict[str, list[str]] = {
    "success": [
        *_PRELUDE,
        *_PROTECTION_ON_MAIN,
        _TARGET_PROBE,
        _STATUS_PROBE,
        "rev-parse --verify refs/heads/kitty/mission-probe-ok-<MID8>",
        "checkout -b kitty/mission-probe-ok-<MID8> main",
        "config user.email",
        "rev-parse --git-common-dir",
        "branch --show-current",
        "symbolic-ref HEAD",
        "rev-parse --verify --quiet refs/heads/kitty/mission-probe-ok-<MID8>",
        "diff --cached --binary --no-ext-diff --no-renames -- <SCAFFOLD>",
        "diff --name-only -z --no-renames --cached -- <SCAFFOLD>",
        "add --force -- kitty-specs/probe-ok-<MID8>/meta.json",
        "add --force -- kitty-specs/probe-ok-<MID8>/status.events.jsonl",
        "add --force -- kitty-specs/probe-ok-<MID8>/tasks/README.md",
        "add --force -- kitty-specs/probe-ok-<MID8>/tasks/.gitkeep",
        "commit --only -m 'Add scaffold for feature probe-ok-<MID8>' -- <SCAFFOLD>",
    ],
    # Created from ``topic``, so the Primary Branch resolution takes a shorter path.
    "target_without_commit": [
        *_PRELUDE,
        "symbolic-ref HEAD",
        "symbolic-ref refs/remotes/origin/HEAD",
        _RELEASE_PROBE,
        *_ROLLBACK,
    ],
    "dirty": [
        *_PRELUDE,
        *_PROTECTION_ON_MAIN,
        _TARGET_PROBE,
        _STATUS_PROBE,
        *_ROLLBACK,
    ],
    "branch_exists": [
        *_PRELUDE,
        *_PROTECTION_ON_MAIN,
        _TARGET_PROBE,
        _STATUS_PROBE,
        "rev-parse --verify refs/heads/kitty/mission-probe-exists-<MID8>",
        *_ROLLBACK,
    ],
}


def _normalise(command: str, tmp_root: Path) -> str:
    command = command.replace(str(tmp_root), "<TMP>")
    command = _MID8_RE.sub("<MID8>", command)
    command = re.sub(r"^read-tree [0-9a-f]{40}$", "read-tree <TREE>", command)
    return re.sub(r" -- (kitty-specs/\S+ ?){3,}$", " -- <SCAFFOLD>", command)


def _git_sequence(trace: Path, tmp_root: Path) -> list[str]:
    """The git built-ins *trace* recorded, normalised; auto-maintenance is dropped."""
    commands: list[str] = []
    for line in trace.read_text(encoding="utf-8").splitlines():
        _, sep, command = line.partition(_BUILTIN)
        if not sep or command.startswith("maintenance "):
            continue
        commands.append(_normalise(command, tmp_root))
    return commands


def _is_mint_view_probe(command: str) -> bool:
    return command in (_TARGET_PROBE, _RELEASE_PROBE, _STATUS_PROBE, _RESOLUTION_MARK, "read-tree <TREE>") or command.startswith(
        (_BRANCH_PROBE_PREFIX, _CHECKOUT_PREFIX, "commit --only")
    )


def _mint_view(sequence: list[str]) -> list[str]:
    """The ordered subsequence this module pins (see the module docstring)."""
    return [command for command in sequence if _is_mint_view_probe(command)]


def _traced_create(
    repo: Path,
    tmp_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    slug: str,
    target_branch: str | None = None,
    mission_id: str | None = None,
) -> tuple[list[str], BaseException | None]:
    trace = tmp_root / "git-trace.txt"
    trace.unlink(missing_ok=True)
    error: BaseException | None = None
    kwargs = {"topology": MissionTopology.SINGLE_BRANCH, "allow_worktree_context": True, "target_branch": target_branch}
    with monkeypatch.context() as env:
        env.setenv("GIT_TRACE", str(trace))
        try:
            if mission_id is None:
                create_mission_core(repo, slug, **kwargs)
            else:
                _create_mission_core_failure_atomic(repo, slug, **kwargs, _mission_id=mission_id)
        except Exception as exc:  # the refusal is the observed outcome
            error = exc
    return _git_sequence(trace, tmp_root), error


def _protected_main(root: Path) -> Path:
    return build_repo(root, target=PRIMARY_BRANCH, protected=(PRIMARY_BRANCH,))


def test_success_cell_probe_order(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _protected_main(tmp_path)
    sequence, error = _traced_create(repo, tmp_path, monkeypatch, "probe-ok")
    assert error is None
    commit_at = next(i for i, command in enumerate(sequence) if command.startswith("commit --only"))
    assert _mint_view(sequence[: commit_at + 1]) == _mint_view(EXPECTED["success"])


def test_target_without_commit_stops_at_target_probe(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = build_repo(tmp_path, protected=(PRIMARY_BRANCH, "release"))
    sequence, error = _traced_create(repo, tmp_path, monkeypatch, "probe-no-commit", target_branch="release")
    assert error is not None
    assert "has no commit" in str(error)
    assert _mint_view(sequence) == _mint_view(EXPECTED["target_without_commit"])
    assert _STATUS_PROBE not in sequence


def test_dirty_checkout_stops_at_status_probe(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _protected_main(tmp_path)
    (repo / "stray.txt").write_text("operator work\n", encoding="utf-8")
    sequence, error = _traced_create(repo, tmp_path, monkeypatch, "probe-dirty")
    assert error is not None
    assert "uncommitted changes outside" in str(error)
    assert _mint_view(sequence) == _mint_view(EXPECTED["dirty"])
    assert not any(command.startswith(_BRANCH_PROBE_PREFIX) for command in sequence)


def test_branch_exists_stops_at_branch_probe(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    slug = "probe-exists"

    repo = _protected_main(tmp_path)
    git(repo, "branch", f"kitty/mission-{slug}-{_FIXED_MID8}", PRIMARY_BRANCH)
    sequence, error = _traced_create(repo, tmp_path, monkeypatch, slug, mission_id=_FIXED_MISSION_ID)
    assert getattr(error, "error_code", None) == "MISSION_BRANCH_EXISTS"
    assert _mint_view(sequence) == _mint_view(EXPECTED["branch_exists"])
    assert not any(command.startswith(_CHECKOUT_PREFIX) for command in sequence)


# --------------------------------------------------------------------------- #
# Protection resolved at most once per create, never earlier
# --------------------------------------------------------------------------- #

#: ``ProtectionPolicy.resolve`` and ``resolve_primary_branch(bias=False)`` from
#: an unprotected ``topic`` checkout (identified with temporary trace markers).
_POLICY_PROBE = "symbolic-ref --quiet --short refs/remotes/origin/HEAD"
_PRIMARY_PROBE = "symbolic-ref refs/remotes/origin/HEAD"
#: ``resolve_primary_branch``'s own probe, the one git command that marks a resolution.
_RESOLUTION_MARK = _PRIMARY_PROBE

#: The idempotent re-create of a SINGLE_BRANCH mission on an UNPROTECTED target
#: with ``meta.json`` present: the recreate guard resolves protection (False,
#: no refusal) and the mint used to resolve it again. Captured on 7c201f9cc,
#: before the shared protection probe, and cut after the scaffold commit.
_RECREATE_DOUBLE_RESOLUTION = [
    *_PRELUDE[:9],
    "ls-files --full-name -z -- <TMP>/repo/kitty-specs/probe-recreate-<MID8>/spec.md",
    _POLICY_PROBE,  # recreate guard: ProtectionPolicy.resolve
    _PRIMARY_PROBE,  # recreate guard: resolve_primary_branch
    "rev-parse --show-toplevel",
    "symbolic-ref HEAD",
    "rev-parse --verify --quiet refs/heads/topic",
    _POLICY_PROBE,
    _POLICY_PROBE,
    _POLICY_PROBE,  # mint: ProtectionPolicy.resolve (second resolution)
    _PRIMARY_PROBE,  # mint: resolve_primary_branch (second resolution)
    "config user.email",
    "rev-parse --git-common-dir",
    "branch --show-current",
    "symbolic-ref HEAD",
    "rev-parse --verify --quiet refs/heads/topic",
    _POLICY_PROBE,
    _POLICY_PROBE,
    "diff --cached --binary --no-ext-diff --no-renames -- <SCAFFOLD>",
    "diff --name-only -z --no-renames --cached -- <SCAFFOLD>",
    "add --force -- kitty-specs/probe-recreate-<MID8>/meta.json",
    "add --force -- kitty-specs/probe-recreate-<MID8>/status.events.jsonl",
    "add --force -- kitty-specs/probe-recreate-<MID8>/tasks/README.md",
    "add --force -- kitty-specs/probe-recreate-<MID8>/tasks/.gitkeep",
    "commit --only -m 'Add scaffold for feature probe-recreate-<MID8>' -- <SCAFFOLD>",
]
#: With the shared probe the mint reuses the guard's memoised answer: exactly the mint's
#: two resolution probes are gone, nothing else moved.
_RECREATE_SINGLE_RESOLUTION = _RECREATE_DOUBLE_RESOLUTION[:17] + _RECREATE_DOUBLE_RESOLUTION[19:]
assert _RECREATE_DOUBLE_RESOLUTION[17:19] == [_POLICY_PROBE, _PRIMARY_PROBE]

_SHIM = """#!/bin/sh
if ls {readme_glob} >/dev/null 2>&1; then written=1; else written=0; fi
printf '%s %s\\n' "$written" "$*" >> {log}
exec {git} "$@"
"""


def _install_git_shim(root: Path, repo: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A ``git`` on ``PATH`` that logs, per call, whether a ``tasks/README.md`` scaffold exists yet.

    An environment change, not a module patch: it records when, relative to the
    scaffold write, each git command runs.
    """
    real_git = shutil.which("git")
    assert real_git is not None
    shim_dir = root / "shim"
    shim_dir.mkdir()
    log = root / "shim.log"
    shim = shim_dir / "git"
    shim.write_text(_SHIM.format(readme_glob=f"{repo}/kitty-specs/*/tasks/README.md", log=log, git=real_git), encoding="utf-8")
    shim.chmod(0o755)
    monkeypatch.setenv("PATH", f"{shim_dir}{os.pathsep}{os.environ['PATH']}")
    return log


def _resolutions(log: Path) -> list[bool]:
    """Per protection resolution: was the scaffold already written?"""
    calls = [line.split(" ", 1) for line in log.read_text(encoding="utf-8").splitlines()]
    return [flag == "1" for flag, command in calls if command == _RESOLUTION_MARK]


def _cut_at_commit(sequence: list[str]) -> list[str]:
    commit_at = next(i for i, command in enumerate(sequence) if command.startswith("commit --only"))
    return sequence[: commit_at + 1]


def test_idempotent_recreate_resolves_protection_once(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The one path that resolved protection twice now resolves it once.

    The single resolution is the recreate guard's, at today's position (the
    guard has always run before the scaffold write); the mint reuses it.
    """
    slug = "probe-recreate"
    repo = build_repo(tmp_path)  # on ``topic``: unprotected
    prior = repo / "kitty-specs" / f"{slug}-{_FIXED_MID8}"
    prior.mkdir(parents=True)
    (prior / "meta.json").write_text('{"mission_type": "software-dev"}\n', encoding="utf-8")
    log = _install_git_shim(tmp_path, repo, monkeypatch)
    sequence, error = _traced_create(repo, tmp_path, monkeypatch, slug, mission_id=_FIXED_MISSION_ID)
    assert error is None
    assert _mint_view(_cut_at_commit(sequence)) == _mint_view(_RECREATE_SINGLE_RESOLUTION)
    assert sequence.count(_RESOLUTION_MARK) == 1
    assert _resolutions(log) == [False]


@pytest.mark.parametrize("protected", [True, False], ids=["protected_main", "unprotected_topic"])
def test_fresh_create_resolves_protection_once_after_the_scaffold_write(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, protected: bool) -> None:
    """No ``meta.json``: the guard never resolves, so the one resolution is the mint's, after the write."""
    repo = _protected_main(tmp_path) if protected else build_repo(tmp_path)
    log = _install_git_shim(tmp_path, repo, monkeypatch)
    _sequence, error = _traced_create(repo, tmp_path, monkeypatch, "probe-fresh")
    assert error is None
    assert _resolutions(log) == [True]
