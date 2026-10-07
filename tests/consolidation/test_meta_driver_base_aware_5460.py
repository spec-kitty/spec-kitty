"""Real-git and subprocess guards for the base-aware ``meta.json`` driver (#5460).

An ordinary ``git merge`` of two clones that changed DISJOINT ``meta.json`` keys
must keep both changes: the driver registered for ``meta.json`` has to honour the
merge base (``%O``). The pre-fix driver ignored ``%O`` and returned the other
side's record wholesale, silently reverting ``mission close --discard`` (#5460).

Every subprocess runs the worktree's own sources (``PYTHONPATH``), never the
editable install of another checkout.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

pytestmark = [pytest.mark.git_repo, pytest.mark.non_sandbox]  # the driver shells out to specify_cli

REPO_ROOT = Path(__file__).resolve().parents[2]
TWO_WAY_ENV = "SPEC_KITTY_META_MERGE_TWO_WAY"
META_REL = "kitty-specs/m/meta.json"

ANCESTOR: dict[str, Any] = {
    "coordination_branch": "kitty/mission-team-01M48ZJZ",
    "flattened": False,
    "mission_id": "01M48ZJZD8FVS9JFZWYD26DZHC",
    "mission_slug": "team-01M48ZJZ",
    "purpose_tldr": "Two clone QA",
    "topology": "coord",
}
DISCARDING: dict[str, Any] = {
    "discarded_at": "2026-10-06T16:09:05.242367+00:00",
    "flattened": True,
    "mission_id": ANCESTOR["mission_id"],
    "mission_slug": ANCESTOR["mission_slug"],
    "purpose_tldr": ANCESTOR["purpose_tldr"],
}
TEAMMATE: dict[str, Any] = ANCESTOR | {
    "vcs": "git",
    "vcs_locked_at": "2026-10-06T16:09:00.623338+00:00",
}


def _env(**extra: str) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if k != TWO_WAY_ENV}
    env["PYTHONPATH"] = str(REPO_ROOT / "src")
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    env.update(extra)
    return env


def _git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=repo, text=True, capture_output=True, check=check, env=_env())


def _write_meta(repo: Path, payload: dict[str, Any]) -> None:
    path = repo / META_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _commit(repo: Path, message: str) -> None:
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", message)


def _make_repo(tmp_path: Path) -> tuple[Path, Path]:
    """Repo with the meta driver registered through a recording wrapper; returns (repo, calls)."""
    repo = tmp_path / "repo"
    repo.mkdir()
    calls = tmp_path / "driver.calls"
    wrapper = tmp_path / "driver.py"
    wrapper.write_text(
        "\n".join(
            [
                "import os, sys",
                f"with open({str(calls)!r}, 'a', encoding='utf-8') as fh:",
                "    fh.write(' '.join(sys.argv[1:]) + '\\n')",
                "os.execv(sys.executable, [sys.executable, '-m', 'specify_cli', 'merge-driver-meta', *sys.argv[1:]])",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Spec Kitty")
    _git(repo, "config", "merge.spec-kitty-meta.name", "test")
    _git(repo, "config", "merge.spec-kitty-meta.driver", f'"{sys.executable}" "{wrapper}" %O %A %B')
    (repo / ".gitattributes").write_text("kitty-specs/**/meta.json merge=spec-kitty-meta\n", encoding="utf-8")
    _write_meta(repo, ANCESTOR)
    _commit(repo, "base")
    _git(repo, "branch", "discard")
    _write_meta(repo, TEAMMATE)
    _commit(repo, "teammate locks vcs")
    _git(repo, "checkout", "-q", "discard")
    _write_meta(repo, DISCARDING)
    _commit(repo, "discard")
    return repo, calls


def _assert_driver_ran_once(calls: Path) -> None:
    assert calls.exists(), "git never invoked the registered meta driver"
    assert len(calls.read_text(encoding="utf-8").splitlines()) == 1


def _assert_discard_kept(repo: Path) -> None:
    merged = json.loads((repo / META_REL).read_text(encoding="utf-8"))
    assert merged.get("discarded_at") == DISCARDING["discarded_at"]
    assert merged["flattened"] is True
    assert "topology" not in merged
    assert "coordination_branch" not in merged
    assert merged["vcs"] == "git"
    assert merged["vcs_locked_at"] == TEAMMATE["vcs_locked_at"]


def test_ordinary_merge_keeps_a_discard_next_to_a_teammates_edit(tmp_path: Path) -> None:
    """A teammate's `git pull` (merge) must not undo `mission close --discard` (#5460).

    The discarding clone is on ``discard`` (ours); the upstream carrying the
    teammate's edit is ``main`` (theirs) -- the shape of ``git pull``.
    """
    repo, calls = _make_repo(tmp_path)

    merge = _git(repo, "merge", "--no-edit", "main", check=False)

    assert merge.returncode == 0, merge.stdout + merge.stderr
    _assert_driver_ran_once(calls)
    _assert_discard_kept(repo)


def _run_driver_subprocess(tmp_path: Path, env: dict[str, str]) -> dict[str, Any]:
    base, ours, theirs = tmp_path / "O", tmp_path / "A", tmp_path / "B"
    base.write_text(json.dumps({"a": 1, "b": 1}), encoding="utf-8")
    ours.write_text(json.dumps({"a": 2, "b": 1}), encoding="utf-8")
    theirs.write_text(json.dumps({"a": 1, "b": 2}), encoding="utf-8")
    done = subprocess.run(
        [sys.executable, "-m", "specify_cli", "merge-driver-meta", str(base), str(ours), str(theirs)],
        text=True,
        capture_output=True,
        env=env,
    )
    assert done.returncode == 0, done.stdout + done.stderr
    loaded: dict[str, Any] = json.loads(ours.read_text(encoding="utf-8"))
    return loaded


def test_two_way_opt_out_selects_the_two_way_rule_in_the_shell(tmp_path: Path) -> None:
    """The consolidation mission→target opt-out must differ from the base-aware result."""
    (tmp_path / "ordinary").mkdir()
    (tmp_path / "squash").mkdir()

    ordinary = _run_driver_subprocess(tmp_path / "ordinary", _env())
    squash = _run_driver_subprocess(tmp_path / "squash", _env(**{TWO_WAY_ENV: "1"}))

    assert ordinary == {"a": 2, "b": 2}  # three-way: each one-sided change survives
    assert squash == {"a": 1, "b": 2}  # two-way: every key from theirs
