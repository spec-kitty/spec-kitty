"""``RETIRED_PACK_FIELD`` on the operator surfaces: coded error text and the lint finding (#3732)."""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest
from rich.console import Console

from charter.offering.packs.retired_fields import RETIRED_PACK_FIELD, RETIRED_PACK_FIELDS, RetiredPackFieldError
from specify_cli.charter_runtime.lint.checks.org_layer import _retired_pack_field_finding
from specify_cli.cli.commands.charter._common import _emit_error

pytestmark = pytest.mark.fast


def _console() -> tuple[Console, io.StringIO]:
    buffer = io.StringIO()
    return Console(file=buffer, width=400, color_system=None), buffer


def test_emit_error_text_names_the_code() -> None:
    console, buffer = _console()
    _emit_error(console, json_output=False, message="the message", code=RETIRED_PACK_FIELD)
    assert buffer.getvalue().strip() == f"Error ({RETIRED_PACK_FIELD}): the message"


def test_emit_error_text_without_code_is_unchanged() -> None:
    console, buffer = _console()
    _emit_error(console, json_output=False, message="the message")
    assert buffer.getvalue().strip() == "Error: the message"


def test_emit_error_json_carries_the_code(capsys: pytest.CaptureFixture[str]) -> None:
    console, _ = _console()
    _emit_error(console, json_output=True, message="the message", code=RETIRED_PACK_FIELD, extra={"code": "ignored"})
    payload = json.loads(capsys.readouterr().out)
    assert payload == {"code": RETIRED_PACK_FIELD, "error": "the message", "result": "error", "success": False}


def test_emit_error_json_without_code_has_no_code_key(capsys: pytest.CaptureFixture[str]) -> None:
    console, _ = _console()
    _emit_error(console, json_output=True, message="the message")
    assert "code" not in json.loads(capsys.readouterr().out)


def test_lint_finding_names_file_field_and_replacement(tmp_path: Path) -> None:
    path = tmp_path / "org-charter.yaml"
    finding = _retired_pack_field_finding(RetiredPackFieldError(RETIRED_PACK_FIELDS[0], path=path))
    assert (finding.category, finding.type, finding.severity, finding.id) == ("org_layer", "retired_pack_field", "high", f"{path}:doctrine_pack_id")
    assert finding.message.startswith(f"{RETIRED_PACK_FIELD}: {path}: field 'doctrine_pack_id' was removed.")
    assert finding.remediation_hint == f"Rename 'doctrine_pack_id' to 'charter_pack_id' in {path}."


def test_generate_error_code_is_only_set_for_a_coded_error() -> None:
    from specify_cli.cli.commands.charter.generate import _error_code

    assert _error_code(RetiredPackFieldError(RETIRED_PACK_FIELDS[0])) == RETIRED_PACK_FIELD
    assert _error_code(ValueError("plain")) is None
