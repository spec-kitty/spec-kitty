"""#3457: direct callers drive ``consolidate`` through one ``ConsolidateOptions`` object.

The Typer command takes 19 ``typer.Option`` parameters. A direct Python call
that omits one used to receive the ``OptionInfo`` sentinel as a live value (the
#3456 landing-pass failure: ``'OptionInfo' object has no attribute 'strip'``).
``ConsolidateOptions`` carries real defaults, and these pins make a new CLI
option without a matching field fail here, in one place.
"""

from __future__ import annotations

import dataclasses
import inspect

import pytest
from typer.models import OptionInfo

from specify_cli.cli.commands import consolidate as consolidate_mod
from specify_cli.cli.commands.consolidate import ConsolidateOptions

pytestmark = pytest.mark.fast


def _typer_parameters() -> dict[str, inspect.Parameter]:
    return dict(inspect.signature(inspect.unwrap(consolidate_mod.consolidate)).parameters)


def test_fields_mirror_the_typer_command_parameters() -> None:
    assert [field.name for field in dataclasses.fields(ConsolidateOptions)] == list(_typer_parameters())


def test_field_defaults_equal_the_cli_defaults() -> None:
    defaults = {field.name: field.default for field in dataclasses.fields(ConsolidateOptions)}
    for name, parameter in _typer_parameters().items():
        option = parameter.default
        assert isinstance(option, OptionInfo), f"consolidate({name}=...) is no longer a typer.Option"
        assert defaults[name] == option.default, f"{name}: options default {defaults[name]!r} != CLI default {option.default!r}"
