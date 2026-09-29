"""Repo-root write-checkout occupancy and dirtiness helpers (#5100 IC-03 / T018).

A single_branch mission's repo-root lane has no worktree of its own -- every
WP in it executes directly in the shared write checkout. Two or more
single_branch missions (or two WPs of the same mission) can therefore contend
for that ONE checkout at once. This module supplies the two pure(ish) reads
``implement``'s repo-root-lane refusal path composes:

- :func:`in_progress_wps_in_write_checkout` -- is another WP (from ANY
  single_branch mission) already ``in_progress`` in this checkout?
- :func:`dirty_paths` -- does the checkout carry uncommitted changes outside
  spec-kitty's own status/runtime artifacts?

Kept out of ``worktree_allocator.py`` (a different concern: THAT module
allocates/reuses a *lane worktree*; this module inspects the *shared
repo-root checkout* no allocation ever touches) and out of
``workspace/context.py`` (a pure resolver, no git/status I/O).
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from mission_runtime import is_single_branch

__all__ = ["dirty_paths", "in_progress_wps_in_write_checkout"]

_KITTY_SPECS_DIR = "kitty-specs"


def in_progress_wps_in_write_checkout(
    repo_root: Path,
    write_checkout: Path,
    *,
    exclude: tuple[str, str] | None = None,
) -> list[tuple[str, str]]:
    """Return ``(mission_slug, wp_id)`` pairs ``in_progress`` in *write_checkout*.

    Scans every mission under ``kitty-specs/`` whose STORED topology
    (:func:`specify_cli.migration.backfill_topology.read_topology`) is
    ``single_branch`` -- the only topology whose WPs ever execute in a shared
    repo-root checkout rather than a per-lane worktree, so this is the whole
    candidate set (NFR-002: bounded scan, status-tail reads only, no git
    subprocess). A single_branch mission's write checkout has no persisted
    alternate root (``effective_root`` is a per-invocation resolver
    parameter, never written to disk), so every single_branch mission's
    checkout is *repo_root* -- this is compared against *write_checkout*
    directly rather than re-resolving each mission's workspace.

    A mission whose ``meta.json`` cannot be read (missing/corrupt) is
    skipped: it never rendered here before this scan existed either, and one
    bad mission's metadata must not block every OTHER mission's implement.

    *exclude* removes one ``(mission_slug, wp_id)`` pair from the result --
    the caller's own WP, so resuming a WP it already holds ``in_progress``
    never reads as occupancy by another WP (contract's resume exemption).
    """
    from specify_cli.context.mission_resolver import list_missions_for_selection
    from specify_cli.core.paths import MissionMetaReadError
    from specify_cli.migration.backfill_topology import read_topology
    from specify_cli.status import Lane
    from specify_cli.status import read_events as _read_events
    from specify_cli.status import reduce as _reduce_events

    write_checkout_resolved = write_checkout.resolve()
    if write_checkout_resolved != repo_root.resolve():
        # No single_branch mission's checkout can be anything other than
        # repo_root without a persisted alternate root -- see the docstring.
        return []

    occupied: list[tuple[str, str]] = []
    for listing in list_missions_for_selection(repo_root):
        mission_slug = listing.mission_slug
        feature_dir = repo_root / _KITTY_SPECS_DIR / mission_slug
        try:
            topology = read_topology(feature_dir)
        except (FileNotFoundError, MissionMetaReadError, ValueError):
            continue
        if not is_single_branch(topology):
            continue

        snapshot = _reduce_events(_read_events(feature_dir))
        for wp_id, wp_state in snapshot.work_packages.items():
            if exclude == (mission_slug, wp_id):
                continue
            if wp_state.get("lane") == Lane.IN_PROGRESS:
                occupied.append((mission_slug, wp_id))
    return occupied


def _is_owned_path(path: str, owned_prefixes: Sequence[str]) -> bool:
    """True when *path* is, or is nested under, one of *owned_prefixes*."""
    for prefix in owned_prefixes:
        if path == prefix:
            return True
        if prefix.endswith("/") and path.startswith(prefix):
            return True
    return False


def dirty_paths(write_checkout: Path, *, owned_prefixes: Sequence[str]) -> list[str]:
    """Return changed paths in *write_checkout*, excluding *owned_prefixes*.

    Reuses the worktree allocator's single ``git status --porcelain`` vehicle
    (:func:`specify_cli.lanes.worktree_allocator._git_status_porcelain_lines`)
    instead of duplicating its subprocess call. A path equal to, or nested
    under (prefix ending in ``/``), any of *owned_prefixes* -- spec-kitty's
    own status/runtime artifacts, e.g. ``kitty-specs/<slug>/status.events.jsonl``,
    ``kitty-specs/<slug>/status.json``, ``.kittify/`` -- is never reported as
    dirty; the caller decides the concrete prefix list (NFR-004: names what
    it excludes).
    """
    from specify_cli.lanes.worktree_allocator import _git_status_porcelain_lines

    paths: list[str] = []
    for line in _git_status_porcelain_lines(write_checkout):
        # Porcelain short format: "XY PATH" (a rename reads "XY OLD -> NEW").
        raw = line[3:] if len(line) > 3 else line.strip()
        path = raw.split(" -> ", 1)[-1].strip()
        if not path or _is_owned_path(path, owned_prefixes):
            continue
        paths.append(path)
    return paths
