"""Sparse-checkout detection, session warning, and preflight API.

This module is the single source of truth for sparse-checkout state handling in
spec-kitty 3.x. v3.0.0 removed sparse-checkout support but did not ship a
migration for existing user repos; this module surfaces the lingering state so
doctor and preflights can act on it, and provides the once-per-process warning
that other CLI surfaces hook into.

See Priivacy-ai/spec-kitty#588 for the data-loss regression that motivated this
surface and the four-layer hybrid architecture recorded in ADR
2026-04-14-1-sparse-checkout-defense-in-depth.

Public API
----------
- :class:`SparseCheckoutState` — immutable per-path probe result.
- :class:`SparseCheckoutScanReport` — aggregate over a repo and its worktrees.
- :class:`SparseCheckoutPreflightError` — raised by ``require_no_sparse_checkout``.
- :func:`scan_path` — pure detection for a single repo or worktree.
- :func:`scan_repo` — pure detection for a primary repo plus ``.worktrees/*``.
- :func:`warn_if_sparse_once` — emits a WARNING log line exactly once per
  process when sparse-checkout state is active.
- :func:`require_no_sparse_checkout` — hard-block preflight used by merge and
  implement call sites.

The module is intentionally side-effect-free except for spawning ``git config``
subprocesses and reading on-disk files. No function in this module mutates
git configuration or sparse-checkout state; remediation lives in WP03.
"""

from __future__ import annotations

from specify_cli.core.constants import KITTY_SPECS_DIR
from specify_cli.lanes.branch_naming import (
    code_lane_branch_name,
    lane_id_for_worktree_dir,
    parse_lane_worktree_dir,
    resolve_mid8,
)
from specify_cli.lanes.compute import PLANNING_LANE_ID
from specify_cli.mission_metadata import load_meta
import enum
import logging
import subprocess
from dataclasses import dataclass, replace
from pathlib import Path

logger = logging.getLogger(__name__)

__all__ = [
    "SparseCheckoutKind",
    "SparseCheckoutState",
    "SparseCheckoutScanReport",
    "SparseCheckoutPreflightError",
    "scan_path",
    "scan_repo",
    "warn_if_sparse_once",
    "require_no_sparse_checkout",
    "_reset_session_warning_state",
]


class SparseCheckoutKind(enum.StrEnum):
    """Classification for active sparse-checkout state."""

    LEGACY_USER = "legacy_user_sparse_checkout"
    MANAGED_LANE = "managed_lane_sparse_checkout"
    UNKNOWN = "unknown_sparse_checkout"


@dataclass(frozen=True)
class SparseCheckoutState:
    """Result of probing a repository or worktree for sparse-checkout state."""

    path: Path
    config_enabled: bool
    pattern_file_path: Path | None
    pattern_file_present: bool
    pattern_line_count: int
    is_worktree: bool
    sparse_checkout_kind: SparseCheckoutKind = SparseCheckoutKind.LEGACY_USER

    @property
    def is_active(self) -> bool:
        """Canonical signal used by preflights and doctor.

        Per research.md R6, ``core.sparseCheckout=true`` is the definitive
        indicator that git will apply sparse-checkout filtering. A lingering
        pattern file without that config is harmless and does not flip
        ``is_active`` to True.
        """
        return self.config_enabled

    @property
    def is_managed_lane(self) -> bool:
        """True iff this active sparse-checkout state is owned by lane policy."""
        return self.is_active and self.sparse_checkout_kind is SparseCheckoutKind.MANAGED_LANE

    @property
    def is_blocking(self) -> bool:
        """True iff sparse-checkout should block legacy preflights/remediation."""
        return self.is_active and not self.is_managed_lane


@dataclass(frozen=True)
class SparseCheckoutScanReport:
    """Aggregate scan of a primary repo and its lane worktrees."""

    primary: SparseCheckoutState
    worktrees: tuple[SparseCheckoutState, ...]

    @property
    def any_active(self) -> bool:
        """True iff the primary repo or any worktree has sparse-checkout active."""
        return self.primary.is_active or any(w.is_active for w in self.worktrees)

    @property
    def any_blocking(self) -> bool:
        """True iff legacy/unknown sparse-checkout state is active."""
        return self.primary.is_blocking or any(w.is_blocking for w in self.worktrees)

    @property
    def affected_paths(self) -> tuple[Path, ...]:
        """Paths where legacy/unknown sparse-checkout is active."""
        hits: list[Path] = []
        if self.primary.is_blocking:
            hits.append(self.primary.path)
        hits.extend(w.path for w in self.worktrees if w.is_blocking)
        return tuple(hits)


# ---------------------------------------------------------------------------
# Pure detection
# ---------------------------------------------------------------------------


def _read_sparse_config_flag(path: Path) -> bool:
    """Return True iff ``git config --get core.sparseCheckout`` is ``true`` at ``path``.

    Runs git inside ``path`` so worktree-local config layering is honoured
    (see WP02 Risks in the WP spec). Any failure — non-git directory, git
    exit != 0 with no value, unreadable config — is treated as "not enabled".
    """
    try:
        result = subprocess.run(
            ["git", "config", "--get", "core.sparseCheckout"],
            cwd=str(path),
            capture_output=True,
            text=True,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    if result.returncode != 0:
        return False
    return result.stdout.strip().lower() == "true"


def _resolve_sparse_pattern_file(path: Path, *, is_worktree: bool) -> Path | None:
    """Resolve the on-disk sparse-checkout pattern file for ``path``.

    For the primary repo, this is ``<path>/.git/info/sparse-checkout``. For a
    worktree, git stores per-worktree state under
    ``<git-common-dir>/worktrees/<name>/info/sparse-checkout``; we resolve that
    by running ``git rev-parse --git-dir`` *inside* the worktree path.
    """
    if not is_worktree:
        return path / ".git" / "info" / "sparse-checkout"

    try:
        result = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            cwd=str(path),
            capture_output=True,
            text=True,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    git_dir_raw = result.stdout.strip()
    if not git_dir_raw:
        return None
    git_dir = Path(git_dir_raw)
    if not git_dir.is_absolute():
        git_dir = (path / git_dir).resolve()
    return git_dir / "info" / "sparse-checkout"


def _count_nonempty_noncomment_lines(p: Path) -> int:
    """Count pattern lines in a sparse-checkout file (non-empty, non-comment)."""
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return 0
    count = 0
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        count += 1
    return count


def scan_path(path: Path, *, is_worktree: bool) -> SparseCheckoutState:
    """Probe a single repo or worktree for sparse-checkout state.

    Reads ``git config --get core.sparseCheckout`` at the path and inspects the
    sparse-checkout pattern file. Never mutates anything on disk or in git
    configuration. A non-existent or non-git ``path`` returns an all-negative
    state (``config_enabled=False``, ``pattern_file_present=False``,
    ``pattern_line_count=0``).
    """
    config_enabled = _read_sparse_config_flag(path)
    pattern_file_path = _resolve_sparse_pattern_file(path, is_worktree=is_worktree)
    pattern_file_present = pattern_file_path is not None and pattern_file_path.exists()
    pattern_line_count = _count_nonempty_noncomment_lines(pattern_file_path) if pattern_file_present and pattern_file_path is not None else 0
    return SparseCheckoutState(
        path=path,
        config_enabled=config_enabled,
        pattern_file_path=pattern_file_path,
        pattern_file_present=pattern_file_present,
        pattern_line_count=pattern_line_count,
        is_worktree=is_worktree,
    )


@dataclass(frozen=True)
class _ManagedLanePolicy:
    mission_slug: str
    expected_patterns: frozenset[str]

    def matches_path(self, path: Path) -> bool:
        return lane_id_for_worktree_dir(path.name, self.mission_slug) is not None

    def expected_branch_for(self, path: Path) -> str | None:
        """The branch a managed lane worktree dir is expected to be on.

        ``None`` for a non-lane path AND for the planning (repo-root) lane:
        that lane has no worktree of its own -- ``.worktrees/<slug>-lane-
        planning`` is exactly the phantom path #5100 is about, and
        ``code_lane_branch_name`` refuses it (ValueError). This preflight
        must classify that state as UNKNOWN (the pre-existing behaviour),
        never crash (#5100 cycle-1 review regression).
        """
        lane_id = lane_id_for_worktree_dir(path.name, self.mission_slug)
        return None if lane_id is None or lane_id == PLANNING_LANE_ID else code_lane_branch_name(self.mission_slug, lane_id)


def _read_patterns(path: Path) -> frozenset[str] | None:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    return frozenset(line.strip() for line in text.splitlines() if line.strip() and not line.strip().startswith("#"))


def _policy_from_meta(raw: dict[str, object] | None) -> _ManagedLanePolicy | None:
    """Build a managed-lane policy from one Mission's ``meta.json``, or ``None``.

    The single gate for "this Mission has lane policy": a non-empty
    ``coordination_branch`` string, a non-empty ``mission_slug`` and a
    ``mission_id`` of at least 8 characters. Both policy sources (the
    repository-root checkout's ``kitty-specs/`` and a lane worktree's own tree)
    route through it, so the managed pattern set has exactly one definition and
    a Mission without coordination topology can never be classified as managed.
    """
    if raw is None:
        return None

    try:
        from specify_cli.coordination.workspace import lane_sparse_checkout_patterns
    except ImportError:
        return None

    coord_branch = raw.get("coordination_branch")
    mission_slug = raw.get("mission_slug") or raw.get("slug")
    mission_id = raw.get("mission_id")
    if not (
        isinstance(coord_branch, str) and coord_branch and isinstance(mission_slug, str) and mission_slug and isinstance(mission_id, str) and len(mission_id) >= 8
    ):
        return None
    # Route through the canonical resolver (FR-001): the guard above
    # guarantees a full str ``mission_id`` (>= 8) and a str ``mission_slug``,
    # so this is byte-identical to the prior ``mission_id[:8]``.
    mid8 = resolve_mid8(mission_slug, mission_id=mission_id)
    return _ManagedLanePolicy(
        mission_slug=mission_slug,
        expected_patterns=frozenset(lane_sparse_checkout_patterns(mission_slug, mid8)),
    )


def _load_managed_lane_policies(repo_root: Path) -> tuple[_ManagedLanePolicy, ...]:
    specs_dir = repo_root / KITTY_SPECS_DIR
    if not specs_dir.is_dir():
        return ()

    policies: list[_ManagedLanePolicy] = []
    for meta_path in sorted(specs_dir.glob("*/meta.json")):
        policy = _policy_from_meta(load_meta(meta_path.parent, on_malformed="none"))
        if policy is not None:
            policies.append(policy)
    return tuple(policies)


def _policy_from_lane_worktree(path: Path) -> _ManagedLanePolicy | None:
    """Resolve a lane worktree's managed policy from the lane's OWN Mission record.

    ``_load_managed_lane_policies`` reads the repository-root checkout's
    ``kitty-specs/``, i.e. whatever its *current branch* committed, so a branch
    that does not carry a (possibly long-merged) Mission's ``kitty-specs/<slug>/``
    hides that Mission entirely and its own lane worktrees fall back to legacy
    state (#6844). The lane worktree carries the same ``meta.json`` in its own
    tree, pinned to its own branch, so reading it here makes the classification
    independent of which branch the repository-root checkout stands on.

    Fail closed: an unrecognised directory name, a missing ``meta.json``, or a
    record that fails the shared gate returns ``None``, which leaves the caller
    with the pre-#6844 verdict. No read failure escapes either: under
    ``on_malformed="none"`` :func:`load_meta` absorbs both a plain read failure
    (``OSError``) and a non-UTF-8 file (``UnicodeDecodeError``) to ``None``, so
    no ``except`` clause is needed here.
    """
    parsed = parse_lane_worktree_dir(path.name)
    if parsed is None:
        return None
    mission_dir = parsed[0]
    return _policy_from_meta(load_meta(path / KITTY_SPECS_DIR / mission_dir, on_malformed="none"))


def _policies_for_worktree(path: Path, root_policies: tuple[_ManagedLanePolicy, ...], *, is_active: bool) -> tuple[_ManagedLanePolicy, ...]:
    """Policies to classify ``path`` with: the root-derived set, plus the lane's own.

    The lane-local record is consulted **only** when no root-derived policy
    already matches the path, because :func:`_classify_worktree_state` treats
    more than one candidate as ``UNKNOWN``: adding a second, identical policy for
    the common case (the root branch knows the Mission too) would turn a correct
    ``MANAGED_LANE`` verdict into ``UNKNOWN``. An inactive worktree needs no
    policy at all (the classifier returns early), so it is not read.
    """
    if not is_active or any(policy.matches_path(path) for policy in root_policies):
        return root_policies
    local = _policy_from_lane_worktree(path)
    if local is None:
        return root_policies
    return (*root_policies, local)


def _registered_worktree_paths(repo_root: Path) -> frozenset[Path]:
    try:
        output = subprocess.check_output(
            ["git", "-C", str(repo_root), "worktree", "list", "--porcelain"],
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except (OSError, subprocess.SubprocessError):
        return frozenset()
    paths: set[Path] = set()
    for line in output.splitlines():
        if line.startswith("worktree "):
            paths.add(Path(line.removeprefix("worktree ")).resolve(strict=False))
    return frozenset(paths)


def _current_branch(path: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(path), "branch", "--show-current"],
            capture_output=True,
            text=True,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    branch = result.stdout.strip()
    return branch or None


def _classify_worktree_state(
    state: SparseCheckoutState,
    *,
    policies: tuple[_ManagedLanePolicy, ...],
    registered_worktrees: frozenset[Path],
) -> SparseCheckoutState:
    if not state.is_active:
        return state
    candidates = [policy for policy in policies if policy.matches_path(state.path)]
    if not candidates:
        return state
    if len(candidates) != 1:
        return replace(state, sparse_checkout_kind=SparseCheckoutKind.UNKNOWN)
    expected_branch = candidates[0].expected_branch_for(state.path)
    if expected_branch is None or _current_branch(state.path) != expected_branch:
        return replace(state, sparse_checkout_kind=SparseCheckoutKind.UNKNOWN)
    if state.path.resolve(strict=False) not in registered_worktrees:
        return replace(state, sparse_checkout_kind=SparseCheckoutKind.UNKNOWN)
    if not state.pattern_file_present or state.pattern_file_path is None:
        return replace(state, sparse_checkout_kind=SparseCheckoutKind.UNKNOWN)

    present = _read_patterns(state.pattern_file_path)
    if present is None:
        return replace(state, sparse_checkout_kind=SparseCheckoutKind.UNKNOWN)
    if candidates[0].expected_patterns.issubset(present):
        return replace(state, sparse_checkout_kind=SparseCheckoutKind.MANAGED_LANE)
    return replace(state, sparse_checkout_kind=SparseCheckoutKind.UNKNOWN)


def scan_repo(repo_root: Path) -> SparseCheckoutScanReport:
    """Probe the primary repo and every lane worktree beneath ``.worktrees/``.

    Worktree candidates are immediate children of ``<repo_root>/.worktrees`` that
    are directories and contain a ``.git`` entry (file or dir — git worktrees
    use a file pointer). Non-worktree directories are skipped silently.

    Each candidate's managed-lane policy comes from the repository-root
    checkout's ``kitty-specs/`` when that branch knows the Mission, and from the
    lane's own ``kitty-specs/<slug>/meta.json`` otherwise, so a branch switch
    cannot reclassify a managed lane as legacy state (#6844).
    """
    primary = scan_path(repo_root, is_worktree=False)
    policies = _load_managed_lane_policies(repo_root)
    registered_worktrees = _registered_worktree_paths(repo_root)
    worktrees_dir = repo_root / ".worktrees"
    worktree_states: list[SparseCheckoutState] = []
    if worktrees_dir.exists() and worktrees_dir.is_dir():
        for child in sorted(worktrees_dir.iterdir()):
            if not child.is_dir():
                continue
            if not (child / ".git").exists():
                continue
            state = scan_path(child, is_worktree=True)
            worktree_states.append(
                _classify_worktree_state(
                    state,
                    policies=_policies_for_worktree(child, policies, is_active=state.is_active),
                    registered_worktrees=registered_worktrees,
                )
            )
    return SparseCheckoutScanReport(primary=primary, worktrees=tuple(worktree_states))


# ---------------------------------------------------------------------------
# Session warning (once-per-process)
# ---------------------------------------------------------------------------

# Module-level flag per R5 — simplest possible once-per-process mechanism.
_SPARSE_WARNING_EMITTED: bool = False


def warn_if_sparse_once(repo_root: Path, *, command: str) -> None:
    """Emit a WARNING log line once per process if sparse-checkout state is active.

    Subsequent calls in the same process are no-ops even if the sparse state
    changes. The stable structured-log marker ``spec_kitty.sparse_checkout.detected``
    is searchable in log aggregators.

    Detection failures are swallowed: a broken probe must never break the CLI
    command that invoked this hook. Remediation is handled by WP03; advisory
    surfacing is the job of this function.
    """
    global _SPARSE_WARNING_EMITTED
    if _SPARSE_WARNING_EMITTED:
        return
    try:
        report = scan_repo(repo_root)
    except Exception:  # noqa: BLE001 — never let detection block the command
        return
    if not report.any_blocking:
        return
    affected = ", ".join(str(p) for p in report.affected_paths)
    logger.warning(
        "spec_kitty.sparse_checkout.detected command=%s repo=%s affected=%s fix='spec-kitty doctor sparse-checkout --fix'",
        command,
        repo_root,
        affected,
    )
    _SPARSE_WARNING_EMITTED = True


def _reset_session_warning_state() -> None:
    """Test helper — resets the session-warning flag. Not for production use."""
    global _SPARSE_WARNING_EMITTED
    _SPARSE_WARNING_EMITTED = False


# ---------------------------------------------------------------------------
# Preflight API
# ---------------------------------------------------------------------------


class SparseCheckoutPreflightError(RuntimeError):
    """Raised when a hard-block preflight detects active sparse-checkout state."""

    def __init__(self, command: str, report: SparseCheckoutScanReport) -> None:
        self.command = command
        self.report = report
        affected = "\n".join(f"  {p}" for p in report.affected_paths)
        super().__init__(
            f"{command} aborted: legacy sparse-checkout state detected.\n"
            f"\nAffected paths:\n{affected}\n"
            "\nThis repository has core.sparseCheckout=true configured, which\n"
            "v3.x spec-kitty does not handle correctly and which has caused\n"
            "silent data loss in prior mission merges (see\n"
            "spec-kitty/spec-kitty#588).\n"
            "\nFix:\n"
            "  spec-kitty doctor sparse-checkout --fix\n"
            "\nIf you have an intentional sparse configuration and understand\n"
            "the risk, you may pass --allow-sparse-checkout to proceed. Use of\n"
            "this override is logged at WARNING level."
        )


def require_no_sparse_checkout(
    repo_root: Path,
    *,
    command: str,
    override_flag: bool,
    actor: str | None,
    mission_slug: str | None,
    mission_id: str | None,
) -> None:
    """Preflight for commands that must not operate under sparse-checkout.

    If ``override_flag`` is True and sparse-checkout is active, emits the
    structured override log record (FR-008) and returns. Otherwise raises
    :class:`SparseCheckoutPreflightError` when sparse-checkout is active.

    ``--force`` is intentionally **not** a parameter here: callers that want
    to bypass must plumb their own ``--allow-sparse-checkout`` flag through to
    ``override_flag``.
    """
    report = scan_repo(repo_root)
    if not report.any_blocking:
        return
    if override_flag:
        logger.warning(
            "spec_kitty.override.sparse_checkout command=%s mission_slug=%s mission_id=%s actor=%s repo=%s affected=%s",
            command,
            mission_slug or "<none>",
            mission_id or "<none>",
            actor or "<unknown>",
            repo_root,
            ",".join(str(p) for p in report.affected_paths),
        )
        return
    raise SparseCheckoutPreflightError(command=command, report=report)
