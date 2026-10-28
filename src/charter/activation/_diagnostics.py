"""Diagnostic codes of the charter activation layer.

Two closed code sets live here:

* :class:`CharterEncodingDiagnostic` -- charter-encoding codes emitted by
  ``src/charter/activation/_io.py``;
* :class:`GovernanceDiagnosticCode` with its :class:`GovernanceDiagnostic`
  value object -- the typed entries of ``GovernanceResolution.diagnostics``
  that ``charter context --json`` renders as ``{"code", "message"}`` objects
  (#6460).

See: src/charter/activation/ERROR_CODES.md (hand-maintained mirror until the
code-to-docs flow envisioned in GitHub #645 ships).
"""

from dataclasses import dataclass
from enum import StrEnum

__all__ = [
    "CharterEncodingDiagnostic",
    "GovernanceDiagnostic",
    "GovernanceDiagnosticCode",
]


class CharterEncodingDiagnostic(StrEnum):
    """JSON-stable diagnostic codes emitted by src/charter/activation/_io.py.

    Per-code remediation guidance is documented in src/charter/activation/ERROR_CODES.md.
    """

    AMBIGUOUS = "CHARTER_ENCODING_AMBIGUOUS"
    NOT_NORMALIZED = "CHARTER_ENCODING_NOT_NORMALIZED"


class GovernanceDiagnosticCode(StrEnum):
    """JSON-stable classification of a governance-resolution diagnostic (closed set).

    Consumers classify a diagnostic by this code, never by its message wording.
    Per-code documentation lives in src/charter/activation/ERROR_CODES.md.
    """

    UNKNOWN_SELECTION_DROPPED = "UNKNOWN_SELECTION_DROPPED"
    CATALOG_DEFAULT_APPLIED = "CATALOG_DEFAULT_APPLIED"
    FALLBACK_APPLIED = "FALLBACK_APPLIED"
    SELECTION_MERGED = "SELECTION_MERGED"
    UNRESOLVED_REFERENCE = "UNRESOLVED_REFERENCE"


@dataclass(frozen=True)
class GovernanceDiagnostic:
    """One governance-resolution diagnostic: a stable ``code`` plus human ``message``.

    ``message`` is display text and may be reworded without notice; only
    ``code`` is a contract.
    """

    code: GovernanceDiagnosticCode
    message: str

    def __post_init__(self) -> None:
        # Coerce a raw code string to its member; a code outside the closed set raises ValueError.
        object.__setattr__(self, "code", GovernanceDiagnosticCode(self.code))

    def to_json(self) -> dict[str, str]:
        """Return the JSON form ``{"code": "<CODE>", "message": "<text>"}``."""
        return {"code": self.code.value, "message": self.message}
