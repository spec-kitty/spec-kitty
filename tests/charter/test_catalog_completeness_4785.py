"""Red-first regression pins for issue #4785 Finding 4b (WP01).

``catalog.references`` is a fully-derived section with ONE compiler authority
(``compile_charter`` / ``write_compiled_charter``, C-001/C-004). Finding 4b
diagnosed a silent-placeholder defect: ``_render_kind_references``
(``compiler.py``) looked up DRG-transitively-reached ids against
``doctrine_service.<kind>`` -- an ACTIVATION-FILTERED dict scoped to
``config.activated_*`` only -- so an id reached solely via a ``requires``/
``suggests`` edge (not directly config-activated) missed even when a bundled
definition genuinely exists in the doctrine corpus, and fell back to the
literal ``"Definition unavailable in bundled doctrine."`` placeholder row
instead of resolving or surfacing as a diagnostic.

Empirical mechanism (pinned by this file, confirmed via T001 before any fix
was written -- see the WP01 prompt's "confirm empirically" instruction): NOT
a URN/config-stem id-format mismatch (transitively-reached directive ids
already match the typed repository's own canonical keys byte-for-byte); the
mismatch is which repository backs the lookup. ``doctrine_service.directives``
et al. (the nine gated properties on ``charter.activation.resolver.DoctrineService``)
return only the DIRECTLY config-activated subset; the DRG transitive closure
(``graph.directives`` et al.) legitimately reaches ids beyond that subset.
The fix routes the lookup through the raw, unfiltered repository
(``doctrine_service.raw_repository(kind)``, the sanctioned FR-002 accessor)
instead, and treats a miss against THAT repository as the genuine-unresolved
case (contract C4).

Contract: ``kitty-specs/charter-catalog-coherence-01M2XQQF/contracts/behavior-contracts.md``
Contract C4.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from ruamel.yaml import YAML

from charter.activation.compiler import _render_kind_references, compile_charter, write_compiled_charter
from charter.activation.interview import default_interview
from charter.activation.pack_context import PackContext
from charter.activation.resolver import DoctrineService as ActivationAwareDoctrineService
from charter.offering.service import DoctrineService as RawDoctrineService

pytestmark = [pytest.mark.fast, pytest.mark.regression]

_PLACEHOLDER_SUMMARY = "Definition unavailable in bundled doctrine."

# packs/built-in/procedure.graph.yaml: `procedure:refactoring` `suggests`
# `directive:DISCIPLINED_REFACTORING` and `directive:RECONCILE_CHANGE_SCOPE_TENSIONS`
# -- both real, bundled directive YAML files
# (packs/built-in/directives/disciplined-refactoring.directive.yaml,
# .../reconcile-change-scope-tensions.directive.yaml). Activating ONLY the
# procedure (never the directives) seeds the DRG transitive closure with
# directive ids that a plain `activated_directives` filter would legitimately
# exclude -- exactly Finding 4b's mechanism, isolated to two ids so the
# fixture is deterministic and does not depend on this repo's own live
# charter config.
_SEED_PROCEDURE = "refactoring"
_TRANSITIVELY_REACHED_DIRECTIVES = {"DISCIPLINED_REFACTORING", "RECONCILE_CHANGE_SCOPE_TENSIONS"}


def _pack_context_seeding_procedure_only(repo_root: Path) -> PackContext:
    """A ``PackContext`` with only ``_SEED_PROCEDURE`` directly activated.

    Every other kind (directives included) is explicitly emptied so nothing
    resolves via direct config activation -- the transitively-reached
    directives can ONLY appear via the DRG requires/suggests walk from the
    procedure root, isolating Finding 4b's mechanism from direct activation.
    """
    return PackContext(
        activated_kinds=frozenset(
            {
                "directives",
                "tactics",
                "styleguides",
                "toolguides",
                "paradigms",
                "procedures",
                "agent_profiles",
                "mission_step_contracts",
            }
        ),
        activated_mission_types=frozenset({"software-dev"}),
        pack_roots=(),
        org_pack_names=(),
        repo_root=repo_root,
        activated_directives=frozenset(),
        activated_tactics=frozenset(),
        activated_styleguides=frozenset(),
        activated_toolguides=frozenset(),
        activated_paradigms=frozenset(),
        activated_procedures=frozenset({_SEED_PROCEDURE}),
        activated_agent_profiles=frozenset(),
    )


def _compile_with_transitive_directive_seed(repo_root: Path) -> Any:
    """Compile with a doctrine service and pack_context that agree (T2/F4b
    fixture): the SAME ``PackContext`` seeds both the reference-set (via
    ``compile_charter``'s own ``config_roots`` derivation) and the
    activation-filtered doctrine service, so this reproduces the real
    two-independent-activation-resolutions shape ``compile_charter`` and
    ``_default_doctrine_service`` share in production.
    """
    pack_context = _pack_context_seeding_procedure_only(repo_root)
    doctrine_service = ActivationAwareDoctrineService(RawDoctrineService(project_root=None), pack_context=pack_context)
    interview = default_interview(mission="software-dev", profile="minimal")
    return compile_charter(
        mission="software-dev",
        interview=interview,
        doctrine_service=doctrine_service,
        pack_context=pack_context,
    )


def _load_yaml(path: Path) -> Any:
    yaml = YAML(typ="safe")
    return yaml.load(path.read_text(encoding="utf-8"))


def test_transitively_reached_directive_with_bundled_definition_does_not_placeholder(tmp_path: Path) -> None:
    """Contract C4 / FR-007: a directive reached only via the DRG requires/
    suggests closure (never directly config-activated) must still resolve to
    its real summary when a bundled definition exists -- never the silent
    placeholder.
    """
    compiled = _compile_with_transitive_directive_seed(tmp_path)
    directive_refs = {ref.id.split(":", 1)[1]: ref for ref in compiled.references if ref.kind == "directive"}

    for directive_id in _TRANSITIVELY_REACHED_DIRECTIVES:
        assert directive_id in directive_refs, (
            f"{directive_id} must be reachable via the transitive closure from '{_SEED_PROCEDURE}'; got directive refs {sorted(directive_refs)}"
        )
        ref = directive_refs[directive_id]
        assert ref.summary != _PLACEHOLDER_SUMMARY, (
            f"{directive_id} has a bundled definition (packs/built-in/directives/) but rendered the placeholder instead of its real summary: {ref.summary!r}"
        )


def test_recompile_is_diff_stable_for_catalog_references(tmp_path: Path) -> None:
    """FR-008 / NFR-002 / NFR-005: two consecutive recompiles of an ALREADY
    ESTABLISHED, unchanged store produce a zero-line diff of
    ``catalog.references`` (canonical order), and ``metadata.generated_at``
    is preserved because the catalog content is byte-unchanged.

    Contract C4's "unchanged charter store" presupposes an established store
    (``catalog.yaml`` already exists), so the diff-stability pair compared
    here is recompile #2 vs recompile #3 -- both through the
    ``update_charter_yaml_section`` merge path. Recompile #1 is a one-time
    bootstrap create (``_bootstrap_charter_yaml``, a different write path
    with no prior ``generated_at`` to preserve by construction) and is
    excluded from the comparison for that reason, not to dodge a real
    instability.
    """
    charter_dir = tmp_path / ".kittify" / "charter"

    # Recompile #1: bootstrap create -- establishes the store.
    write_compiled_charter(charter_dir, _compile_with_transitive_directive_seed(tmp_path), force=True)

    # Recompile #2 vs #3: both against the now-established, unchanged store.
    write_compiled_charter(charter_dir, _compile_with_transitive_directive_seed(tmp_path), force=True)
    second = _load_yaml(charter_dir / "charter.yaml")

    write_compiled_charter(charter_dir, _compile_with_transitive_directive_seed(tmp_path), force=True)
    third = _load_yaml(charter_dir / "charter.yaml")

    assert third["catalog"]["references"] == second["catalog"]["references"], (
        "a recompile of an unchanged, already-established store must not reorder or otherwise change catalog.references"
    )
    assert third["metadata"]["generated_at"] == second["metadata"]["generated_at"], (
        "metadata.generated_at must be preserved when the catalog content is byte-unchanged"
    )


def test_catalog_references_are_in_canonical_deterministic_order(tmp_path: Path) -> None:
    """NFR-005: ``catalog.references`` entries are emitted in a stable
    canonical order (sorted by id), independent of dict/set/graph-walk
    iteration order.
    """
    compiled = _compile_with_transitive_directive_seed(tmp_path)
    charter_dir = tmp_path / ".kittify" / "charter"
    write_compiled_charter(charter_dir, compiled, force=True)

    document = _load_yaml(charter_dir / "charter.yaml")
    ids = [row["id"] for row in document["catalog"]["references"]]

    assert ids == sorted(ids), f"catalog.references is not in canonical (sorted-by-id) order: {ids}"


def test_render_kind_references_routes_genuine_miss_to_diagnostics_not_placeholder() -> None:
    """Contract C4: a directive id with genuinely no bundled definition (a
    miss against the raw, unfiltered repository -- not merely an
    activation-scoped one) must surface through the diagnostics channel
    using the same ``"Unresolved reference: <kind>/<id>"`` format
    ``graph.unresolved`` reporting already uses, never as a silent
    placeholder ``catalog.references`` row.
    """

    class _EmptyRepository:
        def get(self, _item_id: str) -> None:
            return None

    diagnostics: list[str] = []
    references = _render_kind_references(
        ["BOGUS_DIRECTIVE_NOT_IN_BUNDLED_DOCTRINE"],
        kind="directive",
        repository=_EmptyRepository(),
        id_of=lambda model: str(model),
        title_of=lambda model: str(model),
        summary_of=lambda model: str(model),
        diagnostics=diagnostics,
    )

    assert references == [], f"a genuine miss must not produce a placeholder catalog.references row; got {references}"
    assert diagnostics == ["Unresolved reference: directive/BOGUS_DIRECTIVE_NOT_IN_BUNDLED_DOCTRINE"], diagnostics


def test_build_references_from_yaml_dead_builder_removed() -> None:
    """FR-009/campsite: the dead, uncalled ``_build_references_from_yaml``
    second reference-builder is removed so nobody patches the wrong copy.
    """
    import charter.activation.compiler as compiler_module

    assert not hasattr(compiler_module, "_build_references_from_yaml"), "_build_references_from_yaml must be deleted (FR-009) -- it has zero prod callers"
