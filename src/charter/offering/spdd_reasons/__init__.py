"""SPDD/REASONS Charter Pack: charter activation and context injection.

Public surface:

- ``is_spdd_reasons_active(repo_root)`` — single source of truth for whether the
  SPDD/REASONS pack is active for a given project.
- ``append_spdd_reasons_guidance(lines, mission, action)`` — charter-context
  helper that appends the action-scoped REASONS subsection.

See ``contracts/activation.md`` and ``contracts/charter-context.md`` in the
mission directory for the formal contracts.
"""

from __future__ import annotations

from charter.offering.spdd_reasons.activation import (
    clear_activation_cache,
    is_spdd_reasons_active,
)
from charter.offering.spdd_reasons.charter_context import append_spdd_reasons_guidance
from charter.offering.spdd_reasons.template_renderer import (
    REASONS_BLOCK_END,
    REASONS_BLOCK_START,
    UnmatchedReasonsBlockError,
    apply_spdd_blocks_for_project,
    process_spdd_blocks,
)

__all__ = [
    "REASONS_BLOCK_END",
    "REASONS_BLOCK_START",
    "UnmatchedReasonsBlockError",
    "append_spdd_reasons_guidance",
    "apply_spdd_blocks_for_project",
    "clear_activation_cache",
    "is_spdd_reasons_active",
    "process_spdd_blocks",
]
