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


def status_surface_ref(main_repo: Path, mission_slug: str, *, retarget: tuple[str, str] | None = None) -> str | None:
    """The branch status commits (``done`` bookkeeping, operator attestations) land on; ``None`` when unresolvable.

    The canonical write target ``resolve_placement_only(..., kind=STATUS_STATE)``:
    the coordination branch under a coordination topology, the target otherwise.

    ``retarget=(from, to)`` (#7692): a run retargeting the Mission reads the surface the
    run's writes go to, so a resolved ref equal to ``from`` (the old recorded target, on a
    coordination-less topology) reads as ``to``. A coordination branch is left alone by
    construction. ``None`` keeps today's resolution (the forecast, every other caller).
    """
    try:
        ref: str = resolve_placement_only(main_repo, mission_slug, kind=MissionArtifactKind.STATUS_STATE).ref
    except Exception:  # noqa: BLE001 — unresolvable placement: callers treat it as "no status surface"
        return None
    return _retargeted(ref, retarget)


def _retargeted(ref: str, retarget: tuple[str, str] | None) -> str:
    """*ref*, or the new target when *ref* is the old recorded target of ``retarget=(from, to)`` (#7692)."""
    return retarget[1] if retarget is not None and ref == retarget[0] else ref


def status_surface_tip(main_repo: Path, mission_slug: str, *, retarget: tuple[str, str] | None = None) -> tuple[str, str] | None:
    """``(ref, sha)`` of the status surface now (``git rev-parse <ref>``); ``None`` when either does not resolve.

    ``retarget`` maps the resolved ref as :func:`status_surface_ref` does (#7692).
    """
    ref = status_surface_ref(main_repo, mission_slug)
    if ref is None:
        return None
    ref = _retargeted(ref, retarget)
    ret, sha, _err = run_command(["git", "rev-parse", ref], capture=True, check_return=False, cwd=main_repo)
    if ret == 0 and sha.strip():
        return ref, sha.strip()
    return None
