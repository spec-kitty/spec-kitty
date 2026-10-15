"""Tests for entrypoint-level JSON-mode detection."""

from __future__ import annotations

import pytest

import specify_cli

pytestmark = [pytest.mark.fast]


def test_argv_requests_json_mode_detects_json_flag() -> None:
    argv = ["spec-kitty", "agent", "mission", "finalize-tasks", "--mission", "001-x", "--json"]

    assert specify_cli._argv_requests_json_mode(argv) is True


def test_argv_requests_json_mode_ignores_json_as_option_value() -> None:
    argv = ["spec-kitty", "tracker", "search", "--provider", "linear", "--query", "--json"]

    assert specify_cli._argv_requests_json_mode(argv) is False


def test_argv_requests_json_mode_detects_second_json_after_value() -> None:
    argv = [
        "spec-kitty",
        "tracker",
        "search",
        "--provider",
        "linear",
        "--query",
        "--json",
        "--json",
    ]

    assert specify_cli._argv_requests_json_mode(argv) is True


@pytest.mark.parametrize(
    ("args", "expected"),
    [
        (["doctor", "skills", "--json"], True),
        (("charter", "status", "--json"), True),
        (["agent", "tasks", "status", "--mission", "--json"], False),
        (["charter", "status", "--", "--json"], False),
        (["--json"], True),
        ([], False),
    ],
    ids=["list", "tuple", "option-value", "after-double-dash", "first-element-not-skipped", "empty"],
)
def test_args_request_json_mode_reads_args_after_the_program_name(args: list[str] | tuple[str, ...], expected: bool) -> None:
    assert specify_cli._args_request_json_mode(args) is expected


def test_argv_requests_json_mode_skips_the_program_name() -> None:
    """The argv form drops argv[0]; only the args form reads the first element."""
    assert specify_cli._argv_requests_json_mode(["--json"]) is False
    assert specify_cli._argv_requests_json_mode(["spec-kitty", "--json"]) is True
