"""Canonical JSON response envelope and policy metadata for orchestrator-api.

Responsibilities:
- Build a consistent envelope for all orchestrator-api command outputs.
- Parse and validate the --policy JSON required on run-affecting commands.
- Define banned flag constants used by the CI guardrail scan.
"""

from __future__ import annotations

import dataclasses
import re
import uuid
from dataclasses import dataclass
from typing import Any

from kernel.clock import now_utc_iso

# 1.1.0: start-implementation now allocates the real lane worktree and its
# response carries lane_id / lane_branch / lane_base_ref; workspace_path now
# means that lane worktree (previously a bare legacy path). Additive + a
# bugfixed field meaning → minor bump.
# 1.2.0: added read-only ``resolve-workspace`` (#2337) — resolves a WP's lane
# workspace_path / prompt_path / lane_branch WITHOUT allocating or transitioning,
# so an external orchestrator can resume a for_review WP. Purely additive.
# 1.3.0: ``transition`` accepts structured ``--review-result-json`` so normal
# in_review exits satisfy host guards without using the recovery-only force flag.
# 1.4.0: added 11 new verbs -- design-phase scaffolding (``specify``, ``plan``,
# ``tasks``, ``check-prerequisites``, ``record-analysis``); decision-resolution
# (``open-decision``, ``resolve-decision``, ``defer-decision``,
# ``cancel-decision``, ``answer-decision``); plus the read-only ``design-status``
# query verb. Purely additive.
# 1.5.0: the ``tasks`` verb's pass-through data gained the ``planning_commit``
# object (action / previous_sha / branch_tip / resolved sha) from the delegate
# finalize-tasks ``--json`` payload (#4141 -- the --refresh-planning-commit
# re-point affordance). Purely additive.
# 1.6.0: the ``planning_commit.action`` vocabulary gains ``"repinned"`` --
# finalize-tasks's new ``--refresh-planning-commit --allow-orphaned`` re-pins
# an ORPHANED (mid-mission-rebase) recorded SHA to the target-branch tip
# (#4827). Purely additive; no consumer contract test pins the action
# vocabulary (contracts/finalize-repin-contract.md).
# 1.7.0: ``accept-mission`` now APPLIES the host readiness verdict (#4934) --
# it calls ``collect_feature_summary(..., strict_metadata=True)`` and refuses
# with ``MISSION_NOT_READY`` (carrying ``outstanding`` / ``activity_issues`` /
# ``skipped_checks`` / ``blocked_checks``, plus mission identity) whenever
# ``summary.ok`` is False, and records acceptance only through the same
# FR-010 locked pre-stamp verdict guard the host ``accept`` CLI uses.
# Behavioural tightening (a previously-accepting call can now refuse), so a
# minor bump rather than additive-only; no field is removed or renamed.
# 1.8.0: the ``tasks`` verb's pass-through ``data`` gains three keys --
# ``parsed_spec_ids``, ``rejected_requirement_refs``, ``success_criteria_
# coverage`` -- from the delegate finalize-tasks ``--json`` payload
# (requirement-id-grammar-01M3NRCA WP02, FR-010/FR-011). The ``plan`` verb's
# pass-through ``data`` gains ``requirement_id_warnings`` and remaps every
# previously-unregistered delegate error code onto the closed
# ``PLAN_SETUP_FAILED`` envelope with ``data.reason`` naming the concrete
# failure, e.g. ``SPEC_REQUIREMENT_IDS_INVALID`` (WP05, FR-016). The remap
# also closes a latent leak: ``SPEC_FILE_MISSING``, ``TEMPLATE_CONFIGURATION_
# ERROR`` and ``PLAN_CONTEXT_UNRESOLVED`` previously passed through verbatim
# as ``error_code`` (none of the three was contract-registered); they now
# surface as ``PLAN_SETUP_FAILED`` too, with the real code in ``data.reason``.
# Additive keys plus a closed-envelope remap on ``plan``'s previously-leaking
# codes, so a minor bump rather than purely additive; no field is removed.
# 1.9.0: the ``consolidate-mission`` failure envelope's ``data`` gains
# ``teardown_error_code`` when the landing succeeded and only the cleanup after
# it refused (``COORD_MOVED_AFTER_LANDING``, #5613). The envelope ``error_code``
# stays ``PREFLIGHT_FAILED`` and ``data.errors`` is unchanged. Purely additive:
# the key is absent on every other failure.
# 1.10.0: ``consolidate-mission`` can newly refuse a mission before it merges any
# lane (#5668): a lane holding content committed after review approved it, or an
# approved work package whose approval records no usable lane head. The envelope
# ``error_code`` stays ``PREFLIGHT_FAILED`` and the failure ``data`` gains
# ``preflight_error_code`` carrying ``LANE_MOVED_AFTER_APPROVAL``,
# ``APPROVAL_STAMP_MISSING`` or ``APPROVAL_STAMP_NOT_ON_LANE``. A call that used
# to succeed can now refuse, so a minor bump; the key is absent on every other
# failure and no field is removed or renamed.
CONTRACT_VERSION = "1.10.0"
MIN_PROVIDER_VERSION = "0.1.0"

# Banned flags: enforced by parse_and_validate_policy() below (a policy whose
# dangerous_flags include any of these is rejected). The CI scan excludes this
# file from the banned-flag grep (this is the allowlist definition itself).
BANNED_FLAGS: frozenset[str] = frozenset(
    [
        "--full-auto",
        "--yolo",
        "--dangerously-bypass-approvals-and-sandbox",
        "--dangerously-skip-permissions",
    ]
)

SECRET_PATTERN = re.compile(r"(token|secret|key|password|credential)", re.IGNORECASE)

_REQUIRED_POLICY_FIELDS = (
    "orchestrator_id",
    "orchestrator_version",
    "agent_family",
    "approval_mode",
    "sandbox_mode",
    "network_mode",
    "dangerous_flags",
)

_STRING_POLICY_FIELDS = (
    "orchestrator_id",
    "orchestrator_version",
    "agent_family",
    "approval_mode",
    "sandbox_mode",
    "network_mode",
)


def _new_correlation_id() -> str:
    return "corr-" + uuid.uuid4().hex


def make_envelope(
    command: str,
    success: bool,
    data: dict[str, Any],
    error_code: str | None = None,
) -> dict[str, Any]:
    """Build a canonical JSON response envelope.

    Args:
        command: Short command name (e.g. "contract-version").
        success: Whether the operation succeeded.
        data: Payload data dict (may be empty on failure).
        error_code: Machine-readable error code string (None on success).

    Returns:
        Envelope dict with 7 required keys.
    """
    return {
        "contract_version": CONTRACT_VERSION,
        "command": f"orchestrator-api.{command}",
        "timestamp": now_utc_iso(),
        "correlation_id": _new_correlation_id(),
        "success": success,
        "error_code": error_code,
        "data": data,
    }


@dataclass
class PolicyMetadata:
    """Parsed and validated orchestrator policy metadata."""

    orchestrator_id: str
    orchestrator_version: str
    agent_family: str
    approval_mode: str
    sandbox_mode: str
    network_mode: str
    dangerous_flags: list[str]
    tool_restrictions: str | None = None


def _reject_secret_like_policy_value(field_path: str, value: Any) -> None:
    if isinstance(value, str):
        if SECRET_PATTERN.search(value):
            raise ValueError(
                f"--policy field '{field_path}' appears to contain a secret "
                f"(matched pattern: token|secret|key|password|credential). "
                f"Do not pass secrets via --policy."
            )
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _reject_secret_like_policy_value(f"{field_path}[{index}]", item)
        return
    if isinstance(value, dict):
        for key, item in value.items():
            _reject_secret_like_policy_value(f"{field_path}.{key}", item)


def parse_and_validate_policy(raw_json: str) -> PolicyMetadata:
    """Parse --policy JSON, validate structure, reject secret-like values.

    Args:
        raw_json: JSON string from the --policy CLI option.

    Returns:
        Validated PolicyMetadata dataclass.

    Raises:
        ValueError: If required fields are missing, types are wrong,
                    or secret-like values are detected.
    """
    import json

    try:
        data = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        raise ValueError(f"--policy is not valid JSON: {exc}") from exc

    if not isinstance(data, dict):
        raise ValueError("--policy must be a JSON object")

    # Validate required fields are present
    for field_name in _REQUIRED_POLICY_FIELDS:
        if field_name not in data:
            raise ValueError(f"--policy missing required field: '{field_name}'")

    for field_name in _STRING_POLICY_FIELDS:
        if not isinstance(data[field_name], str):
            raise ValueError(f"--policy.{field_name} must be a string")

    # Validate dangerous_flags is a list
    if not isinstance(data["dangerous_flags"], list):
        raise ValueError("--policy.dangerous_flags must be a JSON array")

    for flag in data["dangerous_flags"]:
        if not isinstance(flag, str):
            raise ValueError("--policy.dangerous_flags entries must be strings")
        if flag in BANNED_FLAGS:
            raise ValueError(f"--policy.dangerous_flags contains a banned flag: {flag!r}. Banned flags must never appear in orchestrator policy payloads.")

    tool_restrictions = data.get("tool_restrictions")
    if tool_restrictions is not None and not isinstance(tool_restrictions, str):
        raise ValueError("--policy.tool_restrictions must be a string or null")

    # Validate all policy values: reject secret-like strings at every depth.
    for field_name, value in data.items():
        _reject_secret_like_policy_value(field_name, value)

    return PolicyMetadata(
        orchestrator_id=data["orchestrator_id"],
        orchestrator_version=data["orchestrator_version"],
        agent_family=data["agent_family"],
        approval_mode=data["approval_mode"],
        sandbox_mode=data["sandbox_mode"],
        network_mode=data["network_mode"],
        dangerous_flags=list(data["dangerous_flags"]),
        tool_restrictions=tool_restrictions,
    )


def policy_to_dict(policy: PolicyMetadata) -> dict[str, Any]:
    """Convert PolicyMetadata to a plain dict for storage in events."""
    return dataclasses.asdict(policy)


__all__ = [
    "CONTRACT_VERSION",
    "MIN_PROVIDER_VERSION",
    # BANNED_FLAGS: demoted — referenced intra-module by parse_and_validate_policy;
    # no cross-module src/ from-import callers (WP01 harden-dead-symbol-gate-01KW0RJR).
    "make_envelope",
    # PolicyMetadata: demoted — return type used only within this module;
    # no cross-module src/ from-import callers (WP01).
    "parse_and_validate_policy",
    "policy_to_dict",
]
