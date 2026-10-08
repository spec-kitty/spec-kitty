"""T014 — proof that `pack_context=None` is a genuine unfiltered-diagnostic mode.

charter-sole-door-bypass-closure-01KZ3WAA WP03 (FR-002). WP03 migrated
``_doctrine_collect.py``'s 4 diagnostic sites (``_collect_profile_health``,
``_collect_glossary_pack_health``, ``_collect_doctrine_collisions``,
``_build_selection_block``) from raw ``charter.offering.service.CharterOfferingService(...)``
construction onto ``charter.activation.resolver.DoctrineService(inner, pack_context=None)``
-- the sanctioned unfiltered-diagnostic construction shape (data-model.md
"unfiltered-diagnostic contract"). The WP03 task file names the exact risk
this file guards against: "a plain activation-aware swap compiles and looks
correct but silently narrows doctor/health output" -- so every assertion
below is an EQUALITY check against an independently-computed raw projection,
never an existence/non-empty check (data-model.md "Non-regression
obligations": ``assert svc.directives`` would still pass even if entries
silently leaked away).

Two distinct regressions are guarded here:

1. The nine gated *properties* (``paradigms`` .. ``glossary_packs``) must
   return the identical, full catalog under ``pack_context=None`` that a
   raw, unwrapped ``charter.offering.service.CharterOfferingService`` would expose -- even
   for a project where SOME packs are genuinely deactivated (a real
   ``PackContext`` that WOULD narrow the result if it were used instead).
2. The two raw-*repository* accessors (``agent_profile_repository``,
   ``raw_repository(kind)``) -- the ones the real migrated sites actually
   call, because they need ``.get_provenance()``/``.skipped_profiles()``/
   ``.list_all()`` methods a filtered ``dict`` does not have -- must return
   the raw repository object itself, unaffected by ``pack_context``, since
   these accessors are documented as never gated (contracts/
   charter-doctrine-service-contract.md "Lineage/mutation accessor
   semantics").
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from charter.activation.pack_context import PackContext
from charter.activation.resolver import DoctrineService

pytestmark = pytest.mark.fast

#: All nine gated kinds a WP03 diagnostic site may touch through the wrapper
#: (data-model.md "Gated properties" -- the pre-existing 3 plus FR-005's 6).
_ALL_GATED_KINDS: tuple[str, ...] = (
    "paradigms",
    "procedures",
    "agent_profiles",
    "directives",
    "tactics",
    "styleguides",
    "toolguides",
    "mission_step_contracts",
    "glossary_packs",
)

#: (kind, PackContext activation field) pairs, for parametrized filtering
#: assertions.
_KIND_TO_FIELD: tuple[tuple[str, str], ...] = (
    ("paradigms", "activated_paradigms"),
    ("procedures", "activated_procedures"),
    ("agent_profiles", "activated_agent_profiles"),
    ("directives", "activated_directives"),
    ("tactics", "activated_tactics"),
    ("styleguides", "activated_styleguides"),
    ("toolguides", "activated_toolguides"),
    ("mission_step_contracts", "activated_mission_step_contracts"),
    ("glossary_packs", "activated_glossary_packs"),
)


def _key_attr(kind: str) -> str:
    """The attribute the real gated property keys its dict by.

    ``agent_profiles`` keys by ``profile_id``; every other kind keys by
    ``id`` (mirrors ``charter/resolver.py``'s per-property comprehensions).
    """
    return "profile_id" if kind == "agent_profiles" else "id"


def _mock_item(kind: str, item_id: str) -> MagicMock:
    item = MagicMock()
    setattr(item, _key_attr(kind), item_id)
    return item


def _mock_inner() -> MagicMock:
    """A raw-service double exposing two named items per gated kind."""
    inner = MagicMock()
    for kind in _ALL_GATED_KINDS:
        items = [_mock_item(kind, f"{kind}-alpha"), _mock_item(kind, f"{kind}-beta")]
        getattr(inner, kind).list_all.return_value = items
    return inner


def _raw_projection(inner: object, kind: str) -> dict[str, object]:
    """Independently compute the id-keyed dict a raw, unwrapped service's
    catalog for *kind* projects to -- WITHOUT calling any
    ``charter.activation.resolver.DoctrineService`` code, so the comparison below is a
    real check, not a tautological self-comparison (the exact MAJOR 3 defect
    WP01's cycle-1 review found and required fixed elsewhere in this
    mission).
    """
    key_attr = _key_attr(kind)
    return {getattr(item, key_attr): item for item in getattr(inner, kind).list_all()}


def _some_packs_deactivated_context(repo_root: Path) -> PackContext:
    """A real ``PackContext`` that narrows every gated kind to exactly the
    ``-alpha`` item -- i.e. "some packs deactivated" for every kind, not the
    bare/absent-key default. If ``pack_context=None`` construction ever
    accidentally consulted this context instead of truly ignoring it (the
    regression this file exists to catch), every property below would come
    back with 1 item instead of 2.
    """
    narrowed = {field: frozenset({f"{kind}-alpha"}) for kind, field in _KIND_TO_FIELD}
    return PackContext(
        activated_kinds=frozenset(kind for kind, _ in _KIND_TO_FIELD),
        activated_mission_types=frozenset({"software-dev"}),
        pack_roots=(),
        org_pack_names=(),
        repo_root=repo_root,
        **narrowed,
    )


# ---------------------------------------------------------------------------
# 1. Gated properties: pack_context=None == raw projection (per kind)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("kind", _ALL_GATED_KINDS)
def test_unfiltered_mode_equals_raw_projection(tmp_path: Path, kind: str) -> None:
    """``DoctrineService(inner, pack_context=None).<kind>`` equals the raw,
    independently-computed projection -- for a project where every kind is
    genuinely (narrowly) activated, i.e. "some packs deactivated" is real,
    not the vacuous no-config default.
    """
    inner = _mock_inner()
    deactivated_ctx = _some_packs_deactivated_context(tmp_path)

    # Sanity control: the SAME inner, wrapped with the real (narrowing)
    # PackContext, must NOT equal the raw projection -- otherwise this test
    # would pass even if pack_context had no effect at all.
    narrowed = getattr(DoctrineService(inner, pack_context=deactivated_ctx), kind)
    raw = _raw_projection(inner, kind)
    assert narrowed != raw
    assert narrowed == {f"{kind}-alpha": raw[f"{kind}-alpha"]}

    # The actual T014 assertion: pack_context=None ignores the deactivation
    # entirely and matches the raw, unwrapped catalog -- equality, not an
    # existence/non-empty check.
    unfiltered = getattr(DoctrineService(inner, pack_context=None), kind)
    assert unfiltered == raw


@pytest.mark.parametrize("kind", _ALL_GATED_KINDS)
def test_unfiltered_mode_is_independent_of_which_pack_context_object_is_discarded(
    tmp_path: Path, kind: str
) -> None:
    """Passing ``pack_context=None`` is not merely "happens to match this
    particular PackContext" -- it must hold no matter how aggressively a real
    context WOULD have narrowed the result. Uses an explicit full opt-out
    (``frozenset()``) rather than a partial one, the most aggressive three-
    state case (data-model.md's three-state contract: empty frozenset ->
    "return nothing").
    """
    inner = _mock_inner()
    fully_deactivated: dict[str, frozenset[str]] = {
        field: frozenset() for _kind, field in _KIND_TO_FIELD
    }
    pack_ctx = PackContext(
        activated_kinds=frozenset(),
        activated_mission_types=frozenset(),
        pack_roots=(),
        org_pack_names=(),
        repo_root=tmp_path,
        **fully_deactivated,
    )

    # Sanity control: fully deactivated really does mean empty.
    assert getattr(DoctrineService(inner, pack_context=pack_ctx), kind) == {}

    unfiltered = getattr(DoctrineService(inner, pack_context=None), kind)
    assert unfiltered == _raw_projection(inner, kind)


# ---------------------------------------------------------------------------
# 2. Raw-repository accessors: never gated, regardless of pack_context
# ---------------------------------------------------------------------------


def test_agent_profile_repository_accessor_is_unaffected_by_pack_context(
    tmp_path: Path,
) -> None:
    """``agent_profile_repository`` returns the raw repository object itself
    -- the accessor ``_collect_profile_health`` (T013) uses for
    ``get_provenance()``/``skipped_profiles()``, neither of which exists on
    the gated ``agent_profiles`` dict property. This must hold identically
    whether ``pack_context`` is ``None`` or a real, narrowing context --
    the accessor is documented as never gated (contracts/
    charter-doctrine-service-contract.md).
    """
    inner = _mock_inner()
    deactivated_ctx = _some_packs_deactivated_context(tmp_path)

    unfiltered_repo = DoctrineService(inner, pack_context=None).agent_profile_repository
    filtered_ctx_repo = DoctrineService(inner, pack_context=deactivated_ctx).agent_profile_repository

    assert unfiltered_repo is inner.agent_profiles
    assert filtered_ctx_repo is inner.agent_profiles
    assert unfiltered_repo is filtered_ctx_repo


@pytest.mark.parametrize("kind", _ALL_GATED_KINDS)
def test_raw_repository_accessor_is_unaffected_by_pack_context(
    tmp_path: Path, kind: str
) -> None:
    """``raw_repository(kind)`` -- the generic accessor
    ``_collect_glossary_pack_health`` and ``_build_selection_block`` (T013)
    use for ``.list_all()``/``.get_provenance()`` -- returns the raw
    repository object regardless of ``pack_context``, for every one of the
    nine gated kinds.
    """
    inner = _mock_inner()
    deactivated_ctx = _some_packs_deactivated_context(tmp_path)

    unfiltered = DoctrineService(inner, pack_context=None).raw_repository(kind)
    filtered_ctx = DoctrineService(inner, pack_context=deactivated_ctx).raw_repository(kind)

    assert unfiltered is getattr(inner, kind)
    assert filtered_ctx is getattr(inner, kind)


def test_raw_repository_returns_none_for_a_non_gated_kind() -> None:
    """A kind outside the nine gated kinds (e.g. ``assets``, not charter-
    activatable) degrades to ``None`` rather than raising -- the documented
    degrade-silently contract ``raw_repository`` replaces at its
    ``org_layer.py`` call sites.
    """
    inner = _mock_inner()
    service = DoctrineService(inner, pack_context=None)
    assert service.raw_repository("assets") is None
