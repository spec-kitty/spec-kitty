"""``meta.json`` ``mission_base_sha`` is recorded where the Mission branch is created (#7560).

Drives the real ``agent mission create`` entry point on a real git repository: the default
create (topic-branch mint) and an explicit ``--topology coord`` create (coordination-branch
create) both record the target's tip at create. The value is write-once, and a failed tip
read records nothing instead of raising.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from specify_cli.consolidation.mission_base import MissionBaseProvenance, resolve_mission_base
from specify_cli.mission_metadata import record_mission_base_sha
from specify_cli.meta_keys import MISSION_BASE_SHA_KEY

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

SLUG = "probe"
_TARGET = "main"


def _git(root: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True, encoding="utf-8").stdout.strip()


def _repo(tmp_path: Path) -> Path:
    from tests._factories import provision_test_charter

    root = tmp_path / "repository_root"
    root.mkdir()
    (root / ".kittify").mkdir()
    provision_test_charter(root)
    (root / "kitty-specs").mkdir()
    (root / "kitty-specs" / ".gitkeep").write_text("", encoding="utf-8")
    _git(root, "init", "-q", "-b", _TARGET)
    _git(root, "config", "user.name", "Test")
    _git(root, "config", "user.email", "test@example.invalid")
    _git(root, "config", "commit.gpgsign", "false")
    _git(root, "add", ".")
    _git(root, "commit", "-qm", "init")
    return root


def _create(repo_root: Path, monkeypatch: pytest.MonkeyPatch, *args: str) -> dict[str, Any]:
    from typer.testing import CliRunner

    from specify_cli.cli.commands.agent.mission import app

    monkeypatch.chdir(repo_root)
    result = CliRunner().invoke(app, ["create", SLUG, *args, "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output.strip().splitlines()[-1])
    assert isinstance(payload, dict)
    return payload


def _meta(payload: dict[str, Any]) -> dict[str, Any]:
    meta = json.loads(Path(str(payload["meta_file"])).read_text(encoding="utf-8"))
    assert isinstance(meta, dict)
    return meta


def test_default_create_records_target_tip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo_root = _repo(tmp_path)
    target_tip = _git(repo_root, "rev-parse", _TARGET)

    payload = _create(repo_root, monkeypatch)

    meta = _meta(payload)
    assert meta[MISSION_BASE_SHA_KEY] == target_tip
    resolved = resolve_mission_base(
        repo_root,
        Path(str(payload["meta_file"])).parent,
        mission_branch=meta["mission_branch"],
        mission_slug=meta["mission_slug"],
    )
    assert (resolved.sha, resolved.provenance) == (target_tip, MissionBaseProvenance.RECORDED)


def test_coord_create_records_target_tip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo_root = _repo(tmp_path)
    target_tip = _git(repo_root, "rev-parse", _TARGET)

    meta = _meta(_create(repo_root, monkeypatch, "--topology", "coord"))

    assert meta["topology"] == "coord"
    assert meta[MISSION_BASE_SHA_KEY] == target_tip
    assert _git(repo_root, "merge-base", "--is-ancestor", target_tip, meta["coordination_branch"]) == ""


def test_failed_tip_read_records_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo_root = _repo(tmp_path)
    monkeypatch.setattr("specify_cli.core.mission_creation_protected_mint.capture_branch_tip", lambda *_a, **_k: None)

    meta = _meta(_create(repo_root, monkeypatch))

    assert "mission_branch" in meta
    assert MISSION_BASE_SHA_KEY not in meta


def test_record_is_write_once() -> None:
    meta: dict[str, Any] = {}
    record_mission_base_sha(meta, "a" * 40)
    record_mission_base_sha(meta, "b" * 40)
    assert meta[MISSION_BASE_SHA_KEY] == "a" * 40
