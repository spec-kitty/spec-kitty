"""#3816 sibling — the gated ``DoctrineService.directives`` property must
reconcile the two directive identity spaces.

``config.yaml`` stores ``activated_directives`` as file-stem **slugs**
(``025-boy-scout-rule``), exactly as the ``--json`` surface advertises them,
while the ``DirectiveRepository`` keys its items by the canonical model
``id`` (``DIRECTIVE_025``). The gated property builds ``{item.id: item}`` and
membership-tests each key against ``activated_directives``. Without
normalizing the two spaces onto one form, EVERY directive is silently
dropped whenever activation is configured — the same slug-vs-``DIRECTIVE_NNN``
root cause as the ``--include directive:<id>`` selector bug (#3816), at a
distinct call site (``charter.activation.resolver.DoctrineService.directives``).

This is the sole gated kind affected: tactics/styleguides/etc. carry an
``id`` that already equals their slug, so their activated set and their item
keys coincide. Directives are the one kind where the two diverge.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from charter.activation.pack_context import PackContext
from charter.activation.resolver import DoctrineService

pytestmark = pytest.mark.fast


def _directive(directive_id: str) -> MagicMock:
    item = MagicMock()
    item.id = directive_id
    return item


def _ctx_activating_slugs(repo_root: Path, slugs: frozenset[str]) -> PackContext:
    """A hermetic PackContext activating directives by their file-stem slug,
    the exact shape ``PackContext.from_config`` reads out of ``config.yaml``.
    """
    return PackContext(
        activated_kinds=frozenset({"directives"}),
        activated_mission_types=frozenset({"software-dev"}),
        pack_roots=(),
        org_pack_names=(),
        repo_root=repo_root,
        activated_directives=slugs,
    )


def test_slug_activated_directives_survive_the_gate(tmp_path: Path) -> None:
    boy_scout = _directive("DIRECTIVE_025")
    architecture = _directive("DIRECTIVE_001")
    inner = MagicMock()
    inner.directives.list_all.return_value = [boy_scout, architecture]

    ctx = _ctx_activating_slugs(
        tmp_path,
        frozenset({"025-boy-scout-rule", "001-architectural-integrity-standard"}),
    )

    gated = DoctrineService(inner, pack_context=ctx).directives

    # The activated directives resolve, keyed by their canonical id.
    assert set(gated) == {"DIRECTIVE_025", "DIRECTIVE_001"}
    assert gated["DIRECTIVE_025"] is boy_scout
    assert gated["DIRECTIVE_001"] is architecture


def test_gate_still_drops_non_activated_directives(tmp_path: Path) -> None:
    # Non-vacuity: the gate must still narrow. Activate only one slug and
    # confirm the other directive is excluded — otherwise the test above
    # could pass on a gate that had simply stopped filtering.
    boy_scout = _directive("DIRECTIVE_025")
    architecture = _directive("DIRECTIVE_001")
    inner = MagicMock()
    inner.directives.list_all.return_value = [boy_scout, architecture]

    ctx = _ctx_activating_slugs(tmp_path, frozenset({"025-boy-scout-rule"}))

    gated = DoctrineService(inner, pack_context=ctx).directives

    assert set(gated) == {"DIRECTIVE_025"}


def test_canonical_form_in_activated_set_also_resolves(tmp_path: Path) -> None:
    # An activated set already in canonical DIRECTIVE_NNN form must keep
    # working — the fix normalizes both sides, it does not swap one broken
    # keyspace for another.
    boy_scout = _directive("DIRECTIVE_025")
    inner = MagicMock()
    inner.directives.list_all.return_value = [boy_scout]

    ctx = _ctx_activating_slugs(tmp_path, frozenset({"DIRECTIVE_025"}))

    gated = DoctrineService(inner, pack_context=ctx).directives

    assert set(gated) == {"DIRECTIVE_025"}


@pytest.mark.parametrize("activation", ["foo", "ACME-001-FOO", "ACME_001_FOO", "acme-001-foo"])
def test_org_stem_and_literal_id_do_not_conflate_aliases(tmp_path: Path, activation: str) -> None:
    from charter.activation.doctrine_service_builder import build_activation_aware_doctrine_service

    (tmp_path / ".kittify").mkdir()
    pack = tmp_path / "org"
    (pack / "directives").mkdir(parents=True)
    for stem, identity in [("foo", "ACME-001-FOO"), ("alias", "ACME_001_FOO")]:
        (pack / "directives" / f"{stem}.directive.yaml").write_text(
            f'schema_version: "1.0"\nid: {identity}\ntitle: {stem}\nintent: Apply org policy.\nenforcement: required\n'
        )
    (tmp_path / ".kittify/config.yaml").write_text(
        f"charter_packs:\n  org:\n    packs:\n      - name: org\n        local_path: '{pack}'\nactivated_directives: ['{activation}']\n"
    )
    gated = build_activation_aware_doctrine_service(tmp_path).directives
    expected = "ACME-001-FOO" if activation in {"foo", "ACME-001-FOO"} else "ACME_001_FOO"
    assert set(gated) == {expected}


def test_populated_activation_resolves_once_per_service_and_new_service_refreshes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from charter.activation import resolver
    from charter.activation.doctrine_service_builder import build_activation_aware_doctrine_service

    (tmp_path / ".kittify").mkdir()
    pack = tmp_path / "org"
    (pack / "directives").mkdir(parents=True)
    policy = pack / "directives/policy.directive.yaml"
    policy.write_text('schema_version: "1.0"\nid: FIRST-POLICY\ntitle: First\nintent: First policy.\nenforcement: required\n')
    (tmp_path / ".kittify/config.yaml").write_text(
        f"charter_packs:\n  org:\n    packs:\n      - name: org\n        local_path: '{pack}'\nactivated_directives: [policy]\n"
    )
    calls = 0
    original = resolver.resolve_artifact_urn

    def counted_resolution(*args: object, **kwargs: object) -> str:
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(resolver, "resolve_artifact_urn", counted_resolution)
    service = build_activation_aware_doctrine_service(tmp_path)
    assert set(service.directives) == {"FIRST-POLICY"}
    first_calls = calls
    assert first_calls > 0
    policy.write_text('schema_version: "1.0"\nid: SECOND-POLICY\ntitle: Second\nintent: Second policy.\nenforcement: required\n')
    for _ in range(35):
        assert set(service.directives) == {"FIRST-POLICY"}
    assert calls == first_calls, "Repeated delivery must not rescan activation files"
    refreshed = build_activation_aware_doctrine_service(tmp_path)
    assert set(refreshed.directives) == {"SECOND-POLICY"}
    assert calls > first_calls, "A new service must resolve the new repository snapshot"


def test_cross_layer_ambiguous_directive_id_is_dropped_not_admitted(tmp_path: Path) -> None:
    """A persisted ``activated_directives`` entry naming a declared identity
    that is genuinely cross-layer-ambiguous -- two org packs both ship a
    ``shared.directive.yaml`` stem that disagrees on which id it names --
    must be excluded from the gated ``.directives`` dict, and must not raise.

    Before the #4194 landing fix, ``resolve_config_id``'s stale reordering
    swallowed this collision and returned *some* stem without raising
    ``UnrepresentableDirectiveIdError``, so ``resolve_artifact_urn``'s
    declared-id fallback resolved the unexamined token to a URN. After the
    fix, ``resolve_config_id`` raises, ``resolve_artifact_urn`` re-raises
    ``UnknownArtifactIdError``, and this property's own
    ``except UnknownArtifactIdError`` fallback (alias-by-literal-id, else
    ``normalize_directive_id``) is exercised -- and since neither the raw
    token nor its normalized form names a real catalog entry here, the
    ambiguous identity contributes nothing to ``activated_ids``.
    """
    company = tmp_path / "company"
    team = tmp_path / "team"
    (company / "directives").mkdir(parents=True)
    (team / "directives").mkdir(parents=True)
    (company / "directives" / "shared.directive.yaml").write_text(
        'schema_version: "1.0"\nid: OTHER-POLICY\ntitle: shared\nintent: Apply policy.\nenforcement: required\n'
    )
    (team / "directives" / "shared.directive.yaml").write_text(
        'schema_version: "1.0"\nid: CHOSEN-POLICY\ntitle: shared\nintent: Apply policy.\nenforcement: required\n'
    )

    unrelated = _directive("UNRELATED-REAL-POLICY")
    inner = MagicMock()
    inner.directives.list_all.return_value = [unrelated]

    ctx = PackContext(
        activated_kinds=frozenset({"directives"}),
        activated_mission_types=frozenset(),
        pack_roots=(tmp_path / "builtin", company, team),
        org_pack_names=(),
        repo_root=tmp_path,
        activated_directives=frozenset({"CHOSEN-POLICY"}),
    )

    gated = DoctrineService(inner, pack_context=ctx).directives

    assert gated == {}
