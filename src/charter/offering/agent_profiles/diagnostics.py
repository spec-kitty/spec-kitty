"""Structured diagnostics for skipped agent-profile files.

When the :class:`~charter.offering.agent_profiles.repository.AgentProfileRepository`
loads profile YAML from the built-in, org, or project layers, a file may be
unloadable (invalid YAML, schema/validation failure, missing ``profile-id``,
inline-reference rejection, OS error). Such files are *skipped* rather than
crashing the whole load, but the skip must remain observable (FR-005/006/007).

Each skipped file is recorded as an immutable :class:`SkippedProfile` so callers
can surface deterministic, layer-attributed diagnostics without re-scanning the
filesystem.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["SkippedProfile"]


@dataclass(frozen=True)
class SkippedProfile:
    """A single agent-profile file that was skipped during repository load.

    Attributes:
        layer: The Charter Pack layer the file belongs to — one of ``"builtin"``,
            ``"org"``, or ``"project"``.
        path: Absolute or repository-relative path of the skipped file, as a
            string (stable across processes for deterministic comparison).
        profile_id: The declared ``profile-id`` if it could be parsed, else
            ``None`` (e.g. unparsable YAML or a missing id field).
        error_summary: Human-readable reason the file was skipped.
    """

    layer: str
    path: str
    profile_id: str | None
    error_summary: str
