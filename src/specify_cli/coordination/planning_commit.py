"""Pure planning-artifact commit decisions (partition, demotion verdict, identifiers).

Moved verbatim out of ``cli/commands/implement.py`` (implement-degod WP04). Nothing
here prints, exits or imports the CLI layer: callers in the command package turn the
typed results and errors into console output and ``typer.Exit``.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any, NamedTuple

from kernel.meta_decode import decode_meta
from mission_runtime import MissionArtifactKind, placement_seam
from specify_cli.coordination.coherence import is_coord_residue_churn, is_self_bookkeeping_churn
from specify_cli.core.constants import WORKTREES_DIR
from specify_cli.git.commit_helpers import SafeCommitPathPolicyError


def load_primary_anchored_mission_meta(repo_root: Path | None, mission_slug: str) -> dict[str, Any] | None:
    """FR-003 cascade layer 1: read the PRIMARY-checkout ``meta.json``.

    ``coordination_branch`` / ``mission_id`` / ``mid8`` live ONLY in the
    PRIMARY-checkout meta.json; the coord worktree's mission dir has none.
    ``feature_dir`` (the caller's fallback, see
    :func:`load_fallback_mission_meta`) is topology-aware and prefers the
    coord worktree once materialized — reading meta there returns empty, so
    every identifier silently fell back to the slug (``mid8`` ->
    ``<slug>0000``), which then names a non-existent coord branch/worktree at
    claim time ("Failed to resolve coordination worktree for
    <slug>-<slug-fallback>"). Anchor the config read on the canonical primary
    dir first (the caller threads the true main ``repo_root``), so config is
    read before topology is resolved.

    Returns ``None`` when *repo_root* is not supplied or the primary meta is
    missing/corrupt (legacy). Does NOT catch an ambiguous-handle raise from
    the seam's handle canonicalization — that must propagate (no silent
    pick, C-009).

    read-side-seam-primary-primitive-closure-01KYKMMT WP05/FR-004: routed
    through the kind-aware seam (PRIMARY_METADATA is a PRIMARY-partition
    kind, so it resolves PRIMARY for every topology). The seam's internal
    handle canonicalization propagates ``MissionSelectorAmbiguous`` exactly
    like the drained ``_canonicalize_primary_read_handle`` call did, so it is
    deliberately called OUTSIDE the ``try`` below -- only the meta.json
    read itself is soft-caught.
    """
    if repo_root is None:
        return None

    from specify_cli.core.paths import MissionMetaReadError
    from specify_cli.core.paths import load_meta_fail_closed as _load_meta

    primary_dir = placement_seam(repo_root, mission_slug).read_dir(MissionArtifactKind.PRIMARY_METADATA)
    try:
        return _load_meta(primary_dir)
    except (OSError, MissionMetaReadError):  # corrupt/unreadable primary meta -> fall through to layer 2
        return None


def load_fallback_mission_meta(feature_dir: Path) -> dict[str, Any] | None:
    """FR-003 cascade layer 2: read ``meta.json`` off the passed *feature_dir*.

    Only consulted when :func:`load_primary_anchored_mission_meta` yields
    ``None`` (no ``repo_root``, or the primary meta is missing/corrupt).
    """
    from specify_cli.core.paths import MissionMetaReadError
    from specify_cli.core.paths import load_meta_fail_closed as _load_meta

    try:
        return _load_meta(feature_dir)
    except (OSError, MissionMetaReadError):  # corrupt/unreadable meta.json is legacy-tolerated here
        return None


def extract_mission_identifiers_from_meta(mission_meta: dict[str, Any] | None, mission_slug: str) -> tuple[str | None, str | None, str | None]:
    """Pull ``(coord_branch, mission_id, mid8)`` out of a resolved meta dict.

    mid8 precedence: the stored ``meta["mid8"]`` value wins; otherwise the
    fallback routes through the authoritative :func:`resolve_mid8` resolver
    (WP03 / FR-009). ``or None`` preserves the prior ``None`` contract
    (``resolve_mid8`` declines to ``""``).
    """
    if not isinstance(mission_meta, dict):
        return None, None, None

    coord_branch: str | None = mission_meta.get("coordination_branch") or None
    mission_id: str | None = mission_meta.get("mission_id") or None

    from specify_cli.lanes.branch_naming import resolve_mid8

    mid8: str | None = mission_meta.get("mid8") or (
        resolve_mid8(
            mission_slug,
            mission_id=mission_id if isinstance(mission_id, str) else None,
        )
        or None
    )
    return coord_branch, mission_id, mid8


def compute_effective_bookkeeping_ids(
    mission_slug: str,
    mission_id: str | None,
    mid8: str | None,
    coord_branch: str | None,
) -> tuple[str, str]:
    """Derive ``(effective_mission_id, effective_mid8)`` from the resolved triple.

    ``effective_mission_id`` falls back to ``legacy-<slug>`` when no declared
    ``mission_id`` is available. ``effective_mid8`` routes through the
    canonical fail-closed authority (FR-007) rather than fabricating a
    zero-padded mid8 from the slug — that idiom named a non-existent coord
    branch/worktree at claim time.
    """
    effective_mission_id = str(mission_id) if mission_id else f"legacy-{mission_slug}"

    from specify_cli.lanes.branch_naming import resolve_transaction_mid8

    effective_mid8 = resolve_transaction_mid8(
        mission_slug,
        mission_id=str(mission_id) if mission_id else None,
        mid8=str(mid8) if mid8 else None,
        coordination_branch=coord_branch,
    )
    return effective_mission_id, effective_mid8


class BookkeepingTransactionIdentifiers(NamedTuple):
    """The identifiers :func:`resolve_bookkeeping_transaction_identifiers` returns.

    A ``NamedTuple`` (PR #2662 squad LOW-3 hardening): it IS a 5-tuple, so the
    frozen C-006 contract holds by construction — the cross-lane
    filter reads ``[0]`` and the other in-module caller unpacks all five, both unchanged
    — while the fields are now named/structural instead of a bare positional
    pin. Arity and order MUST NOT change (C-006).
    """

    coord_branch: str | None
    mission_id: str | None
    mid8: str | None
    effective_mission_id: str
    effective_mid8: str


def resolve_bookkeeping_transaction_identifiers(
    feature_dir: Path,
    mission_slug: str,
    repo_root: Path | None = None,
) -> BookkeepingTransactionIdentifiers:
    """Resolve the ``(coord_branch, mission_id, mid8, effective_mission_id,
    effective_mid8)`` bookkeeping identifiers as a 5-field NamedTuple.

    C-006 (frozen contract, #2649): the in-module cross-lane
    filter reads only element ``[0]``, while the other in-module
    caller (``_ensure_planning_artifacts_committed_git``) unpacks all five —
    the 5-tuple arity and order MUST NOT change (a NamedTuple keeps both the
    positional and the new named access working).
    """
    mission_meta = load_primary_anchored_mission_meta(repo_root, mission_slug)
    if mission_meta is None:
        mission_meta = load_fallback_mission_meta(feature_dir)

    coord_branch, mission_id, mid8 = extract_mission_identifiers_from_meta(mission_meta, mission_slug)
    effective_mission_id, effective_mid8 = compute_effective_bookkeeping_ids(mission_slug, mission_id, mid8, coord_branch)
    return BookkeepingTransactionIdentifiers(coord_branch, mission_id, mid8, effective_mission_id, effective_mid8)


def feature_dir_file_paths(repo_root: Path, feature_dir: Path) -> list[str]:
    # FR-005 / Issue #1887: reject calls where feature_dir resolves under
    # .worktrees/.  Relativizing a coord-worktree path against the primary repo
    # root produces paths like ".worktrees/<slug>/..." which safe_commit then
    # stages into the primary index, leaking coord internals into origin/main.
    # The caller must pass the correct coordination-branch-relative path instead.
    feature_dir_resolved = feature_dir.resolve()
    repo_root_resolved = repo_root.resolve()
    try:
        rel = feature_dir_resolved.relative_to(repo_root_resolved)
    except ValueError:
        rel = None
    if rel is not None and rel.parts and rel.parts[0] == WORKTREES_DIR:
        raise SafeCommitPathPolicyError(
            offending_path=rel.as_posix(),
            worktree_root=repo_root_resolved,
        )

    paths: list[str] = []
    for path in sorted(feature_dir.rglob("*")):
        if not path.is_file():
            continue
        try:
            rel_path = path.resolve().relative_to(repo_root_resolved).as_posix()
        except ValueError:
            continue
        # Secondary guard: individual files must not land under .worktrees/.
        if Path(rel_path).parts and Path(rel_path).parts[0] == WORKTREES_DIR:
            raise SafeCommitPathPolicyError(
                offending_path=rel_path,
                worktree_root=repo_root_resolved,
            )
        paths.append(rel_path)
    return paths


def planning_artifact_source_dir(repo_root: Path, feature_dir: Path, mission_slug: str) -> Path:
    """Return the primary-checkout mission dir for planning-artifact discovery."""
    repo_root_resolved = repo_root.resolve()
    try:
        rel = feature_dir.resolve().relative_to(repo_root_resolved)
    except ValueError:
        return feature_dir
    if rel.parts and rel.parts[0] == WORKTREES_DIR:
        # read-side-seam-primary-primitive-closure-01KYKMMT WP05/FR-004: routed
        # through the kind-aware seam. PRIMARY_METADATA is a PRIMARY-partition
        # kind -- it resolves the SAME topology-blind primary mission dir every
        # other PRIMARY-partition kind does (mirroring the established
        # slug-canonicalization idiom: "resolve a handle to its canonical
        # on-disk directory name" always migrates onto PRIMARY_METADATA,
        # never a specific artifact's content -- this call discards content,
        # it only needs the directory).
        primary_dir = placement_seam(repo_root, mission_slug).read_dir(MissionArtifactKind.PRIMARY_METADATA)
        if primary_dir.exists():
            return primary_dir
    return feature_dir


META_JSON_FILENAME = "meta.json"

DEMOTION_REFUSAL_MSG = (
    "Uncommitted change to {rel_path} silently demotes {mission_slug} off its "
    "coordination branch ('{coordination_branch}' -> absent). Auto-committing this "
    "would carry a whole-team routing change into the planning-artifact commit.\n"
    "Restore `coordination_branch` in meta.json if this was accidental. If the "
    "branch is genuinely gone and you already ran `spec-kitty doctor coordination "
    "--fix`, commit the flattened meta.json yourself (`git add` + `git commit`) "
    "before re-running the claim -- the auto-commit intentionally will not do it "
    "silently for you."
)

DEMOTION_CORRUPT_MSG = "{rel_path} ({side}) is not valid JSON. Refusing to auto-commit planning artifacts until it is repaired."


def read_json_at_ref(repo_root: Path, ref: str, rel_path: str) -> tuple[bool, dict[str, Any] | None]:
    """Return ``(has_baseline, parsed_or_None)`` for *rel_path* at *ref*.

    ``git show <ref>:<rel_path>`` exits non-zero when *rel_path* has no
    baseline at *ref* (e.g. a legitimate untracked/first-commit case) --
    reported as ``(False, None)``. A present baseline that fails to parse as
    JSON is reported as ``(True, None)``, distinct from "no baseline" so a
    caller can fail closed on a corrupt-but-present file rather than treating
    it as absent. The parse routes through the canonical kernel L1 decoder
    (:func:`kernel.meta_decode.decode_meta`, ``on_malformed="none"``) rather
    than a hand-rolled ``json.loads`` -- the single meta-decode authority
    (FR-010 / the inline-meta-read gate).
    """
    result = subprocess.run(
        ["git", "show", f"{ref}:{rel_path}"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if result.returncode != 0:
        return False, None
    return True, decode_meta(result.stdout, on_malformed="none")


def meta_json_demotion_refusal(
    repo_root: Path,
    mission_slug: str,
    meta_path: Path,
    rel_path: str,
) -> str | None:
    """Return a REFUSE message iff the uncommitted *meta_path* is a topology
    demotion (#4979 FR-005), else ``None`` (ALLOW).

    Predicate (the robust key -- a ``topology`` coord-to-lanes demotion
    corroborates but is NOT required, since legacy HEAD meta may lack the
    field): HEAD's ``coordination_branch`` is present-and-non-null AND the
    working copy drops it to absent/null. Baseline is ``git show
    HEAD:<rel_path>``; no baseline (untracked -- a legitimate first commit,
    including a genuinely-flat mission) ALLOWS. A HEAD baseline or working
    copy that fails to parse as JSON fails closed to REFUSE.
    """
    has_baseline, head_meta = read_json_at_ref(repo_root, "HEAD", rel_path)
    if not has_baseline:
        return None
    if head_meta is None:
        return DEMOTION_CORRUPT_MSG.format(rel_path=rel_path, side="HEAD")
    try:
        working_raw = meta_path.read_text(encoding="utf-8")
    except OSError:
        return DEMOTION_CORRUPT_MSG.format(rel_path=rel_path, side="working copy")
    working_meta = decode_meta(working_raw, on_malformed="none")
    if working_meta is None:
        return DEMOTION_CORRUPT_MSG.format(rel_path=rel_path, side="working copy")
    head_branch = head_meta.get("coordination_branch")
    working_branch = working_meta.get("coordination_branch")
    if head_branch and not working_branch:
        return DEMOTION_REFUSAL_MSG.format(
            rel_path=rel_path,
            mission_slug=mission_slug,
            coordination_branch=head_branch,
        )
    return None


def meta_json_repo_relative_path(repo_root: Path, artifact_source_dir: Path) -> str | None:
    """Return the repo-relative (posix) path of *artifact_source_dir*'s
    ``meta.json``, or ``None`` when it does not resolve under *repo_root*."""
    try:
        return (artifact_source_dir / META_JSON_FILENAME).resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return None


def partition_files_for_commit(files_to_commit: list[str]) -> tuple[list[str], list[str]]:
    """Split *files_to_commit* into PRIMARY and COORD-residue groups (T007).

    Mirrors ``commit_router._group_files_by_partition``: classifies each
    repo-relative path with the same
    :func:`~specify_cli.coordination.coherence.is_coord_residue_churn`
    predicate WP01 wired into the read-side ``resolve_precondition_ref`` --
    one authority (NFR-004), no new partition literal (WP12 retired the
    former ``mission_runtime`` predicate onto this owner leg). Everything NOT
    explicitly COORD-residue (PRIMARY kinds, ``meta.json``, unrecognized paths)
    defaults to the PRIMARY group -- the same fail-safe-toward-primary
    direction as the read side.
    """
    primary_files: list[str] = []
    coord_files: list[str] = []
    for path_str in files_to_commit:
        if is_coord_residue_churn(path_str):
            coord_files.append(path_str)
        else:
            primary_files.append(path_str)
    return primary_files, coord_files


def guard_planning_commit_partition(files: list[str], *, destination_is_coord: bool) -> None:
    """Seam-A guard for the kind-agnostic ``BookkeepingTransaction`` commit (T011).

    write-path-integrity WP02 / FR-002 / C-008: the ``commit_for_mission``
    classifier already refuses a PRIMARY kind reaching coord staging
    (:class:`~specify_cli.coordination.commit_router.PrimaryKindReachedCoordStagingError`),
    but the P0 planning path commits through the kind-AGNOSTIC
    :class:`BookkeepingTransaction` seam, which never consulted a kind. This is
    the mirror guard on THAT seam: it classifies each staged path and raises the
    SAME exception on a partition mis-route, so a future edit that mixes
    partitions fails loud instead of silently landing a PRIMARY ``lanes.json`` on
    the coordination branch (the #3371 class).

    Exemption ORDER matters (C-008): spec-kitty's OWN bookkeeping
    (:func:`~specify_cli.coordination.coherence.is_self_bookkeeping_churn` --
    ``meta.json``, encoding-provenance, ``kitty-ops`` Op records) is exempted
    BEFORE kind classification, so a legitimate coordination commit co-travelling
    ``meta.json`` (a COORD-partition status commit that also carries mission
    identity metadata) does NOT trip the ``PRIMARY_METADATA``→coord guard. Only
    then is each remaining path checked: under a COORD destination a PRIMARY
    (non-residue) kind is the forbidden PRIMARY→coord route; under a PRIMARY
    destination a coord-residue kind is the forbidden COORD→primary/lane route.

    This guard is only applied under coordination topology (the caller passes
    ``enforce_partition=True`` for the coord-topology partition commits and
    ``False`` for the flat/legacy single-branch collapse, where every kind
    legitimately shares one branch and there is no partition to violate).
    """
    from specify_cli.coordination.commit_router import PrimaryKindReachedCoordStagingError

    for path_str in files:
        if is_self_bookkeeping_churn(path_str):
            # meta.json / encoding-provenance / kitty-ops co-travel — exempt
            # BEFORE kind classification (C-008).
            continue
        file_is_coord = is_coord_residue_churn(path_str)
        if file_is_coord == destination_is_coord:
            continue
        if destination_is_coord:
            raise PrimaryKindReachedCoordStagingError(
                f"PRIMARY-partition planning artifact {path_str!r} reached the "
                f"coordination-branch commit seam; PRIMARY kinds must commit to "
                f"the primary target branch and never transit the coordination "
                f"branch (write-path-integrity FR-002)."
            )
        raise PrimaryKindReachedCoordStagingError(
            f"COORD-partition artifact {path_str!r} reached a PRIMARY/lane commit "
            f"seam; coordination-partition kinds must commit to the coordination "
            f"branch, never a primary or lane branch (write-path-integrity FR-002/#2549)."
        )
