"""Unit tests for tool surface contract enumerations."""

from __future__ import annotations

from enum import StrEnum

from specify_cli.tool_surface.enums import (
    ActivationMode,
    InstallScope,
    RequiredPolicy,
    SourceKind,
    ToolSurfaceKind,
)

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.fast]

ALL_ENUMS = [
    ToolSurfaceKind,
    SourceKind,
    InstallScope,
    ActivationMode,
    RequiredPolicy,
]


def test_all_enums_are_str_enum() -> None:
    for enum_cls in ALL_ENUMS:
        assert issubclass(enum_cls, StrEnum)


def test_surface_kind_values_are_distinct_strings() -> None:
    values = [member.value for member in ToolSurfaceKind]
    assert all(isinstance(value, str) for value in values)
    assert len(values) == len(set(values))


def test_required_policy_values_are_distinct_strings() -> None:
    values = [member.value for member in RequiredPolicy]
    assert all(isinstance(value, str) for value in values)
    assert len(values) == len(set(values))


def test_str_enum_compares_equal_to_raw_string() -> None:
    assert ToolSurfaceKind.COMMAND_SKILL == "command_skill"
    assert RequiredPolicy.RESEARCH_GAP == "research_gap"


def test_each_enum_has_distinct_member_values() -> None:
    for enum_cls in ALL_ENUMS:
        values = [member.value for member in enum_cls]
        assert len(values) == len(set(values))
