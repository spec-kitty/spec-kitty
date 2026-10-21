"""Re-running ``spec-kitty init`` on an unmigrated project leaves rc8 pending (WP08 T049, pass-8 M4, analyze pass 10).

The init-seed case is moot by construction: a re-run of ``init`` on a project
whose ``config.yaml`` exists stops at the already-initialized branch, before
provisioning and before the migration-ledger seed, and a fresh ``init`` never
has pre-existing legacy keys. These tests pin that: the re-run exits 0
("Already initialized", the unmigrated keys read as legacy allow keys), writes
nothing, and ``4.0.0rc8_activation_ledger`` stays pending, so
``spec-kitty upgrade`` moves the keys. The positive control: a fresh ``init``
seeds rc8 as applied, so a later upgrade does not select it.
"""

from __future__ import annotations

import contextlib
import io
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
import typer
import yaml
from rich.console import Console
from typer import Typer
from typer.testing import CliRunner

from charter.activation.activation_ledger import LEDGER_KEYS, ActiveCharterConfigError
from kernel.activation_ledger_store import activation_ledger_path
from specify_cli.cli.commands import init as init_module
from specify_cli.cli.commands.init import register_init_command
from specify_cli.cli.commands.migrate_cmd import app as migrate_app
from specify_cli.cli.commands.upgrade import upgrade
from specify_cli.template.manager import TemplateCopyResult

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_GIT_SETUP = (
    ["init", "-q", "-b", "main"],
    ["config", "user.email", "t@example.com"],
    ["config", "user.name", "T"],
    ["add", "-A"],
    ["commit", "-q", "-m", "init"],
)

_MIGRATION_ID = "4.0.0rc8_activation_ledger"
_BUILT_IN = Path(__file__).resolve().parents[3] / "packs" / "built-in"


def _fake_copy_package(project_path: Path) -> TemplateCopyResult:
    kittify = project_path / ".kittify"
    kittify.mkdir(parents=True, exist_ok=True)
    return TemplateCopyResult(kittify / "templates" / "command-templates", templates_created=True)


@pytest.fixture()
def init_app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Typer:
    packs_root = tmp_path / "packs-root"
    shutil.copytree(_BUILT_IN, packs_root / "built-in")
    monkeypatch.setenv("SPEC_KITTY_PACKS_ROOT", str(packs_root))
    monkeypatch.setattr(init_module, "get_local_repo_root", lambda override_path=None: None)
    monkeypatch.setattr(init_module, "copy_specify_base_from_package", _fake_copy_package)
    app = Typer()
    register_init_command(
        app,
        console=Console(file=io.StringIO(), force_terminal=False),
        show_banner=lambda: None,
        activate_mission=lambda proj, mtype, mdisplay, _con: mdisplay,
        ensure_executable_scripts=lambda path, tracker=None: None,
    )
    return app


def _init(app: Typer, cwd: Path, *args: str) -> Any:
    with contextlib.chdir(cwd):
        return CliRunner().invoke(app, ["init", *args], catch_exceptions=True)


def _fresh(app: Typer, tmp_path: Path, name: str) -> Path:
    result = _init(app, tmp_path, name, "--ai", "claude", "--non-interactive")
    assert result.exit_code == 0, result.output
    project = tmp_path / name
    for args in _GIT_SETUP:
        subprocess.run(["git", *args], cwd=project, check=True, capture_output=True)
    return project


def _unmigrate(project: Path) -> dict[str, Any]:
    """Turn a fresh project into one an older CLI wrote: keys in config.yaml, no ledger, rc8 unrecorded."""
    ledger_path = activation_ledger_path(project)
    keys = dict(yaml.safe_load(ledger_path.read_text(encoding="utf-8")) or {})
    ledger_path.unlink()
    config = project / ".kittify" / "config.yaml"
    data = dict(yaml.safe_load(config.read_text(encoding="utf-8")) or {})
    data.update(keys)
    config.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    tracked = project / ".kittify" / "migration-ledger.jsonl"
    lines = [line for line in tracked.read_text(encoding="utf-8").splitlines() if json.loads(line)["id"] != _MIGRATION_ID]
    tracked.write_text("\n".join(lines) + "\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=project, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-q", "-m", "older cli"], cwd=project, check=True, capture_output=True)
    return keys


def _tree(project: Path) -> dict[str, bytes]:
    files = (path for path in sorted(project.rglob("*")) if path.is_file() and ".git" not in path.relative_to(project).parts)
    return {path.relative_to(project).as_posix(): path.read_bytes() for path in files}


def _rc8_step(project: Path) -> dict[str, Any]:
    with contextlib.chdir(project):
        report = CliRunner().invoke(migrate_app, ["ledger", "--json"])
    assert report.exit_code == 0, report.output
    return next(step for step in json.loads(report.output)["steps"] if step["id"] == _MIGRATION_ID)


def _upgrade(project: Path) -> Any:
    app = typer.Typer(add_completion=False)
    app.command()(upgrade)
    with contextlib.chdir(project):
        return CliRunner().invoke(app, ["--yes", "--no-worktrees"], catch_exceptions=False)


def _refusal_in_chain(exc: BaseException | None) -> ActiveCharterConfigError | None:
    """The activation refusal behind *exc* (``__cause__`` or ``__context__``), if any."""
    seen = 0
    while exc is not None and seen < 10:
        if isinstance(exc, ActiveCharterConfigError):
            return exc
        exc = exc.__cause__ or exc.__context__
        seen += 1
    return None


def _never(name: str) -> Any:
    def _called(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError(f"re-run init reached {name}: it must stop at the already-initialized exit")

    return _called


def test_reinit_of_an_unmigrated_project_exits_early_and_leaves_rc8_pending(init_app: Typer, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from specify_cli.upgrade import init_seed

    project = _fresh(init_app, tmp_path, "older")
    keys = _unmigrate(project)
    assert keys, "the fresh init provisioned nothing to move"
    before = _tree(project)
    monkeypatch.setattr(init_module, "provision_default_mission_type_activations", _never("provisioning"))
    monkeypatch.setattr(init_seed, "seed_migration_ledger_for_init", _never("the migration-ledger seed"))

    rerun = _init(init_app, project, ".", "--ai", "claude", "--non-interactive")

    # One mode: the re-run's surface checks read the unmigrated keys as legacy
    # allow keys, so it exits 0 "Already initialized", stopping before
    # provisioning and the seed (both would raise) and writing nothing.
    assert rerun.exit_code == 0, rerun.output
    assert _refusal_in_chain(rerun.exception) is None
    assert not activation_ledger_path(project).exists(), "no ledger is created beside legacy keys (hole 3)"
    assert _tree(project) == before
    step = _rc8_step(project)
    assert step["applied"] is False and step["pending"] is True

    upgraded = _upgrade(project)
    assert upgraded.exit_code == 0, upgraded.output
    assert dict(yaml.safe_load(activation_ledger_path(project).read_text(encoding="utf-8"))) == keys
    assert not set(yaml.safe_load((project / ".kittify" / "config.yaml").read_text(encoding="utf-8"))) & set(LEDGER_KEYS)


def test_fresh_init_seeds_rc8_so_upgrade_does_not_select_it(init_app: Typer, tmp_path: Path) -> None:
    project = _fresh(init_app, tmp_path, "fresh")
    step = _rc8_step(project)
    assert step["applied"] is True and step["pending"] is False
