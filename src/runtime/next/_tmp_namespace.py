"""Shared, per-user, sweepable prompt-temp root for spec-kitty prompt writers.

WP02 / FR-003: three prompt writers previously rooted their output directly
at ``tempfile.gettempdir()`` (a flat, unbounded ``/tmp``):

- ``runtime.next.prompt_builder`` (``spec-kitty-next-*``)
- ``runtime.next.decision`` (``spec-kitty-composed-{action}-*``, two
  ``mkstemp`` sites — unbounded, a unique suffix per call)
- ``specify_cli.cli.commands.agent.workflow`` (``spec-kitty-{implement,review}-*``)

WP07 / FR-003 FR-010 FR-011 (#4721): that shared-namespace fix still rooted
at ``tempfile.gettempdir()`` — a world-shared, predictable location any
local user can traverse, so another user could pre-create/deny the shared
dir (cross-user DoS) ahead of this one, and prompt files written there
(mode ~0644 under a typical umask) were world-readable (information
disclosure of prompt/mission content). :func:`prompt_tmp_dir` now roots
under the PER-USER runtime state root (``~/.spec-kitty``, via
:func:`kernel.paths.get_runtime_state_root` — the pure resolver
``specify_cli.paths.get_runtime_root().base`` mirrors) and creates the
leaf directory owner-only (``0700``); :func:`write_prompt_file` writes
prompt content through WP01's canonical :func:`kernel.no_follow.open_no_follow`
primitive at mode ``0600`` so a symlink planted at the prompt path is
refused rather than followed, and the file itself is never group/other
readable.

This module is the single source of truth for the namespace all three
writers write under. Callers must build their prompt path under
:func:`prompt_tmp_dir` (e.g. pass ``dir=prompt_tmp_dir(repo_root)`` to
``tempfile.mkstemp`` / ``NamedTemporaryFile``, or join their filename onto
the returned path) and write content through :func:`write_prompt_file`
instead of rooting at the bare ``tempfile.gettempdir()`` or writing via a
bare ``Path.write_text``.

WP01's session reaper imports :data:`SPEC_KITTY_PROMPT_NAMESPACE` /
:func:`prompt_tmp_dir` from here to find and sweep this run's prompt
residue — it must never hand-copy the prefix, or the two can silently drift
apart.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

from kernel.no_follow import open_no_follow
from kernel.paths import ensure_runtime_state_root

#: Directory name under the per-user runtime root that roots every
#: spec-kitty prompt writer. The single shared constant: writers AND the
#: WP01 reaper import this — never hand-copy the literal.
SPEC_KITTY_PROMPT_NAMESPACE = "spec-kitty-prompts"

#: Mode prompt files are created at — owner read/write only. Prompt content
#: may carry the full WP prompt / mission context, so it must never be
#: group- or other-readable (#4721 information-disclosure facet).
_PROMPT_FILE_MODE = 0o600

#: Mode the prompt namespace directory is created at — owner-only, closing
#: the #4721 cross-user DoS facet (another local user can no longer plant or
#: deny this directory, since it is no longer world-traversable).
_PROMPT_DIR_MODE = 0o700


def _repo_identity(repo_root: Path) -> str:
    """Return a short, stable, filesystem-safe identity for *repo_root*.

    Hashing the resolved absolute path keeps the namespace directory name
    short while still giving each distinct repo checkout (including each
    lane's own worktree path) its own subdirectory, so concurrent runs never
    collide and one run's sweep never touches another's residue.
    """
    resolved = str(Path(repo_root).expanduser().resolve())
    digest = hashlib.sha256(resolved.encode("utf-8")).hexdigest()[:16]  # noqa: TID251 - production raw SHA-256 owner (directory-naming hash, non-security)
    return digest


def prompt_tmp_dir(repo_root: Path) -> Path:
    """Return the per-user, per-repo prompt temp-root, creating it if absent.

    Rooted under :func:`kernel.paths.get_runtime_state_root` (``~/.spec-kitty``,
    honoring ``SPEC_KITTY_HOME``) rather than the world-shared, predictable
    ``tempfile.gettempdir()`` (#4721 FR-003/FR-010): another local user can no
    longer pre-create or deny this directory ahead of this one. The leaf
    directory is created (and re-asserted on every call) owner-only
    (``0700``) so it is not even traversable by another local user.

    WP07 cycle-2 / FR-011 residual (#4721): the runtime ROOT itself
    (``get_runtime_state_root()``) is hardened to ``0700`` here too, not
    just this leaf subdir. Before this, ``mkdir(parents=True)`` created any
    missing ancestor (including the root) at the ambient umask (typically
    ``0755``); a prompt-only workload that runs before any credential write
    left the root world-traversable until a later credential write self-healed
    it. The root hardening is delegated to the single kernel-floor door
    :func:`kernel.paths.ensure_runtime_state_root`, shared with WP06's
    ``specify_cli.paths.windows_paths.ensure_runtime_root`` -- one 0o700
    implementation, no longer a second inline copy. ``kernel`` is the root
    layer, importable here (the enforced direction is
    ``kernel <- runtime <- specify_cli``), so this module can share the door
    without importing ``specify_cli``.

    All prompt writers must write their filenames under this directory
    (instead of rooting at ``tempfile.gettempdir()``) and write content
    through :func:`write_prompt_file`. This is what WP01's session reaper
    sweeps at session finish.
    """
    root = ensure_runtime_state_root()
    tmp_dir = root / SPEC_KITTY_PROMPT_NAMESPACE / _repo_identity(repo_root)
    tmp_dir.mkdir(parents=True, exist_ok=True)
    tmp_dir.chmod(_PROMPT_DIR_MODE)
    return tmp_dir


def write_prompt_file(path: Path, content: str, *, encoding: str = "utf-8") -> None:
    """Write *content* to *path*, refusing to follow a final-component symlink.

    Routes through :func:`kernel.no_follow.open_no_follow` (WP01's canonical
    no-follow primitive, #4756 FR-001) so a symlink planted at *path* raises
    :class:`kernel.no_follow.NoFollowPathError` instead of being followed and
    overwritten, and creates the file at mode ``0600`` so prompt content
    (which may include the full resolved WP prompt / mission context) is
    never group- or other-readable (#4721 FR-011).

    Raises:
        kernel.no_follow.NoFollowPathError: If *path* is a final-component
            symlink.
        OSError: If the operating system cannot open the path for another
            reason.
    """
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    fd = open_no_follow(path, flags, _PROMPT_FILE_MODE)
    with os.fdopen(fd, "w", encoding=encoding) as handle:
        handle.write(content)
