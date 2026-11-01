"""One-time re-baseline of recorded snapshot hashes (FR-009, NFR-003, WP05).

WP02 migrated the CLI emit path onto the canonical dossier snapshot hash
(``sha256:``-prefixed, computed over the normalized WP static projection —
see :func:`specify_cli.dossier.hasher.compute_dossier_snapshot_hash`). Snapshot
hashes recorded *before* that cutover were persisted under the retired
concat-of-hashes / bare-hex formula and over the old raw-byte per-artifact
basis, so they are non-comparable with a freshly computed canonical hash. Left
alone they would read as divergent even when nothing changed.

This module provides the one-time re-baseline that recomputes recorded snapshot
hashes under the canonical definition, so unchanged content reconciles as
PARITY after the cutover (FR-009) with zero false-divergence across the local
backlog (NFR-003). It is acceptable to recompute historical hashes because
there are no live hosted customers (spec Assumption A-003).

Design guarantees:

- **Canonical, not re-implemented (C-001).** The hash is produced by re-running
  the live pipeline — :class:`specify_cli.dossier.indexer.Indexer` →
  :func:`specify_cli.dossier.snapshot.compute_snapshot` — the SAME path the
  drift/reconcile surface uses. It does not transform recorded component hashes
  (those carry the retired raw-byte WP basis and would not match a reconcile).
- **Read-only over source artifacts (#2263).** Indexing only reads the mission
  source tree; the re-baseline writes solely to the recorded
  ``.kittify/dossiers/<slug>/snapshot-latest.json`` cache file, never to a
  source artifact.
- **Idempotent.** A snapshot already in the canonical (``sha256:``-prefixed)
  form is left byte-for-byte untouched, so re-running is a no-op.
- **Full re-snapshot, NOT a pure hash reformat (#2883 item 7).** A non-canonical
  recorded hash is replaced by recomputing over *current* source, so any source
  change made since the last emit is absorbed into the new baseline. In other
  words re-baseline silently advances the recorded hash to current source and
  thereby masks any pre-cutover drift. This is intentional for the one-time
  cutover and bounded by A-003 (no live hosted customers); a later reader must
  not mistake it for reformatting the stored value in place.

See: kitty-specs/dossier-parity-reconciler-01KXYXVP/spec.md (FR-009, NFR-003,
A-003) and tasks/WP05-rebaseline-migration.md (T019-T021).

Org-awareness (FR-003, mission cascade-org-inert-01M07E9P, WP01)
------------------------------------------------------------------

Until this WP, ``Indexer`` was constructed with no ``repo_root``
(``Indexer(ManifestRegistry())``), so a configured org pack's
``expected-artifacts.yaml`` override never reached ``rebaseline`` — unlike
every other caller of ``Indexer`` (``reconcile.py``, ``sync/dossier_pipeline.py``,
both already thread ``repo_root``).

**T001 worktree investigation (outcome (a) — worktrees never carry dossier
snapshots). Historical evidence trail, recorded before the sync transport was
deleted (issue #5): every ``sync/dossier_pipeline.py`` site it names is gone,
the conclusion (worktrees never carry snapshots) still describes this module's
guarantee.** Evidence trail. ``Indexer.__init__``'s docstring frames
``repo_root`` as the value threaded into
``manifest_registry.load_manifest(mission_type, repo_root=...)``
(``indexer.py:89-102``); the sole write site for a recorded snapshot is
``save_snapshot`` (``dossier/snapshot.py:154``), called from exactly one
production function, the private helper ``_emit_snapshot``
(``sync/dossier_pipeline.py:117``, ``save_snapshot`` call at line 140).
``_emit_snapshot`` has exactly one caller, ``sync_feature_dossier``
(``sync/dossier_pipeline.py:264``, calls ``_emit_snapshot`` at line 355),
itself only ever invoked via ``trigger_feature_dossier_sync_if_enabled``
(``sync/dossier_pipeline.py:413``). Reaching that function is possible two
ways — DIRECT calls, and one INDIRECT fan-out registered at import time —
both traced below.

*(A) Direct calls.* Nine production call sites call
``trigger_feature_dossier_sync_if_enabled`` (or a same-named thin wrapper
around it) directly:
``cli/commands/agent/tasks_mark_status.py``, ``workflow_executor.py`` (the
``implement``/claim path), ``mission_finalize.py``,
``mission_setup_plan.py``, ``mission_record_analysis.py``, ``research.py``,
``merge/executor.py:1300`` (``_phase_dossier_and_stale``, the
``spec-kitty merge`` post-merge phase — passes ``run.main_repo``, a field
explicitly named/typed as the main checkout), and two migration flows —
``migration/backfill_identity.py:265-277`` (``_rehash_modified_missions``,
the ``migrate backfill-identity`` flow) and
``migration/normalize_mission_lifecycle.py:108-111``
(``_apply_identity_normalization``, the ``migrate
normalize-mission-lifecycle`` flow). All nine resolve their own
``repo_root`` via ``locate_project_root()`` (``core/paths.py:182`` —
docstring: "Locate the MAIN spec-kitty project root directory, **even from
within worktrees**" / "returns Path to MAIN project root (not worktree)"),
the equivalent ``find_repo_root()`` (``task_utils/support.py:45``, itself
delegating to the same primitive), or ``get_main_repo_root()``
(``core/paths.py:451`` — "Get the main repository root, even if called from
a worktree" — reached transitively via ``workflow.py:791``,
``main_repo_root = get_main_repo_root(repo_root)``, which
``workflow_executor.py`` then takes as given per its own docstring at
``workflow_executor.py:513-515``); the two ``migrate_cmd.py`` flows call
``locate_project_root()`` directly (``cli/commands/migrate_cmd.py:265`` for
``backfill-identity``, and the equivalent pattern at the sibling
``normalize-mission-lifecycle`` command). ``migrate rebaseline`` itself
(``cli/commands/migrate_cmd.py``, ``rebaseline_dossier_hashes``) resolves
its own ``repo_root`` the same way.

*(B) Indirect fan-out — removed (issue #677).* This section previously
traced a second pathway into ``trigger_feature_dossier_sync_if_enabled``:
``sync/__init__.py``'s ``_dossier_sync_handler``, registered at import time
via ``register_default_handlers()``, forwarded into it via
``status/adapters.py``'s ``fire_dossier_sync``/``register_dossier_sync_handler``
registry, fired from ``status/emit.py`` (inside
``emit_status_transition``/``emit_status_transition_batch``) and the
transactional wrapper's ``_defer_dossier_sync``. That registrant lived in
``sync/__init__.py``, which issue #5 deleted along with the rest of the sync
transport — leaving the registry with zero production registrants ever
since: every call to ``fire_dossier_sync`` fanned out over an empty handler
list and was, in practice, a no-op. Issue #677 removed the now-dead seam
(``fire_dossier_sync``, ``register_dossier_sync_handler``, the registry, and
every call site) rather than leave a permanently-empty registry in place.
The worktree-safety analysis this section used to carry no longer applies —
there is no fan-out left to be worktree-unsafe.

``.kittify/dossiers/`` is also gitignored (``.gitignore:66,82,86,87``), so a
worktree checkout cannot inherit a stray recorded snapshot via git either.

Net: with (B) gone, every real write path for a recorded snapshot is a
direct call from (A) above, and every one of those nine call sites resolves
its own ``repo_root`` via ``get_main_repo_root()``, ``find_repo_root()``, or
``locate_project_root()`` — all worktree-aware, all resolving to the
PRIMARY/main checkout. So a recorded snapshot still never gets written from
a ``.worktrees/<slug>-<mid8>-lane-<id>/`` path; that invariant no longer
depends on how any indirect fan-out resolves ``repo_root``, since none
remains.

**Fail-safe, not forced.** The derivation still only holds because every
production writer's PRIMARY-partition resolution is literally
``<repo_root>/KITTY_SPECS_DIR/<mission_slug>`` — a structural invariant, not
merely an assumption. ``_derive_repo_root`` below checks that invariant
(``feature_dir.parent.name == KITTY_SPECS_DIR``) before deriving anything,
and returns ``None`` (today's org-blind behavior) when it does not hold —
e.g. a hand-placed or legacy-layout snapshot not nested under
``kitty-specs/``. A wrong ``repo_root`` is worse than none: it would silently
read a *different* project's org config.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from specify_cli.core.constants import KITTY_SPECS_DIR
from specify_cli.dossier.indexer import Indexer
from specify_cli.dossier.manifest import ManifestRegistry
from specify_cli.dossier.snapshot import compute_snapshot

logger = logging.getLogger(__name__)

#: Filename of the recorded per-mission snapshot cache.
SNAPSHOT_FILENAME = "snapshot-latest.json"

#: Prefix that marks the canonical dossier snapshot hash (WP01/WP02, FR-003).
_CANONICAL_PREFIX = "sha256:"

#: Fallback mission type when a mission's ``meta.json`` is typeless/absent —
#: the same default the deleted sync dossier pipeline used.
_DEFAULT_MISSION_TYPE = "software-dev"


@dataclass(frozen=True)
class RebaselineOutcome:
    """Result of re-baselining a single recorded snapshot.

    Attributes:
        snapshot_path: The recorded ``snapshot-latest.json`` that was inspected.
        mission_slug: The mission slug (recorded snapshot's ``mission_slug`` or,
            failing that, the dossier directory name).
        old_hash: The recorded hash before re-baseline.
        new_hash: The recorded hash after re-baseline (canonical when changed;
            equal to ``old_hash`` on a no-op or error).
        changed: True when the recorded hash was rewritten (or, under
            ``dry_run``, *would* be rewritten).
        error: A short reason string when the snapshot could not be re-baselined
            (left untouched); ``None`` on success.
    """

    snapshot_path: Path
    mission_slug: str
    old_hash: str
    new_hash: str
    changed: bool
    error: str | None = None


def is_canonical_snapshot_hash(value: str | None) -> bool:
    """True if *value* is already in the canonical ``sha256:``-prefixed form."""
    return value is not None and value.startswith(_CANONICAL_PREFIX)


def iter_recorded_snapshot_files(root: Path, *, mission_slug: str | None = None) -> Iterator[Path]:
    """Yield every recorded ``snapshot-latest.json`` under *root*, sorted.

    Discovers the ``.kittify/dossiers/<slug>/snapshot-latest.json`` cache files
    written by the live dossier sync, whether *root* is a single mission tree,
    a repository root, or a directory of many missions (the local backlog).

    ``mission_slug`` (#6347) narrows the yield to one Mission's recorded
    snapshot(s); ``None`` keeps the whole-backlog sweep. The scope is decided
    from the PATH (:func:`_snapshot_belongs_to_mission`), never by opening each
    candidate: a scoped run must read at most the target Mission's files, so it
    may not pay for a corpus-wide read to decide what to skip.

    Args:
        root: Directory to search recursively.
        mission_slug: Optional canonical Mission slug to scope the sweep to.

    Yields:
        Paths to recorded snapshot files, in sorted (deterministic) order.
    """
    candidates = sorted(root.glob(f"**/.kittify/dossiers/*/{SNAPSHOT_FILENAME}"))
    if mission_slug is None:
        yield from candidates
        return
    yield from (path for path in candidates if _snapshot_belongs_to_mission(path, mission_slug))


def _snapshot_belongs_to_mission(snapshot_path: Path, mission_slug: str) -> bool:
    """True when *snapshot_path* is *mission_slug*'s recorded snapshot.

    Identity comes from the layout alone, in either of its two real shapes:

    - ``<project>/.kittify/dossiers/<slug>/snapshot-latest.json`` — the dossier
      directory is named for the Mission; and
    - ``kitty-specs/<slug>/.kittify/dossiers/<dossier-slug>/snapshot-latest.json``
      — the owning source directory is named for the Mission. This second
      signal is what keeps a snapshot whose DOSSIER directory slug differs from
      the Mission slug (``rebaseline_snapshot_file`` documents that case) in
      scope.

    The recorded ``mission_slug`` field inside the JSON is deliberately NOT
    consulted: it is only knowable by reading each candidate, and a scoped run
    must read at most the target Mission's files (#6347, NFR-001). A snapshot
    that matches neither path signal is left out of a scoped run — and is still
    picked up by an unscoped one.
    """
    if snapshot_path.parent.name == mission_slug:
        return True
    try:
        feature_dir = _resolve_feature_dir(snapshot_path)
    except IndexError:
        # A hand-built path shallower than <src>/.kittify/dossiers/<slug>/<file>
        # carries no source-directory signal; treat it as out of scope.
        return False
    return feature_dir.name == mission_slug


def _resolve_feature_dir(snapshot_path: Path) -> Path:
    """Resolve the mission source directory for a recorded snapshot file.

    Layout: ``<feature_dir>/.kittify/dossiers/<slug>/snapshot-latest.json`` —
    the feature directory is three levels above the enclosing ``<slug>`` dir.
    """
    return snapshot_path.parents[3]


def _derive_repo_root(feature_dir: Path) -> Path | None:
    """Derive the owning project's ``repo_root`` from a mission ``feature_dir``
    (FR-003, derivation (B)).

    Every production writer of a recorded dossier snapshot resolves
    ``feature_dir`` to ``<repo_root>/KITTY_SPECS_DIR/<mission_slug>`` (see this
    module's docstring, "Org-awareness" section, for the full T001 evidence
    trail) — so ``repo_root = feature_dir.parent.parent`` is correct whenever
    ``feature_dir``'s immediate parent is actually named ``KITTY_SPECS_DIR``.
    That check is the one structural invariant the whole derivation depends
    on, and it is verified here rather than assumed.

    Fails SAFE — returns ``None`` (today's org-blind behavior, identical to
    before this WP) — when the invariant does not hold, e.g. a hand-placed or
    legacy-layout snapshot not nested under ``kitty-specs/``. A wrong
    ``repo_root`` is worse than none: it would silently read a *different*
    project's org config.
    """
    if feature_dir.parent.name != KITTY_SPECS_DIR:
        return None
    return feature_dir.parent.parent


def rebaseline_snapshot_file(snapshot_path: Path, *, dry_run: bool = False) -> RebaselineOutcome:
    """Re-baseline one recorded snapshot to the canonical hash (FR-009).

    Reads the recorded snapshot; if its hash is already canonical it is a no-op
    (idempotent). Otherwise the mission source tree is re-indexed and a fresh
    canonical snapshot is computed via the live pipeline, and the recorded file
    is rewritten in place with the canonical values (unless ``dry_run``).

    The mission source tree is only *read*; the sole write target is the
    recorded snapshot cache file itself (#2263).

    Args:
        snapshot_path: Path to a recorded ``snapshot-latest.json``.
        dry_run: When True, compute the canonical hash and report whether it
            would change, but do not write.

    Returns:
        A :class:`RebaselineOutcome` describing the (potential) change.
    """
    mission_slug = snapshot_path.parent.name
    try:
        data = json.loads(snapshot_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        logger.warning("Cannot read recorded snapshot %s: %s", snapshot_path, exc)
        return RebaselineOutcome(snapshot_path, mission_slug, "", "", changed=False, error="unreadable_snapshot")

    old_hash = str(data.get("parity_hash_sha256", ""))
    mission_slug = str(data.get("mission_slug") or mission_slug)

    # Idempotent: an already-canonical snapshot is left byte-for-byte untouched.
    if is_canonical_snapshot_hash(old_hash):
        return RebaselineOutcome(snapshot_path, mission_slug, old_hash, old_hash, changed=False)

    feature_dir = _resolve_feature_dir(snapshot_path)
    if not feature_dir.is_dir():
        logger.warning("Source dir missing for recorded snapshot %s", snapshot_path)
        return RebaselineOutcome(snapshot_path, mission_slug, old_hash, old_hash, changed=False, error="source_missing")

    # Recompute under the canonical definition by RE-RUNNING the live pipeline
    # over source (never transforming the retired recorded component hashes).
    try:
        from specify_cli.mission import get_mission_type

        mission_type = get_mission_type(feature_dir) or _DEFAULT_MISSION_TYPE
        repo_root = _derive_repo_root(feature_dir)
        dossier = Indexer(ManifestRegistry(), repo_root=repo_root).index_feature(feature_dir, mission_type)
        snapshot = compute_snapshot(dossier)
    except Exception as exc:  # noqa: BLE001 - one bad mission must not abort the backlog sweep
        logger.warning("Re-index failed for %s: %s", feature_dir, exc)
        return RebaselineOutcome(snapshot_path, mission_slug, old_hash, old_hash, changed=False, error=f"reindex_failed: {exc}")

    new_hash = snapshot.parity_hash_sha256

    if not dry_run:
        # Rewrite the recorded snapshot IN PLACE (same file), so a snapshot
        # whose dossier-dir slug differs from the indexed slug is still updated
        # where it lives. Serialization mirrors snapshot.save_snapshot.
        payload = snapshot.model_dump()
        snapshot_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

    return RebaselineOutcome(snapshot_path, mission_slug, old_hash, new_hash, changed=True)


def rebaseline_recorded_snapshots(root: Path, *, dry_run: bool = False, mission_slug: str | None = None) -> list[RebaselineOutcome]:
    """Re-baseline every recorded snapshot under *root* (NFR-003 backlog sweep).

    Discovers all recorded ``snapshot-latest.json`` files and re-baselines each.
    A failure on one mission is captured in its :class:`RebaselineOutcome`
    (``error`` set, ``changed=False``) and never aborts the sweep.

    ``mission_slug`` (#6347) scopes the sweep to one Mission's recorded
    snapshot(s); ``None`` keeps the whole-backlog sweep.

    Args:
        root: Directory to search recursively (repo root or backlog directory).
        dry_run: When True, report changes without writing.
        mission_slug: Optional canonical Mission slug to scope the sweep to.

    Returns:
        One :class:`RebaselineOutcome` per in-scope recorded snapshot.
    """
    return [rebaseline_snapshot_file(path, dry_run=dry_run) for path in iter_recorded_snapshot_files(root, mission_slug=mission_slug)]
