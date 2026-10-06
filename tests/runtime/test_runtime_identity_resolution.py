"""Functional regression guards for runtime identity/coordination resolution
behavior (extracted from the retired WP10 mission test file
``test_bridge_identity.py``; these guard product behavior, not the
decomposition's structure)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from mission_runtime import MissionArtifactKind
from runtime.next import runtime_bridge_identity as identity
from specify_cli.lanes.branch_naming import BranchIdentityUnresolved

pytestmark = [pytest.mark.unit, pytest.mark.fast]


def test_primary_runtime_feature_dir_delegates_to_read_path_resolver(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The moved body composes via the kind-aware placement seam's PRIMARY leg
    (#2091 fix) -- pinned against a stub seam so this test does not depend on
    the real read-path resolver's internals.

    read-side-seam-primary-primitive-closure-01KYKMMT WP08 (T035,
    reconciliation sweep): this test predated WP07's own T032 routing of
    ``_primary_runtime_feature_dir`` onto
    ``placement_seam(...).read_dir(PRIMARY_METADATA)`` (see that function's
    docstring) -- it was patching ``_canonicalize_primary_read_handle`` /
    the (now-deleted) public wrapper, neither of which the routed body calls
    any longer (a WP07 test-authoring gap, not a WP08 regression). Re-pointed
    to patch the seam it actually calls.
    """
    calls: dict[str, Any] = {}

    class _StubSeam:
        def __init__(self, repo_root: Path, mission_slug: str) -> None:
            calls["seam_init"] = (repo_root, mission_slug)

        def read_dir(self, kind: object) -> Path:
            calls["read_dir_kind"] = kind
            return calls["seam_init"][0] / "kitty-specs" / calls["seam_init"][1]

    monkeypatch.setattr("mission_runtime.placement_seam", _StubSeam)

    result = identity._primary_runtime_feature_dir(tmp_path, "my-slug")

    assert calls["seam_init"] == (tmp_path, "my-slug")
    assert calls["read_dir_kind"] is MissionArtifactKind.PRIMARY_METADATA
    assert result == tmp_path / "kitty-specs" / "my-slug"


def test_resolve_coordination_branch_returns_declared_branch_from_meta(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A declared ``coordination_branch`` in meta.json is authoritative."""
    feature_dir = tmp_path / "kitty-specs" / "my-mission-01KWDABC"
    feature_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text(
        json.dumps({"coordination_branch": "kitty/mission-my-mission-01KWDABC-lane-a"}),
        encoding="utf-8",
    )
    monkeypatch.setattr(identity, "_primary_runtime_feature_dir", lambda repo_root, mission_slug: feature_dir)

    branch = identity._resolve_coordination_branch("my-mission-01KWDABC", tmp_path)

    assert branch == "kitty/mission-my-mission-01KWDABC-lane-a"


def test_resolve_coordination_branch_composes_when_undeclared(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """No declared ``coordination_branch`` -> composed via the fail-closed
    seam using the declared ``mission_id`` (#1978)."""
    feature_dir = tmp_path / "kitty-specs" / "my-mission-01KWDABC"
    feature_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text(
        json.dumps({"mission_id": "01KWDABC1234567890ABCDEFGH"}),
        encoding="utf-8",
    )
    monkeypatch.setattr(identity, "_primary_runtime_feature_dir", lambda repo_root, mission_slug: feature_dir)

    branch = identity._resolve_coordination_branch("my-mission-01KWDABC", tmp_path)

    assert branch  # composed, non-empty
    assert "my-mission" in branch


def test_resolve_coordination_branch_malformed_modern_mission_fails_closed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The malformed-coord correctness path (this WP's namesake): a modern
    slug (no ``NNN-`` prefix, no mid8 tail) with no recoverable ``mission_id``
    must raise :class:`BranchIdentityUnresolved` -- NEVER silently compose a
    malformed ``kitty/mission-<slug>-`` branch (the historical #2091-class
    ``git worktree`` exit-128 scar). This is not swallowed anywhere in this
    seam; only ``runtime_bridge_decision_log._wrap_with_decision_git_log``
    decides whether to convert it to ``DecisionGitLogUnavailable`` or a
    warning-logged fallback."""
    feature_dir = tmp_path / "kitty-specs" / "my-mission"
    feature_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text(json.dumps({}), encoding="utf-8")
    monkeypatch.setattr(identity, "_primary_runtime_feature_dir", lambda repo_root, mission_slug: feature_dir)

    with pytest.raises(BranchIdentityUnresolved):
        identity._resolve_coordination_branch("my-mission", tmp_path)


def test_resolve_mission_ulid_returns_ulid_when_present(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    feature_dir = tmp_path / "kitty-specs" / "my-mission-01KWDABC"
    feature_dir.mkdir(parents=True)
    ulid = "01KWDABC1234567890ABCDEFGH"
    (feature_dir / "meta.json").write_text(json.dumps({"mission_id": ulid}), encoding="utf-8")
    monkeypatch.setattr(identity, "_primary_runtime_feature_dir", lambda repo_root, mission_slug: feature_dir)

    assert identity._resolve_mission_ulid("my-mission-01KWDABC", tmp_path) == ulid


def test_resolve_mission_ulid_returns_none_when_absent_fail_closed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Fail-closed (FR-004): absent ``mission_id`` returns ``None``, never
    the slug substituted as a fake identity."""
    feature_dir = tmp_path / "kitty-specs" / "my-mission-01KWDABC"
    feature_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text(json.dumps({}), encoding="utf-8")
    monkeypatch.setattr(identity, "_primary_runtime_feature_dir", lambda repo_root, mission_slug: feature_dir)

    result = identity._resolve_mission_ulid("my-mission-01KWDABC", tmp_path)

    assert result is None
    assert result != "my-mission-01KWDABC"
