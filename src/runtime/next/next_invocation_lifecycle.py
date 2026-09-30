"""FR-014 shared next-invocation lifecycle/event-log seam.

Mission ``design-phase-orchestrator-api-01M1HE6M``, WP02. Extracted (a pure,
behaviour-preserving move -- never a redesign, never duplicated logic) from
``specify_cli.cli.commands.next_cmd``'s formerly-private ``--answer``-path
helpers, per operator ruling SPEC-FRESH2-001
(``kitty-specs/design-phase-orchestrator-api-01M1HE6M/reviews/spec.ruling.md``)
and spec constraint C-005.

The ruling requires that BOTH the host CLI (``next_cmd.py``, this WP) and
orchestrator-api's future ``answer-decision`` verb (WP08, strictly gated on
this WP) reach the SAME three side effects through one shared seam rather
than through two independently-maintained copies -- an ``answer-decision``
verb built only from the two engine calls would look byte-identical to the
CLI's own response while silently failing to advance the mission's event log
or lifecycle-record store (a silent behavioural divergence, this
repository's named dominant failure mode).

Placement (plan.md § (a), not re-derived here): top-level under
``src/runtime/next/``, a sibling of ``runtime_bridge.py`` and
``decision.py`` -- NOT under ``_internal_runtime/`` (reserved for
internalized former-``spec-kitty-runtime``-package DAG-engine re-exports;
that subpackage carries no ``lifecycle_record``/``issuance`` concept), and
NOT under ``specify_cli.orchestrator_api`` (exactly the "inline into the
orchestrator-api layer" the operator ruling rejected). ``runtime.next``
modules already freely import ``specify_cli.*`` domain modules
(``decision.py`` imports ``specify_cli.mission_metadata`` and
``specify_cli.mission_v1.events``; ``runtime_bridge.py`` imports
``specify_cli.mission_metadata``) -- this module's imports below follow that
same established precedent, per the charter's Internal Runtime Boundary
("Runtime code used by ``spec-kitty next`` ... should live inside this
repository" and may freely consume CLI-owned domain modules).

The three functions below are carried over VERBATIM from their former
private, inlined homes -- same parameters, same best-effort/fail-closed
``except Exception: return`` semantics -- with two narrow, non-behavioural
adjustments made necessary by this module joining the genuinely
``mypy --strict``-enforced set (``next_cmd.py`` itself sits in
``pyproject.toml``'s transitional mypy quarantine, so this exact typing gap
was never actually checked there):

1. ``emit_mission_next_invoked``'s ``decision`` parameter is typed
   ``object`` (per this WP's pinned target signature) -- attribute reads on
   it use the two-argument ``getattr(obj, name)`` form instead of dotted
   attribute access. ``getattr(obj, name)`` is runtime-identical to
   ``obj.name`` (same ``AttributeError`` if the attribute is truly absent,
   which never happens for a real ``Decision``) and is simply how one reads
   an attribute off a statically ``object``-typed value without violating
   ``mypy --strict``.
2. ``emit_mission_next_invoked``'s ``repo_root`` is coerced to a real
   ``Path`` before the ``placement_seam(...)`` call, mirroring the
   coercion idiom the sibling ``pair_previous_lifecycle_record`` /
   ``write_issuance_lifecycle_record`` functions already use in this same
   file for the identical ``repo_root: object`` parameter (the original
   ``_emit_mission_next_invoked`` passed ``repo_root`` uncoerced --
   ``mission_runtime.placement_seam`` is itself fully typed
   (``repo_root: Path``), so this was a real, latent type mismatch masked
   only by ``next_cmd.py``'s mypy quarantine, never by anything at
   runtime -- every real caller already passes a ``Path``, so the coercion
   is a no-op for every existing call site).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from mission_runtime import MissionArtifactKind, OwnedCheckout, mission_context_for

from specify_cli.core.paths import MissionMetaReadError

__all__ = [
    "AmbiguousPendingDecisionError",
    "NoPendingDecisionError",
    "emit_mission_next_invoked",
    "pair_previous_lifecycle_record",
    "resolve_pending_decision_id",
    "write_issuance_lifecycle_record",
]


class NoPendingDecisionError(Exception):
    """Raised by :func:`resolve_pending_decision_id` when no decision is pending."""


class AmbiguousPendingDecisionError(Exception):
    """Raised by :func:`resolve_pending_decision_id` when more than one decision
    is pending -- ``pending_ids`` carries the sorted candidate ids so a
    caller can surface them without re-reading the snapshot itself."""

    def __init__(self, pending_ids: list[str]) -> None:
        self.pending_ids = pending_ids
        super().__init__(f"Multiple pending decisions ({', '.join(pending_ids)}). Use --decision-id to specify which one.")


def resolve_pending_decision_id(run_dir: Path, decision_id: str | None) -> str:
    """Resolve an ``--answer``-flow ``decision_id``, auto-resolving from the
    run snapshot's pending decisions when omitted (PR-BOUNDARY-001).

    Concentrates the zero/one/many pending-decision auto-resolve branch that
    ``next_cmd.py``'s ``_handle_answer`` and orchestrator-api's
    ``answer_decision`` each independently reimplemented verbatim before
    this extraction -- exactly the "seam one WP invented and the next WP
    ignored" class the operator ruling (SPEC-FRESH2-001) exists to close.
    Reads via ``runtime_bridge_engine._read_snapshot`` (the FR-013
    concentration seam), never ``_internal_runtime.engine`` directly, so
    this is the ONLY place under either caller that touches the pending
    snapshot for auto-resolve purposes.

    Returns ``decision_id`` unchanged when it is already provided (a no-op
    pass-through, so callers can call this unconditionally).
    """
    if decision_id is not None:
        return decision_id

    from runtime.next.runtime_bridge_engine import _read_snapshot

    snapshot = _read_snapshot(run_dir)
    pending = snapshot.pending_decisions
    if len(pending) == 0:
        raise NoPendingDecisionError("No pending decisions to answer")
    if len(pending) == 1:
        return next(iter(pending.keys()))
    raise AmbiguousPendingDecisionError(sorted(pending.keys()))


def _store_root(repo_root_path: Path, owned: OwnedCheckout | None) -> Path:
    """Root discipline: the lifecycle record store lives at the owned
    checkout P for an owned mission (where it lives today), else at the
    caller's root."""
    return owned.owned_root if owned is not None else repo_root_path


def pair_previous_lifecycle_record(
    agent: str,
    mission_slug: str,
    result: str,
    repo_root: object,
    *,
    owned: OwnedCheckout | None = None,
) -> None:
    """Write the paired ``completed`` / ``failed`` record for the prior issuance.

    Matches the most recent unpaired ``started`` for ``(agent, mission_id)``
    in the local lifecycle store and appends a partner record carrying the
    SAME ``canonical_action_id``. The id is propagated, never re-computed
    (FR-011 / contract: "no rewriting at completion time").

    Best-effort: a missing meta.json or empty store is silently a no-op so
    new missions / first issuance behave naturally.
    """
    from specify_cli.invocation.lifecycle import (
        find_latest_unpaired_started,
        read_lifecycle_records,
        write_paired_completion,
    )
    from specify_cli.invocation.record import ProfileInvocationPhase
    from specify_cli.mission_metadata import resolve_mission_identity

    repo_root_path = Path(str(repo_root)) if not isinstance(repo_root, Path) else repo_root
    # FR-004 (#2186): the lifecycle ``mission_id`` MUST be read from the PRIMARY
    # checkout. ``resolve_feature_dir_for_mission`` is topology-aware and selects
    # the STATUS-only ``-coord`` husk once one exists — which carries no meta.json
    # (a wrong-leg read raises or, with a stale husk meta, returns the wrong id).
    # Anchor identity on the topology-blind PRIMARY dir (handle folded first so a
    # bare mid8 / human slug resolves the durable ``<slug>-<mid8>`` home; an
    # ambiguous handle RAISES — no silent pick, C-003).
    # read-side-seam-primary-primitive-closure-01KYKMMT WP06 (T029): routed off
    # the retiring ``primary_feature_dir_for_mission`` wrapper onto the seam
    # directly — PRIMARY_METADATA, since the read is meta.json's ``mission_id``.
    # WP08 (T036): dropped the caller-side canonicalizer fold — redundant with
    # the seam's own internal fold for a PRIMARY-partition kind.
    try:
        # PRIMARY dir only: the fact's own mission dir (no coordination surface consulted).
        feature_dir = (
            owned.mission_dir if owned is not None else mission_context_for(repo_root_path, mission_slug).artifact(MissionArtifactKind.PRIMARY_METADATA).read_dir
        )
    except Exception:
        return

    try:
        identity = resolve_mission_identity(feature_dir)
    except (FileNotFoundError, ValueError, TypeError, MissionMetaReadError):
        # MissionMetaReadError (landing-fold, PR #3155): resolve_mission_identity
        # now routes through load_meta_fail_closed, so a corrupt meta.json
        # raises the typed error here instead of a raw ValueError -- this
        # observability-only lookup must degrade the same way either case.
        return
    # #2278: the lifecycle pairing key is a ``mission_id`` field — it MUST be a
    # canonical ULID, never a slug (same fail-closed contract as #2138/FR-004).
    # A legacy mission without a minted ``mission_id`` skips the observability
    # pairing rather than persisting a slug into a ULID-typed field. The
    # ``started`` write fails closed identically, so the two stay symmetric.
    mission_id = identity.mission_id
    if mission_id is None:
        return

    records = read_lifecycle_records(_store_root(repo_root_path, owned))
    started = find_latest_unpaired_started(
        records,
        agent=agent,
        mission_id=mission_id,
    )
    if started is None:
        return

    if result == "success":
        phase: ProfileInvocationPhase = "completed"
        reason: str | None = None
    else:
        phase = "failed"
        reason = result  # "failed" or "blocked" — preserves caller intent

    write_paired_completion(
        _store_root(repo_root_path, owned),
        started=started,
        phase=phase,
        reason=reason,
    )


def write_issuance_lifecycle_record(
    agent: str,
    mission_slug: str,
    repo_root: object,
    decision: object,
    *,
    owned: OwnedCheckout | None = None,
) -> None:
    """Write a ``started`` lifecycle record for the action just issued.

    The canonical action id is ``f"{decision.mission_state}::{decision.action}"``
    — the mission step + action that the runtime actually issued. This
    value is read once here and never re-derived at completion time.

    No-op when the decision did not issue a public action (e.g. terminal,
    blocked, decision_required). Failures to write are swallowed: the
    lifecycle log is observability, not a hard runtime dependency.
    """
    from specify_cli.invocation.lifecycle import (
        make_canonical_action_id,
        write_started,
    )
    from specify_cli.mission_metadata import resolve_mission_identity

    action = getattr(decision, "action", None)
    mission_state = getattr(decision, "mission_state", None)
    kind = getattr(decision, "kind", None)
    if not action or not mission_state or kind != "step":
        return

    repo_root_path = Path(str(repo_root)) if not isinstance(repo_root, Path) else repo_root
    # FR-004 (#2186): same PRIMARY anchoring as the completion pairing above — the
    # ``started`` lifecycle record's ``mission_id`` must come from the PRIMARY
    # meta.json, never the coord husk (which lacks it or carries a stale id).
    # read-side-seam-primary-primitive-closure-01KYKMMT WP06 (T029): routed off
    # the retiring ``primary_feature_dir_for_mission`` wrapper onto the seam
    # directly — PRIMARY_METADATA, since the read is meta.json's ``mission_id``.
    # WP08 (T036): dropped the caller-side canonicalizer fold — redundant with
    # the seam's own internal fold for a PRIMARY-partition kind.
    try:
        # PRIMARY dir only: the fact's own mission dir (no coordination surface consulted).
        feature_dir = (
            owned.mission_dir if owned is not None else mission_context_for(repo_root_path, mission_slug).artifact(MissionArtifactKind.PRIMARY_METADATA).read_dir
        )
    except Exception:
        return

    try:
        identity = resolve_mission_identity(feature_dir)
    except (FileNotFoundError, ValueError, TypeError, MissionMetaReadError):
        # MissionMetaReadError (landing-fold, PR #3155): resolve_mission_identity
        # now routes through load_meta_fail_closed, so a corrupt meta.json
        # raises the typed error here instead of a raw ValueError -- this
        # observability-only lookup must degrade the same way either case.
        return
    # #2278: symmetric with the completion-pairing site above — the ``started``
    # record's ``mission_id`` field MUST be a canonical ULID, never a slug
    # (#2138/FR-004 fail-closed contract). Skip the observability record for a
    # legacy mission with no minted ``mission_id`` rather than persisting a slug.
    mission_id = identity.mission_id
    if mission_id is None:
        return

    try:
        canonical_id = make_canonical_action_id(mission_state, action)
    except ValueError:
        return

    try:
        write_started(
            _store_root(repo_root_path, owned),
            canonical_action_id=canonical_id,
            agent=agent,
            mission_id=mission_id,
            wp_id=getattr(decision, "wp_id", None),
        )
    except OSError:
        # Lifecycle log is observability; failures must not break `next`.
        return


def emit_mission_next_invoked(
    agent: str,
    result: str,
    mission_slug: str,
    repo_root: object,
    decision: object,
    *,
    owned: OwnedCheckout | None = None,
) -> None:
    """Append a ``MissionNextInvoked`` event to the mission event log.

    Best-effort: an unresolvable ``feature_dir`` degrades to an
    ``emit_event`` call with ``feature_dir=None`` (debug-logged only, never
    persisted) rather than raising — this observability write must never
    break ``next`` itself.
    """
    from specify_cli.mission_v1.events import emit_event

    # WP09/FR-001 (kind-correct): ``mission-events.jsonl`` is a legacy
    # append-only per-mission event log, the same coord-aware STATUS-namespace
    # shape as ``status.events.jsonl`` — route it through the seam on
    # ``STATUS_STATE`` rather than the kind-blind resolver (NFR-001).
    repo_root_path = Path(str(repo_root)) if not isinstance(repo_root, Path) else repo_root

    try:
        feature_dir = (
            mission_context_for(repo_root_path, mission_slug, owned=owned, tolerate_unmaterialized_coord=True).artifact(MissionArtifactKind.STATUS_STATE).read_dir
        )
    except Exception:
        feature_dir = None
    # ``decision`` is typed ``object`` (this WP's pinned target signature) so
    # calling code need not import ``Decision`` — narrow to ``Any`` once here
    # for plain attribute access (identical at runtime to the original
    # dotted-attribute reads: raises the same ``AttributeError`` if a field
    # were ever truly absent, which never happens for a real ``Decision``).
    decision_fields = cast(Any, decision)
    emit_event(
        "MissionNextInvoked",
        {
            "agent": agent,
            "result_input": result,
            "decision_kind": decision_fields.kind,
            "action": decision_fields.action,
            "wp_id": decision_fields.wp_id,
            "mission_state": decision_fields.mission_state,
        },
        mission_name=decision_fields.mission,
        feature_dir=feature_dir if feature_dir is not None and feature_dir.is_dir() else None,
    )
