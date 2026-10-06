"""Composition-dispatch seam for ``runtime.next.runtime_bridge`` (#2531 WP08).

**Sole home of the composition-dispatch cluster** (mission
``software-dev-composition-rewrite-01KQ26CY``): the dispatch entry
(:func:`_dispatch_via_composition`), the composed-action guard
(:func:`_check_composed_action_guard`), the composition-input resolution
helpers (:func:`_composition_dispatch_inputs` / :func:`_resolve_step_agent_profile`
/ :func:`_resolve_runtime_contract_for_step` / :func:`_resolve_step_binding`),
the research/documentation guard-fact readers
(:func:`_count_source_documented_events` / :func:`_publication_approved` /
:func:`_has_generated_docs`), and — the FR-008 headline — the
**`_should_dispatch_via_composition` selection seam** isolated as a clean,
directly-callable predicate with a stable signature.

FR-008 / C-005 (load-bearing): :func:`_should_dispatch_via_composition` imports
**no gates (#2535) code** and pulls in **no** ``resolve_gates`` dependency.
The inversion that will route through this seam is gates mission #2535's own
WP14, landing *after* this mission — this WP leaves the seam clean; it does
not wire it.

``advance_run_state_after_composition`` is explicitly OUT of scope for this
move: its logic lives in the engine seam
(``runtime_bridge_engine.advance_run_state_after_composition``), which the
bridge calls directly.

``runtime_bridge.py`` no longer carries a forwarder for any name in this
cluster (#2561): the bridge reaches them as ``_composition.<name>``, and a
test that wants to replace one patches THIS module. Every caller inside
``runtime.next`` looks the name up here, so one patch intercepts all of them.

The cluster's internal calls are plain intra-module calls:
``_should_dispatch_via_composition`` / ``_resolve_step_binding`` /
``_resolve_runtime_contract_for_step`` call
``_normalize_action_for_composition``; ``_composition_dispatch_inputs`` calls
``_resolve_step_agent_profile`` / ``_resolve_runtime_contract_for_step``;
``_dispatch_via_composition`` calls ``_check_composed_action_guard``.
``runtime_bridge_io`` reaches ``_resolve_step_agent_profile``,
``_count_source_documented_events`` and ``_publication_approved`` through a
deferred import of this module (this module imports ``runtime_bridge_io`` at
top level, so a top-level import back would be circular).

This module never reads a name off ``runtime_bridge`` (#2560):
``_check_composed_action_guard`` calls ``_should_advance_wp_step`` on
``runtime_bridge_guards``, which sits below this module.

Import DAG (research.md §Import DAG): this module may import
``runtime_bridge_io`` / ``runtime_bridge_engine`` / ``runtime_bridge_cores``;
it must never be imported BY ``runtime_bridge_cores`` (C-007).
"""

from __future__ import annotations

import dataclasses
import json
import logging
from pathlib import Path
from typing import Any

from mission_runtime import OwnedCheckout

from runtime.next import runtime_bridge_cores as _cores
from runtime.next import runtime_bridge_engine as _engine_adapter
from runtime.next import runtime_bridge_guards as _guards
from runtime.next import runtime_bridge_io as _io_seam


# Hardcoded (not ``__name__``) is deliberate: before #2531 WP08 moved this
# cluster out of ``runtime_bridge.py``, its INFO/exception logging carried the
# ``runtime.next.runtime_bridge`` logger identity. Operator triage tooling and
# ``tests/specify_cli/next/test_runtime_bridge_composition.py`` (FR-008) key
# off that exact logger name; letting it drift to
# ``runtime.next.runtime_bridge_composition`` via ``__name__`` silently breaks
# both, since a differently-named logger's effective level is not raised by
# ``caplog.at_level(logging.INFO, logger="runtime.next.runtime_bridge")``.
logger = logging.getLogger("runtime.next.runtime_bridge")

# Duplicated from runtime_bridge.py (same precedent as runtime_bridge_io.py's
# own KITTIFY_DIR — see that module's docstring): a top-level import of the
# residual would be circular, and it is a plain constant, so redefining it
# here is safe and matches the established WP05 pattern.
KITTIFY_DIR = ".kittify"

# ---------------------------------------------------------------------------
# Composition dispatch (WP02 / mission software-dev-composition-rewrite-01KQ26CY)
# ---------------------------------------------------------------------------
#
# These helpers route the live runtime path for the built-in ``software-dev``
# mission's five public actions (``specify``, ``plan``, ``tasks``,
# ``implement``, ``review``) through ``StepContractExecutor.execute`` instead
# of the legacy mission-runtime.yaml DAG step handlers. All other missions and
# step IDs continue to fall through to the runtime planner path unchanged
# (constraint C-008).
#
# Constraints active here:
#   - C-001: the composition path MUST go through ``StepContractExecutor``;
#     never call ``ProfileInvocationExecutor`` directly.
#   - C-002: composition produces invocation payloads; this bridge does NOT
#     generate text or call models.
#   - C-003 / FR-007: any lane-state writes inside composed steps go through
#     ``emit_status_transition`` -- this bridge writes no raw lane strings.
#   - C-008: dispatch is gated on ``action_sequence`` membership for the
#     resolved mission type -- any mission type, not just ``software-dev``
#     -- via ``_should_dispatch_via_composition``.

# Legacy run snapshots and project-local templates may still contain the old
# tasks substep IDs. Normalize them into the single public ``tasks`` action so
# existing in-flight missions can advance through the composition path.
_LEGACY_TASKS_STEP_IDS: frozenset[str] = frozenset({"tasks_outline", "tasks_packages", "tasks_finalize"})


def _normalize_action_for_composition(step_id: str) -> str:
    """Map a legacy DAG step ID to its composed action ID.

    The legacy ``mission-runtime.yaml`` splits ``tasks`` into three steps;
    the composition layer exposes a single ``tasks`` action whose contract
    holds the substructure internally. All other step IDs pass through
    unchanged.
    """
    if step_id in _LEGACY_TASKS_STEP_IDS:
        return "tasks"
    return step_id


def _should_dispatch_via_composition(
    mission: str,
    step_id: str,
    *,
    run_dir: Path | None = None,
    repo_root: Path | None = None,
) -> bool:
    """Return True iff ``(mission, step_id)`` routes through composition.

    **FR-008 selection seam** — this is the clean, testable, gates-#2535-free
    predicate a future consumer (gates mission WP14) can route through
    without this mission coupling to it. Order is critical and load-bearing:

    1. **Live charter lookup** (FR-007 / FR-008): calls
       ``charter.resolve_mission_type_context(repo_root, mission_type=mission)``
       to obtain the action sequence from the resolved mission-type bundle.  When
       ``repo_root`` is ``None`` (e.g., the very first ``decide_next`` call
       before a run is started), fall through directly to the custom widening
       path below without a charter lookup.
    2. **Custom mission widening** (Phase 6 / R-005): consulted only when
       ``run_dir`` is provided AND the charter lookup did not already return
       ``True``. The active step's explicit binding is read from the frozen
       template; a non-empty ``agent_profile`` OR ``contract_ref`` triggers
       composition. Empty / missing bindings fall through to the legacy DAG
       handler unchanged.
    """
    # Live charter lookup path (FR-007 / FR-008).  ``repo_root`` is required;
    # without it skip directly to the custom widening path.
    if repo_root is not None:
        try:
            from charter.activation.mission_type_profiles import (  # noqa: PLC0415
                resolve_mission_type_context,
            )

            action_sequence = resolve_mission_type_context(repo_root, mission_type=mission).action_sequence
            if _normalize_action_for_composition(step_id) in action_sequence:
                return True
        except Exception:
            # Degrade gracefully: if charter is unavailable or the mission type
            # is unknown, fall through to the custom widening path below so
            # in-flight missions are not broken.
            pass

    # Custom mission widening (R-005). ``run_dir`` is required to read the
    # frozen template; without it (e.g., on the very first decide_next call
    # before the run is started), fall through to the legacy DAG handler.
    if run_dir is None:
        return False
    profile, contract_ref = _resolve_step_binding(run_dir, step_id)
    return bool(profile or contract_ref)  # treat empty strings as falsy


def _resolve_step_binding(run_dir: Path, step_id: str) -> tuple[str | None, str | None]:
    """Return ``(agent_profile, contract_ref)`` for ``step_id`` in the frozen template.

    Missing templates, missing steps, and empty strings all resolve to
    ``None`` values so callers fail closed through the legacy path or the
    executor's structured error surface.

    Owned by this seam; a test that replaces it patches it here
    (``_should_dispatch_via_composition`` looks it up on this module).
    """
    try:
        template = _engine_adapter._load_frozen_template(run_dir)
    except Exception:
        return None, None

    normalized = _normalize_action_for_composition(step_id)
    for step in template.steps:
        if step.id == step_id or step.id == normalized:
            profile = step.agent_profile.strip() if step.agent_profile else None
            contract_ref = step.contract_ref.strip() if step.contract_ref else None
            return profile or None, contract_ref or None
    return None, None


def _resolve_step_agent_profile(run_dir: Path, step_id: str) -> str | None:
    """Return the ``agent_profile`` set on ``step_id`` in the frozen template.

    Returns ``None`` when:

    - ``run_dir`` lacks a frozen template (e.g., the run has not been started
      yet, or template load otherwise raises).
    - The step is not present in the template.
    - The step's ``agent_profile`` is ``None`` or an empty string (treated as
      falsy so the gate widens only for explicit author opt-in).

    The lookup tolerates legacy ``tasks_outline`` / ``tasks_packages`` /
    ``tasks_finalize`` substep IDs by normalizing through
    ``_normalize_action_for_composition``.
    """
    profile, _contract_ref = _resolve_step_binding(run_dir, step_id)
    return profile


def _resolve_runtime_contract_for_step(
    *,
    repo_root: Path,
    run_dir: Path,
    mission: str,
    step_id: str,
) -> Any | None:
    """Resolve a custom step contract from durable frozen-template state.

    ``mission run`` and ``next`` normally execute in separate CLI processes,
    so the process-local registry populated by ``mission run`` cannot be the
    only handoff for synthesized contracts.
    """
    try:
        from charter.drg import resolve_org_dirs
        from charter.offering.missions.step_contracts import (
            MissionStepContractRepository,
        )
        from specify_cli.mission_loader.contract_synthesis import synthesize_contracts
        from specify_cli.mission_loader.registry import lookup_contract

        template = _engine_adapter._load_frozen_template(run_dir)
    except Exception:
        return None

    normalized = _normalize_action_for_composition(step_id)
    for step in template.steps:
        if step.id != step_id and step.id != normalized:
            continue
        contract_ref = step.contract_ref.strip() if step.contract_ref else None
        if contract_ref:
            repository = MissionStepContractRepository(
                project_dir=repo_root / KITTIFY_DIR / "doctrine" / "mission_step_contracts",
                org_dirs=resolve_org_dirs(repo_root, "mission_step_contracts"),
            )
            return lookup_contract(contract_ref, repository)
        profile = step.agent_profile.strip() if step.agent_profile else None
        if profile:
            contract_id = f"custom:{mission}:{normalized}"
            for contract in synthesize_contracts(template):
                if contract.id == contract_id:
                    return contract
        return None
    return None


def _composition_dispatch_inputs(
    *,
    repo_root: Path,
    run_dir: Path,
    mission: str,
    step_id: str,
    action: str,
) -> tuple[str | None, Any | None]:
    """Return ``(profile_hint, contract)`` for a composition dispatch.

    Resolves via ``_resolve_step_agent_profile`` / ``PromptStep.
    agent_profile`` — the FR-008-mandated canonical resolution path
    (``mission_step_contracts/executor.py:68-71``) — including when
    ``action`` is a member of the mission type's own ``action_sequence``,
    which is the common case for every canonical step of every mission
    type. A ``resolve_mission_type_context`` probe still runs first so a
    genuine resolution failure (e.g. a malformed org pack) is logged rather
    than silently swallowed (FR-002); its result is otherwise unused here —
    it no longer gates whether profile/contract resolution runs (FR-001/
    FR-003).

    **Built-ins-only exception (PR #797, FR-003, #3830 regression fix):**
    when ``(mission, action)`` has an entry in ``StepContractExecutor``'s
    ``_ACTION_PROFILE_DEFAULTS`` table — i.e. this is a canonical
    ``software-dev`` / ``research`` / ``documentation`` action — the
    template-side ``agent_profile`` is NOT consulted and ``profile_hint``
    resolves to ``None`` unconditionally, so the executor's own
    ``_resolve_profile_hint`` falls back to that built-ins-only table
    exactly as it did before this mission (NFR-001). This preserves PR
    #797's fast path: a frozen template that happens to carry a stray
    ``agent_profile`` value on a built-in step (e.g. through gate-widening
    test scaffolding, or an operator hand-edit) must never override the
    documented built-in resolution. Custom mission types are never members
    of that table, so this exception never narrows FR-001's guarantee that
    a custom type's own action reaches ``PromptStep.agent_profile``.

    Owned by this seam; the bridge calls it as
    ``_composition._composition_dispatch_inputs(...)``, so a test that
    replaces it patches it here.

    """
    try:
        from charter.activation.mission_type_profiles import (  # noqa: PLC0415
            UnknownMissionTypeError,
            resolve_mission_type_context,
        )

        resolve_mission_type_context(repo_root, mission_type=mission)
    except UnknownMissionTypeError:
        # Expected on the happy path: any non-charter-activated custom
        # mission type raises this (the normal #3830 frozen-template path),
        # so it is not a genuine resolution failure and must not be logged
        # at ERROR (that would fire on every dispatch for a custom type).
        # Debug-only so it is still diagnosable on demand.
        logger.debug(
            "mission type %r is not charter-activated; profile_hint resolves via the frozen-template path",
            mission,
        )
    except Exception:
        # Genuine resolution failure (e.g. a malformed org pack) — logged so
        # it is diagnosable, distinguished from the ordinary success case
        # (which logs nothing, NFR-001) by log presence, not conflated with
        # it. Resolution below still proceeds via the frozen-template
        # fallback path; a mission-type-context failure here is not fatal to
        # dispatch.
        logger.exception(
            "resolve_mission_type_context failed for mission=%r action=%r; profile_hint resolution continues via the frozen-template path",
            mission,
            action,
        )

    from specify_cli.mission_step_contracts.executor import (  # noqa: PLC0415
        _ACTION_PROFILE_DEFAULTS,
    )

    profile_hint = None if (mission, action) in _ACTION_PROFILE_DEFAULTS else _resolve_step_agent_profile(run_dir, step_id)
    return (
        profile_hint,
        _resolve_runtime_contract_for_step(
            repo_root=repo_root,
            run_dir=run_dir,
            mission=mission,
            step_id=step_id,
        ),
    )


def _count_source_documented_events(feature_dir: Path) -> int:
    """Return the number of ``source_documented`` events in the mission event log.

    Mirrors the v1 ``event_count`` guard primitive (see
    ``src/specify_cli/mission_v1/guards.py``): reads
    ``feature_dir / "mission-events.jsonl"``, treats each line as a JSON
    record, and counts those whose ``type`` equals ``"source_documented"``.

    Missing or unreadable logs return ``0`` so the guard fails closed at the
    research ``gathering`` branch.
    """
    log_path = feature_dir / "mission-events.jsonl"
    if not log_path.is_file():
        return 0
    count = 0
    try:
        for raw_line in log_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(entry, dict) and entry.get("type") == "source_documented":
                count += 1
    except OSError:
        return 0
    return count


def _publication_approved(feature_dir: Path) -> bool:
    """Return True iff the mission event log carries a ``publication_approved`` gate event.

    Mirrors the v1 ``gate_passed`` guard primitive: a gate event is recorded
    as ``{"type": "gate_passed", "name": "<gate_name>"}`` in
    ``feature_dir / "mission-events.jsonl"``. Missing or unreadable logs
    return ``False`` so the research ``output`` guard fails closed.

    This signal was chosen because the research mission's existing v1
    ``mission.yaml`` declares the same surface
    (``gate_passed("publication_approved")``) for both the source-side gate
    check and the publication-approval gate. Keeping the runtime bridge's
    guard reading from the same JSONL the v1 guard primitives consume
    avoids forking the gate-event surface during the v2 composition
    rewrite.
    """
    log_path = feature_dir / "mission-events.jsonl"
    if not log_path.is_file():
        return False
    try:
        for raw_line in log_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(entry, dict) and entry.get("type") == "gate_passed" and entry.get("name") == "publication_approved":
                return True
    except OSError:
        return False
    return False


def _has_generated_docs(feature_dir: Path) -> bool:
    """Return True iff at least one *.md file exists under feature_dir / 'docs'.

    Used by the documentation `generate` guard branch (D6 of plan.md).
    ``runtime_bridge_io.gather_artifact_presence`` reaches it directly from
    this seam.
    """
    docs_root = feature_dir / "docs"
    if not docs_root.is_dir():
        return False
    return next(docs_root.rglob("*.md"), None) is not None


def _check_composed_action_guard(
    action: str,
    feature_dir: Path,
    *,
    mission: str = "software-dev",
    legacy_step_id: str | None = None,
    repo_root: Path | None = None,
    owned: OwnedCheckout | None = None,
) -> list[str]:
    """Evaluate the post-composition guard for a composed action.

    Forwards to :func:`runtime_bridge_cores.evaluate_guards_strict` over a
    :func:`runtime_bridge_io.gather_artifact_presence` snapshot (#2531 WP06,
    T022; relocated here #2531 WP08). On this tolerant composed extension path
    an :class:`~runtime_bridge_cores.UnregisteredMissionFamilyError` is caught,
    logged at WARNING, and degraded to an explicit neutral (empty) result —
    matching the legacy CLI path (``_check_cli_guards``), which also catches
    and logs it at WARNING before degrading to an empty result.

    Mirrors ``_check_cli_guards`` semantics for the composed actions.

    The ``mission`` keyword-only parameter selects the guard branch family:

    * ``mission="software-dev"`` (default) routes through the original
      software-dev guard chain (``specify`` / ``plan`` / ``tasks`` /
      ``implement`` / ``review``).
    * ``mission="research"`` routes through the research guard chain
      (``scoping`` / ``methodology`` / ``gathering`` / ``synthesis`` /
      ``output``) plus a **fail-closed default** for any unknown research
      action — closing the v1 P1 silent-pass finding where unknown actions
      fell through with empty failures.

    For ``tasks``, the assertion shape depends on which surface invoked us:

    * **Legacy DAG path** (``legacy_step_id`` is ``"tasks_outline"`` /
      ``"tasks_packages"`` / ``"tasks_finalize"``): the runtime engine fires
      the bridge **once per substep**, so the guard must reflect the artifact
      state the user is **expected** to have produced **at that substep**, not
      the terminal post-finalize state. Demanding the terminal state on
      ``tasks_outline`` blocks the user with "Required: at least one
      tasks/WP*.md file" while the surfaced retry action is still
      ``tasks-outline`` — an unsatisfiable loop. (Mission-review follow-up to
      the original WP02 collapsed guard, which conflated dispatch
      normalization with guard semantics.)

    * **Composition-only path** (``legacy_step_id`` is ``None``): a direct
      ``action="tasks"`` invocation represents the terminal state of the
      whole composed action; the guard demands the **union** of all three
      legacy substep checks (no weakening).

    ``repo_root`` (#3704 WP03, FR-003) is forwarded to
    :func:`runtime_bridge_io.gather_artifact_presence` for org-tier
    ``expected-artifacts.yaml`` resolution (#3704 WP02, FR-008); defaults to
    ``None`` (built-in tree only — today's exact behavior for every existing
    caller that does not yet pass a real ``repo_root``).

    Returns a list of failure descriptions; an empty list means all guards
    pass.
    """
    snapshot = _io_seam.gather_artifact_presence(
        feature_dir,
        mission_family=mission,
        step_id=action,
        legacy_step_id=legacy_step_id,
        repo_root=repo_root,
        owned=owned,
    )
    if mission == "software-dev" and action in ("implement", "review"):
        # _should_advance_wp_step is owned by runtime_bridge_guards (#2560); a
        # test patches it there.
        # Intentionally NOT anchored (no repo_root=/mission_slug= forwarded), even
        # though repo_root is in scope above for gather_artifact_presence: this
        # composed-guard path (_dn_composition_dispatch, phase 3 of
        # decide_next_via_runtime) runs only when _dn_dependency_gate (phase 2)
        # returned None -- i.e. only AFTER that phase's own anchored
        # _should_advance_wp_step call (repo_root=repo_root, mission_slug=
        # mission_slug) already ran for the identical (action, feature_dir) and did
        # not block (#3884 INT-001). Do not "fix" this by anchoring it here; a
        # future reorder of decide_next_via_runtime's phase tuple that lets this be
        # reached with WPs still pending would need a repo_root=/mission_slug=
        # forward of its own, mirroring _dn_dependency_gate's call.
        snapshot = dataclasses.replace(snapshot, wp_advance_ready=_guards._should_advance_wp_step(action, feature_dir))
    try:
        return _cores.evaluate_guards_strict(snapshot)
    # #3412 (FR-009/FR-010): NEVER widen this to also catch MalformedManifestError -- that would re-launder a malformed manifest into a tolerant empty result.
    except _cores.UnregisteredMissionFamilyError:
        logger.warning(
            "Unregistered mission_family %r reached the composed guard path; returning a neutral (empty) guard result.",
            mission,
        )
        return []


def _dispatch_via_composition(
    *,
    repo_root: Path,
    mission: str,
    action: str,
    actor: str,
    profile_hint: str | None,
    request_text: str | None,
    mode_of_work: Any | None,
    feature_dir: Path,
    legacy_step_id: str | None = None,
    contract: Any | None = None,
    owned: OwnedCheckout | None = None,
) -> list[str] | None:
    """Run a composed action via ``StepContractExecutor``; then guard.

    Returns:
      - ``None`` on success (composition succeeded AND post-action guard
        passed). On the live ``decide_next_via_runtime`` path the caller then
        invokes :func:`runtime_bridge_engine.advance_run_state_after_composition` to progress run
        state without entering the legacy DAG dispatch handler
        (single-dispatch, FR-001/FR-002).
      - A non-empty list of failure descriptions if the executor raised
        ``StepContractExecutionError`` (FR-009: structured CLI surface, not a
        Python traceback) or the post-action guard failed. The caller turns
        this into a ``Decision`` with ``guard_failures`` populated.

    Constraint C-001 is preserved: this function only ever invokes
    ``StepContractExecutor.execute``; it never touches
    ``ProfileInvocationExecutor`` directly.

    The follow-up advancement is performed by
    :func:`runtime_bridge_engine.advance_run_state_after_composition`, which reuses the same
    primitives ``runtime_next_step(...)`` uses internally for state, lane,
    and prompt progression. The legacy ``runtime_next_step`` is **not**
    called for composition-backed actions (FR-001).
    """
    # Local import keeps module load lean and avoids circular import risk.
    from specify_cli.mission_step_contracts.executor import (
        StepContractExecutionContext,
        StepContractExecutionError,
        StepContractExecutor,
    )

    context = StepContractExecutionContext(
        repo_root=repo_root,
        mission=mission,
        action=action,
        actor=actor or "unknown",
        profile_hint=profile_hint,
        request_text=request_text,
        mode_of_work=mode_of_work,
    )
    # The in-process ``RuntimeContractRegistry`` is the canonical runtime
    # source for custom step contracts (explicitly registered by ``mission
    # run`` / test setup), so a hit there takes priority over ``contract``
    # — a contract this bridge may have locally re-synthesized from the
    # frozen template via ``_resolve_runtime_contract_for_step`` (#3830
    # regression: that local synthesis produces its own object, distinct
    # from the one an operator/test explicitly registered under the same
    # id, and must never shadow it). The locally-resolved ``contract`` is
    # still the fallback for the cross-process case (``mission run`` and
    # ``next`` execute in separate CLI processes, so the registry is empty
    # in the ``next`` process even though the frozen template carries the
    # binding), and the executor's own repository lookup is the final
    # fallback for built-in software-dev dispatch.
    from specify_cli.mission_loader.registry import get_runtime_contract_registry

    selected_contract = get_runtime_contract_registry().lookup(f"custom:{mission}:{action}") or contract
    try:
        result = StepContractExecutor(repo_root=repo_root).execute(context, contract=selected_contract)
    except StepContractExecutionError as exc:
        # Structured CLI failure surface (FR-009) — caller turns this into a
        # Decision; no Python traceback escapes.
        return [f"composition failed for {mission}/{action}: {exc}"]
    except Exception as exc:  # noqa: BLE001 — FR-009 contract: any executor
        # exception class must surface as a structured CLI failure rather than
        # a Python traceback. The narrow ``StepContractExecutionError`` catch
        # above handles the documented executor failure mode; this widened
        # catch defends against contract drift (e.g., a future executor change
        # that raises ``ValueError`` from a malformed YAML, or a transient
        # ``OSError`` reading a contract file). The exception detail is logged
        # for operator triage; the structured surface preserves the FR-009 UX.
        logger.exception("unexpected exception in composition for %s/%s", mission, action)
        return [f"composition crashed for {mission}/{action}: {type(exc).__name__}: {exc}"]

    # FR-008: forward the invocation_id chain produced by the executor to the
    # bridge log so downstream event/trail writers and operators can correlate
    # the composed action with its underlying ProfileInvocationExecutor calls.
    # Defensive ``getattr`` + duck-typed length so test mocks (MagicMock) and
    # real ``StepContractExecutionResult`` instances both flow through cleanly.
    invocation_ids = getattr(result, "invocation_ids", ()) or ()
    try:
        invocation_count = len(invocation_ids)
    except TypeError:
        invocation_count = 0
    logger.info(
        "composed %s/%s emitted %d invocation(s): %s",
        mission,
        action,
        invocation_count,
        invocation_ids,
    )

    # FR-007: surface delegation candidates that were cited (``delegates_to``)
    # but did not resolve against the merged/activated DRG -- previously
    # computed by the executor and read by nothing. Non-blocking (WARNING,
    # never ERROR, D-005): a correctly-cited-but-activation-filtered candidate
    # is a valid, if inert, state, not necessarily an authoring mistake.
    # Defensive ``getattr`` for the same reason as ``invocation_ids`` above --
    # test mocks (MagicMock) and real ``StepContractExecutionResult``
    # instances both flow through cleanly.
    for step in getattr(result, "steps", ()) or ():
        unresolved = getattr(step, "unresolved_candidates", ())
        if unresolved:
            logger.warning(
                "step %s (contract %s) has unresolved delegation candidate(s): %s",
                getattr(step, "step_id", "<unknown>"),
                getattr(result, "contract_id", "<unknown>"),
                ", ".join(unresolved),
            )

    failures = _check_composed_action_guard(action, feature_dir, mission=mission, legacy_step_id=legacy_step_id, repo_root=repo_root, owned=owned)
    if failures:
        return failures
    return None
