"""Direct unit tests for the accept/merge seam (#2056 WP06, T024/T025).

Exercises the relocated worktree finders and the extracted merge phase helpers
in ``specify_cli.cli.commands.agent.mission_accept_merge``: the latest-worktree
scanner, the deterministic worktree resolver, the auto-retry recursion guard,
and the top-level-merge delegation parameter mapping. The end-to-end
``accept``/``merge`` delegators stay pinned by ``test_wrapper_delegation.py`` and
the WP01 golden harness.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import typer

from specify_cli.cli.commands.agent import mission_accept_merge as seam

pytestmark = [pytest.mark.unit, pytest.mark.fast]


# ---------------------------------------------------------------------------
# _find_latest_feature_worktree
# ---------------------------------------------------------------------------


def test_find_latest_none_without_worktrees_dir(tmp_path: Path) -> None:
    assert seam._find_latest_feature_worktree(tmp_path) is None


def test_find_latest_picks_highest_number(tmp_path: Path) -> None:
    wt = tmp_path / ".worktrees"
    (wt / "001-alpha").mkdir(parents=True)
    (wt / "003-gamma").mkdir(parents=True)
    (wt / "002-beta").mkdir(parents=True)
    (wt / "not-a-mission").mkdir(parents=True)
    latest = seam._find_latest_feature_worktree(tmp_path)
    assert latest is not None
    assert latest.name == "003-gamma"


# ---------------------------------------------------------------------------
# _find_feature_worktree
# ---------------------------------------------------------------------------


def test_find_feature_worktree_delegates(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(seam, "resolve_feature_worktree", lambda _r, slug: tmp_path / slug)
    assert seam._find_feature_worktree(tmp_path, "001-demo") == tmp_path / "001-demo"


# ---------------------------------------------------------------------------
# _maybe_auto_retry_in_worktree
# ---------------------------------------------------------------------------


def test_auto_retry_noop_when_recursion_guard_set(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("SPEC_KITTY_AUTORETRY", "1")
    # Returns without raising / re-invoking.
    seam._maybe_auto_retry_in_worktree(
        tmp_path, "001-demo", "main", "merge",
        push=False, dry_run=False, keep_branch=False, keep_worktree=False,
    )


def test_auto_retry_noop_when_on_mission_branch(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("SPEC_KITTY_AUTORETRY", raising=False)
    from specify_cli.cli.commands.agent import mission as mission_mod

    monkeypatch.setattr(mission_mod, "_get_current_branch", lambda _r: "001-demo")
    seam._maybe_auto_retry_in_worktree(
        tmp_path, "001-demo", "main", "merge",
        push=False, dry_run=False, keep_branch=False, keep_worktree=False,
    )


def test_auto_retry_requires_mission_off_branch(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("SPEC_KITTY_AUTORETRY", raising=False)
    from specify_cli.cli.commands.agent import mission as mission_mod

    monkeypatch.setattr(mission_mod, "_get_current_branch", lambda _r: "main")
    with pytest.raises(RuntimeError, match="Auto-retry requires --mission"):
        seam._maybe_auto_retry_in_worktree(
            tmp_path, None, "main", "merge",
            push=False, dry_run=False, keep_branch=False, keep_worktree=False,
        )


def test_auto_retry_raises_when_worktree_missing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("SPEC_KITTY_AUTORETRY", raising=False)
    from specify_cli.cli.commands.agent import mission as mission_mod

    monkeypatch.setattr(mission_mod, "_get_current_branch", lambda _r: "main")
    monkeypatch.setattr(mission_mod, "_find_feature_worktree", lambda _r, _s: None)
    with pytest.raises(RuntimeError, match="Could not find worktree"):
        seam._maybe_auto_retry_in_worktree(
            tmp_path, "001-demo", "main", "merge",
            push=False, dry_run=False, keep_branch=False, keep_worktree=False,
        )


def test_auto_retry_forwards_cleanup_choices(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from specify_cli.cli.commands.agent import mission as mission_mod

    captured: dict[str, object] = {}

    class _Result:
        returncode = 0

    def _run(cmd: list[str], **kwargs: object) -> _Result:
        captured["cmd"] = cmd
        captured["kwargs"] = kwargs
        return _Result()

    monkeypatch.delenv("SPEC_KITTY_AUTORETRY", raising=False)
    monkeypatch.setattr(seam.subprocess, "run", _run)
    monkeypatch.setattr(mission_mod, "_get_current_branch", lambda _r: "main")
    monkeypatch.setattr(mission_mod, "_find_feature_worktree", lambda _r, _s: tmp_path / "001-demo")

    with pytest.raises(SystemExit) as exc:
        seam._maybe_auto_retry_in_worktree(
            tmp_path,
            "001-demo",
            "main",
            "merge",
            push=False,
            dry_run=False,
            keep_branch=None,
            keep_worktree=False,
        )

    assert exc.value.code == 0
    cmd = captured["cmd"]
    assert isinstance(cmd, list)
    assert "--keep-branch" not in cmd
    assert "--delete-branch" not in cmd
    assert "--keep-worktree" not in cmd
    assert "--remove-worktree" in cmd


# ---------------------------------------------------------------------------
# _delegate_to_top_level_merge (parameter mapping / keep-flag inversion)
# ---------------------------------------------------------------------------


def test_delegate_inverts_keep_flags(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}
    from specify_cli.cli.commands.agent import mission as mission_mod

    def _fake_merge(**kwargs: object) -> None:
        captured.update(kwargs)

    monkeypatch.setattr(mission_mod, "top_level_merge", _fake_merge)
    seam._delegate_to_top_level_merge(
        "001-demo", "main", "merge",
        push=True, dry_run=False, keep_branch=True, keep_worktree=False,
    )
    # keep_branch=True → delete_branch=False; keep_worktree=False → remove_worktree=True
    assert captured["delete_branch"] is False
    assert captured["remove_worktree"] is True
    assert captured["push"] is True
    assert captured["mission"] == "001-demo"
    assert captured["target_branch"] == "main"


def test_delegate_preserves_unset_cleanup_flags(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}
    from specify_cli.cli.commands.agent import mission as mission_mod

    def _fake_merge(**kwargs: object) -> None:
        captured.update(kwargs)

    monkeypatch.setattr(mission_mod, "top_level_merge", _fake_merge)
    seam._delegate_to_top_level_merge(
        "001-demo",
        "main",
        "merge",
        push=True,
        dry_run=False,
        keep_branch=None,
        keep_worktree=None,
    )
    assert captured["delete_branch"] is None
    assert captured["remove_worktree"] is None


def test_delegate_maps_explicit_agent_delete_flags(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}
    from specify_cli.cli.commands.agent import mission as mission_mod

    def _fake_merge(**kwargs: object) -> None:
        captured.update(kwargs)

    monkeypatch.setattr(mission_mod, "top_level_merge", _fake_merge)
    seam._delegate_to_top_level_merge(
        "001-demo",
        "main",
        "merge",
        push=False,
        dry_run=False,
        keep_branch=False,
        keep_worktree=False,
    )
    assert captured["delete_branch"] is True
    assert captured["remove_worktree"] is True


def test_delegate_propagates_typer_exit(monkeypatch: pytest.MonkeyPatch) -> None:
    from specify_cli.cli.commands.agent import mission as mission_mod

    def _exit(**_k: object) -> None:
        raise typer.Exit(3)

    monkeypatch.setattr(mission_mod, "top_level_merge", _exit)
    with pytest.raises(typer.Exit) as exc:
        seam._delegate_to_top_level_merge(
            "001-demo", "main", "merge",
            push=False, dry_run=False, keep_branch=False, keep_worktree=False,
        )
    assert exc.value.exit_code == 3


# ---------------------------------------------------------------------------
# accept_feature -> top-level accept delegation (#6321)
# ---------------------------------------------------------------------------


def test_accept_feature_forwards_owned_checkout(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from specify_cli.cli.commands.agent import mission as _mission

    captured: dict[str, object] = {}
    monkeypatch.setattr(_mission, "top_level_accept", lambda **kwargs: captured.update(kwargs))
    seam.accept_feature(feature="001-demo", owned_checkout=tmp_path)
    assert captured["owned_checkout"] == tmp_path
