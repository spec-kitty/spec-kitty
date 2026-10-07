"""#5759 -- a teammate's fresh clone never gets the per-clone merge-driver git config.

``.gitattributes`` travels with the repository, but ``merge.<key>.name`` /
``merge.<key>.driver`` live in ``.git/config`` and do not. ``spec-kitty init`` on
an already-initialized clone returned before installing them and ``upgrade`` ran
only unrecorded migrations, so the first ``git pull`` of divergent
``status.events.jsonl`` / ``meta.json`` edits produced raw conflict markers.

Closed-world arms against REAL git and the REAL CLI (this worktree's ``src``,
no mocks), following the red-first policy of ADR 2026-07-17-1:

* init arm: clone + ``init`` -> same ``merge.*`` key count as the original clone;
* pull arm: divergent edits pulled with ``git pull --no-rebase`` merge cleanly
  (both appended event lines kept, both adjacent ``meta.json`` edits kept);
* base control: a clone WITHOUT the config conflicts on exactly the same pull,
  so the pull arm can fail on the base behaviour;
* upgrade arm: clone + ``upgrade --yes`` installs the same config.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest

from tests._support.two_clone import attach_and_push, clone_from, isolated_git_env, make_bare_remote

pytestmark = [pytest.mark.regression, pytest.mark.integration, pytest.mark.git_repo]

_WORKTREE_ROOT = Path(__file__).resolve().parents[2]
_SRC = _WORKTREE_ROOT / "src"
_MISSION_DIR = "kitty-specs/m"
_EVENTS = f"{_MISSION_DIR}/status.events.jsonl"
_META = f"{_MISSION_DIR}/meta.json"
_MERGE_KEYS = r"^merge\."
_ALREADY_INITIALIZED = "Already Initialized"
_INSTALLED_LINE = "Installed clone-local merge-driver settings"
_CLI_TIMEOUT = 300
_MIN_DRIVER_KEYS = 14  # 7 registered drivers x (name + driver); see lanes.consolidation._MERGE_DRIVERS


def _event(event_id: str, to_lane: str) -> str:
    return json.dumps(
        {
            "actor": "t",
            "at": "2026-01-01T00:00:00+00:00",
            "event_id": event_id,
            "from_lane": "planned",
            "to_lane": to_lane,
            "wp_id": "WP01",
        },
        sort_keys=True,
    )


_BASE_EVENT = _event("01JBASE000000000000000000A", "claimed")
_BASE_META = {"mission_id": "01JBASE000000000000000000A", "slug": "m", "title": "base", "status": "base", "note": "base"}


def _git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-C", str(repo), *args], check=check, capture_output=True, text=True)


def _merge_key_count(repo: Path) -> int:
    result = _git(repo, "config", "--local", "--get-regexp", _MERGE_KEYS, check=False)
    return len([line for line in result.stdout.splitlines() if line.strip()])


@dataclass(frozen=True)
class _World:
    bare: Path
    original: Path
    root: Path
    env: dict[str, str]

    def clone(self, name: str) -> Path:
        return clone_from(self.bare, self.root / name)

    def cli(self, repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "specify_cli", *args],
            cwd=str(repo),
            env=self.env,
            capture_output=True,
            text=True,
            check=False,
            timeout=_CLI_TIMEOUT,
        )


def _write_meta(repo: Path, **changes: str) -> None:
    (repo / _META).write_text(json.dumps({**_BASE_META, **changes}, indent=2) + "\n", encoding="utf-8")


def _commit_all(repo: Path, message: str) -> None:
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", message)


def _install_spec_kitty_shim(bin_dir: Path) -> None:
    """A ``spec-kitty`` on PATH that runs THIS worktree's code (git runs drivers from PATH)."""
    bin_dir.mkdir(parents=True, exist_ok=True)
    shim = bin_dir / "spec-kitty"
    shim.write_text(f'#!/bin/sh\nexec "{sys.executable}" -m specify_cli "$@"\n', encoding="utf-8")
    shim.chmod(0o755)


@pytest.fixture(scope="module")
def world() -> Iterator[_World]:
    """Original clone A (real ``init``) with committed mission artifacts, pushed to a bare remote."""
    root = Path(tempfile.mkdtemp(prefix="clone-merge-drivers-"))
    try:
        with pytest.MonkeyPatch.context() as mp:
            isolated_git_env(mp, root)
            _install_spec_kitty_shim(root / "bin")
            mp.setenv("PATH", f"{root / 'bin'}{os.pathsep}{os.environ['PATH']}")
            mp.setenv("PYTHONPATH", str(_SRC))
            mp.setenv("SPEC_KITTY_NO_UPGRADE_CHECK", "1")
            mp.delenv("VIRTUAL_ENV", raising=False)
            env = os.environ.copy()

            bare = make_bare_remote(root)
            original = root / "original"
            subprocess.run(["git", "init", "-q", "-b", "main", str(original)], check=True, capture_output=True)
            _git(original, "config", "user.name", "Original")
            _git(original, "config", "user.email", "original@example.com")
            world = _World(bare=bare, original=original, root=root, env=env)

            init = world.cli(original, "init", ".", "--ai", "claude", "--non-interactive")
            assert init.returncode == 0, init.stdout + init.stderr
            (original / _MISSION_DIR).mkdir(parents=True)
            (original / _EVENTS).write_text(_BASE_EVENT + "\n", encoding="utf-8")
            _write_meta(original)
            _commit_all(original, "initialize project with a mission")
            attach_and_push(original, bare, ["main"])
            yield world
    finally:
        shutil.rmtree(root, ignore_errors=True)


def _teammate_branch(world: _World, branch: str) -> None:
    """The other side of a divergent pull: appends an event and edits ``title``; pushed to *branch*."""
    teammate = world.clone(f"teammate-{branch}")
    with (teammate / _EVENTS).open("a", encoding="utf-8") as handle:
        handle.write(_event("01JTEAMMATE00000000000000A", "in_progress") + "\n")
    _write_meta(teammate, title="teammate")
    _commit_all(teammate, "teammate progress")
    _git(teammate, "push", "-q", "origin", f"main:refs/heads/{branch}")


def _local_progress_then_pull(world: _World, clone: Path, branch: str) -> subprocess.CompletedProcess[str]:
    """Local edit on the line next to the teammate's (``status``, ours-authoritative in the meta driver) + an appended event, then a merge pull."""
    with (clone / _EVENTS).open("a", encoding="utf-8") as handle:
        handle.write(_event("01JLOCAL00000000000000000A", "for_review") + "\n")
    _write_meta(clone, status="local")
    _commit_all(clone, "local progress")
    return _git(clone, "pull", "--no-rebase", "origin", branch, check=False)


def test_original_clone_has_the_driver_config(world: _World) -> None:
    """Positive control for the init arm: a normal ``init`` defines every driver."""
    assert _merge_key_count(world.original) >= _MIN_DRIVER_KEYS


def test_init_on_a_fresh_clone_installs_the_same_merge_config(world: _World) -> None:
    clone = world.clone("init-arm")
    assert _merge_key_count(clone) == 0, "a fresh clone must start without per-clone merge config"

    first = world.cli(clone, "init", ".", "--ai", "claude", "--non-interactive")

    assert first.returncode == 0, first.stdout + first.stderr
    assert _ALREADY_INITIALIZED in first.stdout
    assert _merge_key_count(clone) == _merge_key_count(world.original)
    assert _INSTALLED_LINE in first.stdout

    before = _git(clone, "config", "--local", "--list").stdout
    second = world.cli(clone, "init", ".", "--ai", "claude", "--non-interactive")
    assert second.returncode == 0, second.stdout + second.stderr
    assert _INSTALLED_LINE not in second.stdout, "an already-configured clone must print nothing new"
    assert _git(clone, "config", "--local", "--list").stdout == before


def test_pull_of_divergent_mission_artifacts_merges_after_init_on_the_clone(world: _World) -> None:
    clone = world.clone("pull-arm")
    init = world.cli(clone, "init", ".", "--ai", "claude", "--non-interactive")
    assert init.returncode == 0, init.stdout + init.stderr
    _teammate_branch(world, "pull-arm")

    pull = _local_progress_then_pull(world, clone, "pull-arm")

    assert pull.returncode == 0, pull.stdout + pull.stderr
    events = (clone / _EVENTS).read_text(encoding="utf-8")
    assert "<<<<<<<" not in events
    assert "01JTEAMMATE00000000000000A" in events
    assert "01JLOCAL00000000000000000A" in events
    meta_text = (clone / _META).read_text(encoding="utf-8")
    assert "<<<<<<<" not in meta_text
    merged = json.loads(meta_text)
    assert (merged["title"], merged["status"]) == ("teammate", "local")


def test_base_control_the_same_pull_conflicts_without_the_driver_config(world: _World) -> None:
    """Falsifiability of the pull arm: with no per-clone config the identical pull leaves markers (#5759)."""
    clone = world.clone("control")
    assert _merge_key_count(clone) == 0
    _teammate_branch(world, "control")

    pull = _local_progress_then_pull(world, clone, "control")

    assert pull.returncode != 0, "adjacent meta.json edits + same-EOF appends must conflict without drivers"
    assert "<<<<<<<" in (clone / _EVENTS).read_text(encoding="utf-8")
    assert "<<<<<<<" in (clone / _META).read_text(encoding="utf-8")


def test_upgrade_on_a_fresh_clone_installs_the_same_merge_config(world: _World) -> None:
    clone = world.clone("upgrade-arm")
    assert _merge_key_count(clone) == 0

    upgrade = world.cli(clone, "upgrade", "--yes")

    assert upgrade.returncode == 0, upgrade.stdout + upgrade.stderr
    assert _merge_key_count(clone) == _merge_key_count(world.original)
