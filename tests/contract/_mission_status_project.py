"""The reference ``Project`` builder of the ``mission-status`` contract (plan D-P4, spec FR-001 to FR-007).

``build_project`` is the production entry point of the reference reader for ``GET /project``. It starts no process of
its own and writes nothing: the project slug comes from ``.kittify/config.yaml``, the recorded versions from
``.kittify/metadata.yaml``, the branch from the ``HEAD`` file, and the Mission count and the last activity from what
``GET /missions`` lists. The one thing that starts processes is the coordination resolver, which the builder reaches
only through the memo (``_mission_status_memo``), so its git queries are counted and never repeated.

Reading the metadata as the product reads it: ``ProjectMetadata.load`` applies ``.get`` to unvalidated YAML and raises
``AttributeError`` or ``TypeError`` for several shapes, and the YAML constructors can raise ``ValueError``. The builder
therefore reads the file once itself, checks the shape, calls ``load`` only when the shape is safe, and reads a
residual error as null: a metadata file the service cannot read is a null, never a failure of the read.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType
from typing import Any

import yaml

from kernel.clock import parse_iso
from specify_cli.coordination.surface_resolver import CoordinationBranchDeleted
from specify_cli.migration import schema_version as schema
from specify_cli.status.aggregate import CoordAuthorityUnavailable, MissionMetadataUnavailable
from specify_cli.status.reducer import materialize_snapshot
from specify_cli.upgrade.metadata import ProjectMetadata
from tests.contract._mission_status_memo import MemoEntry, ResolverMemo, memo_resolve
from tests.contract._mission_status_payloads import enumerate_missions, read_project_name

OUTSIDE_ROOT = "read directory outside this checkout"
HEALTHY = "healthy"
SCHEMA_DRIFT = "schema_drift"
# The three resolver outcomes the v1 reads turn into the Mission's own directory (the fourth fallback is a directory outside the checkout).
V1_FALLBACK_ERRORS = (CoordinationBranchDeleted, CoordAuthorityUnavailable, MissionMetadataUnavailable)
_VERSION = re.compile(r"[0-9A-Za-z][0-9A-Za-z.+!_-]{0,63}")
_BRANCH = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/-]*")
_BRANCH_MAX = 255
_HEADS_PREFIX = "refs/heads/"
_REF_PREFIX = "ref:"
_GITDIR_PREFIX = "gitdir:"
_PRODUCT_SENTINEL = "unknown"
# Errors a metadata file can raise while it is read or parsed: unreadable, not valid UTF-8, or a YAML constructor refusing a value.
_UNREADABLE = (OSError, ValueError, yaml.YAMLError)


@dataclass(frozen=True)
class ProjectOutcome:
    """The ``Project`` payload and the Missions whose read directory fell back to their own directory, with the reason."""

    body: dict[str, Any]
    fallbacks: dict[str, str] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# .kittify/metadata.yaml
# ---------------------------------------------------------------------------


def parsed_metadata(repo_root: Path) -> Any:
    """The parsed ``.kittify/metadata.yaml``, or None when it is absent, unreadable, not UTF-8 or not YAML."""
    path = repo_root / ".kittify" / "metadata.yaml"
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8-sig"))
    except _UNREADABLE:
        return None


def project_version(repo_root: Path) -> str | None:
    """``spec_kitty.version`` as ``ProjectMetadata.load`` reads it, projected: a matching string, else null (FR-002)."""
    try:
        metadata = ProjectMetadata.load(repo_root / ".kittify")
    except (AttributeError, TypeError, ValueError, OverflowError):
        return None
    version = metadata.version if metadata is not None else None
    if not isinstance(version, str) or version == _PRODUCT_SENTINEL or _VERSION.fullmatch(version) is None:
        return None
    return version


def schema_version_of(repo_root: Path) -> int | None:
    """``spec_kitty.schema_version`` exactly as ``get_project_schema_version`` coerces it; null when that returns None (FR-003)."""
    if not isinstance(parsed_metadata(repo_root), dict):
        return None
    try:
        return schema.get_project_schema_version(repo_root)
    except (*_UNREADABLE, OverflowError):
        return None


def health_of(schema_version: int | None) -> str:
    """``healthy`` exactly when the schema lies in the serving build's supported range (FR-004); never a function of a finding."""
    in_range = schema_version is not None and schema.MIN_SUPPORTED_SCHEMA <= schema_version <= schema.MAX_SUPPORTED_SCHEMA
    return HEALTHY if in_range else SCHEMA_DRIFT


# ---------------------------------------------------------------------------
# HEAD
# ---------------------------------------------------------------------------


def head_file(repo_root: Path) -> Path | None:
    """The ``HEAD`` file of the project: ``.git/HEAD``, or the ``HEAD`` of the gitdir a ``.git`` file names; None when there is none."""
    dot_git = repo_root / ".git"
    if dot_git.is_dir():
        return dot_git / "HEAD"
    if not dot_git.is_file():
        return None
    try:
        text = dot_git.read_text(encoding="utf-8").strip()
    except _UNREADABLE:
        return None
    if not text.startswith(_GITDIR_PREFIX):
        return None
    return (repo_root / text.removeprefix(_GITDIR_PREFIX).strip()) / "HEAD"


def read_head(repo_root: Path) -> str | None:
    """The branch name ``HEAD`` points at, with or without a commit; None for a detached, missing, unreadable or unparseable ``HEAD``."""
    head = head_file(repo_root)
    if head is None:
        return None
    try:
        text = head.read_text(encoding="utf-8").strip()
    except _UNREADABLE:
        return None
    if not text.startswith(_REF_PREFIX):
        return None
    target = text.removeprefix(_REF_PREFIX).strip()
    return target.removeprefix(_HEADS_PREFIX) if target.startswith(_HEADS_PREFIX) else None


def current_branch_of(repo_root: Path, leak: ModuleType) -> str | None:
    """``currentBranch`` (FR-005): the name of ``read_head`` when this contract can carry it, else null."""
    name = read_head(repo_root)
    if name is None or len(name) > _BRANCH_MAX or _BRANCH.fullmatch(name) is None:
        return None
    return None if leak.leak_codes(name, leak.STRICT) else name


# ---------------------------------------------------------------------------
# The Missions the project lists
# ---------------------------------------------------------------------------


def last_activity_of(instants: Iterable[str | None]) -> str | None:
    """The latest of ``instants`` compared as instants (offsets ordered by instant, not text), as that value's own string (FR-006)."""
    stamps = [stamp for stamp in instants if stamp]
    return max(stamps, key=lambda stamp: parse_iso(stamp).timestamp()) if stamps else None


def read_dir_of(repo_root: Path, name: str, entry: MemoEntry) -> tuple[Path, str | None]:
    """The directory a Mission is read from and the reason it fell back to its own directory, on the memo's raw outcome.

    The three resolver exceptions and a read directory outside the checkout map to the Mission's own directory, as in the v1
    reads; any other exception is a failure of the read and is raised again.
    """
    own = repo_root / "kitty-specs" / name
    outcome = entry.outcome
    if isinstance(outcome, Exception):
        if isinstance(outcome, V1_FALLBACK_ERRORS):
            return own, type(outcome).__name__
        raise outcome
    if outcome.resolve() == own.resolve():
        return own, None
    try:
        outcome.resolve().relative_to(repo_root.resolve())
    except ValueError:
        return own, OUTSIDE_ROOT
    return outcome, None


def _mission_activity(read_dir: Path) -> str | None:
    try:
        snapshot = materialize_snapshot(read_dir)
    except _UNREADABLE:  # UnicodeDecodeError is a ValueError: the Mission still counts and adds no activity
        return None
    return last_activity_of(state.get("last_transition_at") for state in snapshot.work_packages.values())


def build_project(repo_root: Path, memo: ResolverMemo, *, leak: ModuleType) -> ProjectOutcome:
    """Build the ``Project`` payload of ``repo_root``; every Mission is read through the memo, never through the v1 loader."""
    activity: list[str | None] = []
    fallbacks: dict[str, str] = {}
    names = enumerate_missions(repo_root)
    for name in names:
        read_dir, reason = read_dir_of(repo_root, name, memo_resolve(memo, repo_root, name))
        if reason is not None:
            fallbacks[name] = reason
        activity.append(_mission_activity(read_dir))
    schema_value = schema_version_of(repo_root)
    body = {
        "name": read_project_name(repo_root),
        "missionCount": len(names),
        "specKittyVersion": project_version(repo_root),
        "schemaVersion": schema_value,
        "health": health_of(schema_value),
        "currentBranch": current_branch_of(repo_root, leak),
        "lastActivityAt": last_activity_of(activity),
    }
    return ProjectOutcome(body=body, fallbacks=fallbacks)
