"""``spec-kitty mission close --target`` aims the terminus retrospective commit (#7201).

The refusal warning the terminus prints tells the operator to heal a refused
retrospective commit with ``spec-kitty mission close --mission <slug>`` — the
same code path, which resolved the same stale ``meta.json`` destination and was
therefore refused again. ``--target`` is the missing aim: it is forwarded to the
teardown persist leg, which passes it to the terminus as the resolved landing
branch.

Both halves are pinned against ONE fixture (``acceptance-criteria-non-vacuity``):
``--target`` must reach the seam, and its absence must reach the seam as ``None``
so every Mission landed on its recorded target keeps today's behaviour.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from specify_cli.cli.commands import mission_type

pytestmark = [pytest.mark.unit, pytest.mark.fast]

MISSION_ID = "01M6P3E46H9C4SES0ZXSBZ88NG"
MID8 = MISSION_ID[:8]
MISSION_SLUG = f"terminus-close-target-{MID8}"
LANDING_BRANCH = "topic-landing"


def _scaffold_project(tmp_path: Path) -> Path:
    """A minimal project root with one merged Mission that carries an identity."""
    (tmp_path / ".kittify").mkdir()
    feature_dir = tmp_path / "kitty-specs" / MISSION_SLUG
    feature_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text(
        json.dumps(
            {
                "mission_id": MISSION_ID,
                "mid8": MID8,
                "mission_slug": MISSION_SLUG,
                "target_branch": "main",
                "merged_at": "2026-11-05T00:00:00Z",
            }
        ),
        encoding="utf-8",
    )
    return tmp_path


def _invoke_close(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *argv: str,
) -> tuple[Any, dict[str, Any]]:
    """Run ``mission close`` through Typer; return (result, captured seam kwargs)."""
    project_root = _scaffold_project(tmp_path)
    feature_dir = project_root / "kitty-specs" / MISSION_SLUG
    captured: dict[str, Any] = {}

    def _fake_teardown(*_args: object, **kwargs: object) -> bool:
        captured.update(kwargs)
        captured["positional"] = _args
        return True

    monkeypatch.setattr(mission_type, "get_project_root_or_exit", lambda **_kw: project_root)
    monkeypatch.setattr(mission_type, "_resolve_primary_repo_root", lambda root: root)
    monkeypatch.setattr(mission_type, "resolve_feature_dir_for_mission", lambda _root, _slug: feature_dir)
    monkeypatch.setattr("specify_cli.status.is_mission_merged", lambda _feature_dir: True)
    monkeypatch.setattr(
        "specify_cli.coordination.teardown.teardown_coordination_topology",
        _fake_teardown,
    )
    monkeypatch.setattr(
        "specify_cli.coordination.workspace.CoordinationWorkspace.is_present",
        classmethod(lambda cls, *a, **k: False),
    )

    result = CliRunner().invoke(mission_type.app, ["close", "--mission", MISSION_SLUG, *argv])
    return result, captured


def test_close_target_reaches_the_persist_leg(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``--target`` is forwarded verbatim as the persist leg's destination."""
    result, captured = _invoke_close(tmp_path, monkeypatch, "--target", LANDING_BRANCH)

    assert result.exit_code == 0, result.output
    assert captured, "the teardown seam must run for a merged Mission"
    assert captured.get("destination_ref") == LANDING_BRANCH
    assert captured.get("provenance_kind") == "runtime_post_completion"


def test_close_without_target_preserves_placement_resolution(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """No ``--target`` → ``None`` reaches the seam, i.e. today's resolution."""
    result, captured = _invoke_close(tmp_path, monkeypatch)

    assert result.exit_code == 0, result.output
    assert captured, "the teardown seam must run for a merged Mission"
    assert captured.get("destination_ref") is None


def test_discard_leg_forwards_the_target(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``--discard --target`` forwards the aim and keeps the abandoned provenance."""
    project_root = _scaffold_project(tmp_path)
    feature_dir = project_root / "kitty-specs" / MISSION_SLUG
    captured: dict[str, Any] = {}

    def _fake_discard(**kwargs: object) -> None:
        captured.update(kwargs)

    monkeypatch.setattr(mission_type, "get_project_root_or_exit", lambda **_kw: project_root)
    monkeypatch.setattr(mission_type, "_resolve_primary_repo_root", lambda root: root)
    monkeypatch.setattr(mission_type, "resolve_feature_dir_for_mission", lambda _root, _slug: feature_dir)
    monkeypatch.setattr(mission_type, "_discard_mission", _fake_discard)
    monkeypatch.setattr(mission_type, "_verify_discard_complete", lambda *a, **k: None)
    monkeypatch.setattr(mission_type, "_flatten_discarded_mission", lambda *a, **k: None)
    monkeypatch.setattr(mission_type, "_mark_mission_discarded", lambda *a, **k: None)
    monkeypatch.setattr(mission_type, "_commit_flattened_meta", lambda *a, **k: None)

    result = CliRunner().invoke(
        mission_type.app,
        ["close", "--mission", MISSION_SLUG, "--discard", "--force", "--target", LANDING_BRANCH],
    )

    assert result.exit_code == 0, result.output
    assert captured.get("destination_ref") == LANDING_BRANCH


def test_abandonment_leg_seam_call_carries_the_target(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The abandonment leg's seam call forwards the destination it was given."""
    captured: dict[str, Any] = {}

    def _fake_teardown(*_args: object, **kwargs: object) -> bool:
        captured.update(kwargs)
        return True

    monkeypatch.setattr(
        "specify_cli.coordination.teardown.teardown_coordination_topology",
        _fake_teardown,
    )
    monkeypatch.setattr(
        "specify_cli.coordination.workspace.CoordinationWorkspace.is_present",
        classmethod(lambda cls, *a, **k: False),
    )

    mission_type._teardown_coordination_worktree(
        tmp_path,
        MISSION_SLUG,
        MID8,
        provenance_kind="runtime_abandoned",
        quiet=True,
        destination_ref=LANDING_BRANCH,
    )

    assert captured.get("destination_ref") == LANDING_BRANCH
    assert captured.get("provenance_kind") == "runtime_abandoned"


def test_discard_steps_forward_the_target_to_the_persist_leg(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``_discard_mission_steps`` carries the destination into the abandonment leg.

    The CLI-level test above proves ``close --discard`` reaches ``_discard_mission``;
    this one proves the next hop — the abandonment leg's seam call — is not dropped,
    which the earlier helper test could not see (it started below this function).
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    feature_dir = _scaffold_project(repo) / "kitty-specs" / MISSION_SLUG
    meta_path = feature_dir / "meta.json"
    captured: dict[str, Any] = {}

    def _fake_teardown(*_args: object, **kwargs: object) -> None:
        captured.update(kwargs)

    monkeypatch.setattr(mission_type, "_load_lanes_manifest_for_discard", lambda *a, **k: None)
    monkeypatch.setattr(mission_type, "_discard_target_branch", lambda *a, **k: "main")
    monkeypatch.setattr(mission_type, "_minted_branch_for_discard", lambda *a, **k: None)
    monkeypatch.setattr(mission_type, "_announce_discard_loss", lambda *a, **k: None)
    monkeypatch.setattr(mission_type, "_confirm_discard", lambda *a, **k: None)
    monkeypatch.setattr(mission_type, "_delete_legacy_coordination_branch", lambda *a, **k: None)
    monkeypatch.setattr(mission_type, "_teardown_coordination_worktree", _fake_teardown)

    assert (
        mission_type._discard_mission_steps(
            repo_root=repo,
            feature_dir=feature_dir,
            mission_slug=MISSION_SLUG,
            mid8_value=MID8,
            meta_path=meta_path,
            force=True,
            destination_ref=LANDING_BRANCH,
        )
        is None
    )
    assert captured.get("destination_ref") == LANDING_BRANCH
    assert captured.get("provenance_kind") == "runtime_abandoned"
