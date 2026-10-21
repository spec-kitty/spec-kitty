"""The prepared pack-skill projection honours the effective deny (WP05: M6, FR-006).

``skill_preparation`` reads the in-force set from ``explicit_activated_skills``
and ``PackContext.activated_skills`` (the absent-key "required" default). Both
are deny-netted, so a denied non-required skill is never prepared, under an
absent allow list and under a present one, while a required skill stays
projected even with a stale deny entry. Ledger-seeded.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from charter.activation.pack_context import explicit_activated_skills
from charter.activation.skill_preparation import establish_in_force_skill_ids, prepare_project_skill_activations
from tests._factories.activation_ledger import seed_activation_ledger
from tests.charter import skill_pack_support as support

pytestmark = [pytest.mark.integration]

_DENIED = "deploy-helper"
_KEPT = "lint-helper"
_REQUIRED = "required-one"


def _project(tmp_path: Path, *, required: list[str] | None = None, **ledger: list[str]) -> Path:
    pack = tmp_path / "pack"
    pack.mkdir(parents=True, exist_ok=True)
    for skill_id in (_DENIED, _KEPT, _REQUIRED):
        support.write_skill(pack, skill_id)
    support.write_org_charter(pack, required_skills=required, namespace="acme")
    root = tmp_path / "project"
    config = root / ".kittify" / "config.yaml"
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text(f"charter_packs:\n  org:\n    packs:\n      - name: acme\n        local_path: {pack}\n", encoding="utf-8")
    seed_activation_ledger(root, mission_type_activations=["software-dev"], **ledger)
    return root


def _prepared(root: Path) -> set[str]:
    return {skill.id for skill in prepare_project_skill_activations(root)}


def test_a_denied_skill_leaves_a_present_list_projection(tmp_path: Path) -> None:
    root = _project(tmp_path, activated_skills=[_DENIED, _KEPT])
    assert explicit_activated_skills(root) == frozenset({_DENIED, _KEPT})
    assert _prepared(root) == {_DENIED, _KEPT}  # positive control

    seed_activation_ledger(root, deactivated_skills=[_DENIED])
    assert explicit_activated_skills(root) == frozenset({_KEPT})
    assert establish_in_force_skill_ids(root).ids == frozenset({_KEPT})
    assert _prepared(root) == {_KEPT}


def test_a_denied_non_required_skill_is_absent_under_the_required_default(tmp_path: Path) -> None:
    root = _project(tmp_path, required=[_REQUIRED])
    assert explicit_activated_skills(root) is None
    assert _prepared(root) == {_REQUIRED}  # positive control: the default projects the floor

    seed_activation_ledger(root, deactivated_skills=[_DENIED])
    assert establish_in_force_skill_ids(root).ids == frozenset({_REQUIRED})
    assert _prepared(root) == {_REQUIRED}


def test_a_required_skill_stays_projected_despite_a_stale_deny(tmp_path: Path) -> None:
    root = _project(tmp_path, required=[_REQUIRED], activated_skills=[_REQUIRED, _KEPT])
    assert _prepared(root) == {_REQUIRED, _KEPT}

    seed_activation_ledger(root, deactivated_skills=[_REQUIRED, _KEPT])
    assert explicit_activated_skills(root) == frozenset({_REQUIRED})
    assert _prepared(root) == {_REQUIRED}


def test_denying_the_whole_present_list_establishes_an_empty_set(tmp_path: Path) -> None:
    root = _project(tmp_path, activated_skills=[_DENIED])
    assert _prepared(root) == {_DENIED}

    seed_activation_ledger(root, deactivated_skills=[_DENIED])
    assert establish_in_force_skill_ids(root).is_empty
    assert _prepared(root) == set()
