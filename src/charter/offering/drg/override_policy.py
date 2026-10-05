"""Per-repo governance policy for built-in DRG node overrides.

The three-layer merge (:mod:`charter.offering.drg.merge`) PERMITS a same-kind org node
to override a built-in node in place (recorded as an ``org_override`` conflict).
The merge does not *govern* whether a particular repo sanctions that override —
that is a per-repo policy decision expressed in
``.kittify/doctrine/replaceable-builtins.yaml`` and enforced by an architectural
test (``tests/architectural/test_builtin_override_policy.py``).

Schema (``replaceable-builtins.yaml``)::

    replaceable_builtins:
      - urn: directive:some-built-in
        reason: We replace this directive because ...

FAIL-CLOSED default: an absent file, an empty file, or a URN not listed means
the override is NOT permitted. This module owns parsing + the pure governance
predicates; the architectural test wires them to a live merge.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from charter.offering.drg.models import DRGGraph, NodeKind

# Only the three governance predicates are advertised as the public-by-name API
# (they are the live cross-module callees, wired from
# ``specify_cli.cli.commands._doctrine_collect``). The supporting types/constant
# (``ReplaceableBuiltin``, ``ReplaceableBuiltinsPolicy``, ``POLICY_RELPATH``,
# ``UnsanctionedOverride``) remain module-level symbols — direct
# ``from charter.offering.drg.override_policy import X`` still works for the
# architectural tests that consume them by-name — they are simply not part of the
# ``import *`` public surface (#2082 FR-011).
__all__ = [
    "load_replaceable_builtins",
    "find_overridden_builtin_urns",
    "find_unsanctioned_overrides",
]

#: Repo-root-relative path of the allowlist file.
POLICY_RELPATH = Path(".kittify/doctrine/replaceable-builtins.yaml")

#: Top-level YAML key holding the list of allowlist entries.
_TOP_LEVEL_KEY = "replaceable_builtins"


@dataclass(frozen=True)
class ReplaceableBuiltin:
    """One allowlisted built-in URN permitted to be overridden by an org node.

    ``reason`` is the operator's governance justification. It MAY be empty for
    non-directive kinds, but a built-in *directive* override additionally
    requires a non-empty reason (enforced by the architectural test).
    """

    urn: str
    reason: str


@dataclass(frozen=True)
class ReplaceableBuiltinsPolicy:
    """The parsed allowlist plus pure governance predicates.

    FAIL-CLOSED: an absent file yields an empty policy in which every override
    is forbidden.
    """

    entries: tuple[ReplaceableBuiltin, ...]

    def is_allowed(self, urn: str) -> bool:
        """True iff *urn* is on the allowlist (fail-closed for unlisted URNs)."""
        return any(entry.urn == urn for entry in self.entries)

    def reason_for(self, urn: str) -> str | None:
        """Return the declared reason for *urn*, or ``None`` when not listed."""
        for entry in self.entries:
            if entry.urn == urn:
                return entry.reason
        return None


class OverridePolicyError(ValueError):
    """Raised when ``replaceable-builtins.yaml`` is present but malformed.

    A missing file is NOT an error (fail-closed empty policy); a present file
    whose shape violates the schema is, so a typo does not silently widen the
    allowlist.
    """


def _parse_entry(raw: Any, index: int, *, source_label: str) -> ReplaceableBuiltin:
    if not isinstance(raw, dict):
        raise OverridePolicyError(
            f"{source_label}: entry #{index} must be a mapping with a "
            f"'urn' key, got {type(raw).__name__}"
        )
    urn = raw.get("urn")
    if not isinstance(urn, str) or not urn:
        raise OverridePolicyError(
            f"{source_label}: entry #{index} is missing a non-empty 'urn'"
        )
    reason = raw.get("reason", "")
    if reason is None:
        reason = ""
    if not isinstance(reason, str):
        raise OverridePolicyError(
            f"{source_label}: entry #{index} ('{urn}') has a non-string 'reason'"
        )
    return ReplaceableBuiltin(urn=urn, reason=reason)


def _parse_policy_document(
    data: object, *, source_label: str
) -> ReplaceableBuiltinsPolicy:
    """Build a policy from an already-parsed YAML document (source-agnostic).

    *source_label* prefixes every error message so the same grammar can report
    against whichever file it was read from.
    """
    if data is None:
        return ReplaceableBuiltinsPolicy(entries=())
    if not isinstance(data, dict):
        raise OverridePolicyError(
            f"{source_label}: top-level document must be a mapping with a "
            f"'{_TOP_LEVEL_KEY}' list"
        )

    raw_entries = data.get(_TOP_LEVEL_KEY, [])
    if raw_entries is None:
        raw_entries = []
    if not isinstance(raw_entries, list):
        raise OverridePolicyError(
            f"{source_label}: '{_TOP_LEVEL_KEY}' must be a list"
        )

    entries = tuple(
        _parse_entry(raw, index, source_label=source_label)
        for index, raw in enumerate(raw_entries)
    )
    return ReplaceableBuiltinsPolicy(entries=entries)


def load_replaceable_builtins(repo_root: Path) -> ReplaceableBuiltinsPolicy:
    """Load the per-repo built-in-override allowlist (fail-closed).

    Reads ``<repo_root>/.kittify/doctrine/replaceable-builtins.yaml``. When the
    file is absent or empty, returns an empty policy that forbids every override.
    A present-but-malformed file raises :class:`OverridePolicyError` so a typo
    cannot silently disable governance.
    """
    policy_path = repo_root / POLICY_RELPATH
    if not policy_path.is_file():
        return ReplaceableBuiltinsPolicy(entries=())

    try:
        data = yaml.safe_load(policy_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise OverridePolicyError(
            f"{POLICY_RELPATH}: YAML parse error: {exc}"
        ) from exc

    return _parse_policy_document(data, source_label=str(POLICY_RELPATH))


# ---------------------------------------------------------------------------
# Pure governance predicates over an already-merged DRG graph.
#
# These take already-loaded inputs (a merged ``DRGGraph``, the frozenset of
# built-in URNs, a parsed ``ReplaceableBuiltinsPolicy``) and return findings.
# They perform NO filesystem I/O, NO merge, and NO allowlist parsing — that is
# the caller's job. Keeping them pure makes the governance gate reusable by any
# consumer repo that has already run the merge.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class UnsanctionedOverride:
    """A built-in override that the repo's allowlist does not sanction."""

    urn: str
    kind: str
    why: str


def _is_directive_urn(urn: str) -> bool:
    return urn.split(":", 1)[0] == NodeKind.DIRECTIVE.value


def find_overridden_builtin_urns(
    merged: DRGGraph,
    built_in_urns: frozenset[str],
) -> dict[str, str]:
    """Return ``{urn: kind}`` for every built-in URN now carrying org provenance.

    A merged node that sits at a built-in URN but is tagged ``org:<pack>`` is,
    by construction of :func:`charter.offering.drg.merge.merge_three_layers`, a permitted
    same-kind override (``org_override``). This is the authoritative override set
    — equivalent to the ``org_override`` conflict records, recovered purely from
    the merged graph.

    Scope (intentional): only ``org:``-provenance overrides are adjudicated.
    A *project*-tier override of a built-in URN (``project`` provenance) is
    deliberately OUT of scope — project doctrine is the trusted operator tier
    and is not gated by the consumer-facing replaceable-builtins allowlist.
    """
    return {
        node.urn: node.kind.value
        for node in merged.nodes
        if (node.provenance or "").startswith("org:") and node.urn in built_in_urns
    }


def find_unsanctioned_overrides(
    targets: dict[str, str],
    policy: ReplaceableBuiltinsPolicy,
) -> list[UnsanctionedOverride]:
    """Return every overridden built-in URN not sanctioned by *policy* (pure).

    *targets* maps each overridden built-in URN to its kind (see
    :func:`find_overridden_builtin_urns`). For each target:

    * the URN MUST be on the allowlist (fail-closed if absent); and
    * a built-in **directive** override additionally requires a non-empty reason.

    The result is empty when every override is sanctioned (or none exist).
    """
    findings: list[UnsanctionedOverride] = []
    for urn, kind in sorted(targets.items()):
        if not policy.is_allowed(urn):
            findings.append(
                UnsanctionedOverride(
                    urn=urn,
                    kind=kind,
                    why="not on .kittify/doctrine/replaceable-builtins.yaml",
                )
            )
            continue
        if _is_directive_urn(urn) and not (policy.reason_for(urn) or "").strip():
            findings.append(
                UnsanctionedOverride(
                    urn=urn,
                    kind=kind,
                    why="directive override requires a non-empty reason",
                )
            )
    return findings
