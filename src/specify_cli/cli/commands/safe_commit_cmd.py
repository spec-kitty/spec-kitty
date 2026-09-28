"""Generic ``spec-kitty safe-commit`` command.

Post-#1348 (mission ``mission-coordination-branch-atomic-event-log``) the
underlying :func:`specify_cli.git.commit_helpers.safe_commit` helper resolves a
single :class:`~mission_runtime.context.CommitTarget` — the ONE destination
authority — and structurally enforces that the commit lands on it.

This CLI surfaces that contract via the ``--to-branch`` flag. There is exactly
ONE destination resolution in this file (:func:`_resolve_commit_target`), fed
into ONE ``CommitTarget``; the WP02 ``safe_commit`` facade makes the sole
protection decision (C-GUARD-1, C-GUARD-3a). No env-var inference escape hatch.

That single resolver discriminates TWO responsibilities (FR-007 / NFR-002):

* **Mission-aware planning commit** — when ``--to-branch`` is omitted and a file
  argument lives under ``kitty-specs/<slug>/`` for a resolvable mission, the
  destination is resolved through the WP03 seam
  (:func:`mission_runtime.resolve_placement_only`), never from the current
  ``HEAD`` branch. This is the #2063 fix.
* **Generic operator-file commit** — ``--to-branch X`` lands on ``X``; when
  omitted (and not a mission planning commit), the destination resolves from the
  current ``HEAD`` branch (with a one-line stderr deprecation: ``--to-branch``
  becomes required in v3.3). This generic path is unchanged.

Directory and bulk arguments expand to their contained changed / untracked
files (validated against the CommitTarget's worktree) with an explicit
expansion report, so a directory argument no longer trips the staging backstop
(#1820 / #1330 / F-002).

post-merge-write-authoring-finish-01KYRRM5 WP04 (#3033 T016/T017)
-------------------------------------------------------------------

**T017 (SC-001).** The single ``safe_commit`` call this command makes
(:func:`_resolve_capability_for_target`) asserts
``GuardCapability.POST_CONSOLIDATION_WRITE`` instead of the default
``STANDARD`` ONLY when the resolved mission-aware target is recognised
(:func:`~specify_cli.coordination.write_seam.is_post_consolidation_write_target`,
PUBLIC signals only) as WP03's E2 CONSOLIDATED short-circuit -- a mission
whose Target Ref has been deleted (published to trunk), now resolving to the
repository-root checkout on the Primary Branch. Every other commit this
command performs (mission-aware or generic) keeps asserting ``STANDARD`` --
refused on a protected destination, exactly as before.

**T016 (FR-006 / SC-004).** When the mission-aware seam signals its
structured off-checkout refusal (``ActionContextError`` code
``CONSOLIDATED_CONTENT_ABSENT`` -- the mission is published but this
checkout does not carry its consolidated content), this command raises
:class:`MissionAwareCommitRefused` (a ``ValueError`` subclass, so the
existing top-level exception handler below reports it with exit code 1 and
performs no commit) INSTEAD OF silently falling back to the generic
``--to-branch``/HEAD path -- falling through there would land the commit on
the WRONG branch (the current HEAD) rather than refusing (violating C-004,
"off-checkout = refuse, not force"). Every OTHER ``ActionContextError``
(mission genuinely unresolvable, not a real mission path, etc.) keeps
falling back to the generic path unchanged (#1784).
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import typer
from specify_cli.cli.console import console

from kernel.resolution import resolve_rejecting_loops
from mission_runtime import (
    CommitTarget,
    MissionArtifactKind,
    kind_for_mission_file,
)
from specify_cli.core.commit_guard import GuardCapability
from specify_cli.core.constants import KITTY_SPECS_DIR
from specify_cli.core.git_ops import get_current_branch
from specify_cli.coordination.write_seam import is_post_consolidation_write_target
from specify_cli.git import ProtectedBranchCommitError, safe_commit
from specify_cli.git.commit_helpers import (
    SafeCommitBackstopError,
    SafeCommitError,
)
from specify_cli.task_utils import TaskCliError, find_repo_root

# Mirrors resolution.py's private ``_CONSOLIDATED_CONTENT_ABSENT_CODE`` value
# (mirrored, not imported -- see the same rationale documented in
# ``coordination.write_seam``'s module docstring / ``_CONSOLIDATED_CONTENT_
# ABSENT_CODE`` constant: the code string is the resolver's public
# "structured signal" contract, not a shared importable constant).
_CONSOLIDATED_CONTENT_ABSENT_CODE = "CONSOLIDATED_CONTENT_ABSENT"


class MissionAwareCommitRefused(ValueError):
    """FR-006 (T016): a mission-aware planning commit refuses off-checkout (SC-004).

    Raised when :func:`mission_runtime.resolve_placement_only` signals its
    structured ``CONSOLIDATED_CONTENT_ABSENT`` refusal (the mission is
    published/E2 but this checkout does not carry its consolidated content).
    Deliberately NOT folded into the generic ``except ActionContextError:
    return None`` fallback in :func:`_resolve_mission_aware_target` -- that
    fallback exists for "this doesn't look like a real, resolvable mission,
    try the generic HEAD path" (#1784); silently falling through here would
    let the commit land on the WRONG branch (the current HEAD) instead of
    refusing, defeating C-004 ("off-checkout = refuse, not force"). A
    ``ValueError`` subclass so the CLI's existing top-level ``except
    ValueError`` handler reports it with exit code 1 and no commit
    performed -- no new except arm needed.
    """



def _current_worktree_root() -> Path:
    """Return the git top-level for the current worktree.

    ``find_repo_root()`` intentionally resolves Spec Kitty worktrees back to the
    main repository for status/event callers. This command commits operator
    files, so it must preserve the current worktree as the commit target.
    """
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=Path.cwd(),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if result.returncode == 0 and result.stdout.strip():
        return Path(result.stdout.strip()).resolve()
    # Explicit annotation (campsite, pre-existing under the project's
    # ``follow_imports = "skip"`` mypy config): the cross-module
    # ``task_utils.find_repo_root`` call is seen as returning ``Any`` when
    # this file is type-checked in isolation; the annotation re-narrows it
    # back to ``Path`` (matching the sibling chokepoint pattern this WP
    # already applies in ``coordination/write_seam.py``).
    fallback_root: Path = find_repo_root()
    return fallback_root


def _changed_paths_under(repo_root: Path, rel_dir: str) -> list[str]:
    """Return changed / untracked files (relative to ``repo_root``) under ``rel_dir``.

    Uses ``git status --porcelain --untracked-files=all`` scoped to the
    directory so the expansion is validated against the actual worktree state —
    a directory argument resolves to exactly the files git would stage.
    """
    result = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all", "--", rel_dir],
        cwd=repo_root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Unable to inspect directory '{rel_dir}' before commit.")
    paths: list[str] = []
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        # Porcelain v1 line: ``XY <path>`` (or ``XY <old> -> <new>`` for renames).
        entry = line[3:]
        if " -> " in entry:
            entry = entry.split(" -> ", 1)[1]
        paths.append(entry.strip().strip('"'))
    return paths


def _expand_arguments(
    repo_root: Path,
    normalized_files: list[Path],
) -> tuple[list[Path], list[str]]:
    """Expand directory arguments to contained changed / untracked files.

    Returns the expanded absolute paths and a list of human-readable expansion
    report lines (``Expanding dir/ → N files: …``). File arguments pass through
    unchanged; directory arguments expand against the worktree state.
    """
    expanded: list[Path] = []
    report_lines: list[str] = []
    seen: set[Path] = set()

    def _add(path: Path) -> None:
        if path not in seen:
            seen.add(path)
            expanded.append(path)

    for path in normalized_files:
        if path.is_dir():
            rel_dir = str(path.relative_to(repo_root))
            contained = _changed_paths_under(repo_root, rel_dir)
            contained_abs = [(repo_root / rel).resolve() for rel in contained]
            display = ", ".join(contained) if contained else "(no changed files)"
            report_lines.append(
                f"Expanding {rel_dir}/ → {len(contained_abs)} files: {display}"
            )
            for abs_path in contained_abs:
                _add(abs_path)
        else:
            _add(path)
    return expanded, report_lines


def _has_candidate_changes(repo_root: Path, files_to_commit: list[Path]) -> bool:
    if not files_to_commit:
        return False
    rel_paths = [str(path.relative_to(repo_root)) if path.is_absolute() else str(path) for path in files_to_commit]
    result = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all", "--", *rel_paths],
        cwd=repo_root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError("Unable to inspect requested files before commit.")
    return bool(result.stdout.strip())


def _payload(*, success: bool, committed: bool = False, files: list[str] | None = None, error: str | None = None) -> dict[str, object]:
    payload: dict[str, object] = {
        "result": "success" if success else "error",
        "success": success,
        "committed": committed,
    }
    if files is not None:
        payload["files"] = files
    if error is not None:
        payload["error"] = error
    return payload


def _mission_slug_from_paths(repo_root: Path, files: list[Path]) -> str | None:
    """Return the mission slug iff a file argument lives under ``kitty-specs/<slug>/``.

    The mission-aware DISCRIMINATOR (FR-007 / NFR-002): a planning artifact is
    addressed by a path inside ``kitty-specs/<slug>/`` (e.g. ``spec.md`` /
    ``plan.md`` / ``tasks.md``). When a file argument resolves under that prefix
    the commit targets a mission's planning artifacts and routes through the WP03
    seam. Everything else (operator files, config, generic worktree edits) stays
    on the generic ``--to-branch`` / HEAD path. Returns the first slug found, or
    ``None`` when no argument is a kitty-specs artifact.
    """
    for path in files:
        try:
            rel = path.resolve().relative_to(repo_root.resolve())
        except ValueError:
            continue
        parts = rel.parts
        if len(parts) >= 2 and parts[0] == KITTY_SPECS_DIR:
            return parts[1]
    return None


def _mission_file_kind(repo_root: Path, files: list[Path], mission_slug: str) -> MissionArtifactKind | None:
    """Classify the first kitty-specs file argument to its artifact kind.

    write-surface-coherence WP03 / T012: the safe-commit command holds file
    paths, so it derives the kind through the ONE public classifier
    (:func:`mission_runtime.kind_for_mission_file`) rather than re-deriving the
    partition here (NFR-004). The kind then selects the primary vs topology-routed
    placement: a planning artifact (``spec.md`` / ``plan.md`` / ``tasks/WP*.md``)
    is a primary kind and lands on the primary ``target_branch``; a status
    bookkeeping file (``status.events.jsonl``) keeps the coordination route.
    """
    for path in files:
        try:
            rel = path.resolve().relative_to(repo_root.resolve())
        except ValueError:
            continue
        kind = kind_for_mission_file(rel, mission_slug=mission_slug)
        if kind is not None:
            return kind
    return None


def _resolve_mission_aware_target(
    repo_root: Path, mission_slug: str, kind: MissionArtifactKind
) -> CommitTarget | None:
    """Resolve the mission-aware planning :class:`CommitTarget` via the WP03 seam.

    FR-007 / #2063: the mission-aware planning commit resolves its destination
    from :func:`mission_runtime.resolve_placement_only` (the placement projection
    — the SAME authority status events resolve to), NOT from
    ``get_current_branch``/HEAD. The projection is kind-aware
    (write-surface-coherence WP03 / T012): a planning-artifact ``kind`` resolves
    to the primary ``target_branch`` under coordination topology (no coord
    transit, FR-003 / C-005). Returns ``None`` when the seam cannot resolve the
    mission (no ``meta.json`` yet / not a real mission), so the caller falls back
    to the generic path rather than failing a legitimate operator commit that
    merely *looks* like it lives under ``kitty-specs/``.

    WP04 / T016 (FR-006 / SC-004): a resolver refusal carrying code
    ``CONSOLIDATED_CONTENT_ABSENT`` is NOT folded into that ``None`` fallback
    — see :class:`MissionAwareCommitRefused`'s docstring for why.

    WP05 (#2966 part-2 / FR-008) briefly rerouted this call through the shared
    :func:`mission_runtime.resolve_write_target_or_degrade` helper for
    call-site parity with its three siblings (``coordination.status_transition``,
    ``events.decision_log``, ``git.bookkeeping_commit``). That reroute was
    reverted (partition-authority-residuals / #2966 follow-up): the shared
    helper's ``_mission_meta_exists`` pre-gate short-circuits BEFORE
    :func:`~mission_runtime.resolve_placement_only` is ever consulted whenever
    a mission has no ``meta.json`` yet — exactly the create→first-write window
    a freshly-written ``kitty-specs/<slug>/spec.md`` sits in (the #2063 case
    this function exists to fix). That pre-gate is CORRECT for the three
    siblings, whose OWN fallback is a caller-supplied ``degrade_ref`` threaded
    INTO the helper (so the helper must decide, up front, whether to trust
    ``resolve_placement_only``'s internal silent-default-branch behaviour or
    hand back the caller's explicit ref) — but it is the WRONG contract here:
    this call site's fallback lives entirely in the CALLER
    (:func:`_resolve_commit_target`'s generic HEAD path), so there is nothing
    to gate — ``resolve_placement_only`` is the single source of truth on
    whether a ``kitty-specs/`` artifact resolves, meta.json or not, and this
    function already translates every failure mode it can raise (see below).
    Calling it directly (as before WP05) is therefore the minimal correct
    fix, not a weakening of the pre-gate (which stays intact, unmodified, for
    its three original callers).
    """
    from mission_runtime import ActionContextError, resolve_placement_only

    try:
        return resolve_placement_only(repo_root, mission_slug, kind=kind)
    except ActionContextError as exc:
        if exc.code == _CONSOLIDATED_CONTENT_ABSENT_CODE:
            raise MissionAwareCommitRefused(str(exc)) from exc
        return None
    except (FileNotFoundError, ValueError):
        return None


def _resolve_commit_target(
    *,
    explicit_to_branch: str | None,
    repo_root: Path,
    files: list[Path],
) -> CommitTarget:
    """Resolve the single :class:`CommitTarget` the commit lands on.

    This is the ONLY destination resolution in this file (C-GUARD-3a — single
    destination authority), discriminating TWO responsibilities (FR-007 /
    NFR-002):

    * **Mission-aware planning commit** — when ``--to-branch`` is omitted and a
      file argument lives under ``kitty-specs/<slug>/`` for a resolvable mission,
      the destination is resolved through the WP03 seam
      (:func:`mission_runtime.resolve_placement_only`), never from ``HEAD``. This
      is the #2063 fix: the planning artifact lands on the seam-resolved surface.
    * **Generic operator-file commit** — ``--to-branch X`` resolves to ``X``;
      when omitted (and not a resolvable mission planning commit) the destination
      is the current ``HEAD`` branch (with a stderr v3.3 deprecation notice). This
      path is unchanged (NFR-002 preserved).

    The resulting ``CommitTarget`` is the sole authority handed to ``safe_commit``,
    whose embedded guard makes the protection decision.
    """
    if explicit_to_branch is not None and explicit_to_branch != "":
        # Normalize fully-qualified refs/heads/<name> → <name>. The helper
        # rejects fully-qualified destination refs with
        # SafeCommitDestinationRefShape; the CLI normalizes for ergonomics.
        ref = explicit_to_branch
        if ref.startswith("refs/heads/"):
            ref = ref[len("refs/heads/"):]
        return CommitTarget(ref=ref)

    mission_slug = _mission_slug_from_paths(repo_root, files)
    if mission_slug is not None:
        # write-surface-coherence WP03 / T012: classify the file to its artifact
        # kind so a planning artifact lands on the primary ``target_branch`` (not
        # coord) under coordination topology. An unclassifiable kitty-specs file
        # falls through to the generic HEAD path rather than mis-routing.
        kind = _mission_file_kind(repo_root, files, mission_slug)
        if kind is not None:
            seam_target = _resolve_mission_aware_target(repo_root, mission_slug, kind)
            if seam_target is not None:
                return seam_target

    inferred = get_current_branch(repo_root)
    if inferred is None or inferred == "":
        raise ValueError(
            "Cannot resolve destination ref: HEAD is detached or not on a branch. "
            "Pass --to-branch <ref> explicitly."
        )
    # Print deprecation to stderr (not stdout) so scripted callers parsing
    # --json on stdout are not affected.
    print(
        "warning: --to-branch will be required in v3.3; pass it explicitly",
        file=sys.stderr,
    )
    return CommitTarget(ref=inferred)


def _resolve_capability_for_target(
    repo_root: Path, files: list[Path], target: CommitTarget
) -> GuardCapability:
    """WP04 / T017 (#3033 SC-001): select the ONE ``safe_commit`` capability.

    ``GuardCapability.STANDARD`` (default) for every ordinary commit --
    refused on a protected destination, exactly as before. Only the
    mission-aware CONSOLIDATED (E2) write authorizes
    ``GuardCapability.POST_CONSOLIDATION_WRITE``: ``target`` is recognised as
    WP03's E2 CONSOLIDATED short-circuit purely from PUBLIC signals
    (:func:`~specify_cli.coordination.write_seam.is_post_consolidation_write_target`)
    -- never from an ambient env var or message text (commit_guard's own
    C-GUARD-2 discipline). Re-derives ``mission_slug``/``kind`` from
    ``files`` (the SAME pure, side-effect-free classifiers
    :func:`_resolve_commit_target` already calls) rather than threading them
    through that function's signature, keeping this an orthogonal,
    additive step.
    """
    mission_slug = _mission_slug_from_paths(repo_root, files)
    if mission_slug is None:
        return GuardCapability.STANDARD
    kind = _mission_file_kind(repo_root, files, mission_slug)
    if kind is None:
        return GuardCapability.STANDARD
    if is_post_consolidation_write_target(repo_root, mission_slug, kind, target):
        return GuardCapability.POST_CONSOLIDATION_WRITE
    return GuardCapability.STANDARD


def _resolve_file_argument(candidate: Path) -> Path:
    """Resolve one CLI file argument, refusing a symlink loop on every interpreter (#3189).

    ``resolve_rejecting_loops`` behaves exactly like non-strict
    ``Path.resolve()`` except that a symlink loop anywhere in ``candidate``
    always raises ``OSError(errno.ELOOP, ...)`` -- on every interpreter this
    project supports, not only 3.11/3.12's own non-strict probe (3.13+ no
    longer performs that probe itself, so an un-migrated ``.resolve()`` call
    here would silently return an unresolved path and let the loop's two
    symlinks get staged and committed instead of refused). Translated to a
    ``ValueError`` (already caught by ``safe_commit_command``'s existing
    broad except-all below) rather than added to that tuple as a bare
    ``OSError``, so this refusal alone changes shape -- an unrelated OSError
    elsewhere in the command body is not silently swallowed by this fix.
    """
    try:
        return resolve_rejecting_loops(candidate)
    except OSError as exc:
        raise ValueError(f"Symlink loop while resolving file argument {candidate}: {exc}") from exc


def safe_commit_command(
    files: list[Path] = typer.Argument(
        ...,
        help=(
            "Files or directories to commit, relative to the current worktree "
            "root or absolute. Directory arguments expand to their contained "
            "changed/untracked files with an explicit expansion report."
        ),
    ),
    message: str = typer.Option(..., "--message", "-m", help="Commit message."),
    to_branch: str | None = typer.Option(
        None,
        "--to-branch",
        help=(
            "Short branch name the commit must land on. The helper asserts HEAD "
            "matches this branch before staging. When omitted, the current HEAD "
            "branch is used (deprecated; --to-branch becomes required in v3.3). "
            "This is the only destination authority — no env-var inference."
        ),
    ),
    json_output: bool = typer.Option(False, "--json", help="Output JSON"),
) -> None:
    """Commit only the requested files via Spec Kitty's safe-commit path."""
    try:
        repo_root = _current_worktree_root()
        normalized_files = [
            _resolve_file_argument(repo_root / file_path if not file_path.is_absolute() else file_path)
            for file_path in files
        ]

        expanded_files, expansion_report = _expand_arguments(repo_root, normalized_files)
        rel_files = [str(path.relative_to(repo_root)) for path in expanded_files]

        target = _resolve_commit_target(
            explicit_to_branch=to_branch,
            repo_root=repo_root,
            files=expanded_files,
        )

        if expansion_report and not json_output:
            for line in expansion_report:
                console.print(line)

        had_changes = _has_candidate_changes(repo_root, expanded_files)
        committed = False
        if had_changes:
            # The protection decision is made SOLELY by safe_commit's embedded
            # guard (C-GUARD-1) against the single resolved CommitTarget — this
            # CLI performs no separate protected-branch rim check. The match
            # compares against the EXPANDED set, so directory arguments no
            # longer trip the staging backstop (#1820 / F-002). ``capability``
            # (WP04 / T017) is STANDARD for every commit except the recognised
            # E2 CONSOLIDATED mission-aware write (#3033 SC-001) — see
            # _resolve_capability_for_target.
            capability = _resolve_capability_for_target(repo_root, expanded_files, target)
            safe_commit(
                repo_root=repo_root,
                worktree_root=repo_root,
                target=target,
                message=message,
                paths=tuple(expanded_files),
                capability=capability,
            )
            committed = True

        payload = _payload(success=True, committed=committed, files=rel_files)
        if json_output:
            if expansion_report:
                payload["expansion"] = expansion_report
            print(json.dumps(payload, indent=2))
            return
        if committed:
            console.print("[green]Requested files committed[/green]")
        else:
            console.print("[yellow]No requested changes to commit[/yellow]")
    except (
        SafeCommitError,
        ProtectedBranchCommitError,
        SafeCommitBackstopError,
        TaskCliError,
        ValueError,
        RuntimeError,
    ) as exc:
        if json_output:
            print(json.dumps(_payload(success=False, error=str(exc)), indent=2))
        else:
            console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc
