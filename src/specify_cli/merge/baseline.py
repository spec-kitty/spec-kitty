"""Post-merge review baseline (``baseline_merge_commit``) record/verify cluster.

This module owns the mission-state-surface concern of the ``baseline_merge_commit``
``meta.json`` field: it is written here at merge time and read by
``spec-kitty review --mode post-merge``. Extracted verbatim from
``cli/commands/merge.py`` as part of the merge.py god-module decomposition
(epic #2026); behavior is byte-identical to the original definitions.

``merge/`` deliberately does NOT import ``cli.commands.merge``, so relocating
this cluster here introduces no import cycle.
"""

from __future__ import annotations

import logging
from pathlib import Path

from kernel.clock import now_utc_iso
from kernel.meta_decode import MetaDecodeError, decode_meta
from specify_cli.core.git_ops import run_command
from specify_cli.core.paths import MissionMetaReadError, load_meta_fail_closed
from specify_cli.mission_metadata import write_meta

logger = logging.getLogger(__name__)

META_JSON = "meta.json"


def _resolve_merge_commit(feature_dir: Path) -> str:
    """Best-effort HEAD SHA of the checkout carrying *feature_dir*.

    Provenance only for the ``merged_commit`` marker: at the record call site
    the target branch has already advanced to the merge result, so ``HEAD`` is
    that commit. Non-raising — a non-repo path or a failed ``git`` degrades to
    an empty string and the caller falls back to the captured baseline SHA.
    """
    ret, out, _err = run_command(
        ["git", "rev-parse", "HEAD"],
        capture=True,
        check_return=False,
        cwd=feature_dir,
    )
    return out.strip() if ret == 0 else ""


class BaselineMergeCommitError(RuntimeError):
    """Raised when the post-merge review baseline cannot be recorded or verified.

    Modern lane missions (those whose ``meta.json`` carries a canonical
    ``mission_id``) MUST land ``baseline_merge_commit`` on the target branch.
    When the baseline is missing, the working meta is absent/corrupt, or the
    committed target meta lacks the expected value, downstream
    ``spec-kitty review`` raises ``MISSION_REVIEW_MODE_MISMATCH``. We surface
    that failure loudly at merge time instead of letting an apparently
    successful merge ship a mission that cannot be reviewed post-merge.
    """


def record_baseline_merge_commit(
    feature_dir: Path,
    baseline_commit: str | None,
    *,
    mission_id: str | None = None,
) -> Path | None:
    """Persist the post-merge review baseline AND merge completion marker in meta.json.

    Two sibling records land here on the same merge-finalize path
    (``executor.py`` ``_phase_capture_and_baseline``), folded into the one
    bookkeeping commit + durability path:

    * ``baseline_merge_commit`` — anchors post-merge review diffs. It should
      point at the target-branch baseline before the mission lands, not at the
      final housekeeping commit produced by merge.
    * ``merged_at`` (+ ``merged_commit``) — the post-merge completion marker
      (#4090). Its production writer was deleted in #2258 and never re-added,
      leaving the surface resolver's primary-wins guard
      (``surface_resolver.py`` ``_primary_mission_is_completed`` ->
      ``is_mission_merged`` -> ``meta.get("merged_at")``) and the runtime
      terminal short-circuit dormant. ``merged_at`` is a UTC ISO datetime;
      ``merged_commit`` is the merge-result SHA (provenance). Unlike
      ``baseline_merge_commit`` (modern-mission-only), the marker is written for
      EVERY merge, legacy included.

    For **modern lane missions** (``mission_id`` is set — the canonical ULID
    introduced by mission 083), an empty baseline, a missing ``meta.json``, or
    corrupt JSON is a HARD failure: we raise :class:`BaselineMergeCommitError`
    so the merge stops loudly instead of shipping a mission that
    ``spec-kitty review --mode post-merge`` cannot anchor
    (``MISSION_REVIEW_MODE_MISMATCH``).

    For **legacy missions** (no ``mission_id``) the historical soft behavior is
    preserved for the baseline: the function logs a warning and returns ``None``
    when meta cannot be read so the merge proceeds without a baseline.

    Both records are idempotent — a ``spec-kitty merge --resume`` never
    double-stamps an already-present field — and ``spec-kitty mission reopen``
    clears ``merged_*`` so a re-merge re-stamps a fresh ``merged_at``.
    """
    is_modern = bool(mission_id and str(mission_id).strip())
    baseline = (baseline_commit or "").strip()

    if not baseline and is_modern:
        raise BaselineMergeCommitError(f"Cannot record baseline_merge_commit for modern mission {feature_dir.name}: no target baseline SHA was captured.")

    meta_path = feature_dir / META_JSON
    if not meta_path.exists():
        if is_modern:
            raise BaselineMergeCommitError(f"Cannot record baseline_merge_commit for modern mission {feature_dir.name}: meta.json is missing.")
        logger.warning(
            "Cannot record baseline_merge_commit for %s: meta.json is missing",
            feature_dir.name,
        )
        return None

    try:
        meta = load_meta_fail_closed(feature_dir)
    except MissionMetaReadError as exc:
        if is_modern:
            raise BaselineMergeCommitError(f"Cannot record baseline_merge_commit for modern mission {feature_dir.name}: meta.json is invalid ({exc}).") from exc
        logger.warning(
            "Cannot record baseline_merge_commit for %s: %s",
            feature_dir.name,
            exc,
        )
        return None

    if meta is None:
        if is_modern:
            raise BaselineMergeCommitError(f"Cannot record baseline_merge_commit for modern mission {feature_dir.name}: meta.json could not be loaded.")
        return None

    changed = False

    # baseline_merge_commit — only for missions with a captured baseline SHA,
    # idempotent on --resume.
    existing_baseline = meta.get("baseline_merge_commit")
    if baseline and not (existing_baseline and str(existing_baseline).strip()):
        meta["baseline_merge_commit"] = baseline
        changed = True

    # merged_at (+ merged_commit) — the #4090 completion marker, written for
    # every merge, idempotent on --resume.
    if not str(meta.get("merged_at") or "").strip():
        meta["merged_at"] = now_utc_iso()
        meta["merged_commit"] = _resolve_merge_commit(feature_dir) or baseline
        changed = True

    if changed:
        write_meta(feature_dir, meta, validate=False)
        return meta_path
    return None


def _recorded_baseline_from_working_meta(feature_dir: Path | None) -> str:
    if feature_dir is None:
        return ""
    try:
        working_meta = load_meta_fail_closed(feature_dir)
    except MissionMetaReadError:
        return ""
    if not isinstance(working_meta, dict):
        return ""
    return str(working_meta.get("baseline_merge_commit") or "").strip()


def _read_committed_meta_json(
    main_repo: Path,
    target_branch: str,
    meta_rel: str,
    mission_slug: str,
) -> dict[str, object]:
    ret, out, err = run_command(
        ["git", "show", f"{target_branch}:{meta_rel}"],
        capture=True,
        check_return=False,
        cwd=main_repo,
    )
    if ret != 0:
        raise BaselineMergeCommitError(
            f"Post-merge baseline validation failed for {mission_slug}: "
            f"could not read {meta_rel} from {target_branch} "
            f"({(err or '').strip() or 'git show failed'})."
        )

    try:
        committed_meta = decode_meta(out, on_malformed="raise")
    except MetaDecodeError as exc:
        message = str(exc)
        if message.startswith("Expected JSON object, got "):
            raise BaselineMergeCommitError(
                f"Post-merge baseline validation failed for {mission_slug}: committed {meta_rel} on {target_branch} is not a JSON object."
            ) from exc
        raise BaselineMergeCommitError(
            f"Post-merge baseline validation failed for {mission_slug}: committed {meta_rel} on {target_branch} is not valid JSON ({exc})."
        ) from exc
    return committed_meta if committed_meta is not None else {}


def assert_baseline_merge_commit_on_target(
    main_repo: Path,
    mission_slug: str,
    target_branch: str,
    expected_baseline: str | None,
    *,
    feature_dir: Path | None = None,
    mission_id: str | None = None,
) -> None:
    """Fail the merge if ``baseline_merge_commit`` did not land on *target_branch*.

    Mirrors :func:`_assert_merged_wps_reached_done`: it reads the target
    branch's COMMITTED ``kitty-specs/<slug>/meta.json`` via
    ``git show <target>:<path>`` and asserts ``baseline_merge_commit`` is both
    present and equal to the baseline that was actually RECORDED for this
    mission. This is the post-commit invariant that closes the gap behind
    ``MISSION_REVIEW_MODE_MISMATCH``: it proves the baseline is durable in git
    history (not just in the working tree) before any worktree removal or
    branch cleanup runs.

    The expected baseline is read from the recorded mission ``meta.json`` in
    *feature_dir* (the idempotent value written by
    :func:`record_baseline_merge_commit`) and only falls back to
    *expected_baseline* when that is unavailable. This is deliberate:
    ``target_baseline_sha`` is re-derived from the live target HEAD on every
    invocation, so on ``spec-kitty merge --resume`` — after a prior run already
    landed the mission/bookkeeping commits — the live HEAD has advanced past the
    original baseline. Comparing the committed value against a re-derived HEAD
    would spuriously fail an otherwise-correct resume; comparing it against the
    recorded value does not.

    Only enforced for **modern missions** (``mission_id`` set). Legacy missions
    never carry a baseline and are skipped.
    """
    if not (mission_id and str(mission_id).strip()):
        return

    recorded = _recorded_baseline_from_working_meta(feature_dir)
    expected = recorded or (expected_baseline or "").strip()
    if not expected:
        raise BaselineMergeCommitError(f"Cannot verify baseline_merge_commit for modern mission {mission_slug}: no recorded baseline SHA was found.")

    meta_rel = f"kitty-specs/{mission_slug}/{META_JSON}"
    committed_meta = _read_committed_meta_json(main_repo, target_branch, meta_rel, mission_slug)
    committed_baseline = str(committed_meta.get("baseline_merge_commit") or "").strip()
    if not committed_baseline:
        raise BaselineMergeCommitError(
            f"Post-merge baseline validation failed for {mission_slug}: "
            f"baseline_merge_commit is missing from committed {meta_rel} on "
            f"{target_branch}. Downstream `spec-kitty review --mode post-merge` "
            f"would fail with MISSION_REVIEW_MODE_MISMATCH."
        )

    if committed_baseline != expected:
        raise BaselineMergeCommitError(
            f"Post-merge baseline validation failed for {mission_slug}: "
            f"committed baseline_merge_commit ({committed_baseline}) on "
            f"{target_branch} does not match the captured baseline ({expected})."
        )


__all__ = [
    "BaselineMergeCommitError",
    "record_baseline_merge_commit",
    "assert_baseline_merge_commit_on_target",
]
