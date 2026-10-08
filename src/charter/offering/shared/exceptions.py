"""Shared exceptions for the charter offering."""


class InlineReferenceRejectedError(ValueError):
    """Raised when a doctrine artifact YAML carries a forbidden inline reference field.

    The legacy governance model allowed artifacts to carry inline reference
    arrays such as ``tactic_refs``, ``paradigm_refs``, or ``applies_to``.
    Post-WP02 of the ``excise-doctrine-curation-and-inline-references-01KP54J6``
    mission (EPIC #461, Phase 1), the only legal reference channel is the
    DRG edge set in ``packs/built-in/*.graph.yaml``. Per-kind validators reject
    any remaining inline reference with this error.

    See ``contracts/validator-rejection-error.schema.json`` for the
    structured shape.

    Attributes:
        file_path: Absolute path of the offending YAML file (string form).
        forbidden_field: One of ``"tactic_refs"``, ``"paradigm_refs"``,
            ``"applies_to"``.
        artifact_kind: One of ``"directive"``, ``"tactic"``, ``"procedure"``,
            ``"paradigm"``, ``"styleguide"``, ``"toolguide"``, ``"agent_profile"``.
        migration_hint: Operator-facing text matching the schema pattern
            ``"Remove <field> from YAML; add edge {source: <kind>:<id>,
            target: <target-kind>:<target-id>, relation: requires} to
            packs/built-in/<kind>.graph.yaml"``. The named file is the DRG
            fragment for the source artifact's kind -- edges shard by source
            kind, and #2680 replaced the former single monolith with those
            per-kind fragments. Uses the actual ``DRGEdge`` schema
            (``source``/``target``/``relation``) and the ``requires`` relation
            (the ``Relation`` enum does not include ``uses``).
    """

    def __init__(
        self,
        *,
        file_path: str,
        forbidden_field: str,
        artifact_kind: str,
        migration_hint: str,
    ) -> None:
        self.file_path = file_path
        self.forbidden_field = forbidden_field
        self.artifact_kind = artifact_kind
        self.migration_hint = migration_hint
        super().__init__(
            f"Inline reference rejected in {file_path}:\n"
            f"  artifact_kind: {artifact_kind}\n"
            f"  forbidden_field: {forbidden_field}\n"
            f"  migration: {migration_hint}"
        )


class ArtifactLoadError(Exception):
    """Raised when a doctrine artifact file cannot be loaded or parsed.

    Used when YAML is malformed or the file content is not a valid dict.
    Callers that load artifact directories should catch this and continue,
    issuing a warning rather than aborting the full load.
    """


class ArtifactResolutionCycleError(Exception):
    """Raised when a cycle is detected in doctrine artifact references.

    A cycle in the reference graph (e.g. Tactic A → Tactic B → Tactic A)
    would cause infinite resolution loops and is always a configuration error.

    Attributes:
        cycle: Ordered list of (artifact_type, artifact_id) tuples forming the cycle.
    """

    def __init__(self, cycle: list[tuple[str, str]]) -> None:
        self.cycle = cycle
        path_str = " → ".join(f"{t}/{i}" for t, i in cycle)
        super().__init__(f"Cycle detected in doctrine artifact references: {path_str}")
