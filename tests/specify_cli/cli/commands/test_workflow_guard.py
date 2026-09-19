"""Guard ``workflow import``/``workflow export`` against invalid files (#4738).

Mission ``cli-error-surface-seam-01M2WJD2``, WP02. Before this WP, both commands
called ``load_workflow_file`` with no try/except; a malformed YAML file, a
valid-YAML-but-wrong-schema file, a wrong-top-level-type file, an unreadable
file, or a corrupt resolved/exported workflow all propagated as a raw
traceback instead of the WP01 typed ``GuardedReadError`` presentation seam.

Every test here runs through the *real* ``workflow import``/``workflow
export`` Typer commands (T007's C-003 requirement) via
``specify_cli._run_app_with_error_hook`` — the same global hook production
code path ``main()`` wraps the assembled top-level app with (see
``tests/specify_cli/test_error_hook.py``, the canonical pattern this file
follows). Calling ``load_workflow_file`` directly would prove nothing about
what the operator actually sees at the command boundary.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

from specify_cli import _run_app_with_error_hook
from specify_cli.cli.commands import workflow as workflow_module

pytestmark = [pytest.mark.unit, pytest.mark.fast]

app = workflow_module.app

VALID_WORKFLOW_YAML = """
workflow_id: solo-fast
description: Portable workflow.
version: 1
initial: specify
actions:
  - action_name: specify
    description: Create a mission specification
    terminal: true
""".lstrip()

MALFORMED_YAML = "workflow_id: [unterminated\n  description: oops\n"

WRONG_SCHEMA_YAML = """
workflow_id: solo-fast
description: Missing required fields.
""".lstrip()

WRONG_TOP_LEVEL_TYPE_YAML = "- solo-fast\n- another-item\n"


def _invoke(argv: list[str], *, monkeypatch: pytest.MonkeyPatch, json_mode: bool = False) -> int:
    """Run *argv* through the real ``workflow`` app + the real global hook.

    Returns the process exit code (via the ``SystemExit`` the hook always
    raises for a ``GuardedReadError``/subclass, matching
    ``_run_app_with_error_hook``'s documented contract).
    """
    monkeypatch.setattr(sys, "argv", ["spec-kitty", *argv])
    with pytest.raises(SystemExit) as exc_info:
        _run_app_with_error_hook(app, json_mode=json_mode)
    return int(exc_info.value.code or 0)


# ---------------------------------------------------------------------------
# T007/T009 — workflow import: malformed YAML
# ---------------------------------------------------------------------------


@pytest.mark.regression
def test_workflow_import_malformed_yaml_presents_clean_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """#4738: malformed YAML must exit 1 with an actionable message, no traceback."""
    source = tmp_path / "bad.yaml"
    source.write_text(MALFORMED_YAML, encoding="utf-8")
    project_root = tmp_path / "project"

    exit_code = _invoke(
        ["import", str(source), "--project-root", str(project_root)],
        monkeypatch=monkeypatch,
    )

    assert exit_code == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert str(source) in captured.err
    assert "Traceback" not in captured.err


@pytest.mark.regression
def test_workflow_import_malformed_yaml_json_envelope(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """#4738: ``--json`` mode emits exactly one JSON object matching the envelope contract."""
    source = tmp_path / "bad.yaml"
    source.write_text(MALFORMED_YAML, encoding="utf-8")
    project_root = tmp_path / "project"

    exit_code = _invoke(
        ["import", str(source), "--project-root", str(project_root)],
        monkeypatch=monkeypatch,
        json_mode=True,
    )

    assert exit_code == 1
    captured = capsys.readouterr()
    assert captured.err == ""
    lines = [line for line in captured.out.splitlines() if line.strip()]
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert set(payload) == {"error", "kind", "path"}
    assert payload["kind"] == "WorkflowFileError"
    assert payload["path"] == str(source)


# ---------------------------------------------------------------------------
# T007/T009 — workflow import: valid YAML, wrong schema
# ---------------------------------------------------------------------------


@pytest.mark.regression
def test_workflow_import_wrong_schema_presents_clean_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """#4738: valid YAML that fails ``WorkflowSequence`` validation is the same clean error."""
    source = tmp_path / "wrong-schema.yaml"
    source.write_text(WRONG_SCHEMA_YAML, encoding="utf-8")
    project_root = tmp_path / "project"

    exit_code = _invoke(
        ["import", str(source), "--project-root", str(project_root)],
        monkeypatch=monkeypatch,
    )

    assert exit_code == 1
    captured = capsys.readouterr()
    assert "Traceback" not in captured.err
    assert str(source) in captured.err


# ---------------------------------------------------------------------------
# T007/T009 — workflow import: wrong top-level type (YAML list, not mapping)
# ---------------------------------------------------------------------------


@pytest.mark.regression
def test_workflow_import_wrong_top_level_type_presents_clean_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """#4738: a bare YAML list (not a mapping) is the same clean error, no pydantic traceback."""
    source = tmp_path / "list.yaml"
    source.write_text(WRONG_TOP_LEVEL_TYPE_YAML, encoding="utf-8")
    project_root = tmp_path / "project"

    exit_code = _invoke(
        ["import", str(source), "--project-root", str(project_root)],
        monkeypatch=monkeypatch,
    )

    assert exit_code == 1
    captured = capsys.readouterr()
    assert "Traceback" not in captured.err
    assert str(source) in captured.err


# ---------------------------------------------------------------------------
# T007/T009 — workflow import: unreadable file
# ---------------------------------------------------------------------------


@pytest.mark.regression
@pytest.mark.skipif(
    sys.platform == "win32" or os.geteuid() == 0,
    reason="chmod 0o000 does not deny reads on Windows or for root",
)
def test_workflow_import_unreadable_file_presents_clean_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """#4738: permission-denied on the source file is the same clean error, no OSError traceback."""
    source = tmp_path / "denied.yaml"
    source.write_text(VALID_WORKFLOW_YAML, encoding="utf-8")
    os.chmod(source, 0o000)
    project_root = tmp_path / "project"

    try:
        exit_code = _invoke(
            ["import", str(source), "--project-root", str(project_root)],
            monkeypatch=monkeypatch,
        )
    finally:
        os.chmod(source, 0o644)

    assert exit_code == 1
    captured = capsys.readouterr()
    assert "Traceback" not in captured.err
    assert str(source) in captured.err


# ---------------------------------------------------------------------------
# T007/T009 — workflow export: corrupt resolved/override workflow
# ---------------------------------------------------------------------------


def _write_override(project_root: Path, *, workflow_id: str, content: str) -> Path:
    workflow_dir = project_root / ".kittify" / "overrides" / "workflows"
    workflow_dir.mkdir(parents=True, exist_ok=True)
    path = workflow_dir / f"{workflow_id}.yaml"
    path.write_text(content, encoding="utf-8")
    return path


@pytest.mark.regression
def test_workflow_export_corrupt_resolved_workflow_presents_clean_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """#4738 acceptance scenario 3: exporting a corrupt resolved workflow is the same clean error."""
    project_root = tmp_path / "project"
    source = _write_override(project_root, workflow_id="corrupt-export", content=MALFORMED_YAML)
    destination = tmp_path / "exported.yaml"

    exit_code = _invoke(
        ["export", "corrupt-export", str(destination), "--project-root", str(project_root)],
        monkeypatch=monkeypatch,
    )

    assert exit_code == 1
    captured = capsys.readouterr()
    assert "Traceback" not in captured.err
    assert str(source) in captured.err
    assert not destination.exists()


@pytest.mark.regression
def test_workflow_export_corrupt_resolved_workflow_json_envelope(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """#4738: export's corrupt-file path also emits the JSON envelope under ``--json``."""
    project_root = tmp_path / "project"
    source = _write_override(project_root, workflow_id="corrupt-export", content=MALFORMED_YAML)
    destination = tmp_path / "exported.yaml"

    exit_code = _invoke(
        ["export", "corrupt-export", str(destination), "--project-root", str(project_root)],
        monkeypatch=monkeypatch,
        json_mode=True,
    )

    assert exit_code == 1
    captured = capsys.readouterr()
    assert captured.err == ""
    lines = [line for line in captured.out.splitlines() if line.strip()]
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert payload == {
        "error": payload["error"],
        "kind": "WorkflowFileError",
        "path": str(source),
    }


# ---------------------------------------------------------------------------
# T009 — UnknownWorkflowError (workflow_id mismatch) still presents unchanged
# ---------------------------------------------------------------------------


@pytest.mark.regression
def test_workflow_export_id_mismatch_still_presents_via_hook_unchanged(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """spec.md Edge Cases: re-parenting ``UnknownWorkflowError`` changes surface, not
    wording — the file-declares-X-but-requested-Y message must be byte-identical."""
    project_root = tmp_path / "project"
    mismatch_content = """
workflow_id: other-id
description: Declares a different id than requested.
version: 1
initial: specify
actions:
  - action_name: specify
    description: Create a mission specification
    terminal: true
""".lstrip()
    source = _write_override(project_root, workflow_id="mismatch-id", content=mismatch_content)
    destination = tmp_path / "exported.yaml"

    exit_code = _invoke(
        ["export", "mismatch-id", str(destination), "--project-root", str(project_root)],
        monkeypatch=monkeypatch,
    )

    assert exit_code == 1
    captured = capsys.readouterr()
    assert "Traceback" not in captured.err
    expected_message = f"Error: Workflow file {source} declares workflow_id='other-id' but was requested as 'mismatch-id'."
    assert captured.err.strip() == expected_message


# ---------------------------------------------------------------------------
# T008 binding amendment #2 — the raw `_copy_workflow` read is guarded too
# ---------------------------------------------------------------------------


@pytest.mark.regression
def test_workflow_import_guards_the_raw_copy_read(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """``_copy_workflow``'s ``source.read_bytes()`` (``workflow.py:85``) is reachable
    from both commands and must route through ``read_guarded`` too (BINDING
    AMENDMENT #2) — not just the earlier ``load_workflow_file`` validation call.
    Simulated by having the source vanish between the two reads (e.g. a
    concurrent delete), which a raw ``read_bytes()`` would traceback on.
    """
    source = tmp_path / "solo-fast.yaml"
    source.write_text(VALID_WORKFLOW_YAML, encoding="utf-8")
    project_root = tmp_path / "project"

    original_load_workflow_file = workflow_module.load_workflow_file

    def _load_then_delete(path: Path, *args: object, **kwargs: object) -> object:
        result = original_load_workflow_file(path, *args, **kwargs)
        Path(path).unlink()
        return result

    monkeypatch.setattr(workflow_module, "load_workflow_file", _load_then_delete)

    exit_code = _invoke(
        ["import", str(source), "--project-root", str(project_root)],
        monkeypatch=monkeypatch,
    )

    assert exit_code == 1
    captured = capsys.readouterr()
    assert "Traceback" not in captured.err
    assert str(source) in captured.err
