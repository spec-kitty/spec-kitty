"""T004 — unified builder identical output across all 9 gated properties (FR-008).

charter-sole-door-bypass-closure-01KZ3WAA WP01. Proves the C-001 unification
closed a real divergence: prior to this mission,
``specify_cli.doctrine_service_factory.build_active_charter_service``
and ``charter.activation.active_charter_service_builder._build_active_charter_service``
were two independent implementations that silently disagreed on two axes
(``active_languages`` computation and ``org_roots`` self-resolution). Both are
now thin call-throughs to the single canonical
:func:`charter.activation.active_charter_service_builder.build_active_charter_service`.

Per the post-tasks squad's sequencing correction (data-model.md "Sequencing
note superseded"), this is written ONCE against the full 9-kind surface in a
single unstaged pass — not the originally-planned 3-kind proof extended
later.

Cycle-2 review fix (MAJOR 3): ``test_gated_property_identical_across_entry_points``
previously asserted ``getattr(charter_builder(repo_root), prop) ==
getattr(specify_cli_builder(repo_root), prop)`` — but
``specify_cli_builder`` *is* ``charter_builder`` (proven by
``test_specify_cli_entry_point_delegates_to_charter_builder`` below), so that
reduced to ``f(x) == f(x)``: a self-comparison that cannot fail and proves
nothing about the gated properties themselves. It is replaced by
``test_gated_property_matches_raw_repository_for_bare_project``, which
compares each entry point's gated view against an INDEPENDENTLY-derived
expectation built from the raw repository via the public
:meth:`charter.activation.resolver.ActiveCharterService.raw_repository` accessor (FR-002
Option A) — never ``._inner`` directly (MINOR 4: avoids tripping WP04/T017's
forthcoming zero-tolerance ``._inner``-on-doctrine-service gate from a test
file outside ``src/charter/**``). This also proves the bare-project catalog
is not narrowed by either builder path (the T032 shape, applied here to the
builder entry points rather than a hand-constructed wrapper).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from ruamel.yaml import YAML

from tests._support.org_pack_config import write_org_packs
from charter.activation.active_charter_service_builder import (
    build_active_charter_service as charter_builder,
)
from specify_cli.doctrine_service_factory import (
    build_active_charter_service as specify_cli_builder,
)

pytestmark = pytest.mark.fast

#: The full 9-kind gated-property surface (paradigms/procedures/agent_profiles
#: pre-existing; the other six added by this WP's T026-T031).
_GATED_PROPERTIES: tuple[str, ...] = (
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


def _write_yaml(path: Path, data: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    yaml = YAML()
    yaml.default_flow_style = False
    with path.open("w", encoding="utf-8") as fh:
        yaml.dump(data, fh)


def _configure_language_diverse_fixture(repo_root: Path) -> None:
    """Give the fixture a resolvable, non-empty ``active_languages`` signal.

    Exercises the ``active_languages=infer_repo_languages(repo_root)`` axis
    (the ``charter`` builder's pre-unification behaviour) so the assertion
    below proves genuine resolution happened, not two vacuous empty results.
    """
    _write_yaml(
        repo_root / ".kittify" / "charter" / "interview" / "answers.yaml",
        {
            "schema_version": "1.0.0",
            "mission": "software-dev",
            "profile": "minimal",
            "answers": {"tech_stack": "We use python and pytest for everything."},
            "selected_paradigms": [],
            "selected_directives": [],
            "available_tools": [],
        },
    )


def _configure_org_pack(repo_root: Path, org_root: Path) -> None:
    """Register an on-disk org pack so ``org_roots`` self-resolution is non-trivial.

    Exercises the ``org_roots`` always-self-resolved axis (the
    ``specify_cli`` builder's pre-unification behaviour).
    """
    org_root.mkdir(parents=True, exist_ok=True)
    write_org_packs(repo_root, [{"name": "acme", "local_path": org_root}])


def _configure_provisioned_activation(repo_root: Path) -> None:
    """Write the minimal ``mission_type_activations`` key WP04 now requires.

    ``PackContext.from_config`` (WP04, C-A1) fails closed when this key is
    absent from ``.kittify/config.yaml`` -- unrelated to the gated-property
    axes this module actually exercises. No other activation key is written,
    so every OTHER gated property's ``PackContext.activated_*`` field stays
    the bare-project ``None`` ("admit all") the tests below depend on.
    """
    _write_yaml(
        repo_root / ".kittify" / "config.yaml",
        {"mission_type_activations": ["software-dev"]},
    )


@pytest.fixture()
def repo_root(tmp_path: Path) -> Path:
    """A repo root exercising BOTH former call sites' fuller-behaviour axes."""
    root = tmp_path / "repo"
    root.mkdir()
    _configure_language_diverse_fixture(root)
    # Must run BEFORE ``_configure_org_pack``: that helper merges
    # into an existing ``config.yaml`` (reads-then-writes), whereas this
    # helper's ``_write_yaml`` call replaces the file outright -- reversing
    # the order would silently drop the org-pack registration.
    _configure_provisioned_activation(root)
    _configure_org_pack(root, tmp_path / "org")
    return root


def test_specify_cli_entry_point_delegates_to_charter_builder(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """C-001: a real behavioural proof that specify_cli holds a call-through.

    Patching the charter-layer canonical builder must be observed by the
    ``specify_cli`` entry point -- proving it is a thin re-export, not an
    independent second implementation that merely happens to agree today.
    """
    import charter.activation.active_charter_service_builder as builder_module
    from specify_cli.doctrine_service_factory import (
        build_active_charter_service as specify_cli_entry_point,
    )

    sentinel = object()
    calls: list[Path] = []

    def _fake_builder(repo_root: Path) -> object:
        calls.append(repo_root)
        return sentinel

    monkeypatch.setattr(builder_module, "build_active_charter_service", _fake_builder)

    result = specify_cli_entry_point(tmp_path)

    assert result is sentinel
    assert calls == [tmp_path]


#: A gated kind whose repository actually consumes ``active_languages``
#: (``paradigms``/``directives``/``mission_step_contracts``/``glossary_packs``
#: do not — see ``src/charter/offering/service.py``'s per-property construction).
#: Used by the two axis tests below to observe the service-level resolution.
_LANGUAGE_SCOPED_KIND = "tactics"

#: Per-kind key attribute for building an ``{key: item}`` dict from
#: ``list_all()`` — mirrors each gated property's own key extraction in
#: ``charter.activation.resolver.ActiveCharterService`` (``agent_profiles`` keys on
#: ``profile_id``; every other kind keys on ``id``).
_KEY_ATTR_BY_PROP: dict[str, str] = {"agent_profiles": "profile_id"}


def test_active_languages_resolution_identical_across_entry_points(repo_root: Path) -> None:
    """FR-008 axis 1: ``active_languages`` is always computed, identically.

    MINOR 4 cycle-2 fix: reads the resolved value off a raw repository via
    the public :meth:`~charter.activation.resolver.ActiveCharterService.raw_repository`
    accessor (FR-002 Option A) — every repository the service constructs
    carries the same ``_active_languages`` value the service resolved — rather
    than reaching into the wrapper's ``._inner`` directly. Uses ``tactics``
    (not ``paradigms``) because ``paradigms`` does not consume
    ``active_languages`` at all (``src/charter/offering/service.py``).
    """
    from charter.activation.language_scope import infer_repo_languages

    expected = infer_repo_languages(repo_root)
    assert expected, "fixture must exercise a non-empty active_languages resolution"

    result_a = charter_builder(repo_root)
    result_b = specify_cli_builder(repo_root)

    repo_a = result_a.raw_repository(_LANGUAGE_SCOPED_KIND)
    repo_b = result_b.raw_repository(_LANGUAGE_SCOPED_KIND)
    assert repo_a._active_languages == repo_b._active_languages  # noqa: SLF001
    assert list(repo_a._active_languages) == expected  # noqa: SLF001


def test_org_roots_resolution_identical_across_entry_points(repo_root: Path) -> None:
    """FR-008 axis 2: ``org_roots`` is always self-resolved, identically.

    MINOR 4 cycle-2 fix: compares the per-kind org directories a raw
    repository was constructed with (derived 1:1 from ``org_roots``) via the
    public :meth:`~charter.activation.resolver.ActiveCharterService.raw_repository` accessor,
    rather than reaching into the wrapper's ``._inner._org_roots`` directly.
    """
    result_a = charter_builder(repo_root)
    result_b = specify_cli_builder(repo_root)

    repo_a = result_a.raw_repository(_LANGUAGE_SCOPED_KIND)
    repo_b = result_b.raw_repository(_LANGUAGE_SCOPED_KIND)
    assert repo_a._org_dirs == repo_b._org_dirs  # noqa: SLF001
    assert repo_a._org_dirs, "fixture must exercise a non-empty org_roots resolution"


def _expected_dict_from_raw_repository(service: object, prop: str) -> dict[str, object]:
    """Independently derive the expected gated-property dict from the raw repository.

    Uses the public :meth:`charter.activation.resolver.ActiveCharterService.raw_repository`
    accessor (FR-002 Option A) rather than reaching into ``._inner`` directly
    (MINOR 4) — the non-fakeable reference the MAJOR 3 fix below compares
    against. Keys on the same attribute each gated property itself uses
    (``profile_id`` for ``agent_profiles``, ``id`` for everything else).
    """
    raw_repo = service.raw_repository(prop)  # type: ignore[attr-defined]
    key_attr = _KEY_ATTR_BY_PROP.get(prop, "id")
    return {getattr(item, key_attr): item for item in raw_repo.list_all()}


@pytest.mark.parametrize("prop", _GATED_PROPERTIES)
def test_gated_property_matches_raw_repository_for_bare_project(repo_root: Path, prop: str) -> None:
    """Non-fakeable: the gated dict equals an INDEPENDENTLY-derived raw projection.

    MAJOR 3 cycle-1 finding: the previous version of this test compared
    ``charter_builder(x).<prop>`` against ``specify_cli_builder(x).<prop>`` —
    but ``specify_cli_builder`` *is* ``charter_builder``
    (``test_specify_cli_entry_point_delegates_to_charter_builder`` above
    proves the delegation by monkeypatch), so that assertion reduced to
    ``f(x) == f(x)``: it cannot fail and proves nothing about the gated
    properties. This fixture's ``answers.yaml`` selects no
    paradigms/directives and writes no ``.kittify/config.yaml`` activation
    block, so every gated property's corresponding ``PackContext.activated_*``
    field is the bare-project ``None`` ("admit all") — the gated dict must
    therefore equal the FULL raw catalog for BOTH former call sites, proving
    the unified builder neither narrows nor silently diverges from the raw
    repository it wraps.
    """
    result_a = charter_builder(repo_root)
    result_b = specify_cli_builder(repo_root)

    expected_a = _expected_dict_from_raw_repository(result_a, prop)
    expected_b = _expected_dict_from_raw_repository(result_b, prop)

    assert getattr(result_a, prop) == expected_a
    assert getattr(result_b, prop) == expected_b
    # Transitively also proves both entry points agree with each other.
    assert getattr(result_a, prop) == getattr(result_b, prop)


#: Built-in profiles scoped to a specific language via ``applies_to_languages``
#: — the exact set the FR-008 regression silently dropped on a truly bare
#: project (no compiled charter, no interview transcript at all).
_LANGUAGE_SCOPED_BUILTIN_PROFILE_IDS: tuple[str, ...] = (
    "python-pedro",
    "frontend-freddy",
    "java-jenny",
    "node-norris",
)


def test_bare_project_admits_language_scoped_builtin_profiles(tmp_path: Path) -> None:
    """Regression (charter-sole-door-bypass-closure-01KZ3WAA landing-fold fix).

    A project with NO compiled charter (``.kittify/charter/charter.yaml``)
    and NO interview transcript (``.kittify/charter/interview/answers.yaml``)
    has no active-language *signal at all* -- ``infer_repo_languages`` must
    resolve this to ``None`` ("unknown"), not an explicitly empty list.
    ``charter.offering.shared.scoping.applies_to_languages_match`` treats ``None`` as
    admit-all and an empty active set as admit-none for scoped artifacts, so
    conflating "no signal" with "explicitly no languages" silently drops
    every language-scoped built-in profile from the catalog.

    Confirmed red against the pre-fix code: ``active_languages=
    infer_repo_languages(repo_root)`` computed ``[]`` for this exact bare
    fixture (no compiled charter, no interview answers), and the four
    language-scoped built-ins below were absent from
    ``build_active_charter_service(bare_root).agent_profiles``
    (14 profiles instead of 18) -- matching the two independent adversarial
    review lenses that reproduced this on PR #3175.
    """
    bare_root = tmp_path / "bare-project"
    bare_root.mkdir()
    # Deliberately no compiled charter, no interview transcript -- the "truly
    # nothing configured yet" case for the active-language signal this test
    # exercises. WP04 (C-A1) now fail-closes ``PackContext.from_config`` on
    # any repo_root lacking ``mission_type_activations``, so a minimal
    # ``config.yaml`` carrying ONLY that key is provisioned here -- it does
    # not touch the charter.yaml / interview-transcript axes this test is
    # actually about.
    _configure_provisioned_activation(bare_root)

    service = charter_builder(bare_root)
    catalog_ids = set(service.agent_profiles)

    missing = [pid for pid in _LANGUAGE_SCOPED_BUILTIN_PROFILE_IDS if pid not in catalog_ids]
    assert not missing, (
        f"language-scoped built-in profiles dropped from a bare project's catalog: {missing} "
        f"(catalog had {len(catalog_ids)} profiles: {sorted(catalog_ids)})"
    )
