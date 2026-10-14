"""Suppression matrix tests for the readiness coordinator.

Asserts FR-011 (no Teamspace leakage across the full suppression matrix) and
FR-004 (output policy derivation).

Mission: cli-startup-readiness-coordinator-skeleton-01KS7JRV

The hosted auth-readiness surface (``readiness.auth.probe_auth_status``, the
``SPEC_KITTY_ENABLE_SAAS_SYNC`` enablement path, and the legacy ``_invoke_nag``
seam) was removed from open-core (#6164): the coordinator no longer probes auth
or runs a hosted-enabled path, so it always returns a disabled result. The
hosted-enabled matrix row and the auth-probe/nag monkeypatches that exercised
that path were removed with it; the seven output-policy suppression rows below
exercise the behaviour that remains.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass

import pytest
import typer

from specify_cli.readiness import (
    AuthStatus,
    OutputPolicy,
    ReadinessResult,
    evaluate_readiness,
)
from specify_cli.readiness import coordinator as coord_module


pytestmark = [pytest.mark.unit, pytest.mark.fast]


@dataclass(frozen=True)
class MatrixRow:
    name: str
    argv: list[str]
    ci_env: bool
    isatty: bool
    expected_policy: OutputPolicy


# 7-row suppression matrix. The coordinator is always disabled in open-core
# (the hosted-enabled path was removed, #6164), so every row expects a disabled
# result; only the derived output policy varies.
MATRIX_ROWS: list[MatrixRow] = [
    MatrixRow(
        name="help",
        argv=["--help"],
        ci_env=False,
        isatty=True,
        expected_policy=OutputPolicy.NON_INTERACTIVE,
    ),
    MatrixRow(
        name="version",
        argv=["--version"],
        ci_env=False,
        isatty=True,
        expected_policy=OutputPolicy.NON_INTERACTIVE,
    ),
    MatrixRow(
        name="plain_invocation",
        argv=[],
        ci_env=False,
        isatty=True,
        expected_policy=OutputPolicy.INTERACTIVE,
    ),
    MatrixRow(
        name="json",
        argv=["status", "--json"],
        ci_env=False,
        isatty=True,
        expected_policy=OutputPolicy.MACHINE_OUTPUT,
    ),
    MatrixRow(
        name="quiet",
        argv=["status", "--quiet"],
        ci_env=False,
        isatty=True,
        expected_policy=OutputPolicy.MACHINE_OUTPUT,
    ),
    MatrixRow(
        name="ci",
        argv=["status"],
        ci_env=True,
        isatty=True,
        expected_policy=OutputPolicy.NON_INTERACTIVE,
    ),
    MatrixRow(
        name="non_tty",
        argv=["status"],
        ci_env=False,
        isatty=False,
        expected_policy=OutputPolicy.NON_INTERACTIVE,
    ),
]


def _make_ctx() -> typer.Context:
    """Build a minimal typer.Context with ctx.obj=None for testing."""
    app = typer.Typer()

    @app.callback()
    def _root_cb(ctx: typer.Context) -> None:  # pragma: no cover - test scaffolding
        pass

    cmd = typer.main.get_command(app)
    return typer.Context(cmd)


@pytest.mark.parametrize("row", MATRIX_ROWS, ids=[r.name for r in MATRIX_ROWS])
def test_suppression_matrix_no_teamspace_leakage(
    row: MatrixRow,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Arrange env: CI
    if row.ci_env:
        monkeypatch.setenv("CI", "1")
    else:
        monkeypatch.delenv("CI", raising=False)

    # Suppress side-effects of the (non-hosted) upgrade UX — we are testing the
    # coordinator's suppression contract, not the UX's behaviour.
    monkeypatch.setattr(coord_module, "_invoke_nag", lambda ctx: None)

    # Arrange argv
    monkeypatch.setattr(sys, "argv", ["spec-kitty", *row.argv])

    # Arrange isatty
    monkeypatch.setattr(sys.stdout, "isatty", lambda: row.isatty)

    # Act
    ctx = _make_ctx()
    result = evaluate_readiness(ctx)

    # Assert: result fields. Open-core always returns a disabled result.
    assert isinstance(result, ReadinessResult), f"got {type(result)!r}"
    assert result.enabled is False, f"row={row.name}: open-core is always disabled"
    assert (
        result.output_policy == row.expected_policy
    ), f"row={row.name}: policy mismatch ({result.output_policy})"
    assert result.auth_status == AuthStatus.DISABLED, f"row={row.name}: expected DISABLED"
    assert result.ran is False, f"row={row.name}: disabled result never ran a hosted probe"

    # Assert: no Teamspace leakage
    captured = capsys.readouterr()
    assert "teamspace" not in captured.out.lower(), (
        f"row={row.name}: Teamspace leaked to stdout: {captured.out!r}"
    )
    assert "teamspace" not in captured.err.lower(), (
        f"row={row.name}: Teamspace leaked to stderr: {captured.err!r}"
    )
