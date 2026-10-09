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
engine stays free of an I/O dependency on ``pack_manager`` internals.

FR-021 (backward compatibility)
-------------------------------
A project with **no explicit activation restrictions** for a kind (the YAML key
is absent — the ``None``-state) keeps every artifact that was effective in that
state: :func:`plan_activation` materializes the caller-supplied *effective*
corpus (the resolver's own view, falling back to the available one) into the
plan first, then appends the requested ID, and records an initialization warning
naming how many artifacts it preserved. Before #4253 it materialized a
narrower shipped list instead, which turned a single activation into a silent
deactivation of everything outside it. Deactivation against a ``None``-state
kind is reported as a structured :class:`NoActivationRestrictionsError` (the CLI
surfaces the "activate one first" guidance) rather than silently fabricating a
list.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from charter.offering.artifact_kinds import ArtifactKind

if TYPE_CHECKING:
    from pathlib import Path

__all__ = [
    "ActivationPlan",
    "EffectiveSet",
    "NoActivationRestrictionsError",
    "UnknownActivationIdError",
    "commit_plan",
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
            f"or `doctor doctrine` to verify the doctrine corpus is intact."
        )


class NoActivationRestrictionsError(RuntimeError):
    """Raised when deactivating a kind that has no explicit activation set.

    A kind with no explicit activation set (the YAML key is absent) has no
    known baseline, so removing a single ID would be unsafe. The operator must
    materialize the list first. Replaces the legacy ``sys.exit(1)`` in
    ``pack_manager.deactivate`` so the engine never touches process state
    (the CLI surfaces the guidance).
    """

    def __init__(self, kind: str) -> None:
        self.kind = kind
        super().__init__(_no_restrictions_message(kind))


def _no_restrictions_message(kind: str) -> str:
    """Return the operator remedy for deactivating a kind with no explicit set.

    An absent key is never seeded by ``spec-kitty upgrade`` (absent already
    means "everything effective"), so the
    remedy is the step that actually materializes the list: one explicit
    activation, which seeds the full effective set first, or an explicit list.
    A kind whose absent key means "required only" (see
    :attr:`ArtifactKind.effective_when_absent`) says which entries are in force.
    """
    try:
        required_only = ArtifactKind.from_operator_token(kind).effective_when_absent == "required"
    except ValueError:
        required_only = False
    in_force = " (only org-required entries are in force)" if required_only else ""
    return (
        f"Kind {kind!r} has no explicit activation set{in_force}. "
        f"Activate one first with `spec-kitty charter activate {kind} <id>`, or set the list explicitly in "
        "`.kittify/config.yaml`, before deactivating individual entries."
    )


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
        The post-state list to write for ``yaml_key``.
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
    """

    yaml_key: str
    new_list: list[str]
    warnings: list[str] = field(default_factory=list)
    cascade_targets: dict[str, list[str]] = field(default_factory=dict)
    activated: list[str] = field(default_factory=list)
    deactivated: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Pure planning (no writes)
# ---------------------------------------------------------------------------


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

    warnings: list[str] = []
    current = _current_list(config_data, yaml_key)

    was_unrestricted = current is None
    if current is None:  # the UNRESTRICTED state; narrows `current` for the else branch
        # #4253: an absent key is the UNRESTRICTED state — every EFFECTIVE
        # artifact is in force, which is strictly wider than any shipped
        # list. Materializing such a list here therefore did not merely
        # "initialize" the set: it silently DEACTIVATED every effective
        # artifact outside it (observed: 15 directives and 11
        # procedures, including adversarial-squad-deployment, lost on a
        # single unrelated activation).
        #
        # ``effective_ids`` is the resolver's OWN view of what is in force —
        # read from the activation-aware doctrine service by the caller. It
        # is the right source for two reasons the #4399 squad round found by
        # execution: it spans the full declared org chain (``list_available``
        # is handed a root map that deliberately truncates to org pack #1),
        # and it is already in the keyspace the resolver filters on (Pattern
        # B/C kinds such as procedures match a declared ``id:``, so a set
        # written as filename stems is filtered straight back out). Falling
        # back to ``available_ids`` keeps a caller that cannot build a
        # service — or a kind the service does not expose — behaving as it
        # did before.
        materialized = list(dict.fromkeys(effective_ids))
        if not materialized and effective_when_absent == "all":
            materialized = list(dict.fromkeys(available_ids))
        if effective_ids_in_force:
            warnings.append(
                f"Kind {kind!r} had no explicit activation set. "
                f"Initialized from the {len(materialized)} artifact(s) already effective, "
                "so nothing in force was deactivated."
            )
        new_list = list(materialized)
    else:
        new_list = list(current)

    activated: list[str] = []
    if artifact_id in new_list and not was_unrestricted:
        warnings.append(f"{artifact_id!r} is already activated for kind {kind!r}.")
    else:
        # From the unrestricted state the artifact was effective only
        # implicitly; this call is what makes it explicit, so it is reported
        # as activated even though the materialized set already lists it.
        if artifact_id not in new_list:
            new_list.append(artifact_id)
        activated.append(artifact_id)

    return ActivationPlan(
        yaml_key=yaml_key,
        new_list=new_list,
        warnings=warnings,
        activated=activated,
    )


def plan_deactivation(
    kind: str,
    artifact_id: str,
    *,
    yaml_key: str,
    config_data: Mapping[str, Any],
    cascade_scope: Any = None,  # noqa: ANN401
) -> ActivationPlan:
    """Compute the post-state for deactivating *artifact_id* — purely.

    Mirrors :func:`plan_activation` on the removal side. A kind with no explicit
    activation set has no known baseline, so this raises
    :class:`NoActivationRestrictionsError` (no write) instead of fabricating a
    list. Removing an ID that is not present is a no-op plan (the ``new_list``
    equals the current list) with an explanatory warning.

    Parameters
    ----------
    kind:
        CLI kind token, used only for error/warning text.
    artifact_id:
        The config-stem artifact ID to deactivate.
    yaml_key:
        Resolved ``config.yaml`` key for *kind*.
    config_data:
        The already-loaded ``config.yaml`` mapping (read-only here).
    cascade_scope:
        Reserved for the WP11 cascade engine; threaded but not consumed here.

    Returns
    -------
    ActivationPlan
        The full in-memory post-state.

    Raises
    ------
    NoActivationRestrictionsError
        If *kind* has no explicit activation set (``yaml_key`` absent).
    ValueError
        If ``config_data[yaml_key]`` is present but not a list.
    """
    # Preserve the typed cascade contract at this seam even though this pure
    # planner does not branch on it yet.
    _ = cascade_scope
    current = _current_list(config_data, yaml_key)
    if current is None:
        raise NoActivationRestrictionsError(kind)

    warnings: list[str] = []
    new_list = list(current)
    deactivated: list[str] = []

    if artifact_id in new_list:
        new_list.remove(artifact_id)
        deactivated.append(artifact_id)
    else:
        warnings.append(f"{artifact_id!r} is not in the activation set for kind {kind!r}. Nothing to deactivate.")

    return ActivationPlan(
        yaml_key=yaml_key,
        new_list=new_list,
        warnings=warnings,
        deactivated=deactivated,
    )


# ---------------------------------------------------------------------------
# Single-write commit
# ---------------------------------------------------------------------------


def commit_plan(
    config_path: Path,
    config_data: dict[str, Any],
    plan: ActivationPlan,
    *,
    save: Callable[[Path, dict[str, Any]], None],
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
        ``plan.new_list`` in place before the write.
    plan:
        The plan produced by :func:`plan_activation` / :func:`plan_deactivation`.
    save:
        Single-write callable, e.g. ``functools.partial(_save_config,
        yaml=yaml_inst)`` from ``pack_manager``.

    Returns
    -------
    ActivationPlan
        The committed plan (returned for convenient result chaining).
    """
    config_data[plan.yaml_key] = list(plan.new_list)
    save(config_path, config_data)
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
    """

    committed: list[ActivationPlan] = field(default_factory=list)
    left_absent: dict[str, str] = field(default_factory=dict)

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
    is returned instead and the key stays absent (fail closed).
    """
    current = _current_list(config_data, yaml_key)
    warnings: list[str] = []

    if current is None:
        if effective is None or not effective.resolved:
            return (effective.reason if effective is not None else None) or _NO_EFFECTIVE_SET
        new_list = sorted(effective.ids)
        warnings.append(f"Key {yaml_key!r} had no explicit activation set. Preserved {len(new_list)} effective entries before promotion (absent-key parity).")
    else:
        new_list = list(current)

    activated: list[str] = []
    for artifact_id in dict.fromkeys(ids):
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

    Returns
    -------
    PromotionOutcome
        The committed plans and the keys left absent, with their reasons.
    """
    outcome = PromotionOutcome()
    for yaml_key, ids in promotions.items():
        plan = _plan_promotion(
            yaml_key,
            ids,
            config_data=config_data,
            effective=effective_sets.get(yaml_key),
        )
        if isinstance(plan, str):
            outcome.left_absent[yaml_key] = plan
            continue
        outcome.committed.append(commit_plan(config_path, config_data, plan, save=save))
    return outcome
