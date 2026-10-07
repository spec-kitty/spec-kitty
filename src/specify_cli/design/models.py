"""Closed, bounded requests and host-owned content provenance."""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

MAX_ARTIFACT_BYTES = 256 * 1024
MAX_BATCH_BYTES = 1024 * 1024
MAX_REQUEST_BYTES = 2 * MAX_BATCH_BYTES
MAX_ACTOR_BYTES = 256
MAX_ARTIFACTS = 64
ABSENT = "absent"
Digest = Annotated[str, Field(pattern=r"^(absent|[a-f0-9]{64})$")]


class ArtifactInput(BaseModel):
    """Authored content, never a caller-selected destination or status."""

    model_config = ConfigDict(extra="forbid", strict=True)
    kind: str
    artifact_id: str | None = None
    content: str
    expected_sha256: Digest


class Submission(BaseModel):
    """One cooperative, revision-conditioned batch."""

    model_config = ConfigDict(extra="forbid", strict=True)
    artifacts: Annotated[list[ArtifactInput], Field(min_length=1, max_length=MAX_ARTIFACTS)]
    parents: dict[str, Digest] = Field(default_factory=dict)
    context_sha256: Digest


class Receipt(BaseModel):
    """Accepted content lineage; not a mission phase or execution authority."""

    model_config = ConfigDict(extra="forbid", strict=True)
    kind: str
    artifact_id: str | None
    sha256: Digest
    parents: dict[str, Digest]
    context_sha256: Digest
    context_action: str
    actor: str


class ReceiptSet(BaseModel):
    """Host-local, nonportable provenance for API-authored planning content."""

    model_config = ConfigDict(extra="forbid", strict=True)
    artifacts: dict[str, Receipt] = Field(default_factory=dict)
