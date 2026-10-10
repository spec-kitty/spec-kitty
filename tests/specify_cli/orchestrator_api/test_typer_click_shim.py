"""Regression for spec-kitty#713: the typer/click exception shim must survive typer 0.27+.

typer 0.27.x vendors click as ``typer._click`` but its ``_click.exceptions`` module
defines only ``UsageError`` — no ``Abort``, no ``Exit`` — and raises typer's own public
``typer.Abort``/``typer.Exit`` instead.  The previous shim evaluated
``_CLICK.exceptions.Abort`` eagerly as a ``getattr`` default, which raised
``AttributeError`` at import time and broke every fresh-venv wheel install.
"""

from __future__ import annotations

import json
import tomllib
import types
from pathlib import Path

import click
import pytest
import typer
from packaging.requirements import Requirement
from typer.testing import CliRunner

from specify_cli.orchestrator_api import commands as shim
from specify_cli.orchestrator_api.commands import _JSONErrorGroup

pytestmark = [pytest.mark.fast, pytest.mark.unit]


def _typer_027_like_click_module() -> types.SimpleNamespace:
    """A stand-in for ``typer._click`` as shipped in typer 0.27.2."""
    return types.SimpleNamespace(exceptions=types.SimpleNamespace(UsageError=click.UsageError))  # noqa: TID251 — test names the click universe of the command it built itself, or deliberately the standalone-click spelling


def test_vendored_lookup_returns_none_when_typer_027_omits_abort_and_exit(monkeypatch):
    monkeypatch.setattr(shim.typer_core, "_click", _typer_027_like_click_module(), raising=False)

    assert shim._vendored_click_exception("UsageError") is click.UsageError  # noqa: TID251 — test names the click universe of the command it built itself, or deliberately the standalone-click spelling
    assert shim._vendored_click_exception("Abort") is None
    assert shim._vendored_click_exception("Exit") is None


def test_vendored_lookup_returns_none_without_a_vendored_click(monkeypatch):
    monkeypatch.delattr(shim.typer_core, "_click", raising=False)

    assert shim._vendored_click_exception("UsageError") is None


def test_vendored_lookup_ignores_non_exception_attributes(monkeypatch):
    bogus = types.SimpleNamespace(exceptions=types.SimpleNamespace(Abort="not a class"), Abort=42)
    monkeypatch.setattr(shim.typer_core, "_click", bogus, raising=False)

    assert shim._vendored_click_exception("Abort") is None


def test_exception_classes_drops_none_and_duplicates():
    assert shim._exception_classes(None) == ()
    # Two genuinely distinct classes: on typer <= 0.25 ``typer.Abort`` *is* ``click.Abort``.
    assert shim._exception_classes(click.Abort, None, click.Abort, click.UsageError) == (  # noqa: TID251 — test names the click universe of the command it built itself, or deliberately the standalone-click spelling
        click.Abort,  # noqa: TID251 — test names the click universe of the command it built itself, or deliberately the standalone-click spelling
        click.UsageError,  # noqa: TID251 — test names the click universe of the command it built itself, or deliberately the standalone-click spelling
    )


def test_catch_tuples_always_carry_typers_public_surface():
    """Whatever typer version is installed, typer's own classes must be caught."""
    assert typer.Abort in shim._CLICK_ABORTS
    assert typer.Exit in shim._EXIT
    assert click.UsageError in shim._CLICK_USAGE_ERRORS  # noqa: TID251 — test names the click universe of the command it built itself, or deliberately the standalone-click spelling
    assert click.Abort in shim._CLICK_ABORTS  # noqa: TID251 — test names the click universe of the command it built itself, or deliberately the standalone-click spelling
    for group in (shim._CLICK_USAGE_ERRORS, shim._CLICK_ABORTS, shim._EXIT):
        assert all(isinstance(cls, type) and issubclass(cls, BaseException) for cls in group)


def _group_app() -> typer.Typer:
    app = typer.Typer(name="shim-probe", no_args_is_help=False, cls=_JSONErrorGroup)

    @app.command()
    def abort() -> None:
        raise typer.Abort()

    @app.command()
    def leave() -> None:
        raise typer.Exit(code=7)

    return app


def test_public_typer_abort_becomes_json_envelope():
    result = CliRunner().invoke(_group_app(), ["abort"])

    assert result.exit_code == 2
    envelope = json.loads(result.output.strip())
    assert envelope["success"] is False
    assert envelope["data"]["message"] == "Command aborted"


def test_public_typer_exit_code_is_preserved():
    result = CliRunner().invoke(_group_app(), ["leave"])

    assert result.exit_code == 7


# --- #3794: the dependency must be bounded, and the shim defined once -----
#
# A fresh install once resolved typer 0.27.2 against an unbounded
# ``typer>=0.24.1`` and died at import time (the bug this file's header
# describes).  Two structural regressions guard the fix: the declared
# requirement carries an upper bound the locked version satisfies, and the
# shim block is defined exactly once (a merge on main once pasted the whole
# block twice — the second, silently-winning copy is exactly the hazard the
# dedup guards against).

_REPO_ROOT = Path(__file__).resolve().parents[3]


def _typer_requirement() -> Requirement:
    data = tomllib.loads((_REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    requirements = [Requirement(dep) for dep in data["project"]["dependencies"]]
    typer_requirements = [req for req in requirements if req.name == "typer"]
    assert len(typer_requirements) == 1
    return typer_requirements[0]


def test_typer_requirement_carries_an_upper_bound():
    """#3794: an unbounded ``typer>=0.24.1`` let fresh resolves break at import."""
    requirement = _typer_requirement()

    upper_bounds = [spec for spec in requirement.specifier if spec.operator in ("<", "<=", "==", "===", "~=")]
    assert upper_bounds, "typer requirement must bound the range above (#3794)"


def test_locked_typer_satisfies_the_declared_requirement():
    """The uv.lock pin stays inside the bounded range (lock-parity, T001)."""
    requirement = _typer_requirement()
    lock = tomllib.loads((_REPO_ROOT / "uv.lock").read_text(encoding="utf-8"))
    locked = next(entry["version"] for entry in lock["package"] if entry.get("name") == "typer")

    assert requirement.specifier.contains(locked, prereleases=True), f"uv.lock pins typer {locked}, outside the declared {requirement.specifier}"


def test_shim_block_is_defined_exactly_once():
    """The shim helpers/constants exist once — a merge once duplicated them."""
    source = Path(shim.__file__).read_text(encoding="utf-8")

    for name in ("_vendored_click_exception", "_exception_classes"):
        assert source.count(f"def {name}(") == 1, f"{name} is defined more than once"
    for name in ("_CLICK_USAGE_ERRORS", "_CLICK_ABORTS", "_EXIT"):
        assert source.count(f"\n{name} = ") == 1, f"{name} is assigned more than once"
