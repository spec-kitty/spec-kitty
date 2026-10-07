"""Host-local provenance, crash marker, and cooperative design locking.

Receipts are written AFTER the artifact commit. This is not a journal transaction.
An enabled marker outlives a missing/corrupt receipt and makes finalization refuse
instead of accidentally falling back to the legacy manual-authoring path.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from kernel.git_topology import git_common_dir
from kernel.content_digest import sha256_digest
from kernel.locks import LockAcquireTimeout, machine_file_lock
from pydantic import ValidationError

from specify_cli.core.atomic import atomic_write
from specify_cli.core.checkout_file_lock import LOCK_DIRECTORY
from specify_cli.design.errors import DesignError
from specify_cli.design.models import ABSENT, MAX_ARTIFACT_BYTES, ReceiptSet


def read_bounded(path: Path) -> bytes:
    """Read at most ``MAX_ARTIFACT_BYTES``; an oversize file is a refusal, never a full read."""
    with path.open("rb") as handle:
        body = handle.read(MAX_ARTIFACT_BYTES + 1)
    if len(body) > MAX_ARTIFACT_BYTES:
        raise DesignError("DESIGN_BOUNDS_EXCEEDED", "Artifact content exceeds the inline read bound")
    return body


def content_digest(path: Path) -> str:
    """Return exact-byte revision, or the explicit first-submission sentinel."""
    return sha256_digest(read_bounded(path)).removeprefix("sha256:") if path.exists() else ABSENT


def _paths(repo_root: Path, mission_slug: str) -> tuple[Path, Path]:
    key = sha256_digest(mission_slug.encode("utf-8")).removeprefix("sha256:")
    base = git_common_dir(repo_root) / "spec-kitty-design" / key
    return base.with_suffix(".enabled"), base.with_suffix(".json")


def read_receipts(repo_root: Path, mission_slug: str) -> ReceiptSet | None:
    """Legacy missions have no marker; enabled missions must have valid receipts."""
    marker, path = _paths(repo_root, mission_slug)
    if not marker.exists():
        return None
    try:
        return ReceiptSet.model_validate_json(path.read_bytes())
    except (OSError, ValidationError) as exc:
        raise DesignError("DESIGN_RECEIPT_UNREADABLE", "API authoring provenance requires reconciliation") from exc


def api_authoring_enabled(repo_root: Path, mission_slug: str) -> bool:
    """The persistent marker remains enabled even if receipts become unreadable."""
    marker, _ = _paths(repo_root, mission_slug)
    return marker.exists()


def enable_authoring(repo_root: Path, mission_slug: str, receipts: ReceiptSet) -> None:
    """Set crash protection before content effects, without resetting old lineage."""
    marker, path = _paths(repo_root, mission_slug)
    if marker.exists():
        return
    atomic_write(marker, "enabled\n", mkdir=True)
    atomic_write(path, receipts.model_dump_json(), mkdir=True)


def save_receipts(repo_root: Path, mission_slug: str, receipts: ReceiptSet) -> None:
    """Persist post-commit lineage; failure remains protected by the marker."""
    _, path = _paths(repo_root, mission_slug)
    try:
        atomic_write(path, receipts.model_dump_json(), mkdir=True)
    except OSError as exc:
        raise DesignError(
            "DESIGN_RECEIPT_UNREADABLE",
            "Content committed but provenance requires reconciliation",
            {"effect_state": "reconciliation_required"},
        ) from exc


@contextmanager
def authoring_lock(repo_root: Path, mission_slug: str) -> Iterator[None]:
    """Serialize cooperative API writers, including their finalization boundary."""
    key = sha256_digest(mission_slug.encode("utf-8")).removeprefix("sha256:")
    path = git_common_dir(repo_root) / LOCK_DIRECTORY / f"design-{key}.lock"
    try:
        with machine_file_lock(path, blocking=True, timeout_s=10.0, reentrant=True):
            yield
    except LockAcquireTimeout as exc:
        raise DesignError("DESIGN_LOCK_TIMEOUT", "The mission authoring lock is busy") from exc
