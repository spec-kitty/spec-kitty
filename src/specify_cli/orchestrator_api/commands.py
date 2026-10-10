"""Machine-contract API commands for external orchestrators.

All commands emit a single JSON object to stdout via the canonical envelope.
Non-zero exit on any failure. Output is always JSON (no prose mode).

Error codes used:
  USAGE_ERROR                 -- CLI parse/usage error (missing required arg, bad option, etc.)
  POLICY_METADATA_REQUIRED    -- --policy missing on a run-affecting command
  POLICY_VALIDATION_FAILED    -- policy JSON invalid or contains secrets
  INVALID_MISSION             -- #2879: --mission value is not a safe path segment
                                 (traversal guard: '..', separators, leading dot,
                                 non-ASCII) — JSON envelope, never a raw traceback
  MISSION_NOT_FOUND           -- mission slug does not resolve to a kitty-specs dir
  STATUS_READ_PATH_NOT_FOUND  -- coord topology with a stale/unaddressable primary surface
                                 (fail-closed read-path guard fired; carries coord/primary candidates)
  WP_NOT_FOUND                -- WP ID does not exist in the mission
  TRANSITION_REJECTED         -- transition not allowed by state machine
  WP_ALREADY_CLAIMED          -- WP claimed by a different actor
  MISSION_NOT_READY           -- not all WPs approved/done (for accept-mission)
  HISTORY_COMMIT_FAILED       -- append-history could not create its commit
  PLACEMENT_RESOLUTION_REQUIRED -- append-history's write placement could not be
                                 resolved (D11 fail-closed; FR-004 -- never a
                                 silent current-branch fallback)
  SAFE_COMMIT_*               -- structured safe_commit refusal/failure
  PREFLIGHT_FAILED            -- preflight checks failed (for merge-mission)
  CONTRACT_VERSION_MISMATCH   -- provider version is below MIN_PROVIDER_VERSION
  UNSUPPORTED_STRATEGY        -- merge strategy not implemented
  ANCESTRY_NOT_ESTABLISHED    -- #3281/FR-007: the recorded planning commit or an
                                 approved dependency lane's tip is not (yet) a git
                                 ancestor of the claimed workspace's HEAD, even
                                 after self-heal re-ran the reuse-path merges
  MISSION_ALREADY_EXISTS      -- specify: the delegate mission-creation call
                                 failed with its own typed duplicate signal
                                 (MissionAlreadyExistsError, #3861)
  MISSION_CREATE_FAILED       -- specify: mission creation failed for a reason
                                 other than a typed duplicate signal (WP03)
  PLAN_SETUP_FAILED           -- plan: the delegate plan-scaffold call failed and
                                 carried no more specific error_code of its own (WP03);
                                 ALSO the envelope code when the delegate raised a
                                 typed but contract-unregistered code (e.g.
                                 SPEC_REQUIREMENT_IDS_INVALID, SPEC_FILE_MISSING,
                                 TEMPLATE_CONFIGURATION_ERROR, PLAN_CONTEXT_UNRESOLVED)
                                 -- the real code travels as data["reason"]
                                 (requirement-id-grammar-01M3NRCA WP05)
  TASKS_FINALIZE_FAILED       -- tasks: the delegate finalize-tasks call failed and
                                 carried no more specific error_code of its own (WP03)
  CHECK_PREREQUISITES_FAILED  -- check-prerequisites: the delegate validation call
                                 failed and carried no more specific error_code of
                                 its own (WP04)
  RECORD_ANALYSIS_EMPTY_BODY  -- record-analysis: --input-file/stdin body was empty
                                 (WP04)
  RECORD_ANALYSIS_INPUT_FILE_NOT_FOUND -- record-analysis: --input-file could not
                                 be read (WP04)
  RECORD_ANALYSIS_MALFORMED_CARRIER -- record-analysis: the submitted body carried
                                 a present-but-invalid analysis-findings/v1 carrier
                                 (WP04)
  RECORD_ANALYSIS_WRITE_NOT_CONFIRMED -- record-analysis: no analysis-report.md
                                 generated AFTER this call's start timestamp was
                                 found on disk -- the write did not happen (or could
                                 not be confirmed), regardless of the underlying
                                 call's own return/raise/hang behavior (NFR-004 /
                                 SK-93 / WP04)
  RECORD_ANALYSIS_VERDICT_UNRELIABLE -- record-analysis: a write WAS confirmed
                                 (fresh generated_at) but the re-read verdict is not
                                 a trustworthy match for this call -- either it
                                 diverges from the submitted verdict, or the
                                 submitted verdict was itself `unknown` (no valid
                                 carrier); `unknown` is NEVER reported as success
                                 (SK-06 / #3133 / WP04)
  DIRTY_WORKTREE               -- record-analysis: pre-existing uncommitted changes
                                 block the write (classified from the delegate
                                 preflight's own structured payload; WP04)
  INVALID_ORIGIN_FLOW          -- open-decision: FR-012 scope guard -- --origin is
                                 outside {charter, specify, plan}, rejected BEFORE
                                 the decisions/service.py layer is ever called (WP05)
  DECISION_MISSING_STEP_OR_SLOT -- open-decision: neither --step-id nor --slot-key
                                 supplied (propagated verbatim from
                                 decisions/service.py's DecisionError; WP05)
  DECISION_ALREADY_CLOSED      -- open-decision: a matching logical-key entry
                                 already exists in a terminal state (propagated
                                 verbatim from DecisionError; WP05)
  DECISION_NOT_FOUND           -- resolve/defer/cancel-decision: --decision-id is
                                 not present in the mission's ledger (propagated
                                 verbatim from DecisionError; WP05)
  DECISION_TERMINAL_CONFLICT   -- resolve/defer/cancel-decision: the decision is
                                 already terminal with a DIFFERENT outcome/payload
                                 than requested -- the terminal-transition rejection
                                 (propagated verbatim from DecisionError, same code
                                 the host-CLI ``decision_app`` subcommands raise for
                                 this case; WP05)
  DECISION_EVENT_REPAIR_FAILED -- open-decision (idempotent-open path): the missing
                                 DecisionPointOpened event could not be re-emitted
                                 (propagated verbatim from DecisionError; WP05)
  DESIGN_STATUS_EVENT_LOG_UNREADABLE -- design-status: status.events.jsonl could
                                 not be read cleanly (a torn/truncated line --
                                 ledger SK-131) while deriving the tasks/-finalized
                                 signal; NEVER silently reported as "not finalized"
                                 (WP06). ALSO emitted, verbatim, by open/resolve/
                                 defer/cancel-decision when decisions/index.json
                                 itself exists but is corrupt (malformed JSON,
                                 non-UTF-8, or schema-invalid) -- the SAME
                                 ``DecisionIndexReadError`` design-status already
                                 fails closed on (#4642), reused here rather than
                                 registering a second contract code for the
                                 identical failure shape (see
                                 ``_fail_decision_index_unreadable``).
  RESULT_REQUIRED              -- answer-decision: --result is required alongside
                                 --answer (WP08)
  INVALID_RESULT                -- answer-decision: --result is not one of the host
                                 CLI's {success, failed, blocked} enum
                                 (next_cmd.py:53,610-613), rejected BEFORE decision
                                 resolution/persistence -- mirrors the host CLI's
                                 own ``_validate_result_and_answer`` verbatim,
                                 including its call-sequence position
                                 (WP08-001 fold-in fix)
  NO_PENDING_DECISION          -- answer-decision: no run-snapshot pending_decisions
                                 entry exists to answer (WP08)
  AMBIGUOUS_PENDING_DECISION   -- answer-decision: more than one pending decision
                                 and --decision-id was omitted (WP08)
  DECISION_NOT_PENDING         -- answer-decision: --decision-id does not match any
                                 entry in the current run's pending_decisions (WP08)
"""

from __future__ import annotations

from collections.abc import Callable

import typer

from specify_cli.core.contract_gate import validate_outbound_payload
from specify_cli.status import wp_state_for
from specify_cli.status import Lane

from .envelope import (
    CONTRACT_VERSION,
    MIN_PROVIDER_VERSION,
    make_envelope,
)

import click
from typer import core as typer_core
from typer.core import TyperGroup

from . import _common
from ._common import (
    _HELP_MISSION_SLUG,
    _emit,
    _extract_wp_id,
    _fail,
    _planning_read_dir,
)
from . import consolidation
from . import decision_verbs
from . import design_phase
from . import design_authoring
from . import design_context
from . import design_status
from . import runtime_next
from . import wp_lifecycle


def _vendored_click_exception(name: str) -> type[BaseException] | None:
    """Return ``typer._click``'s exception class ``name``, or ``None`` if absent.

    Looks in the vendored ``exceptions`` submodule first, then the package
    root, and never touches an attribute it has not confirmed exists.
    """
    module = getattr(typer_core, "_click", None)
    if module is None:
        return None
    for holder in (getattr(module, "exceptions", None), module):
        candidate = getattr(holder, name, None) if holder is not None else None
        if isinstance(candidate, type) and issubclass(candidate, BaseException):
            return candidate
    return None


def _exception_classes(*candidates: type[BaseException] | None) -> tuple[type[BaseException], ...]:
    """Deduplicate ``candidates`` into an ``except``-clause tuple, dropping ``None``."""
    classes: list[type[BaseException]] = []
    for candidate in candidates:
        if candidate is not None and candidate not in classes:
            classes.append(candidate)
    return tuple(classes)


_CLICK_USAGE_ERRORS = _exception_classes(click.UsageError, _vendored_click_exception("UsageError"))  # noqa: TID251 — deliberately catches both click universes (standalone and typer-vendored)
_CLICK_ABORTS = _exception_classes(click.Abort, typer.Abort, _vendored_click_exception("Abort"))  # noqa: TID251 — deliberately catches both click universes (standalone and typer-vendored)
# ``typer.Exit`` is click's ``Exit`` on typer <= 0.25 and typer's own class on
# >= 0.26, so it covers the standalone-click spelling in both eras (TID251).
_EXIT = _exception_classes(typer.Exit, _vendored_click_exception("Exit"))


class _JSONErrorGroup(TyperGroup):
    """Click Group that guarantees JSON envelopes for all error paths.

    The orchestrator-api contract requires *every* stdout emission to be a
    single JSON envelope, including parser-level failures (missing required
    args, unknown options, etc.).  Three overrides cooperate to cover every
    dispatch path:

    ``make_context(info_name, args, parent, **extra)``
        Catches errors during *group-level argument parsing* when nested.
        When the parent group calls ``make_context()`` on this sub-group
        (e.g. ``orchestrator-api --bogus``), the error would otherwise
        propagate to the parent's ``BannerGroup``.  This is the outermost
        catch for the nested path.

    ``invoke(ctx)``
        Catches errors during *subcommand dispatch*.  When this group is
        registered as a sub-group of the root CLI via ``add_typer()``, Click
        dispatches through ``invoke()``, not ``main()``.  Without this
        override the root ``BannerGroup`` would format the error as prose.

    ``main(*args, **kwargs)``
        Catches errors during *direct invocation* and group-level argument
        parsing (e.g. ``orchestrator-api --unknown-flag``).  Uses
        ``standalone_mode=False`` so ``click.UsageError`` propagates as an
        exception rather than being printed as plain text.

    Interaction: when both paths are active (direct invocation), a subcommand
    error is caught by ``invoke()`` first, which calls ``ctx.exit(2)``
    (raising ``SystemExit(2)``).  ``main()`` passes ``SystemExit`` through
    via ``except SystemExit: raise``, so no double emission occurs.
    """

    def _emit_error(self, message: str) -> None:
        """Emit a USAGE_ERROR JSON envelope to stdout."""
        _emit(
            make_envelope(
                command="unknown",
                success=False,
                data={"message": message},
                error_code="USAGE_ERROR",
            )
        )

    def make_context(self, info_name, args, parent=None, **extra):
        """Catch group-level parse errors when nested (e.g. orchestrator-api --bogus).

        When nested as a sub-group, the parent's invoke() calls
        make_context() on this group to parse its own arguments.  Errors
        here would propagate to the parent's BannerGroup, producing prose.
        """
        try:
            return super().make_context(info_name, args, parent=parent, **extra)
        except _CLICK_USAGE_ERRORS as exc:
            self._emit_error(exc.format_message())
            raise SystemExit(2) from exc

    def invoke(self, ctx):
        """Catch errors during subcommand dispatch (nested invocation path).

        When this group is registered as a sub-group of the root CLI via
        add_typer(), Click dispatches to invoke(), not main(). This override
        ensures parse/usage errors produce JSON envelopes even when the root
        CLI's BannerGroup would otherwise emit prose.
        """
        try:
            return super().invoke(ctx)
        except _CLICK_USAGE_ERRORS as exc:
            self._emit_error(exc.format_message())
            ctx.exit(2)
        except _CLICK_ABORTS:
            self._emit_error("Command aborted")
            ctx.exit(2)

    def main(self, *args, standalone_mode: bool = True, **kwargs):  # type: ignore[override]
        try:
            rv = super().main(*args, standalone_mode=False, **kwargs)
            # With standalone_mode=False, typer.Exit(code) is caught by
            # Typer's _main() and returned as an integer.  Re-raise it so
            # that CliRunner (and real invocations) see the correct exit code.
            if isinstance(rv, int) and rv != 0:
                raise SystemExit(rv)
            return rv
        except _CLICK_USAGE_ERRORS as exc:
            self._emit_error(exc.format_message())
            raise SystemExit(2) from exc
        except _CLICK_ABORTS:
            self._emit_error("Command aborted")
            raise SystemExit(2)
        except _EXIT as exc:
            raise SystemExit(exc.exit_code) from exc
        except SystemExit:
            raise


# The public ``app`` used by the main CLI to register orchestrator-api.
# Uses _JSONErrorGroup so that Click/Typer parse errors become JSON envelopes.
app = typer.Typer(
    name="orchestrator-api",
    help="Machine-contract API for external orchestrators (JSON-first)",
    no_args_is_help=False,
    cls=_JSONErrorGroup,
)


# ── Command 1: contract-version ────────────────────────────────────────────


def _delivery_profile() -> dict[str, object]:
    """Describe actual local capabilities without claiming the Go wire contract."""
    from specify_cli.design import context, models

    return {
        "semantic_contract": "spec-kitty.orchestrator/2",
        "transport": f"spec-kitty.orchestrator-api/{CONTRACT_VERSION}",
        "full_go_conformance": False,
        "supported": [info.name for info in app.registered_commands if info.name is not None],
        "translated": {
            "CreateMission": "specify: native host-local Mission creation",
            "RecordMissionInterview": "interview-record: canonical decision slots, not aggregate revision CAS",
            "SubmitSpecification": "artifact-submit kind specification: exact-byte SHA-256 CAS",
            "SubmitPlan": "artifact-submit kind plan: accepted specification lineage",
            "SubmitDesignArtifact": "artifact-submit: registered bounded inline support content",
            "SubmitTasksOutline": "artifact-submit kind outline: canonical manifest validation",
            "SubmitWorkPackageDrafts": "artifact-submit kind work_package: declared prompt drafts",
            "ValidateMissionStage": "design-validate: read-only predicates, no durable report revision",
            "CompleteMissionStage": "next --result success: revalidate actually issued native stage",
            "FinalizeWorkPackages": "tasks: native planning pin/status bootstrap, not immutable Go generations",
        },
        "unavailable": [
            "GapDB",
            "leases",
            "fences",
            "runtime_epochs",
            "native_async",
            "watch",
            "durable_operation_replay",
            "immutable_work_revisions",
            "aggregate_revision_cas",
            "opaque_artifact_references",
            "remote_serving",
            "tracker_publication",
            "cross_clone_provenance",
        ],
        "limits": {
            "artifact_bytes": models.MAX_ARTIFACT_BYTES,
            "batch_bytes": models.MAX_BATCH_BYTES,
            "entries": models.MAX_ARTIFACTS,
            "request_json_bytes": models.MAX_REQUEST_BYTES,
            "artifact_actor_bytes": models.MAX_ACTOR_BYTES,
            "context_bytes": context.CONTEXT_BYTES,
            "interview_answer_bytes": context.ANSWER_BYTES,
            "interview_actor_bytes": context.ACTOR_BYTES,
        },
        "persistence": {
            "receipts": "trusted Git common-directory metadata; nonportable between clones",
            "locking": "cooperative API writers only",
            "commit_order": "files and Git commit precede receipt persistence; inspect partial-effect failures",
        },
    }


@app.command(name="contract-version")
def contract_version(
    provider_version: str = typer.Option(
        None,
        "--provider-version",
        help="Caller's provider version; returns CONTRACT_VERSION_MISMATCH if below minimum",
    ),
    require_capability: str | None = typer.Option(
        None,
        "--require-capability",
        help="Require a supported Python command before performing work",
    ),
) -> None:
    """Return the current API contract version.

    Pass --provider-version to check compatibility before running state-mutating commands.
    """
    cmd = "contract-version"

    if provider_version is not None:
        from packaging.version import Version, InvalidVersion

        try:
            if Version(provider_version) < Version(MIN_PROVIDER_VERSION):
                _fail(
                    cmd,
                    "CONTRACT_VERSION_MISMATCH",
                    f"Provider version {provider_version!r} is below minimum {MIN_PROVIDER_VERSION!r}",
                    {
                        "provider_version": provider_version,
                        "min_supported_provider_version": MIN_PROVIDER_VERSION,
                        "api_version": CONTRACT_VERSION,
                    },
                )
                return
        except InvalidVersion:
            _fail(
                cmd,
                "CONTRACT_VERSION_MISMATCH",
                f"Provider version {provider_version!r} is not a valid version string",
                {"provider_version": provider_version},
            )
            return

    if require_capability is not None and not any(info.name == require_capability for info in app.registered_commands):
        _fail(cmd, "UNSUPPORTED_CAPABILITY", "The Python delivery profile does not support this capability", {"capability": require_capability})
        return

    envelope = make_envelope(
        command=cmd,
        success=True,
        data={
            "api_version": CONTRACT_VERSION,
            "min_supported_provider_version": MIN_PROVIDER_VERSION,
            "delivery_profile": _delivery_profile(),
        },
    )
    _emit(envelope)


# ── Command 2: mission-state ────────────────────────────────────────────────


@app.command(name="mission-state")
def mission_state(
    mission: str = typer.Option(
        ...,
        "--mission",
        help=_HELP_MISSION_SLUG,
    ),
) -> None:
    """Return the full state of a mission (all WPs, lanes, dependencies)."""
    main_repo_root = _common._get_main_repo_root()
    mission_dir = _common._resolve_mission_dir_or_fail("mission-state", main_repo_root, mission)

    from specify_cli.status import reduce
    from specify_cli.status import read_events
    from specify_cli.core.dependency_graph import build_dependency_graph

    # STATUS reads stay on the coord-aware dir; PRIMARY reads (dep graph from WP
    # frontmatter, tasks/ enumeration) come from the primary surface (#2118).
    planning_dir = _planning_read_dir(main_repo_root, mission)

    # Query endpoint: reduce from event log without rewriting status.json.
    snapshot = reduce(read_events(mission_dir))
    dep_graph = build_dependency_graph(planning_dir)

    # Build the full WP set from task files + dep graph + snapshot
    # so that untouched WPs (no events yet) still appear as "planned"
    tasks_dir = planning_dir / "tasks"
    task_file_wp_ids: set[str] = set()
    if tasks_dir.exists():
        for p in tasks_dir.iterdir():
            if p.suffix == ".md":
                wp_id = _extract_wp_id(p.stem)
                if wp_id is not None:
                    task_file_wp_ids.add(wp_id)

    all_wp_ids = task_file_wp_ids | set(dep_graph.keys()) | set(snapshot.work_packages.keys())

    work_packages = []
    for wp_id in sorted(all_wp_ids):
        wp_snapshot = snapshot.work_packages.get(wp_id, {})
        work_packages.append(
            {
                "wp_id": wp_id,
                "lane": wp_snapshot.get("lane", Lane.PLANNED),
                "dependencies": dep_graph.get(wp_id, []),
                "last_actor": wp_snapshot.get("last_actor"),
            }
        )

    data = {
        **_common._mission_identity_payload(mission_dir),
        "summary": snapshot.summary,
        "work_packages": work_packages,
    }
    validate_outbound_payload(data, "orchestrator_api")
    envelope = make_envelope(
        command="mission-state",
        success=True,
        data=data,
    )
    _emit(envelope)


# ── Command 3: list-ready ──────────────────────────────────────────────────


@app.command(name="list-ready")
def list_ready(
    mission: str = typer.Option(..., "--mission", help=_HELP_MISSION_SLUG),
) -> None:
    """List WPs that are ready to start (planned and all deps approved or done)."""
    main_repo_root = _common._get_main_repo_root()
    mission_dir = _common._resolve_mission_dir_or_fail("list-ready", main_repo_root, mission)

    from specify_cli.status import reduce
    from specify_cli.status import read_events
    from specify_cli.core.dependency_graph import build_dependency_graph, dependency_readiness_for_wp

    # Query endpoint: reduce from event log without rewriting status.json.
    # STATUS read off the coord-aware dir; the dependency graph (WP frontmatter,
    # PRIMARY-partition) off the primary surface (#2118 — an empty dep graph here
    # is exactly what stalls the orchestrator under coordination topology).
    snapshot = reduce(read_events(mission_dir))
    dep_graph = build_dependency_graph(_planning_read_dir(main_repo_root, mission))
    wp_states = snapshot.work_packages
    wp_lanes = {dep_id: wp_state_for(state.get("lane", Lane.PLANNED)).lane for dep_id, state in wp_states.items()}

    ready_wps = []
    for wp_id, deps in dep_graph.items():
        wp_snapshot = wp_states.get(wp_id, {})
        lane = wp_snapshot.get("lane", Lane.PLANNED)
        state = wp_state_for(lane)
        if state.progress_bucket() != "not_started":
            continue

        # Advisory display parity (FR-009): a canceled-with-operator-provenance
        # dependency is a documented removal, so surface its dependent as ready
        # rather than blocked. `wp_states` is the reduced snapshot already read
        # above, so this reuses the authoritative provenance with no extra I/O.
        # Pre-flight UX only (FR-014, fsm-write-path-integrity WP04). The authoritative
        # dependency gate is `GuardContext.dependency_ready`, resolved in-lock by the emit shells.
        readiness = dependency_readiness_for_wp(wp_id, deps, wp_lanes, provenance=wp_states)

        ready_wps.append(
            {
                "wp_id": wp_id,
                "lane": lane,
                "dependencies_satisfied": readiness.satisfied,
            }
        )

    # Filter to only truly ready ones
    ready_wps = [wp for wp in ready_wps if wp["dependencies_satisfied"]]

    data = {
        **_common._mission_identity_payload(mission_dir),
        "ready_work_packages": ready_wps,
    }
    validate_outbound_payload(data, "orchestrator_api")
    envelope = make_envelope(
        command="list-ready",
        success=True,
        data=data,
    )
    _emit(envelope)


# ── Command table ───────────────────────────────────────────────────────────
# Every verb outside this module is registered here, in the order it was
# registered before the split (the group's ``--help`` order), so that order
# lives in one place (#5628). It is not the order of ``allowed_commands`` in
# ``upstream_contract.json``; the contract tests compare sets.
# ``contract-version``, ``mission-state`` and ``list-ready`` register above via
# their decorators; the latter two stay here for #5532.
_COMMAND_TABLE: tuple[tuple[str, Callable[..., None]], ...] = (
    ("resolve-workspace", wp_lifecycle.resolve_workspace),
    ("start-implementation", wp_lifecycle.start_implementation),
    ("start-review", wp_lifecycle.start_review),
    ("transition", wp_lifecycle.transition),
    ("append-history", wp_lifecycle.append_history),
    ("accept-mission", consolidation.accept_mission),
    ("consolidate-mission", consolidation.consolidate_mission),
    ("specify", design_phase.specify),
    ("plan", design_phase.plan),
    ("tasks", design_phase.tasks),
    ("check-prerequisites", design_phase.check_prerequisites),
    ("record-analysis", design_phase.record_analysis),
    ("open-decision", decision_verbs.open_decision),
    ("resolve-decision", decision_verbs.resolve_decision),
    ("defer-decision", decision_verbs.defer_decision),
    ("cancel-decision", decision_verbs.cancel_decision),
    ("answer-decision", decision_verbs.answer_decision),
    ("design-status", design_status.design_status),
    ("artifact-read", design_authoring.artifact_read),
    ("artifact-submit", design_authoring.artifact_submit),
    ("design-validate", design_authoring.design_validate),
    ("design-context", design_context.design_context),
    ("interview-record", design_context.interview_record),
    ("next", runtime_next.runtime_next),
)
for _name, _handler in _COMMAND_TABLE:
    app.command(name=_name)(_handler)
del _name, _handler


__all__ = ["app"]
