"""Shared non-vacuity examined-floor guard (#3273) + diff-scope resolution (#3147).

``related_validator.validate_related`` and
``relative_link_fixer.check_dead_body_links`` each implement the same
"examined-count floor" shape: walk a tree, count how many things were
examined, and raise :class:`RuntimeError` when that count falls short of a
caller-supplied minimum — a scope-narrowing regression (a missing tree, an
empty tree, or a parsing change that stops matching entries) must go **red**
immediately rather than silently reporting "0 findings" over 0 examined.
``related_validator.py`` even carried a comment self-acknowledging the two
call sites were mirrors of one another. This module is the single source for
that guard so the two modules stop drifting independently.

This is a distinct contract from the published-set floors of the docsite tests
(``tests/docs/test_docs_seo.py``), which are plain assertions, not a raising
guard.

This module also carries :func:`resolve_changed_files`, the shared diff-scope
resolver used by the related-edge, relative-link, audience, and description
blocking gates for their ``--changed-from`` mode (#3147, #3316). **B-WP02
(BLOCKER, see
``kitty-specs/ci-scoping-gate-reliability-01KZP80D/investigate-squad-findings.md``):
the fail-closed trigger is git base RESOLVABILITY, never changed-set
emptiness.** ``docs-freshness.yml`` fires on many non-``.md`` paths
(``src/specify_cli/**``, ``pyproject.toml``, …), so a legitimate PR often
changes zero ``docs/**/*.md`` files; a resolved diff that yields zero
in-scope files must be a clean PASS, not an error. Only a git subprocess
failure — an unresolvable/unfetched base ref — is fail-closed. Callers MUST
NOT route the diff-scope emptiness case through :func:`assert_examined_floor`
(that floor stays reserved for the whole-tree/``push`` mode).
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path


class GitDiffError(RuntimeError):
    """The git base ref could not be resolved (the sole diff-scope fail-closed trigger).

    Raised only on git subprocess failure (non-zero return code, missing
    ``git`` executable, or an unresolvable/unfetched base ref) — never on a
    successfully-resolved diff that happens to contain zero files (B-WP02).
    """


def resolve_changed_files(repo_root: Path, base_ref: str) -> list[str]:
    """Return repo-relative POSIX paths added/copied/modified/renamed since *base_ref*.

    Runs ``git diff --name-only -z --no-renames --diff-filter=ACMD
    <base_ref>...HEAD`` in *repo_root*. Rename detection is disabled so both
    the deleted source and added destination are returned; publication gates
    must see removal of a config path as well as its replacement. The
    three-dot form asks git to diff against the merge-base of *base_ref* and
    ``HEAD``, so a normal PR (base branch has moved on) reports only the PR's
    own changes.

    Fail-closed (B-WP02): a non-zero git return code — an unresolvable or
    unfetched *base_ref*, a missing ``git`` executable, or any other
    subprocess failure — raises :class:`GitDiffError`. This is the ONLY
    fail-closed trigger. An empty result list (base resolved, zero files
    changed) is a normal, successful return — callers must treat it as "zero
    changed files", never as an error.
    """
    try:
        result = subprocess.run(
            [
                "git",
                "diff",
                "--name-only",
                "-z",
                "--no-renames",
                "--diff-filter=ACMD",
                f"{base_ref}...HEAD",
            ],
            cwd=repo_root,
            capture_output=True,
            check=False,
        )
    except OSError as exc:
        raise GitDiffError(f"resolve_changed_files: could not run git (base_ref={base_ref!r}): {exc}") from exc
    if result.returncode != 0:
        stderr = os.fsdecode(result.stderr).strip()
        raise GitDiffError(f"resolve_changed_files: `git diff --name-only -z --no-renames {base_ref}...HEAD` failed (exit {result.returncode}): {stderr}")
    return [os.fsdecode(path) for path in result.stdout.split(b"\0") if path]


def assert_examined_floor(
    count: int,
    minimum: int,
    *,
    gate: str,
    noun: str,
    fr_id: str,
    extra: str | None = None,
) -> None:
    """Raise ``RuntimeError`` when ``count`` falls below the non-vacuity ``minimum``.

    Parameters
    ----------
    count:
        The number of items actually examined by the walk (e.g. files visited,
        edges resolved, links matched).
    minimum:
        The non-vacuity floor: the walk must examine at least this many items.
    gate:
        Name of the calling gate/function, prefixed to the message (e.g.
        ``"related_validator"`` or ``"check_dead_body_links"``).
    noun:
        Description of what was counted, including any scope context (e.g.
        ``"related edge(s) examined under {docs_root}"`` or ``"doc file(s)
        found under docs/"``).
    fr_id:
        The functional-requirement id this floor traces to (e.g. ``"FR-004"``
        or ``"FR-008"``), used to compose the trailing ``"(<fr_id>
        non-vacuity guard)"`` phrase every caller's tests match on.
    extra:
        Optional additional detail appended inside the trailing parenthetical
        (e.g. ``"possible misconfiguration"``), for callers whose original
        message carried a caller-specific caveat.

    Raises
    ------
    RuntimeError
        When ``count < minimum``.
    """
    if count < minimum:
        detail = f", {extra}" if extra else ""
        raise RuntimeError(f"{gate}: only {count} {noun} — expected at least {minimum} ({fr_id} non-vacuity guard{detail})")
