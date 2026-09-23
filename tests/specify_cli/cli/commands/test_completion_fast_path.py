"""Tests for the shell-completion fast path (``specify_cli.completion``).

These guard the mission's responsiveness contract (NFR-001 / SC-003 — completion
within 500 ms) together with correctness (FR-001..FR-004, NFR-002, NFR-004) and
shell safety (NFR-003 / SC-004).  The fast path serves command/subcommand names
from a pre-generated manifest instead of importing the whole CLI; these tests
prove the manifest stays in sync with the real CLI and that the emitted output
is byte-for-byte identical to the full application.
"""

from __future__ import annotations

import contextlib
import io
import os
import subprocess
import sys
from pathlib import Path

import pytest

from specify_cli import completion

pytestmark = [pytest.mark.integration]

# Modules whose import cost is exactly what the fast path exists to avoid.  If
# any of these load while serving a command-name completion, the latency
# contract is at risk and this is a regression.
_HEAVY_MODULES = (
    "specify_cli.cli.commands.init",
    "specify_cli.cli.commands.merge",
    "specify_cli.cli.commands.upgrade",
    "specify_cli.upgrade",
    "specify_cli.status.reducer",
)


def _drive(command: object, instruction: str, *, line: str) -> str:
    """Run Typer completion against ``command`` and capture its stdout.

    ``line`` is the completion command line (e.g. ``"spec-kitty agent "``).
    Bash reads ``COMP_WORDS``/``COMP_CWORD``; zsh/fish read
    ``_TYPER_COMPLETE_ARGS``.  We set all of them so any shell instruction works.
    """
    from typer._completion_classes import completion_init
    from typer.completion import shell_complete

    completion_init()
    saved = {key: os.environ.get(key) for key in ("COMP_WORDS", "COMP_CWORD", "_TYPER_COMPLETE_ARGS")}
    try:
        os.environ["COMP_WORDS"] = line
        os.environ["COMP_CWORD"] = str(len(line.split()))
        os.environ["_TYPER_COMPLETE_ARGS"] = line
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            shell_complete(command, {}, completion.PROG_NAME, completion.COMPLETE_VAR, instruction)
        return buffer.getvalue()
    finally:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _real_command() -> object:
    import specify_cli
    from typer.main import get_command

    return get_command(specify_cli._build_app())


def _fast_command() -> object:
    return completion._build_command_tree(completion._load_manifest())


def _fast_command_for_env() -> object:
    # Mirror the real app: the SaaS-gated surface depends on the environment,
    # and Typer's completion classes read os.environ directly.
    return _fast_command()


# --------------------------------------------------------------------------- #
# Drift protection (Edge case: "remain accurate when commands are added,
# removed, or renamed").
# --------------------------------------------------------------------------- #


def test_manifest_matches_live_cli(monkeypatch: pytest.MonkeyPatch) -> None:
    # The committed manifest is generated with SaaS sync enabled so it contains
    # the SaaS-gated commands; build the live app the same way to compare.
    monkeypatch.setenv("SPEC_KITTY_ENABLE_SAAS_SYNC", "1")

    live = completion.generate_manifest()
    committed = completion._load_manifest()

    assert live == committed, "completion manifest is stale; regenerate with `SPEC_KITTY_ENABLE_SAAS_SYNC=1 python -m specify_cli.completion --regenerate`"


# --------------------------------------------------------------------------- #
# Byte-identical parity with the full application (FR-001..FR-004, NFR-004).
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "line",
    [
        "spec-kitty ",  # FR-001 top-level
        "spec-kitty agent ",  # FR-003 nested (group 1)
        "spec-kitty agent mission ",  # FR-003 deeper nesting
        "spec-kitty doctor ",  # FR-004 scoped to a different group
    ],
)
@pytest.mark.parametrize("instruction", ["complete_bash", "complete_zsh"])
def test_fast_path_output_matches_full_app(line: str, instruction: str) -> None:
    real = _drive(_real_command(), instruction, line=line)
    fast = _drive(_fast_command_for_env(), instruction, line=line)

    assert fast == real
    assert fast.strip(), "expected non-empty completion output"


def test_top_level_completion_covers_all_user_facing_commands() -> None:
    # NFR-002: 100% of user-facing top-level commands/groups.
    real = {line for line in _drive(_real_command(), "complete_bash", line="spec-kitty ").splitlines() if line}
    fast = {line for line in _drive(_fast_command_for_env(), "complete_bash", line="spec-kitty ").splitlines() if line}

    assert fast == real


def test_nested_completion_is_scoped_to_group() -> None:
    # FR-004: nested suggestions never leak commands from another group.
    agent = set(_drive(_fast_command(), "complete_bash", line="spec-kitty agent ").split())

    assert {"config", "mission", "tasks"}.issubset(agent)
    assert "doctor" not in agent  # top-level command must not appear under `agent`


def test_empty_manifest_builds_root_group() -> None:
    from typer.core import TyperGroup

    command = completion._build_command_tree({})

    assert isinstance(command, TyperGroup)


# --------------------------------------------------------------------------- #
# Fallback gating: option tokens must defer to the full application.
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "env",
    [
        {},  # completion not requested
        {"_SPEC_KITTY_COMPLETE": "complete_bash", "COMP_WORDS": "spec-kitty -", "COMP_CWORD": "1"},
        {"_SPEC_KITTY_COMPLETE": "complete_bash", "COMP_WORDS": "spec-kitty merge --", "COMP_CWORD": "2"},
        {"_SPEC_KITTY_COMPLETE": "complete_zsh", "_TYPER_COMPLETE_ARGS": "spec-kitty init --here"},
    ],
)
def test_fast_path_defers_for_options_or_no_request(env: dict[str, str]) -> None:
    assert completion.maybe_run_completion(["spec-kitty"], env) is None


def test_fast_path_handles_command_name_request(monkeypatch: pytest.MonkeyPatch) -> None:
    # Typer's completion classes read os.environ directly, so set it for real.
    monkeypatch.setenv("_SPEC_KITTY_COMPLETE", "complete_bash")
    monkeypatch.setenv("COMP_WORDS", "spec-kitty ")
    monkeypatch.setenv("COMP_CWORD", "1")

    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        code = completion.maybe_run_completion(["spec-kitty"], os.environ)

    assert code == 0
    assert "agent" in buffer.getvalue().split()


# --------------------------------------------------------------------------- #
# Latency, no-heavy-import, and shell-safety contracts (subprocess level).
# --------------------------------------------------------------------------- #


def _completion_env(tmp_path: Path, line: str, instruction: str = "complete_bash") -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        {
            "HOME": str(tmp_path / "home"),
            "XDG_CONFIG_HOME": str(tmp_path / "config"),
            "SPEC_KITTY_NO_UPGRADE_CHECK": "1",
            "COMP_WORDS": line,
            "COMP_CWORD": str(len(line.split())),
            "_SPEC_KITTY_COMPLETE": instruction,
        }
    )
    return env


def test_completion_fast_path_avoids_heavy_imports(tmp_path: Path) -> None:
    # Proves the fast path generates candidates without constructing the full
    # CLI — the structural guarantee behind the latency contract.
    script = (
        "import os, sys\n"
        "from specify_cli.completion import maybe_run_completion\n"
        "rc = maybe_run_completion(['spec-kitty'], os.environ)\n"
        f"heavy = [m for m in {_HEAVY_MODULES!r} if m in sys.modules]\n"
        "sys.stderr.write('RC=' + repr(rc) + ' HEAVY=' + repr(heavy))\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        env=_completion_env(tmp_path, "spec-kitty "),
        text=True,
        capture_output=True,
        timeout=30,
    )

    assert "RC=0" in result.stderr, result.stderr
    assert "HEAVY=[]" in result.stderr, result.stderr
    assert "agent" in result.stdout.split()


def test_generate_manifest_ignores_ambient_argv_narrowing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Landing fold (PR #4992): ``generate_manifest()`` must always capture the
    FULL command tree, regardless of whatever ``sys.argv`` happens to be live
    at call time.

    ``register_commands()`` reads the global ``sys.argv`` to decide lazy vs
    full registration (WP05's single-leaf fast path), so ``_build_app()``
    returns an argv-dependent tree. Pin ``sys.argv`` to a value that resolves
    to a single leaf command (``spec-kitty doctor``) -- the same shape a real
    ``spec-kitty doctor ...`` invocation would leave behind -- and prove the
    manifest generator still returns every top-level command, not just the
    one argv would have lazily registered.
    """
    saved_argv = sys.argv[:]
    sys.argv = ["spec-kitty", "doctor"]
    try:
        manifest = completion.generate_manifest()
    finally:
        sys.argv = saved_argv

    top_level_commands = set(manifest.get("commands", {}))
    assert "doctor" in top_level_commands
    assert "init" in top_level_commands, "manifest was narrowed to the single leaf argv resolved to, not the full command tree"
    assert len(top_level_commands) > 10, f"manifest looks narrowed: only {sorted(top_level_commands)}"


def test_completion_does_not_mutate_project_files(tmp_path: Path) -> None:
    # NFR-003 / SC-004: completion candidate generation creates/modifies nothing.
    project = tmp_path / "project"
    project.mkdir()
    before = set(project.rglob("*"))

    result = subprocess.run(
        [sys.executable, "-m", "specify_cli"],
        cwd=project,
        env=_completion_env(tmp_path, "spec-kitty "),
        text=True,
        capture_output=True,
        timeout=30,
    )

    assert result.returncode == 0, result.stderr
    assert set(project.rglob("*")) == before
