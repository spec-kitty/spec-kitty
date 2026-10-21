"""A fresh ``spec-kitty init`` lives on the activation ledger from birth (WP14, FR-019).

``init`` -> ``charter context`` -> ``agent mission create`` -> ``spec-kitty
upgrade``, all as real subprocesses. The project gets
``.kittify/charter/activation.yaml`` holding the default preset's mission
types, ``config.yaml`` and ``charter.yaml`` carry no activation key, and an
upgrade moves no activation key and changes no activation file: a fresh
project is never "unmigrated".

The first upgrade of a fresh project still settles two files that have nothing
to do with activation (a merge-driver line in ``.gitattributes`` and the
``last_upgraded_at`` spelling in ``.kittify/metadata.yaml``, both written by
the clone-local and metadata steps that run on every new clone). So the
activation files are compared across that first upgrade, and a second upgrade
must change no file at all. The upgrade preview may still list
``4.0.0rc8_activation_ledger`` (selected and reported not needed when no
migration ledger exists, its ``detect()`` being false), so the assertion is
"nothing moved and no file changed", never "not selected" (carry-forward M1).
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

import pytest
from ruamel.yaml import YAML

from charter.activation.activation_ledger import LEDGER_KEYS
from kernel.activation_ledger_store import ACTIVATION_LEDGER, activation_ledger_path
from tests._support.activation_cli import REPO_ROOT, cli, git, init_git_repo, snapshot, unwrapped

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_SAFE = YAML(typ="safe")
_DEFAULT_TYPES = _SAFE.load((REPO_ROOT / "packs" / "built-in" / "presets" / "default.yaml").read_text(encoding="utf-8"))["mission_type_activations"]
_CONFIG = Path(".kittify", "config.yaml")
_CHARTER = Path(".kittify", "charter", "charter.yaml")


def _load(path: Path) -> dict[str, Any]:
    return dict(_SAFE.load(path.read_text(encoding="utf-8")) or {})


@pytest.fixture(scope="module")
def initialized(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """One real ``spec-kitty init`` per module, committed; tests work on copies."""
    repo = init_git_repo(tmp_path_factory.mktemp("init-flow") / "project")
    result = cli(repo, "init", ".", "--ai", "claude")
    assert result.returncode == 0, unwrapped(result)
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "spec-kitty init")
    return repo


@pytest.fixture()
def project(initialized: Path, tmp_path: Path) -> Path:
    copy = tmp_path / "project"
    shutil.copytree(initialized, copy, symlinks=True)
    return copy


def _assert_no_legacy_activation_key(repo: Path) -> None:
    assert set(_load(repo / _CONFIG)).isdisjoint(LEDGER_KEYS)
    if (repo / _CHARTER).is_file():
        assert set(_load(repo / _CHARTER)).isdisjoint(LEDGER_KEYS)


def test_init_writes_the_ledger_and_no_legacy_key(project: Path) -> None:
    ledger = activation_ledger_path(project)
    assert ledger.is_file()
    assert _load(ledger) == {"mission_type_activations": _DEFAULT_TYPES}
    _assert_no_legacy_activation_key(project)


def _activation_files(snap: dict[str, bytes]) -> dict[str, bytes]:
    activation = {ACTIVATION_LEDGER.as_posix(), _CONFIG.as_posix(), _CHARTER.as_posix()}
    return {path: digest for path, digest in snap.items() if path in activation}


def test_context_mission_create_then_upgrade_changes_no_file(project: Path) -> None:
    context = cli(project, "charter", "context", "--action", "implement", "--json", "--no-mark-loaded")
    assert context.returncode == 0, unwrapped(context)
    git(project, "checkout", "-q", "-b", "ledger-flow")
    created = cli(project, "agent", "mission", "create", "ledger-flow", "--mission-type", "software-dev", "--json")
    assert created.returncode == 0, unwrapped(created)
    git(project, "add", "-A")
    git(project, "commit", "-q", "-m", "mission created")
    before = snapshot(project)

    preview = cli(project, "upgrade", "--dry-run", "--json", "--no-worktrees")
    assert preview.returncode == 0, unwrapped(preview)
    assert snapshot(project) == before, "a dry run writes nothing"

    upgraded = cli(project, "upgrade", "--yes", "--no-worktrees")
    assert upgraded.returncode == 0, unwrapped(upgraded)
    settled = snapshot(project)
    assert _activation_files(settled) == _activation_files(before), "an upgrade of a fresh project moves no activation key"
    assert ACTIVATION_LEDGER.as_posix() in _activation_files(settled)
    _assert_no_legacy_activation_key(project)

    again = cli(project, "upgrade", "--yes", "--no-worktrees")
    assert again.returncode == 0, unwrapped(again)
    assert snapshot(project) == settled, "a second upgrade changes no file at all"
