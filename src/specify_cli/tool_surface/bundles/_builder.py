"""Shared build utilities for Spec Kitty plugin bundle projectors.

Provides :class:`BuildError` and helper functions used by both the Claude Code
and Codex bundle projectors.  All helpers are pure (no network / install / publish
side-effects).

**Scope guard (FR-016, C-006):** Nothing in this module installs, registers,
enables, or publishes a bundle.  All filesystem writes are confined to the
staging ``output_dir`` supplied by the caller.
"""

from __future__ import annotations

import importlib.metadata
import re
from pathlib import Path

from ..operations import ApplyConsent, AssessmentInputs, OperationRoot, OwnerAssessment
from .model import PreparedBundle, StagedFile
from .projection import apply_staging, confined_output, json_bytes, prepare_staging, staging_root, write_staged_file

# Minimum number of canonical command skills required in a complete bundle.
MIN_SKILL_COUNT = 14

# Semver pattern: MAJOR.MINOR.PATCH (patch may include pre-release suffix).
_SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+")

# Package name registered on PyPI / importlib.metadata.
_PACKAGE_NAME = "spec-kitty-cli"

# Fallback version emitted when the package metadata is unavailable (e.g.
# during editable / source-tree installs).
_VERSION_FALLBACK = "0.0.0+dev"


def get_cli_version() -> str:
    """Return the installed version of the ``spec-kitty-cli`` package.

    Falls back to :data:`_VERSION_FALLBACK` when the package metadata cannot
    be found (e.g. editable installs that have not been re-registered).  The
    caller is responsible for emitting a warning when the fallback is used.
    """
    try:
        return importlib.metadata.version(_PACKAGE_NAME)
    except importlib.metadata.PackageNotFoundError:
        return _VERSION_FALLBACK


def is_semver(version: str) -> bool:
    """Return ``True`` when *version* matches ``MAJOR.MINOR.PATCH`` (loose)."""
    return bool(_SEMVER_RE.match(version))


def write_json(path: Path, payload: dict[str, object] | bytes, *, mode: int = 0o644) -> None:
    """Compare a new JSON value, or atomically consume already-guarded JSON bytes."""
    if isinstance(payload, bytes):
        write_staged_file(path, payload, mode)
        return
    root = staging_root(path.parent)
    normalized = confined_output(path.parent, root) / path.name
    inputs = AssessmentInputs(root, consent=ApplyConsent(automatic=True))
    assessment = prepare_staging(inputs, (StagedFile(normalized.relative_to(root.path).as_posix(), json_bytes(payload, legacy=True), mode, manifest=True),), ())
    finish_build(assessment)


def command_members(prefix: Path, root: OperationRoot) -> tuple[tuple[StagedFile, ...], OwnerAssessment]:
    """Use WP04's concrete, once-rendered canonical command batch."""
    from specify_cli.skills.command_installer import PreparedCommands, prepare_commands

    supplier = prepare_commands(AssessmentInputs(OperationRoot("bundle-command-source", "project", Path("/"))), ("codex",))
    payload = supplier.prepared
    if not supplier.complete or not isinstance(payload, PreparedCommands):
        raise BuildError("; ".join(d.message for d in supplier.diagnostics))
    files = tuple(
        StagedFile((prefix / Path(command.path).parent.name / "SKILL.md").relative_to(root.path).as_posix(), command.content, logical_owners=("command_skills",))
        for command in payload.commands
        if command.content is not None
    )
    if len(files) < MIN_SKILL_COUNT:
        raise BuildError(f"Expected at least {MIN_SKILL_COUNT} skills, found {len(files)}. Check CANONICAL_COMMANDS in command_installer.")
    return files, supplier


def finish_build(assessment: OwnerAssessment) -> None:
    """Surface blocked preparation and exact failed application, not empty success."""
    if not assessment.complete:
        raise BuildError("; ".join(d.message for d in assessment.diagnostics))
    if isinstance(assessment.prepared, PreparedBundle) and assessment.prepared.version and not is_semver(assessment.prepared.version):
        import typer

        typer.echo(f"Warning: version {assessment.prepared.version!r} is not a clean semver string; the validator may reject it.", err=True)
    result = apply_staging(assessment, assessment.consent)
    if result.failed or result.skipped or result.diagnostics:
        raise BuildError("; ".join(d.message for d in result.diagnostics) or str(result))
    if any(d.state in {"preserve", "consent_required"} for d in assessment.dispositions):
        raise BuildError("Staged build preserved custom or consent-required content")


class BuildError(Exception):
    """Raised when a plugin bundle build step fails with a clear user message."""
