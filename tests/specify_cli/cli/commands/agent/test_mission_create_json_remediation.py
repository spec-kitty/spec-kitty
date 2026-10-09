"""FR-010: the ACTIVE_CHARTER_CONFIG_INVALID remediation body survives ``--json``.

Mission ``upgrade-atomicity-recovery-01KZWSHC`` / WP11 / #3337.

``ActiveCharterConfigError`` (``kernel.errors.KittyInternalConsistencyError``
subclass) carries a JSON-stable ``.code`` (``"ACTIVE_CHARTER_CONFIG_INVALID"``)
and a human-readable ``.body`` with the remediation steps. ``str(exc)`` returns
only the ``code`` — so the generic ``except Exception -> _emit_json({"error":
str(e)})`` funnel in ``_run_create_core_phase`` DROPS the remediation body,
leaving scripted ``--json`` callers with an opaque code and no fix instructions.

These tests pin the dedicated ``except ActiveCharterConfigError`` branch: the
``--json`` failure envelope must carry the remediation ``.body`` (not just the
code). The body text is supplied by the raising test double so the assertion is
decoupled from the WP12-owned prose at ``core/mission_creation.py``.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import typer

from specify_cli.cli.commands.agent import mission_create as seam

pytestmark = [pytest.mark.unit, pytest.mark.fast]


_REMEDIATION_BODY = (
    "This project has no activated mission types, so a mission cannot be "
    "created. Provision the project's charter: run `spec-kitty init` "
    "(new project) or `spec-kitty upgrade` (existing project)."
)


def _raise_charter_config_error(**_kwargs: object) -> None:
    """Stand-in for ``create_mission_core`` that fails the charter-pack gate."""
    from charter.activation.pack_context import ActiveCharterConfigError

    raise ActiveCharterConfigError(_REMEDIATION_BODY)


def _run_core_phase_json(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> dict[str, object]:
    """Drive ``_run_create_core_phase`` in ``--json`` mode, capturing the payload."""
    import specify_cli.core.mission_creation as core

    monkeypatch.setattr(core, "create_mission_core", _raise_charter_config_error)

    emitted: dict[str, object] = {}
    monkeypatch.setattr(seam, "_emit_json", lambda payload: emitted.update(payload))

    with pytest.raises(typer.Exit) as exc_info:
        seam._run_create_core_phase(
            repo_root=tmp_path,
            mission_slug="001-demo",
            resolved_mission_type="software-dev",
            target_branch="main",
            friendly_name=None,
            purpose_tldr=None,
            purpose_context=None,
            pr_bound=False,
            force_recreate_coordination_branch=False,
            owned_create_root=None,
            json_output=True,
        )
    assert exc_info.value.exit_code == 1
    return emitted


def test_json_envelope_carries_remediation_body(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # FR-010 / US5 AC1: the remediation prose must reach the --json envelope.
    envelope = _run_core_phase_json(monkeypatch, tmp_path)
    serialized = repr(envelope)
    assert _REMEDIATION_BODY in serialized, f"remediation body dropped from --json envelope; got only: {serialized}"


def test_json_envelope_exposes_stable_error_code(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # The stable machine code accompanies the body so scripted callers can
    # branch on it (NFR-007-style stable error_code contract).
    envelope = _run_core_phase_json(monkeypatch, tmp_path)
    assert envelope.get("error_code") == "ACTIVE_CHARTER_CONFIG_INVALID"


def test_json_envelope_error_is_not_bare_code(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # Regression guard: the pre-fix generic funnel emitted {"error":
    # "ACTIVE_CHARTER_CONFIG_INVALID"} (str(exc) == code), dropping the body.
    envelope = _run_core_phase_json(monkeypatch, tmp_path)
    assert envelope.get("error") != "ACTIVE_CHARTER_CONFIG_INVALID"
