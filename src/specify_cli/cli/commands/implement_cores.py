"""Pure decision cores + a minimal git port for ``implement.py`` (WP03 / #2173).

This module extracts the git-porcelain/diff family and the placement-resolution
family that used to live inline in ``cli/commands/implement.py`` into small,
independently testable functions. Any function that needs live git data takes
an injected :class:`GitPort` (T015 "git injected as a port" requirement) so
the decision/parsing logic itself can be exercised in unit tests without a
real repository and without mocking ``subprocess``.

:class:`_SubprocessGitPort` is the ONE git-subprocess I/O boundary in this
module -- a thin adapter, not decision logic. Every port-consuming function
below defaults its ``git`` parameter to :data:`DEFAULT_GIT_PORT` (an instance
of that adapter), so every existing call site in ``implement.py`` -- and every
external test that imports these names directly with their historical,
git-param-free signatures -- keeps working unchanged against real git.

``implement.py`` re-exports the public names from here via a bare import (not
added to its own ``__all__``); see the module docstring there for the shim
contract (T019 / FR-009).
"""

from __future__ import annotations

import os
import re
import subprocess
from collections.abc import Callable, Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any, NamedTuple, Protocol, runtime_checkable

from kernel.git import GitCommandError, StatusEntry, status_entries, tree_entries
from kernel.meta_decode import MetaDecodeError, decode_meta
from kernel.vcs_lock import is_vcs_lock_only_change
from mission_runtime import (
    ActionContextError,
    CommitTarget,
    resolve_action_context,
    resolve_topology,
    routes_through_coordination,
)
from specify_cli.coordination.coherence import is_coord_residue_churn, is_status_state_path
from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from specify_cli.core.errors import PlacementResolutionRequired
from specify_cli.frontmatter import WP_RUNTIME_FIELDS
from specify_cli.status import is_dossier_snapshot
from specify_cli.task_utils.support import split_frontmatter

_META_JSON_FILENAME = "meta.json"
_MISSING_META_VALUE = object()

# tasks/WP##[-slug].md filenames (#2570.1) -- e.g. "WP01.md" or the canonical
# "WP01-allocator-runtime-frontmatter.md" shape ``find_wp_file`` resolves
# (see its ``wp_name_re``). The runtime-frontmatter self-write exclusion in
# :func:`_is_self_write_only_diff` is scoped to exactly this shape, never a
# generic "*.md" match. WP14 (IC-07d) renamed this from the retired
# ``_drop_runtime_frontmatter_only_wp``'s module-level ``_WP_FILENAME_PATTERN``
# and registered it as the justified-survivor row's literal (see
# ``tests/architectural/tool_artifact_enrolment/registry/_is_self_write_only_diff.md``).
_WP_SELF_WRITE_FILENAME_RE = re.compile(r"^WP\d{2}(?:[-_.].+)?\.md$", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Git port (T015): the sole I/O boundary in this module.
# ---------------------------------------------------------------------------

#: Paths per ``git ls-tree`` call (paths travel on argv).
_LS_TREE_CHUNK = 500

#: ``ls-tree`` modes of a regular tracked file; symlinks (120000) and gitlinks
#: (160000) are never compared by object id -- they stay "changed".
_PLAIN_BLOB_MODES = frozenset({"100644", "100755"})

#: Seconds before the ``hash-object`` probe is killed. A clean filter can block
#: on a prompt (an LFS credential request) and ``implement`` must not wait on
#: it forever; a timeout reads as "unknown", which the caller treats as changed.
_GIT_OBJECT_ID_PROBE_TIMEOUT_SECONDS = 60.0


def _is_hashable_planning_path(repo_root: Path, repo_rel_path: str) -> bool:
    """True when *repo_rel_path* can be proven clean through ``hash-object --stdin-paths``."""
    # A leading quote would be C-unquoted by ``--stdin-paths``; treat it as unsendable too.
    if "\n" in repo_rel_path or "\r" in repo_rel_path or repo_rel_path.startswith('"'):
        return False
    candidate = repo_root / repo_rel_path
    # Not atomic with the later hash-object batch: a file vanishing in between fails the whole batch closed.
    return candidate.is_file() and not candidate.is_symlink()



@runtime_checkable
class GitPort(Protocol):
    """Minimal git read surface the staging/diff decision cores depend on."""

    def status_entries(self, repo_root: Path, target: Path) -> tuple[StatusEntry, ...]:
        """``git status`` entries under *target* (untracked files expanded).

        Raises:
            GitCommandError: git failed. The claim guards read an empty result
                as "nothing structural", so a failed probe must not pass.
        """
        ...

    def show_blob(self, repo_root: Path, ref: str, repo_rel_path: str) -> bytes | None:
        """Bytes of *repo_rel_path* at *ref*, or ``None`` when absent there."""
        ...

    def changed_vs_ref(self, repo_root: Path, ref: str, repo_rel_paths: Sequence[str]) -> set[str]:
        """The subset of *repo_rel_paths* whose content differs from *ref*.

        "Differs" is judged on the object id Git would store for the working
        file (its clean filters -- ``.gitattributes`` / ``core.autocrlf`` --
        applied) versus the object id at *ref*, never on raw bytes. A path
        absent at *ref* is changed. Any git failure returns every path as
        changed (fail closed): an unreadable comparison must never read as
        "nothing to commit".
        """
        ...


class _SubprocessGitPort:
    """Concrete :class:`GitPort` adapter -- real ``git`` subprocess calls.

    This is the ONLY place in the module that shells out. Every core function
    below defaults to :data:`DEFAULT_GIT_PORT` (an instance of this class), so
    unpatched callers see the exact prior behavior while tests can inject a
    fake port to exercise the pure decision logic.
    """

    def status_entries(self, repo_root: Path, target: Path) -> tuple[StatusEntry, ...]:
        return status_entries(repo_root, untracked="all", pathspecs=[str(target)])

    def show_blob(self, repo_root: Path, ref: str, repo_rel_path: str) -> bytes | None:
        result = subprocess.run(
            ["git", "show", f"{ref}:{repo_rel_path}"],
            cwd=repo_root,
            capture_output=True,
            check=False,
        )
        if result.returncode != 0:
            return None
        return result.stdout

    def changed_vs_ref(self, repo_root: Path, ref: str, repo_rel_paths: Sequence[str]) -> set[str]:
        wanted = list(dict.fromkeys(repo_rel_paths))
        # ``--stdin-paths`` has no NUL mode, so a path with a line break cannot
        # be sent; a missing file would abort the whole hash batch and a
        # symlink would hash its target rather than the stored link text.
        # Neither can be proven clean, so each is reported changed unsent.
        sendable = [p for p in wanted if _is_hashable_planning_path(repo_root, p)]
        if not sendable:
            return set(wanted)
        working = self._working_object_ids(repo_root, sendable)
        committed = self._ref_object_ids(repo_root, ref, sendable)
        if working is None or committed is None:
            return set(wanted)
        unchanged = {p for p in sendable if committed.get(p) == working[p]}
        return set(wanted) - unchanged

    def _working_object_ids(self, repo_root: Path, paths: Sequence[str]) -> dict[str, str] | None:
        """``path -> object id`` Git would store for each working file.

        ``git hash-object --stdin-paths`` applies each path's own filters (it
        is run from *repo_root* so paths resolve against the work tree);
        ``--no-filters`` and ``--path`` are deliberately not used. ``None`` on
        any failure or when the output does not pair up with the input.
        """
        stdout = self._run_git(repo_root, ["hash-object", "--stdin-paths"], b"".join(os.fsencode(p) + b"\n" for p in paths))
        if stdout is None:
            return None
        oids = stdout.decode("ascii", errors="replace").splitlines()
        if len(oids) != len(paths):
            return None
        return dict(zip(paths, oids, strict=True))

    def _ref_object_ids(self, repo_root: Path, ref: str, paths: Sequence[str]) -> dict[str, str] | None:
        """``path -> blob id`` at *ref*; paths absent there (or not plain blobs) are omitted.

        Entries come from the ``kernel.git`` listing owner and are matched by
        path name. Chunked so a long list never overflows the command line.
        ``None`` on any git failure or unparseable record.
        """
        found: dict[str, str] = {}
        for start in range(0, len(paths), _LS_TREE_CHUNK):
            try:
                entries = tree_entries(repo_root, ref, pathspecs=paths[start : start + _LS_TREE_CHUNK])
            except (GitCommandError, ValueError):
                return None
            found.update((str(entry.path), entry.oid) for entry in entries if entry.type == "blob" and entry.mode in _PLAIN_BLOB_MODES)
        return found

    def _run_git(self, repo_root: Path, args: Sequence[str], stdin: bytes | None) -> bytes | None:
        """Run ``git *args`` in *repo_root*; stdout on success, ``None`` on any failure."""
        try:
            result = subprocess.run(
                ["git", *args],
                cwd=repo_root,
                input=stdin,
                capture_output=True,
                check=False,
                timeout=_GIT_OBJECT_ID_PROBE_TIMEOUT_SECONDS,
            )
        except (OSError, subprocess.TimeoutExpired):
            return None
        if result.returncode != 0:
            return None
        return result.stdout


DEFAULT_GIT_PORT: GitPort = _SubprocessGitPort()


# ---------------------------------------------------------------------------
# git-porcelain/diff family (T015)
# ---------------------------------------------------------------------------


class _PorcelainEntry(NamedTuple):
    """A single ``git status`` record for a path in the mission directory.

    ``xy`` is the 2-char status code, ``path`` the current/new repo-relative
    path. ``is_structural`` marks deletions and renames/copies -- changes that
    ``BookkeepingTransaction.write_artifact`` (a write-only API) cannot apply,
    so they must be committed to the coordination branch out-of-band or the
    claim must fail closed rather than silently leave the branch incoherent.
    """

    xy: str
    path: str
    is_structural: bool


def _parse_porcelain_entries(status: Iterable[StatusEntry]) -> list[_PorcelainEntry]:
    """Map typed ``git status`` entries to :class:`_PorcelainEntry`.

    Deletions (``D`` in either column) and renames/copies (an entry with a
    source path) are classified as structural: a write-only transaction cannot
    remove the old path on coord. The path is the current/new one.
    """
    return [
        _PorcelainEntry(
            xy=entry.xy,
            path=str(entry.path),
            is_structural=entry.orig_path is not None or "D" in entry.xy,
        )
        for entry in status
    ]


def _feature_dir_status_entries(repo_root: Path, feature_dir: Path, *, git: GitPort = DEFAULT_GIT_PORT) -> list[_PorcelainEntry]:
    """``git status`` entries under *feature_dir*, minus dossier-snapshot churn.

    FIX-M2-08: drops any entry matching
    :func:`~specify_cli.status.is_dossier_snapshot` before either consumer
    (:func:`_structural_entries` / :func:`detect_structural_planning_changes`,
    and :func:`_status_paths_for_commit` via :func:`resolve_planning_artifact_staging`)
    sees it. ``contracts/dossier-snapshot-ownership.md`` (D1/D2) ratifies the
    dossier snapshot as EXCLUDE: "No staging, no committing... The file is
    just a file" -- a live re-save between the last commit and this claim is
    expected, not a real dirty-state block. FIX-M2-05 already taught
    :func:`~specify_cli.coordination.coherence.is_self_bookkeeping_churn` this
    exemption for ``git/ref_advance.py`` / ``bulk_edit/diff_check.py`` /
    ``review/dirty_classifier.py`` and taught ``agent tasks move-task``'s own
    preflight the same glob directly (``tasks_shared.py`` /
    ``tasks_parsing_validation.py``) -- but this implement-claim planning-
    artifact precheck was never updated, so a dossier-sync write racing this
    claim (e.g. one triggered by the immediately-preceding ``finalize-tasks``)
    tripped ``resolve_planning_artifact_staging``'s "Planning artifacts not
    committed" fail-closed refusal, dragging already-committed spec.md /
    plan.md / tasks.md / lanes.json into the same printed refusal (confirmed
    via ``tests/e2e/test_cli_smoke.py::test_full_workflow_sequence``) --
    exactly the "invisible to one gate, fatal at another" split FIX-M2-05's
    own C7 precedent exists to close, just for this one remaining gate.
    """
    entries = _parse_porcelain_entries(git.status_entries(repo_root, feature_dir))
    return [e for e in entries if not is_dossier_snapshot(e.path)]


def _structural_entries(entries: list[_PorcelainEntry]) -> list[_PorcelainEntry]:
    """Deletions/renames/copies -- changes that cannot be auto-committed to the
    coordination branch and must fail closed (#1598)."""
    return [e for e in entries if e.is_structural]


def detect_structural_planning_changes(repo_root: Path, artifact_source_dir: Path, *, git: GitPort = DEFAULT_GIT_PORT) -> list[_PorcelainEntry]:
    """Structural planning-artifact changes from git porcelain alone.

    Independent of coord/topology resolution, so the git-executor can fire the
    #1598 fail-closed guard BEFORE resolving the coordination-branch filter
    (which can raise on a broken topology). Restores the pre-degod ordering
    (#2464 squad-B1) where a structural change is reported to the operator even
    when topology resolution would fault.
    """
    return _structural_entries(_feature_dir_status_entries(repo_root, artifact_source_dir, git=git))


def _drop_if(paths: Iterable[str], predicate: Callable[[str], bool]) -> list[str]:
    """Keep every path in *paths* for which *predicate* is ``False`` (WP14 / IC-07d).

    The ONE generic claim-time exclusion filter. Each of the three retired
    siblings -- ``_drop_vcs_lock_only_meta``, ``_drop_runtime_frontmatter_only_wp``
    (+ its ``_is_wp_filename``/``_WP_FILENAME_PATTERN`` structural twin), and
    ``_exclude_coord_owned`` -- applied this exact "keep unless the predicate
    says drop" shape at the same two call lines in
    :func:`resolve_planning_artifact_staging`; only the predicate differed. A
    NEW claim-time exclusion is now "write a predicate", never "write a new
    loop" (extends C9's anti-ninth intent to non-registry callers too).
    """
    return [p for p in paths if not predicate(p)]


def _is_coord_legacy_mission_event_log(repo_rel: str, coord_branch_for_filter: str | None) -> bool:
    """True only for the retained direct-child event log on coord topology.

    ``mission-events.jsonl`` is legacy observability, not planning input. A
    retained primary copy may coexist with the newer coord-owned stream, so a
    coord claim must leave this exact path untouched rather than trying to
    stage or reconcile either stream. Keep this exception local to the claim
    guard; globally classifying the filename as status/residue could make it
    discardable by unrelated consumers. The caller must also prove the path is
    still untracked before applying the exception.
    """
    if coord_branch_for_filter is None:
        return False
    parts = Path(repo_rel).parts
    return len(parts) == 3 and parts[0] == "kitty-specs" and parts[2] == "mission-events.jsonl"


def _status_paths_for_commit(entries: list[_PorcelainEntry], coord_branch_for_filter: str | None) -> list[str]:
    """The mission-directory paths to commit from ``git status`` entries.

    Drops the canonical status log/snapshot (``MissionArtifactKind.STATUS_STATE``)
    on coordination-topology missions only (retired ``_exclude_coord_owned``,
    WP14 / IC-07d). On a coordination mission those files are owned by the
    transactional emitter on the coord branch, and the primary checkout's
    copies are stale -- committing them would clobber the seeded lane state
    (#1589). On a non-coordination (flat/legacy) mission there is no coord
    authority, so the primary checkout's status files ARE canonical and must
    be committed; excluding them there silently drops a status edit
    (review M3).

    Routes fully onto the canonical owner family via
    :func:`~specify_cli.coordination.coherence.is_status_state_path` (WP13's
    IC-07c leg) -- narrow ON PURPOSE (STATUS_STATE only, not the broader
    ``is_coord_residue_churn``/``is_toolchain_generated_churn`` union):
    *entries* may legitimately carry OTHER planning artifacts
    (``tasks.md``, ``acceptance-matrix.json``, ...) that must still be
    committed here -- only the status log/snapshot are authored directly on
    the coord branch. See :func:`resolve_planning_artifact_staging` for the
    analogous ``extra_file_paths`` exclusion.
    """
    paths = [e.path for e in entries]
    if not coord_branch_for_filter:
        return paths
    return _drop_if(paths, is_status_state_path)


def _decode_meta_fail_closed(raw: bytes, *, source_id: str) -> dict[str, Any]:
    """Decode *raw* ``meta.json`` bytes via the kernel L1 authority, fail-closed.

    Routes onto :func:`kernel.meta_decode.decode_meta` (the single malformed
    definition, WP01) with ``on_malformed="raise"``: a present-but-corrupt
    ``meta.json`` now surfaces the shared :class:`MetaDecodeError` instead of the
    former silent ``None`` (FR-003/FR-007). The kernel message names only the
    JSON fault, so this thin wrapper re-raises with a message that also names
    ``meta.json`` + *source_id* (the filesystem path for the worktree read, the
    ``ref:path`` blob spec for the committed read) -- the diagnosable identifier
    FR-007 requires. Empty/whitespace-only content is a benign short-circuit the
    caller owns (C-010) and never reaches here.
    """
    try:
        return decode_meta(raw, on_malformed="raise") or {}
    except MetaDecodeError as exc:
        raise MetaDecodeError(f"malformed meta.json ({source_id}): {exc}") from exc


def _commit_target_ref_for(planning_branch: str | None) -> str:
    """The ONE cli-local expression the read side and the write side both
    derive the PRIMARY-partition ref from (FR-005, ref half; #2650 / WP04).

    Pre-unification, the read side (:func:`resolve_precondition_ref`) hard-
    coded the git-rev shorthand ``"HEAD"`` inline and the write side
    (``implement_planning_commit.py::_commit_planning_artifacts_transaction``'s PRIMARY-group
    destination) hard-coded the mission's ``planning_branch`` name inline --
    two independently-written literals that happened to agree only because
    every real claim runs from a checkout whose ``HEAD`` IS ``planning_branch``.
    A detached-HEAD or off-target-branch checkout could silently break that
    coincidence. Routing both sides through this single function removes the
    two-literal duplication (NFR-004): a future edit to "what counts as the
    PRIMARY ref" can only be made here, once.

    ``planning_branch`` is ``None`` at the read-side call sites in this module
    (``resolve_precondition_ref`` resolves a ref PER PATH, not per branch --
    no branch name is in scope there) and always a real branch name at the
    write-side call sites in ``implement.py`` (the mission's actual commit
    destination is already resolved by the time the commit runs).

    ``planning_branch or "HEAD"`` is NOT the C-009-forbidden default-BRANCH
    fallback: an absent/empty ``planning_branch`` resolves to the LOCAL
    CHECKOUT (``"HEAD"``, the read side's original constant), never a
    hardcoded branch name such as ``main``. Pure: no filesystem/git side
    effects.
    """
    return planning_branch or "HEAD"


def resolve_precondition_ref(repo_rel_path: str, coord_branch_for_filter: str | None) -> str:
    """Resolve the SINGLE ref *repo_rel_path* must be compared against for the
    implement-claim precondition (contracts/resolve-precondition-ref.md,
    corrected post-tasks-squad; FR-001/FR-002/BLOCKER-2).

    Per-path, not per-staging-call: on a coordination mission
    ``coord_branch_for_filter`` is one non-``None`` branch for every
    candidate, so only the PATH distinguishes a PRIMARY ``spec.md`` (compares
    against the primary/target branch -- ``HEAD`` in the local checkout) from
    a COORD ``status.events.jsonl`` (compares against the coordination ref).

    Uses :func:`~specify_cli.coordination.coherence.is_coord_residue_churn`
    (None-safe over an unrecognized kind; WP12 retired the former
    ``mission_runtime`` predicate onto this owner leg) -- NOT
    ``is_primary_artifact_kind(kind_for_mission_file(path))``:
    ``kind_for_mission_file("meta.json")`` returns ``None``, so that form is
    both a ``mypy --strict`` error and would misroute ``meta.json`` to coord,
    reintroducing #2533 (BLOCKER-2).

    Defaults toward primary (fail-safe direction, NFR-004): everything not
    explicitly coord-residue -- PRIMARY kinds, ``meta.json`` (kind ``None``),
    and unrecognized paths -- resolves to the shared :func:`_commit_target_ref_for`
    expression (``"HEAD"`` here; FR-005 ref half). A PRIMARY artifact is
    never compared against the coordination branch. Pure: no filesystem/git
    side effects.
    """
    if coord_branch_for_filter and is_coord_residue_churn(repo_rel_path):
        return coord_branch_for_filter
    return _commit_target_ref_for(None)


def _committed_meta_mapping(repo_root: Path, repo_rel: str, ref: str | None, *, git: GitPort = DEFAULT_GIT_PORT) -> dict[str, Any] | None:
    """The committed meta.json mapping at the path-resolved precondition ref
    (:func:`resolve_precondition_ref` -- ``HEAD`` for meta.json, which is
    always a PRIMARY kind), or ``None`` when the blob is absent/empty there.

    Site D (data-model): the ``show_blob`` bytes route onto the kernel L1
    decode fail-closed -- a present-but-corrupt committed blob now raises
    :class:`MetaDecodeError` (naming the ``ref:path`` blob spec) rather than the
    former silent ``None`` (FR-007). An absent blob (``None``) or an
    empty/whitespace-only blob stays benign (``None``; C-010 / FR-005)."""
    resolved_ref = resolve_precondition_ref(repo_rel, ref)
    blob = git.show_blob(repo_root, resolved_ref, repo_rel)
    if blob is None or not blob.strip():
        return None
    return _decode_meta_fail_closed(blob, source_id=f"{resolved_ref}:{repo_rel}")


def _parse_wp_frontmatter(text: str) -> tuple[Mapping[str, Any] | None, str, str]:
    """Split WP-markdown *text* into ``(frontmatter mapping, body, padding)``.

    Returns ``(None, body, padding)`` when *text* has no frontmatter block or
    the block does not parse to a YAML mapping -- defensive: a malformed or
    frontmatter-less WP file can never be treated as a runtime-only diff.
    """
    front_text, body, padding = split_frontmatter(text)
    if not front_text:
        return None, body, padding
    try:
        parsed = YAML(typ="safe").load(front_text)
    except YAMLError:
        return None, body, padding
    return (parsed if isinstance(parsed, dict) else None), body, padding


def _is_runtime_frontmatter_only_wp_diff(
    committed_front: Mapping[str, Any] | None,
    working_front: Mapping[str, Any] | None,
    committed_tail: str,
    working_tail: str,
) -> bool:
    """Pure decision: is the WP##.md change ONLY runtime claim/workspace
    frontmatter (T001's :data:`~specify_cli.frontmatter.WP_RUNTIME_FIELDS`)?

    Structural analogue of :func:`kernel.vcs_lock.is_vcs_lock_only_change` for WP
    markdown files. Returns ``True`` iff (1) both the committed and working frontmatter
    parsed to a mapping, (2) the markdown body -- everything after the
    frontmatter block, byte-compared as ``padding + body`` -- is unchanged,
    AND (3) every frontmatter key whose value differs is a member of
    :data:`~specify_cli.frontmatter.WP_RUNTIME_FIELDS` (K-1/NFR-005: the body
    check alone is not enough -- a non-runtime frontmatter key change must
    also still block).
    """
    if committed_front is None or working_front is None:
        return False
    if committed_tail != working_tail:
        return False
    changed_keys = {
        key
        for key in set(committed_front) | set(working_front)
        if committed_front.get(key, _MISSING_META_VALUE) != working_front.get(key, _MISSING_META_VALUE)
    }
    return bool(changed_keys) and changed_keys <= WP_RUNTIME_FIELDS


def _is_self_write_only_diff(
    repo_root: Path,
    repo_rel: str,
    ref: str | None,
    *,
    git: GitPort = DEFAULT_GIT_PORT,
) -> bool:
    """True iff *repo_rel*'s only diff vs *ref* is the runtime's OWN claim-time
    self-write -- a vcs-lock-only ``meta.json`` change (#2222 / C-003) or a
    runtime-frontmatter-only ``tasks/WP##.md`` change (#2570.1).

    WP14 (IC-07d) structural merge of the retired ``_drop_vcs_lock_only_meta``
    / ``_drop_runtime_frontmatter_only_wp`` twins: identical shape (a single
    filename-scoped, diff-scoped predicate), different filename gate and
    differing-fields comparison. Consumed as the predicate for :func:`_drop_if`
    at both call sites in :func:`resolve_planning_artifact_staging` -- ONE
    per-path decision replaces the two near-identical loops.

    Deliberately NOT delegated to
    :func:`~specify_cli.coordination.coherence.is_toolchain_generated_churn`:
    the owner classifies by declared artifact *kind* (a whole-file verdict --
    ``meta.json`` is unconditionally self-bookkeeping regardless of its diff),
    while this predicate must stay diff-scoped -- a ``meta.json`` carrying a
    genuine NON-lock edit, or a ``WP##.md`` carrying a genuine NON-runtime
    frontmatter/body edit, must still be KEPT (block the claim), which a
    kind-based "this file is always self-bookkeeping" verdict cannot express
    without regressing ``test_non_lock_dirty_meta_still_blocks_auto_commit_false_claim``
    / ``test_runtime_frontmatter_non_runtime_key_change_still_blocks_claim`` (C6).
    A genuine, justified local survivor (C-010) -- registered (not silent) at
    ``tests/architectural/tool_artifact_enrolment/registry/_is_self_write_only_diff.md``.

    Byte-identical no-op semantics are the caller's responsibility: apply this
    predicate via :func:`_drop_if` only under ``auto_commit=False`` (NFR-001).
    """
    name = Path(repo_rel).name
    source = (repo_root / Path(repo_rel)).resolve()
    if not source.exists():
        return False
    if name == _META_JSON_FILENAME:
        # Site C (data-model): the working-tree read stays INLINE here (the trio
        # gate pins the ``source.read_bytes()`` token to this exact site); the
        # bytes route onto the kernel L1 decode fail-closed. Empty/whitespace-only
        # meta.json is a benign short-circuit the caller owns (C-010 / FR-005) --
        # not self-write, so keep the file (block the claim); a present-but-corrupt
        # meta.json now raises :class:`MetaDecodeError` instead of the former
        # silent ``None``->``return False`` (FR-007).
        raw = source.read_bytes()
        if not raw.strip():
            return False
        working = _decode_meta_fail_closed(raw, source_id=str(source))
        committed = _committed_meta_mapping(repo_root, repo_rel, ref, git=git)
        return is_vcs_lock_only_change(committed, working)
    if not _WP_SELF_WRITE_FILENAME_RE.match(name):
        return False
    committed_blob = git.show_blob(repo_root, resolve_precondition_ref(repo_rel, ref), repo_rel)
    if committed_blob is None:
        return False
    working_front, working_body, working_padding = _parse_wp_frontmatter(source.read_text(encoding="utf-8-sig"))
    committed_front, committed_body, committed_padding = _parse_wp_frontmatter(
        committed_blob.decode("utf-8", errors="replace")
    )
    return _is_runtime_frontmatter_only_wp_diff(
        committed_front,
        working_front,
        committed_padding + committed_body,
        working_padding + working_body,
    )


def _files_changed_vs_ref(repo_root: Path, files: list[str], ref: str | None, *, git: GitPort = DEFAULT_GIT_PORT) -> list[str]:
    """Drop files whose working-tree content already matches *ref*.

    "Matches" is Git's own view (:meth:`GitPort.changed_vs_ref`): the object id
    Git would store for the working file, clean filters applied, equals the
    object id at *ref*. A checkout that converts line endings (CRLF) and is
    ``git status``-clean therefore yields no changed files (#5576), while a
    real edit stays changed even when saved with CRLF.

    The coordination model commits claim-time planning-artifact edits to the
    coordination branch but leaves them uncommitted in the main checkout. The
    next claim re-discovers those edits as "uncommitted" even though their
    content is already on the coordination branch. Committing them again would
    produce an empty commit, which ``safe_commit`` rejects ("git commit failed")
    -- silently blocking every claim after the first. Filtering to genuinely
    changed files makes the planning-artifact commit idempotent.
    """
    if not ref:
        return files
    # Defensive: callers pass only writable (non-structural) paths, which exist
    # on disk. Structural deletions/renames are rejected upstream (fail-closed)
    # before reaching here, so a missing path is unexpected -- skip it rather
    # than crash the claim (or abort the whole hash batch).
    existing = [repo_rel for repo_rel in files if (repo_root / Path(repo_rel)).resolve().exists()]
    changed = git.changed_vs_ref(repo_root, ref, existing)
    return [repo_rel for repo_rel in existing if repo_rel in changed]


def _files_changed_vs_precondition_ref(
    repo_root: Path,
    files: list[str],
    coord_branch_for_filter: str | None,
    *,
    verbatim_ref: str | None = None,
    git: GitPort = DEFAULT_GIT_PORT,
) -> list[str]:
    """Per-path idempotency filter (T003, contracts/resolve-precondition-ref.md
    "Preferred design"): partition *files* by :func:`resolve_precondition_ref`
    into a PRIMARY group (diffed against ``HEAD``) and a COORD-residue group
    (diffed against *coord_branch_for_filter*), calling
    :func:`_files_changed_vs_ref` once per group so ITS OWN
    ``(repo_root, files, ref)`` signature stays untouched (its direct unit
    tests keep passing). Preserves the original relative order of *files* in
    the result -- callers print ``files_to_commit`` verbatim in the "not
    committed" instructions.

    ``verbatim_ref`` (PR #2662 squad fix): when the caller commits the WHOLE
    batch to ONE ref (the healthy ``placement_ref is not None`` verbatim path in
    ``_commit_planning_artifacts_transaction``, which the C-004/#2160 deferral
    leaves un-partitioned), the idempotency comparison MUST use that same single
    write target for EVERY file -- not the PRIMARY-vs-``HEAD`` split. Otherwise a
    PRIMARY artifact already-identical on the coord write ref but differing from
    ``HEAD`` is compared vs ``HEAD`` (still "changed"), re-committed verbatim to
    coord, produces an empty commit, and ``safe_commit`` hard-fails the claim
    (confirmed on coordination missions; the read=HEAD / write=coord divergence
    is a concrete instance of the overloaded "primary ref", #2653). Proper fix
    (partition the verbatim write so PRIMARY lands on the primary branch) is
    deferred to #2160.
    """
    if verbatim_ref is not None:
        changed_verbatim = set(_files_changed_vs_ref(repo_root, files, verbatim_ref, git=git))
        return [repo_rel for repo_rel in files if repo_rel in changed_verbatim]
    primary_ref = _commit_target_ref_for(None)
    primary_files: list[str] = []
    coord_files: list[str] = []
    for repo_rel in files:
        if resolve_precondition_ref(repo_rel, coord_branch_for_filter) == primary_ref:
            primary_files.append(repo_rel)
        else:
            coord_files.append(repo_rel)
    changed = set(_files_changed_vs_ref(repo_root, primary_files, primary_ref, git=git))
    changed |= set(_files_changed_vs_ref(repo_root, coord_files, coord_branch_for_filter, git=git))
    return [repo_rel for repo_rel in files if repo_rel in changed]


# ---------------------------------------------------------------------------
# T016: pure staging-decision core for _ensure_planning_artifacts_committed_git
# ---------------------------------------------------------------------------


class PlanningArtifactStagingPlan(NamedTuple):
    """Result of :func:`resolve_planning_artifact_staging`.

    ``structural`` non-empty means the claim must fail closed (the caller
    prints the offending entries and exits); every other field is meaningless
    in that case. Otherwise ``files_to_commit`` is the final (deduped,
    idempotency-filtered) set to stage, and ``status_paths_to_commit`` is the
    subset that came from live ``git status`` entries (used by the caller to
    decide whether to print the "not committed" instructions).
    """

    structural: list[_PorcelainEntry]
    files_to_commit: list[str]
    status_paths_to_commit: list[str]


def resolve_planning_artifact_staging(
    repo_root: Path,
    artifact_source_dir: Path,
    coord_branch_for_filter: str | None,
    extra_file_paths: list[str],
    *,
    auto_commit: bool,
    verbatim_ref: str | None = None,
    git: GitPort = DEFAULT_GIT_PORT,
) -> PlanningArtifactStagingPlan:
    """Pure staging decision for planning-artifact commits (T016).

    Mirrors the pre-extraction body of
    ``_ensure_planning_artifacts_committed_git`` (#1598 fail-closed structural
    guard, #2222 vcs-lock exclusion, idempotency filtering) with zero
    console/typer side effects -- the git-executor caller in ``implement.py``
    turns a non-empty ``structural`` into the fail-closed print+exit, and an
    empty ``files_to_commit`` into a silent no-op return.

    ``extra_file_paths`` is the caller-supplied ``_feature_dir_file_paths``
    listing (a plain filesystem walk, not part of this git-porcelain core);
    passing it in keeps this function's git surface limited to ``git status``
    and ``git show`` via the injected port.

    ``verbatim_ref`` (PR #2662 squad fix) is the single ref the whole batch will
    be committed to on the healthy ``placement_ref is not None`` verbatim path;
    when set, the idempotency filter compares EVERY file against it so a
    PRIMARY artifact already-identical on the (coord) write ref is dropped
    instead of re-committed into an empty commit that hard-fails the claim. See
    :func:`_files_changed_vs_precondition_ref`.
    """
    entries = _feature_dir_status_entries(repo_root, artifact_source_dir, git=git)
    structural = _structural_entries(entries)
    if structural:
        return PlanningArtifactStagingPlan(structural=structural, files_to_commit=[], status_paths_to_commit=[])

    untracked_legacy_event_log_paths = {
        entry.path
        for entry in entries
        if entry.xy == "??" and _is_coord_legacy_mission_event_log(entry.path, coord_branch_for_filter)
    }

    def _self_write(repo_rel: str) -> bool:
        return _is_self_write_only_diff(repo_root, repo_rel, coord_branch_for_filter, git=git)

    status_paths = _drop_if(
        _status_paths_for_commit(entries, coord_branch_for_filter),
        lambda p: p in untracked_legacy_event_log_paths,
    )
    if not auto_commit:
        status_paths = _drop_if(status_paths, _self_write)
    files_to_commit = list(status_paths)
    if coord_branch_for_filter:
        # FIX-M2-08: ``extra_file_paths`` is an UNCONDITIONAL mission-directory walk
        # (not git-status-gated), so it can surface the dossier snapshot even
        # when ``_feature_dir_status_entries`` already dropped it above. Union
        # the narrow STATUS_STATE leg with :func:`is_dossier_snapshot` so this
        # candidate-gathering leg honours the SAME D1 EXCLUDE policy -- never
        # a commit candidate, whether or not it is currently git-dirty
        # (mirrors ``_collect_finalize_artifacts``'s own FIX-M2-05 exclusion;
        # without this leg the file would slip back into ``files_to_commit``
        # and ``_commit_planning_artifacts_transaction`` would commit it,
        # reopening the exact violation FIX-M2-05 closed in
        # ``mission_finalize.py``, just via this sibling producer instead).
        files_to_commit.extend(
            _drop_if(
                extra_file_paths,
                lambda p: is_status_state_path(p) or is_dossier_snapshot(p) or p in untracked_legacy_event_log_paths,
            )
        )
    files_to_commit = list(dict.fromkeys(files_to_commit))
    if not auto_commit:
        files_to_commit = _drop_if(files_to_commit, _self_write)
    if not files_to_commit:
        return PlanningArtifactStagingPlan(structural=[], files_to_commit=[], status_paths_to_commit=[])

    # Idempotency guard: skip files already identical on THEIR OWN partition ref
    # (PRIMARY kinds -> HEAD, COORD-residue kinds -> the coordination branch;
    # see ``resolve_precondition_ref``) so a re-discovered (but
    # already-committed) edit does not produce an empty commit that
    # ``safe_commit`` rejects. See ``_files_changed_vs_precondition_ref``.
    files_to_commit = _files_changed_vs_precondition_ref(repo_root, files_to_commit, coord_branch_for_filter, verbatim_ref=verbatim_ref, git=git)
    if not files_to_commit:
        return PlanningArtifactStagingPlan(structural=[], files_to_commit=[], status_paths_to_commit=[])

    status_paths_to_commit = _files_changed_vs_precondition_ref(repo_root, status_paths, coord_branch_for_filter, verbatim_ref=verbatim_ref, git=git)
    return PlanningArtifactStagingPlan(
        structural=[],
        files_to_commit=files_to_commit,
        status_paths_to_commit=status_paths_to_commit,
    )


# ---------------------------------------------------------------------------
# placement family (T015)
# ---------------------------------------------------------------------------


def _resolve_placement_ref(repo_root: Path, *, mission_slug: str, wp_id: str) -> CommitTarget | None:
    """Resolve the context's artifact-placement ref (C-PLACE-1 / IC-05).

    Routes through the single canonical resolver (``resolve_action_context``,
    C-CTX-1) and returns ``context.artifact_placement.placement_ref`` -- the ONE
    :class:`CommitTarget` that planning artifacts AND status events resolve to.
    On any resolution failure it returns ``None`` so the caller keeps the legacy
    meta-derived placement path (C-004 strangler: never break the implement
    lifecycle on a context-resolution edge case).
    """
    try:
        context = resolve_action_context(
            repo_root,
            action="implement",
            feature=mission_slug,
            wp_id=wp_id,
        )
    except ActionContextError:
        # WP03 / T017 (#3128): this handler is deliberately NARROW — only the
        # legacy-fallback ``ActionContextError`` degrades to ``None`` here. A
        # Seam-B ``CheckoutIdentityError`` is an ``Exception``-direct refusal
        # (NOT an ``ActionContextError``), so it can never be caught/degraded by
        # this arm. (This is a read-shaped placement resolve — it passes no
        # write-intent — so a refusal does not arise here regardless; the narrow
        # catch is the structural guarantee that it could not be swallowed.)
        return None
    placement = context.artifact_placement
    return placement.placement_ref if placement is not None else None


def _resolve_claim_commit_target(
    placement_ref: CommitTarget | None, *, mission_slug: str
) -> CommitTarget:
    """Resolve the WP status claim-commit target (T012 / D11 fail-closed).

    A small, pure extraction (Sonar-testable) over the single seam-resolved
    ``placement_ref`` (the SAME :class:`CommitTarget` planning artifacts AND
    status events resolve to, C-PLACE-1). Replaces the forbidden
    ``_get_current_branch(repo_root) or planning_branch`` grammar: when
    ``placement_ref`` failed to resolve, this FAILS CLOSED with
    :class:`PlacementResolutionRequired` instead of silently committing the
    WP claim to whatever branch happens to be checked out.

    #5113 / FR-014 (T041): ``placement_ref`` is ``None`` for BOTH an
    unmaterialized coordination worktree (branch present) and a deleted /
    never-created coordination branch — ``_resolve_status_surface_dir``
    collapses both into the same generic ``ActionContextError`` the caller
    degrades on (see the module docstring's classification note), so this
    helper cannot tell them apart. The remedy command below is truthful for
    both: ``doctor coordination --fix`` materializes a present branch via its
    ``COORDINATION_WORKTREE_MISSING`` fixer, and flattens (drops the stale
    key) via its ``COORDINATION_WORKTREE_NEVER_CREATED`` fixer.
    """
    if placement_ref is None:
        raise PlacementResolutionRequired(
            "Cannot resolve the canonical write placement for this mission's "
            "WP status claim commit -- refusing to commit to the currently "
            "checked-out branch (D11 fail-closed). This usually means the "
            "mission's stored coordination topology could not be resolved "
            "(e.g. the coordination worktree has not been materialized yet, "
            "or the `coordination_branch` declared in meta.json is missing/"
            "torn down in git). Run `spec-kitty doctor coordination "
            f"--mission {mission_slug} --fix` to repair automatically -- it "
            "materializes a present branch, or flattens (removes the stale "
            "key) if the topology was never activated; or remove "
            "`coordination_branch` from meta.json manually if you know the "
            "coordination topology was never used, then retry."
        )
    return placement_ref


def _placement_coord_filter(repo_root: Path, mission_slug: str, placement_ref: CommitTarget | None) -> str | None:
    """Return the coord-owned-exclusion ref implied by the mission's topology.

    The coord/flattened/primary decision reads the STORED topology via the ONE
    canonical :func:`routes_through_coordination` predicate -- never a per-ref
    ``.kind`` (the retired arm) and not independent meta.json/git logic
    (C-005). Only a genuine *coordination* topology owns the status files on a
    separate branch and therefore excludes them from the primary-checkout
    commit; a flattened/primary topology has no primary/coord split, so the
    primary status files are NOT filtered out. The excluded ref is the
    context's single ``placement_ref.ref`` (the SAME CommitTarget status
    events resolve to). Returns ``None`` for flattened/primary topologies.
    """
    if placement_ref is None:
        return None
    if routes_through_coordination(resolve_topology(repo_root, mission_slug)):
        return placement_ref.ref
    return None
