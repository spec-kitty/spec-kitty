"""T032 — bare-project equality regression, 6 new gated kinds (FR-005).

charter-sole-door-bypass-closure-01KZ3WAA WP01. Non-fakeable proof (post-plan
squad correction): an existence check like ``assert wrapped.directives``
passes even if entries silently leaked away. This asserts EQUALITY between
the wrapped view (a bare ``PackContext`` -- no activated packs authored) and
the unwrapped view (``pack_context=None``) of the SAME inner service, per
contracts/charter-doctrine-service-contract.md's "Non-regression
obligations": both modes exist specifically to admit everything, so their
gated-property output must be identical for every one of the six newly-added
kinds (mirrors the pattern already proven for paradigms/procedures/
agent_profiles in ``tests/charter/test_resolver.py``).
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from charter.activation.pack_context import PackContext
from charter.activation.resolver import DoctrineService

pytestmark = pytest.mark.fast

#: (gated property name, PackContext field it reads) for the 6 new kinds.
_NEW_MECHANICAL_KINDS: tuple[tuple[str, str], ...] = (
    ("directives", "activated_directives"),
    ("tactics", "activated_tactics"),
    ("styleguides", "activated_styleguides"),
    ("toolguides", "activated_toolguides"),
    ("mission_step_contracts", "activated_mission_step_contracts"),
    ("glossary_packs", "activated_glossary_packs"),
)


def _mock_item(item_id: str) -> MagicMock:
    item = MagicMock()
    item.id = item_id
    return item


def _provision_mission_type_activation(tmp_path: Path) -> None:
    """Write the minimal config.yaml key required for ``PackContext.from_config``
    to construct at all (WP04, C-A1: a genuinely absent ``mission_type_activations``
    key hard-fails). This is orthogonal to the ``activated_*`` fields under test
    here -- those stay absent (``None``) exactly as the bare-project assertions
    below require.
    """
    kittify = tmp_path / ".kittify"
    kittify.mkdir(parents=True, exist_ok=True)
    (kittify / "config.yaml").write_text(
        "mission_type_activations:\n  - software-dev\n", encoding="utf-8"
    )


@pytest.mark.parametrize("prop, activated_field", _NEW_MECHANICAL_KINDS)
def test_bare_project_precondition_is_none(tmp_path: Path, prop: str, activated_field: str) -> None:
    """A bare (no ``.kittify/config.yaml``) project has every new field at ``None``."""
    _ = prop
    _provision_mission_type_activation(tmp_path)
    pack_ctx = PackContext.from_config(tmp_path)
    assert getattr(pack_ctx, activated_field) is None


@pytest.mark.parametrize("prop, activated_field", _NEW_MECHANICAL_KINDS)
def test_wrapped_equals_unwrapped_for_bare_project(
    tmp_path: Path, prop: str, activated_field: str
) -> None:
    """``wrapped.<prop> == unwrapped_inner.<prop>`` for a bare PackContext.

    ``wrapped`` uses a real, bare ``PackContext`` (constructed the same way
    production code does, via ``PackContext.from_config``); ``unwrapped_inner``
    uses ``pack_context=None`` directly. Both admit every artifact for this
    kind, so the two views of the SAME inner service must be equal --
    equality, not a truthiness/existence check, per the contract.
    """
    _ = activated_field
    inner = MagicMock()
    items = [_mock_item("alpha"), _mock_item("beta")]
    getattr(inner, prop).list_all.return_value = items

    _provision_mission_type_activation(tmp_path)
    bare_pack_ctx = PackContext.from_config(tmp_path)
    wrapped = DoctrineService(inner, pack_context=bare_pack_ctx)
    unwrapped_inner = DoctrineService(inner, pack_context=None)

    assert getattr(wrapped, prop) == getattr(unwrapped_inner, prop)
    assert getattr(wrapped, prop) == {"alpha": items[0], "beta": items[1]}


@pytest.mark.parametrize("prop, activated_field", _NEW_MECHANICAL_KINDS)
def test_explicit_activation_still_filters(tmp_path: Path, prop: str, activated_field: str) -> None:
    """Sanity control: an explicit activation set DOES filter (not vacuous).

    Without this, the equality tests above could pass even if the new
    property silently ignored the activation field entirely.
    """
    inner = MagicMock()
    alpha, beta = _mock_item("alpha"), _mock_item("beta")
    getattr(inner, prop).list_all.return_value = [alpha, beta]

    _provision_mission_type_activation(tmp_path)
    pack_ctx = replace(PackContext.from_config(tmp_path), **{activated_field: frozenset({"alpha"})})

    wrapped = DoctrineService(inner, pack_context=pack_ctx)
    result = getattr(wrapped, prop)

    assert "alpha" in result
    assert "beta" not in result
