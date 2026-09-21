"""Cross-platform path resolution for the spec-kitty runtime.

Provides the canonical functions for locating:
- The user-global ~/.kittify/ directory (cross-platform)
- The package-bundled mission assets (for ensure_runtime to copy from)

These functions have no spec-kitty-specific dependencies and are consumed
by multiple packages in the stack (specify_cli, charter).  They live
in kernel so that neither package needs to import from the other.
"""

from __future__ import annotations

import os
import warnings
from pathlib import Path, PurePath, PurePosixPath

from kernel.sibling_paths import SiblingPathNotFound, resolve_installed_sibling

#: Environment variable naming the pack root (default- or operator-supplied).
#: Read here, at the kernel floor, so built-in-pack-root *resolution* has exactly
#: ONE ``SPEC_KITTY_PACKS_ROOT`` read (FR-001/DR-1) -- the resolve in
#: :func:`get_built_in_pack_root`; every layer above -- the
#: ``get_package_asset_root`` door here and ``charter.offering.pack_paths`` -- must
#: delegate to it rather than forking a second resolver. (The door also reads
#: the var once as a *presence gate* to decide ``PACKS_ROOT``-vs-``TEMPLATE_ROOT``
#: precedence; that read resolves no path, so the single-resolver invariant --
#: enforced by ``test_packs_root_env_read_lives_only_in_kernel_paths`` at module
#: granularity -- holds.)
_PACKS_ROOT_ENV = "SPEC_KITTY_PACKS_ROOT"

#: Environment variable naming a template/asset-copy root (CI/testing). Still
#: honoured for the asset-copy/template path, but only when ``PACKS_ROOT`` is
#: not governing pack-root location (C-R3): ``PACKS_ROOT`` wins for *location*.
_TEMPLATE_ROOT_ENV = "SPEC_KITTY_TEMPLATE_ROOT"

#: The fixed ``built-in`` pack directory name, both as the child of a
#: ``PACKS_ROOT`` override and as the ``packs/built-in`` sibling segment.
_BUILT_IN_DIR_NAME = "built-in"

#: Fail-closed message when no package mission assets can be located. Kept as a
#: module constant so the door's two closed-error branches speak with one voice.
_MISSION_ASSETS_NOT_FOUND_MSG = "Cannot locate package mission assets. Set SPEC_KITTY_TEMPLATE_ROOT or reinstall spec-kitty-cli."


def is_windows() -> bool:
    """Return True when running on Windows.

    The one canonical, patchable OS-detection seam (FR-004/FR-005, C-003).
    Consumers import this module attribute -- ``from kernel.paths import
    is_windows`` -- and call it (``is_windows()``), never an inline
    ``os.name``/``sys.platform``/``platform.system()`` literal, so tests can
    monkeypatch ``kernel.paths.is_windows`` without ever faking ``os.name``
    (which flips ``pathlib`` to ``WindowsPath`` and crashes pytest). Binding
    the imported name too early -- ``import kernel.paths; kernel.paths.is_windows()``
    at *module* scope, then calling the bound name later -- would freeze the
    pre-monkeypatch function object; call through the module attribute at
    call time instead.
    """
    return os.name == "nt"


def get_kittify_home() -> Path:
    """Return the path to the user-global ~/.kittify/ directory.

    Resolution order:
    1. SPEC_KITTY_HOME environment variable (all platforms)
    2. ~/.kittify/ on macOS/Linux (Path.home() / ".kittify")
    3. %LOCALAPPDATA%\\spec-kitty\\ on Windows (via platformdirs, app name "spec-kitty")

    On Windows the app name used is ``"spec-kitty"`` so that ``kernel.paths``
    resolves to the same root as ``specify_cli.paths.get_runtime_root().base``
    (FR-005 / C-002: unified Windows root, no long-term dual root).
    The ``roaming=False`` flag matches ``get_runtime_root()`` exactly so that
    both resolve to ``%LOCALAPPDATA%\\spec-kitty``.

    On POSIX the behaviour is unchanged: ``~/.kittify/``.

    Returns:
        Path: Absolute path to the global runtime directory.

    Raises:
        RuntimeError: If the home directory cannot be determined.
    """
    if env_home := os.environ.get("SPEC_KITTY_HOME"):
        return Path(env_home)

    if is_windows():
        # platformdirs is the only sanctioned third-party import in kernel/.
        # Use app name "spec-kitty" (not "kittify") so this matches
        # specify_cli.paths.get_runtime_root().base — the two resolutions must
        # agree to satisfy the single-root invariant (FR-005 / C-002).
        # kernel/ must not import specify_cli (architectural layer rule), so we
        # call platformdirs directly with the same arguments.
        from platformdirs import user_data_dir  # noqa: PLC0415

        return Path(str(user_data_dir("spec-kitty", appauthor=False, roaming=False)))

    return Path.home() / ".kittify"


#: The relative shape sought for the *env-var* override branch below: either
#: the mission-assets directory itself, or a checkout/package root one or two
#: levels above it. Generic (a bare directory name, not a package name) --
#: see ``_looks_like_missions_root`` for the content sniff that disambiguates
#: an actual hit from an unrelated directory that happens to be named this.
_MISSION_ASSETS_DIR_NAME = "missions"

#: The relative shape handed to :func:`kernel.sibling_paths.resolve_installed_sibling`
#: for the non-env-var (ancestor-walk) branch. Mission
#: ``doctrine-consumer-surface-missions-extraction-01KZ6G6H`` (FR-005, WP05)
#: relocated the missions *data* subdirectories from ``src/charter/offering/missions``
#: to ``packs/built-in/missions`` -- ``packs/`` ships as a fixed-name,
#: site-packages-level sibling of every top-level package (the root
#: ``pyproject.toml``'s ``force-include = {"packs" = "packs"}``), so this
#: pattern is a **literal** relative path, not a per-package wildcard: it can
#: only ever match the one real data location, never accidentally the
#: still-existing-but-now-data-less ``src/charter/offering/missions`` package
#: directory (the ``.py`` logic modules stay there) that a generic
#: ``"*/missions"`` wildcard pattern would keep matching post-move. This is
#: the exact self-match trap the mission's reader inventory names as the
#: highest-severity finding: a bare wildcard pattern still finds *a* directory
#: named "missions" one ancestor level up from ``src/charter/offering/missions``
#: itself, it is just the wrong (data-less) one. A fully-qualified pattern
#: naming ``packs/built-in/missions`` structurally cannot make that mistake.
#:
#: PUBLIC (exported via ``kernel.__all__``): the ``packs/built-in`` sibling
#: shape used by :func:`get_built_in_pack_root` to locate the built-in pack
#: root, and the single owner of that shape (FR-012 / C-R1) so
#: ``charter.offering.pack_paths`` delegates to a public kernel symbol rather than
#: forking the literal. Built with the multi-argument ``PurePosixPath``
#: constructor (not ``/`` joins) so the shape is a single owned constant, not a
#: scattered ``<path> / "built-in"`` filesystem-join literal.
BUILT_IN_PACK_SIBLING_PATTERN = PurePosixPath("packs", _BUILT_IN_DIR_NAME)

#: PUBLIC: the full ``packs/built-in/missions`` sibling shape -- the built-in
#: pack pattern above composed with the ``missions`` leaf. The one owned
#: composition every consumer (this module's ancestor walk; WP02's
#: ``charter.offering.missions.repository``) reuses instead of re-spelling the literal.
MISSION_ASSETS_SIBLING_PATTERN = BUILT_IN_PACK_SIBLING_PATTERN / _MISSION_ASSETS_DIR_NAME

#: The relative shape used only by :func:`_resolve_env_root` below, globbed
#: directly against a caller-supplied ``SPEC_KITTY_TEMPLATE_ROOT`` checkout
#: root -- NOT handed to the sibling-resolution primitive. A checkout root
#: sits above the sibling package's missions dir
#: (``<root>/src/<namespace>/<pkg>/missions``), unlike the primitive's own anchor (this
#: module's file, one level below ``src/``), so this candidate needs the
#: ``src/`` segment that :data:`MISSION_ASSETS_SIBLING_PATTERN` above must
#: not carry.
#: The editable-checkout ``src`` layout marker: the grandparent directory name
#: a ``<root>/src/<pkg>/missions`` TEMPLATE_ROOT sits under. Owned once so the
#: checkout glob and the sibling-scan guard in :func:`_resolve_env_root` agree.
_SRC_LAYOUT_DIR_NAME = "src"

_MISSION_ASSETS_CHECKOUT_GLOB_PATTERN = PurePosixPath(_SRC_LAYOUT_DIR_NAME) / "*" / "*" / _MISSION_ASSETS_DIR_NAME


def _looks_like_missions_root(path: Path) -> bool:
    """Content-sniff: does ``path`` hold mission-type subdirectories with real content?

    Generic by construction: the mission-type segment is a glob wildcard, not
    an enumerated, hard-coded vocabulary of mission-type names.
    """
    has_content_templates = any(path.glob("*/templates/*.md"))
    has_legacy_commands = any(path.glob("*/command-templates/*.md"))
    has_step_prompts = any(path.glob("mission-steps/*/*/prompt.md"))
    return has_content_templates or has_legacy_commands or has_step_prompts


def _find_relocated_missions_ancestor(root: Path) -> Path | None:
    """Walk ``root`` and its ancestors for the real, post-relocation missions root.

    Mission ``doctrine-consumer-surface-missions-extraction-01KZ6G6H`` (FR-005)
    moved the missions data from ``src/charter/offering/missions`` to
    ``packs/built-in/missions``. ``SPEC_KITTY_TEMPLATE_ROOT`` may be set to any
    of several legacy shapes (the bare missions directory, a full checkout
    root, a stale sibling-package leaf, ...), each sitting at a *different*
    depth relative to the real repository root -- so this walks every
    ancestor (including ``root`` itself) rather than assuming a fixed number
    of ``.parent`` hops, finding the relocated data uniformly regardless of
    which legacy shape the caller supplied. Unlike the other candidates in
    :func:`_resolve_env_root`, the ``packs/built-in/missions`` shape is
    unambiguous -- no unrelated tree can accidentally satisfy it -- so no
    content-sniff is needed once a candidate is found to exist.
    """
    for ancestor in (root, *root.parents):
        candidate = ancestor / MISSION_ASSETS_SIBLING_PATTERN
        if candidate.is_dir():
            return candidate
    return None


def _resolve_env_root(root: Path) -> Path:
    """Resolve ``SPEC_KITTY_TEMPLATE_ROOT`` under its several legacy accepted shapes.

    ``root`` may itself already be the mission-assets directory, a checkout
    root one or two levels above it, or (historically) a stale sibling
    package's own copy -- disambiguated by :func:`_looks_like_missions_root`,
    never by naming a specific package. The relocated ``packs/built-in/missions``
    location (see :func:`_find_relocated_missions_ancestor`) is tried first and
    unconditionally, since every legacy shape below predates mission #3091's
    move and would otherwise resolve into the now data-less
    ``src/charter/offering/missions`` package directory or the unrelated
    ``specify_cli/missions`` legacy tree.

    Candidate order matters: the checkout-root candidate (bare ``root``) is
    tried LAST, after the more specific ``src/*/missions`` glob. A real
    checkout root generally also satisfies ``_looks_like_missions_root``'s
    loose content sniff on its own (e.g. via an unrelated ``docs/templates/
    *.md``), so if bare ``root`` were tried first it would short-circuit
    before the glob ever gets a chance to find the actual missions directory
    nested under it.
    """
    if (relocated := _find_relocated_missions_ancestor(root)) is not None:
        return relocated

    candidates: list[Path] = [root / _MISSION_ASSETS_DIR_NAME]
    candidates.extend(sorted(root.glob(str(_MISSION_ASSETS_CHECKOUT_GLOB_PATTERN))))
    # Sibling-package scan only for a real ``<checkout>/src/<pkg>/missions``
    # shape (grandparent named ``src``): remap a stale sibling package's
    # missions leaf onto the canonical one. Guarded by the grandparent name so
    # a bare ``<dir>/missions`` TEMPLATE_ROOT never scans its arbitrary
    # grandparent's children (which, under a shared pytest tmp base, would
    # non-deterministically pick an unrelated sibling ``*/missions``) -- this
    # preserves the pre-collapse ``home.py`` behavior (behavior parity, DR-1).
    if root.name == _MISSION_ASSETS_DIR_NAME and root.parent.parent.name == _SRC_LAYOUT_DIR_NAME:
        candidates.extend(sorted(root.parent.parent.glob(f"*/*/{_MISSION_ASSETS_DIR_NAME}")))
    candidates.append(root)
    for candidate in candidates:
        if candidate.is_dir() and _looks_like_missions_root(candidate):
            return candidate
    raise FileNotFoundError(f"SPEC_KITTY_TEMPLATE_ROOT does not contain mission assets: {root}. Expected a missions directory or a Spec Kitty checkout root.")


def get_built_in_pack_root() -> Path:
    """Return the ``built-in`` pack root (missions included), ``PACKS_ROOT``-aware.

    The single kernel-floor resolution of the built-in pack root (FR-001/FR-002,
    DR-1). ``SPEC_KITTY_PACKS_ROOT`` -- joined with the fixed ``built-in``
    child -- wins as the env override when it names an existing directory;
    otherwise the shared ancestor-walk primitive
    (:func:`kernel.sibling_paths.resolve_installed_sibling`) locates the
    ``packs/built-in`` sibling (:data:`BUILT_IN_PACK_SIBLING_PATTERN`), covering
    both an editable checkout and an installed wheel in one bounded walk.

    Fail-open-but-loud on a misconfigured override (supersedes DR-1's original
    silent-parity framing, operator decision 2026-08-07 -- see the ADR
    addendum on ``docs/adr/3.x/2026-08-05-1-mission-type-availability-before-kind-promotion.md``):
    when ``SPEC_KITTY_PACKS_ROOT`` is set but ``<value>/built-in`` does not
    resolve to an existing directory, this emits a :class:`UserWarning` naming
    the misconfigured path before falling through to the ancestor walk --
    informing an operator of a broken override beats silently loading whatever
    doctrine/charter pack the ancestor walk happens to find instead. Resolution
    still does not raise on the override itself; only the silence is removed.

    Callers above this layer -- the :func:`get_package_asset_root` door here,
    and ``charter.offering.pack_paths`` (WP02) -- delegate to this one primitive rather
    than forking a second ``SPEC_KITTY_PACKS_ROOT`` read.

    Returns:
        Path: Absolute path to the built-in pack root.

    Raises:
        SiblingPathNotFound: fail-closed when neither the env override nor the
            ancestor walk resolves. The caller translates it -- the door to
            ``FileNotFoundError``; ``charter.offering.pack_paths`` to ``PackRootNotFound``
            -- so kernel need not know either upward-layer error type.
    """
    env_value = os.environ.get(_PACKS_ROOT_ENV)
    env_override = Path(env_value) / _BUILT_IN_DIR_NAME if env_value else None
    if env_override is not None and not env_override.is_dir():
        warnings.warn(
            f"{_PACKS_ROOT_ENV}={env_value!r} does not resolve to a directory "
            f"(expected {env_override} to exist). Ignoring the override and "
            "falling back to the installed built-in pack tree -- fix or unset "
            f"{_PACKS_ROOT_ENV} if this is unexpected.",
            UserWarning,
            stacklevel=2,
        )
    return resolve_installed_sibling(
        anchor_file=Path(__file__),
        env_override=env_override,
        sibling_relative_path=BUILT_IN_PACK_SIBLING_PATTERN,
    )


def get_packs_root_default() -> Path:
    """Return the default value for the ``${SPEC_KITTY_PACKS_ROOT}`` env token.

    The token names the **parent** of the built-in pack directory:
    ``get_built_in_pack_root()`` resolves ``.../packs/built-in``, so the
    token's default is ``.../packs`` -- one ``.parent`` hop, not the
    resolver's own return value. Using the resolver's return directly as the
    default would double-join ``/built-in`` when a downstream template
    appends it back on (e.g. ``${SPEC_KITTY_PACKS_ROOT}/built-in/...``), per
    the ``_PACKS_ROOT_ENV`` override shape documented above
    (:func:`get_built_in_pack_root`).

    This is the single kernel-floor authority for that default -- callers
    needing the ``${SPEC_KITTY_PACKS_ROOT}`` default (e.g.
    :mod:`kernel.env_expand`'s default-injection registry) resolve through
    this function rather than hand-rolling ``get_built_in_pack_root().parent``
    at each call site.

    Returns:
        Path: The parent of the built-in pack root.
    """
    return get_built_in_pack_root().parent


def get_runtime_state_root() -> Path:
    """Return the spec-kitty runtime STATE root for the current platform.

    This is a **different** root from :func:`get_kittify_home` (the
    ``.kittify`` ASSET home) -- the two are deliberately kept separate and
    this function must never collapse them. It exists so a pre-import loader
    (e.g. a future ``.kitty.env`` reader) can resolve the runtime state root
    using stdlib + ``kernel.paths`` only, without importing ``specify_cli``.

    Resolution order (mirrors
    ``specify_cli.paths.windows_paths.get_runtime_root().base`` exactly, so
    both resolve to the same directory on every branch, including the
    platformdirs-failure fallback):

    1. ``SPEC_KITTY_HOME`` environment variable, used verbatim (all
       platforms).
    2. Windows: ``platformdirs.user_data_dir("spec-kitty", appauthor=False,
       roaming=False)`` (non-roaming ``%LOCALAPPDATA%\\spec-kitty``), falling
       back to ``Path.home() / ".spec-kitty"`` if the platformdirs call
       raises (e.g. a constrained/simulated Windows runtime where the
       underlying ctypes/registry lookup is unavailable) -- the same
       fallback ``get_runtime_root()`` applies, so the two resolvers agree
       on this branch too.
    3. POSIX: ``~/.spec-kitty``.

    This function is pure -- it performs no I/O and creates no directories.

    Returns:
        Path: Absolute path to the runtime state root.
    """
    if env_home := os.environ.get("SPEC_KITTY_HOME"):
        return Path(env_home)

    if is_windows():
        # platformdirs is the only sanctioned third-party import in kernel/.
        from platformdirs import user_data_dir  # noqa: PLC0415

        try:
            return Path(str(user_data_dir("spec-kitty", appauthor=False, roaming=False)))
        except Exception:
            # Mirrors specify_cli.paths.windows_paths.get_runtime_root(): keep
            # a constrained/simulated Windows runtime (ctypes/registry lookup
            # unavailable) from crashing before callers can patch or inspect
            # this resolver.
            return Path.home() / ".spec-kitty"

    return Path.home() / ".spec-kitty"


def ensure_runtime_state_root() -> Path:
    """Create (or re-harden) the runtime STATE root at ``0o700``, returning it.

    The single side-effecting door for the runtime-state root.
    :func:`get_runtime_state_root` (and its specify_cli mirror
    ``specify_cli.paths.get_runtime_root``) stay **pure** resolvers, pinned by
    their own contracts ("resolution creates no directories"), so the actual
    ``mkdir``/``chmod`` cannot live in either. This kernel-floor door lets
    BOTH the specify_cli hardening path
    (``specify_cli.paths.windows_paths.ensure_runtime_root``, #4812/#4760) and
    the runtime prompt-namespace path
    (``runtime.next._tmp_namespace.prompt_tmp_dir``, #4721) share ONE
    hardening implementation without either importing the other -- ``runtime``
    must not import ``specify_cli`` (enforced layer direction
    ``kernel <- runtime <- specify_cli``), but both may import ``kernel``.
    Before this door the two hardened the same root with two independent
    ``mkdir(mode=0o700)+chmod(0o700)`` copies ("redundant but not divergent"),
    a DIRECTIVE_044 canonical-source gap that would drift the moment the mode
    policy changed in one and not the other.

    Idempotent and safe to call on every write: an already-existing directory
    is re-chmod'd to ``0o700`` rather than trusted at whatever mode a pre-fix
    write left it (ambient umask, typically ``0o755``).
    """
    root = get_runtime_state_root()
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    root.chmod(0o700)
    return root


def get_package_asset_root() -> Path:
    """Return the path to the package's bundled mission assets.

    Resolution order (DR-1 unified resolver):

    1. ``SPEC_KITTY_PACKS_ROOT`` takes *precedence* over the
       ``SPEC_KITTY_TEMPLATE_ROOT`` branch whenever it is set: the assets are
       ``<built-in-pack-root>/missions`` resolved through
       :func:`get_built_in_pack_root`. Note this is precedence, not a guarantee
       that the override governs the final path -- a set-but-unresolvable
       ``PACKS_ROOT`` (its ``/built-in`` child is not a directory) does not fail
       closed here; :func:`get_built_in_pack_root` falls through to the installed
       sibling. This no longer happens silently (operator decision 2026-08-07,
       superseding DR-1's original silent-parity framing): the door inherits a
       loud :class:`UserWarning` from :func:`get_built_in_pack_root` naming the
       misconfigured override before falling through.
    2. ``SPEC_KITTY_TEMPLATE_ROOT`` (CI/testing), only when ``PACKS_ROOT`` is
       unset -- several accepted legacy shapes, see :func:`_resolve_env_root`.
    3. Otherwise the same :func:`get_built_in_pack_root` primitive locates the
       installed ``packs/built-in`` sibling and the ``missions`` leaf is joined
       onto it. The primitive's ancestor walk is bounded (see
       :mod:`kernel.sibling_paths`) so a broken install fails closed instead of
       matching an unrelated tree several levels up.

    Fail-closed (C-R4 / FR-013): raises rather than returning a nonexistent
    path, and never falls through to a legacy ``specify_cli/missions`` or
    ``dev_root`` layout (those fallbacks are intentionally gone, DR-2). The one
    exception is a set-but-unresolvable ``PACKS_ROOT`` override (point 1), which
    resolves to the installed sibling rather than raising on the override --
    fail-open, but loudly warned (2026-08-07), not silently, as of the DR-1
    supersession above.

    Returns:
        Path: Absolute path to the missions directory.

    Raises:
        FileNotFoundError: If no valid asset root can be found.
    """
    # SPEC_KITTY_TEMPLATE_ROOT still governs the asset-copy/template path, but
    # only when PACKS_ROOT is not governing pack-root location (PACKS_ROOT-first
    # ordering, C-R3): PACKS_ROOT wins.
    if not os.environ.get(_PACKS_ROOT_ENV) and (env_root := os.environ.get(_TEMPLATE_ROOT_ENV)):
        root = Path(env_root)
        if root.is_dir():
            return _resolve_env_root(root)
        raise FileNotFoundError(f"{_TEMPLATE_ROOT_ENV} path does not exist: {env_root}")

    try:
        pack_root = get_built_in_pack_root()
    except SiblingPathNotFound as exc:
        raise FileNotFoundError(_MISSION_ASSETS_NOT_FOUND_MSG) from exc

    missions = pack_root / _MISSION_ASSETS_DIR_NAME
    if missions.is_dir():
        return missions
    raise FileNotFoundError(f"Built-in pack root {pack_root} has no {_MISSION_ASSETS_DIR_NAME!r} directory (fail-closed: no legacy fall-through).")


def render_runtime_path(path: Path, *, for_user: bool = True) -> str:
    """Render a runtime-state path for user-facing output.

    - On Windows: returns the real absolute path string (no tilde substitution).
    - On POSIX: if ``for_user=True`` and ``path`` is under ``$HOME``, returns
      ``~/<relpath>`` form; otherwise returns the absolute path.

    This helper exists in ``kernel`` so that every layer can render runtime
    paths without reintroducing POSIX-tilde literals in user-facing output
    on Windows (SC-002 of the Windows Compatibility Hardening mission).
    Mirrors :func:`specify_cli.paths.render_runtime_path` with identical
    semantics; kept here to preserve the kernel<-doctrine<-charter<-specify_cli
    dependency direction.
    """
    abs_path = Path(path).resolve(strict=False)
    if not for_user:
        return str(abs_path)
    if is_windows():
        return str(abs_path)
    try:
        home = Path.home().resolve(strict=False)
        rel = abs_path.relative_to(home)
        return "~/" + to_posix(rel)
    except ValueError:
        return str(abs_path)


def to_posix(path: Path | str) -> str:
    """Normalize a path (or path-like string) to a forward-slashed string.

    The single separator-normalization seam. For a ``PurePath`` it returns
    ``.as_posix()``; for a ``str`` (git stdout, a glob pattern, user input) it
    swaps ``\\`` for ``/``. Git object/pathspec syntax and cross-platform path
    comparison require forward slashes (#2836); scattering
    ``str(x).replace(...)`` across the tree re-invited the exact per-site Windows
    drift #2836 fixed, so every such normalization routes here. Only the
    separator is touched — surrounding concerns (``.strip()``, ``.rstrip("/")``,
    splitting) stay at the call site.
    """
    if isinstance(path, PurePath):
        return path.as_posix()
    return path.replace("\\", "/")


def posix_tree_path(parts: tuple[str, ...]) -> str:
    """Join path ``parts`` into a git tree path (always forward-slashed).

    Git's ``HEAD:<path>`` object syntax and ``ls-files`` pathspec require
    forward slashes. Rendering with ``str(Path(*parts))`` uses ``os.sep`` — a
    backslash on Windows — which git rejects, making committed specs misreport
    as uncommitted (#2836). ``PurePosixPath`` renders with ``/`` on every host,
    closing the defect by construction: the string is built from the
    separator-agnostic ``parts`` tuple, never re-parsed through a host-native
    ``Path``.

    This lives in ``kernel`` as the single behaviour-agnostic tree-path seam so
    consumers in different layers (``specify_cli.missions._substantive`` and
    ``cli.commands.agent.mission_finalize``) render tree paths identically
    without importing from one another. It is the seam the #2836 regression is
    witnessed against: because the bug is a POSIX/Windows *rendering* difference
    it cannot be caught by a black-box input test on POSIX, so the guard
    substitutes ``PureWindowsPath`` for the module ``Path`` symbol to prove a
    reverted ``str(Path(*parts))`` form would reintroduce backslashes.
    """
    return PurePosixPath(*parts).as_posix() if parts else ""


def repo_tree_path(file_path: Path, repo_root: Path) -> tuple[Path, str]:
    """Return ``(git_cwd, tree_path)`` for a repo file; tree path forward-slashed.

    ``git_cwd`` is the linked-worktree root when ``file_path`` lives under
    ``.worktrees/<name>/`` — branch tree paths start at that worktree root, so a
    file at ``.worktrees/<name>/kitty-specs/<slug>/spec.md`` is addressed as
    ``kitty-specs/<slug>/spec.md`` — else the primary repo root. The tree path is
    always forward-slashed via :func:`posix_tree_path` (#2836).

    Canonical worktree-aware tree-path seam: both the committedness check
    (``specify_cli.missions._substantive._git_commit_check_context``) and
    finalize's branch-artifact reporting
    (``cli.commands.agent.mission_finalize._branch_tree_relative_path``) route
    through here, so the worktree-strip logic lives in exactly one place. Raises
    ``ValueError`` when ``file_path`` is not under ``repo_root``.
    """
    repo_abs = repo_root.resolve()
    rel = file_path.resolve().relative_to(repo_abs)
    parts = rel.parts
    if len(parts) > 2 and parts[0] == ".worktrees":
        worktree_root = repo_abs / parts[0] / parts[1]
        if worktree_root.is_dir():
            return worktree_root, posix_tree_path(parts[2:])
    return repo_abs, posix_tree_path(parts)


__all__ = [
    "BUILT_IN_PACK_SIBLING_PATTERN",
    "MISSION_ASSETS_SIBLING_PATTERN",
    "get_built_in_pack_root",
    "get_kittify_home",
    "get_package_asset_root",
    "get_runtime_state_root",
    "is_windows",
    "render_runtime_path",
    "repo_tree_path",
    "to_posix",
]
# ``get_packs_root_default`` is intentionally NOT exported: its only caller is
# in-package (``kernel.env_expand``'s default-injection registry), which imports
# it by module path (demoted, never deleted -- dead-port-disposition-01M1TZVN,
# FR-014).
# ``posix_tree_path`` is intentionally NOT exported: it is the internal
# forward-slash-join primitive behind ``repo_tree_path`` (the public seam other
# layers consume). It stays a module-level function so the #2836 regression
# witness can substitute ``Path`` and call it directly, but it is not part of the
# public API — keeping it out of ``__all__`` satisfies the dead-symbol gate.
