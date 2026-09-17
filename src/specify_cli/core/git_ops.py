"""Git and subprocess helpers for the Spec Kitty CLI."""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from collections.abc import Sequence

from rich.console import Console
from rich.markup import escape

from specify_cli.cli.console import sanitize_terminal_text

ConsoleType = Console | None


@dataclass
class BranchResolution:
    """Result of branch resolution for feature operations.

    Attributes:
        target: Target branch from meta.json
        current: User's current branch
        should_notify: True if current != target (informational notification needed)
        action: "proceed" (branches match) or "stay_on_current" (respect user's branch)
    """

    target: str
    current: str
    should_notify: bool
    action: str


def _resolve_console(console: ConsoleType) -> Console:
    """Return the provided console or lazily create one."""
    return console if console is not None else Console()


def run_command(
    cmd: Sequence[str] | str,
    *,
    check_return: bool = True,
    capture: bool = False,
    shell: bool = False,
    console: ConsoleType = None,
    cwd: Path | str | None = None,
) -> tuple[int, str, str]:
    """Run a shell command and return (returncode, stdout, stderr).

    Args:
        cmd: Command to run
        check_return: If True, raise on non-zero exit
        capture: If True, capture stdout/stderr
        shell: If True, run through shell
        console: Rich console for output
        cwd: Working directory for command execution

    Returns:
        Tuple of (returncode, stdout, stderr)
    """
    try:
        result = subprocess.run(
            cmd,
            check=check_return,
            capture_output=capture,
            text=True,
            encoding="utf-8",
            errors="replace",
            shell=shell,  # nosec B602 — caller controls shell flag; git commands use list form by default
            cwd=str(cwd) if cwd else None,
        )
        stdout = (result.stdout or "").strip() if capture else ""
        stderr = (result.stderr or "").strip() if capture else ""
        return result.returncode, stdout, stderr
    except subprocess.CalledProcessError as exc:
        if check_return:
            resolved_console = _resolve_console(console)
            command = escape(sanitize_terminal_text(cmd if isinstance(cmd, str) else " ".join(cmd)))
            resolved_console.print(f"[red]Error running command:[/red] {command}")
            resolved_console.print(f"[red]Exit code:[/red] {exc.returncode}")
            if exc.stderr:
                error_output = escape(sanitize_terminal_text(exc.stderr.strip()))
                resolved_console.print(f"[red]Error output:[/red] {error_output}")
        raise


def is_git_repo(path: Path | None = None) -> bool:
    """Return True when the provided path lives inside a git repository."""
    target = (path or Path.cwd()).resolve()
    if not target.is_dir():
        return False
    try:
        subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            check=True,
            capture_output=True,
            cwd=target,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def has_unborn_head(path: Path | None = None) -> bool:
    """Return True when the repository has no commits yet (an unborn HEAD).

    A freshly ``git init``-ed repository has a HEAD that points at a branch
    ref which does not exist yet.  Git cannot create a branch in that state,
    so anything that mints a ref off the current branch — the coordination
    branch, most importantly — silently cannot work until the first commit
    lands (#4033).

    Returns ``False`` for a non-repository or when git is unavailable: callers
    guard on :func:`is_git_repo` separately, and this predicate must never be
    the thing that reports "no commits" for a directory that is not a repo at
    all.
    """
    target = (path or Path.cwd()).resolve()
    if not target.is_dir():
        return False
    # ``git rev-parse --verify HEAD`` fails both for an unborn HEAD and for a
    # directory that is not a repository at all. Only the former is "no commits
    # yet", so establish repo-ness first — otherwise this predicate would tell a
    # non-repo caller to run ``git commit``.
    if not is_git_repo(target):
        return False
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--verify", "HEAD"],
            capture_output=True,
            check=False,
            cwd=target,
        )
    except FileNotFoundError:
        return False
    return result.returncode != 0


def init_git_repo(project_path: Path, quiet: bool = False, console: ConsoleType = None) -> bool:
    """Initialize a git repository with an initial commit.

    NOTE: This function MUST NOT be called from ``init.py``.  As of the
    post-#555 init-coherence change (FR-001), ``spec-kitty init`` is
    file-creation-only and never runs git operations.  This function is
    retained for other callers (e.g. test helpers, one-off utilities) that
    explicitly need to bootstrap a git repo from Python.
    """
    resolved_console = _resolve_console(console)
    original_cwd = Path.cwd()
    try:
        os.chdir(project_path)
        if not quiet:
            resolved_console.print("[cyan]Initializing git repository...[/cyan]")
        subprocess.run(["git", "init"], check=True, capture_output=True)
        subprocess.run(["git", "add", "."], check=True, capture_output=True)
        subprocess.run(
            ["git", "-c", "commit.gpgsign=false", "commit", "-m", "Initial commit"],
            check=True,
            capture_output=True,
        )
        if not quiet:
            resolved_console.print("[green]✓[/green] Git repository initialized")
        return True
    except subprocess.CalledProcessError as exc:
        if not quiet:
            error = escape(sanitize_terminal_text(str(exc)))
            resolved_console.print(f"[red]Error initializing git repository:[/red] {error}")
        return False
    finally:
        os.chdir(original_cwd)


def get_current_branch(path: Path | None = None) -> str | None:
    """Return the current git branch name for the provided repository path.

    Tries ``git branch --show-current`` first (Git 2.22+, correctly handles
    unborn branches).  Falls back to ``git rev-parse --abbrev-ref HEAD`` for
    older Git versions.  Returns ``None`` for detached HEAD or when not
    inside a git repository.
    """
    repo_path = (path or Path.cwd()).resolve()

    # Primary: git branch --show-current (Git 2.22+)
    # Handles unborn branches correctly and returns empty string for detached HEAD.
    try:
        result = subprocess.run(
            ["git", "branch", "--show-current"],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=repo_path,
        )
        branch = result.stdout.strip()
        return branch or None
    except subprocess.CalledProcessError:
        pass
    except FileNotFoundError:
        return None

    # Fallback: git rev-parse --abbrev-ref HEAD (Git < 2.22)
    # Returns "HEAD" for detached HEAD; fails on unborn branches.
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=repo_path,
        )
        branch = result.stdout.strip()
        if branch == "HEAD":
            return None  # Detached HEAD
        return branch or None
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def has_remote(repo_path: Path, remote_name: str = "origin") -> bool:
    """Check if repository has a configured remote.

    Deliberately uses ``git remote get-url`` (the transport view, which
    applies any global ``url.<base>.insteadOf`` rewrite) rather than
    ``git config --get``: only the exit code is consulted, never the URL
    value, and every caller uses this to gate a push/fetch (e.g.
    ``merge/executor.py``'s ``if push and has_remote(...)``) — "does a
    push have somewhere to go" is exactly the transport question. Not an
    identity/slug site, so #111's raw-config criterion does not apply here
    (triaged in spec-kitty#113).

    Args:
        repo_path: Repository root path
        remote_name: Remote name to check (default: "origin")

    Returns:
        True if remote exists, False otherwise
    """
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", remote_name],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=repo_path,
            check=False,
        )
        return result.returncode == 0
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def has_tracking_branch(repo_path: Path) -> bool:
    """Check if current branch has upstream tracking configured.

    Args:
        repo_path: Repository root path

    Returns:
        True if current branch tracks a remote branch, False otherwise
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=repo_path,
            check=False,
        )
        # Returns 0 with output like "origin/main" if tracking exists
        # Returns 128 with error if no tracking configured
        return result.returncode == 0 and result.stdout.strip() != ""
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def exclude_from_git_index(repo_path: Path, patterns: list[str]) -> None:
    """Add patterns to .git/info/exclude to prevent git tracking.

    This is a local-only exclusion (never committed, unlike .gitignore).
    Useful for build artifacts, worktrees, and other local-only files.

    Args:
        repo_path: Repository root path
        patterns: List of patterns to exclude (e.g., [".worktrees/"])
    """
    exclude_file = repo_path / ".git" / "info" / "exclude"
    if not exclude_file.exists():
        return

    # Read existing exclusions
    try:
        existing = set(exclude_file.read_text(encoding="utf-8").splitlines())
    except OSError:
        existing = set()

    # Add new patterns
    new_patterns = [p for p in patterns if p not in existing]
    if new_patterns:
        try:
            with exclude_file.open("a", encoding="utf-8") as f:
                marker = "# Added by spec-kitty (local exclusions)"
                if marker not in existing:
                    f.write(f"\n{marker}\n")
                for pattern in new_patterns:
                    f.write(f"{pattern}\n")
        except OSError:
            pass  # Non-critical, continue silently


#: Branch names treated as a "primary"/trunk branch by the fallback heuristics.
COMMON_PRIMARY_BRANCHES: tuple[str, ...] = ("main", "master", "develop")


def _origin_head_branch(repo_root: Path) -> str | None:
    """Return the branch ``origin/HEAD`` points at, or ``None`` if unresolved."""
    try:
        result = subprocess.run(
            ["git", "symbolic-ref", "refs/remotes/origin/HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return None
    if result.returncode != 0:
        return None
    ref = result.stdout.strip()
    if not ref:
        return None
    return ref.split("/")[-1] or None


def _common_branch_exists(repo_root: Path, branch: str, *, include_remote: bool) -> bool:
    """Return ``True`` when ``branch`` resolves as a ref for the repository.

    ``include_remote=False`` reproduces the feature-bias local-only probe
    (``git rev-parse --verify <branch>``). ``include_remote=True`` reproduces the
    no-feature-bias recommendation probe, which also accepts an ``origin`` ref
    (``refs/heads/<branch>`` or ``refs/remotes/origin/<branch>``). A timeout is
    treated as "unresolved" so the caller advances to the next candidate.
    """
    if include_remote:
        arg_sets = [
            ["git", "rev-parse", "--verify", "--quiet", f"refs/heads/{branch}"],
            ["git", "rev-parse", "--verify", "--quiet", f"refs/remotes/origin/{branch}"],
        ]
    else:
        arg_sets = [["git", "rev-parse", "--verify", branch]]
    for args in arg_sets:
        try:
            result = subprocess.run(
                args,
                cwd=repo_root,
                capture_output=True,
                timeout=5,
                check=False,
            )
        except subprocess.TimeoutExpired:
            continue
        if result.returncode == 0:
            return True
    return False


def resolve_primary_branch(
    repo_root: Path,
    *,
    current_branch: str | None = None,
    bias: bool = True,
) -> str:
    """Detect the primary branch name for the repository.

    Tries multiple methods in order:
    1. origin/HEAD symbolic ref (most reliable for cloned repos)
    2. Current branch (the user is standing on it for a reason)
    3. Check which common branch exists (main, master, develop)
    4. Fallback to "main"

    Args:
        repo_root: Repository root path
        current_branch: Pre-resolved checked-out branch. When ``None`` (default)
            it is auto-detected with :func:`get_current_branch`; callers that
            already know the branch can pass it to avoid a second ``git`` call.
        bias: When ``True`` (default) the checked-out branch wins as the primary
            branch (Method 2) — the historical "feature-branch bias" that keeps
            planning stable on a ticket branch. When ``False`` (no-feature-bias
            mode) the current branch is only honored if it is itself a common
            primary name, the common-branch ladder is probed against local *and*
            origin refs, and — if nothing matches — the resolver defers to the
            default feature-bias cascade as a last resort. This is the mode the
            branch-context recommender needs (see
            ``mission_branch_context._resolve_primary_branch_for_recommendation``)
            so a ticket branch is never mistaken for the primary branch (FR-007).

    Returns:
        Primary branch name (e.g., "main", "master", "develop", "2.x")
    """
    # Method 1: Get from origin's HEAD
    origin_branch = _origin_head_branch(repo_root)
    if origin_branch:
        return origin_branch

    # Method 2: Current branch
    current = current_branch if current_branch is not None else get_current_branch(repo_root)
    if bias:
        if current and current != "HEAD":
            return current
    elif current in COMMON_PRIMARY_BRANCHES:
        return current

    # Method 3: Check which common branch exists
    for branch in COMMON_PRIMARY_BRANCHES:
        if _common_branch_exists(repo_root, branch, include_remote=not bias):
            return branch

    # Method 4: Fallback
    if bias:
        return "main"
    # No-feature-bias exhausted the common-branch ladder; defer to the
    # feature-bias cascade as a last resort (preserves the recommender's
    # historical fallback to the canonical resolution).
    return resolve_primary_branch(repo_root)


def resolve_target_branch(
    mission_slug: str,
    repo_path: Path,
    current_branch: str | None = None,
    respect_current: bool = True,
) -> BranchResolution:
    """Resolve target branch for feature operations without auto-checkout.

    Thin adapter over :func:`specify_cli.core.paths.read_target_branch_from_meta`.

    This function unifies branch resolution logic across all CLI commands.
    It respects the user's current branch and never performs auto-checkout
    to main/master without explicit permission.

    Args:
        mission_slug: Feature identifier (e.g., "038-v0-15-0-quality-bugfix-release")
        repo_path: Repository root path
        current_branch: User's current branch (auto-detected if None)
        respect_current: If True, stay on current branch (default behavior)

    Returns:
        BranchResolution with:
        - target: Target branch from meta.json (or primary-branch fallback)
        - current: User's current branch
        - should_notify: True if current != target (show informational message)
        - action: "proceed" if branches match, "stay_on_current" otherwise

    Raises:
        specify_cli.core.paths.MissionMetaReadError: When meta.json exists but
            is corrupt or unreadable (fail-closed; propagated from the primitive).

    Example:
        >>> resolution = resolve_target_branch("038-bugfix", repo_root, "develop")
        >>> if resolution.should_notify:
        ...     console.print(f"Note: On '{resolution.current}', target is '{resolution.target}'")
        >>> # Proceed on current branch (no checkout)
    """
    # Auto-detect current branch if not provided
    if current_branch is None:
        current_branch = get_current_branch(repo_path)
        if current_branch is None:
            raise RuntimeError("Could not determine current branch")

    # Delegate the meta read to the canonical primitive so the absent-vs-failed
    # decision lives in exactly one place (FR-005 / #2139).
    # Read from the PRIMARY surface — NOT the topology-aware candidate, which
    # under coordination topology resolves to the coordination worktree (no
    # meta.json) and silently fell back to the protected repo primary ``main``
    # (WP00 / FR-004 — the implement-loop refusal-to-main bug).
    #
    # read-side-seam-primary-primitive-closure-01KYKMMT WP07/WP08 (T034/T035,
    # FR-005 / NFR-009): RECORDED FOUNDATION SITE 3/4, deliberately UNROUTED —
    # mirrors ``core/paths.py``'s target-branch resolution one layer up the
    # git-ops composition root; same import-layering + behaviour-preservation
    # rationale (``PlacementSeam.read_dir`` never reaches this target-branch
    # resolution -- it routes to ``resolve_retrospective_home`` or
    # ``resolve_artifact_surface``, neither of which calls
    # ``resolve_target_branch`` -- so no literal cycle is at stake here either;
    # the constraints are early-import layering for ``core/git_ops.py`` and
    # behaviour-preservation with the deleted wrapper's pre-delegation body).
    # WP08 deleted the public wrapper this site imported; calls the
    # module-private ``_compose_primary_feature_dir`` leaf directly
    # (``_FOUNDATION_SANCTION_SEED`` token in
    # ``tests/architectural/test_no_read_side_bypass.py`` re-pointed in the
    # same commit — see that file's entry for ``resolve_target_branch``).
    from specify_cli.core.paths import read_target_branch_from_meta
    from specify_cli.missions._read_path_resolver import (
        _canonicalize_primary_read_handle,
        _compose_primary_feature_dir,
    )

    feature_dir = _compose_primary_feature_dir(
        repo_path,
        _canonicalize_primary_read_handle(repo_path, mission_slug),
    )
    fallback = resolve_primary_branch(repo_path)
    branch = read_target_branch_from_meta(feature_dir)
    target = branch if branch is not None else fallback

    # Check if branches match
    if current_branch == target:
        return BranchResolution(
            target=target,
            current=current_branch,
            should_notify=False,
            action="proceed",
        )

    # Branches differ
    if respect_current:
        # Stay on current branch, notify user
        return BranchResolution(
            target=target,
            current=current_branch,
            should_notify=True,
            action="stay_on_current",
        )
    else:
        # Legacy behavior: auto-checkout allowed (not recommended)
        return BranchResolution(
            target=target,
            current=current_branch,
            should_notify=True,
            action="checkout_target",
        )


__all__ = [
    "BranchResolution",
    "exclude_from_git_index",
    "get_current_branch",
    "has_remote",
    "has_unborn_head",
    "has_tracking_branch",
    "init_git_repo",
    "is_git_repo",
    "resolve_primary_branch",
    "resolve_target_branch",
    "run_command",
]
