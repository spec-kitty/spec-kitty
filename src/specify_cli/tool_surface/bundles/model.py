"""Data model for plugin bundles and pre-publish validation results.

All structures are frozen (immutable, hashable) dataclasses. Sequence fields use
``tuple`` rather than ``list`` so the dataclasses remain hashable, matching the
convention established by :mod:`specify_cli.tool_surface.model`.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..enums import ToolSurfaceKind
from ..findings import SurfaceFinding
from ..operations import ApplyConsent, FileState, OperationRoot, OwnerAssessment

# Stable distribution-target keys. These are inert label values used to tag a
# projected bundle; they never name an install/publish channel.
TARGET_CLAUDE_CODE = "claude_code_plugin"
TARGET_COPILOT = "copilot_skill_package"
TARGET_VSCODE = "vscode_extension"


@dataclass(frozen=True)
class BundleEntry:
    """One surface included in a plugin bundle."""

    surface_kind: ToolSurfaceKind
    source_path: Path
    bundle_relative_path: str
    content: bytes | None = None
    mode: int = 0o644
    logical_owners: tuple[str, ...] = ()
    surface_ids: tuple[str, ...] = ()
    sources: tuple[Path, ...] = ()
    source_root: Path | None = None
    retained: tuple[tuple[Path, bytes, int], ...] = ()
    claims: tuple[tuple[Path, str, str], ...] = ()


@dataclass(frozen=True)
class BundleObservation:
    """An exact no-follow observation, optionally including directory members."""

    path: Path
    state: FileState
    device: int | None
    inode: int | None
    children: tuple[str, ...] | None = None


@dataclass(frozen=True)
class StagedFile:
    """One retained bundle output, including supporting files and manifests."""

    path: str
    content: bytes
    mode: int = 0o644
    logical_owners: tuple[str, ...] = ("plugin_bundle",)
    surface_ids: tuple[str, ...] = ()
    manifest: bool = False
    managed: bool = True


@dataclass(frozen=True)
class PreparedBundle:
    """One whole-root owner batch; apply consumes these bytes without rendering."""

    root: OperationRoot
    consent: ApplyConsent
    files: tuple[StagedFile, ...]
    observations: tuple[BundleObservation, ...]
    suppliers: tuple[OwnerAssessment, ...] = ()
    version: str | None = None
    write_paths: tuple[str, ...] = ()
    supporting_dirs: tuple[tuple[str, int], ...] = ()

    @property
    def execution_artifacts(self) -> tuple[tuple[str, str, str], ...]:
        """Bound the existing per-file atomic writer's apply-only temporary paths."""
        return tuple(
            (str(Path(member.path).parent), f".{Path(member.path).name}." + "[0-9a-f]" * 32 + ".tmp", "atomic_write")
            for member in self.files
            if member.path in self.write_paths
        )


@dataclass(frozen=True)
class BundleSources:
    """Concrete upstream owner outputs and explicit staging selection."""

    assessments: tuple[OwnerAssessment, ...] = ()
    selected_targets: tuple[str, ...] = ()


@dataclass(frozen=True)
class PluginBundle:
    """A projected plugin bundle descriptor for one distribution target.

    This is a *declarative* artifact: it records which surfaces belong in the
    bundle and where they sit inside the package layout. Producing a
    :class:`PluginBundle` does not install, register, enable, or publish
    anything (FR-016, C-006).
    """

    distribution_target: str
    entries: tuple[BundleEntry, ...]
    manifest_path: Path | None

    def kinds(self) -> frozenset[ToolSurfaceKind]:
        """Return the set of surface kinds present in the bundle."""
        return frozenset(entry.surface_kind for entry in self.entries)


@dataclass(frozen=True)
class BundleValidationResult:
    """Outcome of validating a :class:`PluginBundle` before publication."""

    passed: bool
    missing_surfaces: tuple[SurfaceFinding, ...]
    warnings: tuple[str, ...]
    distribution_target: str
