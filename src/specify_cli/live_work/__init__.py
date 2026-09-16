"""live_work — Live Work harness capture (spec-kitty#4268).

Publishes supported harness activity (tools, files, tests, delegation) and
lifecycle continuity as **live relay frames** through the existing
``event.publish`` path. Re-scoped 2026-09-14 (planning#2269,
``decisions/HIC-ZEITGEIST-NOW-GIT-DONE-2026-09-14.md``): Zeitgeist carries
NOW, Git carries DONE — there is no local journal, spool, or durable offset
anywhere in this package, and the bounded wake-up retry is #4311's shared
mechanism, never a second loop here.

Public API:

* :class:`Observation` and friends — the canonical capture record.
* :data:`EMITTED_KINDS` / :func:`payload_id` — the closed emission surface.
* :func:`get_adapter` — the canonical hook-adapter API (Claude Code, Codex).
* :class:`CapabilityMatrix` — the executable per-harness capability matrix.
* :func:`publish_observations` — one bounded ``event.publish`` offer per
  observation through the existing client.
* :func:`watch_changed_files` — the labeled changed-file fallback.
* :func:`install_hooks` / :func:`uninstall_hooks` — harness hook registration.
* :mod:`authored` — #4269's CLI/MCP authored publish, reply and bounded
  conversation retrieval over the same relay path (imported directly, not
  re-exported here: it drags ``spec_kitty_events.models`` and ``ulid``,
  which the hook fast path this package's other consumers ride must not pay).
"""

from __future__ import annotations

from .adapters import HARNESSES_WITH_ADAPTERS, HookAdapter, get_adapter
from .bindings import ResolvedBindings, resolve_bindings
from .capability import CapabilityMatrix, CapabilityRow, CapabilityStatus, matrix_for_harness
from .codec import codec_state, validate_typed
from .coalesce import BURST_WINDOW_S, BurstCoalescer, CoalescedEdit
from .install import InstallOutcome, install_hooks, uninstall_hooks
from .kinds import EMISSION_FAMILIES, EMITTED_KINDS, WorkEmissionKind, payload_id
from .models import (
    ActivityBinding,
    ActorBinding,
    CoverageDetail,
    FileDetail,
    FileOperation,
    MissionBinding,
    Observation,
    ObservationAction,
    Provenance,
    RepositoryBinding,
    SessionBinding,
    TestRunDetail,
    ToolDetail,
    ToolOutcome,
    ToolState,
    UnknownActor,
)
from .publisher import (
    PublishReport,
    project_args,
    publish_observation,
    publish_observations,
)
from .redaction import (
    EXCLUDED_FILE_PATTERNS,
    REDACTED,
    RedactionResult,
    redact_command_summary,
    relativize_path,
)
from .watcher import watch_changed_files

__all__ = [
    "BURST_WINDOW_S",
    "EMISSION_FAMILIES",
    "EMITTED_KINDS",
    "EXCLUDED_FILE_PATTERNS",
    "HARNESSES_WITH_ADAPTERS",
    "ActivityBinding",
    "ActorBinding",
    "BurstCoalescer",
    "CapabilityMatrix",
    "CapabilityRow",
    "CapabilityStatus",
    "CoalescedEdit",
    "CoverageDetail",
    "FileDetail",
    "FileOperation",
    "HookAdapter",
    "InstallOutcome",
    "MissionBinding",
    "Observation",
    "ObservationAction",
    "Provenance",
    "PublishReport",
    "REDACTED",
    "RedactionResult",
    "RepositoryBinding",
    "ResolvedBindings",
    "SessionBinding",
    "TestRunDetail",
    "ToolDetail",
    "ToolOutcome",
    "ToolState",
    "UnknownActor",
    "WorkEmissionKind",
    "codec_state",
    "get_adapter",
    "install_hooks",
    "matrix_for_harness",
    "payload_id",
    "project_args",
    "publish_observation",
    "publish_observations",
    "redact_command_summary",
    "relativize_path",
    "resolve_bindings",
    "uninstall_hooks",
    "validate_typed",
    "watch_changed_files",
]
