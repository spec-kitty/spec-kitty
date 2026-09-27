"""The hosted drain + ledger posture reader, and the personal/repo writers.

This is the mission's foundation module: every hosted edge (relay, capability
fan-out, the status→ledger hook, the operator CLI) reads its posture through
here, and no enforcement edge is wired by this module itself.

**R-1 — no environment variable can enable drain.** Only two files can turn a
scope on: ``<repo>/.kittify/config.yaml`` → ``hosted.drain`` (repository
scope) and ``<runtime-root>/config.toml`` → ``[hosted] drain`` (personal
scope, resolved from :func:`specify_cli.paths.get_runtime_root` -- i.e.
``~/.spec-kitty`` or ``SPEC_KITTY_HOME``, **never**
:func:`kernel.paths.get_kittify_home` and never a repo-relative path). An
environment variable may only *narrow* (force off) via
:func:`specify_cli.core.env.moment_handlers_disabled_reason`. A committed
``.kitty.env`` entry or a ``SPECIFY_REPO_ROOT`` redirect cannot supply the
personal activation, because the personal file path never depends on the
resolved repository root.

**Effective drain**: ``enabled == (repo_value is True and personal_value is
True and narrowed_by is None)``. Any other combination is off, with
``reason`` naming the scope or narrower responsible.

**Fail-closed parsing**: an unparseable config file, or a present-but-non-
boolean value, counts as off for drain (never truthiness-coerced) and as the
default (``True``) for ledger -- both emit exactly one ``warnings.warn(...)``
call per file per posture evaluation, never a crash.

**No caching**: both :func:`drain_posture` and :func:`ledger_posture` open
their two small config files on every call. There is no mtime cache and no
frozen-at-import value, so drain toggled between two commands in one shell is
observed on the very next call.

**Call-site style (fixture effectiveness).** ``tests/conftest.py``'s root
autouse fixture (WP01/T004) patches the ``drain_posture`` *module attribute*
on this module. A downstream caller MUST reach the reader through the module
attribute (``from specify_cli.core import hosted_posture`` then
``hosted_posture.drain_posture()``) or through :func:`require_drain` (which
resolves ``drain_posture`` from this module's globals at call time). A local
binding via ``from specify_cli.core.hosted_posture import drain_posture``
captures the function object at import time and silently bypasses the root
fixture's monkeypatch.

Non-test caller map (S1, ``tests/architectural/test_no_dead_symbols.py``) --
every public name here gains a non-test ``src/`` caller before the mission
merges; at WP01 time these callers do not exist yet and the gate is expected
to flag them (recorded in the WP01 status note, not allowlisted):

* ``write_toml_table_key`` → ``zeitgeist_client/moments.py`` (already wired,
  WP01) + this module's :func:`set_personal_drain`.
* ``require_drain``, ``DrainDisabled``, ``DRAIN_GUIDANCE_LINE`` →
  ``cli/commands/zeitgeist.py``, ``zeitgeist_client/transport.py`` (WP02).
* ``drain_posture`` → ``status/adapters.py``, ``cli/commands/routes.py``
  (WP03).
* ``ledger_posture`` → ``status/emit.py``, ``coordination/status_transition.py`` (WP05).
* ``set_personal_drain``, ``set_repo_drain``, ``DrainPosture``,
  ``LedgerPosture``, ``personal_config_path`` → ``cli/commands/moments.py``
  (WP08; ``personal_config_path`` added at review cycle 1 to give the CLI's
  D7 unparseable-file error the same path derivation ``set_personal_drain``
  uses, instead of re-deriving ``get_runtime_root().base / "config.toml"``
  a second time at the call site).
"""

from __future__ import annotations

import tomllib
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from specify_cli.core import env as _env
from specify_cli.core.paths import locate_project_root
from specify_cli.core.toml_table import write_toml_table_key
from specify_cli.paths import get_runtime_config_toml_path

__all__ = [
    "DRAIN_GUIDANCE_LINE",
    "DrainDisabled",
    "DrainPosture",
    "LedgerPosture",
    "drain_posture",
    "ledger_posture",
    "personal_config_path",
    "require_drain",
    "set_personal_drain",
    "set_repo_drain",
]

#: The CLI guidance line an edge shows when it refuses to act because drain
#: is off (contracts/hosted-posture.md, verbatim). A module constant per the
#: CLAUDE.md Sonar S1192 rule: WP02/WP03/WP08 all reference it.
DRAIN_GUIDANCE_LINE = "Live drain is off ({reason}). Enable with: spec-kitty moments drain on [--repo]"

_REPO_CONFIG_RELATIVE = Path(".kittify") / "config.yaml"


def personal_config_path() -> Path:
    """The personal (runtime-root) ``config.toml`` path -- ``[hosted] drain``,
    D-5. Shared derivation for :func:`_read_personal_drain_key` and
    :func:`set_personal_drain` below, and for any caller (e.g. the CLI's
    unparseable-file error message) that needs the same path.

    DIRECTIVE_044: delegates to the one canonical
    ``get_runtime_config_toml_path()`` (``specify_cli.paths``) every
    "config.toml path" consumer now shares, rather than re-deriving
    ``get_runtime_root().base / "config.toml"`` locally."""
    path: Path = get_runtime_config_toml_path()
    return path


@dataclass(frozen=True)
class DrainPosture:
    """The resolved live-drain posture: whether hosted edges may fire.

    Invariant: ``enabled == (repo_value is True and personal_value is True
    and narrowed_by is None)``.
    """

    enabled: bool
    repo_value: bool | None
    repo_source: str
    personal_value: bool | None
    personal_source: str
    narrowed_by: str | None
    reason: str


@dataclass(frozen=True)
class LedgerPosture:
    """The resolved ledger-projection posture. Defaults to enabled."""

    enabled: bool
    source: str


class DrainDisabled(RuntimeError):
    """Raised by :func:`require_drain` when the effective drain posture is off.

    Carries the human-readable, already-formatted message as its sole
    ``args[0]`` -- no extra fields; a caller that needs the raw
    :class:`DrainPosture` calls :func:`drain_posture` itself.
    """


def _resolve_repo_root(project_root: Path | None) -> Path | None:
    if project_root is not None:
        return project_root
    return locate_project_root()


def _read_repo_bool_key(
    repo_root: Path | None,
    *,
    section: str,
    key: str,
    label: str,
) -> tuple[bool | None, str]:
    """``.kittify/config.yaml`` → ``<section>.<key>``, shared by the
    drain (``hosted.drain``) and ledger (``ledger.projection``) readers.
    Missing file/dir/section/key, or a value that cannot be parsed, reads as
    unset. A parse failure or a non-bool value each warn exactly once,
    naming ``label`` (the caller's own off/default wording) in the message."""
    if repo_root is None:
        return None, "no repository root resolved"
    config_path = repo_root / _REPO_CONFIG_RELATIVE
    source = str(config_path)
    if not config_path.exists():
        return None, source

    from ruamel.yaml import YAML  # noqa: PLC0415 -- lazy: pay the YAML import only when the file exists.

    try:
        data = YAML(typ="safe").load(config_path)
    except Exception:  # noqa: BLE001 -- best-effort read, matching config/path_conventions.py's
        # established tolerance for a corrupt .kittify/config.yaml: a malformed file must fail
        # closed (off/default), never raise or silently widen to "unset == on somewhere else".
        # stacklevel=4: warn -> _read_repo_bool_key -> _read_repo_drain_key/_read_repo_ledger_key
        # -> drain_posture/ledger_posture -> the caller this should attribute to.
        warnings.warn(f"{config_path}: could not parse YAML; {label}", stacklevel=4)
        return None, source

    if not isinstance(data, dict):
        return None, source
    section_value = data.get(section)
    if not isinstance(section_value, dict) or key not in section_value:
        return None, source
    value = section_value[key]
    if not isinstance(value, bool):
        warnings.warn(
            f"{config_path}: {section}.{key} is not a boolean ({value!r}); {label}",
            stacklevel=4,
        )
        return None, source
    return value, source


def _read_repo_drain_key(repo_root: Path | None) -> tuple[bool | None, str]:
    """``.kittify/config.yaml`` → ``hosted.drain``. See :func:`_read_repo_bool_key`."""
    return _read_repo_bool_key(repo_root, section="hosted", key="drain", label="treating drain as off")


def _read_repo_ledger_key(repo_root: Path | None) -> tuple[bool | None, str]:
    """``.kittify/config.yaml`` → ``ledger.projection``. See :func:`_read_repo_bool_key`."""
    return _read_repo_bool_key(repo_root, section="ledger", key="projection", label="using default (True)")


def _read_personal_drain_key() -> tuple[bool | None, str]:
    """``<runtime-root>/config.toml`` → ``[hosted] drain``, using the same
    tolerance :func:`zeitgeist_client.moments._read_section` applies:
    missing/directory/permission-denied reads as unset silently; a TOML
    syntax error reads as unset with one warning."""
    path = personal_config_path()
    source = str(path)
    try:
        with path.open("rb") as fh:
            document: dict[str, Any] = tomllib.load(fh)
    except (FileNotFoundError, IsADirectoryError, PermissionError, OSError):
        return None, source
    except tomllib.TOMLDecodeError:
        warnings.warn(f"{path}: could not parse TOML; treating drain as off", stacklevel=3)
        return None, source

    hosted = document.get("hosted")
    if not isinstance(hosted, dict) or "drain" not in hosted:
        return None, source
    value = hosted["drain"]
    if not isinstance(value, bool):
        warnings.warn(f"{path}: hosted.drain is not a boolean ({value!r}); treating drain as off", stacklevel=3)
        return None, source
    return value, source


def _resolve_drain_posture(
    *,
    repo_value: bool | None,
    repo_source: str,
    personal_value: bool | None,
    personal_source: str,
    narrowed_by: str | None,
) -> tuple[bool, str]:
    """The truth table (contracts/hosted-posture.md): narrower wins first,
    else repo-off, else personal-off, else enabled."""
    if narrowed_by is not None:
        return False, f"narrowed by {narrowed_by}"
    if repo_value is not True:
        return False, f"repository scope is off ({repo_source})"
    if personal_value is not True:
        return False, f"personal scope is off ({personal_source})"
    return True, "repository and personal scopes are both on"


def drain_posture(project_root: Path | None = None) -> DrainPosture:
    """The effective live-drain posture: whether hosted edges may fire.

    Re-reads both config files on every call (NFR-003: at most 2 config
    files per evaluation) -- no caching, no memoization on ``project_root``.
    """
    repo_root = _resolve_repo_root(project_root)
    repo_value, repo_source = _read_repo_drain_key(repo_root)
    personal_value, personal_source = _read_personal_drain_key()
    narrowed_by = _env.moment_handlers_disabled_reason()
    enabled, reason = _resolve_drain_posture(
        repo_value=repo_value,
        repo_source=repo_source,
        personal_value=personal_value,
        personal_source=personal_source,
        narrowed_by=narrowed_by,
    )
    return DrainPosture(
        enabled=enabled,
        repo_value=repo_value,
        repo_source=repo_source,
        personal_value=personal_value,
        personal_source=personal_source,
        narrowed_by=narrowed_by,
        reason=reason,
    )


def ledger_posture(project_root: Path | None = None) -> LedgerPosture:
    """The effective ledger-projection posture. Defaults to enabled (``True``)
    when the key is absent, the file is missing, or the value cannot be
    parsed as a boolean. ``source`` always names the config path (or "no
    repository root resolved") the reader consulted -- even on the
    default-``True`` path -- so an operator can tell a genuinely absent file
    apart from one that was read but held an invalid value (WP08 `drain
    status`)."""
    repo_root = _resolve_repo_root(project_root)
    value, source = _read_repo_ledger_key(repo_root)
    if value is None:
        return LedgerPosture(enabled=True, source=source)
    return LedgerPosture(enabled=value, source=source)


def require_drain(context: str) -> None:
    """Raise :class:`DrainDisabled` when drain is off; return ``None``
    otherwise. One call site per edge instead of re-deriving the posture and
    the guidance text each time."""
    posture = drain_posture()
    if not posture.enabled:
        raise DrainDisabled(f"{context}: {DRAIN_GUIDANCE_LINE.format(reason=posture.reason)}")


def set_personal_drain(enabled: bool) -> Path:
    """Persist ``[hosted] drain = enabled`` to the personal (runtime-root)
    ``config.toml``. Uses ``strict=True`` (D7): the file also carries
    ``[sync].server_url``, so an unparseable existing file raises
    (re-raising ``tomllib.TOMLDecodeError``) instead of being silently
    replaced with an empty document that would drop the sync endpoint."""
    path = personal_config_path()
    return write_toml_table_key(path, table="hosted", key="drain", value=enabled, strict=True)


def set_repo_drain(project_root: Path, enabled: bool) -> Path:
    """Persist ``hosted.drain: enabled`` to ``<project_root>/.kittify/config.yaml``,
    preserving every other key and any comments via a ruamel round-trip load
    (``.kittify/`` must already exist for this to be a Spec Kitty repo; a
    missing ``config.yaml`` itself starts from an empty mapping).

    Intentionally fail-loud (mirroring D7's ``set_personal_drain``, though via
    a different mechanism): an existing but unparseable ``config.yaml``
    propagates ruamel's ``YAMLError`` rather than being silently replaced by
    an empty document, so a hand-edited repo config with a real syntax error
    is never clobbered. Nothing is written in that case -- the raise happens
    before ``write_mapping_atomic`` is reached."""
    from ruamel.yaml import YAML  # noqa: PLC0415 -- lazy, matching drain_posture's YAML-import discipline.
    from ruamel.yaml.comments import CommentedMap  # noqa: PLC0415

    from kernel.yaml_io import write_mapping_atomic  # noqa: PLC0415

    config_path = project_root / _REPO_CONFIG_RELATIVE
    yaml = YAML(typ="rt")
    yaml.preserve_quotes = True
    loaded: Any = yaml.load(config_path) if config_path.exists() else None
    document: CommentedMap = loaded if isinstance(loaded, CommentedMap) else CommentedMap()

    hosted = document.get("hosted")
    if not isinstance(hosted, dict):
        hosted = CommentedMap()
        document["hosted"] = hosted
    hosted["drain"] = enabled

    write_mapping_atomic(document, config_path, mkdir=False)
    return config_path
