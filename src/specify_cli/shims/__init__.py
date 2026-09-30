"""Agent command file generation module.

Public API
----------
- ``generate_shims``   -- Write command files for all configured agents.
"""

from __future__ import annotations

from specify_cli.shims.generator import generate_all_shims as generate_shims

__all__ = [
    "generate_shims",
]
