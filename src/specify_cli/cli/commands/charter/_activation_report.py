"""The change report of ``charter activate`` / ``charter deactivate`` (positional form).

One value per run feeds both the human renderer (``activate.py`` /
``deactivate.py``) and the ``--json`` serializer, so the two can never disagree
about what a run did (issue #6525, local slice). The JSON shape is the local
CLI contract of ``kitty-specs/charter-cli-typed-errors-json-01M5ZC9Z/contracts/cli-json.md``
(``schema_version`` ``1.0.0``, snake_case); it is not the spec-kitty-charter
activation contract.

The cascade part keeps its entries in the order the text renderer prints them:
the per-outcome lists of the JSON payload are views over that one ordered
sequence, so every artifact a cascade line names appears in exactly one list.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

__all__ = [
    "SCHEMA_VERSION",
    "ActivationChangeReport",
    "ArtifactRef",
    "CascadeEntry",
    "CascadeOutcome",
    "CascadeReport",
    "NoCascadeReport",
]

#: Local schema version of the success payload (not the contract revision).
SCHEMA_VERSION = "1.0.0"


class CascadeOutcome(StrEnum):
    """What a cascade did with one artifact; the value is the JSON list it lands in."""

    CASCADED = "cascaded"
    REINSTATED = "reinstated"
    FAILED = "failed"
    SKIPPED_OUT_OF_SCOPE = "skipped_out_of_scope"
    SKIPPED_DEACTIVATED = "skipped_deactivated"
    UNREACHED_BEHIND_DEACTIVATED = "unreached_behind_deactivated"
    SKIPPED_KIND_FILTERED = "skipped_kind_filtered"
    SKIPPED_SHARED = "skipped_shared"
    SKIPPED_REQUIRED = "skipped_required"
    STILL_ACTIVE_UNRESTRICTED = "still_active_unrestricted"


@dataclass(frozen=True)
class ArtifactRef:
    """One artifact: operator kind token, stored (config-stem) id and DRG URN when known."""

    kind: str
    id: str
    urn: str | None = None

    @property
    def label(self) -> str:
        """``<kind>/<id>``, the spelling every text line uses."""
        return f"{self.kind}/{self.id}"

    def to_json(self) -> dict[str, object]:
        return {"kind": self.kind, "id": self.id, "urn": self.urn}


@dataclass(frozen=True)
class CascadeEntry:
    """One cascade line.

    ``message``: the failure text of a ``failed`` entry, or the advisory warning
    a ``cascaded`` entry carries (a mission-step default profile, #4115).
    ``required_by``: the requiring parents of a ``skipped_deactivated`` entry
    (empty when it was reached only through ``suggests``).
    ``referenced_by``: the still-active source of a ``skipped_shared`` entry.
    ``packs``: the org packs of a ``skipped_required`` entry.
    ``deactivated``: a ``skipped_out_of_scope`` node that is itself deactivated
    (the walk stopped there); serialized on every ``skipped_out_of_scope`` entry.
    """

    outcome: CascadeOutcome
    ref: ArtifactRef
    message: str | None = None
    required_by: tuple[str, ...] = ()
    referenced_by: str | None = None
    packs: tuple[str, ...] = ()
    deactivated: bool = False

    def to_json(self) -> dict[str, object]:
        payload = self.ref.to_json()
        if self.outcome is CascadeOutcome.FAILED:
            payload["message"] = self.message
        elif self.outcome is CascadeOutcome.SKIPPED_DEACTIVATED:
            payload["required_by"] = list(self.required_by)
        elif self.outcome is CascadeOutcome.SKIPPED_OUT_OF_SCOPE:
            payload["deactivated"] = self.deactivated
        elif self.outcome is CascadeOutcome.SKIPPED_SHARED:
            payload["referenced_by"] = self.referenced_by
        elif self.outcome is CascadeOutcome.SKIPPED_REQUIRED:
            payload["packs"] = list(self.packs)
        return payload

    @property
    def warning(self) -> str | None:
        """The advisory warning of a ``cascaded`` entry, else ``None``."""
        return self.message if self.outcome is CascadeOutcome.CASCADED else None


@dataclass(frozen=True)
class CascadeReport:
    """A cascade run: its source, scope and every outcome, in render order."""

    source_urn: str
    scope: str | tuple[str, ...]
    entries: tuple[CascadeEntry, ...] = ()
    zero_activatable: bool = False

    def of(self, outcome: CascadeOutcome) -> tuple[CascadeEntry, ...]:
        """The entries with *outcome*, in render order."""
        return tuple(entry for entry in self.entries if entry.outcome is outcome)

    def to_json(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "source_urn": self.source_urn,
            "scope": self.scope if isinstance(self.scope, str) else list(self.scope),
        }
        for outcome in CascadeOutcome:
            payload[outcome.value] = [entry.to_json() for entry in self.of(outcome)]
        return payload


@dataclass(frozen=True)
class NoCascadeReport:
    """What the no-``--cascade`` warning names: referenced but not activated (FR-013)."""

    skipped: tuple[ArtifactRef, ...] = ()
    deactivated: tuple[ArtifactRef, ...] = ()
    kind_filtered: tuple[ArtifactRef, ...] = ()
    hint: str | None = None

    @property
    def warned(self) -> tuple[ArtifactRef, ...]:
        """Every artifact a ``Warning: referenced …`` line names."""
        return (*self.skipped, *self.deactivated)


@dataclass(frozen=True)
class ActivationChangeReport:
    """The success payload of positional ``charter activate`` / ``charter deactivate``.

    ``preflight_warnings`` are printed before the change itself (the in-flight
    step-removal warnings of a mission-type activation, FR-008). ``warnings``
    are the registration warnings of activate (printed as given) or the
    manager warnings of deactivate (and the mission-step default warning of the
    named profile); ``result_warnings`` are the activation manager's warnings
    (printed escaped, after ``warnings``, a8dd1812); ``tension_warnings`` the
    activate-time tension findings, kept apart because the text output prints
    them after the ``--only`` lines. ``now_listed`` is the kind's list as
    written by ``--only`` and ``None`` without it. ``no_longer_in_force`` is
    ``None`` without ``--only``, and also with ``--only`` when what stopped being
    in force could not be determined (the effective set was unresolved; the
    text footer then reads "unknown"), serialized as ``null``.
    """

    command: str
    kind: str
    id: str
    changed: tuple[str, ...] = ()
    no_longer_in_force: tuple[str, ...] | None = None
    now_listed: tuple[str, ...] | None = None
    preflight_warnings: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    result_warnings: tuple[str, ...] = ()
    tension_warnings: tuple[str, ...] = ()
    referenced: NoCascadeReport | None = None
    cascade: CascadeReport | None = None

    def all_warnings(self) -> list[str]:
        """Every warning the run printed, in print order (cascade advisories last)."""
        cascade_warnings = [entry.warning for entry in self.cascade.entries if entry.warning] if self.cascade else []
        return [*self.preflight_warnings, *self.warnings, *self.result_warnings, *self.tension_warnings, *(warning for warning in cascade_warnings if warning)]

    @property
    def dropped_unknown(self) -> bool:
        """``--only`` ran but what stopped being in force could not be determined."""
        return self.now_listed is not None and self.no_longer_in_force is None

    def _no_longer_in_force_json(self) -> list[str] | None:
        """``null`` when unknown (``--only`` on an unresolved effective set), else the list (``[]`` without ``--only``)."""
        return None if self.dropped_unknown else list(self.no_longer_in_force or ())

    def to_json(self) -> dict[str, object]:
        return {
            "schema_version": SCHEMA_VERSION,
            "command": self.command,
            "kind": self.kind,
            "id": self.id,
            "changed": list(self.changed),
            "now_listed": list(self.now_listed or ()),
            "no_longer_in_force": self._no_longer_in_force_json(),
            "warnings": self.all_warnings(),
            "referenced_not_cascaded": [ref.to_json() for ref in self.referenced.warned] if self.referenced else [],
            "cascade": self.cascade.to_json() if self.cascade else None,
        }
