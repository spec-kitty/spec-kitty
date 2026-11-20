"""The one claim release for a move into ``planned`` (#2512, #4673, #7644).

A work package returned to ``planned`` goes back to the pool: its runtime claim
(``agent`` / ``shell_pid`` / ``shell_pid_created_at``) is released, and the
``review`` override slot (a "superseded by approval" note) is cleared, since it no
longer describes the work package. The release rides an ``InnerStateChanged``
annotation carrying ``release_runtime_claim=True``, which the reducer applies as a
real clear of the claim triple (unlike a bare blank value, which it ignores). The
reducer's ``implementer_of_record`` projection (#4786) is not a release slot and
survives.

``move-task --to planned`` and ``orchestrator-api transition --to planned`` both
build their release from this module, so the two paths cannot drift.
"""

from __future__ import annotations

from typing import Any

from specify_cli.status.models import ReviewOverride, WPInnerStateDelta

__all__ = ["planned_claim_release_delta", "planned_claim_release_fields"]


def planned_claim_release_fields() -> dict[str, Any]:
    """The release as ``WPInnerStateDelta`` keyword fields (for callers that merge more fields in)."""
    return {
        "release_runtime_claim": True,
        # An all-empty override is the reducer's "clear the review slot" sentinel.
        "review": ReviewOverride(at="", actor="", wp_id="", reason=""),
    }


def planned_claim_release_delta() -> WPInnerStateDelta:
    """The release as one annotation delta, ready to ride a ``planned`` transition."""
    return WPInnerStateDelta(**planned_claim_release_fields())
