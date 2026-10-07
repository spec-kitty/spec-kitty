"""orchestrator-api design-phase delegate verbs (#5628).

``specify``, ``plan``, ``tasks``, ``check-prerequisites`` and
``record-analysis``. Registered on the app by ``commands.py``.
"""

from __future__ import annotations

import contextlib
import io
import json
import subprocess
import threading
from kernel.clock import now_utc_iso
from pathlib import Path
from dataclasses import dataclass
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from specify_cli.analysis_report import AnalysisReportResult
    from specify_cli.coordination.commit_router import CommitRouterResult

import typer

from mission_runtime import MissionTopology
from specify_cli.core.contract_gate import is_allowed_error_code, validate_outbound_payload
from specify_cli.core.errors import PlacementResolutionRequired

from .envelope import (
    make_envelope,
)


from . import _common
from ._common import (
    _HELP_MISSION_SLUG,
    _HELP_POLICY,
    _emit,
    _fail,
    _parse_policy_or_fail,
)


# Host-CLI create-payload keys that are NOT part of the orchestrator-api contract.
_SPECIFY_HOST_ONLY_PAYLOAD_KEYS = ("mission_branch", "commit_to_target")
_HELP_ANALYZER_AGENT = "Agent name that produced the analysis report"

# WP04 / NFR-004 / SK-93: the enforced wall-clock bound record-analysis's
# underlying write path (write_analysis_report + the best-effort commit) is
# run under -- Thread.join(timeout=...) actually returns control to the
# caller even if the worker thread is still running (a REAL bound; see
# `_run_write_with_timeout`). Module-level so tests can monkeypatch it down
# for a fast, genuine hang proof (T020).
_RECORD_ANALYSIS_TIMEOUT_SECONDS = 10.0


#: Fallback envelope code for the ``plan`` verb (WP05,
#: requirement-id-grammar-01M3NRCA). ``PLAN_SETUP_FAILED`` is ALREADY
#: registered in ``upstream_contract.json``'s ``allowed_error_codes`` -- this
#: constant exists only so ``_plan_contract_error`` below never restates the
#: literal, and so the one remaining literal ``_fail(cmd, "PLAN_SETUP_FAILED"``
#: call the static contract scan sees stays byte-identical to this value.
_PLAN_SETUP_FAILED_FALLBACK = "PLAN_SETUP_FAILED"


def _plan_contract_error(error_code: str, error_data: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """FR-015: keep the ``plan`` verb's envelope in contract.

    ``_classify_delegate_error`` trusts any ``error_code`` the ``setup_plan``
    delegate payload already carries verbatim -- correct for the
    contract-registered ones, but ``SPEC_REQUIREMENT_IDS_INVALID`` (WP05) and
    the pre-existing ``SPEC_FILE_MISSING`` / ``TEMPLATE_CONFIGURATION_ERROR`` /
    ``PLAN_CONTEXT_UNRESOLVED`` codes ``setup_plan`` can also raise are NOT
    registered for ``orchestrator_api`` (the latent leak this WP closes,
    scoped to ``plan`` only -- ``tasks``/``specify`` still share
    ``_classify_delegate_error`` unchanged and are not touched here). A
    registered code passes through unchanged; an unregistered one degrades to
    :data:`_PLAN_SETUP_FAILED_FALLBACK`, with the real code preserved as
    ``data["reason"]`` (never silently dropped, never leaked past the
    contract) -- mirrors ``_fail_from_decision_error``'s
    ``_DECISION_UNREGISTERED_CODE_FALLBACK`` pattern above.
    """
    if is_allowed_error_code("orchestrator_api", error_code):
        return error_code, error_data
    return _PLAN_SETUP_FAILED_FALLBACK, {**error_data, "reason": error_code}


# ── specify / plan / tasks (WP03) ────────────────────────────────────────
#
# Thin, in-process adapters over the SAME JSON-mode service functions the
# host CLI's own ``specify``/``plan``/``tasks`` shims
# (``specify_cli.cli.commands.lifecycle``) already delegate to. NEVER shell
# out to the host CLI: each verb captures the delegate's single ``--json``
# stdout line, then re-emits it (enriched for ``specify``, raw for
# ``plan``/``tasks``) inside the canonical orchestrator-api envelope.


def _extract_json_payload(raw_output: str) -> dict[str, Any] | None:
    """Parse the one JSON object a delegate command printed to its stdout.

    Mirrors ``lifecycle._create_mission_for_specify_json``'s own line-scan
    (first line starting with ``{`` that parses as a JSON object) rather than
    assuming line 1 verbatim -- tolerant of incidental non-JSON stdout noise
    from the delegate without duplicating its parsing logic wholesale.
    """
    for line in raw_output.splitlines():
        stripped = line.strip()
        if not stripped.startswith("{"):
            continue
        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload
    return None


def _classify_delegate_error(
    payload: dict[str, Any] | None,
    raw_output: str,
    *,
    fallback_code: str,
    fallback_message: str,
) -> tuple[str, str, dict[str, Any]]:
    """Classify a failed ``plan``/``tasks``/``specify`` delegate call, trusting
    any typed ``error_code`` the delegate already carries and falling back to
    a verb-specific structured code otherwise -- never a bare exception.

    ``specify`` uses the same seam (#3861): the mission-creation delegate now
    surfaces its duplicate-mission refusal as a typed
    ``MissionAlreadyExistsError`` whose ``error_code`` travels in the JSON
    error payload, so this trust-the-typed-code path is the ONLY
    already-exists classification -- the retired substring heuristic over
    the delegate's message prose could silently mislabel when wording
    changed.
    """
    if payload is None:
        message = raw_output.strip() or fallback_message
        return fallback_code, message, {"raw_output": raw_output}
    message = str(payload.get("error") or payload.get("message") or fallback_message)
    error_code = payload.get("error_code")
    if error_code:
        return str(error_code), message, payload
    return fallback_code, message, payload


# ── Command 10: specify ──────────────────────────────────────────────────


def specify(
    mission: str = typer.Option(..., "--mission", help=_HELP_MISSION_SLUG),
    mission_type: str = typer.Option(..., "--mission-type", help="Mission type (e.g., software-dev)"),
    topology: MissionTopology | None = typer.Option(
        None,
        "--topology",
        help=(
            "Create-time mission shape: single_branch | lanes | coord | lanes_with_coord. Default: context-derived (matches the host CLI's own --topology default)."
        ),
    ),
    policy: str = typer.Option(None, "--policy", help=_HELP_POLICY),
) -> None:
    """Create a mission scaffold, matching the host CLI's enriched ``specify --json`` contract.

    In-process only (FR-001): calls
    ``specify_cli.cli.commands.lifecycle._create_mission_for_specify_json``,
    the SAME enrichment step the host CLI's ``--json`` path runs (adds
    ``scaffold_only``/``spec_state``/``next_action``/``next_step`` on top of
    ``agent_feature.create_mission``'s raw payload) -- never the unenriched
    payload one layer beneath it.
    """
    cmd = "specify"

    if not policy:
        _fail(cmd, "POLICY_METADATA_REQUIRED", "--policy is required for specify")
        return
    _parse_policy_or_fail(cmd, policy)

    from specify_cli.cli.commands.lifecycle import _create_mission_for_specify_json

    capture = io.StringIO()
    try:
        with contextlib.redirect_stdout(capture):
            _create_mission_for_specify_json(mission, mission_type, topology)
    except typer.Exit:
        raw_output = capture.getvalue()
        payload = _extract_json_payload(raw_output)
        error_code, message, error_data = _classify_delegate_error(
            payload,
            raw_output,
            fallback_code="MISSION_CREATE_FAILED",
            fallback_message="mission creation failed",
        )
        _fail(cmd, error_code, message, error_data)
        return

    raw_output = capture.getvalue()
    payload = _extract_json_payload(raw_output)
    if payload is None:
        _fail(
            cmd,
            "MISSION_CREATE_FAILED",
            "specify produced no parseable JSON payload",
            {"raw_output": raw_output},
        )
        return
    # Belt-and-brace, matching ``plan``/``tasks``/``check_prerequisites``
    # (~2320/2383/2536): ``_create_mission_for_specify_json``'s own payload
    # already carries ``mission_slug`` (verified against production), so this
    # is a structural no-op on the normal path -- NOT business-payload
    # enrichment, it fills the ONE transport-contract identity field
    # (``upstream_contract.json``'s ``required_payload_fields``) every
    # orchestrator-api response must carry, only when the delegate omits it.
    #
    # Deliberately NOT a plain ``setdefault("mission_slug", mission)``: the
    # raw ``mission`` input is the PRE-mid8-suffix handle
    # (``mission_dir_name`` appends ``-<mid8>`` at creation --
    # ``lanes/branch_naming.py:488``), so it is not itself the canonical
    # slug once the mission exists on disk. Only resolve (and pay the extra
    # disk lookup) in the fallback branch, using the SAME
    # ``_mission_identity_payload(mission_dir)["mission_slug"]`` the siblings
    # read post-resolution -- the real, mid8-suffixed value -- rather than a
    # guess that could be wrong. Never overwrites a delegate-supplied value.
    if "mission_slug" not in payload:
        main_repo_root = _common._get_main_repo_root()
        mission_dir = _common._resolve_mission_dir_or_fail(cmd, main_repo_root, mission)
        payload["mission_slug"] = _common._mission_identity_payload(mission_dir)["mission_slug"]
    # #5100 (WP08): the host ``agent mission create --json`` payload gained
    # ``mission_branch`` / ``commit_to_target``. They are host-CLI create
    # diagnostics, NOT part of the versioned orchestrator-api contract
    # (``upstream_contract.json``, pinned by
    # ``_SPECIFY_SUCCESS_DATA_KEYS``), so they must not leak through this
    # pass-through. Drop them rather than widening the external contract.
    for host_only_key in _SPECIFY_HOST_ONLY_PAYLOAD_KEYS:
        payload.pop(host_only_key, None)
    validate_outbound_payload(payload, "orchestrator_api")
    envelope = make_envelope(command=cmd, success=True, data=payload)
    _emit(envelope)


# ── Command 11: plan ─────────────────────────────────────────────────────


def plan(
    mission: str = typer.Option(..., "--mission", help=_HELP_MISSION_SLUG),
    policy: str = typer.Option(None, "--policy", help=_HELP_POLICY),
) -> None:
    """Scaffold plan.md for a mission -- an unenriched pass-through of ``setup_plan``.

    FR-002 / Clarification 1: deliberately asymmetric with ``specify`` -- the
    host CLI's own ``--json`` path returns ``agent_feature.setup_plan``'s raw
    dict verbatim (``lifecycle.py`` adds no enrichment here), so this verb
    does the same. Do not add fields ``setup_plan`` does not already return.
    """
    cmd = "plan"

    if not policy:
        _fail(cmd, "POLICY_METADATA_REQUIRED", "--policy is required for plan")
        return
    _parse_policy_or_fail(cmd, policy)

    main_repo_root = _common._get_main_repo_root()
    mission_dir = _common._resolve_mission_dir_or_fail(cmd, main_repo_root, mission)

    from specify_cli.cli.commands.agent import mission as agent_feature

    from specify_cli.design.errors import DesignError
    from specify_cli.design.receipts import api_authoring_enabled
    from specify_cli.design.validation import require_unfinalized

    try:
        if api_authoring_enabled(main_repo_root, mission_dir.name):
            require_unfinalized(main_repo_root, mission_dir.name)
    except DesignError as exc:
        _fail(cmd, exc.code, exc.message, exc.details)
        return

    capture = io.StringIO()
    try:
        with contextlib.redirect_stdout(capture):
            agent_feature.setup_plan(feature=mission, json_output=True)
    except typer.Exit:
        raw_output = capture.getvalue()
        payload = _extract_json_payload(raw_output)
        error_code, message, error_data = _classify_delegate_error(
            payload,
            raw_output,
            fallback_code=_PLAN_SETUP_FAILED_FALLBACK,
            fallback_message="plan scaffolding failed",
        )
        # FR-015: keep the envelope in contract -- an unregistered delegate
        # code (e.g. SPEC_REQUIREMENT_IDS_INVALID) degrades to
        # PLAN_SETUP_FAILED with the real code preserved as data["reason"];
        # a registered code (including this except block's own fallback,
        # already PLAN_SETUP_FAILED) passes through unchanged.
        error_code, error_data = _plan_contract_error(error_code, error_data)
        _fail(cmd, error_code, message, error_data)
        return

    raw_output = capture.getvalue()
    payload = _extract_json_payload(raw_output)
    if payload is None:
        _fail(
            cmd,
            "PLAN_SETUP_FAILED",
            "plan produced no parseable JSON payload",
            {"raw_output": raw_output},
        )
        return
    # ``setup_plan``'s own payload already carries ``mission_slug`` (verified
    # against production); ``setdefault`` is a structural no-op belt-and-brace
    # here -- this is NOT business-payload enrichment (T011's asymmetry bar),
    # it fills the ONE transport-contract identity field
    # (``upstream_contract.json``'s ``required_payload_fields``) every
    # orchestrator-api response must carry, using the already-resolved input
    # identity -- never overwriting a delegate-supplied value.
    payload.setdefault("mission_slug", _common._mission_identity_payload(mission_dir)["mission_slug"])
    if payload.get("result") in ("blocked", "error") or payload.get("success") is False:
        error_code, message, error_data = _classify_delegate_error(
            payload, raw_output, fallback_code=_PLAN_SETUP_FAILED_FALLBACK,
            fallback_message="plan prerequisites are blocked",
        )
        error_code, error_data = _plan_contract_error(error_code, error_data)
        _fail(cmd, error_code, message, error_data)
        return
    validate_outbound_payload(payload, "orchestrator_api")
    envelope = make_envelope(command=cmd, success=True, data=payload)
    _emit(envelope)


# ── Command 12: tasks ────────────────────────────────────────────────────


def tasks(
    mission: str = typer.Option(..., "--mission", help=_HELP_MISSION_SLUG),
    policy: str = typer.Option(None, "--policy", help=_HELP_POLICY),
) -> None:
    """Finalize WP task metadata -- an unenriched pass-through of ``finalize_tasks``.

    FR-003 / Clarification 1: same deliberate asymmetry as ``plan`` -- the
    host CLI's own ``--json`` path returns ``agent_feature.finalize_tasks``'s
    raw dict verbatim, so this verb does the same.
    """
    cmd = "tasks"

    if not policy:
        _fail(cmd, "POLICY_METADATA_REQUIRED", "--policy is required for tasks")
        return
    _parse_policy_or_fail(cmd, policy)

    main_repo_root = _common._get_main_repo_root()
    mission_dir = _common._resolve_mission_dir_or_fail(cmd, main_repo_root, mission)

    from specify_cli.cli.commands.agent import mission as agent_feature

    from specify_cli.design.context import DesignContextError
    from specify_cli.design.errors import DesignError
    from specify_cli.design.validation import finalization_scope

    capture = io.StringIO()
    try:
        with finalization_scope(main_repo_root, mission_dir.name), contextlib.redirect_stdout(capture):
            agent_feature.finalize_tasks(feature=mission, json_output=True)
    except (DesignError, DesignContextError) as exc:
        _fail(cmd, exc.code, exc.message, exc.details)
        return
    except typer.Exit:
        raw_output = capture.getvalue()
        payload = _extract_json_payload(raw_output)
        error_code, message, error_data = _classify_delegate_error(
            payload,
            raw_output,
            fallback_code="TASKS_FINALIZE_FAILED",
            fallback_message="tasks finalization failed",
        )
        _fail(cmd, error_code, message, error_data)
        return

    raw_output = capture.getvalue()
    payload = _extract_json_payload(raw_output)
    if payload is None:
        _fail(
            cmd,
            "TASKS_FINALIZE_FAILED",
            "tasks produced no parseable JSON payload",
            {"raw_output": raw_output},
        )
        return
    # finalize_tasks' raw payload does NOT carry ``mission_slug`` (verified
    # against production) -- unlike ``plan``, this is a genuine gap the
    # transport contract's ``required_payload_fields`` requires filling. Same
    # non-enrichment rationale as ``plan`` above: fills the one identity field
    # from the already-resolved input, adds nothing else.
    payload.setdefault("mission_slug", _common._mission_identity_payload(mission_dir)["mission_slug"])
    validate_outbound_payload(payload, "orchestrator_api")
    envelope = make_envelope(command=cmd, success=True, data=payload)
    _emit(envelope)


# ── Command 13: check-prerequisites ─────────────────────────────────────────


_FEATURE_CONTEXT_UNRESOLVED = "FEATURE_CONTEXT_UNRESOLVED"


def _sanitize_forbidden_error_code(value: Any, forbidden: str, replacement: str) -> Any:
    """Recursively replace every occurrence of *forbidden* with *replacement*,
    at any depth of nested dicts/lists (PR-TESTS-002), including as a dict
    KEY and as a SUBSTRING of a larger string -- not only a whole-value
    match.

    ``_classify_check_prerequisites_error`` translates the top-level
    ``error_code`` correctly, but the raw delegate ``payload`` it also
    returns (spread verbatim into the envelope's ``data``) still carries its
    OWN ``error_code`` key with the untranslated forbidden value -- a leak
    of the terminology-canon-forbidden string one level down, in the SAME
    response whose top-level ``error_code`` claims to have translated it.
    Sanitizing recursively (not just the payload's top-level ``error_code``
    key) closes the leak at whatever nesting level it appears, matching the
    "no forbidden token anywhere in the serialized response" bar this fix's
    regression test asserts.

    A verifier (PR-TESTS-002 residual) defeated an earlier whole-value-only,
    values-only version of this function two ways: the forbidden token as a
    dict KEY (never visited -- only ``.items()`` VALUES were recursed), and
    the forbidden token as a SUBSTRING of a longer string (an exact ``==``
    match against the whole string never fires). Both are closed here: keys
    are sanitized by substring replacement exactly like values, and string
    values use ``str.replace`` (containment) rather than ``==`` (whole-value
    equality), so a forbidden token embedded in a larger string is scrubbed
    without needing the whole string to equal it.
    """
    if isinstance(value, dict):
        return {
            (_sanitize_forbidden_error_code(k, forbidden, replacement) if isinstance(k, str) else k): (_sanitize_forbidden_error_code(v, forbidden, replacement))
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [_sanitize_forbidden_error_code(v, forbidden, replacement) for v in value]
    if isinstance(value, str) and forbidden in value:
        return value.replace(forbidden, replacement)
    return value


def _classify_check_prerequisites_error(payload: dict[str, Any] | None, raw_output: str) -> tuple[str, str, dict[str, Any]]:
    """Classify a failed ``check-prerequisites`` delegate call.

    The host CLI's own detection-failure payload carries
    ``error_code: "FEATURE_CONTEXT_UNRESOLVED"`` (``mission_check_prerequisites.py``)
    -- a feature-named code that must NEVER cross onto the orchestrator-api
    surface verbatim (Terminology Canon; ``upstream_contract.json``'s
    ``forbidden_error_codes`` bans the sibling ``FEATURE_NOT_FOUND``/
    ``FEATURE_NOT_READY`` for the identical reason). This is the ONE place
    that code is translated to this file's canonical ``MISSION_NOT_FOUND`` --
    every other typed ``error_code`` the delegate carries is trusted verbatim,
    mirroring ``_classify_delegate_error``. The translation is applied to the
    WHOLE returned payload (``_sanitize_forbidden_error_code``), not just the
    top-level ``error_code`` this function returns as its first tuple
    element -- the untranslated payload's own nested ``error_code`` key was
    leaking the forbidden string into ``data.error_code`` (PR-TESTS-002).
    """
    if payload is None:
        message = raw_output.strip() or "check-prerequisites failed"
        return "CHECK_PREREQUISITES_FAILED", message, {"raw_output": raw_output}
    message = str(payload.get("error") or payload.get("message") or "check-prerequisites failed")
    error_code = payload.get("error_code")
    if error_code == _FEATURE_CONTEXT_UNRESOLVED:
        sanitized = cast(
            "dict[str, Any]",
            _sanitize_forbidden_error_code(payload, _FEATURE_CONTEXT_UNRESOLVED, "MISSION_NOT_FOUND"),
        )
        return "MISSION_NOT_FOUND", message, sanitized
    if error_code:
        return str(error_code), message, payload
    return "CHECK_PREREQUISITES_FAILED", message, payload


def check_prerequisites(
    mission: str = typer.Option(..., "--mission", help=_HELP_MISSION_SLUG),
    include_tasks: bool = typer.Option(
        False,
        "--include-tasks",
        help="Include tasks.md validation (matches the host CLI's own --include-tasks default)",
    ),
) -> None:
    """Read-only mission-prerequisite context for ``/spec-kitty.analyze`` (FR-004).

    C-002: this verb supplies context ONLY -- it never performs `analyze`'s
    cross-artifact reasoning itself (mirrors ``start-review``'s "cannot
    perform WP implementation itself" pattern). No ``--policy`` is required
    (read-only, per spec Edge Cases: "Read-only verbs (check-prerequisites,
    design-status) do not require --policy").

    In-process only (FR-001-style parity): calls the host CLI's OWN
    ``check_prerequisites`` Typer command function
    (``mission_check_prerequisites.py:498``) directly -- the exact
    established pattern WP03's ``plan``/``tasks`` verbs already use for a
    registered ``agent mission`` Typer command (``setup_plan``/
    ``finalize_tasks`` are registered identically:
    ``app.command(...)(func)`` in ``mission.py``), so field-parity with
    ``agent mission check-prerequisites --json --include-tasks`` is
    guaranteed by construction rather than by re-deriving
    ``validate_feature_structure``'s shaping logic a second time.
    """
    cmd = "check-prerequisites"

    main_repo_root = _common._get_main_repo_root()
    # Existence gate FIRST via the coord-aware read seam (consistent
    # MISSION_NOT_FOUND envelope shared with every other read endpoint in
    # this module) -- the delegate below is only reached for a mission that
    # is already known to exist.
    mission_dir = _common._resolve_mission_dir_or_fail(cmd, main_repo_root, mission)

    from specify_cli.cli.commands.agent.mission_check_prerequisites import (
        check_prerequisites as _host_check_prerequisites,
    )

    capture = io.StringIO()
    try:
        with contextlib.redirect_stdout(capture):
            _host_check_prerequisites(feature=mission, json_output=True, include_tasks=include_tasks)
    except typer.Exit:
        raw_output = capture.getvalue()
        payload = _extract_json_payload(raw_output)
        error_code, message, error_data = _classify_check_prerequisites_error(payload, raw_output)
        _fail(cmd, error_code, message, error_data)
        return

    raw_output = capture.getvalue()
    payload = _extract_json_payload(raw_output)
    if payload is None:
        _fail(
            cmd,
            "CHECK_PREREQUISITES_FAILED",
            "check-prerequisites produced no parseable JSON payload",
            {"raw_output": raw_output},
        )
        return
    # validate_feature_structure()'s own shape does not carry ``mission_slug``
    # (verified against production) -- same transport-contract identity fill
    # as ``plan``/``tasks`` above, never business-payload enrichment.
    payload.setdefault("mission_slug", _common._mission_identity_payload(mission_dir)["mission_slug"])
    validate_outbound_payload(payload, "orchestrator_api")
    envelope = make_envelope(command=cmd, success=True, data=payload)
    _emit(envelope)


# ── Command 14: record-analysis ─────────────────────────────────────────────


@dataclass
class _TimedWriteOutcome:
    """Outcome of a timeout-bounded call to the underlying write path (SK-93).

    ``completed`` is set by the worker thread itself in a ``finally`` block
    (never inferred from ``Thread.is_alive()`` after ``join`` -- a TOCTOU-safe
    signal). NEITHER field drives ``record-analysis``'s ``success`` verdict --
    that is determined SOLELY by re-reading the artifact off disk afterward;
    this dataclass exists only to enrich the failure envelope's diagnostic
    ``data`` (e.g. surfacing whether the underlying call raised or is still
    running in a leaked daemon thread).
    """

    completed: bool = False
    result: AnalysisReportResult | None = None
    commit_result: CommitRouterResult | None = None
    raised: Exception | None = None


def _run_write_with_timeout(fn: Callable[[], tuple[AnalysisReportResult, CommitRouterResult | None]], *, timeout_seconds: float) -> _TimedWriteOutcome:
    """Run ``fn`` bounded by ``timeout_seconds`` in a daemon worker thread.

    A REAL enforced bound (NFR-004(b) / T020): ``Thread.join(timeout=...)``
    returns control to the caller once ``timeout_seconds`` elapses regardless
    of whether the worker thread has finished -- this is not a decorative
    ``try/except TimeoutError`` that never actually fires (Python offers no
    safe thread-kill primitive, so a still-running worker is left as a leaked
    daemon thread, never blocking process exit). Never re-raises: any
    exception the underlying call raises is captured as diagnostic data, not
    propagated -- ``record-analysis``'s success determination never depends
    on whether this call raised, returned, or is still hanging (SK-93).
    """
    outcome = _TimedWriteOutcome()

    def _worker() -> None:
        try:
            outcome.result, outcome.commit_result = fn()
        except Exception as exc:  # noqa: BLE001 -- deliberately broad: captures
            # ANY failure from the underlying write path (including a test
            # double's injected raise) as diagnostic data. Never re-raised;
            # the re-read off disk is the sole success signal (SK-93).
            outcome.raised = exc
        finally:
            outcome.completed = True

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()
    thread.join(timeout=timeout_seconds)
    return outcome


@dataclass(frozen=True)
class _AnalysisReportReread:
    """The re-read artifact state -- the SOLE success signal (SK-93)."""

    path: Path
    verdict: str | None
    generated_at: str | None


def _reread_analysis_report(path: Path) -> _AnalysisReportReread | None:
    """Re-read ``analysis-report.md`` off disk, or ``None`` if absent.

    Never trusts the write call's own return/raise/hang behavior (SK-93) --
    this reads whatever landed on disk, if anything, after the write
    attempt returned or the enforced timeout fired.
    """
    if not path.exists():
        return None
    from specify_cli.frontmatter import FrontmatterError, FrontmatterManager

    try:
        frontmatter, _body = FrontmatterManager().read(path)
    except FrontmatterError:
        return _AnalysisReportReread(path=path, verdict=None, generated_at=None)
    verdict = frontmatter.get("verdict")
    generated_at = frontmatter.get("generated_at")
    return _AnalysisReportReread(
        path=path,
        verdict=str(verdict) if verdict is not None else None,
        generated_at=str(generated_at) if generated_at is not None else None,
    )


def _is_strictly_after(candidate_iso: str, reference_iso: str) -> bool:
    """True if ``candidate_iso`` is a strictly later instant than ``reference_iso``.

    Parses both through :func:`kernel.clock.parse_iso` (the single wall-clock
    door, C-008) rather than comparing raw strings -- an explicit, honest
    comparison instead of relying on ISO-8601 lexicographic-ordering luck.
    """
    from kernel.clock import parse_iso

    try:
        return parse_iso(candidate_iso) > parse_iso(reference_iso)
    except ValueError:
        return False


def _read_record_analysis_body(input_file: str) -> str:
    """Read the analysis report body from ``--input-file``, or stdin for ``-``.

    Mirrors the host CLI's own ``record_analysis``'s ``--input-file`` flag
    semantics exactly (``mission_record_analysis.py``).
    """
    if input_file == "-":
        import sys

        return sys.stdin.read()
    return Path(input_file).read_text(encoding="utf-8")


def _classify_record_analysis_failure(
    *,
    submitted_verdict: str,
    reread: _AnalysisReportReread | None,
    call_start: str,
) -> tuple[str, str]:
    """Classify a ``record-analysis`` failure into a structured ``(error_code, message)``.

    Distinguishes "write did not happen" (no artifact re-read confirms a
    fresh write after ``call_start`` -- SC-005(c)'s stale-but-matching-verdict
    shape included) from "write happened, signal was noise" (a confirmed
    fresh write whose verdict is not trustworthy -- either it disagrees with
    what THIS call submitted, or the submission itself carried no valid
    carrier and computed to ``unknown``, SK-06/#3133) -- never collapsed into
    one generic code (T018 step 3).
    """
    from specify_cli.analysis_report import VERDICT_UNKNOWN

    write_confirmed = reread is not None and reread.generated_at is not None and _is_strictly_after(reread.generated_at, call_start)
    if not write_confirmed:
        return "RECORD_ANALYSIS_WRITE_NOT_CONFIRMED", (
            "record-analysis could not confirm a fresh write: no analysis-report.md with a generated_at timestamp later than this call's start was found on disk."
        )
    if submitted_verdict == VERDICT_UNKNOWN:
        return "RECORD_ANALYSIS_VERDICT_UNRELIABLE", (
            "The submitted analysis report carried no valid "
            "analysis-findings/v1 carrier, so no reliable verdict could be "
            "recorded (verdict: unknown is never reported as success)."
        )
    return "RECORD_ANALYSIS_VERDICT_UNRELIABLE", (
        f"analysis-report.md was written but its verdict ({reread.verdict if reread else None!r}) does not match the submitted verdict ({submitted_verdict!r})."
    )


def _do_record_analysis_write(
    *,
    write_feature_dir: Path,
    main_repo_root: Path,
    body: str,
    agent: str | None,
    mission_slug: str,
) -> tuple[AnalysisReportResult, CommitRouterResult | None]:
    """The underlying write path: ``write_analysis_report`` + a best-effort commit.

    Option (a) from plan.md § (j) (NFR-004(b)'s explicitly offered
    mitigation): calls ``write_analysis_report``/``commit_for_mission``
    directly rather than going through ``record_analysis``'s full CLI
    wrapper, so ``record_analysis``'s own unbounded
    ``trigger_feature_dossier_sync_if_enabled`` tail
    (``mission_record_analysis.py:384-388``, bounded only against a *raised*
    exception via ``contextlib.suppress(Exception)`` -- NOT against a *hang*)
    is never invoked at all. This function itself additionally runs under
    :func:`_run_write_with_timeout` as defense-in-depth against any OTHER
    hang (e.g. a wedged git subprocess inside ``commit_for_mission``).

    WP14 (contracts/commit-outcome.md): the return now ALSO carries the
    router's own ``CommitRouterResult`` (``None`` when the best-effort commit
    itself raised) so the caller can render ``commit_surfaces`` additively
    instead of discarding the outcome entirely.
    """
    from specify_cli.analysis_report import write_analysis_report

    result = write_analysis_report(
        feature_dir=write_feature_dir,
        repo_root=main_repo_root,
        body=body,
        analyzer_agent=agent,
    )

    # Best-effort commit -- mirrors mission_record_analysis.py's own narrowed
    # exception set (WP03/#3128 there): a commit failure (e.g. a protected
    # target ref) never undoes the write already on disk.
    commit_result: CommitRouterResult | None = None
    with contextlib.suppress(subprocess.CalledProcessError, OSError, RuntimeError, ValueError):
        from mission_runtime import MissionArtifactKind
        from specify_cli.coordination.commit_router import commit_for_mission
        from specify_cli.core.paths import get_feature_target_branch
        from specify_cli.git.protection_policy import ProtectionPolicy

        commit_result = commit_for_mission(
            repo_root=main_repo_root,
            mission_slug=mission_slug,
            files=(result.path,),
            message=f"docs(record-analysis): record analysis report for mission {mission_slug}",
            policy=ProtectionPolicy.resolve(main_repo_root),
            kind=MissionArtifactKind.ANALYSIS_REPORT,
            target_branch=get_feature_target_branch(main_repo_root, mission_slug),
        )
    return result, commit_result


def _record_analysis_commit_surfaces_payload(commit_result: CommitRouterResult | None) -> dict[str, Any]:
    """Additive ``commit_surfaces`` (+ ``warnings``) fields for the success envelope (WP14, T076).

    ``None`` (the best-effort commit itself raised) or an empty ``surfaces``
    tuple (the legacy shape) adds nothing -- additive-only, never a new
    required key (contracts/commit-outcome.md: "finalize-tasks (--json) adds
    commit_surfaces beside the existing commit_hashes", the same additive
    shape this orchestrator verb mirrors). ``warnings`` is populated only when
    some surface is neither ``committed`` nor ``unchanged`` (research D8).
    """
    if commit_result is None or not commit_result.surfaces:
        return {}
    from specify_cli.coordination.commit_outcome import STATUS_COMMITTED, STATUS_UNCHANGED, commit_outcome_payload, render_commit_outcome

    extra: dict[str, Any] = {"commit_surfaces": commit_outcome_payload(commit_result)["surfaces"]}
    if any(outcome.status not in (STATUS_COMMITTED, STATUS_UNCHANGED) for outcome in commit_result.surfaces):
        extra["warnings"] = render_commit_outcome(commit_result)
    return extra


def record_analysis(
    mission: str = typer.Option(..., "--mission", help=_HELP_MISSION_SLUG),
    input_file: str = typer.Option(
        "-",
        "--input-file",
        help="Markdown report path, or '-' to read the report body from stdin",
    ),
    agent: str | None = typer.Option(None, "--agent", help=_HELP_ANALYZER_AGENT),
    policy: str = typer.Option(None, "--policy", help=_HELP_POLICY),
) -> None:
    """Persist an ``/spec-kitty.analyze`` report, verified against disk (FR-005).

    NFR-004 / SK-93 (verified): a subprocess/call-level success signal
    (return code, "did not raise") is UNTRUSTWORTHY -- SK-93 documented
    ``record-analysis`` reporting a false timeout FAILURE after a write had
    already genuinely succeeded. This verb instead:

    1. Captures ``now_utc_iso()`` immediately before invoking the write path.
    2. Calls ``write_analysis_report``/``commit_for_mission`` directly
       (bypassing ``record_analysis``'s own unbounded dossier-sync trigger
       entirely -- option (a), plan.md § (j)), under an enforced
       :func:`_run_write_with_timeout` bound as defense-in-depth.
    3. Re-reads ``analysis-report.md`` off disk unconditionally afterward.
       ``success: true`` ONLY if BOTH (a) the re-read ``verdict`` matches
       what THIS call submitted, AND (b) the re-read ``generated_at`` is
       STRICTLY LATER than the call-start timestamp -- a verdict-string
       match alone is never sufficient (distinguishes a genuine fresh write
       from a stale, coincidentally-matching pre-existing artifact).

    SK-06 / #3133: an ``unknown`` verdict (no valid ``analysis-findings/v1``
    carrier in the submitted body) is NEVER reported as ``success: true``,
    even when the write genuinely, freshly succeeds -- silently writing
    ``verdict: unknown`` for an explicitly-intended report is this repo's
    dominant failure mode and this verb refuses to propagate it as success.

    A mutating verb: ``--policy`` is required (``POLICY_METADATA_REQUIRED``
    pattern, matching ``specify``/``plan``/``tasks``).
    """
    cmd = "record-analysis"

    if not policy:
        _fail(cmd, "POLICY_METADATA_REQUIRED", "--policy is required for record-analysis")
        return
    _parse_policy_or_fail(cmd, policy)

    main_repo_root = _common._get_main_repo_root()
    mission_dir = _common._resolve_mission_dir_or_fail(cmd, main_repo_root, mission)
    mission_slug = _common._mission_identity_payload(mission_dir)["mission_slug"]

    # PR-CONTRACT-001 (host-CLI parity, R3-confirmed live ordering fork):
    # placement resolution + the dirty-worktree preflight run BEFORE the
    # body is read/validated -- matching the host CLI's own
    # ``mission_record_analysis.record_analysis`` ordering EXACTLY
    # (placement -> dirty-tree preflight -> THEN ``body = sys.stdin.read()``,
    # mission_record_analysis.py's ``record_analysis`` function). Pre-fix,
    # this verb read/validated the body FIRST, so an identical on-disk state
    # (dirty tree + empty/malformed body) reported a DIFFERENT first
    # error_code than the host CLI for the same request -- this is the
    # THIRD instance of that ordering-fork class in this mission (after
    # WP05-001/WP08-001). See ``tests/specify_cli/orchestrator_api/
    # test_check_prerequisites_record_analysis.py``'s
    # ``_host_record_analysis_error_code`` helper and its docstring
    # for the reusable, verb-agnostic parity-test pattern added alongside
    # this fix (and for why a production-code "by construction" ordering
    # guard was judged infeasible within this diff, not silently skipped).
    from specify_cli.cli.commands.agent.mission_feature_resolution import _kind_for_artifact
    from specify_cli.cli.commands.agent.mission_record_analysis import (
        _enforce_analysis_report_write_preflight,
        _require_record_analysis_placement,
        _resolve_record_analysis_placement_ref,
    )
    from mission_runtime import placement_seam

    placement_ref = _resolve_record_analysis_placement_ref(main_repo_root, mission_dir)
    try:
        placement_ref = _require_record_analysis_placement(placement_ref, mission_slug=mission_slug)
    except PlacementResolutionRequired as exc:
        _fail(cmd, "PLACEMENT_RESOLUTION_REQUIRED", str(exc), {"mission_slug": mission_slug})
        return

    capture = io.StringIO()
    try:
        with contextlib.redirect_stdout(capture):
            _enforce_analysis_report_write_preflight(main_repo_root, json_output=True, placement_ref=placement_ref, mission_slug=mission_slug)
    except typer.Exit:
        raw_output = capture.getvalue()
        payload = _extract_json_payload(raw_output)
        error_code, message, error_data = _classify_delegate_error(
            payload,
            raw_output,
            fallback_code="DIRTY_WORKTREE",
            fallback_message="record-analysis dirty-tree preflight failed",
        )
        error_data.setdefault("mission_slug", mission_slug)
        _fail(cmd, error_code, message, error_data)
        return

    try:
        body = _read_record_analysis_body(input_file)
    except OSError as exc:
        _fail(
            cmd,
            "RECORD_ANALYSIS_INPUT_FILE_NOT_FOUND",
            f"Could not read --input-file {input_file!r}: {exc}",
            {"mission_slug": mission_slug},
        )
        return
    if not body.strip():
        _fail(cmd, "RECORD_ANALYSIS_EMPTY_BODY", "Analysis report body is empty", {"mission_slug": mission_slug})
        return

    from specify_cli.analysis_report import VERDICT_UNKNOWN, FindingsCarrierError, parse_structured_findings

    try:
        structured = parse_structured_findings(body)
    except FindingsCarrierError as exc:
        _fail(cmd, "RECORD_ANALYSIS_MALFORMED_CARRIER", str(exc), {"mission_slug": mission_slug})
        return
    submitted_verdict = structured.verdict if structured is not None else VERDICT_UNKNOWN

    write_feature_dir = placement_seam(main_repo_root, mission_slug).read_dir(_kind_for_artifact("spec"))

    # Step 1 (NFR-004 / SK-93): the call-start timestamp, captured
    # IMMEDIATELY before invoking the write path -- everything above this
    # line is preflight/validation, not "the underlying write call".
    call_start = now_utc_iso()

    def _do_write() -> tuple[AnalysisReportResult, CommitRouterResult | None]:
        return _do_record_analysis_write(
            write_feature_dir=write_feature_dir,
            main_repo_root=main_repo_root,
            body=body,
            agent=agent,
            mission_slug=mission_slug,
        )

    write_outcome = _run_write_with_timeout(_do_write, timeout_seconds=_RECORD_ANALYSIS_TIMEOUT_SECONDS)

    # Step 3 (NFR-004 / SK-93): unconditional re-read -- the SOLE success
    # signal, regardless of whether the call above returned, raised, or is
    # still hanging in a leaked daemon thread.
    report_path = write_feature_dir / "analysis-report.md"
    reread = _reread_analysis_report(report_path)

    write_confirmed = reread is not None and reread.generated_at is not None and _is_strictly_after(reread.generated_at, call_start)
    success = write_confirmed and submitted_verdict != VERDICT_UNKNOWN and reread is not None and reread.verdict == submitted_verdict

    if success and reread is not None:
        data = {
            **_common._mission_identity_payload(mission_dir),
            "path": str(reread.path),
            "verdict": reread.verdict,
            "generated_at": reread.generated_at,
            **_record_analysis_commit_surfaces_payload(write_outcome.commit_result),
        }
        validate_outbound_payload(data, "orchestrator_api")
        envelope = make_envelope(command=cmd, success=True, data=data)
        _emit(envelope)
        return

    error_code, message = _classify_record_analysis_failure(submitted_verdict=submitted_verdict, reread=reread, call_start=call_start)
    failure_data: dict[str, Any] = {"mission_slug": mission_slug, "submitted_verdict": submitted_verdict}
    if reread is not None:
        failure_data["reread_verdict"] = reread.verdict
        failure_data["reread_generated_at"] = reread.generated_at
    if not write_outcome.completed:
        failure_data["underlying_call_timed_out"] = True
    elif write_outcome.raised is not None:
        failure_data["underlying_call_error"] = str(write_outcome.raised)
    _fail(cmd, error_code, message, failure_data)
