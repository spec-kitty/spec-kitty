"""The verified-fact adoption of an unbound run uses the SAME strict matcher
as the ``RunIdentityMigrationRequired`` guard (owned-checkout-lifecycle-
authority WP11, review cycle 2 finding 2).

``_adopt_verified_unbound_run`` may only re-key a run that the guard would
itself have refused to resume: a ``mission_id``-less entry whose recorded
``mission_slug`` IS the owned mission's slug. An entry recorded for another
slug, or with no ``mission_slug`` at all (a pre-WP05 slug-keyed foreign
entry ``_canonicalize_run_index`` left un-rekeyed), is never adopted.
"""

from __future__ import annotations

from typing import Any

import pytest

from runtime.next.runtime_bridge_io import RunIdentityMigrationRequired, _adopt_verified_unbound_run, _entry_for_mission

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_SLUG = "owned-mission-01M2D900"
_ID = "01M2D900000000000000000001"


def _run(run_id: str, **extra: Any) -> dict[str, Any]:
    return {"run_id": run_id, "run_dir": f"/runs/{run_id}", "mission_type": "software-dev", "mission_key": "software-dev", **extra}


def test_the_reviewers_reproduction_is_not_adopted() -> None:
    """A foreign pre-WP05 slug-keyed entry (no ``mission_slug``) sitting beside
    its own canonical ``legacy-`` entry must not be re-keyed under the owned id."""
    index = {
        "other-mission": _run("foreign-1"),
        "legacy-other-mission": _run("foreign-2", mission_slug="other-mission", mission_id=None),
    }
    before = {key: dict(entry) for key, entry in index.items()}

    assert _adopt_verified_unbound_run(index, mission_slug=_SLUG, mission_id=_ID) is False

    assert index == before


@pytest.mark.parametrize(
    "entry",
    [
        pytest.param(_run("a", mission_slug="another-slug"), id="unbound-entry-for-a-different-slug"),
        pytest.param(_run("b"), id="unbound-entry-with-no-slug-field"),
        pytest.param(_run("c", mission_slug=_SLUG, mission_id="01M2D900000000000000000099"), id="entry-bound-to-another-mission-id"),
    ],
)
def test_only_this_slugs_unbound_run_is_ever_adopted(entry: dict[str, Any]) -> None:
    index = {"legacy-x": entry}

    assert _adopt_verified_unbound_run(index, mission_slug=_SLUG, mission_id=_ID) is False
    assert list(index) == ["legacy-x"]


def test_this_slugs_unbound_run_is_adopted_and_rekeyed() -> None:
    index = {f"legacy-{_SLUG}": _run("mine", mission_slug=_SLUG, mission_id=None)}

    assert _adopt_verified_unbound_run(index, mission_slug=_SLUG, mission_id=_ID) is True

    assert list(index) == [_ID]
    assert index[_ID]["run_id"] == "mine"
    assert index[_ID]["mission_id"] == _ID
    assert index[_ID]["mission_slug"] == _SLUG


@pytest.mark.parametrize(
    ("entry", "guard_refuses"),
    [
        pytest.param(_run("own", mission_slug=_SLUG), True, id="own-unbound"),
        pytest.param(_run("other", mission_slug="another-slug"), False, id="other-slug"),
        pytest.param(_run("noslug"), False, id="no-slug-field"),
        pytest.param(_run("bound", mission_slug=_SLUG, mission_id="01M2D900000000000000000099"), False, id="bound-elsewhere"),
    ],
)
def test_adoption_and_the_migration_guard_share_one_predicate(entry: dict[str, Any], guard_refuses: bool) -> None:
    """The guard refuses exactly the entries adoption is allowed to take."""
    guard_index = {"legacy-x": dict(entry)}
    if guard_refuses:
        with pytest.raises(RunIdentityMigrationRequired):
            _entry_for_mission(guard_index, mission_slug=_SLUG, mission_id=_ID)
    else:
        assert _entry_for_mission(guard_index, mission_slug=_SLUG, mission_id=_ID) is None

    adoption_index = {"legacy-x": dict(entry)}
    assert _adopt_verified_unbound_run(adoption_index, mission_slug=_SLUG, mission_id=_ID) is guard_refuses
