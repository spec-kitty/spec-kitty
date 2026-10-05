"""Per-repo governance policy for built-in DRG node overrides.

The three-layer merge (:mod:`charter.offering.drg.merge`) PERMITS a same-kind org node
to override a built-in node in place (recorded as an ``org_override`` conflict).
The merge does not *govern* whether a particular repo sanctions that override.
That decision is made here, from two sources:

* the consumer allowlist ``.kittify/doctrine/replaceable-builtins.yaml``, which
  may also carry ``revoked_pack_sanctions`` to withdraw what a pack delivered;
* each configured org pack's own ``replaceable-builtins.yaml`` at its pack root,
  effective only for overrides that same pack contributes.

Schema (both files; ``revoked_pack_sanctions`` is consumer-only)::

    replaceable_builtins:
      - urn: directive:some-built-in
        reason: We replace this directive because ...
    revoked_pack_sanctions:          # consumer file only
      - urn: directive:some-built-in # or: pack: <configured pack name>

FAIL-CLOSED default: an absent file, an empty file, or a URN not listed means
the override is NOT permitted. This module is the single authority for parsing,
scoping, revocation and the sanction decision table; the doctor report and the
architectural gate only wire it in. :func:`adjudicate_overrides` and
:func:`find_overridden_builtins` are pure (no I/O).
"""

from __future__ import annotations

import warnings
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

import yaml

from charter.offering.drg.models import DRGGraph, NodeKind
from charter.offering.drg.org_pack_config import (
    OrgPackSubdirEscapeError,
    load_pack_registry,
    resolve_relative_path_within_root,
)
from kernel.resolution import resolve_rejecting_loops

if TYPE_CHECKING:
    from charter.offering.drg.org_pack_loader import OrgDRGFragment

# The functions are the public-by-name API (wired from
# ``specify_cli.cli.commands._doctrine_collect`` and the architectural gate). The
# supporting types/constants remain module-level symbols: direct
# ``from charter.offering.drg.override_policy import X`` still works for the
# callers that consume them by name; they are simply not part of the
# ``import *`` public surface (#2082 FR-011).
__all__ = [
    "adjudicate_overrides",
    "dump_pack_sanction",
    "configured_pack_names",
    "find_overridden_builtins",
    "legacy_template_entries",
    "load_effective_override_policy",
    "load_pack_sanction",
    "pack_roots_from_fragments",
    "pack_sanction_present",
    "render_sanction_entries",
    "sanction_reason_missing",
]

#: Repo-root-relative path of the allowlist file.
POLICY_RELPATH = Path(".kittify/doctrine/replaceable-builtins.yaml")

#: Top-level YAML key holding the list of allowlist entries.
_TOP_LEVEL_KEY = "replaceable_builtins"

#: Consumer-only top-level key withdrawing pack-delivered sanctions.
_REVOCATIONS_KEY = "revoked_pack_sanctions"

#: File name of a pack's own sanction, at the pack root.
PACK_POLICY_FILENAME = "replaceable-builtins.yaml"

#: Pre-contract location some packs still ship; advisory only, never a sanction.
LEGACY_TEMPLATE_RELPATH = "templates/setup/replaceable-builtins.yaml"


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
    revoked_urns: frozenset[str] = frozenset()
    revoked_packs: frozenset[str] = frozenset()

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


def _parse_revocations(
    raw: object, *, source_label: str
) -> tuple[frozenset[str], frozenset[str]]:
    """Parse the consumer-only ``revoked_pack_sanctions`` list into (urns, packs)."""
    if raw is None:
        return frozenset(), frozenset()
    if not isinstance(raw, list):
        raise OverridePolicyError(
            f"{source_label}: '{_REVOCATIONS_KEY}' must be a list"
        )
    urns: set[str] = set()
    packs: set[str] = set()
    for index, item in enumerate(raw):
        where = f"{source_label}: {_REVOCATIONS_KEY} entry #{index}"
        if not isinstance(item, dict):
            raise OverridePolicyError(
                f"{where} must be a mapping with exactly one of 'urn' or 'pack'"
            )
        unknown = sorted(set(item) - {"urn", "pack", "reason"})
        selectors = [key for key in ("urn", "pack") if key in item]
        if unknown or len(selectors) != 1:
            raise OverridePolicyError(
                f"{where} must have exactly one of 'urn' or 'pack' "
                f"(and an optional 'reason'), got keys {sorted(item)}"
            )
        value = item[selectors[0]]
        if not isinstance(value, str) or not value:
            raise OverridePolicyError(
                f"{where} needs a non-empty string '{selectors[0]}'"
            )
        if not isinstance(item.get("reason", ""), (str, type(None))):
            raise OverridePolicyError(f"{where} has a non-string 'reason'")
        (urns if selectors[0] == "urn" else packs).add(value)
    return frozenset(urns), frozenset(packs)


def _parse_policy_document(
    data: object, *, source_label: str, allow_revocations: bool
) -> ReplaceableBuiltinsPolicy:
    """Build a policy from an already-parsed YAML document (source-agnostic).

    *source_label* prefixes every error message so the same grammar can report
    against whichever file it was read from. ``revoked_pack_sanctions`` is honoured
    only when *allow_revocations* (the consumer file); in any other file it is an
    error, so a pack cannot pretend to revoke a sibling's sanction.
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
    if _REVOCATIONS_KEY in data and not allow_revocations:
        raise OverridePolicyError(
            f"{source_label}: '{_REVOCATIONS_KEY}' is consumer-only and is not "
            f"allowed in a pack sanction file"
        )
    revoked_urns, revoked_packs = _parse_revocations(
        data.get(_REVOCATIONS_KEY), source_label=source_label
    )
    return ReplaceableBuiltinsPolicy(
        entries=entries, revoked_urns=revoked_urns, revoked_packs=revoked_packs
    )


def _read_policy_file(
    path: Path, *, source_label: str, allow_revocations: bool
) -> ReplaceableBuiltinsPolicy:
    """Read and parse one policy file, wrapping every I/O and YAML failure."""
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise OverridePolicyError(
            f"{source_label}: YAML parse error: {exc}"
        ) from exc
    except (OSError, UnicodeDecodeError) as exc:
        raise OverridePolicyError(f"{source_label}: cannot read file: {exc}") from exc
    return _parse_policy_document(
        data, source_label=source_label, allow_revocations=allow_revocations
    )


def _load_consumer_policy(repo_root: Path) -> ReplaceableBuiltinsPolicy:
    """Load the per-repo built-in-override allowlist (fail-closed).

    Reads ``<repo_root>/.kittify/doctrine/replaceable-builtins.yaml``. When the
    file is absent or empty, returns an empty policy that forbids every override.
    A present-but-malformed file raises :class:`OverridePolicyError` so a typo
    cannot silently disable governance.
    """
    policy_path = repo_root / POLICY_RELPATH
    if not policy_path.is_file():
        return ReplaceableBuiltinsPolicy(entries=())
    return _read_policy_file(
        policy_path, source_label=str(POLICY_RELPATH), allow_revocations=True
    )


def _resolve_policy_file(root: Path, relpath: str, *, source_label: str) -> Path:
    """Resolve ``<root>/<relpath>`` with containment, as a regular file.

    Raises :class:`OverridePolicyError` when the path escapes *root* or is not a
    regular file. The caller has already established that something exists there.
    """
    try:
        resolved = resolve_relative_path_within_root(root, relpath)
    except OrgPackSubdirEscapeError as exc:
        raise OverridePolicyError(f"{source_label}: {exc}") from exc
    if not resolved.is_file():
        raise OverridePolicyError(f"{source_label}: not a regular file")
    return Path(resolved)


def pack_sanction_present(pack_root: Path) -> bool:
    """True when *pack_root* holds a sanction entry, even a dangling symlink.

    The one presence rule (``exists() or is_symlink()``): a bare ``exists()``
    follows symlinks and would skip a file the parser rejects.
    """
    candidate = pack_root / PACK_POLICY_FILENAME
    return candidate.exists() or candidate.is_symlink()


def dump_pack_sanction(entries: Iterable[ReplaceableBuiltin]) -> str:
    """Render *entries* as a pack sanction document (the inverse of the parser).

    This module owns the ``replaceable_builtins`` top-level key, so writers go
    through here instead of spelling it themselves.
    """
    payload = {_TOP_LEVEL_KEY: [{"urn": entry.urn, "reason": entry.reason} for entry in entries]}
    return yaml.safe_dump(payload, sort_keys=False)


def render_sanction_entries(entries: Iterable[ReplaceableBuiltin]) -> str:
    """Render *entries* as a ``replaceable_builtins:`` snippet an operator can paste.

    Unlike :func:`dump_pack_sanction` an empty reason is omitted, so a
    non-directive entry stays minimal. This module owns the file grammar; callers
    (``doctor``) print the result instead of spelling the key or dumping YAML.
    """
    items = [{"urn": entry.urn, **({"reason": entry.reason} if entry.reason else {})} for entry in entries]
    return yaml.safe_dump({_TOP_LEVEL_KEY: items}, sort_keys=False, default_flow_style=False, width=10**6, allow_unicode=True)


def load_pack_sanction(pack_name: str, pack_root: Path) -> ReplaceableBuiltinsPolicy:
    """Load the sanction file a pack ships at its root (fail-closed, contained).

    An absent file is an empty policy. A file that escapes *pack_root*, is not a
    regular file, cannot be read, is not valid YAML of the right shape, or carries
    the consumer-only ``revoked_pack_sanctions`` key raises
    :class:`OverridePolicyError` naming the pack and the path.
    """
    if not pack_sanction_present(pack_root):
        return ReplaceableBuiltinsPolicy(entries=())
    candidate = pack_root / PACK_POLICY_FILENAME
    label = f"pack '{pack_name}' {candidate}"
    path = _resolve_policy_file(pack_root, PACK_POLICY_FILENAME, source_label=label)
    return _read_policy_file(path, source_label=label, allow_revocations=False)


def legacy_template_entries(pack_root: Path, urns: Iterable[str]) -> dict[str, str]:
    """Return ``{urn: reason}`` the pack lists in its legacy setup template.

    A tolerant, advisory probe: ``templates/setup/replaceable-builtins.yaml`` is
    never a sanction. Any problem (absent, escaping, malformed) yields ``{}``.
    Transitional; removed together with #2594.
    """
    wanted = set(urns)
    try:
        path = _resolve_policy_file(
            pack_root, LEGACY_TEMPLATE_RELPATH, source_label="legacy template"
        )
        policy = _read_policy_file(
            path, source_label="legacy template", allow_revocations=False
        )
    except (OverridePolicyError, OSError):
        return {}
    return {
        entry.urn: entry.reason for entry in policy.entries if entry.urn in wanted
    }


@dataclass(frozen=True)
class EffectiveOverridePolicy:
    """The consumer allowlist plus every configured pack's sanction (FR-013).

    Built by :func:`load_effective_override_policy` and consumed by
    :func:`adjudicate_overrides`. Problems are recorded rather than raised, so
    one broken file never hides the other findings (isolation) and never widens
    governance (the broken file contributes no sanction).
    """

    consumer: ReplaceableBuiltinsPolicy
    packs: Mapping[str, ReplaceableBuiltinsPolicy]
    pack_errors: tuple[str, ...] = ()
    pack_error_names: frozenset[str] = frozenset()
    consumer_error: str | None = None
    revocation_errors: tuple[str, ...] = ()


def pack_roots_from_fragments(
    fragments: Iterable[OrgDRGFragment], repo_root: Path
) -> dict[str, Path]:
    """Map each configured pack's registry name to its effective root.

    The loader stamps ``source_ref`` with the absolute effective root (including
    any ``subdir``); a relative one is resolved against *repo_root*.
    """
    return {
        fragment.pack_name: repo_root / fragment.source_ref
        for fragment in fragments
    }


def _same_file(first: Path, second: Path) -> bool:
    """True when both paths resolve to the same location (symlink-safe).

    Resolution goes through the canonical loop-aware resolver, which raises
    ``OSError`` for a symlink loop on every supported interpreter; an
    unresolvable path is never the same file.
    """
    try:
        return resolve_rejecting_loops(first) == resolve_rejecting_loops(second)
    except OSError:
        return False


def _revocation_errors(
    consumer: ReplaceableBuiltinsPolicy, configured: Iterable[str]
) -> tuple[str, ...]:
    return tuple(
        f"{POLICY_RELPATH}: {_REVOCATIONS_KEY} names pack '{name}', which is not a "
        f"configured org pack"
        for name in sorted(consumer.revoked_packs - set(configured))
    )


def configured_pack_names(repo_root: Path, pack_roots: Mapping[str, Path]) -> frozenset[str]:
    """Every pack name the repo configures: the registry's names plus *pack_roots*.

    The one definition of "configured" that ``revoked_pack_sanctions`` targets are
    validated against, shared by ``doctor doctrine`` and the override gate. The
    caller has already read the registry once, so the legacy-config
    ``DeprecationWarning`` is suppressed here rather than emitted a second time.
    """
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        registry_names = load_pack_registry(repo_root, quiet=True).names()
    return frozenset({*registry_names, *pack_roots})


def load_effective_override_policy(
    repo_root: Path,
    pack_roots: Mapping[str, Path],
    configured_pack_names: Iterable[str] | None = None,
) -> EffectiveOverridePolicy:
    """Load the consumer allowlist and every pack's sanction in one pass.

    A malformed consumer file does not raise: it is recorded in ``consumer_error``
    and treated as empty (fail-closed). Each pack file is read exactly once; a
    failing pack is left out of ``packs`` and recorded in ``pack_errors``. A pack
    whose sanction path is the consumer file itself counts once, for the consumer.

    *configured_pack_names* is the registry's view of which packs exist (used to
    validate ``revoked_pack_sanctions`` targets); it defaults to the keys of
    *pack_roots*, but a configured pack whose fragment failed to load is still
    configured and must not be reported as unknown.
    """
    consumer_error: str | None = None
    try:
        consumer = _load_consumer_policy(repo_root)
    except OverridePolicyError as exc:
        consumer = ReplaceableBuiltinsPolicy(entries=())
        consumer_error = str(exc)

    consumer_path = repo_root / POLICY_RELPATH
    packs: dict[str, ReplaceableBuiltinsPolicy] = {}
    pack_errors: list[str] = []
    pack_error_names: set[str] = set()
    for name, root in pack_roots.items():
        if _same_file(root / PACK_POLICY_FILENAME, consumer_path):
            packs[name] = ReplaceableBuiltinsPolicy(entries=())
            continue
        try:
            packs[name] = load_pack_sanction(name, root)
        except OverridePolicyError as exc:
            pack_errors.append(str(exc))
            pack_error_names.add(name)
    return EffectiveOverridePolicy(
        consumer=consumer,
        packs=packs,
        pack_errors=tuple(pack_errors),
        pack_error_names=frozenset(pack_error_names),
        consumer_error=consumer_error,
        revocation_errors=_revocation_errors(
            consumer, pack_roots if configured_pack_names is None else configured_pack_names
        ),
    )


# ---------------------------------------------------------------------------
# Pure governance predicates over an already-merged DRG graph.
#
# These take already-loaded inputs (a merged ``DRGGraph``, the frozenset of
# built-in URNs, an ``EffectiveOverridePolicy``) and return findings. They
# perform NO filesystem I/O, NO merge, and NO allowlist parsing — that is the
# caller's job. Keeping them pure makes the governance gate reusable by any
# consumer repo that has already run the merge.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class UnsanctionedOverride:
    """A built-in override that no source sanctions."""

    urn: str
    kind: str
    why: str


@dataclass(frozen=True)
class OverriddenBuiltin:
    """A built-in URN whose surviving node carries ``org:<pack>`` provenance."""

    urn: str
    kind: str
    pack: str


@dataclass(frozen=True)
class SanctionedOverride:
    """An override sanctioned by the consumer allowlist or by its own pack."""

    urn: str
    kind: str
    pack: str
    source: Literal["consumer", "pack"]
    reason: str


@dataclass(frozen=True)
class OverrideAdjudication:
    """Result of :func:`adjudicate_overrides`: both partitions, input-ordered."""

    sanctioned: list[SanctionedOverride]
    unsanctioned: list[UnsanctionedOverride]


def _is_directive_urn(urn: str) -> bool:
    return bool(urn.split(":", 1)[0] == NodeKind.DIRECTIVE.value)


def find_overridden_builtins(
    merged: DRGGraph,
    built_in_urns: frozenset[str],
) -> list[OverriddenBuiltin]:
    """Return every built-in URN now carrying org provenance, sorted by URN.

    A merged node that sits at a built-in URN but is tagged ``org:<pack>`` is,
    by construction of :func:`charter.offering.drg.merge.merge_three_layers`, a permitted
    same-kind override (``org_override``). The contributing pack is read from the
    provenance with ``removeprefix`` (pack names may contain ``:``).

    Scope (intentional): only ``org:``-provenance overrides are adjudicated.
    A *project*-tier override of a built-in URN (``project`` provenance) is
    deliberately OUT of scope — project doctrine is the trusted operator tier
    and is not gated by the consumer-facing replaceable-builtins allowlist.
    """
    found = [
        OverriddenBuiltin(
            urn=node.urn,
            kind=node.kind.value,
            pack=(node.provenance or "").removeprefix("org:"),
        )
        for node in merged.nodes
        if (node.provenance or "").startswith("org:") and node.urn in built_in_urns
    ]
    return sorted(found, key=lambda override: override.urn)


def sanction_reason_missing(urn: str, reason: str) -> bool:
    """True when *urn* is a directive and *reason* is blank (the single rule).

    A directive override needs a non-empty reason; other kinds do not. The
    adjudicator and the pack validator both ask this one question.
    """
    return _is_directive_urn(urn) and not reason.strip()


def _valid_entry(policy: ReplaceableBuiltinsPolicy | None, urn: str) -> str | None:
    """Return the reason when *policy* validly sanctions *urn*, else ``None``."""
    if policy is None or not policy.is_allowed(urn):
        return None
    reason = policy.reason_for(urn) or ""
    return None if sanction_reason_missing(urn, reason) else reason


def _why_unsanctioned(
    override: OverriddenBuiltin,
    effective: EffectiveOverridePolicy,
    pack_policy: ReplaceableBuiltinsPolicy | None,
) -> str:
    """Explain why no valid sanction applies (the decision table's red rows)."""
    consumer = effective.consumer
    if _valid_entry(pack_policy, override.urn) is not None and (
        override.urn in consumer.revoked_urns or override.pack in consumer.revoked_packs
    ):
        return (
            f"pack '{override.pack}' sanction revoked by {POLICY_RELPATH} "
            f"({_REVOCATIONS_KEY})"
        )
    if consumer.is_allowed(override.urn):
        return "directive override requires a non-empty reason"
    if pack_policy is not None and pack_policy.is_allowed(override.urn):
        return (
            f"directive override requires a non-empty reason (pack "
            f"'{override.pack}' {PACK_POLICY_FILENAME})"
        )
    if override.pack in effective.pack_error_names:
        return (
            f"pack '{override.pack}' {PACK_POLICY_FILENAME} could not be read "
            f"(see the sanction file errors)"
        )
    return f"not on {POLICY_RELPATH} or pack '{override.pack}' {PACK_POLICY_FILENAME}"


def _verdict_for(
    override: OverriddenBuiltin, effective: EffectiveOverridePolicy
) -> SanctionedOverride | UnsanctionedOverride:
    """Apply the sanction decision table to one override."""
    consumer_reason = _valid_entry(effective.consumer, override.urn)
    if consumer_reason is not None:
        return SanctionedOverride(
            urn=override.urn,
            kind=override.kind,
            pack=override.pack,
            source="consumer",
            reason=consumer_reason,
        )
    pack_policy = effective.packs.get(override.pack)
    pack_reason = _valid_entry(pack_policy, override.urn)
    revoked = (
        override.urn in effective.consumer.revoked_urns
        or override.pack in effective.consumer.revoked_packs
    )
    if pack_reason is not None and not revoked:
        return SanctionedOverride(
            urn=override.urn,
            kind=override.kind,
            pack=override.pack,
            source="pack",
            reason=pack_reason,
        )
    return UnsanctionedOverride(
        urn=override.urn,
        kind=override.kind,
        why=_why_unsanctioned(override, effective, pack_policy),
    )


def adjudicate_overrides(
    overrides: Iterable[OverriddenBuiltin],
    effective: EffectiveOverridePolicy,
) -> OverrideAdjudication:
    """Partition *overrides* into sanctioned and unsanctioned (pure, fail-closed).

    Implements the sanction decision table: the consumer allowlist is checked
    first; otherwise only the pack that contributed the surviving node can
    sanction it, unless the consumer revoked that URN or that pack; a directive
    needs a non-empty reason from the source that sanctions it.
    """
    sanctioned: list[SanctionedOverride] = []
    unsanctioned: list[UnsanctionedOverride] = []
    for override in overrides:
        verdict = _verdict_for(override, effective)
        if isinstance(verdict, SanctionedOverride):
            sanctioned.append(verdict)
        else:
            unsanctioned.append(verdict)
    return OverrideAdjudication(sanctioned=sanctioned, unsanctioned=unsanctioned)
