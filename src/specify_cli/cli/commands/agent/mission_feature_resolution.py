"""Shared feature-dir resolution seam for ``agent mission`` (#2056 Seam D).

This module hosts the mission-handle → on-disk-directory resolution surface that
``mission.py`` (and, via the WP09 shim re-export, every historical
``mission.<name>`` patch target) shares with the lifecycle commands. It is a
**one-way** leaf: it imports lower layers only
(``missions._read_path_resolver``, ``core``, ``mission_runtime``,
``mission_metadata``) and NEVER back into ``mission`` or any other seam (INV-8).

#2113 / gate-read-surface-completion: this leaf also hosts the kind-aware
planning-read chokepoint (``_kind_for_artifact`` + ``_ARTIFACT_TYPE_TO_KIND`` and
the ``_planning_read_dir`` seam wrapper). They live here — the lowest leaf both
``mission_setup_plan`` and ``mission_record_analysis`` already import one-way —
so every gate planning-read can route through the single chokepoint without a
back-edge (INV-8 preserved). ``mission_setup_plan`` re-exports
``_kind_for_artifact`` so its public surface (tests / ``lifecycle.py`` /
``_commit_to_branch``) is unchanged.

Behavior is preserved byte-for-byte from the pre-decomposition ``mission.py``;
the golden CLI characterization harness (WP01) is the regression net.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from mission_runtime import ActionContextError, MissionArtifactKind
from specify_cli import __version__ as SPEC_KITTY_VERSION
from specify_cli.context.mission_resolver import mission_not_found_message
from specify_cli.core.constants import KITTY_SPECS_DIR
from specify_cli.core.paths import get_main_repo_root

# WP03 (FR-002/FR-003): the marker prefix ``_find_feature_directory`` raises for
# an explicit handle that resolves to no mission directory. Shared between the
# raise site and ``_build_setup_plan_detection_error`` so the two never drift —
# the builder keys its truthful not-found branch on this exact signal, rather
# than mislabeling an unmatched explicit handle as a disambiguation prompt.
_NOT_FOUND_HANDLE_MARKER = "Mission not found for handle"


# write-surface-coherence WP02 (T007): the ``artifact_type`` string each caller
# passes to :func:`_commit_to_branch` maps to a single canonical
# :class:`~mission_runtime.MissionArtifactKind`. All of these are primary planning
# kinds (they live with their mission on the primary surface), but the kind must
# be NAMED, never guessed (DECISION 1) — an unmapped type raises so the gap is loud.
#
# #2113 / gate-read-surface-completion: relocated from ``mission_setup_plan`` into
# this INV-8 one-way leaf so ``_planning_read_dir`` (consumed by BOTH this module
# and ``mission_setup_plan``) can name its kind without creating an import cycle
# (``mission_setup_plan`` already imports this leaf, never the reverse). The single
# definition lives here; ``mission_setup_plan`` re-exports it to preserve the
# public ``_kind_for_artifact`` surface used by tests / ``lifecycle.py`` /
# ``_commit_to_branch``.
_ARTIFACT_TYPE_TO_KIND: dict[str, MissionArtifactKind] = {
    "spec": MissionArtifactKind.SPEC,
    "plan": MissionArtifactKind.FINALIZED_EXECUTION_PLAN,
    "tasks": MissionArtifactKind.TASKS_INDEX,
}


def _kind_for_artifact(artifact_type: str) -> MissionArtifactKind:
    """Map a planning ``artifact_type`` string to its canonical artifact kind.

    Raises ``KeyError`` (loud, not a silent ``SPEC`` default) when the type has no
    mapping, so a new artifact type cannot silently mis-route (DECISION 1 spirit).
    """
    try:
        return _ARTIFACT_TYPE_TO_KIND[artifact_type]
    except KeyError as exc:
        raise KeyError(
            f"_commit_to_branch: no MissionArtifactKind mapped for artifact_type {artifact_type!r}; add it to _ARTIFACT_TYPE_TO_KIND (no silent default)."
        ) from exc


def _planning_read_dir(repo_root: Path, mission_slug: str, *, artifact_type: str) -> Path:
    """Resolve the read dir for a planning artifact via the single kind-aware seam.

    The canonical chokepoint (gate-read-surface-completion WP01 / FR-004 / FR-009):
    every gate command that reads a planning artifact routes through this one locus.
    A PRIMARY-kind artifact resolves to the primary ``target_branch`` dir for ALL
    topologies; a STATUS/bookkeeping kind resolves to its placed surface (coord under
    coord topology). No gate command may reconstruct this via topology routing or a
    bespoke primary-anchor helper — they consume the one seam
    (:func:`~specify_cli.missions._read_path_resolver.resolve_planning_read_dir`).

    The kind is NAMED via :func:`_kind_for_artifact` (no silent default — an unmapped
    ``artifact_type`` raises so a new type cannot mis-route, DECISION 1 spirit). No new
    resolver is introduced (C-001): this wraps the existing kind map and seam.

    Raises:
        KeyError: When ``artifact_type`` has no kind mapping (propagated unchanged from
            :func:`_kind_for_artifact` — no silent default).
        ValueError: When ``mission_slug`` is not a safe path segment (traversal guard,
            propagated from the seam primitive).
        MissionSelectorAmbiguous: When ``mission_slug`` is an ambiguous handle
            (propagated unchanged from the seam — no silent pick).
    """
    # coord-primary-partition-lock WP01 (T004): repoint through the placement
    # seam's ``read_dir`` rather than ``resolve_planning_read_dir`` directly —
    # DRY-only consolidation (C-001), out-of-map edit (this file is not a WP01
    # owned file; the 4 duplicate ``_planning_read_dir`` wrapper copies collapse
    # onto the seam's single read entry point).
    from mission_runtime import placement_seam

    kind = _kind_for_artifact(artifact_type)
    # Explicit ``Path`` annotation: under the project's ``follow_imports = "skip"``
    # mypy config the cross-module ``PlacementSeam.read_dir`` return is seen as
    # ``Any``; the annotation re-narrows it (the method IS typed ``-> Path``) so the
    # chokepoint return is not an ``Any`` leak — matching the sibling ``tasks.py``
    # pattern rather than suppressing the check.
    read_dir: Path = placement_seam(repo_root, mission_slug).read_dir(kind)
    return read_dir


def _read_feature_meta(feature_dir: Path) -> dict[str, Any]:
    """Read feature metadata when present.

    Routes through the canonical ``mission_metadata.load_meta`` authority
    (FR-009 / SC-004) via the silent-empty adapter ``load_meta_or_empty``:
    a missing *or* malformed ``meta.json`` degrades to ``{}`` -- never raises
    (preserving the prior ``except (JSONDecodeError, OSError): return {}``).
    """
    from specify_cli.mission_metadata import load_meta_or_empty

    return load_meta_or_empty(feature_dir)


def _safe_load_meta(repo_root: Path, mission_slug: str) -> dict[str, object] | None:
    """Load a mission's ``meta.json`` for worktree resolution, or ``None``.

    Used only to derive the ``mid8`` worktree disambiguator — NEVER as a commit
    destination authority (that is ``resolve_placement_only``, FR-003).

    FR-003 / C-GUARD-3a (coord-topology placement regression fix): ``meta.json``
    only ever lives on the PRIMARY checkout, so the read is anchored on the
    topology-blind primary constructor. The coord-aware
    ``candidate_feature_dir_for_mission`` returns the coordination worktree once
    one exists — and that worktree carries no ``meta.json`` — so ``mid8`` read
    back as ``None`` and ``_planning_commit_worktree`` silently fell back to the
    main checkout, making ``safe_commit`` reject the (correctly COORDINATION)
    placement because the main checkout HEAD is the target branch, not the coord
    branch.
    """
    from mission_runtime import placement_seam
    from specify_cli.core.paths import MissionMetaReadError, load_meta_fail_closed

    # read-side-seam-primary-primitive-closure-01KYKMMT WP06 (T029): routed off
    # the retiring ``primary_feature_dir_for_mission`` wrapper onto the seam
    # directly — PRIMARY_METADATA, since the read is meta.json (FR-003 above).
    # WP08 (T036): the caller-side canonicalizer fold DROPPED — redundant with
    # the seam's own internal fold for a PRIMARY-partition kind.
    feature_dir = placement_seam(repo_root, mission_slug).read_dir(MissionArtifactKind.PRIMARY_METADATA)
    try:
        meta = load_meta_fail_closed(feature_dir)
    except MissionMetaReadError:
        return None
    return meta or None


def _find_feature_directory(
    repo_root: Path,
    _cwd: Path,
    explicit_feature: str | None = None,
) -> Path:
    """Find the mission directory from an explicit mission handle.

    WP06 / T020 / C-CTX-4: routes through the single read primitive
    (:func:`specify_cli.missions._read_path_resolver.resolve_mission_read_path`),
    so a ``--mission <mid8>`` handle resolves to the same directory as the full
    slug (F-001/F-003/F-004). There is **no silent fallback** to a
    wrong-but-plausible primary-checkout path: an unresolvable handle raises a
    structured :class:`ActionContextError` (``FEATURE_CONTEXT_UNRESOLVED``) and
    an ambiguous handle raises ``MISSION_AMBIGUOUS_SELECTOR`` (C-CTX-4 / C-009).
    WP04 deliberately left this caller for WP06, which owns ``mission.py``.

    Args:
        repo_root: Repository root path
        _cwd: Current working directory (unused — kept for signature compatibility)
        explicit_feature: Mission handle provided explicitly (required)

    Returns:
        Path to mission directory

    Raises:
        ActionContextError: If no handle is provided, the handle is ambiguous, or
            it resolves to no existing mission directory (structured error).
    """
    from specify_cli.missions._read_path_resolver import (
        MissionSelectorAmbiguous,
        StatusReadPathNotFound,
        resolve_handle_to_read_path,
    )

    raw_handle = explicit_feature.strip() if explicit_feature else None
    if not raw_handle:
        raise ActionContextError("FEATURE_CONTEXT_UNRESOLVED", "--mission <slug> is required")
    # WP02/FR-002: the single guarded read-side seam (IC-01) collapses the former
    # raw-join → load_meta → resolve_mid8 bootstrap. It performs the primary-meta
    # probe, the sanctioned mid8 cascade, the fail-closed coord gate, and the
    # existence-gated topology routing internally — and adds the missing
    # assert_safe_path_segment guard (FR-004) the hand-rolled block lacked.
    try:
        feature_dir: Path = resolve_handle_to_read_path(
            repo_root,
            raw_handle,
            require_exists=True,
        )
    except MissionSelectorAmbiguous as exc:
        raise ActionContextError(exc.error_code, str(exc)) from exc
    except StatusReadPathNotFound as exc:
        raise ActionContextError(
            "FEATURE_CONTEXT_UNRESOLVED",
            f"{_NOT_FOUND_HANDLE_MARKER} {raw_handle!r}; checked the coordination worktree and the primary checkout. {exc}",
        ) from exc
    return feature_dir


def _resolve_mission_dir_name_primary_anchored(repo_root: Path, explicit_feature: str | None) -> str | None:
    """Resolve a mission handle to its on-disk dir name WITHOUT requiring coord.

    #11 / #1718 / #1692: ``finalize-tasks`` only needs the mission slug to anchor
    its primary-surface reads. The coord-aware ``_find_feature_directory``
    fail-closes when a materialized-but-empty coordination worktree exists,
    pre-empting the primary read. This helper canonicalises the handle against
    the PRIMARY checkout only (no coord-existence gate), returning the mission
    dir name when the primary surface exists, or ``None`` so the caller falls
    back to the structured detection error (no silent wrong-path).

    gate-read-surface-completion WP01 / FR-009: the primary-surface existence probe
    routes through the ONE kind-aware chokepoint (``_planning_read_dir`` → the seam),
    not a bespoke ``primary_feature_dir_for_mission`` call — there is no parallel
    primary-anchor planning-read path left. The remaining
    :func:`_canonicalize_handle` step is handle canonicalization (mid8 / ULID /
    numeric / human slug → dir name), NOT a planning-path join, so it stays.

    Propagates :class:`MissionSelectorAmbiguous` (no silent fallback on an
    ambiguous selector, C-CTX-4 / C-009).
    """
    raw_handle = explicit_feature.strip() if explicit_feature else None
    if not raw_handle:
        return None

    # Deferred call-time import of the ``mission`` shim (NOT a module-scope edge —
    # INV-8 one-way leaf preserved): the gate planning-read chokepoint is consumed
    # through the historical ``mission._planning_read_dir`` patch seam, the same
    # call-time-lookup pattern ``setup_plan`` uses for ``mission.<name>`` targets.
    # #2113 routes the primary-surface probe through this seam so tests that revert
    # the chokepoint body (``monkeypatch.setattr(mission, "_planning_read_dir", …)``)
    # exercise the live caller.
    from specify_cli.cli.commands.agent import mission as _mission
    from specify_cli.missions._read_path_resolver import (
        MissionSelectorAmbiguous,
        _canonicalize_handle,
    )

    main_root = get_main_repo_root(repo_root)

    # Literal directory name on the primary checkout. gate-read-surface-completion
    # WP01 / FR-009: the primary-surface planning-read anchor routes through the ONE
    # kind-aware chokepoint (``_planning_read_dir`` → ``resolve_planning_read_dir``).
    # SPEC is a PRIMARY-partition kind, so the seam resolves
    # ``primary_feature_dir_for_mission`` topology-blind — byte-equivalent to the
    # former direct primitive call, with no surviving bespoke primary-anchor path.
    # This preserves the PRIMARY-ONLY ``.is_dir()`` existence intent: the coord-aware
    # ``resolve_handle_to_read_path`` is deliberately NOT used here, because
    # ``finalize-tasks`` must read the primary surface even when a materialized-but-
    # empty coordination worktree exists (#11 / #1718 / #1692, which the coord-aware
    # seam would fail-close; the seam's PRIMARY branch honors this fail-open intent).
    if _mission._planning_read_dir(repo_root, raw_handle, artifact_type="spec").is_dir():
        return raw_handle

    # Canonicalise the handle (mid8 / ULID / numeric / human slug) against the
    # primary checkout. ``_canonicalize_handle`` raises MissionSelectorAmbiguous
    # for an ambiguous selector (we let it propagate) and returns ``None`` for an
    # unresolvable handle.
    try:
        canonical = _canonicalize_handle(main_root, raw_handle)
    except MissionSelectorAmbiguous:
        raise
    if canonical is None:
        return None
    canonical_dir: Path = canonical[2]
    if canonical_dir.is_dir():
        return canonical_dir.name
    return None


def _primary_anchored_feature_dir(repo_root: Path, explicit_feature: str | None) -> Path | None:
    """Resolve a mission handle to its PRIMARY-checkout feature dir, or ``None``.

    The planning-authoring surface companion to finalize-tasks' input read: both
    must anchor to the SAME primary surface so an agent authoring at the reported
    ``feature_dir`` writes where finalize-tasks reads. gate-read-surface-completion
    WP01 / FR-009: that anchor now flows through the ONE kind-aware chokepoint
    (``_planning_read_dir`` → the seam, which resolves the primary dir topology-blind
    for the PRIMARY ``spec`` kind), not a bespoke ``primary_feature_dir_for_mission``
    call. Returns ``None`` (so the caller falls back to the coord-aware resolver)
    when no explicit handle is given or the mission has no primary-surface
    directory. Propagates :class:`MissionSelectorAmbiguous` — an ambiguous handle is
    never silently resolved (C-CTX-4 / C-009).
    """
    if not explicit_feature or not explicit_feature.strip():
        return None
    # Deferred call-time import of the ``mission`` shim (NOT a module-scope edge —
    # INV-8 one-way leaf preserved): the gate planning-read chokepoint is consumed
    # through the historical ``mission._planning_read_dir`` patch seam, the same
    # call-time-lookup pattern ``setup_plan`` uses, so #2113's body-revert tests
    # (``monkeypatch.setattr(mission, "_planning_read_dir", …)``) exercise this
    # caller. The sibling-helper hop (``_resolve_mission_dir_name_primary_anchored``)
    # stays a same-module call so the seam unit test that patches it on THIS module
    # (``test_mission_feature_resolution``) drives the ambiguity-propagation branch.
    from specify_cli.cli.commands.agent import mission as _mission
    from specify_cli.missions._read_path_resolver import MissionSelectorAmbiguous

    try:
        dir_name = _resolve_mission_dir_name_primary_anchored(repo_root, explicit_feature)
    except MissionSelectorAmbiguous as exc:
        # No silent fallback on an ambiguous selector — surface the structured
        # error the same way the coord-aware resolver does (C-CTX-4 / C-009).
        raise ActionContextError(exc.error_code, str(exc)) from exc
    if not dir_name:
        return None
    # gate-read-surface-completion WP01 / FR-009: the planning-read anchor flows
    # through the ONE kind-aware chokepoint (``_planning_read_dir`` → the seam),
    # not a parallel ``primary_feature_dir_for_mission`` call. SPEC is a PRIMARY
    # kind, so the seam resolves the primary dir topology-blind — byte-equivalent
    # to the former direct primitive, with no surviving bespoke primary-anchor path.
    candidate = _mission._planning_read_dir(repo_root, dir_name, artifact_type="spec")
    return candidate if candidate.is_dir() else None


def _list_feature_spec_candidates(repo_root: Path) -> list[dict[str, object]]:
    """List candidate missions with absolute spec.md paths for remediation output."""
    main_repo_root = get_main_repo_root(repo_root)
    mission_specs_dir = main_repo_root / KITTY_SPECS_DIR
    if not mission_specs_dir.is_dir():
        return []

    candidates: list[dict[str, object]] = []
    for feature_dir in sorted(mission_specs_dir.iterdir()):
        if not feature_dir.is_dir():
            continue
        spec_file = feature_dir / "spec.md"
        meta_file = feature_dir / "meta.json"
        if not spec_file.exists() and not meta_file.exists():
            continue
        candidates.append(
            {
                "mission_slug": feature_dir.name,
                "feature_dir": str(feature_dir.resolve()),
                "spec_file": str(spec_file.resolve()),
                "spec_exists": spec_file.exists(),
            }
        )
    return candidates


def _sole_mission_slug_or_none(repo_root: Path) -> str | None:
    """Return the sole substantive mission's slug, or ``None``.

    FR-004 / #4: ``setup-plan`` auto-selects the only mission when exactly one is
    resolvable, instead of hard-requiring ``--mission``. This lives in the
    ``setup_plan`` caller (NOT the shared ``_find_feature_directory``, which
    other callers rely on to require an explicit handle). Returns ``None`` for
    zero or >1 candidates so the existing structured detection-error path fires
    (no silent fallback when ambiguous).
    """
    candidates = _list_feature_spec_candidates(repo_root)
    if len(candidates) != 1:
        return None
    return str(candidates[0]["mission_slug"])


def _build_setup_plan_detection_error(
    repo_root: Path,
    _base_error: str,
    mission_flag: str | None,
    *,
    error_code: str = "PLAN_CONTEXT_UNRESOLVED",
    command_name: str = "setup-plan",
    command_args: list[str] | None = None,
) -> dict[str, object]:
    """Build a concise mission-context detection error payload.

    This payload is consumed by LLMs via ``--json`` output.  Keep it small:
    slugs only (no absolute paths), one example command, and a short
    remediation string so the agent can act without parsing kilobytes of
    redundant path data.

    WP03 (FR-002/FR-003): when an explicit ``--mission`` handle was provided AND
    the inbound resolution error is the not-found signal, the operator did NOT
    fail to disambiguate — they named a mission that does not exist. Emit the
    canonical ``Mission not found: <handle>`` and skip the disambiguate/no-missions
    branch entirely. The no-handle auto-detect-failed cases (multi-mission
    disambiguate, zero-mission) are left byte-unchanged below.
    """
    explicit_handle = mission_flag.strip() if mission_flag else ""
    if explicit_handle and _NOT_FOUND_HANDLE_MARKER in _base_error:
        return {
            "error_code": error_code,
            "mission_flag": mission_flag,
            "spec_kitty_version": SPEC_KITTY_VERSION,
            "error": mission_not_found_message(explicit_handle),
            "remediation": "Re-run with an existing --mission <slug>, or create it: spec-kitty agent mission create <name> --json",
        }

    candidates = _list_feature_spec_candidates(repo_root)
    command_args = command_args if command_args is not None else ["--json"]

    payload: dict[str, object] = {
        "error_code": error_code,
        "mission_flag": mission_flag,
        "spec_kitty_version": SPEC_KITTY_VERSION,
    }

    if not candidates:
        payload["error"] = "No missions found in kitty-specs/"
        payload["remediation"] = "Run /spec-kitty.specify or: spec-kitty agent mission create <name> --json"
        return payload

    slugs = [str(c["mission_slug"]) for c in candidates]
    n = len(slugs)
    payload["error"] = f"{n} missions found, pass --mission <slug> to disambiguate"
    payload["available_missions"] = slugs

    # One example command so the LLM knows the exact syntax
    args_suffix = f" {' '.join(command_args)}" if command_args else ""
    payload["example_command"] = f"spec-kitty agent mission {command_name} --mission {slugs[0]}{args_suffix}"
    payload["remediation"] = "Re-run with --mission <slug>"
    return payload
