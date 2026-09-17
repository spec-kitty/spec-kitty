"""Pre-import ``.kitty.env`` two-tier loader + the single ``config.yaml``
``env_file`` pointer (FR-004/FR-004a/FR-005; ``contracts/kitty-env-loader.md``
C-LDR-1..7).

Import-purity (C-LDR-6, arch-gated by
``tests/architectural/test_bootstrap_import_purity.py``): this module's
transitive import set is stdlib + :mod:`kernel` ONLY -- no
``specify_cli.core`` import, even though that layer would otherwise be
permitted by the WP task text. :mod:`specify_cli.core` is reached only
through ``specify_cli.core.__init__``, which unconditionally imports a wide
slice of the CLI (``typer``-adjacent config, git helpers, tool checkers --
see ``specify_cli/core/__init__.py``). Importing ANY ``specify_cli.core.*``
submodule -- including the nominally tiny ``specify_cli.core.env`` -- forces
that whole package ``__init__`` to execute first, which is exactly the cost
and ordering hazard this pre-import loader exists to avoid (NFR-001). This
module needs no truthy-parsing grammar from ``core.env`` -- ``.kitty.env``
values are seeded into ``os.environ`` verbatim; interpreting them as booleans
is each downstream reader's own concern.

Call order (load-bearing): :func:`load_operator_env_file` is invoked as the
very FIRST statements of ``specify_cli/__init__.py`` -- before that module's
own ``SPEC_KITTY_TEST_MODE`` read and before any other spec-kitty submodule
is imported (C-LDR-2). Merge order is likewise load-bearing: tiers are
merged ``{**home, **repo}`` FIRST, then exactly ONE ``os.environ.setdefault``
pass over the merged result, giving precedence real-env > per-repo > home. A
naive per-tier ``os.environ.setdefault`` loop (home pass, then a separate
repo pass) would let an already-home-seeded key win over a differing repo
value on the second pass -- inverting the intended repo-over-home precedence.
Do not "simplify" back to that shape.
"""

from __future__ import annotations

import logging
import os
import re
import warnings
from collections.abc import Mapping, MutableMapping
from pathlib import Path

from kernel.env_expand import expand_env_template
from kernel.paths import get_runtime_state_root

__all__ = [
    "OperatorEnvFileUnreadableError",
    "load_operator_env_file",
    "parse_env_file",
]

logger = logging.getLogger(__name__)

_KITTY_ENV_FILENAME = ".kitty.env"
_KITTIFY_DIR_NAME = ".kittify"
_GIT_DIR_NAME = ".git"
_CONFIG_YAML_RELATIVE = Path(_KITTIFY_DIR_NAME) / "config.yaml"
_ENV_FILE_CONFIG_KEY = "env_file"
_ENV_FILE_CONFIG_PREFIX = f"{_ENV_FILE_CONFIG_KEY}:"

#: The one ``${SPEC_KITTY_HOME}`` expansion the ``env_file`` config-pointer
#: key introduces (data-model.md "ConfigPointer"); used both as the literal
#: default raw template and to build the ``env_file:`` line a fresh
#: ``config.yaml`` documents. The ``SPEC_KITTY_HOME`` locator name is spelled
#: inline (never bound to a module constant) per the home-pin census SC-002b
#: inert sub-form -- a ``NAME = "SPEC_KITTY_HOME"`` binding is forbidden
#: tree-wide (isolated-home-pin-guard-r1a); as a fragment of this larger
#: template literal it is not an assignment-bound pin.
_DEFAULT_ENV_FILE_TEMPLATE = f"${{SPEC_KITTY_HOME}}/{_KITTY_ENV_FILENAME}"

#: ``KEY=VALUE`` key grammar (T006): a bare shell-identifier. A line whose
#: key doesn't match this is malformed and is skipped + debug-logged, never
#: raised -- bootstrap must survive a malformed file (C-LDR-3).
_KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

_EXPORT_PREFIX = "export "
_COMMENT_PREFIX = "#"


class OperatorEnvFileUnreadableError(RuntimeError):
    """Raised when a configured operator env file exists but cannot be read.

    Fail-loud per FR-004a/C-LDR-3: this file gates authentication/sync
    secrets, so silently skipping a read failure (bad permission bits, bad
    encoding, a directory where a file was expected, ...) would hide an
    operator-visible misconfiguration behind a confusing downstream auth
    error instead of naming the actual cause up front.
    """

    def __init__(self, path: Path, reason: Exception) -> None:
        self.path = path
        self.reason = reason
        super().__init__(f"Cannot read operator env file {path}: {reason}")


def _strip_quotes(value: str) -> str:
    """Strip one layer of matching surrounding quotes, if present."""
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def parse_env_file(text: str) -> dict[str, str]:
    """Hand-rolled ``KEY=VALUE`` parser (T006). Never raises on malformed input.

    - Full-line ``#`` comments (after stripping leading whitespace) and
      blank lines are skipped.
    - A leading ``export `` prefix is stripped before the ``KEY=VALUE``
      split (shell-sourceable files stay parseable).
    - ``KEY`` must match ``[A-Za-z_][A-Za-z0-9_]*``; a line that doesn't
      (or that has no ``=`` at all) is skipped and logged at debug level
      rather than raising.
    - ``VALUE`` is taken literally: one layer of surrounding matching quotes
      is stripped, but no in-value ``${...}``/``$VAR`` interpolation is
      performed (that is the kernel expander's job, applied only to the
      single ``env_file`` config-pointer value, never to arbitrary
      ``.kitty.env`` values).
    """
    result: dict[str, str] = {}
    for lineno, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith(_COMMENT_PREFIX):
            continue
        if line.startswith(_EXPORT_PREFIX):
            line = line[len(_EXPORT_PREFIX) :].strip()
        if "=" not in line:
            logger.debug("Skipping malformed .kitty.env line %d (no '='): %r", lineno, raw_line)
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if not _KEY_RE.match(key):
            logger.debug("Skipping malformed .kitty.env line %d (invalid key %r)", lineno, key)
            continue
        result[key] = _strip_quotes(value.strip())
    return result


def _find_repo_root(start: Path) -> Path | None:
    """Ancestor-walk from ``start`` for the nearest ``.kittify`` or ``.git`` (T006).

    Stdlib-only, deliberately narrow mirror of the richer project-root
    resolver in ``specify_cli.core.paths`` (not importable here -- see the
    module docstring): this only needs to know where the per-repo
    ``.kitty.env`` tier and the ``config.yaml`` pointer would live.
    """
    for ancestor in (start, *start.parents):
        if (ancestor / _KITTIFY_DIR_NAME).is_dir() or (ancestor / _GIT_DIR_NAME).exists():
            return ancestor
    return None


def _read_tier(path: Path) -> dict[str, str]:
    """Read + parse one ``.kitty.env`` tier file (T008).

    Absent -> continue (empty dict, C-LDR-3) -- logged at DEBUG, not warned:
    having no ``.kitty.env`` yet is the default state for almost every
    existing project (before the WP04 provision migration creates one), so a
    user-visible ``UserWarning`` on every single CLI invocation would be pure
    noise, and -- concretely -- breaks the clean-stderr-on-import contract
    ``tests/specify_cli/bootstrap/test_env_file_loader.py``'s
    ``test_bare_import_emits_no_stderr`` and
    ``test_bare_import_without_operator_env_file_is_silent`` pin for a bare
    ``import specify_cli``. Present-but-unreadable
    (permission bits, bad encoding, a directory instead of a file, ...) ->
    :class:`OperatorEnvFileUnreadableError` (fail loud, C-LDR-3) -- that
    condition is both rare and actionable, unlike a simply-absent file. A
    ``SPEC_KITTY_HOME=`` line inside the file is dropped with a genuine
    ``UserWarning`` (locator recursion, C-LDR-4) rather than merged --
    unlike absence, an operator had to actively write that line, so it is
    both rare and worth surfacing.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        logger.debug("No operator env file found at %s; continuing without it.", path)
        return {}
    except OSError as exc:
        raise OperatorEnvFileUnreadableError(path, exc) from exc
    except UnicodeDecodeError as exc:
        raise OperatorEnvFileUnreadableError(path, exc) from exc

    parsed = parse_env_file(text)
    # Drop any SPEC_KITTY_HOME line: the locator that found this file may never
    # be redefined by it (C-LDR-4 / FR-004a). `.pop` in one statement keeps the
    # locator name to a single inline spelling (home-pin census SC-002b forbids
    # binding it to a constant).
    if parsed.pop("SPEC_KITTY_HOME", None) is not None:
        warnings.warn(
            f"{path} defines SPEC_KITTY_HOME; ignoring that line (the locator that finds this file cannot be redefined by it).",
            UserWarning,
            stacklevel=3,
        )
    return parsed


def _read_config_env_file_pointer(repo_root: Path | None) -> str | None:
    """Read ONLY the top-level ``env_file:`` key from ``.kittify/config.yaml`` (T007).

    Deliberately not a full YAML parse (C-LDR-5: "no full model load; do not
    choke the ~30 config readers") -- a targeted scan for the TOP-LEVEL
    (zero-indent -- i.e. not nested under ``doctrine:`` or any other
    section) ``env_file:`` key, stdlib-only. This keeps the key outside
    ``charter.offering.drg.org_pack_config.PackRegistry``'s ``extra="forbid"``
    model, which validates only the ``charter.offering.org`` subsection of this same
    file (``src/charter/offering/drg/org_pack_config.py:307``) -- a sibling
    top-level key is invisible to it.

    Returns the raw (unexpanded) value, or ``None`` when there's no repo, no
    readable config file, no such key, or the key's value is blank.
    This optional import-time pointer probe must not disable repair commands;
    required config-content reads report corruption at their own boundary.
    """
    if repo_root is None:
        return None
    config_path = repo_root / _CONFIG_YAML_RELATIVE
    try:
        text = config_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    for raw_line in text.splitlines():
        if not raw_line.startswith(_ENV_FILE_CONFIG_PREFIX):
            continue
        value = raw_line[len(_ENV_FILE_CONFIG_PREFIX) :].strip()
        # Strip a trailing inline comment, then one layer of quotes -- mirrors
        # the .kitty.env value grammar above.
        value = value.split(" #", 1)[0].strip()
        return _strip_quotes(value) or None
    return None


def _resolve_home_tier_path(repo_root: Path | None, environ: Mapping[str, str]) -> Path:
    """Resolve the single ``env_file`` pointer to an absolute path (T007).

    Default when the key/file is absent: ``<state-root>/.kitty.env``
    (C-LDR-7). The one ``${SPEC_KITTY_HOME}`` token this key introduces is
    expanded via :func:`kernel.env_expand.expand_env_template` with the
    state-root default supplied through its ``environ`` parameter --
    ``kernel.env_expand``'s own ``inject_defaults=True`` registry only knows
    ``${SPEC_KITTY_PACKS_ROOT}`` (WP01-owned; not this WP's to extend), so
    the ``SPEC_KITTY_HOME`` default is supplied here instead, only when
    ``environ`` doesn't already carry one.
    """
    raw = _read_config_env_file_pointer(repo_root) or _DEFAULT_ENV_FILE_TEMPLATE
    effective_environ = dict(environ)
    effective_environ.setdefault("SPEC_KITTY_HOME", str(get_runtime_state_root()))
    expanded = expand_env_template(raw, inject_defaults=True, environ=effective_environ)
    return Path(expanded)


def load_operator_env_file(
    *,
    start: Path | None = None,
    environ: MutableMapping[str, str] | None = None,
) -> None:
    """Seed the two-tier ``.kitty.env`` into ``environ`` (FR-004/FR-004a).

    Must run as the FIRST statements of ``specify_cli/__init__.py`` -- see
    the module docstring for why (C-LDR-2) and for the load-bearing
    merge-then-setdefault order (C-LDR-1).

    Args:
        start: Where to begin the per-repo ancestor walk. Defaults to
            ``Path.cwd()`` -- production always resolves the tier relative
            to wherever the operator invoked the CLI from. Tests pass an
            explicit ``tmp_path``-rooted directory so collection never
            wanders into the real checkout this test suite runs inside.
        environ: The mapping to read precedence from and seed via
            ``setdefault``. Defaults to the real ``os.environ`` (production
            behaviour). Tests inject a plain ``dict`` for full isolation --
            no monkeypatch/teardown needed for the merge logic itself.
    """
    target_environ: MutableMapping[str, str] = os.environ if environ is None else environ
    cwd = start if start is not None else Path.cwd()
    repo_root = _find_repo_root(cwd)

    home_path = _resolve_home_tier_path(repo_root, target_environ)
    home_values = _read_tier(home_path)

    repo_values: dict[str, str] = {}
    if repo_root is not None:
        repo_path = repo_root / _KITTIFY_DIR_NAME / _KITTY_ENV_FILENAME
        repo_values = _read_tier(repo_path)

    # Merge-then-setdefault (load-bearing, see module docstring): tiers are
    # combined into ONE dict, repo overriding home, THEN a single setdefault
    # pass seeds the result -- so an already-set real-env value always wins,
    # and a repo value always wins over a differing home value.
    merged = {**home_values, **repo_values}
    for key, value in merged.items():
        target_environ.setdefault(key, value)
