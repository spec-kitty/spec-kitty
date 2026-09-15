"""``_prepare_review_workspace`` renders the review lock refusal (#4163).

The ``ReviewLockError`` leg was the last builtin ``print`` in ``src/`` carrying
Rich markup, so ``[red]…[/red]`` reached the terminal literally. It now goes
through the CLI console seam, with the message escaped: lock messages name
agents, work packages and paths, and a bracketed one would otherwise be eaten
as a tag (or raise ``MarkupError`` on a stray closing tag).
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
import typer

from specify_cli.cli.commands.agent import workflow


def test_review_lock_refusal_is_rendered_and_escaped(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    from specify_cli.review.lock import ReviewLock, ReviewLockError

    reason = "[locked] WP01 held by agent [claude] since 10:00 [/]"

    def _refuse(*args: object, **kwargs: object) -> None:
        raise ReviewLockError(reason)

    monkeypatch.setattr("specify_cli.review.lock._get_isolation_config", lambda root: None)
    monkeypatch.setattr(ReviewLock, "acquire", staticmethod(_refuse))

    workspace = SimpleNamespace(
        worktree_path=tmp_path,
        branch_name="kitty/wp01",
        is_husk=False,
        exists=True,
    )

    with pytest.raises(typer.Exit):
        workflow._prepare_review_workspace(workspace, tmp_path, "WP01", "claude")

    out = " ".join(capsys.readouterr().out.split())
    assert reason in out
    assert "[red]" not in out
