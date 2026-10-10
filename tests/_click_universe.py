"""The click classes typer actually builds its commands from.

typer 0.26+ vendors click (``typer._click``) and its commands no longer share
any class with the standalone ``click`` package: ``isinstance(cmd, click.Group)``
is False for a typer-built group, and ``except click.UsageError`` does not catch
what a typer command raises. typer <= 0.25 builds on the real ``click``.

Tests that inspect, walk, or parse typer-built commands therefore take their
click classes from here, never from ``import click``. Everything is derived from
typer's own public classes (``typer.core``), so one authority serves both eras
and no private ``typer._click`` name is imported.

* ``Group`` / ``Option`` / ``Argument`` are typer's own subclasses (typer 0.27's
  vendored click has no ``Group`` and its ``Option`` is not a ``Parameter``
  subclass of anything standalone); they are what typer instantiates.
* ``Command`` / ``Context`` / ``Parameter`` / ``ParameterSource`` and the
  exceptions are the base-click universe those subclasses derive from.

Tests that deliberately exercise standalone click (no typer objects involved)
may keep ``import click``.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

import typer.core as _typer_core

Group = _typer_core.TyperGroup
Option = _typer_core.TyperOption
Argument = _typer_core.TyperArgument
# Concrete command class for *constructing* test commands: the vendored base
# ``Command`` is abstract, so only isinstance checks use ``Command``.
LeafCommand = _typer_core.TyperCommand


def _universe_root() -> Any:
    """The package (``click`` or ``typer._click``) typer's commands derive from."""
    for base in _typer_core.TyperCommand.__mro__:
        if base.__name__ == "Command" and not base.__module__.startswith("typer.core"):
            return import_module(base.__module__.rsplit(".", 1)[0])
    raise RuntimeError("could not locate the click universe typer derives from")  # pragma: no cover


_root = _universe_root()
_core = import_module(f"{_root.__name__}.core")
_exceptions = import_module(f"{_root.__name__}.exceptions")
_types = import_module(f"{_root.__name__}.types")

Command = _core.Command
Context = _core.Context
Parameter = _core.Parameter
ParameterSource = _core.ParameterSource
UsageError = _exceptions.UsageError
NoSuchOption = _exceptions.NoSuchOption
BoolParamType = _types.BoolParamType
