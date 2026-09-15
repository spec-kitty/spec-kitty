"""Commit-on-record for the Decision Moment ledger (#4311).

Robert's 2026-09-14 ruling (planning#2269): Zeitgeist carries NOW, Git carries
DONE, and mission decisions must be BOTH — "I need decisions in real time AND
as a permanent record." The permanent half is this module: every ledger change
a decision record makes (``decisions/index.json``, the ``DM-<ulid>.md``
artifact, and the ``status.events.jsonl`` row the emit step appended) is
committed through the ONE coordination write seam
(:func:`specify_cli.coordination.write_seam.write_artifact`, kind
``DECISION_LEDGER``) in the same operation that recorded it. A resolved
decision is therefore never left sitting uncommitted in the working tree of a
routable mission.

Idempotence (issue #4311 Required 1) is inherited, not re-implemented: the
seam's own contract returns ``"unchanged"`` for a byte-identical artifact
already committed at the resolved placement, so a crash-then-rerun or a
duplicate record never produces an empty commit. The service only calls this
module when a ledger change actually happened — the idempotent re-open and
the same-payload terminal re-run short-circuit before reaching here.

The commit is LOCAL by design. GOAL.md permanently defers auto-push, so
"permanent" means committed in the checkout and visible to the team on the
next normal push; nothing here pushes, and the CLI says so in its output.

Failure honesty over failure-masking: an unroutable target (the seam's
FR-011 zero-write refusal — missing coord surface, deleted target branch)
or a commit error is returned as a structured :class:`LedgerCommitReport`
with the seam's own diagnostic, never raised into the caller — the ledger
row and its event are already durably on disk, and losing the record because
its commit hiccupped would be the worse failure. The report is what the CLI
prints loudly (and what a caller can act on); it is never silently dropped.
"""

from __future__ import annotations

import logging
from pathlib import Path

from mission_runtime import MissionArtifactKind
from specify_cli.decisions.models import LedgerCommitReport

__all__ = ["commit_ledger_change"]

logger = logging.getLogger(__name__)

#: The commit-message verb for each recording action, kept in one place so
#: the git history reads uniformly ("record open of DM-…", "record resolved …").
_ACTIONS = ("open", "resolved", "deferred", "canceled", "repaired")

#: The two ledger files plus the companion event log a record touches. The
#: event log is the ``STATUS_STATE`` kind's file, but it is committed in the
#: same DECISION_LEDGER batch: both kinds are COORD-partition, so the seam's
#: per-file partition grouping routes every file to the same surface, and one
#: commit carries the whole record (ledger + its event) atomically.
_INDEX_FILE = "index.json"
_EVENTS_FILE = "status.events.jsonl"


def commit_ledger_change(
    repo_root: Path,
    mission_slug: str,
    mission_dir: Path,
    decision_id: str,
    *,
    action: str,
) -> LedgerCommitReport:
    """Commit one decision record's ledger change through the write seam.

    Args:
        repo_root:    Primary checkout root (the same root the service
                      resolved ``mission_dir`` from).
        mission_slug: The mission slug.
        mission_dir:  The kind-routed mission directory the store already
                      wrote the ledger into (``read_dir(STATUS_STATE)`` —
                      the same surface ``write_target(DECISION_LEDGER)``
                      resolves for every topology, so the files the store
                      materialized are the files the seam commits).
        decision_id:  The ULID decision id (names the DM artifact and the
                      commit's ``entry_id``).
        action:       The recording action, for the commit message (one of
                      :data:`_ACTIONS`).

    Returns:
        A :class:`LedgerCommitReport`; never raises — every failure mode
        (unroutable target, git error, an unexpected seam defect) is a
        structured report carrying the diagnostic.
    """
    if action not in _ACTIONS:
        raise ValueError(f"unknown ledger commit action {action!r}")

    # Function-local imports on purpose: the write seam pulls the git and
    # coordination machinery, none of which belongs on the decisions
    # package's import-time surface (the cold-import boundary tests).
    from specify_cli.coordination.write_seam import write_artifact
    from specify_cli.core.paths import get_feature_target_branch
    from specify_cli.git.protection_policy import ProtectionPolicy

    d_dir = mission_dir / "decisions"
    candidates = (
        d_dir / _INDEX_FILE,
        d_dir / f"DM-{decision_id}.md",
        mission_dir / _EVENTS_FILE,
    )
    files = tuple(path for path in candidates if path.exists())
    if not files:
        return LedgerCommitReport(
            status="error",
            diagnostic=(f"ledger commit for {decision_id!r} found no materialized ledger files under {mission_dir}"),
        )

    try:
        policy = ProtectionPolicy.resolve(repo_root)
        try:
            target_branch = get_feature_target_branch(repo_root, mission_slug)
        except Exception:  # noqa: BLE001 - best-effort ff-advance target only
            target_branch = None
        result = write_artifact(
            repo_root=repo_root,
            mission_slug=mission_slug,
            kind=MissionArtifactKind.DECISION_LEDGER,
            files=files,
            message=f"chore(decisions): record {action} of DM-{decision_id} for {mission_slug}",
            policy=policy,
            entry_id=decision_id,
            target_branch=target_branch,
        )
    except Exception:
        logger.warning(
            "decision ledger commit failed for %s (%s); ledger row stays on disk",
            decision_id,
            action,
            exc_info=True,
        )
        return LedgerCommitReport(
            status="error",
            diagnostic=f"ledger commit raised for decision {decision_id!r}; see log",
        )

    if result.status in ("committed", "unchanged"):
        return LedgerCommitReport(
            status=result.status,
            surface=result.destination_surface,
            commit_hash=result.commit_hash,
        )
    # "refused" (FR-011 zero-write) and "error"/"no_op_wrong_surface" both
    # carry the seam's own diagnostic — project the status, never re-derive
    # the reason.
    return LedgerCommitReport(
        status="refused" if result.status == "refused" else "error",
        surface=result.destination_surface,
        diagnostic=result.diagnostic,
    )
