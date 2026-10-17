"""Runtime-shape step-id parser and WP-iteration rule (single source).

Pure kernel primitives for the flat ``steps:`` list of a ``mission-runtime.yaml``
file. Charter and runtime layers consume these instead of keeping their own copy.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML

__all__ = ["read_runtime_shape_step_ids", "step_ids_declare_wp_iteration"]

_IMPLEMENT_STEP_ID = "implement"


def read_runtime_shape_step_ids(path: Path) -> list[str]:
    """Ordered step ids from a flat ``steps:`` list; ``[]`` if unreadable or malformed.

    Fails closed on ANY malformed entry rather than filtering it out: if even one
    ``steps`` entry is not a mapping, or lacks a non-empty ``id`` or ``title``, the
    whole file yields ``[]`` so callers never fabricate a shorter, wrong sequence.
    ``id`` + ``title`` mirror the minimum the runtime loader (``PromptStep``) requires.

    **Duplicate ids also fail closed (#6323).** A ``steps:`` list with a repeated
    ``id`` cannot be a valid action sequence (the invariant requires unique ids),
    so the whole file yields ``[]`` — routing to the governed
    ``MissionTypeEmptyActionSequenceError`` upstream — rather than emitting a
    duplicate-bearing list that ``project_action_sequence`` would reject downstream
    with a *raw* ``ValueError`` escaping custom-type resolution. This is one of two
    deliberate charter<->runtime divergences: the runtime loader (a ``PromptStep``
    list) tolerates duplicate ids, and its ``min_length=1`` ids are laxer than
    charter's ``IDENTIFIER_PATTERN`` (enforced one layer up, in the charter shim's
    ``resolve_runtime_shape_steps``). This reader fails closed in both cases —
    refuse, never accept what the runtime loader would reject. Both boundaries, and
    the single-valid-fixture agreement, are pinned by the charter<->runtime parity
    tests.
    """
    try:
        # A fresh instance per call: YAML(typ="safe") is not thread-safe to share.
        raw: Any = YAML(typ="safe").load(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001  # malformed runtime file => no steps (fail-closed)
        return []
    steps = raw.get("steps") if isinstance(raw, dict) else None
    if not isinstance(steps, list):
        return []
    if not all(isinstance(step, dict) and step.get("id") and step.get("title") for step in steps):
        return []
    step_ids = [str(step["id"]) for step in steps]
    if len(step_ids) != len(set(step_ids)):
        return []
    return step_ids


def step_ids_declare_wp_iteration(step_ids: Iterable[str]) -> bool:
    """True when the sequence declares the canonical ``implement`` step (WP-driven)."""
    return _IMPLEMENT_STEP_ID in set(step_ids)
