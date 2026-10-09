"""Shared helpers for validator rejection of forbidden inline reference fields.

Introduced in WP03 of the
``excise-doctrine-curation-and-inline-references-01KP54J6`` mission (EPIC
#461, Phase 1). See
``kitty-specs/excise-doctrine-curation-and-inline-references-01KP54J6/contracts/validator-rejection-error.schema.json``
for the error-shape contract and the required ``migration_hint`` pattern.

The canonical ``migration_hint`` string must match::

    ^Remove .+ from YAML; add edge \\{source: .+, target: .+, relation: requires\\}
     to packs/built-in/[a-z_]+\\.graph\\.yaml$

The trailing path is the DRG fragment for the *source* artifact's kind, which
is where an edge with that source belongs. Mission #2680 sharded the former
single DRG monolith into one ``<kind>.graph.yaml`` fragment per
kind, and mission ``relocate-builtin-doctrine-packs-01KYT87F`` then relocated
those shipped fragments from ``src/charter/offering/`` to the top-level
``packs/built-in/`` pack root — so a hint naming either the monolith or the
old ``src/charter/offering/`` home sends the operator to a file that is not there.

The hint uses the actual ``DRGEdge`` schema: ``source``/``target``/``relation``
keys (not ``from``/``to``/``kind``), and ``requires`` as the relation value (the
``Relation`` enum does not contain ``uses``). Callers in the charter resolver
use ``{Relation.REQUIRES, Relation.SUGGESTS}`` for legacy parity, so
``requires`` is the canonical relation for "this artifact needs that one"
patterns.

Any code that raises :class:`InlineReferenceRejectedError` should build the
hint via :func:`build_migration_hint` to keep the textual shape consistent.
"""

from __future__ import annotations

from typing import Any

from charter.offering.shared.exceptions import InlineReferenceRejectedError

#: Inline-reference fields rejected at the top level of any artifact YAML.
FORBIDDEN_TOP_LEVEL_FIELDS: tuple[str, ...] = (
    "tactic_refs",
    "paradigm_refs",
    "applies_to",
)

#: Inline-reference fields rejected on procedure steps.
FORBIDDEN_STEP_FIELDS: tuple[str, ...] = (
    "tactic_refs",
    "paradigm_refs",
)


def build_migration_hint(
    *,
    forbidden_field: str,
    source_kind: str,
    source_id: str,
    target_kind: str = "<target-kind>",
    target_id: str = "<target-id>",
) -> str:
    """Return the operator-facing migration hint for a rejected inline field.

    The returned text matches the regex in
    ``contracts/validator-rejection-error.schema.json``.

    The named file is the DRG fragment for ``source_kind`` -- edges are
    sharded by their source's kind, so that is the fragment the operator
    actually has to open. There is no monolith left to open: #2680 replaced
    it with per-kind fragments, and ``relocate-builtin-doctrine-packs-01KYT87F``
    relocated those fragments to the ``packs/built-in/`` pack root.
    """
    return (
        f"Remove {forbidden_field} from YAML; "
        f"add edge {{source: {source_kind}:{source_id}, "
        f"target: {target_kind}:{target_id}, relation: requires}} "
        f"to packs/built-in/{source_kind}.graph.yaml"
    )


def reject_inline_refs(
    data: dict[str, Any],
    *,
    file_path: str,
    artifact_kind: str,
) -> None:
    """Raise :class:`InlineReferenceRejectedError` if ``data`` carries forbidden
    inline references at the top level.

    Args:
        data: Raw YAML dict, pre-Pydantic-validation.
        file_path: Absolute file path used for the error message.
        artifact_kind: One of the seven per-kind artifact strings.

    Raises:
        InlineReferenceRejectedError: If any of :data:`FORBIDDEN_TOP_LEVEL_FIELDS`
            is present at the top level of ``data``.
    """
    artifact_id = str(data.get("id", "?"))
    for field in FORBIDDEN_TOP_LEVEL_FIELDS:
        if field in data:
            raise InlineReferenceRejectedError(
                file_path=file_path,
                forbidden_field=field,
                artifact_kind=artifact_kind,
                migration_hint=build_migration_hint(
                    forbidden_field=field,
                    source_kind=artifact_kind,
                    source_id=artifact_id,
                ),
            )


def reject_inline_refs_in_procedure_steps(
    data: dict[str, Any],
    *,
    file_path: str,
) -> None:
    """Raise :class:`InlineReferenceRejectedError` if any procedure ``step``
    carries :data:`FORBIDDEN_STEP_FIELDS`.

    Procedures require step-level scanning in addition to the top-level
    scan; without it, step-level ``tactic_refs`` would fall through to
    Pydantic's generic ``extra_forbidden`` error (after WP02 removed
    ``ProcedureStep.tactic_refs``), which is valid but lacks the structured
    migration hint the spec requires (FR-008).
    """
    artifact_id = str(data.get("id", "?"))
    steps = data.get("steps") or []
    if not isinstance(steps, list):
        return
    for step in steps:
        if not isinstance(step, dict):
            continue
        for field in FORBIDDEN_STEP_FIELDS:
            if field in step:
                raise InlineReferenceRejectedError(
                    file_path=file_path,
                    forbidden_field=field,
                    artifact_kind="procedure",
                    migration_hint=build_migration_hint(
                        forbidden_field=field,
                        source_kind="procedure",
                        source_id=artifact_id,
                    ),
                )


__all__ = [
    # FORBIDDEN_STEP_FIELDS, FORBIDDEN_TOP_LEVEL_FIELDS, build_migration_hint:
    # demoted — no cross-module src/ from-import callers; used only within
    # this module (WP01 harden-dead-symbol-gate-01KW0RJR).
    "reject_inline_refs",
    "reject_inline_refs_in_procedure_steps",
]
