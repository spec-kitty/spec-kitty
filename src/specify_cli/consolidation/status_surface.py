"""The Mission's status surface: the branch status commits land on, and its tip now (pre-PR fold M7).

One neutral home for the two reads the fresh run's claim phase (``run_state._capture_coord_checkpoint``)
and the dry-run forecast (``claim_inputs``, FR-013) both make, so the forecast resolves its
coordination base exactly as the fresh run does without importing the executor family. Read-only:
placement resolution and ``git rev-parse`` never seed or materialize a surface.
"""

from __future__ import annotations

from pathlib import Path

from mission_runtime import MissionArtifactKind, resolve_placement_only

from specify_cli.core.git_ops import run_command

__all__ = ["status_surface_ref", "status_surface_tip"]


def status_surface_ref(main_repo: Path, mission_slug: str) -> str | None:
    """The branch status commits (``done`` bookkeeping, operator attestations) land on; ``None`` when unresolvable.

    The canonical write target ``resolve_placement_only(..., kind=STATUS_STATE)``:
    the coordination branch under a coordination topology, the target otherwise.
    """
    try:
        ref: str = resolve_placement_only(main_repo, mission_slug, kind=MissionArtifactKind.STATUS_STATE).ref
    except Exception:  # noqa: BLE001 — unresolvable placement: callers treat it as "no status surface"
        return None
    return ref


def status_surface_tip(main_repo: Path, mission_slug: str) -> tuple[str, str] | None:
    """``(ref, sha)`` of the status surface now (``git rev-parse <ref>``); ``None`` when either does not resolve."""
    ref = status_surface_ref(main_repo, mission_slug)
    if ref is None:
        return None
    ret, sha, _err = run_command(["git", "rev-parse", ref], capture=True, check_return=False, cwd=main_repo)
    if ret == 0 and sha.strip():
        return ref, sha.strip()
    return None
