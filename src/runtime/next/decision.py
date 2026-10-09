"""Core decision engine for ``spec-kitty next``.

Delegates planning to the CLI-internal runtime
(``runtime.next._internal_runtime``) via :mod:`runtime_bridge`.
Post-mission ``shared-package-boundary-cutover-01KQ22DS`` the standalone
``spec-kitty-runtime`` PyPI package is no longer involved in any
production code path.

The :class:`Decision` dataclass and :class:`DecisionKind` constants are the
public JSON contract.  WP helpers (``_compute_wp_progress``,
``_find_first_wp_by_lane``) and ``_state_to_action`` are kept for use by the
bridge layer.
"""

from __future__ import annotations

import contextlib
import io
import logging
import os
import re
import tempfile
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal

from charter.activation.pack_context import ActiveCharterConfigError
from mission_runtime import ActionContextError, OwnedCheckout
from runtime.next._tmp_namespace import prompt_tmp_dir
from specify_cli.mission_metadata import mission_identity_fields
from specify_cli.status import wp_state_for
from specify_cli.status import Lane
from specify_cli.status import NON_DISPLAY_LANES
from specify_cli.workspace.context import resolve_workspace_for_wp

_logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------


class DecisionKind(StrEnum):
    """Canonical kind values for :class:`Decision` envelopes.

    Declared as a ``StrEnum`` so that:

    * Comparisons against raw strings (e.g. ``decision.kind == "terminal"``)
      continue to work without change — every member *is* its string value.
    * JSON serialisation of ``to_dict()`` is byte-identical to the pre-enum
      form: ``self.kind`` in the dict is the bare string value.
    * Type-checkers can now flag typos such as ``"terminl"`` at analysis time.

    Serialisation note: ``DecisionKind.step.value == "step"``.  With
    ``StrEnum``, ``str(DecisionKind.step) == "step"`` and
    ``json.dumps({"kind": DecisionKind.step}) == '{"kind": "step"}'``.
    The ``to_dict()`` method emits ``self.kind`` directly, which serialises
    as the bare string value — byte-identical to the pre-enum form.
    """

    step = "step"
    decision_required = "decision_required"
    blocked = "blocked"
    terminal = "terminal"
    query = "query"  # bare next call; state not advanced


# Canonical ``--result`` enum for a mission-step invocation outcome, shared
# by every caller that validates a raw ``--result``/``result`` string before
# it reaches the engine: the host CLI's ``next`` command
# (``specify_cli.cli.commands.next_cmd``) and the orchestrator-api's
# ``answer-decision`` verb (``specify_cli.orchestrator_api.decision_verbs``).
# Mirrors ``runtime.next._internal_runtime.engine.ResultType`` (a
# ``typing.Literal``, not a runtime enum, so it cannot itself be introspected
# for its member values) -- this tuple is the single source both CLI-facing
# validators import instead of each keeping an independent literal copy.
VALID_RESULT_VALUES: tuple[str, ...] = ("success", "failed", "blocked")


# ---------------------------------------------------------------------------
# Analysis currency (WP07, FR-016, C-001)
# ---------------------------------------------------------------------------
#
# The runtime may not import ``specify_cli.analysis_report``; the CLI wraps
# ``check_analysis_report_current`` in a callable and injects it through
# ``decide_next`` / ``query_current_state``. The bridge evaluates it only on the
# ``analyze`` step and in the finalized-board override that would hand out
# ``implement`` (it never reaches the pure cores module, B5).

#: ``Decision.error_code`` values of a software-dev ``analyze`` step re-issued
#: because the analysis report is not current.
ANALYSIS_REPORT_MISSING = "ANALYSIS_REPORT_MISSING"
ANALYSIS_REPORT_STALE = "ANALYSIS_REPORT_STALE"
#: No currency check reached the runtime, so the report cannot be judged: the
#: step fails closed instead of being treated as not evaluated.
ANALYSIS_CURRENCY_UNAVAILABLE = "ANALYSIS_CURRENCY_UNAVAILABLE"


@dataclass(frozen=True)
class AnalysisVerdict:
    """Whether the mission's analysis report is current.

    ``stale_inputs`` names one entry per stale input of a ``stale`` verdict (an
    input artifact whose hash moved, or the reason when no input is to blame).
    """

    status: Literal["current", "missing", "stale"]
    stale_inputs: tuple[str, ...] = ()


#: The injected currency check; it closes over the mission and repository.
AnalysisCurrency = Callable[[], AnalysisVerdict]


class InvalidStepDecision(ValueError):
    """Raised when a ``kind="step"`` ``Decision`` is constructed without a
    valid, on-disk-resolvable ``prompt_file``.

    See contracts C1/C2/C3 in
    ``kitty-specs/charter-e2e-827-followups-01KQAJA0/contracts/next-prompt-file-contract.md``:
    a ``kind="step"`` envelope MUST carry a non-null, non-empty ``prompt_file``
    that resolves on disk. ``null`` is legal only for non-step kinds.
    """


@dataclass
class Decision:
    kind: str  # one of DecisionKind.*
    agent: str | None
    mission_slug: str
    mission: str
    mission_state: str
    timestamp: str
    action: str | None = None
    wp_id: str | None = None
    workspace_path: str | None = None
    prompt_file: str | None = None
    reason: str | None = None
    guard_failures: list[str] = field(default_factory=list)
    # #3883: the path each failing guard actually read, so a blocked
    # result is diagnosable without a source read. Additive and
    # defaulted: ``guard_failures`` keeps its exact identity strings
    # (the SC-007 query/advance parity invariant compares those).
    guard_failure_paths: dict[str, str] = field(default_factory=dict)
    progress: dict | None = None
    origin: dict = field(default_factory=dict)
    # Runtime fields (added in v2.0.0)
    run_id: str | None = None
    step_id: str | None = None
    decision_id: str | None = None
    input_key: str | None = None
    question: str | None = None
    options: list[str] | None = None
    is_query: bool = False  # New: True when kind == DecisionKind.query
    preview_step: str | None = None
    mission_number: str | None = None
    mission_type: str | None = None
    # owned-checkout-lifecycle-authority WP11 (#4867, FR-012): the typed
    # OwnedRefusalCode a blocked owned-checkout decision carries, so a
    # caller routes on ``error_code`` rather than parsing ``reason`` text.
    # ``None`` for every decision that carries no typed refusal — including
    # every non-owned payload, which stays byte-identical (see ``to_dict``).
    error_code: str | None = None

    def __post_init__(self) -> None:
        """Enforce the ``kind="step"`` prompt-file contract at construction time.

        Contract (C1/C2 in
        ``kitty-specs/charter-e2e-827-followups-01KQAJA0/contracts/next-prompt-file-contract.md``):
        a ``kind="step"`` envelope MUST carry a non-null, non-empty
        ``prompt_file`` that resolves on disk. Non-step kinds (``blocked``,
        ``terminal``, ``decision_required``, ``query``) remain permissive —
        ``prompt_file=None`` is legal there.

        Raises :class:`InvalidStepDecision` (a :class:`ValueError`) on
        violation so the call site can ``try/except`` and route to a
        ``kind="blocked"`` envelope (Constraint C-005: do NOT weaken the
        ``kind="step"`` contract).
        """
        if self.kind == DecisionKind.step:
            prompt = self.prompt_file
            if not prompt:
                raise InvalidStepDecision("kind='step' requires a non-empty prompt_file; got None/empty")
            if not Path(prompt).is_file():
                raise InvalidStepDecision(f"kind='step' prompt_file must resolve on disk: {prompt!r} does not")

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "kind": self.kind,
            "agent": self.agent,
            **mission_identity_fields(
                self.mission_slug,
                self.mission_number,
                self.mission_type or self.mission,
            ),
            "mission": self.mission,
            "mission_state": self.mission_state,
            "timestamp": self.timestamp,
            "action": self.action,
            "wp_id": self.wp_id,
            "workspace_path": self.workspace_path,
            # kind='step' MUST carry a non-null prompt_file that resolves on
            # disk (see C1/C2 in
            # kitty-specs/charter-e2e-827-followups-01KQAJA0/contracts/next-prompt-file-contract.md).
            # null is legal only for non-step kinds.
            "prompt_file": self.prompt_file,
            "reason": self.reason,
            "guard_failures": self.guard_failures,
            "guard_failure_paths": self.guard_failure_paths,
            "progress": self.progress,
            "origin": self.origin,
            "run_id": self.run_id,
            "step_id": self.step_id,
            "decision_id": self.decision_id,
            "input_key": self.input_key,
            "question": self.question,
            "options": self.options,
            "is_query": self.is_query,
            "preview_step": self.preview_step,
        }
        # #4867 (FR-012): additive-only — emitted only when a typed owned
        # refusal is present, so every non-owned payload stays byte-identical.
        if self.error_code is not None:
            payload["error_code"] = self.error_code
        return payload


# ---------------------------------------------------------------------------
# WP progress helpers
# ---------------------------------------------------------------------------


def _get_wp_lanes(feature_dir: Path) -> dict[str, str]:
    """Return a mapping of wp_id -> canonical lane from the event log.

    Best-effort: routes through the canonical reader and returns ``{}`` when no
    canonical event log exists yet (#1775 Randy-Reducer F5 — this was a verbatim
    duplicate of ``get_all_wp_lanes`` minus the fail-loud guard).
    """
    from specify_cli.status import CanonicalStatusNotFoundError, get_all_wp_lanes

    try:
        return get_all_wp_lanes(feature_dir)
    except CanonicalStatusNotFoundError:
        return {}


def _compute_wp_progress(
    feature_dir: Path,
    *,
    status_dir: Path | None = None,
) -> dict[str, int | float] | None:
    """Compute WP lane counts and weighted progress for the progress field from the event log."""
    tasks_dir = feature_dir / "tasks"
    if not tasks_dir.is_dir():
        return None

    wp_files = sorted(tasks_dir.glob("WP*.md"))
    if not wp_files:
        return None

    lane_read_dir = status_dir if status_dir is not None else feature_dir
    wp_lanes = _get_wp_lanes(lane_read_dir)

    counts: dict[str, int | float] = {
        "total_wps": 0,
        "done_wps": 0,
        "approved_wps": 0,
        "in_progress_wps": 0,
        "planned_wps": 0,
        "for_review_wps": 0,
    }

    for wp_file in wp_files:
        counts["total_wps"] += 1
        wp_match = re.match(r"(WP\d+)", wp_file.stem)
        wp_id = wp_match.group(1) if wp_match else wp_file.stem
        # Default to GENESIS for unseeded WPs: they are not displayed in any
        # progress bucket until finalize-tasks seeds them (Contract 3, FR-008).
        lane = wp_lanes.get(wp_id, Lane.GENESIS)
        # Non-display lanes (genesis, uninitialized) belong in no progress
        # bucket — route through the single NON_DISPLAY_LANES authority rather
        # than inlining an `== Lane.GENESIS` check (total_wps above still counts
        # every WP file per the Contract-3 public-JSON contract).
        if lane in NON_DISPLAY_LANES:
            continue
        state = wp_state_for(lane)
        if state.lane == Lane.DONE:
            counts["done_wps"] += 1
        elif state.lane == Lane.APPROVED:
            counts["approved_wps"] += 1
        elif state.progress_bucket() == "in_flight" and not state.is_blocked:
            counts["in_progress_wps"] += 1
        elif state.progress_bucket() == "review":
            counts["for_review_wps"] += 1
        elif state.progress_bucket() == "not_started":
            counts["planned_wps"] += 1

    # Compute weighted progress from a PURE snapshot reduce (FR-017): this is
    # a query, so it must never rewrite the tracked status.json the way the
    # writing ``materialize`` does. The fallback is logged, not swallowed.
    try:
        from specify_cli.status import compute_weighted_progress
        from specify_cli.status import materialize_snapshot

        snapshot = materialize_snapshot(lane_read_dir)
        progress = compute_weighted_progress(snapshot)
        counts["weighted_percentage"] = round(progress.percentage, 1)
    except Exception as exc:
        _logger.warning("weighted progress unavailable for %s: %s", lane_read_dir, exc)

    return counts


def _find_first_wp_by_lane(
    feature_dir: Path,
    lane: str,
    *,
    status_dir: Path | None = None,
) -> str | None:
    """Find the first WP file with the given lane value (from event log).

    Accepts canonical lane strings (e.g. ``"planned"``) or legacy aliases
    (e.g. ``"doing"``).  Comparison is done via :func:`wp_state_for` so
    that aliases resolve to their canonical ``Lane`` enum member.
    """
    tasks_dir = feature_dir / "tasks"
    if not tasks_dir.is_dir():
        return None

    target_lane = wp_state_for(lane).lane

    lane_read_dir = status_dir if status_dir is not None else feature_dir
    wp_lanes = _get_wp_lanes(lane_read_dir)
    wp_files = sorted(tasks_dir.glob("WP*.md"))
    for wp_file in wp_files:
        wp_match = re.match(r"(WP\d+)", wp_file.stem)
        if wp_match is None:
            continue
        wp_id = wp_match.group(1)
        # Default to GENESIS for unseeded WPs: they are not claimable/findable
        # by any lane query until finalize-tasks seeds them (Contract 3, FR-008).
        wp_lane = wp_lanes.get(wp_id, Lane.GENESIS)
        # Non-display lanes cannot be found by a lane query — skip them via the
        # single NON_DISPLAY_LANES authority.
        if wp_lane in NON_DISPLAY_LANES:
            continue
        if wp_state_for(wp_lane).lane == target_lane:
            return wp_id
    return None


# ---------------------------------------------------------------------------
# Main decision function
# ---------------------------------------------------------------------------


def decide_next(
    agent: str,
    mission_slug: str,
    result: str,
    repo_root: Path,
    *,
    owned: OwnedCheckout | None = None,
    analysis_currency: AnalysisCurrency | None = None,
) -> Decision:
    """Decide the next action for an agent in the mission loop.

    Delegates to :func:`runtime_bridge.decide_next_via_runtime` which uses
    the CLI-internal runtime's DAG planner
    (``runtime.next._internal_runtime.planner``) for step resolution
    and manages run state locally under ``.kittify/runtime/runs/``.

    The canonical agent loop is::

        while True:
            decision = spec-kitty next --agent X --json
            if decision.kind == "terminal": break
            execute(decision.prompt_file)

    ``analysis_currency`` is the injected analysis-report check (WP07, FR-016):
    the bridge reads it only on the software-dev ``analyze`` step and in the
    finalized-board override that would hand out ``implement``; ``None`` there
    fails closed with ``ANALYSIS_CURRENCY_UNAVAILABLE``.
    """
    from runtime.next.runtime_bridge import decide_next_via_runtime

    # Forwarded only when injected, so a caller (or a test double) that never
    # supplies a check sees the exact pre-WP07 call.
    injected: dict[str, AnalysisCurrency] = {} if analysis_currency is None else {"analysis_currency": analysis_currency}
    decision = decide_next_via_runtime(
        agent,
        mission_slug,
        result,
        repo_root,
        owned=owned,
        **injected,
    )
    return _with_guard_failure_paths(decision, repo_root, owned=owned)


def _with_guard_failure_paths(decision: Decision, repo_root: Path, *, owned: OwnedCheckout | None = None) -> Decision:
    """Attach the path each failing guard read, keyed by the real artifact
    tag (#3883, #4390).

    A blocked decision that names an artifact but not the directory it was
    read from is not diagnosable without a source read — the reported
    query-vs-advance disagreement was unrecoverable for exactly that reason.
    The paths come from ``runtime_bridge_io.guard_failure_artifact_paths``,
    which resolves the same placement seam ``gather_artifact_presence`` uses
    for its own reads, so this reports where the guard actually looked rather
    than a second guess at it.

    #4390: ``guard_failures`` is keyed by real artifact tag, not by the raw
    failure string — every registered mission family's guard table
    (software-dev/research/documentation/plan) reports genuine
    artifact-presence failures as human-readable MESSAGES
    (``"Required artifact missing: {name}"``), not filenames, and mixes them
    with free-form non-artifact failures (WP status, source counts, ...).
    Keying by the raw string (the pre-#4390 shape) fabricated a "looked for"
    path for every failure indiscriminately. ``guard_failure_artifact_paths``
    resolves the real tag for each failure and only emits an entry for a
    genuine artifact-presence failure; the render (``next_cmd.py``) iterates
    the resulting tags directly, never ``decision.guard_failures``.

    Root discipline (owned-checkout-lifecycle-authority WP11): for an owned
    mission the paths are resolved from the mission's own home on P through
    the same owned placement seam the guards read, never from the repository
    root checkout R.

    Reporting must never change the outcome: any failure to resolve leaves the
    decision exactly as the runtime produced it.
    """
    if not decision.guard_failures or decision.guard_failure_paths:
        return decision
    try:
        from runtime.next.runtime_bridge import get_mission_type
        from runtime.next.runtime_bridge_identity import _resolve_runtime_feature_dir
        from runtime.next.runtime_bridge_io import guard_failure_artifact_paths

        if owned is None:
            feature_dir = _resolve_runtime_feature_dir(repo_root, decision.mission_slug)
        else:
            from mission_runtime import MissionArtifactKind, mission_context_for

            context = mission_context_for(repo_root, decision.mission_slug, owned=owned)
            status_dir = context.artifact(MissionArtifactKind.STATUS_STATE).read_dir
            feature_dir = status_dir if status_dir.is_dir() else context.artifact(MissionArtifactKind.PRIMARY_METADATA).read_dir
        decision.guard_failure_paths = guard_failure_artifact_paths(
            feature_dir,
            mission_family=decision.mission or get_mission_type(feature_dir),
            repo_root=repo_root,
            guard_failures=decision.guard_failures,
            owned=owned,
        )
    except Exception as exc:  # noqa: BLE001 — diagnostics must never break a decision
        _logger.debug("guard-failure paths unavailable for %s: %s", decision.mission_slug, exc)
    return decision


# ---------------------------------------------------------------------------
# State-to-action mapping
# ---------------------------------------------------------------------------


# Known aliases (maps mission-specific state names to standard templates).
# Module-level (T066 campsite extraction) so both `_state_to_action` and
# `_template_state_action` share the one definition (Sonar S1192).
_STATE_ALIASES: dict[str, str] = {
    "discovery": "research",
    "scoping": "specify",
    "methodology": "plan",
    "tasks_outline": "tasks-outline",
    "tasks_packages": "tasks-packages",
    "tasks_finalize": "tasks-finalize",
    "gathering": "implement",
    "synthesis": "review",
    "output": "accept",
    "goals": "specify",
    "structure": "plan",
    "draft": "plan",
}


def _implement_state_action(
    mission_slug: str,
    feature_dir: Path,
    repo_root: Path,
    *,
    owned: OwnedCheckout | None = None,
) -> tuple[str | None, str | None, str | None]:
    """Campsite extraction (T066) of ``_state_to_action``'s ``"implement"``
    branch: the dependency-aware planned-WP authority (#4860), falling back
    to a claimable review WP. Behaviour-preserving."""
    from runtime.next.discovery import preview_claimable_wp

    wp_id = preview_claimable_wp(feature_dir).wp_id
    if wp_id is None:
        wp_id = _find_first_wp_by_lane(feature_dir, "doing")
    if wp_id is None:
        wp_id = _find_first_wp_by_lane(feature_dir, "in_progress")

    if wp_id is None:
        # No implementable WPs — check for reviewable ones.
        # Only for_review WPs are available for pickup; in_review WPs
        # are already claimed by another reviewer and must NOT be
        # reassigned (FR-012a).
        review_wp = _find_first_wp_by_lane(feature_dir, "for_review")
        if review_wp:
            workspace_path = str(resolve_workspace_for_wp(repo_root, mission_slug, review_wp, owned=owned).worktree_path)
            return "review", review_wp, workspace_path
        # in_review WPs exist but are not actionable by this agent —
        # review is already in progress, nothing to pick up.
        return None, None, None

    workspace_path = str(resolve_workspace_for_wp(repo_root, mission_slug, wp_id, owned=owned).worktree_path)
    return "implement", wp_id, workspace_path


def _review_state_action(
    mission_slug: str,
    feature_dir: Path,
    repo_root: Path,
    *,
    owned: OwnedCheckout | None = None,
) -> tuple[str | None, str | None, str | None] | None:
    """Campsite extraction (T066) of ``_state_to_action``'s ``"review"``
    branch. Returns ``None`` to signal fall-through to generic template
    resolution (no claimable ``for_review`` WP). Behaviour-preserving."""
    wp_id = _find_first_wp_by_lane(feature_dir, "for_review")
    if wp_id is not None:
        workspace_path = str(resolve_workspace_for_wp(repo_root, mission_slug, wp_id, owned=owned).worktree_path)
        return "review", wp_id, workspace_path
    # Explicitly skip in_review WPs — they are claimed by another
    # reviewer (FR-012a). Fall through to generic template resolution.
    return None


def _template_state_action(
    state: str,
    repo_root: Path,
    mission_name: str,
    *,
    owned: OwnedCheckout | None = None,
) -> tuple[str | None, str | None, str | None]:
    """Campsite extraction (T066) of ``_state_to_action``'s generic
    template + alias resolution. Behaviour-preserving.

    A command template is a P-local governance read (owned-checkout-
    lifecycle-authority WP11 / #5009 e6923bc97): ``resolve_command`` reads
    ``owned.owned_root`` when this call runs under an owned checkout.
    """
    from specify_cli.runtime.resolver import resolve_command

    template_root = owned.owned_root if owned is not None else repo_root
    try:
        resolve_command(f"{state}.md", template_root, mission=mission_name)
        return state, None, None
    except FileNotFoundError:
        pass

    alias = _STATE_ALIASES.get(state)
    if alias:
        # Registered consumer skills (CLI-driven shims or prompt-driven
        # commands) are known to the shim registry and do not require a
        # resolvable template file to be considered valid.
        from specify_cli.shims.registry import is_cli_driven, is_prompt_driven

        if is_cli_driven(alias) or is_prompt_driven(alias):
            return alias, None, None
        try:
            resolve_command(f"{alias}.md", template_root, mission=mission_name)
            return alias, None, None
        except FileNotFoundError:
            pass

    return None, None, None


def _state_to_action(
    state: str,
    mission_slug: str,
    feature_dir: Path,
    repo_root: Path,
    mission_name: str,
    *,
    owned: OwnedCheckout | None = None,
) -> tuple[str | None, str | None, str | None]:
    """Map a mission state to a ``(action, wp_id, workspace_path)`` triple.

    Returns ``(None, None, None)`` if the state cannot be mapped to a
    command template. A 4-way dispatch over ``_implement_state_action``,
    ``_review_state_action``, the ``"done"`` terminal, and
    ``_template_state_action`` (T066 campsite extraction).
    """
    # "implement" state: use the same dependency-aware planned-WP authority
    # as query mode and ``agent action implement`` (#4860). Filename/lane order
    # alone cannot make a dependency-blocked package actionable.
    if state == "implement":
        return _implement_state_action(mission_slug, feature_dir, repo_root, owned=owned)

    # "review" state: WP-level if for_review WP exists, else template-level.
    # in_review WPs are already being reviewed by another agent and must
    # NOT be reassigned — only for_review WPs are available for pickup.
    if state == "review":
        review_action = _review_state_action(mission_slug, feature_dir, repo_root, owned=owned)
        if review_action is not None:
            return review_action
        # Fall through to generic template resolution below.

    # "done" state -- terminal, no action
    if state == "done":
        return "accept", None, None

    return _template_state_action(state, repo_root, mission_name, owned=owned)


def _build_prompt_safe(
    action: str,
    feature_dir: Path,
    mission_slug: str,
    wp_id: str | None,
    agent: str,
    repo_root: Path,
    mission_type: str,
    *,
    owned: OwnedCheckout | None = None,
) -> str | None:
    """Build prompt, returning None on failure instead of raising.

    .. deprecated::
        Prefer :func:`_build_prompt_or_error` which surfaces the underlying
        exception text so callers can emit a structured ``blocked`` decision
        with a populated ``reason`` (WP06 / FR-006 / FR-013).
    """
    path, _err, _error_code = _build_prompt_or_error(
        action=action,
        feature_dir=feature_dir,
        mission_slug=mission_slug,
        wp_id=wp_id,
        agent=agent,
        repo_root=repo_root,
        mission_type=mission_type,
        owned=owned,
    )
    return path


def _write_templateless_step_prompt(
    action: str,
    mission_slug: str,
    agent: str,
    mission_type: str,
    repo_root: Path,
    owned: OwnedCheckout | None,
) -> str:
    """Write an actionable prompt for a non-WP step that has no prompt template.

    Names the step, tells the agent to perform it per the Mission's charter and
    spec, and gives the exact next command including the Mission selector.
    """
    config_root = owned.owned_root if owned is not None else repo_root
    prompt = (
        f"# {mission_type} — {action}\n\n"
        f"Perform the `{action}` step for this Mission according to its charter and spec.\n\n"
        f"When the step is done, advance with:\n\n"
        f"    spec-kitty next --agent {agent} --mission {mission_slug}\n"
    )
    fd, path = tempfile.mkstemp(prefix=f"spec-kitty-step-{action}-", suffix=".md", dir=prompt_tmp_dir(config_root))
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(prompt)
    return path


def _build_prompt_or_error(
    action: str,
    feature_dir: Path,
    mission_slug: str,
    wp_id: str | None,
    agent: str,
    repo_root: Path,
    mission_type: str,
    *,
    owned: OwnedCheckout | None = None,
) -> tuple[str | None, str | None, str | None]:
    """Build prompt, returning ``(path, None, None)`` on success or
    ``(None, error, error_code)`` on failure.

    The ``error`` message is suitable for embedding in a ``blocked`` decision's
    ``reason`` so callers can avoid emitting a ``kind=step`` decision with a
    null/missing ``prompt_file`` (WP06 / FR-006 / FR-013).

    ``error_code`` carries a typed :class:`~mission_runtime.OwnedRefusalCode`
    value (as a string) when the failure originated from a typed
    :class:`~mission_runtime.ActionContextError` raised by ``build_prompt``'s
    owned-aware resolution path (T067 item 4); it is ``None`` for every other
    failure so ``next``'s JSON contract gets a structured ``error_code``
    without ever having to parse the ``reason`` text.

    The path is also verified to exist on disk; if ``build_prompt`` returned a
    path that does not resolve, ``error`` is populated and ``path`` is ``None``.

    Steps resolve their real mission-step prompt through ``build_prompt``. A
    non-WP step that genuinely has no prompt template (a workflow-inserted
    step such as ``design-review``, or ``discovery``) gets a short actionable
    prompt naming the step and the exact next command. Any other unresolvable
    prompt makes the caller emit a blocked decision with the failure reason.
    """
    try:
        from runtime.next.prompt_builder import build_prompt

        # The fact rides down to the prompt builder (WP12): an owned prompt reads
        # the WP file, workspace, governance and its own temp file from the
        # owned checkout, never from ``repo_root``.
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            _, prompt_path = build_prompt(
                action=action,
                feature_dir=feature_dir,
                mission_slug=mission_slug,
                wp_id=wp_id,
                agent=agent,
                repo_root=repo_root,
                mission_type=mission_type,
                owned=owned,
            )
        path_str = str(prompt_path)
        try:
            if not Path(path_str).exists():
                return None, (f"prompt template did not materialize on disk for action '{action}' (path={path_str})"), None
        except OSError as exc:
            return None, (f"prompt template path is not stat-able for action '{action}': {exc}"), None
        return path_str, None, None
    except FileNotFoundError as exc:
        if wp_id is None:
            return _write_templateless_step_prompt(action, mission_slug, agent, mission_type, repo_root, owned), None, None
        return None, (f"no actionable prompt template for {mission_type}/{action}: {exc}"), None
    except ActiveCharterConfigError as exc:
        # A corrupt/unreadable ``.kittify/config.yaml`` (bad encoding or
        # malformed YAML) is an operator-facing configuration fault, not an
        # internal crash. Surface the fail-loud body verbatim (it names the
        # offending file and the decode/parse cause) so the blocked decision
        # renders without a Python traceback or a raw exception class name.
        # ``str(exc)`` would yield only the machine code, so use ``exc.body``.
        return None, exc.body, None
    except ActionContextError as exc:
        # T067 item 4: build_prompt's owned-aware resolution path (WP12)
        # raises the typed ActionContextError contract. Carry its code on
        # error_code so ``next``'s JSON contract gets a structured refusal
        # without the caller having to parse ``reason`` text (T062's
        # Decision.error_code contract).
        return None, str(exc), exc.code
    except Exception as exc:
        return None, (f"prompt resolution failed for action '{action}': {type(exc).__name__}: {exc}"), None
