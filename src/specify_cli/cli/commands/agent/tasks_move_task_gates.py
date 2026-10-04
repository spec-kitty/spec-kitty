"""The ``move-task`` transition-gate seam, extracted from ``tasks_move_task`` (#5629).

The pre-review regression gate and the inverted transition-gate hook — gate
binding resolution, scope/baseline resolution, gate dispatch, verdict
aggregation and translation into a :class:`_TransitionGateEffect`, and the
byproduct enrolment — are gate *policy*, not CLI parsing or presentation. They
moved here VERBATIM out of the 3,786-LOC ``tasks_move_task`` god-module; no
behaviour changed.

**Compat surface.** ``tasks_move_task`` re-imports every public symbol of this
module in the explicit ``as`` re-export form, so ``tasks_move_task.<name>``
(and, through it, ``tasks.<name>``) still resolves. The ``_do_move_task`` call
site still calls ``tasks_move_task._mt_run_pre_review_gate`` by name, so a
monkeypatch on that symbol keeps intercepting. A patch that must intercept a
call made *inside* the gate family targets this module instead.

**Seam bridge.** Patched ``tasks`` seam symbols are still reached through the
lazy in-function ``from specify_cli.cli.commands.agent import tasks as _tasks``
import, exactly as before the move. ``_MoveTaskState`` is imported for typing
only, and ``_lane_deliverable_paths`` lazily, so this module never imports
``tasks_move_task`` at module scope (no import cycle).
"""

from __future__ import annotations

import warnings
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from kernel.git import GitCommandError, status_entries
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import typer

if TYPE_CHECKING:
    from specify_cli.cli.commands.agent.tasks_move_task import _MoveTaskState
    from collections.abc import Sequence

    from charter.offering.missions.step_contracts import GateBinding

from mission_runtime import MissionArtifactKind, placement_seam
from specify_cli.cli.commands.agent.tasks_materialization import (
    _resolve_wp_slug,
)
from specify_cli.coordination.atomic_write import (
    enroll_subprocess_byproducts,
    restore_generated_artifact_snapshots,
    subprocess_created_paths,
)
from specify_cli.core.env import pre_review_gate_skip_reason
from specify_cli.core.vcs.git import merge_base_changed_files
from specify_cli.review import pre_review_gate
from specify_cli.review.baseline import BaselineTestResult
from specify_cli.review.gate_bindings import (
    GateBindingResolution,
    resolve_gate_bindings_for_transition,
    resolve_mission_type,
)
from specify_cli.review.gate_registry import (
    GateHandler,
    TransitionGateContext,
    get_gate_handler,
)
from specify_cli.review.scope_source import ScopeSource, resolve_scope_source
from specify_cli.review.verdict_aggregation import (
    AggregateDecision,
    aggregate_verdicts,
)
from specify_cli.status import (
    Lane,
)
from specify_cli.task_utils import (
    extract_scalar,
)


# --- phase C.5: pre-review regression gate (WP02 T004/T005, FR-001/FR-004) ---
#
# Mission review-regression-gate-01KWX6DF WP02: wires WP01's engine
# (``review/pre_review_gate.py`` — ``evaluate_pre_review_gate`` +
# ``run_scoped_tests_at_head`` + reused ``review/baseline.py`` JUnit
# parser/``diff_baseline``) into the ``for_review`` transition. Warn by
# default (NFR-001); opt-in block via config
# ``review.fail_on_pre_review_regression``; ``--force`` bypasses the block
# and is recorded on the transition's ``policy_metadata`` (FR-004).
#
# The composition helper below (``_mt_pre_review_gate_with_override_scope``)
# calls ONLY WP01's already-public primitives (``evaluate_with_scope``, the
# ``GateVerdict``/``ScopeResult`` dataclasses) — it lives here, not in
# ``review/pre_review_gate.py``, because that module is WP01's owned surface
# (outside this WP's ``owned_files``): the override-scope tier needs a
# manually-built ``ScopeResult`` that the engine has no seam for, so its tail
# (head-run -> ``diff_baseline``) is mirrored rather than threaded through a
# WP01 signature change. (The sibling census-derived composition helper,
# ``_mt_pre_review_gate_verdict``, was dead code with no production call site
# — retired by mission scopesource-gate-followup-01KY6S9P WP04, FR-002.)

_PRE_REVIEW_CONFIG_KEY_BLOCK = "fail_on_pre_review_regression"
_PRE_REVIEW_CONFIG_KEY_TEST_COMMAND = "pre_review_test_command"
_PRE_REVIEW_CONFIG_KEY_TEST_COMMAND_REPLACEMENT = "test_command"
_PRE_REVIEW_FRONTMATTER_KEY = "pre_review_test_scope"

#: T043 (FR-011): the legacy ``review.pre_review_test_command`` key is aliased to
#: the ``ScopeSource`` single test-command authority (``review.test_command``).
#: Its name always lied about its axis (squad C-C3) — it fed scope *targets*, not
#: a command. Under the inverted, doctrine-resolved gate the ``ScopeSource`` is
#: the single authority, so a config that still sets the old key keeps working
#: but earns a ONE-TIME deprecation warning (guarded by the module flag below) —
#: never a silent break for existing consumer configs.
_PRE_REVIEW_TEST_COMMAND_DEPRECATION = (
    "review.pre_review_test_command is deprecated; the inverted pre-review gate "
    "resolves its test command from the ScopeSource single authority "
    "(review.test_command). The old key is still honored — move the value to "
    "review.test_command to silence this notice."
)
#: One-shot latch so the deprecation warning fires at most once per process, not
#: on every ``for_review`` transition (T043).
_pre_review_test_command_deprecation_emitted = False


def _pre_review_gate_filter_groups() -> Mapping[str, tuple[str, ...]] | None:
    """Compatibility test seam: production always returns ``None``.

    The workflow-derived scope source was retired. The value is still threaded
    through ``_mt_resolve_scope_source`` for call-site compatibility, but
    ``resolve_scope_source`` ignores it and always resolves
    ``DeclaredCommandScopeSource``.
    """
    return None


def _pre_review_gate_composite_routing() -> Mapping[str, pre_review_gate._CompositeRoute] | None:
    """Compatibility seam sibling to :func:`_pre_review_gate_filter_groups`."""
    return None


def _mt_review_config_section(main_repo_root: Path) -> Mapping[str, Any]:
    """Best-effort read of the ``review:`` section of ``.kittify/config.yaml``.

    Mirrors ``review/baseline.py``'s ``_get_test_command`` read pattern
    exactly: a missing file, malformed YAML, or absent section all degrade to
    an empty mapping rather than raising — config lookup must never crash a
    transition.
    """
    config_path = main_repo_root / ".kittify" / "config.yaml"
    if not config_path.exists():
        return {}
    try:
        from ruamel.yaml import YAML

        yaml = YAML()
        config = yaml.load(config_path)
    except Exception:
        return {}
    if not config:
        return {}
    review_section = config.get("review") if hasattr(config, "get") else None
    return dict(review_section) if review_section else {}


def _mt_pre_review_block_enabled(main_repo_root: Path) -> bool:
    """FR-001/NFR-001: opt-in block toggle — ``review.fail_on_pre_review_regression``."""
    return bool(_mt_review_config_section(main_repo_root).get(_PRE_REVIEW_CONFIG_KEY_BLOCK, False))


def _mt_pre_review_gate_declared(scope_source_root: Path) -> bool:
    """#3821: does this repo declare anything for a bound gate to run?

    Asks the SAME activation-selected ``ScopeSource`` the dispatch would use
    (:func:`_mt_resolve_scope_source` — the single test-command authority,
    FR-011): a source with a runnable command means the gate is declared and
    fires normally. A source with NO command is undeclared — the
    ``spec-kitty init`` consumer default — so the built-in
    ``software-dev`` review contract's gate binding must not run there.
    #2598 closed #2534 on the premise that "a consumer repo that has not
    declared it" never activates the binding — but the binding ships built-in
    on that very contract, so every consumer repo activates it (#3821); the
    source's own command is the one signal the join cannot fake.

    A repo that declares the ``review.test_command`` key at all — even
    present-but-empty, or a malformed template the source refuses to render —
    still counts as declared, via a config-key **presence** fallback (NOT the
    FR-011 authority: a raw config read, so a started-but-unconfigured gate is
    not collapsed into "never declared"). Dispatch then surfaces the engine's
    visible ``no test command configured`` warn, which a broken or empty
    declaration deserves — never a quiet skip. Only a truly-absent key (the
    ``spec-kitty init`` consumer default) is undeclared.

    Cost note (squad NOTE on #4803, folded): this probe builds its own
    throwaway ``DeclaredCommandScopeSource``, and any ``test_command()`` call
    that reaches command rendering evaluates that instance's ``_output_file``
    cached_property — an immediate ``mkdtemp`` — so a DECLARED repo pays one
    extra tempdir per ``for_review`` transition on top of the dispatch's own
    instance. Deliberately accepted: the class already documents the tempdir
    as a per-run leak rather than threading teardown through a frozen
    dataclass, and avoiding the second instance would mean re-deriving
    ``review.test_command`` config semantics outside the single FR-011
    authority this probe exists to ask. Undeclared repos — the case #3821
    exists for — return ``None`` before command rendering and pay nothing.
    """
    if _mt_resolve_scope_source(scope_source_root).test_command() is not None:
        return True
    return _PRE_REVIEW_CONFIG_KEY_TEST_COMMAND_REPLACEMENT in _mt_review_config_section(scope_source_root)


def _mt_pre_review_gate_env_disable_reason() -> str | None:
    """#3980: the gate's own opt-out env, or ``None`` if not set.

    The gate reads ``SPEC_KITTY_SKIP_PRE_REVIEW_GATE`` — its own name — and
    no longer the sync-disable vocabulary: disarming sync must not silently
    skip a review gate. See ``core.env.pre_review_gate_skip_reason``.
    """
    # ``pre_review_gate_skip_reason`` surfaces as ``Any`` under this quarantined
    # module's ``follow_imports = "skip"``; pin the known concrete return type via
    # an annotated local rather than a suppression (mirrors the workspace resolver).
    reason: str | None = pre_review_gate_skip_reason()
    return reason


def _mt_pre_review_gate_skip_reason(st: _MoveTaskState) -> str | None:
    """#2573 FR-002: why the gate should be skipped this move, or ``None`` to run it.

    The ``--skip-pre-review-gate`` flag is checked first (an explicit, per-
    invocation opt-out); ``SPEC_KITTY_SKIP_PRE_REVIEW_GATE`` is checked
    second (the gate's own process-wide opt-out, #3980 — it no longer reads
    the sync-disable vocabulary). Either one skips
    the gate WITHOUT ever resolving a workspace or spawning the scoped
    pytest subprocess — the default (neither set) still runs/enforces the
    gate exactly as before this fix.
    """
    if st.skip_pre_review_gate:
        return "--skip-pre-review-gate flag"
    return _mt_pre_review_gate_env_disable_reason()


def _mt_pre_review_scope_override(wp_frontmatter: str, main_repo_root: Path) -> tuple[str, ...] | None:
    """FR-004 override precedence: frontmatter > config > ``None`` (auto-scope).

    Precedence is frontmatter ``pre_review_test_scope`` > config
    ``review.pre_review_test_command`` > ``None`` (WP01's census-derived
    auto-scope). Both override surfaces hold a whitespace-separated list of
    pytest target arguments — the SAME shape
    ``pre_review_gate.run_scoped_tests_at_head`` already consumes — so only
    WHICH targets run is overridable; the runner mechanics (head-side pytest
    + ``diff_baseline``) stay WP01's regardless of precedence tier.
    """
    frontmatter_value = extract_scalar(wp_frontmatter, _PRE_REVIEW_FRONTMATTER_KEY)
    if frontmatter_value:
        return tuple(frontmatter_value.split())
    config_value = _mt_review_config_section(main_repo_root).get(_PRE_REVIEW_CONFIG_KEY_TEST_COMMAND)
    if config_value:
        return tuple(str(config_value).split())
    return None


def _mt_resolve_pre_review_workspace(st: _MoveTaskState) -> Path | None:
    """Resolve the on-disk worktree the WP's code changes live in.

    Returns ``None`` when no genuine workspace is resolvable (planning-lane
    WP, missing ``lanes.json``, a worktree husk, ...) — the gate then
    degrades cheaply to a ``no_coverage`` warn without ever diffing or
    running tests. Mirrors ``_mt_commit_lane_deliverables``'s own resolution
    + exception handling.
    """
    from specify_cli.cli.commands.agent import tasks as _tasks
    from specify_cli.lanes.persistence import CorruptLanesError, MissingLanesError

    if st.owned is not None:
        # ``st.owned.owned_root`` surfaces as ``Any`` under this quarantined module's
        # ``follow_imports = "skip"``; pin it to the concrete ``Path`` via an
        # annotated local (same idiom as the ``workspace.worktree_path`` return).
        owned_root: Path = st.owned.owned_root
        return owned_root
    try:
        workspace = _tasks.resolve_workspace_for_wp(st.main_repo_root, st.mission_slug, st.task_id)
    except (ValueError, FileNotFoundError, MissingLanesError, CorruptLanesError):
        return None
    if not workspace.exists:
        return None
    # Annotated local: mypy runs with ``follow_imports = "skip"`` on this
    # quarantined module, so ``workspace`` (and ``ResolvedWorkspace`` itself)
    # surface as ``Any`` here; pinning the FIELD access to the stdlib ``Path``
    # type re-establishes the known concrete return type without a
    # suppression (mirrors ``RealFsReader``'s own idiom in
    # ``agent_tasks_ports.py``, which pins against a non-quarantined type).
    resolved_worktree_path: Path = workspace.worktree_path
    return resolved_worktree_path


def _mt_pre_review_changed_files(worktree_path: Path, base_branch: str) -> tuple[str, ...]:
    """Merge-base diff of the WP's worktree HEAD vs. its target branch.

    Routes through the canonical merge-base/diff surface
    (``core.vcs.git.merge_base_changed_files``, mission
    merge-base-diff-ssot-01KX44SD) rather than an inline ``git merge-base`` /
    ``git diff --name-only`` pair, generalized to every changed file rather
    than a ``kitty-specs/`` subset — the gate scopes tests off the WP's FULL
    changed-file set, not just spec docs. Any git failure degrades to an
    empty tuple (folds into a cheap ``no_coverage`` warn), never a crash.
    """
    # FR-013 advisory: a git failure only narrows the test scope, so () is acceptable.
    changed = set(merge_base_changed_files(worktree_path, base_branch))
    # Advisory: these paths only widen the test scope; an unknown snapshot adds none.
    changed.update(_mt_pre_review_dirty_paths(worktree_path) or ())
    return tuple(sorted(changed))


def _mt_pre_review_dirty_paths(worktree_path: Path) -> tuple[str, ...] | None:
    """Relevant staged, unstaged, and untracked deliverable paths, or ``None`` when unknown.

    ``None`` (a failed probe) is distinct from ``()`` (provably clean): the
    byproduct enrolment must not read an unknown snapshot as an empty one, or
    every pre-existing dirty file would look like a subprocess byproduct. The
    advisory test-scope caller (:func:`_mt_pre_review_changed_files`) degrades
    ``None`` to "no extra paths".
    """
    from specify_cli.cli.commands.agent import tasks as _tasks
    from specify_cli.cli.commands.agent.tasks_move_task import _lane_deliverable_paths

    try:
        status = status_entries(worktree_path, untracked=None)
    except GitCommandError:
        return None
    filtered = _tasks._filter_runtime_state_paths(status)
    paths = _lane_deliverable_paths(worktree_path, filtered)
    return tuple(sorted(str(path.relative_to(worktree_path)) for path in paths if path.is_relative_to(worktree_path)))


def _mt_pre_review_gate_with_override_scope(
    test_targets: tuple[str, ...],
    *,
    repo_root: Path,
    baseline: BaselineTestResult | None,
    progress_callback: Callable[[float], None] | None = None,
    status_observer: pre_review_gate.GateStatusObserver | None = None,
) -> pre_review_gate.GateVerdict:
    """Compose a verdict for an EXPLICIT override scope (FR-004).

    An override IS the test scope, by definition — the resolved scope source
    never runs for this precedence tier. The non-empty
    tail (head-run -> ``diff_baseline`` -> verdict) is NOT hand-mirrored here
    (pre-merge finding, #572/#1979/#2283: the mirrored copy left its
    ``NEW_FAILURES``/block/force + ``UNVERIFIED_BASELINE`` branches with zero
    coverage) — it REUSES ``pre_review_gate.evaluate_with_scope``, the exact
    same tested body ``evaluate_pre_review_gate`` itself drives. Only the
    empty-scope branch stays local: an override's empty list isn't a census
    exclusion, so ``ScopeResult.describe_empty_reason()``'s catch-all/
    composite-dir wording would be misleading — this keeps its own literal
    "override test scope is empty" reason instead.

    No ``SOURCE_MISMATCH`` here by design (#2894): this tier calls
    ``evaluate_with_scope`` with ``scope_source=None``, so it runs the legacy
    hardcoded pytest/JUnit path and never computes a ``source_identity`` to
    compare against the baseline's. That is intentional — an operator-pinned
    override IS the authoritative scope, so a baseline captured under a
    different source is not a reason to distrust it; the tier fails toward
    ``NEW_FAILURES``/``UNVERIFIED_BASELINE``, never a hard block.
    """
    scope = pre_review_gate.ScopeResult.from_override(test_targets)
    if scope.is_empty:
        return pre_review_gate.GateVerdict(
            outcome=pre_review_gate.GateOutcome.NO_COVERAGE,
            scope=scope,
            reason="override test scope is empty",
        )
    return pre_review_gate.evaluate_with_scope(
        scope,
        repo_root=repo_root,
        baseline=baseline,
        progress_callback=progress_callback,
        status_observer=status_observer,
    )


def _mt_empty_scope_verdict(reason: str, *, excluded_scope_files: tuple[str, ...] = ()) -> pre_review_gate.GateVerdict:
    """A ``no_coverage`` verdict built without deriving/running anything."""
    return pre_review_gate.GateVerdict(
        outcome=pre_review_gate.GateOutcome.NO_COVERAGE,
        scope=pre_review_gate.ScopeResult(
            test_targets=(),
            matched_shard_groups=(),
            matched_composite_dirs=(),
            empty_cone_composite_dirs=(),
            excluded_scope_files=excluded_scope_files,
        ),
        reason=reason,
    )


#: #3821: the calm, consumer-facing reason recorded when a bound gate does not
#: fire because the repo has not declared one. Deliberately names NO internal
#: concept (no ``ScopeSource``, no authorities module) — an operator in a
#: ``spec-kitty init`` consumer repo has never heard of those, and the absence
#: is expected, not a defect. Distinct from the escape hatch's visible yellow
#: ``SKIPPED`` line (#2573): an explicit opt-out is surfaced, an undeclared
#: repo's default is recorded in transition metadata only.
_PRE_REVIEW_GATE_NOT_DECLARED_REASON = (
    "pre-review regression gate not declared by this repo — skipped (non-blocking; configure review.test_command in .kittify/config.yaml to declare one)"
)


def _mt_not_declared_skip_verdict() -> pre_review_gate.GateVerdict:
    """The quiet ``SKIPPED`` verdict for a repo that has not declared the gate (#3821).

    Deliberately NOT a ``NO_COVERAGE`` warn: an undeclared repo has no coverage
    gap to surface — nothing was declared to verify against — so #2598's
    acceptance criterion ("the pre-review gate does not fire/leak in a consumer
    repo that has not declared it") makes this a metadata-only skip.
    """
    return pre_review_gate.GateVerdict(
        outcome=pre_review_gate.GateOutcome.SKIPPED,
        scope=pre_review_gate.ScopeResult(
            test_targets=(),
            matched_shard_groups=(),
            matched_composite_dirs=(),
            empty_cone_composite_dirs=(),
            excluded_scope_files=(),
        ),
        reason=_PRE_REVIEW_GATE_NOT_DECLARED_REASON,
    )


def _mt_cancelled_verdict() -> pre_review_gate.GateVerdict:
    """The terminal ``CANCELLED`` verdict a ``KeyboardInterrupt`` degrades to (T041/C-003).

    Single construction shared by every fail-open envelope (gate execution AND
    the pre-dispatch resolution phase) so a ``Ctrl-C`` anywhere in the hook lands
    on the sanctioned terminal-``CANCELLED`` hard-stop, never an unhandled
    ``BaseException`` that escapes ``move-task`` as exit 130 (FR-013 invariant).
    """
    return pre_review_gate.GateVerdict(
        outcome=pre_review_gate.GateOutcome.CANCELLED,
        scope=pre_review_gate.ScopeResult.from_override(()),
        reason="scoped test run cancelled",
        run_state=pre_review_gate.HeadRunState.CANCELLED,
    )


def _mt_pre_review_gate_metadata(
    verdict: pre_review_gate.GateVerdict,
    *,
    block_enabled: bool,
    blocked: bool,
    force_bypassed: bool,
) -> dict[str, Any]:
    """The FR-004 transition-evidence payload recorded via ``policy_metadata``."""
    scope = verdict.scope
    metadata: dict[str, Any] = {
        "outcome": verdict.outcome.value,
        "reason": verdict.reason,
        "new_failure_count": len(verdict.new_failures),
        "new_failure_nodeids": [failure.test for failure in verdict.new_failures],
        "pre_existing_failure_count": len(verdict.pre_existing_failures),
        "affected_shard_count": len(scope.matched_shard_groups) + len(scope.matched_composite_dirs),
        "matched_shard_groups": list(scope.matched_shard_groups),
        "matched_composite_dirs": list(scope.matched_composite_dirs),
        "test_targets": list(scope.test_targets),
        "block_enabled": block_enabled,
        "blocked": blocked,
        "force_bypassed": force_bypassed,
        "run_state": verdict.run_state.value,
    }
    assessment = verdict.budget_assessment
    if assessment is not None:
        metadata.update(
            {
                "budget_classification": assessment.classification.value,
                "scope_identity": assessment.scope_identity.value,
                "effective_budget_seconds": assessment.effective_budget_seconds,
                "matched_budget_rule": assessment.matched_rule_id,
                "classification_candidate": verdict.classification_candidate,
                "observed_elapsed_seconds": verdict.observed_elapsed_seconds,
                "classification_guidance": assessment.guidance,
            }
        )
        if verdict.outcome is pre_review_gate.GateOutcome.SCOPE_OVERSIZED:
            metadata["recovery_choices"] = [
                "Select a bounded pre_review_test_scope",
                "Use --skip-pre-review-gate explicitly",
            ]
    return metadata


#: Pre-merge finding (#572/#1979/#2283): the opt-in block
#: (``review.fail_on_pre_review_regression``) can ONLY ever fire on a
#: ``NEW_FAILURES`` verdict (see ``_mt_run_pre_review_gate``'s ``would_block``
#: below), which itself needs a computed baseline. ``baseline.py``'s
#: ``capture_baseline`` returns ``None`` (no artifact ever written) when
#: ``review.test_command`` is unset — so an operator who opts in to the block
#: WITHOUT also configuring ``review.test_command`` gets a block that can
#: NEVER engage: every for_review move degrades to ``NO_COVERAGE`` or
#: ``UNVERIFIED_BASELINE`` (never ``NEW_FAILURES``), silently. That silence is
#: itself a defect, so this hint is surfaced as an EXPLICIT, non-dim warning
#: rather than folded into the routine dim advisory line below.
_PRE_REVIEW_BLOCK_UNENFORCEABLE_HINT = (
    "block requested via review.fail_on_pre_review_regression but COULD NOT be enforced — "
    "no verified new-failure verdict exists to block on. A baseline must be captured at "
    "implement time (configure review.test_command in .kittify/config.yaml) before this "
    "block can ever take effect."
)


def _mt_pre_review_gate_console_warning(verdict: pre_review_gate.GateVerdict, *, block_enabled: bool) -> str | None:
    """Human-readable (non-JSON) console line surfacing the verdict, or ``None``
    when the verdict renders no line at all.

    ``block_enabled`` does not change the warn-vs-block semantics here (the
    transition still proceeds — you cannot block on data that doesn't
    exist) — it only decides whether the ``NO_COVERAGE``/``UNVERIFIED_BASELINE``
    line escalates from a routine dim advisory to an explicit block-inert
    warning naming the ``review.test_command`` prerequisite.

    ``SKIPPED`` (#3821) renders NO line by default — the gate "does not
    fire/leak" in a repo that never declared it — with the one exception of
    ``block_enabled``: an operator who opted into the block deserves to hear
    it cannot engage, exactly like the other can't-enforce outcomes.
    """
    outcome = verdict.outcome
    if outcome is pre_review_gate.GateOutcome.NEW_FAILURES:
        shard_count = len(verdict.scope.matched_shard_groups) + len(verdict.scope.matched_composite_dirs)
        nodeids = ", ".join(failure.test for failure in verdict.new_failures[:5])
        more = f" (+{len(verdict.new_failures) - 5} more)" if len(verdict.new_failures) > 5 else ""
        return f"[yellow]Pre-review regression gate:[/yellow] {len(verdict.new_failures)} new failure(s) across {shard_count} affected shard(s) — {nodeids}{more}"
    if outcome in (pre_review_gate.GateOutcome.NO_COVERAGE, pre_review_gate.GateOutcome.UNVERIFIED_BASELINE):
        if block_enabled:
            return (
                f"[yellow]Pre-review regression gate:[/yellow] {_PRE_REVIEW_BLOCK_UNENFORCEABLE_HINT} (outcome={outcome.value}: {verdict.reason or 'unverified'})"
            )
        return f"[dim]Pre-review regression gate: {outcome.value} — {verdict.reason or 'unverified'}[/dim]"
    if outcome is pre_review_gate.GateOutcome.SKIPPED:
        if block_enabled:
            return (
                f"[yellow]Pre-review regression gate:[/yellow] {_PRE_REVIEW_BLOCK_UNENFORCEABLE_HINT} (outcome={outcome.value}: {verdict.reason or 'gate skipped'})"
            )
        return None
    if outcome is pre_review_gate.GateOutcome.SOURCE_MISMATCH:
        # FR-009/FR-011 (mission scopesource-gate-followup-01KY6S9P WP04):
        # warn-shaped, fail-open by construction (absent from
        # ``verdict_aggregation``'s terminal/block member allowlists) — names
        # both identities so an operator can see WHY the diff is untrustworthy.
        return f"[yellow]Pre-review regression gate: {outcome.value} — {verdict.reason or 'unverified'}[/yellow]"
    if outcome in (pre_review_gate.GateOutcome.TIMED_OUT, pre_review_gate.GateOutcome.CANCELLED):
        return f"[red]Pre-review regression gate: {outcome.value} — {verdict.reason or 'interrupted'}[/red]"
    if outcome is pre_review_gate.GateOutcome.SCOPE_OVERSIZED:
        targets = ", ".join(verdict.scope.test_targets) or "(empty)"
        return (
            "[red]Pre-review regression gate: scope_oversized — validation did not start; "
            f"targets={targets}; {verdict.reason or 'scope exceeds the effective budget'}. "
            "The work package remains in its prior lane. Recovery choices: select a bounded "
            "pre_review_test_scope or use --skip-pre-review-gate explicitly.[/red]"
        )
    if outcome is pre_review_gate.GateOutcome.NO_NEW_FAILURES:
        return "[dim]Pre-review regression gate: no new failures[/dim]"
    # Defensive: a future ``GateOutcome`` member must never silently render as
    # a clean pass (mission scopesource-gate-followup-01KY6S9P WP04, T023) —
    # this branch is unreachable for today's exhaustive member set but closes
    # the silent-clean-pass class for whatever comes next.
    return f"[dim]Pre-review regression gate: {outcome.value}[/dim]"


def _mt_pre_review_gate_block_message(verdict: pre_review_gate.GateVerdict) -> str:
    """The refusal message when the opt-in block engages (FR-001)."""
    nodeids = ", ".join(failure.test for failure in verdict.new_failures[:5])
    more = f" (+{len(verdict.new_failures) - 5} more)" if len(verdict.new_failures) > 5 else ""
    return (
        "Pre-review regression gate BLOCKED this for_review move: "
        f"{len(verdict.new_failures)} new failure(s) introduced — {nodeids}{more}. "
        "Fix the regression, or re-run with --force to override (recorded in the transition evidence)."
    )


@dataclass(frozen=True)
class _TransitionGateInputs:
    """The shared, per-transition I/O the gate resolves once before dispatch.

    The changed-files SSOT (``_mt_pre_review_changed_files`` → ``:927``) is
    resolved here, then handed to the doctrine-resolved dispatch and the
    aggregation. Reused, never re-derived (contract "What the hook does NOT
    change"). The dirty-path baseline used to enrol subprocess byproducts
    (:func:`_mt_resolve_transition_gate_verdicts`) is resolved alongside these
    inputs but returned separately — it is transient bookkeeping, not part of
    the shared per-transition surface.

    ``gate_repo_root`` and ``scope_source_root`` are deliberately DIFFERENT
    roots (issue #3611 fix): ``gate_repo_root`` is where the scoped test
    subprocess actually RUNS (the worktree, when one exists — the run must
    execute against the code under review); ``scope_source_root`` is where
    ``ScopeSource`` SELECTION happens. Flagless calls keep ``st.main_repo_root``
    — the SAME root ``implement_capture_baseline`` uses — while explicit owned
    calls use the selected owned checkout where their planning inputs live.
    Resolving selection from ``gate_repo_root`` (the worktree) instead let a
    lane worktree whose checked-out ``.kittify/config.yaml`` lacks
    ``review.test_command`` silently diverge from the planning root's
    selection — capture picks ``DeclaredCommandScopeSource``, the head gate
    picks ``GateCoverageScopeSource`` for the SAME WP — which defeats the
    ``SOURCE_MISMATCH`` safety check before it ever gets a chance to compare
    identities. Splitting the two roots keeps selection stable while still
    running the tests where the changes actually live.
    """

    worktree_path: Path | None
    changed_files: tuple[str, ...]
    gate_repo_root: Path
    scope_source_root: Path


@dataclass(frozen=True)
class _TransitionGateEffect:
    """The observable surface the aggregate decision maps onto (hook performs it).

    ``metadata`` is the ``policy_metadata`` payload; ``console_lines`` are the
    per-handler warn lines (≤1 per handler, NFR-002 — a ``SKIPPED`` verdict
    renders none, #3821); ``representative`` is the
    single verdict the metadata/block message render from; ``blocked`` /
    ``terminal`` / ``should_exit`` drive the two hard-stops (T041).
    """

    metadata: dict[str, Any]
    console_lines: tuple[str, ...]
    representative: pre_review_gate.GateVerdict
    blocked: bool
    terminal: bool
    should_exit: bool


def _mt_warn_pre_review_test_command_deprecated(main_repo_root: Path) -> None:
    """T043 (FR-011): one-time deprecation warning for ``review.pre_review_test_command``.

    The legacy key is aliased to the ``ScopeSource`` single authority
    (``review.test_command``) and STILL honored — never a silent break — but a
    config that sets it earns exactly one process-wide deprecation warning
    (guarded by the module latch), routed through the standard ``warnings``
    surface so it never pollutes ``--json`` output.
    """
    global _pre_review_test_command_deprecation_emitted
    if _pre_review_test_command_deprecation_emitted:
        return
    if _mt_review_config_section(main_repo_root).get(_PRE_REVIEW_CONFIG_KEY_TEST_COMMAND) is None:
        return
    _pre_review_test_command_deprecation_emitted = True
    warnings.warn(_PRE_REVIEW_TEST_COMMAND_DEPRECATION, DeprecationWarning, stacklevel=2)


def _mt_resolve_scope_source(gate_repo_root: Path) -> ScopeSource:
    """Build the activation-selected ``ScopeSource`` for the pre-review handler.

    FR-014 (mission scopesource-gate-followup-01KY6S9P WP04, post-plan squad
    finding priti-M1 — load-bearing): delegates to WP02's
    ``resolve_scope_source`` factory — the SAME selection authority
    ``baseline.py``'s write-side capture already uses — instead of
    constructing a source independently. Independent construction could let
    the head and baseline drift, producing a false ``SOURCE_MISMATCH``.

    The two compatibility seams (:func:`_pre_review_gate_filter_groups` /
    :func:`_pre_review_gate_composite_routing`) are threaded through as
    ``resolve_scope_source``'s ``*_override`` parameters; the factory ignores
    them after the workflow-derived source's retirement. ``resolve_scope_source``
    lives in ``scope_source.py`` and never imports back into this module, so
    no import cycle forms.
    """
    return resolve_scope_source(
        gate_repo_root,
        filter_groups_override=_pre_review_gate_filter_groups(),
        composite_routing_override=_pre_review_gate_composite_routing(),
    )


def _mt_resolve_active_gate_bindings(st: _MoveTaskState) -> GateBindingResolution:
    """Resolve which doctrine-bound handlers gate this lane edge (FR-007/008).

    The impure orchestration seam: resolves the mission type from identity
    (never hardcoded) and delegates to
    :func:`resolve_gate_bindings_for_transition` (one graph load + one filter +
    one contract-bindings load, NFR-005). Kept a named module function so the
    escape-hatch / observability tests can inject a canned resolution without a
    full activated-doctrine repo fixture.
    """
    edge_key = f"{st.old_lane.value}->{st.target_lane.value}"
    # Status may live in a coord husk without the PRIMARY mission identity.
    identity_dir = placement_seam(
        st.main_repo_root,
        st.mission_slug,
        owned=st.owned,
    ).read_dir(MissionArtifactKind.PRIMARY_METADATA)
    mission = resolve_mission_type(st, feature_dir=identity_dir)
    operation_root = st.owned.owned_root if st.owned is not None else st.main_repo_root
    return resolve_gate_bindings_for_transition(operation_root, mission, edge_key)


def _mt_resolve_gate_baseline(st: _MoveTaskState) -> BaselineTestResult | None:
    """Load the WP's captured baseline (``None`` when never captured).

    Shared by the doctrine-bound handler context and the FR-004 override tier so
    both diff against the SAME baseline artifact.
    """
    if st.owned is not None:
        assert st.wp is not None
        wp_slug = st.wp.path.stem
        baseline_read_dir = st.feature_dir
        return BaselineTestResult.load(baseline_read_dir / "tasks" / wp_slug / "baseline-tests.json")
    wp_slug = _resolve_wp_slug(st.main_repo_root, st.mission_slug, st.task_id)
    # C-008 (coord-commit-integrity-01KY5JS8): baseline-tests.json is a
    # WORK_PACKAGE_TASK-kind (PRIMARY-partition) artifact authored by
    # implement_capture_baseline. Under coord topology ``st.feature_dir`` is the
    # kind-blind coord husk where the PRIMARY-authored baseline does NOT exist —
    # reading it there silently loses pre-existing-failure suppression. Route the
    # READ through the SAME kind-aware seam the review gate uses (workflow.py
    # ``_resolve_workflow_read_dir(kind=WORK_PACKAGE_TASK)``), not the husk.
    from specify_cli.cli.commands.agent.workflow import _resolve_workflow_read_dir

    baseline_read_dir = _resolve_workflow_read_dir(
        repo_root=st.main_repo_root,
        mission_slug=st.mission_slug,
        kind=MissionArtifactKind.WORK_PACKAGE_TASK,
    )
    return BaselineTestResult.load(baseline_read_dir / "tasks" / wp_slug / "baseline-tests.json")


def _mt_build_transition_gate_context(
    st: _MoveTaskState,
    inputs: _TransitionGateInputs,
    *,
    status_observer: pre_review_gate.GateStatusObserver | None = None,
) -> TransitionGateContext:
    """Assemble the ``TransitionGateContext`` handed to every handler (data-model §8)."""
    return TransitionGateContext(
        changed_files=inputs.changed_files,
        scope_source=_mt_resolve_scope_source(inputs.scope_source_root),
        baseline=_mt_resolve_gate_baseline(st),
        repo_root=inputs.gate_repo_root,
        force=st.force,
        from_lane=st.old_lane,
        to_lane=st.target_lane,
        status_observer=status_observer,
    )


def _mt_fail_open_gate(
    run: Callable[[], pre_review_gate.GateVerdict],
    *,
    changed_files: tuple[str, ...] = (),
) -> pre_review_gate.GateVerdict:
    """Run a gate-execution callable under the incumbent three-catch fail-open (T041/FR-013).

    Mirrors the incumbent's three-catch verbatim:
    ``KeyboardInterrupt`` → terminal ``CANCELLED``; ``GateAuthoritiesUnavailable``
    → unverified ``NO_COVERAGE`` warn (the erroneous-activation degrade, #2534);
    any other ``Exception`` → unverified ``NO_COVERAGE`` warn. Guarantees a gate
    fault yields exactly ONE verdict and never escapes move-task — whichever
    precedence tier produced the callable (a bound handler OR the FR-004 explicit
    override scope). The override tier is just another gate-execution path, so it
    MUST fail open here too; a bare ``KeyboardInterrupt`` in the override runner
    escaping to exit 130 would breach the terminal-CANCELLED hard-stop invariant.
    """
    try:
        return run()
    except KeyboardInterrupt:
        return _mt_cancelled_verdict()
    except pre_review_gate.GateAuthoritiesUnavailable as exc:
        return _mt_empty_scope_verdict(
            f"gate authorities unavailable — unverified: {exc}",
            excluded_scope_files=changed_files,
        )
    except Exception as exc:  # noqa: BLE001 — FR-013 per-handler fail-open (never break move-task)
        return _mt_empty_scope_verdict(f"pre-review gate evaluation failed — unverified: {exc}")


def _mt_dispatch_one_gate(
    binding: GateBinding,
    ctx: TransitionGateContext,
    handler_lookup: Callable[[str], GateHandler],
) -> pre_review_gate.GateVerdict:
    """Dispatch ONE bound handler under the shared three-catch fail-open (T041).

    Each fault yields exactly ONE verdict and never crosses into another handler.
    """
    return _mt_fail_open_gate(
        lambda: handler_lookup(binding.handler).run(ctx),
        changed_files=ctx.changed_files,
    )


def _mt_dispatch_transition_gates(
    bindings: Sequence[GateBinding],
    ctx: TransitionGateContext,
    *,
    handler_lookup: Callable[[str], GateHandler] = get_gate_handler,
) -> list[pre_review_gate.GateVerdict]:
    """Dispatch each active binding in the resolver's stable order (FR-004/008).

    ``get_gate_handler(b.handler).run(ctx)`` per binding (never a bare
    ``GATE_REGISTRY[name]``); order is the stable sort the resolver already
    applied, so aggregation precedence is deterministic (NFR-001).
    """
    return [_mt_dispatch_one_gate(binding, ctx, handler_lookup) for binding in bindings]


_PRE_REVIEW_GATE_RUNNING_NOTICE = "[cyan]Pre-review regression gate: running scoped tests at head (may take a few minutes)...[/cyan]"


def _mt_human_gate_status_observer(_tasks: Any) -> pre_review_gate.GateStatusObserver:
    """Build the sole human renderer for engine-owned gate status events.

    The callback is presentation-only: it cannot classify a scope, decide a
    verdict, or mutate transition state. JSON callers never construct it.
    """

    def _observe(event: pre_review_gate.GateStatusEvent) -> None:
        if isinstance(event, pre_review_gate.ScopeAssessed):
            assessment = event.assessment
            targets = ", ".join(assessment.scope_identity.normalized_targets) or "(empty)"
            suffix = ""
            if assessment.classification.value == "unknown":
                suffix = "; no reviewed metadata matches, so validation will run under the existing timeout"
            _tasks.console.print(
                "[cyan]Pre-review gate scope assessment: "
                f"{assessment.classification.value}; targets={targets}; "
                f"effective budget={assessment.effective_budget_seconds:g}s{suffix}[/cyan]"
            )
            return

        elapsed = event.observed_elapsed_seconds
        if elapsed <= 0:
            _tasks.console.print(f"[cyan]Pre-review gate validation started; phase={event.phase}; elapsed={elapsed:g}s[/cyan]")
            return
        _tasks.console.print(f"[cyan]Pre-review gate still running; phase={event.phase}; elapsed={elapsed:g}s[/cyan]")

    return _observe


def _mt_collect_transition_gate_verdicts(
    st: _MoveTaskState,
    inputs: _TransitionGateInputs,
    _tasks: Any,
) -> list[pre_review_gate.GateVerdict]:
    """Resolve the FR-004 precedence tier, then the bindings, and return the verdict list.

    Precedence, mirroring the incumbent (NFR-001): an explicit operator override
    (frontmatter ``pre_review_test_scope`` > config ``pre_review_test_command``)
    IS the test scope — it bypasses BOTH the changed-file census AND doctrine
    binding resolution, evaluated through the shared
    :func:`_mt_pre_review_gate_with_override_scope` tier. WP09's first inversion
    dropped this tier (it never consulted the override), silently ignoring every
    operator-pinned scope; restoring it is part of full incumbent fidelity.

    Absent an override: a cheap short-circuit first — an empty changed-file set
    means there is nothing to gate, so it degrades to a single ``NO_COVERAGE``
    warn WITHOUT loading the activation graph (bounded cost, NFR-005). A
    resolution with no active binding (no contract / no binding / not activated)
    returns the resolver's **distinguishable** ``NO_COVERAGE`` reason
    (FR-008/012), never a silent vanish. A resolution WITH active bindings but
    no declared gate command (``review.test_command`` unset and no override
    above) returns one quiet ``SKIPPED`` verdict instead of dispatching (#3821):
    the built-in binding ships with the ``software-dev`` review contract, so
    binding resolution alone cannot tell a declared gate from an undeclared one.
    """
    wp = getattr(st, "wp", None)
    status_observer = None if st.json_output else _mt_human_gate_status_observer(_tasks)
    override_targets = _mt_pre_review_scope_override(wp.frontmatter, st.repo_root) if wp is not None else None
    if override_targets is not None:
        if not st.json_output:
            _tasks.console.print(_PRE_REVIEW_GATE_RUNNING_NOTICE)
        return [
            _mt_fail_open_gate(
                lambda: _mt_pre_review_gate_with_override_scope(
                    override_targets,
                    repo_root=inputs.gate_repo_root,
                    baseline=_mt_resolve_gate_baseline(st),
                    status_observer=status_observer,
                ),
                changed_files=inputs.changed_files,
            )
        ]
    if not inputs.changed_files:
        return [_mt_empty_scope_verdict("no changed files detected for this WP — skipping the gate cheaply")]
    resolution = _mt_resolve_active_gate_bindings(st)
    if not resolution.active:
        return [_mt_empty_scope_verdict(resolution.reason)]
    if not _mt_pre_review_gate_declared(inputs.scope_source_root):
        # #3821: the binding resolved ACTIVE (it ships built-in with the
        # ``software-dev`` review contract), but this repo has declared no
        # command for any handler to run — the gate does not fire here.
        return [_mt_not_declared_skip_verdict()]
    if not st.json_output:
        _tasks.console.print(_PRE_REVIEW_GATE_RUNNING_NOTICE)
    ctx = _mt_build_transition_gate_context(st, inputs, status_observer=status_observer)
    return _mt_dispatch_transition_gates(list(resolution.active), ctx)


def _mt_resolve_transition_gate_inputs(
    st: _MoveTaskState,
) -> tuple[_TransitionGateInputs, tuple[str, ...] | None]:
    """Resolve the workspace, dirty-path baseline, and changed-files SSOT (unchanged).

    Returns ``(inputs, dirty_before)``: ``dirty_before`` is the transient
    pre-dispatch dirty-path snapshot used later to enrol whatever a gate's
    subprocess creates (:func:`_mt_run_transition_gates`) — it is not part of
    the shared :class:`_TransitionGateInputs` surface.
    """
    worktree_path = _mt_resolve_pre_review_workspace(st)
    dirty_before = _mt_pre_review_dirty_paths(worktree_path) if worktree_path is not None else ()
    changed_files = _mt_pre_review_changed_files(worktree_path, st.review_base_ref or st.target_branch) if worktree_path is not None else ()
    inputs = _TransitionGateInputs(
        worktree_path=worktree_path,
        changed_files=changed_files,
        gate_repo_root=worktree_path or st.main_repo_root,
        scope_source_root=st.repo_root if st.owned is not None else st.main_repo_root,
    )
    return inputs, dirty_before


def _mt_resolve_transition_gate_verdicts(
    st: _MoveTaskState, _tasks: Any
) -> tuple[_TransitionGateInputs | None, tuple[str, ...] | None, list[pre_review_gate.GateVerdict]]:
    """Run the pre-dispatch resolution phase under the SAME fail-open as :func:`_mt_fail_open_gate`.

    The incumbent (base ``e4ef6e850``) degraded a *resolution* fault to a
    ``NO_COVERAGE`` warn and PROCEEDED. The inverted hook only wrapped the
    dispatch/override tiers, so a fault in the pre-dispatch resolution phase —
    the deprecation warn, input resolution, or binding resolution + context build
    inside :func:`_mt_collect_transition_gate_verdicts` — escaped unwrapped to
    ``_do_move_task``'s outer ``except Exception`` and REFUSED the ``for_review``
    move (a fail-open→fail-closed regression + an unsanctioned third hard-stop),
    while a ``Ctrl-C`` (a ``BaseException``) slipped past that ``except Exception``
    entirely and exited 130 — the exact breach the terminal-``CANCELLED`` path
    exists to prevent. Routing resolution through the same three-catch restores
    C-003 / FR-013: ``KeyboardInterrupt`` → terminal ``CANCELLED``; any other
    ``Exception`` (malformed step-contract, unset org-pack env var, invalid DRG
    graph, malformed ``meta.json``/``"pending"`` sentinel, or ``warnings.warn``
    under ``-W error``) → exactly one visible ``NO_COVERAGE`` warn and PROCEED.

    Returns ``(inputs, dirty_before, verdicts)``; ``inputs`` is ``None`` when
    resolution raised before the workspace inputs were built (no changed/dirty
    paths to reconcile), in which case ``dirty_before`` is empty.
    """
    try:
        _mt_warn_pre_review_test_command_deprecated(st.main_repo_root)
        inputs, dirty_before = _mt_resolve_transition_gate_inputs(st)
        return inputs, dirty_before, _mt_collect_transition_gate_verdicts(st, inputs, _tasks)
    except KeyboardInterrupt:
        return None, (), [_mt_cancelled_verdict()]
    except pre_review_gate.GateAuthoritiesUnavailable as exc:
        return None, (), [_mt_empty_scope_verdict(f"gate authorities unavailable — unverified: {exc}")]
    except Exception as exc:  # noqa: BLE001 — FR-013 fail-open over resolution (never break move-task)
        return None, (), [_mt_empty_scope_verdict(f"pre-review gate resolution failed — unverified: {exc}")]


def _mt_gate_representative(aggregate: Any, verdicts: Sequence[pre_review_gate.GateVerdict]) -> pre_review_gate.GateVerdict:
    """The single verdict the metadata / block message render from.

    Deterministic and, for the half-A single-handler reality, always the one
    dispatched verdict: the terminal verdict if the decision is terminal, else
    the first blocking (``NEW_FAILURES``) verdict, else the last verdict.
    """
    if aggregate.terminal_verdict is not None:
        return cast(pre_review_gate.GateVerdict, aggregate.terminal_verdict)
    if aggregate.blocking_verdicts:
        return cast(pre_review_gate.GateVerdict, aggregate.blocking_verdicts[0])
    if verdicts:
        return verdicts[-1]
    return _mt_empty_scope_verdict("no active gate bindings for this transition")


def _mt_translate_gate_verdicts(
    verdicts: Sequence[pre_review_gate.GateVerdict],
    *,
    block_enabled: bool,
    force: bool,
) -> _TransitionGateEffect:
    """Aggregate the per-handler verdicts and render the observable effect (FR-014).

    Precedence (terminal > block > warn) lives in WP08's pure
    :func:`aggregate_verdicts`; this helper only maps the aggregate onto the
    metadata / console / block-exit surface the incumbent produced, so the
    single-verdict path reproduces the base-captured parity tuple field-by-field
    (NFR-001).
    """
    aggregate = aggregate_verdicts(verdicts, block_enabled=block_enabled, force=force)
    representative = _mt_gate_representative(aggregate, verdicts)
    blocked = aggregate.decision is AggregateDecision.BLOCK
    terminal = aggregate.decision is AggregateDecision.TERMINAL
    force_bypassed = block_enabled and force and bool(aggregate.blocking_verdicts)
    metadata = _mt_pre_review_gate_metadata(
        representative,
        block_enabled=block_enabled,
        blocked=blocked,
        force_bypassed=force_bypassed,
    )
    if terminal:
        metadata["transition_applied"] = False
    # #3821: a ``SKIPPED`` verdict renders NO console line, so the per-verdict
    # lines are filtered for ``None`` (the renderer's quiet-skip signal). The
    # incumbent's representative fallback only ever fired for an EMPTY
    # ``warnings`` sequence (every verdict rendered a line before #3821), so it
    # is preserved for exactly that case — an all-``SKIPPED`` set renders zero
    # lines, never a fallback line.
    rendered_warnings = tuple(_mt_pre_review_gate_console_warning(verdict, block_enabled=block_enabled) for verdict in aggregate.warnings)
    if rendered_warnings:
        console_lines = tuple(line for line in rendered_warnings if line is not None)
    else:
        representative_line = _mt_pre_review_gate_console_warning(representative, block_enabled=block_enabled)
        console_lines = () if representative_line is None else (representative_line,)
    return _TransitionGateEffect(
        metadata=metadata,
        console_lines=console_lines,
        representative=representative,
        blocked=blocked,
        terminal=terminal,
        should_exit=aggregate.should_exit,
    )


def _mt_emit_skipped_gate(st: _MoveTaskState, _tasks: Any, skip_reason: str) -> None:
    """Record + announce a skipped gate (escape hatch, #2573 FR-002)."""
    verdict = _mt_empty_scope_verdict(f"gate skipped — {skip_reason}")
    st.pre_review_gate_metadata = _mt_pre_review_gate_metadata(
        verdict,
        block_enabled=False,
        blocked=False,
        force_bypassed=False,
    )
    if not st.json_output:
        _tasks.console.print(f"[yellow]Pre-review regression gate: SKIPPED ({skip_reason})[/yellow]")


def _mt_emit_transition_gate_effect(
    st: _MoveTaskState,
    effect: _TransitionGateEffect,
    _tasks: Any,
) -> None:
    """Emit console + perform the two hard-stops (T041) from the aggregate effect."""
    if not st.json_output:
        for line in effect.console_lines:
            _tasks.console.print(line)
    if effect.terminal:
        outcome_value = effect.representative.outcome.value
        _tasks._output_error(
            st.json_output,
            f"Pre-review regression gate {outcome_value}; transition not applied",
            diagnostic={
                "result": "error",
                "error": f"pre-review gate {outcome_value}",
                "transition_applied": False,
                "pre_review_gate": st.pre_review_gate_metadata,
            },
        )
        raise typer.Exit(1)
    if effect.blocked:
        block_message = _mt_pre_review_gate_block_message(effect.representative)
        _tasks._output_error(
            st.json_output,
            block_message,
            diagnostic={
                "result": "error",
                "error": block_message,
                "transition_applied": False,
                "pre_review_gate": st.pre_review_gate_metadata,
            },
        )
        raise typer.Exit(1)


def _mt_run_transition_gates(st: _MoveTaskState) -> None:
    """FR-009/013/014: the inverted, doctrine-resolved transition gate.

    Generalizes the incumbent ``_mt_run_pre_review_gate``: instead of a
    hardcoded call to ``evaluate_pre_review_gate``, it resolves WHICH named
    handlers the repo's active doctrine binds to the current lane edge (WP06's
    ``resolve_gate_bindings_for_transition`` + WP04's ``GATE_REGISTRY``),
    dispatches each with per-handler fail-open (T041), and aggregates via WP08's
    pure ``aggregate_verdicts`` (T040). A thin orchestrator: the join and the
    aggregation are the pure functions it merely calls (NFR-006).

    Runs ONLY for ``for_review`` moves, right after ``_mt_run_decision`` in
    ``_do_move_task`` — AFTER every pre-existing guard clears and BEFORE the
    transition is emitted/committed. Purely additive after the guard sequence:
    the two hard-stops (terminal interruption; opt-in ``NEW_FAILURES`` block) are
    the only non-local exits, and every handler-execution error degrades to one
    visible ``NO_COVERAGE`` warn (C-003).
    """
    if st.target_lane != Lane.FOR_REVIEW:
        return
    from specify_cli.cli.commands.agent import tasks as _tasks

    # #2573 FR-002: the opt-out escape hatch — checked BEFORE touching the
    # workspace or WP frontmatter, so a skip never resolves a lane workspace,
    # diffs changed files, or spawns the scoped pytest subprocess.
    skip_reason = _mt_pre_review_gate_skip_reason(st)
    if skip_reason is not None:
        _mt_emit_skipped_gate(st, _tasks, skip_reason)
        return

    assert st.wp is not None
    inputs, dirty_before, verdicts = _mt_resolve_transition_gate_verdicts(st, _tasks)
    worktree_path = inputs.worktree_path if inputs is not None else None
    byproduct_snapshots = _mt_enrol_gate_byproducts(worktree_path, dirty_before)
    block_enabled = _mt_pre_review_block_enabled(st.repo_root)
    effect = _mt_translate_gate_verdicts(verdicts, block_enabled=block_enabled, force=st.force)
    # IC-07f (WP16): the enrolment above is the compensator's snapshot leg
    # (``{path: None}`` for a subprocess-created path — the pre-transaction
    # state the compensator restores to). Committed on success means simply
    # NOT restoring: the created bytes stay put. On the two hard-stops
    # (terminal interruption, opt-in block) the step aborts, so the SAME
    # single restore path the merge executor and the coordination transaction
    # use (:func:`restore_generated_artifact_snapshots`) unlinks them —
    # genuinely reverted, not merely detected-and-abandoned.
    if byproduct_snapshots and effect.should_exit:
        restore_generated_artifact_snapshots(byproduct_snapshots)
    st.pre_review_gate_metadata = effect.metadata
    _mt_emit_transition_gate_effect(st, effect, _tasks)


def _mt_enrol_gate_byproducts(worktree_path: Path | None, dirty_before: tuple[str, ...] | None) -> dict[Path, bytes | None]:
    """Enrol any path a bound gate's subprocess created into the owner (C3).

    A gate handler may spawn a scoped pytest run that creates cache/coverage
    byproducts inside the WP's own worktree. Diffing the post-dispatch dirty
    set against ``dirty_before`` (captured pre-dispatch) yields exactly the
    paths the subprocess created (:func:`subprocess_created_paths`, the SAME
    owner helper the merge executor and the coordination transaction use).
    Enrolling them (:func:`enroll_subprocess_byproducts`) snapshots their
    absent pre-transaction state and returns it — the caller (
    :func:`_mt_run_transition_gates`) routes that snapshot through the single
    restore compensator on the abort/block path, so the byproduct is
    genuinely committed on success and reverted on abort, never merely
    detected and abandoned.
    """
    if worktree_path is None or dirty_before is None:
        return {}
    dirty_after = _mt_pre_review_dirty_paths(worktree_path)
    if dirty_after is None:
        # Fail closed (FR-013): with either snapshot unknown, the byproduct set is
        # unknowable, and the abort compensator UNLINKS what it enrols. Enrol nothing.
        return {}
    created = subprocess_created_paths(
        (worktree_path / rel for rel in dirty_before),
        (worktree_path / rel for rel in dirty_after),
    )
    if not created:
        return {}
    # Annotated local: mypy runs with ``follow_imports = "skip"`` on this
    # quarantined module, so the cross-module call surfaces as ``Any`` here;
    # pinning it re-establishes the known concrete return type without a
    # suppression (mirrors ``_mt_resolve_pre_review_workspace``'s own idiom).
    snapshots: dict[Path, bytes | None] = enroll_subprocess_byproducts(created, trusted_roots=(worktree_path,))
    return snapshots


def _mt_run_pre_review_gate(st: _MoveTaskState) -> None:
    """Thin forwarder onto the inverted hook :func:`_mt_run_transition_gates`.

    Kept as a real, exported symbol (frozen compat surface, squad P-F1) and as
    the ``_do_move_task`` call-site target so the observability monkeypatch that
    binds ``_mt_run_pre_review_gate`` by name keeps intercepting. Do NOT repoint
    the call site at ``_mt_run_transition_gates`` — that would no-op the patch.
    """
    return _mt_run_transition_gates(st)
