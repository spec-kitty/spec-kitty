"""Post-merge retrospective postcondition check (WP07 — FR-007, Issue #1888).

Ensures the retrospective learning-capture fires on the ``spec-kitty merge``
completion path, not only on the ``spec-kitty next`` terminal-decision branch.

Public API:
    run_retrospective_postcondition(mission_slug, repo_root) -> None

Design invariants:
    * Fail-open: retrospective failure MUST NOT abort the merge.
    * Idempotent: if ``retrospective.yaml`` already exists the CAPTURE step is a
      no-op (no new event). The function still commits any leftover uncommitted
      retrospective artifacts (#2280 idempotency-heal): a prior run may have
      captured the record but failed to commit it (the commit is fail-open), so a
      clean re-run must land the dirty append rather than leave the durable event
      log dirty. A clean tree makes the commit a no-op — no double commit.
    * On failure, a ``retrospective.capture_failed`` event is appended to
      ``kitty-specs/<slug>/status.events.jsonl`` so the gap is auditable.
"""

from __future__ import annotations

import contextlib
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from kernel.git import GitCommandError, status_entries
from specify_cli.core.constants import RETROSPECTIVE_FILENAME
from specify_cli.mission_metadata import load_meta_or_empty
from specify_cli.status import BOUNDED_STATUS_LOCK_TIMEOUT_SECONDS

if TYPE_CHECKING:
    from specify_cli.retrospective.schema import ProvenanceKind

logger = logging.getLogger(__name__)

# The durable mission event log. Kept local (not imported from the migration-only
# module) so the post-merge terminus owns its own literal.
_STATUS_EVENTS_FILENAME = "status.events.jsonl"

FailureCategory = Literal[
    "missing_artifacts",
    "generator_exception",
    "schema_validation_error",
    "io_error",
    "other",
]

# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def run_retrospective_postcondition(
    *,
    mission_slug: str,
    repo_root: Path,
    provenance_kind: ProvenanceKind = "runtime_post_completion",
) -> None:
    """Run the post-merge retrospective postcondition check.

    Checks whether ``kitty-specs/<slug>/retrospective.yaml`` exists after a
    successful merge.  If it does not, invokes
    ``_run_retrospective_learning_capture`` from the runtime bridge to attempt
    best-effort capture (fail-open: failure is recorded but does NOT abort).

    This function is the canonical call-site for FR-007.  It consolidates the
    previously dead ``run_terminus`` path with the live runtime-bridge capture
    path so that merge completion always triggers the learning loop.

    Args:
        mission_slug: The mission slug (e.g. ``"017-my-feature"``).
        repo_root: Absolute path to the repository root (primary checkout).
        provenance_kind: Provenance to stamp on a freshly captured record
            (#3716). The ``mission close --discard`` leg passes
            ``"runtime_abandoned"`` so an abandoned mission is not tagged with
            completion provenance; the default keeps the merge/close-completion
            behaviour (``runtime_post_completion``).

    Note:
        ``run_terminus`` (the old dead-code stub in the lifecycle module) is
        superseded by this function.  Do not add new callers of ``run_terminus``.
    """
    # Late import to keep module-level import graph clean and to avoid heavy
    # optional deps being pulled in unconditionally at CLI startup.
    # FR-001/003 (#2119): route through the single durable-home authority so the
    # post-merge terminus reads/writes the retrospective in the PRIMARY home for
    # every topology — never the materialized ``-coord`` husk (the #1771 leak).
    from specify_cli.retrospective.writer import resolve_retrospective_home  # noqa: PLC0415

    feature_dir = resolve_retrospective_home(repo_root, mission_slug)

    # T031 — Merge-completion postcondition: check for retrospective.yaml.
    retro_path = feature_dir / RETROSPECTIVE_FILENAME
    if retro_path.exists():
        # Idempotency-heal (#2280): a prior run may have CAPTURED the record but
        # FAILED to commit it (the commit below is fail-open). Do NOT return
        # early — skipping straight to the commit-of-uncommitted-artifacts below
        # re-commits any leftover dirty append instead of leaving the durable
        # event log dirty forever. Capture itself is the only no-op here.
        logger.debug(
            "retrospective.yaml already exists for mission %s — skipping capture; "
            "healing any uncommitted retrospective append",
            mission_slug,
        )
    else:
        # Resolve mission_id (T034 — use canonical path from feature_dir, not a
        # stale NNN-slug-based path).  Legacy missions pre-083 may lack a ULID
        # mission_id; fall back to empty string so the event is still valid.
        mission_id = _resolve_mission_id(feature_dir)

        # fsm-write-path-integrity WP01 (FR-003 b / NFR-003): this runs on the
        # ``spec-kitty merge`` completion path, under the merge-global sentinel
        # (L5). Every mission status-lock (L1) take the retrospective appenders
        # make from here -- ``emit_captured`` reached through the runtime
        # bridge, and ``emit_capture_failed`` below -- is bounded by the scoped
        # timeout, so a stalled status writer surfaces as a structured
        # ``FeatureStatusLockTimeoutError`` (caught by the fail-open handlers
        # below, i.e. a failed retrospective step) instead of converting into
        # an unbounded, repo-wide merge refusal (R7).
        from specify_cli.retrospective.lifecycle_events import bounded_lock_timeout

        # T032 — Call the live capture path (not a duplicate implementation).
        with bounded_lock_timeout(BOUNDED_STATUS_LOCK_TIMEOUT_SECONDS):
            try:
                _invoke_capture(
                    mission_id=mission_id,
                    mission_slug=mission_slug,
                    feature_dir=feature_dir,
                    repo_root=repo_root,
                    provenance_kind=provenance_kind,
                )
            except Exception as exc:  # noqa: BLE001 — fail-open: record but don't abort
                logger.warning(
                    "post-merge retrospective capture failed for mission %s: %s",
                    mission_slug,
                    exc,
                )
                # T033 — Emit capture_failed event so the gap is auditable.
                _emit_capture_failed(
                    mission_id=mission_id,
                    mission_slug=mission_slug,
                    repo_root=repo_root,
                    exc=exc,
                )

    # #2119 follow-up: commit whatever the capture wrote — the RetrospectiveCaptured
    # event + retrospective.yaml on success, or the capture_failed event append on
    # failure. Both merge and `mission close` funnel through here, so committing at
    # this single seam keeps the two paths consistent and honours the atomic
    # event-log discipline (FR-016): a merged/closed mission must never be left with
    # an uncommitted append in its durable status.events.jsonl. Fail-open-but-loud —
    # a commit failure is reported, never raised (must not abort merge/close).
    _commit_captured_retrospective(
        mission_slug=mission_slug,
        feature_dir=feature_dir,
        repo_root=repo_root,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _primary_target_branch(feature_dir: Path) -> str | None:
    """Return the mission's PRIMARY ``target_branch`` from ``meta.json``, or None.

    Used as a fail-closed-avoiding degrade ref for the bookkeeping commit (#3716):
    a legacy mission whose ``meta.json`` is missing/malformed or lacks
    ``target_branch`` yields ``None`` (unchanged pre-#3716 behaviour — the commit
    then raises-and-warns rather than silently degrading to a null ref).
    """
    data = load_meta_or_empty(feature_dir)
    if isinstance(data, dict):
        target = str(data.get("target_branch") or "").strip()
        if target:
            return target
    return None


def _resolve_mission_id(feature_dir: Path) -> str:
    """Return the ULID mission_id from meta.json, or empty string for legacy missions."""
    # T034 — use the canonical feature_dir path (already resolved by the caller);
    # never reconstruct a path with a NNN- numeric prefix.
    # load_meta_or_empty (post-#2091 silent contract) absorbs a missing or
    # malformed meta.json to {}, matching the prior try/except-"" absorption.
    data = load_meta_or_empty(feature_dir)
    return str(data.get("mission_id") or "")


def _invoke_capture(
    *,
    mission_id: str,
    mission_slug: str,
    feature_dir: Path,
    repo_root: Path,
    provenance_kind: ProvenanceKind = "runtime_post_completion",
) -> None:
    """Delegate to the runtime-bridge capture implementation (T032).

    Reuses ``_run_retrospective_learning_capture`` from the
    ``runtime.next.runtime_bridge_retrospective`` seam — does NOT duplicate the
    implementation. ``block_on_failure=False`` keeps the merge/close fail-open.

    The seam is imported directly (rather than through the thin
    ``runtime_bridge`` compat delegate) so the ``provenance_kind`` override
    (#3716) reaches the facilitator: the delegate's signature is a fixed
    five-kwarg forward that cannot carry the new argument. The seam's own
    intra-cluster calls still route through the live ``runtime_bridge`` lookup,
    so per-symbol monkeypatch observation is unchanged.
    """
    from runtime.next.runtime_bridge_retrospective import (  # noqa: PLC0415
        _run_retrospective_learning_capture,
    )

    _run_retrospective_learning_capture(
        mission_id=mission_id,
        mission_slug=mission_slug,
        feature_dir=feature_dir,
        repo_root=repo_root,
        block_on_failure=False,
        provenance_kind=provenance_kind,
    )


def _paths_with_uncommitted_changes(repo_root: Path, paths: list[Path]) -> tuple[Path, ...]:
    """Return the subset of ``paths`` that differ from HEAD or are untracked.

    Fail-open (module contract): this helper MUST NOT raise. In particular the
    absolute→relative fold below resolves BOTH sides before comparing (mirroring
    ``safe_commit``) so a symlinked ``repo_root`` cannot raise ``ValueError`` out
    of ``Path.relative_to`` and abort the merge/close.
    """
    resolved_root = repo_root.resolve()
    dirty: list[Path] = []
    for path in paths:
        if not path.exists():
            continue
        rel = str(path)
        if path.is_absolute():
            # A symlinked repo_root would make a naive relative_to() raise; resolve
            # both sides and suppress the mismatch so we stay fail-open (fall back
            # to the absolute path, which git accepts inside the worktree).
            with contextlib.suppress(ValueError):
                rel = str(path.resolve().relative_to(resolved_root))
        try:
            entries = status_entries(repo_root, pathspecs=(rel,), untracked=None)
        except GitCommandError:
            # Advisory (module contract: fail-open, MUST NOT raise): a probe that
            # failed reports the path as not dirty, exactly as before.
            continue
        if entries:
            dirty.append(path)
    return tuple(dirty)


def _commit_captured_retrospective(
    *,
    mission_slug: str,
    feature_dir: Path,
    repo_root: Path,
) -> None:
    """Commit the just-captured retrospective + its event-log append.

    Routes through the ONE sanctioned protected-flow bookkeeping-commit surface
    (``git.bookkeeping_commit.commit_merge_bookkeeping``) that the ``spec-kitty
    merge`` executor also uses, so the auto-capture path (merge OR ``mission
    close``) never leaves the durable event log with an uncommitted append and
    there is no second guard-capability call site outside the merge executor.

    Fail-open-but-loud: any failure is reported via a WARNING (surfaced by the CLI
    logging bootstrap) with the exact remediation command, and NEVER raised — the
    caller must not abort the merge/close.
    """
    candidates = [feature_dir / RETROSPECTIVE_FILENAME, feature_dir / _STATUS_EVENTS_FILENAME]
    paths = _paths_with_uncommitted_changes(repo_root, candidates)
    if not paths:
        return  # nothing the capture wrote is dirty — already committed or absent

    # coord-write-placement-closure-01KYCF83 WP03/FR-003: the destination is
    # resolved through the placement port (mission_slug -> commit_merge_bookkeeping)
    # rather than an ambient ``get_current_branch(repo_root)`` HEAD read — the
    # CWD-dependent branch-detection fallback this mission retires. Any failure
    # to resolve/commit (unresolvable mission, detached HEAD/HEAD-mismatch,
    # non-git worktree, ...) is caught below and reported, never raised — the
    # caller must not abort the merge/close.
    from specify_cli.git.bookkeeping_commit import commit_merge_bookkeeping  # noqa: PLC0415

    # #3716: on the ``mission close --discard`` leg the coordination context is
    # being torn down, so ``resolve_write_target_or_degrade`` fails closed and —
    # with no degrade ref — the retrospective commit degrades, leaving the durable
    # event log + retrospective.yaml uncommitted. Supply the mission's PRIMARY
    # ``target_branch`` as the degrade path so the commit lands on the primary
    # surface (never the now-deleted coordination branch). Consulted ONLY when
    # placement resolution genuinely fails; the merge path (which resolves) is
    # unaffected.
    degrade_ref = _primary_target_branch(feature_dir)

    try:
        commit_merge_bookkeeping(
            repo_root=repo_root,
            worktree_root=repo_root,
            mission_slug=mission_slug,
            message=f"chore({mission_slug}): capture mission retrospective",
            paths=paths,
            branch=degrade_ref,
        )
        logger.debug("committed retrospective bookkeeping for mission %s", mission_slug)
    except Exception as exc:  # noqa: BLE001 — fail-open: report but never abort merge/close
        joined = " ".join(str(p) for p in paths)
        logger.warning(
            "retrospective for mission %s was captured but could NOT be committed: %s. "
            "The durable event log has an uncommitted append. Commit it manually: "
            "git -C %s add %s && git -C %s commit -m 'chore(%s): capture mission retrospective'",
            mission_slug,
            exc,
            repo_root,
            joined,
            repo_root,
            mission_slug,
        )


def _emit_capture_failed(
    *,
    mission_id: str,
    mission_slug: str,
    repo_root: Path,
    exc: Exception,
) -> None:
    """Emit a ``retrospective.capture_failed`` event (T033).

    Appends the event to ``kitty-specs/<slug>/status.events.jsonl`` so the
    gap is auditable.  This helper is intentionally best-effort: if the emit
    itself fails we log and swallow so the merge is never aborted.
    """
    try:
        from specify_cli.retrospective.lifecycle_events import (  # noqa: PLC0415
            Actor,
            emit_capture_failed,
        )

        _classify = _classify_exc(exc)
        system_actor = Actor(kind="runtime", id="spec-kitty-merge-postcondition")

        emit_capture_failed(
            mission_id=mission_id,
            mission_slug=mission_slug,
            repo_root=repo_root,
            failure_category=_classify,
            failure_message=f"post-merge retrospective capture: {exc!s}",
            remediation_hint=(
                "Run `spec-kitty agent retrospect synthesize --mission <slug>` "
                "to retry retrospective capture after merge."
            ),
            policy_source={"source": "merge_postcondition"},
            attempted_provenance_kind="runtime_post_completion",
            missing_artifacts=None,
            actor=system_actor,
            execution_mode="main",
            # FR-003 (b): explicit finite bound on the merge-path L1 take.
            lock_timeout=BOUNDED_STATUS_LOCK_TIMEOUT_SECONDS,
        )
    except Exception as emit_exc:  # noqa: BLE001
        logger.warning(
            "could not emit capture_failed event for mission %s: %s",
            mission_slug,
            emit_exc,
        )


def _classify_exc(exc: Exception) -> FailureCategory:
    """Map an exception to a failure_category string."""
    if isinstance(exc, (FileNotFoundError, IsADirectoryError)):
        return "missing_artifacts"
    if isinstance(exc, (OSError, PermissionError)):
        return "io_error"
    return "generator_exception"
