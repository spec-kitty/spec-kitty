"""Work package kind normalisation for lane topologies (#7809, ADR 2026-11-06-3 Amendment 2026-11-22).

In a lane topology a ``planning_artifact`` work package is placed on
``lane-planning``, whose branch is the target branch. A docs work package that
owns paths outside ``kitty-specs/`` does real work, so ``finalize-tasks``
records it as ``code_change`` and it gets its own lane (operator ruling
"Normalise kind"). The size-based topology settlement counts it the same way
("Count it").

Pure: no I/O. A started work package is never rewritten (frozen lane
membership, ADR 2026-10-04-2). ``single_branch`` never calls this.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace

from specify_cli.ownership.models import OwnershipManifest, WorkProductKind
from specify_cli.ownership.paths import is_kitty_specs_path

__all__ = [
    "KindNormalisation",
    "KindRewrite",
    "normalise_kinds_for_lane_topology",
]


@dataclass(frozen=True)
class KindRewrite:
    """One work package recorded as ``code_change``, with the owned paths that caused it."""

    wp_id: str
    paths_outside_kitty_specs: tuple[str, ...]
    owns_kitty_specs_paths: bool

    def as_payload(self) -> dict[str, object]:
        """The ``kind_normalised`` JSON entry (``contracts/finalize-kind-normalisation.md``)."""
        return {
            "wp_id": self.wp_id,
            "from": WorkProductKind.PLANNING_ARTIFACT.value,
            "to": WorkProductKind.CODE_CHANGE.value,
            "paths_outside_kitty_specs": list(self.paths_outside_kitty_specs),
        }


@dataclass(frozen=True)
class KindNormalisation:
    """The normalised manifests and the work packages that were rewritten (in work package order)."""

    manifests: dict[str, OwnershipManifest]
    rewritten: tuple[KindRewrite, ...]

    @property
    def mixed(self) -> tuple[KindRewrite, ...]:
        """Rewritten work packages that also own ``kitty-specs/`` paths: they must be split."""
        return tuple(rewrite for rewrite in self.rewritten if rewrite.owns_kitty_specs_paths)


def _paths_outside_kitty_specs(owned_files: tuple[str, ...]) -> tuple[str, ...]:
    """The owned paths (globs included) that do not start with ``kitty-specs/``, in declared order."""
    return tuple(path for path in owned_files if not is_kitty_specs_path(path))


def normalise_kinds_for_lane_topology(
    manifests: Mapping[str, OwnershipManifest],
    *,
    started_wp_ids: frozenset[str],
) -> KindNormalisation:
    """Record each unstarted ``planning_artifact`` work package owning a path outside ``kitty-specs/`` as ``code_change``.

    Every other manifest is returned unchanged: a ``code_change`` work package, a
    planning work package confined to ``kitty-specs/`` (or owning nothing), and
    any started work package.
    """
    normalised: dict[str, OwnershipManifest] = {}
    rewritten: list[KindRewrite] = []
    for wp_id in sorted(manifests):
        manifest = manifests[wp_id]
        outside = _paths_outside_kitty_specs(manifest.owned_files)
        if manifest.execution_mode != WorkProductKind.PLANNING_ARTIFACT or not outside or wp_id in started_wp_ids:
            normalised[wp_id] = manifest
            continue
        normalised[wp_id] = replace(manifest, execution_mode=WorkProductKind.CODE_CHANGE)
        rewritten.append(
            KindRewrite(
                wp_id=wp_id,
                paths_outside_kitty_specs=outside,
                owns_kitty_specs_paths=len(outside) != len(manifest.owned_files),
            )
        )
    return KindNormalisation(manifests=normalised, rewritten=tuple(rewritten))
