"""``doctor workspaces --remote`` through the CLI (#7214).

The option selects which remote's primary ref proves a landing. This file drives
the pre-existing command surface (``CliRunner`` over ``doctor.app``) so the flag
is exercised as an operator types it, and pins the operator-facing contract:
the JSON payload names the remote, the text header names the remote's primary
ref, a mistyped remote exits 1 with one error line, and the printed prune remedy
stays runnable.
"""

from __future__ import annotations

import json
import os
import subprocess
from collections.abc import Sequence
from pathlib import Path

import pytest
import typer
from typer.testing import CliRunner

from specify_cli.cli.commands import doctor as doctor_module
from specify_cli.workspace import process_probe
from specify_cli.workspace.process_probe import ProcessProbeResult

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

runner = CliRunner()

_OLD_DATE = "2001-02-03T04:05:06+00:00"
_LANDED = "land-7214"
_HUSK_KEYS = {"worktrees_dir", "healthy", "registration_error", "husks"}


def _git(cwd: Path, *args: str, env: dict[str, str] | None = None) -> str:
    result = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True, check=False, env=env)
    if result.returncode != 0:
        raise AssertionError(f"git {' '.join(args)} failed in {cwd}: {result.stderr.strip() or result.stdout.strip()}")
    return result.stdout


def _commit(cwd: Path, name: str, content: str) -> str:
    (cwd / name).write_text(content, encoding="utf-8")
    _git(cwd, "add", "-A")
    _git(cwd, "commit", "-q", "-m", f"add {name}")
    return _git(cwd, "rev-parse", "HEAD").strip()


@pytest.fixture
def fork_clone(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, object]:
    """A fork clone whose landing commit is on ``upstream/main`` only; the CLI resolves to it."""
    upstream = tmp_path / "upstream.git"
    origin = tmp_path / "origin.git"
    _git(tmp_path, "init", "-q", "--bare", "-b", "main", str(upstream))
    _git(tmp_path, "init", "-q", "--bare", "-b", "main", str(origin))
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "t@example.invalid")
    _git(root, "config", "user.name", "T")
    _git(root, "config", "commit.gpgsign", "false")
    (root / ".gitignore").write_text(".worktrees/\n", encoding="utf-8")
    _commit(root, "src.py", "x = 1\n")
    _git(root, "remote", "add", "origin", str(origin))
    _git(root, "remote", "add", "upstream", str(upstream))
    _git(root, "push", "-q", "-u", "origin", "main")
    _git(root, "push", "-q", "upstream", "main")

    path = root / ".worktrees" / _LANDED
    _git(root, "worktree", "add", "-q", "-b", _LANDED, str(path), "main")
    tip = _commit(path, f"{_LANDED}.txt", f"{_LANDED}\n")
    _git(root, "cherry-pick", tip, env={**os.environ, "GIT_COMMITTER_DATE": _OLD_DATE})
    _git(root, "push", "-q", "upstream", "main")
    _git(root, "fetch", "-q", "upstream")

    monkeypatch.setattr(doctor_module, "locate_project_root", lambda *a, **k: root)
    monkeypatch.chdir(root)
    return {"root": root, "path": path, "tip": tip}


@pytest.fixture(autouse=True)
def idle_proc(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The real probe over an empty fake ``/proc``: no process stands in any worktree."""
    real = process_probe.processes_with_cwd_under
    empty = tmp_path / "proc-empty"
    empty.mkdir()

    def probe(paths: Sequence[Path]) -> ProcessProbeResult:
        return real(paths, proc_root=empty)

    monkeypatch.setattr(process_probe, "processes_with_cwd_under", probe)


def _invoke(*args: str) -> tuple[int, str]:
    result = runner.invoke(doctor_module.app, ["workspaces", *args])
    return result.exit_code, result.stdout


def _registered(root: Path, path: Path) -> bool:
    return str(path.resolve()) in _git(root, "worktree", "list", "--porcelain")


def _has_branch(root: Path, branch: str) -> bool:
    probe = subprocess.run(["git", "rev-parse", "--verify", "--quiet", f"refs/heads/{branch}"], cwd=root, capture_output=True, check=False)
    return probe.returncode == 0


def _verdict_of(payload: dict[str, object], path: Path) -> dict[str, object]:
    worktrees = payload["worktrees"]
    assert isinstance(worktrees, list)
    matches = [w for w in worktrees if Path(str(w["path"])).resolve() == path.resolve()]
    assert len(matches) == 1, payload
    return dict(matches[0])


def test_help_lists_the_remote_option() -> None:
    result = runner.invoke(doctor_module.app, ["workspaces", "--help"])

    assert result.exit_code == 0, result.stdout
    assert "--remote" in result.stdout


def test_the_typer_default_is_the_module_default_remote() -> None:
    """The shell's literal and ``landed_worktrees.DEFAULT_REMOTE`` are one authority, guarded."""
    from specify_cli.workspace.landed_worktrees import DEFAULT_REMOTE

    command = typer.main.get_command(doctor_module.app).commands["workspaces"]  # type: ignore[attr-defined]
    remote_param = next(param for param in command.params if param.name == "remote")

    assert remote_param.default == DEFAULT_REMOTE


def test_remote_upstream_reports_the_landing_and_names_the_ref(fork_clone: dict[str, object]) -> None:
    path = fork_clone["path"]
    assert isinstance(path, Path)

    code, out = _invoke("--remote", "upstream")

    assert code == 0, out
    assert "proven against the local refs/remotes/upstream/main" in out
    assert f"({_LANDED}): landed" in out
    assert "1 landed, 0 kept" in out
    # The remedy must stay runnable: without the flag it would prove against origin again.
    assert "remove with: spec-kitty doctor workspaces --prune --remote upstream" in out


def test_remote_is_carried_in_the_json_payload(fork_clone: dict[str, object]) -> None:
    root, path = fork_clone["root"], fork_clone["path"]
    assert isinstance(root, Path) and isinstance(path, Path)

    code, out = _invoke("--remote", "upstream", "--json")

    assert code == 0, out
    payload = json.loads(out)
    assert payload.keys() >= _HUSK_KEYS
    assert payload["remote"] == "upstream"
    assert _verdict_of(payload, path)["verdict"] == "landed"

    code, out = _invoke("--json")
    assert code == 0, out
    payload = json.loads(out)
    assert payload["remote"] == "origin"
    assert _verdict_of(payload, path)["verdict"] == "not_landed"


def test_prune_remote_upstream_removes_and_keeps_the_remedy_honest(fork_clone: dict[str, object]) -> None:
    root, path = fork_clone["root"], fork_clone["path"]
    assert isinstance(root, Path) and isinstance(path, Path)

    code, out = _invoke("--prune", "--remote", "upstream")

    assert code == 0, out
    assert "Removed .worktrees/land-7214" in out
    assert "No landed worktrees to prune." not in out
    assert not path.exists()
    assert not _registered(root, path)
    assert not _has_branch(root, _LANDED)


def test_prune_without_the_option_still_proves_against_origin(fork_clone: dict[str, object]) -> None:
    root, path = fork_clone["root"], fork_clone["path"]
    assert isinstance(root, Path) and isinstance(path, Path)

    code, out = _invoke("--prune")

    assert code == 0, out
    assert "No landed worktrees to prune." in out
    assert path.exists() and _registered(root, path)


def test_an_unknown_remote_exits_one_with_the_configured_names(fork_clone: dict[str, object]) -> None:
    code, out = _invoke("--remote", "upstrem")

    assert code == 1, out
    assert "no such remote 'upstrem'" in out
    assert "origin" in out and "upstream" in out

    code, out = _invoke("--remote", "upstrem", "--json")
    assert code == 1, out
    payload = json.loads(out)
    assert "no such remote 'upstrem'" in payload["worktrees_error"]


def test_a_blank_remote_exits_one_instead_of_using_origin(fork_clone: dict[str, object]) -> None:
    """An empty value (an unset shell variable) is an error, not a silent fall back to origin."""
    root, path = fork_clone["root"], fork_clone["path"]
    assert isinstance(root, Path) and isinstance(path, Path)

    code, out = _invoke("--remote", "", "--json")

    assert code == 1, out
    payload = json.loads(out)
    assert payload["worktrees_error"] == "a remote name is required; got ''"
    assert payload["worktrees"] == []
    assert path.exists() and _registered(root, path)


def test_fix_still_reports_against_the_named_remote_and_prunes_nothing(fork_clone: dict[str, object]) -> None:
    """--fix removes husks only; the report it also prints honours --remote and nothing is pruned."""
    root, path = fork_clone["root"], fork_clone["path"]
    assert isinstance(root, Path) and isinstance(path, Path)

    code, out = _invoke("--fix", "--remote", "upstream")

    assert code == 0, out
    assert "No workspace husks found." in out
    assert "refs/remotes/upstream/main" in out
    assert path.exists() and _registered(root, path)
