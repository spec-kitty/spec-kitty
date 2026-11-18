"""Checkpoint/resume mechanism for cross-session conflict resolution (WP07).

This module implements event-sourced checkpoint/resume that enables:
1. Persisting minimal state before the generation gate blocks
2. Verifying input hash on resume to detect context changes
3. Restoring execution from the checkpoint cursor

Architecture:
- StepCheckpoint: Frozen dataclass with mission/run/step IDs, strictness,
  scope refs, input hash, cursor, retry token
- compute_input_hash(): Deterministic SHA256 of sorted JSON inputs
- verify_input_hash(): Compare checkpoint vs current context
- handle_context_change(): Prompt user if hash differs
- load_checkpoint(): Retrieve latest checkpoint from event log
- parse_checkpoint_event(): Reconstruct StepCheckpoint from event payload
"""

from __future__ import annotations

import hashlib
import json
import logging
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from glossary.scope import GlossaryScope
from glossary.strictness import Strictness
from kernel.clock import datetime, now_utc, parse_iso

logger = logging.getLogger(__name__)

# Valid cursor values representing execution stages
VALID_CURSORS = frozenset({"pre_generation_gate", "post_clarification", "post_gate"})


@dataclass(frozen=True)
class ScopeRef:
    """Reference to a specific glossary scope version."""

    scope: GlossaryScope
    version_id: str  # e.g., "v3", "2026-02-16-001"


@dataclass(frozen=True)
class StepCheckpoint:
    """Minimal state for resuming step execution after conflict resolution.

    All fields are immutable (frozen dataclass). The input_hash is a SHA256
    digest that allows detecting if the execution context has changed since
    the checkpoint was created. The retry_token is a UUID for idempotency.
    """

    mission_id: str
    run_id: str
    step_id: str
    strictness: Strictness
    scope_refs: tuple[ScopeRef, ...]  # tuple for immutability
    input_hash: str  # SHA256 hex digest (64 chars)
    cursor: str  # Execution stage (e.g., "pre_generation_gate")
    retry_token: str  # UUID v4 string (36 chars)
    timestamp: datetime

    def __post_init__(self) -> None:
        """Validate checkpoint fields."""
        # Validate hash format (64 hex chars for SHA256)
        if len(self.input_hash) != 64 or not all(c in "0123456789abcdef" for c in self.input_hash):
            raise ValueError(f"Invalid input_hash format: {self.input_hash}")

        # Validate retry token is UUID format (36 chars with hyphens)
        if len(self.retry_token) != 36:
            raise ValueError(f"Invalid retry_token format: {self.retry_token}")

        # Validate cursor is known stage
        if self.cursor not in VALID_CURSORS:
            raise ValueError(f"Unknown cursor value: {self.cursor}")


def compute_input_hash(inputs: dict[str, Any]) -> str:
    """Compute deterministic SHA256 hash of step inputs.

    Uses json.dumps with sort_keys=True for deterministic serialization.
    The same inputs always produce the same hash regardless of insertion order.

    Args:
        inputs: Step input dictionary (any JSON-serializable structure)

    Returns:
        64-character lowercase hex string (SHA256 hash)
    """
    canonical = json.dumps(inputs, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()  # noqa: TID251 - production raw SHA-256 owner


def create_checkpoint(
    mission_id: str,
    run_id: str,
    step_id: str,
    strictness: Strictness,
    scope_refs: list[ScopeRef],
    inputs: dict[str, Any],
    cursor: str,
) -> StepCheckpoint:
    """Create a new checkpoint with computed input hash and fresh retry token.

    Args:
        mission_id: Mission identifier
        run_id: Run instance identifier
        step_id: Step identifier
        strictness: Resolved strictness mode
        scope_refs: Active glossary scope versions
        inputs: Step input dictionary (hashed for context verification)
        cursor: Execution stage (e.g., "pre_generation_gate")

    Returns:
        StepCheckpoint instance ready for event emission
    """
    return StepCheckpoint(
        mission_id=mission_id,
        run_id=run_id,
        step_id=step_id,
        strictness=strictness,
        scope_refs=tuple(scope_refs),
        input_hash=compute_input_hash(inputs),
        cursor=cursor,
        retry_token=str(uuid.uuid4()),
        timestamp=now_utc(),
    )


# ---------------------------------------------------------------------------
# T032: Checkpoint loading from event log
# ---------------------------------------------------------------------------


def load_checkpoint(
    project_root: Path,
    step_id: str,
    mission_id: str | None = None,
    retry_token: str | None = None,
) -> StepCheckpoint | None:
    """Load latest checkpoint for step_id from event log.

    Reads StepCheckpointed events from event log and returns the most recent
    checkpoint for the given step_id. With a ``mission_id`` only that mission's
    own log is read; on a miss there (or without a ``mission_id``) every
    mission event log in the glossary events directory is scanned, which also
    covers logs written under a legacy filename.

    Args:
        project_root: Repository root (contains .kittify/events/)
        step_id: Step identifier to load checkpoint for
        mission_id: Optional mission identifier filter (recommended)
        retry_token: Optional retry token filter (exact-match resume)

    Returns:
        Latest StepCheckpoint for step_id, or None if not found
    """
    from .events import EVENT_LOG_SUFFIX, sanitize_mission_id

    events_dir = project_root / ".kittify" / "events" / "glossary"
    if not events_dir.exists():
        logger.info("No glossary events directory for step=%s", step_id)
        return None

    latest: StepCheckpoint | None = None
    own_log: Path | None = None
    if isinstance(mission_id, str):
        # The writer names a mission's log through the same sanitizer
        # (``events.get_event_log_path``, which is not called here because it
        # creates directories), so the mission's checkpoints live in one file.
        own_log = events_dir / f"{sanitize_mission_id(mission_id)}{EVENT_LOG_SUFFIX}"
        if own_log.is_file():
            latest = _latest_checkpoint_in(own_log, step_id, mission_id, retry_token)

    if latest is None:
        # No mission filter, or a miss in the mission's own log: scan every log,
        # which covers logs written under a legacy filename.
        for event_log_path in sorted(events_dir.glob(f"*{EVENT_LOG_SUFFIX}")):
            if event_log_path == own_log:
                continue
            found = _latest_checkpoint_in(event_log_path, step_id, mission_id, retry_token)
            if found is not None and (latest is None or found.timestamp > latest.timestamp):
                latest = found

    if latest is not None:
        logger.info(
            "Loaded checkpoint for step=%s mission=%s cursor=%s",
            step_id,
            mission_id or "*",
            latest.cursor,
        )
    else:
        logger.info(
            "No checkpoint found for step=%s mission=%s retry_token=%s",
            step_id,
            mission_id or "*",
            "set" if retry_token else "unset",
        )

    return latest


def _latest_checkpoint_in(
    event_log_path: Path,
    step_id: str,
    mission_id: str | None,
    retry_token: str | None,
) -> StepCheckpoint | None:
    """Return the latest matching checkpoint in one event log, or None."""
    from .events import read_events

    latest: StepCheckpoint | None = None
    for event_payload in read_events(event_log_path, event_type="StepCheckpointed"):
        if event_payload.get("step_id") != step_id:
            continue
        if mission_id is not None and event_payload.get("mission_id") != mission_id:
            continue
        if retry_token is not None and event_payload.get("retry_token") != retry_token:
            continue

        try:
            checkpoint = parse_checkpoint_event(event_payload)
        except ValueError as exc:
            logger.warning("Invalid checkpoint event in %s: %s", event_log_path.name, exc)
            continue

        if latest is None or checkpoint.timestamp > latest.timestamp:
            latest = checkpoint
    return latest


def parse_checkpoint_event(
    event_payload: dict[str, Any],
) -> StepCheckpoint:
    """Parse StepCheckpointed event payload into StepCheckpoint instance.

    Args:
        event_payload: Event dictionary from event log

    Returns:
        Parsed StepCheckpoint instance

    Raises:
        ValueError: If payload is missing required fields or has invalid format
    """
    try:
        return StepCheckpoint(
            mission_id=event_payload["mission_id"],
            run_id=event_payload["run_id"],
            step_id=event_payload["step_id"],
            strictness=Strictness(event_payload["strictness"]),
            scope_refs=tuple(
                ScopeRef(
                    scope=GlossaryScope(ref["scope"]),
                    version_id=ref["version_id"],
                )
                for ref in event_payload.get("scope_refs", [])
            ),
            input_hash=event_payload["input_hash"],
            cursor=event_payload["cursor"],
            retry_token=event_payload["retry_token"],
            timestamp=parse_iso(event_payload["timestamp"]),
        )
    except (KeyError, ValueError) as e:
        raise ValueError(f"Invalid checkpoint event payload: {e}") from e


def checkpoint_to_dict(checkpoint: StepCheckpoint) -> dict[str, Any]:
    """Serialize StepCheckpoint to dict for event emission.

    Args:
        checkpoint: Checkpoint to serialize

    Returns:
        JSON-serializable dictionary
    """
    return {
        "mission_id": checkpoint.mission_id,
        "run_id": checkpoint.run_id,
        "step_id": checkpoint.step_id,
        "strictness": checkpoint.strictness.value,
        "scope_refs": [{"scope": ref.scope.value, "version_id": ref.version_id} for ref in checkpoint.scope_refs],
        "input_hash": checkpoint.input_hash,
        "cursor": checkpoint.cursor,
        "retry_token": checkpoint.retry_token,
        "timestamp": checkpoint.timestamp.isoformat(),
    }


# ---------------------------------------------------------------------------
# T033: Input hash verification
# ---------------------------------------------------------------------------


def verify_input_hash(
    checkpoint: StepCheckpoint,
    current_inputs: dict[str, Any],
) -> tuple[bool, str, str]:
    """Verify current inputs match checkpoint context.

    Args:
        checkpoint: Checkpoint with original input_hash
        current_inputs: Current step inputs

    Returns:
        Tuple of (matches, old_hash_display, new_hash_display):
        - matches: True if hashes match, False if context changed
        - old_hash_display: Original hash from checkpoint (first 16 chars)
        - new_hash_display: Current hash (first 16 chars)
    """
    current_hash = compute_input_hash(current_inputs)
    matches = current_hash == checkpoint.input_hash

    return (matches, checkpoint.input_hash[:16], current_hash[:16])


def handle_context_change(
    checkpoint: StepCheckpoint,
    current_inputs: dict[str, Any],
    confirm_fn: Any = None,
) -> bool:
    """Handle input context change between checkpoint and resume.

    Computes current input hash and prompts user for confirmation if
    context has changed materially (per spec.md FR-019).

    Args:
        checkpoint: Checkpoint with original input_hash
        current_inputs: Current step inputs
        confirm_fn: Optional confirmation function override (for testing).
                    Signature: (old_hash: str, new_hash: str) -> bool.
                    Defaults to prompt_context_change_confirmation.

    Returns:
        True if context unchanged or user confirms resumption,
        False if user declines (abort resume)
    """
    matches, old_hash, new_hash = verify_input_hash(checkpoint, current_inputs)

    if matches:
        # Context unchanged, safe to resume
        return True

    # Context changed - prompt user for confirmation
    if confirm_fn is not None:
        result: bool = confirm_fn(old_hash, new_hash)
        return result

    return prompt_context_change_confirmation(old_hash, new_hash)


def prompt_context_change_confirmation(
    old_hash: str,
    new_hash: str,
) -> bool:
    """Prompt user for confirmation when context has changed.

    This is the default confirmation prompt. WP06 may provide a richer
    implementation via glossary/prompts.py; when available, pass it as
    confirm_fn to handle_context_change().

    Args:
        old_hash: Truncated hash from checkpoint (display only)
        new_hash: Truncated hash from current inputs (display only)

    Returns:
        True if user confirms resumption, False if user declines
    """
    import typer

    typer.echo(f"\nContext has changed since checkpoint was created.\n  Checkpoint hash: {old_hash}...\n  Current hash:    {new_hash}...\n")
    result: bool = typer.confirm(
        "Resume despite context change?",
        default=False,
    )
    return result


def compute_input_diff(
    old_inputs: dict[str, Any],
    new_inputs: dict[str, Any],
) -> dict[str, tuple[Any, Any]]:
    """Compute detailed diff between old and new inputs.

    Useful for debugging context changes -- shows which keys changed,
    were added, or were removed.

    Args:
        old_inputs: Original inputs from checkpoint
        new_inputs: Current inputs

    Returns:
        Dict mapping changed keys to (old_value, new_value) tuples.
        Removed keys have new_value=None; added keys have old_value=None.
    """
    diff: dict[str, tuple[Any, Any]] = {}

    # Find changed/removed keys
    for key in old_inputs:
        old_val = old_inputs[key]
        new_val = new_inputs.get(key)

        if new_val != old_val:
            diff[key] = (old_val, new_val)

    # Find added keys
    for key in new_inputs:
        if key not in old_inputs:
            diff[key] = (None, new_inputs[key])

    return diff
