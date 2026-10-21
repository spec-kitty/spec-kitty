"""The activation ledger seam: vocabulary, typed load, write and the deny guard (FR-001, FR-002, FR-014, FR-020).

``.kittify/charter/activation.yaml`` is the single authority for charter
activation (ADR ``2026-10-19-1``). This module owns everything above the
kernel floor (:mod:`kernel.activation_ledger_store`):

* **Vocabulary** -- :func:`allow_key`, :func:`deny_key` and the key tuples, all
  derived from :class:`ArtifactKind` (C-004).
* **Typed load** -- :func:`load_activation_ledger` returns an
  :class:`ActivationLedger` from whichever source the kernel resolver names.
  A ``LEDGER`` source is validated (L1: an unknown non-deny key fails closed;
  L2: every value is a list of strings, ``null`` reads as absent). A
  ``LEGACY`` mapping (a ``charter.yaml`` or ``config.yaml`` full of other
  keys) is projected onto the allow keys of :data:`LEDGER_KEYS` first and
  never trips L1; a legacy ``deactivated_<kind>`` key is never applied, only
  reported (hole 6). An unmigrated project reads its legacy allow keys, and
  :func:`refuse_unmigrated_deny_write` refuses a deny write on it.
* **Write** -- :func:`prepare_ledger_write`, guarded: a write that changes a
  deny-list (compared as normalised sets) without an explicit
  :class:`DenyListChoice` raises :class:`DenyListWriteRefused` and writes
  nothing.
* **Error home** -- :class:`ActiveCharterConfigError` lives here;
  ``charter.activation.pack_context`` imports it back for its importers.
* **Diagnostics** -- :func:`ledger_findings` (``spec-kitty doctor
  charter-packs``) and :func:`required_not_in_force` (``charter list``), WP09.

Import direction (F20): this module imports only ``kernel``,
``charter.offering.artifact_kinds`` and ``charter.activation.charter_yaml_io``.
It never imports ``pack_context`` or ``pack_manager``. The diagnostics, the
migration's bundle stamp and the identity lookups import their collaborators
(``org_pack_discovery``, ``identity_index``, ``interview``, ``charter.bundle``)
lazily, inside the function that needs them, because those modules import this
one.
"""

from __future__ import annotations

import dataclasses
import sys
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar, Protocol

from kernel.activation_ledger_store import (
    ACTIVATION_LEDGER,
    ActivationLedgerFormatError,
    ActivationSource,
    ResolvedActivationSource,
    activation_ledger_path,
    legacy_keys_present,
    legacy_pointer_path,
    read_activation_ledger_raw,
    resolve_activation_source,
    top_level_keys,
)
from kernel.errors import KittyInternalConsistencyError
from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap

from charter.activation.charter_yaml_io import (
    PreparedYamlWrite,
    apply_yaml_write,
    load_charter_yaml,
    observe_yaml_input,
    prepare_charter_yaml_section,
    prepare_yaml_write,
    render_yaml_document,
)
from charter.offering.artifact_kinds import ArtifactKind
from charter.offering.drg.migration.id_normalizer import artifact_to_urn

if TYPE_CHECKING:
    from charter.activation.synthesizer.manifest import SynthesisManifest

__all__ = [
    "ActivationLedger",
    "ActiveCharterConfigError",
    "DenyListChoice",
    "DenyListWriteRefused",
    "DenySet",
    "LedgerFinding",
    "LedgerFindings",
    "LedgerMigrationPlan",
    "LedgerMigrationRefusal",
    "LedgerMigrationRefused",
    "LedgerMove",
    "RequiredOmission",
    "apply_ledger_migration",
    "config_error",
    "ledger_findings",
    "load_activation_ledger",
    "plan_ledger_migration",
    "refuse_unmigrated_deny_write",
    "required_not_in_force",
    "resolve_ledger_source",
]

_ALLOW_PREFIX = "activated_"
_DENY_PREFIX = "deactivated_"
_CONFIG_YAML_REL = ".kittify/config.yaml"
_CHARTER_POINTER_KEY = "charter"
_CHARTER_DIR = ACTIVATION_LEDGER.parent
_LEDGER_REL = ACTIVATION_LEDGER.as_posix()
#: How an operator-facing message names the activation ledger (never bare "the ledger": the Migration Ledger exists too).
_LEDGER_NAME = f"the activation ledger ({ACTIVATION_LEDGER.name})"
#: The ``charter_yaml_io`` section every activation write is prepared under.
_ACTIVATION_SECTION = "activation"
_ACTIVATED_KINDS = "activated_kinds"
_MISSION_TYPE_ACTIVATIONS = "mission_type_activations"


class ActiveCharterConfigError(KittyInternalConsistencyError):
    """Raised when the active charter configuration has an invalid shape.

    The active charter configuration is the activation ledger, or (before the
    ledger migration) ``.kittify/config.yaml`` or the ``charter.yaml`` it
    points to (#3732, ADR 2026-10-06-2 section 1, ADR 2026-10-19-1).
    """

    def __init__(self, body: str) -> None:
        super().__init__("ACTIVE_CHARTER_CONFIG_INVALID", body)


def config_error(message: str) -> ActiveCharterConfigError:
    """The legacy-surface configuration error, with its standard remediation line."""
    return ActiveCharterConfigError(
        f"{message}\nRemediation: fix .kittify/config.yaml (or the charter.yaml "
        f"it points to) or run `spec-kitty upgrade` to restore the default "
        f"active charter shape."
    )


# --------------------------------------------------------------------------- #
# Vocabulary (FR-002, C-004)
# --------------------------------------------------------------------------- #


def _activatable(kind: ArtifactKind) -> ArtifactKind:
    if not kind.activatable:
        raise ValueError(f"{kind.value} is not charter-activatable; it has no activation key")
    return kind


def allow_key(kind: ArtifactKind) -> str:
    """The ledger allow-list key of *kind* (``activated_<plural>``)."""
    return f"{_ALLOW_PREFIX}{_activatable(kind).plural}"


def deny_key(kind: ArtifactKind) -> str:
    """The ledger deny-list key of *kind* (``deactivated_<plural>``)."""
    return f"{_DENY_PREFIX}{_activatable(kind).plural}"


_ACTIVATABLE_KINDS: tuple[ArtifactKind, ...] = tuple(kind for kind in ArtifactKind if kind.activatable)

#: Per-kind allow keys, in enum order.
KIND_ALLOW_KEYS: tuple[str, ...] = tuple(allow_key(kind) for kind in _ACTIVATABLE_KINDS)
#: The two allow keys that are not artifact kinds; they get no deny-list.
NON_KIND_ALLOW_KEYS: tuple[str, ...] = (_ACTIVATED_KINDS, _MISSION_TYPE_ACTIVATIONS)
#: Per-kind deny keys, in enum order.
DENY_KEYS: tuple[str, ...] = tuple(deny_key(kind) for kind in _ACTIVATABLE_KINDS)
#: Every ledger key, in the order new keys are appended on write.
LEDGER_KEYS: tuple[str, ...] = NON_KIND_ALLOW_KEYS + KIND_ALLOW_KEYS + DENY_KEYS

_LEGACY_KEYS: frozenset[str] = frozenset(LEDGER_KEYS)
#: What a LEGACY read projects: the allow keys only; a legacy deny key is never applied (hole 6).
_LEGACY_ALLOW_KEYS: tuple[str, ...] = NON_KIND_ALLOW_KEYS + KIND_ALLOW_KEYS


# --------------------------------------------------------------------------- #
# Typed read model
# --------------------------------------------------------------------------- #

KindIds = tuple[tuple[ArtifactKind, tuple[str, ...] | None], ...]


@dataclass(frozen=True)
class ActivationLedger:
    """The typed, hashable activation state of one project (data-model.md §1)."""

    path: Path
    source: ActivationSource
    exists: bool
    activated_kinds: tuple[str, ...] | None
    mission_type_activations: tuple[str, ...] | None
    allow: KindIds
    deny: tuple[tuple[ArtifactKind, tuple[str, ...]], ...]
    unknown_deny_keys: tuple[str, ...] = ()
    stray_legacy_keys: tuple[tuple[Path, tuple[str, ...]], ...] = ()
    _unknown_deny_values: tuple[tuple[str, tuple[str, ...]], ...] = ()

    def allow_for(self, kind: ArtifactKind) -> tuple[str, ...] | None:
        """The allow state of *kind*: ``None`` when absent, else the listed ids."""
        return dict(self.allow).get(kind)

    def deny_for(self, kind: ArtifactKind) -> tuple[str, ...]:
        """The deny-list of *kind* (``()`` when nothing is denied)."""
        return dict(self.deny).get(kind, ())

    def raw(self) -> dict[str, Any]:
        """The present keys as a plain mapping, in :data:`LEDGER_KEYS` order, unknown deny keys last."""
        values: dict[str, tuple[str, ...] | None] = {
            _ACTIVATED_KINDS: self.activated_kinds,
            _MISSION_TYPE_ACTIVATIONS: self.mission_type_activations,
        }
        values.update({allow_key(kind): ids for kind, ids in self.allow})
        values.update({deny_key(kind): ids for kind, ids in self.deny})
        raw: dict[str, Any] = {key: list(ids) for key in LEDGER_KEYS if (ids := values.get(key)) is not None}
        raw.update({key: list(ids) for key, ids in self._unknown_deny_values})
        return raw


def _ids_or_error(key: str, value: Any, *, strict_ids: bool, where: str) -> tuple[str, ...] | None:
    """L2: ``None`` stays absent; a list becomes a tuple of ids; anything else fails closed."""
    if value is None:
        return None
    if not isinstance(value, list):
        message = f"Activation key '{key}' must be a list, got {type(value).__name__}."
        raise ActiveCharterConfigError(f"{message} ({where})") if strict_ids else config_error(message)
    if strict_ids and not all(isinstance(item, str) for item in value):
        raise ActiveCharterConfigError(f"Activation key '{key}' in {where} must list string ids, got {value!r}.")
    return tuple(str(item) for item in value)


def _validate_ledger_keys(data: Mapping[str, Any], where: str) -> tuple[str, ...]:
    """L1: refuse an unknown non-deny key; return the unknown deny keys (kept verbatim)."""
    unknown_deny: list[str] = []
    for key in data:
        if key in _LEGACY_KEYS:
            continue
        if isinstance(key, str) and key.startswith(_DENY_PREFIX):
            unknown_deny.append(key)
            continue
        raise ActiveCharterConfigError(f"Unknown activation ledger key {key!r} in {where}. Allowed keys: {', '.join(LEDGER_KEYS)} (and deactivated_<kind> keys).")
    return tuple(unknown_deny)


def _build_ledger(path: Path, source: ActivationSource, exists: bool, data: Mapping[str, Any], *, strict: bool) -> ActivationLedger:
    where = str(path)
    ids = {key: _ids_or_error(key, data.get(key), strict_ids=strict, where=where) for key in LEDGER_KEYS}
    unknown = _validate_ledger_keys(data, where) if strict else ()
    return ActivationLedger(
        path=path,
        source=source,
        exists=exists,
        activated_kinds=ids[_ACTIVATED_KINDS],
        mission_type_activations=ids[_MISSION_TYPE_ACTIVATIONS],
        allow=tuple((kind, ids[allow_key(kind)]) for kind in _ACTIVATABLE_KINDS),
        deny=tuple((kind, denied) for kind in _ACTIVATABLE_KINDS if (denied := ids[deny_key(kind)])),
        unknown_deny_keys=unknown,
        _unknown_deny_values=tuple((key, kept) for key in unknown if (kept := _ids_or_error(key, data[key], strict_ids=True, where=where)) is not None),
    )


# --------------------------------------------------------------------------- #
# Identity-space deny (FR-006, data-model.md §2.1, R4/R5)
# --------------------------------------------------------------------------- #


class IdentityLookup(Protocol):
    """The two identity lookups :func:`resolve_deny` needs (``IdentityIndex`` satisfies it)."""

    def declared_id(self, kind: ArtifactKind, token: str) -> str | None: ...

    def stem(self, kind: ArtifactKind, token: str) -> str | None: ...


@dataclass(frozen=True)
class DenySet:
    """One kind's effective deny, held in every spelling a reader filters by.

    A deny entry is stored as a stem, an allow entry may be a declared id and a
    DRG node is a URN; membership is tested against all three, so a stem deny
    subtracts a declared-id allow entry (R4). Hashable (``PackContext`` cache keys).
    """

    stems: frozenset[str] = frozenset()
    declared_ids: frozenset[str] = frozenset()
    urns: frozenset[str] = frozenset()

    EMPTY: ClassVar[DenySet]

    def __bool__(self) -> bool:
        return bool(self.stems or self.declared_ids or self.urns)

    def admits(self, token: str) -> bool:
        """``False`` when *token* matches any spelling of a denied id."""
        return token not in self.stems and token not in self.declared_ids and token not in self.urns

    def spellings(self) -> frozenset[str]:
        """Every spelling held (stems, declared ids and URNs)."""
        return self.stems | self.declared_ids | self.urns


DenySet.EMPTY = DenySet()


def _spell(kind: ArtifactKind, token: str, identity: IdentityLookup) -> DenySet:
    """*token*'s stem, declared id and URN; an unknown token keeps itself as the stem and mints its own URN."""
    declared = identity.declared_id(kind, token)
    if declared is None:
        return DenySet(frozenset({token}), frozenset(), frozenset({artifact_to_urn(kind.value, token)}))
    stem = identity.stem(kind, token) or token
    return DenySet(frozenset({stem}), frozenset({declared}), frozenset({f"{kind.value}:{declared}"}))


def _union(parts: Iterable[DenySet]) -> DenySet:
    stems: set[str] = set()
    declared: set[str] = set()
    urns: set[str] = set()
    for part in parts:
        stems |= part.stems
        declared |= part.declared_ids
        urns |= part.urns
    return DenySet(frozenset(stems), frozenset(declared), frozenset(urns))


def resolve_deny(kind: ArtifactKind, tokens: Iterable[str], identity: IdentityLookup) -> DenySet:
    """The :class:`DenySet` of *tokens* (deny entries of *kind*), expanded through *identity*."""
    return _union(_spell(kind, token, identity) for token in tokens)


def _effective_deny(kind: ArtifactKind, deny: Iterable[str], required_floor: Iterable[str], identity: IdentityLookup) -> DenySet:
    """``D* = resolve_deny(D) − R`` in identity space: the one effective-deny helper (ADR 2026-10-19-1 Decision 2).

    A deny entry any of whose spellings is a spelling of a required-floor id is
    dropped (a stale deny of a required id is inert); the rest are expanded.
    """
    floor = resolve_deny(kind, required_floor, identity).spellings()
    return _union(spelled for token in deny if (spelled := _spell(kind, token, identity)).spellings().isdisjoint(floor))


# --------------------------------------------------------------------------- #
# Sources
# --------------------------------------------------------------------------- #


def _read_ledger_mapping(repo_root: Path) -> dict[str, Any]:
    try:
        raw = read_activation_ledger_raw(repo_root)
    except ActivationLedgerFormatError as exc:
        raise ActiveCharterConfigError(f"{exc.body}\nRemediation: fix {_LEDGER_REL}.") from exc
    return raw or {}


def load_config_yaml(repo_root: Path) -> dict[str, Any]:
    """Read ``.kittify/config.yaml`` with today's golden texts (``{}`` when absent or empty).

    The one ``config.yaml`` reader of the activation layer:
    ``pack_context._load_config`` delegates here. The seam reads it before the
    kernel probe, so a malformed file fails with this text, not the kernel's
    format error (tolerant mode is byte-identical).
    """
    config_path = repo_root / _CONFIG_YAML_REL
    if not config_path.exists():
        return {}
    try:
        yaml = YAML()
        yaml.preserve_quotes = True
        raw: Any = yaml.load(config_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise config_error(f"Invalid YAML in {_CONFIG_YAML_REL}: {exc}") from exc
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise config_error(f"{_CONFIG_YAML_REL} root must be a mapping.")
    return dict(raw)


def _load_legacy_file(path: Path, display: str) -> dict[str, Any]:
    try:
        loaded = load_charter_yaml(path)
    except Exception as exc:
        raise config_error(f"Invalid YAML in {display}: {exc}") from exc
    if not isinstance(loaded, dict):
        raise config_error(f"{display} root must be a mapping.")
    return dict(loaded)


def _legacy_path(repo_root: Path, resolved: ResolvedActivationSource) -> Path:
    if resolved.pointer is None:
        return repo_root / _CONFIG_YAML_REL
    if not resolved.pointer_exists:
        raise config_error(f".kittify/config.yaml 'charter:' pointer names {resolved.pointer}, which does not exist.")
    return resolved.pointer


def _default_legacy_loader(repo_root: Path, path: Path) -> Mapping[str, Any]:
    if path == repo_root / _CONFIG_YAML_REL:
        return load_config_yaml(repo_root)
    return _load_legacy_file(path, str(path))


#: The remedy every unmigrated-project refusal names (FR-017).
UNMIGRATED_REMEDY = "Run `spec-kitty upgrade` (or `spec-kitty migrate activation-ledger`) to move them, then retry."


def unmigrated_deny_error(resolved: ResolvedActivationSource) -> ActiveCharterConfigError:
    """The refusal of a deny write on an unmigrated project, naming its keys, its files and the remedy."""
    keys = sorted({key for _path, file_keys in resolved.unmigrated_keys for key in file_keys})
    files = ", ".join(str(path) for path, _keys in resolved.unmigrated_keys)
    return ActiveCharterConfigError(
        f"Refused: activation keys {', '.join(keys)} in {files} have not been moved to {_LEDGER_REL}, and a "
        f"deactivation (deactivated_<kind>) is recorded only there. {UNMIGRATED_REMEDY} Nothing was written."
    )


LegacyLoader = Callable[[Path], Mapping[str, Any]]


def _resolve(repo_root: Path) -> ResolvedActivationSource:
    load_config_yaml(repo_root)
    try:
        return resolve_activation_source(repo_root, legacy_keys=_LEGACY_KEYS, pointer_key=_CHARTER_POINTER_KEY)
    except ActivationLedgerFormatError as exc:
        raise config_error(exc.body) from exc


def resolve_ledger_source(repo_root: Path) -> ResolvedActivationSource:
    """The kernel resolver's answer with this seam's errors (FR-017).

    A malformed ``config.yaml`` or legacy file raises the golden
    :class:`ActiveCharterConfigError`. ``LEDGER`` and ``LEGACY`` are returned
    for the caller to read or write (the write target keeps its own pointer
    text); an unmigrated project is ``LEGACY`` with ``unmigrated`` set.
    """
    return _resolve(repo_root)


def refuse_unmigrated_deny_write(repo_root: Path) -> None:
    """Raise :func:`unmigrated_deny_error` when *repo_root* is unmigrated (hole 2); a no-op otherwise.

    The one predicate a deny writer asks before any write and before the
    required-floor read, so a refused command writes nothing (NFR-001).
    """
    resolved = resolve_ledger_source(repo_root)
    if resolved.unmigrated:
        raise unmigrated_deny_error(resolved)


def ledger_may_hold_deny(repo_root: Path) -> bool:
    """Whether *repo_root*'s activation source can carry a deny list, without parsing a legacy file.

    A ``LEDGER`` source is small and is simply read (``True``). A ``LEGACY``
    surface (a large ``charter.yaml``) is answered from the kernel's cached
    top-level key probe: no ``deactivated_<kind>`` key means no deny list, so
    the read path skips the full parse (NFR-003). A legacy deny key answers
    ``True``, so the full read reports it (it is never applied, hole 6).
    Fails closed like :func:`resolve_ledger_source`.
    """
    resolved = resolve_ledger_source(repo_root)
    if resolved.source is not ActivationSource.LEGACY:
        return True
    try:
        keys = top_level_keys(_legacy_path(repo_root, resolved))
    except ActivationLedgerFormatError as exc:
        raise config_error(exc.body) from exc
    return any(key.startswith(_DENY_PREFIX) for key in keys)


def load_activation_ledger(repo_root: Path, *, legacy_loader: LegacyLoader | None = None, report_stray: bool = True) -> ActivationLedger:
    """The typed activation state of *repo_root*, from the source the kernel resolver names.

    *legacy_loader*, when given, replaces the default read of the legacy
    mapping (it receives *repo_root*). *report_stray* routes stray legacy keys
    beside a ledger through :func:`report_stray_legacy_keys` (the ordinary
    command read path); a doctor-style caller passes ``False`` and reads
    :attr:`ActivationLedger.stray_legacy_keys` as data.
    """
    resolved = resolve_ledger_source(repo_root)
    if resolved.source is ActivationSource.LEGACY:
        path = _legacy_path(repo_root, resolved)
        mapping = legacy_loader(repo_root) if legacy_loader is not None else _default_legacy_loader(repo_root, path)
        if report_stray:
            report_legacy_deny_keys(path, mapping)
        projected = {key: mapping[key] for key in _LEGACY_ALLOW_KEYS if key in mapping}
        return _build_ledger(path, ActivationSource.LEGACY, path.exists(), projected, strict=False)
    if report_stray:
        report_stray_legacy_keys(resolved.stray_legacy_keys)
    ledger = _build_ledger(activation_ledger_path(repo_root), ActivationSource.LEDGER, resolved.ledger_exists, _read_ledger_mapping(repo_root), strict=True)
    return _with_stray(ledger, resolved.stray_legacy_keys)


def _with_stray(ledger: ActivationLedger, stray: tuple[tuple[Path, tuple[str, ...]], ...]) -> ActivationLedger:
    return dataclasses.replace(ledger, stray_legacy_keys=stray) if stray else ledger


# --------------------------------------------------------------------------- #
# FR-020: stray legacy keys beside a ledger
# --------------------------------------------------------------------------- #

_REPORTED_STRAY: set[tuple[tuple[Path, tuple[str, ...]], ...]] = set()


def _stray_message(stray: tuple[tuple[Path, tuple[str, ...]], ...]) -> str:
    listed = "; ".join(f"{', '.join(keys)} in {path}" for path, keys in stray)
    return f"Legacy activation keys beside {_LEDGER_REL} are ignored; {_LEDGER_NAME} wins: {listed}. Remove them, or run `spec-kitty doctor charter-packs`."


def _warn_once(report: tuple[tuple[Path, tuple[str, ...]], ...], message: str) -> None:
    """Print ``Warning: <message>`` once per process for each distinct *report*.

    A plain CLI line on stderr (F10): not a Python ``UserWarning`` (whose
    rendering names an internal source path and which ``--json`` modes
    silence), and never on stdout, so JSON output stays parseable.
    """
    if report in _REPORTED_STRAY:
        return
    _REPORTED_STRAY.add(report)
    print(f"Warning: {message}", file=sys.stderr)


def report_stray_legacy_keys(stray: tuple[tuple[Path, tuple[str, ...]], ...]) -> None:
    """FR-020: warn once per process for each distinct *stray* report (legacy keys beside a ledger; the ledger wins)."""
    if stray:
        _warn_once(stray, _stray_message(stray))


def report_legacy_deny_keys(path: Path, mapping: Mapping[str, Any]) -> None:
    """Hole 6: warn once per process that the ``deactivated_<kind>`` keys of the legacy *mapping* at *path* are not applied."""
    keys = tuple(sorted(key for key in mapping if isinstance(key, str) and key.startswith(_DENY_PREFIX)))
    if keys:
        message = (
            f"{', '.join(keys)} in {path} is not applied: a deactivation is recorded only in {_LEDGER_REL}. "
            "Remove the key by hand, then run `spec-kitty upgrade` (or `spec-kitty migrate activation-ledger`)."
        )
        _warn_once(((path, keys),), message)


# --------------------------------------------------------------------------- #
# Write and the deny_change guard (FR-014)
# --------------------------------------------------------------------------- #


class DenyListChoice(StrEnum):
    """The four explicit choices that may change a deny-list (ADR 2026-10-19-1 Decision 4)."""

    ACTIVATE = "activate"
    DEACTIVATE = "deactivate"
    CASCADE_INCLUDE_DEACTIVATED = "cascade-include-deactivated"
    PRESET_FORCE = "preset-force"


class DenyListWriteRefused(ActiveCharterConfigError):
    """A ledger write would change a deny-list without an explicit :class:`DenyListChoice`."""

    def __init__(self, key: str, added: tuple[str, ...], removed: tuple[str, ...]) -> None:
        self.key = key
        self.added = added
        self.removed = removed
        super().__init__(
            f"Refused to change {key} without an explicit choice (added: {list(added)}, removed: {list(removed)}). "
            "Only charter activate/deactivate, --include-deactivated and --preset --force change a deny-list. Nothing was written."
        )


def _deny_set(value: Any) -> frozenset[str]:
    return frozenset(str(item) for item in value) if isinstance(value, list) else frozenset()


def _deny_changes(before: Mapping[str, Any], after: Mapping[str, Any]) -> tuple[tuple[str, tuple[str, ...], tuple[str, ...]], ...]:
    """Per known deny key, the ``(key, added, removed)`` ids; absent, ``[]`` and ``null`` are equal."""
    changes: list[tuple[str, tuple[str, ...], tuple[str, ...]]] = []
    for key in DENY_KEYS:
        old, new = _deny_set(before.get(key)), _deny_set(after.get(key))
        if old != new:
            changes.append((key, tuple(sorted(new - old)), tuple(sorted(old - new))))
    return tuple(changes)


def _check_write_keys(values: Mapping[str, Any], removals: tuple[str, ...]) -> None:
    unknown = (set(values) | set(removals)) - _LEGACY_KEYS
    if unknown:
        raise ValueError(f"Unknown activation ledger key(s): {sorted(unknown)}")
    overlap = sorted(set(values) & set(removals))
    if overlap:
        raise ValueError(f"Activation ledger key(s) both written and removed: {overlap}")


def _check_write_values(values: Mapping[str, Any]) -> None:
    """L2 on the write side: every written value is a list of string ids, or ``None`` (remove)."""
    for key, value in values.items():
        if value is None:
            continue
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            raise ValueError(f"Activation ledger key {key!r} must be written as a list of string ids or None, got {value!r}.")


#: What a ledger emptied by a write holds: an empty mapping. The file stays, so the
#: project still resolves ``LEDGER`` (an emptied ledger is not an unmigrated project).
_EMPTY_LEDGER = b"{}\n"


def _load_document(before: bytes | None, where: str) -> CommentedMap:
    if before is None:
        return CommentedMap()
    try:
        document = YAML().load(before)
    except Exception as exc:
        raise ActiveCharterConfigError(f"Invalid YAML in {where}: {exc}\nRemediation: fix {_LEDGER_REL}.") from exc
    if document is None:
        return CommentedMap()
    if not isinstance(document, CommentedMap):
        raise ActiveCharterConfigError(f"{where} root must be a mapping.\nRemediation: fix {_LEDGER_REL}.")
    return document


def _assign(document: CommentedMap, key: str, value: Any) -> None:
    """Set *key*, normalising deny lists (sorted, unique; empty removes the key)."""
    if key in DENY_KEYS:
        value = sorted(_deny_set(value)) or None
    if value is None:
        document.pop(key, None)
    elif document.get(key) != value:
        document[key] = value


def prepare_ledger_write(
    repo_root: Path,
    values: Mapping[str, Any],
    *,
    remove: Iterable[str] = (),
    deny_change: DenyListChoice | None = None,
) -> PreparedYamlWrite:
    """Prepare the one ledger write: *values* set (``None`` removes), *remove* deleted.

    Comments and order survive (ruamel round trip); new keys are appended in
    :data:`LEDGER_KEYS` order; an empty deny list is removed; unknown deny keys
    pass through untouched. The guard runs before anything is written: a
    changed deny-list without *deny_change* raises :class:`DenyListWriteRefused`.
    """
    removals = tuple(dict.fromkeys(remove))
    _check_write_keys(values, removals)
    _check_write_values(values)
    target = activation_ledger_path(repo_root)
    before = observe_yaml_input(target)
    document = _load_document(before.content, str(target))
    _build_ledger(target, ActivationSource.LEDGER, before.content is not None, document, strict=True)
    original = dict(document)
    for key in LEDGER_KEYS:
        if key in values:
            _assign(document, key, values[key])
        elif key in removals:
            document.pop(key, None)
    changes = _deny_changes(original, document)
    if changes and deny_change is None:
        key, added, removed = changes[0]
        raise DenyListWriteRefused(key, added, removed)
    return prepare_yaml_write(target, _ledger_bytes(before.content, document), section=_ACTIVATION_SECTION, inputs=(before,))


def _ledger_bytes(before: bytes | None, document: CommentedMap) -> bytes:
    """The ledger's new bytes: the rendered mapping; ``{}`` when an existing ledger is emptied.

    An absent ledger that would stay empty keeps no bytes at all, so the
    prepared write is unchanged and applying it creates no file (empty writes
    are a no-op, WP08 T048).
    """
    if document:
        rendered: bytes = render_yaml_document(before, document, YAML())
        return rendered
    return _EMPTY_LEDGER if before is not None else b""


# --------------------------------------------------------------------------- #
# Ledger migration: the move off the legacy surfaces (FR-003/FR-004, WP08)
# --------------------------------------------------------------------------- #

#: The allow keys a migration moves; it never moves a deny key (operator ruling ``deny_writers``).
_ALLOW_KEYS: tuple[str, ...] = NON_KIND_ALLOW_KEYS + KIND_ALLOW_KEYS

#: The two refusal reasons (data-model.md §11).
_REFUSAL_DIVERGENT = "divergent"
_REFUSAL_LEGACY_DENY_KEY = "legacy_deny_key"


@dataclass(frozen=True)
class LedgerMigrationRefusal:
    """Why the move refuses: the key, the files that disagree (or hold it), and the reason."""

    key: str
    files: tuple[Path, ...]
    reason: str

    @property
    def message(self) -> str:
        """The operator-facing explanation, ending with the remedy."""
        listed = ", ".join(str(path) for path in self.files)
        if self.reason == _REFUSAL_LEGACY_DENY_KEY:
            what = f"{self.key} in {listed} is a legacy deny-list key; it was never applied and is not moved. Remove it by hand"
        else:
            what = f"{self.key} differs between {listed}. Make the files agree, or remove the stale copy"
        rerun = "`spec-kitty migrate activation-ledger` or `spec-kitty upgrade`"
        return f"Refused to move the activation keys to {_LEDGER_REL}: {what}, then run {rerun} again. Nothing was written."


class LedgerMigrationRefused(ActiveCharterConfigError):
    """:func:`apply_ledger_migration` was given a refused plan; nothing was written."""

    def __init__(self, refusal: LedgerMigrationRefusal) -> None:
        self.refusal = refusal
        super().__init__(refusal.message)


@dataclass(frozen=True)
class LedgerMove:
    """One key leaving one legacy file for the ledger."""

    key: str
    source: Path
    target: Path


@dataclass(frozen=True)
class LedgerMigrationPlan:
    """The pure plan of the move (:func:`plan_ledger_migration`); apply it with :func:`apply_ledger_migration`.

    ``ledger_values`` are the allow keys written into the ledger, verbatim
    (no stem normalisation, no de-duplication). ``strips`` are the activation
    keys removed from each legacy file, authority first. The synthesis
    manifest is not part of the plan (planning only validates it): the apply
    stamps it after the ledger write and before the strips, so there is no
    separate re-stamp step to recover.
    """

    repo_root: Path
    ledger_values: tuple[tuple[str, tuple[str, ...]], ...] = ()
    strips: tuple[tuple[Path, tuple[str, ...]], ...] = ()
    refusal: LedgerMigrationRefusal | None = None

    @property
    def moves(self) -> tuple[LedgerMove, ...]:
        """Every ``(key, from-file, to-file)`` the apply performs (empty for a refusal)."""
        target = activation_ledger_path(self.repo_root)
        return tuple(LedgerMove(key, path, target) for path, keys in self.strips for key in keys)

    @property
    def noop(self) -> bool:
        """Nothing to move or strip, and no refusal (a lagging manifest stamp is not this migration's business)."""
        return self.refusal is None and not self.strips and not self.ledger_values


@dataclass(frozen=True)
class _Surface:
    path: Path
    data: Mapping[str, Any]


def _legacy_surfaces(repo_root: Path) -> tuple[_Surface, ...]:
    """The authority (pointed ``charter.yaml``, else ``config.yaml``), then the leftover ``config.yaml`` copy."""
    config_path = repo_root / _CONFIG_YAML_REL
    config = load_config_yaml(repo_root)
    pointer = legacy_pointer_path(repo_root, config.get(_CHARTER_POINTER_KEY))
    if pointer is None:
        return (_Surface(config_path, config),) if config_path.is_file() else ()
    if not pointer.exists():
        # Raised during ``spec-kitty upgrade``: re-running it cannot help, so the remedy names the pointer (F9).
        raise ActiveCharterConfigError(
            f".kittify/config.yaml 'charter:' pointer names {pointer}, which does not exist.\n"
            f"Remediation: fix the 'charter:' pointer in .kittify/config.yaml, or remove it when the "
            f"activation keys live in .kittify/config.yaml itself."
        )
    return (_Surface(pointer, _load_legacy_file(pointer, str(pointer))), _Surface(config_path, config))


def _legacy_ids(surface: _Surface, key: str) -> tuple[str, ...] | None:
    """The three-state value of *key* on *surface* (``None`` = absent or ``null``); L2 on legacy input."""
    value = surface.data.get(key)
    if value is None:
        return None
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise config_error(f"Activation key '{key}' in {surface.path} must be a list of string ids, got {value!r}.")
    return tuple(value)


def _same(left: tuple[str, ...] | None, right: tuple[str, ...] | None) -> bool:
    """Order-insensitive, three-state equality: absent, ``[]`` and a list are three distinct states.

    Ids are compared after the project-intent rename's stem mapping (F5): that
    migration runs first (``order_manifest.txt`` tie) and rewrites a legacy
    ``NNN-mission-type-scope-directive`` stem only in the activation write
    target, so a leftover copy that still holds the old stem is equal, not
    divergent. What moves is the authority's (renamed) value.
    """
    if left is None or right is None:
        return left is right
    converged_left, converged_right = _converged(left), _converged(right)
    if converged_left == left and converged_right == right:
        return sorted(left) == sorted(right)
    # The rename de-duplicates as it rewrites, so a renamed list is compared as a set.
    return set(converged_left) == set(converged_right)


def _converged(ids: tuple[str, ...]) -> tuple[str, ...]:
    """*ids* with each legacy project-intent stem replaced by its target stem."""
    from charter.activation.synthesizer.legacy_rename import _rename_stem  # lazy: the synthesizer imports this module

    return tuple(_rename_stem(token) or token for token in ids)


def _deny_refusal(surfaces: tuple[_Surface, ...]) -> LedgerMigrationRefusal | None:
    for surface in surfaces:
        for key in DENY_KEYS:
            if key in surface.data:
                return LedgerMigrationRefusal(key, (surface.path,), _REFUSAL_LEGACY_DENY_KEY)
    return None


def _key_refusal(key: str, surfaces: tuple[_Surface, ...], ledger: Mapping[str, Any] | None, ledger_path: Path) -> LedgerMigrationRefusal | None:
    """The divergence of *key*: against the ledger when it exists, else the copy against the authority."""
    held = [(surface.path, _legacy_ids(surface, key)) for surface in surfaces if key in surface.data]
    if ledger is not None:
        target = _ids_or_error(key, ledger.get(key), strict_ids=True, where=str(ledger_path))
        for path, ids in held:
            if not _same(ids, target):
                return LedgerMigrationRefusal(key, (path, ledger_path), _REFUSAL_DIVERGENT)
        return None
    if len(surfaces) < 2 or key not in surfaces[1].data:
        return None
    authority, copy = surfaces
    if not _same(_legacy_ids(copy, key), _legacy_ids(authority, key)):
        return LedgerMigrationRefusal(key, (authority.path, copy.path), _REFUSAL_DIVERGENT)
    return None


def _first_refusal(surfaces: tuple[_Surface, ...], ledger: Mapping[str, Any] | None, ledger_path: Path) -> LedgerMigrationRefusal | None:
    refusal = _deny_refusal(surfaces)
    for key in _ALLOW_KEYS:
        refusal = refusal or _key_refusal(key, surfaces, ledger, ledger_path)
    return refusal


def plan_ledger_migration(repo_root: Path) -> LedgerMigrationPlan:
    """Plan the move of *repo_root*'s legacy activation keys into the ledger (pure; nothing is written).

    The surfaces are the authority (the ``charter.yaml`` the ``config.yaml``
    pointer names, else ``config.yaml``), the leftover ``config.yaml`` copy
    beside a pointer, and an existing ledger. Each allow key is compared
    order-insensitively, keeping three states (absent, ``[]``, a list). The plan
    is a refusal, naming the key and the files, when a legacy surface holds a
    ``deactivated_<kind>`` key, when the copy differs from the authority (or
    holds a key the authority lacks), or when a legacy key differs from an
    existing ledger. Otherwise every legacy key is stripped, and the
    authority's keys are written verbatim when no ledger exists yet.
    """
    ledger_path = activation_ledger_path(repo_root)
    surfaces = _legacy_surfaces(repo_root)
    ledger = _read_ledger_mapping(repo_root) if ledger_path.is_file() else None
    if ledger is not None:
        _build_ledger(ledger_path, ActivationSource.LEDGER, True, ledger, strict=True)
    refusal = _first_refusal(surfaces, ledger, ledger_path)
    if refusal is not None:
        return LedgerMigrationPlan(repo_root, refusal=refusal)
    strips = tuple((surface.path, keys) for surface in surfaces if (keys := tuple(key for key in _ALLOW_KEYS if key in surface.data)))
    values: tuple[tuple[str, tuple[str, ...]], ...] = ()
    if ledger is None and surfaces:
        values = tuple((key, ids) for key in _ALLOW_KEYS if (ids := _legacy_ids(surfaces[0], key)) is not None)
    if strips or values:
        _stampable_manifest(repo_root)  # F8: an unreadable manifest refuses here, before the apply writes anything
    return LedgerMigrationPlan(repo_root, values, strips, None)


def _strip(path: Path, keys: tuple[str, ...]) -> PreparedYamlWrite:
    """Remove *keys* from *path*, every other line kept; a file left with no key becomes ``{}``."""
    if top_level_keys(path) <= set(keys):
        # Removing every key leaves no mapping for the span-preserving renderer to keep.
        return prepare_yaml_write(path, _EMPTY_LEDGER, section=_ACTIVATION_SECTION, inputs=(observe_yaml_input(path),))
    return prepare_charter_yaml_section(path, _ACTIVATION_SECTION, {}, remove=keys)


def _prospective_bundle_hash(repo_root: Path, charter_bytes: bytes | None) -> str | None:
    """The ``bundle_content_hash`` the bundle will have once the move is complete.

    Computed by the single hash recipe (:func:`charter.bundle.compute_bundle_content_hash`,
    C-005) over a scratch copy of the bundle's hashed files and the ledger as it
    is on disk now, with ``charter.yaml`` replaced by *charter_bytes* when it is
    about to be stripped. This module never re-implements the recipe.
    """
    import tempfile

    from charter.bundle import BUNDLE_CONTENT_HASH_FILES, CHARTER_YAML, compute_bundle_content_hash

    charter_dir = repo_root / _CHARTER_DIR
    with tempfile.TemporaryDirectory() as scratch:
        scratch_dir = Path(scratch) / _CHARTER_DIR
        scratch_dir.mkdir(parents=True)
        for name in (*BUNDLE_CONTENT_HASH_FILES, ACTIVATION_LEDGER.name):
            if (charter_dir / name).is_file():
                (scratch_dir / name).write_bytes((charter_dir / name).read_bytes())
        if charter_bytes is not None:
            (Path(scratch) / CHARTER_YAML).write_bytes(charter_bytes)
        digest: str | None = compute_bundle_content_hash(Path(scratch))
        return digest


def _stampable_manifest(repo_root: Path) -> SynthesisManifest | None:
    """The synthesis manifest when it carries a stamp to keep in parity, else ``None``.

    Read in the plan phase as well (F8): a manifest that does not validate
    refuses the move before anything is written, naming the manifest.
    """
    from pydantic import ValidationError
    from ruamel.yaml.error import YAMLError

    from charter.activation.synthesizer.manifest import MANIFEST_PATH, load_yaml

    manifest_path = repo_root / MANIFEST_PATH
    if not manifest_path.is_file():
        return None
    try:
        manifest = load_yaml(manifest_path)
    except (ValidationError, YAMLError, OSError, UnicodeDecodeError) as exc:
        raise ActiveCharterConfigError(
            f"The synthesis manifest {MANIFEST_PATH} is unreadable, so the activation keys cannot be moved to "
            f"{_LEDGER_REL} with its bundle_content_hash kept in parity: {exc}\n"
            f"Remediation: fix or regenerate {MANIFEST_PATH} (`spec-kitty charter synthesize`), then retry. Nothing was written."
        ) from exc
    if manifest.built_in_only or manifest.bundle_content_hash is None:
        return None
    return manifest


def _stamp_manifest(repo_root: Path, bundle_hash: str) -> bool:
    """Set the synthesis manifest's ``bundle_content_hash`` to *bundle_hash* (the checks of ``restamp_bundle_hash``).

    No-op (``False``) without a manifest, for a built-in-only seed or an
    unstamped manifest, and when the stamp already equals *bundle_hash*.
    """
    from charter.activation.synthesizer.manifest import MANIFEST_PATH, finalize_manifest
    from charter.activation.synthesizer.synthesize_pipeline import canonical_yaml

    manifest = _stampable_manifest(repo_root)
    if manifest is None or manifest.bundle_content_hash == bundle_hash:
        return False
    stamped = finalize_manifest(manifest.model_copy(update={"bundle_content_hash": bundle_hash}))
    (repo_root / MANIFEST_PATH).write_text(canonical_yaml(stamped.model_dump(mode="python")).decode("utf-8"), encoding="utf-8")
    return True


def _stamp_before_strips(repo_root: Path, prepared: tuple[tuple[Path, PreparedYamlWrite], ...]) -> Path | None:
    """Stamp the manifest with the hash the bundle has once the ledger is written and *prepared* are applied (F3).

    Runs after the ledger write and before any strip, whichever legacy file
    the keys came from: the ledger is in the bundle hash, so moving keys out
    of ``config.yaml`` alone also changes it. A run that stops between the
    stamp and the strips still has the legacy keys on disk, so ``detect()``
    stays True and the re-run strips them: the stamp itself is never a
    recovery trigger. Returns the manifest path when it was written.
    """
    from charter.activation.synthesizer.manifest import MANIFEST_PATH
    from charter.bundle import CHARTER_YAML

    charter = (repo_root / CHARTER_YAML).resolve()
    charter_bytes = next((write.desired_bytes for path, write in prepared if path.resolve() == charter), None)
    bundle_hash = _prospective_bundle_hash(repo_root, charter_bytes)
    if bundle_hash is None or not _stamp_manifest(repo_root, bundle_hash):
        return None
    manifest: Path = repo_root / MANIFEST_PATH
    return manifest


def apply_ledger_migration(repo_root: Path, plan: LedgerMigrationPlan) -> tuple[Path, ...]:
    """Apply *plan*: (a) the ledger write (allow keys only), (b) the manifest stamp, (c) per legacy file its strip.

    (b) stamps the synthesis manifest with the hash the bundle has after (a)
    and (c), whichever file the keys leave. Each step is idempotent, and every
    crash window leaves a legacy key behind, so the next run completes the
    move (the ledger then exists and the equal legacy keys are stripped). A
    refused plan raises :class:`LedgerMigrationRefused`; a plan that no longer
    matches the files raises ``ValueError("precondition_changed")``; a
    synthesis manifest that does not validate raises
    :class:`ActiveCharterConfigError` (from the plan). Nothing is written in
    any of these cases. Returns the files written.
    """
    if plan.refusal is not None:
        raise LedgerMigrationRefused(plan.refusal)
    if plan_ledger_migration(repo_root) != plan:
        raise ValueError(f"precondition_changed: {repo_root} changed since the move to {_LEDGER_NAME} was planned")
    written: list[Path] = []
    if plan.ledger_values and apply_yaml_write(prepare_ledger_write(repo_root, {key: list(ids) for key, ids in plan.ledger_values})):
        written.append(activation_ledger_path(repo_root))
    prepared = tuple((path, _strip(path, keys)) for path, keys in plan.strips)
    if not plan.noop:
        manifest = _stamp_before_strips(repo_root, prepared)
        if manifest is not None:
            written.append(manifest)
    for path, write in prepared:
        if apply_yaml_write(write):
            written.append(path)
    return tuple(written)


# --------------------------------------------------------------------------- #
# Doctor findings (FR-005, FR-023, data-model.md §9; WP09)
# --------------------------------------------------------------------------- #
#
# The diagnostic read of the seam. It never raises an activation error: the
# first ``ActiveCharterConfigError`` becomes ``ACTIVATION_STORE_ERROR`` (its
# body is the message). Legacy keys beside a ledger are read as *data* from the
# resolver (``stray_legacy_keys``), never through the raising read path (M2), so
# ``LEGACY_KEYS_PRESENT`` is reported in every mode. The org floor, the identity
# index and the interview answers are imported lazily (they import this module).

_STORE_ERROR = "ACTIVATION_STORE_ERROR"
_UNMIGRATED = "ACTIVATION_UNMIGRATED"
_LEGACY_DENY_KEY = "LEGACY_DENY_KEY"
_REQUIRED_OMITTED = "REQUIRED_OMITTED_BY_ALLOW_LIST"
_LEGACY_KEYS_PRESENT = "LEGACY_KEYS_PRESENT"
_DENY_UNKNOWN_ID = "DENY_UNKNOWN_ID"
_DENY_REQUIRED_ID = "DENY_REQUIRED_ID"
_DENY_SELECTED_ID = "DENY_SELECTED_ID"
_UNKNOWN_DENY_KEY = "UNKNOWN_DENY_KEY"

_ANSWERS_REL = Path(_CHARTER_DIR, "interview", "answers.yaml")
_MIGRATE_REMEDY = "`spec-kitty upgrade` or `spec-kitty migrate activation-ledger`"


@dataclass(frozen=True)
class LedgerFinding:
    """One doctor finding: ``{code, file, key, ids, message}`` (data-model.md §9)."""

    code: str
    file: str
    key: str | None
    ids: tuple[str, ...]
    message: str

    def to_dict(self) -> dict[str, Any]:
        """The JSON shape (``ids`` as a list)."""
        return {"code": self.code, "file": self.file, "key": self.key, "ids": list(self.ids), "message": self.message}


@dataclass(frozen=True)
class LedgerFindings:
    """The doctor's activation findings: errors turn the report unhealthy, warnings do not."""

    errors: tuple[LedgerFinding, ...] = ()
    warnings: tuple[LedgerFinding, ...] = ()

    def to_dict(self) -> dict[str, list[dict[str, Any]]]:
        """``{"errors": [...], "warnings": [...]}``, the ``org_drg["activation_ledger"]`` block."""
        return {"errors": [item.to_dict() for item in self.errors], "warnings": [item.to_dict() for item in self.warnings]}


@dataclass(frozen=True)
class RequiredOmission:
    """An org-required id that an explicit ``activated_<kind>`` list leaves out (FR-023, R12).

    Core semantics are unchanged (ruling ``required_always_active_divergence``):
    the explicit allow list still decides. ``packs`` are the requiring packs
    (:class:`~charter.activation.org_pack_discovery.RequiringPack`).
    """

    kind: ArtifactKind
    artifact_id: str
    packs: tuple[Any, ...]

    @property
    def pack_names(self) -> tuple[str, ...]:
        """The requiring packs' names, first-seen order."""
        return tuple(dict.fromkeys(str(pack.pack) for pack in self.packs))

    def describe_packs(self) -> str:
        """``'acme'`` or ``'base' (via 'overlay')``, comma-joined."""
        return ", ".join(str(pack.describe()) for pack in self.packs)


def _identity_index(repo_root: Path) -> IdentityLookup:
    from charter.activation.identity_index import IdentityIndex  # identity_index imports this module

    index: IdentityLookup = IdentityIndex.build(repo_root)
    return index


def _required_provenance(repo_root: Path, kind: ArtifactKind, *, strict: bool) -> dict[str, tuple[Any, ...]]:
    from charter.activation.org_pack_discovery import read_org_required_provenance  # it imports this module

    provenance: dict[str, tuple[Any, ...]] = dict(read_org_required_provenance(repo_root, kind, strict=strict))
    return provenance


def _omitted(kind: ArtifactKind, allow: tuple[str, ...], floor: Mapping[str, tuple[Any, ...]], identity: IdentityLookup) -> list[RequiredOmission]:
    """The required stems of *floor* that no spelling of *allow* names (stem comparison in identity space)."""
    allowed = resolve_deny(kind, allow, identity).spellings()
    return [RequiredOmission(kind, stem, packs) for stem, packs in floor.items() if _spell(kind, stem, identity).spellings().isdisjoint(allowed)]


Floors = Mapping[ArtifactKind, Mapping[str, tuple[Any, ...]]]


def _required_floors(repo_root: Path, *, strict: bool) -> dict[ArtifactKind, Mapping[str, tuple[Any, ...]]]:
    """Every org-requirable kind's required floor with provenance, each read once."""
    return {kind: _required_provenance(repo_root, kind, strict=strict) for kind in _ACTIVATABLE_KINDS if kind.org_requirable}


def required_not_in_force(
    repo_root: Path,
    ledger: ActivationLedger | None = None,
    *,
    strict: bool = True,
    identity: IdentityLookup | None = None,
    floors: Floors | None = None,
) -> tuple[RequiredOmission, ...]:
    """Every org-required id an explicit allow list omits, per kind in enum order (FR-023).

    Only a *present* ``activated_<kind>`` list can omit anything; an absent one
    leaves the required floor in force. *ledger* defaults to the doctor-style
    read (stray keys as data). With *strict* an unreadable required floor raises
    :class:`ActiveCharterConfigError`; ``charter list`` reads leniently.
    *floors*, when given, are the already-read floors (:func:`ledger_findings`
    reads each once); otherwise only the kinds with a present allow list are read.
    """
    state = ledger if ledger is not None else load_activation_ledger(repo_root, report_stray=False)
    omissions: list[RequiredOmission] = []
    for kind, allow in state.allow:
        if allow is None:
            continue
        floor = floors.get(kind, {}) if floors is not None else _required_provenance(repo_root, kind, strict=strict)
        if floor:
            identity = identity or _identity_index(repo_root)
            omissions.extend(_omitted(kind, allow, floor, identity))
    return tuple(omissions)


def _store_error(exc: ActiveCharterConfigError) -> LedgerFinding:
    return LedgerFinding(_STORE_ERROR, _LEDGER_REL, None, (), exc.body)


def _stray_findings(resolved: ResolvedActivationSource) -> list[LedgerFinding]:
    """``LEGACY_KEYS_PRESENT``: one error per legacy key beside the ledger (US2.4; the ledger wins)."""
    return [
        LedgerFinding(
            _LEGACY_KEYS_PRESENT,
            str(path),
            key,
            (),
            f"{key} in {path} is ignored: {_LEDGER_REL} exists and {_LEDGER_NAME} wins. Remove the key by hand, "
            f"or run `spec-kitty migrate activation-ledger`, which strips a copy equal to {_LEDGER_NAME}.",
        )
        for path, keys in resolved.stray_legacy_keys
        for key in keys
    ]


def _legacy_keys_by_file(repo_root: Path, resolved: ResolvedActivationSource) -> tuple[tuple[Path, tuple[str, ...]], ...]:
    """The activation keys on the legacy surfaces of a project without a ledger, per file (data, never raises an activation error)."""
    if resolved.unmigrated_keys:
        return resolved.unmigrated_keys
    try:
        return legacy_keys_present(repo_root, legacy_keys=_LEGACY_KEYS, pointer_key=_CHARTER_POINTER_KEY)
    except ActivationLedgerFormatError as exc:
        raise config_error(exc.body) from exc


def _listed_ids(mapping: Mapping[str, Any], key: str) -> tuple[str, ...]:
    value = mapping.get(key)
    return tuple(str(item) for item in value) if isinstance(value, list) else ()


def _legacy_key_finding(path: Path, key: str, mapping: Mapping[str, Any]) -> tuple[bool, LedgerFinding]:
    """``(is_error, finding)`` for one legacy activation key on a project without a ledger."""
    if key.startswith(_DENY_PREFIX):
        message = (
            f"{key} in {path} is a legacy deny-list key: it was never applied, and the move to {_LEDGER_NAME} refuses it. "
            f"Remove it by hand, then run {_MIGRATE_REMEDY}."
        )
        return True, LedgerFinding(_LEGACY_DENY_KEY, str(path), key, _listed_ids(mapping, key), message)
    message = f"{key} in {path} has not been moved to {_LEDGER_REL}; reads still use the legacy surface. Run {_MIGRATE_REMEDY}."
    return False, LedgerFinding(_UNMIGRATED, str(path), key, (), message)


def _legacy_surface_findings(repo_root: Path, resolved: ResolvedActivationSource) -> tuple[list[LedgerFinding], list[LedgerFinding]]:
    """``LEGACY_DENY_KEY`` errors and ``ACTIVATION_UNMIGRATED`` warnings (no ledger, legacy keys present)."""
    errors: list[LedgerFinding] = []
    warnings: list[LedgerFinding] = []
    if resolved.ledger_exists:
        return errors, warnings
    for path, keys in _legacy_keys_by_file(repo_root, resolved):
        mapping = _default_legacy_loader(repo_root, path)
        for key in keys:
            is_error, finding = _legacy_key_finding(path, key, mapping)
            (errors if is_error else warnings).append(finding)
    return errors, warnings


def _omission_findings(ledger: ActivationLedger, omissions: Iterable[RequiredOmission]) -> list[LedgerFinding]:
    """``REQUIRED_OMITTED_BY_ALLOW_LIST``: one warning per omitted id, naming its packs."""
    return [
        LedgerFinding(
            _REQUIRED_OMITTED,
            str(ledger.path),
            allow_key(item.kind),
            (item.artifact_id,),
            f"{allow_key(item.kind)} in {ledger.path} leaves out {item.artifact_id!r}, required by org pack {item.describe_packs()}: "
            f"the explicit allow list keeps it out of force. Run `spec-kitty charter activate {item.kind.operator_token} {item.artifact_id}`.",
        )
        for item in omissions
    ]


def _selected_ids(repo_root: Path) -> Mapping[str, tuple[str, ...]]:
    """``answers.selected_<plural>`` (provenance only, ADR 3.x/2026-07-18-1); ``{}`` when absent or unreadable."""
    from charter.activation.interview import read_interview_answers  # interview imports the activation layer

    try:
        interview = read_interview_answers(repo_root / _ANSWERS_REL)
    except KittyInternalConsistencyError:
        return {}
    if interview is None:
        return {}
    selected: dict[str, tuple[str, ...]] = {}
    for kind in _ACTIVATABLE_KINDS:
        value = getattr(interview, f"selected_{kind.plural}", None)
        if isinstance(value, list) and value:
            selected[kind.plural] = tuple(str(item) for item in value)
    return selected


def _requiring(kind: ArtifactKind, token: str, floor: Mapping[str, tuple[Any, ...]], identity: IdentityLookup) -> tuple[Any, ...]:
    """The packs requiring *token* (any spelling); ``()`` when it is not required."""
    spellings = _spell(kind, token, identity).spellings()
    packs: list[Any] = []
    for stem, requirers in floor.items():
        if not _spell(kind, stem, identity).spellings().isdisjoint(spellings):
            packs.extend(pack for pack in requirers if pack not in packs)
    return tuple(packs)


def _deny_finding(code: str, ledger: ActivationLedger, kind: ArtifactKind, ids: tuple[str, ...], message: str) -> LedgerFinding:
    return LedgerFinding(code, str(ledger.path), deny_key(kind), ids, message)


def _deny_kind_findings(
    ledger: ActivationLedger,
    kind: ArtifactKind,
    denied: tuple[str, ...],
    floor: Mapping[str, tuple[Any, ...]],
    identity: IdentityLookup,
) -> list[LedgerFinding]:
    """``DENY_UNKNOWN_ID`` and ``DENY_REQUIRED_ID`` for one kind's deny list."""
    key = deny_key(kind)
    findings: list[LedgerFinding] = []
    unknown = tuple(token for token in denied if identity.declared_id(kind, token) is None)
    if unknown:
        message = f"{key} in {ledger.path} lists {', '.join(unknown)}, which no layer provides. Remove the stale entry by hand."
        findings.append(_deny_finding(_DENY_UNKNOWN_ID, ledger, kind, unknown, message))
    for token in denied:
        packs = _requiring(kind, token, floor, identity)
        if packs:
            named = ", ".join(str(pack.describe()) for pack in packs)
            message = (
                f"{key} in {ledger.path} lists {token!r}, required by org pack {named}: the required floor wins, so the "
                "entry has no effect. Remove the stale entry by hand."
            )
            findings.append(_deny_finding(_DENY_REQUIRED_ID, ledger, kind, (token,), message))
    return findings


def _deny_selected_finding(
    repo_root: Path,
    ledger: ActivationLedger,
    kind: ArtifactKind,
    denied: tuple[str, ...],
    selected: tuple[str, ...],
    identity: IdentityLookup,
) -> LedgerFinding | None:
    """``DENY_SELECTED_ID`` when ``answers.selected_<plural>`` lists a denied id (any spelling)."""
    chosen = resolve_deny(kind, selected, identity).spellings()
    hits = tuple(token for token in denied if not _spell(kind, token, identity).spellings().isdisjoint(chosen))
    if not hits:
        return None
    answers = repo_root / _ANSWERS_REL
    message = (
        f"selected_{kind.plural} in {answers} lists {', '.join(hits)}, excluded by {deny_key(kind)} in {ledger.path}: "
        f"the exclusion wins (answers.yaml is provenance only). Run `spec-kitty charter activate {kind.operator_token} <id>` "
        "to clear the exclusion, or remove the stale entry by hand."
    )
    return LedgerFinding(_DENY_SELECTED_ID, str(answers), deny_key(kind), hits, message)


def _unknown_deny_key_findings(ledger: ActivationLedger) -> list[LedgerFinding]:
    """``UNKNOWN_DENY_KEY``: a ``deactivated_<x>`` for a kind this CLI does not know (P15; kept verbatim)."""
    values = dict(ledger._unknown_deny_values)
    return [
        LedgerFinding(
            _UNKNOWN_DENY_KEY,
            str(ledger.path),
            key,
            values.get(key, ()),
            f"{key} in {ledger.path} names a kind this CLI does not know; it is kept and ignored. Remove the stale entry by hand.",
        )
        for key in ledger.unknown_deny_keys
    ]


def _deny_findings(repo_root: Path, ledger: ActivationLedger, identity: IdentityLookup, floors: Floors) -> list[LedgerFinding]:
    """The deny-list warnings of a ledger: unknown, required and selected ids, unknown deny keys."""
    findings = _unknown_deny_key_findings(ledger)
    selected = _selected_ids(repo_root) if ledger.deny else {}
    for kind, denied in ledger.deny:
        findings.extend(_deny_kind_findings(ledger, kind, denied, floors.get(kind, {}), identity))
        chosen = _deny_selected_finding(repo_root, ledger, kind, denied, selected.get(kind.plural, ()), identity)
        if chosen is not None:
            findings.append(chosen)
    return findings


def _content_warnings(repo_root: Path, ledger: ActivationLedger) -> list[LedgerFinding]:
    """The warnings computed from a readable activation state.

    Every org-requirable kind's floor is read strictly exactly once, here, and
    passed down; an unreadable floor raises even when no list consults it.
    """
    floors = _required_floors(repo_root, strict=True)
    identity = _identity_index(repo_root)
    warnings = _omission_findings(ledger, required_not_in_force(repo_root, ledger, identity=identity, floors=floors))
    if ledger.source is ActivationSource.LEDGER:
        warnings.extend(_deny_findings(repo_root, ledger, identity, floors))
    return warnings


def ledger_findings(repo_root: Path) -> LedgerFindings:
    """Diagnose *repo_root*'s activation state for ``spec-kitty doctor charter-packs`` (FR-005, data-model.md §9).

    Errors: ``ACTIVATION_STORE_ERROR`` (the seam raised :class:`ActiveCharterConfigError`:
    malformed ledger, unreadable required floor; caught once, its body is the
    message), ``LEGACY_DENY_KEY`` and ``LEGACY_KEYS_PRESENT``. Warnings:
    ``ACTIVATION_UNMIGRATED``, ``REQUIRED_OMITTED_BY_ALLOW_LIST``,
    ``DENY_UNKNOWN_ID``, ``DENY_REQUIRED_ID``, ``DENY_SELECTED_ID`` and
    ``UNKNOWN_DENY_KEY``. Findings computed before a store error are kept.
    Never raises an activation error; read-only.
    """
    errors: list[LedgerFinding] = []
    warnings: list[LedgerFinding] = []
    try:
        resolved = _resolve(repo_root)
        errors.extend(_stray_findings(resolved))
        legacy_errors, legacy_warnings = _legacy_surface_findings(repo_root, resolved)
        errors.extend(legacy_errors)
        warnings.extend(legacy_warnings)
        ledger = load_activation_ledger(repo_root, report_stray=False)
        warnings.extend(_content_warnings(repo_root, ledger))
    except ActiveCharterConfigError as exc:
        errors.append(_store_error(exc))
    return LedgerFindings(tuple(errors), tuple(warnings))
