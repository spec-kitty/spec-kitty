"""FR-010: refuse to classify a merge whose result git would compute with an unregistered driver.

The two merge probes in :mod:`specify_cli.consolidation.git_probes`
(:func:`~specify_cli.consolidation.git_probes.n_way_merge_blob` and
:func:`~specify_cli.consolidation.git_probes.merge_own_changed_paths`) re-run git's merge.
git honours clone-local and unreviewed merge settings while it does so: a ``merge=union``
attribute from ``$GIT_COMMON_DIR/info/attributes``, an uncommitted ``.gitattributes`` or
``core.attributesFile``; a ``merge.<name>.driver`` in any config scope (git looks user drivers
up BEFORE its built-ins, so ``merge=text`` and ``merge=binary`` can be redirected); and
``merge.default``, which re-routes every path whose attribute is ``unspecified``. Each one can
make arbitrary bytes look like a clean merge.

:func:`assert_registered_merge_behaviour` raises :class:`MergeAttributeRefused` (a
:class:`~specify_cli.consolidation.git_probes.GitProbeError`) unless every probed path merges
with git's built-in merge or with a registered spec-kitty driver, with its registered command,
on its registered pattern. Every failure to read attributes or config raises too: nothing ever
reads a probe failure as "no attribute" (NFR-002).

Committed ``union`` (operator ruling 2026-11-20, option (a)): with *attributes_source* (the
claim's pre-run target tip) a built-in ``union`` is honoured only when git >= 2.40, the
committed value at that tip is the effective one, no clone-local source sets it (read with the
empty tree as source), and no ``merge.union.*`` driver is configured.

Content conversion: git runs clean filters and line-ending conversion during a merge only when
``merge.renormalize`` is on, and a hostile clean filter can then rewrite either side into a hand
resolution. An effective ``merge.renormalize`` (any scope or the environment) refuses, naming the
cause; ``filter``, ``ident`` and ``working-tree-encoding`` attributes alone are inert in a merge
and are not refused (git-lfs repositories keep working). The probes also run git with
:func:`pinned_merge_env` (the lane-consolidation pipeline's env under :func:`merge_probe_env`), which pins :data:`MERGE_PROBE_CONFIG_PINS` (``merge.directoryRenames``,
``merge.renames``, ``diff.algorithm``, ``merge.conflictStyle``, ``merge.renormalize=false``)
over every other config source, so a value changed after the guard's read cannot take effect.

Cost (NFR-001): one batched ``git check-attr --stdin merge`` per call (three when a committed
``union`` is judged), plus targeted ``git config --get`` reads (``merge.renormalize``,
``merge.default`` and the names in play; never a name listing, since a value may span lines),
read live on every call: the run's read cache cannot see global, system or ``include.path``
config, so a cached answer could go stale mid-run (#5604 review fold I2).
"""

from __future__ import annotations

import os
import re
import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from kernel.git.read_cache import Depends, cached_git_read
from specify_cli.consolidation.git_probes import GitProbeError
from specify_cli.git.merge_tree_probe import check_attr_source_available

#: ``MergeAttributeRefused`` stays out of ``__all__`` until a src caller needs it; callers catch ``GitProbeError``.
__all__ = [
    "assert_registered_merge_behaviour",
    "check_merge_attributes",
    "committed_attributes_source",
    "pinned_merge_env",
]

#: Attribute values that are git's built-in merge with no user-driver lookup: ``merge`` set
#: (the text merge) and ``-merge`` (keep ours, conflict). Neither can forge bytes.
_BUILTIN_STATES = frozenset({"set", "unset"})

#: Built-in driver names that a user ``merge.<name>.driver`` overrides.
_OVERRIDABLE_BUILTINS = frozenset({"text", "binary"})

#: The built-in value a committed ``.gitattributes`` may set (operator ruling (a)).
_COMMITTABLE_BUILTIN = "union"

_MERGE_DEFAULT_KEY = "merge.default"
_DRIVER = "driver"
_RECURSIVE = "recursive"

_UNSPECIFIED = "unspecified"

_RENORMALIZE_KEY = "merge.renormalize"

#: Config every merge probe runs with, whatever any config scope or the environment says (review
#: cycle 1): a user ``merge.directoryRenames=true`` turns a file-location conflict into a clean
#: merge, ``merge.renames`` and ``diff.algorithm`` change what the automatic merge is, and
#: ``merge.conflictStyle`` changes the conflicted content a re-merge compares against, and
#: ``merge.renormalize`` runs each side through clean filters (review cycle 2: pinned off, so a
#: renormalize turned on after the guard's read cannot launder through a filter). One table
#: for every merge a verdict depends on (the probes; later the incorporate merge and the printed
#: review command), so they cannot drift.
MERGE_PROBE_CONFIG_PINS: tuple[tuple[str, str], ...] = (
    ("merge.directoryRenames", "conflict"),
    ("merge.renames", "true"),
    ("diff.algorithm", "myers"),
    ("merge.conflictStyle", "merge"),
    ("merge.renormalize", "false"),
)

_REFUSAL_TAIL = "refusing to classify a merge whose resolution git would compute with an unregistered driver"

#: Driver names the guard reads config for: built-ins and registry keys only, so a name is always a literal regex.
_CONFIG_NAME = re.compile(r"^[a-z0-9-]+$")


class MergeAttributeRefused(GitProbeError):
    """An effective merge attribute or driver for a probed path is not git's built-in merge or a registered driver."""


@dataclass(frozen=True)
class RegisteredDriver:
    """One registry row: ``merge=<config_key>`` on *pattern* runs *command*."""

    config_key: str
    command: str
    pattern: str


@dataclass(frozen=True)
class DriverConfig:
    """The configured ``merge.<name>.*`` keys of one driver name: its command, whether ``recursive`` is set, whether any key is."""

    driver: str | None = None
    recursive: bool = False
    any_key: bool = False


@dataclass(frozen=True)
class MergeConfig:
    """The effective merge config the guard judges: ``merge.default`` and each driver name in play."""

    merge_default: bool = False
    names: Mapping[str, DriverConfig] = field(default_factory=dict)

    def of(self, name: str) -> DriverConfig:
        return self.names.get(name, DriverConfig())


def _refusal(path: str, value: str, detail: str = "") -> str:
    middle = f" ({detail})" if detail else ""
    return f"merge attribute '{value}' from the effective git attributes applies to {path}{middle}; {_REFUSAL_TAIL}"


def _matches_registered_pattern(pattern: str, path: str) -> bool:
    """gitattributes wildmatch of *path* against a registry *pattern*, for exactly the tokens the registry uses.

    Supported: a leading anchored ``kitty-specs/``, ``**/`` (zero or more directories), ``*`` (no
    ``/``) and literal text. Any other wildmatch token raises :class:`GitProbeError`.
    """
    if not pattern.startswith("kitty-specs/") or pattern.endswith("/**") or any(token in pattern for token in "[?\\"):
        raise GitProbeError(f"merge driver pattern {pattern!r} uses a wildmatch form the FR-010 guard cannot judge")
    regex: list[str] = []
    index = 0
    while index < len(pattern):
        if pattern.startswith("**/", index):
            regex.append("(?:[^/]+/)*")
            index += 3
        elif pattern.startswith("**", index):
            raise GitProbeError(f"merge driver pattern {pattern!r} uses a wildmatch form the FR-010 guard cannot judge")
        elif pattern[index] == "*":
            regex.append("[^/]*")
            index += 1
        else:
            regex.append(re.escape(pattern[index]))
            index += 1
    return re.fullmatch("".join(regex), path) is not None


def _registered_refusal(path: str, value: str, config: MergeConfig, registry: Sequence[RegisteredDriver]) -> str:
    """Refusal for a registered *value* on *path*, or ``""`` when the registered driver applies as shipped."""
    rows = [row for row in registry if row.config_key == value]
    if not any(_matches_registered_pattern(row.pattern, path) for row in rows):
        return _refusal(path, value, "a registered spec-kitty driver on a path outside its registered pattern")
    configured = config.of(value)
    if configured.recursive:
        return _refusal(path, value, f"git config merge.{value}.{_RECURSIVE} is set")
    shipped = rows[0].command
    if configured.driver is not None and configured.driver != shipped:
        return _refusal(path, value, f"git config merge.{value}.driver is not the registered command '{shipped}'")
    return ""


def _builtin_override_refusal(path: str, value: str, configured: DriverConfig) -> str:
    """A user ``merge.<value>.*`` entry shadows git's built-in driver of that name (git looks user drivers up first)."""
    if configured.driver is not None:
        return _refusal(path, value, f"git config merge.{value}.{_DRIVER} is set")
    if configured.recursive:
        return _refusal(path, value, f"git config merge.{value}.{_RECURSIVE} is set")
    if configured.any_key:
        return _refusal(path, value, f"git config merge.{value}.* is set")
    return ""


def _path_refusal(path: str, value: str, config: MergeConfig, registry: Sequence[RegisteredDriver]) -> str:
    """Why git's merge of *path* under attribute *value* could run an unregistered driver, or ``""`` when it cannot (pure)."""
    if value == _UNSPECIFIED:
        return _refusal(path, value, f"git config {_MERGE_DEFAULT_KEY} is set") if config.merge_default else ""
    if value in _BUILTIN_STATES:
        return ""
    if value in _OVERRIDABLE_BUILTINS:
        return _builtin_override_refusal(path, value, config.of(value))
    if any(row.config_key == value for row in registry):
        return _registered_refusal(path, value, config, registry)
    return _refusal(path, value)


def merge_probe_env(base: Mapping[str, str] | None = None) -> dict[str, str]:
    """*base* (default: this process's environment) with :data:`MERGE_PROBE_CONFIG_PINS` appended to ``GIT_CONFIG_PARAMETERS``.

    git reads ``GIT_CONFIG_PARAMETERS`` (what ``git -c`` sets) after every config file and after
    ``GIT_CONFIG_COUNT``, and the last value of a key wins, so the pins override every other
    source, an inherited ``-c`` included. Run every merge a verdict depends on with this env.
    """
    env = dict(os.environ if base is None else base)
    pins = " ".join(f"'{key}'='{value}'" for key, value in MERGE_PROBE_CONFIG_PINS)
    inherited = env.get("GIT_CONFIG_PARAMETERS", "").strip()
    env["GIT_CONFIG_PARAMETERS"] = f"{inherited} {pins}" if inherited else pins
    return env


def pinned_merge_env() -> dict[str, str]:
    """The ONE environment every merge a verdict depends on runs with (#5604 review fold A1).

    The lane-consolidation pipeline's environment authority
    (:func:`specify_cli.lanes.consolidation.make_merge_env`: the running spec-kitty's drivers first
    on ``PATH``, no two-way ``meta.json`` opt-out) with :data:`MERGE_PROBE_CONFIG_PINS` over it. The
    merge probes, the stale-lane auto-rebase and ``--incorporate`` all build their env here.
    """
    # Function-local: ``lanes.consolidation`` imports ``git_probes`` at module top, which imports this module lazily.
    from specify_cli.lanes.consolidation import make_merge_env

    return merge_probe_env(make_merge_env())


def committed_attributes_source(repo_root: Path, target_branch: str | None) -> str | None:
    """The tip of *target_branch*: the committed attributes source the guard trusts, or ``None`` (#5604 review fold I3).

    The claim trusts the target branch's pre-run tip; a merge made before the claim (the stale-lane
    auto-rebase, ``--incorporate``) trusts the target's tip as it is then, the same rule. ``None``
    (no target, or an unreadable one) honours no committed ``union`` (fail closed). Never cached:
    the tip moves.
    """
    if not target_branch:
        return None
    result = _run_git(repo_root, ["rev-parse", "--verify", "--quiet", "--end-of-options", f"refs/heads/{target_branch}^{{commit}}"])
    sha = (result.stdout or "").strip()
    return sha if result.returncode == 0 and sha else None


def _run_git(repo_root: Path, argv: Sequence[str], stdin: str | None = None) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(["git", *argv], cwd=str(repo_root), input=stdin, capture_output=True, text=True, check=False)
    except OSError as exc:
        raise GitProbeError(f"git {' '.join(argv)} could not be started: {exc}") from exc


def check_merge_attributes(repo_root: Path, paths: Sequence[str], source: str | None = None, attributes: Sequence[str] = ("merge",)) -> list[dict[str, str]]:
    """*attributes* of each of *paths*, in order, from ONE ``git check-attr --stdin`` (never cached: it reads the working tree).

    git prints one line per (path, attribute), path-major, in input order.
    """
    argv = ["check-attr", *(["--source", source] if source else []), "--stdin", *attributes]
    result = _run_git(repo_root, argv, "".join(f"{path}\n" for path in paths))
    if result.returncode != 0:
        raise GitProbeError(f"git {' '.join(argv)} exited {result.returncode}: {(result.stderr or '').strip()}")
    lines = (result.stdout or "").splitlines()
    if len(lines) != len(paths) * len(attributes):
        raise GitProbeError(f"git {' '.join(argv)} printed {len(lines)} line(s) for {len(paths)} path(s) x {len(attributes)} attribute(s)")
    per_path: list[dict[str, str]] = []
    for index, line in enumerate(lines):
        name = attributes[index % len(attributes)]
        prefix, separator, value = line.rpartition(": ")
        if not separator or not prefix.endswith(f": {name}"):
            raise GitProbeError(f"git {' '.join(argv)} printed an unexpected line: {line!r}")
        if index % len(attributes) == 0:
            per_path.append({})
        per_path[-1][name] = value.strip()
    return per_path


def _read_config(repo_root: Path, argv: Sequence[str]) -> subprocess.CompletedProcess[str]:
    """One ``git config`` read, never cached (#5604 review fold I2).

    The run's read cache fingerprints only ``.git/config`` and ``config.worktree``, while git also
    reads global, system and ``include.path`` config: a driver added there mid-run would be served
    stale to the guard and honoured by the merge. The guard's few reads are cheap; they stay live.
    """
    return _run_git(repo_root, argv)


def _config_value(repo_root: Path, key: str) -> str | None:
    """The value git uses for *key* (the last one, every scope), or ``None`` when unset. Only the output's own newline is stripped."""
    result = _read_config(repo_root, ["config", "--get", key])
    if result.returncode == 1 and not (result.stderr or "").strip():
        return None
    if result.returncode != 0:
        raise GitProbeError(f"git config --get {key} exited {result.returncode}: {(result.stderr or '').strip()}")
    output = result.stdout or ""
    return output[:-1] if output.endswith("\n") else output


def _config_section_set(repo_root: Path, name: str) -> bool:
    """True when any ``merge.<name>.*`` key is configured in any scope."""
    if not _CONFIG_NAME.match(name):
        raise GitProbeError(f"merge driver name {name!r} cannot be looked up safely")
    result = _read_config(repo_root, ["config", "--get-regexp", rf"^merge\.{name}\."])
    if result.returncode == 1 and not (result.stderr or "").strip():
        return False
    if result.returncode != 0:
        raise GitProbeError(f"git config --get-regexp ^merge\\.{name}\\. exited {result.returncode}: {(result.stderr or '').strip()}")
    return True


def _renormalize_refusal(repo_root: Path, paths: Sequence[str]) -> str:
    """Refusal when the effective ``merge.renormalize`` (every scope and the environment) is true, or ``""``.

    Renormalizing runs each side through the clean filters and line-ending conversion before the
    merge, so a clone-local filter can rewrite either side into a hand resolution.
    """
    result = _read_config(repo_root, ["config", "--get", "--type=bool", _RENORMALIZE_KEY])
    if result.returncode == 1 and not (result.stderr or "").strip():
        return ""
    if result.returncode != 0:
        raise GitProbeError(f"git config --get --type=bool {_RENORMALIZE_KEY} exited {result.returncode}: {(result.stderr or '').strip()}")
    if (result.stdout or "").strip() == "false":
        return ""
    return f"git config {_RENORMALIZE_KEY} is true for the merge of {', '.join(paths)}; it rewrites each side before git merges it; {_REFUSAL_TAIL}"


def _driver_config(repo_root: Path, name: str) -> DriverConfig:
    if not _config_section_set(repo_root, name):
        return DriverConfig()
    return DriverConfig(
        driver=_config_value(repo_root, f"merge.{name}.{_DRIVER}"),
        recursive=_config_value(repo_root, f"merge.{name}.{_RECURSIVE}") is not None,
        any_key=True,
    )


def _merge_config(repo_root: Path, values: Sequence[str], registry: Sequence[RegisteredDriver]) -> MergeConfig:
    """``merge.default`` and the driver config of every built-in or registered name among *values* (other names refuse outright)."""
    judged = _OVERRIDABLE_BUILTINS | {_COMMITTABLE_BUILTIN} | {row.config_key for row in registry}
    in_play = sorted(judged.intersection(values))
    merge_default = _UNSPECIFIED in values and _config_value(repo_root, _MERGE_DEFAULT_KEY) is not None
    return MergeConfig(merge_default=merge_default, names={name: _driver_config(repo_root, name) for name in in_play})


def _registry() -> tuple[RegisteredDriver, ...]:
    # Function-local: ``lanes.consolidation`` imports ``git_probes`` at module top, which imports this module lazily.
    from specify_cli.lanes.consolidation import registered_merge_driver_specs

    return tuple(RegisteredDriver(key, command, pattern) for key, command, pattern in registered_merge_driver_specs())


def _empty_tree(repo_root: Path) -> str:
    def read() -> subprocess.CompletedProcess[str]:
        return _run_git(repo_root, ["hash-object", "-t", "tree", "--stdin"], "")

    result = cached_git_read(repo_root, ("fr010-empty-tree",), read, depends=Depends())
    tree = (result.stdout or "").strip()
    if result.returncode != 0 or not tree:
        raise GitProbeError(f"git hash-object -t tree --stdin exited {result.returncode}: {(result.stderr or '').strip()}")
    return tree


def _committed_union_refusals(repo_root: Path, paths: Sequence[str], config: MergeConfig, attributes_source: str) -> dict[str, str]:
    """For effective ``union`` *paths*: the refusal of each one whose value is not the committed one at *attributes_source*."""
    if config.of(_COMMITTABLE_BUILTIN).any_key:
        return {path: _refusal(path, _COMMITTABLE_BUILTIN, "git config merge.union.* is set") for path in paths}
    if not check_attr_source_available(repo_root):
        return {path: _refusal(path, _COMMITTABLE_BUILTIN, "honouring a committed value needs git >= 2.40") for path in paths}
    committed = [values["merge"] for values in check_merge_attributes(repo_root, paths, source=attributes_source)]
    clone_local = [values["merge"] for values in check_merge_attributes(repo_root, paths, source=_empty_tree(repo_root))]
    refusals = {}
    for path, at_source, local in zip(paths, committed, clone_local, strict=True):
        if at_source != _COMMITTABLE_BUILTIN:
            refusals[path] = _refusal(path, _COMMITTABLE_BUILTIN, f"the committed value at {attributes_source} is '{at_source}'")
        elif local != _UNSPECIFIED:
            refusals[path] = _refusal(path, _COMMITTABLE_BUILTIN, "a clone-local attributes source sets it")
    return refusals


def _validated(paths: Sequence[str]) -> list[str]:
    unique = list(dict.fromkeys(paths))
    for path in unique:
        if not path or "\n" in path or "\r" in path or path.startswith('"'):
            raise GitProbeError(f"path {path!r} cannot be passed to git check-attr --stdin; refusing to classify its merge")
    return unique


def assert_registered_merge_behaviour(repo_root: Path, paths: Sequence[str], *, attributes_source: str | None = None) -> None:
    """Raise :class:`MergeAttributeRefused` when an effective merge attribute or driver for any of *paths* is unregistered (FR-010).

    *attributes_source* is the claim's pre-run target tip: with it, a committed ``union`` is
    honoured (module docstring); ``None`` refuses ``union`` from any source.
    """
    unique = _validated(paths)
    if not unique:
        return
    renormalize = _renormalize_refusal(repo_root, unique)
    if renormalize:
        raise MergeAttributeRefused(renormalize)
    values = [attributes["merge"] for attributes in check_merge_attributes(repo_root, unique)]
    registry = _registry()
    config = _merge_config(repo_root, values, registry)
    refusals = {path: reason for path, value in zip(unique, values, strict=True) if (reason := _path_refusal(path, value, config, registry))}
    union_paths = [path for path, value in zip(unique, values, strict=True) if value == _COMMITTABLE_BUILTIN and path in refusals]
    if union_paths and attributes_source is not None:
        committed_refusals = _committed_union_refusals(repo_root, union_paths, config, attributes_source)
        for path in union_paths:
            if path in committed_refusals:
                refusals[path] = committed_refusals[path]
            else:
                del refusals[path]  # a reviewed, committed ``union`` (operator ruling (a))
    if refusals:
        raise MergeAttributeRefused("; ".join(refusals[path] for path in unique if path in refusals))
