"""#6224 regression: the init console sink must not leak across tests.

``specify_cli.cli.commands.init`` keeps a module-global ``_console`` that
``register_init_command`` binds. A test that registers init on its own throwaway
app with a private console mutates that global; a later test that drives the
CACHED real app (``from specify_cli import app``) never re-registers, so without
isolation it inherits the previous test's dead buffer and its output is written
there instead of to ``CliRunner``'s captured stream -- the order-dependent
``default-preset-missing`` empty-output flake (#6210/#6211/#6212, owner #6224).

These two tests run in order (same file -> same xdist worker under
``--dist loadfile``): the first installs the pollution; the second proves the
autouse ``_isolate_init_console_seam`` fixture (``tests/conftest.py``) restored
the canonical seam so the cached real app's refusal is captured again. Remove
the fixture and the second test goes red -- that is the red-first witness.
"""

from __future__ import annotations

import contextlib
import io
import shutil
from pathlib import Path

import pytest
from typer import Typer
from typer.testing import CliRunner

from specify_cli.cli.commands import init as init_module
from specify_cli.cli.commands.init import register_init_command
from specify_cli.cli.console import CliConsole, console

pytestmark = [pytest.mark.integration]

_BUILTIN_PACK = Path(__file__).resolve().parents[4] / "packs" / "built-in"


def test_a_foreign_registration_pollutes_the_init_console_global() -> None:
    """A throwaway-app registration rebinds the shared module-global (the polluter)."""
    # Build + cache the real app first (the full suite does this long before any
    # init test; done here too so the pair reproduces in isolation), so the later
    # invocation reuses the cached app rather than re-registering the console.
    from specify_cli import app as _real_app  # noqa: F401

    polluter = CliConsole(file=io.StringIO())
    register_init_command(
        Typer(),
        console=polluter,
        show_banner=lambda: None,
        ensure_executable_scripts=lambda path, tracker=None: None,
    )
    assert init_module._console is polluter


def test_b_cached_app_init_error_is_captured_despite_prior_pollution(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The cached real app's DEFAULT_PRESET_MISSING refusal still reaches the
    captured output after a prior test polluted the init console global."""
    assert init_module._console is console, "the autouse fixture must restore the canonical seam"

    packs_root = tmp_path / "packs-root"
    shutil.copytree(_BUILTIN_PACK, packs_root / "built-in")
    monkeypatch.setenv("SPEC_KITTY_PACKS_ROOT", str(packs_root))
    (packs_root / "built-in" / "presets" / "default.yaml").unlink()

    from specify_cli import app

    work = tmp_path / "work"
    work.mkdir()
    with contextlib.chdir(work):
        result = CliRunner().invoke(app, ["init", "p", "--ai", "claude", "--non-interactive"], catch_exceptions=True)

    assert result.exit_code == 1, f"exit={result.exit_code}\n{result.output}"
    assert "Error (DEFAULT_PRESET_MISSING):" in result.output, f"output was {result.output!r}"
