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
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

from charter.activation.pack_context import CharterPackConfigError
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
# ``answer-decision`` verb (``specify_cli.orchestrator_api.commands``).
# Mirrors ``runtime.next._internal_runtime.engine.ResultType`` (a
# ``typing.Literal``, not a runtime enum, so it cannot itself be introspected
# for its member values) -- this tuple is the single source both CLI-facing
# validators import instead of each keeping an independent literal copy.
VALID_RESULT_VALUES: tuple[str, ...] = ("success", "failed", "blocked")


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
        return {
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
    effective_root: Path | None = None,
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
    """
    from runtime.next.runtime_bridge import decide_next_via_runtime

    if effective_root is None:
        decision = decide_next_via_runtime(agent, mission_slug, result, repo_root)
    else:
        decision = decide_next_via_runtime(agent, mission_slug, result, repo_root, effective_root=effective_root)
    return _with_guard_failure_paths(decision, repo_root)


def _with_guard_failure_paths(decision: Decision, repo_root: Path) -> Decision:
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

    Reporting must never change the outcome: any failure to resolve leaves the
    decision exactly as the runtime produced it.
    """
    if not decision.guard_failures or decision.guard_failure_paths:
        return decision
    try:
        from runtime.next.runtime_bridge import _resolve_runtime_feature_dir, get_mission_type
        from runtime.next.runtime_bridge_io import guard_failure_artifact_paths

        feature_dir = _resolve_runtime_feature_dir(repo_root, decision.mission_slug)
        decision.guard_failure_paths = guard_failure_artifact_paths(
            feature_dir,
            mission_family=decision.mission or get_mission_type(feature_dir),
            repo_root=repo_root,
            guard_failures=decision.guard_failures,
        )
    except Exception as exc:  # noqa: BLE001 — diagnostics must never break a decision
        _logger.debug("guard-failure paths unavailable for %s: %s", decision.mission_slug, exc)
    return decision


# ---------------------------------------------------------------------------
# State-to-action mapping
# ---------------------------------------------------------------------------


def _state_to_action(
    state: str,
    mission_slug: str,
    feature_dir: Path,
    repo_root: Path,
    mission_name: str,
) -> tuple[str | None, str | None, str | None]:
    """Map a mission state to a ``(action, wp_id, workspace_path)`` triple.

    Returns ``(None, None, None)`` if the state cannot be mapped to a
    command template.
    """
    # "implement" state: use the same dependency-aware planned-WP authority
    # as query mode and ``agent action implement`` (#4860). Filename/lane order
    # alone cannot make a dependency-blocked package actionable.
    if state == "implement":
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
                workspace_path = str(resolve_workspace_for_wp(repo_root, mission_slug, review_wp).worktree_path)
                return "review", review_wp, workspace_path
            # in_review WPs exist but are not actionable by this agent —
            # review is already in progress, nothing to pick up.
            in_review_wp = _find_first_wp_by_lane(feature_dir, "in_review")
            if in_review_wp:
                return None, None, None
            return None, None, None

        workspace_path = str(resolve_workspace_for_wp(repo_root, mission_slug, wp_id).worktree_path)
        return "implement", wp_id, workspace_path

    # "review" state: WP-level if for_review WP exists, else template-level.
    # in_review WPs are already being reviewed by another agent and must
    # NOT be reassigned — only for_review WPs are available for pickup.
    if state == "review":
        wp_id = _find_first_wp_by_lane(feature_dir, "for_review")
        if wp_id is not None:
            workspace_path = str(resolve_workspace_for_wp(repo_root, mission_slug, wp_id).worktree_path)
            return "review", wp_id, workspace_path
        # Explicitly skip in_review WPs — they are claimed by another
        # reviewer (FR-012a).  Fall through to generic template resolution.
        # Note: _find_first_wp_by_lane(feature_dir, "in_review") is
        # intentionally not called here because we don't act on it.

    # "done" state -- terminal, no action
    if state == "done":
        return "accept", None, None

    # Generic: try state name as command template, then known aliases
    from specify_cli.runtime.resolver import resolve_command

    try:
        resolve_command(f"{state}.md", repo_root, mission=mission_name)
        return state, None, None
    except FileNotFoundError:
        pass

    # Known aliases (maps mission-specific state names to standard templates)
    _ALIASES: dict[str, str] = {
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
    alias = _ALIASES.get(state)
    if alias:
        # Registered consumer skills (CLI-driven shims or prompt-driven
        # commands) are known to the shim registry and do not require a
        # resolvable template file to be considered valid.
        from specify_cli.shims.registry import is_cli_driven, is_prompt_driven

        if is_cli_driven(alias) or is_prompt_driven(alias):
            return alias, None, None
        try:
            resolve_command(f"{alias}.md", repo_root, mission=mission_name)
            return alias, None, None
        except FileNotFoundError:
            pass

    return None, None, None


def _build_prompt_safe(
    action: str,
    feature_dir: Path,
    mission_slug: str,
    wp_id: str | None,
    agent: str,
    repo_root: Path,
    mission_type: str,
) -> str | None:
    """Build prompt, returning None on failure instead of raising.

    .. deprecated::
        Prefer :func:`_build_prompt_or_error` which surfaces the underlying
        exception text so callers can emit a structured ``blocked`` decision
        with a populated ``reason`` (WP06 / FR-006 / FR-013).
    """
    path, _err = _build_prompt_or_error(
        action=action,
        feature_dir=feature_dir,
        mission_slug=mission_slug,
        wp_id=wp_id,
        agent=agent,
        repo_root=repo_root,
        mission_type=mission_type,
    )
    return path


def _build_prompt_or_error(
    action: str,
    feature_dir: Path,
    mission_slug: str,
    wp_id: str | None,
    agent: str,
    repo_root: Path,
    mission_type: str,
) -> tuple[str | None, str | None]:
    """Build prompt, returning ``(path, None)`` on success or ``(None, error)``.

    The ``error`` message is suitable for embedding in a ``blocked`` decision's
    ``reason`` so callers can avoid emitting a ``kind=step`` decision with a
    null/missing ``prompt_file`` (WP06 / FR-006 / FR-013).

    The path is also verified to exist on disk; if ``build_prompt`` returned a
    path that does not resolve, ``error`` is populated and ``path`` is ``None``.

    For composed actions (documentation ``discover``, ``audit``, … and their
    equivalents in research / software-dev missions), no file-based prompt
    template exists — dispatch happens through the composition layer.  Rather
    than returning ``(None, error)`` and causing ``_map_runtime_decision`` to
    emit a ``blocked`` decision, this function writes a minimal marker file so
    the ``kind=step`` invariant is satisfied (FR-007 / T019).
    """
    # Fast path: composed actions do not use file-based templates.  Write a
    # lightweight marker file and return its path so callers can emit a
    # ``kind=step`` Decision without hitting the ``if prompt_file is None``
    # blocked branch in ``_map_runtime_decision``.
    _is_composed_action = False
    try:
        from charter.activation.mission_type_profiles import (  # noqa: PLC0415
            resolve_mission_type_context,
        )

        action_sequence = resolve_mission_type_context(repo_root, mission_type=mission_type).action_sequence
        _is_composed_action = wp_id is None and action in action_sequence
    except Exception:
        pass
    if _is_composed_action:
        composed_prompt = f"# {mission_type} — {action}\n\nThis step is dispatched via composition.\nRun `spec-kitty next --agent <name>` to advance.\n"
        marker_fd, marker_path = tempfile.mkstemp(
            prefix=f"spec-kitty-composed-{action}-",
            suffix=".md",
            dir=prompt_tmp_dir(repo_root),
        )
        os.write(marker_fd, composed_prompt.encode("utf-8"))
        os.close(marker_fd)
        return marker_path, None

    try:
        from runtime.next.prompt_builder import build_prompt

        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            _, prompt_path = build_prompt(
                action=action,
                feature_dir=feature_dir,
                mission_slug=mission_slug,
                wp_id=wp_id,
                agent=agent,
                repo_root=repo_root,
                mission_type=mission_type,
            )
        path_str = str(prompt_path)
        try:
            if not Path(path_str).exists():
                return None, (f"prompt template did not materialize on disk for action '{action}' (path={path_str})")
        except OSError as exc:
            return None, (f"prompt template path is not stat-able for action '{action}': {exc}")
        return path_str, None
    except FileNotFoundError:
        # No file-based template for this non-WP step (e.g. workflow-inserted
        # steps like ``design-review``, or global-runtime steps like
        # ``discovery`` that have no mission-step prompt file).  Rather than
        # returning an error and causing ``_map_runtime_decision`` to emit a
        # ``kind=blocked`` decision, write a minimal composition marker so the
        # ``kind=step`` invariant is satisfied (FR-007 / T019).
        if wp_id is None:
            composed_prompt = f"# {mission_type} — {action}\n\nThis step is dispatched via composition.\nRun `spec-kitty next --agent <name>` to advance.\n"
            marker_fd, marker_path = tempfile.mkstemp(
                prefix=f"spec-kitty-composed-{action}-",
                suffix=".md",
                dir=prompt_tmp_dir(repo_root),
            )
            os.write(marker_fd, composed_prompt.encode("utf-8"))
            os.close(marker_fd)
            return marker_path, None
        return None, (f"prompt resolution failed for action '{action}': FileNotFoundError: no template found")
    except CharterPackConfigError as exc:
        # A corrupt/unreadable ``.kittify/config.yaml`` (bad encoding or
        # malformed YAML) is an operator-facing configuration fault, not an
        # internal crash. Surface the fail-loud body verbatim (it names the
        # offending file and the decode/parse cause) so the blocked decision
        # renders without a Python traceback or a raw exception class name.
        # ``str(exc)`` would yield only the machine code, so use ``exc.body``.
        return None, exc.body
    except Exception as exc:
        return None, (f"prompt resolution failed for action '{action}': {type(exc).__name__}: {exc}")
