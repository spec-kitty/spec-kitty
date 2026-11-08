"""``charter context --include`` accepts a repeated selector and refuses commas (#3261).

The flag used to be a scalar ``str``, so ``--include a --include b`` silently kept
only ``b`` (data loss, no warning) and the comma form resolved the whole tail as
one bogus id. The flag is now repeatable — one ``<kind>:<id>`` per occurrence — and
a comma-containing selector fails loudly with the correct syntax instead of the
confusing "No <kind> found for selector '...'" error.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from charter.activation.context import build_charter_context_include
from specify_cli.cli.commands.charter import app

pytestmark = pytest.mark.fast

runner = CliRunner()

_FIRST = "agent-profile:reviewer-renata"
_SECOND = "agent-profile:architect-alphonso"


def _project(tmp_path: Path) -> Path:
    (tmp_path / ".kittify" / "charter").mkdir(parents=True)
    return tmp_path


def _invoke(project: Path, builder, args: list[str]):
    with (
        patch("specify_cli.cli.commands.charter.find_repo_root", return_value=project),
        patch("charter.drg.resolve_org_roots", return_value=[]),
        patch("charter.activation.context.build_charter_context_include", side_effect=builder),
    ):
        return runner.invoke(app, ["context", *args])


def test_repeated_include_renders_every_selector(tmp_path: Path) -> None:
    """Both selectors are fetched; neither is silently dropped."""
    project = _project(tmp_path)
    calls: list[str] = []

    def builder(_root: Path, selector: str, **_kwargs) -> str:
        calls.append(selector)
        return f"BLOCK {selector}"

    result = _invoke(project, builder, ["--include", _FIRST, "--include", _SECOND])

    assert result.exit_code == 0, result.output
    assert calls == [_FIRST, _SECOND]
    assert "BLOCK agent-profile:reviewer-renata" in result.output
    assert "BLOCK agent-profile:architect-alphonso" in result.output


def test_repeated_include_json_envelope_lists_every_selector(tmp_path: Path) -> None:
    project = _project(tmp_path)

    result = _invoke(
        project,
        lambda _root, selector, **_kwargs: f"BLOCK {selector}",
        ["--include", _FIRST, "--include", _SECOND, "--json"],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["include"] == [_FIRST, _SECOND]
    assert "BLOCK agent-profile:reviewer-renata" in payload["text"]
    assert "BLOCK agent-profile:architect-alphonso" in payload["text"]


def test_comma_selector_refuses_with_the_correct_syntax(tmp_path: Path) -> None:
    """The comma form used to resolve one bogus id; it must fail loudly instead."""
    project = _project(tmp_path)

    result = _invoke(project, build_charter_context_include, ["--include", f"{_FIRST},{_SECOND}"])

    assert result.exit_code == 1
    assert "Expected a single --include selector" in result.output
    assert "repeat the flag" in result.output


def test_comma_selector_refusal_is_the_layer_contract(tmp_path: Path) -> None:
    """Every caller is protected, not just the CLI: the layer itself refuses a comma."""
    with pytest.raises(ValueError, match="Expected a single --include selector"):
        build_charter_context_include(_project(tmp_path), f"{_FIRST},{_SECOND}")
