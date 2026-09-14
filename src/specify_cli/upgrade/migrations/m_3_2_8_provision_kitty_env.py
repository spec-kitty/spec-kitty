"""Migration: provision the per-repo ``.kitty.env`` operator env-file scaffold.

Companion to WP02's pre-import loader (``specify_cli.bootstrap.env_file``,
contracts/kitty-env-loader.md) and WP03's doctor auto-discovery seam
(``cli/commands/doctor.py``): a project that never ran ``spec-kitty init``
after the loader landed has no ``.kittify/.kitty.env`` and no ``env_file:``
config.yaml pointer to discover it from -- this migration provisions both, on
``spec-kitty upgrade``, so the loader has something to find.

**CRITICAL -- never seeds ``SPEC_KITTY_PACKS_ROOT`` (C-MIG-2).** The loader
merges the produced ``.kitty.env`` into ``os.environ`` via
``os.environ.setdefault`` (``load_operator_env_file``), so an *always-present*
``SPEC_KITTY_PACKS_ROOT=<value>`` line would flip
``kernel.paths.get_package_asset_root``'s PACKS_ROOT-vs-TEMPLATE_ROOT
precedence (``kernel/paths.py:324`` doc comment; C-R3) on every subsequent
invocation of this project, permanently and silently -- even for an operator
who never intended to override the pack root. ``SPEC_KITTY_PACKS_ROOT`` is
therefore excluded categorically: this migration never reads it, never
writes it, and never mentions it in the generated file, regardless of
whether it happens to be set in ``os.environ`` at apply time. A regression
test (``tests/specify_cli/upgrade/migrations/test_provision_kitty_env.py``)
proves ``SPEC_KITTY_TEMPLATE_ROOT`` still governs asset resolution with the
scaffold on disk.

**Secret vars are never seeded by value either.** A var in
:data:`GOVERNED_SECRET_VARS` (e.g. ``SPEC_KITTY_SAAS_TOKEN``) is emitted only
as a commented, blank template line (``# SPEC_KITTY_SAAS_TOKEN=``) -- never
the live value, even when one happens to be set in the invoking shell.
Copying a live credential into a generated file (however well-gitignored)
would still create a second at-rest copy of a secret nobody asked this
migration to relocate; the operator fills the template in by hand if they
want the per-repo tier to carry it.

**``target_version`` pinned to the installed package version, not the WP-
prescribed ``3.2.8``.** Mirrors ``m_3_2_7_heal_provenance_paths.py``'s own
documented precedent for exactly this situation:
``test_discovered_migration_targets_do_not_exceed_package_version`` skips any
migration whose ``target_version`` exceeds the installed package version
(``pyproject.toml`` is ``"3.2.6rc2"`` at authoring time), so a literal
``"3.2.8"`` would mean this migration silently never runs until a release
actually reaches 3.2.8. Both this module and the heal migration therefore
share ``target_version="3.2.6rc2"`` -- **ordering between the two is NOT
decided by the version string** (a tie), and ``MigrationRegistry.get_all()``'s
stable sort falls through to whatever order the two migration classes were
*registered* (``@MigrationRegistry.register`` fires at import time) in.

That registration order is **not** reliably ``upgrade/migrations/__init__.py:
auto_discover_migrations()``'s own alphabetical ``m_*.py`` enumeration
(which WOULD put ``m_3_2_7_heal_provenance_paths`` first by filename) --
empirically, in a real ``spec-kitty`` invocation ``cli/commands/__init__.py:
register_commands`` imports ``cli/commands/doctor.py`` while building the
full CLI surface (for ``--help`` et al.) BEFORE any subcommand body runs, and
``doctor.py``'s OWN sibling auto-discovery loop (T015) imports
``_env_file_doctor.py`` before ``_provenance_doctor.py`` (alphabetical among
``_*_doctor.py`` files: ``e`` < ``p``) -- which transitively imports *this*
module before the heal migration's, registering provision FIRST. Because
``auto_discover_migrations()`` skips re-registering a module it finds already
imported (its own documented re-registration guard), that earlier order
sticks for the rest of the process. A verbatim rerun with only this module
importable does put heal first, since without the doctor.py import racing
ahead, filename order governs -- so the ordering is genuinely
import-sequence-dependent, not a fixed contract either module can promise
on its own.

**This is safe because heal and provision are function-disjoint.** Heal
only ever touches ``.kittify/charter/charter.yaml``'s catalog and
``.kittify/agent_profiles_manifest.json``; provision only ever touches
``.kittify/.kitty.env``, ``.kittify/config.yaml``'s ``env_file`` key,
``.gitignore``, and ``.claudeignore``. Neither migration's ``detect()`` or
``apply()`` reads any file the other writes, so which one physically runs
first on a given ``spec-kitty upgrade`` has no observable effect on the
end state -- proven by
``tests/specify_cli/upgrade/migrations/test_provision_kitty_env.py``'s
order-independence regression, which applies both in each order and asserts
identical results. This module deliberately does NOT try to force a
specific relative order (e.g. via a distinct ``target_version``) precisely
because none is required.

**Ordering vs. #3381.** https://github.com/Priivacy-ai/spec-kitty/issues/3381
is an open, separate bug about the hosted-sync consent migration (FR-019)
silently dropping legacy opt-ins; a future fix there is expected to land its
own migration touching sync consent state. This module owns the *env-file
scaffold* provisioning axis only and is independently triggered (``detect()``
below never inspects sync-consent state) -- by the same function-disjoint
argument above, a future #3381 migration touching sync consent needs no
deliberate ordering relative to this one either, provided it stays disjoint
from ``.kitty.env``/``config.yaml``'s ``env_file`` key/the two ignore files.
"""

from __future__ import annotations

import contextlib
import errno
import os
import secrets
import stat
from pathlib import Path

from ruamel.yaml import YAML

from specify_cli.core.no_follow import chmod_fd
from specify_cli.gitignore_manager import GitignoreManager

from ..registry import MigrationRegistry
from .base import BaseMigration, ClaudeignorePathError, MigrationResult

MIGRATION_ID = "3.2.8_provision_kitty_env"
TARGET_VERSION = "3.2.6rc2"

_KITTIFY_DIRNAME = ".kittify"
_ENV_FILENAME = ".kitty.env"
_CONFIG_YAML_FILENAME = "config.yaml"
_GITIGNORE_FILENAME = ".gitignore"
_CLAUDEIGNORE_FILENAME = ".claudeignore"

#: The .gitignore/.claudeignore pattern for the provisioned per-repo tier
#: file (C-SEC-2: must match a rule in BOTH files).
_ENV_FILE_IGNORE_ENTRY = ".kittify/.kitty.env"

_ENV_FILE_CONFIG_KEY = "env_file"
#: Must match ``bootstrap.env_file._DEFAULT_ENV_FILE_TEMPLATE`` exactly --
#: this migration documents the loader's own default as an explicit
#: config.yaml pointer rather than leaving it implicit (T017).
_ENV_FILE_CONFIG_VALUE = "${SPEC_KITTY_HOME}/.kitty.env"

#: Vars explicitly excluded from every seeding form -- never read, never
#: written, never even named in the generated file. See the module
#: docstring's CRITICAL note: this is the one hard exclusion (C-MIG-2).
NEVER_SEED_VARS: frozenset[str] = frozenset({"SPEC_KITTY_PACKS_ROOT"})

#: Operator-settable flag/pointer vars: seeded with their CURRENT
#: ``os.environ`` value when already set at apply time, otherwise omitted
#: entirely (never invented). Mirrors ``core.secret_redaction``'s printable
#: allowlist -- these are exactly the names safe to persist and later render
#: by value.
GOVERNED_OPERATOR_VARS: tuple[str, ...] = (
    "SPEC_KITTY_HOME",
    "SPEC_KITTY_NON_INTERACTIVE",
    "SPEC_KITTY_FORCE_INTERACTIVE",
    "SPEC_KITTY_SYNC_DISABLE",
    "SPEC_KITTY_SYNC_MINIMAL_IMPORT",
    "SPEC_KITTY_NO_MOMENT_HANDLERS",
    "SPEC_KITTY_SKIP_PRE_REVIEW_GATE",
    "SPEC_KITTY_ENABLE_SAAS_SYNC",
    "SPEC_KITTY_SAAS_URL",
    "SPEC_KITTY_TEAM_SLUG",
    "SPEC_KITTY_NO_BANNER",
    "SPEC_KITTY_NO_NAG",
    "SPEC_KITTY_NO_UPGRADE_CHECK",
)

#: Secret-shaped vars: always emitted (if at all) as a commented, blank
#: template line -- see the module docstring. Never a value, whether or not
#: currently set.
GOVERNED_SECRET_VARS: tuple[str, ...] = (
    "SPEC_KITTY_SAAS_TOKEN",
    "SPEC_KITTY_ORG_TOKEN",
    "SPEC_KITTY_ORG_AUTH_HEADER",
    # #3277: the machine/CI client secret. A CI runner supplies it as a real
    # process env var or a secret file (SPEC_KITTY_MACHINE_CLIENT_SECRET_FILE)
    # -- never via a committed .kitty.env. Listed here so the provisioning
    # template and the env-file doctor both treat it as secret-shaped: a
    # commented blank template line at most, and name/presence-only reporting.
    "SPEC_KITTY_MACHINE_CLIENT_SECRET",
)


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------


def _env_file_path(project_path: Path) -> Path:
    return project_path / _KITTIFY_DIRNAME / _ENV_FILENAME


def _config_yaml_path(project_path: Path) -> Path:
    return project_path / _KITTIFY_DIRNAME / _CONFIG_YAML_FILENAME


# ---------------------------------------------------------------------------
# .kitty.env scaffold content
# ---------------------------------------------------------------------------


def _build_env_file_content() -> str:
    """Build the scaffold's text -- seeded operator vars + secret templates.

    ``SPEC_KITTY_PACKS_ROOT`` is categorically absent (see module docstring);
    it is not read from ``os.environ`` here at all, so there is no branch
    that could accidentally emit it.
    """
    lines = [
        "# Spec Kitty per-repo operator environment file.",
        f"# Provisioned by migration {MIGRATION_ID} -- see",
        "# contracts/kitty-env-loader.md and contracts/provenance-and-channel.md.",
        "#",
        "# SPEC_KITTY_PACKS_ROOT is intentionally never written here: an",
        "# always-set value flips the TEMPLATE_ROOT gate (kernel/paths.py).",
        "",
    ]
    seeded = [(var, os.environ[var]) for var in GOVERNED_OPERATOR_VARS if var in os.environ]
    for var, value in seeded:
        lines.append(f"{var}={value}")
    if seeded:
        lines.append("")

    lines.append("# Secret-shaped vars are never auto-seeded by value -- fill in by hand:")
    for var in GOVERNED_SECRET_VARS:
        lines.append(f"# {var}=")
    lines.append("")
    return "\n".join(lines)


def _env_file_missing(project_path: Path) -> bool:
    return not _env_file_path(project_path).exists()


# ---------------------------------------------------------------------------
# config.yaml env_file: pointer
# ---------------------------------------------------------------------------


def _config_env_file_pointer_missing(project_path: Path) -> bool:
    config_path = _config_yaml_path(project_path)
    if not config_path.exists():
        return True
    yaml = YAML()
    yaml.preserve_quotes = True
    with config_path.open("r", encoding="utf-8") as handle:
        data = yaml.load(handle) or {}
    return not (isinstance(data, dict) and data.get(_ENV_FILE_CONFIG_KEY))


def _write_config_env_file_pointer(project_path: Path) -> None:
    config_path = _config_yaml_path(project_path)
    yaml = YAML()
    yaml.preserve_quotes = True

    if config_path.exists():
        with config_path.open("r", encoding="utf-8") as handle:
            data = yaml.load(handle) or {}
    else:
        data = {}
        config_path.parent.mkdir(parents=True, exist_ok=True)

    if not isinstance(data, dict):
        data = {}

    data[_ENV_FILE_CONFIG_KEY] = _ENV_FILE_CONFIG_VALUE

    with config_path.open("w", encoding="utf-8") as handle:
        yaml.dump(data, handle)


# ---------------------------------------------------------------------------
# .gitignore / .claudeignore coverage (C-SEC-2)
# ---------------------------------------------------------------------------


class NonRegularIgnoreFileError(OSError):
    """Raised when a ``.gitignore``/``.claudeignore`` path is not a regular
    file -- e.g. a FIFO, a symlink, a device, or a socket.

    A FIFO named ``.gitignore``/``.claudeignore`` hangs a bare
    ``path.read_text()``/``path.write_text()`` indefinitely: ``open()`` on a
    FIFO blocks until a peer connects unless ``O_NONBLOCK`` is set, and
    nothing upstream of this module supplied a timeout. Rejecting outright
    (rather than trying to read/write it) is fail-closed and immediate.
    """


def _open_ignore_file_no_follow(path: Path, flags: int, mode: int = 0o644) -> int:
    """Open *path* for the ignore-file read/write helpers, then fail closed.

    ``O_NOFOLLOW`` refuses to traverse a final symlink component.
    ``O_NONBLOCK`` is folded in unconditionally: it is what stops the
    ``open()`` call itself from blocking forever on a FIFO (opening a FIFO
    read-only blocks until a writer connects, and opening it write-only
    blocks until a reader connects -- both unless ``O_NONBLOCK`` is set).
    It is a no-op for a genuine regular file, so always including it never
    changes behaviour on the common path.

    The ``S_ISREG`` check runs on the fd this call already has open, not on
    a separate ``path.stat()``/``is_file()`` call beforehand -- a
    check-then-open of the path is a TOCTOU window (the path can be
    swapped between the check and the open), whereas checking the already-
    open descriptor's own mode is atomic with respect to that race (mirrors
    ``coordination/atomic_write.py``'s fd-relative confinement checks).
    """
    no_follow = getattr(os, "O_NOFOLLOW", 0)
    non_blocking = getattr(os, "O_NONBLOCK", 0)
    try:
        fd = os.open(path, flags | no_follow | non_blocking, mode)
    except FileNotFoundError:
        raise
    except OSError as exc:
        if exc.errno == errno.ELOOP:
            raise NonRegularIgnoreFileError(f"Refusing to open {path}: {exc}") from exc
        raise
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise NonRegularIgnoreFileError(f"Refusing to open {path}: not a regular file")
    except BaseException:
        os.close(fd)
        raise
    return fd


def _read_ignore_file_text(path: Path) -> str:
    """Read an ignore file's full text -- "" if it does not exist yet.

    Fails closed via :class:`NonRegularIgnoreFileError` on a symlink or any
    other non-regular file (FIFO, device, socket) instead of following it or
    hanging. See :func:`_open_ignore_file_no_follow`.
    """
    try:
        fd = _open_ignore_file_no_follow(path, os.O_RDONLY)
    except FileNotFoundError:
        return ""
    with os.fdopen(fd, "r", encoding="utf-8-sig") as handle:
        return handle.read()


def _ignore_file_entries(path: Path) -> set[str]:
    return {line.strip() for line in _read_ignore_file_text(path).splitlines() if line.strip() and not line.lstrip().startswith("#")}


def _gitignore_missing_entry(project_path: Path) -> bool:
    return _ENV_FILE_IGNORE_ENTRY not in _ignore_file_entries(project_path / _GITIGNORE_FILENAME)


def _claudeignore_missing_entry(project_path: Path) -> bool:
    path = project_path / _CLAUDEIGNORE_FILENAME
    _reject_claudeignore_symlink(path)
    entries = {line.strip() for line in _read_claudeignore_no_follow(path).splitlines() if line.strip() and not line.lstrip().startswith("#")}
    return _ENV_FILE_IGNORE_ENTRY not in entries


def _reject_claudeignore_symlink(path: Path) -> None:
    """Raise ``ClaudeignorePathError`` if *path* is a symlink.

    Checks ``is_symlink()``, not ``exists()`` -- ``exists()`` follows
    symlinks and returns ``False`` for a dangling one, which would
    otherwise let a dangling-symlink ``.claudeignore`` slip past an
    ``exists()``-gated check.

    This is a fast, friendly up-front rejection only -- it is a separate
    syscall from whatever the caller does next, so it does NOT by itself
    close the window where a ``.claudeignore`` swapped for a symlink after
    this check returns gets read through or probed. Callers that go on to
    open/read/probe the same path use :func:`_open_claudeignore_no_follow`
    so the guard and the use are the same syscall.
    """
    if path.is_symlink():
        try:
            target = os.readlink(path)
        except OSError as exc:
            raise ClaudeignorePathError(f".claudeignore is a symlink; refusing to read or write through it: {path} (could not resolve target: {exc})") from exc
        raise ClaudeignorePathError(f".claudeignore is a symlink to {target!r}; refusing to read or write through it: {path}")


def _open_claudeignore_no_follow(path: Path, flags: int) -> int:
    """Open *path* with ``O_NOFOLLOW`` and return the fd.

    Folds the symlink guard into the ``open()`` call itself: a
    ``.claudeignore`` swapped for a symlink between an earlier
    ``is_symlink()`` check and this call still fails closed, because the
    kernel raises ``ELOOP`` on the ``open()`` rather than following it --
    there is no separate check-then-use window left to race. Falls back to
    a plain (racy) ``is_symlink()`` check only on a platform without
    ``O_NOFOLLOW`` (there is none among this project's supported targets;
    kept for parity with the other no-follow call sites in this codebase,
    e.g. ``invocation/writer.py``).
    """
    no_follow = getattr(os, "O_NOFOLLOW", 0)
    if no_follow == 0:
        _reject_claudeignore_symlink(path)
    try:
        return _open_ignore_file_no_follow(path, flags)
    except NonRegularIgnoreFileError as exc:
        cause = exc.__cause__
        if isinstance(cause, OSError) and cause.errno == errno.ELOOP:
            raise ClaudeignorePathError(f".claudeignore is a symlink; refusing to read or write through it: {path}") from cause
        raise


def _atomic_write_claudeignore(path: Path, content: str) -> None:
    """Write ``.claudeignore`` atomically without following a symlink.

    Writes to a same-directory tempfile, then ``os.replace()``s it into
    place -- ``os.replace()`` (POSIX ``rename()``) replaces the destination
    directory entry itself rather than following it, so even a
    ``.claudeignore`` swapped for a symlink between the guard above and this
    call cannot redirect the write to an arbitrary target.
    """
    _reject_claudeignore_symlink(path)
    existing_mode: int | None = None
    # os.replace() (rename) only requires write access to the parent directory,
    # not to the file it replaces, so it would otherwise silently clobber a
    # read-only .claudeignore. Probe with a real open() to preserve the
    # PermissionError a direct write raises -- through a no-follow fd, so a
    # symlink swapped in since the guard above both fails closed AND can't
    # substitute its target's mode for the real file's (fstat() reads whatever
    # inode this fd is actually attached to, never a followed symlink target).
    try:
        probe_fd = _open_claudeignore_no_follow(path, os.O_WRONLY)
    except FileNotFoundError:
        existing_mode = None
    else:
        try:
            existing_mode = stat.S_IMODE(os.fstat(probe_fd).st_mode)
        finally:
            os.close(probe_fd)

    temporary_flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    for _ in range(100):
        tmp_path = path.parent / f".claudeignore.{os.getpid()}.{secrets.token_hex(8)}.tmp"
        try:
            fd = os.open(tmp_path, temporary_flags, 0o666)
            break
        except FileExistsError:
            continue
    else:
        raise FileExistsError(f"could not create a unique temporary file beside {path}")

    try:
        try:
            if existing_mode is not None:
                chmod_fd(fd, tmp_path, existing_mode)
            remaining = memoryview(content.encode("utf-8"))
            while remaining:
                written = os.write(fd, remaining)
                if written == 0:
                    raise OSError(f"temporary file beside {path} accepted zero bytes")
                remaining = remaining[written:]
        finally:
            os.close(fd)
        # Replace only after the fd is closed. An open fd from os.open carries no
        # FILE_SHARE_DELETE on Windows, so it blocks MoveFileExW there -- replacing
        # while the fd was still open failed every .claudeignore write on that
        # platform (issue #655 squad pass-1 MAJOR). Mirrors the repo's established
        # close-before-replace idiom in coordination/atomic_write.py's
        # _write_and_replace_via_parent_fd.
        os.replace(tmp_path, path)
    except BaseException:
        # Covers both failure stages -- a write/fchmod failure (fd already closed
        # by the inner finally, tmp left behind) and an os.replace failure (fd
        # closed, tmp still present). The fd is closed exactly once, so there is no
        # double-close.
        with contextlib.suppress(OSError):
            os.unlink(tmp_path)
        raise


def _read_claudeignore_no_follow(path: Path) -> str:
    """Read ``.claudeignore``'s content through a no-follow fd.

    A guard-then-use pair spread across two syscalls (an ``is_symlink()``
    check followed by a separate ``read_text()``) leaves a window where a
    ``.claudeignore`` swapped for a symlink in between gets its target's
    content read and merged into the new file. Opening with
    :func:`_open_claudeignore_no_follow` makes the guard and the read the
    same syscall.
    """
    try:
        fd = _open_claudeignore_no_follow(path, os.O_RDONLY)
    except FileNotFoundError:
        return ""
    with os.fdopen(fd, encoding="utf-8-sig") as handle:
        return handle.read()


def _append_claudeignore_entry(project_path: Path) -> None:
    path = project_path / _CLAUDEIGNORE_FILENAME
    _reject_claudeignore_symlink(path)
    existing = _read_claudeignore_no_follow(path)
    lines = existing.splitlines()
    if lines and lines[-1].strip():
        lines.append("")
    lines.append(_ENV_FILE_IGNORE_ENTRY)
    lines.append("")
    _atomic_write_claudeignore(path, "\n".join(lines))


# ---------------------------------------------------------------------------
# Migration
# ---------------------------------------------------------------------------


@MigrationRegistry.register
class ProvisionKittyEnvMigration(BaseMigration):
    """Provision ``.kittify/.kitty.env`` + its config.yaml pointer + ignore coverage."""

    migration_id = MIGRATION_ID
    description = (
        "Create .kittify/.kitty.env (seeding only already-set governed operator "
        "vars, never SPEC_KITTY_PACKS_ROOT), register its config.yaml env_file "
        "pointer, and gitignore/claudeignore the file."
    )
    target_version = TARGET_VERSION
    runs_on_worktrees = False

    def detect(self, project_path: Path) -> bool:
        return (
            _env_file_missing(project_path)
            or _config_env_file_pointer_missing(project_path)
            or _gitignore_missing_entry(project_path)
            or _claudeignore_missing_entry(project_path)
        )

    def can_apply(self, project_path: Path) -> tuple[bool, str]:
        if self.detect(project_path):
            return True, ""
        return False, ".kitty.env already provisioned (file, config pointer, ignore coverage all present)"

    def apply(self, project_path: Path, dry_run: bool = False) -> MigrationResult:
        changes: list[str] = []

        if _env_file_missing(project_path):
            if not dry_run:
                env_path = _env_file_path(project_path)
                env_path.parent.mkdir(parents=True, exist_ok=True)
                env_path.write_text(_build_env_file_content(), encoding="utf-8")
            changes.append(f"Created {_KITTIFY_DIRNAME}/{_ENV_FILENAME}")

        if _config_env_file_pointer_missing(project_path):
            if not dry_run:
                _write_config_env_file_pointer(project_path)
            changes.append(f"Registered {_ENV_FILE_CONFIG_KEY}: {_ENV_FILE_CONFIG_VALUE} in config.yaml")

        if _gitignore_missing_entry(project_path):
            if not dry_run:
                GitignoreManager(project_path).ensure_entries([_ENV_FILE_IGNORE_ENTRY])
            changes.append(f"Added {_ENV_FILE_IGNORE_ENTRY} to .gitignore")

        if _claudeignore_missing_entry(project_path):
            if not dry_run:
                _append_claudeignore_entry(project_path)
            changes.append(f"Added {_ENV_FILE_IGNORE_ENTRY} to .claudeignore")

        if not changes:
            changes = ["already provisioned"]

        return MigrationResult(success=True, changes_made=changes)
