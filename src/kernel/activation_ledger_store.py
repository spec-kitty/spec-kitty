"""The activation ledger's floor: path, raw read, legacy scope and the one source resolver (FR-017).

``.kittify/charter/activation.yaml`` is the single authority for charter
activation (ADR ``2026-10-19-1``). This module is the layer-neutral floor every
reader builds on:

* :data:`ACTIVATION_LEDGER` / :func:`activation_ledger_path` -- the path. No
  other module spells the ledger filename; derive it from here.
* :func:`read_activation_ledger_raw` -- the raw read (``None`` when absent,
  ``{}`` for an empty file, :class:`ActivationLedgerFormatError` otherwise on
  bad content).
* :func:`legacy_activation_scope` / :func:`in_legacy_activation_scope` -- the
  upgrade-only scope in which a project without a ledger still reads its
  legacy surface.
* :func:`resolve_activation_source` -- the one resolver deciding where
  activation is read from and written to (data-model.md §5, the one-mode
  table of operator ruling ``mission_pivot_option_b``).

The kernel never raises an activation-domain error: it returns the source, the
pointer and the legacy keys it found, and each caller keeps its own error text.
Its only raise is :class:`ActivationLedgerFormatError`, from a raw read.

Layer rule: ``kernel`` imports nothing upward (no ``charter``, ``glossary``,
``runtime`` or ``specify_cli``) and spells none of their vocabulary. The legacy
activation key set and the ``config.yaml`` key naming the active
``charter.yaml`` (``pointer_key``) are therefore parameters of the resolver,
supplied by the activation seam. The ledger path names the bundle directory on
disk (``.kittify/charter/``), a filesystem-layout literal like
``kernel.charter_pack_paths``'s, not the charter package.
"""

from __future__ import annotations

import stat
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from kernel.charter_pack_paths import KITTIFY_DIRNAME
from kernel.errors import KittyInternalConsistencyError

__all__ = [
    "ACTIVATION_LEDGER",
    "ActivationLedgerFormatError",
    "ActivationSource",
    "ResolvedActivationSource",
    "activation_ledger_path",
    "in_legacy_activation_scope",
    "legacy_activation_scope",
    "legacy_keys_present",
    "read_activation_ledger_raw",
    "resolve_activation_source",
    "top_level_keys",
]

#: The activation ledger, relative to the repository root.
ACTIVATION_LEDGER = Path(KITTIFY_DIRNAME, "charter/activation.yaml")

#: ``.kittify/config.yaml``, relative to the repository root.
_CONFIG_YAML = Path(KITTIFY_DIRNAME, "config.yaml")

KeysByFile = tuple[tuple[Path, tuple[str, ...]], ...]


class ActivationLedgerFormatError(KittyInternalConsistencyError):
    """A ledger or legacy activation file is not a readable YAML mapping."""

    def __init__(self, body: str) -> None:
        super().__init__("ACTIVATION_LEDGER_FORMAT_INVALID", body)


class ActivationSource(StrEnum):
    """Where activation is read from and written to."""

    LEDGER = "ledger"
    LEGACY = "legacy"


@dataclass(frozen=True)
class ResolvedActivationSource:
    """The resolver's answer. Data only: the caller decides what to raise.

    An *unmigrated* project (no ledger, legacy activation keys, outside the
    upgrade scope) resolves ``LEGACY`` with its keys in :attr:`unmigrated_keys`,
    so a writer can refuse a deny write and the doctor can warn.
    """

    source: ActivationSource
    pointer: Path | None
    pointer_exists: bool
    ledger_exists: bool = False
    stray_legacy_keys: KeysByFile = ()
    unmigrated_keys: KeysByFile = ()

    @property
    def unmigrated(self) -> bool:
        """True for an unmigrated project: legacy keys to move, no ledger, outside the upgrade scope."""
        return bool(self.unmigrated_keys)


def activation_ledger_path(repo_root: Path) -> Path:
    """The ledger path of *repo_root*."""
    return repo_root / ACTIVATION_LEDGER


# --------------------------------------------------------------------------- #
# Raw reads
# --------------------------------------------------------------------------- #


def _safe_load_mapping(path: Path) -> Any:
    """Parse *path* (the one YAML load of this module).

    The round-trip loader, the one every activation file is written and read
    with: a ``config.yaml`` with a custom tag or a complex key, which the
    safe loader refuses, still resolves its pointer as it does today.
    """
    return YAML(typ="rt").load(path.read_bytes())


def _load_mapping(path: Path, display: str) -> dict[str, Any]:
    """Load *path* as a YAML mapping (``{}`` for an empty file), or raise the format error naming *display*."""
    try:
        loaded: Any = _safe_load_mapping(path)
    except YAMLError as exc:
        raise ActivationLedgerFormatError(f"Invalid YAML in {display}: {exc}") from exc
    if loaded is None:
        return {}
    if not isinstance(loaded, Mapping):
        raise ActivationLedgerFormatError(f"{display} root must be a mapping.")
    return dict(loaded)


def read_activation_ledger_raw(repo_root: Path) -> dict[str, Any] | None:
    """The ledger mapping, ``None`` when the file is absent, ``{}`` when it is empty."""
    path = activation_ledger_path(repo_root)
    if not path.is_file():
        return None
    return _load_mapping(path, str(path))


@dataclass(frozen=True)
class _Probe:
    keys: frozenset[str]
    #: Every top-level string value, by key: a pointer is looked up here by the caller's key.
    strings: Mapping[str, str]


#: Per-process probe cache keyed on ``(resolved path, st_mtime_ns, st_size)`` (NFR-003).
_PROBE_CACHE: dict[tuple[Path, int, int], _Probe] = {}


def _probe(path: Path, display: str) -> _Probe | None:
    """The top-level keys and string values of *path*, cached; ``None`` unless a regular file."""
    try:
        info = path.stat()
    except FileNotFoundError:
        return None
    if not stat.S_ISREG(info.st_mode):
        return None
    cache_key = (path.resolve(), info.st_mtime_ns, info.st_size)
    cached = _PROBE_CACHE.get(cache_key)
    if cached is None:
        data = _load_mapping(path, display)
        strings = {str(key): value for key, value in data.items() if isinstance(value, str)}
        cached = _Probe(frozenset(str(key) for key in data), strings)
        _PROBE_CACHE[cache_key] = cached
    return cached


def top_level_keys(path: Path) -> frozenset[str]:
    """The top-level keys of the YAML mapping at *path* (``frozenset()`` unless a regular file).

    Served from the per-process probe cache, so asking again for an unchanged
    file costs a ``stat`` (NFR-003). A malformed file raises
    :class:`ActivationLedgerFormatError`.
    """
    probe = _probe(path, str(path))
    return probe.keys if probe is not None else frozenset()


def legacy_pointer_path(repo_root: Path, value: Any) -> Path | None:
    """The path a ``config.yaml`` ``charter:`` *value* points to, or ``None`` when it is not a pointer.

    Only a *string* value is a pointer: absent (``None``) or a non-string
    legacy inline mapping is ``None``, never stringified into a bogus path. A
    relative pointer resolves against *repo_root*; existence is not checked.
    The one pointer rule: :func:`resolve_legacy_pointer` and
    ``charter.activation.pack_context.resolve_charter_yaml_pointer`` both call it.
    """
    if not isinstance(value, str):
        return None
    pointer = Path(value)
    return pointer if pointer.is_absolute() else repo_root / pointer


def resolve_legacy_pointer(repo_root: Path, *, pointer_key: str) -> tuple[Path | None, bool]:
    """The *pointer_key* pointer of ``config.yaml`` as ``(path, exists)``; never raises for a dangling one.

    *pointer_key* is the ``config.yaml`` key naming the active ``charter.yaml``,
    supplied by the activation seam (layer rule). Only a *string* value is a
    pointer: absent, or a non-string legacy inline mapping, is ``(None, False)``.
    A relative pointer resolves against *repo_root*. Existence is reported, not
    enforced.
    """
    probe = _probe(repo_root / _CONFIG_YAML, _CONFIG_YAML.as_posix())
    path = legacy_pointer_path(repo_root, probe.strings.get(pointer_key)) if probe is not None else None
    if path is None:
        return None, False
    return path, path.exists()


# --------------------------------------------------------------------------- #
# Upgrade-only legacy scope
# --------------------------------------------------------------------------- #

_LEGACY_SCOPE: ContextVar[frozenset[Path]] = ContextVar("_LEGACY_SCOPE", default=frozenset())
#: Canonical roots not resolved yet: each is resolved the first time a query names another path.
_PENDING_ROOTS: ContextVar[tuple[Callable[[], Path | None], ...]] = ContextVar("_PENDING_ROOTS", default=())

#: A canonical root, or a thunk that resolves it (``None``: no other root).
_CanonicalRoot = Path | Callable[[], Path | None]


@contextmanager
def legacy_activation_scope(repo_root: Path, canonical_root: _CanonicalRoot | None = None) -> Iterator[None]:
    """Run the body inside the upgrade scope for *repo_root* (and its canonical root). Re-entrant.

    *canonical_root* may be a thunk: it is called only when a query names a path
    other than an already-recorded root, so a scope whose body only ever asks
    about *repo_root* never resolves it (and never runs the git probe behind it).
    """
    roots = {repo_root.resolve()}
    pending = _PENDING_ROOTS.get()
    if isinstance(canonical_root, Path):
        roots.add(canonical_root.resolve())
    elif canonical_root is not None:
        pending = (*pending, canonical_root)
    token = _LEGACY_SCOPE.set(_LEGACY_SCOPE.get() | roots)
    pending_token = _PENDING_ROOTS.set(pending)
    try:
        yield
    finally:
        _PENDING_ROOTS.reset(pending_token)
        _LEGACY_SCOPE.reset(token)


def in_legacy_activation_scope(repo_root: Path) -> bool:
    """True inside a :func:`legacy_activation_scope` recorded for *repo_root*."""
    resolved = repo_root.resolve()
    if resolved in _LEGACY_SCOPE.get():
        return True
    return any(root is not None and root.resolve() == resolved for root in (thunk() for thunk in _PENDING_ROOTS.get()))


# --------------------------------------------------------------------------- #
# The one resolver
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class _Inputs:
    repo_root: Path
    pointer: Path | None
    pointer_exists: bool
    ledger_exists: bool
    legacy_keys: frozenset[str]


def _legacy_keys_present(inputs: _Inputs) -> KeysByFile:
    """Legacy activation keys in ``config.yaml`` and the pointed ``charter.yaml``, per file."""
    candidates = [inputs.repo_root / _CONFIG_YAML]
    if inputs.pointer is not None and inputs.pointer_exists:
        candidates.append(inputs.pointer)
    found: list[tuple[Path, tuple[str, ...]]] = []
    for path in candidates:
        probe = _probe(path, _CONFIG_YAML.as_posix() if path == candidates[0] else str(path))
        keys = tuple(sorted(probe.keys & inputs.legacy_keys)) if probe is not None else ()
        if keys:
            found.append((path, keys))
    return tuple(found)


def legacy_keys_present(repo_root: Path, *, legacy_keys: frozenset[str], pointer_key: str) -> KeysByFile:
    """The *legacy_keys* found on ``config.yaml`` and the ``charter.yaml`` it points to, per file.

    The resolver's own scan (the same candidates and cached probe), for a
    caller that needs the keys whatever the resolver answered: the doctor
    reports an unmigrated project in either mode. A malformed file raises
    :class:`ActivationLedgerFormatError`. *pointer_key* is as for
    :func:`resolve_legacy_pointer`.
    """
    pointer, pointer_exists = resolve_legacy_pointer(repo_root, pointer_key=pointer_key)
    return _legacy_keys_present(_Inputs(repo_root, pointer, pointer_exists, activation_ledger_path(repo_root).is_file(), legacy_keys))


def _ledger(inputs: _Inputs) -> ResolvedActivationSource:
    return ResolvedActivationSource(
        ActivationSource.LEDGER,
        inputs.pointer,
        inputs.pointer_exists,
        ledger_exists=inputs.ledger_exists,
        stray_legacy_keys=_legacy_keys_present(inputs) if inputs.ledger_exists else (),
    )


def _legacy(inputs: _Inputs, unmigrated_keys: KeysByFile = ()) -> ResolvedActivationSource:
    return ResolvedActivationSource(ActivationSource.LEGACY, inputs.pointer, inputs.pointer_exists, unmigrated_keys=unmigrated_keys)


def _one_mode(inputs: _Inputs) -> ResolvedActivationSource:
    """The one-mode table: the ledger when it exists; legacy inside the upgrade scope or for an unmigrated project; else fresh.

    A dangling ``charter:`` pointer is never fresh: the activation it names
    cannot be read, so the project stays on its legacy surface and the reader
    reports the dangling pointer, as on ``main``.
    """
    if inputs.ledger_exists:
        return _ledger(inputs)
    if in_legacy_activation_scope(inputs.repo_root) or (inputs.pointer is not None and not inputs.pointer_exists):
        return _legacy(inputs)
    present = _legacy_keys_present(inputs)
    if present:
        return _legacy(inputs, present)
    return _ledger(inputs)


def resolve_activation_source(repo_root: Path, *, legacy_keys: frozenset[str], pointer_key: str) -> ResolvedActivationSource:
    """Decide where *repo_root*'s activation lives (data-model.md §5, one mode).

    ``LEDGER`` when the ledger exists, or for a fresh project (no ledger, no
    legacy key: ``ledger_exists`` is ``False``). ``LEGACY`` inside the upgrade
    scope, and for an unmigrated project (no ledger, legacy keys, outside the
    scope), which carries its keys in ``unmigrated_keys``. *legacy_keys* is
    the activation key set a legacy surface may carry (the seam passes
    ``frozenset(LEDGER_KEYS)``); *pointer_key* is the ``config.yaml`` key
    naming the active ``charter.yaml`` (see :func:`resolve_legacy_pointer`).
    Never raises an activation-domain error; a
    malformed ``config.yaml`` or ``charter.yaml`` raises
    :class:`ActivationLedgerFormatError`.
    """
    pointer, pointer_exists = resolve_legacy_pointer(repo_root, pointer_key=pointer_key)
    inputs = _Inputs(repo_root, pointer, pointer_exists, activation_ledger_path(repo_root).is_file(), legacy_keys)
    return _one_mode(inputs)
