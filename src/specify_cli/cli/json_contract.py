"""Canonical error envelope and diagnostic guard for machine-readable CLI output.

Successful payloads remain command-specific. Emit these error objects through
``CliConsole.emit_json`` so serialization and terminal policy have one owner.
"""

from __future__ import annotations

import logging
import warnings
from collections.abc import Generator
from contextlib import contextmanager

__all__ = ["json_error", "json_output_guard"]


def json_error(code: str, message: str) -> dict[str, object]:
    """Build the adopted CLI error contract without changing command exit codes."""
    return {"ok": False, "error": {"code": code, "message": message}}


@contextmanager
def json_output_guard(enabled: bool) -> Generator[None, None, None]:
    """Suppress incidental diagnostics in JSON mode and restore them on every exit."""
    if not enabled:
        yield
        return

    previous_disable = logging.root.manager.disable
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        logging.disable(logging.CRITICAL)
        try:
            yield
        finally:
            logging.disable(previous_disable)
