"""Provenance sidecar writer (T034, T035).

Writes a YAML provenance sidecar for every applied proposal.

Canonical sidecar path (idempotency key):
    <artifact_dir>/.provenance/<artifact_id>.yaml

This path scheme is deterministic: given (artifact_path, artifact_id) the
sidecar location is always the same, enabling the idempotency check in T035.

Minimum field set required by FR-022 / synthesizer_hook.md:
    artifact_id
    source: retrospective
    source_mission_id
    source_proposal_id
    source_evidence_event_ids
    applied_by: {kind, id, profile_id}
    applied_at
    re_applied
"""

from __future__ import annotations

import hashlib
from pathlib import Path
import re
from typing import Any

from ruamel.yaml import YAML

from kernel.clock import now_utc_iso
from specify_cli.retrospective.schema import ActorRef, Proposal

# ---------------------------------------------------------------------------
# Canonical path helper
# ---------------------------------------------------------------------------

_PROVENANCE_SUBDIR = ".provenance"
_SAFE_PATH_COMPONENT_RE = re.compile(r"[^A-Za-z0-9._-]+")


def _safe_path_component(value: str) -> str:
    """Return a deterministic, traversal-safe filename stem for an artifact id."""
    cleaned = _SAFE_PATH_COMPONENT_RE.sub("_", value).strip("._")
    while ".." in cleaned:
        cleaned = cleaned.replace("..", "__")
    if not cleaned:
        cleaned = "artifact"
    if cleaned != value or len(cleaned) > 128:
        digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]  # noqa: TID251 - production raw SHA-256 owner
        cleaned = f"{cleaned[:115]}-{digest}"
    return cleaned


def provenance_path(artifact_path: Path, artifact_id: str) -> Path:
    """Return the canonical provenance sidecar path for *artifact_id*.

    The sidecar lives in a ``.provenance/`` sub-directory of the artifact's
    parent directory.  ``artifact_id`` is preserved in the YAML body, but the
    filename is sanitized because DRG node ids and target URNs can contain
    path separators, colons, or other characters that are valid identifiers
    but unsafe as path components.

    Args:
        artifact_path: The path to the primary artifact on disk.
        artifact_id: A stable id for the artifact (e.g. term key, edge id).

    Returns:
        Absolute path to the ``.provenance/<artifact_id>.yaml`` sidecar.
    """
    return artifact_path.parent / _PROVENANCE_SUBDIR / f"{_safe_path_component(artifact_id)}.yaml"


# ---------------------------------------------------------------------------
# Sidecar reader (idempotency check)
# ---------------------------------------------------------------------------


def load_provenance(sidecar_path: Path) -> dict[str, Any] | None:
    """Load an existing provenance sidecar, or return None if absent.

    Does not raise on missing file (used by idempotency check).

    Args:
        sidecar_path: Path returned by :func:`provenance_path`.

    Returns:
        The parsed YAML dict, or ``None`` if the file does not exist.
    """
    if not sidecar_path.exists():
        return None
    yaml = YAML()
    yaml.preserve_quotes = True
    with sidecar_path.open("r", encoding="utf-8") as fh:
        result = yaml.load(fh)
        return dict(result) if isinstance(result, dict) else {}


def is_already_applied(
    sidecar_path: Path,
    source_mission_id: str,
    proposal_id: str,
) -> bool:
    """Return True if a sidecar exists for (source_mission_id, proposal_id).

    Implements the idempotency key check from T035.  A sidecar is treated as
    "already applied" only when *both* fields match — so re-applying the same
    proposal from a different mission source is treated as a fresh apply.

    Args:
        sidecar_path: Path returned by :func:`provenance_path`.
        source_mission_id: Canonical mission ULID of the source retrospective.
        proposal_id: ULID of the proposal.

    Returns:
        ``True`` if an existing sidecar carries the matching identity fields.
    """
    data = load_provenance(sidecar_path)
    if data is None:
        return False
    return data.get("source_mission_id") == source_mission_id and data.get("source_proposal_id") == proposal_id


# ---------------------------------------------------------------------------
# write_provenance
# ---------------------------------------------------------------------------


def write_provenance(
    *,
    artifact_path: Path,
    artifact_id: str,
    proposal: Proposal,
    actor: ActorRef,
    re_applied: bool = False,
) -> Path:
    """Write a provenance sidecar for an applied proposal.

    The sidecar is placed at the deterministic path
    ``<artifact_path.parent>/.provenance/<artifact_id>.yaml`` so it is
    co-located with the artifact it describes.

    FR-022 / synthesizer_hook.md minimum fields:
        artifact_id, source, source_mission_id, source_proposal_id,
        source_evidence_event_ids, applied_by, applied_at, re_applied.

    Args:
        artifact_path: Path to the primary artifact.  The sidecar is placed
            in the ``.provenance/`` sub-directory of this file's parent.
        artifact_id: Stable identifier for the artifact (term key, edge id…).
        proposal: The :class:`~specify_cli.retrospective.schema.Proposal` that
            was applied.
        actor: The :class:`~specify_cli.retrospective.schema.ActorRef` who
            authorized the synthesis run.
        re_applied: ``True`` when a sidecar already existed and this is a
            no-op idempotent re-run.

    Returns:
        The absolute path of the written sidecar.
    """
    sidecar = provenance_path(artifact_path, artifact_id)
    sidecar.parent.mkdir(parents=True, exist_ok=True)

    record: dict[str, Any] = {
        "artifact_id": artifact_id,
        "source": "retrospective",
        "source_mission_id": proposal.provenance.source_mission_id,
        "source_proposal_id": proposal.id,
        "source_evidence_event_ids": list(proposal.provenance.source_evidence_event_ids),
        "applied_by": {
            "kind": actor.kind,
            "id": actor.id,
            "profile_id": actor.profile_id,
        },
        "applied_at": now_utc_iso(),
        "re_applied": re_applied,
    }

    yaml = YAML()
    yaml.default_flow_style = False
    with sidecar.open("w", encoding="utf-8") as fh:
        yaml.dump(record, fh)

    return sidecar
