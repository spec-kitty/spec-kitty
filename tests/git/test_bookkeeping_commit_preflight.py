"""``preflight_merge_bookkeeping`` validates exactly what ``commit_merge_bookkeeping`` would commit (#4041)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from mission_runtime import MissionArtifactKind
from specify_cli.core.commit_guard import GuardCapability
from specify_cli.git import bookkeeping_commit

pytestmark = [pytest.mark.unit, pytest.mark.fast]


def test_preflight_resolves_the_commit_destination_and_asserts_merge_bookkeeping(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, Any] = {}

    def _resolve(repo_root: Path, mission_slug: str, branch: str | None, kind: MissionArtifactKind) -> str:
        seen["resolve"] = (repo_root, mission_slug, branch, kind)
        return "resolved-target"

    monkeypatch.setattr(bookkeeping_commit, "_resolve_bookkeeping_commit_target", _resolve)
    monkeypatch.setattr(bookkeeping_commit, "preflight_commit", lambda **kwargs: seen.update(preflight=kwargs))
    meta = tmp_path / "meta.json"

    bookkeeping_commit.preflight_merge_bookkeeping(
        repo_root=tmp_path, worktree_root=tmp_path, mission_slug="m-01ABCDEF", message="msg", paths=(meta,), branch="main"
    )

    assert seen["resolve"] == (tmp_path, "m-01ABCDEF", "main", MissionArtifactKind.PRIMARY_METADATA)
    assert seen["preflight"] == {
        "repo_root": tmp_path,
        "worktree_root": tmp_path,
        "target": "resolved-target",
        "message": "msg",
        "paths": (meta,),
        "capability": GuardCapability.MERGE_BOOKKEEPING,
    }


def test_preflight_propagates_a_refused_commit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from specify_cli.git.commit_helpers import SafeCommitError

    monkeypatch.setattr(bookkeeping_commit, "_resolve_bookkeeping_commit_target", lambda *_a: "t")

    def _refuse(**_kwargs: Any) -> None:
        raise SafeCommitError("refused")

    monkeypatch.setattr(bookkeeping_commit, "preflight_commit", _refuse)
    with pytest.raises(SafeCommitError):
        bookkeeping_commit.preflight_merge_bookkeeping(
            repo_root=tmp_path, worktree_root=tmp_path, mission_slug="m-01ABCDEF", message="msg", paths=(tmp_path / "meta.json",)
        )
