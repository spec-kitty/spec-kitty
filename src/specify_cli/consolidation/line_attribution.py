"""Line-level attribution of a canceled commit's change in a lane's final state (#6309).

The supersession question both canceled-content axes ask — "does this canceled
commit's change still live in the lane's final state for this path?" — used to be
a line-SUBSET test (the former ``git_probes.canceled_content_survives``, #5932): the content counted
as gone unless EVERY line the canceled commit added was still present. A survivor
that kept two of three canceled lines laundered the two, and a canceled DELETION
(no added lines) read as gone whenever a survivor touched the path. Both shipped
reviewer-rejected content at PASS.

This module answers the question by authorship instead (operator ruling on #6309):

* **Added lines** — a forward ``git blame`` of the final state attributes every
  line to the commit that last wrote it. The change survives when a non-trivial
  line is still attributed to a canceled commit. Blame follows a line a later
  commit only re-indented or re-ended (``-w``), a longer line moved within the
  file (``-M``) and a whole-file rename, and hands a line that a later commit
  removed and re-added to that later commit (its own authorship). The old subset
  test stays as a second "survives" signal, so nothing it caught is lost.
* **Removed lines** — a canceled deletion is located in the final state by the
  nearest lines around it that survive (a ``--reverse`` blame). It stays in
  effect unless its lines come back in that spot, or approved work rewrote the
  spot: the spot holds non-trivial lines and none of them is still a canceled
  commit's. An empty spot — the deletion simply stands — keeps it in effect.
* **Renames** — when the path is absent from the final state, a rename of it (one
  source, one target) is followed and the target path is judged and reported.
* **Whitespace-blind blind spots** — a canceled change that is only a re-indent, a
  line-ending change or a lone punctuation line is invisible to ``-w`` and to the
  trivial-line filter, so it is judged byte for byte (``_exact_change_kept``).
* **Trivial lines** — blank, whitespace-only and punctuation-only lines are
  ignored on every arm, so a full rewrite that happens to keep a ``}`` or a blank
  line is not read as surviving canceled content.

Fail-closed, like every probe in :mod:`~specify_cli.consolidation.git_probes`: any
git error or unparseable output raises :class:`GitProbeError`, so the caller
REFUSEs rather than reading an unevaluable probe as "superseded". Cost is bounded:
one forward blame per (final state, path), memoized, limited to history after the
oldest canceled commit, plus one reverse blame and one diff per canceled commit
that removed non-trivial lines.

Known limits (ADR 2026-09-29-1, Amendment 2026-10-22). Pinned as strict ``xfail``
in ``tests/consolidation/test_canceled_line_attribution_6309.py``: approved lines
inserted exactly at a canceled deletion's spot supersede it, canceled content
copied into another file is not followed, and a rename whose old path is re-created
is judged at the re-created path only. An approved WP that later re-indents the same lines
identically is indistinguishable from the canceled re-indent and is refused (deliberate
fail-closed over-refusal). Not pinned: a short line moved within the
file (below git's ``-M`` threshold) is caught only by the subset signal, and content inside a
merge commit stays the existing residual. The rename lookup diffs the window from the
newest canceled commit to the lane tip with no rename limit, and runs only when the
path is gone from the final state.
"""

from __future__ import annotations

import os
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from kernel.git import BlameLine, DiffHunk, GitCommandError, blame_lines, blob_at, changed_entries, diff_hunks, numstat_entries, run_git, tree_entry
from specify_cli.consolidation.git_probes import GitProbeError, path_state_at

__all__ = ["LineAttribution"]

# A rename status letter in ``git diff --name-status`` (``R<score>``).
_RENAME = "R"
# Rename detection must never silently give up on a large window: git's default
# ``diff.renameLimit`` skips inexact detection past it, which would read a renamed
# canceled path as deleted (gone). ``0`` means no limit.
_UNLIMITED_RENAMES: tuple[tuple[str, str], ...] = (("diff.renameLimit", "0"),)


@dataclass(frozen=True)
class CanceledSurvival:
    """Whether a canceled change still lives in a final state, and where.

    ``final_path`` is the path the change lives at in ``final_ref`` (the probed
    path, or its rename target), or ``None`` when the path is gone from the final
    state. ``added`` is True when a non-trivial canceled line is still there;
    ``deletion`` when a non-trivial canceled deletion is still in effect.
    """

    final_path: str | None
    final_ref: str
    added: bool
    deletion: bool

    @property
    def survives(self) -> bool:
        """The canceled change is still (at least partly) in the final state."""
        return self.final_path is not None and (self.added or self.deletion)


def is_trivial_line(text: bytes) -> bool:
    """A blank, whitespace-only or punctuation-only line (no letter or digit)."""
    return not any(char.isalnum() for char in text.decode("utf-8", "surrogateescape"))


def _normalized(text: bytes) -> bytes:
    """Whitespace-insensitive line identity (indentation and line endings ignored)."""
    return b" ".join(text.split())


def _is_subsequence(needle: Sequence[bytes], haystack: Sequence[bytes]) -> bool:
    """True when every item of *needle* appears in *haystack*, in order."""
    remaining = iter(haystack)
    return all(any(item == candidate for candidate in remaining) for item in needle)


def _git_env_with(config: Sequence[tuple[str, str]]) -> dict[str, str]:
    """The caller's environment plus *config* as ``GIT_CONFIG_*`` entries (appended, never replacing)."""
    env = dict(os.environ)
    try:
        count = int(env.get("GIT_CONFIG_COUNT", "0"))
    except ValueError:
        count = 0
    for offset, (key, value) in enumerate(config):
        env[f"GIT_CONFIG_KEY_{count + offset}"] = key
        env[f"GIT_CONFIG_VALUE_{count + offset}"] = value
    env["GIT_CONFIG_COUNT"] = str(count + len(config))
    return env


class LineAttribution:
    """Memoized line-attribution reads over one repository (one gate evaluation).

    Construct one per attribution walk; it caches resolved refs, parents, the
    forward blame of each (final state, path, history floor) and each canceled
    commit's hunks, so the same history is never blamed twice.
    """

    def __init__(self, repo_root: Path) -> None:
        self._repo = repo_root
        self._resolved: dict[str, str] = {}
        self._parents: dict[str, str | None] = {}
        self._forward: dict[tuple[str, str, str], tuple[BlameLine, ...]] = {}
        self._hunks: dict[tuple[str, str, bool], tuple[DiffHunk, ...]] = {}

    @property
    def repo_root(self) -> Path:
        """The repository every read runs in."""
        return self._repo

    def survival(
        self,
        canceled_shas: Sequence[str],
        path: str,
        final_ref: str,
        *,
        floor: str,
        tip: str | None = None,
        other_canceled: frozenset[str] = frozenset(),
    ) -> CanceledSurvival:
        """Does any of *canceled_shas*' change at *path* still live in *final_ref*?

        *canceled_shas* are the canceled commits that touched *path*, newest
        first. *floor* is the OLDEST canceled commit the caller's walk can
        reach: blame stops at its parent, which bounds the cost and can never hide
        a canceled line (every canceled commit is at or after it). *tip* is the
        lane's final commit; when *path* is absent from *final_ref*, a rename of
        it is looked up between the newest canceled commit and *tip* (default
        *final_ref*) and the target is judged at *tip*. *other_canceled* are
        further canceled commits: their lines never count as approved rework of a
        deletion's spot, though only *canceled_shas*' own lines and deletions are
        asked about.

        Raises:
            GitProbeError: any git read failed or its output could not be parsed.
        """
        if not canceled_shas:
            return CanceledSurvival(None, final_ref, added=False, deletion=False)
        try:
            return self._survival(canceled_shas, path, final_ref, floor=floor, tip=tip or final_ref, other_canceled=other_canceled)
        except (GitCommandError, ValueError) as exc:
            detail = exc.stderr.strip() if isinstance(exc, GitCommandError) else str(exc)
            raise GitProbeError(f"line attribution of '{path}' at {final_ref} failed: {detail}") from exc

    def _survival(self, canceled_shas: Sequence[str], path: str, final_ref: str, *, floor: str, tip: str, other_canceled: frozenset[str]) -> CanceledSurvival:
        final_path, judged_ref = self._final_location(canceled_shas[0], path, final_ref, tip)
        if final_path is None:
            return CanceledSurvival(None, judged_ref, added=False, deletion=False)
        canceled = frozenset(self._resolve(sha) for sha in canceled_shas)
        final_blame = self._forward_blame(judged_ref, final_path, floor)
        added = (
            any(line.commit in canceled and not is_trivial_line(line.text) for line in final_blame)
            or any(self._all_added_lines_kept(sha, path, final_blame) for sha in canceled_shas)
            or any(self._exact_change_kept(sha, path, final_blame) for sha in canceled_shas)
            or any(self._mode_or_empty_creation_kept(sha, path, judged_ref, final_path) for sha in canceled_shas)
        )
        if added:
            return CanceledSurvival(final_path, judged_ref, added=True, deletion=False)
        any_canceled = canceled | {self._resolve(sha) for sha in other_canceled}
        deletion = any(self._deletion_in_effect(sha, path, judged_ref, final_blame, any_canceled) for sha in canceled_shas)
        if not deletion:
            self._refuse_binary(canceled_shas, path)
        return CanceledSurvival(final_path, judged_ref, added=False, deletion=deletion)

    # -- reads -------------------------------------------------------------

    def _resolve(self, ref: str) -> str:
        if ref not in self._resolved:
            self._resolved[ref] = run_git(self._repo, "rev-parse", "--verify", f"{ref}^{{commit}}").stdout.decode("ascii").strip()
        return self._resolved[ref]

    def _parent(self, sha: str) -> str | None:
        """The first parent of *sha*, or ``None`` for a root commit."""
        if sha not in self._parents:
            tokens = run_git(self._repo, "rev-list", "--parents", "-n1", sha).stdout.split()
            if not tokens:
                raise ValueError(f"git rev-list --parents -n1 {sha} produced no output")
            self._parents[sha] = tokens[1].decode("ascii") if len(tokens) > 1 else None
        return self._parents[sha]

    def _final_location(self, newest_canceled: str, path: str, final_ref: str, tip: str) -> tuple[str | None, str]:
        """``(path the change lives at, ref to judge it at)``; ``(None, ref)`` when the path is gone."""
        if path_state_at(self._repo, final_ref, path) is not None:
            return path, final_ref
        renames = changed_entries(self._repo, newest_canceled, tip, renames=True, diff_filter=_RENAME, env=_git_env_with(_UNLIMITED_RENAMES))
        targets = sorted({str(entry.path) for entry in renames if entry.orig_path is not None and str(entry.orig_path) == path})
        if len(targets) > 1:
            raise ValueError(f"'{path}' was renamed to more than one path: {', '.join(targets)}")
        return (targets[0], tip) if targets else (None, final_ref)

    def _forward_blame(self, final_ref: str, path: str, floor: str) -> tuple[BlameLine, ...]:
        key = (final_ref, path, floor)
        if key not in self._forward:
            parent = self._parent(self._resolve(floor))
            revs = [f"{parent}..{final_ref}"] if parent is not None else [final_ref]
            self._forward[key] = blame_lines(self._repo, path, revs=revs, first_parent=True, ignore_whitespace=True, detect_moves=True)
        return self._forward[key]

    def _is_binary_change(self, sha: str, path: str) -> bool:
        """Did *sha* change *path* as a binary file (git prints ``-`` counts, or a root commit's blob holds a NUL)?"""
        parent = self._parent(self._resolve(sha))
        if parent is None:
            return b"\0" in (blob_at(self._repo, sha, path) or b"")
        return any(entry.added is None for entry in numstat_entries(self._repo, parent, sha, pathspecs=[path]))

    def _refuse_binary(self, canceled_shas: Sequence[str], path: str) -> None:
        """Refuse a binary path that no arm found surviving: git yields no hunks for it, so only blame judged it."""
        for sha in canceled_shas:
            if self._is_binary_change(sha, path):
                raise ValueError(f"canceled commit {sha} changed binary '{path}' and a later commit changed it too; line attribution cannot judge a binary file")

    def _canceled_hunks(self, sha: str, path: str, *, exact: bool = False) -> tuple[DiffHunk, ...]:
        """What canceled commit *sha* removed and added at *path*.

        Whitespace-only changes are dropped unless *exact* asks for the byte-for-byte diff.
        """
        key = (sha, path, exact)
        if key not in self._hunks:
            parent = self._parent(self._resolve(sha))
            if parent is None:
                # A root commit added the whole file; it removed nothing.
                blob = blob_at(self._repo, sha, path)
                lines = tuple(blob.split(b"\n")) if blob else ()
                self._hunks[key] = (DiffHunk(0, 0, 1, len(lines), (), lines),) if lines else ()
            else:
                self._hunks[key] = diff_hunks(self._repo, parent, sha, path, ignore_whitespace=not exact)
        return self._hunks[key]

    # -- the two arms ------------------------------------------------------

    def _all_added_lines_kept(self, sha: str, path: str, final_blame: Sequence[BlameLine]) -> bool:
        """The #5932 subset signal: every non-trivial line *sha* added is still in the final state."""
        added = {_normalized(text) for hunk in self._canceled_hunks(sha, path) for text in hunk.added if not is_trivial_line(text)}
        return bool(added) and added <= {_normalized(line.text) for line in final_blame}

    def _whitespace_only_lines(self, sha: str, path: str) -> tuple[list[bytes], list[bytes]]:
        """``(added, removed)`` non-blank lines of *sha*'s byte-for-byte diff that the ``-w`` judgement does not account for.

        A line is accounted for when its whitespace-normalised form is a non-trivial line of the
        ``-w`` diff of a change that has a real edit (which the ``-w`` arms judge); the rest are re-indents, line-ending
        changes and lone punctuation lines.
        """
        lines = [text for hunk in self._canceled_hunks(sha, path) for text in (*hunk.removed, *hunk.added)]
        # Trivial lines of a change that also has a real edit stay under the trivial-line policy (ignored).
        judged = {_normalized(text) for text in lines} if any(not is_trivial_line(text) for text in lines) else set()
        exact = self._canceled_hunks(sha, path, exact=True)
        added = [text for hunk in exact for text in hunk.added if text.strip() and _normalized(text) not in judged]
        removed = [text for hunk in exact for text in hunk.removed if text.strip() and _normalized(text) not in judged]
        return added, removed

    def _exact_change_kept(self, sha: str, path: str, final_blame: Sequence[BlameLine]) -> bool:
        """The part of a canceled change that the whitespace-blind arms cannot see, still in the final state byte for byte.

        A re-indent (meaning in Python, YAML, Makefiles), a line-ending change or a lone
        punctuation line is invisible to ``-w`` blame and diff and to the trivial-line filter, so
        those arms would read it as superseded, also when it rides along with a real edit. Such an
        added line stays live while the final state holds more copies of it than the commit's parent
        did (a copy that was already there, elsewhere, is not the change); a pure removal, while a
        removed line has fewer copies than before. An approved work package that later re-indents the
        same lines identically is indistinguishable from the canceled change and is refused too
        (deliberate fail-closed over-refusal).
        """
        added, removed = self._whitespace_only_lines(sha, path)
        if not added and not removed:
            return False
        parent = self._parent(self._resolve(sha))
        before = Counter((blob_at(self._repo, parent, path) or b"").split(b"\n")) if parent is not None else Counter()
        final = Counter(line.text for line in final_blame)
        if added:
            return any(final[text] > before[text] for text in set(added))
        return parent is not None and any(final[text] < before[text] for text in set(removed))

    def _mode_or_empty_creation_kept(self, sha: str, path: str, final_ref: str, final_path: str) -> bool:
        """A canceled change with no line to blame: a mode change, or an empty file's creation, still in effect.

        Neither adds nor removes a line, so blame and the hunks never see it. A mode change
        stays live while the final state has the mode it set; an empty file's creation, while
        the file still exists (what a survivor wrote into it is the survivor's, the file is not).
        Relies on the caller having returned early for a deleted final path (*final_path* exists).
        """
        entry = tree_entry(self._repo, sha, path)
        if entry is None:
            return False
        parent = self._parent(self._resolve(sha))
        before = tree_entry(self._repo, parent, path) if parent is not None else None
        if before is None:
            return not (blob_at(self._repo, sha, path) or b"")
        final = tree_entry(self._repo, final_ref, final_path)
        return entry.mode != before.mode and final is not None and final.mode == entry.mode

    def _deletion_in_effect(self, sha: str, path: str, final_ref: str, final_blame: Sequence[BlameLine], canceled: frozenset[str]) -> bool:
        """Is any non-trivial deletion of *sha* at *path* still in effect in *final_ref*?"""
        deletions = [hunk for hunk in self._canceled_hunks(sha, path) if any(not is_trivial_line(text) for text in hunk.removed)]
        parent = self._parent(self._resolve(sha))
        if parent is None or not deletions:
            return False  # nothing removed (a root commit removes nothing)
        survivors, start_len = self._surviving_start_lines(parent, path, final_ref)
        return any(self._hunk_in_effect(hunk, self._region(hunk, survivors, start_len, final_blame), canceled) for hunk in deletions)

    def _surviving_start_lines(self, start: str, path: str, final_ref: str) -> tuple[Mapping[int, int], int]:
        """``({line in start: line in final}, lines in start)`` for the start lines that survive to *final_ref*."""
        end = self._resolve(final_ref)
        reverse = blame_lines(self._repo, path, revs=[f"{start}..{end}"], reverse=True, first_parent=True, ignore_whitespace=True, detect_moves=True)
        survivors = {line.blamed_line: line.commit_line for line in reverse if line.commit == end}
        return survivors, len(reverse)

    @staticmethod
    def _region(hunk: DiffHunk, survivors: Mapping[int, int], start_len: int, final_blame: Sequence[BlameLine]) -> tuple[BlameLine, ...]:
        """The lines written since the start revision between the deletion's nearest surviving neighbours.

        File edges always count as surviving neighbours. Lines that survive from the
        start revision are left out, so the spot holds only what later commits wrote.
        """
        first, last = hunk.old_start, hunk.old_start + hunk.old_count - 1
        before = first - 1
        while before > 0 and before not in survivors:
            before -= 1
        after = last + 1
        while after <= start_len and after not in survivors:
            after += 1
        low = survivors.get(before, 0)
        high = survivors[after] if after <= start_len else len(final_blame) + 1
        # A neighbour that moved (``-M``) can stretch the spot over original lines that
        # survive untouched; those are nobody's rework, so only lines written since count.
        original = frozenset(survivors.values())
        return tuple(line for line in final_blame[low : max(low, high - 1)] if line.blamed_line not in original)

    @staticmethod
    def _hunk_in_effect(hunk: DiffHunk, region: Sequence[BlameLine], canceled: frozenset[str]) -> bool:
        """Is this canceled deletion still in effect in its spot of the final state?

        Ended when every removed line is back in the spot, or when approved work
        rewrote the spot (non-trivial lines, none still a canceled commit's). An empty
        spot, or one still holding a canceled commit's line, keeps it in effect.
        """
        removed = [_normalized(text) for text in hunk.removed if not is_trivial_line(text)]
        authored = [line for line in region if not is_trivial_line(line.text)]
        if _is_subsequence(removed, [_normalized(line.text) for line in authored]):
            return False  # every removed line is back in the spot
        return not authored or any(line.commit in canceled for line in authored)
