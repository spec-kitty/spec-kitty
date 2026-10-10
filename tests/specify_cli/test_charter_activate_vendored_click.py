"""``charter activate``'s preset-only flag check works in both click eras.

typer 0.26+ vendors its own click (``typer._click``), so the context hands back
a ``ParameterSource`` from a different enum than ``click.core.ParameterSource``.
An identity comparison flagged ``--pack``/``--force``/``--json`` as given on
every positional ``charter activate KIND ARTIFACT_ID`` and refused the command.
The lockfile pins typer 0.24, so these tests stand in a foreign enum instead of
depending on the installed typer.
"""

from __future__ import annotations

import enum

import pytest

from specify_cli.cli.commands.charter.activate import _check_preset_flags

pytestmark = [pytest.mark.unit, pytest.mark.fast]


class _ForeignParameterSource(enum.Enum):
    """Same member names as click's enum, no shared identity (the vendored era)."""

    COMMANDLINE = enum.auto()
    ENVIRONMENT = enum.auto()
    DEFAULT = enum.auto()
    DEFAULT_MAP = enum.auto()
    PROMPT = enum.auto()


class _UsageError(Exception):
    pass


class _FakeContext:
    def __init__(self, sources: dict[str, _ForeignParameterSource]) -> None:
        self._sources = sources

    def get_parameter_source(self, name: str) -> _ForeignParameterSource:
        return self._sources.get(name, _ForeignParameterSource.DEFAULT)

    def fail(self, message: str) -> None:
        raise _UsageError(message)


def test_defaults_from_a_foreign_enum_are_not_reported_as_given() -> None:
    _check_preset_flags(_FakeContext({}), preset=None, positional=True, cascade=None)  # type: ignore[arg-type]


def test_a_flag_typed_on_the_command_line_is_refused_through_ctx_fail() -> None:
    ctx = _FakeContext({"pack": _ForeignParameterSource.COMMANDLINE})
    with pytest.raises(_UsageError, match=r"^--pack only applies with --preset\.$"):
        _check_preset_flags(ctx, preset=None, positional=True, cascade=None)  # type: ignore[arg-type]


def test_preset_with_a_positional_is_refused_through_ctx_fail() -> None:
    with pytest.raises(_UsageError, match="cannot be combined with a positional"):
        _check_preset_flags(_FakeContext({}), preset="default", positional=True, cascade=None)  # type: ignore[arg-type]
