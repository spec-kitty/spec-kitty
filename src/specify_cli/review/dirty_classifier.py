"""Dirty-path classifier for review handoff.

Partitions ``git status --porcelain`` file paths into two buckets:

- **blocking**: files owned by the current WP that must be committed before
  moving to ``for_review``.
- **benign**: files that change for legitimate concurrent-agent reasons
  (status artifacts, other WPs' task files, generated metadata) and should
  NOT block the review handoff.

Usage::

    from specify_cli.review.dirty_classifier import classify_dirty_paths

    blocking, benign = classify_dirty_paths(
        dirty_paths=["src/foo.py", "kitty-specs/066-foo/status.events.jsonl"],
        wp_id="WP01",
        mission_slug="066-foo",
    )
"""

from __future__ import annotations

import re

from specify_cli.coordination.coherence import is_toolchain_generated_churn
from kernel.paths import to_posix


def _is_review_handoff_survivor_path(normalised: str) -> bool:
    """Review-handoff-only benign paths the shared owner cannot classify.

    Justified survivor (IC-07g / WP17; registry row
    ``_is_review_handoff_survivor_path.md``, status ``justified-survivor`` —
    mirrors the WP15 precedent ``_is_review_lifecycle_basename``). Retiring the
    four former module-level filename/prefix/regex collections that fed the
    review-handoff gate onto
    :func:`specify_cli.coordination.coherence.is_toolchain_generated_churn`
    wholesale is NOT possible without changing that owner's answer for the
    merge/accept gates that also consult it (a regression, C6):

    - ``lanes.json`` is the ``LANE_STATE`` kind, a PRIMARY-partition mission
      artifact (``mission_runtime._PRIMARY_ARTIFACT_KINDS``) — a stale copy of it
      IS real dirt for the merge/accept gate by design (the owner's
      ``is_coord_residue_churn`` leg correctly returns ``False`` for it); only
      review handoff treats an in-flight rewrite by ``finalize-tasks`` / the lane
      allocator as benign.
    - ``.kittify/`` config/metadata files are not ``kitty-specs/<slug>/`` mission
      artifacts at all — no ``MissionArtifactKind`` applies to most of them
      (parallel to WP15's ``notes.md`` / ``review-cycle-*.md``); only the single
      nested ``.kittify/encoding-provenance/global.jsonl`` path is covered by the
      owner's self-bookkeeping leg.
    - any WP's ``tasks/WP##-*.md`` task file, and the mission-root ``tasks.md``,
      are the ``WORK_PACKAGE_TASK`` / ``TASKS_INDEX`` kinds — also
      PRIMARY-partition, auto-committed by ``move-task`` / ``mark-status`` as
      toolchain writes-in-flight — but the merge/accept gate must still block a
      genuinely-uncommitted one; only review handoff treats them as benign.

    The filename / suffix / regex literals are function-local (not module-level
    ``frozenset`` / ``tuple`` / ``re.compile`` assignments) so the R-014
    exemption-registry scan — which only walks module-level assignments
    (``tests/architectural/test_exemption_registry_ratchet.py``) — does not treat
    this as a NEW per-gate filename exemption requiring the collection-scan's
    row (mirrors :func:`specify_cli.coordination.coherence.is_self_bookkeeping_churn`'s
    function-local ``kitty-ops`` regex). It is still explicitly enumerated —
    ``literals: (none)`` — and held accountable by the symbol-presence arm
    instead (the WP15 precedent).
    """
    basename = normalised.rsplit("/", 1)[-1] if "/" in normalised else normalised

    # lanes.json (LANE_STATE, PRIMARY-partition) — see docstring bullet 1.
    if basename == "lanes.json":
        return True

    # .kittify/ config/metadata (no MissionArtifactKind) — see docstring bullet 2.
    kittify_prefixes = (".kittify/", ".kittify" + "\\")  # trailing arm: Windows paths — defensive
    if normalised.startswith(kittify_prefixes) or normalised == ".kittify":
        return True

    # Any WP's FLAT task file (WORK_PACKAGE_TASK, PRIMARY-partition) — bullet
    # 3. Tightened per adversarial plan review (PLAN-ARCH-001): the prior
    # `.+` was not `/`-anchored, so it over-matched ANY nested `.md` file
    # under ANY WP directory in ANY mission (e.g. a WP's own
    # `tasks/WP01-foo/scratch.md`, or a different mission's
    # `tasks/WP01-foo/x.md`), short-circuiting `_is_benign` to `True` before
    # `owning_wp_for_path` was ever consulted — silently defeating spec.md
    # AC3 and FR-008 for a nested-`.md` shape. `[^/]+` cannot cross a `/`, so
    # only a FLAT `tasks/WPxx-*.md` file matches here now; a nested path
    # falls through to `owning_wp_for_path` in `classify_dirty_paths`, which
    # resolves it correctly (own-WP → blocking; unattributable/cross-mission
    # → blocking; genuine cross-WP → benign).
    # Anchored full-string match (PR-FRESH-001 Bug A): ``.search()`` with no
    # ``^`` let a composite "old -> new" rename-porcelain string (or any
    # other larger string) match on a trailing substring alone -- e.g. a
    # rename whose *new* side happens to look like a flat WPxx task file
    # short-circuited to benign regardless of what the *old* side was.
    # ``fullmatch`` requires the ENTIRE string to satisfy the pattern.
    wp_task_pattern = re.compile(r"kitty-specs/[^/]+/tasks/WP\d+-[^/]+\.md$")
    if wp_task_pattern.fullmatch(normalised):
        return True

    # Mission-root tasks.md (TASKS_INDEX, PRIMARY-partition) — bullet 3.
    root_tasks_md_pattern = re.compile(r"kitty-specs/[^/]+/tasks\.md$")
    if root_tasks_md_pattern.search(normalised):
        return True

    return False


def _is_benign(path: str, wp_id: str) -> bool:
    """Return True if *path* is a benign (non-blocking) dirty file.

    A path is benign when it satisfies any of the following:

    1. It is toolchain-generated churn the shared
       :func:`specify_cli.coordination.coherence.is_toolchain_generated_churn`
       owner recognises — spec-kitty's own bookkeeping (``meta.json``,
       encoding-provenance JSONL, a ``kitty-ops/<ULID>.jsonl`` Op-record orphan)
       or a recognised coordination-residue artifact (``status.events.jsonl``,
       ``status.json``) — delegated with NO independent literal here (#2251 /
       FR-001 / G-5 invariant; IC-07g retired the former status/meta filename
       entries onto this owner-module leg).
    2. It is one of the genuine review-handoff-only survivors the owner cannot
       classify — see :func:`_is_review_handoff_survivor_path`.
    """
    # Normalise separators for cross-platform safety
    normalised = to_posix(path).strip()

    if is_toolchain_generated_churn(normalised):
        return True

    return _is_review_handoff_survivor_path(normalised)


def owning_wp_for_path(path: str, mission_slug: str) -> str | None:
    """Return the WP id that owns *path* by directory/file-naming convention, or None.

    Generalizes the flat ``.md``-only convention ``_is_review_handoff_survivor_path``'s
    ``wp_task_pattern`` implements (now tightened to a flat-only match — see that
    function) to also cover:

    - any file nested under a WP's task directory, any extension (FR-002)
    - the WP task directory reported as a bare, wholly-untracked path (FR-003)

    Scoped to *mission_slug* (FR-008): a same-numbered WP under a different
    mission's ``kitty-specs/<other-slug>/tasks/`` tree never matches.

    This is a pure path-string regex over the ``kitty-specs/<mission_slug>/
    tasks/WP<n>-*`` directory-naming convention — it does not read, import, or
    extend ``src/specify_cli/ownership/`` (the ``owned_files``
    frontmatter-driven module), which cannot answer this question for
    ``kitty-specs/`` paths on ``code_change`` WPs (C-001).

    Deliberately public (no leading underscore) — consumed cross-module by
    ``tasks_parsing_validation.py`` via a direct submodule import, mirroring
    how that module already imports :func:`classify_dirty_paths`.

    Guarded against a rename-form composite ``"old -> new"`` porcelain
    string (PR-FRESH-001 Bug B): the trailing ``(?:\\.md|/.*)$`` alternation's
    ``.*`` matches any character, so it would otherwise absorb an embedded
    ``" -> "`` rename arrow and the new path whole, resolving ownership from
    the OLD path's prefix alone even when the new path lands inside a
    different WP's own directory. A composite is never a single real path,
    so it is explicitly rejected (returns ``None`` -- unattributable,
    fail-closed) before the regex ever runs, rather than trying to teach the
    regex two-sided rename semantics.
    """
    normalised = to_posix(path).strip()
    if " -> " in normalised or normalised.count("kitty-specs/") > 1:
        return None
    pattern = re.compile(rf"^kitty-specs/{re.escape(mission_slug)}/tasks/WP(\d+)-[^/]+(?:\.md|/.*)$")
    match = pattern.fullmatch(normalised)
    return f"WP{match.group(1)}" if match else None


def classify_dirty_paths(
    dirty_paths: list[str],
    wp_id: str,
    mission_slug: str,
    wp_slug: str | None = None,
) -> tuple[list[str], list[str]]:
    """Classify dirty paths as blocking or benign.

    Args:
        dirty_paths: Paths from ``git status --porcelain`` (the file-path
            portion, **after** stripping the two-character status prefix).
        wp_id: Current WP ID (e.g. ``"WP01"``).
        mission_slug: Mission slug (e.g. ``"066-review-loop-stabilization"``).
        wp_slug: Optional WP slug for task-file matching
            (e.g. ``"WP01-persisted-review-artifact-model"``).  When
            provided, a path that matches ``tasks/{wp_slug}.md`` is treated as
            blocking.  Not strictly necessary because the regex already handles
            the ``WP<id>`` prefix, but accepted for API completeness.

    Returns:
        A tuple ``(blocking, benign)`` — two lists of path strings.  Each
        input path appears in exactly one of the two lists.

    Ownership attribution (FR-001–004, FR-007, FR-008): a path not already
    benign under :func:`_is_benign` (toolchain churn, or a flat any-WP
    ``tasks/WPxx-*.md`` task file) is checked against
    :func:`owning_wp_for_path`. When it resolves to a *different* WP than
    *wp_id*, the path is provably that other WP's residue and is benign
    (FR-001/002/003). When it resolves to *wp_id* itself (the WP's own
    non-task-file residue, FR-007) or to ``None`` (unattributable, FR-004 —
    fail-closed), the path stays blocking.
    """
    blocking: list[str] = []
    benign: list[str] = []

    for path in dirty_paths:
        if not path:
            continue
        if _is_benign(path, wp_id):
            benign.append(path)
            continue
        owner = owning_wp_for_path(path, mission_slug)
        if owner is not None and owner != wp_id:
            benign.append(path)  # FR-001/002/003 — provably another WP's residue
        else:
            blocking.append(path)  # owner == wp_id (FR-007) or owner is None (FR-004)

    return blocking, benign
