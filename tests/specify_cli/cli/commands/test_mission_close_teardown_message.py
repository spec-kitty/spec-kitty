"""``_teardown_coordination_worktree`` names the coordination identity once (#4163).

The slug read from the feature directory already embeds the mid8
(``relcheck-01M21R2T``); the success line appended the mid8 a second time and
printed ``relcheck-01M21R2T-01M21R2T``. The message now composes the identity
through the seam's idempotent :func:`coord_mission_dir_name`, so a slug with
or without the embedded mid8 renders the same name the branch line uses.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import typer

from specify_cli.cli.commands import mission_type
from specify_cli.coordination.teardown import ProjectionTeardownAbort
from specify_cli.coordination.workspace import CoordinationWorkspace

MID8 = "01M21R2T"


@pytest.mark.parametrize("mission_slug", ["relcheck-01M21R2T", "relcheck"])
def test_teardown_success_line_does_not_double_the_mid8(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], mission_slug: str
) -> None:
    monkeypatch.setattr(
        "specify_cli.coordination.teardown.teardown_coordination_topology",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(CoordinationWorkspace, "is_present", classmethod(lambda cls, *args, **kwargs: False))

    mission_type._teardown_coordination_worktree(tmp_path, mission_slug, MID8)

    out = capsys.readouterr().out
    assert f"Coordination worktree torn down for relcheck-{MID8}" in out
    assert f"{MID8}-{MID8}" not in out


# ---------------------------------------------------------------------------
# WP17 (binding corrections, FR-009c, #5023): ``teardown_coordination_topology``
# can now raise ``ProjectionTeardownAbort`` (``COORDINATION_LEDGER_UNREPAIRED``)
# -- this leg used to carry the comment "this never raises". The close/discard
# caller must render the refusal and exit non-zero, not crash with a raw
# traceback (no partial teardown: the abort runs before any mutation).
# ---------------------------------------------------------------------------


def test_teardown_renders_coordination_ledger_unrepaired_abort_human(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    def _raise(*_args: object, **_kwargs: object) -> None:
        raise ProjectionTeardownAbort(
            reason="the decisions ledger exists only on this coordination branch",
            coord_ref="kitty/mission-relcheck-01M21R2T",
            error_code="COORDINATION_LEDGER_UNREPAIRED",
            remedy="run `spec-kitty doctor decisions --mission relcheck-01M21R2T --repair`",
        )

    monkeypatch.setattr("specify_cli.coordination.teardown.teardown_coordination_topology", _raise)

    with pytest.raises(typer.Exit) as excinfo:
        mission_type._teardown_coordination_worktree(tmp_path, "relcheck-01M21R2T", MID8)

    assert excinfo.value.exit_code == 1
    out = capsys.readouterr().out
    assert "COORDINATION_LEDGER_UNREPAIRED" in out or "doctor decisions" in out


def test_teardown_renders_coordination_ledger_unrepaired_abort_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """``quiet=True`` (the ``--json`` close path) emits the structured
    machine contract instead of a rich human line."""
    import json

    def _raise(*_args: object, **_kwargs: object) -> None:
        raise ProjectionTeardownAbort(
            reason="the decisions ledger exists only on this coordination branch",
            coord_ref="kitty/mission-relcheck-01M21R2T",
            error_code="COORDINATION_LEDGER_UNREPAIRED",
            remedy="run `spec-kitty doctor decisions --mission relcheck-01M21R2T --repair`",
        )

    monkeypatch.setattr("specify_cli.coordination.teardown.teardown_coordination_topology", _raise)

    with pytest.raises(typer.Exit) as excinfo:
        mission_type._teardown_coordination_worktree(tmp_path, "relcheck-01M21R2T", MID8, quiet=True)

    assert excinfo.value.exit_code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["error"]["code"] == "COORDINATION_LEDGER_UNREPAIRED"
