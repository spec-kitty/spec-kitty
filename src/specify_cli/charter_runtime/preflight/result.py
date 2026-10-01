"""Result dataclasses for ``spec-kitty charter preflight``.

These types are the **callable surface** consumed by:

* the typer CLI command (``spec-kitty charter preflight``);
* the session-start hook callable ``run_charter_preflight(...)`` used by
  ``spec-kitty next`` and ``spec-kitty implement``.

The JSON shape produced by :py:meth:`CharterPreflightResult.to_dict` and
:py:meth:`CharterPreflightResult.to_json` is the binding contract documented
in
``kitty-specs/charter-ux-and-org-pack-vocabulary-01KSAF14/contracts/charter-preflight-json.md``.

Both dataclasses are frozen — the runner constructs the result once and
hands it to callers; no mutation is permitted downstream.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Literal

__all__ = [
    "CharterPreflightCheck",
    "CharterPreflightResult",
]


# Allowed states for a single preflight check.  ``skipped`` is reserved for
# checks the runner intentionally did not evaluate (e.g. a degraded mode);
# ``built_in_only`` is reserved for the synthesized DRG layer when the
# project legitimately runs without a generated graph (FR-009).
CheckState = Literal[
    "fresh",
    "stale",
    "missing",
    "built_in_only",
    "invalid",
    "skipped",
]


@dataclass(frozen=True)
class CharterPreflightCheck:
    """One row in the preflight result.

    Attributes:
        name: Stable identifier for this layer (e.g. ``charter_source``,
            ``synced_bundle``, ``synthesized_drg``).
        state: Outcome of the check.  See :data:`CheckState`.
        detail: Human-readable explanation surfaced verbatim in CLI output
            and JSON output.
        remediation: Exact recovery command, or ``None`` when no action is
            required.  When ``state`` is ``fresh``, ``skipped``, or
            ``built_in_only`` this MUST be ``None``.
    """

    name: str
    state: CheckState
    detail: str
    remediation: str | None


@dataclass(frozen=True)
class CharterPreflightResult:
    """Aggregate outcome of a charter preflight invocation.

    The shape is locked by
    ``contracts/charter-preflight-json.md`` — callers serialise via
    :py:meth:`to_dict` / :py:meth:`to_json` and parse via
    :py:meth:`from_dict` (not provided here; callers re-hydrate from JSON
    only when crossing process boundaries, which is not yet a use case).

    Attributes:
        passed: ``True`` iff every check is ``fresh``, ``skipped``, or
            ``built_in_only``.
        checks: Ordered list of layer checks; consumers MAY rely on the
            ordering (charter_source, synced_bundle, synthesized_drg).
        auto_refresh_applied: ``True`` iff ``--auto-refresh`` was honoured
            AND at least one refresh action ran successfully.
        auto_refresh_actions: Ordered list of exact commands executed.
            Empty when ``auto_refresh_applied`` is ``False``.
        blocked_reason: Non-``None`` iff ``passed`` is ``False`` AND
            ``auto_refresh_applied`` is ``False``.  For each non-passing
            check that names a remediation, the string names an actionable
            next command; for a check on the declared exemption set (no
            effective self-service remediation — R-006, C-EFF-2) it instead
            names the check and explains why, with no command.
        warnings: Structured non-blocking operator notes.  Machine consumers
            read these from JSON instead of scraping human warning text.
    """

    passed: bool
    checks: list[CharterPreflightCheck] = field(default_factory=list)
    auto_refresh_applied: bool = False
    auto_refresh_actions: list[str] = field(default_factory=list)
    blocked_reason: str | None = None
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-ready dict matching the contract shape.

        Uses :func:`dataclasses.asdict` so frozen child dataclasses are
        flattened recursively.  Key ordering is fixed (insertion order).
        """
        payload: dict[str, object] = {
            "passed": self.passed,
            "checks": [asdict(c) for c in self.checks],
            "auto_refresh_applied": self.auto_refresh_applied,
            "auto_refresh_actions": list(self.auto_refresh_actions),
            "blocked_reason": self.blocked_reason,
        }
        if self.warnings:
            payload["warnings"] = list(self.warnings)
        return payload

    def to_json(self) -> str:
        """Serialise to a stable JSON string with sorted keys.

        Sorted keys make the output deterministic across Python versions
        and platforms — critical because this output is consumed by other
        tools and by humans during incident response.
        """
        return json.dumps(self.to_dict(), sort_keys=True, ensure_ascii=False)
