"""#6320 WP01 -- the fail-closed write-target gate is owned-aware.

An owned-only mission has its ``meta.json`` in the owned checkout, never at the
repository root. Without the owned fact the terminus-write gate must still
refuse (negative control); with it, the gate resolves (positive control).
The three unrelated callers pass no ``owned`` and must resolve unchanged.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mission_runtime import ActionContextError, MissionArtifactKind, MissionTopology
from mission_runtime.owned_checkout import OwnedCheckout
from mission_runtime.write_target_degrade import resolve_write_target_or_degrade

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_SLUG = "owned-gate-6320-01M6320A"
_KIND = MissionArtifactKind.ISSUE_MATRIX


def _owned_only_mission(tmp_path: Path) -> OwnedCheckout:
    repository_root = tmp_path / "R"
    repository_root.mkdir()
    mission_dir = tmp_path / "P" / "kitty-specs" / _SLUG
    mission_dir.mkdir(parents=True)
    (mission_dir / "meta.json").write_text(
        json.dumps(
            {
                "mission_id": "01M6320A000000000000000001",
                "mission_slug": _SLUG,
                "slug": _SLUG,
                "mission_type": "software-dev",
                "topology": MissionTopology.SINGLE_BRANCH.value,
                "target_branch": "main",
            }
        ),
        encoding="utf-8",
    )
    return OwnedCheckout._mint(
        repository_root=repository_root,
        owned_root=tmp_path / "P",
        mission_dir=mission_dir,
        mission_slug=_SLUG,
        topology=MissionTopology.SINGLE_BRANCH,
        write_branch="main",
    )


def test_owned_only_mission_passes_gate_but_primary_root_still_fails_closed(tmp_path: Path) -> None:
    fact = _owned_only_mission(tmp_path)

    # Negative control: same fixture, no owned fact -> fail-closed (unchanged).
    with pytest.raises(ActionContextError):
        resolve_write_target_or_degrade(fact.repository_root, _SLUG, _KIND, degrade_ref=None, terminus_write=True)

    # Positive: the owned fact reaches the gate.
    target = resolve_write_target_or_degrade(fact.repository_root, _SLUG, _KIND, degrade_ref=None, terminus_write=True, owned=fact)
    assert target.ref == "main"


@pytest.mark.parametrize("terminus_write,degrade_ref", [(False, "fallback"), (False, None), (True, None)])
def test_unrelated_callers_unchanged_without_owned(tmp_path: Path, terminus_write: bool, degrade_ref: str | None) -> None:
    """No-meta mission, no owned: each caller shape behaves exactly as before."""
    root = tmp_path / "plain"
    root.mkdir()
    if degrade_ref is not None and not terminus_write:
        # fail-open caller: degrades to its ref, with and without the explicit default.
        a = resolve_write_target_or_degrade(root, "no-such-mission", _KIND, degrade_ref=degrade_ref, terminus_write=terminus_write)
        b = resolve_write_target_or_degrade(root, "no-such-mission", _KIND, degrade_ref=degrade_ref, terminus_write=terminus_write, owned=None)
        assert a == b and a.ref == degrade_ref
    else:
        with pytest.raises(ActionContextError) as plain:
            resolve_write_target_or_degrade(root, "no-such-mission", _KIND, degrade_ref=degrade_ref, terminus_write=terminus_write)
        with pytest.raises(ActionContextError) as explicit:
            resolve_write_target_or_degrade(root, "no-such-mission", _KIND, degrade_ref=degrade_ref, terminus_write=terminus_write, owned=None)
        # Non-vacuous: a real fail-closed code is recorded (not two empty strings)
        # and is identical with and without the explicit owned=None default.
        assert plain.value.code and plain.value.code == explicit.value.code
