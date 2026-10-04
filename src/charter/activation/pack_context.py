"""Pre-validated pack set snapshot passed to doctrine resolvers (C-005).

This module defines ``PackContext`` — a frozen dataclass constructed
exclusively by the charter module.  The doctrine resolver receives a
``PackContext`` instance instead of reading ``.kittify/config.yaml``
directly, which enforces the architectural constraint that no
doctrine-layer code ever reads project configuration (C-005).

Invariant: ``PackContext`` is always constructed here via
``PackContext.from_config()``.  Callers in ``src/charter/`` that
previously read ``config.yaml`` for pack or activation state must
delegate to this constructor.

Layer rule
----------
``src/charter/`` MUST NOT import from ``specify_cli`` (C-001, hard
ratchet pinned by ``tests/architectural/test_layer_rules.py``).  This
module uses only stdlib + ``charter.offering.drg.org_pack_config`` (which is
within the allowed layer boundary for charter→doctrine reads).
"""

from __future__ import annotations

import warnings
from collections.abc import Iterable, Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from kernel.errors import KittyInternalConsistencyError
from ruamel.yaml import YAML

from charter.activation.charter_yaml_io import load_charter_yaml
from charter.offering.artifact_kinds import ArtifactKind

__all__ = [
    "ActivationReachabilityPartition",
    "CharterPackConfigError",
    "PackContext",
    "charter_activated_urns",
    "normalize_activation_identifier",
    "partition_activated_unreachable",
    "resolve_charter_yaml_pointer",
]

#: Config-key prefix on every ``activated_<plural>`` activation-store key. The
#: normalization boundary strips it so the store's own key form
#: (``activated_directives``) is accepted alongside the plural (``directives``)
#: and the singular node kind (``directive``).
_ACTIVATION_KEY_PREFIX = "activated_"

#: The single ``config.yaml`` key naming the active charter (consolidate-
#: charter-bundle WP02, data-model.md "Entity: .kittify/config.yaml (after
#: relocation)"). Absent -> legacy/un-migrated project (activation stays in
#: ``config.yaml`` itself). Present -> the resolver follows it to
#: ``charter.yaml`` (INV-2).
_CHARTER_POINTER_KEY = "charter"


class CharterPackConfigError(KittyInternalConsistencyError):
    """Raised when ``.kittify/config.yaml`` has invalid charter pack shape."""

    def __init__(self, body: str) -> None:
        super().__init__("CHARTER_PACK_CONFIG_INVALID", body)


# ---------------------------------------------------------------------------
# Built-in constants
# ---------------------------------------------------------------------------

#: All built-in artifact kinds (plural form used by DoctrineService). Derived
#: from the single :class:`ArtifactKind` authority — exactly
#: ``{kind.plural for kind in ArtifactKind}`` — so it can never drift from the
#: enum (issue #5409; it now includes ``anti_patterns``). Value-equal to
#: ``charter.activation.activations._ALLOWED_KINDS`` by construction (both derive
#: from the same authority); the structural single-authority gate
#: (``tests/architectural/test_charter_kind_vocabulary_single_authority.py``)
#: supersedes the former hand-kept three-way drift guard.
#: Used as the default for ``activated_kinds`` when config.yaml has no
#: ``activated_kinds`` key (backward-compat default — all kinds are active).
_BUILTIN_ARTIFACT_KINDS: frozenset[str] = frozenset(kind.plural for kind in ArtifactKind)

# ---------------------------------------------------------------------------
# Dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PackContext:
    """Pre-validated pack set constructed by the charter module.

    The doctrine resolver receives this; it never reads
    ``.kittify/config.yaml`` directly.  Invariant: constructed by the
    charter module only (C-005).

    All fields are immutable types (``frozenset``, ``tuple``) so the
    instance is safe to hash and use as a dict key.
    """

    activated_kinds: frozenset[str]
    """Artifact kinds explicitly activated in the project charter.

    Plural form (e.g. ``"directives"``, ``"agent_profiles"``).
    Defaults to all built-in kinds (every :class:`ArtifactKind`) when the ``activated_kinds``
    key is absent from ``.kittify/config.yaml``.
    """

    activated_mission_types: frozenset[str]
    """Mission type IDs activated in the project charter.

    Read directly from the provisioned ``mission_type_activations`` key
    (WP04): the provisioned charter is the sole activation authority, with no
    implicit "all built-ins" backfill (absent != all-four, #2657/FR-008).
    Both a genuinely absent key AND an explicit empty list
    (``mission_type_activations: []``) resolve to ``frozenset()``
    (C-A2/FR-039/C-008) — construction is total and never raises on
    absence. Provisioning (``spec-kitty init`` / ``spec-kitty upgrade``) is
    the only writer of a non-empty set. The fail-closed for an empty set
    fires at the mission-create / mission-type-use boundary
    (``create_mission_core``), never at construction.
    """

    pack_roots: tuple[Path, ...]
    """Ordered pack root paths: built-in first, then org packs in
    config declaration order.
    """

    org_pack_names: tuple[str, ...]
    """Org pack names as declared in ``config.yaml``."""

    repo_root: Path
    """Repository root path (for resolving project-layer overrides)."""

    # ------------------------------------------------------------------
    # Per-kind activation fields (three-state: None / frozenset() / {ids})
    # ------------------------------------------------------------------

    activated_directives: frozenset[str] | None = None
    """Directive IDs activated for this project.

    ``None`` → key absent from config (all built-ins available).
    ``frozenset()`` → key present but empty (nothing activated).
    Non-empty frozenset → explicit set of activated IDs.
    """

    activated_tactics: frozenset[str] | None = None
    """Tactic IDs activated for this project (three-state)."""

    activated_styleguides: frozenset[str] | None = None
    """Styleguide IDs activated for this project (three-state)."""

    activated_toolguides: frozenset[str] | None = None
    """Toolguide IDs activated for this project (three-state)."""

    activated_paradigms: frozenset[str] | None = None
    """Paradigm IDs activated for this project (three-state)."""

    activated_procedures: frozenset[str] | None = None
    """Procedure IDs activated for this project (three-state)."""

    activated_agent_profiles: frozenset[str] | None = None
    """Agent profile IDs activated for this project (three-state)."""

    activated_mission_step_contracts: frozenset[str] | None = None
    """Mission step contract IDs activated for this project (three-state)."""

    activated_glossary_packs: frozenset[str] | None = None
    """Glossary pack IDs activated for this project (three-state)."""

    activated_anti_patterns: frozenset[str] | None = None
    """Anti-pattern node IDs activated for this project (three-state)."""

    activated_skills: frozenset[str] | None = None
    """Pack-skill IDs activated for this project (three-state)."""

    # ------------------------------------------------------------------
    # Derived accessors
    # ------------------------------------------------------------------

    @property
    def org_roots(self) -> tuple[Path, ...]:
        """Org/project pack roots -- every :attr:`pack_roots` entry after the
        built-in root at index 0.

        Named accessor so new call sites (the activation gate, WP01 --
        mission ``drg-relation-parity-activation-gate-01KY48PD``) don't
        re-open-code the ``pack_roots[1:]`` slice already duplicated at
        ``charter/compiler.py:144`` and ``charter/consistency_check.py:940``.
        Those two existing sites are left as-is (out of scope for WP01).
        """
        return self.pack_roots[1:]

    # ------------------------------------------------------------------
    # Constructor
    # ------------------------------------------------------------------

    @classmethod
    def from_config(cls, repo_root: Path) -> PackContext:
        """Construct a ``PackContext`` from ``.kittify/config.yaml``.

        Reads the project charter activation state and pack roots. When
        config.yaml is absent, ``activated_kinds`` defaults to all
        built-in kinds and ``org_pack_names``/``pack_roots`` default to
        no org packs. ``mission_type_activations`` defaults to
        ``frozenset()`` on an absent key (WP04): construction is total and
        never raises on an unprovisioned project, since ``PackContext`` is
        built on dozens of read / compose hot paths that must not crash.
        The fail-closed for an empty activation set lives at the
        mission-create / mission-type-use boundary
        (``specify_cli.core.mission_creation.create_mission_core``), not
        here.

        Parameters
        ----------
        repo_root:
            Repository root containing ``.kittify/config.yaml``.

        Returns
        -------
        PackContext
            Frozen, immutable snapshot ready for the doctrine resolver.

        Raises
        ------
        CharterPackConfigError
            When an activation key has an invalid shape (e.g. a non-list
            value), or a ``charter:`` pointer is dangling / unreadable.
            An absent ``mission_type_activations`` key is NOT an error
            (it resolves to ``frozenset()``).
        """
        data = _load_config(repo_root)

        # --- activation source (two-file read, INV-2) -------------------
        # Absent `charter:` pointer -> legacy/un-migrated project: activation
        # keys are read directly from the already-loaded config.yaml mapping
        # (unchanged pre-relocation behavior). Present pointer -> the
        # resolved charter.yaml supplies the flat activation keys instead;
        # `org_pack_names`/`pack_roots` below STILL read from `data`
        # (config.yaml), never from the activation source.
        activation = _load_charter_activation_source(repo_root, data)

        # --- activated_kinds -------------------------------------------
        activated_kinds = _read_activated_kinds(activation)

        # --- activated_mission_types -----------------------------------
        activated_mission_types = _read_activated_mission_types(activation)

        # --- org packs -------------------------------------------------
        org_pack_names, org_pack_roots = _read_org_packs(repo_root, data)

        # --- pack_roots ------------------------------------------------
        # ``pack_context.py`` lives one level deeper than before (moved into
        # ``charter/activation/`` by mission charter-activation-split-01M16ZSE,
        # MAP-A MOVE) -- ``charter/offering/`` is now a *sibling of the parent*
        # package, not a sibling of this module, hence the extra ``.parent``.
        builtin_root = Path(__file__).parent.parent / "offering"
        pack_roots: tuple[Path, ...] = (builtin_root, *org_pack_roots)

        return cls(
            activated_kinds=activated_kinds,
            activated_mission_types=activated_mission_types,
            pack_roots=pack_roots,
            org_pack_names=org_pack_names,
            repo_root=repo_root,
            activated_directives=_read_activated_directives(activation),
            activated_tactics=_read_activated_tactics(activation),
            activated_styleguides=_read_activated_styleguides(activation),
            activated_toolguides=_read_activated_toolguides(activation),
            activated_paradigms=_read_activated_paradigms(activation),
            activated_procedures=_read_activated_procedures(activation),
            activated_agent_profiles=_read_activated_agent_profiles(activation),
            activated_mission_step_contracts=_read_activated_mission_step_contracts(activation),
            activated_glossary_packs=_read_activated_glossary_packs(activation),
            activated_anti_patterns=_read_activated_anti_patterns(activation),
            activated_skills=_read_activated_skills(activation),
        )


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _yaml_loader() -> YAML:
    """Return a YAML parser instance (round-trip mode, preserve quotes)."""
    yaml = YAML()
    yaml.preserve_quotes = True
    return yaml


def _config_error(message: str) -> CharterPackConfigError:
    return CharterPackConfigError(
        f"{message}\nRemediation: fix .kittify/config.yaml (or the charter.yaml "
        f"it points to) or run `spec-kitty upgrade` to restore the default "
        f"charter pack shape."
    )


def resolve_charter_yaml_pointer(repo_root: Path, config_data: dict[str, Any]) -> Path | None:
    """Resolve the ``charter:`` pointer key from parsed ``config.yaml`` data.

    Returns ``None`` when the key is absent — the legacy/un-migrated state,
    where callers fall back to reading/writing activation directly in
    ``config.yaml`` (INV-2). Also returns ``None`` when the key is present but
    its value is NOT a string (e.g. a ``charter:`` mapping namespace holding
    the pre-#2773 inline ``synthesis_inputs`` block): a mapping/list/scalar
    value is the legacy inline shape, not a charter.yaml pointer, so it MUST
    NOT be stringified into a bogus filesystem path. This mirrors
    ``charter.activation.evidence.orchestrator.load_url_list_from_config``, which likewise
    reads ``url_list`` out of a mapping-shaped ``charter:`` key and treats the
    path-string shape as "no inline mapping". Only a *string* value is a
    pointer. Returns the resolved (repo-root-relative or absolute) path when a
    string pointer is present, WITHOUT checking existence: callers apply their
    own fail-loud policy so the "missing file" error can name the calling
    operation (read vs write).

    Shared by :meth:`PackContext.from_config` (read) and
    ``charter.activation.pack_manager`` (write) so pointer resolution has exactly one
    implementation (INV-5).
    """
    pointer = config_data.get(_CHARTER_POINTER_KEY)
    if not isinstance(pointer, str):
        # Absent (None) OR a non-string legacy inline mapping/namespace ->
        # no pointer to resolve; callers use the legacy config.yaml read.
        return None
    pointer_path = Path(pointer)
    return pointer_path if pointer_path.is_absolute() else repo_root / pointer_path


# ---------------------------------------------------------------------------
# Identifier normalization boundary (I-V4 / C-009, WP06)
# ---------------------------------------------------------------------------
#
# The activation store keeps a directive as its file slug (``025-boy-scout-
# rule``); the selector / DRG-node form is ``directive:DIRECTIVE_025``. Every
# other kind stores the node id verbatim, so only the kind prefix is added.
# These two forms are reconciled at exactly ONE place — the two functions below
# — rather than by scattered ``.replace()`` calls (WP06 risk row). The id
# translation is delegated to the canonical
# ``charter.offering.drg.migration.id_normalizer.artifact_to_urn`` — the same algorithm
# the DRG extractor uses to mint node URNs — so the store form and the node form
# can never drift.
#
# C-009 — THIS NORMALIZATION IS NOT REACHABILITY PROGRESS. Reconciling the form
# moves the measured "activated-but-unreachable" count by ~25 artefacts (the
# activated directives, whose stored slug is not a node URN while their
# normalized form is) WITHOUT making anything reachable. That swing is reported
# separately (:attr:`ActivationReachabilityPartition.normalization_delta`) and
# is explicitly excluded from any SC-005 claim. See
# ``kitty-specs/doctrine-delivery-reachability-01KYMXD6/spec.md`` (C-009) and
# ``data-model.md`` (I-V4).


def _resolve_activation_kind(kind: str) -> str:
    """Return the canonical singular artifact-kind value for an activation kind.

    Accepts the singular node kind (``directive``), the plural directory form
    (``directives``) and the ``activated_<plural>`` config-key form
    (``activated_directives``) — the three shapes the activation store speaks.

    Fail-closed (C-006 / NFR-005): an unrecognised kind raises ``ValueError``
    naming the accepted kinds rather than silently inferring an identity.
    """
    # Lazy: charter→doctrine read, mirrors the NFR-001 import-time-I/O convention.
    from charter.offering.artifact_kinds import (  # noqa: PLC0415
        ArtifactKind,
    )

    token = kind.strip().lower()
    if token.startswith(_ACTIVATION_KEY_PREFIX):
        token = token[len(_ACTIVATION_KEY_PREFIX) :]
    try:
        return ArtifactKind.from_plural(token).value
    except KeyError:
        # from_operator_token raises ValueError (naming the valid tokens) when
        # the singular form is also unknown — exactly the fail-closed shape.
        return ArtifactKind.from_operator_token(token).value


def normalize_activation_identifier(kind: str, identifier: str) -> str:
    """Reconcile one activation-store identifier to its selector / DRG-node URN.

    This is the **single boundary** (I-V4) between the store's identifier form
    and the selector form. ``normalize_activation_identifier("directive",
    "025-boy-scout-rule")`` returns ``"directive:DIRECTIVE_025"``; a non-directive
    kind only gains its kind prefix (``"tactic:usage-examples-sync"``).

    Per C-009 this reconciliation is **not** a reachability improvement — see the
    module comment above.

    Parameters
    ----------
    kind:
        Singular node kind, plural directory name, or ``activated_<plural>``
        config-key form. Unknown kinds raise ``ValueError`` naming the accepted
        forms.
    identifier:
        The stored identifier (file slug or node id).
    """
    # Lazy: charter→doctrine read, mirrors the NFR-001 import-time-I/O convention.
    from charter.offering.drg.migration.id_normalizer import (  # noqa: PLC0415
        artifact_to_urn,
    )

    return artifact_to_urn(_resolve_activation_kind(kind), identifier)


@dataclass(frozen=True)
class ActivationReachabilityPartition:
    """C-009 partition of activated identifiers that are not reachable-as-stored.

    Measured on the activation store form against the DRG node / reachable sets,
    so the partition names *why* each activated identifier misses reachability:

    * :attr:`not_a_node` — the stored form is not a graph node URN at all. This
      is the set the C-009 identifier normalization reconciles (chiefly the
      activated directives, whose stored slug is not a node URN). Reducing this
      count by normalizing the form is **not** reachability progress and is
      excluded from SC-005.
    * :attr:`node_but_unreachable` — the stored form already IS a graph node but
      no traversal reaches it. This is FR-015's real wiring target — the only
      partition SC-005 progress may touch.

    The two sets are disjoint and together cover every activated identifier that
    is not reachable in its stored form.

    :attr:`normalization_recovered` is the declared C-009 swing: the subset of
    :attr:`not_a_node` whose **normalized** selector URN IS a real node. Its
    cardinality (:attr:`normalization_delta`) is the count the boundary moves and
    that a later pin (WP08) subtracts before claiming any artefact "made
    reachable".
    """

    not_a_node: frozenset[str]
    node_but_unreachable: frozenset[str]
    normalization_recovered: frozenset[str]

    @property
    def normalization_delta(self) -> int:
        """Count of activated identifiers the normalization reconciles to a real
        node — the C-009 swing, reported separately and never banked as progress."""
        return len(self.normalization_recovered)


def partition_activated_unreachable(
    activated: Mapping[str, Iterable[str]],
    node_urns: AbstractSet[str],
    reachable_urns: AbstractSet[str],
) -> ActivationReachabilityPartition:
    """Partition activated identifiers by why they miss reachability (T033).

    Parameters
    ----------
    activated:
        Mapping of activation kind (any form :func:`normalize_activation_identifier`
        accepts) to the stored identifiers activated under it.
    node_urns:
        Every DRG node URN (selector form).
    reachable_urns:
        The subset of ``node_urns`` a traversal reaches. Must be expressed in the
        same selector form as ``node_urns``.

    Returns
    -------
    ActivationReachabilityPartition
        The ``{not-a-node, node-but-unreachable}`` split plus the declared,
        excluded C-009 normalization swing.
    """
    not_a_node: set[str] = set()
    node_but_unreachable: set[str] = set()
    normalization_recovered: set[str] = set()

    for kind, identifiers in activated.items():
        singular = _resolve_activation_kind(kind)
        for identifier in identifiers:
            stored_urn = f"{singular}:{identifier}"
            if stored_urn in reachable_urns:
                # Reachable in its stored form (non-directive kinds): delivered,
                # not part of the unreachable partition.
                continue
            if stored_urn in node_urns:
                node_but_unreachable.add(stored_urn)
                continue
            # Stored form is not a node URN. This is the C-009 set: if the
            # normalized selector form IS a node, the normalization is exactly
            # what recovers it — a form reconciliation, never new reachability.
            not_a_node.add(stored_urn)
            selector_urn = normalize_activation_identifier(kind, identifier)
            if selector_urn in node_urns:
                normalization_recovered.add(selector_urn)

    return ActivationReachabilityPartition(
        not_a_node=frozenset(not_a_node),
        node_but_unreachable=frozenset(node_but_unreachable),
        normalization_recovered=frozenset(normalization_recovered),
    )


#: Per-artifact activation keys projected to ``<kind>:<id>`` selector URNs by
#: :func:`charter_activated_urns`. Restricted to the DRG-node-bearing kinds the
#: reachability projection gate compares against (directives, tactics,
#: toolguides, procedures, paradigms, styleguides); agent profiles / mission
#: step contracts / glossary packs are activation-eligible but are not part of
#: that orphan-partition comparison.
_ACTIVATION_URN_KINDS: dict[str, str] = {
    "activated_directives": "directive",
    "activated_tactics": "tactic",
    "activated_toolguides": "toolguide",
    "activated_procedures": "procedure",
    "activated_paradigms": "paradigm",
    "activated_styleguides": "styleguide",
}


def charter_activated_urns(repo_root: Path) -> set[str]:
    """Return every ``<kind>:<id>`` URN the project's *resolved* activation store activates.

    This is the single activation authority (FR-017). It reads the activation
    store resolved through the ``charter:`` pointer — ``charter.yaml`` when the
    pointer is present, else the legacy ``config.yaml``-embedded keys — via
    :func:`_load_charter_activation_source`. It never consults the retired
    ``config.yaml`` ``activated_*`` mirror once a charter pointer resolves, so a
    divergent config mirror can never win (SC-007).

    Directive slugs are reconciled to their DRG node code
    (``025-boy-scout-rule`` -> ``directive:DIRECTIVE_025``) through the single
    C-009 normalization boundary (:func:`normalize_activation_identifier`), so
    the returned URNs match DRG node URNs. Other kinds only gain their kind
    prefix.

    Parameters
    ----------
    repo_root:
        Repository root containing ``.kittify/config.yaml`` (and, when
        migrated, the pointed-at ``charter.yaml``).
    """
    data = _load_config(repo_root)
    activation = _load_charter_activation_source(repo_root, data)
    urns: set[str] = set()
    for key, kind in _ACTIVATION_URN_KINDS.items():
        entries = activation.get(key)
        if not entries:
            continue
        for entry in entries:
            urns.add(normalize_activation_identifier(kind, str(entry)))
    return urns


def _load_charter_activation_source(repo_root: Path, data: dict[str, Any]) -> dict[str, Any]:
    """Return the mapping ``_read_activated_*`` reads activation keys from.

    Two-state resolution keyed on the ``charter:`` pointer (INV-2/INV-5):

    * Pointer absent -> legacy/un-migrated project. Activation is read
      directly from ``config.yaml`` (the pre-relocation behavior, preserved
      byte-for-byte for projects that have not yet run the charter-bundle
      migration).
    * Pointer present -> the project has been migrated. The pointer MUST
      resolve to a readable ``charter.yaml``; a dangling/unreadable pointer
      is a fail-loud error (INV-5, re-homed #2530) — never a silent
      fallback to the legacy config-embedded keys.
    """
    charter_path = resolve_charter_yaml_pointer(repo_root, data)
    if charter_path is None:
        return data
    if not charter_path.exists():
        raise _config_error(f".kittify/config.yaml 'charter:' pointer names {charter_path}, which does not exist.")
    try:
        loaded = load_charter_yaml(charter_path)
    except Exception as exc:
        raise _config_error(f"Invalid YAML in {charter_path}: {exc}") from exc
    if not isinstance(loaded, dict):
        raise _config_error(f"{charter_path} root must be a mapping.")
    return dict(loaded)


def _load_config(repo_root: Path) -> dict[str, Any]:
    """Read and parse ``.kittify/config.yaml``.

    Returns an empty dict when the file is absent. Invalid YAML or a non-mapping
    root is a hard error: activation filters must not fail open.
    """
    config_path = repo_root / ".kittify" / "config.yaml"
    if not config_path.exists():
        return {}
    try:
        yaml = _yaml_loader()
        raw: Any = yaml.load(config_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise _config_error(f"Invalid YAML in .kittify/config.yaml: {exc}") from exc
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise _config_error(".kittify/config.yaml root must be a mapping.")
    return dict(raw)


def _read_list_key(data: dict[str, Any], key: str) -> frozenset[str] | None:
    raw = data.get(key)
    if raw is None:
        return None
    if not isinstance(raw, list):
        raise _config_error(f"Activation key '{key}' must be a list, got {type(raw).__name__}.")
    return frozenset(str(item) for item in raw)


def _read_activated_kinds(data: dict[str, Any]) -> frozenset[str]:
    """Extract ``activated_kinds`` from parsed config data.

    Falls back to all built-in kinds when the key is absent.
    An explicit empty list ``[]`` returns ``frozenset()`` (FR-039 fix).
    """
    activated = _read_list_key(data, "activated_kinds")
    return _BUILTIN_ARTIFACT_KINDS if activated is None else activated


def _read_activated_mission_types(data: dict[str, Any]) -> frozenset[str]:
    """Extract ``mission_type_activations`` from parsed config data.

    Construction is **total** — this reader never raises on absence (WP04
    re-architecture). A genuinely absent ``mission_type_activations`` key
    resolves to ``frozenset()``, the same result as an explicit empty list
    (``mission_type_activations: []``, C-A2/FR-039/C-008). Absent is
    deliberately NOT backfilled to the all-four built-in roster
    (#2657/FR-008): the provisioned charter (``spec-kitty init`` /
    ``spec-kitty upgrade``, see ``specify_cli.provisioning.default_charter``)
    is the sole writer of a non-empty set, so absent != all-four.

    Why totality: ``PackContext`` is constructed on dozens of hot read /
    compose paths (runtime-bridge composition through
    ``doctrine_service_builder``, invocation ``ProfileRegistry``, charter
    listing, tool-surface projection, ``doctor``) that must not crash on an
    unprovisioned project. Reading an empty activation set is a valid, total
    outcome. The fail-closed "a mission requires at least one activated
    mission type" lives at the mission-create / mission-type-use boundary
    (``specify_cli.core.mission_creation.create_mission_core``), NOT here:
    only *creating / requiring* a mission against an empty set is the
    actionable, unusable case — never merely *reading* it.
    """
    activated = _read_list_key(data, "mission_type_activations")
    if activated is None:
        return frozenset()
    return activated


def _read_activated_directives(data: dict[str, Any]) -> frozenset[str] | None:
    """Extract ``activated_directives`` from parsed config data (three-state).

    ``None`` → key absent (all built-ins available).
    ``frozenset()`` → key present with empty list (nothing activated).
    Non-empty frozenset → explicit set of activated IDs.
    """
    return _read_list_key(data, "activated_directives")


def _read_activated_tactics(data: dict[str, Any]) -> frozenset[str] | None:
    """Extract ``activated_tactics`` from parsed config data (three-state)."""
    return _read_list_key(data, "activated_tactics")


def _read_activated_styleguides(data: dict[str, Any]) -> frozenset[str] | None:
    """Extract ``activated_styleguides`` from parsed config data (three-state)."""
    return _read_list_key(data, "activated_styleguides")


def _read_activated_toolguides(data: dict[str, Any]) -> frozenset[str] | None:
    """Extract ``activated_toolguides`` from parsed config data (three-state)."""
    return _read_list_key(data, "activated_toolguides")


def _read_activated_paradigms(data: dict[str, Any]) -> frozenset[str] | None:
    """Extract ``activated_paradigms`` from parsed config data (three-state)."""
    return _read_list_key(data, "activated_paradigms")


def _read_activated_procedures(data: dict[str, Any]) -> frozenset[str] | None:
    """Extract ``activated_procedures`` from parsed config data (three-state)."""
    return _read_list_key(data, "activated_procedures")


def _read_activated_agent_profiles(data: dict[str, Any]) -> frozenset[str] | None:
    """Extract ``activated_agent_profiles`` from parsed config data (three-state)."""
    return _read_list_key(data, "activated_agent_profiles")


def _read_activated_mission_step_contracts(
    data: dict[str, Any],
) -> frozenset[str] | None:
    """Extract ``activated_mission_step_contracts`` from parsed config data (three-state)."""
    return _read_list_key(data, "activated_mission_step_contracts")


def _read_activated_glossary_packs(data: dict[str, Any]) -> frozenset[str] | None:
    """Extract ``activated_glossary_packs`` from parsed config data (three-state)."""
    return _read_list_key(data, "activated_glossary_packs")


def _read_activated_anti_patterns(data: dict[str, Any]) -> frozenset[str] | None:
    """Extract ``activated_anti_patterns`` from parsed config data (three-state)."""
    return _read_list_key(data, "activated_anti_patterns")


def _read_activated_skills(data: dict[str, Any]) -> frozenset[str] | None:
    """Extract ``activated_skills`` from parsed config data (three-state)."""
    return _read_list_key(data, "activated_skills")


def _read_org_packs(repo_root: Path, _data: dict[str, Any]) -> tuple[tuple[str, ...], tuple[Path, ...]]:
    """Resolve org pack names and root paths from config data.

    Delegates to ``charter.offering.drg.org_pack_config.load_pack_registry``
    so that legacy ``organisation_packs`` form and deprecation warnings
    are handled consistently with the rest of the codebase.

    Returns
    -------
    (names, roots)
        ``names`` — org pack names in declaration order.
        ``roots`` — resolved absolute pack root paths in the same order.
    """
    names: list[str] = []
    roots: list[Path] = []
    try:
        from charter.offering.drg.org_pack_config import (  # noqa: PLC0415
            OrgPackEnvVarUnsetError,
            OrgPackSubdirEscapeError,
            load_pack_registry,
        )

        registry = load_pack_registry(repo_root)
        # Resolve effective roots inside the try so a resolution-time subdir
        # escape or unset-env-var failure (raised by ``effective_root``) is
        # re-raised below rather than swallowed by the broad ``except`` into
        # a silent empty registry.
        for pack in registry.packs:
            names.append(pack.name)
            roots.append(pack.effective_root(repo_root))
    except (OrgPackSubdirEscapeError, OrgPackEnvVarUnsetError):
        raise
    except Exception as exc:  # pragma: no cover – defensive
        warnings.warn(
            f"Failed to load org pack registry; org packs disabled: {exc}",
            stacklevel=4,
        )
        return (), ()

    return tuple(names), tuple(roots)
