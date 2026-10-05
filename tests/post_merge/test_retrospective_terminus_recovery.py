"""The recovery sentence of the retrospective postcondition's failed-commit warning (#2280, #5751).

When the commit of the captured retrospective fails, the warning tells the operator how to get the
leftover artefacts committed. Three small functions decide that sentence, and they are tested here
directly, in the per-PR ``post_merge`` home, so a change to any of them is covered by the shard that
owns ``specify_cli/post_merge``:

* ``_has_recorded_identity``: can ``mission close`` derive a mid8 for this Mission at all;
* ``_rerun_command``: the idempotent command that re-runs the postcondition;
* ``_recovery_guidance``: the sentence itself, for a Mission with and without a recorded identity.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from specify_cli.post_merge import retrospective_terminus as terminus

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_SLUG = "recovery-mission"
_MISSION_ID = "01KX0000000000000000000000"


def _mission_dir(tmp_path: Path, meta: object | None) -> Path:
    directory = tmp_path / "kitty-specs" / _SLUG
    directory.mkdir(parents=True)
    if meta is not None:
        (directory / "meta.json").write_text(meta if isinstance(meta, str) else json.dumps(meta), encoding="utf-8")
    return directory


@pytest.mark.parametrize(
    ("meta", "expected"),
    [
        ({"mission_id": _MISSION_ID}, True),
        ({"mid8": "01KX0000"}, True),
        ({"mid8": "01KX0000", "mission_id": "short"}, True),
        ({"mission_slug": _SLUG}, False),
        ({"mission_id": "short"}, False),
        ({"mid8": "   ", "mission_id": ""}, False),
        ("{not json", False),
        (None, False),  # no meta.json at all
    ],
)
def test_a_recorded_identity_is_a_mid8_or_a_long_enough_mission_id(tmp_path: Path, meta: object | None, expected: bool) -> None:
    assert terminus._has_recorded_identity(_mission_dir(tmp_path, meta)) is expected


def test_the_rerun_command_closes_the_mission_and_discards_only_an_abandoned_one() -> None:
    assert terminus._rerun_command(_SLUG, "runtime_post_completion") == f"spec-kitty mission close --mission {_SLUG}"
    assert terminus._rerun_command(_SLUG, "runtime_abandoned") == f"spec-kitty mission close --mission {_SLUG} --discard --force"


def test_recovery_guidance_for_a_mission_with_an_identity_is_the_rerun_alone(tmp_path: Path) -> None:
    feature_dir = _mission_dir(tmp_path, {"mission_id": _MISSION_ID})

    assert terminus._recovery_guidance(_SLUG, feature_dir, "runtime_post_completion") == f"re-run `spec-kitty mission close --mission {_SLUG}` to commit them."
    assert terminus._recovery_guidance(_SLUG, feature_dir, "runtime_abandoned").startswith(f"re-run `spec-kitty mission close --mission {_SLUG} --discard --force`")


def test_recovery_guidance_for_a_mission_without_an_identity_mints_it_first_and_says_the_backfill_leaves_meta_modified(tmp_path: Path) -> None:
    feature_dir = _mission_dir(tmp_path, {"mission_slug": _SLUG})

    guidance = terminus._recovery_guidance(_SLUG, feature_dir, "runtime_post_completion")

    assert "no recorded identity" in guidance
    assert f"`spec-kitty migrate backfill-identity --mission {_SLUG}`" in guidance
    assert f"then `spec-kitty mission close --mission {_SLUG}`" in guidance
    assert "the backfill leaves meta.json modified, so commit that too." in guidance
    assert "--discard" not in guidance
    assert "--discard --force" in terminus._recovery_guidance(_SLUG, feature_dir, "runtime_abandoned")
