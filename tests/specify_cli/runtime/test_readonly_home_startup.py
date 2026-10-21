"""Issue #6473: a read-only home folder must not stop the CLI before it runs.

Every CLI invocation (except the ``next``/hook fast paths, ``upgrade`` and
``migrate``) first prepares three global asset owners in the home folder:
``bootstrap.ensure_runtime``, ``agent_skills.ensure_global_agent_skills`` and
``agent_commands.ensure_global_agent_commands``. In a sandbox that can only
write to the workspace (agent harnesses, plain CI containers) those writes
fail. Before the fix an empty read-only home died with a raw ``OSError``
traceback on the cold-install sentinel, and a set-up home with something to
refresh exited 1 with a ``StartupAssetError`` -- in both cases before the
requested command ran.

The tests inject the failure at leaf I/O only (``asset_preparation.
machine_file_lock`` and ``asset_preparation._write_asset``), the same seams
``tests/runtime/test_startup_torn_read_escalation.py`` uses, because ``chmod``
does not bind uid 0. ``TestReadOnlyHomeSubprocess`` repeats the check with a
real ``chmod 0o555`` home where the process is not root.
"""

from __future__ import annotations

import errno
import json
import logging
import os
import subprocess
import sys
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

import specify_cli
import specify_cli.runtime.agent_commands as agent_commands
import specify_cli.runtime.agent_skills as agent_skills
import specify_cli.runtime.asset_preparation as asset_preparation
import specify_cli.runtime.bootstrap as bootstrap
from specify_cli.runtime.asset_preparation import UNWRITABLE_HOME_CODE, StartupAssetError, is_unwritable_home_error
from specify_cli.runtime.startup_assets import prepare_startup_assets
from specify_cli.skills.registry import SkillRegistry

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_ENTRY_POINTS: dict[str, Callable[[], None]] = {
    "runtime": bootstrap.ensure_runtime,
    "commands": lambda: agent_commands.ensure_global_agent_commands(agent_keys=["claude"]),
    "skills": agent_skills.ensure_global_agent_skills,
}
_OWNER_KEYS = {"runtime": "runtime_bootstrap", "commands": "slash_commands", "skills": "global_skills"}


@pytest.fixture()
def fake_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A cold home; mirrors ``test_startup_torn_read_escalation.fake_home``."""
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("SPEC_KITTY_HOME", str(home / ".kittify"))
    monkeypatch.delenv("OPENCODE_CONFIG_DIR", raising=False)
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.delenv("LLXPRT_CONFIG_HOME", raising=False)
    return home


@pytest.fixture()
def fake_assets(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Small deterministic sources for all three owners (no ``packs/built-in`` reads)."""
    from specify_cli.shims.registry import PROMPT_DRIVEN_COMMANDS

    missions = tmp_path / "package" / "missions"
    (missions / "software-dev" / "templates").mkdir(parents=True)
    (missions / "software-dev" / "mission.yaml").write_text("test-mission")
    (missions / "software-dev" / "templates" / "spec.md").write_text("test-template")
    (tmp_path / "package" / "scripts").mkdir()
    (tmp_path / "package" / "scripts" / "validate.py").write_text("# validate")
    (tmp_path / "package" / "AGENTS.md").write_text("# Agents")
    monkeypatch.setenv("SPEC_KITTY_TEMPLATE_ROOT", str(missions))

    templates_dir = tmp_path / "command-templates"
    for command in PROMPT_DRIVEN_COMMANDS:
        (templates_dir / command).mkdir(parents=True)
        (templates_dir / command / "prompt.md").write_text(f"---\ndescription: {command}\n---\n# {command}\n", encoding="utf-8")
    monkeypatch.setattr(agent_commands, "_get_command_templates_dir", lambda: templates_dir)

    skill_dir = tmp_path / "doctrine_skills" / "spec-kitty-test-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("---\nname: spec-kitty-test-skill\ndescription: test\n---\n# test\n", encoding="utf-8")
    registry = SkillRegistry(tmp_path / "doctrine_skills")
    monkeypatch.setattr(agent_skills, "_discover_registry", lambda: registry)


def _make_home_read_only(home: Path, monkeypatch: pytest.MonkeyPatch, err: int = errno.EROFS) -> None:
    """Fail every lock and asset write under *home* the way a read-only mount does."""
    real_lock = asset_preparation.machine_file_lock
    real_write = asset_preparation._write_asset

    def _refuse(path: Path) -> None:
        if path == home or home in path.parents:
            raise OSError(err, os.strerror(err), str(path))

    def fake_lock(path: Path, *args: object, **kwargs: object) -> object:
        _refuse(Path(path))
        return real_lock(path, *args, **kwargs)

    def fake_write(write: asset_preparation.AssetWrite) -> None:
        _refuse(write.effect.destination)
        real_write(write)

    monkeypatch.setattr(asset_preparation, "machine_file_lock", fake_lock)
    monkeypatch.setattr(asset_preparation, "_write_asset", fake_write)


@pytest.fixture()
def no_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    cwd = tmp_path / "outside-project"
    cwd.mkdir()
    monkeypatch.chdir(cwd)
    return cwd


class TestOwnersNameTheUnwritableHome:
    """Each startup owner reports an unwritable home as one named error code."""

    @pytest.mark.parametrize("owner", sorted(_ENTRY_POINTS))
    def test_empty_read_only_home_raises_named_error_not_traceback(
        self, owner: str, fake_home: Path, fake_assets: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _make_home_read_only(fake_home, monkeypatch)

        with pytest.raises(StartupAssetError) as exc_info:
            _ENTRY_POINTS[owner]()

        assert exc_info.value.code == UNWRITABLE_HOME_CODE
        assert exc_info.value.owner_key == _OWNER_KEYS[owner]

    @pytest.mark.parametrize("owner", sorted(_ENTRY_POINTS))
    def test_set_up_home_with_something_to_refresh_raises_named_error(
        self, owner: str, fake_home: Path, fake_assets: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _ENTRY_POINTS[owner]()  # set the home up while it is writable
        inventory = fake_home / ".kittify" / "cache" / f"{_OWNER_KEYS[owner]}-assets.json"
        managed = sorted(json.loads(inventory.read_text())["entries"])
        target = next(p for p in (Path(e) for e in managed) if p.is_file() and p.suffix != ".lock")
        target.unlink()  # a deleted copy: the next start has something to write
        _make_home_read_only(fake_home, monkeypatch, err=errno.EACCES)

        with pytest.raises(StartupAssetError) as exc_info:
            _ENTRY_POINTS[owner]()

        assert exc_info.value.code == UNWRITABLE_HOME_CODE

    def test_unwritable_error_hint_names_the_remedy(self) -> None:
        error = asset_preparation.startup_asset_error(
            "global_skills", (asset_preparation.Diagnostic(UNWRITABLE_HOME_CODE, "global_skills", "error", "denied"),)
        )
        assert "not writable" in str(error)
        assert error.owner_key == "global_skills"


class TestIsUnwritableHomeError:
    @pytest.mark.parametrize("err", [errno.EACCES, errno.EPERM, errno.EROFS])
    def test_permission_and_read_only_errnos(self, err: int) -> None:
        assert is_unwritable_home_error(OSError(err, os.strerror(err)))

    def test_permission_error_without_errno(self) -> None:
        assert is_unwritable_home_error(PermissionError("denied"))

    @pytest.mark.parametrize("error", [OSError(errno.ENOSPC, "full"), OSError("no errno"), ValueError("x")])
    def test_other_failures_are_not_unwritable(self, error: Exception) -> None:
        assert not is_unwritable_home_error(error)


class TestPrepareStartupAssets:
    """The startup driver degrades only the unwritable-home class."""

    def _unwritable(self, owner_key: str) -> Callable[[], None]:
        def fail() -> None:
            raise StartupAssetError(f"{owner_key}: denied", path=None, code=UNWRITABLE_HOME_CODE, owner_key=owner_key)

        return fail

    def test_all_owners_run_and_one_warning_names_them(self, caplog: pytest.LogCaptureFixture) -> None:
        ran: list[str] = []
        caplog.set_level(logging.WARNING)

        prepare_startup_assets(
            [
                self._unwritable("runtime_bootstrap"),
                lambda: ran.append("skills"),
                self._unwritable("slash_commands"),
            ]
        )

        assert ran == ["skills"]
        warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert len(warnings) == 1
        message = warnings[0].getMessage()
        assert "runtime assets" in message
        assert "agent commands" in message
        assert "agent skills" not in message
        assert "runtime_bootstrap: denied" in message

    def test_raw_unwritable_os_error_is_degraded(self, caplog: pytest.LogCaptureFixture) -> None:
        def fail() -> None:
            raise PermissionError(errno.EACCES, "Permission denied", "/home/x/.spec-kitty-cold-install")

        caplog.set_level(logging.WARNING)
        prepare_startup_assets([fail])
        assert "Permission denied" in caplog.text

    def test_other_startup_asset_errors_stay_fatal(self) -> None:
        def torn() -> None:
            raise StartupAssetError("torn", path=None, code="asset_torn_read")

        with pytest.raises(StartupAssetError):
            prepare_startup_assets([torn])

    def test_other_os_errors_stay_fatal(self) -> None:
        def full() -> None:
            raise OSError(errno.ENOSPC, "No space left on device")

        with pytest.raises(OSError):
            prepare_startup_assets([full])

    def test_no_failure_no_warning(self, caplog: pytest.LogCaptureFixture) -> None:
        caplog.set_level(logging.WARNING)
        prepare_startup_assets([lambda: None])
        assert caplog.records == []


class TestCliRunsWithReadOnlyHome:
    """Through the real root callback and error hook (never ``CliRunner``,
    which bypasses ``_run_app_with_error_hook``)."""

    @pytest.fixture(autouse=True)
    def _fresh_app(self, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
        # _get_app() memoizes a process-global app narrowed to sys.argv.
        monkeypatch.setattr(specify_cli, "_APP", None)
        yield

    @pytest.mark.parametrize("argv", [["agent", "--help"], ["doctor", "--help"], ["events", "--help"]])
    def test_subcommand_help_runs_and_warns_once(
        self,
        argv: list[str],
        fake_home: Path,
        fake_assets: None,
        no_project: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        _make_home_read_only(fake_home, monkeypatch)
        monkeypatch.setattr(sys, "argv", ["spec-kitty", *argv])
        caplog.set_level(logging.WARNING)

        with pytest.raises(SystemExit) as exc_info:
            specify_cli._run_app_with_error_hook(specify_cli._get_app(), json_mode=False)

        assert exc_info.value.code in (0, None)
        captured = capsys.readouterr()
        assert "Usage:" in captured.out
        assert "Traceback" not in captured.out + captured.err
        unwritable = [r for r in caplog.records if "not writable" in r.getMessage()]
        assert len(unwritable) == 1

    def test_json_command_runs_and_keeps_stdout_json(
        self,
        fake_home: Path,
        fake_assets: None,
        no_project: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """The requested command's own result reaches stdout, not a startup error."""
        _make_home_read_only(fake_home, monkeypatch)
        monkeypatch.setattr(sys, "argv", ["spec-kitty", "agent", "tasks", "status", "--json"])

        with pytest.raises(SystemExit):
            specify_cli._run_app_with_error_hook(specify_cli._get_app(), json_mode=True)

        payload = json.loads(capsys.readouterr().out)
        assert payload.get("kind") != "StartupAssetError"
        assert payload["error"]["code"] == "mission_required"


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX directory permissions")
@pytest.mark.skipif(hasattr(os, "geteuid") and os.geteuid() == 0, reason="chmod does not bind uid 0")
class TestReadOnlyHomeSubprocess:
    """A real ``chmod 0o555`` empty home, driving the installed console entry."""

    @pytest.mark.parametrize(
        ("args", "expect_exit"),
        [
            (["--version"], 0),
            (["--help"], 0),
            (["agent", "--help"], 0),
            (["agent", "tasks", "status", "--json"], 1),  # the command's own mission_required
        ],
    )
    def test_command_runs(self, args: list[str], expect_exit: int, tmp_path: Path) -> None:
        home = tmp_path / "home"
        home.mkdir(mode=0o555)
        cwd = tmp_path / "cwd"
        cwd.mkdir()
        env = {k: v for k, v in os.environ.items() if not k.startswith(("SPEC_KITTY_HOME", "XDG_"))}
        env["HOME"] = str(home)
        try:
            result = subprocess.run(
                [sys.executable, "-m", "specify_cli", *args],
                cwd=cwd,
                env=env,
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
            )
        finally:
            home.chmod(0o755)

        assert "Traceback" not in result.stderr, result.stderr
        assert result.returncode == expect_exit, result.stdout + result.stderr
        if args[-1] == "--json":
            assert json.loads(result.stdout)["error"]["code"] == "mission_required"
