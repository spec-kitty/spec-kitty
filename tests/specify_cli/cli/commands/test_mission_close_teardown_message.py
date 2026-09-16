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

from specify_cli.cli.commands import mission_type
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
