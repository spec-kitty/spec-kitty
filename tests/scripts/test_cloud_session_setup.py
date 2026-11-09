"""Behavior of ``scripts/dev/cloud-session-setup.sh``: what it runs, in which order, when.

The script is driven through a fake ``uv`` on ``PATH`` that records its arguments,
so no dependency sync, pack fetch or service download happens here.
"""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

from tests._support.temp_root import harness_env

pytestmark = [
    pytest.mark.fast,
    pytest.mark.skipif(shutil.which("bash") is None, reason="needs bash"),
]

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/dev/cloud-session-setup.sh"

_PACK_CHECK = "scripts/sync_packs.py --pack all --check"
_PACK_SYNC = "scripts/sync_packs.py --pack all"
_SERVICE_EXTRAS = "scripts/sync_services.py --service all --extras-only"

# Records each call on one line; a call whose arguments contain a key from the
# FAKE_UV_FAIL list (``|``-separated) exits 1.
_FAKE_UV = """#!/bin/bash
echo "$*" >> "$FAKE_UV_LOG"
IFS='|' read -ra fails <<< "${FAKE_UV_FAIL:-}"
for key in "${fails[@]}"; do
  [ -n "$key" ] && [[ "$*" == *"$key"* ]] && exit 1
done
exit 0
"""


def _setup(tmp_path: Path) -> tuple[Path, Path, Path]:
    repo = tmp_path / "repo"
    repo.mkdir(parents=True)
    env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    env.update(harness_env())
    subprocess.run(["git", "init", "-q", str(repo)], env=env, check=True)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    uv = bin_dir / "uv"
    uv.write_text(_FAKE_UV, encoding="utf-8")
    uv.chmod(uv.stat().st_mode | stat.S_IXUSR)
    return repo, bin_dir, tmp_path / "uv.log"


def _run(tmp_path: Path, *, remote: str | None = "true", fail: str = "") -> tuple[subprocess.CompletedProcess[str], list[str], Path]:
    repo, bin_dir, log = _setup(tmp_path)
    env = {key: value for key, value in os.environ.items() if not key.startswith(("GIT_", "CLAUDE_"))}
    env.update(harness_env())
    env.update({"PATH": f"{bin_dir}{os.pathsep}/usr/bin{os.pathsep}/bin", "CLAUDE_PROJECT_DIR": str(repo)})
    env.update({"FAKE_UV_LOG": str(log), "FAKE_UV_FAIL": fail})
    if remote is not None:
        env["CLAUDE_CODE_REMOTE"] = remote
    result = subprocess.run(["bash", str(SCRIPT)], cwd=repo, env=env, text=True, capture_output=True, check=False)
    calls = log.read_text(encoding="utf-8").splitlines() if log.exists() else []
    return result, calls, repo


def _index(calls: list[str], needle: str, *, exact_tail: bool = False) -> int:
    for i, call in enumerate(calls):
        if call.endswith(needle) if exact_tail else needle in call:
            return i
    raise AssertionError(f"no call matching {needle!r} in {calls}")


def test_noop_outside_a_cloud_session(tmp_path: Path) -> None:
    for remote in (None, "false"):
        result, calls, _ = _run(tmp_path / str(remote), remote=remote)
        assert result.returncode == 0, result.stderr
        assert calls == []


def test_stale_packs_are_synced_after_the_dependency_sync(tmp_path: Path) -> None:
    result, calls, _ = _run(tmp_path, fail=_PACK_CHECK)
    assert result.returncode == 0, result.stderr
    uv_sync = _index(calls, "sync --frozen --all-extras")
    check = _index(calls, _PACK_CHECK)
    sync = _index(calls, _PACK_SYNC, exact_tail=True)
    assert uv_sync < check < sync


def test_present_packs_take_the_fast_path(tmp_path: Path) -> None:
    result, calls, _ = _run(tmp_path)
    assert result.returncode == 0, result.stderr
    _index(calls, _PACK_CHECK)
    assert not any(call.endswith(_PACK_SYNC) for call in calls), calls


def test_failed_pack_sync_fails_the_script(tmp_path: Path) -> None:
    result, calls, _ = _run(tmp_path, fail=f"{_PACK_CHECK}|--pack all")
    assert result.returncode != 0
    assert any(call.endswith(_PACK_SYNC) for call in calls), calls


def test_pinned_service_extras_are_fetched_and_a_failure_is_only_a_note(tmp_path: Path) -> None:
    result, calls, _ = _run(tmp_path, fail=_SERVICE_EXTRAS)
    assert result.returncode == 0, result.stderr
    assert _index(calls, "sync --frozen --all-extras") < _index(calls, _SERVICE_EXTRAS)
    assert "make sync-services" in result.stdout + result.stderr


def test_rerun_is_idempotent(tmp_path: Path) -> None:
    _, _, repo = _run(tmp_path)
    env = {key: value for key, value in os.environ.items() if not key.startswith(("GIT_", "CLAUDE_"))}
    env.update(harness_env())
    env.update(
        {
            "PATH": f"{tmp_path / 'bin'}{os.pathsep}/usr/bin{os.pathsep}/bin",
            "CLAUDE_PROJECT_DIR": str(repo),
            "CLAUDE_CODE_REMOTE": "true",
            "FAKE_UV_LOG": str(tmp_path / "uv.log"),
        }
    )
    second = subprocess.run(["bash", str(SCRIPT)], cwd=repo, env=env, text=True, capture_output=True, check=False)
    assert second.returncode == 0, second.stderr
    exclude = (repo / ".git/info/exclude").read_text(encoding="utf-8")
    assert exclude.splitlines().count(".codegraph/") == 1
