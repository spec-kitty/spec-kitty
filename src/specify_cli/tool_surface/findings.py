"""Stable finding codes and the reporting-layer ``SurfaceFinding`` type.

Finding codes are the **public JSON wire API** of ``doctor tool-surfaces
--json``. They are kebab-case strings and are immutable once published: a code
that has appeared in any released version cannot be renamed or removed without a
deprecation cycle. The Python module constants below use ``SCREAMING_SNAKE``
names purely as ergonomic intermediates -- their string *values* are kebab-case
and only those values are ever emitted in JSON.

This module deliberately defines its own :class:`SurfaceFinding` (distinct from
the plan-layer ``tool_surface.model.SurfaceFinding``) so the reporting surface
matches ``contracts/doctor-tool-surfaces-output.schema.json`` exactly without
disturbing the policy/plan dataclasses established in WP01.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

# Severity values (stable JSON wire strings). Research gaps use ``info``.
SEVERITY_ERROR = "error"
SEVERITY_WARNING = "warning"
SEVERITY_INFO = "info"

# --- Command skills / command files -----------------------------------------
GENERATED_SURFACE_MISSING = "generated-surface-missing"
MANAGED_FILE_DRIFT = "managed-file-drift"
MANAGED_FILE_MODIFIED = "managed-file-modified"
STALE_GENERATED_SURFACE = "stale-generated-surface"
UNSAFE_MANAGED_PATH = "unsafe-managed-path"
UNMANAGED_SPEC_KITTY_SURFACE = "unmanaged-spec-kitty-surface"
CONFIGURED_TOOL_SURFACE_UNINSTALLED = "configured-tool-surface-uninstalled"

# --- Session presence / context files (placeholders, populated in WP04) -----
CONTEXT_FILE_MISSING = "context-file-missing"
SESSION_PRESENCE_INCOMPLETE = "session-presence-incomplete"
NATIVE_CONFIG_MISSING = "native-config-missing"
NATIVE_CONFIG_DRIFT = "native-config-drift"
# .claude/settings.json bytes cannot be provably decoded (#4940, D6): the
# probe reports this truthfully instead of raising SettingsNotDecodableError.
SESSION_PRESENCE_UNDECODABLE = "session-presence-undecodable"

# --- Agent profiles (placeholders, populated in WP06) -----------------------
NATIVE_AGENT_PROFILE_MISSING = "native-agent-profile-missing"
NATIVE_AGENT_PROFILE_DRIFT = "native-agent-profile-drift"
PROFILE_PROJECTION_UNSUPPORTED = "profile-projection-unsupported"
RESEARCH_GAP_SURFACE = "research-gap-surface"

# --- Agent-profile projection diagnostics (#1940) ---------------------------
# Append-only: these four codes extend the agent-profile vocabulary; the three
# codes above are stable and MUST NOT be renamed. Values match
# ``contracts/profile-findings-and-manifest.md`` verbatim.
PROFILE_SOURCE_INVALID = "profile-source-invalid"
PROFILE_NAME_INVALID = "profile-name-invalid"
PROFILE_OVERLAY_CONFLICT = "profile-overlay-conflict"
PROFILE_SENTINEL_SKIPPED = "profile-sentinel-skipped"

# --- Plugin bundles (placeholders, populated in WP09) -----------------------
BUNDLE_COMPONENT_MISSING = "bundle-component-missing"
PLUGIN_MANIFEST_STALE_PATH = "plugin-manifest-stale-path"

# --- Docs (placeholder, populated in WP08) ----------------------------------
DOCS_REF_STALE = "docs-ref-stale"


@dataclass(frozen=True)
class SurfaceFinding:
    """A diagnostic produced while probing or validating a surface.

    Mirrors ``SurfaceFinding`` in ``doctor-tool-surfaces-output.schema.json``.
    """

    code: str
    severity: str
    message: str
    tool_key: str | None = None
    surface_id: str | None = None
    path: Path | None = None
    repair_command: str | None = None
    docs_ref: str | None = None
    details: Mapping[str, object] = field(default_factory=dict)

    def to_json(self) -> dict[str, object]:
        """Serialize to the schema-conformant JSON shape."""
        return {
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
            "tool_key": self.tool_key,
            "surface_id": self.surface_id,
            "path": str(self.path) if self.path is not None else None,
            "repair_command": self.repair_command,
            "docs_ref": self.docs_ref,
            "details": dict(self.details),
        }


def make_finding(
    code: str,
    severity: str,
    message: str,
    *,
    tool_key: str | None = None,
    surface_id: str | None = None,
    path: Path | None = None,
    repair_command: str | None = None,
    docs_ref: str | None = None,
    details: Mapping[str, object] | None = None,
) -> SurfaceFinding:
    """Build a :class:`SurfaceFinding`.

    ``code`` must be a kebab-case string from the stable code table (use the
    module constants above). ``severity`` must be one of ``error``,
    ``warning``, or ``info`` -- never ``research_gap`` (research gaps are
    ``info``).
    """
    return SurfaceFinding(
        code=code,
        severity=severity,
        message=message,
        tool_key=tool_key,
        surface_id=surface_id,
        path=path,
        repair_command=repair_command,
        docs_ref=docs_ref,
        details=dict(details) if details else {},
    )
