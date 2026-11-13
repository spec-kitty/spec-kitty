"""The branch a checkout has checked out, with a caller-supplied fallback."""

from __future__ import annotations

from pathlib import Path

from specify_cli.core.git_ops import get_current_branch


def checkout_branch_or_fallback(checkout: Path, fallback_branch: str) -> str:
    """The branch *checkout* has checked out, or *fallback_branch* when it is detached or unreadable.

    The one current-checkout HEAD read the protected-branch preflights share: the claim
    preflight (``implement_claim._claim_checkout_branch``) and move-task's WP-file holder
    (``tasks_shared._wp_file_commit_branch``) both judge the branch of the checkout the
    commit runs in (#7601, decision ``01M78JFMRQS6GE04BENPXGQX8J``). Tracked by #2453.
    """
    return get_current_branch(checkout) or fallback_branch
