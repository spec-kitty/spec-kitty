"""Pure plan/commit seam for charter activation (FR-011, FR-012, FR-021, NFR-003).

This module makes "validation provably precedes the single config write" a
*structural* property instead of an implementation detail. The previous
``ActiveCharterManager.activate`` body (``pack_manager.py``) interleaved
validation, absent-key materialization, list mutation, and the single
``_save_config`` write. That made the NFR-003 invariant ("config bytes
unchanged after any activation failure") true only by careful ordering and
hard to test in isolation.

The seam splits that into two functions:

* :func:`plan_activation` / :func:`plan_deactivation` — **pure**. They read the
  already-loaded config data, validate the kind + artifact ID (raising a
  structured :class:`UnknownActivationIdError` *before* computing any
  post-state), and return an :class:`ActivationPlan` describing the in-memory
  post-state. They never write. Materialization of the effective set is
  computed *into* the plan, so a failing plan never stages a half-materialized
  list.
* :func:`commit_plan` — performs the single ``_save_config`` write applying
  ``plan.new_list``. Nothing is written when there is no plan (a raised
  ``plan_*`` never reaches ``commit_plan``).

Consumers
---------
* ``pack_manager`` (WP09) will thin ``activate``/``deactivate`` to call this
  engine. The :class:`ActivationPlan` and the structured error are the seam
  surface.
* The CLI (WP12) renders ``plan.warnings`` and the structured error message.
* :func:`promote_activations` (WP06) is a second, append-only entry point onto
  the same :func:`commit_plan` chokepoint, used by the config-seeded migration
  and the interview command (WP07) and by the org-pack ``required_*`` union
  (WP04) to promote an arbitrary ``{yaml_key: [config-stem ids]}`` set in one
  pass — deliberately not limited to directive/paradigm roots, since org packs
  can mandate non-root kinds (tactics, styleguides, toolguides, ...). An absent
  key is seeded from its :class:`EffectiveSet` (resolved by the caller through
  :mod:`charter.activation.effective_set`); when that set is unresolved the key
  is left absent and reported (fail closed, FR-015 / #4400).

Layering
--------
Charter layer: this module may import ``doctrine`` and ``kernel`` but never
``specify_cli`` (C-001). The available-ID universe and the loaded config data
are passed in **as data** (C-008); this module performs no filesystem
discovery and no ``config.yaml`` load of its own. The single write in
:func:`commit_plan` delegates to the caller-supplied ``save`` callable so the
engine stays free of an I/O dependency on ``pack_manager`` internals. The one
read it makes is the effective deny of :func:`promote_activations`, through the
activation ledger seam (:func:`charter.activation.pack_context.load_denied`,
imported lazily), so no promotion caller can forget the required floor or apply
a legacy deny key. :func:`plan_activation` / :func:`plan_deactivation` take the
stored deny-list as data (``current_deny``), never from the write-target mapping.

FR-021 (backward compatibility)
-------------------------------
A project with **no explicit activation restrictions** for a kind (the YAML key
is absent — the ``None``-state) keeps every artifact that was effective in that
state: :func:`plan_activation` materializes the caller-supplied *effective*
corpus (the resolver's own view, falling back to the available one) into the
plan first, then appends the requested ID, and records an initialization warning
naming how many artifacts it preserved. Before #4253 it materialized a
narrower shipped list instead, which turned a single activation into a silent
deactivation of everything outside it.

Deny-lists (ADR 2026-10-19-1)
-----------------------------
A plan carries the allow **and** the deny state of one kind, so the
:func:`commit_plan` write stays single. Deactivation records an exclusion in
``deactivated_<plural>`` (also under "absent = all"), after the one refusal
seam :func:`check_deactivation_permitted` (an org-required id raises
:class:`RequiredArtifactDeactivationError`). Activation clears the id's
exclusion; promotion never re-adds an effective-denied id
(:attr:`PromotionOutcome.skipped_denied`).
"""

from __future__ import annotations

import dataclasses
from collections.abc import Callable, Iterable, Mapping, Sequence
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from charter.activation.activation_ledger import DenyListChoice, DenySet
from charter.offering.artifact_kinds import ArtifactKind

if TYPE_CHECKING:
    from pathlib import Path

    from charter.activation.org_pack_discovery import RequiringPack

__all__ = [
    "NARROW_UNRESOLVED_WARNING",
    "ActivationPlan",
    "DeactivationRefused",
    "EffectiveSet",
    "RequiredArtifactDeactivationError",
    "UnknownActivationIdError",
    "check_deactivation_permitted",
    "commit_plan",
    "deny_delta",
    "plan_activation",
    "plan_deactivation",
    "promote_activations",
]


# ---------------------------------------------------------------------------
# Structured errors
# ---------------------------------------------------------------------------


class UnknownActivationIdError(ValueError):
    """Raised when an activation artifact ID is unknown for its kind (FR-012).

    The message names the kind, the missing ID, and the recovery path so the
    error is actionable without grepping (Contract C3.1). The structured
    attributes let the CLI (WP12) render the same facts without re-parsing the
    string.
    """

    def __init__(self, kind: str, artifact_id: str) -> None:
        self.kind = kind
        self.artifact_id = artifact_id
        super().__init__(
            f"Unknown {kind} ID {artifact_id!r}. "
            f"No artifact with that ID is available for kind {kind!r}. "
            f"Run `charter list --show-available` to inspect available IDs, "
            f"or `doctor charter-packs` to verify the doctrine corpus is intact."
        )


class DeactivationRefused(ValueError):
    """Abstract: a deactivation the project's policy does not permit (ADR 2026-10-19-1 Decision 6).

    ``reason`` names the policy (``"required"`` today; a later ``"locked"``
    mutability level joins here). Only subclasses are raised.
    """

    def __init__(self, kind: str, artifact_id: str, reason: str, message: str) -> None:
        if type(self) is DeactivationRefused:
            raise TypeError("DeactivationRefused is abstract; raise a subclass")
        self.kind = kind
        self.artifact_id = artifact_id
        self.reason = reason
        super().__init__(message)


class RequiredArtifactDeactivationError(DeactivationRefused):
    """An org pack requires the artifact, so it cannot be deactivated (FR-007, US4.1)."""

    def __init__(self, kind: str, artifact_id: str, policy_key: str, requiring: tuple[RequiringPack, ...]) -> None:
        self.policy_key = policy_key
        self.requiring = requiring
        noun = "org pack" if len(requiring) == 1 else "org packs"
        packs = ", ".join(entry.describe() for entry in requiring)
        super().__init__(
            kind, artifact_id, "required", f"Cannot deactivate {kind} {artifact_id!r}: required by {noun} {packs} ({policy_key}). Nothing was recorded."
        )


def _policy_key(kind: str) -> str:
    """``required_<plural>`` of an operator kind token."""
    return f"required_{ArtifactKind.from_operator_token(kind).plural}"


def check_deactivation_permitted(kind: str, artifact_id: str, required_by: Mapping[str, tuple[RequiringPack, ...]]) -> None:
    """The one refusal seam (Decision 6): raise when *artifact_id* is in the required floor *required_by*."""
    requiring = required_by.get(artifact_id)
    if requiring:
        raise RequiredArtifactDeactivationError(kind, artifact_id, _policy_key(kind), tuple(requiring))


# ---------------------------------------------------------------------------
# ActivationPlan value object (data model §6)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ActivationPlan:
    """In-memory description of a single activation/deactivation post-state.

    Produced purely by :func:`plan_activation` / :func:`plan_deactivation` and
    applied (single write) by :func:`commit_plan`. The plan carries the *full*
    post-state list (``new_list``) — including any effective-set
    materialization — so the commit is a single assignment and a failing plan never leaves a
    half-materialized list behind (NFR-003).

    Attributes
    ----------
    yaml_key:
        The resolved ``config.yaml`` key the plan targets (e.g.
        ``"activated_directives"``).
    new_list:
        The post-state list to write for ``yaml_key``; ``None`` leaves the
        allow state as it is (an absent list stays absent).
    warnings:
        Operator-facing warnings (effective-set initialization, no-cascade
        skipped references (FR-013), mission-type step removal). The CLU/CLI
        renders these for any kind without special-casing.
    cascade_targets:
        Cascade activation/deactivation targets keyed by kind → IDs. Empty in
        WP10 (the cascade engine lands in WP11); the field exists so the seam
        shape is stable for WP11 and the CLI (WP12) needs no shape change.
    activated:
        IDs newly added by this plan (empty when the ID was already present).
    deactivated:
        IDs removed by this plan (empty for an activation plan or a no-op
        removal).
    deny_key:
        The ``deactivated_<plural>`` key the plan changes, or ``None`` when the
        deny-list is untouched.
    new_deny_list:
        The post-state deny-list for ``deny_key`` (``[]`` removes the key).
    deny_change:
        The explicit choice that authorises the deny change (FR-014).
    noop:
        ``True`` when the plan changes nothing (the caller writes nothing).
    """

    yaml_key: str
    new_list: list[str] | None
    warnings: list[str] = field(default_factory=list)
    cascade_targets: dict[str, list[str]] = field(default_factory=dict)
    activated: list[str] = field(default_factory=list)
    deactivated: list[str] = field(default_factory=list)
    deny_key: str | None = None
    new_deny_list: list[str] | None = None
    deny_change: DenyListChoice | None = None
    noop: bool = False


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


#: Appended to the warnings that materialise an absent key into an explicit list (#6408).
FROZEN_LIST_NOTE = (
    " This list is now explicit: artifacts shipped later are not activated automatically;"
    " use 'spec-kitty charter activate <kind> <id> --only' to keep activation narrow."
)


def _current_list(config_data: Mapping[str, Any], yaml_key: str) -> list[str] | None:
    """Return the current activation list for *yaml_key*, or ``None`` if absent.

    ``None`` is the no-restrictions / unupgraded state (FR-021). A present but
    non-list value is a malformed config and fails closed.
    """
    if yaml_key not in config_data:
        return None
    raw = config_data[yaml_key]
    if raw is None:
        return None
    if not isinstance(raw, list):
        raise ValueError(f"Activation key {yaml_key!r} must be a list, got {type(raw).__name__}.")
    return [str(item) for item in raw]


def _deny_list(deny_key: str | None, current_deny: Iterable[str]) -> list[str]:
    """The caller-supplied deny-list of *deny_key* (``[]`` for a kind without one).

    The deny-list always comes from the activation ledger seam, never from the
    write-target mapping (on a legacy source that mapping may hold a
    hand-written ``deactivated_<kind>`` key, which is never applied; FR-017).
    """
    if deny_key is None:
        return []
    return [str(item) for item in current_deny]


def _deny_key_for(yaml_key: str) -> str | None:
    """``deactivated_<plural>`` for an ``activated_<plural>`` key; ``None`` for a non-kind key."""
    plural = yaml_key.removeprefix("activated_")
    if plural == yaml_key or plural == "kinds":
        return None
    try:
        kind = ArtifactKind.from_plural(plural)
    except ValueError:
        return None
    return f"deactivated_{plural}" if kind.activatable else None


def deny_delta(before: Iterable[str] | None, after: Iterable[str] | None) -> tuple[list[str], list[str]]:
    """``(added, cleared)`` between two deny-lists, sorted; ``None`` reads as empty (R11)."""
    old, new = set(before or ()), set(after or ())
    return sorted(new - old), sorted(old - new)


def _with_deny(plan: ActivationPlan, deny_key: str | None, deny: list[str], cleared: str, choice: DenyListChoice) -> ActivationPlan:
    """*plan* with *cleared* taken off the deny-list, when it was on it (an explicit activation)."""
    if deny_key is None or cleared not in deny:
        return plan
    return dataclasses.replace(plan, deny_key=deny_key, new_deny_list=[item for item in deny if item != cleared], deny_change=choice)


def _materialise_absent(
    kind: str,
    effective_ids: Iterable[str],
    available_ids: Iterable[str],
    *,
    effective_when_absent: str,
    in_force: bool,
    exclude: AbstractSet[str],
) -> tuple[list[str], list[str]]:
    """What an absent list materialises (#4253), less the effective-denied ids; ``(ids, warnings)``."""
    materialized = [item for item in dict.fromkeys(effective_ids) if item not in exclude]
    if not materialized and effective_when_absent == "all":
        materialized = [item for item in dict.fromkeys(available_ids) if item not in exclude]
    warnings: list[str] = []
    if in_force:
        warnings.append(
            f"Kind {kind!r} had no explicit activation set. "
            f"Initialized from the {len(materialized)} artifact(s) already effective, "
            "so nothing in force was deactivated." + FROZEN_LIST_NOTE
        )
    return materialized, warnings


# ---------------------------------------------------------------------------
# Pure planning (no writes)
# ---------------------------------------------------------------------------


#: Warning shared by every narrowing caller when what was in force cannot be listed.
NARROW_UNRESOLVED_WARNING = "What stopped being in force cannot be listed: the effective set could not be resolved."


def plan_narrowed_list(yaml_key: str, selection: Iterable[str], base: Iterable[str], previous: Iterable[str]) -> ActivationPlan:
    """The one narrow post-state: *base* plus *selection*; what stops being in force is reported (#6408).

    Every id must already be in activation-stem spelling (callers map the effective
    set's declared ids through the identity index first). ``activated`` is the
    selection ids that were not already in *previous*; ``deactivated`` is every
    *previous* id that is not in the new list.
    """
    chosen = list(dict.fromkeys(selection))
    in_force = list(dict.fromkeys(previous))
    new_list = list(dict.fromkeys([*base, *chosen]))
    return ActivationPlan(
        yaml_key=yaml_key,
        new_list=new_list,
        activated=[item for item in chosen if item not in in_force],
        deactivated=[item for item in in_force if item not in new_list],
    )


def plan_activation(
    kind: str,
    artifact_id: str,
    *,
    yaml_key: str,
    available_ids: Iterable[str],
    config_data: Mapping[str, Any],
    effective_ids: Iterable[str] = (),
    effective_when_absent: str = "all",
    effective_ids_in_force: bool = True,
    cascade_scope: Any = None,  # noqa: ANN401
    narrow_base: Iterable[str] | None = None,
    previous_ids: Iterable[str] = (),
    deny_key: str | None = None,
    current_deny: Iterable[str] = (),
    deny_change: DenyListChoice = DenyListChoice.ACTIVATE,
    effective_deny: AbstractSet[str] = frozenset(),
) -> ActivationPlan:
    """Compute the post-state for activating *artifact_id* — purely (FR-011/012).

    Validation order is the structural NFR-003 guarantee: the artifact ID is
    checked against *available_ids* **before** any post-state is computed. On an
    unknown ID an :class:`UnknownActivationIdError` is raised and **no plan is
    returned**, so :func:`commit_plan` is never reached and nothing is written.

    FR-021: when the kind has no explicit activation set (``yaml_key`` absent in
    ``config_data``), everything currently in force is materialized into the
    plan first — *effective_ids* when the caller supplies them, else
    *available_ids* — and then *artifact_id* is appended. Writing a bare
    restrictive list into a previously-absent key would otherwise flip
    "everything is available" to "only this one is", silently deactivating the
    rest (#4253).

    Parameters
    ----------
    kind:
        CLI kind token (e.g. ``"directive"``), used only for error/warning text.
    artifact_id:
        The config-stem artifact ID to activate.
    yaml_key:
        Resolved ``config.yaml`` key for *kind* (caller supplies it as data).
    available_ids:
        The universe of valid artifact IDs for *kind* (caller-discovered).
    config_data:
        The already-loaded ``config.yaml`` mapping (read-only here).
    effective_ids:
        What the activation-aware resolver currently has in force for *kind*,
        supplied as data by the caller (C-008). This is the materialization
        source for the no-restrictions state: it spans the full declared org
        chain and is already in the keyspace the resolver filters on. Empty
        falls back to ``available_ids`` (for ``effective_when_absent="all"``).
    effective_when_absent:
        ``ArtifactKind.effective_when_absent`` of *kind*. ``"required"`` means
        the absent key put only the org-required set in force, so an empty
        *effective_ids* is genuinely empty and must NOT fall back to every
        available artifact (that would activate all skills at once).

        ``default_ids`` used to be this function's materialization source and
        is gone (#4399 squad MINOR): once the preserved set became the
        effective corpus, no reachable path could consume it — validation
        above guarantees ``artifact_id in available_ids``, so the
        empty-availability branch it guarded cannot occur.
        ``promote_activations`` is a different planner
        (:func:`_plan_promotion`) with its own fail-closed absent-key contract.
    effective_ids_in_force:
        ``True`` (default) when *effective_ids* is what was in force while the
        key was absent; the plan then reports that nothing in force was
        deactivated. ``False`` when the caller materialized a substitute (the
        effective set was unresolved, or ``mission-type``, whose absent key
        puts nothing in force); the claim would be false, so it is not made and
        the caller reports what it used instead.
    cascade_scope:
        Reserved for the WP11 cascade engine; threaded but not consumed here
        (never collapsed to a bool — Contract C3.3).
    narrow_base:
        Opt-in narrow activation (#6408, ``charter activate --only``). When not
        ``None`` the kind's list becomes *narrow_base* (de-duplicated) plus
        *artifact_id*, replacing any present list and skipping absent-key
        materialisation. ``None`` (default) keeps the append behaviour.
    previous_ids:
        What was in force before a narrowing, in the same spelling as
        *narrow_base*. ``deactivated`` reports every one that is not in the new
        list. Ignored unless *narrow_base* is given.
    deny_key:
        The kind's ``deactivated_<plural>`` key (``None``: the kind has no
        deny-list). When *artifact_id* is on *current_deny*, the plan clears
        it with *deny_change*; under an absent "all" list the plan is deny-only
        and the allow list stays absent (D-09).
    current_deny:
        The kind's stored deny-list, read by the caller through the activation
        ledger seam (``ActivationLedger.deny_for``; empty on a legacy source).
        It is never read from *config_data*: a hand-written legacy
        ``deactivated_<kind>`` key is reported, never applied (FR-017).
    deny_change:
        The explicit choice recorded for a cleared exclusion.
    effective_deny:
        ``D*`` in stem spelling: left out of an absent-list materialisation.

    Returns
    -------
    ActivationPlan
        The full in-memory post-state.

    Raises
    ------
    UnknownActivationIdError
        If *artifact_id* is not in *available_ids* (raised before any post-state
        is computed — FR-011/012, NFR-003).
    ValueError
        If ``config_data[yaml_key]`` is present but not a list (malformed
        config, fail-closed).
    """
    # Preserve the typed cascade contract at this seam even though this pure
    # planner does not branch on it yet.
    _ = cascade_scope
    # FR-011/012/NFR-003: validate BEFORE computing any post-state.
    if artifact_id not in set(available_ids):
        raise UnknownActivationIdError(kind, artifact_id)

    # Fail closed on a malformed (non-list) value on every path, narrowing included.
    current = _current_list(config_data, yaml_key)
    deny = _deny_list(deny_key, current_deny)

    if narrow_base is not None:
        return _with_deny(plan_narrowed_list(yaml_key, [artifact_id], narrow_base, previous_ids), deny_key, deny, artifact_id, deny_change)

    if current is None and effective_when_absent == "all" and artifact_id in deny:
        # D-09: clearing the exclusion is enough; materialising would freeze the list.
        plan = ActivationPlan(
            yaml_key=yaml_key,
            new_list=None,
            activated=[artifact_id],
            warnings=[f"Kind {kind!r} keeps no explicit activation set, so artifacts shipped later stay active."],
        )
        return _with_deny(plan, deny_key, deny, artifact_id, deny_change)

    warnings: list[str] = []
    if current is None:
        # #4253: an absent key is the UNRESTRICTED state — every EFFECTIVE
        # artifact is in force. ``effective_ids`` is the resolver's own view
        # (it spans the full org chain and the keyspace the resolver filters
        # on); ``available_ids`` is the fallback. Effective-denied ids stay out.
        new_list, warnings = _materialise_absent(
            kind, effective_ids, available_ids, effective_when_absent=effective_when_absent, in_force=effective_ids_in_force, exclude=effective_deny - {artifact_id}
        )
    else:
        new_list = list(current)

    activated: list[str] = []
    if artifact_id in new_list and current is not None:
        warnings.append(f"{artifact_id!r} is already activated for kind {kind!r}.")
    else:
        # From the unrestricted state the artifact was effective only
        # implicitly; this call is what makes it explicit, so it is reported
        # as activated even though the materialized set already lists it.
        if artifact_id not in new_list:
            new_list.append(artifact_id)
        activated.append(artifact_id)

    plan = ActivationPlan(yaml_key=yaml_key, new_list=new_list, warnings=warnings, activated=activated)
    return _with_deny(plan, deny_key, deny, artifact_id, deny_change)


def plan_deactivation(
    kind: str,
    artifact_id: str,
    *,
    yaml_key: str,
    config_data: Mapping[str, Any],
    available_ids: Iterable[str],
    required_by: Mapping[str, tuple[RequiringPack, ...]],
    deny_key: str | None,
    current_deny: Iterable[str] = (),
    record_exclusion: bool = True,
    also_matches: Iterable[str] = (),
    cascade_scope: Any = None,  # noqa: ANN401
) -> ActivationPlan:
    """Compute the post-state for deactivating *artifact_id* — purely (FR-007, data-model.md §3).

    In order: the refusal seam (:func:`check_deactivation_permitted`; an id the
    required floor *required_by* lists raises), the unknown id (neither
    available, listed nor already denied: :class:`UnknownActivationIdError`),
    then the plan.
    *artifact_id* is removed from a present allow list (with any spelling in
    *also_matches*) and, with *record_exclusion*, added to the deny-list under
    :attr:`DenyListChoice.DEACTIVATE` — also when the allow list is absent
    ("absent = all"), which the allow list alone cannot express. An id that is
    already denied is a flagged no-op with a warning. A cascade child
    (*record_exclusion* ``False``) only loses its allow entry (D-11).

    Raises
    ------
    RequiredArtifactDeactivationError
        If an org pack requires *artifact_id*.
    UnknownActivationIdError
        If *artifact_id* is neither available, in the allow list nor denied.
    ValueError
        If ``config_data[yaml_key]`` is present but not a list.
    """
    _ = cascade_scope
    check_deactivation_permitted(kind, artifact_id, required_by)
    current = _current_list(config_data, yaml_key)
    deny = _deny_list(deny_key, current_deny)
    spellings = {artifact_id, *also_matches}
    if artifact_id not in set(available_ids) and not spellings & {*(current or ()), *deny}:
        raise UnknownActivationIdError(kind, artifact_id)

    records = record_exclusion and deny_key is not None
    if records and artifact_id in deny:
        return ActivationPlan(
            yaml_key=yaml_key, new_list=current, noop=True, warnings=[f"{artifact_id!r} is already deactivated for kind {kind!r}. Nothing was recorded."]
        )

    removed = [item for item in current or () if item in spellings]
    new_list = None if current is None else [item for item in current if item not in spellings]
    if not removed and not records:
        warning = f"{artifact_id!r} is not in the activation set for kind {kind!r}. Nothing to deactivate."
        return ActivationPlan(yaml_key=yaml_key, new_list=current, noop=True, warnings=[warning])

    plan = ActivationPlan(yaml_key=yaml_key, new_list=new_list, deactivated=[artifact_id])
    if not records:
        return plan
    return dataclasses.replace(plan, deny_key=deny_key, new_deny_list=sorted({*deny, artifact_id}), deny_change=DenyListChoice.DEACTIVATE)


# ---------------------------------------------------------------------------
# Single-write commit
# ---------------------------------------------------------------------------


def commit_plan(
    config_path: Path,
    config_data: dict[str, Any],
    plan: ActivationPlan,
    *,
    save: Callable[..., None],
) -> ActivationPlan:
    """Apply *plan* to *config_data* and persist it with a single write.

    The caller passes the *same* config mapping it handed to ``plan_*`` (so
    round-trip metadata such as ruamel comments is preserved) and a ``save``
    callable that performs the actual ``_save_config`` write. This is the
    **only** write path: ``plan_*`` raised before producing a plan means
    ``commit_plan`` is never called and nothing is written (NFR-003).

    Parameters
    ----------
    config_path:
        Destination ``config.yaml`` path (passed through to ``save``).
    config_data:
        The mutable config mapping; ``plan.yaml_key`` is assigned
        ``plan.new_list`` (unless ``None``) and ``plan.deny_key`` its new
        deny-list (an empty one removes the key) in place before the write.
    plan:
        The plan produced by :func:`plan_activation` / :func:`plan_deactivation`.
    save:
        Single-write callable, e.g. ``functools.partial(_save_config,
        yaml=yaml_inst)`` from ``pack_manager``. Called as ``save(path, data)``,
        plus ``deny_change=`` when the plan changes a deny-list.

    Returns
    -------
    ActivationPlan
        The committed plan (returned for convenient result chaining).
    """
    if plan.new_list is not None:
        config_data[plan.yaml_key] = list(plan.new_list)
    if plan.deny_key is not None:
        if plan.new_deny_list:
            config_data[plan.deny_key] = sorted(set(plan.new_deny_list))
        else:
            config_data.pop(plan.deny_key, None)
    if plan.deny_change is None:
        save(config_path, config_data)
    else:
        save(config_path, config_data, deny_change=plan.deny_change)
    return plan


# ---------------------------------------------------------------------------
# Append-promotion primitive (WP06, FR-006/FR-007; fail closed, FR-015 / #4400)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EffectiveSet:
    """What is effective for one activation key while that key is absent.

    Produced by :func:`charter.activation.effective_set.resolve_effective_sets`
    (the one public effective-set seam) and consumed here as data, so this
    engine stays free of repository I/O. It is defined in the engine because the
    engine is what consumes it; the seam module exposes a single function.

    Attributes
    ----------
    kind:
        Charter kind operator token (e.g. ``"procedure"``).
    yaml_key:
        The activation key (e.g. ``"activated_procedures"``).
    ids:
        The effective ids, in the spelling the activation filter compares
        against. Empty when :attr:`resolved` is ``False``.
    resolved:
        ``False`` when the set could not be determined; the caller must then
        leave the key absent and report :attr:`reason` (never write a bare list).
    reason:
        Why the set is unresolved; ``None`` when resolved.
    fallback_ids:
        Set only when :attr:`resolved` is ``False``: the best-effort union of
        the ids available across every *readable* layer (the built-in layer,
        each declared org pack root that can be read, the project layer, plus
        the activation-aware service's keys when it can be built). It is not
        the effective set and no promotion writes it; only a tolerant single
        activation (``ActiveCharterManager.activate``) materializes it, so
        that activation never narrows below the whole readable chain. Empty
        for a required-only kind (``skill``).
    """

    kind: str
    yaml_key: str
    ids: frozenset[str] = frozenset()
    resolved: bool = True
    reason: str | None = None
    fallback_ids: frozenset[str] = frozenset()


@dataclass(frozen=True)
class PromotionOutcome:
    """Result of :func:`promote_activations`.

    Attributes
    ----------
    committed:
        The committed plans, one per promoted key, in iteration order.
    left_absent:
        ``yaml_key`` -> reason for every absent key whose effective set was
        unresolved: nothing was written for it and the caller reports it.
    skipped_denied:
        ``yaml_key`` -> the effective-denied ids the promotion left out
        (promotion never re-adds an excluded id; FR-009).
    """

    committed: list[ActivationPlan] = field(default_factory=list)
    left_absent: dict[str, str] = field(default_factory=dict)
    skipped_denied: dict[str, list[str]] = field(default_factory=dict)

    def skipped_denied_messages(self) -> list[str]:
        """One warning per key whose promotion skipped effective-denied ids (FR-009)."""
        return [
            f"{yaml_key}: skipped {', '.join(repr(item) for item in ids)}: deactivated; run `spec-kitty charter activate` to reinstate."
            for yaml_key, ids in self.skipped_denied.items()
        ]

    def left_absent_messages(self) -> list[str]:
        """One operator-facing line per left-absent key, the same wording for every caller."""
        return [
            f"{yaml_key} was left absent and nothing was promoted into it: the effective set could not be resolved ({reason})."
            for yaml_key, reason in self.left_absent.items()
        ]


#: Reason recorded when a caller supplied no effective set for an absent key.
_NO_EFFECTIVE_SET = "no effective set was resolved for this key"


def _plan_promotion(
    yaml_key: str,
    ids: Iterable[str],
    *,
    config_data: Mapping[str, Any],
    effective: EffectiveSet | None,
    narrow_base: Sequence[str] | None = None,
    denied: DenySet = DenySet.EMPTY,
) -> ActivationPlan | str:
    """Compute the append-only post-state for promoting *ids* into *yaml_key*.

    Pure — no writes (mirrors :func:`plan_activation` / :func:`plan_deactivation`).
    This is a **separate** planner from :func:`plan_activation`: it never raises
    on an unknown ID (the caller owns ID validation, e.g. via
    :func:`charter.activation.kind_vocabulary.resolve_artifact_urn`) and it does not reuse
    :func:`plan_activation`'s absent-key branch.

    Absent-key semantics (FR-015 / #4400): an absent ``activated_<kind>`` key
    means "everything effective" (three-state contract of
    :meth:`~charter.activation.pack_context.PackContext.from_config`). Writing a
    bare list into it would narrow that to "only these ids", so an absent key is
    seeded from *effective* (sorted, deterministic) before *ids* are appended.
    When *effective* is missing or unresolved, no plan is produced: the reason
    is returned instead and the key stays absent (fail closed). Ids in
    *denied* (``D*``) are neither seeded nor appended.
    """
    current = _current_list(config_data, yaml_key)
    warnings: list[str] = []

    if narrow_base is not None:
        resolved = effective is not None and effective.resolved
        previous = current if current is not None else sorted(effective.ids) if effective is not None and resolved else []
        plan = plan_narrowed_list(yaml_key, [item for item in ids if denied.admits(item)], narrow_base, previous)
        if current is None and not resolved:
            plan.warnings.append(NARROW_UNRESOLVED_WARNING)
        return plan

    if current is None:
        if effective is None or not effective.resolved:
            return (effective.reason if effective is not None else None) or _NO_EFFECTIVE_SET
        new_list = sorted(item for item in effective.ids if denied.admits(item))
        warnings.append(
            f"Key {yaml_key!r} had no explicit activation set. Preserved {len(new_list)} effective entries before promotion (absent-key parity)." + FROZEN_LIST_NOTE
        )
    else:
        new_list = list(current)

    activated: list[str] = []
    for artifact_id in dict.fromkeys(ids):
        if not denied.admits(artifact_id):
            continue
        if artifact_id in new_list:
            warnings.append(f"{artifact_id!r} is already activated for key {yaml_key!r}.")
        else:
            new_list.append(artifact_id)
            activated.append(artifact_id)

    return ActivationPlan(
        yaml_key=yaml_key,
        new_list=new_list,
        warnings=warnings,
        activated=activated,
    )


def promote_activations(
    promotions: Mapping[str, Iterable[str]],
    *,
    config_path: Path,
    config_data: dict[str, Any],
    save: Callable[[Path, dict[str, Any]], None],
    effective_sets: Mapping[str, EffectiveSet],
    narrow_bases: Mapping[str, Sequence[str]] | None = None,
    repo_root: Path | None = None,
    denied: Mapping[str, DenySet] | None = None,
) -> PromotionOutcome:
    """Promote an arbitrary ``{yaml_key: [config-stem ids]}`` set, append-only.

    Shared by the config-seeded migration, the interview command, the org-pack
    ``required_*`` union and (as a reader of the same rule) the resynthesis
    preflight. Deliberately **not** roots-only: org packs can mandate non-root
    kinds (tactics, styleguides, toolguides, ...), so *promotions* accepts any
    resolved ``config.yaml`` activation key.

    Fail-closed rule (FR-015 / #4400):

    * key present → the promoted ids are appended (append-only);
    * key absent and its :class:`EffectiveSet` resolved → the new list is the
      effective set (sorted) followed by the promoted ids not already in it, so
      nothing effective before is lost;
    * key absent and its set unresolved, or missing from *effective_sets* →
      **no plan is committed for that key**: it stays absent and is reported in
      :attr:`PromotionOutcome.left_absent`. A bare list is never written.

    Write mechanism (C-002): one :class:`ActivationPlan` per committed key via
    :func:`_plan_promotion`, applied with exactly one :func:`commit_plan` call
    per committed key. ``save`` is never invoked directly, and never for a
    left-absent key.

    Parameters
    ----------
    promotions:
        Maps a resolved activation key (e.g. ``"activated_directives"``) to the
        config-stem IDs to append. Callers resolve the key themselves; this
        module does not re-derive it. An included key with no IDs still
        performs a single no-op commit when the key is present.
    config_path:
        Destination path (passed through to ``save``).
    config_data:
        The mutable, already-loaded activation mapping; mutated in place, one
        key at a time.
    save:
        Single-write callable, forwarded verbatim to :func:`commit_plan`.
    effective_sets:
        ``yaml_key`` -> :class:`EffectiveSet`, resolved by the caller (as data,
        C-008) for the keys that are absent. Keys that are present need no entry.
    narrow_bases:
        Opt-in narrowing (#6408): ``yaml_key`` -> base ids. A key listed here is
        written as that base plus its promoted ids (replacing any present list,
        never reading its effective set); the plan's ``deactivated`` names what
        stopped being in force. ``None`` (default) keeps append-only behaviour.
    repo_root:
        The project whose effective deny ``D*`` (deny less the org required
        floor, in identity space) the promotion honours. ``D*`` is derived
        here, through the activation ledger seam
        (:func:`charter.activation.pack_context.load_denied`), never from
        *config_data*: a legacy source holds no applied deny (FR-017) and a
        stale deny of a required id is inert (FR-006). Defaults to the project
        that holds *config_path* (the parent of its ``.kittify`` ancestor). An
        id in ``D*`` is skipped and reported in
        :attr:`PromotionOutcome.skipped_denied`; a deny-list is never changed.
    denied:
        ``yaml_key`` -> an already-derived ``D*``, replacing the seam read
        (pure callers and tests).

    Returns
    -------
    PromotionOutcome
        The committed plans and the keys left absent, with their reasons.
    """
    outcome = PromotionOutcome()
    effective_denied = denied if denied is not None else _seam_deny(repo_root if repo_root is not None else _owning_project(config_path), promotions)
    for yaml_key, ids in promotions.items():
        ids = list(ids)
        effective = effective_sets.get(yaml_key)
        key_denied = effective_denied.get(yaml_key, DenySet.EMPTY)
        plan = _plan_promotion(
            yaml_key,
            ids,
            config_data=config_data,
            effective=effective,
            narrow_base=narrow_bases.get(yaml_key) if narrow_bases is not None else None,
            denied=key_denied,
        )
        if isinstance(plan, str):
            outcome.left_absent[yaml_key] = plan
            continue
        skipped = _skipped_ids(key_denied, ids, effective, seeded=_current_list(config_data, yaml_key) is None)
        if skipped:
            outcome.skipped_denied[yaml_key] = skipped
        outcome.committed.append(commit_plan(config_path, config_data, plan, save=save))
    return outcome


def _owning_project(config_path: Path) -> Path | None:
    """The project root holding *config_path* (the parent of its nearest ``.kittify`` ancestor), else ``None``."""
    for parent in config_path.parents:
        if parent.name == ".kittify":
            return parent.parent
    return None


def _promoted_kinds(promotions: Iterable[str]) -> frozenset[ArtifactKind]:
    """The activatable kinds of the promoted ``activated_<plural>`` keys (non-kind keys have no deny-list)."""
    kinds: set[ArtifactKind] = set()
    for yaml_key in promotions:
        if _deny_key_for(yaml_key) is not None:
            kinds.add(ArtifactKind.from_plural(yaml_key.removeprefix("activated_")))
    return frozenset(kinds)


def _seam_deny(repo_root: Path | None, promotions: Iterable[str]) -> dict[str, DenySet]:
    """``yaml_key`` -> ``D*`` of the promoted kinds, through the activation ledger seam (one place, FR-006/FR-017).

    ``{}`` without a project or without a promoted kind; the seam itself reads
    nothing more when no deny-list is recorded (NFR-003).
    """
    kinds = _promoted_kinds(promotions)
    if repo_root is None or not kinds:
        return {}
    from charter.activation.pack_context import load_denied  # lazy: pack_context imports the activation layer

    return {f"activated_{plural}": deny for plural, deny in load_denied(repo_root, kinds=kinds)}


def _skipped_ids(denied: DenySet, ids: Iterable[str], effective: EffectiveSet | None, *, seeded: bool) -> list[str]:
    """The denied ids a promotion would have written: promoted ones, and seeded ones for an absent key."""
    if not denied:
        return []
    candidates = set(ids) | (set(effective.ids) if seeded and effective is not None and effective.resolved else set())
    return sorted(item for item in candidates if not denied.admits(item))
