"""Status-surface trust + coord→target status projection for the merge seam.

Mission #2057 (decompose ``cli/commands/merge.py``) — IC-09 / WP09.

The security-sensitive path-trust assertions and the coord→target status
projection moved out of the command shim verbatim. The final-bookkeeping
snapshot/restore compensator that once lived here has been RETIRED by the
lifecycle-gate-execution-context mission (T048 / TAO-3): the merge executor now
enrols its bytes with the single owner compensator in
``coordination.atomic_write`` instead of a second implementation in this package.
One-way import: this module never imports the command shim.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from mission_runtime import MissionArtifactKind, kind_for_mission_file, placement_seam

from specify_cli.coordination.surface_resolver import is_under_worktrees_segment
from specify_cli.core.constants import KITTY_SPECS_DIR, WORKTREES_DIR
from specify_cli.core.git_ops import run_command
from specify_cli.core.paths import assert_safe_path_segment, get_main_repo_root
from specify_cli.core.utils import ensure_within_any, ensure_within_directory
from specify_cli.merge._constants import _STATUS_EVENTS_FILENAME, _STATUS_FILENAME
from specify_cli.merge.git_probes import GitProbeError, driver_replay_expected_bytes

# The kind used to derive the PRIMARY (target-checkout) surface this projection
# stages onto (coord-write-placement-closure-01KYCF83 WP03 / FR-003). The
# projection ALWAYS lands on the target checkout's ``kitty-specs/<slug>/`` dir
# by contract (module docstring) — never the coordination worktree — so any
# PRIMARY-partition kind resolves the identical dir via ``placement_seam(...)
# .read_dir(...)``; ``PRIMARY_METADATA`` is used as the selector because this
# is mission bookkeeping metadata, not a re-classification of the projected
# ``status.events.jsonl`` / ``status.json`` files themselves (those stay
# STATUS_STATE — see ``_classify_status_bookkeeping_filename`` below).
_TARGET_SURFACE_KIND = MissionArtifactKind.PRIMARY_METADATA


def _classify_status_bookkeeping_filename(filename: str) -> MissionArtifactKind | None:
    """Classify ``filename`` via the SSOT classifier (FR-003), basename-only.

    :func:`~mission_runtime.kind_for_mission_file` requires a path shaped like
    ``kitty-specs/<slug>/<basename>`` to locate its classification anchor; the
    mission slug is irrelevant to a basename-only classification, so a
    placeholder segment satisfies the classifier's expected shape without
    hand-rolling the basename -> kind mapping inline here.
    """
    return kind_for_mission_file(f"{KITTY_SPECS_DIR}/_/{filename}")


def _validate_mission_slug_path_segment(mission_slug: str) -> str:
    """Reject mission slugs unsafe for direct path composition.

    Delegates to the canonical ``assert_safe_path_segment`` validator (FR-002 / WP04).
    Raises ``ValueError`` on any traversal-unsafe value, preserving the existing contract.
    """
    return str(assert_safe_path_segment(mission_slug))


def _target_bookkeeping_status_paths(
    *,
    main_repo: Path,
    mission_slug: str,
    status_feature_dir: Path,
) -> tuple[Path, Path]:
    """Return status paths that may be staged from the target checkout.

    ``status_feature_dir`` is topology-aware and can point at the coordination
    worktree. The final merge bookkeeping commit runs from ``main_repo`` onto
    the target branch, so it must stage primary-checkout paths only.

    The target directory is derived through the placement port
    (:func:`mission_runtime.placement_seam`) rather than composing
    ``primary_feature_dir_for_mission`` directly (coord-write-placement-closure-
    01KYCF83 WP03 / FR-003) — byte-identical to the prior derivation, now
    routed through the SAME authority every other primary-partition read uses.
    """
    safe_mission_slug = _validate_mission_slug_path_segment(mission_slug)
    target_feature_dir = (
        placement_seam(main_repo, safe_mission_slug).read_dir(_TARGET_SURFACE_KIND)
        if is_under_worktrees_segment(status_feature_dir)
        else status_feature_dir
    )
    safe_target_feature_dir = ensure_within_directory(target_feature_dir, main_repo)
    return (
        safe_target_feature_dir / _STATUS_EVENTS_FILENAME,
        safe_target_feature_dir / _STATUS_FILENAME,
    )


def _read_optional_bytes(path: Path) -> bytes | None:
    if not path.exists():
        return None
    return path.read_bytes()


def _assert_status_path_within_target_surface(
    *,
    repo_root: Path,
    mission_slug: str,
    candidate: Path,
) -> Path:
    """Reject bookkeeping paths that escape the canonical mission status surface.

    Validates ``mission_slug`` via ``assert_safe_path_segment`` (FR-003) before
    composing the surface root, then delegates containment to ``ensure_within_any``
    (FR-006 / T016). The surface root is derived through the placement port
    (:func:`mission_runtime.placement_seam`), not a direct
    ``primary_feature_dir_for_mission`` composition (coord-write-placement-
    closure-01KYCF83 WP03 / FR-003) — byte-identical to the prior derivation.
    """
    assert_safe_path_segment(mission_slug)
    repo_resolved = get_main_repo_root(repo_root).resolve(strict=False)
    surface_root = placement_seam(repo_resolved, mission_slug).read_dir(
        _TARGET_SURFACE_KIND
    ).resolve(strict=False)
    contained: Path = ensure_within_any(candidate, roots=[surface_root])
    return contained


def _assert_status_surface_path_is_trusted(
    *,
    repo_root: Path,
    status_feature_dir: Path,
) -> Path:
    """Reject status surfaces that resolve outside the repo's trusted roots.

    Selects the single correct root via ``is_under_worktrees_segment`` (worktrees
    vs kitty-specs), then delegates containment to ``ensure_within_any``
    (FR-006 / T018).  The selection is intentionally preserved — widening to a
    union of both roots would be a behavior change (research.md §(d)).

    The *claimed* topology (the path segment) must match the *resolved* topology:
    if the segment says worktrees but the resolved path is not under the worktrees
    root (or vice versa), the surface is rejected.  This closes a symlink/taint
    gap where a kitty-specs-shaped path could resolve into the worktrees tree (or
    the reverse) and slip past the single-root containment check.
    """
    repo_resolved = get_main_repo_root(repo_root).resolve(strict=False)
    worktrees_root = (repo_resolved / WORKTREES_DIR).resolve(strict=False)
    # Root specs dir (no per-mission slug appended) used purely for symlink/taint
    # containment checking, not raw per-mission-spec path composition. Bound to a
    # neutrally named local (``specs_root``) to avoid a false positive on the raw
    # mission-spec path ratchet (test_no_raw_mission_spec_paths) while keeping that
    # ratchet active over the rest of this module.
    specs_root = (repo_resolved / KITTY_SPECS_DIR).resolve(strict=False)
    # Absolutize the candidate (anchor a relative surface to the repo root) before
    # any containment check, then reject — pre-resolution — a path that escapes the
    # root its segment claims. Hardens the write path against a traversal/symlink
    # surface that would otherwise only be caught after ``.resolve()`` (#2043 Sonar).
    status_candidate = (
        status_feature_dir
        if status_feature_dir.is_absolute()
        else repo_resolved / status_feature_dir
    ).absolute()
    segment_claims_worktrees = is_under_worktrees_segment(status_candidate)
    claimed_root = worktrees_root if segment_claims_worktrees else specs_root
    try:
        status_candidate.relative_to(claimed_root)
    except ValueError as exc:
        raise ValueError(f"Untrusted status surface path: {status_feature_dir}") from exc
    status_resolved = status_candidate.resolve(strict=False)
    resolves_under_worktrees = status_resolved.is_relative_to(worktrees_root)
    resolves_under_specs = status_resolved.is_relative_to(specs_root)

    if segment_claims_worktrees != resolves_under_worktrees:
        raise ValueError(f"Untrusted status surface path: {status_feature_dir}")
    if not resolves_under_worktrees and not resolves_under_specs:
        raise ValueError(f"Untrusted status surface path: {status_feature_dir}")

    trusted_root = worktrees_root if resolves_under_worktrees else specs_root
    trusted_surface: Path = ensure_within_directory(status_resolved, trusted_root)
    return trusted_surface


def _assert_status_surface_file_path_is_trusted(
    *,
    repo_root: Path,
    status_feature_dir: Path,
    filename: str,
) -> Path:
    """Reject status-surface child paths outside the exact bookkeeping files.

    The trust decision is classifier-derived (FR-003): a basename is only a
    bookkeeping status file when :func:`kind_for_mission_file` classifies it to
    ``STATUS_STATE`` — this replaces a hand-maintained ``{filename1, filename2}``
    literal (a form of inline classification) with the SSOT classifier, per
    basename, one at a time (never a single combined membership test).
    """
    if _classify_status_bookkeeping_filename(filename) is not MissionArtifactKind.STATUS_STATE:
        raise ValueError(f"Refusing untrusted status filename: {filename}")
    trusted_surface = _assert_status_surface_path_is_trusted(
        repo_root=repo_root,
        status_feature_dir=status_feature_dir,
    )
    candidate = trusted_surface / filename
    if candidate.is_symlink():
        raise ValueError(f"Refusing symlinked status surface path: {candidate}")
    trusted_file: Path = ensure_within_any(
        candidate,
        roots=[],
        files=[trusted_surface / _STATUS_EVENTS_FILENAME, trusted_surface / _STATUS_FILENAME],
    )
    return trusted_file


def _restore_optional_bytes(path: Path, original: bytes | None) -> None:
    if original is None:
        path.unlink(missing_ok=True)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(original)


# WP09 (T048 / C4b / TAO-3): the merge-side snapshot-trust helper and the
# final-bookkeeping snapshot/restore compensator that used to live here are
# RETIRED. The compensator is no longer a second implementation in the ``merge/``
# package: the merge executor now enrols its primary-checkout (non-coord)
# bookkeeping bytes with the SINGLE owner compensator in
# ``coordination.atomic_write`` (capture + restore), which also owns the
# trusted-root containment these helpers used to carry. The projection helpers
# below (``_project_status_bookkeeping_to_target`` and its trust/reconcile
# support) survive — they are the coord→target projection, not a compensator.


def _target_branch_still_at_baseline(
    main_repo: Path,
    target_branch: str,
    baseline_sha: str,
) -> bool:
    """Return True when target still points at the pre-target-merge baseline."""
    if not baseline_sha or baseline_sha == "HEAD~1":
        return False
    ret, out, _err = run_command(
        ["git", "rev-parse", target_branch],
        capture=True,
        check_return=False,
        cwd=main_repo,
    )
    return bool(ret == 0 and out.strip() == baseline_sha)


def _union_event_logs(
    source_bytes: bytes | None,
    original_bytes: bytes | None,
) -> bytes | None:
    """Union two ``status.events.jsonl`` byte-sets via the canonical reconciler.

    FR-005: the coord→target projection must union ``source ∪ original`` through
    ``merge_event_log_texts`` (``merge_event_payloads`` — id-keyed dedupe/sort)
    rather than blind-overwriting the target log, so a target-newer event the
    coord worktree lacks survives. Returns ``None`` only when both sides are empty.
    """
    if source_bytes is None and original_bytes is None:
        return None
    from specify_cli.status import merge_event_log_texts

    source_text = source_bytes.decode("utf-8") if source_bytes is not None else ""
    original_text = original_bytes.decode("utf-8") if original_bytes is not None else ""
    merged_text: str = merge_event_log_texts(source_text, original_text)
    return merged_text.encode("utf-8")


def _rematerialize_status_snapshot(
    events_bytes: bytes,
    read_context_dir: Path,
) -> bytes:
    """Rematerialize ``status.json`` = ``reduce(union events)`` (FR-005).

    ``status.json`` is a derived reduced snapshot, so after the event log is
    unioned it must be re-reduced from the unioned events — a blind copy would
    leave it contradicting the log. ``read_context_dir`` supplies slug/meta
    context for legacy (mission_id-less) events.
    """
    from specify_cli.status import materialize_to_json, read_events_from_text, reduce

    events = read_events_from_text(read_context_dir, events_bytes.decode("utf-8"))
    snapshot_json: str = materialize_to_json(reduce(events))
    return snapshot_json.encode("utf-8")


def _project_status_bookkeeping_to_target(
    *,
    main_repo: Path,
    mission_slug: str,
    status_feature_dir: Path,
    checkpoint_sha: str | None = None,
    coord_ref: str | None = None,
) -> tuple[Path, Path]:
    """Copy authoritative status bookkeeping to target-checkout paths.

    Coord-backed missions write done transitions through the coordination
    surface, but the final target-branch housekeeping commit can only stage
    paths tracked under ``main_repo``. Project the status artifacts into
    ``kitty-specs/<slug>/`` before the commit; keep the authoritative write
    topology unchanged.

    S-B / FR-004 (#4981/#4970/#4973): when BOTH ``checkpoint_sha`` and
    ``coord_ref`` are supplied (the WP09 integration hook threads them from
    ``run.coord_checkpoint``), this ALSO projects every NON-status file changed on
    the coord ref after the checkpoint via
    :func:`project_post_checkpoint_commits_to_target`, so a concurrent
    status-emit / acceptance-verdict committed during the merge is not lost when
    the coord branch is torn down. The status byte-sets keep their union /
    rematerialize path below (FR-005); the general projection deliberately skips
    them. Both kwargs default to ``None`` so the existing call site
    (``executor._phase_record_done_and_project``) is byte-unchanged until wired.
    """
    target_events_path, target_status_path = _target_bookkeeping_status_paths(
        main_repo=main_repo,
        mission_slug=mission_slug,
        status_feature_dir=status_feature_dir,
    )
    trusted_status_feature_dir = _assert_status_surface_path_is_trusted(
        repo_root=main_repo,
        status_feature_dir=status_feature_dir,
    )
    trusted_target_events_path = _assert_status_path_within_target_surface(
        repo_root=main_repo,
        mission_slug=mission_slug,
        candidate=target_events_path,
    )
    trusted_target_status_path = _assert_status_path_within_target_surface(
        repo_root=main_repo,
        mission_slug=mission_slug,
        candidate=target_status_path,
    )
    if not is_under_worktrees_segment(trusted_status_feature_dir):
        return trusted_target_events_path, trusted_target_status_path

    trusted_target_events_path.parent.mkdir(parents=True, exist_ok=True)
    source_events_path = _assert_status_surface_file_path_is_trusted(
        repo_root=main_repo,
        status_feature_dir=trusted_status_feature_dir,
        filename=_STATUS_EVENTS_FILENAME,
    )
    source_status_path = _assert_status_surface_file_path_is_trusted(
        repo_root=main_repo,
        status_feature_dir=trusted_status_feature_dir,
        filename=_STATUS_FILENAME,
    )
    source_events_bytes = _read_optional_bytes(source_events_path)
    source_status_bytes = _read_optional_bytes(source_status_path)
    original_events_bytes = _read_optional_bytes(trusted_target_events_path)
    original_status_bytes = _read_optional_bytes(trusted_target_status_path)
    # FR-005: union the event log (source ∪ original) instead of blind-overwriting,
    # and rematerialize status.json from the unioned events (a derived reduced
    # snapshot) rather than blind-copying the coord copy.
    union_events_bytes = _union_event_logs(source_events_bytes, original_events_bytes)
    try:
        if union_events_bytes is not None:
            trusted_target_events_path.write_bytes(union_events_bytes)
            trusted_target_status_path.write_bytes(
                _rematerialize_status_snapshot(
                    union_events_bytes, trusted_target_events_path.parent
                )
            )
        elif source_status_bytes is not None:
            trusted_target_status_path.write_bytes(source_status_bytes)
    except OSError:
        _restore_optional_bytes(trusted_target_events_path, original_events_bytes)
        _restore_optional_bytes(trusted_target_status_path, original_status_bytes)
        raise

    if checkpoint_sha is not None and coord_ref is not None:
        # S-B/FR-004: bring EVERY post-checkpoint coord commit's non-status files
        # forward too — the status union above covers only the two status files.
        project_post_checkpoint_commits_to_target(
            main_repo=main_repo,
            mission_slug=mission_slug,
            coord_ref=coord_ref,
            checkpoint_sha=checkpoint_sha,
        )
    return trusted_target_events_path, trusted_target_status_path


@dataclass(frozen=True)
class ProjectionResult:
    """Outcome of :func:`project_post_checkpoint_commits_to_target` (S-B/FR-004).

    ``projected_paths`` — the repo-relative mission paths whose coord-ref content
    was staged onto the target checkout. ``projected_commits`` — the SHAs in
    ``checkpoint_sha..coord_ref`` (the bounded window, NFR-003). ``coord_tip_sha``
    — the coord tip observed while projecting; the compare-and-swap anchor the
    teardown gate re-checks (unchanged since projection ⇒ safe to tear down).
    """

    projected_paths: tuple[str, ...] = ()
    projected_commits: tuple[str, ...] = ()
    coord_tip_sha: str = ""


def _resolve_ref_sha(main_repo: Path, ref: str) -> str:
    """Resolve ``ref`` to a commit SHA (``""`` when it does not resolve)."""
    ret, out, _err = run_command(["git", "rev-parse", ref], capture=True, check_return=False, cwd=main_repo)
    return out.strip() if ret == 0 and out.strip() else ""


def _post_checkpoint_commit_shas(main_repo: Path, checkpoint_sha: str, coord_ref: str) -> list[str]:
    """SHAs reachable from ``coord_ref`` but not ``checkpoint_sha`` (bounded window)."""
    ret, out, _err = run_command(
        ["git", "rev-list", f"{checkpoint_sha}..{coord_ref}"],
        capture=True,
        check_return=False,
        cwd=main_repo,
    )
    if ret != 0:
        return []
    return [line for line in out.splitlines() if line.strip()]


def _post_checkpoint_mission_paths(main_repo: Path, mission_slug: str, checkpoint_sha: str, coord_ref: str) -> list[str]:
    """Non-status COORD-partition mission paths changed in ``checkpoint_sha..coord_ref``.

    Scoped to ``kitty-specs/<slug>/`` and with the two status byte-sets removed —
    those stay owned by the union / rematerialize path (FR-005). Everything else a
    concurrent coord commit touched (verdict, notes, trace, issue-matrix) is fair
    game for projection.

    WP10 integration fix: a PRIMARY-partition artifact
    (:func:`~mission_runtime.is_primary_artifact_kind` — ``meta.json``, spec/plan/
    tasks, ``lanes.json``, the retrospective) is EXCLUDED. Those live with the
    mission on the PRIMARY surface and are authored by the merge itself on the
    target (the ``mission_number`` bake / ``baseline_merge_commit`` stamp land AFTER
    the transaction-start checkpoint), so the coord ref carries only their STALE
    pre-merge copies. Projecting them forward would clobber the target's freshly
    committed values — the concrete regression this guard closes (the clean-merge
    baseline-validation failure). Unrecognised paths (kind ``None``) stay projected:
    they cannot be a known PRIMARY artifact, and the coord surface legitimately owns
    the coord-partition bookkeeping this projection exists to carry.
    """
    mission_prefix = f"{KITTY_SPECS_DIR}/{mission_slug}/"
    ret, out, _err = run_command(
        ["git", "diff", "--name-only", checkpoint_sha, coord_ref, "--", mission_prefix],
        capture=True,
        check_return=False,
        cwd=main_repo,
    )
    if ret != 0:
        return []
    from mission_runtime import MissionArtifactKind, is_primary_artifact_kind

    # DENYLIST (WP10 integration fix). Project every coord-owned bookkeeping path a
    # concurrent commit touched that has no dedicated preservation path — recognised
    # coord-partition bookkeeping (tracer files) AND coord bookkeeping with no single
    # declared kind (``decision-log/*-verdict.md``, ``notes/*``): those are what
    # #4981/#4973 must carry forward. EXCLUDE anything the target authors or preserves
    # for itself:
    #   * the two status byte-sets (owned by the union / rematerialize path, FR-005);
    #   * ``meta.json`` — a PRIMARY-partition artifact that
    #     :func:`~mission_runtime.kind_for_mission_file` returns ``None`` for, yet the
    #     merge stamps its ``mission_number`` bake / ``baseline_merge_commit`` on the
    #     TARGET after the checkpoint, so the coord ref holds only a stale copy;
    #     projecting it forward clobbers the target's freshly committed value (the
    #     clean-merge baseline-validation regression);
    #   * every OTHER recognised PRIMARY-partition kind (spec / plan / tasks / lanes /
    #     research / analysis-report / retrospective — :func:`is_primary_artifact_kind`);
    #   * the accept-time gate matrices ``issue-matrix.json`` / ``acceptance-matrix.json``
    #     (``ISSUE_MATRIX`` / ``ACCEPTANCE_MATRIX``): although coord-partition, these are
    #     authored on the PRIMARY checkout by ``accept`` (#2404) and have their OWN
    #     squash-merge preservation path (``executor._restore_regressed_gate_artifacts``,
    #     #2804). The general projection must NOT overwrite an already-accepted target
    #     fill with the coord branch's stale finalize-time placeholder.
    # A ``None`` kind that is NOT ``meta.json`` stays projected (coord bookkeeping).
    excluded_kinds = {MissionArtifactKind.ISSUE_MATRIX, MissionArtifactKind.ACCEPTANCE_MATRIX}
    status_and_primary_basenames = {_STATUS_EVENTS_FILENAME, _STATUS_FILENAME, "meta.json"}
    paths: list[str] = []
    for line in out.splitlines():
        candidate = line.strip()
        if not candidate or not candidate.startswith(mission_prefix):
            continue
        if Path(candidate).name in status_and_primary_basenames:
            continue
        kind = kind_for_mission_file(candidate, mission_slug=mission_slug)
        if kind is not None and (is_primary_artifact_kind(kind) or kind in excluded_kinds):
            continue
        paths.append(candidate)
    return paths


def _git_show_blob_bytes(main_repo: Path, ref: str, repo_rel_path: str) -> bytes | None:
    """Return the exact bytes of ``ref:repo_rel_path`` (``None`` when absent at ``ref``).

    Uses ``subprocess`` directly (not ``run_command``, which decodes to text) so a
    JSONL/YAML/Markdown bookkeeping blob is projected byte-for-byte — mirroring the
    raw-read pattern in :func:`specify_cli.merge.git_probes.patch_id_of`.
    """
    result = subprocess.run(
        ["git", "show", f"{ref}:{repo_rel_path}"],
        cwd=str(main_repo),
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    return result.stdout


def project_post_checkpoint_commits_to_target(
    *,
    main_repo: Path,
    mission_slug: str,
    coord_ref: str,
    checkpoint_sha: str,
) -> ProjectionResult:
    """Project every non-status post-checkpoint coord commit onto the target (S-B).

    Closes #4981/#4970/#4973: today only ``status.events.jsonl`` / ``status.json``
    are projected, so a concurrent status-emit / acceptance-verdict commit landing
    on the coord ref during the merge writes files that are dropped when the coord
    branch is torn down. This stages the coord-ref content of every path changed
    in ``checkpoint_sha..coord_ref`` (scoped to ``kitty-specs/<slug>/``, status
    byte-sets excluded) into the target checkout's mission dir.

    Append-only preserved (NFR): content is brought FORWARD only — a path deleted
    at the coord tip is never deleted on the target here (WP08 owns the SHA-scoped
    heal, and range-reverting the log would collide with it). Bounded
    O(#post-checkpoint commits) (NFR-003).
    """
    safe_slug = _validate_mission_slug_path_segment(mission_slug)
    coord_tip = _resolve_ref_sha(main_repo, coord_ref)
    if not coord_tip or not checkpoint_sha:
        return ProjectionResult(coord_tip_sha=coord_tip)

    commits = _post_checkpoint_commit_shas(main_repo, checkpoint_sha, coord_ref)
    if not commits:
        return ProjectionResult(coord_tip_sha=coord_tip)

    changed_paths = _post_checkpoint_mission_paths(main_repo, safe_slug, checkpoint_sha, coord_ref)
    target_feature_dir = placement_seam(main_repo, safe_slug).read_dir(_TARGET_SURFACE_KIND)
    mission_prefix = Path(KITTY_SPECS_DIR) / safe_slug
    projected: list[str] = []
    for repo_rel in changed_paths:
        content = _git_show_blob_bytes(main_repo, coord_ref, repo_rel)
        if content is None:
            continue
        rel_within = Path(repo_rel).relative_to(mission_prefix)
        trusted = _assert_status_path_within_target_surface(
            repo_root=main_repo,
            mission_slug=safe_slug,
            candidate=target_feature_dir / rel_within,
        )
        # WP10 integration fix (never clobber independently-filled target content,
        # #2804): only bring the coord change forward when the target has NOT
        # diverged from the shared checkpoint baseline for this path. If the target
        # working-tree content differs from the checkpoint content, the target was
        # updated on its own (e.g. an ``acceptance-matrix.json`` filled/accepted on
        # the primary surface pre-merge) — overwriting it with the coord ref's stale
        # copy would revert that accepted evidence. A concurrent coord commit the
        # target never touched (the #4981/#4970/#4973 case: target == checkpoint for
        # the path, usually both absent) is still projected.
        checkpoint_content = _git_show_blob_bytes(main_repo, checkpoint_sha, repo_rel)
        target_current = trusted.read_bytes() if trusted.exists() else None
        if target_current != checkpoint_content and target_current is not None:
            continue
        trusted.parent.mkdir(parents=True, exist_ok=True)
        trusted.write_bytes(content)
        projected.append(repo_rel)

    return ProjectionResult(
        projected_paths=tuple(projected),
        projected_commits=tuple(commits),
        coord_tip_sha=coord_tip,
    )


def _projected_path_content_matches(
    *,
    main_repo: Path,
    coord_ref: str,
    target_ref: str,
    checkpoint_sha: str,
    pre_squash_target_ref: str,
    repo_rel: str,
) -> bool:
    """Single-path proof body for :func:`projected_content_matches_target` (#5038).

    Two verdicts, chosen by whether the TARGET diverged from the shared
    checkpoint baseline for this path (``ours != base``):

    * **Not diverged** (``ours == base``): the target never touched this path
      after the checkpoint, so the original byte-equality proof still applies
      verbatim -- PASS iff ``target_bytes == coord_bytes`` (FR-004 / INV-NO-
      REGRESSION; never weakened by this rewrite).
    * **Diverged**: both sides independently edited the path from the shared
      baseline, and a legitimate squash reconciles that overlap through the
      path's registered ``.gitattributes`` merge driver (the SAME driver git
      invoked during the real squash) -- PASS iff the landed target blob
      byte-equals the driver's own replayed output (FR-001), REFUSE otherwise
      (FR-002) or when the probe cannot be evaluated at all -- no registered
      driver, a missing blob, or a driver error (FR-003 / INV-FLOOR-2, never
      silently PASS).
    """
    coord_bytes = _git_show_blob_bytes(main_repo, coord_ref, repo_rel)
    if coord_bytes is None:
        return False
    target_bytes = _git_show_blob_bytes(main_repo, target_ref, repo_rel)
    base_bytes = _git_show_blob_bytes(main_repo, checkpoint_sha, repo_rel)
    pre_squash_target_bytes = _git_show_blob_bytes(main_repo, pre_squash_target_ref, repo_rel)
    if pre_squash_target_bytes == base_bytes:
        return target_bytes == coord_bytes
    try:
        expected_bytes = driver_replay_expected_bytes(
            main_repo,
            repo_rel,
            base_ref=checkpoint_sha,
            ours_ref=pre_squash_target_ref,
            theirs_ref=coord_ref,
        )
    except GitProbeError:
        return False
    return target_bytes == expected_bytes


def projected_content_matches_target(
    *,
    main_repo: Path,
    coord_ref: str,
    target_ref: str,
    projected_paths: tuple[str, ...],
    checkpoint_sha: str,
    pre_squash_target_ref: str,
) -> bool:
    """Squash content proof (WP06 handoff, driver-replay attribution — #5038).

    WP06's reconciliation gate drops content reachability for squash
    (``verify_reachability=False``) because a squash merge preserves neither
    lane-tip SHAs nor per-lane patch-ids, and an aggregate mission→target tree
    comparison additionally diverges on legitimate post-merge bookkeeping. This
    proves — SCOPED to the projected paths — that each one legitimately landed
    on ``target_ref``: verbatim byte-equality with ``coord_ref`` when the target
    never diverged from the shared ``checkpoint_sha`` baseline for that path
    (the original, unweakened proof — FR-004), or driver-replay attribution
    against ``pre_squash_target_ref`` (the target's tip BEFORE the squash
    landed) when it did (see :func:`_projected_path_content_matches`). A
    diverged path with no registered driver, a missing blob, or a driver error
    REFUSEs fail-closed rather than passing vacuously (FR-003). Vacuously
    ``True`` for an empty set — nothing projected, nothing to diverge.
    """
    return all(
        _projected_path_content_matches(
            main_repo=main_repo,
            coord_ref=coord_ref,
            target_ref=target_ref,
            checkpoint_sha=checkpoint_sha,
            pre_squash_target_ref=pre_squash_target_ref,
            repo_rel=repo_rel,
        )
        for repo_rel in projected_paths
    )


__all__ = [
    "_validate_mission_slug_path_segment",
    "_target_bookkeeping_status_paths",
    "_read_optional_bytes",
    "_restore_optional_bytes",
    "_assert_status_path_within_target_surface",
    "_assert_status_surface_path_is_trusted",
    "_assert_status_surface_file_path_is_trusted",
    "_target_branch_still_at_baseline",
    "_project_status_bookkeeping_to_target",
    "ProjectionResult",
    "project_post_checkpoint_commits_to_target",
    "projected_content_matches_target",
]
