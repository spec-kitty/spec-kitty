"""Retired charter pack fields and their ``RETIRED_PACK_FIELD`` rejection (#3732).

The charter-pack cutover (ADR 2026-10-06-1) removes some fields from pack files
outright, with no alias (C-001). A file that still carries one is rejected with
the code :data:`RETIRED_PACK_FIELD`, naming the field and its replacement, instead
of pydantic's generic "extra fields not permitted" error (``contracts/errors.md``).

:data:`RETIRED_PACK_FIELDS` is the one table of retired fields: a loader or
validator calls :func:`reject_retired_fields` with the raw mapping and the scope
it is reading (:data:`SCOPE_ACTIVATION_ENTRY` or :data:`SCOPE_ORG_CHARTER`), and a
loader that only sees a pydantic ``ValidationError`` relocates the typed error to
the file it read with :func:`raise_retired_field_at` (or recovers every one with
:func:`retired_field_errors`).

Scopes
------
A row's ``scope`` names the mapping the field is checked in, and each scope has
exactly one model validator that enforces it:

* :data:`SCOPE_ACTIVATION_ENTRY` -- every ``activations[*]`` entry, enforced by
  ``ActivationEntry``. The entry shape is shared by an ``org-charter.yaml`` and
  the project ``charter.yaml``, so a row in this scope binds both files.
* :data:`SCOPE_ORG_CHARTER` -- the top level of an ``org-charter.yaml``, enforced
  by ``OrgCharterPolicy``.

Adding a row in one of these scopes is the whole change for a new retired field.
A new scope (for example the top level of ``pack.yaml``) also needs the loader of
that file to call :func:`reject_retired_fields` with it.

This module is the only source of the ``RETIRED_PACK_FIELD`` code string. It
lives in the offering tier and imports nothing from ``charter.activation``.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import ValidationError

__all__ = [
    "RETIRED_PACK_FIELD",
    "RETIRED_PACK_FIELDS",
    "RetiredField",
    "RetiredPackFieldError",
    "SCOPE_ACTIVATION_ENTRY",
    "SCOPE_ORG_CHARTER",
    "raise_retired_field_at",
    "reject_retired_fields",
    "retired_field_errors",
]

#: The error code a retired pack field is rejected with (``contracts/errors.md``).
RETIRED_PACK_FIELD = "RETIRED_PACK_FIELD"

#: The runbook every rejection points at.
_MIGRATION_RUNBOOK = "docs/migrations/charter-pack-cutover.md"


#: Scope: one ``activations[*]`` entry, in an ``org-charter.yaml`` or the project ``charter.yaml``.
SCOPE_ACTIVATION_ENTRY = "activation entry"
#: Scope: the top level of an ``org-charter.yaml``.
SCOPE_ORG_CHARTER = "org-charter.yaml"


@dataclass(frozen=True)
class RetiredField:
    """One retired field: the scope it is checked in, its name and its replacement."""

    scope: str
    field: str
    replacement: str


#: Every retired pack field. Adding a row in an enforced scope is the whole change.
RETIRED_PACK_FIELDS: tuple[RetiredField, ...] = (RetiredField(scope=SCOPE_ACTIVATION_ENTRY, field="doctrine_pack_id", replacement="charter_pack_id"),)


def _retired_field_message(location: str, field: str, replacement: str) -> str:
    """Return the operator message for a retired *field* found at *location*."""
    return f"{location}: field '{field}' was removed. Replacement: {replacement}. See {_MIGRATION_RUNBOOK}."


class RetiredPackFieldError(ValueError):
    """A pack file still carries a retired field (code :data:`RETIRED_PACK_FIELD`)."""

    code = RETIRED_PACK_FIELD

    def __init__(self, retired: RetiredField, *, path: Path | str | None = None) -> None:
        self.scope = retired.scope
        self.field = retired.field
        self.replacement = retired.replacement
        self.path = path
        #: The file the field was found in, or the scope when no caller located it yet.
        self.file = str(path) if path is not None else retired.scope
        super().__init__(_retired_field_message(self.file, retired.field, retired.replacement))

    @property
    def retired(self) -> RetiredField:
        """The table row this error was raised for."""
        return RetiredField(scope=self.scope, field=self.field, replacement=self.replacement)

    def at(self, path: Path | str) -> RetiredPackFieldError:
        """Return the same rejection located at *path* (for a caller that knows the file)."""
        return RetiredPackFieldError(self.retired, path=path)


def reject_retired_fields(raw: object, *, scope: str, path: Path | str | None) -> None:
    """Raise :class:`RetiredPackFieldError` when *raw* carries a field retired in *scope*.

    *raw* is the mapping as read from YAML; anything that is not a mapping is left
    to the model's own validation. *path* locates the message (*scope* is used
    when it is ``None``).
    """
    if not isinstance(raw, Mapping):
        return
    data: Mapping[str, Any] = raw
    for retired in RETIRED_PACK_FIELDS:
        if retired.scope == scope and retired.field in data:
            raise RetiredPackFieldError(retired, path=path)


def retired_field_errors(exc: ValidationError) -> list[RetiredPackFieldError]:
    """Return the :class:`RetiredPackFieldError`\\ s pydantic wrapped into *exc*."""
    found: list[RetiredPackFieldError] = []
    for error in exc.errors():
        cause = (error.get("ctx") or {}).get("error")
        if isinstance(cause, RetiredPackFieldError):
            found.append(cause)
    return found


def raise_retired_field_at(exc: ValidationError, path: Path | str) -> None:
    """Re-raise the first retired field wrapped in *exc*, located at *path*.

    A loader calls this from its ``except ValidationError`` block so a retired
    field surfaces as :class:`RetiredPackFieldError` naming the file it read; it
    returns (and the caller handles *exc* as before) when *exc* wraps none.
    """
    retired = retired_field_errors(exc)
    if retired:
        raise retired[0].at(path) from exc
