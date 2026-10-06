"""Identity/coord resolution seam for ``runtime.next.runtime_bridge`` (#2531 WP10).

**The hottest fracture line in the god-module decomposition** — coord-branch
naming, mission-ULID resolution, and primary-feature-dir resolution. It
carries the mission's fattest scar debt (#2091/#1978/#1918/#1814/#2069) and is
correctness-critical: a malformed coord branch composed here eventually drives
a ``git worktree`` call that exits 128. It is cut LAST (behind the fattest
golden coverage: the WP01 parity oracle + WP02 compat guard, both proven green
on every prior extraction) because a silent drift in this cluster is the most
dangerous possible regression in the whole mission.

Sole home of:

- :func:`_primary_runtime_feature_dir` — the topology-BLIND primary-checkout
  mission dir resolver identity/meta reads anchor on (the #2091 fix).
- :func:`_resolve_coordination_branch` — coord-branch naming: reads the
  declared ``coordination_branch`` from ``meta.json`` when present, otherwise
  composes it via the fail-closed :func:`mission_branch_name_required` seam
  (#1978). Raises :class:`BranchIdentityUnresolved` for a genuinely
  unresolvable modern mission — this fail-loud contract is preserved EXACTLY,
  never swallowed by a fallback (C-001; the exit-128 scar this WP is named
  for is what a silently-wrong compose here would eventually cause).
- :func:`_resolve_mission_ulid` — reads the canonical ULID ``mission_id`` from
  ``meta.json`` via the identity SSOT (:func:`resolve_mission_identity`),
  fail-closed (``None``, never the slug, when absent — FR-004).

**KEEP-IN-PLACE / not moved.** ``_wrap_with_decision_git_log`` and
``_mission_routes_through_coordination`` stay in the residual
(``runtime_bridge.py``) per research.md §Compat -- they are the *callers* of
this cluster, not part of it. The residual calls the three functions below on
this seam (``_identity_seam.<name>``); it defines none of them.

**Patch point.** ``_primary_runtime_feature_dir`` is called directly by
``_resolve_coordination_branch`` and ``_resolve_mission_ulid`` (module-global
lookup), so a test that replaces it patches
``runtime.next.runtime_bridge_identity._primary_runtime_feature_dir`` and
steers both, plus ``committed_authority``'s merged-mission short-circuit,
which imports it from here.

Import DAG (research.md §Import DAG): this module may import
``runtime_bridge_io`` (not needed today -- none of the three functions above
requires an I/O-port call); it must NOT be imported by ``runtime_bridge_
cores`` (enforced by ``tests/runtime/test_runtime_bridge_family_arch.py``'s
``test_identity_seam_not_imported_by_cores``). No top-level
``decision.py -> runtime_bridge*`` edge is
introduced (C-007) -- this module imports neither ``runtime_bridge`` nor
``decision`` at module scope.

De-godding effort: https://github.com/Priivacy-ai/spec-kitty/issues/2531
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from specify_cli.mission_metadata import load_meta_or_empty


def _primary_runtime_feature_dir(repo_root: Path, mission_slug: str) -> Path:
    """Return the PRIMARY-checkout mission feature dir for identity/meta reads.

    Mission identity (``mission_id``, ``coordination_branch``, stored topology)
    is persisted ONLY on the primary checkout's ``meta.json``. A KIND-BLIND
    resolver (``candidate_feature_dir_for_mission``) genuinely CAN return the
    coordination worktree once it is materialized under coordination topology
    — whose mission dir has NO ``meta.json`` — so reading identity there found
    nothing and fell back to the bare slug, yielding an empty ``mid8`` and a
    malformed ``kitty/mission-<slug>-`` coord branch (#2091). Anchor on the
    topology-BLIND ``PRIMARY_METADATA`` leg of the kind-aware placement seam,
    mirroring :func:`_mission_routes_through_coordination` (``runtime_bridge.py``)
    and the canonical precedent in ``core/paths.py`` (the same bug-class fixed
    for the merge target): the kind-aware seam CANNOT land on a
    materialized-but-empty coord worktree here — for a PRIMARY-partition kind
    the decision layer short-circuits to the primary anchor for every topology
    and coord state, before any coord probe (read-side-seam-primary-primitive-
    closure-01KYKMMT WP07, T032 — FR-004/FR-015).
    """
    from mission_runtime import MissionArtifactKind, placement_seam

    result: Path = placement_seam(repo_root, mission_slug).read_dir(
        MissionArtifactKind.PRIMARY_METADATA
    )
    return result


def _resolve_coordination_branch(mission_slug: str, repo_root: Path) -> str:
    """Return the coordination branch for a mission from meta.json.

    When meta.json declares ``coordination_branch`` explicitly, that value is
    authoritative. Otherwise the branch is composed via the fail-closed WP01
    seam (:func:`coord_branch_name`/:func:`mission_branch_name_required`) using
    the declared ``mission_id``, instead of a bare ``kitty/mission-<slug>``
    f-string that drops the ``-<mid8>`` disambiguator (#1978). When the mission
    is legacy/unresolvable the seam still composes the legacy branch; a modern
    slug with no recoverable identity raises :class:`BranchIdentityUnresolved`,
    surfacing the lost identity rather than silently mis-composing (the
    malformed-coord-branch correctness path this WP is named for — preserved
    exactly, never swallowed here).
    """

    # load_meta_or_empty (post-#2091 silent contract) absorbs a missing or
    # malformed meta.json to {}, matching the prior try/except-{} absorption.
    meta: dict[str, Any] = load_meta_or_empty(_primary_runtime_feature_dir(repo_root, mission_slug))
    branch = meta.get("coordination_branch")
    if isinstance(branch, str) and branch.strip():
        return branch.strip()

    from specify_cli.lanes.branch_naming import mission_branch_name_required

    mission_id = meta.get("mission_id")
    resolved_id = mission_id.strip() if isinstance(mission_id, str) and mission_id.strip() else None
    # Local annotation re-narrows the specify_cli.* import from Any back to
    # str (follow_imports = "skip" mypy override, see the note above).
    composed: str = mission_branch_name_required(mission_slug, resolved_id)
    return composed


def _resolve_mission_ulid(mission_slug: str, repo_root: Path) -> str | None:
    """Read the canonical ULID mission_id from meta.json via the identity SSOT.

    WP04/FR-004: Routes through ``mission_metadata.resolve_mission_identity``
    (the single source of truth) instead of hand-rolling a json.loads read.
    Returns the ULID string when present, or ``None`` when absent — fail-closed:
    callers must NOT substitute the slug for the absent ULID.
    """
    from specify_cli.mission_metadata import resolve_mission_identity  # noqa: PLC0415

    feature_dir = _primary_runtime_feature_dir(repo_root, mission_slug)
    # Local annotation re-narrows the specify_cli.* import from Any back to
    # str | None (follow_imports = "skip" mypy override, see the note above).
    mission_id: str | None = resolve_mission_identity(feature_dir).mission_id
    return mission_id
