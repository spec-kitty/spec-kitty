"""Projection seam: derive ``action_sequence`` / ``template_set`` from steps.

Single canonical, doctrine-layer seam (S-B, WP02; retired the persisted
``MissionType.template_set`` field entirely in the S-C atomic cutover,
mission-step-creatability-01KXQA6R WP01). **Every** consumer -- the
charter/runtime seam (:func:`charter.activation.mission_type_profiles._resolve_template_set_slot`)
and the (future, FR-009) DRG extractor pass -- imports *this* module and
its :func:`iter_template_refs` helper, never a second copy, never
independently re-derived downstream (C-003, "one ordering authority: every
consumer switches"). Layering: this module lives in ``doctrine`` and is
imported *by* the charter layer, never the reverse -- no layering
inversion.

The functions here are pure and deterministic: given the same
``MissionStep`` collection, each always returns byte-identical output. The
DRG freshness gate (NFR-002) and the software-dev parity scaffold
(NFR-001a) both depend on that determinism, so none may read the
filesystem, mutate its input, or depend on iteration/dict ordering beyond
what is explicitly sorted below.

Scope fence (C-008, "whack-a-field"): this module projects **only** the
``dict[artifact_key, template_file]`` mapping derived from
``MissionStep.template`` (exposed as ``MissionType.template_set`` was,
pre-cutover, and as ``ResolvedMissionType.template_set`` still is,
per C-006). The unrelated charter/project ``governance.charter.template_set``
**scalar** (``charter/resolver.py``, ``compiler.py``, ``compact.py``,
``generator.py``, ``catalog.py``, ``prompt_builder.py``,
``scope_router.py``, ``governance-profile.yaml``) is a different domain
object entirely. This module must never import from, or reference, that
scalar surface.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING

from .models import MissionStep, MissionStepTemplateRef, validate_action_sequence

if TYPE_CHECKING:
    from .expected_artifact_manifest import ExpectedArtifactManifest

__all__ = [
    "iter_template_refs",
    "project_action_sequence",
    "project_artifact_name_set",
    "project_template_set",
]
# ``iter_template_refs`` is the single shared traversal of ``MissionStep.template``:
# both ``project_template_set`` (in-module) and the DRG extractor's
# ``extract_template_instantiation_edges`` (cross-module, drg/migration/extractor.py)
# consume it, so it is a public surface with a live non-test caller under ``src/``
# (satisfying tests.architectural.test_no_dead_symbols).

#: Sentinel sort weight for a sequence member with no ``sequence_index``.
#: Sorts after every real (non-negative) index so the total order stays
#: deterministic even for data that should not occur in practice (an
#: ``in_action_sequence: true`` step is expected to always carry an index --
#: WP03 author discipline).
_UNINDEXED = 2**31


def _sequence_sort_key(step: MissionStep) -> tuple[int, str]:
    """Sort key: ``sequence_index`` first, ``id`` as a deterministic tiebreak."""
    index = step.sequence_index if step.sequence_index is not None else _UNINDEXED
    return (index, step.id)


def project_action_sequence(steps: Iterable[MissionStep]) -> list[str]:
    """Project the ordered action-sequence step ids from *steps*.

    Returns the ``id`` of every step with ``in_action_sequence is True``,
    sorted ascending by ``sequence_index`` (stable, deterministic -- the DRG
    freshness gate needs byte-identical regeneration across runs). Steps
    with ``in_action_sequence is False`` (e.g. ``retrospect``,
    software-dev's 7 non-sequence steps) are excluded entirely -- they mint
    no entry and, downstream, no DRG edge (WP04).

    Returns an empty list when no step is a sequence member. That is a
    valid **transitional** state: before a mission type's steps are
    annotated with ``sequence_index``/``in_action_sequence`` (pending
    WP03/WP05), every step in that type projects to nothing. Callers that
    require a non-empty sequence (e.g. the ``MissionTypeRepository`` cached
    accessor, see ``mission_type_repository._inject_projected_fields``) are
    responsible for falling back to the still-authored YAML value during
    this transition -- this function itself never fabricates or fails on
    an honestly-empty projection.

    When the projection *is* non-empty, the WP01->WP02 contract invariant
    (non-empty + unique ids) is re-asserted here via
    :func:`~charter.offering.missions.models.validate_action_sequence` -- the same
    check :class:`~charter.offering.missions.models.MissionType` applies to the raw
    YAML-authored field -- so direct consumers of this pure function (the
    DRG extractor, WP04; the runtime seam, WP06) get the same guarantee
    without needing to construct a ``MissionType`` first.
    """
    members = [step for step in steps if step.in_action_sequence]
    members.sort(key=_sequence_sort_key)
    sequence = [step.id for step in members]
    if sequence:
        validate_action_sequence(sequence)
    return sequence


def project_template_set(steps: Iterable[MissionStep]) -> dict[str, str] | None:
    """Project the ``template_set`` mapping from *steps*.

    Keyed on ``MissionStepTemplateRef.artifact_key`` -- **not** the step
    id. A step's id need not match its template's artifact key (e.g.
    software-dev's ``specify`` step projects ``template_set["spec"]``,
    because ``artifact_key="spec"``); the resolver reads
    ``template_set["spec"]``, so keying on step id would silently break it.

    Built from :func:`iter_template_refs` (single traversal, shared with
    the FR-009 DRG extractor pass), so key order is deterministic
    ``sequence_index`` order (FR-011) -- software-dev's order stays
    ``{spec, plan}`` (specify=idx0, plan=idx1). Steps without a
    ``template`` ref are dropped. Returns ``None`` when no step in *steps*
    carries a template -- matching the 3 built-in mission types
    (``documentation``, ``research``, ``plan``) whose ``template_set`` is
    explicitly ``null`` today.
    """
    template_set: dict[str, str] = {}
    for _step, template_ref in iter_template_refs(steps):
        template_set[template_ref.artifact_key] = template_ref.template_file
    return template_set or None


def project_artifact_name_set(manifest: ExpectedArtifactManifest) -> dict[str, str] | None:
    """Project the ``artifact_key -> path_pattern`` mapping from a manifest."""
    name_set: dict[str, str] = {}
    for spec in manifest.required_always:
        name_set[spec.artifact_key] = spec.path_pattern
    for specs in manifest.required_by_step.values():
        for spec in specs:
            name_set[spec.artifact_key] = spec.path_pattern
    for spec in manifest.optional_always:
        name_set[spec.artifact_key] = spec.path_pattern
    return name_set or None


def iter_template_refs(
    steps: Iterable[MissionStep],
) -> list[tuple[MissionStep, MissionStepTemplateRef]]:
    """Return every ``(step, template_ref)`` pair in *steps*, ``sequence_index``-ordered.

    The **sole traversal** of ``MissionStep.template`` in this module --
    both :func:`project_template_set` and the FR-009 DRG extractor pass
    (``instantiates`` edges, WP06) build from this single helper rather
    than each independently walking *steps* and re-checking ``.template``
    (C-003, "one ordering authority"). Steps carrying no ``template`` ref
    are dropped; ordering mirrors :func:`project_action_sequence`'s
    ``sequence_index`` sort (FR-011) so both the dict key order here and
    the downstream edge-emission order are deterministic.
    """
    ordered = sorted(steps, key=_sequence_sort_key)
    refs: list[tuple[MissionStep, MissionStepTemplateRef]] = []
    for step in ordered:
        template_ref = step.template
        if template_ref is not None:
            refs.append((step, template_ref))
    return refs
