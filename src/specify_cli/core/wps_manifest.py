"""Structured WP manifest reader for wps.yaml.

Provides the canonical data model, YAML loader, and tasks.md generator
for spec-kitty missions that use wps.yaml as their primary WP source.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, PrivateAttr, field_validator
from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from kernel.errors import GuardedReadError
from kernel.guarded_read import read_guarded


class WpsManifestReadError(GuardedReadError, RuntimeError):
    """Raised when ``wps.yaml`` exists but cannot be read or is malformed YAML.

    Mission cli-error-surface-seam WP07/#4746: pre-fix,
    :func:`load_wps_manifest` was fully unguarded for non-UTF-8 bytes and
    malformed YAML syntax -- both surfaced as a raw traceback through every
    reachable command (``finalize-tasks``, ``runtime.next.runtime_bridge``).
    Never raised when ``wps.yaml`` is simply absent (D5) -- that case still
    returns ``None`` (legacy mission, prose-based ``tasks.md`` fallback).

    Deliberately NOT raised for a schema-invalid-but-syntactically-valid
    manifest: that case still raises ``pydantic.ValidationError`` directly,
    unchanged from the pre-WP07 contract (pinned by
    ``tests/core/test_wps_manifest.py``'s
    ``test_malformed_raises_validation_error_with_field_name`` and
    siblings). ``pydantic.ValidationError`` is a ``pydantic-core``
    (Rust) type that cannot be practically re-parented onto
    :class:`kernel.errors.GuardedReadError` via multiple inheritance (its
    ``__new__`` does not accept this hierarchy's ``path``/``reason``
    keyword-only constructor contract) — so, per D3 ("subclass, never
    flat-replace" the existing type), the read+YAML-syntax guard-gap is
    closed here while the schema-validation surface is left exactly as
    every other caller already found it.
    """


class WorkPackageEntry(BaseModel):
    """One work package entry in wps.yaml."""

    id: str  # e.g. "WP01" — validated as WPnn pattern
    title: str
    dependencies: list[str] = Field(default_factory=list)
    owned_files: list[str] = Field(default_factory=list)
    requirement_refs: list[str] = Field(default_factory=list)
    subtasks: list[str] = Field(default_factory=list)
    prompt_file: str | None = None
    plan_concern_refs: list[str] = Field(default_factory=list)
    cross_cutting: bool = False

    # Internal: True when 'dependencies' key was present in the source YAML.
    # Set by load_wps_manifest(); NOT part of the serialized schema.
    _dependencies_explicit: bool = PrivateAttr(default=False)
    _plan_concern_refs_explicit: bool = PrivateAttr(default=False)
    _cross_cutting_explicit: bool = PrivateAttr(default=False)

    @field_validator("id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        if not re.match(r"^WP\d{2}$", v):
            raise ValueError(f"WP id must be WPnn (e.g. WP01), got: {v!r}")
        return v

    @field_validator("dependencies")
    @classmethod
    def validate_dependencies(cls, v: list[str]) -> list[str]:
        for dep in v:
            if not re.match(r"^WP\d{2}$", dep):
                raise ValueError(f"Dependency must be WPnn (e.g. WP01), got: {dep!r}")
        return v

    @field_validator("plan_concern_refs")
    @classmethod
    def validate_plan_concern_refs(cls, v: list[str]) -> list[str]:
        """Validate that each ref matches the IC-## pattern (ASCII digits only)."""
        for ref in v:
            if not re.match(r"^IC-\d{2}$", ref, re.ASCII):
                raise ValueError(
                    f"plan_concern_ref must match IC-## (e.g. IC-01), got: {ref!r}"
                )
        return v


class WpsManifest(BaseModel):
    """Top-level wps.yaml manifest."""

    work_packages: list[WorkPackageEntry]
    _concern_tracking_fields_seen: bool | None = PrivateAttr(default=None)
    _concern_tracking_required: bool | None = PrivateAttr(default=None)


def _parse_wps_manifest(content: bytes | str, feature_dir: Path) -> WpsManifest:
    """Decode already-read ``wps.yaml`` *content* into a validated :class:`WpsManifest`.

    Raises ``ruamel.yaml.YAMLError`` on malformed YAML or
    ``pydantic.ValidationError`` on a schema-invalid manifest — both
    collapsed by :func:`kernel.guarded_read.read_guarded` into
    :class:`WpsManifestReadError`.
    """
    text = content.decode("utf-8") if isinstance(content, bytes) else content
    yaml = YAML(typ="safe")
    raw: dict[str, Any] = yaml.load(text)

    # Track explicit dependencies before Pydantic validation
    wps_raw: list[dict[str, Any]] = raw.get("work_packages", [])
    manifest = WpsManifest.model_validate(raw)

    concern_tracking_fields_seen = False

    # Back-fill source-key presence on each entry using PrivateAttr mechanism.
    for entry, raw_wp in zip(manifest.work_packages, wps_raw):
        object.__setattr__(entry, "_dependencies_explicit", "dependencies" in raw_wp)
        plan_refs_explicit = "plan_concern_refs" in raw_wp
        cross_cutting_explicit = "cross_cutting" in raw_wp
        object.__setattr__(entry, "_plan_concern_refs_explicit", plan_refs_explicit)
        object.__setattr__(entry, "_cross_cutting_explicit", cross_cutting_explicit)
        concern_tracking_fields_seen = (
            concern_tracking_fields_seen or plan_refs_explicit or cross_cutting_explicit
        )

    object.__setattr__(
        manifest,
        "_concern_tracking_fields_seen",
        concern_tracking_fields_seen,
    )
    object.__setattr__(
        manifest,
        "_concern_tracking_required",
        concern_tracking_fields_seen or _plan_contains_implementation_concerns(feature_dir),
    )

    return manifest


def load_wps_manifest(feature_dir: Path) -> WpsManifest | None:
    """Load wps.yaml from feature_dir if present.

    Returns None if wps.yaml does not exist (legacy mission — use prose parser).

    Raises:
        WpsManifestReadError: If the file exists but cannot be read (e.g.
            non-UTF-8 bytes) or is malformed YAML syntax — a
            :class:`kernel.errors.GuardedReadError` subclass (see
            contracts/error-envelope.md).
        pydantic.ValidationError: If the file is valid YAML but fails
            schema validation, with the failing field name and value in the
            error message — unchanged from the pre-WP07 contract (see
            :class:`WpsManifestReadError`'s docstring for why this is not
            also re-parented onto ``GuardedReadError``).

    Args:
        feature_dir: Path to the kitty-specs/<mission>/ directory.
    """
    wps_path = feature_dir / "wps.yaml"
    if not wps_path.exists():
        return None

    return read_guarded(
        wps_path,
        lambda content: _parse_wps_manifest(content, feature_dir),
        errors=(YAMLError, AttributeError),
        error_cls=WpsManifestReadError,
    )


def dependencies_are_explicit(entry: WorkPackageEntry) -> bool:
    """Return True if the 'dependencies' key was present in the source YAML.

    When True, the pipeline must not overwrite or augment the value.
    When False, the field was absent from YAML and may be populated by tasks-packages.
    """
    return getattr(entry, "_dependencies_explicit", False)


def _plan_contains_implementation_concerns(feature_dir: Path) -> bool:
    """Return True when plan.md contains IC-## concern headings."""
    plan_path = feature_dir / "plan.md"
    if not plan_path.exists():
        return False
    try:
        plan_text = plan_path.read_text(encoding="utf-8")
    except OSError:
        return False
    return bool(re.search(r"(?m)^#{2,4}\s+IC-\d{2}\b", plan_text, re.ASCII))


def check_concern_refs_coverage(manifest: WpsManifest) -> list[str]:
    """Return a list of warning messages for WPs missing concern coverage.

    A WP is considered adequately covered if it has at least one entry in
    ``plan_concern_refs`` OR has ``cross_cutting`` set to ``True``.  WPs that
    have neither trigger a warning so the author can either cite an IC-## ref
    or explicitly mark the WP as cross-cutting infrastructure.

    Args:
        manifest: Loaded WpsManifest to inspect.

    Returns:
        A (possibly empty) list of human-readable warning strings, one per
        uncovered WP.  An empty list means all WPs have adequate coverage.
    """
    # Legacy manifests predate concern traceability. FR-010/NFR-001 require those
    # files to finalize without new warning noise when no new fields are present.
    if getattr(manifest, "_concern_tracking_required", None) is False:
        return []

    warnings: list[str] = []
    for wp in manifest.work_packages:
        if not wp.plan_concern_refs and not wp.cross_cutting:
            warnings.append(
                f"{wp.id} ({wp.title!r}): missing plan_concern_refs and "
                "cross_cutting is not set — add IC-## refs or set cross_cutting: true"
            )
    return warnings


def generate_tasks_md_from_manifest(manifest: WpsManifest, feature_name: str) -> str:
    """Generate tasks.md content from a WpsManifest.

    Output is a human-readable markdown document following tasks-template.md
    conventions. Does NOT include implementation notes or risks — those live
    in the WP prompt files.

    Args:
        manifest: Loaded WpsManifest.
        feature_name: Mission slug or friendly name for the heading.
    """
    lines: list[str] = [
        f"# Work Packages: {feature_name}",
        "",
        "_Generated by finalize-tasks from wps.yaml. Do not edit directly._",
        "",
        "---",
        "",
    ]

    for wp in manifest.work_packages:
        lines.append(f"## Work Package {wp.id}: {wp.title}")
        lines.append("")

        if wp.dependencies:
            lines.append(f"**Dependencies**: {', '.join(wp.dependencies)}")
        else:
            lines.append("**Dependencies**: None")

        if wp.requirement_refs:
            lines.append(f"**Requirement Refs**: {', '.join(wp.requirement_refs)}")

        if wp.plan_concern_refs:
            lines.append(f"**Plan Concerns**: {', '.join(wp.plan_concern_refs)}")

        if wp.owned_files:
            lines.append(f"**Owned Files**: {', '.join(wp.owned_files)}")

        if wp.subtasks:
            lines.append(f"**Subtasks**: {', '.join(wp.subtasks)}")

        if wp.prompt_file:
            lines.append(f"**Prompt**: `{wp.prompt_file}`")

        lines.append("")
        lines.append("---")
        lines.append("")

    return "\n".join(lines)
