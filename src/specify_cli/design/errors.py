"""Typed refusal at the design application boundary."""

from __future__ import annotations


class DesignError(RuntimeError):
    """A bounded authoring refusal with safe machine-readable detail."""

    def __init__(self, code: str, message: str, details: dict[str, object] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}
