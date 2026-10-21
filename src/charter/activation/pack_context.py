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
from collections.abc import Callable, Iterable, Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from pathlib import Path
from typing import Any


# ActiveCharterConfigError and its standard-remediation helper live in the
# activation ledger seam (WP02); importing them here keeps
# ``from charter.activation.pack_context import ActiveCharterConfigError``
# resolving to the same class object for every existing importer.
from charter.activation.activation_ledger import (
    ActivationLedger,
    ActiveCharterConfigError,
    DenySet,
    _effective_deny,
    allow_key,
    ledger_may_hold_deny,
    load_activation_ledger,
    load_config_yaml,
)
from charter.activation.activation_ledger import config_error as _config_error
from charter.activation.charter_yaml_io import load_charter_yaml
from charter.bundle import CHARTER_YAML
from kernel.activation_ledger_store import legacy_pointer_path
from charter.activation.org_pack_discovery import read_org_required_ids, read_org_required_tokens
from charter.offering.artifact_kinds import ArtifactKind

__all__ = [
    "ActivationReachabilityPartition",
    "ActiveCharterConfigError",
    "PackContext",
    "charter_activated_urns",
    "explicit_activated_skills",
    "load_charter_yaml_mapping",
    "load_denied",
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

#: Repo-root-relative default location of ``charter.yaml`` (no pointer set).


# ---------------------------------------------------------------------------
# Built-in constants
# ---------------------------------------------------------------------------

#: All built-in artifact kinds (plural form used by ActiveCharterService). Derived
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

    denied: tuple[tuple[str, DenySet], ...] = ()
    """The effective deny ``D*`` per plural kind, sorted by plural (hashable, FR-006).

    Holds only kinds whose effective deny is non-empty. The present
    ``activated_<plural>`` lists above are already netted by it; an absent list
    stays ``None``, so readers subtract it through :meth:`admits`,
    :meth:`effective_ids` or :meth:`denied_for`.
    """

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
    # Effective membership (FR-006, ADR 2026-10-19-1 Decision 2)
    # ------------------------------------------------------------------

    def denied_for(self, kind: ArtifactKind) -> DenySet:
        """The effective deny of *kind*; :attr:`DenySet.EMPTY` when nothing is denied."""
        for plural, deny in self.denied:
            if plural == kind.plural:
                return deny
        return DenySet.EMPTY

    def with_allow_lists(self, lists: Mapping[str, frozenset[str]]) -> PackContext:
        """A copy whose ``activated_<plural>`` sets named in *lists* are replaced; every other field is kept.

        The typed form of ``dataclasses.replace(context, **lists)`` (the
        resynthesis preflight checks the sets an activation will write). A key
        that is not a per-kind allow key raises :class:`ValueError`.
        """
        unknown = sorted(set(lists) - {allow_key(kind) for kind in ArtifactKind if kind.activatable})
        if unknown:
            raise ValueError(f"Not a per-kind activation key: {unknown}")

        def pick(kind: ArtifactKind) -> frozenset[str] | None:
            return lists.get(allow_key(kind), self.allow_for(kind))

        return PackContext(
            activated_kinds=self.activated_kinds,
            activated_mission_types=self.activated_mission_types,
            pack_roots=self.pack_roots,
            org_pack_names=self.org_pack_names,
            repo_root=self.repo_root,
            activated_directives=pick(ArtifactKind.DIRECTIVE),
            activated_tactics=pick(ArtifactKind.TACTIC),
            activated_styleguides=pick(ArtifactKind.STYLEGUIDE),
            activated_toolguides=pick(ArtifactKind.TOOLGUIDE),
            activated_paradigms=pick(ArtifactKind.PARADIGM),
            activated_procedures=pick(ArtifactKind.PROCEDURE),
            activated_agent_profiles=pick(ArtifactKind.AGENT_PROFILE),
            activated_mission_step_contracts=pick(ArtifactKind.MISSION_STEP_CONTRACT),
            activated_glossary_packs=pick(ArtifactKind.GLOSSARY_PACK),
            activated_anti_patterns=pick(ArtifactKind.ANTI_PATTERN),
            activated_skills=pick(ArtifactKind.SKILL),
            denied=self.denied,
        )

    def allow_for(self, kind: ArtifactKind) -> frozenset[str] | None:
        """The deny-netted allow state of *kind*: ``None`` when the key is absent."""
        value: frozenset[str] | None = getattr(self, allow_key(kind))
        return value

    def admits(self, kind: ArtifactKind, token: str, *, available: AbstractSet[str]) -> bool:
        """Whether *token* is in the effective set of *kind* (the membership accessor, M2).

        An absent "all" list admits a token of *available*; an absent "required"
        list admits nothing beyond the floor :meth:`from_config` materialises; a
        present list admits its own (netted) tokens. A denied token is never admitted.
        """
        if not self.denied_for(kind).admits(token):
            return False
        allow = self.allow_for(kind)
        if allow is None:
            return kind.effective_when_absent == "all" and token in available
        return token in allow

    def effective_ids(self, kind: ArtifactKind, available: AbstractSet[str]) -> frozenset[str]:
        """``E(k)`` over *available*: the ids :meth:`admits` keeps."""
        return frozenset(token for token in available if self.admits(kind, token, available=available))

    @property
    def deactivated_urns(self) -> frozenset[str]:
        """Every denied DRG URN (the DRG filter and the cascade read these, R5)."""
        return frozenset().union(*(deny.urns for _plural, deny in self.denied))

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
        ActiveCharterConfigError
            When an activation key has an invalid shape (e.g. a non-list
            value), or a ``charter:`` pointer is dangling / unreadable.
            An absent ``mission_type_activations`` key is NOT an error
            (it resolves to ``frozenset()``).
        """
        data = _load_config(repo_root)

        # --- activation source (the ledger seam, FR-017) ----------------
        # `org_pack_names`/`pack_roots` below STILL read from `data`
        # (config.yaml), never from the activation source.
        ledger = load_activation_ledger(repo_root)
        activation = ledger.raw()

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

        # --- effective deny, computed once (FR-006, NFR-003) -------------
        denied = load_denied(repo_root, ledger=ledger, org_roots=org_pack_roots)
        deny = dict(denied)

        return cls(
            activated_kinds=activated_kinds,
            activated_mission_types=activated_mission_types,
            pack_roots=pack_roots,
            org_pack_names=org_pack_names,
            repo_root=repo_root,
            activated_directives=_net(_read_activated_directives(activation), deny.get("directives")),
            activated_tactics=_net(_read_activated_tactics(activation), deny.get("tactics")),
            activated_styleguides=_net(_read_activated_styleguides(activation), deny.get("styleguides")),
            activated_toolguides=_net(_read_activated_toolguides(activation), deny.get("toolguides")),
            activated_paradigms=_net(_read_activated_paradigms(activation), deny.get("paradigms")),
            activated_procedures=_net(_read_activated_procedures(activation), deny.get("procedures")),
            activated_agent_profiles=_net(_read_activated_agent_profiles(activation), deny.get("agent_profiles")),
            activated_mission_step_contracts=_net(_read_activated_mission_step_contracts(activation), deny.get("mission_step_contracts")),
            activated_glossary_packs=_net(_read_activated_glossary_packs(activation), deny.get("glossary_packs")),
            activated_anti_patterns=_net(_read_activated_anti_patterns(activation), deny.get("anti_patterns")),
            activated_skills=_net(_read_activated_skills(activation, repo_root), deny.get("skills")),
            denied=denied,
        )


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def load_denied(
    repo_root: Path,
    *,
    ledger: ActivationLedger | None = None,
    org_roots: Iterable[Path] | None = None,
    kinds: AbstractSet[ArtifactKind] | None = None,
) -> tuple[tuple[str, DenySet], ...]:
    """The effective deny ``D*(k) = resolve_deny(D(k)) − R(k)`` per plural, sorted (FR-006).

    The one place a reader's deny is computed (:meth:`PackContext.from_config`
    and the readers that hold no ``PackContext`` call it). Only kinds with a
    non-empty deny list are resolved, so a project without one reads no
    identity index and no floor (NFR-003). The floor is read strictly: an
    unreadable declared org pack raises :class:`ActiveCharterConfigError`, as
    does a malformed ledger (fail closed). *kinds* narrows the resolution.
    """
    if ledger is None:
        if not ledger_may_hold_deny(repo_root):
            return ()
        ledger = load_activation_ledger(repo_root)
    pending = [(kind, tokens) for kind, tokens in ledger.deny if kinds is None or kind in kinds]
    if not pending:
        return ()
    from charter.activation.identity_index import IdentityIndex  # noqa: PLC0415 — lazy: identity_index imports layer_roots (cycle)

    roots = list(org_roots) if org_roots is not None else list(_read_org_packs(repo_root, {})[1])
    identity = IdentityIndex.build(repo_root, org_roots=roots)
    denied: list[tuple[str, DenySet]] = []
    for kind, tokens in pending:
        effective = _effective_deny(kind, tokens, read_org_required_tokens(repo_root, kind, strict=True), identity)
        if effective:
            denied.append((kind.plural, effective))
    return tuple(sorted(denied, key=lambda entry: entry[0]))


def _net(ids: frozenset[str] | None, deny: DenySet | None) -> frozenset[str] | None:
    """*ids* less the denied tokens; an absent list (``None``) stays absent. Reads only: writers derive from the ledger."""
    if ids is None or not deny:
        return ids
    return frozenset(token for token in ids if deny.admits(token))


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
    # The rule itself lives in the kernel (FR-017); this keeps its importers' signature.
    return legacy_pointer_path(repo_root, config_data.get(_CHARTER_POINTER_KEY))


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
    _load_config(repo_root)
    ledger = load_activation_ledger(repo_root)
    activation = ledger.raw()
    deny = dict(load_denied(repo_root, ledger=ledger))
    urns: set[str] = set()
    for key, kind in _ACTIVATION_URN_KINDS.items():
        entries = _net(_read_list_key(activation, key), deny.get(key.removeprefix(_ACTIVATION_KEY_PREFIX)))
        for entry in entries or ():
            urns.add(normalize_activation_identifier(kind, str(entry)))
    return urns


def _load_charter_activation_source(repo_root: Path, data: dict[str, Any]) -> dict[str, Any]:
    """Return the mapping ``_read_activated_*`` reads activation keys from.

    The activation ledger seam decides the source (FR-017,
    :func:`charter.activation.activation_ledger.load_activation_ledger`): the
    ledger when the kernel resolver says ``LEDGER``; otherwise the legacy
    surface by today's pointer rule (pointer absent -> ``config.yaml``;
    pointer present -> the pointed ``charter.yaml``, where a dangling or
    unreadable pointer fails loud, INV-5 / #2530). An unmigrated project fails
    closed naming ``spec-kitty upgrade``. The mapping is projected onto the
    ledger keys; *data* (the caller's parsed ``config.yaml``) is no longer
    read, the seam reads the files itself.
    """
    del data  # kept for the callers' signature; the seam reads the files itself
    activation: dict[str, Any] = load_activation_ledger(repo_root).raw()
    return activation


def _read_charter_mapping(
    charter_path: Path,
    display: str,
    fail: Callable[[str], ActiveCharterConfigError],
) -> dict[str, Any]:
    """Load ``charter_path`` as a mapping, refusing anything unparseable or non-mapping.

    The single parse + shape implementation behind :func:`load_charter_yaml_mapping` (the
    ``charter synthesize`` soundness gate, #6415). Any load exception (a scanner, composer or
    constructor error, ``RecursionError``, an unreadable file) is an invalid charter.
    """
    try:
        loaded = load_charter_yaml(charter_path)
    except Exception as exc:
        raise fail(f"Invalid YAML in {display}: {exc}") from exc
    if not isinstance(loaded, dict):
        raise fail(f"{display} root must be a mapping.")
    return dict(loaded)


def load_charter_yaml_mapping(repo_root: Path, *, remediation: str | None = None) -> tuple[Path, dict[str, Any]] | None:
    """Load the active ``charter.yaml`` as a mapping, or ``None`` when it is absent.

    Resolves the ``.kittify/config.yaml`` ``charter:`` pointer (falling back to
    the default ``.kittify/charter/charter.yaml``), then applies the activation
    reader's own soundness rule: unparseable or non-mapping content raises
    :class:`ActiveCharterConfigError`. An absent default file is ``None`` (the
    caller owns that case); a pointer naming a missing file is a refusal, as it
    is for the activation reader.

    *remediation* replaces the reader's default advice in the error text and
    marks the refusal as having written nothing. Returns ``(path, mapping)``.
    """
    pointer = resolve_charter_yaml_pointer(repo_root, _load_config(repo_root))
    charter_path = pointer if pointer is not None else repo_root / CHARTER_YAML
    try:
        display = charter_path.relative_to(repo_root).as_posix()
    except ValueError:
        display = str(charter_path)

    def fail(message: str) -> ActiveCharterConfigError:
        if remediation is None:
            return _config_error(message)
        return ActiveCharterConfigError(f"{message}\nNothing was written.\n{remediation}")

    if not charter_path.exists():
        if pointer is not None:
            raise fail(f".kittify/config.yaml 'charter:' pointer names {display}, which does not exist.")
        return None
    return charter_path, _read_charter_mapping(charter_path, display, fail)


def _load_config(repo_root: Path) -> dict[str, Any]:
    """Read and parse ``.kittify/config.yaml`` (the seam's one reader).

    Returns an empty dict when the file is absent. Invalid YAML or a non-mapping
    root is a hard error: activation filters must not fail open.
    """
    config: dict[str, Any] = load_config_yaml(repo_root)
    return config


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
    ``active_charter_service_builder``, invocation ``ProfileRegistry``, charter
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


def _read_activated_skills(data: dict[str, Any], repo_root: Path) -> frozenset[str] | None:
    """Extract ``activated_skills`` (three-state), applying the absent-key default.

    A present key keeps its literal meaning (``[]`` = nothing, ``[ids]`` =
    exactly those). An absent key resolves through
    :func:`_absent_key_default` -- for skills that is the org-required set, not
    ``None`` ("everything").
    """
    declared = _read_list_key(data, "activated_skills")
    if declared is not None:
        return declared
    return _absent_key_default(ArtifactKind.SKILL, repo_root)


def explicit_activated_skills(repo_root: Path) -> frozenset[str] | None:
    """The project's own ``activated_skills`` list, or ``None`` when the key is absent.

    Unlike :attr:`PackContext.activated_skills` this never applies the absent-key
    default (the org-required set), so a caller can tell "the project lists these
    skills" from "the org packs decide". Raises :class:`ActiveCharterConfigError` on a
    non-list value, exactly as :meth:`PackContext.from_config` does. The list is
    deny-netted (a denied skill is not listed; the required floor is never subtracted).
    """
    _load_config(repo_root)
    ledger = load_activation_ledger(repo_root)
    declared = _read_list_key(ledger.raw(), "activated_skills")
    if not declared:
        return declared
    return _net(declared, dict(load_denied(repo_root, ledger=ledger, kinds=frozenset({ArtifactKind.SKILL}))).get(ArtifactKind.SKILL.plural))


def _absent_key_default(kind: ArtifactKind, repo_root: Path) -> frozenset[str] | None:
    """What an absent activation key means for *kind* (default-in-force, plan decision 5).

    ``effective_when_absent == "all"`` kinds stay ``None`` (unrestricted: every
    available artifact is effective). ``"required"`` kinds put only the org
    packs' ``required_<plural>`` in force -- built-in defaults are empty at MVP.
    """
    if kind.effective_when_absent == "all":
        return None
    return frozenset(read_org_required_ids(repo_root, kind))


def _read_org_packs(repo_root: Path, _data: dict[str, Any]) -> tuple[tuple[str, ...], tuple[Path, ...]]:
    """Resolve org pack names and root paths from config data.

    Delegates to ``charter.offering.drg.org_pack_config.load_pack_registry``,
    which reads only the canonical ``charter_packs.org.packs``: a config that
    carries only a retired key yields no packs, never an error.

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
